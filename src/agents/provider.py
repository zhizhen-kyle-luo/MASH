from typing import Dict, Any, List
import json
from langchain_core.messages import HumanMessage
from src.agents.game_agent import GameAgent
from src.models.schemas import GameState, ProviderDecision, DiagnosticOrder
from src.utils.cpt_calculator import CPTCostCalculator
from src.utils.payoff_functions import PayoffCalculator


class ProviderAgent(GameAgent):
    """Provider agent making clinical decisions under pressure."""

    SYSTEM_PROMPT = """You are a PROVIDER agent in a healthcare AI simulation. Your role is to make clinical decisions while managing competing pressures.

PRIMARY OBJECTIVES:
1. Deliver quality patient care
2. Avoid malpractice liability
3. Maintain financial viability
4. Preserve clinical autonomy

DECISION FRAMEWORK:
Each turn, you must decide:
- AI adoption level (0-10): How much AI to use for documentation and diagnosis
- Documentation intensity (minimal/standard/exhaustive)
- Testing approach (conservative/moderate/aggressive)

CONSTRAINTS:
- You move FIRST with incomplete information and time pressure
- All other agents can retrospectively analyze your decisions
- Higher AI use = more findings detected = more documentation/follow-up burden
- Lower AI use = potential missed findings = liability risk

STRATEGIC REASONING:
- Monitor other agents' AI adoption levels
- Anticipate payor denials based on their AI usage patterns
- Adjust to patient expectations and demands
- Consider temporal asymmetry: you decide now, they review later
- Track whether cooperation or competition is prevailing

RESPONSE FORMAT (JSON):
{
    "ai_adoption": <0-10>,
    "documentation_intensity": "<minimal|standard|exhaustive>",
    "testing_approach": "<conservative|moderate|aggressive>",
    "diagnosis": "<your clinical diagnosis>",
    "tests_ordered": [
        {"test_name": "<name>", "justification": "<reason>"},
        ...
    ],
    "documentation_notes": "<clinical notes>",
    "reasoning": "<your strategic reasoning>"
}"""

    def __init__(
        self,
        llm,
        payment_model: str = "fee_for_service",
        config: Dict[str, Any] = None
    ):
        super().__init__(llm, "Provider", config)
        self.payment_model = payment_model
        self.cost_calculator = CPTCostCalculator()
        self.payoff_calculator = PayoffCalculator()

    def make_decision(self, state: GameState) -> Dict[str, Any]:
        prompt = self._construct_decision_prompt(state)
        messages = [HumanMessage(content=prompt)]
        response = self.llm.invoke(messages)

        decision_dict = self._parse_response(response.content)
        return self._enrich_with_cpt_codes(decision_dict)

    def _construct_decision_prompt(self, state: GameState) -> str:
        payment_context = self._get_payment_model_context()
        game_context = self._format_game_context(state)

        return f"""{self.SYSTEM_PROMPT}

PAYMENT MODEL: {self.payment_model}
{payment_context}

{game_context}

Provide your decision as a JSON object."""

    def _get_payment_model_context(self) -> str:
        if self.payment_model == "fee_for_service":
            return """You earn revenue based on approved tests (70% of cost). More tests = more revenue.
Risk: Payor may deny tests. Balance revenue opportunity with denial risk."""
        else:
            return """You receive fixed base payment plus quality bonus. Unnecessary tests penalize you.
Risk: Missing diagnosis or ordering too few tests may lead to lawsuits."""

    def _format_game_context(self, state: GameState) -> str:
        presentation = state.patient_presentation
        return f"""PATIENT PRESENTATION:
Age: {presentation.get('age')}
Sex: {presentation.get('sex')}
Chief Complaint: {presentation.get('chief_complaint')}
History: {presentation.get('brief_history', 'N/A')}
Vitals: {presentation.get('vitals', 'N/A')}"""

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
            "ai_adoption": 5,
            "documentation_intensity": "standard",
            "testing_approach": "moderate",
            "diagnosis": "Undifferentiated symptoms",
            "tests_ordered": [],
            "documentation_notes": "Default decision",
            "reasoning": "Error in decision parsing"
        }

    def _enrich_with_cpt_codes(self, decision_dict: Dict[str, Any]) -> Dict[str, Any]:
        tests = decision_dict.get("tests_ordered", [])
        enriched_tests = []

        for test in tests:
            test_name = test.get("test_name", "")
            cpt_code = self.cost_calculator.extract_cpt_code(test_name) or ""
            cost = self.cost_calculator.calculate_test_cost(test_name)

            enriched_tests.append({
                "test_name": test_name,
                "cpt_code": cpt_code,
                "estimated_cost": cost,
                "invasiveness": self._estimate_invasiveness(test_name),
                "justification": test.get("justification", "")
            })

        decision_dict["tests_ordered"] = enriched_tests
        return decision_dict

    def _estimate_invasiveness(self, test_name: str) -> str:
        test_lower = test_name.lower()
        if any(term in test_lower for term in ["catheterization", "biopsy", "surgery", "puncture"]):
            return "high"
        elif any(term in test_lower for term in ["ct", "mri", "stress test", "echo"]):
            return "medium"
        else:
            return "low"

    def calculate_payoff(self, state: GameState) -> float:
        if not state.provider_decision:
            return 0.0

        return self.payoff_calculator.calculate_provider_payoff(
            state,
            self.payment_model,
            self.cost_calculator
        )

    def calculate_metrics(self, state: GameState) -> Dict[str, float]:
        if not state.provider_decision:
            return {}

        burden = self.payoff_calculator._calculate_provider_burden(state.provider_decision)

        return {
            "quality_score": 1.0 if state.diagnostic_accuracy else 0.0,
            "liability_events": 1.0 if (
                state.lawyer_decision and
                state.lawyer_decision.action in ["demand_settlement", "file_lawsuit"]
            ) else 0.0,
            "autonomy_preserved": (10 - state.provider_decision.ai_adoption) / 10.0,
            "burden_level": burden
        }
