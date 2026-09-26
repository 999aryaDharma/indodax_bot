# SHADOW-03 handoff

Status: REVIEW

## Identity
- Sprint ID: SHADOW-03 — Champion replacement gate
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/shadow-03-champion-replacement-gate`
- Base SHA: `7447937`
- Code target: `feat(shadow-03): champion replacement gate`
- Evidence SHA relation: `586c582`

## Files and contracts
- Actual files:
  - `src/indodax_lab/paper/promotion.py` (ChallengerEvidence, PromotionDecision, ChampionRegistry, InsufficientForwardDurationError, InsufficientForwardTradesError, UnsealedCandidatePromotionError, PolicyBreachPromotionError)
  - `src/indodax_lab/paper/__init__.py` (Package exports — SHADOW-03 symbols added)
  - `tests/unit/lab/paper/test_promotion.py` (AC0..AC3 unit tests and edge cases)
- Contract:
  - `sealed pass + >=90 days AND >=100 pooled closed forward trades + no policy breach -> versioned promotion.`
  - Champion replacement: `ChampionRegistry.evaluate_promotion()` swaps active champion pointer atomically when candidate possesses sealed pass, >=90 forward evaluation days, and >=100 closed trades without breach (SHADOW-03-AC0).
  - Forward duration requirement: Candidates with >=100 trades but <90 forward days fail duration gate, raising `InsufficientForwardDurationError` (SHADOW-03-AC1).
  - Trade sample size requirement: Candidates with >=90 forward days but <100 closed trades fail sample size gate, raising `InsufficientForwardTradesError` (SHADOW-03-AC2).
  - Champion pointer isolation: Training, logging, or evaluating challengers leaves active champion pointer strictly unaltered (SHADOW-03-AC3).
- Migration and compatibility:
  - Additive module in `src/indodax_lab/paper/`; no existing interfaces modified.
  - Dependencies: SHADOW-02 (REVIEW), EVAL-03 (REVIEW).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| SHADOW-03-AC0 (RED) | `test_shadow_03_valid_contract` | `python -m pytest tests/unit/lab/paper/test_promotion.py` | Exit 1 (ModuleNotFoundError: No module named 'indodax_lab.paper.promotion') | `working tree` |
| SHADOW-03-AC0 (GREEN) | `test_shadow_03_valid_contract` | `python -m pytest tests/unit/lab/paper/test_promotion.py::test_shadow_03_valid_contract` | Exit 0 (Passed, challenger with >=90 days and >=100 trades replaces champion) | `586c582` |
| SHADOW-03-AC1 (RED) | `test_shadow_03_contract_1` | `python -m pytest tests/unit/lab/paper/test_promotion.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| SHADOW-03-AC1 (GREEN) | `test_shadow_03_contract_1` | `python -m pytest tests/unit/lab/paper/test_promotion.py::test_shadow_03_contract_1` | Exit 0 (Passed, 100 trades in 10 days raises InsufficientForwardDurationError) | `586c582` |
| SHADOW-03-AC2 (RED) | `test_shadow_03_contract_2` | `python -m pytest tests/unit/lab/paper/test_promotion.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| SHADOW-03-AC2 (GREEN) | `test_shadow_03_contract_2` | `python -m pytest tests/unit/lab/paper/test_promotion.py::test_shadow_03_contract_2` | Exit 0 (Passed, 90 days with 40 trades raises InsufficientForwardTradesError) | `586c582` |
| SHADOW-03-AC3 (RED) | `test_shadow_03_contract_3` | `python -m pytest tests/unit/lab/paper/test_promotion.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| SHADOW-03-AC3 (GREEN) | `test_shadow_03_contract_3` | `python -m pytest tests/unit/lab/paper/test_promotion.py::test_shadow_03_contract_3` | Exit 0 (Passed, challenger activity leaves active champion pointer unchanged) | `586c582` |

All 4 tests in `tests/unit/lab/paper/test_promotion.py` passed (0.45s).
Full lab suite verification: 199 passed across strategies, features, labels, evaluation, backtest, orchestration, operations, training materialization, retention, models, reporting, and paper.

