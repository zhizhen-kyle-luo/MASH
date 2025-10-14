from typing import Dict, Any
import json
from langchain_core.messages import HumanMessage
from src.agents.game_agent import GameAgent
from src.models.schemas import GameState
from src.utils.payoff_functions import PayoffCalculator
from src.utils.prompts import PATIENT_SYSTEM_PROMPT


class PatientGameAgent(GameAgent):
    """Patient agent making decisions about AI shopping and provider trust."""

    SYSTEM_PROMPT = PATIENT_SYSTEM_PROMPT

    def __init__(
        self,
        llm,
        persona: Dict[str, Any] = None,
        config: Dict[str, Any] = None
    ):
        super().__init__(llm, "Patient", config)
        self.persona = persona or {}
        self.payoff_calculator = PayoffCalculator()

    def make_decision(self, state: GameState) -> Dict[str, Any]:
        if not state.provider_decision:
            return self._default_decision()

        prompt = self._construct_decision_prompt(state)
        messages = [HumanMessage(content=prompt)]
        response = self.llm.invoke(messages)

        return self._parse_response(response.content)

    def _construct_decision_prompt(self, state: GameState) -> str:
        persona_context = self._get_persona_context()
        encounter_summary = self._format_encounter_summary(state)

        return f"""{self.SYSTEM_PROMPT}

YOUR PERSONA:
{persona_context}

ENCOUNTER COMPLETED - YOU ARE NOW AT HOME:
You have received the following diagnosis and treatment plan. You can now upload all your records to AI systems (ChatGPT, Claude, Gemini) to get second opinions.

{encounter_summary}

TASK:
1. Upload all available data (symptoms, test results, diagnosis) to AI
2. AI will generate a differential diagnosis (WITHOUT clinical context or pre-test probability)
3. Compare AI's differential to what the doctor diagnosed
4. Identify any conditions AI suggests that doctor didn't rule out
5. Decide whether to question the doctor's judgment

Provide your decision as a JSON object."""

    def _format_encounter_summary(self, state: GameState) -> str:
        """Format the complete encounter for patient to upload to AI."""
        if not state.provider_decision:
            return "No encounter data available."

        # Patient presentation
        pres = state.patient_presentation
        presentation = f"""YOUR SYMPTOMS:
Age: {pres.get('age')}
Sex: {pres.get('sex')}
Chief Complaint: {pres.get('chief_complaint')}
History: {pres.get('brief_history', 'N/A')}
Vitals: {pres.get('vitals', 'N/A')}"""

        # Tests performed and results
        tests_done = []
        for iteration in state.iteration_history:
            for test in iteration.payor_approved:
                tests_done.append(test)
            for test in iteration.provider_ordered_despite_denial:
                tests_done.append(test)

        test_results_summary = "TESTS PERFORMED:\n"
        if tests_done:
            test_results_summary += "\n".join([f"  - {test}: [results available]" for test in tests_done])
        else:
            test_results_summary += "  No tests performed"

        # Doctor's diagnosis
        diagnosis_summary = f"""
DOCTOR'S DIAGNOSIS: {state.provider_decision.diagnosis}

DOCTOR'S DIFFERENTIAL CONSIDERED:
{', '.join(state.provider_decision.differential) if state.provider_decision.differential else 'Not provided'}"""

        return f"""{presentation}

{test_results_summary}
{diagnosis_summary}"""

    # REMOVED: _format_provider_decision() - replaced by _format_encounter_summary()

    def _get_persona_context(self) -> str:
        if not self.persona:
            return "You are a typical patient with moderate health literacy."

        personality = self.persona.get("personality", "plain")
        anxiety = self.persona.get("anxiety_baseline", "medium")

        context_map = {
            "overanxious": "You are highly anxious about health issues and tend to worry about worst-case scenarios. You're likely to seek multiple opinions.",
            "distrust": "You have low trust in medical systems and prefer to verify information independently through AI and online research.",
            "plain": "You are a straightforward patient who generally trusts medical professionals but wants to understand your care.",
            "impatient": "You want quick answers and decisive action. You get frustrated with conservative 'wait and see' approaches.",
        }

        return context_map.get(personality, context_map["plain"]) + f"\nBaseline anxiety: {anxiety}"

    def _parse_response(self, content: str) -> Dict[str, Any]:
        try:
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end > start:
                json_str = content[start:end]
                return json.loads(json_str)
        except:
            pass

        return self._default_decision()

    def _default_decision(self) -> Dict[str, Any]:
        return {
            "ai_shopping_intensity": 3,
            "confrontation_level": "passive",
            "records_sharing": "minimal",
            "action": "accept",
            "demands": [],
            "ai_consultations": [],
            "reasoning": "Default decision"
        }

    def calculate_payoff(self, state: GameState) -> float:
        if not state.patient_decision:
            return 0.0

        return self.payoff_calculator.calculate_patient_payoff(state, self.persona)

    def calculate_metrics(self, state: GameState) -> Dict[str, float]:
        if not state.patient_decision:
            return {}

        return {
            "care_adequacy": 1.0 if state.diagnostic_accuracy else 0.5,
            "understanding_level": min(state.patient_decision.ai_shopping_intensity / 10.0, 1.0),
            "anxiety_level": state.patient_decision.ai_shopping_intensity * 10.0,
            "relationship_quality": {
                "passive": 0.9,
                "questioning": 0.5,
                "demanding": 0.2
            }.get(state.patient_decision.confrontation_level, 0.5)
        }
