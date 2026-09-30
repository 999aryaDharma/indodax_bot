# RW7-01 Handoff — Read-only QuantOps MCP boundary

Status: SUBMITTED FOR INDEPENDENT REVIEW (implementation complete; coordinator dispatches reviewer, manifest untouched).

## Identity

- Sprint: RW7-01 — Read-only QuantOps MCP boundary
- Implementation owner: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- Independent reviewer: UNASSIGNED (coordinator dispatches; implementer cannot self-approve)
- Branch: `dev` (shared checkout; recommended `feat/rw7-01-...` not used — isolated additive paths, no other owner on these files)
- Code SHA: `7f6a70b` — `feat(rw7-01): read-only quantops mcp boundary`
- This handoff is the evidence follow-up; it contains no code changes.
- Environment: Windows (win32), Python 3.14.0, pytest 9.0.3, ruff 0.16.9, `D:\bot-trading`

## Files and contracts

- `src/indodax_lab/mcp/server.py` (NEW) — `QuantOpsReadServer` allowlisted dispatcher.
  Unknown tools (including `submit_real_order`/`withdraw`/`direct_promote_live`) reject
  with `TOOL_UNKNOWN`. Every response carries `schema_version` (`rw7-01-v1`), `request_id`,
  and exactly one of `data`/`error`. Every call appends a redacted request/outcome audit
  record (secret-looking keys → `***`, long strings truncated). No transport dependency.
- `src/indodax_lab/mcp/read_tools.py` (NEW) — 12 tools mapped to existing public service
  reads (duck-typed, zero service-implementation imports): `list_pairs` (capability
  pairs/timeframes), `find_dataset`/`list_datasets`/`get_dataset` (`DatasetRegistry`
  find/catalog-read/get), `list_strategies`/`get_strategy` (`component_metadata`/get),
  `list_models`/`get_model` (`list_models`/`load_verified`, readiness rows carry
  `runtime_eligible` + explicit `reason`), `get_pipeline` (store `get_published`),
  `get_backtest_status`/`get_backtest_result`/`compare_experiments` (experiment
  `get`/`result`/`compare`). Per-tool typed schemas; traversal/SQL/code payloads are
  treated as data and rejected with `DATA_INVALID`. Full `ArtifactRef` (incl. sha256)
  required for every `get_*`: references are verified before use, never trusted by
  name (CONTRACTS.md identity rule). Missing service → `SERVICE_UNAVAILABLE`, never
  synthetic success; missing refs → `NOT_FOUND`. Deep-copied listings; no raw bytes
  on wire (byte payloads represented by sha256/length only).
- `tests/security/test_quantops_boundary.py` (NEW) — 5 AC-mapped tests, fake
  provider + tmp state only, store/catalog bytes hashed before/after every read path.
- Untouched: `docs/sprints/sprint-manifest.json`, `docs/.obsidian/workspace.json`,
  everything outside the three owned paths.

## Acceptance evidence (behavioral RED observed, then GREEN)

- Setup RED: modules absent → collection error (not proof).
- Behavioral RED (throwaway canned-wrong stub exporting the real names, never committed):
  `5 failed` — `KeyError: 'pairs'` / assertion failures on allowlist, rejection codes,
  and unavailable reasons.
- GREEN: `python -m pytest tests/security/test_quantops_boundary.py -q -p no:cacheprovider`
  → `5 passed`, exit 0.

| AC | Test | Assertion |
|---|---|---|
| AC0 | `test_rw7_01_0` | `find_dataset`/`get_dataset` return the published registry ref sha/manifest; `list_pairs`/`list_strategies` (C02/C07) match service truth; ghost experiment → `SERVICE_UNAVAILABLE`; all store bytes identical before/after |
| AC1 | `test_rw7_01_1` | `submit_real_order`/`withdraw`/`direct_promote_live` + unknown tool → `TOOL_UNKNOWN`, no data; allowlist exact; fresh-interpreter probe loads zero live/production/execution/venue/order/withdraw/credential modules; AST import scan of both mcp modules clean |
| AC2 | `test_rw7_01_2` | 12 traversal/SQL/code payloads (`../`, absolute paths, `; DROP`, `SELECT`, `__import__`, `eval(`, `${}`, `{{}}`, pickle, 600-char) → `DATA_INVALID` across find/get/compare; non-mapping params and unknown param keys → `DATA_INVALID`; store bytes unchanged |
| AC3 | `test_rw7_01_3` | All 12 tools with valid-shaped params and no services → `SERVICE_UNAVAILABLE` with a naming message, `data is None` in every case |
| AC4 | `test_rw7_01_program_4` | `list_pairs` covers `CollectionCapabilities.defaults()` (`btc_idr`, `1h`); stub model row surfaces `runtime_eligible False` + `MODEL_NOT_VERIFIED` reason; missing model/pair services → explicit `SERVICE_UNAVAILABLE` naming the service |

## Gates

1. Focused: `tests/security/test_quantops_boundary.py` → 5 passed, exit 0.
2. Affected subsystem: `tests/security` (incl. pre-existing `test_lab_boundaries.py`) → 9 passed, exit 0.
3. `ruff check` on all 3 touched files → clean (6 own findings fixed, re-verified GREEN after).
4. `git diff --check` → exit 0.
5. No skips. No network/credentials/live DBs. Fake clock injectable; tmp state only.

## Self-review notes and deviations

- Deviation (recorded, additive): `src/indodax_lab/mcp/` has no `__init__.py`; namespace-package
  import resolves under the repo's `pythonpath = ["src"]` pytest config (proven by the green
  run). Adding one would touch an unlisted path; reviewer/coordinator may request it.
- Deviation: `list_datasets` reads the registry's existing catalog listing in-memory
  (`all_entries`, else the catalog's own read method) with a 500-row bound + `truncated`
  flag. Read-only snapshot, deep-copied; zero-mutation proven by byte-hash assertions.
- Deviation: schema validated before service resolution (fail-closed input handling); a
  schema-invalid request to an unwired tool answers `DATA_INVALID`, not `SERVICE_UNAVAILABLE`.
- No MCP package install: the boundary is plain Python callables per the sprint brief
  ("NO MCP package install if it needs a new dependency"). A real MCP transport needs a
  later CR (noted in `read_tools.py` module docstring).
- Shared-checkout incident (no content impact): a concurrent sibling worker's staged files
  were once swept into an intermediate commit; repaired via soft-reset with sibling content
  preserved byte-identical in the working tree. Final code commit `7f6a70b` verified
  byte-identical to the working tree (SHA-256 per file) and contains exactly the 3 owned
  paths. A transient mislabeled commit is dangling/unreferenced. Coordinator: consider
  isolated worktrees per AGENTS.md to avoid recurrence.
- Capability gaps: global Caveman/Ponytail/RTK tooling unavailable in this host; continued
  with repo rules (`git`, `Select-String`, `ruff`, `pytest -p no:cacheprovider`).
- No subagent dispatch; no manifest edit; no push/merge/deploy.

## Next eligible consumers

RW7-02 (unblocked on code; still subject to coordinator DAG + review PASS).

## Pending external gates

- Independent review of `7f6a70b` — not dispatched by the owner; coordinator assigns.
- Real MCP transport (if wanted) requires a later CR + reviewed dependency change.
- No production activation, deployment, push, or merge authorized by this sprint.
