"""Tournament cohorts leaderboard and qualification service (RW5-02).

Contract:
    TournamentService.create(cohort_manifest) -> CohortRecord
    TournamentService.leaderboard(cohort_id) -> Leaderboard
    TournamentService.compare(agent_ids) -> ComparisonReport
    TournamentService.qualify(agent_id, policy_ref=None) -> QualificationDecision

Invariants (CONTRACTS.md & BOT-TRADE-PROGRAM.md):
- Enforce frozen 90-day AND 100-closed-forward-trade gate for qualification (RW5-02-AC0).
- Rank is distinct from qualification: Rank 1 with unresolved incidents is unqualified (RW5-02-AC1).
- Candidate hash change invalidates accumulated qualification (RW5-02-AC2).
- Missing marks produce unknown/unavailable metrics rather than zero (RW5-02-AC3).
- Qualification cannot call venue or release activation (RW5-02-AC4).
- Top 10 filters comparable valid entries by inclusive frozen drawdown limit
  before net-return ranking (RW5-02-AC5).
- Ranking ties use drawdown, candidate ID, then agent ID, and return
  fewer than 10 when necessary (RW5-02-AC6).
- Duplicate ranked candidate in one cohort rejects and qualification remains separate (RW5-02-AC7).
"""

from __future__ import annotations

import hashlib
import sqlite3
import threading
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from indodax_lab.contracts.identity import (
    ArtifactRef,
    ImmutableManifest,
    _ensure_utc,
    manifest_digest,
)
from indodax_lab.contracts.workbench import (
    MetricValidity,
    MetricValue,
)

if TYPE_CHECKING:
    from indodax_lab.paper.agents import AgentFactory, AgentRecord


class TournamentError(Exception):
    """Base error for tournament cohort and qualification failures."""


class CohortNotFoundError(TournamentError, KeyError):
    """Raised when a requested cohort ID is not registered."""


class DuplicateCandidateCohortError(TournamentError, ValueError):
    """Raised when duplicate candidates are registered within one cohort."""


class IncomparableCohortError(TournamentError, ValueError):
    """Raised when agents fail cohort comparability criteria."""


class CohortManifest(ImmutableManifest):
    """Immutable specification of a tournament cohort pinning comparability criteria."""

    cohort_id: str
    version: str = "v1"
    agent_ids: tuple[str, ...]
    pair: str | None = None
    universe: tuple[str, ...] = ()
    initial_virtual_cash: Decimal
    currency: str = "IDR"
    feed_id: str = "feed-default"
    cost_policy_ref: ArtifactRef | None = None
    execution_policy_ref: ArtifactRef | None = None
    comparison_policy_ref: ArtifactRef | None = None
    max_drawdown_limit: Decimal
    evaluation_window_start_utc: datetime | None = None
    evaluation_window_end_utc: datetime | None = None
    schema_version: str = "v1"
    created_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator(
        "created_at_utc", "evaluation_window_start_utc", "evaluation_window_end_utc", mode="after"
    )
    @classmethod
    def validate_utc(cls, value: datetime | None, info: Any) -> datetime | None:
        if value is None:
            return None
        return _ensure_utc(value, info.field_name)

    @field_validator("initial_virtual_cash", mode="before")
    @classmethod
    def validate_positive_cash(cls, value: Any) -> Decimal:
        dec = Decimal(str(value))
        if not dec.is_finite() or dec <= 0:
            raise ValueError("POSITIVE_VIRTUAL_CASH_REQUIRED")
        return dec

    @field_validator("max_drawdown_limit", mode="before")
    @classmethod
    def validate_drawdown_limit(cls, value: Any) -> Decimal:
        dec = Decimal(str(value))
        if not dec.is_finite() or dec <= 0 or dec > 1:
            raise ValueError("MAX_DRAWDOWN_LIMIT_MUST_BE_IN_0_TO_1")
        return dec

    @field_validator("agent_ids")
    @classmethod
    def validate_agent_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("NON_EMPTY_AGENT_IDS_REQUIRED")
        return value


