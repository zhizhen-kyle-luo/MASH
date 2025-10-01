"""
PatientSim persona demonstration.
Shows different patient personalities and communication patterns.
"""

import sys
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from agents.patient_simulator import MASHPatientSimulator


def demo_overanxious_patient():
    """Overanxious patient with low recall."""
    print("\n" + "="*70)
    print("DEMO 1: Overanxious Patient with Low Recall")
    print("="*70)

    patient = MASHPatientSimulator(
        personality="overanxious",
        recall_level="low",
        confusion_level="normal",
        lang_proficiency_level="C",
        age="52",
        gender="female",
        allergies="Penicillin"
    )

    clinician_questions = [
        "Hello, I'm your healthcare concierge. What brings you in today?",
        "How long have you been experiencing these symptoms?",
        "Have you taken any medication for this?",
        "Do you have any other symptoms I should know about?"
    ]

    for question in clinician_questions:
        print(f"\nClinician: {question}")
        response = patient.respond(question)
        print(f"Patient: {response}")

    summary = patient.get_clinical_summary()
    print(f"\nPersona: {summary['persona']['personality']}, Recall: {summary['persona']['recall_level']}")
    print(f"Conversation turns: {summary['conversation_turns']}")


def demo_impatient_confused_patient():
    """Impatient patient with moderate confusion."""
    print("\n" + "="*70)
    print("DEMO 2: Impatient Patient with Moderate Confusion")
    print("="*70)

    patient = MASHPatientSimulator(
        personality="impatient",
        recall_level="high",
        confusion_level="moderate",
        lang_proficiency_level="C",
        age="67",
        gender="male",
        allergies="None known"
    )

    clinician_questions = [
        "Good morning. Can you tell me what's bothering you today?",
        "I understand you're concerned. Can you describe the pain for me?",
        "When did this start happening?"
    ]

    for question in clinician_questions:
        print(f"\nClinician: {question}")
        response = patient.respond(question)
        print(f"Patient: {response}")

    summary = patient.get_clinical_summary()
    print(f"\nPersona: {summary['persona']['personality']}, Confusion: {summary['persona']['confusion_level']}")
    print(f"Conversation turns: {summary['conversation_turns']}")


def demo_verbose_patient():
    """Verbose patient with high recall."""
    print("\n" + "="*70)
    print("DEMO 3: Verbose Patient with High Recall")
    print("="*70)

    patient = MASHPatientSimulator(
        personality="verbose",
        recall_level="high",
        confusion_level="normal",
        lang_proficiency_level="C",
        age="45",
        gender="female",
        allergies="Sulfa drugs"
    )

    clinician_questions = [
        "Hello, what brings you to the emergency department today?",
        "Thank you for that detail. What makes the symptoms worse?"
    ]

    for question in clinician_questions:
        print(f"\nClinician: {question}")
        response = patient.respond(question)
        print(f"Patient: {response}")

    summary = patient.get_clinical_summary()
    print(f"\nPersona: {summary['persona']['personality']}, Recall: {summary['persona']['recall_level']}")
    print(f"Conversation turns: {summary['conversation_turns']}")


def demo_limited_english_patient():
    """Patient with limited English proficiency (Level A)."""
    print("\n" + "="*70)
    print("DEMO 4: Patient with Limited English Proficiency")
    print("="*70)

    patient = MASHPatientSimulator(
        personality="plain",
        recall_level="high",
        confusion_level="normal",
        lang_proficiency_level="A",
        age="38",
        gender="male",
        allergies="None"
    )

    clinician_questions = [
        "Hello, can you tell me why you came to the hospital?",
        "Where does it hurt?",
        "How many days?"
    ]

    for question in clinician_questions:
        print(f"\nClinician: {question}")
        response = patient.respond(question)
        print(f"Patient: {response}")

    summary = patient.get_clinical_summary()
    print(f"\nLanguage Level: {summary['persona']['language_proficiency']}")
    print(f"Conversation turns: {summary['conversation_turns']}")


def main():
    """Run all demos."""
    print("="*70)
    print("MASH PatientSim Persona Demonstrations")
    print("="*70)

    try:
        demo_overanxious_patient()
        demo_impatient_confused_patient()
        demo_verbose_patient()
        demo_limited_english_patient()

        print("\n" + "="*70)
        print("All demos completed")
        print("="*70)

    except Exception as e:
        print(f"\nDemo failed: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
