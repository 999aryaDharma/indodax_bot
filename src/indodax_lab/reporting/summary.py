"""Compact experiment summary and multi-run comparison reporting (REPORT-01).

Guarantees:
1. REPORT-01-AC0: Summary displays data quality, net performance, and rejection reasons clearly.
2. REPORT-01-AC1: No-data is distinct from zero profit (represented as NO_DATA, never 0.00%).
3. REPORT-01-AC2: Shared pipeline lineage is separated from candidate-independent parameters.
4. REPORT-01-AC3: Invalid runs are excluded from ranking leaderboards and listed in Disqualified section.
"""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any, Sequence
from pydantic import BaseModel, ConfigDict

from indodax_lab.evaluation.gates import EvaluationOutcome, EvaluationResult
from indodax_lab.evaluation.registry import ExperimentRunRecord, ExperimentRunStatus


def _format_metric_display(key: str, val: Any) -> str:
    """Format metric value safely, never converting missing/None data to 0.00%."""
    if val is None:
        return "NO_DATA"

    if key == "data_quality_score" and isinstance(val, (int, float)):
        return f"{val * 100:.1f}% ({val:.4f})"

    if key.endswith("_pct") and isinstance(val, (int, float)):
        return f"{val:.2f}%"

    if isinstance(val, float):
        return f"{val:.2f}"

    if isinstance(val, int):
        return str(val)

    return str(val)


