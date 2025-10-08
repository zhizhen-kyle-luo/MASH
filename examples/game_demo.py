import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from src.simulation.game_runner import StackelbergGameSimulation


def run_demo():
    """Demo: Single case through Stackelberg game simulation."""
    load_dotenv()

    azure_config = {
        "endpoint": os.getenv("AZURE_ENDPOINT"),
        "key": os.getenv("AZURE_KEY"),
        "deployment_name": os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
    }

    with open("data/cases/game_cases/case_game_001.json", 'r') as f:
        case = json.load(f)

    print("=== Healthcare AI Arms Race Simulation Demo ===\n")
    print(f"Case: {case['case_id']}")
    print(f"Patient: {case['patient_presentation']['age']}yo {case['patient_presentation']['sex']}")
    print(f"Chief complaint: {case['patient_presentation']['chief_complaint']}\n")

    sim = StackelbergGameSimulation(
        provider_llm="gpt-4",
        patient_llm="gpt-4",
        payor_llm="gpt-4",
        lawyer_llm="gpt-4",
        payment_model="fee_for_service",
        azure_config=azure_config
    )

    print("Running simulation...")
    result = sim.run_case(case)

    print("\n=== TURN 1: Provider Decision ===")
    print(f"AI adoption: {result.provider_decision.ai_adoption}/10")
    print(f"Documentation: {result.provider_decision.documentation_intensity}")
    print(f"Testing approach: {result.provider_decision.testing_approach}")
    print(f"Diagnosis: {result.provider_decision.diagnosis}")
    print(f"Tests ordered:")
    for test in result.provider_decision.tests_ordered:
        print(f"  - {test.test_name} (${test.estimated_cost})")
    print(f"Reasoning: {result.provider_decision.reasoning[:200]}...")

    print("\n=== TURN 2: Patient Decision ===")
    print(f"AI shopping: {result.patient_decision.ai_shopping_intensity}/10")
    print(f"Confrontation: {result.patient_decision.confrontation_level}")
    print(f"Action: {result.patient_decision.action}")
    print(f"Reasoning: {result.patient_decision.reasoning[:200]}...")

    print("\n=== TURN 3: Payor Decision ===")
    print(f"AI review: {result.payor_decision.ai_review_intensity}/10")
    print(f"Denial threshold: {result.payor_decision.denial_threshold}")
    print(f"Approved: {', '.join(result.payor_decision.approved_tests)}")
    print(f"Denied: {', '.join(result.payor_decision.denied_tests)}")
    print(f"Reasoning: {result.payor_decision.reasoning[:200]}...")

    print("\n=== TURN 4: Lawyer Decision ===")
    print(f"AI analysis: {result.lawyer_decision.ai_analysis_intensity}/10")
    print(f"Malpractice detected: {result.lawyer_decision.malpractice_detected}")
    print(f"Action: {result.lawyer_decision.action}")
    print(f"Reasoning: {result.lawyer_decision.reasoning[:200]}...")

    print("\n=== OUTCOMES ===")
    print(f"Diagnostic accuracy: {result.diagnostic_accuracy}")
    print(f"Ground truth: {result.ground_truth_diagnosis}")
    print(f"Defensive medicine index: {result.defensive_medicine_index:.2%}")
    print(f"Total system cost: ${result.collective_metrics.total_system_cost:.2f}")
    print(f"Trust index: {result.collective_metrics.overall_trust_index:.2f}")
    print(f"Defensive cascade: {result.collective_metrics.defensive_cascade}")

    print("\n=== PAYOFFS ===")
    print(f"Provider: ${result.provider_payoff:.2f}")
    print(f"Patient: ${result.patient_payoff:.2f}")
    print(f"Payor: ${result.payor_payoff:.2f}")
    print(f"Lawyer: ${result.lawyer_payoff:.2f}")


if __name__ == "__main__":
    run_demo()
