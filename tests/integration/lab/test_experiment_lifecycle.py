"""RW3-01 acceptance: experiment lifecycle and backtest orchestration.

Fake clocks/candidates/transports, temporary state only. No network,
no credentials, no live DB. Candidate doubles are explicit test fixtures;
the default path calls the real CandidateRuntime.load_plan (AC5).
"""
import threading
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.backtest.events import MarketBar
from indodax_lab.contracts.identity import ArtifactRef, manifest_digest
from indodax_lab.contracts.workbench import RuntimePlan, VerifiedRuntimePlan
from indodax_lab.evaluation.experiment_service import (
    ExperimentManifest,
    ExperimentService,
    ResolvedDataset,
)

BASE_TS = datetime(2025, 1, 1, tzinfo=UTC)
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
PLAN_SEED_DIGEST = "ab" * 32


def _ref(kind="dataset", ident="ds1"):
    return ArtifactRef(kind=kind, id=ident, version="v1", sha256="cd" * 32)


def _manifest(pairs=("btc_idr",), capital=Decimal("10000000"), seed=7):
    return ExperimentManifest(
        name="rw3-probe",
        dataset_ref=_ref(),
        pipeline_ref=_ref(kind="pipeline", ident="pipe1"),
        policy_version="risk-v1",
        seed=seed,
        pairs=tuple(pairs),
        capital=capital,
    )


def _test_plan():
    plan = RuntimePlan(
        plan_id="plan_rw3",
        version="1.0.0",
        universe=("btc_idr", "eth_idr"),
        timeframe="1h",
        dataset_refs=(_ref(),),
        pipeline_ref=_ref(kind="pipeline", ident="pipe1"),
        feature_schema_hash="ef" * 32,
        ordered_feature_names=("ema_fast", "ema_slow", "atr_14"),
        sizing_policy_ref=_ref(kind="policy", ident="size1"),
        exit_policy_ref=_ref(kind="policy", ident="exit1"),
        risk_policy_ref=_ref(kind="policy", ident="risk1"),
        cost_policy_ref=_ref(kind="policy", ident="cost1"),
        execution_policy_ref=_ref(kind="policy", ident="exec1"),
        git_sha="01" * 20,
        environment_digest="23" * 32,
        seed=7,
    )
    return VerifiedRuntimePlan(
        plan=plan,
        plan_digest=manifest_digest(plan),
        verified_at_utc=NOW,
    )


def _service(tmp_path: Path, clock=None, candidate_factory=None):
    now = [NOW]

    def _clock():
        return now[0]

    service = ExperimentService(
        run_root=tmp_path / "runs",
        queue_path=tmp_path / "jobs.sqlite",
        clock=clock or _clock,
        dataset_resolver=lambda ref: ResolvedDataset(
            snapshot_id="snap_test_001", content_hash="ab" * 32
        ),
        pipeline_resolver=lambda ref: _test_plan(),
        candidate_factory=candidate_factory,
        policy_versions={"risk-v1"},
    )
    return service, now


def _bar(pair: str, close_time: datetime, price: str) -> MarketBar:
    return MarketBar(
        pair=pair,
        open_time=close_time - timedelta(minutes=1),
        close_time=close_time,
        open=Decimal(price),
        high=Decimal(price),
        low=Decimal(price),
        close=Decimal(price),
        base_volume=Decimal("1"),
        quote_volume=Decimal(price),
    )


def _events(pair: str, prices: list[str]):
    from indodax_lab.runtime.candidate import CanonicalMarketEvent

    out = []
    for i, price in enumerate(prices, start=1):
        ts = BASE_TS + timedelta(minutes=i)
        out.append(
            CanonicalMarketEvent(
                event_id=f"feed-{pair}-{i}",
                feed_id=f"feed-{pair}",
                sequence=i,
                pair=pair,
                event_time=ts,
                available_at=ts,
                observation=_bar(pair, ts, price),
                quality_ref=None,
            )
        )
    return out


