"""
Test simulation against AppriseMD ground truth case
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.simulation.game_runner import UtilizationReviewSimulation
from src.data.apprisemd_sepsis_case import get_apprisemd_case
from src.data.case_converter import convert_case_to_models


def test_apprisemd_simulation():
    """Run AppriseMD case and validate against ground truth"""

    case = get_apprisemd_case()
    print("=" * 80)
    print("RUNNING APPRISEMD CASE SIMULATION")
    print("=" * 80)
    print(f"Case ID: {case['case_id']}")
    print(f"Patient: {case['patient_presentation']['age']}yo {case['patient_presentation']['sex']}")
    print(f"Chief Complaint: {case['patient_presentation']['chief_complaint']}")
    print()

    case = convert_case_to_models(case)

    azure_config = {
        "endpoint": "https://azure-ai.hms.edu",
        "key": "59352b8b5029493a861f26c74ef46cfe",
        "deployment_name": "gpt-4o-1120"
    }

    sim = UtilizationReviewSimulation(azure_config=azure_config)

    print("Running 4-phase simulation...")
    result = sim.run_case(case)

    print("\n" + "=" * 80)
    print("SIMULATION RESULTS")
    print("=" * 80)

    print("\n--- PHASE 1: ADMISSION ---")
    print(f"Admission Date: {result.admission.admission_date}")
    print(f"Insurance: {result.admission.insurance.payer_name}")

    print("\n--- PHASE 2: CONCURRENT REVIEW ---")
    if result.provider_documentation:
        print(f"Iterations: {len(result.provider_documentation.iterations)}")
        print(f"Final Diagnoses: {', '.join(result.provider_documentation.final_diagnoses)}")
    if result.utilization_review:
        print(f"Authorization Status: {result.utilization_review.authorization_status}")
        print(f"Authorized Level: {result.utilization_review.authorized_level_of_care}")
        if result.utilization_review.denial_reason:
            print(f"Denial Reason: {result.utilization_review.denial_reason}")

    print("\n--- PHASE 3: APPEAL ---")
    if result.appeal_record:
        print(f"Appeal Filed: {result.appeal_filed}")
        if result.appeal_record.appeal_decision:
            print(f"Appeal Outcome: {result.appeal_record.appeal_decision.appeal_outcome}")
            print(f"Final Level: {result.appeal_record.appeal_decision.final_authorized_level}")
    else:
        print("No appeal filed (approved on initial review)")

    print("\n--- PHASE 4: FINANCIAL SETTLEMENT ---")
    if result.financial_settlement:
        if result.financial_settlement.drg_assignment:
            print(f"DRG: {result.financial_settlement.drg_assignment.drg_code}")
        print(f"Hospital Revenue: ${result.financial_settlement.total_hospital_revenue:,.2f}")
        print(f"Patient Responsibility: ${result.financial_settlement.patient_responsibility:,.2f}")

    print("\n" + "=" * 80)
    print("VALIDATION AGAINST GROUND TRUTH")
    print("=" * 80)

    ground_truth = case['ground_truth_payer_actions']
    ground_truth_financial = case['ground_truth_financial']

    validations = []

    gt_denied = "DENIED" in ground_truth['initial_decision']['status']
    sim_denied = result.denial_occurred if result.denial_occurred is not None else False
    validations.append(("Initial Denial Occurred", gt_denied, sim_denied))

    gt_appeal = ground_truth['appeal_process']['appeal_outcome'] is not None
    sim_appeal = result.appeal_filed if result.appeal_filed is not None else False
    validations.append(("Appeal Filed", gt_appeal, sim_appeal))

    gt_approved = ground_truth['appeal_process']['appeal_outcome'] == "APPROVED"
    sim_approved = result.appeal_successful if result.appeal_successful is not None else False
    validations.append(("Appeal Approved", gt_approved, sim_approved))

    gt_final_level = ground_truth_financial['actual_outcome']['level_authorized']
    sim_final_level = result.final_authorized_level
    validations.append(("Final Authorization Level", gt_final_level, sim_final_level))

    gt_payment = ground_truth_financial['actual_outcome']['payment_received']
    sim_payment = result.financial_settlement.total_hospital_revenue if result.financial_settlement else 0
    validations.append(("Hospital Payment Amount", gt_payment, sim_payment))

    print("\nValidation Item                    | Ground Truth | Simulation | Match")
    print("-" * 80)
    for item, gt_val, sim_val in validations:
        match = "PASS" if gt_val == sim_val else "FAIL"
        print(f"{item:35} | {str(gt_val):12} | {str(sim_val):10} | {match}")

    matches = sum(1 for _, gt, sim in validations if gt == sim)
    total = len(validations)
    print(f"\nValidation Score: {matches}/{total} ({matches/total*100:.0f}%)")

    return result, validations


if __name__ == "__main__":
    result, validations = test_apprisemd_simulation()

    all_passed = all(gt == sim for _, gt, sim in validations)

    if all_passed:
        print("\n" + "=" * 80)
        print("SUCCESS: Simulation matches AppriseMD ground truth!")
        print("=" * 80)
    else:
        print("\n" + "=" * 80)
        print("VALIDATION FAILED: Some outputs don't match ground truth")
        print("=" * 80)
        print("\nDebugging needed - check which phase produced incorrect output")
