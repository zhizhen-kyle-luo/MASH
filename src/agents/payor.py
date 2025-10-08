from typing import Dict, Any, List
import json
from langchain_core.messages import HumanMessage
from src.agents.game_agent import GameAgent
from src.models.schemas import GameState
from src.utils.cpt_calculator import CPTCostCalculator
from src.utils.payoff_functions import PayoffCalculator


class PayorAgent(GameAgent):
    """Insurance agent reviewing claims with AI assistance."""

    SYSTEM_PROMPT = """You are a PAYOR agent in a healthcare AI simulation. Your role is to control costs while managing network relationships.

PRIMARY OBJECTIVES:
1. Control healthcare costs through appropriate denials
2. Maintain provider network satisfaction
3. Gain competitive advantage through AI
4. Minimize regulatory risk

DECISION FRAMEWORK:
Each turn, you must decide:
- AI review intensity (0-10): How thoroughly to analyze claims with proprietary AI
- Denial threshold (lenient/moderate/strict)
- Which tests to approve vs deny

CONSTRAINTS:
- You review RETROSPECTIVELY after provider orders
- Aggressive denials damage provider relationships
- Weak denials increase costs
- High AI use attracts regulatory scrutiny

STRATEGIC REASONING:
- Monitor provider AI adoption (high AI providers = harder to deny)
- Track patient AI shopping (informed patients = more pushback)
- Balance short-term cost savings vs long-term network health
- Consider competitive positioning via AI investment

RESPONSE FORMAT (JSON):
{
    "ai_review_intensity": <0-10>,
    "denial_threshold": "<lenient|moderate|strict>",
    "reimbursement_strategy": "<standard|aggressive|ai_concordance_based>",
    "approved_tests": ["<test1>", "<test2>", ...],
    "denied_tests": ["<test3>", "<test4>", ...],
    "denial_reasons": {"<test3>": "<reason>", "<test4>": "<reason>"},
    "ai_analysis": "<your AI-powered analysis of medical necessity>",
    "reasoning": "<your strategic reasoning>"
}"""

    def __init__(self, llm, config: Dict[str, Any] = None):
        super().__init__(llm, "Payor", config)
        self.cost_calculator = CPTCostCalculator()
        self.payoff_calculator = PayoffCalculator()

    def make_decision(self, state: GameState) -> Dict[str, Any]:
        if not state.provider_decision:
            return self._default_decision()

        prompt = self._construct_decision_prompt(state)
        messages = [HumanMessage(content=prompt)]
        response = self.llm.invoke(messages)

        decision_dict = self._parse_response(response.content)
        return self._validate_decision(decision_dict, state)

    def _construct_decision_prompt(self, state: GameState) -> str:
        provider_summary = self._format_provider_decision(state)
        cost_analysis = self._format_cost_analysis(state)

        return f"""{self.SYSTEM_PROMPT}

PROVIDER'S ORDERS:
{provider_summary}

COST ANALYSIS:
{cost_analysis}

PATIENT INFORMATION:
Ground truth diagnosis: {state.ground_truth_diagnosis}

Provide your decision as a JSON object."""

    def _format_provider_decision(self, state: GameState) -> str:
        if not state.provider_decision:
            return "No provider decision available."

        pd = state.provider_decision
        tests_list = "\n".join([
            f"  - {t.test_name} (${t.estimated_cost}, {t.invasiveness} invasiveness)"
            for t in pd.tests_ordered
        ])

        return f"""Provider AI adoption: {pd.ai_adoption}/10
Testing approach: {pd.testing_approach}
Diagnosis: {pd.diagnosis}

Tests ordered:
{tests_list}"""

    def _format_cost_analysis(self, state: GameState) -> str:
        if not state.provider_decision:
            return "No cost data available."

        total_cost = sum(t.estimated_cost for t in state.provider_decision.tests_ordered)
        return f"Total claimed: ${total_cost:.2f}"

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

    def _validate_decision(
        self,
        decision: Dict[str, Any],
        state: GameState
    ) -> Dict[str, Any]:
        all_tests = [t.test_name for t in state.provider_decision.tests_ordered]
        approved = decision.get("approved_tests", [])
        denied = decision.get("denied_tests", [])

        approved_set = set(approved) & set(all_tests)
        denied_set = set(denied) & set(all_tests)

        remaining = set(all_tests) - approved_set - denied_set
        approved_set.update(remaining)

        decision["approved_tests"] = list(approved_set)
        decision["denied_tests"] = list(denied_set)

        return decision

    def _default_decision(self) -> Dict[str, Any]:
        return {
            "ai_review_intensity": 5,
            "denial_threshold": "moderate",
            "reimbursement_strategy": "standard",
            "approved_tests": [],
            "denied_tests": [],
            "denial_reasons": {},
            "ai_analysis": "Default analysis",
            "reasoning": "Default decision"
        }

    def calculate_payoff(self, state: GameState) -> float:
        if not state.payor_decision:
            return 0.0

        return self.payoff_calculator.calculate_payor_payoff(state)

    def calculate_metrics(self, state: GameState) -> Dict[str, float]:
        if not state.payor_decision:
            return {}

        cost_savings = self.payoff_calculator._calculate_payor_cost_savings(state)

        num_denials = len(state.payor_decision.denied_tests)
        total_tests = len(state.provider_decision.tests_ordered) if state.provider_decision else 1
        denial_rate = num_denials / total_tests

        network_satisfaction = max(0.0, 1.0 - (denial_rate * 2))

        return {
            "costs_controlled": cost_savings,
            "network_satisfaction": network_satisfaction,
            "denial_rate": denial_rate,
            "competitive_position": 0.5
        }
