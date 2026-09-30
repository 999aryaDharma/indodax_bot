"""Reviewed account portfolio adoption and ownership governance (PM-07).

Guarantees:
- PM-07-AC0: Stale snapshot or unresolved existing order prevents adoption.
- PM-07-AC1: Unknown cost basis stays unknown while post-adoption baseline is separately attributed.
- PM-07-AC2: Unadopted assets affect exposure but cannot be sold by a strategy.
- PM-07-AC3: Unexplained external account change blocks new entry until reviewed reconciliation.
- PM-07-AC4: Duplicate adoption and restart have one position ownership effect.
- PM-07-AC5: Verified deposits do not appear as trading profit.
"""

from __future__ import annotations

import contextlib
import json
import logging
import sqlite3
import threading
import uuid
from collections.abc import Generator, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from indodax_lab.backtest.ledger import ResearchLedger
from indodax_lab.contracts.identity import ArtifactRef, _ensure_utc
from indodax_lab.contracts.workbench import MetricValidity, MetricValue
from indodax_lab.execution.indodax_readonly import (
    VenueAccountSnapshot,
    VenueOrder,
)
from indodax_lab.execution.reconciliation import (
    ReconciliationReport,
)

logger = logging.getLogger("indodax_lab.portfolio.adoption")


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class AdoptionError(ValueError):
    """Base error for portfolio adoption violations."""


class StaleSnapshotError(AdoptionError):
    """Raised when an account snapshot exceeds max age policy or clock is skewed."""


class UnresolvedOrdersError(AdoptionError):
    """Raised when unresolved venue orders exist before adoption."""


class UnadoptedAssetError(AdoptionError):
    """Raised when a strategy attempts to sell an unadopted asset."""


class CostBasisValidityError(AdoptionError):
    """Raised when cost basis validity invariants are violated."""


class RevisionMismatchError(AdoptionError):
    """Raised when expected revision does not match the active store revision."""


# ---------------------------------------------------------------------------
# Enums and Data Models
# ---------------------------------------------------------------------------


class CostBasisValidity(StrEnum):
    """Validity state of an asset's cost basis."""

    KNOWN = "KNOWN"
    UNKNOWN = "UNKNOWN"


class AssetAssignment(BaseModel):
    """Strategy assignment for an existing account asset."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pair: str
    asset: str
    strategy_id: str
    quantity: Decimal
    exit_policy_ref: str | None = None
    cost_basis: Decimal | None = None
    cost_basis_validity: CostBasisValidity = CostBasisValidity.UNKNOWN
    cost_basis_evidence: str | None = None

    @field_validator("pair", "asset", "strategy_id", mode="before")
    @classmethod
    def normalize_identifiers(cls, value: Any, info: Any) -> str:
        s = str(value).strip().lower()
        if not s:
            raise ValueError(f"IDENTIFIER_REQUIRED:{info.field_name}")
        return s

    @field_validator("quantity", mode="before")
    @classmethod
    def validate_positive_quantity(cls, value: Any) -> Decimal:
        dec = Decimal(str(value))
        if not dec.is_finite() or dec <= 0:
            raise ValueError("POSITIVE_FINITE_QUANTITY_REQUIRED")
        return dec

    @model_validator(mode="after")
    def validate_cost_basis_invariants(self) -> AssetAssignment:
        if self.cost_basis_validity == CostBasisValidity.UNKNOWN:
            if self.cost_basis is not None:
                raise CostBasisValidityError(
                    "UNKNOWN_COST_BASIS_MUST_BE_NONE: "
                    "cost basis cannot be set when validity is UNKNOWN"
                )
            if self.cost_basis_evidence is not None:
                raise CostBasisValidityError(
                    "UNKNOWN_COST_BASIS_CANNOT_HAVE_EVIDENCE: "
                    "evidence must be None when validity is UNKNOWN"
                )
        elif self.cost_basis_validity == CostBasisValidity.KNOWN:
            if self.cost_basis is None:
                raise CostBasisValidityError(
                    "KNOWN_COST_BASIS_REQUIRES_VALUE_AND_EVIDENCE: cost_basis is None"
                )
            if not self.cost_basis.is_finite() or self.cost_basis <= 0:
                raise CostBasisValidityError(
                    "KNOWN_COST_BASIS_REQUIRES_VALUE_AND_EVIDENCE: "
                    "cost_basis must be positive finite"
                )
            if not self.cost_basis_evidence or not self.cost_basis_evidence.strip():
                raise CostBasisValidityError(
                    "KNOWN_COST_BASIS_REQUIRES_VALUE_AND_EVIDENCE: cost_basis_evidence required"
                )
        return self


class AdoptedAsset(BaseModel):
    """Immutable record of an adopted asset bound to an active strategy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pair: str
    asset: str
    strategy_id: str
    quantity: Decimal
    exit_policy_ref: str | None = None
    cost_basis: Decimal | None = None
    cost_basis_validity: CostBasisValidity = CostBasisValidity.UNKNOWN
    cost_basis_evidence: str | None = None
    adoption_baseline_price: Decimal
    adoption_baseline_notional: Decimal


