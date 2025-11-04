"""
test simulation against infliximab specialty medication case
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.simulation.game_runner import UtilizationReviewSimulation
from src.data.infliximab_crohns_case import get_infliximab_case
from src.data.case_converter import convert_case_to_models


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

    print("\n--- PHASE 3: APPEAL ---")
    if result.appeal_record:
        print(f"Appeal Filed: {result.appeal_filed}")
        if result.appeal_record.appeal_decision:
            print(f"Appeal Outcome: {result.appeal_record.appeal_decision.appeal_outcome}")
            print(f"Reviewer: {result.appeal_record.appeal_decision.reviewer_credentials}")
            print(f"P2P Conducted: {result.appeal_record.appeal_decision.peer_to_peer_conducted}")
    else:
        print("no appeal filed (approved on initial review)")

    print("\n--- PHASE 4: FINANCIAL SETTLEMENT ---")
    if result.medication_financial:
        print(f"Medication: {result.medication_financial.medication_name}")
        print(f"Drug Cost: ${result.medication_financial.acquisition_cost:,.2f}")
        print(f"Admin Fee: ${result.medication_financial.administration_fee:,.2f}")
        print(f"Total Billed: ${result.medication_financial.total_billed:,.2f}")
        print(f"Payer Payment: ${result.medication_financial.payer_payment:,.2f}")
        print(f"Patient Copay: ${result.medication_financial.patient_copay:,.2f}")
        print(f"PA Cost: ${result.medication_financial.prior_auth_cost:,.2f}")
        print(f"Appeal Cost: ${result.medication_financial.appeal_cost:,.2f}")
        print(f"Total Admin Burden: ${result.medication_financial.total_administrative_cost:,.2f}")

    print("\n" + "=" * 80)
    print("VALIDATION AGAINST GROUND TRUTH")
    print("=" * 80)

    ground_truth = case['ground_truth_payer_actions']
    ground_truth_financial = case['ground_truth_financial']

    validations = []

    # initial denial occurred
    gt_denied = "DENIED" in ground_truth['initial_decision']['status']
    sim_denied = result.denial_occurred
    validations.append(("Initial Denial Occurred", gt_denied, sim_denied))

    # appeal filed
    gt_appeal = ground_truth['appeal_process']['appeal_outcome'] is not None
    sim_appeal = result.appeal_filed
    validations.append(("Appeal Filed", gt_appeal, sim_appeal))

    # appeal approved
    gt_approved = ground_truth['appeal_process']['appeal_outcome'] == "APPROVED"
    sim_approved = result.appeal_successful
    validations.append(("Appeal Approved", gt_approved, sim_approved))

    # administrative burden
    gt_admin_cost = ground_truth_financial['administrative_costs']['total_administrative_burden']
    sim_admin_cost = result.medication_financial.total_administrative_cost if result.medication_financial else 0
    admin_match = abs(gt_admin_cost - sim_admin_cost) < 50.0  # within $50
    validations.append(("Admin Cost (~$375)", gt_admin_cost, sim_admin_cost))

    print("\nValidation Item                    | Ground Truth | Simulation | Match")
    print("-" * 80)
    for item, gt_val, sim_val in validations:
        if isinstance(gt_val, float):
            match = "PASS" if abs(gt_val - sim_val) < 50 else "FAIL"
            print(f"{item:35} | ${gt_val:11,.2f} | ${sim_val:9,.2f} | {match}")
        else:
            match = "PASS" if gt_val == sim_val else "FAIL"
            print(f"{item:35} | {str(gt_val):12} | {str(sim_val):10} | {match}")

    matches = sum(1 for item, gt, sim in validations
                  if (isinstance(gt, float) and abs(gt - sim) < 50) or gt == sim)
    total = len(validations)
    print(f"\nValidation Score: {matches}/{total} ({matches/total*100:.0f}%)")

    return result, validations


if __name__ == "__main__":
    result, validations = test_infliximab_simulation()

    all_passed = all(
        (isinstance(gt, float) and abs(gt - sim) < 50) or gt == sim
        for _, gt, sim in validations
    )

    if all_passed:
        print("\n" + "=" * 80)
        print("SUCCESS: Simulation matches Infliximab case ground truth!")
        print("=" * 80)
    else:
        print("\n" + "=" * 80)
        print("VALIDATION FAILED: Some outputs don't match ground truth")
        print("=" * 80)
        print("\ndebugging needed - check which phase produced incorrect output")
