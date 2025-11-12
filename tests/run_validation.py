"""
run macro-validation: aggregate metrics from all cases and compare to benchmarks
"""
import sys
import os
from datetime import datetime
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.simulation.game_runner import UtilizationReviewSimulation
from src.data.case_registry import list_cases, get_case
from src.data.case_converter import convert_case_to_models
from src.utils.metrics_aggregator import MetricsAggregator


# benchmarks from PAPERDRAFT.md Table 1
BENCHMARKS = {
    "overall_pa_denial_rate": {
        "value": 6.4,
        "source": "KFF analysis of CMS data (2023)"
    },
    "post_acute_care_denial_rate": {
        "value": 17.5,  # midpoint of 15-20% range
        "source": "OIG audits, Senate investigations"
    },
    "appeal_rate": {
        "value": 11.7,
        "source": "CMS Medicare Advantage data"
    },
    "appeal_success_rate": {
        "value": 81.7,
        "source": "CMS Medicare Advantage data"
    },
}


def run_validation():
    """orchestrate full validation workflow"""
    print("=" * 80)
    print("MACRO-VALIDATION: POPULATION-LEVEL METRICS")
    print("=" * 80)
    print()

    # azure configuration
    azure_config = {
        "endpoint": "https://azure-ai.hms.edu",
        "key": "59352b8b5029493a861f26c74ef46cfe",
        "deployment_name": "gpt-4o-1120"
    }

    # get all cases from registry
    case_ids = list_cases()
    total_cases = len(case_ids)

    print(f"Cases in registry: {total_cases}")
    if total_cases < 15:
        print(f"WARNING: Macro-validation requires 15-20 cases, found {total_cases}")
        print(f"WARNING: Results will be marked as INCOMPLETE VALIDATION")
    print()

    # initialize simulation
    sim = UtilizationReviewSimulation(azure_config=azure_config)

    # run all cases and collect results
    encounter_states = []
    print("Running simulations...")
    print("-" * 80)

    for i, case_id in enumerate(case_ids, 1):
        print(f"[{i}/{total_cases}] Running case: {case_id}...", end=" ")

        try:
            # load and convert case
            case = get_case(case_id)
            case = convert_case_to_models(case)

            # run simulation
            result = sim.run_case(case)
            encounter_states.append(result)

            # brief status
            status = "DENIED" if result.denial_occurred else "APPROVED"
            print(f"{status}")

        except Exception as e:
            print(f"ERROR: {str(e)}")
            continue

    print("-" * 80)
    print(f"Completed: {len(encounter_states)}/{total_cases} cases")
    print()

    # aggregate metrics
    print("Calculating aggregate metrics...")
    metrics = MetricsAggregator.calculate_aggregate_metrics(encounter_states)

    # format validation report
    report = MetricsAggregator.format_validation_report(metrics, BENCHMARKS)

    # print to console
    print()
    print(report)

    # save to file
    output_dir = "outputs"
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"{output_dir}/validation_report_{timestamp}.md"

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print()
    print(f"Report saved to: {report_path}")
    print()


if __name__ == "__main__":
    run_validation()
