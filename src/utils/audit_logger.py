"""
Audit Logger for LLM Interactions in Healthcare Simulation

Captures all prompts and responses between Provider and Payor agents
for research transparency and reproducibility.
"""

from typing import Dict, Any, Optional
from datetime import datetime
import uuid
import json
from src.models.schemas import AuditLog, LLMInteraction


class AuditLogger:
    """Logs all LLM interactions during simulation."""

    def __init__(self, case_id: str):
        self.audit_log = AuditLog(
            case_id=case_id,
            simulation_start=datetime.now().isoformat(),
            interactions=[]
        )

    def log_interaction(
        self,
        phase: str,
        agent: str,
        action: str,
        system_prompt: str,
        user_prompt: str,
        llm_response: str,
        parsed_output: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Log a single LLM interaction.

        Args:
            phase: Phase identifier (e.g., "phase_2_pa", "phase_3_claims")
            agent: Agent name ("provider" or "payor")
            action: Action being performed (e.g., "pa_request", "concurrent_review")
            system_prompt: System prompt sent to LLM
            user_prompt: User prompt sent to LLM
            llm_response: Raw response from LLM
            parsed_output: Parsed/structured output from response
            metadata: Additional context (iteration number, etc.)

        Returns:
            Interaction ID for reference
        """
        interaction_id = f"{phase}_{agent}_{action}_{uuid.uuid4().hex[:8]}"

        interaction = LLMInteraction(
            interaction_id=interaction_id,
            timestamp=datetime.now().isoformat(),
            phase=phase,
            agent=agent,
            action=action,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            llm_response=llm_response,
            parsed_output=parsed_output or {},
            metadata=metadata or {}
        )

        self.audit_log.interactions.append(interaction)
        return interaction_id

    def finalize(self, summary: Optional[Dict[str, Any]] = None):
        """Finalize audit log with summary statistics."""
        self.audit_log.simulation_end = datetime.now().isoformat()
        self.audit_log.summary = summary or self._generate_summary()

    def _generate_summary(self) -> Dict[str, Any]:
        """Generate summary statistics from interactions."""
        interactions_by_phase = {}
        interactions_by_agent = {}

        for interaction in self.audit_log.interactions:
            # Count by phase
            if interaction.phase not in interactions_by_phase:
                interactions_by_phase[interaction.phase] = 0
            interactions_by_phase[interaction.phase] += 1

            # Count by agent
            if interaction.agent not in interactions_by_agent:
                interactions_by_agent[interaction.agent] = 0
            interactions_by_agent[interaction.agent] += 1

        return {
            "total_interactions": len(self.audit_log.interactions),
            "interactions_by_phase": interactions_by_phase,
            "interactions_by_agent": interactions_by_agent,
            "simulation_duration_seconds": self._calculate_duration()
        }

    def _calculate_duration(self) -> float:
        """Calculate simulation duration in seconds."""
        if not self.audit_log.simulation_end:
            return 0.0

        start = datetime.fromisoformat(self.audit_log.simulation_start)
        end = datetime.fromisoformat(self.audit_log.simulation_end)
        return (end - start).total_seconds()

    def get_audit_log(self) -> AuditLog:
        """Get the complete audit log."""
        return self.audit_log

    def save_to_json(self, filepath: str):
        """Save audit log to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.audit_log.model_dump(), f, indent=2)

    def get_interaction_sequence(self) -> str:
        """Get human-readable interaction sequence."""
        lines = []
        lines.append("=" * 80)
        lines.append("LLM INTERACTION AUDIT LOG")
        lines.append("=" * 80)
        lines.append(f"Case ID: {self.audit_log.case_id}")
        lines.append(f"Start: {self.audit_log.simulation_start}")
        lines.append(f"End: {self.audit_log.simulation_end or 'In Progress'}")
        lines.append("")

        for i, interaction in enumerate(self.audit_log.interactions, 1):
            lines.append(f"\n[{i}] {interaction.timestamp}")
            lines.append(f"Phase: {interaction.phase}")
            lines.append(f"Agent: {interaction.agent.upper()}")
            lines.append(f"Action: {interaction.action}")
            lines.append("")
            lines.append("SYSTEM PROMPT:")
            lines.append("-" * 80)
            lines.append(interaction.system_prompt[:500] + "..." if len(interaction.system_prompt) > 500 else interaction.system_prompt)
            lines.append("")
            lines.append("USER PROMPT:")
            lines.append("-" * 80)
            lines.append(interaction.user_prompt[:500] + "..." if len(interaction.user_prompt) > 500 else interaction.user_prompt)
            lines.append("")
            lines.append("LLM RESPONSE:")
            lines.append("-" * 80)
            lines.append(interaction.llm_response[:500] + "..." if len(interaction.llm_response) > 500 else interaction.llm_response)
            lines.append("")
            lines.append("PARSED OUTPUT:")
            lines.append(json.dumps(interaction.parsed_output, indent=2)[:300])
            lines.append("")
            lines.append("=" * 80)

        return "\n".join(lines)

    def save_to_markdown(self, filepath: str):
        """Save audit log to markdown file with full interaction details."""
        lines = []

        # Header
        lines.append(f"# Audit Log: {self.audit_log.case_id}")
        lines.append("")
        lines.append(f"**Simulation Start:** {self.audit_log.simulation_start}")
        lines.append(f"**Simulation End:** {self.audit_log.simulation_end or 'In Progress'}")
        lines.append("")

        # Summary
        if self.audit_log.summary:
            lines.append("## Summary")
            lines.append("")
            lines.append(f"- **Total Interactions:** {self.audit_log.summary.get('total_interactions', 0)}")
            lines.append(f"- **Duration:** {self.audit_log.summary.get('simulation_duration_seconds', 0):.2f} seconds")
            lines.append("")

            if "interactions_by_phase" in self.audit_log.summary:
                lines.append("**Interactions by Phase:**")
                for phase, count in self.audit_log.summary["interactions_by_phase"].items():
                    lines.append(f"- {phase}: {count}")
                lines.append("")

            if "interactions_by_agent" in self.audit_log.summary:
                lines.append("**Interactions by Agent:**")
                for agent, count in self.audit_log.summary["interactions_by_agent"].items():
                    lines.append(f"- {agent}: {count}")
                lines.append("")

        lines.append("---")
        lines.append("")

        # Detailed interactions
        for i, interaction in enumerate(self.audit_log.interactions, 1):
            # Interaction header
            phase_name = self._format_phase_name(interaction.phase)
            lines.append(f"## Interaction {i}: {phase_name}")
            lines.append("")
            lines.append(f"**Timestamp:** {interaction.timestamp}")
            lines.append(f"**Agent:** {interaction.agent.capitalize()}")
            lines.append(f"**Action:** {interaction.action.replace('_', ' ').title()}")
            lines.append("")

            # Metadata
            if interaction.metadata:
                lines.append("**Metadata:**")
                for key, value in interaction.metadata.items():
                    if isinstance(value, (list, dict)):
                        lines.append(f"- {key}: `{json.dumps(value)}`")
                    else:
                        lines.append(f"- {key}: {value}")
                lines.append("")

            # System prompt
            lines.append("### System Prompt")
            lines.append("")
            lines.append("```")
            lines.append(interaction.system_prompt)
            lines.append("```")
            lines.append("")

            # User prompt
            lines.append("### User Prompt")
            lines.append("")
            lines.append("```")
            lines.append(interaction.user_prompt)
            lines.append("```")
            lines.append("")

            # LLM response
            lines.append("### LLM Response")
            lines.append("")
            lines.append("```")
            lines.append(interaction.llm_response)
            lines.append("```")
            lines.append("")

            # Parsed output
            lines.append("### Parsed Output")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(interaction.parsed_output, indent=2))
            lines.append("```")
            lines.append("")
            lines.append("---")
            lines.append("")

        # Write to file
        with open(filepath, 'w') as f:
            f.write("\n".join(lines))

    def _format_phase_name(self, phase: str) -> str:
        """Format phase identifier as readable name."""
        phase_names = {
            "phase_2_pa": "Phase 2: Prior Authorization",
            "phase_2_pa_appeal": "Phase 2: PA Appeal Process",
            "phase_3_claims": "Phase 3: Claims Adjudication",
            "phase_4_financial": "Phase 4: Financial Settlement"
        }
        return phase_names.get(phase, phase.replace("_", " ").title())
