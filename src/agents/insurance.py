import json
from pathlib import Path
from .base import BaseAgent
from ..graph.state import GraphState
from ..utils.logger import get_logger
from langchain_core.messages import SystemMessage, HumanMessage

logger = get_logger(__name__)


INSURANCE_PROMPT = """You are an insurance coverage specialist.

Your responsibilities:
1. Answer only coverage/prior-authorization questions for proposed studies
2. Return exactly one of: "Approved", "Denied", or "Not required" plus a one-line reason
3. Use the provided policy rules to make deterministic decisions
4. If a policy isn't found, say "Not required (no prior auth for this indication)" unless in_network is false

Response format:
Decision: [Approved/Denied/Not required]
Reason: [One-line explanation]
"""


class InsuranceAgent(BaseAgent):
    def __init__(self, llm, policies_path: str = None):
        super().__init__(name="Insurance", llm=llm, system_prompt=INSURANCE_PROMPT)
        self.policies = self._load_policies(policies_path)
        
    def _load_policies(self, path: str = None) -> dict:
        if path and Path(path).exists():
            with open(path, 'r') as f:
                return json.load(f)
        else:
            return {
                "CT": {
                    "in_network": {"default": "Approved"},
                    "out_network": {"default": "Denied"}
                },
                "Ultrasound": {
                    "in_network": {"default": "Approved"},
                    "out_network": {"default": "Not required"}
                },
                "MRI": {
                    "in_network": {"default": "Approved", "requires_prior_auth": True},
                    "out_network": {"default": "Denied"}
                },
                "Labs": {
                    "in_network": {"default": "Not required"},
                    "out_network": {"default": "Not required"}
                }
            }
    
    def process(self, state: GraphState) -> GraphState:
        patient_ehr = state.get("patient_ehr")

        recent_request = None
        for msg in reversed(state["messages"]):
            if "@Insurance:" in msg.content:
                recent_request = msg.content.split("@Insurance:")[1].strip()
                break

        if not recent_request:
            recent_request = "Check coverage for proposed studies"

        workup = state["internal_context"].get("workup_recommendations", "")
        study_type = self._extract_study_type(workup + " " + recent_request)

        is_in_network = patient_ehr.insurance.get("in_network", True) if patient_ehr else True
        network_status = "in_network" if is_in_network else "out_network"

        decision = "Not required"
        reason = "No prior authorization needed for this indication"

        if study_type in self.policies:
            policy = self.policies[study_type].get(network_status, {})
            decision = policy.get("default", "Not required")

            if decision == "Approved" and policy.get("requires_prior_auth"):
                reason = f"Prior authorization approved for {study_type}"
            elif decision == "Denied":
                reason = f"{study_type} denied for out-of-network provider"
            elif decision == "Not required":
                reason = f"No prior authorization required for {study_type}"

        context = f"""
        Insurance Plan: {patient_ehr.insurance.get('plan', 'Standard') if patient_ehr else 'Standard'}
        Network Status: {'In-network' if is_in_network else 'Out-of-network'}
        Requested Study: {study_type}
        Request: {recent_request}

        Policy Decision: {decision}
        Reason: {reason}

        Provide the decision in the specified format.
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

        state["internal_context"]["insurance_decision"] = decision

        logger.info(f"Insurance provided decision: {decision} at turn {state['turn_count']}")

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