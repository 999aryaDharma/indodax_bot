"""Unit tests for REPORT-01 Compact experiment reports.

Acceptance Criteria:
- REPORT-01-AC0 (test_report_01_valid_contract): Pengguna dapat melihat kualitas data, performa net dan alasan penolakan tanpa membaca raw logs.
- REPORT-01-AC1 (test_report_01_contract_1): No-data berbeda dari zero profit.
- REPORT-01-AC2 (test_report_01_contract_2): Shared dan independent dipisahkan.
- REPORT-01-AC3 (test_report_01_contract_3): Run invalid tidak ranking.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
import pytest

from indodax_lab.evaluation.gates import EvaluationOutcome, EvaluationResult
from indodax_lab.evaluation.registry import ExperimentRunRecord, ExperimentRunStatus
from indodax_lab.reporting.summary import (
    ExperimentSummaryReport,
    generate_experiment_report_json,
    generate_experiment_report_md,
    generate_multi_run_comparison_md,
)


def _build_test_run(
    run_id: str = "run_rep_001",
    status: ExperimentRunStatus = ExperimentRunStatus.SUCCESS,
    metrics: dict | None = None,
    candidate_id: str = "cand_donchian_v1",
) -> tuple[ExperimentRunRecord, EvaluationResult]:
    base_ts = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    default_metrics = {
        "net_profit_pct": 12.5,
        "gross_profit_pct": 15.2,
        "total_fee_cost": 2.7,
        "sharpe_ratio": 1.45,
        "profit_factor": 1.6,
        "trade_count": 52,
        "data_quality_score": 0.998,
    }
    m = metrics if metrics is not None else default_metrics

    run = ExperimentRunRecord(
        run_id=run_id,
        candidate_id=candidate_id,
        candidate_version="1.0.0",
        family="trend",
        git_sha="git_sha_abc123",
        is_dirty=False,
        environment_hash="env_hash_456",
        dataset_snapshot_id="snapshot_btc_2025_06",
        dataset_hash="dsh_789",
        config_hash="cfg_donchian_10_20",
        cost_schedule_hash="cst_indodax_taker_v1",
        execution_hash="exe_sim_v1",
        status=status,
        metrics=m,
        created_at=base_ts,
        promotable=True if status == ExperimentRunStatus.SUCCESS else False,
    )

    eval_result = EvaluationResult(
        run_id=run_id,
        candidate_id=candidate_id,
        outcome=EvaluationOutcome.PASS if status == ExperimentRunStatus.SUCCESS else EvaluationOutcome.HARD_FAIL,
        passed_gates=["profit_factor", "trade_count"] if status == ExperimentRunStatus.SUCCESS else [],
        failed_gates=[] if status == ExperimentRunStatus.SUCCESS else ["profit_factor"],
        reasons=[] if status == ExperimentRunStatus.SUCCESS else ["PROFIT_FACTOR_TOO_LOW"],
        metrics=m,
    )
    return run, eval_result


def test_report_01_valid_contract() -> None:
    """REPORT-01-AC0: Pengguna dapat melihat kualitas data, performa net dan alasan penolakan tanpa membaca raw logs."""
    run, eval_result = _build_test_run("run_valid_ok")

    md_report = generate_experiment_report_md(run, eval_result)
    assert "## Experiment Summary: run_valid_ok" in md_report
    assert "cand_donchian_v1" in md_report
    assert "Net Profit" in md_report
    assert "12.50%" in md_report
    assert "Data Quality" in md_report or "99.8" in md_report
    assert "Status" in md_report
    assert "PASS" in md_report

    json_report = generate_experiment_report_json(run, eval_result)
    data = json.loads(json_report)
    assert data["run_id"] == "run_valid_ok"
    assert data["metrics"]["net_profit_pct"] == 12.5
    assert data["outcome"] == "PASS"


def test_report_01_contract_1() -> None:
    """REPORT-01-AC1: No-data berbeda dari zero profit."""
    # Run with zero trades / undefined returns
    no_data_metrics = {
        "net_profit_pct": None,  # No data / undefined
        "sharpe_ratio": None,
        "profit_factor": None,
        "trade_count": 0,
    }
    run, eval_result = _build_test_run("run_no_data", metrics=no_data_metrics)

    md_report = generate_experiment_report_md(run, eval_result)

    # Invariant: Must display NO_DATA or UNDEFINED, NEVER "0.00%" or zero profit!
    assert "0.00%" not in md_report
    assert "NO_DATA" in md_report or "UNDEFINED" in md_report


def test_report_01_contract_2() -> None:
    """REPORT-01-AC2: Shared dan independent dipisahkan."""
    run, eval_result = _build_test_run("run_split_params")

    summary = ExperimentSummaryReport.from_run(
        run,
        eval_result,
        independent_params={"lookback": 20, "stop_pct": 0.03, "seed": 42},
    )

    # Shared pipeline lineage
    assert summary.shared_pipeline["dataset_snapshot_id"] == "snapshot_btc_2025_06"
    assert summary.shared_pipeline["cost_schedule_hash"] == "cst_indodax_taker_v1"
    assert summary.shared_pipeline["git_sha"] == "git_sha_abc123"

    # Candidate-independent strategy params
    assert summary.candidate_parameters["lookback"] == 20
    assert summary.candidate_parameters["seed"] == 42

    md_report = generate_experiment_report_md(run, eval_result, independent_params={"lookback": 20})
    assert "### Shared Pipeline Lineage" in md_report
    assert "### Candidate Parameters" in md_report


def test_report_01_contract_3() -> None:
    """REPORT-01-AC3: Run invalid tidak ranking."""
    run_valid_1, eval_1 = _build_test_run("run_1", candidate_id="cand_A", metrics={"net_profit_pct": 10.0, "sharpe_ratio": 1.2, "trade_count": 30})
    run_invalid, eval_inv = _build_test_run(
        "run_invalid",
        status=ExperimentRunStatus.INVALID_RUN,
        candidate_id="cand_B_invalid",
        metrics={"net_profit_pct": 999.0, "sharpe_ratio": 50.0, "trade_count": 5},
    )
    eval_inv_custom = EvaluationResult(
        run_id="run_invalid",
        candidate_id="cand_B_invalid",
        outcome=EvaluationOutcome.INVALID_RUN,
        passed_gates=[],
        failed_gates=["DATA_VALIDITY"],
        reasons=["PROVENANCE_CORRUPT"],
        metrics=run_invalid.metrics,
    )
    run_valid_2, eval_2 = _build_test_run("run_2", candidate_id="cand_C", metrics={"net_profit_pct": 5.0, "sharpe_ratio": 0.9, "trade_count": 35})

    comparison_md = generate_multi_run_comparison_md(
        runs=[run_valid_1, run_invalid, run_valid_2],
        evaluations=[eval_1, eval_inv_custom, eval_2],
    )

    # Invariant: Invalid run must NOT appear in the ranking leaderboard table
    assert "| 1 | cand_A" in comparison_md
    assert "| 2 | cand_C" in comparison_md
    assert "| 1 | cand_B_invalid" not in comparison_md
    assert "| 2 | cand_B_invalid" not in comparison_md
    assert "| 3 | cand_B_invalid" not in comparison_md

    # Invalid run is explicitly placed in the Disqualified / Invalid Runs section
    assert "### Disqualified / Invalid Runs" in comparison_md
    assert "cand_B_invalid" in comparison_md
    assert "PROVENANCE_CORRUPT" in comparison_md


def test_report_01_statistical_selection_and_errors() -> None:
    """REPORT-01 edge cases: DSR/PBO rendering, length mismatch, and direct report objects."""
    run, eval_result = _build_test_run("run_stat_eval")
    eval_result_stat = EvaluationResult(
        run_id=run.run_id,
        candidate_id=run.candidate_id,
        outcome=EvaluationOutcome.PASS,
        passed_gates=["profit_factor"],
        failed_gates=[],
        reasons=[],
        metrics=run.metrics,
        dsr=0.8523,
        dsr_status="SIGNIFICANT",
        pbo=0.1245,
        pbo_status="ACCEPTABLE",
    )

    summary = ExperimentSummaryReport.from_run(run, eval_result_stat)
    md = summary.to_markdown()
    assert "### Statistical Selection Adjustments" in md
    assert "0.8523" in md
    assert "SIGNIFICANT" in md
    assert "0.1245" in md
    assert "ACCEPTABLE" in md

    # Direct report instance passed to generator functions
    md2 = generate_experiment_report_md(summary)
    assert md2 == md
    json_str = generate_experiment_report_json(summary)
    assert "run_stat_eval" in json_str

    # Missing eval_result when passing ExperimentRunRecord
    with pytest.raises(ValueError, match="eval_result must be provided"):
        generate_experiment_report_md(run, None)

    with pytest.raises(ValueError, match="eval_result must be provided"):
        generate_experiment_report_json(run, None)

    # Length mismatch in multi-run comparison
    with pytest.raises(ValueError, match="LENGTH_MISMATCH"):
        generate_multi_run_comparison_md([run], [])

