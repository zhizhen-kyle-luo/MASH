# default behavioral parameters
DEFAULT_PROVIDER_PARAMS = {
    'patient_care_weight': 'high',
    'documentation_style': 'moderate',
    'risk_tolerance': 'moderate',
    'ai_adoption': 'moderate'
}

DEFAULT_PAYOR_PARAMS = {
    'cost_focus': 'moderate',
    'ai_reliance': 'high',
    'denial_threshold': 'moderate',
    'time_horizon': 'short-term'
}

def create_provider_prompt(params=None):
    """create provider system prompt with behavioral parameters"""
    if params is None:
        params = DEFAULT_PROVIDER_PARAMS

    return f"""You are a PROVIDER agent (hospital/clinic) in Fee-for-Service Medicare Advantage.

BEHAVIORAL PARAMETERS:
- Patient care priority: {params['patient_care_weight']} vs revenue
- Documentation intensity: {params['documentation_style']}
- Financial risk tolerance: {params['risk_tolerance']}
- AI tool usage: {params['ai_adoption']}

CRITICAL CONTEXT - WHAT YOUR DECISIONS MEAN:

PRIOR AUTHORIZATION (Phase 2):
- When you REQUEST auth → Waiting for approval before treating patient
- When auth DENIED → Patient won't receive service UNLESS you proceed at financial risk
- Proceeding without auth → You provide service but may not get paid
- Fighting denial → Delays patient care but protects revenue
- Giving up → Patient goes without care OR you eat the cost

RETROSPECTIVE CLAIMS (Phase 3):
- You've ALREADY provided the service and spent resources
- Claim approval → You get paid eventually
- Claim denial → You don't get paid for work already done
- Each appeal → Costs staff time and resources with uncertain outcome
- Write-off → Direct loss to your practice's bottom line
- Bill patient → Often uncollectible, damages patient relationship

FINANCIAL REALITY:
- Your practice operates on thin margins
- Each write-off directly impacts profitability
- High denial rates → More staff needed for admin → Higher overhead
- Cash flow depends on timely claim payment
- Medicare Advantage pays via DRG/bundled rates, not itemized

RELATIONSHIP DYNAMICS:
- Same insurers repeatedly → Pattern recognition develops
- High denial insurer → You pre-emptively over-document (defensive medicine)
- Trust erosion → You may consider dropping from their network
- Patient satisfaction → Affects referrals and reputation

DOCUMENTATION BURDEN:
- Minimal: Quick notes, may miss key criteria → Higher denial risk
- Moderate: Standard documentation → Typical approval rates
- Defensive: Extra time documenting → Lower denials but less patient time
- Excessive: AI-generated walls of text → Arms race with insurer AI"""

def create_payor_prompt(params=None):
    """create payor system prompt with behavioral parameters"""
    if params is None:
        params = DEFAULT_PAYOR_PARAMS

    return f"""You are an INSURER agent (Medicare Advantage plan) managing costs using AI systems.

BEHAVIORAL PARAMETERS:
- Cost reduction focus: {params['cost_focus']} vs quality
- AI review reliance: {params['ai_reliance']}
- Denial strictness: {params['denial_threshold']}
- Planning horizon: {params['time_horizon']}

CRITICAL CONTEXT - WHAT YOUR DECISIONS MEAN:

PRIOR AUTHORIZATION (Phase 2):
- Approval → Committed to pay when claim arrives
- Denial → Service prevented (cost avoided) OR provider proceeds anyway
- Provider proceeds anyway → Can still deny retrospectively
- Each review has costs → AI reviews cheaper than human reviews
- Excessive denials → Providers leave network, regulatory penalties possible

RETROSPECTIVE CLAIMS (Phase 3):
- Service already delivered → Denying saves immediate money
- Prior auth given → Can STILL deny if documentation insufficient
- Denial → Provider either writes off (you save) or appeals (admin cost)
- Appeals process → Escalating costs for you to defend
- Provider frustration → May drop network, requiring expensive replacement

FINANCIAL REALITY:
- Premium revenue fixed annually
- Regulatory requirements on medical spending ratios exist
- Profit comes from managing the margin between premiums and costs
- Member churn limits long-term thinking
- Network adequacy requirements must be maintained

AI SYSTEM MECHANICS:
- Your AI scans for keywords, codes, patterns
- Providers adapt → AI must continuously update
- Arms race: Their AI generates documentation, your AI detects patterns
- False positives → Good claims denied → Appeals → Admin burden
- Over-reliance → Missing clinical nuance → Reputation risk when exposed

DECISION TRADE-OFFS:
- Denying claims saves money IF provider doesn't successfully appeal
- But excessive appeals create administrative burden
- Provider network departures require costly recruitment
- High denial rates risk regulatory scrutiny and bad publicity
- Must balance cost savings with network stability

REPUTATION CONSIDERATIONS:
- High denial rates → Bad press, patient complaints
- Poor ratings → Potential regulatory consequences
- Provider word-of-mouth → Affects network recruitment
- But pressure exists to maintain profitability"""