class UnadoptedAsset(BaseModel):
    """Asset present in the account that was not adopted by any strategy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    asset: str
    pair: str
    total_qty: Decimal
    mark_price: Decimal | None = None
    exposure_notional: Decimal = Decimal("0")
    reason: str = "UNADOPTED_ACCOUNT_ASSET"


class AdoptionProposal(BaseModel):
    """Proposal generated for operator review prior to adoption approval."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    proposal_id: str
    snapshot_ref: str
    snapshot_server_time: datetime
    snapshot_revision: int
    assignments: tuple[AssetAssignment, ...]
    adopted_assets: tuple[AdoptedAsset, ...]
    unadopted_assets: tuple[UnadoptedAsset, ...]
    total_account_exposure: Decimal
    cost_basis_validity: dict[str, CostBasisValidity]
    reconciliation_report: ReconciliationReport | None = None
    reconciliation_evidence: dict[str, Any] | None = None
    created_at_utc: datetime
    status: str = "PROPOSED"
    rejection_reason: str | None = None


class AdoptionRecord(BaseModel):
    """Durable record of reviewed and approved portfolio adoption."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    adoption_id: str
    proposal_id: str
    snapshot_ref: str
    snapshot_revision: int
    release_ref: str | None = None
    actor: str
    reason: str
    request_id: str
    approved_at_utc: datetime
    adopted_assets: tuple[AdoptedAsset, ...] = ()
    unadopted_assets: tuple[UnadoptedAsset, ...] = ()
    cost_basis_validity: dict[str, CostBasisValidity] = Field(default_factory=dict)
    reconciliation_evidence: dict[str, Any] | None = None
    total_account_exposure: Decimal = Decimal("0")
    status: str = "APPROVED"
    effective_revision: int = 0


class VerifiedDepositRecord(BaseModel):
    """Audited external cash deposit attribution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    deposit_id: str
    amount: Decimal
    currency: str = "IDR"
    evidence_ref: str
    actor: str
    reason: str
    timestamp: datetime
    applied_revision: int


class ReviewedReconciliationRecord(BaseModel):
    """Explicit operator review and acknowledgement of reconciliation discrepancy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    reconciliation_id: str
    actor: str
    reason: str
    timestamp: datetime
    issues_acknowledged: tuple[str, ...]
    resolved: bool = True


class PortfolioExposureReport(BaseModel):
    """Total account exposure split between adopted and unadopted assets."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    adopted_exposure: Decimal
    unadopted_exposure: Decimal
    total_account_exposure: Decimal
    cash_balance: Decimal
    total_equity: Decimal
    has_missing_marks: bool = False