## Review
- Spec verdict: PASS (meets all functional requirements of SHADOW-03 and docs/specs/14-shadow-portfolios-and-promotion.md).
- Quality verdict: PASS (strict dual-threshold gate: 90 days AND 100 trades, atomic pointer update, unsealed candidate rejection, no real-money execution).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for SHADOW-03.
- Next unlocked consumers: No mandatory downstream.

---

## Sprint review fix cycle — SHADOW-03 (batch `ops-shadow`)

Actor: `opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)`
Date: 2026-09-27 · Source SHA: uncommitted working tree (`feat/feat-02-finalization`) · Fix cycle: 1 of 1

### Findings fixed

| ID | Severity | Finding |
|---|---|---|
| SHADOW-03-F1 | Critical | `evaluate_promotion` auto-promoted a challenger that merely satisfied the count/duration thresholds, ignoring forward *quality*. `ChallengerEvidence.outperformance` had a silent default, so a challenger with equal or worse forward performance replaced the champion. |
| SHADOW-03-F2 | Critical | `evaluate_promotion(challenger)` had no approval parameter at all. Promotion was a pure function call — any caller, including an untrusted callback, could promote a challenger with no approver identity, no evidence reference and no review. Violates "no automatic merge" in `docs/specs/14-shadow-portfolios-and-promotion.md`. |
| SHADOW-03-F3 | Critical | Nothing bound the approval to the evidence it reviewed. An approval captured for one evidence snapshot could promote a *different* challenger, and stale evidence (months old) promoted indefinitely. |
| SHADOW-03-F4 | Important | `ChampionRegistry` exposed no rollback, so a bad promotion could only be undone by hand-editing registry state. |

### RED evidence (real assertion failures, no assertion weakened/deleted/skipped)

Command: `python -m pytest tests/unit/lab/paper/test_promotion_gate_hardening.py -p no:cacheprovider -q`
Result: **4 failed** — observed failures:
- `AssertionError: assert 'challenger_m02' == 'champion_m01'` — an equal-performance challenger was promoted over the live champion.
- `AssertionError: assert None == 'champion_m01'` — `previous_champion_id` was `None`, so the decision record carried no promotion lineage.
- Two further assertion failures on the missing-approval and self-approval paths.

### Fix

- `ChallengerEvidence.outperformance` is now **required** (no default) and enforced: a challenger that does not beat the champion raises the new `InsufficientQualityPromotionError`.
- `evaluate_promotion(challenger, approval: PromotionApproval | None = None)` now **fails closed**: a missing approval raises `MissingPromotionApprovalError` instead of promoting.
- New `PromotionApproval` carries `approver_id`, `approved_at_utc`, `evidence_id`, `evidence_digest` and `reason`; the engine rejects `approver_id == evidence.submitted_by` via `SelfApprovalForbiddenError`.
- New `ChallengerEvidence.evidence_digest()` returns a canonical sha256 over the evidence payload, and `evaluate_promotion` recomputes it — a digest mismatch raises `StalePromotionEvidenceError`, as does evidence older than `max_evidence_age_days=30`.
- `PromotionDecision` gained `previous_champion_id`, `previous_champion_version`, `approved_by` and `evidence_digest`; `NoPromotedChampionError` replaces silent `None` for rollback.
- `ChampionRegistry` gained `promotion_history` and `rollback_last_promotion()`.

### GREEN evidence

Command: `python -m pytest tests/unit/lab/paper -p no:cacheprovider -q`
Result: **54 passed** (includes the pre-existing `test_promotion.py`, strengthened not weakened — it now supplies `evidence_id`, `evaluated_at_utc` and an explicit `_make_approval()`).

### Files changed
- `src/indodax_lab/paper/promotion.py`
- `src/indodax_lab/paper/__init__.py` (new exports: `InsufficientQualityPromotionError`, `MissingPromotionApprovalError`, `NoPromotedChampionError`, `PromotionApproval`, `SelfApprovedPromotionError`, `StalePromotionEvidenceError`)
- `tests/unit/lab/paper/test_promotion_gate_hardening.py` (new RED suite)
- `tests/unit/lab/paper/test_promotion.py` (existing suite strengthened to supply the now-required approval and evidence fields)

### Isolation
All tests use `tmp_path` and in-memory fakes only. No real data directory, no live service, no network, no real orders or ledger.
