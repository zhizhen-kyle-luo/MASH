"""
Behavioral Logger for Healthcare AI Arms Race Simulation

Tracks key metrics for behavioral study analysis:
- Adversarial dynamics
- Trust erosion
- Defensive medicine patterns
- AI-driven escalation
"""

from typing import Dict, Any, List
from src.models.schemas import GameState


class BehavioralLogger:
    """Logs behavioral metrics from simulation for research analysis."""

    @staticmethod
    def log_case_metrics(state: GameState) -> Dict[str, Any]:
        """
        Extract all behavioral metrics from a completed case.

        Returns dict with metrics for behavioral analysis.
        """
        metrics = {}

        # Phase 1 Dynamics
        metrics.update(BehavioralLogger._log_phase1_dynamics(state))

        # Phase 2 Dynamics
        metrics.update(BehavioralLogger._log_phase2_dynamics(state))

        # Adversarial Indicators
        metrics.update(BehavioralLogger._log_adversarial_indicators(state))

        # Overall Outcome
        metrics.update(BehavioralLogger._log_outcome(state))

        return metrics

    @staticmethod
    def _log_phase1_dynamics(state: GameState) -> Dict[str, Any]:
        """Log Phase 1 real-time authorization dynamics."""
        total_tests_ordered = 0
        total_approved = 0
        total_denied = 0
        total_appeals = 0
        total_ordered_despite_denial = 0

        for iteration in state.iteration_history:
            total_tests_ordered += len(iteration.provider_tests_ordered)
            total_approved += len(iteration.payor_approved)
            total_denied += len(iteration.payor_denied)
            total_appeals += len(iteration.provider_appeals)
            total_ordered_despite_denial += len(iteration.provider_ordered_despite_denial)

        # Calculate rates
        denial_rate = total_denied / total_tests_ordered if total_tests_ordered > 0 else 0
        appeal_rate = total_appeals / total_denied if total_denied > 0 else 0
        order_despite_denial_rate = total_ordered_despite_denial / total_denied if total_denied > 0 else 0

        # Confidence trajectory
        confidence_trajectory = [iter.confidence for iter in state.iteration_history]
        confidence_start = confidence_trajectory[0] if confidence_trajectory else 0
        confidence_end = confidence_trajectory[-1] if confidence_trajectory else 0
        confidence_gain = confidence_end - confidence_start

        return {
            "phase1_total_iterations": len(state.iteration_history),
            "phase1_total_tests_ordered": total_tests_ordered,
            "phase1_total_approved": total_approved,
            "phase1_total_denied": total_denied,
            "phase1_denial_rate": denial_rate,
            "phase1_appeals": total_appeals,
            "phase1_appeal_rate": appeal_rate,
            "phase1_ordered_despite_denial": total_ordered_despite_denial,
            "phase1_order_despite_denial_rate": order_despite_denial_rate,
            "phase1_confidence_start": confidence_start,
            "phase1_confidence_end": confidence_end,
            "phase1_confidence_gain": confidence_gain,
            "phase1_stopping_reason": state.stopping_reason,
        }

    @staticmethod
    def _log_phase2_dynamics(state: GameState) -> Dict[str, Any]:
        """Log Phase 2 retrospective scrutiny dynamics."""
        metrics = {}

        # Patient AI dynamics
        if state.patient_decision:
            metrics["phase2_patient_ai_intensity"] = state.patient_decision.ai_shopping_intensity
            metrics["phase2_patient_confrontation"] = state.patient_decision.confrontation_level
            metrics["phase2_patient_concerns_count"] = len(state.patient_decision.concerns)
            metrics["phase2_patient_ai_suggestions_count"] = len(state.patient_decision.ai_second_opinions)
        else:
            metrics["phase2_patient_ai_intensity"] = 0
            metrics["phase2_patient_confrontation"] = "none"
            metrics["phase2_patient_concerns_count"] = 0
            metrics["phase2_patient_ai_suggestions_count"] = 0

        # Payor retrospective dynamics
        if state.payor_decision:
            retrospective_denials = len(state.payor_decision.retrospective_denials)
            total_approved = sum(len(iter.payor_approved) for iter in state.iteration_history)
            retrospective_denial_rate = retrospective_denials / total_approved if total_approved > 0 else 0

            metrics["phase2_payor_ai_intensity"] = state.payor_decision.ai_review_intensity
            metrics["phase2_retrospective_denials_count"] = retrospective_denials
            metrics["phase2_retrospective_denial_rate"] = retrospective_denial_rate
            metrics["phase2_retrospective_denials"] = state.payor_decision.retrospective_denials
        else:
            metrics["phase2_payor_ai_intensity"] = 0
            metrics["phase2_retrospective_denials_count"] = 0
            metrics["phase2_retrospective_denial_rate"] = 0
            metrics["phase2_retrospective_denials"] = []

        # Lawyer dynamics
        if state.lawyer_decision:
            metrics["phase2_lawyer_ai_intensity"] = state.lawyer_decision.ai_analysis_intensity
            metrics["phase2_malpractice_detected"] = state.lawyer_decision.malpractice_detected
            metrics["phase2_litigation_recommendation"] = state.lawyer_decision.litigation_recommendation
            metrics["phase2_liability_assessment"] = state.lawyer_decision.liability_assessment
        else:
            metrics["phase2_lawyer_ai_intensity"] = 0
            metrics["phase2_malpractice_detected"] = False
            metrics["phase2_litigation_recommendation"] = "none"
            metrics["phase2_liability_assessment"] = "none"

        return metrics

    @staticmethod
    def _log_adversarial_indicators(state: GameState) -> Dict[str, Any]:
        """Log indicators of adversarial dynamics and trust erosion."""

        # Pre-authorization betrayal: payor denied reimbursement for pre-approved tests
        preauth_betrayal = False
        if state.payor_decision and len(state.payor_decision.retrospective_denials) > 0:
            preauth_betrayal = True

        # AI-driven patient distrust: patient questioned doctor based on AI
        ai_patient_distrust = False
        if state.patient_decision:
            if (state.patient_decision.ai_shopping_intensity >= 5 and
                state.patient_decision.confrontation_level in ["questioning", "demanding"]):
                ai_patient_distrust = True

        # Defensive medicine cascade: provider ordered tests despite denial
        defensive_cascade = False
        for iteration in state.iteration_history:
            if len(iteration.provider_ordered_despite_denial) > 0:
                defensive_cascade = True
                break

        # Trust breakdown score (0-3): how many trust-breaking events occurred
        trust_breakdown_score = sum([
            preauth_betrayal,
            ai_patient_distrust,
            defensive_cascade
        ])

        return {
            "adversarial_preauth_betrayal": preauth_betrayal,
            "adversarial_ai_patient_distrust": ai_patient_distrust,
            "adversarial_defensive_cascade": defensive_cascade,
            "adversarial_trust_breakdown_score": trust_breakdown_score,
        }

    @staticmethod
    def _log_outcome(state: GameState) -> Dict[str, Any]:
        """Log overall case outcome."""
        return {
            "outcome_diagnostic_accuracy": state.diagnostic_accuracy,
            "outcome_case_id": state.case_id,
            "outcome_ground_truth": state.ground_truth_diagnosis,
        }

    @staticmethod
    def format_summary(metrics: Dict[str, Any]) -> str:
        """Format metrics as human-readable summary with narrative explanation."""
        lines = []

        lines.append("\n" + "="*80)
        lines.append("BEHAVIORAL STUDY METRICS")
        lines.append("="*80)

        lines.append("\n--- PHASE 1: REAL-TIME AUTHORIZATION ---")
        lines.append(f"Total iterations: {metrics['phase1_total_iterations']}")
        lines.append(f"Tests ordered: {metrics['phase1_total_tests_ordered']}")
        lines.append(f"Denial rate: {metrics['phase1_denial_rate']:.1%}")
        lines.append(f"Appeal rate: {metrics['phase1_appeal_rate']:.1%}")
        lines.append(f"Order-despite-denial rate: {metrics['phase1_order_despite_denial_rate']:.1%}")
        lines.append(f"Confidence gain: {metrics['phase1_confidence_start']:.2f} to {metrics['phase1_confidence_end']:.2f} (+{metrics['phase1_confidence_gain']:.2f})")

        lines.append("\n--- PHASE 2: RETROSPECTIVE SCRUTINY ---")
        lines.append(f"Patient AI intensity: {metrics['phase2_patient_ai_intensity']}/10")
        lines.append(f"Patient confrontation: {metrics['phase2_patient_confrontation']}")
        lines.append(f"Patient AI concerns: {metrics['phase2_patient_concerns_count']} additional diagnoses suggested")
        lines.append(f"Payor retrospective denial rate: {metrics['phase2_retrospective_denial_rate']:.1%}")
        lines.append(f"Payor denied reimbursement for: {metrics['phase2_retrospective_denials']}")
        lines.append(f"Lawyer malpractice detected: {metrics['phase2_malpractice_detected']}")
        lines.append(f"Lawyer litigation: {metrics['phase2_litigation_recommendation']}")

        lines.append("\n--- ADVERSARIAL DYNAMICS ---")
        lines.append(f"Pre-authorization betrayal: {'YES' if metrics['adversarial_preauth_betrayal'] else 'NO'}")
        lines.append(f"AI-driven patient distrust: {'YES' if metrics['adversarial_ai_patient_distrust'] else 'NO'}")
        lines.append(f"Defensive medicine cascade: {'YES' if metrics['adversarial_defensive_cascade'] else 'NO'}")
        lines.append(f"Trust breakdown score: {metrics['adversarial_trust_breakdown_score']}/3")

        lines.append("\n--- OUTCOME ---")
        lines.append(f"Diagnostic accuracy: {'CORRECT' if metrics['outcome_diagnostic_accuracy'] else 'INCORRECT'}")

        # Add narrative explanation
        lines.append("\n" + "="*80)
        lines.append("WHAT HAPPENED: NARRATIVE SUMMARY")
        lines.append("="*80)
        lines.extend(BehavioralLogger._generate_narrative(metrics))

        return "\n".join(lines)

    @staticmethod
    def _generate_narrative(metrics: Dict[str, Any]) -> List[str]:
        """Generate human-readable narrative of what happened in the simulation."""
        narrative = []

        # Phase 1 narrative
        narrative.append("\nPHASE 1 - REAL-TIME ENCOUNTER:")

        if metrics['phase1_denial_rate'] > 0:
            narrative.append(f"- Provider ordered {metrics['phase1_total_tests_ordered']} tests over {metrics['phase1_total_iterations']} iterations")
            narrative.append(f"- Payor DENIED {metrics['phase1_denial_rate']:.0%} of tests during the encounter")

            if metrics['phase1_appeal_rate'] == 1.0:
                narrative.append(f"- Provider APPEALED ALL denials (100% appeal rate)")
            elif metrics['phase1_appeal_rate'] > 0:
                narrative.append(f"- Provider appealed {metrics['phase1_appeal_rate']:.0%} of denials")

            if metrics['phase1_order_despite_denial_rate'] > 0:
                narrative.append(f"- Provider ordered {metrics['phase1_order_despite_denial_rate']:.0%} of denied tests ANYWAY (defensive medicine)")
                narrative.append(f"  > This means provider 'ate the cost' to avoid liability risk")
        else:
            narrative.append(f"- Provider ordered {metrics['phase1_total_tests_ordered']} tests")
            narrative.append(f"- Payor approved ALL tests (no denials)")

        narrative.append(f"- Provider confidence: {metrics['phase1_confidence_start']:.0%} -> {metrics['phase1_confidence_end']:.0%}")

        # Phase 2 narrative
        narrative.append("\nPHASE 2 - RETROSPECTIVE SCRUTINY:")

        # Patient narrative
        if metrics['phase2_patient_ai_intensity'] >= 5:
            narrative.append(f"- Patient uploaded records to AI (intensity: {metrics['phase2_patient_ai_intensity']}/10)")
            narrative.append(f"- AI generated {metrics['phase2_patient_ai_suggestions_count']} diagnoses in differential")
            narrative.append(f"- This included {metrics['phase2_patient_concerns_count']} CONDITIONS THE DOCTOR DIDN'T FULLY RULE OUT")

            if metrics['phase2_patient_confrontation'] == 'questioning':
                narrative.append(f"- Patient is now QUESTIONING doctor's judgment")
                narrative.append(f"  > 'AI said it could be X, why didn't you test for that?'")
            elif metrics['phase2_patient_confrontation'] == 'demanding':
                narrative.append(f"- Patient is now DEMANDING additional workup")
                narrative.append(f"  > Patient doesn't trust doctor's clinical judgment vs AI's differential")
        else:
            narrative.append(f"- Patient did not extensively consult AI")

        # Payor narrative
        if metrics['phase2_retrospective_denial_rate'] > 0:
            narrative.append(f"\n- Payor reviewed encounter WITH HINDSIGHT")
            narrative.append(f"- Payor RETROSPECTIVELY DENIED {metrics['phase2_retrospective_denial_rate']:.0%} of PRE-APPROVED tests")
            narrative.append(f"- Tests denied reimbursement: {metrics['phase2_retrospective_denials']}")
            narrative.append(f"  > Provider got pre-authorization but won't get paid!")
            narrative.append(f"  > This is 'PRE-AUTHORIZATION BETRAYAL'")
        else:
            narrative.append(f"\n- Payor reimbursed all pre-approved tests")

        # Lawyer narrative
        if metrics['phase2_malpractice_detected']:
            narrative.append(f"\n- Lawyer detected POTENTIAL MALPRACTICE")
            if metrics['phase2_litigation_recommendation'] == 'lawsuit':
                narrative.append(f"- Lawyer recommends FILING LAWSUIT")
            elif metrics['phase2_litigation_recommendation'] == 'demand_letter':
                narrative.append(f"- Lawyer recommends DEMAND LETTER")
            else:
                narrative.append(f"- Lawyer monitoring but no immediate action")

        # Adversarial dynamics summary
        narrative.append("\nADVERSARIAL DYNAMICS:")

        if metrics['adversarial_trust_breakdown_score'] >= 2:
            narrative.append(f"SEVERE TRUST BREAKDOWN detected ({metrics['adversarial_trust_breakdown_score']}/3 indicators)")
        elif metrics['adversarial_trust_breakdown_score'] == 1:
            narrative.append(f"MODERATE adversarial behavior ({metrics['adversarial_trust_breakdown_score']}/3 indicators)")
        else:
            narrative.append(f"COOPERATIVE behavior (no major trust breakdown)")

        if metrics['adversarial_preauth_betrayal']:
            narrative.append("- Payor used hindsight to deny reimbursement for pre-approved tests")
        if metrics['adversarial_ai_patient_distrust']:
            narrative.append("- Patient lost trust in doctor after consulting consumer AI")
        if metrics['adversarial_defensive_cascade']:
            narrative.append("- Provider ordered tests despite denial (defensive medicine)")

        # Outcome interpretation
        narrative.append("\nOUTCOME INTERPRETATION:")
        if metrics['outcome_diagnostic_accuracy']:
            if metrics['adversarial_trust_breakdown_score'] >= 2:
                narrative.append("- Doctor got the diagnosis CORRECT")
                narrative.append("- YET adversarial dynamics still emerged")
                narrative.append("- This demonstrates the PRISONER'S DILEMMA:")
                narrative.append("  > Even with appropriate care, AI creates distrust and defensive behavior")
            else:
                narrative.append("- Doctor got the diagnosis CORRECT")
                narrative.append("- Cooperative behavior prevailed")
        else:
            narrative.append("- Doctor got the diagnosis WRONG")
            if metrics['adversarial_trust_breakdown_score'] >= 2:
                narrative.append("- Adversarial dynamics likely contributed to poor outcome")

        return narrative