def _stub_candidate_factory(plan_digest: str, behavior: str = "buy"):
    """Explicit test double: deterministic intents per pair (namespace stub)."""

    from types import SimpleNamespace

    from indodax_lab.contracts.decision import SignalIntent

    def _factory(plan, pair: str):
        def _evaluate(event, state):
            seq = event.sequence
            head = f"{pair[:3]}{seq:02d}rw3x"
            if behavior == "buy_sell" and pair == "btc_idr" and seq == 2:
                return (
                    SignalIntent(
                        intent_id=f"{head}sell",
                        decision_ts=event.event_time,
                        pair=pair,
                        side=OrderSide.SELL,
                        desired_qty=Decimal("0.001"),
                        limit_price=Decimal("110"),
                        stop_loss=None,
                        take_profit=None,
                    ),
                )
            return (
                SignalIntent(
                    intent_id=f"{head}buy1",
                    decision_ts=event.event_time,
                    pair=pair,
                    side=OrderSide.BUY,
                    desired_qty=Decimal("0.001"),
                    limit_price=Decimal("100"),
                    stop_loss=None,
                    take_profit=None,
                ),
            )

        return SimpleNamespace(
            plan_digest=plan_digest, candidate_digest=None, evaluate=_evaluate
        )

    return _factory


def test_rw3_01_bootstrap_recovery(tmp_path: Path) -> None:
    """RW3-01-AC5: first run from resolved components, pinned plan digest bound."""
    service, _ = _service(tmp_path)
    exp = service.create(_manifest())
    assert exp.status == "DRAFT"
    report = service.validate(exp.experiment_id)
    assert report.valid is True
    assert report.runtime_plan_digest == manifest_digest(_test_plan().plan)

    service.event_source = lambda pair: _events(pair, ["100"] * 30)
    job = service.run_backtest(exp.experiment_id)
    assert job.status.value == "SUCCESS"
    result = service.result(exp.experiment_id)
    assert result.runtime_plan_digest == report.runtime_plan_digest
    assert Path(result.artifact_path).is_file()
    import hashlib

    assert (
        hashlib.sha256(Path(result.artifact_path).read_bytes()).hexdigest()
        == result.artifact_sha256
    )


def test_rw3_01_0(tmp_path: Path) -> None:
    """RW3-01-AC0: completed edit rejects; clone always mints a new ID."""
    service, _ = _service(
        tmp_path, candidate_factory=_stub_candidate_factory(PLAN_SEED_DIGEST)
    )
    exp = service.create(_manifest())
    service.validate(exp.experiment_id)
    service.event_source = lambda pair: _events(pair, ["100"])
    service.run_backtest(exp.experiment_id)

    with pytest.raises(ValueError, match="EXPERIMENT_EDIT_REJECTED"):
        service.edit(exp.experiment_id, name="mutated")
    clone = service.clone(exp.experiment_id, {"name": "forked"})
    assert clone.experiment_id != exp.experiment_id
    assert clone.parent_id == exp.experiment_id
    assert clone.status == "DRAFT"
    assert clone.manifest.name == "forked"


def test_rw3_01_1(tmp_path: Path) -> None:
    """RW3-01-AC1: cancel racing a stale worker prevents publication."""
    gate = threading.Event()
    started = threading.Event()

    def _factory(plan, pair: str):
        from types import SimpleNamespace

        from indodax_lab.contracts.decision import SignalIntent

        def _evaluate(event, state):
            started.set()
            assert gate.wait(timeout=30)
            return (
                SignalIntent(
                    intent_id=f"{pair[:3]}01rw3xbuy1",
                    decision_ts=event.event_time,
                    pair=pair,
                    side=OrderSide.BUY,
                    desired_qty=Decimal("0.001"),
                    limit_price=Decimal("100"),
                    stop_loss=None,
                    take_profit=None,
                ),
            )

        return SimpleNamespace(
            plan_digest=PLAN_SEED_DIGEST, candidate_digest=None, evaluate=_evaluate
        )

    service, now = _service(tmp_path, candidate_factory=_factory)
    exp = service.create(_manifest())
    service.validate(exp.experiment_id)
    service.event_source = lambda pair: _events(pair, ["100"])

    thread = threading.Thread(
        target=service.run_backtest, args=(exp.experiment_id,), daemon=True
    )
    thread.start()
    assert started.wait(timeout=30)
    from datetime import UTC as _UTC
    from datetime import datetime as _dt

    _deadline = _dt.now(_UTC) + timedelta(seconds=30)
    while service.get(exp.experiment_id).status != "RUNNING":
        assert _dt.now(_UTC) < _deadline, "worker never reached RUNNING"
    cancelled = service.cancel(exp.experiment_id, "req-cancel-1")
    assert cancelled.status == "CANCELLED"
    gate.set()
    thread.join(timeout=60)
    assert not thread.is_alive()

    final = service.get(exp.experiment_id)
    assert final.status == "CANCELLED"
    job = service.queue.get_job(f"rw3_{exp.experiment_id}")
    assert job.status.value != "SUCCESS"
    with pytest.raises(ValueError, match="NOT_TERMINAL"):
        service.result(exp.experiment_id)


