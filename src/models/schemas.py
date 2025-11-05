from __future__ import annotations
from typing import List, Dict, Any, Optional, Literal, Union
from datetime import date
from pydantic import BaseModel, Field
import json


# pa type discriminator for different authorization workflows
class PAType:
    INPATIENT_ADMISSION = "inpatient_admission"
    SPECIALTY_MEDICATION = "specialty_medication"
    OUTPATIENT_IMAGING = "outpatient_imaging"
    POST_ACUTE_CARE = "post_acute_care"


class PatientDemographics(BaseModel):
    patient_id: str
    age: int
    sex: Literal["M", "F"]
    mrn: str


class InsuranceInfo(BaseModel):
    plan_type: Literal["MA", "Commercial", "Medicare_FFS", "Medicaid"]
    payer_name: str
    member_id: str
    group_number: Optional[str] = None
    authorization_required: bool = True


class AdmissionNotification(BaseModel):
    patient_demographics: PatientDemographics
    insurance: InsuranceInfo
    admission_date: date
    admission_source: Literal["ER", "Direct", "Transfer"]
    chief_complaint: str
    preliminary_diagnoses: List[str]
    expected_drg: Optional[str] = None
    expected_los_days: Optional[int] = None


class ClinicalPresentation(BaseModel):
    chief_complaint: str
    history_of_present_illness: str
    vital_signs: Dict[str, Any]
    physical_exam_findings: str
    medical_history: List[str]


class DiagnosticTest(BaseModel):
    test_name: str
    cpt_code: Optional[str] = None
    icd10_codes: List[str] = Field(default_factory=list)
    clinical_rationale: str


class LabResult(BaseModel):
    test_name: str
    result_summary: str


class ImagingResult(BaseModel):
    exam_name: str
    impression: str


class ClinicalIteration(BaseModel):
    iteration_number: int
    tests_ordered: List[str]
    tests_approved: List[str]
    tests_denied: List[str]
    denial_reasons: Dict[str, str] = Field(default_factory=dict)
    provider_confidence: float = Field(ge=0.0, le=1.0)
    differential_diagnoses: List[str] = Field(default_factory=list)


class ProviderClinicalRecord(BaseModel):
    iterations: List[ClinicalIteration] = Field(default_factory=list)
    final_diagnoses: List[str]
    lab_results: List[LabResult] = Field(default_factory=list)
    imaging_results: List[ImagingResult] = Field(default_factory=list)
    clinical_justification: str
    severity_indicators: List[str] = Field(default_factory=list)


class UtilizationReviewDecision(BaseModel):
    reviewer_type: str
    authorization_status: Literal["approved_inpatient", "denied_suggest_observation", "pending_info"]
    authorized_level_of_care: Literal["inpatient", "observation", "outpatient"]
    denial_reason: Optional[str] = None
    criteria_used: str
    criteria_met: bool = True
    missing_documentation: List[str] = Field(default_factory=list)
    requires_peer_to_peer: bool = False


class AppealSubmission(BaseModel):
    appeal_type: Literal["peer_to_peer", "written_appeal", "expedited"]
    additional_clinical_evidence: str
    severity_documentation: str
    guideline_references: List[str] = Field(default_factory=list)
    new_lab_results: List[LabResult] = Field(default_factory=list)
    new_imaging: List[ImagingResult] = Field(default_factory=list)


class AppealDecision(BaseModel):
    reviewer_credentials: str
    appeal_outcome: Literal["approved", "upheld_denial", "partial_approval"]
    final_authorized_level: Literal["inpatient", "observation", "outpatient"]
    decision_rationale: str
    criteria_applied: str
    peer_to_peer_conducted: bool = False
    peer_to_peer_notes: Optional[str] = None


class AppealRecord(BaseModel):
    initial_denial: UtilizationReviewDecision
    appeal_submission: Optional[AppealSubmission] = None
    appeal_decision: Optional[AppealDecision] = None
    appeal_filed: bool = False
    appeal_successful: bool = False


class ServiceLineItem(BaseModel):
    service_description: str
    cpt_or_drg_code: str
    billed_amount: float
    allowed_amount: float
    paid_amount: float


