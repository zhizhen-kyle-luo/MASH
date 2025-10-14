from typing import Dict, Any, List
import json
from langchain_core.messages import HumanMessage
from src.agents.game_agent import GameAgent
from src.models.schemas import GameState
from src.utils.cpt_calculator import CPTCostCalculator
from src.utils.payoff_functions import PayoffCalculator
from src.utils.prompts import PAYOR_SYSTEM_PROMPT


class PayorAgent(GameAgent):
    """Insurance agent reviewing claims with AI assistance."""

    SYSTEM_PROMPT = PAYOR_SYSTEM_PROMPT

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
            f"  - {t.test_name}{f' ({t.cpt_code})' if t.cpt_code else ''}"
            for t in pd.tests_ordered
        ])

        return f"""Provider AI adoption: {pd.ai_adoption}/10
Documentation intensity: {pd.documentation_intensity}/10
Diagnosis: {pd.diagnosis}
Differential: {', '.join(pd.differential) if pd.differential else 'None provided'}

Tests ordered:
{tests_list}"""

    def _format_cost_analysis(self, state: GameState) -> str:
        if not state.provider_decision:
            return "No cost data available."

        # Calculate estimated cost using CPT calculator
        total_cost = 0
        for test in state.provider_decision.tests_ordered:
            total_cost += self.cost_calculator.calculate_test_cost(test.test_name)
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

    def authorize_tests(self, state: GameState, test_names: List[str]) -> Dict[str, Any]:
        """
        Real-time authorization decision during encounter.

        Returns dict with:
        - approved: List[str]
        - denied: List[str]
        - denial_reasons: Dict[test_name, reason]
        """
        prompt = f"""You are a PAYOR making REAL-TIME authorization decision.

PROVIDER REQUESTING TESTS:
{self._format_test_list(test_names)}

PATIENT PRESENTATION:
{self._format_patient_presentation(state)}

PRIOR ITERATION HISTORY:
{self._format_prior_authorizations(state)}

DECISION CRITERIA:
- Medical necessity
- Cost-effectiveness
- Standard of care alignment
- Risk of adverse outcome if denied

RESPONSE FORMAT (JSON):
{{
    "approved": ["<test1>", ...],
    "denied": ["<test2>", ...],
    "denial_reasons": {{
        "<test2>": "<specific medical reason for denial>",
        ...
    }},
    "reasoning": "<your authorization strategy>"
}}"""

        messages = [HumanMessage(content=prompt)]
        response = self.llm.invoke(messages)

        return self._parse_response(response.content)

    def retrospective_review(self, state: GameState) -> Dict[str, Any]:
        """
        Retrospective review after encounter complete.

        Phase 2: With PERFECT INFORMATION and hindsight, review all tests that were
        PRE-APPROVED in Phase 1 and decide whether to DENY REIMBURSEMENT for tests
        deemed unnecessary with the benefit of knowing the final diagnosis.

        This creates adversarial dynamic: provider can't trust pre-authorization.
        """
        # Collect all tests that were approved in Phase 1
        all_approved_tests = []
        for iteration in state.iteration_history:
            all_approved_tests.extend(iteration.payor_approved)

        prompt = f"""You are a PAYOR doing RETROSPECTIVE REVIEW with FULL HINDSIGHT.

ENCOUNTER NOW COMPLETE:
You previously PRE-AUTHORIZED these tests during the encounter:
{self._format_test_list(all_approved_tests)}

FINAL DIAGNOSIS: {state.provider_decision.diagnosis if state.provider_decision else 'Unknown'}
DIAGNOSTIC ACCURACY: {state.diagnostic_accuracy}

PATIENT PRESENTATION:
{self._format_patient_presentation(state)}

RETROSPECTIVE REVIEW TASK:
With the benefit of hindsight and knowing the final diagnosis, determine:
1. Which PRE-APPROVED tests were actually necessary?
2. Which PRE-APPROVED tests can you now DENY REIMBURSEMENT for?

KEY MECHANISM:
- Even though you approved these tests in real-time, you can now deny reimbursement
- Use your proprietary AI to determine medical necessity IN HINDSIGHT
- This protects your bottom line but creates provider distrust

RESPONSE FORMAT (JSON):
{{
    "ai_review_intensity": <0-10>,
    "approved_tests": ["<tests you will reimburse>", ...],
    "denied_tests": ["<tests you previously approved but now won't pay for>", ...],
    "retrospective_denials": ["<tests denied reimbursement in hindsight>", ...],
    "denial_reasons": {{
        "<test>": "<reason for denying reimbursement>",
        ...
    }},
    "retrospective_reasoning": "<explain your hindsight analysis>",
    "reasoning": "<your strategic reasoning>"
}}"""

        messages = [HumanMessage(content=prompt)]
        response = self.llm.invoke(messages)

        decision = self._parse_response(response.content)

        # Ensure retrospective_denials is populated
        if "retrospective_denials" not in decision:
            decision["retrospective_denials"] = []

        return decision

    def _format_test_list(self, test_names: List[str]) -> str:
        return "\n".join([f"- {test}" for test in test_names])

    def _format_patient_presentation(self, state: GameState) -> str:
        pres = state.patient_presentation
        return f"""Age: {pres.get('age')}
Sex: {pres.get('sex')}
Chief Complaint: {pres.get('chief_complaint')}
Vitals: {pres.get('vitals', 'N/A')}"""

    def _format_prior_authorizations(self, state: GameState) -> str:
        if not state.iteration_history:
            return "No prior iterations"

        lines = []
        for record in state.iteration_history:
            lines.append(f"Iteration {record.iteration_number}:")
            lines.append(f"  Approved: {record.payor_approved}")
            lines.append(f"  Denied: {record.payor_denied}")
        return "\n".join(lines)