class AdoptedAssetPerformance(BaseModel):
    """Attribution separating unavailable lifetime PnL from valid post-adoption PnL."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pair: str
    current_price: Decimal
    adoption_baseline_price: Decimal
    post_adoption_pnl: MetricValue
    post_adoption_return: MetricValue
    lifetime_pnl: MetricValue


# ---------------------------------------------------------------------------
# Durable SQLite Store
# ---------------------------------------------------------------------------


class AdoptionStore:
    """Durable SQLite storage for portfolio adoption, ownership, and cash-flow baselines."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    @contextlib.contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=FULL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS adoption_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS adoption_proposals (
                    proposal_id TEXT PRIMARY KEY,
                    snapshot_ref TEXT NOT NULL,
                    snapshot_revision INTEGER NOT NULL,
                    proposal_data_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS adoption_records (
                    adoption_id TEXT PRIMARY KEY,
                    proposal_id TEXT NOT NULL UNIQUE,
                    request_id TEXT NOT NULL UNIQUE,
                    actor TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    record_data_json TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    approved_at_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS pair_ownership (
                    pair TEXT PRIMARY KEY,
                    strategy_id TEXT NOT NULL,
                    adoption_id TEXT NOT NULL,
                    quantity TEXT NOT NULL,
                    cost_basis_validity TEXT NOT NULL,
                    cost_basis TEXT,
                    cost_basis_evidence TEXT,
                    adoption_baseline_price TEXT NOT NULL,
                    assigned_at_utc TEXT NOT NULL,
                    FOREIGN KEY(adoption_id) REFERENCES adoption_records(adoption_id)
                );

                CREATE TABLE IF NOT EXISTS verified_deposits (
                    deposit_id TEXT PRIMARY KEY,
                    amount TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    evidence_ref TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    timestamp_utc TEXT NOT NULL,
                    applied_revision INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS reviewed_reconciliations (
                    reconciliation_id TEXT PRIMARY KEY,
                    actor TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    issues_json TEXT NOT NULL,
                    timestamp_utc TEXT NOT NULL,
                    resolved INTEGER NOT NULL DEFAULT 1
                );
                """
            )
            # Initialize current_revision if missing
            row = conn.execute(
                "SELECT value FROM adoption_metadata WHERE key = 'current_revision'"
            ).fetchone()
            if not row:
                now_str = datetime.now(UTC).isoformat()
                conn.execute(
                    "INSERT INTO adoption_metadata (key, value, updated_at_utc) "
                    "VALUES ('current_revision', '0', ?)",
                    (now_str,),
                )

    @property
    def current_revision(self) -> int:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM adoption_metadata WHERE key = 'current_revision'"
            ).fetchone()
            return int(row["value"]) if row else 0

    def _increment_revision_locked(self, conn: sqlite3.Connection) -> int:
        row = conn.execute(
            "SELECT value FROM adoption_metadata WHERE key = 'current_revision'"
        ).fetchone()
        rev = int(row["value"]) if row else 0
        next_rev = rev + 1
        now_str = datetime.now(UTC).isoformat()
        conn.execute(
            "UPDATE adoption_metadata SET value = ?, updated_at_utc = ? "
            "WHERE key = 'current_revision'",
            (str(next_rev), now_str),
        )
        return next_rev

    def save_proposal(self, proposal: AdoptionProposal) -> None:
        with self._lock, self._connect() as conn:
            data_json = json.dumps(proposal.model_dump(mode="json"), sort_keys=True)
            conn.execute(
                """
                INSERT OR REPLACE INTO adoption_proposals (
                    proposal_id, snapshot_ref, snapshot_revision,
                    proposal_data_json, status, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    proposal.proposal_id,
                    proposal.snapshot_ref,
                    proposal.snapshot_revision,
                    data_json,
                    proposal.status,
                    proposal.created_at_utc.isoformat(),
                ),
            )

    def get_proposal(self, proposal_id: str) -> AdoptionProposal | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT proposal_data_json FROM adoption_proposals WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
            if not row:
                return None
            data = json.loads(row["proposal_data_json"])
            return AdoptionProposal.model_validate(data)

    def get_record_by_request_id(self, request_id: str) -> AdoptionRecord | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT record_data_json FROM adoption_records WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            if not row:
                return None
            data = json.loads(row["record_data_json"])
            return AdoptionRecord.model_validate(data)

    def get_record_by_proposal_id(self, proposal_id: str) -> AdoptionRecord | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT record_data_json FROM adoption_records WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
            if not row:
                return None
            data = json.loads(row["record_data_json"])
            return AdoptionRecord.model_validate(data)

    def save_adoption_record(
        self,
        record: AdoptionRecord,
        expected_revision: int,
    ) -> AdoptionRecord:
        with self._lock, self._connect() as conn:
            # Check idempotency first by request_id
            existing = self.get_record_by_request_id(record.request_id)
            if existing is not None:
                return existing

            # Check revision fencing
            row = conn.execute(
                "SELECT value FROM adoption_metadata WHERE key = 'current_revision'"
            ).fetchone()
            cur_rev = int(row["value"]) if row else 0
            if cur_rev != expected_revision:
                raise RevisionMismatchError(
                    f"REVISION_MISMATCH: expected {expected_revision}, current {cur_rev}"
                )

            next_rev = self._increment_revision_locked(conn)
            effective_record = record.model_copy(update={"effective_revision": next_rev})
            data_json = json.dumps(effective_record.model_dump(mode="json"), sort_keys=True)

            conn.execute(
                """
                INSERT INTO adoption_records (
                    adoption_id, proposal_id, request_id, actor, reason,
                    record_data_json, revision, approved_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    effective_record.adoption_id,
                    effective_record.proposal_id,
                    effective_record.request_id,
                    effective_record.actor,
                    effective_record.reason,
                    data_json,
                    next_rev,
                    effective_record.approved_at_utc.isoformat(),
                ),
            )

            # Persist pair ownership
            for asset in effective_record.adopted_assets:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO pair_ownership (
                        pair, strategy_id, adoption_id, quantity, cost_basis_validity,
                        cost_basis, cost_basis_evidence, adoption_baseline_price, assigned_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        asset.pair.lower(),
                        asset.strategy_id,
                        effective_record.adoption_id,
                        str(asset.quantity),
                        asset.cost_basis_validity.value,
                        str(asset.cost_basis) if asset.cost_basis is not None else None,
                        asset.cost_basis_evidence,
                        str(asset.adoption_baseline_price),
                        effective_record.approved_at_utc.isoformat(),
                    ),
                )

            # Update proposal status
            conn.execute(
                "UPDATE adoption_proposals SET status = 'APPROVED' WHERE proposal_id = ?",
                (effective_record.proposal_id,),
            )
            return effective_record

    def get_pair_owner(self, pair: str) -> str | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT strategy_id FROM pair_ownership WHERE pair = ?",
                (pair.lower(),),
            ).fetchone()
            return row["strategy_id"] if row else None

    def get_adopted_quantity(self, pair: str) -> Decimal:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT quantity FROM pair_ownership WHERE pair = ?",
                (pair.lower(),),
            ).fetchone()
            return Decimal(row["quantity"]) if row else Decimal("0")

    def get_adopted_asset(self, pair: str) -> AdoptedAsset | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT pair, strategy_id, quantity, cost_basis_validity,
                       cost_basis, cost_basis_evidence, adoption_baseline_price
                FROM pair_ownership WHERE pair = ?
                """,
                (pair.lower(),),
            ).fetchone()
            if not row:
                return None
            qty = Decimal(row["quantity"])
            baseline_p = Decimal(row["adoption_baseline_price"])
            cb = Decimal(row["cost_basis"]) if row["cost_basis"] is not None else None
            asset_code = row["pair"].split("_")[0]
            return AdoptedAsset(
                pair=row["pair"],
                asset=asset_code,
                strategy_id=row["strategy_id"],
                quantity=qty,
                cost_basis=cb,
                cost_basis_validity=CostBasisValidity(row["cost_basis_validity"]),
                cost_basis_evidence=row["cost_basis_evidence"],
                adoption_baseline_price=baseline_p,
                adoption_baseline_notional=qty * baseline_p,
            )

    def record_verified_deposit(
        self,
        deposit_record: VerifiedDepositRecord,
    ) -> VerifiedDepositRecord:
        with self._lock, self._connect() as conn:
            # Idempotency check by deposit_id
            row = conn.execute(
                "SELECT deposit_id FROM verified_deposits WHERE deposit_id = ?",
                (deposit_record.deposit_id,),
            ).fetchone()
            if row:
                return deposit_record

            conn.execute(
                """
                INSERT INTO verified_deposits (
                    deposit_id, amount, currency, evidence_ref, actor,
                    reason, timestamp_utc, applied_revision
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    deposit_record.deposit_id,
                    str(deposit_record.amount),
                    deposit_record.currency,
                    deposit_record.evidence_ref,
                    deposit_record.actor,
                    deposit_record.reason,
                    deposit_record.timestamp.isoformat(),
                    deposit_record.applied_revision,
                ),
            )
            return deposit_record

    def get_total_verified_deposits(self) -> Decimal:
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT amount FROM verified_deposits").fetchall()
            return sum((Decimal(r["amount"]) for r in rows), Decimal("0"))

    def get_cash_flow_adjusted_baseline(self, initial_capital: Decimal) -> Decimal:
        """Calculate adjusted equity baseline: initial capital + verified deposits."""
        return initial_capital + self.get_total_verified_deposits()

    def record_reviewed_reconciliation(
        self,
        reviewed_record: ReviewedReconciliationRecord,
    ) -> ReviewedReconciliationRecord:
        with self._lock, self._connect() as conn:
            issues_json = json.dumps(list(reviewed_record.issues_acknowledged))
            conn.execute(
                """
                INSERT OR REPLACE INTO reviewed_reconciliations (
                    reconciliation_id, actor, reason, issues_json, timestamp_utc, resolved
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    reviewed_record.reconciliation_id,
                    reviewed_record.actor,
                    reviewed_record.reason,
                    issues_json,
                    reviewed_record.timestamp.isoformat(),
                    1 if reviewed_record.resolved else 0,
                ),
            )
            return reviewed_record

    def is_issue_reviewed(self, issue_code: str) -> bool:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT issues_json FROM reviewed_reconciliations WHERE resolved = 1"
            ).fetchall()
            for r in rows:
                issues: list[str] = json.loads(r["issues_json"])
                if issue_code in issues:
                    return True
            return False

    def evaluate_adopted_asset_performance(
        self,
        pair: str,
        current_price: Decimal,
    ) -> AdoptedAssetPerformance:
        asset = self.get_adopted_asset(pair)
        if asset is None:
            raise UnadoptedAssetError(f"PAIR_NOT_ADOPTED:{pair}")

        current_val = asset.quantity * current_price
        baseline_notional = asset.adoption_baseline_notional

        # Post-adoption PnL: separately attributed from adoption mark baseline
        post_adoption_diff = current_val - baseline_notional
        post_adoption_pnl = MetricValue(
            value=post_adoption_diff,
            unit="IDR",
            validity=MetricValidity.VALID,
        )
        post_adoption_ret = (
            (current_price - asset.adoption_baseline_price) / asset.adoption_baseline_price
            if asset.adoption_baseline_price > 0
            else Decimal("0")
        )
        post_adoption_return = MetricValue(
            value=post_adoption_ret,
            unit="ratio",
            validity=MetricValidity.VALID,
        )

        # Lifetime PnL: remains unavailable if cost basis is unknown
        if asset.cost_basis_validity == CostBasisValidity.UNKNOWN:
            lifetime_pnl = MetricValue(
                value=None,
                unit="IDR",
                validity=MetricValidity.UNAVAILABLE,
                reason="UNKNOWN_HISTORICAL_COST_BASIS",
            )
        else:
            assert asset.cost_basis is not None
            lifetime_diff = current_val - asset.cost_basis
            lifetime_pnl = MetricValue(
                value=lifetime_diff,
                unit="IDR",
                validity=MetricValidity.VALID,
            )

        return AdoptedAssetPerformance(
            pair=pair,
            current_price=current_price,
            adoption_baseline_price=asset.adoption_baseline_price,
            post_adoption_pnl=post_adoption_pnl,
            post_adoption_return=post_adoption_return,
            lifetime_pnl=lifetime_pnl,
        )


