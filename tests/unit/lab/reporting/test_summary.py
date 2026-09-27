"""Unit tests for REPORT-01 Compact experiment reports.

Acceptance Criteria:
- REPORT-01-AC0 (test_report_01_valid_contract): Pengguna dapat melihat kualitas data, performa net
  dan alasan penolakan tanpa membaca raw logs.
- REPORT-01-AC1 (test_report_01_contract_1): No-data berbeda dari zero profit.
- REPORT-01-AC2 (test_report_01_contract_2): Shared dan independent dipisahkan.
- REPORT-01-AC3 (test_report_01_contract_3): Run invalid tidak ranking.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

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
    error_message: str | None = None,
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
        error_message=error_message,
        created_at=base_ts,
        promotable=True if status == ExperimentRunStatus.SUCCESS else False,
    )

    eval_result = EvaluationResult(
        run_id=run_id,
        candidate_id=candidate_id,
        policy_id="eval_policy_v1",
        policy_version="1.0.0",
        outcome=(
            EvaluationOutcome.PASS
            if status == ExperimentRunStatus.SUCCESS
            else EvaluationOutcome.HARD_FAIL
        ),
        passed_gates=(
            ["profit_factor", "trade_count"]
            if status == ExperimentRunStatus.SUCCESS
            else []
        ),
        failed_gates=[] if status == ExperimentRunStatus.SUCCESS else ["profit_factor"],
        reasons=[] if status == ExperimentRunStatus.SUCCESS else ["PROFIT_FACTOR_TOO_LOW"],
        metrics=m,
    )
    return run, eval_result


def test_report_01_valid_contract() -> None:
    """REPORT-01-AC0: report shows data quality, net performance and rejection reasons."""
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
    run = run.model_copy(update={"dataset_split_id": "split_v2_abc"})

    summary = ExperimentSummaryReport.from_run(
        run,
        eval_result,
        independent_params={"lookback": 20, "stop_pct": 0.03, "seed": 42},
    )

    # Shared pipeline lineage
    assert summary.shared_pipeline["dataset_snapshot_id"] == "snapshot_btc_2025_06"
    assert summary.shared_pipeline["dataset_split_id"] == "split_v2_abc"
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
    run_valid_1, eval_1 = _build_test_run(
        "run_1",
        candidate_id="cand_A",
        metrics={"net_profit_pct": 10.0, "sharpe_ratio": 1.2, "trade_count": 30},
    )
    run_invalid, eval_inv = _build_test_run(
        "run_invalid",
        status=ExperimentRunStatus.INVALID_RUN,
        candidate_id="cand_B_invalid",
        metrics={"net_profit_pct": 999.0, "sharpe_ratio": 50.0, "trade_count": 5},
    )
    eval_inv_custom = EvaluationResult(
        run_id="run_invalid",
        candidate_id="cand_B_invalid",
        policy_id="eval_policy_v1",
        policy_version="1.0.0",
        outcome=EvaluationOutcome.INVALID_RUN,
        passed_gates=[],
        failed_gates=["DATA_VALIDITY"],
        reasons=["PROVENANCE_CORRUPT"],
        metrics=run_invalid.metrics,
    )
    run_valid_2, eval_2 = _build_test_run(
        "run_2",
        candidate_id="cand_C",
        metrics={"net_profit_pct": 5.0, "sharpe_ratio": 0.9, "trade_count": 35},
    )

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


def test_single_report_rejects_evaluation_from_another_run() -> None:
    run, evaluation = _build_test_run("run_identity")
    wrong_evaluation = evaluation.model_copy(update={"run_id": "other_run"})

    with pytest.raises(ValueError, match="EVALUATION_IDENTITY_MISMATCH"):
        ExperimentSummaryReport.from_run(run, wrong_evaluation)


def test_leaderboard_rejects_swapped_evaluation_identities() -> None:
    run_a, evaluation_a = _build_test_run("run_identity_a", candidate_id="candidate_a")
    run_b, evaluation_b = _build_test_run("run_identity_b", candidate_id="candidate_b")

    with pytest.raises(ValueError, match="EVALUATION_IDENTITY_MISMATCH"):
        generate_multi_run_comparison_md(
            runs=[run_a, run_b],
            evaluations=[evaluation_b, evaluation_a],
        )


def test_disqualified_runs_render_in_stable_order() -> None:
    run_a, evaluation_a = _build_test_run(
        "run_invalid_a", status=ExperimentRunStatus.INVALID_RUN, candidate_id="candidate_a"
    )
    run_b, evaluation_b = _build_test_run(
        "run_invalid_b", status=ExperimentRunStatus.INVALID_RUN, candidate_id="candidate_b"
    )

    first = generate_multi_run_comparison_md([run_a, run_b], [evaluation_a, evaluation_b])
    reversed_order = generate_multi_run_comparison_md(
        [run_b, run_a], [evaluation_b, evaluation_a]
    )

    assert first == reversed_order


def test_report_01_statistical_selection_and_errors() -> None:
    """REPORT-01 edge cases: DSR/PBO rendering, length mismatch, and direct report objects."""
    run, eval_result = _build_test_run("run_stat_eval")
    eval_result_stat = EvaluationResult(
        run_id=run.run_id,
        candidate_id=run.candidate_id,
        policy_id="eval_policy_v1",
        policy_version="1.0.0",
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


def test_leaderboard_does_not_rank_a_run_with_no_net_profit_data() -> None:
    """REPORT-01-AC1/AC3: a run with no net profit must not receive a rank.

    ``_rank_key`` substituted ``float("-inf")`` for a missing ``net_profit_pct``,
    so an unmeasured run was still assigned a leaderboard position. Ranking a run
    that produced no performance data states a measured outcome that does not
    exist, which is exactly the "no-data berbeda dari zero profit" boundary and
    the spec rule "missing data is unavailable not zero".
    """
    run_measured, eval_measured = _build_test_run(
        "run_measured",
        candidate_id="cand_measured",
        metrics={"net_profit_pct": 10.0, "sharpe_ratio": 1.2, "trade_count": 30},
    )
    run_unmeasured, eval_unmeasured = _build_test_run(
        "run_unmeasured",
        candidate_id="cand_unmeasured",
        metrics={"net_profit_pct": None, "sharpe_ratio": None, "trade_count": 0},
    )

    md = generate_multi_run_comparison_md(
        runs=[run_measured, run_unmeasured],
        evaluations=[eval_measured, eval_unmeasured],
    )

    # The measured run keeps rank 1; the unmeasured run gets no rank at all.
    assert "| 1 | cand_measured" in md
    assert "| 2 | cand_unmeasured" not in md
    assert "| 1 | cand_unmeasured" not in md

    # It is still reported, in a dedicated section, so nothing is hidden.
    assert "### Unranked / No Data" in md
    assert "cand_unmeasured" in md
    assert "NO_DATA" in md


def test_leaderboard_does_not_rank_a_run_with_a_non_finite_net_profit() -> None:
    """REPORT-01-AC1: NaN and infinity are not data and must not be ranked.

    ``float("nan")`` compares false against every value, so a NaN metric produced
    an arbitrary, input-order-dependent leaderboard, and ``inf`` ranked a run
    above every real result. Both are missing/unusable data, not measurements.
    """
    run_measured, eval_measured = _build_test_run(
        "run_measured",
        candidate_id="cand_measured",
        metrics={"net_profit_pct": 10.0, "sharpe_ratio": 1.2, "trade_count": 30},
    )
    run_nan, eval_nan = _build_test_run(
        "run_nan",
        candidate_id="cand_nonfinite_a",
        metrics={"net_profit_pct": float("nan"), "sharpe_ratio": 1.0, "trade_count": 5},
    )
    run_inf, eval_inf = _build_test_run(
        "run_inf",
        candidate_id="cand_infinite_b",
        metrics={"net_profit_pct": float("inf"), "sharpe_ratio": 1.0, "trade_count": 5},
    )

    md = generate_multi_run_comparison_md(
        runs=[run_nan, run_inf, run_measured],
        evaluations=[eval_nan, eval_inf, eval_measured],
    )

    # The only real measurement is the one that ranks.
    assert "| 1 | cand_measured" in md
    assert "cand_nonfinite_a" not in md.split("### Unranked / No Data")[0]
    assert "cand_infinite_b" not in md.split("### Unranked / No Data")[0]

    # NaN/inf must never be rendered as a numeric percentage either.
    leaderboard_rows = [
        line
        for line in md.split("### Unranked / No Data")[0].splitlines()
        if line.startswith("| ") and "cand_" in line
    ]
    assert not any("nan" in row.lower() for row in leaderboard_rows)
    assert not any("inf" in row.lower() for row in leaderboard_rows)


def test_summary_markdown_reports_the_run_error_message() -> None:
    """REPORT-01-AC0: the run's own failure reason must be visible in the report.

    The failure reason is the whole point of "alasan penolakan tanpa membaca raw
    logs", but ``to_markdown`` never rendered ``error_message``, so a crashed run
    reported only the evaluator's generic rejection reasons and the actual cause
    existed only in the JSON artifact.
    """
    run, eval_result = _build_test_run(
        "run_crashed",
        status=ExperimentRunStatus.FAILED,
        metrics={"net_profit_pct": None, "sharpe_ratio": None, "trade_count": 0},
        error_message="DATA_LOAD_FAILED: snapshot_btc_2025_06 unreadable",
    )

    md = generate_experiment_report_md(run, eval_result)

    assert "DATA_LOAD_FAILED" in md, "the run's actual failure reason must be in the report"
    assert "### Run Error" in md
    # A clean run must not invent an error section.
    clean_run, clean_eval = _build_test_run("run_clean")
    assert "### Run Error" not in generate_experiment_report_md(clean_run, clean_eval)


def test_report_escapes_markdown_structure_in_untrusted_values() -> None:
    """REPORT-01: a newline in a value must not forge a leaderboard row.

    Candidate ids, run ids and rejection reasons reach these reports from
    persisted run records. Interpolated raw into a Markdown table, a value
    containing a newline or pipe breaks the table and injects attacker-shaped
    rows, so a reader sees a fabricated candidate in the ranking table. The spec
    requires "escape Markdown" for this subsystem.
    """
    run_real, eval_real = _build_test_run(
        "run_real",
        candidate_id="cand_real",
        metrics={"net_profit_pct": 10.0, "sharpe_ratio": 1.2, "trade_count": 30},
    )
    forged = "\n| 99 | cand_forged | run_forged | 999.00% | 99.00 | 99 | success | PASS |"
    run_hostile, eval_hostile = _build_test_run(
        "run_hostile",
        candidate_id=f"cand_hostile{forged}",
        metrics={"net_profit_pct": -5.0, "sharpe_ratio": -0.5, "trade_count": 4},
    )

    md = generate_multi_run_comparison_md(
        runs=[run_real, run_hostile],
        evaluations=[eval_real, eval_hostile],
    )

    # The injected payload must not be able to create a row of its own: the only
    # way a value becomes a row is a newline, and no value may contribute one.
    table_lines = [line for line in md.splitlines() if line.startswith("| ")]
    forged_rows = [
        line for line in table_lines if "cand_forged" in line and "cand_hostile" not in line
    ]
    assert forged_rows == [], "the injected payload forged a standalone leaderboard row"

    # And the table itself must still parse: a real ranked row has 9 cells, so
    # a payload that broke out of its cell would leave a different cell count.
    header_index = next(
        i for i, line in enumerate(table_lines) if line.startswith("| Rank | Candidate |")
    )
    body_rows = table_lines[header_index + 1 : header_index + 3]
    assert len(body_rows) == 2
    for row in body_rows:
        assert row.count("|") == 9, f"row escaped the table structure: {row!r}"


def test_leaderboard_preserves_each_run_identity_end_to_end() -> None:
    """REPORT-01: ranking must be reproducible for the same input set.

    A leaderboard whose order depends on hash or input ordering cannot be
    re-derived from the same artifacts later, which breaks the report's
    idempotency requirement.
    """
    runs = []
    evals = []
    for i, (net, sharpe) in enumerate([(5.0, 0.5), (5.0, 0.5), (5.0, 0.5)]):
        r, e = _build_test_run(
            f"run_tie_{i}",
            candidate_id=f"cand_tie_{i}",
            metrics={"net_profit_pct": net, "sharpe_ratio": sharpe, "trade_count": 10},
        )
        runs.append(r)
        evals.append(e)

    first = generate_multi_run_comparison_md(runs=runs, evaluations=evals)
    second = generate_multi_run_comparison_md(
        runs=list(reversed(runs)), evaluations=list(reversed(evals))
    )
    assert first == second, "identical input set must produce an identical leaderboard"
