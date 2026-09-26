Status: DONE

## Identity

- Sprint ID: RW2-01 — Durable versioned strategy registry
- Owner: Codex
- Independent reviewer: `/root/docs_review` (Round 3 PASS)
- Base SHA: `12fd468a99fe4615f7789204dad3694bd42fbd89`
- Code SHA: `e2471a0d4112868454949ecf37b2dd843b281421`
- Branch: `feat/feat-02-finalization`
- Environment: Windows, Python 3.12.13, `C:/Users/User/miniconda3/envs/ML/python.exe`

## Scope Delivered

- Added SQLite-backed draft revisions, compare-and-swap updates, immutable publication and read-back integrity checks for manifest and source bytes.
- Bound source identities to bytes read from statically imported, allowlisted C02/C07 modules. YAML uses `safe_load`; unrecognized module/expression fields reject.
- Exposed versioned parameter schemas, required feature metadata and content-versioned exit contract metadata through `StrategyService.component_metadata()`. Manifest YAML import/export uses the same typed contract.
- Added declarative BTC-C07, ETH-C02 and SOL-C02 seed records with pair-specific parameters. Existing strategy and risk defaults are copied from the checked-in C02/C07 YAML files; no pair-to-code dispatch was added.
- Clone retains its published parent reference and gets a unique opaque version suffix so subsequent parameter edits can publish without modifying the parent.
- Existing `StrategyRegistry.register/get` behavior remains available. Same-version identity now binds every `StrategySpecification` field, not only its parameters.
- `register_builtin()` now executes C02/C07 with a defensive copy of the supplied specification; strategy ID, sizing and indicator parameters therefore remain bound to the registration.
- The actual allowlisted function is captured in the registered wrapper. Its code/defaults/closure are included in the wrapper logic hash; same-version re-registration with a replaced implementation rejects.

## Actual Paths

- `src/indodax_lab/strategies/base.py`
- `src/indodax_lab/strategies/registry.py`
- `src/indodax_lab/strategies/store.py`
- `src/indodax_lab/strategies/__init__.py`
- `configs/strategies/seeds.yaml`
- `tests/unit/lab/strategies/test_versioned_registry.py`
- `tests/unit/lab/strategies/test_c02.py`
- `tests/unit/lab/strategies/test_c07.py`

## Acceptance Evidence

- AC0: valid same-version parameter and source-byte changes reject; full specification metadata changes reject in the legacy registry.
- AC1: stale revisions reject within one service and across two store connections. SQLite publication failure injection confirms the draft remains editable and no partial publication becomes visible.
- AC2: unknown source identities, unlisted components and executable YAML module fields reject. No user-controlled module import occurs.
- AC3: clone records its exact parent; clone edits publish under a new version while the parent artifact remains unchanged.
- AC4: schema/feature/exit metadata, YAML round-trip and durable reopen are covered; seed records preserve the selected pair and checked-in parameter/risk defaults.
- Source artifact corruption probe rejects read-back with `STRATEGY_SOURCE_HASH_MISMATCH`.

## Checks

- `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest tests/unit/lab/strategies -q -p no:cacheprovider` — 68 passed on corrected code SHA.
- C02/C07 custom-registration regressions verify candidate identity and quantity, custom C02 ATR stop, and pinned callable behavior under module replacement.
- `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest -q -p no:cacheprovider` on code SHA `ab8fff6b2a7a64dbc84388f03f2b90bf05e4691c` — 1,121 passed, 2 platform-specific skipped, 4 warnings, 30.42s.
- `C:/Users/User/miniconda3/envs/ML/python.exe -m ruff check src/indodax_lab/strategies/registry.py` — passed. Existing unrelated lint findings remain in test modules.
- `rtk git diff --check` and staged diff check — passed before code commit.

## Migration, Deviations and External Gates

- No prior durable strategy store or DB rows existed; the in-memory `StrategyRegistry` remains compatible. SQLite uses transactional local storage without shared cross-host WAL.
- `StrategyManifest` has a generic `parameters` mapping and no dedicated pair or risk-profile fields. Pair scope and the legacy risk profile are retained inside the validated, versioned parameter payload; adding shared manifest fields was not required.
- The existing repository has no GUI or MCP server module to wire. The service exposes structured metadata and safe YAML methods for those adapters; transport integration remains with their owning tasks.
- Seed registration and registry publication do not qualify candidates, activate a runtime, grant Production authority, or prove profitability. Source/license, current venue cost, resource and runtime qualification gates remain external.
- No real market data, credentials, production DB, live account or host was accessed.

## Review Rounds

- Round 1: CHANGES_REQUESTED on `ab8fff6b2a7a64dbc84388f03f2b90bf05e4691c`; built-in execution ignored supplied specifications.
- Round 2: CHANGES_REQUESTED on `43691811731a840e9642c1f09e1c0ebcd5e0cb75`; runtime lookup could execute a replacement callable.
- Round 3 fix commit: `e2471a0d4112868454949ecf37b2dd843b281421`; exact-SHA independent review pending.
- Round 3 review: PASS on `e2471a0d4112868454949ecf37b2dd843b281421`; no Critical/Important findings. Reviewer verified implementation pinning, immutable spec binding, mutation regression and prior publication/CAS/corruption/clone/allowlist boundaries.
