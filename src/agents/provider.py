from typing import Dict, Any, List
import json
from langchain_core.messages import HumanMessage
from src.agents.game_agent import GameAgent
from src.models.schemas import GameState, ProviderDecision, TestOrdered
from src.utils.cpt_calculator import CPTCostCalculator
from src.utils.payoff_functions import PayoffCalculator
from src.utils.prompts import PROVIDER_SYSTEM_PROMPT, PROVIDER_CONFIDENCE_GUIDELINES


class ProviderAgent(GameAgent):
    """Provider agent making clinical decisions under pressure."""

    SYSTEM_PROMPT = PROVIDER_SYSTEM_PROMPT

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
        """Legacy method - not used. Use make_iterative_decision() instead."""
        return {"error": "Use make_iterative_decision() for provider decisions"}

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
                state.lawyer_decision.litigation_recommendation in ["demand_letter", "lawsuit"]
            ) else 0.0,
            "autonomy_preserved": (10 - state.provider_decision.ai_adoption) / 10.0,
            "burden_level": burden
        }

    def make_iterative_decision(self, state: GameState, iteration: int) -> Dict[str, Any]:
        """
        Make decision in iterative encounter loop.

        Returns dict with:
        - tests_ordered: List[TestOrdered]
        - differential: List[str]
        - confidence: float (0-1)
        - workup_completeness: float (0-1)
        - diagnosis: str
        - reasoning: str
        """
        prior_tests = []
        for iter_record in state.iteration_history:
            prior_tests.extend([t.test_name for t in iter_record.provider_tests_ordered])

        prompt = f"""{self.SYSTEM_PROMPT}

ITERATIVE DIAGNOSTIC SESSION - Iteration {iteration}/{state.max_iterations}

PATIENT PRESENTATION:
{self._format_game_context(state)}

PRIOR ITERATIONS:
{self._format_iteration_history(state.iteration_history)}

TEST RESULTS RECEIVED SO FAR:
{self._format_test_results(state.accumulated_test_results)}

CURRENT CONFIDENCE: {state.current_confidence:.2f}

{PROVIDER_CONFIDENCE_GUIDELINES}

Your task: Analyze available test results. Order next round of tests to refine diagnosis. Update your confidence based on the guidelines above.

RESPONSE FORMAT (JSON):
{{
    "tests_ordered": [
        {{"test_name": "<name>", "rationale": "<reason>"}},
        ...
    ],
    "differential": ["<diagnosis 1>", "<diagnosis 2>", ...],
    "confidence": <0.0-1.0>,
    "workup_completeness": <0.0-1.0>,
    "diagnosis": "<primary diagnosis>",
    "ai_adoption": <0-10>,
    "reasoning": "<clinical reasoning>"
}}

If workup is complete and you are confident, return empty tests_ordered list."""

        messages = [HumanMessage(content=prompt)]
        response = self.llm.invoke(messages)

        decision_dict = self._parse_response(response.content)
        return self._enrich_with_cpt_codes(decision_dict)

    def react_to_denials(
        self,
        state: GameState,
        denied_tests: List[str],
        denial_reasons: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        React to payer denials.

        Returns dict with:
        - appeals: Dict[test_name, appeal_justification]
        - order_anyway: List[test_name] (tests ordered despite denial)
        """
        prompt = f"""You are a PROVIDER reacting to PAYER denials.

DENIED TESTS:
{self._format_denials(denied_tests, denial_reasons)}

CURRENT CASE:
{self._format_game_context(state)}

OPTIONS:
1. APPEAL: Provide additional justification for medical necessity
2. ORDER ANYWAY: Order test and "eat cost" (you pay out of pocket)
3. ACCEPT: Move on without test

STRATEGIC CONSIDERATIONS:
- Appeals take time and may not succeed
- Ordering anyway costs you money but protects against liability
- Accepting denial may lead to missed diagnosis and lawsuit

RESPONSE FORMAT (JSON):
{{
    "appeals": {{
        "<test_name>": "<appeal justification>",
        ...
    }},
    "order_anyway": ["<test_name>", ...],
    "reasoning": "<strategic reasoning>"
}}"""

        messages = [HumanMessage(content=prompt)]
        response = self.llm.invoke(messages)

        return self._parse_response(response.content)

    def _format_iteration_history(self, history: List) -> str:
        if not history:
            return "No prior iterations"

        lines = []
        for record in history:
            lines.append(f"Iteration {record.iteration_number}:")
            lines.append(f"  Tests ordered: {[t.test_name for t in record.provider_tests_ordered]}")
            lines.append(f"  Approved: {record.payor_approved}")
            lines.append(f"  Denied: {record.payor_denied}")
            lines.append(f"  Confidence: {record.confidence:.2f}")
            lines.append(f"  Differential: {record.differential}")
        return "\n".join(lines)

    def _format_denials(self, denied_tests: List[str], reasons: Dict[str, str]) -> str:
        lines = []
        for test in denied_tests:
            reason = reasons.get(test, "No reason provided")
            lines.append(f"- {test}: {reason}")
        return "\n".join(lines)

    def _format_test_results(self, accumulated_results: List[str]) -> str:
        """Format accumulated test results for provider to analyze."""
        if not accumulated_results:
            return "No test results available yet (first iteration)"

        return "\n".join([f"  - {result}" for result in accumulated_results])
