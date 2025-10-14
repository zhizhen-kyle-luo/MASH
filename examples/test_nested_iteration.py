import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
from src.data.mimic_adapter import MIMICDataAdapter
from src.simulation.game_runner import StackelbergGameSimulation
from src.utils.behavioral_logger import BehavioralLogger
from src.utils.mermaid_generator import MermaidGenerator

load_dotenv()

azure_config = {
    "endpoint": os.getenv("AZURE_ENDPOINT"),
    "key": os.getenv("AZURE_KEY"),
    "deployment_name": os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
}

adapter = MIMICDataAdapter("c:/Work/Research/MASH/data/mimic_raw.json")
appendicitis_cases = adapter.get_by_pathology("appendicitis", limit=1)

if appendicitis_cases:
    test_case = appendicitis_cases[0]

    sim = StackelbergGameSimulation(
        provider_llm="gpt-4",
        patient_llm="gpt-4",
        payor_llm="gpt-4",
        lawyer_llm="gpt-4",
        payment_model="fee_for_service",
        confidence_threshold=0.9,
        azure_config=azure_config
    )

    result = sim.run_case(test_case)

    # TRANSCRIPT - what happened during simulation
    print("\nCase:", result.case_id)
    print("Ground truth:", result.ground_truth_diagnosis)
    print("\nPHASE 1 - Iterative Encounter:")

    for iteration in result.iteration_history:
        print(f"\nIteration {iteration.iteration_number}:")
        print(f"  Provider orders: {[t.test_name for t in iteration.provider_tests_ordered]}")
        print(f"  Payor approves: {iteration.payor_approved}")
        print(f"  Payor denies: {iteration.payor_denied}")
        if iteration.provider_appeals:
            print(f"  Provider appeals: {list(iteration.provider_appeals.keys())}")
        if iteration.provider_ordered_despite_denial:
            print(f"  Provider orders anyway: {iteration.provider_ordered_despite_denial}")
        print(f"  Provider confidence: {iteration.confidence}")
        print(f"  Provider differential: {iteration.differential}")

    print("\nPHASE 2 - Retrospective Scrutiny:")

    if result.patient_decision:
        print(f"\nPatient uploads to AI")
        print(f"  AI suggests: {result.patient_decision.ai_second_opinions}")
        print(f"  Patient confrontation: {result.patient_decision.confrontation_level}")
        print(f"  Patient concerns: {result.patient_decision.concerns}")

    if result.payor_decision:
        print(f"\nPayor retrospective review")
        print(f"  Retrospectively denies: {result.payor_decision.retrospective_denials}")

    if result.lawyer_decision:
        print(f"\nLawyer review")
        print(f"  Malpractice detected: {result.lawyer_decision.malpractice_detected}")
        print(f"  Litigation: {result.lawyer_decision.litigation_recommendation}")
        if result.lawyer_decision.standard_of_care_violations:
            print(f"  Violations: {result.lawyer_decision.standard_of_care_violations}")

    # RAW METRICS
    print("\nRAW METRICS:")
    metrics = BehavioralLogger.log_case_metrics(result)
    for key, value in metrics.items():
        print(f"  {key}: {value}")

    # Generate mermaid sequence diagram
    mermaid_path = "simulation_output.mmd"
    MermaidGenerator.save_to_file(result, mermaid_path)
    print(f"\nMermaid diagram saved to: {mermaid_path}")

    # Payoffs disabled - incomplete calculations
    # print(f"\n{'='*80}")
    # print("PAYOFFS")
    # print(f"{'='*80}")
    # print(f"Provider: ${result.provider_payoff:,.2f}")
    # print(f"Patient: ${result.patient_payoff:,.2f}")
    # print(f"Payor: ${result.payor_payoff:,.2f}")
    # print(f"Lawyer: ${result.lawyer_payoff:,.2f}")

else:
    print("No appendicitis cases found in dataset")
