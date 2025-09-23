import json
from pathlib import Path
from datetime import datetime, timedelta
from .base import BaseAgent
from ..graph.state import GraphState
from ..utils.logger import get_logger
from langchain_core.messages import SystemMessage, HumanMessage

logger = get_logger(__name__)


COORDINATOR_PROMPT = """You are a scheduling coordinator for healthcare appointments.

Your responsibilities:
1. Return the earliest slot(s) that match the patient's constraints
2. Consider in-network modality requirements and patient time preferences
3. If no same-day slot is available, state a simple monitoring plan
4. Be specific about times and dates

Response format:
- Available: [Day] at [Time] for [Service]
- OR: No same-day availability. Monitoring for cancellations. Next available: [Day] at [Time]
"""


class CoordinatorAgent(BaseAgent):
    def __init__(self, llm, availability_path: str = None):
        super().__init__(name="Coordinator", llm=llm, system_prompt=COORDINATOR_PROMPT)
        self.availability = self._load_availability(availability_path)
        
    def _load_availability(self, path: str = None) -> dict:
        if path and Path(path).exists():
            with open(path, 'r') as f:
                return json.load(f)
        else:
            return {
                "CT": {
                    "today": ["14:30", "16:00"],
                    "tomorrow": ["09:00", "10:30", "14:00", "15:30"]
                },
                "Ultrasound": {
                    "today": ["15:00"],
                    "tomorrow": ["08:30", "11:00", "13:30", "16:00"]
                },
                "MRI": {
                    "today": [],
                    "tomorrow": ["11:30", "14:30"]
                },
                "Labs": {
                    "today": ["immediate"],
                    "tomorrow": ["08:00", "09:00", "10:00"]
                }
            }
    
    def process(self, state: GraphState) -> GraphState:
        patient_ehr = state.get("patient_ehr")

        recent_request = None
        for msg in reversed(state["messages"]):
            if "@Coordinator:" in msg.content:
                recent_request = msg.content.split("@Coordinator:")[1].strip()
                break

        if not recent_request:
            recent_request = "Find earliest available appointment"

        workup = state["internal_context"].get("workup_recommendations", "")
        insurance_decision = state["internal_context"].get("insurance_decision", "Approved")

        study_type = self._extract_study_type(workup + " " + recent_request)
        prefer_morning = patient_ehr.constraints.get("prefer_morning", False) if patient_ehr else False
        slots = self._find_slots(study_type, prefer_morning, insurance_decision)

        context = f"""
        Requested Service: {study_type}
        Insurance Status: {insurance_decision}
        Patient Preference: {'Morning preferred' if prefer_morning else 'No time preference'}
        Request: {recent_request}

        Available Slots:
        {slots}

        Provide scheduling options based on the available slots.
        """

        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=context)
        ]

        response = self.llm.invoke(messages)
        content = response.content

        message = self.create_message(content, state)
        state["messages"].append(message)

        state["current_agent"] = self.name
        state["next_agent"] = "Concierge"
        state["turn_count"] += 1

        state["internal_context"]["scheduled_appointment"] = slots

        logger.info(f"Coordinator provided scheduling options at turn {state['turn_count']}")

        return state
    
    def _extract_study_type(self, text: str) -> str:
        text_lower = text.lower()

        if "ct" in text_lower or "computed tomography" in text_lower:
            return "CT"
        elif "ultrasound" in text_lower or "sonography" in text_lower:
            return "Ultrasound"
        elif "mri" in text_lower or "magnetic resonance" in text_lower:
            return "MRI"
        elif "lab" in text_lower or "blood" in text_lower:
            return "Labs"
        else:
            return "General"

    def _find_slots(self, study_type: str, prefer_morning: bool, insurance_status: str) -> str:
        if insurance_status == "Denied":
            return "Cannot schedule: Insurance authorization denied. Please contact insurance or consider self-pay options."

        slots = self.availability.get(study_type, {})

        today_slots = slots.get("today", [])
        tomorrow_slots = slots.get("tomorrow", [])

        if prefer_morning:
            today_slots = [s for s in today_slots if s < "12:00" or s == "immediate"]
            tomorrow_slots = [s for s in tomorrow_slots if s < "12:00"]

        result = []

        if today_slots:
            result.append(f"Today: {', '.join(today_slots)}")
        else:
            result.append("No same-day availability")

        if tomorrow_slots:
            result.append(f"Tomorrow: {', '.join(tomorrow_slots)}")

        if not today_slots and not tomorrow_slots:
            result.append("Monitoring for cancellations. Will notify if earlier slot becomes available.")

        return "\n".join(result)