"""
Generate mermaid sequence diagrams from simulation runs.
"""
from typing import List
from src.models.schemas import GameState


class MermaidGenerator:
    """Generates mermaid sequence diagrams from simulation output."""

    @staticmethod
    def generate_sequence_diagram(state: GameState) -> str:
        """Generate mermaid sequence diagram from completed simulation."""
        lines = ["sequenceDiagram"]
        lines.append("    participant Provider")
        lines.append("    participant Payor")
        lines.append("    participant Patient")
        lines.append("    participant AI")
        lines.append("    participant Lawyer")
        lines.append("")

        # Phase 1: Iterative encounter
        lines.append("    Note over Provider,Payor: PHASE 1 - Real-time Encounter")

        for iteration in state.iteration_history:
            iter_num = iteration.iteration_number

            # Provider orders tests
            if iteration.provider_tests_ordered:
                test_names = [t.test_name for t in iteration.provider_tests_ordered]
                lines.append(f"    Provider->>Payor: Iteration {iter_num}: Request authorization for {len(test_names)} tests")

            # Payor approves/denies
            if iteration.payor_approved:
                lines.append(f"    Payor-->>Provider: Approve: {', '.join(iteration.payor_approved[:2])}")
            if iteration.payor_denied:
                lines.append(f"    Payor-->>Provider: Deny: {', '.join(iteration.payor_denied[:2])}")

            # Provider appeals
            if iteration.provider_appeals:
                lines.append(f"    Provider->>Payor: Appeal {len(iteration.provider_appeals)} denials")

            # Provider orders despite denial
            if iteration.provider_ordered_despite_denial:
                lines.append(f"    Provider->>Provider: Order anyway: {len(iteration.provider_ordered_despite_denial)} tests")

            # Confidence update
            lines.append(f"    Note over Provider: Confidence: {iteration.confidence:.2f}, Differential: {len(iteration.differential)} diagnoses")

        lines.append("")

        # Phase 2: Retrospective scrutiny
        lines.append("    Note over Patient,Lawyer: PHASE 2 - Retrospective Scrutiny")

        if state.patient_decision:
            lines.append("    Patient->>AI: Upload all records for second opinion")
            if state.patient_decision.ai_second_opinions:
                lines.append(f"    AI-->>Patient: Suggest {len(state.patient_decision.ai_second_opinions)} conditions")
            lines.append(f"    Note over Patient: Confrontation level: {state.patient_decision.confrontation_level}")

        if state.payor_decision and hasattr(state.payor_decision, 'retrospective_denials'):
            if state.payor_decision.retrospective_denials:
                lines.append(f"    Payor->>Provider: Retrospective denial: {len(state.payor_decision.retrospective_denials)} tests")

        if state.lawyer_decision:
            lines.append("    Lawyer->>Lawyer: Review case with AI")
            if state.lawyer_decision.malpractice_detected:
                lines.append(f"    Lawyer->>Provider: {state.lawyer_decision.litigation_recommendation}")
                if state.lawyer_decision.standard_of_care_violations:
                    lines.append(f"    Note over Lawyer: Found {len(state.lawyer_decision.standard_of_care_violations)} violations")

        return "\n".join(lines)

    @staticmethod
    def save_to_file(state: GameState, filepath: str):
        """Generate and save mermaid diagram to file."""
        diagram = MermaidGenerator.generate_sequence_diagram(state)
        with open(filepath, 'w') as f:
            f.write(diagram)