class CohortRecord(BaseModel):
    """Durable cohort identity record."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cohort_ref: ArtifactRef
    cohort_id: str
    agent_refs: tuple[ArtifactRef, ...]
    comparison_policy_ref: ArtifactRef | None = None
    created_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def cohort_manifest_ref(self) -> ArtifactRef:
        return self.cohort_ref


class QualificationDecision(BaseModel):
    """Evidence-based qualification gate verdict distinct from tournament rank."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    agent_ref: ArtifactRef
    candidate_ref: ArtifactRef
    policy_ref: ArtifactRef | str | None = None
    elapsed_days: int = Field(ge=0)
    closed_forward_trades: int = Field(ge=0)
    incident_refs: tuple[str, ...] = ()
    recovery_evidence_refs: tuple[str, ...] = ()
    qualified: bool
    rejection_reasons: tuple[str, ...] = ()
    decided_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))
    authority_disclaimer: str = (
        "NO_DEPLOYMENT_AUTHORITY: Qualification is an evaluation gate, "
        "not live execution activation."
    )


class LeaderboardRankRow(BaseModel):
    """Ranked candidate representative in Top 10."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rank: int = Field(ge=1)
    agent_id: str
    candidate_id: str
    candidate_version: str = "v1"
    candidate_digest: str
    net_return: MetricValue
    max_drawdown: MetricValue
    win_rate: MetricValue | None = None
    closed_trades_count: int = Field(default=0, ge=0)
    forward_days: int = Field(default=0, ge=0)
    status: str = "ELIGIBLE"
    qualified: bool = False


class LeaderboardExcludedRow(BaseModel):
    """Entry excluded or ineligible from Top 10 ranking with clear reason."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    agent_id: str
    candidate_id: str
    reason: str
    net_return: MetricValue | None = None
    max_drawdown: MetricValue | None = None


class Leaderboard(BaseModel):
    """Cohort leaderboard with Top 10 ranking and per-agent qualification."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cohort_ref: ArtifactRef
    as_of_time_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))
    as_of_feed_cursor: str | None = None
    entries: tuple[LeaderboardRankRow, ...] = ()
    excluded_entries: tuple[LeaderboardExcludedRow, ...] = ()
    comparability_reasons: tuple[str, ...] = ()
    qualifications: dict[str, QualificationDecision] = Field(default_factory=dict)


class ComparisonMetricRow(BaseModel):
    """Per-agent performance metrics in comparison."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    agent_id: str
    candidate_id: str
    net_return: MetricValue
    max_drawdown: MetricValue
    win_rate: MetricValue | None = None
    closed_trades_count: int = Field(default=0, ge=0)
    forward_days: int = Field(default=0, ge=0)


class SubjectPolicyInfo(BaseModel):
    """Per-subject operational configuration and policies."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    agent_id: str
    capital: Decimal
    currency: str
    feed_id: str
    cost_policy: str | None = None
    window_start_utc: datetime | None = None
    window_end_utc: datetime | None = None


class ComparisonReport(BaseModel):
    """Descriptive comparison across candidate agents with comparability check."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    subject_refs: tuple[ArtifactRef, ...]
    metric_rows: tuple[ComparisonMetricRow, ...]
    policies: tuple[SubjectPolicyInfo, ...]
    comparable: bool
    incompatibility_reasons: tuple[str, ...] = ()
    disclaimer: str = "NO_WINNER_OR_DEPLOYMENT_AUTHORITY: Comparison is descriptive only."


