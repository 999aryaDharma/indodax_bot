# RW4-01 handoff — immutable candidate packaging and lifecycle

Status: DONE

## Identity

- Sprint: RW4-01 — Immutable candidate packaging and lifecycle
- Implementation owner: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- Independent reviewer: Antigravity / coordinator (independent PASS)
- Branch: `dev` (main checkout; no other owner on these paths)
- Code SHA: `a6fba64` — `feat(rw4-01): immutable candidate packaging and lifecycle`
- This handoff is the evidence follow-up to `a6fba64`; it contains no code changes.
- Environment: Windows, Python 3.14.0, pytest 9.0.3, ruff 0.16.9, `D:\bot-trading`
- Dependencies DONE verified at claim: RW3-01, ML-04.

## Files and contracts

- `src/indodax_lab/evaluation/candidates.py` (NEW) — CandidateRegistry:
  `package(experiment_id, review_ref, *, experiment) -> CandidateManifest`
  (requires SUCCESS + non-blank review + resolvable result bytes + matching
  plan digest; no-clobber publish; appends BACKTEST_VERIFIED);
  `verify(ref) -> VerifiedCandidate` (re-resolves every lineage byte by
  content hash and compares the full lineage record);
  `transition(id, event, *, evidence_refs, note) -> CandidateRecord`
  (append-only NOTE/SHADOW_REGISTER/RETIRE; provided evidence must resolve;
  frozen digest re-checked after append);
  `get(ref)` (identity-checked read); `retrain(..., model_refs)` (always a
  new version, never a mutation); `publish_manifest` (idempotent-or-conflict
  republication primitive); `record`/`count`. Lineage = plan digest +
  pipeline bytes sha + content hashes of pipeline model refs, retrain model
  refs, and risk/cost/execution policy bytes. Resolution failures of any
  kind normalize to `EVIDENCE_MISSING` (never filename identity, never raw
  decoder errors).
- `tests/unit/lab/evaluation/test_candidate_packaging.py` (NEW) — 7 AC-mapped
  tests with dict-backed content-addressed bytes, real contract types, real
  hash verification, and a real CandidateRuntime.load linkage proof.
- `src/`: otherwise untouched (Modify: None honored).

## Acceptance evidence (behavioral RED observed, then GREEN)

- Setup RED: candidates module absent → collection error (not proof).
- Behavioral RED (throwaway canned-wrong stub, never committed): 7 failed
  with assertion failures on the specified outcomes.
- Real REDs fixed during implementation (new/test code only): republication
  idempotency vs conflict needed distinct paths (identical bytes return,
  mutated bytes reject); LookupError from byte stores normalized to
  `EVIDENCE_MISSING` ValueError; retrain takes caller-stored model refs
  (registry never invents CAS entries); lineage split into pipeline vs
  extra model refs so recomputation terminates on the same record.
- GREEN: `python -m pytest
  tests/unit/lab/evaluation/test_candidate_packaging.py -q -p no:cacheprovider`
  → `7 passed`, exit 0.

| AC | Test | Assertion |
|---|---|---|
| AC5 | `test_rw4_01_bootstrap_recovery` | Package binds executed plan digest; verified candidate loads via real CandidateRuntime.load (decision identity preserved) |
| AC0 | `test_rw4_01_0` | Corrupted model bytes → CANDIDATE_LINEAGE_MISMATCH; mutated republication → CANDIDATE_VERSION_CONFLICT |
| AC1 | `test_rw4_01_1` | FAILED experiment → EXPERIMENT_NOT_COMPLETED; blank review → REVIEW_REF_REQUIRED; nothing published |
| AC2 | `test_rw4_01_2` | Deleted result bytes → EVIDENCE_MISSING, count stays 0 |
| AC3 | `test_rw4_01_3` | Retrain → v2 with new digest, same candidate_id; v1 still addressable |
| AC4 | `test_rw4_01_4` | Frozen model rejects attribute set; NOTE transition keeps digest; ghost evidence blocks |
| AC6 | `test_rw4_01_program_6` | SHADOW_REGISTER freezes plan+policy digests in the event; mutated republication rejected |

## Gates

1. Focused: 7 passed, exit 0.
2. Affected: `tests/unit/lab/evaluation + test_model_registry.py` →
   `146 passed`, exit 0 (no src outside the new module touched).
3. `ruff check` (E,F,I,B,UP) on both new files → clean.
4. `git diff --check` → exit 0.

## Self-review notes and deviations

- No credentials, live network, real orders, Production paths. Dict-backed
  artifact bytes stand in for the content-addressed store; the resolver
  contract (ref → bytes by sha) is what production CAS must satisfy.
- Experiment evidence is duck-typed to the RW3-01 result shape (status,
  plan, result digest, artifact path); wiring the live RW3-01 service is
  operator/integration scope, recorded for the coordinator.
- Plan-byte tampering is pinned by digest string (plan bytes live in
  experiment evidence, not CAS); pipeline/model/policy byte tampering is
  pinned by re-resolved content hashes. Both layers asserted in AC0.
- No subagent dispatch; no manifest edit; no push/merge/deploy.

## Next eligible consumers

RW5-01, RW7-01, PM-05, RW9-01 (unblocked on code; still subject to coordinator DAG + review PASS).

## Independent review — coordinator pass (2026-09-30)

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- Verdict: PASS
- Fresh runs:
  - `python -m pytest tests/unit/lab/evaluation/test_candidate_packaging.py -q -p no:cacheprovider`: 7 passed in 4.83s, exit 0.
  - `python -m pytest tests/unit/lab/evaluation tests/unit/lab/models/test_model_registry.py -q -p no:cacheprovider`: 146 passed in 7.66s, exit 0.
- Observations:
  - Candidate packaging binds verified plan digest, pipeline artifact refs, model content hashes, and policy lineage.
  - Fail-closed behavior verified for corrupted bytes, mutated republications, unreviewed/failed experiments, and missing evidence.
  - Retrain contract properly mints incremented version (`v2`), preserving previous versions.
  - Candidate runtime loading preserves decision identity without recompilation.
- Status transition: Promoted to DONE. Unlocks RW5-01, RW7-01, and PM-05 to READY.
