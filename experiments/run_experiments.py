import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from src.simulation.game_runner import StackelbergGameSimulation


def load_test_cases(cases_dir: str):
    """Load all game test cases from directory."""
    cases = []
    cases_path = Path(cases_dir)

    for case_file in cases_path.glob("case_game_*.json"):
        with open(case_file, 'r') as f:
            cases.append(json.load(f))

    return cases


def run_llm_asymmetry_experiment(azure_config, cases):
    """
    Experiment 1: LLM Strength Asymmetry

    Compare symmetric (all GPT-4) vs asymmetric (provider GPT-3.5, others GPT-4).
    Hypothesis: Weak provider leads to more defensive medicine.
    """
    print("\n=== Experiment 1: LLM Strength Asymmetry ===\n")

    configs = [
        {
            "name": "Symmetric (all GPT-4)",
            "provider_llm": "gpt-4",
            "patient_llm": "gpt-4",
            "payor_llm": "gpt-4",
            "lawyer_llm": "gpt-4",
        },
        {
            "name": "Asymmetric (weak provider)",
            "provider_llm": "gpt-3.5-turbo",
            "patient_llm": "gpt-4",
            "payor_llm": "gpt-4",
            "lawyer_llm": "gpt-4",
        }
    ]

    results = {}
    for config in configs:
        print(f"\nRunning: {config['name']}")

        sim = StackelbergGameSimulation(
            provider_llm=config["provider_llm"],
            patient_llm=config["patient_llm"],
            payor_llm=config["payor_llm"],
            lawyer_llm=config["lawyer_llm"],
            payment_model="fee_for_service",
            azure_config=azure_config
        )

        case_results = []
        for case in cases:
            print(f"  Processing case: {case['case_id']}")
            result = sim.run_case(case)
            case_results.append(result)

        results[config["name"]] = case_results

        avg_cost = sum(r.collective_metrics.total_system_cost for r in case_results) / len(case_results)
        avg_accuracy = sum(1 if r.diagnostic_accuracy else 0 for r in case_results) / len(case_results)
        avg_defensive = sum(r.defensive_medicine_index for r in case_results) / len(case_results)

        print(f"\n  Results for {config['name']}:")
        print(f"    Average cost: ${avg_cost:.2f}")
        print(f"    Average accuracy: {avg_accuracy:.2%}")
        print(f"    Average defensive medicine index: {avg_defensive:.2%}")

    return results


def run_payment_model_experiment(azure_config, cases):
    """
    Experiment 2: Payment Model Comparison

    Compare fee-for-service vs value-based payment.
    Hypothesis: FFS leads to higher costs and more defensive medicine.
    """
    print("\n=== Experiment 2: Payment Model Comparison ===\n")

    payment_models = ["fee_for_service", "value_based"]
    results = {}

    for payment_model in payment_models:
        print(f"\nRunning: {payment_model}")

        sim = StackelbergGameSimulation(
            provider_llm="gpt-4",
            patient_llm="gpt-4",
            payor_llm="gpt-4",
            lawyer_llm="gpt-4",
            payment_model=payment_model,
            azure_config=azure_config
        )

        case_results = []
        for case in cases:
            print(f"  Processing case: {case['case_id']}")
            result = sim.run_case(case)
            case_results.append(result)

        results[payment_model] = case_results

        avg_cost = sum(r.collective_metrics.total_system_cost for r in case_results) / len(case_results)
        avg_provider_payoff = sum(r.provider_payoff for r in case_results) / len(case_results)

        print(f"\n  Results for {payment_model}:")
        print(f"    Average cost: ${avg_cost:.2f}")
        print(f"    Average provider payoff: ${avg_provider_payoff:.2f}")

    return results


def save_results(results, output_path: str):
    """Save experimental results to JSON."""
    serializable_results = {}

    for exp_name, case_results in results.items():
        serializable_results[exp_name] = [
            {
                "case_id": r.case_id,
                "diagnostic_accuracy": r.diagnostic_accuracy,
                "defensive_medicine_index": r.defensive_medicine_index,
                "total_cost": r.collective_metrics.total_system_cost,
                "provider_ai": r.provider_decision.ai_adoption,
                "patient_ai": r.patient_decision.ai_shopping_intensity,
                "payor_ai": r.payor_decision.ai_review_intensity,
                "lawyer_ai": r.lawyer_decision.ai_analysis_intensity,
            }
            for r in case_results
        ]

    with open(output_path, 'w') as f:
        json.dump(serializable_results, f, indent=2)

    print(f"\nResults saved to: {output_path}")


def main():
    load_dotenv()

    azure_config = {
        "endpoint": os.getenv("AZURE_ENDPOINT"),
        "key": os.getenv("AZURE_KEY"),
        "deployment_name": os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
    }

    cases_dir = "data/cases/game_cases"
    cases = load_test_cases(cases_dir)

    print(f"Loaded {len(cases)} test cases")

    exp1_results = run_llm_asymmetry_experiment(azure_config, cases)
    save_results(exp1_results, "experiments/results_llm_asymmetry.json")

    exp2_results = run_payment_model_experiment(azure_config, cases)
    save_results(exp2_results, "experiments/results_payment_model.json")

    print("\n=== All experiments completed ===")


if __name__ == "__main__":
    main()