# ---------------------------------------------------------------------------
# Core Operations
# ---------------------------------------------------------------------------


def propose_adoption(
    snapshot_ref: ArtifactRef | str | VenueAccountSnapshot,
    assignments: Sequence[AssetAssignment | Mapping[str, Any]],
    *,
    snapshot: VenueAccountSnapshot | None = None,
    venue_open_orders: Sequence[VenueOrder] = (),
    mark_prices: Mapping[str, Decimal] | None = None,
    evaluation_time: datetime | None = None,
    max_snapshot_age: timedelta = timedelta(seconds=30),
    store: AdoptionStore | None = None,
    current_revision: int = 0,
) -> AdoptionProposal:
    """Propose reviewed portfolio adoption bound to an exact account snapshot."""
    # 1. Resolve snapshot
    if snapshot is None:
        if isinstance(snapshot_ref, VenueAccountSnapshot):
            snapshot = snapshot_ref
            snapshot_ref_str = f"snapshot-{int(snapshot.server_time.timestamp())}"
        else:
            raise AdoptionError("VENUE_ACCOUNT_SNAPSHOT_REQUIRED")
    else:
        snapshot_ref_str = snapshot_ref.id if hasattr(snapshot_ref, "id") else str(snapshot_ref)

    eval_time = evaluation_time or datetime.now(UTC)
    _ensure_utc(eval_time, "evaluation_time")

    # 2. PM-07-AC0: Check snapshot freshness
    if snapshot.server_time.tzinfo is None or snapshot.server_time.utcoffset() != timedelta(0):
        raise StaleSnapshotError("VENUE_TIMESTAMP_INVALID: snapshot must be timezone-aware UTC")

    age = eval_time - snapshot.server_time
    if age < -timedelta(seconds=1):
        raise StaleSnapshotError(
            f"VENUE_CLOCK_AHEAD: snapshot is {-age.total_seconds():.3f}s ahead of evaluation clock"
        )
    if age > max_snapshot_age:
        raise StaleSnapshotError(
            f"STALE_ACCOUNT_SNAPSHOT: snapshot age {age.total_seconds():.3f}s "
            f"exceeds policy {max_snapshot_age.total_seconds():.3f}s"
        )

    # 3. PM-07-AC0: Check for unresolved existing open orders
    unresolved_orders = [
        o for o in venue_open_orders if o.status in ("OPEN", "PENDING", "PARTIALLY_FILLED")
    ]
    if unresolved_orders:
        raise UnresolvedOrdersError(
            f"UNRESOLVED_EXISTING_ORDERS: found {len(unresolved_orders)} open orders "
            "at venue, adoption requires resolved orders"
        )

    # 4. Normalize assignments and check uniqueness
    parsed_assignments: list[AssetAssignment] = []
    seen_pairs: set[str] = set()
    for item in assignments:
        assignment = (
            item if isinstance(item, AssetAssignment) else AssetAssignment.model_validate(item)
        )
        if assignment.pair in seen_pairs:
            raise AdoptionError(
                f"DUPLICATE_PAIR_ASSIGNMENT: pair {assignment.pair} assigned multiple times"
            )
        seen_pairs.add(assignment.pair)
        parsed_assignments.append(assignment)

    # 5. Check balances and construct AdoptedAsset records
    adopted_assets: list[AdoptedAsset] = []
    cost_basis_validity_map: dict[str, CostBasisValidity] = {}
    adopted_currencies: dict[str, Decimal] = {}

    marks = dict(mark_prices or {})

    for asgn in parsed_assignments:
        bal = snapshot.balances.get(asgn.asset)
        if bal is None or bal.available < asgn.quantity:
            avail = bal.available if bal else Decimal("0")
            raise AdoptionError(
                f"INSUFFICIENT_AVAILABLE_BALANCE: asset {asgn.asset} "
                f"available {avail} < desired {asgn.quantity}"
            )

        # Mark price required for adoption baseline
        mark = marks.get(asgn.pair) or marks.get(asgn.asset)
        if mark is None or mark <= 0:
            raise AdoptionError(f"MISSING_MARK_PRICE:{asgn.pair}")

        baseline_notional = asgn.quantity * mark
        adopted_assets.append(
            AdoptedAsset(
                pair=asgn.pair,
                asset=asgn.asset,
                strategy_id=asgn.strategy_id,
                quantity=asgn.quantity,
                exit_policy_ref=asgn.exit_policy_ref,
                cost_basis=asgn.cost_basis,
                cost_basis_validity=asgn.cost_basis_validity,
                cost_basis_evidence=asgn.cost_basis_evidence,
                adoption_baseline_price=mark,
                adoption_baseline_notional=baseline_notional,
            )
        )
        cost_basis_validity_map[asgn.pair] = asgn.cost_basis_validity
        adopted_currencies[asgn.asset] = (
            adopted_currencies.get(asgn.asset, Decimal("0")) + asgn.quantity
        )

    # 6. PM-07-AC2: Inventory unadopted assets
    unadopted_assets: list[UnadoptedAsset] = []
    for cur, bal in snapshot.balances.items():
        if cur.lower() in ("idr", "usd", "usdt") and bal.total > 0:
            # Quote currency cash is handled separately in portfolio equity
            continue
        adopted_qty = adopted_currencies.get(cur.lower(), Decimal("0"))
        remaining_qty = bal.total - adopted_qty
        if remaining_qty > 0:
            pair = f"{cur.lower()}_idr"
            mark = marks.get(pair) or marks.get(cur.lower())
            notional = (remaining_qty * mark) if (mark is not None and mark > 0) else Decimal("0")
            unadopted_assets.append(
                UnadoptedAsset(
                    asset=cur.lower(),
                    pair=pair,
                    total_qty=remaining_qty,
                    mark_price=mark,
                    exposure_notional=notional,
                    reason="UNADOPTED_ACCOUNT_ASSET",
                )
            )

    # 7. Total exposure includes adopted + unadopted assets
    total_adopted_exposure = sum(
        (a.adoption_baseline_notional for a in adopted_assets), Decimal("0")
    )
    total_unadopted_exposure = sum((u.exposure_notional for u in unadopted_assets), Decimal("0"))
    total_exposure = total_adopted_exposure + total_unadopted_exposure

    proposal_id = f"prop-adopt-{uuid.uuid4().hex[:12]}"
    proposal = AdoptionProposal(
        proposal_id=proposal_id,
        snapshot_ref=snapshot_ref_str,
        snapshot_server_time=snapshot.server_time,
        snapshot_revision=current_revision,
        assignments=tuple(parsed_assignments),
        adopted_assets=tuple(adopted_assets),
        unadopted_assets=tuple(unadopted_assets),
        total_account_exposure=total_exposure,
        cost_basis_validity=cost_basis_validity_map,
        created_at_utc=eval_time,
        status="PROPOSED",
    )

    if store is not None:
        store.save_proposal(proposal)

    return proposal


