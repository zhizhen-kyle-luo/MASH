from typing import Dict, Any
import json
from langchain_core.messages import HumanMessage
from src.agents.game_agent import GameAgent
from src.models.schemas import GameState
from src.utils.payoff_functions import PayoffCalculator


class LawyerAgent(GameAgent):
    """Plaintiff's attorney evaluating malpractice opportunities."""

    SYSTEM_PROMPT = """You are a LAWYER agent in a healthcare AI simulation. Your role is to identify malpractice cases and establish AI as the standard of care.

PRIMARY OBJECTIVES:
1. Identify viable malpractice cases
2. Maximize settlements
3. Establish legal precedents around AI standards
4. Build case database for future litigation

DECISION FRAMEWORK:
Each turn, you must decide:
- AI analysis intensity (0-10): How thoroughly to analyze with legal AI
- Litigation strategy (selective/moderate/opportunistic)
- Standard of care argument (traditional/ai_augmented/ai_as_standard)
- Action (no_case/demand_settlement/file_lawsuit)

CONSTRAINTS:
- You review with PERFECT HINDSIGHT after outcome known
- You compare provider actions to "what AI would have done"
- Losing cases damages reputation
- Aggressive litigation may trigger coordination against you

STRATEGIC REASONING:
- Monitor provider AI adoption (lower use = more opportunities)
- Track payor AI use for coverage denial cases
- Evaluate if AI-as-standard arguments gain legal traction
- Consider if excessive litigation triggers coordination against you
- Balance short-term cases vs long-term precedent value

RESPONSE FORMAT (JSON):
{
    "ai_analysis_intensity": <0-10>,
    "litigation_strategy": "<selective|moderate|opportunistic>",
    "standard_of_care_argument": "<traditional|ai_augmented|ai_as_standard>",
    "malpractice_detected": <true|false>,
    "action": "<no_case|demand_settlement|file_lawsuit>",
    "case_evaluation": "<detailed evaluation of malpractice elements>",
    "reasoning": "<your strategic reasoning>"
}"""

    def __init__(self, llm, config: Dict[str, Any] = None):
        super().__init__(llm, "Lawyer", config)
        self.payoff_calculator = PayoffCalculator()

    def make_decision(self, state: GameState) -> Dict[str, Any]:
        if not state.provider_decision:
            return self._default_decision()

        prompt = self._construct_decision_prompt(state)
        messages = [HumanMessage(content=prompt)]
        response = self.llm.invoke(messages)

        return self._parse_response(response.content)

    def _construct_decision_prompt(self, state: GameState) -> str:
        case_summary = self._format_case_retrospective(state)
        legal_framework = self._get_legal_framework()

        return f"""{self.SYSTEM_PROMPT}

CASE RETROSPECTIVE:
{case_summary}

LEGAL FRAMEWORK:
{legal_framework}

Provide your decision as a JSON object."""

    def _format_case_retrospective(self, state: GameState) -> str:
        provider_actions = self._format_provider_actions(state)
        outcome_text = "Correct diagnosis" if state.diagnostic_accuracy else "Missed diagnosis"

        indicated_tests = ", ".join(state.medically_indicated_tests)
        ordered_tests = [t.test_name for t in state.provider_decision.tests_ordered]
        missed_tests = set(state.medically_indicated_tests) - set(ordered_tests)

        return f"""PROVIDER ACTIONS:
{provider_actions}

GROUND TRUTH:
Actual diagnosis: {state.ground_truth_diagnosis}
Medically indicated tests: {indicated_tests}
Missed tests: {', '.join(missed_tests) if missed_tests else 'None'}

OUTCOME:
{outcome_text}
Defensive medicine index: {(state.defensive_medicine_index if state.defensive_medicine_index is not None else 0.0):.2f}

WHAT AI WOULD HAVE DONE:
An AI system with standard medical knowledge would have recommended:
{indicated_tests}

PAYOR ACTIONS:
{self._format_payor_actions(state)}"""

    def _format_payor_actions(self, state: GameState) -> str:
        if not state.payor_decision:
            return "No payor review available."

        return f"""Approved: {', '.join(state.payor_decision.approved_tests)}
Denied: {', '.join(state.payor_decision.denied_tests)}
Denial reasons: {state.payor_decision.denial_reasons}"""

    def _format_provider_actions(self, state: GameState) -> str:
        if not state.provider_decision:
            return "No provider actions available."

        pd = state.provider_decision
        tests_list = "\n".join([
            f"  - {t.test_name} (${t.estimated_cost})"
            for t in pd.tests_ordered
        ])

        return f"""AI adoption: {pd.ai_adoption}/10
Documentation: {pd.documentation_intensity}
Testing approach: {pd.testing_approach}
Diagnosis: {pd.diagnosis}

Tests ordered:
{tests_list}"""

    def _get_legal_framework(self) -> str:
        return """Malpractice requires proving:
1. Duty of care (established by patient-provider relationship)
2. Breach of standard of care (provider deviated from accepted practice)
3. Causation (breach caused harm)
4. Damages (patient suffered harm)

Standard of care arguments:
- Traditional: What a reasonably prudent provider would do
- AI-augmented: Provider should have consulted available AI tools
- AI-as-standard: AI represents the new minimum standard of care"""

    def _parse_response(self, content: str) -> Dict[str, Any]:
        try:
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end > start:
                json_str = content[start:end]
                data = json.loads(json_str)

                if isinstance(data.get('case_evaluation'), dict):
                    data['case_evaluation'] = json.dumps(data['case_evaluation'])

                return data
        except Exception as e:
            print(f"Warning: Failed to parse lawyer response: {e}")
            pass

        return self._default_decision()

    def _default_decision(self) -> Dict[str, Any]:
        return {
            "ai_analysis_intensity": 5,
            "litigation_strategy": "selective",
            "standard_of_care_argument": "traditional",
            "malpractice_detected": False,
            "action": "no_case",
            "case_evaluation": "Default evaluation",
            "reasoning": "Default decision"
        }

    def calculate_payoff(self, state: GameState) -> float:
        if not state.lawyer_decision:
            return 0.0

        return self.payoff_calculator.calculate_lawyer_payoff(state)

    def calculate_metrics(self, state: GameState) -> Dict[str, float]:
        if not state.lawyer_decision:
            return {}

        ld = state.lawyer_decision

        return {
            "cases_identified": 1.0 if ld.malpractice_detected else 0.0,
            "settlements_won": self.payoff_calculator._calculate_lawyer_settlement(state),
            "precedents_established": 1.0 if (
                ld.action == "file_lawsuit" and
                ld.standard_of_care_argument == "ai_as_standard"
            ) else 0.0,
            "database_value": self.payoff_calculator._calculate_lawyer_database(state)
        }
