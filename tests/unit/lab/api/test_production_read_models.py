from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from indodax_lab.api.services.production_read import ProductionReadService
from indodax_lab.control.mode import ExecutionMode
from indodax_lab.execution.indodax_readonly import VenueAccountSnapshot, VenueBalance
from indodax_lab.execution.state_store import ExecutionSnapshot

_NOW = datetime(2026, 9, 24, 4, 1, tzinfo=UTC)


class FakeModeStore:
    def get_effective_mode(self):
        return ExecutionMode.SHADOW

    def get_requested_mode(self):
        return ExecutionMode.SHADOW

    def verify_journal_integrity(self):
        return True

    def get_journal(self):
        return (
            {
                "sequence": 2,
                "entry_hash": "mode-rev-2",
                "timestamp_utc": "2026-09-24T04:00:00+00:00",
            },
        )


class FakeExecutionStore:
    namespace = "production_main"
    valuation_currency = "IDR"
    db_path = Path("var/lib/indodax/production.sqlite3")

    def restore(self):
        return ExecutionSnapshot(
            namespace=self.namespace,
            revision=7,
            feed_cursor=None,
            cash=Decimal("1250000"),
            positions={"btc_idr": {"base_qty": Decimal("0.002"), "cost_basis": Decimal("900000")}},
            orders={
                "ord-1": {
                    "client_order_id": "c1",
                    "venue_order_id": None,
                    "pair": "btc_idr",
                    "side": "buy",
                    "desired_qty": Decimal("0.002"),
                    "filled_qty": Decimal("0"),
                    "state": "UNKNOWN",
                }
            },
            reservations={},
            last_transaction_id="tx-7",
            halted=False,
        )


class FakeRiskEngine:
    is_kill_switch_active = False

    def verify_risk_state_integrity(self):
        return True


class FakeVenueAccountProvider:
    authority = "production.indodax.account"

    def __init__(self, snapshot):
        self.snapshot = snapshot

    def get_account_snapshot(self):
        return self.snapshot


def service(*, venue_account_source=None, namespace="production_main"):
    return ProductionReadService(
        mode_store=FakeModeStore(),
        execution_store=FakeExecutionStore(),
        risk_engine=FakeRiskEngine(),
        venue_account_source=venue_account_source,
        production_namespace=namespace,
        production_state_root=Path("var/lib/indodax"),
        clock=lambda: _NOW,
    )


def account_snapshot(server_time=_NOW - timedelta(seconds=1)):
    return VenueAccountSnapshot(
        server_time=server_time,
        balances={
            "btc": VenueBalance("btc", Decimal("0.002"), Decimal("0")),
            "idr": VenueBalance("idr", Decimal("1000000"), Decimal("250000")),
        },
    )


def test_api_01_0_missing_authority_never_becomes_healthy_or_zero():
    snapshot = service().snapshot(request_id="req-1")

    assert snapshot.overview.market_health == "UNKNOWN"
    assert snapshot.overview.venue_health == "UNKNOWN"
    assert snapshot.reconciliation.evidence.status == "UNAVAILABLE"
    assert snapshot.reconciliation.healthy is None
    assert snapshot.risk.utilization is None
    assert snapshot.risk.status == "UNKNOWN"
    assert snapshot.release.status == "UNAVAILABLE"
    assert snapshot.portfolio.evidence.status == "UNAVAILABLE"
    assert snapshot.portfolio.balances == ()
    assert snapshot.portfolio.quote_available is None


def test_api_01_7_account_freshness_uses_observation_time_after_provider_read():
    source_time = _NOW + timedelta(milliseconds=500)
    provider = FakeVenueAccountProvider(account_snapshot(source_time))
    read_service = service(venue_account_source=provider)
    clock_times = iter((_NOW, _NOW + timedelta(seconds=1)))
    read_service.clock = lambda: next(clock_times)

    snapshot = read_service.snapshot(request_id="req-fresh-after-fetch")

    assert snapshot.portfolio.evidence.status == "AVAILABLE"
    assert snapshot.portfolio.evidence.freshness == "FRESH"
    assert snapshot.portfolio.evidence.as_of == _NOW + timedelta(seconds=1)
    assert snapshot.overview.unknown_orders_count == 1
    assert snapshot.orders.data[0].state == "UNKNOWN"
    assert snapshot.fills.evidence.status == "UNAVAILABLE"
    assert snapshot.audit.last_event is None


