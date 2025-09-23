from .base import BaseAgent
from ..graph.state import GraphState
from ..utils.logger import get_logger
from langchain_core.messages import SystemMessage, HumanMessage

logger = get_logger(__name__)


URGENT_CARE_PROMPT = """You are a clinician doing initial evaluation in an urgent care setting.

Your responsibilities:
1. Review clinical summary from Concierge agent
2. Propose minimal, safe initial work-up (≤2 options) with clinical rationale
3. Use patient EHR data (vitals, history) provided - don't request additional information
4. Stay concise - one focused reply per request
5. Focus on immediate assessment needs based on clinical presentation

Guidelines:
- ALWAYS provide recommendations even with limited information
- Consider both lab work and imaging when appropriate
- Provide clear clinical reasoning
- Be decisive but safe in recommendations
- If clinical summary is limited, work with what you have
- Format: "Recommend: [test/imaging] because [brief rationale]"

IMPORTANT: Never say "insufficient information" - always provide some clinical recommendation based on available data.
"""


class UrgentCareAgent(BaseAgent):
    def __init__(self, llm):
        super().__init__(name="UrgentCare", llm=llm, system_prompt=URGENT_CARE_PROMPT)

    def process(self, state: GraphState) -> GraphState:
        patient_ehr = state.get("patient_ehr")
        clinical_summary = state.get("clinical_summary")

        # Extract request from Concierge
        recent_request = None
        for msg in reversed(state["messages"]):
            if "@UrgentCare:" in msg.content:
                recent_request = msg.content.split("@UrgentCare:")[1].strip()
                break

        if not recent_request:
            recent_request = "Please provide initial workup recommendations"

        # Build clinical context using clinical summary and EHR data
        if patient_ehr:
            patient_info = f"{patient_ehr.demographics.get('age', 'Unknown')}yo {patient_ehr.demographics.get('sex', 'Unknown')}"
            vitals_info = str(patient_ehr.vitals)
            history_info = ', '.join(patient_ehr.medical_history) if patient_ehr.medical_history else 'No significant history'
        else:
            patient_info = "Unknown demographics"
            vitals_info = "No vitals available"
            history_info = "No medical history available"

        clinical_context = f"""
        Patient: {patient_info}
        Vitals: {vitals_info}
        Medical History: {history_info}

        Clinical Summary: {clinical_summary.summary if clinical_summary else 'No clinical summary available'}
        Chief Complaint: {clinical_summary.chief_complaint if clinical_summary else 'Not specified'}
        Presenting Symptoms: {clinical_summary.presenting_symptoms if clinical_summary else 'Not specified'}
        Urgency Level: {clinical_summary.urgency_level if clinical_summary else 'routine'}

        Request: {recent_request}
        """

        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=clinical_context)
        ]

        response = self.llm.invoke(messages)
        content = response.content

        message = self.create_message(content, state)
        state["messages"].append(message)

        state["current_agent"] = self.name
        state["next_agent"] = "Concierge"
        state["turn_count"] += 1

        state["internal_context"]["workup_recommendations"] = content

        logger.info(f"UrgentCare provided workup recommendations at turn {state['turn_count']}")

        return state