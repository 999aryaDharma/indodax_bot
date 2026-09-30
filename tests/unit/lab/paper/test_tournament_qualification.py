"""Unit tests for RW5-02: Tournament cohorts leaderboard and qualification.

Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)

Acceptance Criteria:
- RW5-02-AC0 / FR0: 89 days/100 trades and 90 days/99 trades both reject
  (enforce frozen 90-day AND 100-closed-trade gate).
- RW5-02-AC1 / FR1: Rank one with unresolved incident is unqualified.
- RW5-02-AC2 / FR2: Candidate hash change invalidates accumulated qualification.
- RW5-02-AC3 / FR3: Missing marks produce unknown metrics rather than zero.
- RW5-02-AC4 / FR4: Qualification cannot call venue or release activation.
- RW5-02-AC5: Top 10 filters comparable valid entries by inclusive frozen drawdown limit
  before net-return ranking.
- RW5-02-AC6: Ranking ties use drawdown candidate ID then agent ID and return fewer than
  ten when necessary.
- RW5-02-AC7: Duplicate ranked candidate in one cohort rejects and qualification remains
  separate.

Constraints:
- Tests must use tmp_path, fake clocks, in-memory/tmp DBs only.
- Never connect to real venues, real network, or live credentials.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from indodax_lab.contracts.identity import ArtifactRef
from indodax_lab.contracts.workbench import AgentManifest, MetricValidity
from indodax_lab.paper.agents import AgentFactory
from indodax_lab.paper.tournament_service import (
    CohortManifest,
    ComparisonReport,
    DuplicateCandidateCohortError,
    QualificationDecision,
    TournamentService,
)

BASE_TS = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)
SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64


def _ref(candidate_id: str, sha: str, version: str = "v1") -> ArtifactRef:
    return ArtifactRef(kind="candidate", id=candidate_id, version=version, sha256=sha)


def _agent_manifest(
    agent_id: str,
    *,
    candidate_id: str = "cand_1",
    sha: str = SHA_A,
    cohort_id: str = "cohort_alpha",
    cash: Decimal = Decimal("1000000"),
    feed_id: str = "feed-indodax-btc",
) -> AgentManifest:
    return AgentManifest(
        agent_id=agent_id,
        version="v1",
        candidate_ref=_ref(candidate_id, sha),
        cohort_id=cohort_id,
        initial_virtual_cash=cash,
        currency="IDR",
        runtime_policy_refs=(),
        namespace_id=f"ns_{agent_id}",
        canonical_feed_identity=feed_id,
    )


def _make_factory(root: Path) -> AgentFactory:
    bindings = {
        ("cand_1", "v1"): SimpleNamespace(candidate_digest=SHA_A, plan_digest="plan_1"),
        ("cand_2", "v1"): SimpleNamespace(candidate_digest=SHA_B, plan_digest="plan_2"),
        ("cand_3", "v1"): SimpleNamespace(candidate_digest=SHA_C, plan_digest="plan_3"),
        ("cand_4", "v1"): SimpleNamespace(candidate_digest=SHA_D, plan_digest="plan_4"),
    }

    def _resolve(ref: ArtifactRef) -> SimpleNamespace:
        key = (ref.id, ref.version)
        if key not in bindings:
            return SimpleNamespace(candidate_digest=ref.sha256, plan_digest=f"plan_{ref.id}")
        return bindings[key]

    return AgentFactory(root=root, candidate_resolver=_resolve)


# ---------------------------------------------------------------------------
# RW5-02-AC0 / FR0: 89 days/100 trades and 90 days/99 trades both reject
# ---------------------------------------------------------------------------


def test_rw5_02_0(tmp_path: Path) -> None:
    """RW5-02-AC0: Enforce frozen 90-day AND 100-closed-forward-trade gate."""
    factory = _make_factory(tmp_path / "agents")
    service = TournamentService(root=tmp_path / "tournament", agent_factory=factory)

    # Agent 1: 89 days, 100 trades (fails duration)
    manifest_1 = _agent_manifest("agent_89_100", candidate_id="cand_1", sha=SHA_A)
    factory.register(manifest_1)
    service.record_agent_evidence(
        "agent_89_100",
        forward_days=89,
        closed_trades_count=100,
        candidate_digest=SHA_A,
    )
    decision_1 = service.qualify("agent_89_100")
    assert isinstance(decision_1, QualificationDecision)
    assert decision_1.qualified is False
    assert any("INSUFFICIENT_FORWARD_DURATION" in r for r in decision_1.rejection_reasons)
    assert decision_1.elapsed_days == 89
    assert decision_1.closed_forward_trades == 100

    # Agent 2: 90 days, 99 trades (fails trades count)
    manifest_2 = _agent_manifest("agent_90_99", candidate_id="cand_2", sha=SHA_B)
    factory.register(manifest_2)
    service.record_agent_evidence(
        "agent_90_99",
        forward_days=90,
        closed_trades_count=99,
        candidate_digest=SHA_B,
    )
    decision_2 = service.qualify("agent_90_99")
    assert isinstance(decision_2, QualificationDecision)
    assert decision_2.qualified is False
    assert any("INSUFFICIENT_CLOSED_FORWARD_TRADES" in r for r in decision_2.rejection_reasons)
    assert decision_2.elapsed_days == 90
    assert decision_2.closed_forward_trades == 99

    # Agent 3: 90 days, 100 trades (passes both)
    manifest_3 = _agent_manifest("agent_90_100", candidate_id="cand_3", sha=SHA_C)
    factory.register(manifest_3)
    service.record_agent_evidence(
        "agent_90_100",
        forward_days=90,
        closed_trades_count=100,
        candidate_digest=SHA_C,
    )
    decision_3 = service.qualify("agent_90_100")
    assert decision_3.qualified is True
    assert len(decision_3.rejection_reasons) == 0


# ---------------------------------------------------------------------------
# RW5-02-AC1 / FR1: Rank one with unresolved incident is unqualified
# ---------------------------------------------------------------------------


def test_rw5_02_1(tmp_path: Path) -> None:
    """RW5-02-AC1: Rank one with unresolved incident is unqualified."""
    factory = _make_factory(tmp_path / "agents")
    service = TournamentService(root=tmp_path / "tournament", agent_factory=factory)

    # Register two agents
    m1 = _agent_manifest("agent_champ", candidate_id="cand_1", sha=SHA_A)
    m2 = _agent_manifest("agent_runner_up", candidate_id="cand_2", sha=SHA_B)
    factory.register(m1)
    factory.register(m2)

    # Champ has highest net return (e.g. 50%), lowest drawdown (5%), >=90 days & >=100 trades
    # BUT champ has an unresolved incident!
    service.record_agent_evidence(
        "agent_champ",
        forward_days=95,
        closed_trades_count=120,
        net_return=Decimal("0.50"),
        max_drawdown=Decimal("0.05"),
        candidate_digest=SHA_A,
        incident_refs=("INCIDENT_RISK_BREACH_001",),
    )

    # Runner up has lower return (e.g. 20%), 10% drawdown, clean incidents
    service.record_agent_evidence(
        "agent_runner_up",
        forward_days=92,
        closed_trades_count=105,
        net_return=Decimal("0.20"),
        max_drawdown=Decimal("0.10"),
        candidate_digest=SHA_B,
        incident_refs=(),
    )

    cohort = CohortManifest(
        cohort_id="cohort_incidents",
        agent_ids=("agent_champ", "agent_runner_up"),
        initial_virtual_cash=Decimal("1000000"),
        feed_id="feed-indodax-btc",
        max_drawdown_limit=Decimal("0.20"),
    )
    service.create(cohort)

    leaderboard = service.leaderboard("cohort_incidents")
    assert len(leaderboard.entries) == 2

    # Champ is Rank 1
    rank_1 = leaderboard.entries[0]
    assert rank_1.agent_id == "agent_champ"
    assert rank_1.rank == 1

    # But Champ is UNQUALIFIED!
    assert rank_1.qualified is False
    champ_qual = leaderboard.qualifications["agent_champ"]
    assert champ_qual.qualified is False
    assert any("UNRESOLVED_INCIDENT" in r for r in champ_qual.rejection_reasons)

    # Runner up is Rank 2 and QUALIFIED
    rank_2 = leaderboard.entries[1]
    assert rank_2.agent_id == "agent_runner_up"
    assert rank_2.rank == 2
    assert rank_2.qualified is True


# ---------------------------------------------------------------------------
# RW5-02-AC2 / FR2: Candidate hash change invalidates accumulated qualification
# ---------------------------------------------------------------------------


def test_rw5_02_2(tmp_path: Path) -> None:
    """RW5-02-AC2: Candidate hash change invalidates accumulated qualification."""
    factory = _make_factory(tmp_path / "agents")
    service = TournamentService(root=tmp_path / "tournament", agent_factory=factory)

    m = _agent_manifest("agent_hash_mod", candidate_id="cand_1", sha=SHA_A)
    factory.register(m)

    # 100 days, 150 trades accumulated, but candidate hash changed to SHA_B
    service.record_agent_evidence(
        "agent_hash_mod",
        forward_days=100,
        closed_trades_count=150,
        candidate_digest=SHA_B,  # Mismatched with registered SHA_A!
    )

    decision = service.qualify("agent_hash_mod")
    assert decision.qualified is False
    assert any(
        "CANDIDATE_HASH_CHANGED" in r or "CANDIDATE_IDENTITY_MISMATCH" in r
        for r in decision.rejection_reasons
    )


# ---------------------------------------------------------------------------
# RW5-02-AC3 / FR3: Missing marks produce unknown metrics rather than zero
# ---------------------------------------------------------------------------


def test_rw5_02_3(tmp_path: Path) -> None:
    """RW5-02-AC3: Missing marks produce unknown metrics rather than zero."""
    factory = _make_factory(tmp_path / "agents")
    service = TournamentService(root=tmp_path / "tournament", agent_factory=factory)

    m = _agent_manifest("agent_no_marks", candidate_id="cand_1", sha=SHA_A)
    factory.register(m)

    # Record agent with missing mark prices
    service.record_agent_evidence(
        "agent_no_marks",
        forward_days=95,
        closed_trades_count=110,
        marks_available=False,
        missing_marks_reason="MISSING_MARKS: mark price unavailable for btc_idr",
        candidate_digest=SHA_A,
    )

    cohort = CohortManifest(
        cohort_id="cohort_marks",
        agent_ids=("agent_no_marks",),
        initial_virtual_cash=Decimal("1000000"),
        feed_id="feed-indodax-btc",
        max_drawdown_limit=Decimal("0.20"),
    )
    service.create(cohort)

    leaderboard = service.leaderboard("cohort_marks")

    # Agent with unavailable metrics must not be ranked as 0 drawdown / 0 return winner
    # It must be excluded or flagged with MetricValidity.UNAVAILABLE
    assert len(leaderboard.entries) == 0
    assert len(leaderboard.excluded_entries) == 1
    excluded = leaderboard.excluded_entries[0]
    assert excluded.agent_id == "agent_no_marks"
    assert "UNAVAILABLE" in excluded.reason or "MISSING_MARKS" in excluded.reason
    if excluded.max_drawdown is not None:
        assert excluded.max_drawdown.validity == MetricValidity.UNAVAILABLE
        assert excluded.max_drawdown.value is None
        assert "MISSING_MARKS" in (excluded.max_drawdown.reason or "")


# ---------------------------------------------------------------------------
# RW5-02-AC4 / FR4: Qualification cannot call venue or release activation
# ---------------------------------------------------------------------------


def test_rw5_02_4(tmp_path: Path) -> None:
    """RW5-02-AC4: Qualification cannot call venue or release activation."""
    # Venue mock / spy to verify zero calls
    mock_venue = MagicMock()
    mock_venue.submit_order = MagicMock()
    mock_venue.cancel_order = MagicMock()

    factory = AgentFactory(
        root=tmp_path / "agents",
        candidate_resolver=lambda ref: SimpleNamespace(
            candidate_digest=ref.sha256, plan_digest="plan"
        ),
        venue_factory=lambda _id: mock_venue,
    )
    service = TournamentService(root=tmp_path / "tournament", agent_factory=factory)

    m = _agent_manifest("agent_safe_qual", candidate_id="cand_1", sha=SHA_A)
    factory.register(m)
    service.record_agent_evidence(
        "agent_safe_qual",
        forward_days=95,
        closed_trades_count=120,
        candidate_digest=SHA_A,
    )

    decision = service.qualify("agent_safe_qual")

    # Verify no venue submission or execution was called
    assert mock_venue.submit_order.call_count == 0
    assert mock_venue.cancel_order.call_count == 0

    # Verify decision contains strict no-deployment authority disclaimer
    assert "NO_DEPLOYMENT_AUTHORITY" in decision.authority_disclaimer


# ---------------------------------------------------------------------------
# RW5-02-AC5: Top 10 filters comparable valid entries by inclusive frozen drawdown limit
# ---------------------------------------------------------------------------


def test_rw5_02_program_5(tmp_path: Path) -> None:
    """RW5-02-AC5: Top 10 filters comparable valid entries by inclusive drawdown limit."""
    factory = _make_factory(tmp_path / "agents")
    service = TournamentService(root=tmp_path / "tournament", agent_factory=factory)

    # Agents with various drawdowns against a 0.20 (20%) limit
    manifests = [
        _agent_manifest("agent_dd_25", candidate_id="cand_1", sha=SHA_A),
        _agent_manifest("agent_dd_20", candidate_id="cand_2", sha=SHA_B),
        _agent_manifest("agent_dd_15", candidate_id="cand_3", sha=SHA_C),
        _agent_manifest("agent_dd_10", candidate_id="cand_4", sha=SHA_D),
    ]
    for m in manifests:
        factory.register(m)

    # Agent 1: 50% return, 25% drawdown (> 20% limit -> MUST BE FILTERED OUT)
    service.record_agent_evidence(
        "agent_dd_25",
        net_return=Decimal("0.50"),
        max_drawdown=Decimal("0.25"),
        candidate_digest=SHA_A,
    )
    # Agent 2: 30% return, 20% drawdown (== 20% limit -> INCLUSIVE PASS)
    service.record_agent_evidence(
        "agent_dd_20",
        net_return=Decimal("0.30"),
        max_drawdown=Decimal("0.20"),
        candidate_digest=SHA_B,
    )
    # Agent 3: 10% return, 15% drawdown (< 20% limit -> PASS)
    service.record_agent_evidence(
        "agent_dd_15",
        net_return=Decimal("0.10"),
        max_drawdown=Decimal("0.15"),
        candidate_digest=SHA_C,
    )
    # Agent 4: 40% return, 10% drawdown (< 20% limit -> PASS)
    service.record_agent_evidence(
        "agent_dd_10",
        net_return=Decimal("0.40"),
        max_drawdown=Decimal("0.10"),
        candidate_digest=SHA_D,
    )

    cohort = CohortManifest(
        cohort_id="cohort_dd_filter",
        agent_ids=("agent_dd_25", "agent_dd_20", "agent_dd_15", "agent_dd_10"),
        initial_virtual_cash=Decimal("1000000"),
        feed_id="feed-indodax-btc",
        max_drawdown_limit=Decimal("0.20"),
    )
    service.create(cohort)

    leaderboard = service.leaderboard("cohort_dd_filter")

    # Ranked entries should only contain the 3 valid entries (dd <= 0.20)
    ranked_ids = [e.agent_id for e in leaderboard.entries]
    assert "agent_dd_25" not in ranked_ids
    assert ranked_ids == ["agent_dd_10", "agent_dd_20", "agent_dd_15"]

    # agent_dd_25 must be in excluded_entries with reason EXCEEDS_MAX_DRAWDOWN_LIMIT
    excluded_ids = [e.agent_id for e in leaderboard.excluded_entries]
    assert "agent_dd_25" in excluded_ids
    excluded_row = next(e for e in leaderboard.excluded_entries if e.agent_id == "agent_dd_25")
    assert "EXCEEDS_MAX_DRAWDOWN_LIMIT" in excluded_row.reason


# ---------------------------------------------------------------------------
# RW5-02-AC6: Ranking ties use drawdown, candidate ID then agent ID
# ---------------------------------------------------------------------------


def test_rw5_02_program_6(tmp_path: Path) -> None:
    """RW5-02-AC6: Ranking ties use drawdown, candidate ID then agent ID."""
    factory = _make_factory(tmp_path / "agents")
    service = TournamentService(root=tmp_path / "tournament", agent_factory=factory)

    # 3 agents with identical net return of 25%
    # Agent A: dd 15%, cand_2
    # Agent B: dd 10%, cand_1 -> lower drawdown beats Agent A
    # Agent C: dd 10%, cand_2 -> tie with B on dd, but cand_1 < cand_2
    manifests = [
        _agent_manifest("agent_a", candidate_id="cand_2", sha=SHA_B),
        _agent_manifest("agent_b", candidate_id="cand_1", sha=SHA_A),
        _agent_manifest("agent_c", candidate_id="cand_3", sha=SHA_C),
    ]
    for m in manifests:
        factory.register(m)

    service.record_agent_evidence(
        "agent_a", net_return=Decimal("0.25"), max_drawdown=Decimal("0.15"), candidate_digest=SHA_B
    )
    service.record_agent_evidence(
        "agent_b", net_return=Decimal("0.25"), max_drawdown=Decimal("0.10"), candidate_digest=SHA_A
    )
    service.record_agent_evidence(
        "agent_c", net_return=Decimal("0.25"), max_drawdown=Decimal("0.10"), candidate_digest=SHA_C
    )

    cohort = CohortManifest(
        cohort_id="cohort_ties",
        agent_ids=("agent_a", "agent_b", "agent_c"),
        initial_virtual_cash=Decimal("1000000"),
        feed_id="feed-indodax-btc",
        max_drawdown_limit=Decimal("0.20"),
    )
    service.create(cohort)

    leaderboard = service.leaderboard("cohort_ties")

    # Exactly 3 entries returned (fewer than 10, no fake padding!)
    assert len(leaderboard.entries) == 3

    # Tie breaking order:
    # 1. agent_b (net_return 0.25, dd 0.10, cand_1)
    # 2. agent_c (net_return 0.25, dd 0.10, cand_3) -> cand_1 < cand_3
    # 3. agent_a (net_return 0.25, dd 0.15, cand_2) -> higher dd
    assert leaderboard.entries[0].agent_id == "agent_b"
    assert leaderboard.entries[1].agent_id == "agent_c"
    assert leaderboard.entries[2].agent_id == "agent_a"


# ---------------------------------------------------------------------------
# RW5-02-AC7: Duplicate ranked candidate in one cohort rejects
# ---------------------------------------------------------------------------


def test_rw5_02_program_7(tmp_path: Path) -> None:
    """RW5-02-AC7: Duplicate ranked candidate in one cohort rejects."""
    factory = _make_factory(tmp_path / "agents")
    service = TournamentService(root=tmp_path / "tournament", agent_factory=factory)

    # Two agents binding the EXACT SAME candidate (cand_1 with SHA_A)
    m1 = _agent_manifest("agent_dup_1", candidate_id="cand_1", sha=SHA_A)
    m2 = _agent_manifest("agent_dup_2", candidate_id="cand_1", sha=SHA_A)
    factory.register(m1)
    factory.register(m2)

    cohort = CohortManifest(
        cohort_id="cohort_dup",
        agent_ids=("agent_dup_1", "agent_dup_2"),
        initial_virtual_cash=Decimal("1000000"),
        feed_id="feed-indodax-btc",
        max_drawdown_limit=Decimal("0.20"),
    )

    # Creating cohort with duplicate candidate must reject
    with pytest.raises(DuplicateCandidateCohortError):
        service.create(cohort)


# ---------------------------------------------------------------------------
# ComparisonReport & Comparability verification
# ---------------------------------------------------------------------------


def test_rw5_02_compare_and_comparability(tmp_path: Path) -> None:
    """Verify TournamentService.compare flags incompatible capital/feed/policies."""
    factory = _make_factory(tmp_path / "agents")
    service = TournamentService(root=tmp_path / "tournament", agent_factory=factory)

    # Agent 1: 1M cash, feed-btc
    m1 = _agent_manifest(
        "agent_comp_1",
        candidate_id="cand_1",
        sha=SHA_A,
        cash=Decimal("1000000"),
        feed_id="feed-btc",
    )
    # Agent 2: 500k cash, feed-btc (different capital)
    m2 = _agent_manifest(
        "agent_comp_2", candidate_id="cand_2", sha=SHA_B, cash=Decimal("500000"), feed_id="feed-btc"
    )
    factory.register(m1)
    factory.register(m2)

    service.record_agent_evidence(
        "agent_comp_1",
        net_return=Decimal("0.10"),
        max_drawdown=Decimal("0.05"),
        candidate_digest=SHA_A,
    )
    service.record_agent_evidence(
        "agent_comp_2",
        net_return=Decimal("0.15"),
        max_drawdown=Decimal("0.08"),
        candidate_digest=SHA_B,
    )

    report = service.compare(("agent_comp_1", "agent_comp_2"))
    assert isinstance(report, ComparisonReport)
    assert report.comparable is False
    assert any("INCOMPATIBLE_CAPITAL" in r for r in report.incompatibility_reasons)
    assert "NO_WINNER_OR_DEPLOYMENT_AUTHORITY" in report.disclaimer


def test_rw5_02_promotion_qualification_bridge(tmp_path: Path) -> None:
    """Verify promotion.check_qualification_decision correctly validates decisions."""
    from indodax_lab.paper.promotion import check_qualification_decision

    factory = _make_factory(tmp_path / "agents")
    service = TournamentService(root=tmp_path / "tournament", agent_factory=factory)

    m = _agent_manifest("agent_qual_pass", candidate_id="cand_1", sha=SHA_A)
    factory.register(m)
    service.record_agent_evidence(
        "agent_qual_pass", forward_days=95, closed_trades_count=120, candidate_digest=SHA_A
    )

    valid_decision = service.qualify("agent_qual_pass")
    assert check_qualification_decision(valid_decision) is True

    # Failed decision (e.g. 89 days)
    m_fail = _agent_manifest("agent_qual_fail", candidate_id="cand_2", sha=SHA_B)
    factory.register(m_fail)
    service.record_agent_evidence(
        "agent_qual_fail", forward_days=89, closed_trades_count=120, candidate_digest=SHA_B
    )

    invalid_decision = service.qualify("agent_qual_fail")
    assert check_qualification_decision(invalid_decision) is False