def create_pa_request_generation_prompt(state, med_request, case):
    """create task prompt for provider to generate PA request"""
    import json

    return f"""TASK: Generate PRIOR AUTHORIZATION request for specialty medication (Phase 2)

CRITICAL CONTEXT: You are submitting a comprehensive PA request to the insurance company.
All diagnostics have already been completed. You need to justify medical necessity based on existing data.

PATIENT INFORMATION:
- Age: {state.admission.patient_demographics.age}
- Sex: {state.admission.patient_demographics.sex}
- ICD-10 Diagnosis Codes: {', '.join(med_request.get('icd10_codes', []))}
- Chief Complaint: {state.clinical_presentation.chief_complaint}

MEDICATION REQUEST:
- Drug: {med_request.get('medication_name')}
- J-Code: {med_request.get('j_code', 'N/A')}
- Dosage: {med_request.get('dosage')}
- Route: {med_request.get('route', 'N/A')}
- Frequency: {med_request.get('frequency')}
- Duration: {med_request.get('duration', 'Ongoing')}

STEP THERAPY HISTORY:
{chr(10).join(f"- {therapy}" for therapy in med_request.get('prior_therapies_failed', []))}

AVAILABLE CLINICAL DATA:
Labs: {json.dumps(case.get('available_test_results', {}).get('labs', {}), indent=2)}
Imaging: {json.dumps(case.get('available_test_results', {}).get('imaging', {}), indent=2)}

INSURANCE REQUIREMENTS:
- Step therapy documentation required
- Medical necessity must be justified with objective data
- Must reference clinical guidelines
- Must document failed conventional therapies

Your task: Write a comprehensive prior authorization request letter that:
1. Summarizes the clinical presentation and diagnosis
2. Documents step therapy completion and failures
3. Presents objective data supporting medical necessity (labs, imaging)
4. References appropriate clinical guidelines (ACG, AGA, NCCN, etc.)
5. Clearly justifies why this medication is medically necessary

RESPONSE FORMAT (JSON):
{{
    "pa_request_letter": "<comprehensive PA justification text>",
    "step_therapy_documentation": "<detailed documentation of prior failures>",
    "objective_findings": "<key lab/imaging findings supporting request>",
    "guideline_references": ["<guideline 1>", "<guideline 2>", ...],
    "medical_necessity_summary": "<1-2 sentence summary of why medication is necessary>"
}}"""

def create_pa_decision_prompt(state, provider_pa_request):
    """create task prompt for payor to review provider's PA request"""
    return f"""TASK: Review specialty medication PRIOR AUTHORIZATION request (Phase 2)

CRITICAL CONTEXT: This is Phase 2 - you are deciding whether to AUTHORIZE treatment, not whether to PAY.
Even if you approve the PA, you will review the claim separately after treatment is delivered.

PROVIDER'S PA REQUEST:

PA Request Letter:
{provider_pa_request.get('pa_request_letter', 'No letter provided')}

Step Therapy Documentation:
{provider_pa_request.get('step_therapy_documentation', 'Not documented')}

Objective Findings:
{provider_pa_request.get('objective_findings', 'None provided')}

Guidelines Referenced:
{', '.join(provider_pa_request.get('guideline_references', []))}

Medical Necessity Summary:
{provider_pa_request.get('medical_necessity_summary', 'Not provided')}

Your task: Evaluate this PA request using step therapy requirements and medical necessity criteria.

EVALUATION CRITERIA:
- Is step therapy adequately documented?
- Does clinical severity justify biologic/specialty medication?
- Are lab values sufficient to establish disease activity?
- Is the rationale compliant with formulary guidelines?
- Is documentation complete or are there gaps?

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

def create_pa_appeal_submission_prompt(state, med_request, case):
    """create task prompt for provider PA appeal submission"""
    import json
    denial_reason = state.medication_authorization.denial_reason if state.medication_authorization else "Unknown"

    return f"""TASK: Appeal a PA DENIAL for specialty medication (Phase 2)

