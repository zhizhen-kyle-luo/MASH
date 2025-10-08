import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from src.simulation.game_runner import StackelbergGameSimulation


def run_all_cases():
    """Run all 3 game cases and display results."""
    load_dotenv()

    azure_config = {
        "endpoint": os.getenv("AZURE_ENDPOINT"),
        "key": os.getenv("AZURE_KEY"),
        "deployment_name": os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
    }

    sim = StackelbergGameSimulation(
        provider_llm="gpt-4",
        patient_llm="gpt-4",
        payor_llm="gpt-4",
        lawyer_llm="gpt-4",
        payment_model="fee_for_service",
        azure_config=azure_config
    )

    cases_dir = Path("data/cases/game_cases")
    results = []

    for case_file in sorted(cases_dir.glob("case_game_*.json")):
        with open(case_file, 'r') as f:
            case = json.load(f)

        print(f"\n{'=' * 80}")
        print(f"Running: {case['case_id']}")
        print(f"Patient: {case['patient_presentation']['age']}yo {case['patient_presentation']['sex']}")
        print(f"Chief complaint: {case['patient_presentation']['chief_complaint']}")
        print(f"Ground truth: {case['ground_truth']['diagnosis']}")
        print(f"{'=' * 80}\n")

        result = sim.run_case(case)
        results.append(result)

        print(f"\n--- RESULTS FOR {case['case_id']} ---")
        print(f"Provider AI adoption: {result.provider_decision.ai_adoption}/10")
        print(f"Patient AI shopping: {result.patient_decision.ai_shopping_intensity}/10")
        print(f"Payor AI review: {result.payor_decision.ai_review_intensity}/10")
        print(f"Lawyer AI analysis: {result.lawyer_decision.ai_analysis_intensity}/10")
        print(f"\nDiagnostic accuracy: {result.diagnostic_accuracy}")
        print(f"Defensive medicine index: {result.defensive_medicine_index:.1%}")
        print(f"Total system cost: ${result.collective_metrics.total_system_cost:.2f}")
        print(f"\nPayoffs:")
        print(f"  Provider: ${result.provider_payoff:.2f}")
        print(f"  Patient: ${result.patient_payoff:.2f}")
        print(f"  Payor: ${result.payor_payoff:.2f}")
        print(f"  Lawyer: ${result.lawyer_payoff:.2f}")

    print(f"\n\n{'=' * 80}")
    print("SUMMARY ACROSS ALL CASES")
    print(f"{'=' * 80}\n")

    avg_defensive_medicine = sum(r.defensive_medicine_index for r in results) / len(results)
    avg_cost = sum(r.collective_metrics.total_system_cost for r in results) / len(results)
    avg_provider_payoff = sum(r.provider_payoff for r in results) / len(results)
    accuracy_rate = sum(1 for r in results if r.diagnostic_accuracy) / len(results)

    print(f"Average defensive medicine index: {avg_defensive_medicine:.1%}")
    print(f"Average total system cost: ${avg_cost:.2f}")
    print(f"Average provider payoff: ${avg_provider_payoff:.2f}")
    print(f"Diagnostic accuracy rate: {accuracy_rate:.1%}")


if __name__ == "__main__":
    run_all_cases()