def approve_adoption(
    proposal_id: str,
    expected_revision: int,
    actor: str,
    reason: str,
    request_id: str,
    *,
    store: AdoptionStore,
    release_ref: str | None = None,
    ledger: ResearchLedger | None = None,
    evaluation_time: datetime | None = None,
) -> AdoptionRecord:
    """Approve a reviewed adoption proposal and commit durable position ownership."""
    if not actor or not actor.strip():
        raise AdoptionError("ACTOR_REQUIRED")
    if not reason or not reason.strip():
        raise AdoptionError("REASON_REQUIRED")
    if not request_id or not request_id.strip():
        raise AdoptionError("REQUEST_ID_REQUIRED")

    # 1. PM-07-AC4: Check idempotency by request_id
    existing_by_req = store.get_record_by_request_id(request_id)
    if existing_by_req is not None:
        return existing_by_req

    # Check idempotency by proposal_id
    existing_by_prop = store.get_record_by_proposal_id(proposal_id)
    if existing_by_prop is not None:
        return existing_by_prop

    # 2. Load proposal
    proposal = store.get_proposal(proposal_id)
    if proposal is None:
        raise AdoptionError(f"PROPOSAL_NOT_FOUND:{proposal_id}")
    if proposal.status == "REJECTED":
        raise AdoptionError("CANNOT_APPROVE_REJECTED_PROPOSAL")

    eval_time = evaluation_time or datetime.now(UTC)
    _ensure_utc(eval_time, "evaluation_time")

    adoption_id = f"adopt-{uuid.uuid4().hex[:12]}"
    record = AdoptionRecord(
        adoption_id=adoption_id,
        proposal_id=proposal_id,
        snapshot_ref=proposal.snapshot_ref,
        snapshot_revision=proposal.snapshot_revision,
        release_ref=release_ref,
        actor=actor.strip(),
        reason=reason.strip(),
        request_id=request_id.strip(),
        approved_at_utc=eval_time,
        adopted_assets=proposal.adopted_assets,
        unadopted_assets=proposal.unadopted_assets,
        cost_basis_validity=proposal.cost_basis_validity,
        reconciliation_evidence=proposal.reconciliation_evidence,
        total_account_exposure=proposal.total_account_exposure,
        status="APPROVED",
        effective_revision=expected_revision + 1,
    )

    committed = store.save_adoption_record(record, expected_revision=expected_revision)
    return committed


