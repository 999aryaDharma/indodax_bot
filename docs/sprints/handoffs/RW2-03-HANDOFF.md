# RW2-03 Handoff — Typed declarative pipeline composer

- **Sprint:** RW2-03 (`docs/sprints/research-workbench/RW2-03-typed-declarative-pipeline-composer.md`)
- **Owner:** implementation owner (task 4), isolated worktree `D:\bot-trading\.worktrees\feat-rw2-03`
- **Reviewer:** independent reviewer not yet dispatched — coordinator assigns after this handoff
- **Branch:** `feat/rw2-03-typed-declarative-pipeline-composer`
- **Base SHA:** `e9f6a34`
- **Implementation/evidence SHA:** `9921b31607cb533f1c50c0bb5425f562af7cd99e` (`9921b31`)
  — commit `feat(rw2-03): typed declarative pipeline composer`, contains tests + implementation
- **Environment:** Windows (win32), Python 3.14.0, pytest 9.0.3, pydantic 2.12.3, PyYAML 6.0.3

## Scope delivered

New, additive package `src/indodax_lab/pipelines/` — one validated graph for TA-only and
TA+ML+DL soft-vote compositions, with draft/revision/publish lifecycle and a single
YAML presentation contract. No existing file was modified (spec `Modify:` list = None).

| Actual path | Action | Notes |
|---|---|---|
| `src/indodax_lab/pipelines/__init__.py` | CREATE | package export surface (`PipelineService`, `ValidationReport`, `PipelineValidationError`, `ValidationIssue`, `canonicalize`) |
| `src/indodax_lab/pipelines/registry.py` | CREATE | `PipelineDraftStore` (SQLite drafts + publications) and `PipelineService` |
| `src/indodax_lab/pipelines/validation.py` | CREATE | typed-port/DAG/ensemble/component validation, `canonicalize`, hardened `import_yaml`/`export_yaml` |
| `tests/unit/lab/pipelines/__init__.py` | CREATE | package marker |
| `tests/unit/lab/pipelines/test_pipeline_validation.py` | CREATE | 9 behavioral tests (6 AC + 3 supporting) |

Declared interface implemented exactly:
`create(manifest)->DraftRef`, `clone(ref)->DraftRef`,
`update(id, expected_revision, manifest)->DraftRef`,
`validate(manifest)->ValidationReport`, `publish(id, revision)->ArtifactRef`.
`ValidationReport` contains `valid`, `errors(code, node_id, port)`, `resolved_refs`.

## Reuse (nothing rebuilt)

- `PipelineManifest` / `PipelineNode` / `PipelineEdge` — RW0-01 `contracts/workbench.py` (read-only)
- `ArtifactRef`, `canonical_bytes`, `manifest_digest` — `contracts/identity.py`
- `DraftRef` — `strategies/base.py`; strategy resolution via `StrategyService.get` (RW2-01, published only)
- `ModelRegistry.load_verified`, `ModelRegistryError`, `RuntimeBlockedError` (`BLOCKED_RESOURCE`) — RW2-02
- CAS / no-clobber / idempotent-publication patterns — `strategies/store.py` (RW2-01)

## TDD evidence

### RED (before behavior was implemented)

- Command: `python -m pytest tests/unit/lab/pipelines/test_pipeline_validation.py -q`
- Exit: **1** — `7 failed, 2 passed in 5.65s`
- Wrong behavior (assertion failures, **not** import/dependency errors):

| Test | RED failure reason |
|---|---|
| `test_rw2_03_0` (AC0) | `resolved_refs == ()` — no component resolution implemented |
| `test_rw2_03_1` (AC1) | `cycle_report.valid is True` — no cycle/port/fan-in rejection |
| `test_rw2_03_2` (AC2) | `report.valid is True` — no abstain path |
| `test_rw2_03_3` (AC3) | digests differed across presentation order — no canonicalization |
| `test_rw2_03_program_4` (AC4) | reordered-YAML digest mismatch — no canonical export/import |
| `test_rw2_03_program_5` (AC5) | `DID NOT RAISE` for duplicate YAML key — SafeLoader silently overwrote |
| `test_rw2_03_ensemble_soft_vote_parameter_rules` | missing `PIPELINE_ENSEMBLE_WEIGHT_INVALID` |

