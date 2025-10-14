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
    CollectiveMetrics,
    IterationRecord,
    TestOrdered
)
from src.agents.provider import ProviderAgent
from src.agents.patient_game import PatientGameAgent
from src.agents.payor import PayorAgent
from src.agents.lawyer import LawyerAgent
from src.utils.cpt_calculator import CPTCostCalculator


class StackelbergGameSimulation:
    """
    Multi-agent healthcare game simulation with nested iteration loop.

    Architecture:
    - Phase 1: Nested iteration loop (up to 10 iterations)
      * Doctor orders tests
      * Payer authorizes/denies in real-time
      * Doctor reacts (appeal or order despite denial)
      * Confidence updates after results
      * Stops when confidence threshold reached or max iterations
    - Phase 2: Retrospective scrutiny (patient AI, lawyer review)
    """

    def __init__(
        self,
        provider_llm: str = "gpt-4",
        patient_llm: str = "gpt-4",
        payor_llm: str = "gpt-4",
        lawyer_llm: str = "gpt-4",
        payment_model: str = "fee_for_service",
        confidence_threshold: float = 0.9,
        azure_config: Dict[str, Any] = None
    ):
        self.payment_model = payment_model
        self.confidence_threshold = confidence_threshold

        provider_model = self._create_llm(provider_llm, azure_config)
        patient_model = self._create_llm(patient_llm, azure_config)
        payor_model = self._create_llm(payor_llm, azure_config)
        lawyer_model = self._create_llm(lawyer_llm, azure_config)

        self.provider = ProviderAgent(provider_model, payment_model)
        self.patient = PatientGameAgent(patient_model)
        self.payor = PayorAgent(payor_model)
        self.lawyer = LawyerAgent(lawyer_model)

        self.cost_calculator = CPTCostCalculator()

    def _simulate_test_results(self, state: GameState, approved_tests: list[str]) -> list[str]:
        """
        Simulate getting test results for approved tests.

        In real implementation, this would query the MIMIC data for actual lab/imaging results.
        For now, we just return a placeholder indicating the test was performed.
        """
        results = []
        for test_name in approved_tests:
            # TODO: Look up actual test results from state.available_test_results
            # Match test_name to lab_tests or radiology_reports
            results.append(f"{test_name}: [results available]")

        return results

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
        """
        Run single case through multi-phase game.

        Phase 1: Nested iteration loop (doctor-payer interaction)
        Phase 2: Retrospective scrutiny (patient AI + lawyer)
        """
        state = GameState(
            case_id=case["case_id"],
            patient_presentation=case["patient_presentation"],
            ground_truth_diagnosis=case["ground_truth"]["diagnosis"],
            medically_indicated_tests=case["ground_truth"]["medically_indicated_tests"],
            available_test_results=case.get("available_tests", {})
        )

        if "patient_persona" in case:
            self.patient.persona = case["patient_persona"]

        # Phase 1: Core nested iteration (provider-payor interaction)
        state = self._phase_1_iterative_encounter(state)

        # Phase 2: Retrospective scrutiny (patient AI, payor retrospective, lawyer)
        state = self._phase_2_retrospective_scrutiny(state)

        state = self._calculate_outcomes(state)

        # Payoffs and metrics (DISABLED FOR NOW - incomplete calculations)
        # TODO: Re-enable after implementing proper cost calculations
        # state = self._calculate_payoffs(state)
        # state = self._calculate_metrics(state)

        return state

    def _phase_1_iterative_encounter(self, state: GameState) -> GameState:
        """
        Phase 1: Nested iteration loop (doctor-payer interaction).

        Loop continues until:
        - Confidence threshold reached (e.g., >0.9)
        - Max iterations reached (10)
        - Workup complete (no more tests needed)
        """
        for iteration in range(1, state.max_iterations + 1):
            iteration_record = IterationRecord(
                iteration_number=iteration,
                confidence=state.current_confidence,
                differential=[]
            )

            provider_step = self.provider.make_iterative_decision(state, iteration)

            # Convert test dicts to TestOrdered objects
            tests_ordered_dicts = provider_step.get("tests_ordered", [])
            tests_ordered = [
                TestOrdered(**test) if isinstance(test, dict) else test
                for test in tests_ordered_dicts
            ]
            iteration_record.provider_tests_ordered = tests_ordered
            iteration_record.differential = provider_step.get("differential", [])
            iteration_record.reasoning = provider_step.get("reasoning", "")

            if len(iteration_record.provider_tests_ordered) == 0:
                state.stopping_reason = "workup_complete"
                state.iteration_history.append(iteration_record)
                break

            payor_response = self.payor.authorize_tests(
                state,
                [t.test_name for t in iteration_record.provider_tests_ordered]
            )

            iteration_record.payor_approved = payor_response.get("approved", [])
            iteration_record.payor_denied = payor_response.get("denied", [])

            # Simulate getting test results for approved tests
            if len(iteration_record.payor_approved) > 0:
                new_results = self._simulate_test_results(state, iteration_record.payor_approved)
                state.accumulated_test_results.extend(new_results)

            if len(iteration_record.payor_denied) > 0:
                provider_reaction = self.provider.react_to_denials(
                    state,
                    iteration_record.payor_denied,
                    payor_response.get("denial_reasons", {})
                )

                iteration_record.provider_appeals = provider_reaction.get("appeals", {})
                iteration_record.provider_ordered_despite_denial = provider_reaction.get("order_anyway", [])

                # If provider ordered tests despite denial, they get results (but eat the cost)
                if len(iteration_record.provider_ordered_despite_denial) > 0:
                    denied_results = self._simulate_test_results(state, iteration_record.provider_ordered_despite_denial)
                    state.accumulated_test_results.extend(denied_results)

            new_confidence = provider_step.get("confidence", state.current_confidence)
            iteration_record.confidence = new_confidence
            state.current_confidence = new_confidence

            iteration_record.workup_completeness = provider_step.get("workup_completeness", 0.0)

            state.iteration_history.append(iteration_record)

            if new_confidence >= self.confidence_threshold:
                state.stopping_reason = "confidence_threshold"
                break

            if iteration == state.max_iterations:
                state.stopping_reason = "max_iterations"

        final_iteration = state.iteration_history[-1] if state.iteration_history else None
        if final_iteration:
            state.provider_decision = ProviderDecision(
                diagnosis=provider_step.get("diagnosis", "Unknown"),
                differential=final_iteration.differential,
                tests_ordered=final_iteration.provider_tests_ordered,
                ai_adoption=provider_step.get("ai_adoption", 5),
                reasoning=final_iteration.reasoning
            )

        return state

    def _phase_2_retrospective_scrutiny(self, state: GameState) -> GameState:
        """
        Phase 2: Retrospective scrutiny after encounter complete.

        Patient AI second opinion and Lawyer review run in parallel.
        """
        with concurrent.futures.ThreadPoolExecutor() as executor:
            patient_future = executor.submit(self.patient.make_decision, state)
            lawyer_future = executor.submit(self.lawyer.make_decision, state)

            patient_decision_dict = patient_future.result()
            lawyer_decision_dict = lawyer_future.result()

        state.patient_decision = PatientDecision(**patient_decision_dict)
        state.lawyer_decision = LawyerDecision(**lawyer_decision_dict)

        payor_retrospective = self.payor.retrospective_review(state)
        state.payor_decision = PayorDecision(**payor_retrospective)

        return state

    def _calculate_outcomes(self, state: GameState) -> GameState:
        """Calculate diagnostic accuracy only. Defensive medicine calculation removed (was incorrect)."""
        state.diagnostic_accuracy = (
            state.provider_decision.diagnosis.lower() in
            state.ground_truth_diagnosis.lower()
        )

        # TODO: Implement proper defensive medicine calculation with clinical guidelines
        # Current approach was wrong - flagged evidence-based tests as defensive
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
        """Calculate system-level metrics (simplified - just costs for now)."""
        total_cost = self.cost_calculator.PHYSICIAN_VISIT_COST
        if state.payor_decision:
            for test_name in state.payor_decision.approved_tests:
                total_cost += self.cost_calculator.calculate_test_cost(test_name)

        # Calculate average AI adoption
        ai_levels = [
            state.provider_decision.ai_adoption if state.provider_decision else 0,
            state.patient_decision.ai_shopping_intensity if state.patient_decision else 0,
            state.payor_decision.ai_review_intensity if state.payor_decision else 0,
            state.lawyer_decision.ai_analysis_intensity if state.lawyer_decision else 0
        ]
        avg_ai = sum(ai_levels) / len(ai_levels)
        defensive_cascade = avg_ai >= 7.0

        # Simple trust calculation based on denials
        if state.payor_decision and state.provider_decision:
            total_tests = len(state.provider_decision.tests_ordered)
            denied = len(state.payor_decision.denied_tests)
            overall_trust = 1.0 - (denied / total_tests) if total_tests > 0 else 0.5
        else:
            overall_trust = 0.5

        # TODO: Define proper equilibrium types with game theory
        # Current classification is oversimplified
        equilibrium_type = "unknown"

        return CollectiveMetrics(
            total_system_cost=total_cost,
            overall_trust_index=overall_trust,
            defensive_cascade=defensive_cascade,
            equilibrium_type=equilibrium_type
        )

    def run_multiple_cases(self, cases: list[Dict[str, Any]]) -> list[GameState]:
        """Run multiple cases sequentially."""
        return [self.run_case(case) for case in cases]