def test_rw3_01_2(tmp_path: Path) -> None:
    """RW3-01-AC2: crash between artifact and final status resumes idempotently."""
    service, now = _service(
        tmp_path, candidate_factory=_stub_candidate_factory(PLAN_SEED_DIGEST)
    )
    exp = service.create(_manifest())
    service.validate(exp.experiment_id)
    service.event_source = lambda pair: _events(pair, ["100", "101"])

    real_complete = service.queue.complete_job
    crashed = {"done": False}

    def _crash_once(*args, **kwargs):
        if not crashed["done"]:
            crashed["done"] = True
            raise RuntimeError("SIMULATED_CRASH_AFTER_ARTIFACT")
        return real_complete(*args, **kwargs)

    service.queue.complete_job = _crash_once  # type: ignore[method-assign]
    try:
        crashed_result = service.run_backtest(exp.experiment_id)
        assert crashed_result is None  # crash path returns no job ref
    finally:
        service.queue.complete_job = real_complete  # type: ignore[method-assign]
    assert service.get(exp.experiment_id).status == "FAILED"

    now[0] = NOW + timedelta(seconds=300)
    job = service.run_backtest(exp.experiment_id)
    assert job.status.value == "SUCCESS"
    result = service.result(exp.experiment_id)
    assert result.status == "SUCCESS"
    # No duplicate orders from the resumed replay.
    total_orders = sum(len(child.order_ids) for child in result.children)
    assert total_orders == 2


def test_rw3_01_3(tmp_path: Path) -> None:
    """RW3-01-AC3: failed trials remain queryable (record, job, counts)."""

    def _factory(plan, pair: str):
        from types import SimpleNamespace

        def _evaluate(event, state):
            raise RuntimeError("TRIAL_POISON")

        return SimpleNamespace(
            plan_digest=PLAN_SEED_DIGEST, candidate_digest=None, evaluate=_evaluate
        )

    service, _ = _service(tmp_path, candidate_factory=_factory)
    exp = service.create(_manifest())
    service.validate(exp.experiment_id)
    service.event_source = lambda pair: _events(pair, ["100"])
    job = service.run_backtest(exp.experiment_id)
    assert job.status.value in ("FAILED_RETRYABLE", "FAILED_FINAL")

    failed = service.get(exp.experiment_id)
    assert failed.status == "FAILED"
    assert "TRIAL_POISON" in (failed.error_message or "")
    listed = service.list_experiments(status="FAILED")
    assert [e.experiment_id for e in listed] == [exp.experiment_id]
    assert service.queue.get_job(job.job_id).status.value == job.status.value


def test_rw3_01_4(tmp_path: Path) -> None:
    """RW3-01-AC4: same manifest/seed/events reproduces the normalized digest."""
    service, _ = _service(
        tmp_path, candidate_factory=_stub_candidate_factory(PLAN_SEED_DIGEST)
    )
    exp = service.create(_manifest())
    service.validate(exp.experiment_id)
    service.event_source = lambda pair: _events(pair, ["100", "101"])
    service.run_backtest(exp.experiment_id)
    first = service.result(exp.experiment_id).result_digest

    exp2 = service.create(_manifest())
    service.validate(exp2.experiment_id)
    service.run_backtest(exp2.experiment_id)
    second = service.result(exp2.experiment_id).result_digest
    assert first == second

    exp3 = service.create(_manifest(seed=99))
    service.validate(exp3.experiment_id)
    service.run_backtest(exp3.experiment_id)
    assert service.result(exp3.experiment_id).result_digest != first