def validate_strategy_sell(
    strategy_id: str,
    pair: str,
    qty: Decimal,
    *,
    store: AdoptionStore,
) -> None:
    """Validate that an asset can be sold by a strategy (PM-07-AC2)."""
    norm_pair = pair.lower()
    owner = store.get_pair_owner(norm_pair)
    if owner != strategy_id:
        raise UnadoptedAssetError(
            f"UNADOPTED_ASSET_CANNOT_BE_SOLD: pair {norm_pair} "
            f"is not adopted by strategy {strategy_id}"
        )
    adopted_qty = store.get_adopted_quantity(norm_pair)
    if qty > adopted_qty:
        raise UnadoptedAssetError(
            f"SELL_QUANTITY_EXCEEDS_ADOPTED: requested {qty} exceeds adopted {adopted_qty}"
        )


def can_strategy_sell(
    strategy_id: str,
    pair: str,
    *,
    store: AdoptionStore,
) -> bool:
    """Check if an asset is adopted and sellable by a strategy."""
    norm_pair = pair.lower()
    owner = store.get_pair_owner(norm_pair)
    return owner == strategy_id


def is_new_entry_allowed(
    *,
    reconciliation_report: ReconciliationReport,
    store: AdoptionStore,
) -> bool:
    """Check if new position entry is allowed under reconciliation governance (PM-07-AC3)."""
    if reconciliation_report.healthy:
        return True

    # If there are blocking issues, each must be explicitly reviewed and acknowledged
    blocking_issues = [issue for issue in reconciliation_report.issues if issue.blocking]
    if not blocking_issues:
        return True

    for issue in blocking_issues:
        if not store.is_issue_reviewed(issue.code):
            return False

    return True


