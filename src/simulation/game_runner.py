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
from src.utils.audit_logger import AuditLogger
from src.utils.prompts import (
    create_provider_prompt,
    create_payor_prompt,
    create_unified_provider_request_prompt,
    create_unified_payor_review_prompt,
    create_pa_request_generation_prompt,
    create_pa_decision_prompt,
    create_pa_appeal_submission_prompt,
    create_pa_appeal_decision_prompt,
    create_claim_adjudication_prompt,
    DEFAULT_PROVIDER_PARAMS,
    DEFAULT_PAYOR_PARAMS,
    MAX_ITERATIONS,
    CONFIDENCE_THRESHOLD
)


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
        confidence_threshold: float = None,
        max_iterations: int = None,
        azure_config: Dict[str, Any] = None
    ):
        self.confidence_threshold = confidence_threshold if confidence_threshold is not None else CONFIDENCE_THRESHOLD
        self.max_iterations = max_iterations if max_iterations is not None else MAX_ITERATIONS

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

        # initialize audit logger for this case
        self.audit_logger = AuditLogger(case_id=case["case_id"])

        # unified phase 2 workflow (all case types)
        state = self._phase_2_unified_pa(state, case)

        # phase 3: claims adjudication (if treatment was approved and delivered)
        if state.medication_authorization and state.medication_authorization.authorization_status == "approved":
            state = self._phase_3_medication_claims(state, case)

        # phase 4: financial settlement
        if state.medication_authorization:
            state = self._phase_4_medication_financial(state, case)

        if "ground_truth" in case:
            state.ground_truth_outcome = case["ground_truth"]["outcome"]
            state.simulation_matches_reality = (
                state.final_authorized_level == case["ground_truth"]["outcome"]
            )

        # finalize audit log and attach to state with behavioral parameters
        summary = self.audit_logger._generate_summary()
        summary["behavioral_parameters"] = {
            "provider": DEFAULT_PROVIDER_PARAMS,
            "payor": DEFAULT_PAYOR_PARAMS
        }
        self.audit_logger.finalize(summary)
        state.audit_log = self.audit_logger.get_audit_log()

        return state

    def _phase_2_unified_pa(
        self,
        state: EncounterState,
        case: Dict[str, Any]
    ) -> EncounterState:
        """
        unified phase 2: iterative PA workflow for all case types

        provider agent decides:
          - if confidence < threshold: request diagnostic test PA
          - if confidence >= threshold: request treatment PA

        continues until: treatment approved OR max iterations OR agent stops
        """
        import json

        state.review_date = state.admission_date

        prior_iterations = []
        treatment_approved = False

        for iteration_num in range(1, self.max_iterations + 1):
            # provider generates request based on confidence
            provider_system_prompt = create_provider_prompt(DEFAULT_PROVIDER_PARAMS)
            provider_user_prompt = create_unified_provider_request_prompt(
                state, case, iteration_num, prior_iterations
            )

            full_prompt = f"{provider_system_prompt}\n\n{provider_user_prompt}"
            messages = [HumanMessage(content=full_prompt)]
            response = self.provider.llm.invoke(messages)
            provider_response_text = response.content

            try:
                clean_response = provider_response_text
                if "```json" in clean_response:
                    clean_response = clean_response.split("```json")[1].split("```")[0].strip()
                elif "```" in clean_response:
                    clean_response = clean_response.split("```")[1].split("```")[0].strip()
                provider_request = json.loads(clean_response)
            except:
                provider_request = {
                    "confidence": 0.5,
                    "confidence_rationale": "unable to parse response",
                    "differential_diagnoses": [],
                    "request_type": "diagnostic_test",
                    "request_details": {}
                }

            confidence = provider_request.get("confidence", 0.5)
            request_type = provider_request.get("request_type")

            # log provider request
            self.audit_logger.log_interaction(
                phase="phase_2_pa",
                agent="provider",
                action=f"{request_type}_request",
                system_prompt=provider_system_prompt,
                user_prompt=provider_user_prompt,
                llm_response=provider_response_text,
                parsed_output=provider_request,
                metadata={
                    "iteration": iteration_num,
                    "confidence": confidence,
                    "request_type": request_type
                }
            )

            # payor reviews request
            payor_system_prompt = create_payor_prompt(DEFAULT_PAYOR_PARAMS)
            payor_user_prompt = create_unified_payor_review_prompt(
                state, provider_request, iteration_num
            )

            full_prompt = f"{payor_system_prompt}\n\n{payor_user_prompt}"
            messages = [HumanMessage(content=full_prompt)]
            response = self.payor.llm.invoke(messages)
            payor_response_text = response.content

            try:
                clean_response = payor_response_text
                if "```json" in clean_response:
                    clean_response = clean_response.split("```json")[1].split("```")[0].strip()
                elif "```" in clean_response:
                    clean_response = clean_response.split("```")[1].split("```")[0].strip()
                payor_decision = json.loads(clean_response)
            except:
                payor_decision = {
                    "authorization_status": "denied",
                    "denial_reason": "unable to parse response",
                    "criteria_used": "unknown",
                    "reviewer_type": "AI algorithm"
                }

            # log payor decision
            self.audit_logger.log_interaction(
                phase="phase_2_pa",
                agent="payor",
                action=f"{request_type}_review",
                system_prompt=payor_system_prompt,
                user_prompt=payor_user_prompt,
                llm_response=payor_response_text,
                parsed_output=payor_decision,
                metadata={
                    "iteration": iteration_num,
                    "request_type": request_type
                }
            )

            # track iteration for next round
            iteration_record = {
                "provider_request_type": request_type,
                "provider_confidence": confidence,
                "payor_decision": payor_decision["authorization_status"],
                "payor_denial_reason": payor_decision.get("denial_reason")
            }

            # handle decision outcomes
            if payor_decision["authorization_status"] == "approved":
                if request_type == "treatment":
                    # treatment approved - DONE
                    treatment_approved = True
                    state.medication_authorization = MedicationAuthorizationDecision(
                        reviewer_type=payor_decision.get("reviewer_type", "AI algorithm"),
                        authorization_status="approved",
                        denial_reason=None,
                        criteria_used=payor_decision.get("criteria_used", "Medical necessity"),
                        step_therapy_required=False,
                        missing_documentation=[],
                        approved_duration_days=90,
                        requires_peer_to_peer=False
                    )
                    break
                elif request_type == "diagnostic_test":
                    # diagnostic test approved - simulate running test and getting results
                    test_name = provider_request.get("request_details", {}).get("test_name")
                    test_results = case.get("available_test_results", {}).get("labs", {}).get(test_name, {})
                    iteration_record["test_results"] = test_results

            elif payor_decision["authorization_status"] == "denied":
                # request denied - provider will address in next iteration
                state.denial_occurred = True

            prior_iterations.append(iteration_record)

        # if treatment never approved, mark as denied
        if not treatment_approved:
            state.medication_authorization = MedicationAuthorizationDecision(
                reviewer_type="AI algorithm",
                authorization_status="denied",
                denial_reason="max iterations reached without approval",
                criteria_used="Medical necessity",
                step_therapy_required=False,
                missing_documentation=[],
                approved_duration_days=None,
                requires_peer_to_peer=False
            )
            state.denial_occurred = True

        return state

    def run_multiple_cases(self, cases: list[Dict[str, Any]]) -> list[EncounterState]:
        """run multiple cases sequentially"""
        return [self.run_case(case) for case in cases]

    def _phase_3_medication_claims(
        self,
        state: EncounterState,
        case: Dict[str, Any]
    ) -> EncounterState:
        """
        phase 2: prior authorization review (BEFORE treatment)

        provider submits pa request → payer evaluates → approve/deny
        if denied → provider appeals pa → payer reconsiders

        KEY: this is permission to treat, NOT payment guarantee
        """
        import json

        state.review_date = state.admission_date

        med_request = case.get("medication_request", {})

        # step 1: provider generates pa request
        provider_system_prompt = create_provider_prompt()
        provider_user_prompt = create_pa_request_generation_prompt(state, med_request, case)

        full_prompt = f"{provider_system_prompt}\n\n{provider_user_prompt}"
        messages = [HumanMessage(content=full_prompt)]
        response = self.provider.llm.invoke(messages)
        provider_response_text = response.content

        try:
            clean_response = provider_response_text
            if "```json" in clean_response:
                clean_response = clean_response.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_response:
                clean_response = clean_response.split("```")[1].split("```")[0].strip()

            provider_pa_request = json.loads(clean_response)
        except:
            provider_pa_request = {
                "pa_request_letter": "Unable to generate PA request",
                "step_therapy_documentation": "Error parsing response",
                "objective_findings": "None",
                "guideline_references": [],
                "medical_necessity_summary": "Error generating summary"
            }

        # log provider pa generation
        self.audit_logger.log_interaction(
            phase="phase_2_pa",
            agent="provider",
            action="pa_request_generation",
            system_prompt=provider_system_prompt,
            user_prompt=provider_user_prompt,
            llm_response=provider_response_text,
            parsed_output=provider_pa_request,
            metadata={"medication": med_request.get('medication_name')}
        )

        # step 2: payer reviews provider's generated pa request
        payor_system_prompt = create_payor_prompt()
        payor_user_prompt = create_pa_decision_prompt(state, provider_pa_request)

        full_prompt = f"{payor_system_prompt}\n\n{payor_user_prompt}"
        messages = [HumanMessage(content=full_prompt)]
        response = self.payor.llm.invoke(messages)
        response_text = response.content

        try:
            clean_response = response_text
            if "```json" in clean_response:
                clean_response = clean_response.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_response:
                clean_response = clean_response.split("```")[1].split("```")[0].strip()

            payor_decision = json.loads(clean_response)
        except:
            payor_decision = {
                "authorization_status": "denied",
                "denial_reason": "Unable to parse authorization response",
                "criteria_used": "Unknown",
                "reviewer_type": "AI algorithm"
            }

        # log payor decision
        self.audit_logger.log_interaction(
            phase="phase_2_pa",
            agent="payor",
            action="pa_decision",
            system_prompt=payor_system_prompt,
            user_prompt=payor_user_prompt,
            llm_response=response_text,
            parsed_output=payor_decision,
            metadata={"medication": med_request.get('medication_name')}
        )

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

        # if pa denied, provider appeals within phase 2
        if state.medication_authorization.authorization_status == "denied":
            state.denial_occurred = True
            state.appeal_date = state.review_date + timedelta(days=2)
            state.appeal_filed = True

            # provider creates pa appeal
            provider_system_prompt = create_provider_prompt()
            provider_user_prompt = create_pa_appeal_submission_prompt(state, med_request, case)

            full_prompt = f"{provider_system_prompt}\n\n{provider_user_prompt}"
            messages = [HumanMessage(content=full_prompt)]
            response = self.provider.llm.invoke(messages)
            response_text = response.content

            try:
                clean_response = response_text
                if "```json" in clean_response:
                    clean_response = clean_response.split("```json")[1].split("```")[0].strip()
                elif "```" in clean_response:
                    clean_response = clean_response.split("```")[1].split("```")[0].strip()
                provider_appeal = json.loads(clean_response)
            except:
                provider_appeal = {
                    "appeal_type": "written_appeal",
                    "additional_evidence": "Clinical evidence submitted",
                    "severity_documentation": "Disease severity documented",
                    "guideline_references": []
                }

            # log provider appeal submission with properly separated prompts
            self.audit_logger.log_interaction(
                phase="phase_2_pa_appeal",
                agent="provider",
                action="pa_appeal_submission",
                system_prompt=provider_system_prompt,
                user_prompt=provider_user_prompt,
                llm_response=response_text,
                parsed_output=provider_appeal,
                metadata={"denial_reason": state.medication_authorization.denial_reason}
            )

            appeal_submission = AppealSubmission(
                appeal_type=provider_appeal.get("appeal_type", "peer_to_peer"),
                additional_clinical_evidence=provider_appeal.get("additional_evidence", ""),
                severity_documentation=provider_appeal.get("severity_documentation", ""),
                guideline_references=provider_appeal.get("guideline_references", [])
            )

            # payer reviews pa appeal
            payor_appeal_system_prompt = create_payor_prompt()
            payor_appeal_user_prompt = create_pa_appeal_decision_prompt(state, provider_appeal)

            full_prompt = f"{payor_appeal_system_prompt}\n\n{payor_appeal_user_prompt}"
            messages = [HumanMessage(content=full_prompt)]
            response = self.payor.llm.invoke(messages)
            response_text = response.content

            try:
                clean_response = response_text
                if "```json" in clean_response:
                    clean_response = clean_response.split("```json")[1].split("```")[0].strip()
                elif "```" in clean_response:
                    clean_response = clean_response.split("```")[1].split("```")[0].strip()
                appeal_decision_data = json.loads(clean_response)
            except:
                appeal_decision_data = {
                    "appeal_outcome": "upheld_denial",
                    "decision_rationale": "Unable to parse appeal response",
                    "criteria_applied": "Formulary guidelines",
                    "reviewer_credentials": "Medical Director"
                }

            # log payor appeal decision with properly separated prompts
            self.audit_logger.log_interaction(
                phase="phase_2_pa_appeal",
                agent="payor",
                action="pa_appeal_decision",
                system_prompt=payor_appeal_system_prompt,
                user_prompt=payor_appeal_user_prompt,
                llm_response=response_text,
                parsed_output=appeal_decision_data,
                metadata={"appeal_type": provider_appeal.get("appeal_type")}
            )

            appeal_decision = AppealDecision(
                reviewer_credentials=appeal_decision_data.get("reviewer_credentials", "Medical Director"),
                appeal_outcome=appeal_decision_data["appeal_outcome"],
                final_authorized_level="approved" if appeal_decision_data["appeal_outcome"] == "approved" else "denied",
                decision_rationale=appeal_decision_data.get("decision_rationale", ""),
                criteria_applied=appeal_decision_data.get("criteria_applied", ""),
                peer_to_peer_conducted=appeal_decision_data.get("peer_to_peer_conducted", False)
            )

            # update state with pa appeal result
            state.appeal_record = AppealRecord(
                initial_denial=state.medication_authorization,
                appeal_submission=appeal_submission,
                appeal_decision=appeal_decision,
                appeal_filed=True,
                appeal_successful=(appeal_decision.appeal_outcome == "approved")
            )

            # if pa appeal successful, update authorization status
            if appeal_decision.appeal_outcome == "approved":
                state.medication_authorization.authorization_status = "approved"
                state.denial_occurred = False
                state.appeal_successful = True

        return state

    def _phase_3_medication_claims(
        self,
        state: EncounterState,
        case: Dict[str, Any]
    ) -> EncounterState:
        """
        phase 3: claims adjudication (AFTER treatment delivered)

        if pa approved → provider treats patient and submits claim
        payer reviews claim → approve/deny (INDEPENDENT from pa decision)
        if claim denied → provider appeals claim

        KEY: payer can deny claim even if pa was approved
        """
        import json

        # only process claims if pa was approved (or appealed successfully)
        if state.medication_authorization.authorization_status != "approved":
            # pa denied and not overturned - no treatment, no claim
            return state

        med_request = case.get("medication_request", {})
        cost_ref = case.get("cost_reference", {})

        # provider treats patient and submits claim
        claim_date = state.appeal_date if state.appeal_date else state.review_date
        claim_date = claim_date + timedelta(days=7)  # treatment + claim submission

        # payer reviews claim (AFTER treatment delivered)
        payor_claim_system_prompt = create_payor_prompt()
        payor_claim_user_prompt = create_claim_adjudication_prompt(state, med_request, cost_ref, case)

        full_prompt = f"{payor_claim_system_prompt}\n\n{payor_claim_user_prompt}"
        messages = [HumanMessage(content=full_prompt)]
        response = self.payor.llm.invoke(messages)
        response_text = response.content

        try:
            clean_response = response_text
            if "```json" in clean_response:
                clean_response = clean_response.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_response:
                clean_response = clean_response.split("```")[1].split("```")[0].strip()
            claim_decision = json.loads(clean_response)
        except:
            claim_decision = {
                "claim_status": "approved",
                "criteria_used": "Standard billing guidelines",
                "reviewer_type": "Claims adjudicator"
            }

        # log claim adjudication with properly separated prompts
        self.audit_logger.log_interaction(
            phase="phase_3_claims",
            agent="payor",
            action="claim_adjudication",
            system_prompt=payor_claim_system_prompt,
            user_prompt=payor_claim_user_prompt,
            llm_response=response_text,
            parsed_output=claim_decision,
            metadata={"medication": med_request.get('medication_name'), "pa_approved": True}
        )

        # store claim decision (reuse medication_authorization field but for claims)
        # TODO: add separate ClaimDecision model to schemas
        state.medication_authorization.authorization_status = claim_decision["claim_status"]
        if claim_decision["claim_status"] == "denied":
            state.medication_authorization.denial_reason = claim_decision.get("denial_reason")

            # claim denied - provider can appeal
            state.appeal_date = claim_date + timedelta(days=2)
            state.appeal_filed = True

            # provider appeals claim denial
            provider_claim_appeal_prompt = f"""You are a PROVIDER appealing a CLAIM DENIAL (Phase 3).

CLAIM WAS DENIED - you already treated the patient, but payer is denying payment.
Note: PA was approved, but claim was denied anyway.

CLAIM DENIAL REASON:
{claim_decision.get('denial_reason')}

TREATMENT PROVIDED:
- Medication: {med_request.get('medication_name')}
- Dosage: {med_request.get('dosage')}
- Clinical Rationale: {med_request.get('clinical_rationale')}

Your task: Submit claim appeal to get payment for treatment already delivered.

RESPONSE FORMAT (JSON):
{{
    "appeal_type": "peer_to_peer" or "written_appeal",
    "additional_documentation": "<what you're providing>",
    "billing_justification": "<why claim should be paid>",
    "guidelines_cited": ["<guideline 1>", ...]
}}"""

            messages = [HumanMessage(content=provider_claim_appeal_prompt)]
            response = self.provider.llm.invoke(messages)

            try:
                response_text = response.content
                if "```json" in response_text:
                    response_text = response_text.split("```json")[1].split("```")[0].strip()
                elif "```" in response_text:
                    response_text = response_text.split("```")[1].split("```")[0].strip()
                provider_claim_appeal = json.loads(response_text)
            except:
                provider_claim_appeal = {
                    "appeal_type": "written_appeal",
                    "additional_documentation": "Additional documentation submitted",
                    "billing_justification": "Claim meets billing criteria"
                }

            # payer reviews claim appeal
            payor_claim_appeal_prompt = f"""You are a PAYER MEDICAL DIRECTOR reviewing CLAIM APPEAL (Phase 3).

Provider appealing your claim denial. Treatment already delivered, they want payment.

ORIGINAL CLAIM DENIAL:
{claim_decision.get('denial_reason')}

PROVIDER APPEAL:
{provider_claim_appeal.get('additional_documentation')}

BILLING JUSTIFICATION:
{provider_claim_appeal.get('billing_justification')}

Your task: Reconsider claim decision based on appeal.

RESPONSE FORMAT (JSON):
{{
    "appeal_outcome": "approved" or "upheld_denial" or "partial_approval",
    "approved_amount": <dollar amount or null>,
    "decision_rationale": "<reasoning>",
    "criteria_applied": "<guidelines>"
}}"""

            messages = [HumanMessage(content=payor_claim_appeal_prompt)]
            response = self.payor.llm.invoke(messages)

            try:
                response_text = response.content
                if "```json" in response_text:
                    response_text = response_text.split("```json")[1].split("```")[0].strip()
                elif "```" in response_text:
                    response_text = response_text.split("```")[1].split("```")[0].strip()
                claim_appeal_decision = json.loads(response_text)
            except:
                claim_appeal_decision = {
                    "appeal_outcome": "upheld_denial",
                    "decision_rationale": "Unable to parse appeal"
                }

            # update state with claim appeal result
            if claim_appeal_decision["appeal_outcome"] == "approved":
                state.medication_authorization.authorization_status = "approved"
                state.appeal_successful = True
            elif claim_appeal_decision["appeal_outcome"] == "partial_approval":
                state.medication_authorization.authorization_status = "partial"

        return state

    def _phase_4_medication_financial(
        self,
        state: EncounterState,
        case: Dict[str, Any]
    ) -> EncounterState:
        """
        phase 4: financial settlement based on CLAIM outcome (not pa outcome)

        KEY: payment only happens if CLAIM approved in phase 3
        pa approval does NOT guarantee payment
        """
        state.settlement_date = (state.appeal_date or state.review_date) + timedelta(days=7)

        cost_ref = case.get("cost_reference", {})

        # payment based on CLAIM outcome (phase 3), not PA outcome (phase 2)
        claim_approved = (
            state.medication_authorization and
            state.medication_authorization.authorization_status == "approved"
        )

        if claim_approved:
            acquisition_cost = cost_ref.get("drug_acquisition_cost", 7800.0)
            admin_fee = cost_ref.get("administration_fee", 150.0)
            total_cost = acquisition_cost + admin_fee

            # typical ma copay: 20% patient, 80% plan
            patient_copay = total_cost * 0.20
            payer_payment = total_cost * 0.80
        else:
            # claim denied - provider gets $0 even though they already treated patient
            acquisition_cost = cost_ref.get("drug_acquisition_cost", 7800.0)
            admin_fee = cost_ref.get("administration_fee", 150.0)
            total_cost = acquisition_cost + admin_fee
            patient_copay = 0.0
            payer_payment = 0.0

        # administrative costs: pa review + claim review + appeals
        pa_review_cost = cost_ref.get("pa_review_cost", 75.0)
        claim_review_cost = cost_ref.get("claim_review_cost", 50.0)
        appeal_cost = 0.0
        if state.appeal_filed:
            appeal_cost = cost_ref.get("appeal_cost", 180.0)

        total_admin_cost = pa_review_cost + claim_review_cost + appeal_cost

        state.medication_financial = MedicationFinancialSettlement(
            medication_name=case.get("medication_request", {}).get("medication_name", "Unknown"),
            j_code=case.get("medication_request", {}).get("j_code"),
            acquisition_cost=acquisition_cost,
            administration_fee=admin_fee,
            total_billed=total_cost,
            payer_payment=payer_payment,
            patient_copay=patient_copay,
            prior_auth_cost=pa_review_cost + claim_review_cost,
            appeal_cost=appeal_cost,
            total_administrative_cost=total_admin_cost
        )

        return state