- Passed at RED (store mechanics were already real in the RED skeleton):
  `test_rw2_03_draft_revision_fencing_and_idempotent_publication`,
  `test_rw2_03_clone_identity_fencing_and_published_fork`.

### GREEN (after implementation)

- Command: `python -m pytest tests/unit/lab/pipelines/test_pipeline_validation.py -q`
- Exit: **0** — `9 passed in 5.32s`

## AC → test mapping

| Acceptance | Test | Required assertion | Result |
|---|---|---|---|
| RW2-03-AC0 / FR0 | `test_rw2_03_0` | TA-only and TA+ML+DL soft-vote graphs validate | PASS (RED → GREEN) |
| RW2-03-AC1 / FR1 | `test_rw2_03_1` | Cycles, incompatible ports, dangling refs, ambiguous fan-in reject | PASS (RED → GREEN) |
| RW2-03-AC2 / FR2 | `test_rw2_03_2` | Missing required model output abstains with reason | PASS (RED → GREEN) |
| RW2-03-AC3 / FR3 | `test_rw2_03_3` | Identical graph ⇒ identical digest regardless of UI mode | PASS (RED → GREEN) |
| RW2-03-AC4 | `test_rw2_03_program_4` | Form YAML and MCP round trip to identical canonical digest | PASS (RED → GREEN) |
| RW2-03-AC5 | `test_rw2_03_program_5` | Reject duplicate YAML keys, custom tags, unknown fields, oversized payloads | PASS (RED → GREEN) |
| (supporting) | `test_rw2_03_ensemble_soft_vote_parameter_rules` | Soft-vote weight/threshold/mode/input/orphan rules, exit uniqueness | PASS (RED → GREEN) |
| (supporting) | `test_rw2_03_draft_revision_fencing_and_idempotent_publication` | `expected_revision` fencing, no-clobber, idempotent publish | PASS (passed at RED) |
| (supporting) | `test_rw2_03_clone_identity_fencing_and_published_fork` | clone digest fencing, published fork with new version | PASS (passed at RED) |

## Gates (run inside the worktree, in order)

| # | Command | Result | Exit |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/lab/pipelines/test_pipeline_validation.py -q` | `9 passed in 5.32s` | 0 |
| 2 | `python -m pytest tests/unit/lab -q` | `1483 passed, 1 warning in 72.23s` (baseline before this sprint: `1474 passed, 1 warning`) | 0 |
| 3 | `python -m ruff check src/indodax_lab/pipelines tests/unit/lab/pipelines` | `All checks passed!` | 0 |
| 4 | `git diff --check` / `git diff --cached --check` | clean (no whitespace errors) | 0 |

- Pre-change baseline gate recorded before any edit: `python -m pytest tests/unit/lab -q` →
  `1474 passed, 1 warning`, exit 0.
- No required tests skipped; the only warning is the pre-existing
  langsmith `pydantic.v1` / Python 3.14 `UserWarning` (unrelated to RW2-03).

## Behavior summary (what the validator enforces)

- **Typed ports:** a node's `output_port` must equal its kind's output type; an edge is legal
  only when `source_port == source.output_port` and `target_port` ∈ the target kind's accepted
  inputs. Port set: `MarketObservation`, `FeatureFrame`, `DecisionProposal`, `ProbabilityVector`,
  `SignalIntent`, `ExecutionPolicyRef`.
- **DAG:** unknown node/kind, duplicate/invalid node ids, cycles (`PIPELINE_CYCLE_DETECTED`,
  `evaluation_order == ()`), ambiguous multi-writer fan-in (`PIPELINE_AMBIGUOUS_FAN_IN`, allowed
  only on the ensemble node), unreachable nodes, unconsumed outputs, missing/duplicate sizing and
  exit nodes, dataset timeframe coverage, and any edge touching `execution_policy` reject.
- **Components:** a decision node binds only to a reference whose `id` equals its `node_id` and
  whose `kind` matches (`ta → strategy_manifest`, `ml`/`dl → model`); duplicate, missing,
  kind-mismatched, orphaned and unpublished/unresolvable references reject; resolution goes only
  through `StrategyService.get` (published RW2-01) and `ModelRegistry.load_verified` (RW2-02).
- **Abstention:** any ML/DL binding or resolution failure, and any ensemble-declared input that is
  absent / not ML-DL / not connected, emits `PIPELINE_ABSTAIN_MISSING_MODEL_OUTPUT` instead of a
  silent neutral vote; `RuntimeBlockedError` surfaces `BLOCKED_RESOURCE` in the reason.
