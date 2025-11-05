"""
Example demonstrating audit log structure and Mermaid diagram generation.

This shows what the audit log captures without requiring actual LLM calls.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.audit_logger import AuditLogger
from src.utils.mermaid_audit_generator import MermaidAuditGenerator
import json


def create_example_audit_log():
    """Create example audit log showing typical PA workflow."""

    # Initialize audit logger
    logger = AuditLogger(case_id="example_infliximab_001")

    # Phase 2: PA Request - Payor reviews
    logger.log_interaction(
        phase="phase_2_pa",
        agent="payor",
        action="pa_decision",
        system_prompt="You are a PAYER reviewing a specialty medication PRIOR AUTHORIZATION request.",
        user_prompt="""You are a PAYER reviewing a specialty medication PRIOR AUTHORIZATION request.

PATIENT:
- Age: 60
- Sex: F
- Diagnoses: Crohn's disease, Iron deficiency anemia
- Chief Complaint: 10-day history of small intestinal stenosis, abdominal pain, watery diarrhea

MEDICATION REQUEST:
- Drug: Infliximab (Remicade)
- Dosage: 5 mg/kg IV infusion
- Frequency: Weeks 0, 2, 6, then every 8 weeks
- ICD-10 Codes: K50.011, D50.9

CLINICAL RATIONALE:
Patient has active Crohn's disease with small bowel stenosis despite conventional therapy...

STEP THERAPY:
- Prior Therapies Failed: Mesalamine, Prednisone, Azathioprine
- Step Therapy Completed: True

Your task: Evaluate this PA request using step therapy requirements and medical necessity criteria.

RESPONSE FORMAT (JSON):
{
    "authorization_status": "approved" or "denied",
    "denial_reason": "<reason if denied>",
    "criteria_used": "<guidelines>",
    "reviewer_type": "AI algorithm"
}""",
        llm_response="""{
    "authorization_status": "denied",
    "denial_reason": "Insufficient documentation of disease activity. CRP and fecal calprotectin levels not provided.",
    "criteria_used": "Step therapy protocol + disease activity criteria",
    "step_therapy_required": false,
    "missing_documentation": ["CRP level", "Fecal calprotectin"],
    "approved_duration_days": null,
    "requires_peer_to_peer": true,
    "reviewer_type": "AI algorithm"
}""",
        parsed_output={
            "authorization_status": "denied",
            "denial_reason": "Insufficient documentation of disease activity",
            "criteria_used": "Step therapy protocol",
            "reviewer_type": "AI algorithm"
        },
        metadata={"medication": "Infliximab"}
    )

    # Phase 2: PA Appeal - Provider submits appeal
    logger.log_interaction(
        phase="phase_2_pa_appeal",
        agent="provider",
        action="pa_appeal_submission",
        system_prompt="You are a PROVIDER appealing a PA DENIAL for specialty medication.",
        user_prompt="""You are a PROVIDER appealing a PA DENIAL for specialty medication.

DENIAL REASON:
Insufficient documentation of disease activity. CRP and fecal calprotectin levels not provided.

PATIENT CLINICAL DATA:
- Age: 60
- Medical History: Crohn's disease, Iron deficiency anemia
- Chief Complaint: 10-day history of small intestinal stenosis

MEDICATION REQUESTED:
- Drug: Infliximab (Remicade)
- Clinical Rationale: Active Crohn's with stricture despite conventional therapy

AVAILABLE EVIDENCE:
{
    "labs": {
        "CRP": "45 mg/L (elevated)",
        "Fecal_calprotectin": "850 mcg/g (significantly elevated)",
        "Albumin": "3.2 g/dL (low)",
        "Hemoglobin": "10.5 g/dL (anemia)"
    }
}

Your task: Submit PA appeal with additional clinical evidence.

RESPONSE FORMAT (JSON):
{
    "appeal_type": "peer_to_peer" or "written_appeal",
    "additional_evidence": "<evidence>",
    "severity_documentation": "<severity>",
    "guideline_references": ["<ref>"]
}""",
        llm_response="""{
    "appeal_type": "peer_to_peer",
    "additional_evidence": "CRP 45 mg/L and fecal calprotectin 850 mcg/g confirm active inflammation. Patient has stricturing disease with partial obstruction.",
    "severity_documentation": "Harvey-Bradshaw Index score of 14 indicating severe disease activity. Failed 3 conventional therapies.",
    "guideline_references": ["ACG Crohn's Disease Guidelines 2018", "AGA IBD Guidelines"]
}""",
        parsed_output={
            "appeal_type": "peer_to_peer",
            "additional_evidence": "CRP 45 mg/L confirms inflammation",
            "severity_documentation": "Harvey-Bradshaw Index 14",
            "guideline_references": ["ACG Guidelines 2018"]
        },
        metadata={"denial_reason": "Insufficient documentation"}
    )

    # Phase 2: PA Appeal Decision - Payor reviews appeal
    logger.log_interaction(
        phase="phase_2_pa_appeal",
        agent="payor",
        action="pa_appeal_decision",
        system_prompt="You are a PAYER MEDICAL DIRECTOR reviewing a PA APPEAL.",
        user_prompt="""You are a PAYER MEDICAL DIRECTOR reviewing a PA APPEAL (Phase 2).

ORIGINAL PA DENIAL:
Insufficient documentation of disease activity

PROVIDER APPEAL:
CRP 45 mg/L and fecal calprotectin 850 mcg/g confirm active inflammation...

