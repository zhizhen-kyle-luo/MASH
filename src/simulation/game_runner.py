from typing import Dict, Any
from datetime import date, timedelta
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage
from src.models.schemas import (
    EncounterState,
    ProviderClinicalRecord,
    ClinicalIteration,
    UtilizationReviewDecision,
    AppealRecord,
    AppealSubmission,
    AppealDecision,
    FinancialSettlement,
    ServiceLineItem,
    DRGAssignment,
    LabResult,
    ImagingResult,
    MedicationAuthorizationDecision,
    MedicationFinancialSettlement,
    PAType
)
from src.agents.provider import ProviderAgent
from src.agents.payor import PayorAgent
from src.utils.cpt_calculator import CPTCostCalculator


class UtilizationReviewSimulation:
    """
    2-agent Provider-Payer concurrent utilization review simulation.

    Architecture:
    Phase 1: Admission & Insurance Notification
    Phase 2: Clinical Care & Concurrent Utilization Review (iterative)
    Phase 3: Denial & Appeal Process (if denied)
    Phase 4: Financial Resolution
    """

    def __init__(
        self,
        provider_llm: str = "gpt-4",
        payor_llm: str = "gpt-4",
        confidence_threshold: float = 0.9,
        max_iterations: int = 10,
        azure_config: Dict[str, Any] = None
    ):
        self.confidence_threshold = confidence_threshold
        self.max_iterations = max_iterations

        provider_model = self._create_llm(provider_llm, azure_config)
        payor_model = self._create_llm(payor_llm, azure_config)

        self.provider = ProviderAgent(provider_model)
        self.payor = PayorAgent(payor_model)
        self.cost_calculator = CPTCostCalculator()

    def _create_llm(self, model_name: str, azure_config: Dict[str, Any] = None):
        if azure_config:
            return AzureChatOpenAI(
                azure_endpoint=azure_config["endpoint"],
                api_key=azure_config["key"],
                azure_deployment=azure_config["deployment_name"],
                api_version="2024-08-01-preview",
                temperature=0.7
            )
        else:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model=model_name, temperature=0.7)

    def run_case(self, case: Dict[str, Any]) -> EncounterState:
        """
        Run single case through 4-phase utilization review workflow.

        Phase 1: Patient presentation (already complete in case data)
        Phase 2: Prior authorization review
        Phase 3: Appeal process if denied
        Phase 4: Financial settlement

        routes to appropriate workflow based on pa_type
        """
        pa_type = case.get("pa_type", PAType.INPATIENT_ADMISSION)

        state = EncounterState(
            case_id=case["case_id"],
            admission_date=case["admission"].admission_date,
            admission=case["admission"],
            clinical_presentation=case["clinical_presentation"],
            pa_type=pa_type
        )

        # route based on pa type
        if pa_type == PAType.SPECIALTY_MEDICATION:
            state.medication_request = case.get("medication_request_model")
            state = self._phase_2_medication_pa(state, case)
            if state.denial_occurred:
                state = self._phase_3_medication_appeal(state, case)
            state = self._phase_4_medication_financial(state, case)

        else:  # inpatient admission (default)
            state = self._phase_2_concurrent_review(state, case)
            if state.denial_occurred:
                state = self._phase_3_appeal_process(state, case)
            state = self._phase_4_financial_settlement(state, case)

        if "ground_truth" in case:
            state.ground_truth_outcome = case["ground_truth"]["outcome"]
            state.simulation_matches_reality = (
                state.final_authorized_level == case["ground_truth"]["outcome"]
            )

        return state

    def _phase_2_concurrent_review(
        self,
        state: EncounterState,
        case: Dict[str, Any]
    ) -> EncounterState:
        """
        Phase 2: Iterative clinical care with concurrent utilization review.

        Provider orders tests → Payer reviews → Provider reacts to denials
        Continues until confidence threshold or max iterations reached.
        """
        state.review_date = state.admission_date

        iterations = []
        current_confidence = 0.3
        available_tests = case.get("available_tests", {})

        for iteration_num in range(1, self.max_iterations + 1):
            provider_decision = self.provider.order_tests(
                state,
                iteration_num,
                current_confidence,
                iterations
            )

            if not provider_decision.get("tests_ordered"):
                break

            tests_ordered = provider_decision["tests_ordered"]

            payor_decision = self.payor.concurrent_review(
                state,
                tests_ordered,
                iteration_num
            )

            iteration_record = ClinicalIteration(
                iteration_number=iteration_num,
                tests_ordered=tests_ordered,
                tests_approved=payor_decision["approved"],
                tests_denied=payor_decision["denied"],
                denial_reasons=payor_decision.get("denial_reasons", {}),
                provider_confidence=provider_decision["confidence"],
                differential_diagnoses=provider_decision.get("differential", [])
            )

            iterations.append(iteration_record)
            current_confidence = provider_decision["confidence"]

            if current_confidence >= self.confidence_threshold:
                break

        lab_results = []
        imaging_results = []

        if "lab_results" in available_tests:
            lab_results = available_tests["lab_results"]
        if "imaging_results" in available_tests:
            imaging_results = available_tests["imaging_results"]

        state.provider_documentation = ProviderClinicalRecord(
            iterations=iterations,
            final_diagnoses=case["admission"].preliminary_diagnoses,
            lab_results=lab_results,
            imaging_results=imaging_results,
            clinical_justification=case["ground_truth"].get(
                "severity_indicators", []
            )[0] if case.get("ground_truth") else "Clinical justification pending",
            severity_indicators=case["ground_truth"].get(
                "severity_indicators", []
            ) if case.get("ground_truth") else []
        )

        final_ur_decision = self.payor.make_authorization_decision(state)

        state.utilization_review = UtilizationReviewDecision(
            reviewer_type=final_ur_decision["reviewer_type"],
            authorization_status=final_ur_decision["authorization_status"],
            authorized_level_of_care=final_ur_decision["authorized_level_of_care"],
            denial_reason=final_ur_decision.get("denial_reason"),
            criteria_used=final_ur_decision["criteria_used"],
            criteria_met=final_ur_decision["criteria_met"],
            requires_peer_to_peer=final_ur_decision.get("requires_peer_to_peer", False)
        )

        if state.utilization_review.authorization_status == "denied_suggest_observation":
            state.denial_occurred = True

        return state

    def _phase_3_appeal_process(
        self,
        state: EncounterState,
        case: Dict[str, Any]
    ) -> EncounterState:
        """
        Phase 3: Provider appeals denial through peer-to-peer review.
        """
        state.appeal_date = state.review_date + timedelta(days=1)
        state.appeal_filed = True

        appeal_submission_data = self.provider.submit_appeal(
            state,
            state.utilization_review
        )

        additional_evidence = appeal_submission_data.get("additional_evidence", "")
        if isinstance(additional_evidence, dict):
            additional_evidence = str(additional_evidence)

        severity_doc = appeal_submission_data.get("severity_documentation", "")
        if isinstance(severity_doc, dict):
            severity_doc = str(severity_doc)

        appeal_submission = AppealSubmission(
            appeal_type=appeal_submission_data.get("appeal_type", "peer_to_peer"),
            additional_clinical_evidence=additional_evidence,
            severity_documentation=severity_doc,
            guideline_references=appeal_submission_data.get("guideline_references", [])
        )

        appeal_decision_data = self.payor.review_appeal(
            state,
            appeal_submission
        )

        appeal_decision = AppealDecision(
            reviewer_credentials=appeal_decision_data["reviewer_credentials"],
            appeal_outcome=appeal_decision_data["appeal_outcome"],
            final_authorized_level=appeal_decision_data["final_authorized_level"],
            decision_rationale=appeal_decision_data["decision_rationale"],
            criteria_applied=appeal_decision_data["criteria_applied"],
            peer_to_peer_conducted=appeal_decision_data.get("peer_to_peer_conducted", False)
        )

        state.appeal_record = AppealRecord(
            initial_denial=state.utilization_review,
            appeal_submission=appeal_submission,
            appeal_decision=appeal_decision,
            appeal_filed=True,
            appeal_successful=(appeal_decision.appeal_outcome == "approved")
        )

        state.final_authorized_level = appeal_decision.final_authorized_level
        state.appeal_successful = state.appeal_record.appeal_successful

        return state

    def _phase_4_financial_settlement(
        self,
        state: EncounterState,
        case: Dict[str, Any]
    ) -> EncounterState:
        """
        Phase 4: Calculate DRG payment and financial settlement.
        """
        state.settlement_date = (state.appeal_date or state.review_date) + timedelta(days=30)

        if not state.final_authorized_level:
            state.final_authorized_level = state.utilization_review.authorized_level_of_care

        ground_truth = case.get("ground_truth_financial", {})
        drg_info = ground_truth.get("drg_assignment", {})

        if state.final_authorized_level == "inpatient":
            drg_code = drg_info.get("drg_code", "Unknown")
            drg_description = drg_info.get("drg_description", "Unspecified DRG")
            drg_payment = drg_info.get("payment_amount", 0.0)

            relative_weight = drg_payment / 3614.0 if drg_payment > 0 else 1.0

            drg_assignment = DRGAssignment(
                drg_code=drg_code,
                drg_description=drg_description,
                relative_weight=relative_weight,
                geometric_mean_los=5.0,
                base_payment_rate=3614.0,
                total_drg_payment=drg_payment
            )

            line_items = [
                ServiceLineItem(
                    service_description=f"DRG {drg_code} - {drg_description}",
                    cpt_or_drg_code=drg_code,
                    billed_amount=drg_payment,
                    allowed_amount=drg_payment,
                    paid_amount=drg_payment
                )
            ]

            total_payment = drg_payment
            patient_copay = ground_truth.get("if_approved_inpatient", {}).get("patient_copay", 350.0)
            hospital_cost = drg_payment * 0.75

        else:
            drg_assignment = None
            line_items = [
                ServiceLineItem(
                    service_description="Observation Services",
                    cpt_or_drg_code="99234",
                    billed_amount=2500.0,
                    allowed_amount=1800.0,
                    paid_amount=1800.0
                )
            ]
            total_payment = 1800.0
            patient_copay = 150.0
            hospital_cost = total_payment * 0.70

        state.financial_settlement = FinancialSettlement(
            line_items=line_items,
            drg_assignment=drg_assignment,
            total_billed_charges=total_payment,
            total_allowed_amount=total_payment,
            payer_payment=total_payment - patient_copay,
            patient_responsibility=patient_copay,
            total_hospital_revenue=total_payment,
            estimated_hospital_cost=hospital_cost,
            hospital_margin=total_payment - hospital_cost
        )

        return state

    def run_multiple_cases(self, cases: list[Dict[str, Any]]) -> list[EncounterState]:
        """Run multiple cases sequentially."""
        return [self.run_case(case) for case in cases]

    # medication pa workflow methods
    def _phase_2_medication_pa(
        self,
        state: EncounterState,
        case: Dict[str, Any]
    ) -> EncounterState:
        """
        phase 2 for specialty medication: prior authorization review

        provider submits med request → payer evaluates → approve/deny
        """
        import json

        state.review_date = state.admission_date

        med_request = case.get("medication_request", {})

        # payer reviews medication request
        payor_prompt = f"""You are a PAYER reviewing a specialty medication prior authorization request.

PATIENT:
- Age: {state.admission.patient_demographics.age}
- Sex: {state.admission.patient_demographics.sex}
- Diagnoses: {', '.join(state.clinical_presentation.medical_history)}
- Chief Complaint: {state.clinical_presentation.chief_complaint}

MEDICATION REQUEST:
- Drug: {med_request.get('medication_name')}
- Dosage: {med_request.get('dosage')}
- Frequency: {med_request.get('frequency')}
- ICD-10 Codes: {', '.join(med_request.get('icd10_codes', []))}

CLINICAL RATIONALE:
{med_request.get('clinical_rationale')}

STEP THERAPY:
- Prior Therapies Failed: {', '.join(med_request.get('prior_therapies_failed', []))}
- Step Therapy Completed: {med_request.get('step_therapy_completed', False)}

AVAILABLE LAB DATA:
{json.dumps(case.get('available_test_results', {}).get('labs', {}), indent=2)}

Your task: Evaluate this PA request using step therapy requirements and medical necessity criteria.

EVALUATION CRITERIA:
- Is step therapy adequately documented?
- Does clinical severity justify biologic/specialty medication?
- Are lab values sufficient to establish disease activity?
- Is the rationale compliant with formulary guidelines?

RESPONSE FORMAT (JSON):
{{
    "authorization_status": "approved" or "denied" or "pending_info",
    "denial_reason": "<specific reason if denied>",
    "criteria_used": "<guidelines applied>",
    "step_therapy_required": true/false,
    "missing_documentation": ["<item1>", ...],
    "approved_duration_days": <number or null>,
    "requires_peer_to_peer": true/false,
    "reviewer_type": "AI algorithm" or "Nurse reviewer"
}}"""

        messages = [HumanMessage(content=payor_prompt)]
        response = self.payor.llm.invoke(messages)

        try:
            response_text = response.content
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            payor_decision = json.loads(response_text)
        except:
            payor_decision = {
                "authorization_status": "denied",
                "denial_reason": "Unable to parse authorization response",
                "criteria_used": "Unknown",
                "reviewer_type": "AI algorithm"
            }

        state.medication_authorization = MedicationAuthorizationDecision(
            reviewer_type=payor_decision.get("reviewer_type", "AI algorithm"),
            authorization_status=payor_decision["authorization_status"],
            denial_reason=payor_decision.get("denial_reason"),
            criteria_used=payor_decision.get("criteria_used", "Formulary guidelines"),
            step_therapy_required=payor_decision.get("step_therapy_required", False),
            missing_documentation=payor_decision.get("missing_documentation", []),
            approved_duration_days=payor_decision.get("approved_duration_days"),
            requires_peer_to_peer=payor_decision.get("requires_peer_to_peer", False)
        )

        if state.medication_authorization.authorization_status == "denied":
            state.denial_occurred = True

        return state

    def _phase_3_medication_appeal(
        self,
        state: EncounterState,
        case: Dict[str, Any]
    ) -> EncounterState:
        """
        phase 3 for medication: provider appeals pa denial
        """
        import json

        state.appeal_date = state.review_date + timedelta(days=2)
        state.appeal_filed = True

        med_request = case.get("medication_request", {})
        denial = state.medication_authorization

        # provider submits appeal
        provider_prompt = f"""You are a PROVIDER appealing a specialty medication PA denial.

DENIAL REASON:
{denial.denial_reason}

PATIENT CLINICAL DATA:
- Age: {state.admission.patient_demographics.age}
- Medical History: {', '.join(state.clinical_presentation.medical_history)}
- Chief Complaint: {state.clinical_presentation.chief_complaint}

MEDICATION REQUESTED:
- Drug: {med_request.get('medication_name')}
- Clinical Rationale: {med_request.get('clinical_rationale')}

AVAILABLE EVIDENCE:
{json.dumps(case.get('available_test_results', {}), indent=2)}

Your task: Submit appeal with additional clinical evidence demonstrating medical necessity.

RESPONSE FORMAT (JSON):
{{
    "appeal_type": "peer_to_peer" or "written_appeal",
    "additional_evidence": "<specific clinical data points>",
    "severity_documentation": "<disease severity indicators>",
    "guideline_references": ["<guideline 1>", ...]
}}"""

        messages = [HumanMessage(content=provider_prompt)]
        response = self.provider.llm.invoke(messages)

        try:
            response_text = response.content
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            provider_appeal = json.loads(response_text)
        except:
            provider_appeal = {
                "appeal_type": "written_appeal",
                "additional_evidence": "Clinical evidence submitted",
                "severity_documentation": "Disease severity documented",
                "guideline_references": []
            }

        appeal_submission = AppealSubmission(
            appeal_type=provider_appeal.get("appeal_type", "peer_to_peer"),
            additional_clinical_evidence=provider_appeal.get("additional_evidence", ""),
            severity_documentation=provider_appeal.get("severity_documentation", ""),
            guideline_references=provider_appeal.get("guideline_references", [])
        )

        # payer reviews appeal
        payor_appeal_prompt = f"""You are a PAYER MEDICAL DIRECTOR reviewing a medication PA appeal.

ORIGINAL DENIAL:
{denial.denial_reason}

PROVIDER APPEAL:
{provider_appeal.get('additional_evidence')}

SEVERITY DOCUMENTATION:
{provider_appeal.get('severity_documentation')}

GUIDELINES CITED:
{', '.join(provider_appeal.get('guideline_references', []))}

CLINICAL CONTEXT:
{json.dumps(case.get('available_test_results', {}), indent=2)}

Your task: Re-evaluate PA decision based on appeal evidence.

RESPONSE FORMAT (JSON):
{{
    "appeal_outcome": "approved" or "upheld_denial",
    "decision_rationale": "<reasoning>",
    "criteria_applied": "<guidelines>",
    "peer_to_peer_conducted": true/false,
    "reviewer_credentials": "Medical Director, Board Certified <specialty>"
}}"""

        messages = [HumanMessage(content=payor_appeal_prompt)]
        response = self.payor.llm.invoke(messages)

        try:
            response_text = response.content
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            appeal_decision_data = json.loads(response_text)
        except:
            appeal_decision_data = {
                "appeal_outcome": "upheld_denial",
                "decision_rationale": "Unable to parse appeal response",
                "criteria_applied": "Formulary guidelines",
                "reviewer_credentials": "Medical Director"
            }

        appeal_decision = AppealDecision(
            reviewer_credentials=appeal_decision_data.get("reviewer_credentials", "Medical Director"),
            appeal_outcome=appeal_decision_data["appeal_outcome"],
            final_authorized_level="approved" if appeal_decision_data["appeal_outcome"] == "approved" else "denied",
            decision_rationale=appeal_decision_data.get("decision_rationale", ""),
            criteria_applied=appeal_decision_data.get("criteria_applied", ""),
            peer_to_peer_conducted=appeal_decision_data.get("peer_to_peer_conducted", False)
        )

        state.appeal_record = AppealRecord(
            initial_denial=denial,
            appeal_submission=appeal_submission,
            appeal_decision=appeal_decision,
            appeal_filed=True,
            appeal_successful=(appeal_decision.appeal_outcome == "approved")
        )

        state.appeal_successful = state.appeal_record.appeal_successful

        return state

    def _phase_4_medication_financial(
        self,
        state: EncounterState,
        case: Dict[str, Any]
    ) -> EncounterState:
        """
        phase 4 for medication: calculate drug costs + administrative burden
        """
        state.settlement_date = (state.appeal_date or state.review_date) + timedelta(days=7)

        ground_truth = case.get("ground_truth_financial", {})
        med_costs = ground_truth.get("medication_costs", {})
        admin_costs = ground_truth.get("administrative_costs", {})

        # determine if medication was ultimately approved
        approved = False
        if state.medication_authorization and state.medication_authorization.authorization_status == "approved":
            approved = True
        elif state.appeal_successful:
            approved = True

        if approved:
            acquisition_cost = med_costs.get("drug_acquisition_cost", 7800.0)
            admin_fee = med_costs.get("administration_fee", 150.0)
            total_cost = acquisition_cost + admin_fee

            # typical ma copay structure: 20% patient, 80% plan
            patient_copay = total_cost * 0.20
            payer_payment = total_cost * 0.80
        else:
            acquisition_cost = 0.0
            admin_fee = 0.0
            total_cost = 0.0
            patient_copay = 0.0
            payer_payment = 0.0

        # administrative costs
        pa_cost = admin_costs.get("provider_pa_submission", 50.0) + admin_costs.get("payer_pa_review", 25.0)
        appeal_cost = 0.0
        if state.appeal_filed:
            appeal_cost = admin_costs.get("provider_appeal_p2p", 180.0) + admin_costs.get("payer_appeal_review", 120.0)

        state.medication_financial = MedicationFinancialSettlement(
            medication_name=case.get("medication_request", {}).get("medication_name", "Unknown"),
            j_code=case.get("medication_request", {}).get("j_code"),
            acquisition_cost=acquisition_cost,
            administration_fee=admin_fee,
            total_billed=total_cost,
            payer_payment=payer_payment,
            patient_copay=patient_copay,
            prior_auth_cost=pa_cost,
            appeal_cost=appeal_cost,
            total_administrative_cost=pa_cost + appeal_cost
        )

        return state