- **Soft vote:** `mode == "soft_vote"`, ≥2 distinct declared inputs covering exactly the ensemble's
  incoming sources, non-negative finite weights covering exactly those inputs with positive sum,
  explicit threshold in (0, 1); parameters without an ensemble node are `..._PARAMS_ORPHANED`.
- **Canonical identity:** `canonicalize` sorts nodes by `node_id`, edges by
  (source node/port, target node/port), component refs by (kind, id, version, sha256) and sorts the
  soft-vote input list, so form view, graph view, YAML and MCP presentations of the same graph share
  one `manifest_digest`.
- **YAML (fail-closed, before any object is constructed):** 65 536-byte size cap, 32-level depth
  cap, tag allowlist (standard `yaml.org,2002:*` only — `!!python/*`, `!local` and `%TAG`-remapped
  tags reject as `PIPELINE_YAML_FORBIDDEN_TAG`), explicit duplicate-key detection on the composed
  node tree, non-finite number rejection, then `PipelineManifest` validation with
  `PIPELINE_MANIFEST_UNKNOWN_FIELD` for extra keys. SafeLoader is used for construction; nothing is
  ever constructed from a rejected document.
- **Store:** local SQLite `pipeline_drafts` + `pipeline_publications`, default journal (no WAL),
  `BEGIN IMMEDIATE` compare-and-swap, `expected_revision` fencing on update/publish, publication
  no-clobber (`IMMUTABLE_VERSION_CONFLICT`) with idempotent repeat publication, and
  `clone(DraftRef)` digest fencing / `clone(ArtifactRef)` version fork.

## Self-review notes (owner cannot final-approve)

- Full scoped diff reviewed (5 new files, 1688 insertions, 0 modified existing files).
- Found and fixed before commit: one `E501` (101 > 100) in `registry.py` SQL text, and one unused
  module constant (`DECISION_KINDS`) left over from drafting (YAGNI). Re-ran all gates after.
- Tests drive the public `PipelineService` boundary only; temp SQLite files, temp model registry
  and synthetic M01 portable bundles — no network, no Telegram, no production database, no real
  market data, no live credentials.
- No test was weakened, skipped or deleted; `docs/sprints/sprint-manifest.json` untouched;
  `src/indodax_lab/models/`, `src/indodax_lab/strategies/`, `src/indodax_lab/contracts/` untouched.
- No `git push`, no `git merge`, no worktree/branch deletion, no production activation.

## Deviations / design decisions

