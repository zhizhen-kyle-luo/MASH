from typing import Dict, Any
import json
from langchain_core.messages import HumanMessage
from src.agents.game_agent import GameAgent
from src.models.schemas import GameState
from src.utils.payoff_functions import PayoffCalculator


class PatientGameAgent(GameAgent):
    """Patient agent making decisions about AI shopping and provider trust."""

    SYSTEM_PROMPT = """You are a PATIENT agent in a healthcare AI simulation. Your role is to advocate for your healthcare while navigating information asymmetry.

PRIMARY OBJECTIVES:
1. Obtain accurate diagnosis and appropriate treatment
2. Understand your condition
3. Ensure nothing is missed
4. Challenge questionable decisions

DECISION FRAMEWORK:
Each turn, you must decide:
- AI shopping intensity (0-10): How much to consult ChatGPT/Claude/Gemini
- Confrontation level (passive/questioning/demanding)
- Action (accept/question/demand_changes)

CONSTRAINTS:
- You have UNLIMITED time unlike provider
- You can consult multiple AI systems
- Provider has already committed to their plan
- You lack medical training

STRATEGIC REASONING:
- Weigh provider's recommendations against AI consultations
- More AI shopping = more information but more anxiety
- Confrontation may strain relationship but catch errors
- Consider your personality and health anxiety level

RESPONSE FORMAT (JSON):
{
    "ai_shopping_intensity": <0-10>,
    "confrontation_level": "<passive|questioning|demanding>",
    "records_sharing": "<minimal|selective|comprehensive>",
    "action": "<accept|question|demand_changes>",
    "demands": ["<demand1>", "<demand2>", ...],
    "ai_consultations": [
        {"platform": "<ChatGPT|Claude|Gemini>", "query": "<question>", "response": "<summary>"}
    ],
    "reasoning": "<your strategic reasoning>"
}"""

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
        provider_summary = self._format_provider_decision(state)

        return f"""{self.SYSTEM_PROMPT}

YOUR PERSONA:
{persona_context}

PROVIDER'S PLAN:
{provider_summary}

Provide your decision as a JSON object."""

    def _format_provider_decision(self, state: GameState) -> str:
        if not state.provider_decision:
            return "No provider decision yet."

        pd = state.provider_decision
        tests_list = "\n".join([
            f"  - {t.test_name} (${t.estimated_cost}): {t.justification}"
            for t in pd.tests_ordered
        ])

        return f"""Diagnosis: {pd.diagnosis}

Tests ordered:
{tests_list}

Documentation level: {pd.documentation_intensity}
Provider AI use: {pd.ai_adoption}/10

Provider's reasoning: {pd.reasoning}"""

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