def test_api_01_1_live_venue_balances_have_server_time_and_provenance():
    provider = FakeVenueAccountProvider(account_snapshot())
    snapshot = service(venue_account_source=provider).snapshot(request_id="req-2")
    portfolio = snapshot.portfolio

    assert snapshot.as_of == _NOW
    assert snapshot.provenance.source == "production-read-service"
    assert snapshot.mode.evidence.source_revision == "mode-rev-2"
    assert snapshot.positions.evidence.source_revision == "7"
    assert portfolio.evidence.source == "production.venue_account"
    assert portfolio.evidence.status == "AVAILABLE"
    assert portfolio.evidence.freshness == "FRESH"
    assert portfolio.evidence.as_of == _NOW
    assert portfolio.evidence.source_updated_at == _NOW - timedelta(seconds=1)
    assert portfolio.evidence.source_revision
    assert portfolio.balance_authority == "AVAILABLE"
    assert portfolio.quote_available == Decimal("1000000")
    assert portfolio.quote_hold == Decimal("250000")
    assert portfolio.quote_currency == "idr"
    assert portfolio.equity is None
    assert {balance.currency: balance.total for balance in portfolio.balances} == {
        "btc": Decimal("0.002"),
        "idr": Decimal("1250000"),
    }


@pytest.mark.parametrize("namespace", ["research-shadow-agent-1", "tournament-1", "prod_paper"])
def test_api_01_2_non_production_namespace_cannot_be_read_as_production(namespace):
    read_service = service(namespace=namespace)
    read_service.execution_store.namespace = namespace
    snapshot = read_service.snapshot(request_id="req-3")

    assert snapshot.positions.evidence.status == "UNAVAILABLE"
    assert snapshot.positions.evidence.reason == "NON_PRODUCTION_NAMESPACE_FORBIDDEN"
    assert snapshot.orders.evidence.status == "UNAVAILABLE"
    assert snapshot.overview.unknown_orders_count is None
    assert snapshot.release.verified is None
    assert snapshot.release.status == "UNAVAILABLE"


def test_api_01_3_stale_venue_account_is_unavailable_and_never_zero():
    provider = FakeVenueAccountProvider(account_snapshot(_NOW - timedelta(seconds=31)))
    portfolio = service(venue_account_source=provider).snapshot(request_id="req-4").portfolio

    assert portfolio.evidence.status == "UNAVAILABLE"
    assert portfolio.evidence.freshness == "STALE"
    assert portfolio.evidence.source_updated_at == _NOW - timedelta(seconds=31)
    assert portfolio.balances == ()
    assert portfolio.quote_available is None


def test_api_01_4_research_account_provider_cannot_satisfy_production_portfolio():
    provider = FakeVenueAccountProvider(account_snapshot())
    provider.authority = "research.indodax.account"
    portfolio = service(venue_account_source=provider).snapshot(request_id="req-5").portfolio

    assert portfolio.evidence.status == "UNAVAILABLE"
    assert portfolio.evidence.reason == "PRODUCTION_ACCOUNT_PROVIDER_REQUIRED"
    assert portfolio.balances == ()
    assert portfolio.quote_available is None


def test_api_01_5_research_database_cannot_satisfy_production_positions_or_orders():
    read_service = service()
    read_service.execution_store.db_path = Path("var/lib/research.sqlite3")
    snapshot = read_service.snapshot(request_id="req-6")

    assert snapshot.positions.evidence.status == "UNAVAILABLE"
    assert snapshot.positions.evidence.reason == "EXECUTION_DATABASE_OUTSIDE_PRODUCTION_ROOT"
    assert snapshot.orders.evidence.status == "UNAVAILABLE"
    assert snapshot.orders.data == ()
    assert snapshot.overview.unknown_orders_count is None
