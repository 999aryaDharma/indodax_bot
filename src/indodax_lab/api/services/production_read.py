"""Assemble read-only Production views from independently owned authorities."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal, Protocol

from indodax_lab.api.contracts.common import Provenance
from indodax_lab.api.contracts.production import (
    AuditView,
    BalanceView,
    FillsView,
    Freshness,
    OrdersView,
    OrderView,
    PortfolioView,
    PositionsView,
    PositionView,
    ProductionModeView,
    ProductionOverview,
    ProductionReadSnapshot,
    ReconciliationView,
    ReleaseView,
    ResourceEvidence,
    RiskView,
)
from indodax_lab.control.mode import DurableModeStore
from indodax_lab.execution.indodax_readonly import VenueAccountSnapshot
from indodax_lab.execution.reconciliation import ReconciliationPolicy
from indodax_lab.execution.state_store import ExecutionStateStore
from indodax_lab.risk.engine import RiskEngine


class VenueAccountProvider(Protocol):
    authority: Literal["production.indodax.account"]

    def get_account_snapshot(self) -> VenueAccountSnapshot: ...


class ProductionReadService:
    """Build immutable views from explicitly injected Production-owned read sources."""

    def __init__(
        self,
        *,
        mode_store: DurableModeStore | None = None,
        execution_store: ExecutionStateStore | None = None,
        risk_engine: RiskEngine | None = None,
        venue_account_source: VenueAccountProvider | None = None,
        production_namespace: str | None = None,
        production_state_root: str | Path | None = None,
        reconciliation_policy: ReconciliationPolicy | None = None,
        clock: Callable[[], datetime] | None = None,
        max_orders: int = 500,
    ) -> None:
        if max_orders < 1:
            raise ValueError("MAX_ORDERS_MUST_BE_POSITIVE")
        self.mode_store = mode_store
        self.execution_store = execution_store
        self.risk_engine = risk_engine
        self.venue_account_source = venue_account_source
        self.production_namespace = production_namespace.strip() if production_namespace else None
        self.production_state_root = (
            Path(production_state_root).resolve() if production_state_root is not None else None
        )
        policy = reconciliation_policy or ReconciliationPolicy()
        self.reconciliation_policy = policy
        self.max_account_snapshot_age = policy.max_snapshot_age
        self.clock = clock or (lambda: datetime.now(UTC))
        self.max_orders = max_orders

    @staticmethod
    def _evidence(
        *,
        status: str,
        source: str,
        as_of: datetime | None = None,
        revision: str | None = None,
        source_updated_at: datetime | None = None,
        freshness: Freshness = "UNKNOWN",
        reason: str | None = None,
    ) -> ResourceEvidence:
        return ResourceEvidence(
            status=status,
            source=source,
            source_revision=revision,
            as_of=as_of,
            source_updated_at=source_updated_at,
            freshness=freshness,
            reason=reason,
        )

    @staticmethod
    def _parse_utc(value: str) -> datetime | None:
        try:
            parsed = datetime.fromisoformat(value)
        except (TypeError, ValueError):
            return None
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed.astimezone(UTC)

    def snapshot(
        self,
        *,
        request_id: str,
        orders_offset: int = 0,
        orders_limit: int | None = None,
    ) -> ProductionReadSnapshot:
        if not request_id or not request_id.strip():
            raise ValueError("REQUEST_ID_REQUIRED")
        if orders_offset < 0:
            raise ValueError("ORDERS_OFFSET_MUST_BE_NON_NEGATIVE")
        if orders_limit is not None and orders_limit < 1:
            raise ValueError("ORDERS_LIMIT_MUST_BE_POSITIVE")
        selected_order_limit = self.max_orders if orders_limit is None else orders_limit
        as_of = self.clock()
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("UTC_TIMEZONE_AWARE_REQUIRED:as_of")
        as_of = as_of.astimezone(UTC)

        mode = self._mode_view(as_of)
        positions, orders, unknown_orders = self._execution_views(
            as_of, orders_offset=orders_offset, orders_limit=selected_order_limit
        )
        portfolio = self._venue_portfolio(as_of)
        risk = self._risk_view(as_of)
        reconciliation = ReconciliationView(
            evidence=self._evidence(
                status="UNAVAILABLE",
                source="production.reconciliation",
                reason="NO_AUTHORITATIVE_RECONCILIATION_SNAPSHOT",
            )
        )
        release = ReleaseView(
            evidence=self._evidence(
                status="UNAVAILABLE",
                source="production.release_registry",
                reason="NO_VERIFIED_CURRENT_RELEASE_SOURCE",
            )
        )
        fills = FillsView(
            evidence=self._evidence(
                status="UNAVAILABLE",
                source="production.fill_history",
                reason="NO_AUTHORITATIVE_FILL_HISTORY_READ_MODEL",
            )
        )
        audit = AuditView(
            evidence=self._evidence(
                status="UNAVAILABLE",
                source="production.audit",
                reason="NO_AUTHORITATIVE_AUDIT_READ_MODEL",
            )
        )
        overview = ProductionOverview(
            mode=mode.effective_mode,
            reconciliation_status=reconciliation.evidence.status,
            unknown_orders_count=unknown_orders,
            risk_status=risk.status,
            release_id=release.release_id,
            last_audit_event=audit.last_event,
        )

        revisions = {
            "mode": mode.evidence.source_revision,
            "portfolio": portfolio.evidence.source_revision,
            "positions": positions.evidence.source_revision,
            "orders": orders.evidence.source_revision,
            "risk": risk.evidence.source_revision,
        }
        known_revisions = {key: value for key, value in revisions.items() if value is not None}
        aggregate_revision = (
            hashlib.sha256(
                json.dumps(known_revisions, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            if known_revisions
            else "unavailable"
        )
        return ProductionReadSnapshot(
            request_id=request_id.strip(),
            as_of=as_of,
            source_revision=aggregate_revision,
            provenance=Provenance(
                source="production-read-service", revision=aggregate_revision
            ),
            status="PARTIAL" if known_revisions else "UNAVAILABLE",
            overview=overview,
            mode=mode,
            portfolio=portfolio,
            positions=positions,
            orders=orders,
            fills=fills,
            reconciliation=reconciliation,
            risk=risk,
            release=release,
            audit=audit,
        )

    def _mode_view(self, as_of: datetime) -> ProductionModeView:
        source = "production.mode_store"
        if self.mode_store is None:
            return ProductionModeView(
                evidence=self._evidence(
                    status="UNAVAILABLE", source=source, reason="MODE_STORE_NOT_CONFIGURED"
                )
            )
        try:
            if not self.mode_store.verify_journal_integrity():
                raise ValueError("MODE_JOURNAL_UNVERIFIED")
            journal = self.mode_store.get_journal()
            if not journal:
                raise ValueError("MODE_JOURNAL_EMPTY")
            latest = journal[-1]
            revision = str(latest.get("entry_hash") or latest.get("sequence") or "")
            source_updated_at = self._parse_utc(latest.get("timestamp_utc"))
            if not revision or source_updated_at is None:
                raise ValueError("MODE_REVISION_OR_TIMESTAMP_MISSING")
            return ProductionModeView(
                evidence=self._evidence(
                    status="AVAILABLE",
                    source=source,
                    as_of=as_of,
                    revision=revision,
                    source_updated_at=source_updated_at,
                ),
                effective_mode=str(self.mode_store.get_effective_mode().value),
                requested_mode=str(self.mode_store.get_requested_mode().value),
            )
        except Exception:
            return ProductionModeView(
                evidence=self._evidence(
                    status="UNAVAILABLE", source=source, reason="MODE_AUTHORITY_UNAVAILABLE"
                )
            )

    def _execution_views(
        self, as_of: datetime, *, orders_offset: int, orders_limit: int
    ) -> tuple[PositionsView, OrdersView, int | None]:
        source = "production.execution_state"
        if self.execution_store is None:
            reason = "EXECUTION_STORE_NOT_CONFIGURED"
        elif self.production_namespace is None:
            reason = "PRODUCTION_NAMESPACE_NOT_CONFIGURED"
        elif self._is_non_production_namespace(self.production_namespace):
            reason = "NON_PRODUCTION_NAMESPACE_FORBIDDEN"
        elif self.production_state_root is None:
            reason = "PRODUCTION_STATE_ROOT_NOT_CONFIGURED"
        elif getattr(self.execution_store, "namespace", None) != self.production_namespace:
            reason = "EXECUTION_NAMESPACE_MISMATCH"
        elif not self._execution_store_is_within_production_root():
            reason = "EXECUTION_DATABASE_OUTSIDE_PRODUCTION_ROOT"
        else:
            reason = ""
        if reason:
            evidence = self._evidence(status="UNAVAILABLE", source=source, reason=reason)
            return (
                PositionsView(evidence=evidence),
                OrdersView(evidence=evidence),
                None,
            )
        try:
            snapshot = self.execution_store.restore()
            if snapshot.namespace != self.production_namespace:
                raise ValueError("EXECUTION_NAMESPACE_MISMATCH")
            revision = str(snapshot.revision)
            evidence = self._evidence(
                status="PARTIAL",
                source=source,
                as_of=as_of,
                revision=revision,
                reason="RECONCILIATION_AND_SOURCE_FRESHNESS_UNAVAILABLE",
            )
            positions_data = tuple(
                PositionView(
                    pair=pair,
                    base_qty=values["base_qty"],
                    cost_basis=values["cost_basis"],
                )
                for pair, values in sorted(snapshot.positions.items())
            )
            orders_data = tuple(
                OrderView(
                    internal_order_id=order_id,
                    venue_order_id=values.get("venue_order_id"),
                    pair=values["pair"],
                    side=values["side"],
                    desired_qty=values["desired_qty"],
                    filled_qty=values["filled_qty"],
                    state=values["state"],
                )
                for order_id, values in sorted(snapshot.orders.items())[
                    orders_offset : orders_offset + orders_limit
                ]
            )
            unknown_orders = sum(
                values.get("state") == "UNKNOWN" for values in snapshot.orders.values()
            )
            return (
                PositionsView(evidence=evidence, data=positions_data),
                OrdersView(evidence=evidence, data=orders_data, total=len(snapshot.orders)),
                unknown_orders,
            )
        except Exception:
            evidence = self._evidence(
                status="UNAVAILABLE", source=source, reason="EXECUTION_AUTHORITY_UNAVAILABLE"
            )
            return (
                PositionsView(evidence=evidence),
                OrdersView(evidence=evidence),
                None,
            )

    @staticmethod
    def _is_non_production_namespace(namespace: str) -> bool:
        normalized = namespace.strip().lower().replace("_", "-")
        known = {"research", "shadow", "tournament", "portfolio-shadow", "prod-paper"}
        prefixes = ("research-", "shadow-", "tournament-", "portfolio-shadow-")
        return normalized in known or normalized.startswith(prefixes)

    def _execution_store_is_within_production_root(self) -> bool:
        db_path = getattr(self.execution_store, "db_path", None)
        if self.production_state_root is None or db_path is None:
            return False
        try:
            Path(db_path).resolve().relative_to(self.production_state_root)
            return True
        except (OSError, RuntimeError, ValueError):
            return False

    def _venue_portfolio(self, as_of: datetime) -> PortfolioView:
        """Read the Production account snapshot from its explicit read-only authority."""
        source = "production.venue_account"
        if self.venue_account_source is None:
            return PortfolioView(
                evidence=self._evidence(
                    status="UNAVAILABLE",
                    source=source,
                    reason="VENUE_ACCOUNT_PROVIDER_NOT_CONFIGURED",
                )
            )
        if getattr(self.venue_account_source, "authority", None) != "production.indodax.account":
            return PortfolioView(
                evidence=self._evidence(
                    status="UNAVAILABLE",
                    source=source,
                    reason="PRODUCTION_ACCOUNT_PROVIDER_REQUIRED",
                )
            )
        try:
            snapshot = self.venue_account_source.get_account_snapshot()
            if not isinstance(snapshot, VenueAccountSnapshot):
                raise ValueError("VENUE_ACCOUNT_SNAPSHOT_INVALID")
            if snapshot.server_time.tzinfo is None or snapshot.server_time.utcoffset() is None:
                raise ValueError("VENUE_ACCOUNT_TIMESTAMP_INVALID")
            source_time = snapshot.server_time.astimezone(UTC)
            balances_list: list[BalanceView] = []
            for currency, balance in sorted(snapshot.balances.items()):
                if currency.lower() != balance.currency.lower():
                    raise ValueError("VENUE_BALANCE_CURRENCY_MISMATCH")
                balances_list.append(
                    BalanceView(
                        currency=currency.lower(),
                        available=balance.available,
                        hold=balance.hold,
                        total=balance.total,
                    )
                )
            balances = tuple(balances_list)
            revision_source = {
                "server_time": source_time.isoformat(),
                "balances": [item.model_dump(mode="json") for item in balances],
            }
            revision = hashlib.sha256(
                json.dumps(revision_source, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            observed_at = self.clock()
            if observed_at.tzinfo is None or observed_at.utcoffset() is None:
                raise ValueError("UTC_TIMEZONE_AWARE_REQUIRED:portfolio_observation")
            observed_at = observed_at.astimezone(UTC)
            age = observed_at - source_time
            if age < timedelta(0):
                raise ValueError("VENUE_ACCOUNT_TIMESTAMP_IN_FUTURE")
            if age > self.max_account_snapshot_age:
                return PortfolioView(
                    evidence=self._evidence(
                        status="UNAVAILABLE",
                        source=source,
                        as_of=observed_at,
                        revision=revision,
                        source_updated_at=source_time,
                        freshness="STALE",
                        reason="VENUE_ACCOUNT_SNAPSHOT_STALE",
                    )
                )
            quote_currency = self.reconciliation_policy.quote_currency.lower()
            quote = next(
                (balance for balance in balances if balance.currency == quote_currency), None
            )
            return PortfolioView(
                evidence=self._evidence(
                    status="AVAILABLE",
                    source=source,
                    as_of=observed_at,
                    revision=revision,
                    source_updated_at=source_time,
                    freshness="FRESH",
                ),
                balances=balances,
                quote_available=quote.available if quote else None,
                quote_hold=quote.hold if quote else None,
                quote_currency=quote_currency if quote else None,
                balance_authority="AVAILABLE",
            )
        except Exception:
            return PortfolioView(
                evidence=self._evidence(
                    status="UNAVAILABLE",
                    source=source,
                    reason="VENUE_ACCOUNT_UNAVAILABLE",
                )
            )

    def _risk_view(self, as_of: datetime) -> RiskView:
        source = "production.risk_engine"
        if self.risk_engine is None:
            return RiskView(
                evidence=self._evidence(
                    status="UNAVAILABLE", source=source, reason="RISK_ENGINE_NOT_CONFIGURED"
                )
            )
        try:
            if not self.risk_engine.verify_risk_state_integrity():
                raise ValueError("RISK_STATE_UNVERIFIED")
            kill_switch_active = bool(self.risk_engine.is_kill_switch_active)
            state = "HALTED" if kill_switch_active else "UNKNOWN"
            return RiskView(
                evidence=self._evidence(
                    status="PARTIAL",
                    source=source,
                    as_of=as_of,
                    reason="RISK_LIMIT_SNAPSHOT_UNAVAILABLE",
                ),
                status=state,
                kill_switch_active=kill_switch_active,
            )
        except Exception:
            return RiskView(
                evidence=self._evidence(
                    status="UNAVAILABLE", source=source, reason="RISK_AUTHORITY_UNAVAILABLE"
                )
            )


__all__ = ["ProductionReadService"]
