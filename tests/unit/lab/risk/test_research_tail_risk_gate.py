from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.backtest.events import SignalIntent
from indodax_lab.backtest.ledger import Position
from indodax_lab.backtest.risk import PortfolioRiskManager, RiskPolicy
from indodax_lab.risk.engine import RiskEngine

NOW = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)


def _risk_manager() -> PortfolioRiskManager:
    return PortfolioRiskManager(
        policy=RiskPolicy(
            policy_id="risk-test",
            version="1",
            max_position_fraction=Decimal("0.25"),
            max_open_positions=3,
            min_order_notional=Decimal("10000"),
        ),
        initial_equity=Decimal("100000000"),
        start_time=NOW,
    )


def _intent(side: OrderSide = OrderSide.BUY) -> SignalIntent:
    return SignalIntent(
        intent_id=f"tail-{side.value}",
        decision_ts=NOW,
        pair="btc_idr",
        side=side,
        desired_qty=Decimal("0.02"),
        limit_price=Decimal("1000000000"),
    )


def _policy() -> dict[str, object]:
    # Explicit fixture values exercise a configured policy; they are not defaults.
    return {
        "policy_id": "research-tail-fixture",
        "version": "test-v1",
        "approved_by": "test-operator",
        "approval_ref": "TEST-APPROVAL-1",
        "evidence_source_id": "fixture-bars",
        "evidence_source_version": "fixture-v1",
        "max_pump_gap_fraction": "0.10",
        "max_amihud_24_1h": "0.01",
        "max_evidence_age_seconds": 120,
    }


def _evidence(**overrides: object) -> dict[str, object]:
    evidence: dict[str, object] = {
        "pair": "btc_idr",
        "decision_ts": NOW,
        "event_at": NOW - timedelta(seconds=90),
        "available_at": NOW - timedelta(seconds=60),
        "risk_period_id": "period-test-1",
        "source_id": "fixture-bars",
        "source_version": "fixture-v1",
        "source_sha256": "a" * 64,
        "pump_gap_fraction": "0.02",
        "amihud_24_1h": "0.001",
    }
    evidence.update(overrides)
    return evidence


def _assess(
    engine: RiskEngine,
    intent: SignalIntent | None = None,
    evidence: dict[str, object] | None = None,
    positions: dict[str, Position] | None = None,
    evaluation_time: datetime = NOW,
):
    kwargs = {
        "current_equity": Decimal("100000000"),
        "current_positions": positions or {},
        "mark_prices": {"btc_idr": Decimal("1000000000")},
        "evaluation_time": evaluation_time,
        "available_cash": Decimal("100000000"),
        "research_risk_period_id": "period-test-1",
    }
    if evidence is not None:
        kwargs["research_tail_risk_evidence"] = evidence
    return engine.assess_intent(intent or _intent(), **kwargs)


def test_research_tail_gate_fails_closed_when_required_policy_is_missing() -> None:
    engine = RiskEngine(risk_manager=_risk_manager(), research_tail_risk_required=True)

    result = _assess(engine)

    assert not result.approved
    assert result.reason_code == "RESEARCH_TAIL_POLICY_MISSING"


def test_research_tail_gate_fails_closed_when_evidence_is_missing() -> None:
    engine = RiskEngine(
        risk_manager=_risk_manager(),
        research_tail_risk_policy=_policy(),
    )

    result = _assess(engine)

    assert not result.approved
    assert result.reason_code == "RESEARCH_TAIL_EVIDENCE_MISSING"


def test_research_tail_gate_fails_closed_for_unapproved_thresholds() -> None:
    policy = _policy()
    policy["max_pump_gap_fraction"] = None
    engine = RiskEngine(
        risk_manager=_risk_manager(),
        research_tail_risk_required=True,
        research_tail_risk_policy=policy,
    )

    result = _assess(engine, evidence=_evidence())

    assert not result.approved
    assert result.reason_code == "RESEARCH_TAIL_POLICY_UNAPPROVED"


@pytest.mark.parametrize(
    ("evidence_overrides", "reason"),
    [
        ({"available_at": NOW + timedelta(seconds=1)}, "RESEARCH_TAIL_EVIDENCE_NOT_CAUSAL"),
        (
            {
                "event_at": NOW - timedelta(seconds=180),
                "available_at": NOW - timedelta(seconds=121),
            },
            "RESEARCH_TAIL_EVIDENCE_STALE",
        ),
        ({"risk_period_id": "other-period"}, "RESEARCH_TAIL_EVIDENCE_PERIOD_MISMATCH"),
        ({"source_version": "unregistered-v2"}, "RESEARCH_TAIL_EVIDENCE_LINEAGE_MISMATCH"),
        ({"pump_gap_fraction": None}, "RESEARCH_TAIL_EVIDENCE_INCOMPLETE"),
    ],
)
def test_research_tail_gate_rejects_bad_or_stale_evidence(
    evidence_overrides: dict[str, object], reason: str
) -> None:
    engine = RiskEngine(
        risk_manager=_risk_manager(),
        research_tail_risk_policy=_policy(),
    )

    result = _assess(engine, evidence=_evidence(**evidence_overrides))

    assert not result.approved
    assert result.reason_code == reason


def test_research_tail_gate_checks_freshness_at_assessment_time() -> None:
    engine = RiskEngine(
        risk_manager=_risk_manager(),
        research_tail_risk_policy=_policy(),
    )

    result = _assess(
        engine,
        evidence=_evidence(),
        evaluation_time=NOW + timedelta(seconds=121),
    )

    assert not result.approved
    assert result.reason_code == "RESEARCH_TAIL_EVIDENCE_STALE"


@pytest.mark.parametrize(
    ("evidence_overrides", "reason"),
    [
        ({"pump_gap_fraction": "0.11"}, "RESEARCH_TAIL_PUMP_GAP_BREACH"),
        ({"amihud_24_1h": "0.011"}, "RESEARCH_TAIL_ILLIQUIDITY_BREACH"),
    ],
)
def test_research_tail_gate_blocks_configured_breaches(
    evidence_overrides: dict[str, object], reason: str
) -> None:
    engine = RiskEngine(
        risk_manager=_risk_manager(),
        research_tail_risk_policy=_policy(),
    )

    result = _assess(engine, evidence=_evidence(**evidence_overrides))

    assert not result.approved
    assert result.reason_code == reason


def test_research_tail_gate_allows_valid_buy_and_does_not_block_sell() -> None:
    engine = RiskEngine(
        risk_manager=_risk_manager(),
        research_tail_risk_required=True,
        research_tail_risk_policy=_policy(),
    )

    buy = _assess(engine, evidence=_evidence())
    sell = _assess(
        engine,
        _intent(OrderSide.SELL),
        positions={
            "btc_idr": Position(
                pair="btc_idr",
                base_qty=Decimal("0.02"),
                cost_basis=Decimal("20000000"),
            )
        },
    )

    assert buy.approved
    assert sell.approved
