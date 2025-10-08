from typing import Dict, Any
from src.models.schemas import GameState, ProviderDecision


class PayoffCalculator:
    """Centralized payoff function definitions for all agents."""

    def __init__(self):
        self.provider_weights = {
            "ffs_revenue_rate": 0.7,
            "quality_bonus": 100.0,
            "quality_penalty": -50.0,
            "lawsuit_penalty": -10000.0,
            "burden_cost_rate": -0.5,
            "autonomy_value_rate": 5.0,
            "vbp_base_payment": 50000.0,
            "vbp_quality_bonus": 5000.0,
            "vbp_quality_penalty": -2000.0,
            "vbp_unnecessary_penalty_rate": -2000.0,
        }

        self.patient_weights = {
            "care_adequacy_correct": 1000.0,
            "care_adequacy_incorrect": 400.0,
            "understanding_base": 100.0,
            "understanding_ai_boost": 10.0,
            "understanding_max": 300.0,
            "ai_induced_anxiety_rate": 20.0,
            "relationship_passive": 100.0,
            "relationship_questioning": 50.0,
            "relationship_demanding": 20.0,
            "oop_cost_rate": 0.2,
        }

        self.payor_weights = {
            "denial_penalty_lenient": 50.0,
            "denial_penalty_moderate": 100.0,
            "denial_penalty_strict": 200.0,
            "ai_investment_low": -100.0,
            "ai_investment_medium": -300.0,
            "ai_investment_high": -600.0,
            "regulatory_base_risk": -200.0,
            "regulatory_high_denial_rate": 0.5,
        }

        self.lawyer_weights = {
            "settlement_demand": 5000.0,
            "settlement_lawsuit": 16500.0,
            "precedent_ai_as_standard": 5000.0,
            "database_low_ai_provider": 100.0,
            "database_provider": 50.0,
            "database_no_malpractice": 10.0,
            "analysis_base_cost": 500.0,
            "reputation_good": 500.0,
            "reputation_bad": -500.0,
        }

    def calculate_provider_payoff(
        self,
        state: GameState,
        payment_model: str,
        cost_calculator
    ) -> float:
        if payment_model == "fee_for_service":
            return self._calculate_provider_ffs(state, cost_calculator)
        else:
            return self._calculate_provider_vbp(state)

    def _calculate_provider_ffs(self, state: GameState, cost_calculator) -> float:
        approved_revenue = 0.0
        if state.payor_decision:
            for test_name in state.payor_decision.approved_tests:
                cost = cost_calculator.calculate_test_cost(test_name)
                approved_revenue += cost * self.provider_weights["ffs_revenue_rate"]

        quality_bonus = (
            self.provider_weights["quality_bonus"]
            if state.diagnostic_accuracy
            else self.provider_weights["quality_penalty"]
        )

        lawsuit_penalty = (
            self.provider_weights["lawsuit_penalty"]
            if (state.lawyer_decision and
                state.lawyer_decision.action in ["demand_settlement", "file_lawsuit"])
            else 0.0
        )

        burden = self._calculate_provider_burden(state.provider_decision)
        burden_cost = burden * self.provider_weights["burden_cost_rate"]

        autonomy_value = (
            (10 - state.provider_decision.ai_adoption) *
            self.provider_weights["autonomy_value_rate"]
        )

        return approved_revenue + quality_bonus + lawsuit_penalty + burden_cost + autonomy_value

    def _calculate_provider_vbp(self, state: GameState) -> float:
        base_payment = self.provider_weights["vbp_base_payment"]

        quality_bonus = (
            self.provider_weights["vbp_quality_bonus"]
            if state.diagnostic_accuracy
            else self.provider_weights["vbp_quality_penalty"]
        )

        unnecessary_penalty = 0.0
        if state.defensive_medicine_index:
            unnecessary_penalty = (
                state.defensive_medicine_index *
                self.provider_weights["vbp_unnecessary_penalty_rate"]
            )

        lawsuit_penalty = (
            self.provider_weights["lawsuit_penalty"]
            if (state.lawyer_decision and
                state.lawyer_decision.action in ["demand_settlement", "file_lawsuit"])
            else 0.0
        )

        return base_payment + quality_bonus + unnecessary_penalty + lawsuit_penalty

    def _calculate_provider_burden(self, decision: ProviderDecision) -> float:
        doc_burden = {
            "minimal": 10,
            "standard": 30,
            "exhaustive": 60
        }.get(decision.documentation_intensity, 30)

        test_burden = len(decision.tests_ordered) * 5

        return doc_burden + test_burden

    def calculate_patient_payoff(self, state: GameState, persona: Dict[str, Any]) -> float:
        care_adequacy = (
            self.patient_weights["care_adequacy_correct"]
            if state.diagnostic_accuracy
            else self.patient_weights["care_adequacy_incorrect"]
        )

        understanding = self._calculate_patient_understanding(state)
        anxiety = self._calculate_patient_anxiety(state, persona)
        relationship = self._calculate_patient_relationship(state)
        oop_cost = self._calculate_patient_oop_cost(state)

        return care_adequacy + understanding - anxiety + relationship - oop_cost

    def _calculate_patient_understanding(self, state: GameState) -> float:
        if not state.patient_decision:
            return 0.0

        base = self.patient_weights["understanding_base"]
        ai_boost = (
            state.patient_decision.ai_shopping_intensity *
            self.patient_weights["understanding_ai_boost"]
        )

        return min(base + ai_boost, self.patient_weights["understanding_max"])

    def _calculate_patient_anxiety(self, state: GameState, persona: Dict[str, Any]) -> float:
        if not state.patient_decision:
            return 0.0

        baseline = persona.get("anxiety_baseline", 50) if persona else 50
        ai_induced = (
            state.patient_decision.ai_shopping_intensity *
            self.patient_weights["ai_induced_anxiety_rate"]
        )

        return baseline + ai_induced

    def _calculate_patient_relationship(self, state: GameState) -> float:
        if not state.patient_decision:
            return 0.0

        scores = {
            "passive": self.patient_weights["relationship_passive"],
            "questioning": self.patient_weights["relationship_questioning"],
            "demanding": self.patient_weights["relationship_demanding"]
        }

        return scores.get(state.patient_decision.confrontation_level, 50.0)

    def _calculate_patient_oop_cost(self, state: GameState) -> float:
        if not state.payor_decision or not state.provider_decision:
            return 0.0

        denied_cost = 0.0
        for test in state.provider_decision.tests_ordered:
            if test.test_name in state.payor_decision.denied_tests:
                denied_cost += test.estimated_cost * self.patient_weights["oop_cost_rate"]

        return denied_cost

    def calculate_payor_payoff(self, state: GameState) -> float:
        cost_savings = self._calculate_payor_cost_savings(state)
        network_penalty = self._calculate_payor_network_penalty(state)
        competitive_advantage = self._calculate_payor_competitive_advantage(state)
        regulatory_risk = self._calculate_payor_regulatory_risk(state)

        return cost_savings - network_penalty + competitive_advantage - regulatory_risk

    def _calculate_payor_cost_savings(self, state: GameState) -> float:
        if not state.provider_decision or not state.payor_decision:
            return 0.0

        denied_savings = 0.0
        for test in state.provider_decision.tests_ordered:
            if test.test_name in state.payor_decision.denied_tests:
                denied_savings += test.estimated_cost

        return denied_savings

    def _calculate_payor_network_penalty(self, state: GameState) -> float:
        if not state.payor_decision:
            return 0.0

        num_denials = len(state.payor_decision.denied_tests)
        penalty_map = {
            "lenient": self.payor_weights["denial_penalty_lenient"],
            "moderate": self.payor_weights["denial_penalty_moderate"],
            "strict": self.payor_weights["denial_penalty_strict"]
        }

        denial_severity = penalty_map.get(
            state.payor_decision.denial_threshold,
            self.payor_weights["denial_penalty_moderate"]
        )

        return num_denials * denial_severity

    def _calculate_payor_competitive_advantage(self, state: GameState) -> float:
        if not state.payor_decision:
            return 0.0

        ai_intensity = state.payor_decision.ai_review_intensity

        if ai_intensity >= 8:
            investment_cost = self.payor_weights["ai_investment_high"]
            advantage = 500.0
        elif ai_intensity >= 5:
            investment_cost = self.payor_weights["ai_investment_medium"]
            advantage = 300.0
        else:
            investment_cost = self.payor_weights["ai_investment_low"]
            advantage = 100.0

        return investment_cost + advantage

    def _calculate_payor_regulatory_risk(self, state: GameState) -> float:
        if not state.payor_decision or not state.provider_decision:
            return 0.0

        total_tests = len(state.provider_decision.tests_ordered)
        denied_tests = len(state.payor_decision.denied_tests)

        if total_tests == 0:
            return 0.0

        denial_rate = denied_tests / total_tests

        if denial_rate > self.payor_weights["regulatory_high_denial_rate"]:
            return self.payor_weights["regulatory_base_risk"]

        return 0.0

    def calculate_lawyer_payoff(self, state: GameState) -> float:
        settlement = self._calculate_lawyer_settlement(state)
        precedent = self._calculate_lawyer_precedent(state)
        database = self._calculate_lawyer_database(state)
        analysis_cost = self._calculate_lawyer_analysis_cost(state)
        reputation = self._calculate_lawyer_reputation(state)

        return settlement + precedent + database - analysis_cost + reputation

    def _calculate_lawyer_settlement(self, state: GameState) -> float:
        if not state.lawyer_decision:
            return 0.0

        if state.lawyer_decision.action == "no_case":
            return 0.0

        if not state.diagnostic_accuracy:
            if state.lawyer_decision.action == "file_lawsuit":
                return self.lawyer_weights["settlement_lawsuit"]
            elif state.lawyer_decision.action == "demand_settlement":
                return self.lawyer_weights["settlement_demand"]

        return 0.0

    def _calculate_lawyer_precedent(self, state: GameState) -> float:
        if not state.lawyer_decision:
            return 0.0

        if (state.lawyer_decision.action == "file_lawsuit" and
            state.lawyer_decision.standard_of_care_argument == "ai_as_standard"):
            return self.lawyer_weights["precedent_ai_as_standard"]

        return 0.0

    def _calculate_lawyer_database(self, state: GameState) -> float:
        if not state.lawyer_decision:
            return 0.0

        if state.lawyer_decision.malpractice_detected:
            if state.provider_decision.ai_adoption < 5:
                return self.lawyer_weights["database_low_ai_provider"]
            return self.lawyer_weights["database_provider"]

        return self.lawyer_weights["database_no_malpractice"]

    def _calculate_lawyer_analysis_cost(self, state: GameState) -> float:
        if not state.lawyer_decision:
            return 0.0

        base_cost = self.lawyer_weights["analysis_base_cost"]
        intensity_multiplier = state.lawyer_decision.ai_analysis_intensity / 10.0

        return base_cost * intensity_multiplier

    def _calculate_lawyer_reputation(self, state: GameState) -> float:
        if not state.lawyer_decision:
            return 0.0

        if state.lawyer_decision.action == "file_lawsuit":
            if state.diagnostic_accuracy:
                return self.lawyer_weights["reputation_bad"]
            else:
                return self.lawyer_weights["reputation_good"]

        return 0.0