SEVERITY DOCUMENTATION:
Harvey-Bradshaw Index score of 14 indicating severe disease activity...

GUIDELINES CITED:
ACG Crohn's Disease Guidelines 2018, AGA IBD Guidelines

Your task: Re-evaluate PA decision based on appeal evidence.

RESPONSE FORMAT (JSON):
{
    "appeal_outcome": "approved" or "upheld_denial",
    "decision_rationale": "<reasoning>",
    "criteria_applied": "<guidelines>",
    "reviewer_credentials": "Medical Director, Board Certified Gastroenterology"
}""",
        llm_response="""{
    "appeal_outcome": "approved",
    "decision_rationale": "Lab values confirm active disease. Step therapy adequately documented. Meets criteria for biologic therapy.",
    "criteria_applied": "ACG Crohn's guidelines + step therapy protocol",
    "peer_to_peer_conducted": true,
    "reviewer_credentials": "Medical Director, Board Certified Gastroenterology"
}""",
        parsed_output={
            "appeal_outcome": "approved",
            "decision_rationale": "Lab values confirm active disease",
            "criteria_applied": "ACG Crohn's guidelines",
            "reviewer_credentials": "Medical Director"
        },
        metadata={"appeal_type": "peer_to_peer"}
    )

    # Phase 3: Claims Adjudication - Payor reviews claim after treatment
    logger.log_interaction(
        phase="phase_3_claims",
        agent="payor",
        action="claim_adjudication",
        system_prompt="You are a PAYER reviewing a CLAIM for specialty medication.",
        user_prompt="""You are a PAYER reviewing a CLAIM for specialty medication (Phase 3).

CRITICAL: This is CLAIM ADJUDICATION after treatment already delivered.
The PA was approved in Phase 2, but you can still deny payment if documentation is insufficient.

PATIENT:
- Age: 60
- Medical History: Crohn's disease

CLAIM SUBMITTED:
- Medication: Infliximab (Remicade)
- Dosage Administered: 5 mg/kg IV infusion
- Amount Billed: $7,950.00

PA APPROVAL RATIONALE (from Phase 2):
ACG Crohn's guidelines + step therapy protocol

Your task: Review claim and decide to approve/deny PAYMENT.

RESPONSE FORMAT (JSON):
{
    "claim_status": "approved" or "denied",
    "denial_reason": "<reason if denied>",
    "approved_amount": <amount>,
    "criteria_used": "<guidelines>",
    "reviewer_type": "Claims adjudicator"
}""",
        llm_response="""{
    "claim_status": "approved",
    "denial_reason": null,
    "approved_amount": 7950.00,
    "criteria_used": "Standard billing guidelines - matches PA approval",
    "requires_additional_documentation": [],
    "reviewer_type": "Claims adjudicator"
}""",
        parsed_output={
            "claim_status": "approved",
            "approved_amount": 7950.00,
            "criteria_used": "Standard billing guidelines",
            "reviewer_type": "Claims adjudicator"
        },
        metadata={"medication": "Infliximab", "pa_approved": True}
    )

    # Finalize audit log
    logger.finalize()

    return logger.get_audit_log()


def main():
    print("=" * 80)
    print("AUDIT LOG EXAMPLE: Infliximab PA Workflow")
    print("=" * 80)

    # Create example audit log
    audit_log = create_example_audit_log()

    print(f"\nCase ID: {audit_log.case_id}")
    print(f"Total Interactions: {len(audit_log.interactions)}")
    print(f"Summary: {json.dumps(audit_log.summary, indent=2)}")

    # Create output directory
    output_dir = "outputs"
    os.makedirs(output_dir, exist_ok=True)

    # Save audit log to JSON
    audit_log_path = f"{output_dir}/example_audit_log.json"
    with open(audit_log_path, 'w') as f:
        json.dump(audit_log.model_dump(), f, indent=2)
    print(f"\n✓ Audit log saved to: {audit_log_path}")

    # Generate and save Mermaid diagram
    mermaid_diagram = MermaidAuditGenerator.generate_from_audit_log(audit_log)
    mermaid_path = f"{output_dir}/example_workflow.mmd"
    with open(mermaid_path, 'w') as f:
        f.write(mermaid_diagram)
    print(f"✓ Mermaid diagram saved to: {mermaid_path}")

    # Print Mermaid diagram
    print("\n" + "=" * 80)
    print("MERMAID SEQUENCE DIAGRAM")
    print("=" * 80)
    print(mermaid_diagram)

    # Print interaction details
    print("\n" + "=" * 80)
    print("INTERACTION DETAILS")
    print("=" * 80)

    for i, interaction in enumerate(audit_log.interactions, 1):
        print(f"\n[{i}] {interaction.phase} - {interaction.agent.upper()} - {interaction.action}")
        print(f"Timestamp: {interaction.timestamp}")
        print(f"Parsed Output: {json.dumps(interaction.parsed_output, indent=2)}")
        print("-" * 80)

    print("\n" + "=" * 80)
    print("EXAMPLE COMPLETE")
    print("=" * 80)
    print("\nKey Features Demonstrated:")
    print("✓ Full prompt/response capture")
    print("✓ System and user prompts logged")
    print("✓ Parsed outputs structured")
    print("✓ Phase-based organization")
    print("✓ Mermaid diagram generation")
    print("✓ JSON export for analysis")


if __name__ == "__main__":
    main()
