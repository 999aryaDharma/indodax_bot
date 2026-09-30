# RW5-01 handoff — isolated durable forward-shadow agents

Status: REVIEW (implementation complete; independent review required)

## Identity

- Sprint: RW5-01 — Isolated durable forward-shadow agents
- Implementation owner: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- Independent reviewer: UNASSIGNED
- Branch: `dev` (shared checkout; only owned paths staged/committed)
- Code SHA: `5ccea35` — `feat(rw5-01): isolated durable forward-shadow agents`
- This handoff is the evidence follow-up to `5ccea35`; it contains no code changes.
- Environment: Windows, Python 3.14.0, pytest 9.0.3, ruff (repo pinned), `D:\bot-trading`
- Dependencies DONE verified at claim: RW4-01, RP-05 (handoff evidence read).
  S09-01 is IN_PROGRESS; only its LiveShadowEngine context (risk-period
  isolation, no shared-wallet resets) was consumed as background, not as code.
- No subagent dispatch; no manifest edit; no push/merge/deploy.

## Files and contracts

- `src/indodax_lab/paper/agents.py` (NEW) — `AgentFactory`:
  `register(manifest)`, `start(id)`, `pause(id)`, `retire(id)`,
  `recover(id) -> AgentRecoveryReport`, `get(id)`, plus `process(id, event)`
  event routing, `apply_fill(id, fill)` fill routing, `list_agents()`,
  `count()`. Each agent owns one `ExecutionStateStore` file
  (`<root>/stores/<namespace>.db`, immutable starting cash) and one
  per-agent `RuntimeKernel` over simulator/shadow venues; candidate binding
  is verified at register (`AGENT_CANDIDATE_UNRESOLVED` /
  `AGENT_CANDIDATE_IDENTITY_MISMATCH`); namespace is UNIQUE
  (`AGENT_NAMESPACE_COLLISION`); same-identity different-bytes republication
  rejects (`AGENT_CANDIDATE_REPLACEMENT_REJECTED`), identical bytes are
  idempotent. Lifecycle REGISTERED→RUNNING↔PAUSED→RETIRED; conflicting event
  bytes or store faults halt only the affected agent with an incident ref;
  `recover()` runs store recovery and lands PAUSED (HALTED when the store
  latched halt). Admission bound `max_agents` defers with
  `AGENT_ADMISSION_DEFERRED`. The module never imports a live venue.
- `src/indodax_lab/cli/shadow.py` (NEW) — research-only CLI over a factory
  root: `list` / `show` (read-only queries), `replay --feed-file` (fake
  canonical-feed JSON routed into RUNNING agents; CLI behavior defaults to
  no-intent coverage advance, never invents strategies, never resolves live
  venues).
- `tests/integration/lab/test_agent_isolation.py` (NEW) — 7 AC-mapped tests
  with fake resolvers/venues/clocks and tmp_path only.
- `src/`: otherwise untouched (Modify: None honored — no existing file edited).

## Acceptance evidence (behavioral RED observed, then GREEN)

- Setup RED: agents module absent → collection `ModuleNotFoundError` (not proof).
- Behavioral RED (temporary uncommitted mutation, reverted before commit):
  `_store_path` forced to one shared `shared.db` → `test_rw5_01_0` FAILED
  with B holding A's `0.001` BTC position (isolation violation caught);
  `test_rw5_01_1` still passed. Mutation reverted; never committed.
- GREEN: `python -m pytest tests/integration/lab/test_agent_isolation.py
  -q -p no:cacheprovider` → `7 passed`, exit 0.

| AC | Test | Assertion |
|---|---|---|
| AC0 | `test_rw5_01_0` | A fill moves A cash/positions only; B cash/positions/orders/cursor untouched; B no-op processing cannot move A; no `indodax_trading` in new modules |
| AC1 | `test_rw5_01_1` | Shared namespace → `AGENT_NAMESPACE_COLLISION`; same-id new bytes → `AGENT_CANDIDATE_REPLACEMENT_REJECTED`; prior digest/namespace kept; identical bytes idempotent |
| AC2 | `test_rw5_01_2` | Fresh factory over same root restores RUNNING + cursor; recover → PAUSED; duplicate replay ACKs with equal cash/positions/orders/revision |
| AC3 | `test_rw5_01_3` | Same-ID different-bytes event → `AGENT_EVENT_CONFLICT`, A HALTED with incident, prior evidence kept, further processing refused; B completes both events |
| AC4 | `test_rw5_01_4` | Retire keeps digest/cursor/cash/orders queryable; processing rejects `AGENT_RETIRED`; CLI `show`/`list` read back the retired record |
| AC5 | `test_rw5_01_program_5` | Partial fill (0.0004) moves A wallet only; stop-gap bar emits A SELL exit only; restart: duplicate fill no-op, replay adds no orders |
| AC6 | `test_rw5_01_capacity_6` | `max_agents=2` admits 2, third defers `AGENT_ADMISSION_DEFERRED`; paused A keeps cursor while B advances; recover+start resumes A to identical cursor |

