# PM-05 handoff — candidate-bound release provenance

Status: REVIEW (implementation complete, independent review required; not self-approved DONE)

## Identity

- Sprint: PM-05 — Candidate-bound release provenance
- Implementation owner: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- Independent reviewer: UNASSIGNED
- Branch: `dev` (already checked out; no branch switch, worktree, push, merge, or deploy)
- Base SHA: `abb8af6`
- Code SHA: `212d28d` — `feat(pm-05): candidate-bound release provenance` (exactly the 4 owned paths; no sibling files)
- Environment: Windows PowerShell, Python 3.14.0, pytest 9.0.3, ruff 0.16.8, `D:\bot-trading`
- Dependencies DONE verified at claim: RW4-01 (DONE), PM-03 (DONE)
- Production-main constraint honored: offline release-provenance verification ONLY.
  No live orders, credentials, production DB/state changes, gate activation, or new
  production write authority. Research requests can never be eligible.

## Files and contracts (owned paths only)

- `src/indodax_lab/verification/release_bundle.py` (MODIFY) —
  `ProductionReleaseManifest` requires candidate/models/features/pipeline/risk/cost/
  execution/Git/dependency/environment digests plus qualification refs, per-candidate
  gate refs, exclusive `pair_owner_map`, allocation-policy digest, aggregate
  shared-capital evidence digest, and per-file `artifact_manifest`; `manifest_digest`
  is an explicitly documented content-integrity hash, never a signature.
  `create_production_release_manifest` rejects missing/blank/mismatched identity
  fail-closed (`POLICY/MODEL/SCHEMA/..._IDENTITY_MISSING`,
  `CANDIDATE_IDENTITY_MISMATCH/INVALID`, `PAIR_OWNER_UNKNOWN/MISSING`,
  `QUALIFICATION_REF_MISSING` via candidate mismatch). Legacy `ReleaseBundle` /
  `create_release_bundle` / `verify_release_bundle` unchanged and still readable.
- `src/indodax_lab/verification/release.py` (MODIFY, REL-01 code untouched) —
  `verify_release(manifest, artifacts, trust_policy) -> VerifiedRelease` with
  detached-signature capability against caller-supplied offline trust roots
  (`TrustPolicy.trusted_key_ids` + `DetachedSignature` covering the manifest
  digest). No keys added anywhere in the module. Legacy digest-only bundles
  raise `LEGACY_BUNDLE_NOT_AUTHENTIC`; unsigned manifests report
  `authenticity="CHECKSUM_ONLY"` and can never read as signed — a local SHA
  checksum is never described as a signature. Eligibility additionally requires
  qualified independent gate evidence per candidate, matching aggregate
  shared-capital evidence, clean source, known dependency identity, exclusive
  pair ownership, and production origin. `mark_deployed` always raises
  `RESEARCH_CANNOT_DEPLOY` for research origin and `ACTIVATION_NOT_ELIGIBLE` /
  `AUTHENTICITY_INSUFFICIENT` otherwise; it changes no production state.
- `deploy/release-lab.sh` (MODIFY, shell-only) — packages an immutable
  read-only release manifest JSON (`release-manifest-<tag>.json` with
  `manifest_sha256`, sprint-manifest digest, git SHA) instead of printing
  READY; still fails closed when core sprints are not all DONE. No live effects.
- `tests/unit/lab/verification/test_release_provenance.py` (NEW) — 7 AC-mapped
  tests, in-memory bytes only, no network/credentials/live DBs.

## Acceptance evidence (behavioral RED observed, then GREEN)

- Behavioral RED on unmodified baseline (no stubs committed):
  legacy `create_release_bundle` without candidate identity succeeds and
  `verify_release_bundle` returns `True` on digest alone (gap: identity optional,
  digest is not signature); `verify_release` does not exist in `release.py`.
- Import RED after writing tests, before implementing: collection error on
  `DetachedSignature` (not counted as behavioral proof).
- GREEN: `python -m pytest tests/unit/lab/verification/test_release_provenance.py -q -p no:cacheprovider` → `7 passed`, exit 0.

