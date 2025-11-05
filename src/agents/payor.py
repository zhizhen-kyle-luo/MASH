from typing import Dict, Any, List
import json
from langchain_core.messages import HumanMessage
from src.agents.game_agent import GameAgent
from src.models.schemas import EncounterState, AppealSubmission
from src.utils.cpt_calculator import CPTCostCalculator
from src.utils.prompts import create_payor_prompt


class PayorAgent(GameAgent):
    """Payer agent for concurrent utilization review and appeals."""

    SYSTEM_PROMPT = create_payor_prompt()

    def __init__(self, llm, config: Dict[str, Any] = None):
        super().__init__(llm, "Payor", config)
        self.cost_calculator = CPTCostCalculator()

    def concurrent_review(
        self,
        state: EncounterState,
        tests_ordered: List[str],
        iteration: int
    ) -> Dict[str, Any]:
        """
        Real-time test authorization during concurrent review.

        Returns dict with:
        - approved: List[str]
        - denied: List[str]
        - denial_reasons: Dict[test_name, reason]
        """
        prompt = f"""{self.SYSTEM_PROMPT}

CONCURRENT UTILIZATION REVIEW - Test Authorization

PROVIDER REQUESTING TESTS:
{self._format_test_list(tests_ordered)}

PATIENT CLINICAL DATA:
{self._format_patient_presentation(state)}

Your task: Authorize or deny tests based on medical necessity criteria.

AUTHORIZATION CRITERIA:
- Medical necessity for requested tests
- Appropriateness for clinical presentation
- Cost-effectiveness
- Alignment with evidence-based guidelines

RESPONSE FORMAT (JSON):
{{
    "approved": ["<test1>", ...],
    "denied": ["<test2>", ...],
    "denial_reasons": {{
        "<test2>": "<specific reason for denial>",
        ...
    }},
    "reasoning": "<authorization rationale>"
}}"""

        messages = [HumanMessage(content=prompt)]
        response = self.llm.invoke(messages)
        return self._parse_response(response.content)

    def make_authorization_decision(self, state: EncounterState) -> Dict[str, Any]:
        """
        Final utilization review decision on level of care.

        Returns dict with:
        - reviewer_type: str
        - authorization_status: str
        - authorized_level_of_care: str
        - denial_reason: Optional[str]
        - criteria_used: str
        - criteria_met: bool
        - requires_peer_to_peer: bool
        """
        prompt = f"""{self.SYSTEM_PROMPT}

UTILIZATION REVIEW DECISION - Level of Care Authorization

PATIENT CLINICAL DATA:
{self._format_patient_presentation(state)}

CLINICAL DOCUMENTATION:
{self._format_clinical_documentation(state)}

Your task: Determine if inpatient level of care is medically necessary or if observation
level is more appropriate.

AUTHORIZATION OPTIONS:
- approved_inpatient: Patient meets inpatient criteria
- denied_suggest_observation: Observation level sufficient
- pending_info: Need additional documentation

MEDICAL NECESSITY CRITERIA:
- Severity of illness (vital sign instability, organ dysfunction)
- Intensity of service required (IV medications, continuous monitoring)
- Risk of adverse outcome without inpatient care
- Expected length of stay and complexity

RESPONSE FORMAT (JSON):
{{
    "reviewer_type": "UM Nurse" or "Physician Advisor",
    "authorization_status": "approved_inpatient" or "denied_suggest_observation",
    "authorized_level_of_care": "inpatient" or "observation",
    "denial_reason": "<reason if denied>",
    "criteria_used": "MCG" or "InterQual" or "Milliman",
    "criteria_met": true or false,
    "requires_peer_to_peer": true or false,
    "reasoning": "<clinical rationale>"
}}"""

        messages = [HumanMessage(content=prompt)]
        response = self.llm.invoke(messages)
        return self._parse_response(response.content)

    def review_appeal(
        self,
        state: EncounterState,
        appeal: AppealSubmission
    ) -> Dict[str, Any]:
        """
        Review provider's appeal with peer-to-peer.

        Returns dict with:
        - reviewer_credentials: str
        - appeal_outcome: str
        - final_authorized_level: str
        - decision_rationale: str
        - criteria_applied: str
        - peer_to_peer_conducted: bool
        """
        prompt = f"""{self.SYSTEM_PROMPT}

PEER-TO-PEER APPEAL REVIEW

INITIAL DENIAL:
{state.utilization_review.denial_reason if state.utilization_review else "No denial on record"}

PROVIDER'S APPEAL:
Appeal Type: {appeal.appeal_type}
Additional Evidence: {appeal.additional_clinical_evidence}
Severity Documentation: {appeal.severity_documentation}
Guidelines Referenced: {', '.join(appeal.guideline_references)}

PATIENT CLINICAL DATA:
{self._format_patient_presentation(state)}

CLINICAL DOCUMENTATION:
{self._format_clinical_documentation(state)}

Your task: Conduct peer-to-peer review and make final authorization decision.

APPEAL REVIEW CRITERIA:
- Does new evidence demonstrate medical necessity?
- Are severity indicators sufficient for inpatient level?
- Do guideline references support provider's position?
- Would observation level create patient safety risk?

RESPONSE FORMAT (JSON):
{{
    "reviewer_credentials": "Board-Certified [Specialty]",
    "appeal_outcome": "approved" or "upheld_denial" or "partial_approval",
    "final_authorized_level": "inpatient" or "observation",
    "decision_rationale": "<detailed rationale>",
    "criteria_applied": "<criteria or guidelines used>",
    "peer_to_peer_conducted": true,
    "peer_to_peer_notes": "<discussion notes>"
}}"""

        messages = [HumanMessage(content=prompt)]
        response = self.llm.invoke(messages)
        return self._parse_response(response.content)

    def _format_test_list(self, test_names: List[str]) -> str:
        return "\n".join([f"- {test}" for test in test_names])

    def _format_patient_presentation(self, state: EncounterState) -> str:
        presentation = state.clinical_presentation
        demographics = state.admission.patient_demographics
        return f"""Age: {demographics.age}
Sex: {demographics.sex}
Chief Complaint: {presentation.chief_complaint}
Vitals: {presentation.vital_signs}
Physical Exam: {presentation.physical_exam_findings}
Medical History: {', '.join(presentation.medical_history)}"""

    def _format_clinical_documentation(self, state: EncounterState) -> str:
        if not state.provider_documentation:
            return "No clinical documentation available"

        lines = []
        doc = state.provider_documentation

        if doc.final_diagnoses:
            lines.append(f"Diagnoses: {', '.join(doc.final_diagnoses)}")

        if doc.lab_results:
            lines.append("\nLab Results:")
            for lab in doc.lab_results:
                lines.append(f"  - {lab.test_name}: {lab.result_summary}")

        if doc.imaging_results:
            lines.append("\nImaging:")
            for img in doc.imaging_results:
                lines.append(f"  - {img.exam_name}: {img.impression}")

        if doc.severity_indicators:
            lines.append("\nSeverity Indicators:")
            for indicator in doc.severity_indicators:
                lines.append(f"  - {indicator}")

        return "\n".join(lines)

    def _parse_response(self, content: str) -> Dict[str, Any]:
        try:
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end > start:
                json_str = content[start:end]
                return json.loads(json_str)
        except:
            pass

        return {
            "approved": [],
            "denied": [],
            "denial_reasons": {},
            "reasoning": "Error parsing response"
        }

    def make_decision(self, state: EncounterState) -> Dict[str, Any]:
        """Make strategic decision based on game state (stub implementation)."""
        return {"action": "review_authorization", "state": "utilization_review"}

    def calculate_payoff(self, state: EncounterState) -> float:
        """Calculate utility/payoff from game outcome (stub implementation)."""
        if state.financial_settlement:
            # Payor's payoff is negative of payment made
            return -state.financial_settlement.payer_payment
        return 0.0

    def calculate_metrics(self, state: EncounterState) -> Dict[str, float]:
        """Calculate agent-specific metrics (stub implementation)."""
        metrics = {
            "denial_issued": float(state.denial_occurred),
            "appeal_reviewed": float(state.appeal_filed),
            "appeal_upheld": float(not state.appeal_successful) if state.appeal_filed else 0.0
        }
        return metrics