def test_rw3_01_program_6(tmp_path: Path) -> None:
    """RW3-01-AC6: multi-pair batch, equal capital, stable child IDs on retry."""
    service, _ = _service(
        tmp_path, candidate_factory=_stub_candidate_factory(PLAN_SEED_DIGEST)
    )
    exp = service.create(_manifest(pairs=("btc_idr", "eth_idr")))
    service.validate(exp.experiment_id)
    service.event_source = lambda pair: _events(pair, ["100"])
    job = service.run_backtest(exp.experiment_id)
    assert job.status.value == "SUCCESS"
    result = service.result(exp.experiment_id)
    assert sorted(c.pair for c in result.children) == ["btc_idr", "eth_idr"]
    capitals = {c.capital for c in result.children}
    assert capitals == {Decimal("5000000")}
    first_ids = sorted(c.child_id for c in result.children)

    again = service.run_backtest(exp.experiment_id)
    assert again.status.value == "SUCCESS"
    assert sorted(
        c.child_id for c in service.result(exp.experiment_id).children
    ) == first_ids


def test_rw3_01_program_7(tmp_path: Path) -> None:
    """RW3-01-AC7: one failed pair preserves siblings and stays visible."""

    def _factory(plan, pair: str):
        from types import SimpleNamespace

        def _evaluate(event, state):
            if pair == "eth_idr":
                raise RuntimeError("TRIAL_POISON_ETH")
            from indodax_lab.contracts.decision import SignalIntent

            return (
                SignalIntent(
                    intent_id=f"{pair[:3]}01rw3xbuy1",
                    decision_ts=event.event_time,
                    pair=pair,
                    side=OrderSide.BUY,
                    desired_qty=Decimal("0.001"),
                    limit_price=Decimal("100"),
                    stop_loss=None,
                    take_profit=None,
                ),
            )

        return SimpleNamespace(
            plan_digest=PLAN_SEED_DIGEST, candidate_digest=None, evaluate=_evaluate
        )

    service, _ = _service(tmp_path, candidate_factory=_factory)
    exp = service.create(_manifest(pairs=("btc_idr", "eth_idr")))
    service.validate(exp.experiment_id)
    service.event_source = lambda pair: _events(pair, ["100"])
    service.run_backtest(exp.experiment_id)

    final = service.get(exp.experiment_id)
    assert final.status == "FAILED"
    result = service.result(exp.experiment_id)
    by_pair = {c.pair: c for c in result.children}
    assert by_pair["btc_idr"].status == "SUCCESS"
    assert by_pair["btc_idr"].order_ids != []
    assert by_pair["eth_idr"].status == "FAILED"
    assert "TRIAL_POISON_ETH" in (by_pair["eth_idr"].error_message or "")


def test_rw3_01_program_8(tmp_path: Path) -> None:
    """RW3-01-AC8: trade report separates fills/closed/open/fees; win rate explicit."""
    service, _ = _service(
        tmp_path,
        candidate_factory=_stub_candidate_factory(PLAN_SEED_DIGEST, behavior="buy_sell"),
    )
    exp = service.create(_manifest())
    service.validate(exp.experiment_id)
    service.event_source = lambda pair: _events(pair, ["100", "110"])
    service.run_backtest(exp.experiment_id)

    report = service.trade_report(exp.experiment_id)
    assert report.fills != []
    assert all(isinstance(f.qty, Decimal) for f in report.fills)
    assert len(report.closed_trades) == 1
    assert report.closed_trades[0].pair == "btc_idr"
    assert report.closed_trades[0].realized_pnl == Decimal("0.01")
    assert report.win_rate == Decimal("1")
    assert report.fee_status == "FEES_UNKNOWN"

    service2, _ = _service(
        tmp_path / "svc2", candidate_factory=_stub_candidate_factory(PLAN_SEED_DIGEST)
    )
    exp_b = service2.create(_manifest())
    service2.validate(exp_b.experiment_id)
    service2.event_source = lambda pair: _events(pair, ["100", "101"])
    service2.run_backtest(exp_b.experiment_id)
    report_b = service2.trade_report(exp_b.experiment_id)
    assert tuple(report_b.closed_trades) == ()
    assert report_b.win_rate_status == "UNAVAILABLE"
    assert "no_closed_trades" in report_b.win_rate_reason
