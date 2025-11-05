"""
generate mermaid sequence diagrams from audit logs

creates visual abstractions of provider-payor interactions across
the 4-phase utilization review workflow
"""

from typing import List
from src.models.schemas import AuditLog, EncounterState


class MermaidAuditGenerator:
    """generates mermaid sequence diagrams from audit logs"""

    @staticmethod
    def generate_from_audit_log(audit_log: AuditLog) -> str:
        """generate mermaid diagram from audit log"""
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
        """generate mermaid diagram from encounter state with audit log"""
        if not state.audit_log:
            return "sequenceDiagram\n    Note over Provider,Payor: No audit log available"

        lines = ["sequenceDiagram"]
        lines.append("    participant Provider as Provider Agent")
        lines.append("    participant Payor as Payor Agent")
        lines.append("")

        # phase 1: patient presentation
        lines.append("    Note over Provider,Payor: PHASE 1: Patient Presentation")
        lines.append("")

        if state.admission:
            patient = state.admission.patient_demographics
            insurance = state.admission.insurance
            lines.append(f"    Note right of Provider: Patient: {patient.age}yo {patient.sex}")

        if state.clinical_presentation:
            diagnosis = state.clinical_presentation.medical_history[0] if state.clinical_presentation.medical_history else "Unknown"
            lines.append(f"    Note right of Provider: Diagnosis: {diagnosis}")

        if state.admission:
            lines.append(f"    Note right of Provider: Insurance: {insurance.payer_name}")

        lines.append("")

        # phase 2-3: llm interactions from audit log
        current_phase = None
        for interaction in state.audit_log.interactions:
            if interaction.phase != current_phase:
                current_phase = interaction.phase
                phase_name = MermaidAuditGenerator._format_phase_name(interaction.phase)
                lines.append(f"    Note over Provider,Payor: {phase_name}")
                lines.append("")

            if interaction.agent == "provider":
                action_label = MermaidAuditGenerator._format_action(interaction.action, interaction.parsed_output)
                lines.append(f"    Provider->>Payor: {action_label}")
            elif interaction.agent == "payor":
                action_label = MermaidAuditGenerator._format_action(interaction.action, interaction.parsed_output)
                lines.append(f"    Payor-->>Provider: {action_label}")

            if interaction.metadata:
                metadata_str = MermaidAuditGenerator._format_metadata(interaction.metadata)
                if metadata_str:
                    lines.append(f"    Note over {interaction.agent.capitalize()}: {metadata_str}")

            lines.append("")

        # phase 4: financial settlement
        lines.append("    Note over Provider,Payor: PHASE 4: Financial Settlement")
        lines.append("")

        if state.medication_financial:
            fin = state.medication_financial
            lines.append(f"    Note right of Payor: Drug Cost: ${fin.acquisition_cost:,.2f}")
            lines.append(f"    Note right of Payor: Total Billed: ${fin.total_billed:,.2f}")
            lines.append(f"    Note right of Payor: Payer Payment: ${fin.payer_payment:,.2f}")
            lines.append(f"    Note right of Payor: Patient Copay: ${fin.patient_copay:,.2f}")
            lines.append(f"    Note right of Payor: Administrative Cost: ${fin.total_administrative_cost:,.2f}")
        elif state.financial_settlement:
            fin = state.financial_settlement
            lines.append(f"    Note right of Payor: Total Billed: ${fin.total_billed_charges:,.2f}")
            lines.append(f"    Note right of Payor: Payer Payment: ${fin.payer_payment:,.2f}")
            lines.append(f"    Note right of Payor: Patient Responsibility: ${fin.patient_responsibility:,.2f}")
            lines.append(f"    Note right of Payor: Hospital Revenue: ${fin.total_hospital_revenue:,.2f}")

        lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _format_phase_name(phase: str) -> str:
        """format phase identifier as readable name"""
        phase_names = {
            "phase_2_pa": "PHASE 2: Prior Authorization",
            "phase_2_pa_appeal": "PHASE 2: PA Appeal Process",
            "phase_3_claims": "PHASE 3: Claims Adjudication",
            "phase_4_financial": "PHASE 4: Financial Settlement"
        }
        return phase_names.get(phase, phase.upper())

    @staticmethod
    def _format_action(action: str, parsed_output: dict) -> str:
        """format action with key details from parsed output"""
        # For PA requests
        if action == "pa_request" or action == "medication_pa_request":
            medication = parsed_output.get('medication_name', 'medication')
            return f"PA Request: {medication}"

        # For PA decisions
        elif action == "pa_decision":
            status = parsed_output.get("authorization_status", "unknown")
            if status == "denied":
                return "PA DENIED"
            elif status == "approved":
                return "PA APPROVED"
            else:
                return f"PA {status.upper()}"

        # For appeals
        elif action == "pa_appeal_submission":
            appeal_type = parsed_output.get("appeal_type", "appeal")
            return f"Submit Appeal ({appeal_type})"

        elif action == "pa_appeal_decision":
            outcome = parsed_output.get("appeal_outcome", "unknown")
            if outcome == "approved":
                return "Appeal APPROVED"
            elif outcome == "upheld_denial":
                return "Appeal DENIED"
            else:
                return f"Appeal {outcome.upper()}"

        # For claims
        elif action == "claim_submission":
            amount = parsed_output.get("amount_billed", 0)
            if amount:
                return f"Submit Claim (${amount:,.2f})"
            return "Submit Claim (post-treatment)"

        elif action == "claim_adjudication":
            status = parsed_output.get("claim_status", "unknown")
            approved_amount = parsed_output.get("approved_amount")

            if status == "approved" and approved_amount:
                return f"Claim APPROVED (${approved_amount:,.2f})"
            elif status == "denied":
                return "Claim DENIED"
            else:
                return f"Claim {status.upper()}"

        # Generic fallback
        else:
            return action.replace("_", " ").title()

    @staticmethod
    def _format_metadata(metadata: dict) -> str:
        """format metadata for display in notes"""
        important_keys = ["medication", "appeal_type", "pa_approved",
                         "iteration", "confidence", "tests_ordered", "tests_denied"]
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
                elif key == "medication" and value:
                    parts.append(f"Medication: {value}")
                elif key == "appeal_type" and value:
                    parts.append(f"Appeal Type: {value}")
                elif key == "pa_approved" and value:
                    parts.append("PA Previously Approved")
                else:
                    parts.append(f"{key}: {value}")

        return ", ".join(parts) if parts else ""

    @staticmethod
    def save_to_file(audit_log: AuditLog, filepath: str):
        """generate and save mermaid diagram to file"""
        diagram = MermaidAuditGenerator.generate_from_audit_log(audit_log)
        with open(filepath, 'w') as f:
            f.write(diagram)

    @staticmethod
    def save_from_state(state: EncounterState, filepath: str):
        """generate and save mermaid diagram from encounter state"""
        diagram = MermaidAuditGenerator.generate_from_encounter_state(state)
        with open(filepath, 'w') as f:
            f.write(diagram)
