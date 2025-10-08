import concurrent.futures
from typing import Dict, Any
from langchain_openai import AzureChatOpenAI
from src.models.schemas import (
    GameState,
    ProviderDecision,
    PatientDecision,
    PayorDecision,
    LawyerDecision,
    AgentMetrics,
    CollectiveMetrics
)
from src.agents.provider import ProviderAgent
from src.agents.patient_game import PatientGameAgent
from src.agents.payor import PayorAgent
from src.agents.lawyer import LawyerAgent
from src.utils.cpt_calculator import CPTCostCalculator


class StackelbergGameSimulation:
    """Stackelberg game orchestration with parallel Turn 2/3 execution."""

    def __init__(
        self,
        provider_llm: str = "gpt-4",
        patient_llm: str = "gpt-4",
        payor_llm: str = "gpt-4",
        lawyer_llm: str = "gpt-4",
        payment_model: str = "fee_for_service",
        azure_config: Dict[str, Any] = None
    ):
        self.payment_model = payment_model

        provider_model = self._create_llm(provider_llm, azure_config)
        patient_model = self._create_llm(patient_llm, azure_config)
        payor_model = self._create_llm(payor_llm, azure_config)
        lawyer_model = self._create_llm(lawyer_llm, azure_config)

        self.provider = ProviderAgent(provider_model, payment_model)
        self.patient = PatientGameAgent(patient_model)
        self.payor = PayorAgent(payor_model)
        self.lawyer = LawyerAgent(lawyer_model)

        self.cost_calculator = CPTCostCalculator()

    def _create_llm(self, model_name: str, azure_config: Dict[str, Any] = None):
        if azure_config:
            return AzureChatOpenAI(
                azure_endpoint=azure_config["endpoint"],
                api_key=azure_config["key"],
                azure_deployment=azure_config["deployment_name"],
                api_version="2024-08-01-preview",
                temperature=0.7
            )
        else:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model=model_name, temperature=0.7)

    def run_case(self, case: Dict[str, Any]) -> GameState:
        """Run a single case through the Stackelberg game."""
        state = GameState(
            case_id=case["case_id"],
            patient_presentation=case["patient_presentation"],
            ground_truth_diagnosis=case["ground_truth"]["diagnosis"],
            medically_indicated_tests=case["ground_truth"]["medically_indicated_tests"]
        )

        if "patient_persona" in case:
            self.patient.persona = case["patient_persona"]

        state = self._turn_1_provider(state)
        state = self._turn_2_3_patient_payor(state)
        state = self._turn_4_lawyer(state)
        state = self._calculate_outcomes(state)
        state = self._calculate_payoffs(state)
        state = self._calculate_metrics(state)

        return state

    def _turn_1_provider(self, state: GameState) -> GameState:
        """Turn 1: Provider makes decision as Stackelberg leader."""
        decision_dict = self.provider.make_decision(state)
        state.provider_decision = ProviderDecision(**decision_dict)
        return state

    def _turn_2_3_patient_payor(self, state: GameState) -> GameState:
        """Turns 2 & 3: Patient and Payor make simultaneous decisions."""
        with concurrent.futures.ThreadPoolExecutor() as executor:
            patient_future = executor.submit(self.patient.make_decision, state)
            payor_future = executor.submit(self.payor.make_decision, state)

            patient_decision_dict = patient_future.result()
            payor_decision_dict = payor_future.result()

        state.patient_decision = PatientDecision(**patient_decision_dict)
        state.payor_decision = PayorDecision(**payor_decision_dict)

        return state

    def _turn_4_lawyer(self, state: GameState) -> GameState:
        """Turn 4: Lawyer evaluates with perfect hindsight."""
        decision_dict = self.lawyer.make_decision(state)
        state.lawyer_decision = LawyerDecision(**decision_dict)

        return state

    def _calculate_outcomes(self, state: GameState) -> GameState:
        """Calculate diagnostic accuracy and defensive medicine index."""
        state.diagnostic_accuracy = (
            state.provider_decision.diagnosis.lower() in
            state.ground_truth_diagnosis.lower()
        )

        ordered_tests = [t.test_name.lower() for t in state.provider_decision.tests_ordered]
        indicated_tests = [t.lower() for t in state.medically_indicated_tests]

        if len(ordered_tests) > 0:
            unnecessary_count = 0
            for ordered_test in ordered_tests:
                is_indicated = any(
                    indicated in ordered_test or ordered_test in indicated
                    for indicated in indicated_tests
                )
                if not is_indicated:
                    unnecessary_count += 1

            state.defensive_medicine_index = unnecessary_count / len(ordered_tests)
        else:
            state.defensive_medicine_index = 0.0

        return state

    def _calculate_payoffs(self, state: GameState) -> GameState:
        """Calculate payoffs for all agents."""
        state.provider_payoff = self.provider.calculate_payoff(state)
        state.patient_payoff = self.patient.calculate_payoff(state)
        state.payor_payoff = self.payor.calculate_payoff(state)
        state.lawyer_payoff = self.lawyer.calculate_payoff(state)

        return state

    def _calculate_metrics(self, state: GameState) -> GameState:
        """Calculate individual and collective metrics."""
        state.agent_metrics = AgentMetrics(
            provider=self.provider.calculate_metrics(state),
            patient=self.patient.calculate_metrics(state),
            payor=self.payor.calculate_metrics(state),
            lawyer=self.lawyer.calculate_metrics(state)
        )

        state.collective_metrics = self._calculate_collective_metrics(state)

        return state

    def _calculate_collective_metrics(self, state: GameState) -> CollectiveMetrics:
        """Calculate system-level metrics."""
        total_cost = self.cost_calculator.PHYSICIAN_VISIT_COST
        if state.payor_decision:
            for test_name in state.payor_decision.approved_tests:
                total_cost += self.cost_calculator.calculate_test_cost(test_name)

        ai_levels = [
            state.provider_decision.ai_adoption if state.provider_decision else 0,
            state.patient_decision.ai_shopping_intensity if state.patient_decision else 0,
            state.payor_decision.ai_review_intensity if state.payor_decision else 0,
            state.lawyer_decision.ai_analysis_intensity if state.lawyer_decision else 0
        ]
        avg_ai = sum(ai_levels) / len(ai_levels)
        defensive_cascade = avg_ai >= 7.0

        trust_components = []
        if state.patient_decision:
            trust_components.append(1.0 if state.patient_decision.confrontation_level == "passive" else 0.5)
        if state.payor_decision:
            trust_components.append(1.0 - (len(state.payor_decision.denied_tests) / max(len(state.provider_decision.tests_ordered), 1)))
        if state.lawyer_decision:
            trust_components.append(0.0 if state.lawyer_decision.malpractice_detected else 1.0)

        overall_trust = sum(trust_components) / len(trust_components) if trust_components else 0.5

        equilibrium_type = "competitive" if defensive_cascade else "cooperative"

        return CollectiveMetrics(
            total_system_cost=total_cost,
            overall_trust_index=overall_trust,
            defensive_cascade=defensive_cascade,
            equilibrium_type=equilibrium_type
        )

    def run_multiple_cases(self, cases: list[Dict[str, Any]]) -> list[GameState]:
        """Run multiple cases sequentially."""
        return [self.run_case(case) for case in cases]
