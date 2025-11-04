from typing import Dict, Any, List
import json
from langchain_core.messages import HumanMessage
from src.agents.game_agent import GameAgent
from src.models.schemas import EncounterState, ClinicalIteration, UtilizationReviewDecision
from src.utils.cpt_calculator import CPTCostCalculator
from src.utils.prompts import PROVIDER_SYSTEM_PROMPT


class ProviderAgent(GameAgent):
    """Provider agent for concurrent utilization review workflow."""

    SYSTEM_PROMPT = PROVIDER_SYSTEM_PROMPT

    def __init__(self, llm, config: Dict[str, Any] = None):
        super().__init__(llm, "Provider", config)
        self.cost_calculator = CPTCostCalculator()

    def order_tests(
        self,
        state: EncounterState,
        iteration: int,
        confidence: float,
        prior_iterations: List[ClinicalIteration]
    ) -> Dict[str, Any]:
        """
        Order diagnostic tests during concurrent review.

        Returns dict with:
        - tests_ordered: List[str]
        - differential: List[str]
        - confidence: float (0-1)
        - reasoning: str
        """
        prompt = f"""{self.SYSTEM_PROMPT}

CONCURRENT UTILIZATION REVIEW - Iteration {iteration}

PATIENT PRESENTATION:
{self._format_clinical_presentation(state)}

PRIOR TEST ORDERS:
{self._format_prior_iterations(prior_iterations)}

CURRENT CONFIDENCE: {confidence:.2f}

Your task: Order next round of tests to establish medical necessity for inpatient admission.
Focus on documenting severity indicators that justify inpatient level of care.

RESPONSE FORMAT (JSON):
{{
    "tests_ordered": ["<test_name>", ...],
    "differential": ["<diagnosis 1>", "<diagnosis 2>"],
    "confidence": <0.0-1.0>,
    "reasoning": "<clinical reasoning>"
}}

If workup complete, return empty tests_ordered list."""

        messages = [HumanMessage(content=prompt)]
        response = self.llm.invoke(messages)
        return self._parse_response(response.content)

    def submit_appeal(
        self,
        state: EncounterState,
        denial: UtilizationReviewDecision
    ) -> Dict[str, Any]:
        """
        Submit appeal with peer-to-peer justification.

        Returns dict with:
        - appeal_type: str
        - additional_evidence: str
        - severity_documentation: str
        - guideline_references: List[str]
        """
        prompt = f"""{self.SYSTEM_PROMPT}

APPEAL SUBMISSION - Peer-to-Peer Review

DENIAL REASON:
{denial.denial_reason}

PATIENT CLINICAL DATA:
{self._format_clinical_presentation(state)}

AVAILABLE EVIDENCE:
{self._format_clinical_evidence(state)}

Your task: Submit peer-to-peer appeal with specific clinical evidence demonstrating
medical necessity for inpatient level of care.

APPEAL REQUIREMENTS:
- Cite specific lab values and vital signs
- Document severity indicators and organ dysfunction
- Reference clinical guidelines or criteria
- Explain why observation level is insufficient

RESPONSE FORMAT (JSON):
{{
    "appeal_type": "peer_to_peer",
    "additional_evidence": "<specific clinical data>",
    "severity_documentation": "<severity indicators>",
    "guideline_references": ["<guideline>", ...]
}}"""

        messages = [HumanMessage(content=prompt)]
        response = self.llm.invoke(messages)
        return self._parse_response(response.content)

    def _format_clinical_presentation(self, state: EncounterState) -> str:
        presentation = state.clinical_presentation
        demographics = state.admission.patient_demographics
        return f"""Age: {demographics.age}
Sex: {demographics.sex}
Chief Complaint: {presentation.chief_complaint}
History: {presentation.history_of_present_illness}
Vitals: {presentation.vital_signs}
Physical Exam: {presentation.physical_exam_findings}
Medical History: {', '.join(presentation.medical_history)}"""

    def _format_prior_iterations(self, iterations: List[ClinicalIteration]) -> str:
        if not iterations:
            return "No prior test orders"

        lines = []
        for iter in iterations:
            lines.append(f"Iteration {iter.iteration_number}:")
            lines.append(f"  Tests ordered: {iter.tests_ordered}")
            lines.append(f"  Approved: {iter.tests_approved}")
            lines.append(f"  Denied: {iter.tests_denied}")
            lines.append(f"  Confidence: {iter.provider_confidence:.2f}")
        return "\n".join(lines)

    def _format_clinical_evidence(self, state: EncounterState) -> str:
        if not state.provider_documentation:
            return "No clinical documentation available"

        lines = []
        doc = state.provider_documentation

        if doc.lab_results:
            lines.append("LAB RESULTS:")
            for lab in doc.lab_results:
                lines.append(f"  - {lab.test_name}: {lab.result_summary}")

        if doc.imaging_results:
            lines.append("\nIMAGING RESULTS:")
            for img in doc.imaging_results:
                lines.append(f"  - {img.exam_name}: {img.impression}")

        if doc.severity_indicators:
            lines.append("\nSEVERITY INDICATORS:")
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
            "tests_ordered": [],
            "differential": [],
            "confidence": 0.5,
            "reasoning": "Error parsing response"
        }