def review_reconciliation(
    report: ReconciliationReport,
    actor: str,
    reason: str,
    *,
    store: AdoptionStore,
    timestamp: datetime | None = None,
) -> ReviewedReconciliationRecord:
    """Review and acknowledge reconciliation discrepancy to clear entry block (PM-07-AC3)."""
    if not actor or not actor.strip():
        raise AdoptionError("ACTOR_REQUIRED")
    if not reason or not reason.strip():
        raise AdoptionError("REASON_REQUIRED")

    ts = timestamp or datetime.now(UTC)
    _ensure_utc(ts, "timestamp")

    issue_codes = tuple(sorted({issue.code for issue in report.issues if issue.blocking}))
    rec_id = f"rev-rec-{uuid.uuid4().hex[:12]}"
    record = ReviewedReconciliationRecord(
        reconciliation_id=rec_id,
        actor=actor.strip(),
        reason=reason.strip(),
        timestamp=ts,
        issues_acknowledged=issue_codes,
        resolved=True,
    )
    return store.record_reviewed_reconciliation(record)


def compute_portfolio_exposure(
    *,
    record: AdoptionRecord,
    mark_prices: Mapping[str, Decimal],
    cash_balance: Decimal,
) -> PortfolioExposureReport:
    """Compute total account exposure, verifying unadopted assets affect exposure (PM-07-AC2)."""
    adopted_exp = Decimal("0")
    for asset in record.adopted_assets:
        mark = mark_prices.get(asset.pair) or mark_prices.get(asset.asset)
        if mark is None or mark <= 0:
            raise AdoptionError(f"MISSING_MARK_PRICE:{asset.pair}")
        adopted_exp += asset.quantity * mark

    unadopted_exp = Decimal("0")
    has_missing_marks = False
    for asset in record.unadopted_assets:
        mark = mark_prices.get(asset.pair) or mark_prices.get(asset.asset)
        if mark is None or mark <= 0:
            has_missing_marks = True
        else:
            unadopted_exp += asset.total_qty * mark

    total_exp = adopted_exp + unadopted_exp
    total_eq = cash_balance + total_exp
    return PortfolioExposureReport(
        adopted_exposure=adopted_exp,
        unadopted_exposure=unadopted_exp,
        total_account_exposure=total_exp,
        cash_balance=cash_balance,
        total_equity=total_eq,
        has_missing_marks=has_missing_marks,
    )


