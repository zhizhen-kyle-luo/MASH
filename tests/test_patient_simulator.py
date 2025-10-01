"""
Tests for PatientSim integration with MASH system.
Validates Azure OpenAI connectivity and patient interaction flow.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from agents.patient_simulator import MASHPatientSimulator


def test_azure_credentials():
    """Verify Azure OpenAI credentials are configured."""
    print("Testing Azure OpenAI credentials...")

    required_vars = ["AZURE_KEY", "AZURE_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT_NAME"]
    missing = [var for var in required_vars if not os.getenv(var)]

    if missing:
        print(f"FAIL: Missing environment variables: {', '.join(missing)}")
        return False

    print("PASS: Azure credentials configured")
    return True


def test_patient_initialization():
    """Test patient simulator initialization."""
    print("\nTesting patient simulator initialization...")

    try:
        patient = MASHPatientSimulator(
            personality="plain",
            age="45",
            gender="male",
            lang_proficiency_level="C",
            recall_level="high",
            confusion_level="normal",
            model="gpt-4o",
            use_azure=True
        )
        print("PASS: Patient simulator initialized")
        print(f"  Persona: {patient.personality}, Language: {patient.lang_proficiency_level}")
        print(f"  Recall: {patient.recall_level}, Confusion: {patient.confusion_level}")
        return patient

    except Exception as e:
        print(f"FAIL: Initialization failed - {str(e)}")
        return None


def test_conversation_flow(patient: MASHPatientSimulator):
    """Test multi-turn conversation."""
    print("\nTesting conversation flow...")

    try:
        question = "Hello, I'm your healthcare concierge. What brings you in today?"
        print(f"\nClinician: {question}")

        response = patient.respond(question)
        print(f"Patient: {response}")

        question2 = "Can you tell me more about when these symptoms started?"
        print(f"\nClinician: {question2}")

        response2 = patient.respond(question2)
        print(f"Patient: {response2}")

        history = patient.get_conversation_transcript()
        print(f"\nPASS: Conversation flow working ({len(history)} exchanges)")

        summary = patient.get_clinical_summary()
        print(f"\nClinical Summary:")
        print(f"  Chief Complaint: {summary['clinical_context']['chief_complaint']}")
        print(f"  Symptoms: {len(summary['clinical_context']['symptoms'])} noted")

        return True

    except Exception as e:
        print(f"FAIL: Conversation test failed - {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_persona_configurations():
    """Test multiple persona configurations."""
    print("\nTesting persona configurations...")

    personas = [
        {"personality": "overanxious", "recall_level": "low"},
        {"personality": "impatient", "confusion_level": "moderate"},
        {"personality": "verbose", "lang_proficiency_level": "B"}
    ]

    for i, persona_config in enumerate(personas, 1):
        try:
            patient = MASHPatientSimulator(
                age="55",
                gender="female",
                use_azure=True,
                **persona_config
            )
            print(f"PASS: Persona {i} - {persona_config}")
        except Exception as e:
            print(f"FAIL: Persona {i} failed - {str(e)}")
            return False

    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("MASH PatientSim Integration Tests")
    print("=" * 60)

    if not test_azure_credentials():
        print("\nCannot proceed without Azure credentials")
        print("Required: AZURE_KEY, AZURE_ENDPOINT, AZURE_OPENAI_DEPLOYMENT_NAME")
        return

    patient = test_patient_initialization()
    if not patient:
        print("\nTests failed at initialization")
        return

    if not test_conversation_flow(patient):
        print("\nTests failed at conversation flow")
        return

    if not test_persona_configurations():
        print("\nTests failed at persona configuration")
        return

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