class ExperimentSummaryReport(BaseModel):
    """Structured report separating shared pipeline lineage from candidate parameters."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    candidate_id: str
    candidate_version: str
    family: str
    status: str
    outcome: str
    created_at: datetime
    metrics: dict[str, Any]
    passed_gates: list[str] = []
    failed_gates: list[str] = []
    reasons: list[str] = []
    shared_pipeline: dict[str, Any]
    candidate_parameters: dict[str, Any] = {}
    dsr: float | None = None
    dsr_status: str = "NOT_ESTIMABLE"
    pbo: float | None = None
    pbo_status: str = "NOT_ESTIMABLE"
    error_message: str | None = None

    @classmethod
    def from_run(
        cls,
        run: ExperimentRunRecord,
        evaluation: EvaluationResult,
        independent_params: dict[str, Any] | None = None,
    ) -> ExperimentSummaryReport:
        """Create summary report from execution record and evaluation outcome."""
        shared = {
            "git_sha": run.git_sha,
            "is_dirty": run.is_dirty,
            "environment_hash": run.environment_hash,
            "dataset_snapshot_id": run.dataset_snapshot_id,
            "dataset_hash": run.dataset_hash,
            "cost_schedule_hash": run.cost_schedule_hash,
            "execution_hash": run.execution_hash,
            "config_hash": run.config_hash,
        }
        candidate_params = dict(independent_params) if independent_params else {}

        status_val = run.status.value if hasattr(run.status, "value") else str(run.status)
        outcome_val = evaluation.outcome.value if hasattr(evaluation.outcome, "value") else str(evaluation.outcome)

        return cls(
            run_id=run.run_id,
            candidate_id=run.candidate_id,
            candidate_version=run.candidate_version,
            family=run.family,
            status=status_val,
            outcome=outcome_val,
            created_at=run.created_at,
            metrics=run.metrics,
            passed_gates=list(evaluation.passed_gates),
            failed_gates=list(evaluation.failed_gates),
            reasons=list(evaluation.reasons),
            shared_pipeline=shared,
            candidate_parameters=candidate_params,
            dsr=evaluation.dsr,
            dsr_status=evaluation.dsr_status,
            pbo=evaluation.pbo,
            pbo_status=evaluation.pbo_status,
            error_message=run.error_message,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert report to serializable dictionary."""
        return self.model_dump(mode="json")

    def to_json(self, indent: int = 2) -> str:
        """Convert report to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def to_markdown(self) -> str:
        """Generate human-readable compact markdown report."""
        lines: list[str] = [
            f"## Experiment Summary: {self.run_id}",
            "",
            "### Candidate Information",
            f"- **Candidate ID**: `{self.candidate_id}`",
            f"- **Candidate Version**: `{self.candidate_version}`",
            f"- **Family**: `{self.family}`",
            f"- **Status**: `{self.status}`",
            f"- **Outcome**: `{self.outcome}`",
            f"- **Created At**: `{self.created_at.isoformat()}`",
            "",
            "### Key Performance Metrics",
            "| Metric | Value |",
            "|---|---|",
        ]

        # Order key metrics logically
        key_order = [
            ("net_profit_pct", "Net Profit"),
            ("gross_profit_pct", "Gross Profit"),
            ("total_fee_cost", "Total Fees"),
            ("sharpe_ratio", "Sharpe Ratio"),
            ("profit_factor", "Profit Factor"),
            ("trade_count", "Trade Count"),
            ("data_quality_score", "Data Quality"),
        ]
        displayed_keys = set()
        for k, label in key_order:
            if k in self.metrics:
                displayed_keys.add(k)
                lines.append(f"| {label} | {_format_metric_display(k, self.metrics[k])} |")

        for k, v in self.metrics.items():
            if k not in displayed_keys:
                lines.append(f"| {k} | {_format_metric_display(k, v)} |")

        lines.extend([
            "",
            "### Evaluation Gates",
            f"- **Passed Gates**: {', '.join(f'`{g}`' for g in self.passed_gates) if self.passed_gates else 'None'}",
            f"- **Failed Gates**: {', '.join(f'`{g}`' for g in self.failed_gates) if self.failed_gates else 'None'}",
            f"- **Rejection Reasons**: {', '.join(f'`{r}`' for r in self.reasons) if self.reasons else 'None'}",
        ])

        if self.dsr is not None or self.pbo is not None:
            lines.extend([
                "",
                "### Statistical Selection Adjustments",
                f"- **DSR**: {f'{self.dsr:.4f}' if self.dsr is not None else 'N/A'} ({self.dsr_status})",
                f"- **PBO**: {f'{self.pbo:.4f}' if self.pbo is not None else 'N/A'} ({self.pbo_status})",
            ])

        lines.extend([
            "",
            "### Shared Pipeline Lineage",
            "| Lineage Property | Identifier / Digest |",
            "|---|---|",
        ])
        for prop, val in self.shared_pipeline.items():
            lines.append(f"| {prop} | `{val}` |")

        lines.extend([
            "",
            "### Candidate Parameters",
        ])
        if self.candidate_parameters:
            lines.extend([
                "| Parameter | Value |",
                "|---|---|",
            ])
            for param, val in self.candidate_parameters.items():
                lines.append(f"| {param} | `{val}` |")
        else:
            lines.append("*(No independent parameters specified)*")

        return "\n".join(lines)


def generate_experiment_report_md(
    run_or_report: ExperimentRunRecord | ExperimentSummaryReport,
    eval_result: EvaluationResult | None = None,
    independent_params: dict[str, Any] | None = None,
) -> str:
    """Generate Markdown report for single experiment run."""
    if isinstance(run_or_report, ExperimentSummaryReport):
        return run_or_report.to_markdown()

    if eval_result is None:
        raise ValueError("eval_result must be provided when passing ExperimentRunRecord")

    report = ExperimentSummaryReport.from_run(
        run=run_or_report,
        evaluation=eval_result,
        independent_params=independent_params,
    )
    return report.to_markdown()


def generate_experiment_report_json(
    run_or_report: ExperimentRunRecord | ExperimentSummaryReport,
    eval_result: EvaluationResult | None = None,
    independent_params: dict[str, Any] | None = None,
) -> str:
    """Generate JSON report for single experiment run."""
    if isinstance(run_or_report, ExperimentSummaryReport):
        return run_or_report.to_json()

    if eval_result is None:
        raise ValueError("eval_result must be provided when passing ExperimentRunRecord")

    report = ExperimentSummaryReport.from_run(
        run=run_or_report,
        evaluation=eval_result,
        independent_params=independent_params,
    )
    return report.to_json()


def generate_multi_run_comparison_md(
    runs: Sequence[ExperimentRunRecord],
    evaluations: Sequence[EvaluationResult],
) -> str:
    """Generate multi-run comparison leaderboard, strictly excluding invalid runs."""
    if len(runs) != len(evaluations):
        raise ValueError("LENGTH_MISMATCH: Number of runs must match number of evaluation results")

    valid_entries: list[tuple[ExperimentRunRecord, EvaluationResult]] = []
    disqualified_entries: list[tuple[ExperimentRunRecord, EvaluationResult]] = []

    for run, evaluation in zip(runs, evaluations):
        is_invalid = (
            run.status == ExperimentRunStatus.INVALID_RUN
            or str(run.status).lower() == "invalid_run"
            or evaluation.outcome == EvaluationOutcome.INVALID_RUN
            or str(evaluation.outcome).upper() == "INVALID_RUN"
        )
        if is_invalid:
            disqualified_entries.append((run, evaluation))
        else:
            valid_entries.append((run, evaluation))

    # Rank valid entries by net_profit_pct (descending), then sharpe_ratio
    def _rank_key(item: tuple[ExperimentRunRecord, EvaluationResult]) -> tuple[float, float]:
        r, _ = item
        net_pct = r.metrics.get("net_profit_pct")
        sharpe = r.metrics.get("sharpe_ratio")
        net_val = float(net_pct) if net_pct is not None else float("-inf")
        sharpe_val = float(sharpe) if sharpe is not None else float("-inf")
        return (net_val, sharpe_val)

    valid_entries.sort(key=_rank_key, reverse=True)

    lines: list[str] = [
        "## Experiment Comparison Leaderboard",
        "",
        "| Rank | Candidate | Run ID | Net Profit | Sharpe Ratio | Trades | Status | Outcome |",
        "|---|---|---|---|---|---|---|---|",
    ]

    for rank, (run, evaluation) in enumerate(valid_entries, start=1):
        net_profit_str = _format_metric_display("net_profit_pct", run.metrics.get("net_profit_pct"))
        sharpe_str = _format_metric_display("sharpe_ratio", run.metrics.get("sharpe_ratio"))
        trade_str = _format_metric_display("trade_count", run.metrics.get("trade_count"))
        status_str = run.status.value if hasattr(run.status, "value") else str(run.status)
        outcome_str = evaluation.outcome.value if hasattr(evaluation.outcome, "value") else str(evaluation.outcome)
        lines.append(
            f"| {rank} | {run.candidate_id} | {run.run_id} | {net_profit_str} | {sharpe_str} | {trade_str} | {status_str} | {outcome_str} |"
        )

    if disqualified_entries:
        lines.extend([
            "",
            "### Disqualified / Invalid Runs",
            "",
            "| Candidate | Run ID | Status | Outcome | Reasons |",
            "|---|---|---|---|---|",
        ])
        for run, evaluation in disqualified_entries:
            status_str = run.status.value if hasattr(run.status, "value") else str(run.status)
            outcome_str = evaluation.outcome.value if hasattr(evaluation.outcome, "value") else str(evaluation.outcome)
            reasons_str = ", ".join(evaluation.reasons) if evaluation.reasons else (run.error_message or "N/A")
            lines.append(
                f"| {run.candidate_id} | {run.run_id} | {status_str} | {outcome_str} | {reasons_str} |"
            )

    return "\n".join(lines)