1. **`import_yaml` / `export_yaml` added to `PipelineService`.** Not part of the five-method
   interface in the sprint spec, but required by `BOT-TRADE-PROGRAM.md` ("one PipelineManifest for
   form/YAML/MCP"). Additive; the declared five methods are unchanged.
2. **`ValidationReport.evaluation_order`.** Additive field beyond the three declared fields;
   required by spec implementation Step 4 ("Compile stable topological evaluation order"). Kahn
   order with a min-heap keyed on `node_id`, `()` when a cycle exists. No consumer yet (RP-01).
3. **`__init__.py` files.** The spec's `FILES` list names only three files; the brief explicitly
   allows "`__init__.py` files only as needed for package imports".
4. **Node kind is not statically pinned to a model architecture.** RW2-02 currently allowlists only
   `m01_logistic`; binding is enforced through `component_refs` + `load_verified`, so architecture
   correctness is checked by RW2-02 at resolution time rather than by a RW2-03 graph rule.
5. **Binding rule: `node_id` must equal the referenced component's `id`.** `PipelineNode` has no
   `version` field, so the unique matching reference pins the version; multiple versions of one id
   are ambiguous and reject (`..._COMPONENT_REF_DUPLICATE`).
6. **Soft-vote `inputs` is sorted by `canonicalize`.** The list is a set of voters and carries no
   order semantics; sorting keeps the digest independent of presentation order for that field too.
7. **Terminal kinds.** `exits` and `execution_policy` are exempt from the unconsumed-output rule —
   per `CONTRACTS.md` the decision DAG terminates in intents, and execution policy configures the
   adapter and "is not a second runtime" (hence `PIPELINE_EXECUTION_POLICY_EDGE` for any edge).
8. **Abstain attribution.** Ensemble-declared-input failures attribute `node_id` to the ensemble
   node (`port = ProbabilityVector`, per AC2); a failing model node's own binding/resolution
   failure attributes `node_id` to that model node. Both use
   `PIPELINE_ABSTAIN_MISSING_MODEL_OUTPUT`.
9. **Known gap, raised for the coordinator.** `CONTRACTS.md` requires soft voting to use "ordered
   compatible model outputs". RW2-03 can enforce this only as far as it is statically declared:
   every ensemble input must be an ML/DL node whose verified model resolves through RW2-02 (which
   validates `ordered_feature_schema` against the bundle). `ModelManifest` declares no output
   dimension or class order, so no static cross-model equality rule exists at this layer; runtime
   enforcement belongs to the RP-01 consumer. Not implemented here — needs a coordinator decision
   on whether a new contract field is warranted (change-control CR if so).

## Migration / rollback

- Additive-only: no schema migration, no data backfill, no existing manifest or store altered.
- Rollback = delete the new `src/indodax_lab/pipelines/` and `tests/unit/lab/pipelines/` packages;
  no other file depends on them yet, so no compatibility adapter is required.
- Draft/publication tables are created on demand in the caller-supplied path; tests always use a
  temporary namespace. No production database is touched.

## Pending external gates

- Independent review of `9921b31` - not dispatched by the owner; coordinator assigns.
- No production activation, deployment, push or merge is authorized by this sprint.
- RP-01 (runtime consumer of `evaluation_order` and the resolved refs) is out of scope.
- The `CONTRACTS.md` "ordered compatible model outputs" decision (deviation 9) is pending.

## Independent task review record (2026-09-28)

- Reviewed SHA: `b3bc01f3853f24bbcae3ba02b8533df51bc5ce66` (tip of
  `feat/rw2-03-typed-declarative-pipeline-composer`; code
  `9921b31607cb533f1c50c0bb5425f562af7cd99e`), delta against BASE `e9f6a34`;
  6 files, +1876/-0.
- Reviewer: independent session `ses_f186d242cffeE2HA37Ie73VmQh` (did not
  implement the change). Verdict: **Spec PASS (AC0-AC5), task quality
  Approved-with-Minors — 0 Critical, 0 Important, 3 Minor.**
- Evidence re-run by the reviewer in the sprint worktree: focused
  `test_pipeline_validation.py` 9 passed (all 6 manifest names verbatim);
  `tests/unit/lab` 1483 passed; `ruff check` on both new packages clean;
  scope exactly the 6 owned files; worktree clean. Independent YAML probes
  (read-only): dup→PIPELINE_YAML_DUPLICATE_KEY, `!local`→FORBIDDEN_TAG,
  unknown→UNKNOWN_FIELD, deep→TOO_DEEP, 70KB→TOO_LARGE, roundtrip/export/
  MCP/reorder digests all equal. Declared 5-method/3-field contract exact
  (additive `evaluation_order` only).
- Concern rulings: C1 "ordered compatible model outputs" RULED NOT blocking —
  CONTRACTS.md's normative field table gives ModelManifest no output
  dimension/order field (only ordered_feature_schema for inputs), so there is
  nothing static to compare; runtime-resolution enforcement (verified
  resolution, declared-input coverage, weight/threshold rules) plus
  abstain-on-missing-output satisfies FR2/AC2; inventing a static rule would
  violate CONTRACTS.md:3. Mitigation logged: an incompatible-output ensemble
  could still validate — RP-01 (DONE, historical) must enforce output-compat
  at evaluation time where the data exists; recorded here as a cross-sprint
  constraint for any future RP-01 change (RP-01 evidence itself untouched).
  No CR needed unless a static contract field is desired. C2 additive API
  justified (spec Step 4 + BOT-TRADE-PROGRAM:121), do not trim. C3 narrow
  except-clauses acceptable fail-loud (declared failures covered, no store
  mutation before validation). C4 acknowledged (workspace.json IDE noise).
- Backlog (Minor, non-blocking): (1) handoff/report prose misnames the
  runtime-blocked error class — correct the name; (2) handoff attributes the
  1 warning to langsmith, observed run shows s07 FutureWarning — one-line
  correction; (3) duplicate-key check tracks only ScalarNode keys — optional
  hardening to track all keys (still fail-closed downstream).
- Integration: merged to `dev` via merge commit (reviewed content
  byte-identical, no conflicts).
