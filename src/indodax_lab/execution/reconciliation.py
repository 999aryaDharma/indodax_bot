"""Deterministic exchange-versus-ledger reconciliation.

Reconciliation is deliberately side-effect free. A mismatch produces a blocking report;
it never edits ledger state, guesses missing fills, or auto-flattens positions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import AbstractSet, Sequence

from indodax_lab.backtest.ledger import ResearchLedger
from indodax_lab.execution.indodax_readonly import (
    VenueAccountSnapshot,
    VenueFill,
    VenueOrder,
)


class ReconciliationStatus(StrEnum):
    """Operational decision produced by reconciliation."""

    HEALTHY = "HEALTHY"
    HALT_NEW_ORDERS = "HALT_NEW_ORDERS"


@dataclass(frozen=True)
class ReconciliationPolicy:
    """Reviewed reconciliation tolerances and evidence requirements."""

    quote_currency: str = "idr"
    quote_balance_tolerance: Decimal = Decimal("0")
    base_quantity_tolerance: Decimal = Decimal("0")
    max_snapshot_age: timedelta = timedelta(seconds=30)
    require_order_match: bool = True
    require_recent_fill_match: bool = True

    def __post_init__(self) -> None:
        if not self.quote_currency or not self.quote_currency.isalnum():
            raise ValueError("INVALID_QUOTE_CURRENCY")
        if (
            not self.quote_balance_tolerance.is_finite()
            or self.quote_balance_tolerance < 0
        ):
            raise ValueError("INVALID_QUOTE_TOLERANCE")
        if (
            not self.base_quantity_tolerance.is_finite()
            or self.base_quantity_tolerance < 0
        ):
            raise ValueError("INVALID_BASE_TOLERANCE")
        if self.max_snapshot_age <= timedelta(0):
            raise ValueError("INVALID_MAX_SNAPSHOT_AGE")


@dataclass(frozen=True)
class ReconciliationIssue:
    """One explainable difference between internal and venue truth."""

    code: str
    detail: str
    blocking: bool = True


@dataclass(frozen=True)
class ReconciliationReport:
    """Immutable reconciliation result used by control/risk layers."""

    status: ReconciliationStatus
    evaluated_at: datetime
    issues: tuple[ReconciliationIssue, ...]

    @property
    def healthy(self) -> bool:
        return self.status == ReconciliationStatus.HEALTHY


class ReconciliationEngine:
    """Compare double-entry ledger state against private exchange evidence."""

    def __init__(self, policy: ReconciliationPolicy | None = None) -> None:
        self.policy = policy or ReconciliationPolicy()

    def reconcile(
        self,
        *,
        ledger: ResearchLedger,
        account: VenueAccountSnapshot,
        venue_open_orders: Sequence[VenueOrder] = (),
        venue_fills: Sequence[VenueFill] = (),
        expected_open_order_ids: AbstractSet[str] = frozenset(),
        expected_recent_fill_ids: AbstractSet[str] = frozenset(),
        tracked_pairs: Sequence[str] | None = None,
        evaluation_time: datetime,
    ) -> ReconciliationReport:
        if evaluation_time.tzinfo is None or evaluation_time.utcoffset() != timedelta(0):
            raise ValueError("UTC_TIMEZONE_AWARE_REQUIRED:evaluation_time")

        issues: list[ReconciliationIssue] = []
        if account.server_time.tzinfo is None or account.server_time.utcoffset() != timedelta(0):
            issues.append(
                ReconciliationIssue(
                    code="VENUE_TIMESTAMP_INVALID",
                    detail="venue account snapshot timestamp is not timezone-aware UTC",
                )
            )
            age = timedelta.max
        else:
            age = evaluation_time - account.server_time
        if age < -timedelta(seconds=1):
            issues.append(
                ReconciliationIssue(
                    code="VENUE_CLOCK_AHEAD",
                    detail=f"venue snapshot is {-age.total_seconds():.3f}s ahead of evaluation clock",
                )
            )
        elif age > self.policy.max_snapshot_age:
            issues.append(
                ReconciliationIssue(
                    code="STALE_ACCOUNT_SNAPSHOT",
                    detail=f"venue snapshot age {age.total_seconds():.3f}s exceeds policy",
                )
            )

        quote = self.policy.quote_currency.lower()
        venue_quote = account.balances.get(quote)
        if venue_quote is None:
            issues.append(
                ReconciliationIssue(
                    code="QUOTE_BALANCE_MISSING",
                    detail=f"venue did not return {quote} balance",
                )
            )
        else:
            quote_diff = abs(ledger.cash - venue_quote.total)
            if quote_diff > self.policy.quote_balance_tolerance:
                issues.append(
                    ReconciliationIssue(
                        code="QUOTE_BALANCE_MISMATCH",
                        detail=(
                            f"ledger={ledger.cash} venue={venue_quote.total} "
                            f"diff={quote_diff}"
                        ),
                    )
                )

        pairs = (
            tuple(tracked_pairs)
            if tracked_pairs is not None
            else tuple(sorted(ledger.positions))
        )
        seen_base: set[str] = set()
        for pair in pairs:
            parts = pair.lower().split("_")
            if len(parts) != 2:
                raise ValueError(f"INVALID_TRACKED_PAIR:{pair}")
            base, pair_quote = parts
            if pair_quote != quote:
                raise ValueError(f"UNSUPPORTED_RECONCILIATION_QUOTE:{pair}")
            if base in seen_base:
                raise ValueError(f"DUPLICATE_BASE_ASSET_TRACKING:{base}")
            seen_base.add(base)

            ledger_position = ledger.positions.get(pair)
            ledger_qty = (
                ledger_position.base_qty if ledger_position is not None else Decimal("0")
            )
            venue_balance = account.balances.get(base)
            venue_qty = venue_balance.total if venue_balance is not None else Decimal("0")
            diff = abs(ledger_qty - venue_qty)
            if diff > self.policy.base_quantity_tolerance:
                issues.append(
                    ReconciliationIssue(
                        code="ASSET_BALANCE_MISMATCH",
                        detail=(
                            f"pair={pair} ledger={ledger_qty} venue={venue_qty} diff={diff}"
                        ),
                    )
                )

        if self.policy.require_order_match:
            venue_ids = {order.order_id for order in venue_open_orders}
            missing_at_venue = set(expected_open_order_ids) - venue_ids
            unexpected_at_venue = venue_ids - set(expected_open_order_ids)
            for order_id in sorted(missing_at_venue):
                issues.append(
                    ReconciliationIssue(
                        code="INTERNAL_OPEN_ORDER_MISSING_AT_VENUE",
                        detail=f"order_id={order_id}",
                    )
                )
            for order_id in sorted(unexpected_at_venue):
                issues.append(
                    ReconciliationIssue(
                        code="UNEXPECTED_VENUE_OPEN_ORDER",
                        detail=f"order_id={order_id}",
                    )
                )

        if self.policy.require_recent_fill_match:
            ledger_fill_ids = set(ledger.to_dict()["processed_fill_ids"])
            venue_fill_ids = [fill.fill_id for fill in venue_fills]
            if len(set(venue_fill_ids)) != len(venue_fill_ids):
                issues.append(
                    ReconciliationIssue(
                        code="DUPLICATE_VENUE_FILL_ID",
                        detail="venue fill window contains duplicate trade IDs",
                    )
                )
            venue_fill_id_set = set(venue_fill_ids)
            for fill_id in sorted(venue_fill_id_set - ledger_fill_ids):
                issues.append(
                    ReconciliationIssue(
                        code="VENUE_FILL_MISSING_FROM_LEDGER",
                        detail=f"fill_id={fill_id}",
                    )
                )
            for fill_id in sorted(set(expected_recent_fill_ids) - venue_fill_id_set):
                issues.append(
                    ReconciliationIssue(
                        code="LEDGER_FILL_MISSING_AT_VENUE",
                        detail=f"fill_id={fill_id}",
                    )
                )

        status = (
            ReconciliationStatus.HALT_NEW_ORDERS
            if any(issue.blocking for issue in issues)
            else ReconciliationStatus.HEALTHY
        )
        return ReconciliationReport(
            status=status,
            evaluated_at=evaluation_time,
            issues=tuple(issues),
        )
