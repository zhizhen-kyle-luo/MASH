import sys
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import uuid

# Load environment
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Fix Windows encoding
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from src.agents.patient_simulator import MASHPatientSimulator
from src.graph.workflow import MASHWorkflow
from src.models.schemas import PatientEHR, Message, GraphState


def load_case(case_file: str) -> PatientEHR:
    """Load patient EHR data from case file."""
    case_path = Path(__file__).parent.parent / case_file

    if not case_path.exists():
        raise FileNotFoundError(f"Case file not found: {case_path}")

    with open(case_path, 'r') as f:
        case_data = json.load(f)

    ehr_data = {
        "patient_id": case_data.get("patient_id", case_data.get("case_id", "unknown")),
        "demographics": case_data.get("demographics", {}),
        "vitals": case_data.get("vitals", {}),
        "medical_history": case_data.get("medical_history", case_data.get("history", [])),
        "insurance": case_data.get("insurance", {}),
        "constraints": case_data.get("constraints", {}),
        "availability": case_data.get("availability", {}),
        "emergency_contacts": case_data.get("emergency_contacts", {})
    }

    return PatientEHR(**ehr_data)


def create_patient_from_case(case_file: str):
    """Create PatientSim instance from case file with patient_sim_config."""
    case_path = Path(__file__).parent.parent / case_file

    if not case_path.exists():
        raise FileNotFoundError(f"Case file not found: {case_path}")

    with open(case_path, 'r') as f:
        case_data = json.load(f)

    sim_config = case_data.get("patient_sim_config", {})
    demographics = case_data.get("demographics", {})

    patient = MASHPatientSimulator(
        personality=sim_config.get("personality", "plain"),
        recall_level=sim_config.get("recall_level", "high"),
        confusion_level=sim_config.get("confusion_level", "normal"),
        lang_proficiency_level=sim_config.get("lang_proficiency_level", "C"),
        age=demographics.get("age", "40"),
        gender=demographics.get("sex", "unknown"),
        allergies=case_data.get("allergies", "None known")
    )

    ehr = load_case(case_file)
    return patient, ehr


def create_initial_state(patient_ehr: PatientEHR, max_turns: int = 12):
    """Create initial state for conversational mode."""
    return {
        "messages": [],
        "patient_ehr": patient_ehr,
        "clinical_summary": None,
        "current_agent": "supervisor",
        "next_agent": "Concierge",
        "turn_count": 0,
        "max_turns": max_turns,
        "workflow_status": "active",
        "current_plan": None,
        "internal_context": {},
        "conversation_history": []
    }