| AC | Test | Assertion |
|---|---|---|
| AC0 | `test_pm_05_0` | Blank risk/model/features identity and mismatched/invalid candidate identity raise `ReleaseProvenanceError` |
| AC1 | `test_pm_05_1` | Same filename with changed bytes raises `ARTIFACT_BYTES_MISMATCH` |
| AC2 | `test_pm_05_2` | Legacy digest-only bundle raises `LEGACY_BUNDLE_NOT_AUTHENTIC`; unsigned manifest is `CHECKSUM_ONLY`, never signed |
| AC3 | `test_pm_05_3` | Dirty source / unknown dependency → `eligible False` (`SOURCE_DIRTY` / `UNKNOWN_DEPENDENCY_IDENTITY`); deploy raises |
| AC4 | `test_pm_05_4` | Research origin → `eligible False` (`RESEARCH_NEVER_ELIGIBLE`); `mark_deployed` raises `RESEARCH_CANNOT_DEPLOY` |
| AC5 | `test_pm_05_program_5` | Two-candidate exclusive pair ownership + per-candidate gate evidence + detached signature → eligible, deployable under production; unknown/missing pair owner rejects; legacy bundle still readable |
| AC6 | `test_pm_05_program_6` | Tampered candidate digest → `MANIFEST_DIGEST_MISMATCH`; divergent aggregate evidence → `eligible False` (`AGGREGATE_EVIDENCE_MISMATCH`); activation refused in both |

## Gates

1. Focused: `tests/unit/lab/verification/test_release_provenance.py` → `7 passed`, exit 0.
2. Affected (shared-file gate): `tests/unit/lab/verification + tests/regression/test_release_candidate.py` → `31 passed`, exit 0; full `tests/unit/lab + tests/regression/test_release_candidate.py` → `1572 passed`, exit 0.
3. Repository gate (informational, pre-existing failures outside scope):
   `python -m pytest -q -p no:cacheprovider --continue-on-collection-errors` →
   1886 passed, 2 skipped, 2 collection errors, 10–13 failed in ~70s. All out of
   scope and untouched by this diff: 2 collection errors from missing optional
   dep `pandas_ta_classic` (`tests/regression/test_phase0_invariants.py`,
   `tests/unit/test_risk_manager.py` via `src/ta_processor.py`); 5 failures in
   `tests/integration/test_signal_observation.py` (unmodified tracked file, does
   not import verification modules); failures in untracked sibling-WIP files
   `tests/security/test_quantops_boundary.py` (RW7-01) and
   `tests/integration/lab/test_agent_isolation.py` (RW5-01). No package installs
   performed; recorded as capability gap.
4. `ruff check` on touched Python files → clean. One `E501` at
   `src/indodax_lab/verification/release.py:316` is pre-existing baseline in
   untouched REL-01 rollback code (verified absent from this diff); left alone
   per scope rules.
5. `git diff --check` → exit 0.

## Self-review notes and deviations

- No credentials, live network, real orders, or production paths touched.
  `TrustPolicy`/`DetachedSignature` carry caller-supplied offline roots only;
  asymmetric crypto itself is operator-provided outside the module.
- `request_origin` defaults to `"production"` but every other gate (signature,
  gate evidence, source, dependencies, aggregate, pairs) still applies, so the
  default grants nothing by itself; research origin is doubly refused
  (ineligible + `mark_deployed` raise).
- `mark_deployed` returning an already-deployed record unchanged preserves
  exactly-once semantics for duplicate identical requests.
- No subagent dispatch; `docs/sprints/sprint-manifest.json` untouched;
  `docs/.obsidian/workspace.json` (modified by environment/sibling) never staged.
- Sibling-owned untracked files (`src/indodax_lab/mcp/`,
  `src/indodax_lab/paper/agents.py`, `tests/integration/lab/test_agent_isolation.py`,
  `tests/security/test_quantops_boundary.py`) and the `docs/.obsidian` change
  were left intact and unstaged.

## Next eligible consumers

PM-06, RW9-01, PM-07, PM-08 (unblocked on code; still subject to coordinator DAG + review PASS).

## Pending external gates

Independent reviewer assignment and PASS; coordinator manifest/DONE transition;
no activation/deployment authorized by this sprint (offline verification only).

## Coordinator recovery note (2026-09-30)

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | Shared-checkout index race swept staged PM-05 files into sibling commits; orphaned worker commits 8de9a52/8246a50 abandoned (reflog only). Content recommitted as 212d28d (this handoff updated to match); worktree tests re-verified 7 passed before recommit. Sibling files untouched. Recommend isolated worktrees for future parallel dispatches.
