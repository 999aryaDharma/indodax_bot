# ADR-012 — Runtime ownership and storage layout

Status: Owner-directed target architecture recorded 2026-09-24. This decision guides new code and planning; broad migrations require their own scoped CRs and evidence.

## Operating areas and authority

The product has three operational areas and two financial authorities:

- **Production** owns selected candidates, shared real capital, real orders, ledger and reconciliation.
- **Shadow** runs immutable candidates on realtime data, virtual portfolios and tournaments. Shadow is an operating area within Research authority and never owns Production money or risk state.
- **Research** owns datasets, strategy composition, training, backtests and evaluation. Research authority includes its isolated Shadow workloads.

One shared trading engine owns candidate evaluation, portfolio sizing, risk, exits, OMS and accounting semantics across paper/shadow/live adapters. Runtime wiring may select adapters and policies; it must not fork shared rules into three implementations. Shared modules never import a Production runtime or acquire credentials.

Use `production` consistently for the live system. Avoid `main` as a runtime or API authority name where it can be confused with an entrypoint or Git branch. The new operator-authenticated read composition requires `PRODUCTION_NAMESPACE=production`; existing legacy namespaces are not migrated by this decision.

## Code ownership target

Add or move code gradually toward:

```text
src/indodax_lab/
├── runtimes/production/  # Production wiring and lifecycle
├── runtimes/shadow/      # agents, cohorts and Shadow lifecycle
├── runtimes/research/    # experiment job wiring
├── contracts/ strategies/ features/ portfolio/ risk/ execution/ market/
├── data/ models/ backtest/ evaluation/ api/ cli/
```

The runtime folders connect shared modules. Existing shared components remain in place until a scoped refactor proves behavior-preserving ownership changes. The Tailscale Production API composition is placed under `runtimes/production/` as the first small application of this rule.

## Storage target

Target root (not an instruction to move existing state):

```text
/srv/storage/trading-bot/
├── production/{releases,state,audit}/
├── research/{market,datasets,artifacts,experiments}/
└── shadow/{agents,cohorts,portfolios}/
```

Store each immutable dataset once; experiments reference version/hash. Shadow agents may share compatible feed/features but have isolated financial state. Production receives a verified release copy, never mutable Research drafts. Secrets live in protected configuration outside datasets and Git. Paths are absolute and namespace-specific; permissions and tests enforce the boundary. No live Production state is moved under this decision.

## Migration order

1. Inventory module ownership and import directions.
2. Define absolute per-area config/state roots.
3. Route only new outputs to the approved roots.
4. Migrate existing data only through a separately reviewed checksum/rollback procedure.
5. Refactor code ownership/imports incrementally after migration evidence.

Do not move the whole repository or running Production state as a cleanup step. Qualify ASUS Production + Research mixed load before deployment changes; Lenovo remains ML/DL training and tuning.
