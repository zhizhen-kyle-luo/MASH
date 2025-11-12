"""
aggregate population-level metrics from simulation results for macro-validation
"""
from typing import List, Dict, Any
from src.models.schemas import EncounterState, PAType


class MetricsAggregator:
    """calculate aggregate metrics from list of EncounterState objects"""

    @staticmethod
    def calculate_aggregate_metrics(states: List[EncounterState]) -> Dict[str, Any]:
        """
        calculate all population-level metrics from simulation results

        returns dict with metrics matching paper Table 1 structure
        """
        if not states:
            return {
                "total_cases": 0,
                "error": "no cases to aggregate"
            }

        metrics = {
            "total_cases": len(states),
            "phase_2_metrics": MetricsAggregator._calculate_phase_2_metrics(states),
            "phase_3_metrics": MetricsAggregator._calculate_phase_3_metrics(states),
            "phase_4_metrics": MetricsAggregator._calculate_phase_4_metrics(states),
        }

        return metrics

    @staticmethod
    def _calculate_phase_2_metrics(states: List[EncounterState]) -> Dict[str, float]:
        """calculate phase 2 PA denial metrics"""
        total_cases = len(states)

        # overall PA denial rate
        denied_count = sum(1 for state in states if state.denial_occurred)
        overall_pa_denial_rate = (denied_count / total_cases * 100) if total_cases > 0 else 0.0

        # post-acute care denial rate (filter by pa_type)
        post_acute_cases = [s for s in states if s.pa_type == PAType.POST_ACUTE_CARE]
        post_acute_denied = sum(1 for s in post_acute_cases if s.denial_occurred)
        post_acute_total = len(post_acute_cases)
        post_acute_care_denial_rate = (post_acute_denied / post_acute_total * 100) if post_acute_total > 0 else None

        return {
            "overall_pa_denial_rate": overall_pa_denial_rate,
            "overall_pa_denial_count": denied_count,
            "post_acute_care_denial_rate": post_acute_care_denial_rate,
            "post_acute_care_total": post_acute_total,
            "post_acute_care_denied_count": post_acute_denied,
        }

    @staticmethod
    def _calculate_phase_3_metrics(states: List[EncounterState]) -> Dict[str, float]:
        """calculate phase 3 appeal metrics"""
        # appeal rate: % of denials that led to appeals
        denials = sum(1 for state in states if state.denial_occurred)
        appeals_filed = sum(1 for state in states if state.appeal_filed)
        appeal_rate = (appeals_filed / denials * 100) if denials > 0 else 0.0

        # appeal success rate: % of appeals that succeeded
        appeals_successful = sum(1 for state in states if state.appeal_successful)
        appeal_success_rate = (appeals_successful / appeals_filed * 100) if appeals_filed > 0 else 0.0

        return {
            "appeal_rate": appeal_rate,
            "appeals_filed_count": appeals_filed,
            "denials_count": denials,
            "appeal_success_rate": appeal_success_rate,
            "appeals_successful_count": appeals_successful,
        }

    @staticmethod
    def _calculate_phase_4_metrics(states: List[EncounterState]) -> Dict[str, float]:
        """calculate phase 4 financial metrics"""
        # collect all administrative costs
        admin_costs = []
        for state in states:
            if state.medication_financial:
                admin_costs.append(state.medication_financial.total_administrative_cost)
            elif state.financial_settlement:
                # inpatient cases may have different cost structure
                # for now, skip or handle differently if needed
                pass

        total_admin_cost = sum(admin_costs) if admin_costs else 0.0
        per_case_admin_cost = (total_admin_cost / len(admin_costs)) if admin_costs else 0.0

        return {
            "total_admin_cost": total_admin_cost,
            "per_case_admin_cost": per_case_admin_cost,
            "cases_with_financial_data": len(admin_costs),
        }

    @staticmethod
    def format_validation_report(
        metrics: Dict[str, Any],
        benchmarks: Dict[str, Dict[str, Any]]
    ) -> str:
        """
        format metrics comparison against benchmarks as markdown table

        benchmarks format:
        {
            "overall_pa_denial_rate": {"value": 6.4, "source": "KFF..."},
            ...
        }
        """
        lines = []

        total_cases = metrics["total_cases"]
        phase_2 = metrics["phase_2_metrics"]
        phase_3 = metrics["phase_3_metrics"]
        phase_4 = metrics["phase_4_metrics"]

        lines.append("# Macro-Validation Report")
        lines.append("")
        lines.append(f"**Cases Processed:** {total_cases}")
        lines.append("")

        # validation completeness warning
        if total_cases < 15:
            lines.append(f"**WARNING - INCOMPLETE VALIDATION:** Results based on {total_cases}/20 cases")
            lines.append("Macro-validation requires 15-20 cases for reliable population-level statistics")
            lines.append("")

        lines.append("## Validation Results")
        lines.append("")
        lines.append("| Metric | Simulated | Benchmark | Difference | Status |")
        lines.append("|--------|-----------|-----------|------------|--------|")

        # phase 2 metrics
        MetricsAggregator._add_validation_row(
            lines,
            "Overall PA Denial Rate",
            phase_2["overall_pa_denial_rate"],
            benchmarks.get("overall_pa_denial_rate"),
            percentage=True
        )

        if phase_2["post_acute_care_denial_rate"] is not None:
            MetricsAggregator._add_validation_row(
                lines,
                "Post-Acute Care Denial Rate",
                phase_2["post_acute_care_denial_rate"],
                benchmarks.get("post_acute_care_denial_rate"),
                percentage=True
            )
        else:
            lines.append("| Post-Acute Care Denial Rate | N/A | - | - | SKIP |")

        # phase 3 metrics
        MetricsAggregator._add_validation_row(
            lines,
            "Appeal Rate",
            phase_3["appeal_rate"],
            benchmarks.get("appeal_rate"),
            percentage=True
        )

        MetricsAggregator._add_validation_row(
            lines,
            "Appeal Success Rate",
            phase_3["appeal_success_rate"],
            benchmarks.get("appeal_success_rate"),
            percentage=True
        )

        # phase 4 metrics (no comparison per user instruction)
        lines.append(f"| Per-Case Admin Cost | ${phase_4['per_case_admin_cost']:.2f} | (not compared) | - | INFO |")

        lines.append("")
        lines.append("**Status Key:**")
        lines.append("- PASS: Within +/-20% of benchmark (acceptable macro-validation threshold)")
        lines.append("- FAIL: Outside +/-20% of benchmark")
        lines.append("- SKIP: Insufficient data for metric")
        lines.append("- INFO: Calculated but not validated")
        lines.append("")

        # detailed breakdown
        lines.append("## Detailed Breakdown")
        lines.append("")
        lines.append("### Phase 2: Prior Authorization")
        lines.append(f"- Total cases: {total_cases}")
        lines.append(f"- Denials: {phase_2['overall_pa_denial_count']} ({phase_2['overall_pa_denial_rate']:.1f}%)")
        if phase_2["post_acute_care_total"] > 0:
            lines.append(f"- Post-acute care cases: {phase_2['post_acute_care_total']}")
            lines.append(f"- Post-acute care denials: {phase_2['post_acute_care_denied_count']} ({phase_2['post_acute_care_denial_rate']:.1f}%)")
        lines.append("")

        lines.append("### Phase 3: Appeals")
        lines.append(f"- Denials: {phase_3['denials_count']}")
        lines.append(f"- Appeals filed: {phase_3['appeals_filed_count']} ({phase_3['appeal_rate']:.1f}%)")
        lines.append(f"- Appeals successful: {phase_3['appeals_successful_count']} ({phase_3['appeal_success_rate']:.1f}%)")
        lines.append("")

        lines.append("### Phase 4: Financial")
        lines.append(f"- Cases with financial data: {phase_4['cases_with_financial_data']}")
        lines.append(f"- Total admin cost: ${phase_4['total_admin_cost']:.2f}")
        lines.append(f"- Per-case admin cost: ${phase_4['per_case_admin_cost']:.2f}")
        lines.append("")

        # data sources
        lines.append("## Benchmark Sources")
        for metric_name, benchmark_data in benchmarks.items():
            if isinstance(benchmark_data, dict) and "source" in benchmark_data:
                lines.append(f"- **{metric_name}**: {benchmark_data['source']}")

        return "\n".join(lines)

    @staticmethod
    def _add_validation_row(
        lines: List[str],
        metric_name: str,
        simulated_value: float,
        benchmark: Dict[str, Any],
        percentage: bool = False
    ):
        """add single validation row to table"""
        if benchmark is None:
            lines.append(f"| {metric_name} | - | - | - | SKIP |")
            return

        benchmark_value = benchmark["value"]

        if percentage:
            simulated_str = f"{simulated_value:.1f}%"
            benchmark_str = f"{benchmark_value:.1f}%"
        else:
            simulated_str = f"${simulated_value:.2f}"
            benchmark_str = f"${benchmark_value:.2f}"

        # calculate difference
        if benchmark_value > 0:
            diff_pct = ((simulated_value - benchmark_value) / benchmark_value) * 100
            diff_str = f"{diff_pct:+.1f}%"

            # determine status (+/-20% threshold)
            if abs(diff_pct) <= 20:
                status = "PASS"
            else:
                status = "FAIL"
        else:
            diff_str = "N/A"
            status = "SKIP"

        lines.append(f"| {metric_name} | {simulated_str} | {benchmark_str} | {diff_str} | {status} |")
