"""
Patient Simulator Integration Module
Uses PatientSim framework to create realistic patient interactions with persona-driven behavior.
"""

import os
from typing import Optional, Dict, Any, List
from patientsim import PatientAgent


class MASHPatientSimulator:
    """
    Wrapper for PatientSim PatientAgent that integrates with MASH healthcare coordination system.

    Provides persona-driven patient simulation using MIMIC-IV/MIMIC-ED datasets with:
    - 6 personality types (plain, verbose, pleasing, impatient, distrust, overanxious)
    - 3 language proficiency levels (A/B/C - CEFR standard)
    - 3 recall levels (no_history, low, high)
    - 3 confusion levels (normal, moderate, high)

    Attributes:
        patient_agent: PatientSim PatientAgent instance
        conversation_history: List of message exchanges
        clinical_context: Accumulated clinical information from conversation
    """

    def __init__(
        self,
        profile_id: Optional[int] = None,
        personality: str = "plain",
        lang_proficiency_level: str = "C",
        recall_level: str = "high",
        confusion_level: str = "normal",
        visit_type: str = "emergency_department",
        model: str = "gpt-4o",
        use_azure: bool = True,
        **ehr_params
    ):
        """
        Initialize patient simulator with persona and clinical profile.

        Args:
            profile_id: Optional MIMIC-based patient profile ID (1-170)
            personality: One of [plain, verbose, pleasing, impatient, distrust, overanxious]
            lang_proficiency_level: CEFR level [A, B, C]
            recall_level: Medical history recall [no_history, low, high]
            confusion_level: Cognitive confusion [normal, moderate, high]
            visit_type: Type of visit [emergency_department, outpatient, ...]
            model: LLM model name (default: gpt-4o)
            use_azure: Whether to use Azure OpenAI (default: True)
            **ehr_params: Additional EHR parameters (age, gender, allergies, etc.)
        """
        self.profile_id = profile_id
        self.personality = personality
        self.lang_proficiency_level = lang_proficiency_level
        self.recall_level = recall_level
        self.confusion_level = confusion_level
        self.visit_type = visit_type

        # Verify and set Azure credentials
        if use_azure:
            self._setup_azure_credentials()

        # Initialize PatientAgent
        try:
            # Use Azure deployment name if using Azure
            if use_azure:
                deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", model)
                self.patient_agent = PatientAgent(
                    model=deployment_name,
                    visit_type=visit_type,
                    personality=personality,
                    recall_level=recall_level,
                    confusion_level=confusion_level,
                    lang_proficiency_level=lang_proficiency_level,
                    use_azure=use_azure,
                    **ehr_params
                )
            else:
                self.patient_agent = PatientAgent(
                    model=model,
                    visit_type=visit_type,
                    personality=personality,
                    recall_level=recall_level,
                    confusion_level=confusion_level,
                    lang_proficiency_level=lang_proficiency_level,
                    use_azure=use_azure,
                    **ehr_params
                )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize PatientAgent: {str(e)}")

        # Track conversation state
        self.conversation_history: List[Dict[str, str]] = []
        self.clinical_context: Dict[str, Any] = {
            "chief_complaint": None,
            "symptoms": [],
            "history": [],
            "concerns": []
        }

    def _setup_azure_credentials(self):
        """
        Setup Azure OpenAI credentials for PatientSim.
        Maps MASH environment variables to PatientSim's expected variable names.
        """
        required_vars = ["AZURE_KEY", "AZURE_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT_NAME"]
        missing = [var for var in required_vars if not os.getenv(var)]

        if missing:
            raise EnvironmentError(
                f"Missing required Azure OpenAI environment variables: {', '.join(missing)}\n"
                "Please set: AZURE_KEY, AZURE_ENDPOINT, AZURE_OPENAI_DEPLOYMENT_NAME"
            )

        # Map MASH env vars to PatientSim expected names
        if not os.getenv("AZURE_OPENAI_API_KEY"):
            os.environ["AZURE_OPENAI_API_KEY"] = os.getenv("AZURE_KEY")
        if not os.getenv("AZURE_OPENAI_ENDPOINT"):
            os.environ["AZURE_OPENAI_ENDPOINT"] = os.getenv("AZURE_ENDPOINT")

        # Set API version if not already set
        if not os.getenv("AZURE_OPENAI_API_VERSION"):
            api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
            os.environ["AZURE_OPENAI_API_VERSION"] = api_version

    def respond(self, clinician_message: str) -> str:
        """
        Generate patient response to clinician message.

        Args:
            clinician_message: Message from the clinician/concierge agent

        Returns:
            Patient's response based on persona and clinical context
        """
        try:
            # Get response from PatientAgent
            response = self.patient_agent(user_prompt=clinician_message)

            # Track conversation
            self.conversation_history.append({
                "clinician": clinician_message,
                "patient": response
            })

            # Extract clinical information (simple keyword-based extraction)
            self._extract_clinical_info(clinician_message, response)

            return response

        except Exception as e:
            raise RuntimeError(f"Error generating patient response: {str(e)}")

    def _extract_clinical_info(self, question: str, response: str):
        """
        Extract and accumulate clinical information from conversation.
        Simple keyword-based extraction for demo purposes.

        Args:
            question: Clinician's question
            response: Patient's response
        """
        # Extract chief complaint
        if any(keyword in question.lower() for keyword in ["brings you", "reason for", "why are you here"]):
            if not self.clinical_context["chief_complaint"]:
                self.clinical_context["chief_complaint"] = response

        # Extract symptoms
        if any(keyword in question.lower() for keyword in ["symptom", "feel", "pain", "experiencing"]):
            self.clinical_context["symptoms"].append(response)

        # Extract history
        if any(keyword in question.lower() for keyword in ["history", "past", "before", "previous"]):
            self.clinical_context["history"].append(response)

        # Extract concerns
        if any(keyword in question.lower() for keyword in ["concern", "worry", "afraid"]):
            self.clinical_context["concerns"].append(response)

    def get_clinical_summary(self) -> Dict[str, Any]:
        """
        Get accumulated clinical information from conversation.

        Returns:
            Dictionary containing extracted clinical context
        """
        return {
            "persona": {
                "personality": self.personality,
                "language_proficiency": self.lang_proficiency_level,
                "recall_level": self.recall_level,
                "confusion_level": self.confusion_level
            },
            "clinical_context": self.clinical_context,
            "conversation_turns": len(self.conversation_history)
        }

    def get_conversation_transcript(self) -> List[Dict[str, str]]:
        """
        Get full conversation history.

        Returns:
            List of conversation exchanges
        """
        return self.conversation_history

    def reset_conversation(self):
        """Reset conversation history while preserving patient profile."""
        self.conversation_history = []
        self.clinical_context = {
            "chief_complaint": None,
            "symptoms": [],
            "history": [],
            "concerns": []
        }


def create_patient_from_profile(profile_id: int, **kwargs) -> MASHPatientSimulator:
    """
    Create patient simulator from a MIMIC-based profile ID.

    Args:
        profile_id: MIMIC patient profile ID (1-170)
        **kwargs: Additional parameters to override profile defaults

    Returns:
        Configured MASHPatientSimulator instance
    """
    return MASHPatientSimulator(profile_id=profile_id, **kwargs)


def create_custom_patient(
    personality: str,
    age: str,
    gender: str,
    chief_complaint: Optional[str] = None,
    **kwargs
) -> MASHPatientSimulator:
    """
    Create custom patient simulator with specific attributes.

    Args:
        personality: Patient personality type
        age: Patient age
        gender: Patient gender
        chief_complaint: Optional chief complaint
        **kwargs: Additional EHR parameters

    Returns:
        Configured MASHPatientSimulator instance
    """
    ehr_params = {"age": age, "gender": gender}
    if chief_complaint:
        ehr_params["chief_complaint"] = chief_complaint
    ehr_params.update(kwargs)

    return MASHPatientSimulator(personality=personality, **ehr_params)
