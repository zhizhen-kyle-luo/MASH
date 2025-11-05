"""
Generate Mermaid sequence diagrams from audit logs.

Creates visual abstractions of provider-payor interactions across
the 4-phase utilization review workflow.
"""

from typing import List
from src.models.schemas import AuditLog, EncounterState


class MermaidAuditGenerator:
    """Generates Mermaid sequence diagrams from audit logs."""

    @staticmethod
    def generate_from_audit_log(audit_log: AuditLog) -> str:
        """Generate Mermaid diagram from audit log."""
        lines = ["sequenceDiagram"]
        lines.append("    participant Provider as Provider Agent")
        lines.append("    participant Payor as Payor Agent")
        lines.append("")

        # Group interactions by phase
        current_phase = None

        for interaction in audit_log.interactions:
            # Add phase separator
            if interaction.phase != current_phase:
                current_phase = interaction.phase
                phase_name = MermaidAuditGenerator._format_phase_name(interaction.phase)
                lines.append(f"    Note over Provider,Payor: {phase_name}")
                lines.append("")

            # Add interaction arrows
            if interaction.agent == "provider":
                action_label = MermaidAuditGenerator._format_action(interaction.action, interaction.parsed_output)
                lines.append(f"    Provider->>Payor: {action_label}")
            elif interaction.agent == "payor":
                action_label = MermaidAuditGenerator._format_action(interaction.action, interaction.parsed_output)
                lines.append(f"    Payor-->>Provider: {action_label}")

            # Add metadata notes if relevant
            if interaction.metadata:
                metadata_str = MermaidAuditGenerator._format_metadata(interaction.metadata)
                if metadata_str:
                    lines.append(f"    Note over {interaction.agent.capitalize()}: {metadata_str}")

            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def generate_from_encounter_state(state: EncounterState) -> str:
        """Generate Mermaid diagram from encounter state with audit log."""
        if not state.audit_log:
            return "sequenceDiagram\n    Note over Provider,Payor: No audit log available"

        return MermaidAuditGenerator.generate_from_audit_log(state.audit_log)

    @staticmethod
    def _format_phase_name(phase: str) -> str:
        """Format phase identifier as readable name."""
        phase_names = {
            "phase_2_pa": "PHASE 2: Prior Authorization",
            "phase_2_pa_appeal": "PHASE 2: PA Appeal Process",
            "phase_3_claims": "PHASE 3: Claims Adjudication",
            "phase_4_financial": "PHASE 4: Financial Settlement"
        }
        return phase_names.get(phase, phase.upper())

    @staticmethod
    def _format_action(action: str, parsed_output: dict) -> str:
        """Format action with key details from parsed output."""
        # For PA requests
        if action == "pa_request" or action == "medication_pa_request":
            return f"PA Request: {parsed_output.get('medication_name', 'medication')}"

        # For PA decisions
        elif action == "pa_decision":
            status = parsed_output.get("authorization_status", "unknown")
            return f"PA Decision: {status.upper()}"

        # For appeals
        elif action == "pa_appeal_submission":
            appeal_type = parsed_output.get("appeal_type", "appeal")
            return f"Submit Appeal: {appeal_type}"

        elif action == "pa_appeal_decision":
            outcome = parsed_output.get("appeal_outcome", "unknown")
            return f"Appeal Decision: {outcome.upper()}"

        # For claims
        elif action == "claim_submission":
            return "Submit Claim (post-treatment)"

        elif action == "claim_adjudication":
            status = parsed_output.get("claim_status", "unknown")
            return f"Claim Decision: {status.upper()}"

        # Generic fallback
        else:
            return action.replace("_", " ").title()

    @staticmethod
    def _format_metadata(metadata: dict) -> str:
        """Format metadata for display in notes."""
        important_keys = ["iteration", "confidence", "denial_reason", "tests_ordered", "tests_denied"]
        parts = []

        for key in important_keys:
            if key in metadata:
                value = metadata[key]
                if key == "confidence":
                    parts.append(f"Confidence: {value:.2f}")
                elif key == "tests_denied" and value:
                    parts.append(f"Denied: {len(value)} tests")
                elif key == "tests_ordered" and value:
                    parts.append(f"Ordered: {len(value)} tests")
                else:
                    parts.append(f"{key}: {value}")

        return ", ".join(parts) if parts else ""

    @staticmethod
    def save_to_file(audit_log: AuditLog, filepath: str):
        """Generate and save Mermaid diagram to file."""
        diagram = MermaidAuditGenerator.generate_from_audit_log(audit_log)
        with open(filepath, 'w') as f:
            f.write(diagram)

    @staticmethod
    def save_from_state(state: EncounterState, filepath: str):
        """Generate and save Mermaid diagram from encounter state."""
        diagram = MermaidAuditGenerator.generate_from_encounter_state(state)
        with open(filepath, 'w') as f:
            f.write(diagram)