class DRGAssignment(BaseModel):
    drg_code: str
    drg_description: str
    relative_weight: float
    geometric_mean_los: float
    base_payment_rate: float
    total_drg_payment: float


class FinancialSettlement(BaseModel):
    line_items: List[ServiceLineItem] = Field(default_factory=list)
    drg_assignment: Optional[DRGAssignment] = None
    total_billed_charges: float
    total_allowed_amount: float
    payer_payment: float
    patient_responsibility: float
    outlier_payment: float = 0.0
    quality_adjustments: float = 0.0
    total_hospital_revenue: float
    estimated_hospital_cost: float
    hospital_margin: float


class EncounterState(BaseModel):
    case_id: str
    encounter_id: str = Field(default_factory=lambda: f"ENC-{date.today().strftime('%Y%m%d')}")

    # pa type discriminator
    pa_type: str = PAType.INPATIENT_ADMISSION

    admission_date: date
    review_date: Optional[date] = None
    appeal_date: Optional[date] = None
    settlement_date: Optional[date] = None

    admission: AdmissionNotification
    clinical_presentation: ClinicalPresentation

    # inpatient-specific fields
    provider_documentation: Optional[ProviderClinicalRecord] = None
    utilization_review: Optional[UtilizationReviewDecision] = None
    appeal_record: Optional[AppealRecord] = None
    financial_settlement: Optional[FinancialSettlement] = None
    final_authorized_level: Optional[Literal["inpatient", "observation", "outpatient"]] = None

    # medication-specific fields
    medication_request: Optional[MedicationRequest] = None
    medication_authorization: Optional[MedicationAuthorizationDecision] = None
    medication_financial: Optional[MedicationFinancialSettlement] = None

    denial_occurred: bool = False
    appeal_filed: bool = False
    appeal_successful: bool = False

    ground_truth_outcome: Optional[Union[Literal["inpatient", "observation"], Literal["approved", "denied"]]] = None
    simulation_matches_reality: Optional[bool] = None

    # audit log for LLM interactions
    audit_log: Optional["AuditLog"] = None


class Message(BaseModel):
    id: str
    session_id: str
    turn_id: int
    speaker: Literal["user", "agent"]
    agent: Optional[Literal["Provider", "Payer"]] = None
    role: Literal["system", "assistant", "user"]
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TestOrdered(BaseModel):
    test_name: str
    cpt_code: Optional[str] = None
    rationale: Optional[str] = None


# specialty medication pa models
class MedicationRequest(BaseModel):
    medication_name: str
    ndc_code: Optional[str] = None
    j_code: Optional[str] = None
    dosage: str
    frequency: str
    duration: str
    icd10_codes: List[str] = Field(default_factory=list)
    clinical_rationale: str
    prior_therapies_failed: List[str] = Field(default_factory=list)
    step_therapy_completed: bool = False


class MedicationAuthorizationDecision(BaseModel):
    reviewer_type: str
    authorization_status: Literal["approved", "denied", "pending_info"]
    denial_reason: Optional[str] = None
    criteria_used: str
    step_therapy_required: bool = False
    missing_documentation: List[str] = Field(default_factory=list)
    approved_quantity: Optional[str] = None
    approved_duration_days: Optional[int] = None
    requires_peer_to_peer: bool = False


class MedicationFinancialSettlement(BaseModel):
    medication_name: str
    j_code: Optional[str] = None
    acquisition_cost: float
    administration_fee: float = 0.0
    total_billed: float
    payer_payment: float
    patient_copay: float
    prior_auth_cost: float = 0.0
    appeal_cost: float = 0.0
    total_administrative_cost: float