## Gates

1. Focused: 7 passed, exit 0.
2. Affected: `test_runtime_adapters.py + test_runtime_parity.py +
   tests/unit/lab/paper + tests/unit/lab/execution +
   tests/unit/lab/evaluation` → `284 passed`, exit 0.
3. `ruff check` on all three new files → clean.
4. `git diff --check` → exit 0 (only sibling-worker CRLF notices elsewhere).

## Self-review notes and deviations

- Kernel feature/exit windows (`_bars`/`_exits`) are rehydrated from the
  durable inbox journal on kernel rebuild (fix round 1/5); restart
  durability covers envelopes, cursor, OMS/ledger/journal AND the
  feature/exit windows, proven by `test_rw5_01_2_window_rehydration`.
- `AgentFactory` takes injected `candidate_resolver` / `behavior_resolver` /
  `venue_factory` ports; production candidate wiring (RW4-01 registry →
  `CandidateRuntime.load`) is operator/integration scope, recorded for the
  coordinator. Test doubles use `SimpleNamespace` runtimes shaped to the
  RP-04 kernel port (`plan_digest`, `candidate_digest`, `evaluate`).
- AC6 offline portion only: the admission slot bound + defer reason +
  pause-with-gap + durable resume are proven; the measured ASUS mixed-load
  host artifact is explicitly pending and no throughput claim is made.
- No credentials, live network, real orders, production paths, or real
  runtime DBs touched. Sibling-worker dirty paths
  (`deploy/release-lab.sh`, `docs/.obsidian/workspace.json`,
  `src/indodax_lab/verification/*`, `src/indodax_lab/mcp/`, unrelated test
  files) were left untouched and unstaged.
- Known RP-04 inherited quirk (not fixed here, out of scope): kernel
  `_intent_to_order` truncates intent IDs to a 12-char head; fixtures vary
  the ID head per agent/event to keep order identities distinct.

## Fix round 1/5 (review CHANGES_REQUESTED → addressed)

- Code SHA: `5ccea35` reviewed; fix commit SHA recorded below.
- Scope: the 3 Important findings only; 5 Minors deferred to final review
  per reviewer instruction (not fixed here).

### Finding 1 — get() wrote to the registry (ADDRESSED)

- `AgentFactory.get()` no longer executes `UPDATE agents SET cursor`; it is
  a pure read of the stored row (`src/indodax_lab/paper/agents.py`, `get`).
  Cursor re-sync from the durable store is now the explicit
  `sync_cursor()` method; write paths (process/pause/retire/recover) still
  persist the cursor themselves. CLI `show`/`list`
  (`src/indodax_lab/cli/shadow.py`) therefore perform zero writes.
- Covered by: all existing cursor assertions in `test_rw5_01_0..4`,
  `test_rw5_01_program_5`, `test_rw5_01_capacity_6` (cursors are
  process-persisted, so pure reads return identical values).

### Finding 2 — restart window rehydration (ADDRESSED via rehydration)

- `_ensure_kernel` now calls `_rehydrate_kernel`, which rebuilds the
  in-memory feature window (bounded, last-N), exit state (deterministic
  replay of `advance_exit_state`), cursor (`MarketCursor`) and risk
  revision from the durable `events_inbox` journal. Bars are deserialized
  to real `MarketBar` observations in sequence order; an undecodable bar
  fails closed with `AGENT_WINDOW_REHYDRATE_FAILED` — no invented state.
- The prior handoff deviation note ("feature-window rehydration not
  implemented") is superseded by this fix.
- Covered by: new `test_rw5_01_2_window_rehydration` — a restarted agent
  observing a new event sees the same bar count (3) and equal exit state
  as an uninterrupted control agent; duplicate replay re-evaluates
  nothing. Behavioral RED proven: with the rehydrate call disabled, the
  test FAILS (resumed window empty); with it, GREEN.

### Finding 3 — real RW4-01 registry → CandidateRuntime binding (ADDRESSED)

- New `test_rw5_01_5_registry_bound_candidate` wires the real
  `CandidateRegistry` (dict-backed CAS): SUCCESS experiment → `package` →
  `get` identity check → `verify` lineage check → real
  `CandidateRuntime.load` with a TA pipeline and registered strategy —
  into the agent `register` path (`candidate_ref` =
  `manifest.to_artifact_ref()`, digest-checked against
  `verified.candidate_digest`). One real evaluator intent becomes exactly
  one kernel order; restart + duplicate replay + new-event processing all
  pass feature identity against rehydrated real bars.

### Fix-round gates

- `python -m pytest tests/integration/lab/test_agent_isolation.py -q
  -p no:cacheprovider` → `9 passed`, exit 0.
- Affected: runtime adapters + parity + unit paper/execution/evaluation →
  `284 passed`, exit 0.
- `ruff check` on all three touched source/test files → clean.
- `git diff --check` → exit 0.

## Next eligible consumers

RW5-02, RW6-01, PM-06 (unblocked on code; still subject to coordinator DAG
+ independent review PASS + external capacity gates).