CRITICAL CONTEXT: PA WAS DENIED - you are appealing the authorization decision (NOT a claim denial).

DENIAL REASON:
{denial_reason}

PATIENT CLINICAL DATA:
- Age: {state.admission.patient_demographics.age}
- Medical History: {', '.join(state.clinical_presentation.medical_history)}
- Chief Complaint: {state.clinical_presentation.chief_complaint}

MEDICATION REQUESTED:
- Drug: {med_request.get('medication_name')}
- Clinical Rationale: {med_request.get('clinical_rationale')}

AVAILABLE EVIDENCE:
{json.dumps(case.get('available_test_results', {}), indent=2)}

Your task: Submit PA appeal with additional clinical evidence.

RESPONSE FORMAT (JSON):
{{
    "appeal_type": "peer_to_peer" or "written_appeal",
    "additional_evidence": "<specific clinical data points>",
    "severity_documentation": "<disease severity indicators>",
    "guideline_references": ["<guideline 1>", ...]
}}"""

def create_pa_appeal_decision_prompt(state, provider_appeal):
    """create task prompt for payor PA appeal review"""
    return f"""TASK: Medical Director review of PA APPEAL (Phase 2)

CRITICAL CONTEXT: This is an appeal of a PRIOR AUTHORIZATION denial, not a claim denial.
You previously denied the PA. Now reconsider based on additional evidence.

ORIGINAL PA DENIAL:
{state.medication_authorization.denial_reason}

PROVIDER APPEAL:
{provider_appeal.get('additional_evidence')}

SEVERITY DOCUMENTATION:
{provider_appeal.get('severity_documentation')}

GUIDELINES CITED:
{', '.join(provider_appeal.get('guideline_references', []))}

Your task: Re-evaluate PA decision based on appeal evidence.

RESPONSE FORMAT (JSON):
{{
    "appeal_outcome": "approved" or "upheld_denial",
    "decision_rationale": "<reasoning>",
    "criteria_applied": "<guidelines>",
    "peer_to_peer_conducted": true/false,
    "reviewer_credentials": "Medical Director, Board Certified <specialty>"
}}"""

def create_claim_adjudication_prompt(state, med_request, cost_ref, case):
    """create task prompt for claim review"""
    total_billed = cost_ref.get('drug_acquisition_cost', 7800) + cost_ref.get('administration_fee', 150)

    return f"""TASK: Review CLAIM for specialty medication (Phase 3)

CRITICAL CONTEXT: This is Phase 3 - CLAIM ADJUDICATION after treatment already delivered.
The PA was approved in Phase 2, but you can still deny payment if documentation is insufficient.

PATIENT:
- Age: {state.admission.patient_demographics.age}
- Medical History: {', '.join(state.clinical_presentation.medical_history)}

CLAIM SUBMITTED:
- Medication: {med_request.get('medication_name')}
- Dosage Administered: {med_request.get('dosage')}
- Amount Billed: ${total_billed:.2f}

PA APPROVAL RATIONALE (from Phase 2):
{state.medication_authorization.criteria_used if state.medication_authorization else 'PA approved'}

CLINICAL DOCUMENTATION:
{med_request.get('clinical_rationale')}

LAB DATA:
{__import__('json').dumps(case.get('available_test_results', {}).get('labs', {}), indent=2)}

Your task: Review claim and decide to approve/deny PAYMENT.

Common reasons to deny claim despite PA approval:
- Dosing doesn't match PA approval
- Documentation insufficient (missing notes, labs)
- Treatment delivered doesn't match authorized indication
- Billing errors or upcoding

RESPONSE FORMAT (JSON):
{{
    "claim_status": "approved" or "denied" or "partial",
    "denial_reason": "<specific reason if denied>",
    "approved_amount": <dollar amount or null>,
    "criteria_used": "<billing guidelines>",
    "requires_additional_documentation": ["<item1>", ...],
    "reviewer_type": "Claims adjudicator" or "Medical reviewer"
}}"""