class TournamentService:
    """Service managing tournament cohorts, leaderboards, comparisons, and qualifications."""

    def __init__(
        self,
        root: Path | str | None = None,
        *,
        agent_factory: AgentFactory | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._root = Path(root) if root is not None else None
        if self._root is not None:
            self._root.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(str(self._root / "tournament.sqlite"), timeout=30.0)
        else:
            self._db = sqlite3.connect(":memory:", timeout=30.0)
        self._db.row_factory = sqlite3.Row
        self._agent_factory = agent_factory
        self._clock = clock
        self._lock = threading.RLock()
        self._cohorts: dict[str, CohortManifest] = {}
        self._evidence_records: dict[str, dict[str, Any]] = {}
        self._init_db()

    def _init_db(self) -> None:
        with self._lock, self._db:
            self._db.execute(
                """
                CREATE TABLE IF NOT EXISTS cohorts (
                    cohort_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    manifest_json TEXT NOT NULL,
                    manifest_digest TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    PRIMARY KEY (cohort_id, version)
                )
                """
            )
            self._db.execute(
                """
                CREATE TABLE IF NOT EXISTS qualifications (
                    agent_id TEXT NOT NULL PRIMARY KEY,
                    decision_json TEXT NOT NULL,
                    decided_at_utc TEXT NOT NULL
                )
                """
            )

    def _utcnow(self) -> datetime:
        return self._clock() if self._clock is not None else datetime.now(UTC)

    def record_agent_evidence(
        self,
        agent_id: str,
        *,
        forward_days: int = 0,
        closed_trades_count: int = 0,
        net_return: Decimal | float | None = None,
        max_drawdown: Decimal | float | None = None,
        win_rate: Decimal | float | None = None,
        marks_available: bool = True,
        missing_marks_reason: str | None = None,
        candidate_digest: str | None = None,
        incident_refs: Sequence[str] = (),
        recovery_evidence_refs: Sequence[str] = (),
    ) -> None:
        """Record verified forward shadow evidence for an agent."""
        with self._lock:
            self._evidence_records[agent_id] = {
                "forward_days": forward_days,
                "closed_trades_count": closed_trades_count,
                "net_return": Decimal(str(net_return)) if net_return is not None else None,
                "max_drawdown": Decimal(str(max_drawdown)) if max_drawdown is not None else None,
                "win_rate": Decimal(str(win_rate)) if win_rate is not None else None,
                "marks_available": marks_available,
                "missing_marks_reason": missing_marks_reason,
                "candidate_digest": candidate_digest,
                "incident_refs": tuple(incident_refs),
                "recovery_evidence_refs": tuple(recovery_evidence_refs),
                "updated_at_utc": self._utcnow().isoformat(),
            }

    def _get_agent_info(self, agent_id: str) -> tuple[AgentRecord | None, dict[str, Any]]:
        record: AgentRecord | None = None
        if self._agent_factory is not None:
            try:
                record = self._agent_factory.get(agent_id)
            except Exception:
                record = None
        evidence = self._evidence_records.get(agent_id, {})
        return record, evidence

    def create(self, cohort_manifest: CohortManifest) -> CohortRecord:
        """Create and persist a new tournament cohort with strict comparability guards."""
        with self._lock:
            # Check for duplicate candidates in cohort (RW5-02-AC7)
            seen_candidates: dict[str, str] = {}
            for aid in cohort_manifest.agent_ids:
                record, evidence = self._get_agent_info(aid)
                cand_key: str | None = None
                if record is not None:
                    c_ref = record.candidate_ref
                    cand_key = f"{c_ref.id}:{c_ref.version}:{c_ref.sha256}"
                elif evidence.get("candidate_digest"):
                    cand_key = f"cand_{aid}:{evidence['candidate_digest']}"

                if cand_key is not None:
                    if cand_key in seen_candidates:
                        prior_agent = seen_candidates[cand_key]
                        cid = cohort_manifest.cohort_id
                        raise DuplicateCandidateCohortError(
                            f"DUPLICATE_CANDIDATE_IN_COHORT: duplicate candidate {cand_key} "
                            f"bound to both '{prior_agent}' and '{aid}' in cohort '{cid}'"
                        )
                    seen_candidates[cand_key] = aid

            digest = manifest_digest(cohort_manifest)
            cohort_ref = ArtifactRef(
                kind="cohort",
                id=cohort_manifest.cohort_id,
                version=cohort_manifest.version,
                sha256=digest,
            )

            # Build agent refs
            agent_refs: list[ArtifactRef] = []
            for aid in cohort_manifest.agent_ids:
                record, _ = self._get_agent_info(aid)
                if record is not None:
                    aref = ArtifactRef(
                        kind="agent",
                        id=aid,
                        version=record.version,
                        sha256=record.manifest_digest,
                    )
                else:
                    sha = hashlib.sha256(f"agent:{aid}".encode()).hexdigest()
                    aref = ArtifactRef(kind="agent", id=aid, version="v1", sha256=sha)
                agent_refs.append(aref)

            now = self._utcnow()
            with self._db:
                self._db.execute(
                    """
                    INSERT INTO cohorts (
                        cohort_id, version, manifest_json, manifest_digest, created_at_utc
                    )
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(cohort_id, version) DO UPDATE SET
                        manifest_json = excluded.manifest_json,
                        manifest_digest = excluded.manifest_digest
                    """,
                    (
                        cohort_manifest.cohort_id,
                        cohort_manifest.version,
                        cohort_manifest.model_dump_json(),
                        digest,
                        now.isoformat(),
                    ),
                )
            self._cohorts[cohort_manifest.cohort_id] = cohort_manifest

            return CohortRecord(
                cohort_ref=cohort_ref,
                cohort_id=cohort_manifest.cohort_id,
                agent_refs=tuple(agent_refs),
                comparison_policy_ref=cohort_manifest.comparison_policy_ref,
                created_at_utc=now,
            )

    def _load_cohort(self, cohort_id: str) -> CohortManifest:
        if cohort_id in self._cohorts:
            return self._cohorts[cohort_id]
        row = self._db.execute(
            "SELECT manifest_json FROM cohorts WHERE cohort_id = ? ORDER BY version DESC LIMIT 1",
            (cohort_id,),
        ).fetchone()
        if row is None:
            raise CohortNotFoundError(f"COHORT_NOT_FOUND:{cohort_id}")
        manifest = CohortManifest.model_validate_json(row["manifest_json"])
        self._cohorts[cohort_id] = manifest
        return manifest

    def leaderboard(self, cohort_id: str) -> Leaderboard:
        """Compute Top 10 leaderboard with drawdown limit filter and separate qualification."""
        cohort = self._load_cohort(cohort_id)
        digest = manifest_digest(cohort)
        cohort_ref = ArtifactRef(
            kind="cohort",
            id=cohort.cohort_id,
            version=cohort.version,
            sha256=digest,
        )

        eligible_entries: list[dict[str, Any]] = []
        excluded_entries: list[LeaderboardExcludedRow] = []
        comparability_reasons: list[str] = []
        qualifications: dict[str, QualificationDecision] = {}

        seen_candidate_digests: dict[str, str] = {}

        for aid in cohort.agent_ids:
            record, evidence = self._get_agent_info(aid)
            cand_id = record.candidate_ref.id if record else f"cand_{aid}"
            cand_ver = record.candidate_ref.version if record else "v1"
            cand_digest = (
                record.candidate_ref.sha256
                if record
                else evidence.get("candidate_digest", "0" * 64)
            )

            # 1. Check comparability against cohort
            incomparable_reason: str | None = None
            if record is not None:
                if Decimal(record.initial_cash) != cohort.initial_virtual_cash:
                    incomparable_reason = (
                        f"INCOMPATIBLE_CAPITAL:{record.initial_cash}!={cohort.initial_virtual_cash}"
                    )
            if incomparable_reason:
                comparability_reasons.append(incomparable_reason)
                excluded_entries.append(
                    LeaderboardExcludedRow(
                        agent_id=aid,
                        candidate_id=cand_id,
                        reason=incomparable_reason,
                    )
                )
                continue

            # 2. Check marks availability (RW5-02-AC3: missing marks produce unknown metrics)
            marks_available = evidence.get("marks_available", True)
            if not marks_available:
                missing_reason = (
                    evidence.get("missing_marks_reason")
                    or "MISSING_MARKS: mark price unavailable for position valuation"
                )
                unknown_ret = MetricValue(
                    value=None,
                    unit="ratio",
                    validity=MetricValidity.UNAVAILABLE,
                    reason=missing_reason,
                )
                unknown_dd = MetricValue(
                    value=None,
                    unit="ratio",
                    validity=MetricValidity.UNAVAILABLE,
                    reason=missing_reason,
                )
                excluded_entries.append(
                    LeaderboardExcludedRow(
                        agent_id=aid,
                        candidate_id=cand_id,
                        reason=f"UNAVAILABLE_METRICS:{missing_reason}",
                        net_return=unknown_ret,
                        max_drawdown=unknown_dd,
                    )
                )
                continue

            # 3. Extract metrics
            raw_ret = evidence.get("net_return")
            raw_dd = evidence.get("max_drawdown")
            if raw_ret is None or raw_dd is None:
                # Metrics not yet available
                unknown_metric = MetricValue(
                    value=None,
                    unit="ratio",
                    validity=MetricValidity.UNAVAILABLE,
                    reason="METRICS_NOT_RECORDED",
                )
                excluded_entries.append(
                    LeaderboardExcludedRow(
                        agent_id=aid,
                        candidate_id=cand_id,
                        reason="UNAVAILABLE_METRICS:metrics_not_recorded",
                        net_return=unknown_metric,
                        max_drawdown=unknown_metric,
                    )
                )
                continue

            ret_val = Decimal(str(raw_ret))
            dd_val = Decimal(str(raw_dd))

            # 4. Check inclusive drawdown limit (RW5-02-AC5)
            # dd_val <= max_drawdown_limit passes; > fails
            if dd_val > cohort.max_drawdown_limit:
                excluded_entries.append(
                    LeaderboardExcludedRow(
                        agent_id=aid,
                        candidate_id=cand_id,
                        reason=f"EXCEEDS_MAX_DRAWDOWN_LIMIT:{dd_val}>{cohort.max_drawdown_limit}",
                        net_return=MetricValue(
                            value=ret_val, unit="ratio", validity=MetricValidity.VALID
                        ),
                        max_drawdown=MetricValue(
                            value=dd_val, unit="ratio", validity=MetricValidity.VALID
                        ),
                    )
                )
                continue

            # 5. Check duplicate candidate representative (RW5-02-AC7)
            if cand_digest in seen_candidate_digests:
                prior = seen_candidate_digests[cand_digest]
                reason = (
                    f"DUPLICATE_CANDIDATE_REPRESENTATIVE: candidate {cand_id} "
                    f"already represented by {prior}"
                )
                excluded_entries.append(
                    LeaderboardExcludedRow(
                        agent_id=aid,
                        candidate_id=cand_id,
                        reason=reason,
                        net_return=MetricValue(
                            value=ret_val, unit="ratio", validity=MetricValidity.VALID
                        ),
                        max_drawdown=MetricValue(
                            value=dd_val, unit="ratio", validity=MetricValidity.VALID
                        ),
                    )
                )
                continue

            seen_candidate_digests[cand_digest] = aid

            # Eligible
            win_rate_val = evidence.get("win_rate")
            win_rate_metric = (
                MetricValue(
                    value=Decimal(str(win_rate_val)), unit="ratio", validity=MetricValidity.VALID
                )
                if win_rate_val is not None
                else None
            )

            eligible_entries.append(
                {
                    "agent_id": aid,
                    "candidate_id": cand_id,
                    "candidate_version": cand_ver,
                    "candidate_digest": cand_digest,
                    "net_return_val": ret_val,
                    "max_dd_val": dd_val,
                    "net_return": MetricValue(
                        value=ret_val, unit="ratio", validity=MetricValidity.VALID
                    ),
                    "max_drawdown": MetricValue(
                        value=dd_val, unit="ratio", validity=MetricValidity.VALID
                    ),
                    "win_rate": win_rate_metric,
                    "closed_trades_count": evidence.get("closed_trades_count", 0),
                    "forward_days": evidence.get("forward_days", 0),
                }
            )

        # 6. Sort eligible entries (RW5-02-AC6):
        # net return descending, drawdown ascending, candidate ID ascending, agent ID ascending
        eligible_entries.sort(
            key=lambda e: (
                -e["net_return_val"],
                e["max_dd_val"],
                e["candidate_id"],
                e["agent_id"],
            )
        )

        # Truncate to Top 10 (fewer than 10 returned when necessary)
        top_10 = eligible_entries[:10]

        # 7. Evaluate qualification separately per agent (RW5-02-AC1)
        ranked_rows: list[LeaderboardRankRow] = []
        for idx, entry in enumerate(top_10, start=1):
            qual = self.qualify(entry["agent_id"])
            qualifications[entry["agent_id"]] = qual
            ranked_rows.append(
                LeaderboardRankRow(
                    rank=idx,
                    agent_id=entry["agent_id"],
                    candidate_id=entry["candidate_id"],
                    candidate_version=entry["candidate_version"],
                    candidate_digest=entry["candidate_digest"],
                    net_return=entry["net_return"],
                    max_drawdown=entry["max_drawdown"],
                    win_rate=entry["win_rate"],
                    closed_trades_count=entry["closed_trades_count"],
                    forward_days=entry["forward_days"],
                    status="ELIGIBLE",
                    qualified=qual.qualified,
                )
            )

        # Also qualify any excluded agents to populate complete qualifications map
        for excl in excluded_entries:
            if excl.agent_id not in qualifications:
                qualifications[excl.agent_id] = self.qualify(excl.agent_id)

        now = self._utcnow()
        return Leaderboard(
            cohort_ref=cohort_ref,
            as_of_time_utc=now,
            entries=tuple(ranked_rows),
            excluded_entries=tuple(excluded_entries),
            comparability_reasons=tuple(comparability_reasons),
            qualifications=qualifications,
        )

    def compare(self, agent_ids: Sequence[str]) -> ComparisonReport:
        """Compare candidate agents and flag any capital/feed/policy incompatibility."""
        metric_rows: list[ComparisonMetricRow] = []
        policies: list[SubjectPolicyInfo] = []
        subject_refs: list[ArtifactRef] = []
        incompatibility_reasons: list[str] = []

        capitals: dict[str, Decimal] = {}
        feeds: dict[str, str] = {}
        currencies: dict[str, str] = {}

        for aid in agent_ids:
            record, evidence = self._get_agent_info(aid)
            cand_id = record.candidate_ref.id if record else f"cand_{aid}"

            # Ref
            if record is not None:
                aref = ArtifactRef(
                    kind="agent",
                    id=aid,
                    version=record.version,
                    sha256=record.manifest_digest,
                )
                cap = Decimal(record.initial_cash)
                cur = "IDR"
                feed = getattr(record, "canonical_feed_identity", "feed-btc")
            else:
                aref = ArtifactRef(
                    kind="agent",
                    id=aid,
                    version="v1",
                    sha256=hashlib.sha256(f"agent:{aid}".encode()).hexdigest(),
                )
                cap = Decimal("1000000")
                cur = "IDR"
                feed = "feed-btc"

            subject_refs.append(aref)
            capitals[aid] = cap
            currencies[aid] = cur
            feeds[aid] = feed

            policies.append(
                SubjectPolicyInfo(
                    agent_id=aid,
                    capital=cap,
                    currency=cur,
                    feed_id=feed,
                )
            )

            # Metrics
            raw_ret = evidence.get("net_return")
            raw_dd = evidence.get("max_drawdown")
            marks_avail = evidence.get("marks_available", True)

            if not marks_avail or raw_ret is None or raw_dd is None:
                net_ret = MetricValue(
                    value=None,
                    unit="ratio",
                    validity=MetricValidity.UNAVAILABLE,
                    reason=evidence.get("missing_marks_reason") or "METRICS_UNAVAILABLE",
                )
                max_dd = MetricValue(
                    value=None,
                    unit="ratio",
                    validity=MetricValidity.UNAVAILABLE,
                    reason=evidence.get("missing_marks_reason") or "METRICS_UNAVAILABLE",
                )
            else:
                net_ret = MetricValue(
                    value=Decimal(str(raw_ret)),
                    unit="ratio",
                    validity=MetricValidity.VALID,
                )
                max_dd = MetricValue(
                    value=Decimal(str(raw_dd)),
                    unit="ratio",
                    validity=MetricValidity.VALID,
                )

            win_rate_val = evidence.get("win_rate")
            win_rate_metric = (
                MetricValue(
                    value=Decimal(str(win_rate_val)), unit="ratio", validity=MetricValidity.VALID
                )
                if win_rate_val is not None
                else None
            )

            metric_rows.append(
                ComparisonMetricRow(
                    agent_id=aid,
                    candidate_id=cand_id,
                    net_return=net_ret,
                    max_drawdown=max_dd,
                    win_rate=win_rate_metric,
                    closed_trades_count=evidence.get("closed_trades_count", 0),
                    forward_days=evidence.get("forward_days", 0),
                )
            )

        # Check comparability across all subjects
        unique_capitals = set(capitals.values())
        if len(unique_capitals) > 1:
            sorted_caps = sorted(str(c) for c in unique_capitals)
            incompatibility_reasons.append(
                f"INCOMPATIBLE_CAPITAL: differing initial cash {sorted_caps}"
            )

        unique_feeds = set(feeds.values())
        if len(unique_feeds) > 1:
            incompatibility_reasons.append(
                f"INCOMPATIBLE_FEED: differing feeds {sorted(unique_feeds)}"
            )

        unique_currencies = set(currencies.values())
        if len(unique_currencies) > 1:
            incompatibility_reasons.append(
                f"INCOMPATIBLE_CURRENCY: differing currencies {sorted(unique_currencies)}"
            )

        comparable = len(incompatibility_reasons) == 0

        return ComparisonReport(
            subject_refs=tuple(subject_refs),
            metric_rows=tuple(metric_rows),
            policies=tuple(policies),
            comparable=comparable,
            incompatibility_reasons=tuple(incompatibility_reasons),
        )

    def qualify(
        self, agent_id: str, policy_ref: ArtifactRef | str | None = None
    ) -> QualificationDecision:
        """Evaluate evidence-based forward qualification distinct from leaderboard rank.

        Invariants enforced:
        - Exactly >=90 forward days AND >=100 closed trades required (RW5-02-AC0).
        - Any unresolved incident rejects qualification (RW5-02-AC1).
        - Candidate hash change invalidates accumulated qualification (RW5-02-AC2).
        - No venue execution or release activation authority (RW5-02-AC4).
        """
        record, evidence = self._get_agent_info(agent_id)

        # Resolve candidate reference
        if record is not None:
            cand_ref = record.candidate_ref
            registered_candidate_digest = record.candidate_ref.sha256
            agent_ref = ArtifactRef(
                kind="agent",
                id=agent_id,
                version=record.version,
                sha256=record.manifest_digest,
            )
            incident_list = list(record.incident_refs)
        else:
            cand_digest = evidence.get("candidate_digest", "a" * 64)
            registered_candidate_digest = cand_digest
            cand_ref = ArtifactRef(
                kind="candidate",
                id=f"cand_{agent_id}",
                version="v1",
                sha256=cand_digest,
            )
            agent_ref = ArtifactRef(
                kind="agent",
                id=agent_id,
                version="v1",
                sha256=hashlib.sha256(f"agent:{agent_id}".encode()).hexdigest(),
            )
            incident_list = []

        # Merge incident refs from evidence
        ev_incidents = evidence.get("incident_refs", ())
        for inc in ev_incidents:
            if inc not in incident_list:
                incident_list.append(inc)

        forward_days = evidence.get("forward_days", 0)
        closed_trades = evidence.get("closed_trades_count", 0)
        ev_candidate_digest = evidence.get("candidate_digest")

        rejection_reasons: list[str] = []

        # RW5-02-AC2: Candidate hash change invalidates accumulated qualification
        if ev_candidate_digest is not None and ev_candidate_digest != registered_candidate_digest:
            rejection_reasons.append(
                f"CANDIDATE_HASH_CHANGED: registered candidate digest "
                f"{registered_candidate_digest} does not match current "
                f"evidence digest {ev_candidate_digest}"
            )
            # Accumulated days and trades are invalidated
            forward_days = 0
            closed_trades = 0

        # RW5-02-AC0: 90 days AND 100 trades gate
        if forward_days < 90:
            rejection_reasons.append(
                f"INSUFFICIENT_FORWARD_DURATION: {forward_days} < 90 forward days required"
            )
        if closed_trades < 100:
            rejection_reasons.append(
                f"INSUFFICIENT_CLOSED_FORWARD_TRADES: {closed_trades} < 100 closed trades required"
            )

        # RW5-02-AC1: Unresolved incident rejects qualification
        if len(incident_list) > 0:
            rejection_reasons.append(
                f"UNRESOLVED_INCIDENT: unresolved incidents present: {', '.join(incident_list)}"
            )

        qualified = len(rejection_reasons) == 0
        now = self._utcnow()

        decision = QualificationDecision(
            agent_ref=agent_ref,
            candidate_ref=cand_ref,
            policy_ref=policy_ref,
            elapsed_days=forward_days,
            closed_forward_trades=closed_trades,
            incident_refs=tuple(incident_list),
            recovery_evidence_refs=tuple(evidence.get("recovery_evidence_refs", ())),
            qualified=qualified,
            rejection_reasons=tuple(rejection_reasons),
            decided_at_utc=now,
        )

        with self._lock, self._db:
            self._db.execute(
                """
                INSERT INTO qualifications (agent_id, decision_json, decided_at_utc)
                VALUES (?, ?, ?)
                ON CONFLICT(agent_id) DO UPDATE SET
                    decision_json = excluded.decision_json,
                    decided_at_utc = excluded.decided_at_utc
                """,
                (agent_id, decision.model_dump_json(), now.isoformat()),
            )

        return decision
