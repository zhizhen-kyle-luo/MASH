"""
test simulation against infliximab specialty medication case
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.simulation.game_runner import UtilizationReviewSimulation
from src.data.infliximab_crohns_case import get_infliximab_case
from src.data.case_converter import convert_case_to_models
from src.utils.mermaid_audit_generator import MermaidAuditGenerator
import os


def test_infliximab_simulation():
    """run infliximab case and validate against ground truth"""

    case = get_infliximab_case()
    print("=" * 80)
    print("RUNNING INFLIXIMAB SPECIALTY MEDICATION CASE SIMULATION")
    print("=" * 80)
    print(f"Case ID: {case['case_id']}")
    print(f"Patient: {case['patient_presentation']['age']}yo {case['patient_presentation']['sex']}")
    print(f"Chief Complaint: {case['patient_presentation']['chief_complaint']}")
    print(f"PA Type: {case['pa_type']}")
    print()

    case = convert_case_to_models(case)

    azure_config = {
        "endpoint": "https://azure-ai.hms.edu",
        "key": "59352b8b5029493a861f26c74ef46cfe",
        "deployment_name": "gpt-4o-1120"
    }

    sim = UtilizationReviewSimulation(azure_config=azure_config)

    print("running 4-phase medication pa simulation...")
    result = sim.run_case(case)

    print("\n" + "=" * 80)
    print("SIMULATION RESULTS")
    print("=" * 80)

    print("\n--- PHASE 1: PATIENT PRESENTATION ---")
    print(f"Patient: {result.admission.patient_demographics.age}yo {result.admission.patient_demographics.sex}")
    print(f"Diagnoses: {', '.join(result.clinical_presentation.medical_history)}")
    print(f"Insurance: {result.admission.insurance.payer_name}")

    print("\n--- PHASE 2: MEDICATION PRIOR AUTHORIZATION ---")
    if result.medication_request:
        print(f"Medication: {result.medication_request.medication_name}")
        print(f"Dosage: {result.medication_request.dosage}")
        print(f"Step Therapy Completed: {result.medication_request.step_therapy_completed}")
        print(f"Prior Failures: {', '.join(result.medication_request.prior_therapies_failed)}")

    if result.medication_authorization:
        print(f"\nAuthorization Status: {result.medication_authorization.authorization_status}")
        print(f"Reviewer: {result.medication_authorization.reviewer_type}")
        if result.medication_authorization.denial_reason:
            print(f"Denial Reason: {result.medication_authorization.denial_reason}")
        if result.medication_authorization.missing_documentation:
            print(f"Missing Docs: {', '.join(result.medication_authorization.missing_documentation)}")

    print("\n--- PHASE 3: CLAIMS ADJUDICATION ---")
    if result.medication_authorization and result.medication_authorization.authorization_status == "approved":
        print("Provider treated patient and submitted claim")
        print(f"Claim Status: {result.medication_authorization.authorization_status.upper()}")
        if result.medication_authorization.denial_reason:
            print(f"Claim Denial: {result.medication_authorization.denial_reason[:150]}...")
    else:
        print("No claim submitted (PA denied and not overturned)")

    print("\n--- PHASE 4: FINANCIAL SETTLEMENT ---")
    if result.medication_financial:
        print(f"Drug Cost: ${result.medication_financial.acquisition_cost:,.2f}")
        print(f"Admin Fee: ${result.medication_financial.administration_fee:,.2f}")
        print(f"Total Billed: ${result.medication_financial.total_billed:,.2f}")
        print(f"\nPayer Payment: ${result.medication_financial.payer_payment:,.2f}")
        print(f"Patient Copay: ${result.medication_financial.patient_copay:,.2f}")
        print(f"\nAdministrative Costs:")
        print(f"  PA + Claim Review: ${result.medication_financial.prior_auth_cost:,.2f}")
        print(f"  Appeals: ${result.medication_financial.appeal_cost:,.2f}")
        print(f"  Total Admin Burden: ${result.medication_financial.total_administrative_cost:,.2f}")

    print("\n" + "=" * 80)
    print("EXECUTION VERIFICATION")
    print("=" * 80)

    checks = []
    checks.append(("Phase 1 Complete", result.admission is not None))
    checks.append(("Phase 2 PA Decision Made", result.medication_authorization is not None))
    checks.append(("Phase 3 Claims Processed", result.medication_financial is not None))
    checks.append(("Phase 4 Settlement Calculated", result.medication_financial.total_billed > 0))

    all_passed = all(passed for _, passed in checks)

    print("\nExecution Checks:")
    for check, passed in checks:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{check:40} {status}")

    print(f"\nResult: {'SUCCESS - All phases executed' if all_passed else 'FAILURE - Some phases missing'}")
    print("\n" + "=" * 80)
    print("NOTE: Validation happens at POPULATION level (15-20 cases)")
    print("Individual case outcomes are NOT validated against ground truth")
    print("Agents make real LLM-based decisions - not following predetermined paths")
    print("=" * 80)

    # Save audit log and mermaid diagram
    if result.audit_log:
        output_dir = "outputs"
        os.makedirs(output_dir, exist_ok=True)

        # Save audit log as markdown
        audit_log_path = f"{output_dir}/{result.audit_log.case_id}_audit_log.md"
        result.audit_log.save_to_markdown(audit_log_path)
        print(f"\n[OK] Audit log saved to: {audit_log_path}")

        # Generate and save mermaid diagram
        mermaid_path = f"{output_dir}/{result.audit_log.case_id}_workflow.mmd"
        MermaidAuditGenerator.save_from_state(result, mermaid_path)
        print(f"[OK] Mermaid diagram saved to: {mermaid_path}")
    else:
        print("\n[WARN] No audit log available")

    return result


if __name__ == "__main__":
    result = test_infliximab_simulation()