def run_patient_concierge_conversation(patient, workflow, patient_ehr, max_turns=8):
    """Run autonomous conversation between PatientSim and Concierge."""
    print("\n" + "="*80)
    print("MASH AUTONOMOUS PATIENT-CONCIERGE CONVERSATION")
    print("="*80)
    print(f"Patient Persona: {patient.personality}")
    print(f"Language Level: {patient.lang_proficiency_level}")
    print(f"Recall Level: {patient.recall_level}")
    print(f"Confusion Level: {patient.confusion_level}")
    print("="*80 + "\n")

    state = create_initial_state(patient_ehr, max_turns)
    concierge_agent = workflow.agents["Concierge"]

    print("[Concierge initiates conversation]\n")

    initial_greeting = "Hello, I'm your healthcare concierge. What brings you in today?"
    state["conversation_history"].append(f"Concierge: {initial_greeting}")

    patient_response = patient.respond(initial_greeting)
    print(f"Concierge: {initial_greeting}")
    print(f"\nPatient: {patient_response}\n")

    session_id = str(uuid.uuid4())
    patient_message = Message(
        id=str(uuid.uuid4()),
        session_id=session_id,
        turn_id=state["turn_count"],
        speaker="user",
        role="user",
        content=patient_response,
        timestamp=datetime.now()
    )
    state["messages"].append(patient_message)
    state["conversation_history"].append(f"Patient: {patient_response}")

    while state["workflow_status"] == "active" and state["turn_count"] < max_turns:
        try:
            state = concierge_agent.process(state)

            if state["messages"]:
                last_msg = state["messages"][-1]
                if last_msg.speaker == "agent" and last_msg.agent == "Concierge":
                    concierge_question = last_msg.content

                    if state.get("clinical_summary"):
                        print(f"Concierge: {concierge_question}\n")

                        clinical_summary = state["clinical_summary"]
                        print("="*80)
                        print("CLINICAL SUMMARY GENERATED")
                        print("="*80)
                        print(f"Chief Complaint: {clinical_summary.chief_complaint}")
                        print(f"Symptoms: {clinical_summary.presenting_symptoms}")
                        print(f"Urgency: {clinical_summary.urgency_level}")
                        print(f"\nSummary:\n{clinical_summary.summary}")

                        print("\n" + "="*80)
                        print("SPECIALIST COORDINATION")
                        print("="*80 + "\n")

                        print("Concierge -> UrgentCare: Please provide workup recommendations\n")
                        concierge_request = Message(
                            id=str(uuid.uuid4()),
                            session_id=session_id,
                            turn_id=state["turn_count"],
                            speaker="agent",
                            agent="Concierge",
                            role="assistant",
                            content="@UrgentCare: Please provide workup recommendations",
                            timestamp=datetime.now()
                        )
                        state["messages"].append(concierge_request)

                        urgent_care_agent = workflow.agents["UrgentCare"]
                        state = urgent_care_agent.process(state)
                        if state["messages"]:
                            last_msg = state["messages"][-1]
                            if last_msg.agent == "UrgentCare":
                                print(f"UrgentCare -> Concierge:\n{last_msg.content}\n")

                        print("Concierge -> Insurance: Coverage for proposed studies\n")
                        concierge_request = Message(
                            id=str(uuid.uuid4()),
                            session_id=session_id,
                            turn_id=state["turn_count"],
                            speaker="agent",
                            agent="Concierge",
                            role="assistant",
                            content="@Insurance: Coverage for proposed studies",
                            timestamp=datetime.now()
                        )
                        state["messages"].append(concierge_request)

                        insurance_agent = workflow.agents["Insurance"]
                        state = insurance_agent.process(state)
                        if state["messages"]:
                            last_msg = state["messages"][-1]
                            if last_msg.agent == "Insurance":
                                print(f"Insurance -> Concierge:\n{last_msg.content}\n")

                        print("Concierge -> Coordinator: Find earliest available appointments\n")
                        concierge_request = Message(
                            id=str(uuid.uuid4()),
                            session_id=session_id,
                            turn_id=state["turn_count"],
                            speaker="agent",
                            agent="Concierge",
                            role="assistant",
                            content="@Coordinator: Find earliest available appointments",
                            timestamp=datetime.now()
                        )
                        state["messages"].append(concierge_request)

                        coordinator_agent = workflow.agents["Coordinator"]
                        state = coordinator_agent.process(state)
                        if state["messages"]:
                            last_msg = state["messages"][-1]
                            if last_msg.agent == "Coordinator":
                                print(f"Coordinator -> Concierge:\n{last_msg.content}\n")

                        state["workflow_status"] = "done"
                        print("="*80)
                        print("CARE PLAN COMPLETE")
                        print("="*80)
                        break
                    else:
                        print(f"Concierge: {concierge_question}\n")
                        patient_response = patient.respond(concierge_question)
                        print(f"Patient: {patient_response}\n")

                        patient_message = Message(
                            id=str(uuid.uuid4()),
                            session_id=session_id,
                            turn_id=state["turn_count"],
                            speaker="user",
                            role="user",
                            content=patient_response,
                            timestamp=datetime.now()
                        )
                        state["messages"].append(patient_message)
                        state["conversation_history"].append(f"Patient: {patient_response}")

        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            traceback.print_exc()
            break

    print(f"\nConversation Status: {state['workflow_status']}")
    print(f"Total Turns: {state['turn_count']}")
    return state


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Run autonomous PatientSim to Concierge conversation"
    )
    parser.add_argument("case_file", help="Path to case JSON file with patient_sim_config")
    parser.add_argument("--max-turns", type=int, default=8, help="Maximum conversation turns")

    args = parser.parse_args()

    try:
        print(f"Loading case: {args.case_file}")
        patient, patient_ehr = create_patient_from_case(args.case_file)

        print("Patient EHR loaded:")
        print(f"  ID: {patient_ehr.patient_id}")
        print(f"  Demographics: {patient_ehr.demographics}")
        print(f"  Insurance: {patient_ehr.insurance.get('plan', 'Unknown')}")

        print("\nInitializing MASH workflow...")
        workflow = MASHWorkflow(max_turns=args.max_turns)

        final_state = run_patient_concierge_conversation(
            patient, workflow, patient_ehr, args.max_turns
        )

        print("\n" + "="*80)
        print("DEMO COMPLETE")
        print("="*80)
        print("\nPhase 1: PatientSim -> Concierge -> Clinical Summary")
        print("Phase 2: Concierge -> [UrgentCare, Insurance, Coordinator] -> Care Plan")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