def record_verified_deposit(
    amount: Decimal,
    currency: str,
    evidence_ref: str,
    actor: str,
    reason: str,
    *,
    store: AdoptionStore,
    ledger: ResearchLedger | None = None,
    timestamp: datetime | None = None,
) -> VerifiedDepositRecord:
    """Record a verified external cash deposit without generating trading profit (PM-07-AC5)."""
    amount = Decimal(str(amount))
    if not amount.is_finite() or amount <= 0:
        raise AdoptionError("INVALID_DEPOSIT_AMOUNT")
    if not actor or not actor.strip():
        raise AdoptionError("ACTOR_REQUIRED")
    if not evidence_ref or not evidence_ref.strip():
        raise AdoptionError("EVIDENCE_REF_REQUIRED")

    ts = timestamp or datetime.now(UTC)
    _ensure_utc(ts, "timestamp")

    dep_id = f"dep-{uuid.uuid4().hex[:12]}"
    record = VerifiedDepositRecord(
        deposit_id=dep_id,
        amount=amount,
        currency=currency.upper(),
        evidence_ref=evidence_ref.strip(),
        actor=actor.strip(),
        reason=reason.strip(),
        timestamp=ts,
        applied_revision=store.current_revision,
    )
    store.record_verified_deposit(record)

    if ledger is not None:
        ledger.deposit(amount=amount, timestamp=ts, deposit_id=f"tx-{dep_id}")

    return record


class PortfolioAdoptionService:
    """Unified service coordinating account portfolio adoption and reconciliation."""

    def __init__(self, store: AdoptionStore) -> None:
        self.store = store

    def propose(
        self,
        snapshot_ref: ArtifactRef | str | VenueAccountSnapshot,
        assignments: Sequence[AssetAssignment | Mapping[str, Any]],
        **kwargs: Any,
    ) -> AdoptionProposal:
        return propose_adoption(snapshot_ref, assignments, store=self.store, **kwargs)

    def approve(
        self,
        proposal_id: str,
        expected_revision: int,
        actor: str,
        reason: str,
        request_id: str,
        **kwargs: Any,
    ) -> AdoptionRecord:
        return approve_adoption(
            proposal_id=proposal_id,
            expected_revision=expected_revision,
            actor=actor,
            reason=reason,
            request_id=request_id,
            store=self.store,
            **kwargs,
        )
