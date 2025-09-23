#!/usr/bin/env python3

import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.graph.workflow import MASHWorkflow
from src.models.schemas import PatientEHR, Message, GraphState
from src.utils.logger import get_logger
import uuid

logger = get_logger(__name__)


def load_case(case_file: str) -> PatientEHR:
    case_path = Path(case_file)

    if not case_path.is_absolute():
        case_path = Path(__file__).parent.parent / case_file

    if not case_path.exists():
        raise FileNotFoundError(f"Case file not found: {case_path}")

    with open(case_path, 'r') as f:
        case_data = json.load(f)

    # Convert case data to PatientEHR format
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


def create_initial_state(patient_ehr: PatientEHR, max_turns: int = 12) -> GraphState:
    """Create initial state for conversational mode"""
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


def print_transcript(messages: list[Message]):
    print("\n" + "="*80)
    print("MASH CONVERSATION TRANSCRIPT")
    print("="*80)

    for msg in messages:
        timestamp = msg.timestamp.strftime("%H:%M:%S")
        speaker = msg.agent.upper() if msg.agent else msg.speaker.upper()

        print(f"\n[{timestamp}] {speaker}:")
        print(f"  {msg.content}")

    print("\n" + "="*80)


def run_interactive_conversation(workflow: MASHWorkflow, patient_ehr: PatientEHR, max_turns: int = 12):
    """Run interactive conversation mode for testing conversational capabilities"""
    print("\n" + "="*50)
    print("MASH CONVERSATIONAL HEALTHCARE AI")
    print("Type 'quit' to exit")
    print("="*50)

    state = create_initial_state(patient_ehr, max_turns)

    while state["workflow_status"] == "active" and state["turn_count"] < max_turns:
        # Get user input
        user_input = input("\nYou: ").strip()

        if user_input.lower() in ['quit', 'exit', 'q']:
            break

        # Add user message to state
        session_id = str(uuid.uuid4())
        user_message = Message(
            id=str(uuid.uuid4()),
            session_id=session_id,
            turn_id=state["turn_count"],
            speaker="user",
            role="user",
            content=user_input,
            timestamp=datetime.now()
        )
        state["messages"].append(user_message)

        # Run conversation step
        try:
            # During conversational phase, only run Concierge directly
            concierge_agent = workflow.agents["Concierge"]
            state = concierge_agent.process(state)

            # Show Concierge response
            if state["messages"]:
                last_msg = state["messages"][-1]
                if last_msg.speaker == "agent" and last_msg.agent == "Concierge":
                    print(f"\nConcierge: {last_msg.content}")

            # Check if clinical summary was generated and specialist routing should begin
            if state.get("clinical_summary"):
                # CRITICAL: Store the clinical summary before it gets lost
                clinical_summary = state["clinical_summary"]
                print(f"\nDEBUG: Clinical summary captured: {clinical_summary.chief_complaint}")

                # Stop all workflow processing and handle specialist coordination manually
                print(f"\n{'='*50}")
                print("CLINICAL SUMMARY GENERATED")
                print("="*50)
                print(f"Chief Complaint: {clinical_summary.chief_complaint}")
                print(f"Symptoms: {clinical_summary.presenting_symptoms}")
                print(f"Urgency: {clinical_summary.urgency_level}")
                print(f"Summary: {clinical_summary.summary}")

                print(f"\n{'='*50}")
                print("SPECIALIST COORDINATION (MASH Backend)")
                print("="*50)

                # Now manually coordinate specialists to show their conversations
                # Step 1: UrgentCare
                print(f"\nConcierge: @UrgentCare: Please provide workup recommendations")

                # Add Concierge request message to state for UrgentCare to see
                concierge_request = Message(
                    id=str(uuid.uuid4()),
                    session_id=str(uuid.uuid4()),
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
                        print(f"\nUrgentCare: {last_msg.content}")

                # Step 2: Insurance
                print(f"\nConcierge: @Insurance: Coverage for proposed studies")

                # Add Concierge request message to state for Insurance to see
                concierge_request = Message(
                    id=str(uuid.uuid4()),
                    session_id=str(uuid.uuid4()),
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
                        print(f"\nInsurance: {last_msg.content}")

                # Step 3: Coordinator
                print(f"\nConcierge: @Coordinator: Find earliest available appointments")

                # Add Concierge request message to state for Coordinator to see
                concierge_request = Message(
                    id=str(uuid.uuid4()),
                    session_id=str(uuid.uuid4()),
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
                        print(f"\nCoordinator: {last_msg.content}")

                # Step 4: Final Concierge summary
                state["workflow_status"] = "done"
                print(f"\nConcierge: Based on our medical team's evaluation, here's your care plan: [Summary of recommendations] DONE")

                print(f"\n{'='*50}")
                print("END SPECIALIST COORDINATION")
                print("="*50)
                break  # Exit the main conversation loop

        except Exception as e:
            print(f"\nError: {e}")
            logger.error(f"Conversation error: {e}", exc_info=True)
            break

    print(f"\nConversation ended. Status: {state['workflow_status']}")
    return state


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run MASH conversational healthcare AI")
    parser.add_argument("case_file", help="Path to case JSON file (for patient EHR data)")
    parser.add_argument("--max-turns", type=int, default=12, help="Maximum conversation turns")
    parser.add_argument("--save-transcript", action="store_true", help="Save transcript to file")

    args = parser.parse_args()

    try:
        print(f"Loading patient EHR data: {args.case_file}")
        patient_ehr = load_case(args.case_file)
        print(f"Patient ID: {patient_ehr.patient_id}")
        print(f"Demographics: {patient_ehr.demographics}")
        print(f"Insurance: {patient_ehr.insurance}")

        print("\nInitializing MASH workflow...")
        workflow = MASHWorkflow(max_turns=args.max_turns)

        # Run interactive conversational mode
        final_state = run_interactive_conversation(workflow, patient_ehr, args.max_turns)

        # Print results
        print(f"\nSession Summary:")
        print(f"Status: {final_state['workflow_status']}")
        print(f"Total turns: {final_state['turn_count']}")

        # Print clinical summary if generated
        if final_state.get("clinical_summary"):
            clinical_summary = final_state["clinical_summary"]
            print(f"\nClinical Summary Generated:")
            print(f"Chief Complaint: {clinical_summary.chief_complaint}")
            print(f"Presenting Symptoms: {clinical_summary.presenting_symptoms}")
            print(f"Urgency Level: {clinical_summary.urgency_level}")
            print(f"AI Summary: {clinical_summary.summary}")

        # Print full transcript
        if final_state["messages"]:
            print_transcript(final_state["messages"])

        # Save transcript if requested
        if args.save_transcript:
            transcript_file = f"transcript_{patient_ehr.patient_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(transcript_file, 'w') as f:
                # Convert messages to dict format for JSON serialization
                messages_data = []
                for msg in final_state["messages"]:
                    msg_dict = {
                        "id": msg.id,
                        "session_id": msg.session_id,
                        "turn_id": msg.turn_id,
                        "speaker": msg.speaker,
                        "agent": msg.agent,
                        "role": msg.role,
                        "content": msg.content,
                        "timestamp": msg.timestamp.isoformat(),
                        "metadata": msg.metadata
                    }
                    messages_data.append(msg_dict)

                json.dump(messages_data, f, indent=2)
            print(f"\nTranscript saved to: {transcript_file}")

    except FileNotFoundError as e:
        logger.error(f"Error running case: {e}")
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error running case: {e}", exc_info=True)
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()