# Audit Log Schemas for LLM Interaction Tracking
class LLMInteraction(BaseModel):
    """Single LLM prompt-response interaction."""
    interaction_id: str
    timestamp: str
    phase: Literal["phase_2_pa", "phase_2_pa_appeal", "phase_3_claims", "phase_4_financial"]
    agent: Literal["provider", "payor"]
    action: str  # e.g., "order_tests", "concurrent_review", "submit_appeal", "review_appeal"
    system_prompt: str
    user_prompt: str
    llm_response: str
    parsed_output: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AuditLog(BaseModel):
    """Complete audit log for a case simulation."""
    case_id: str
    simulation_start: str
    simulation_end: Optional[str] = None
    interactions: List[LLMInteraction] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)

    def save_to_markdown(self, filepath: str):
        """save audit log to markdown file with full interaction details"""
        lines = []

        # header
        lines.append(f"# Audit Log: {self.case_id}")
        lines.append("")
        lines.append(f"**Simulation Start:** {self.simulation_start}")
        lines.append(f"**Simulation End:** {self.simulation_end or 'In Progress'}")
        lines.append("")

        # summary
        if self.summary:
            lines.append("## Summary")
            lines.append("")
            lines.append(f"- **Total Interactions:** {self.summary.get('total_interactions', 0)}")
            lines.append(f"- **Duration:** {self.summary.get('simulation_duration_seconds', 0):.2f} seconds")
            lines.append("")

            if "interactions_by_phase" in self.summary:
                lines.append("**Interactions by Phase:**")
                for phase, count in self.summary["interactions_by_phase"].items():
                    lines.append(f"- {phase}: {count}")
                lines.append("")

            if "interactions_by_agent" in self.summary:
                lines.append("**Interactions by Agent:**")
                for agent, count in self.summary["interactions_by_agent"].items():
                    lines.append(f"- {agent}: {count}")
                lines.append("")

            if "behavioral_parameters" in self.summary:
                lines.append("**Behavioral Parameters:**")
                params = self.summary["behavioral_parameters"]
                if "provider" in params:
                    lines.append("- **Provider:**")
                    for key, value in params["provider"].items():
                        lines.append(f"  - {key}: {value}")
                if "payor" in params:
                    lines.append("- **Payor:**")
                    for key, value in params["payor"].items():
                        lines.append(f"  - {key}: {value}")
                lines.append("")

        lines.append("---")
        lines.append("")

        # detailed interactions
        for i, interaction in enumerate(self.interactions, 1):
            # interaction header
            phase_name = self._format_phase_name(interaction.phase)
            lines.append(f"## Interaction {i}: {phase_name}")
            lines.append("")
            lines.append(f"**Timestamp:** {interaction.timestamp}")
            lines.append(f"**Agent:** {interaction.agent.capitalize()}")
            lines.append(f"**Action:** {interaction.action.replace('_', ' ').title()}")
            lines.append("")

            # metadata
            if interaction.metadata:
                lines.append("**Metadata:**")
                for key, value in interaction.metadata.items():
                    if isinstance(value, (list, dict)):
                        lines.append(f"- {key}: `{json.dumps(value)}`")
                    else:
                        lines.append(f"- {key}: {value}")
                lines.append("")

            # system prompt
            lines.append("### System Prompt")
            lines.append("")
            lines.append("```")
            lines.append(interaction.system_prompt)
            lines.append("```")
            lines.append("")

            # user prompt
            lines.append("### User Prompt")
            lines.append("")
            lines.append("```")
            lines.append(interaction.user_prompt)
            lines.append("```")
            lines.append("")

            # llm response
            lines.append("### LLM Response")
            lines.append("")
            lines.append("```")
            lines.append(interaction.llm_response)
            lines.append("```")
            lines.append("")

            # parsed output
            lines.append("### Parsed Output")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(interaction.parsed_output, indent=2))
            lines.append("```")
            lines.append("")
            lines.append("---")
            lines.append("")

        # write to file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))

    def _format_phase_name(self, phase: str) -> str:
        """format phase identifier as readable name"""
        phase_names = {
            "phase_2_pa": "Phase 2: Prior Authorization",
            "phase_2_pa_appeal": "Phase 2: PA Appeal Process",
            "phase_3_claims": "Phase 3: Claims Adjudication",
            "phase_4_financial": "Phase 4: Financial Settlement"
        }
        return phase_names.get(phase, phase.replace("_", " ").title())
