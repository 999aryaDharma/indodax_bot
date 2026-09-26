# S09-01 — Tail risk abstention

## Metadata

Status: IN_PROGRESS

Priority: P1 | Type: feature | Domain: strategies | Portfolio: EXTENSION

Implementation Owner: Codex /root | Independent Reviewer: /root/docs_review

Recommended Branch: `feat/s09-01-tail-risk-abstention`

Requirements: FR-08 | Legacy tasks: Catalog extension / operational gap identified in audit

External gates: Portfolio backlog activation by owner; not in default scheduler

Implementation artifacts named below are planned unless present in baseline; WIP does not satisfy acceptance.

## Goal

Integrasikan tail-risk abstention pada Research risk-authority boundary. S09 tidak menjadi alpha strategy atau order authority.

## Why This Sprint Exists

Tanpa kapabilitas ini, kontrak `S09-01` belum dapat dibuktikan dan downstream tidak boleh mengasumsikan hasilnya tersedia. Nilai spesifiknya: uncertain or breached risk evidence blocks new exposure while registered exits stay enabled.

Direct consumers: Release or owner-reviewed research comparison; no required downstream implementation.

## Depends On

- STRAT-01 — Declarative strategy protocol

## Unlocks

No mandatory dependent sprint.

## Required Reading

- `AGENTS.md`
- `docs/specs/00-master-product-technical-spec.md`
- `docs/specs/10-strategy-catalog-and-protocol.md`
- `docs/specs/20-testing-strategy.md`
- `docs/decisions/ADR-002-temporal-and-accounting-semantics.md`
- `docs/specs/14-shadow-portfolios-and-promotion.md`
- `docs/research/dataset-feature-contracts.md`
- `docs/sprints/handoffs/STRAT-01-HANDOFF.md`
- `docs/decisions/CR-S09-risk-gate-ownership.md`

## Current Context

New capability; dependencies must be DONE before implementation.

- Dependency STRAT-01 supplies: StrategySpecification + DecisionFrame -> list[SignalIntent]; ID/version/family/timeframes/risk/split required.
- CR-S09 Research-only risk-authority boundary is owner-approved (2026-09-27). An opt-in gate now exists in the existing `RiskEngine`; it accepts only complete approved versioned policy/evidence and returns an assessment, never an order. Preserve breach periods across separately approved resets, block new BUYs on unknown/stale data or a breach, and leave eligible protective exits available. Numeric pump-gap threshold and data-age limit remain unresolved; no candidate evaluation/qualification until a versioned policy and pump-gap producer/provenance are defined. Do not add a second risk authority or touch Production/runtime state.

## In Scope

- Research-only gate uses the existing risk authority; no second risk engine or Production integration.
- Unknown/stale risk evidence and a configured risk breach block new BUY exposure; eligible protective exits remain available through the registered path.
- A separately authorized new risk period starts only after positions are closed, uses reconciled remaining equity as its opening capital, and preserves prior breach-period records and closed trades across restart/reset.
- Define the owning interface, specific fixtures, diagnostics and migration evidence required by these behaviors.

## Out of Scope

- Kapabilitas downstream: track riset atau release lain.
- Mengubah evaluator gates atau menambah retry/search budget untuk membuat hasil lolos.
- Auto-trading uang nyata, UI baru, dan refactor modul yang tidak dibutuhkan acceptance.

## User / Actor Behavior

Given versioned Research risk evidence, when the owning risk authority evaluates it, then it either admits eligible new exposure under an approved policy or blocks it with an explicit reason; the capability never creates orders.

Given input tidak valid pada acceptance boundary di bawah, when diproses, then hasil ditolak/ditandai eksplisit tanpa menciptakan successful downstream artifact.

## Functional Requirements

0. **S09-01-FR0:** Research gate integrates with the existing risk authority and never creates alpha intents or orders.
1. **S09-01-FR1:** Unknown/stale data or configured breach blocks new BUY exposure; eligible protective exits remain available.
2. **S09-01-FR2:** Risk-period reset requires separate explicit operator approval, no open positions, uses remaining portfolio equity as opening capital, and preserves prior breach history.
3. **S09-01-FR3:** Missing policy thresholds or pump-gap provenance fail closed and block qualification.

## Domain Rules / Invariants

Available pump gap and illiquidity state blocks new BUY risk through the existing Research risk authority; it does not emit strategy alpha or direct orders.

Global causality, identity, exact accounting and paper-only constraints apply; tidak ada exception lokal yang mengizinkan pengubahan histori.

## Architecture / Design Contract

Layer owner: existing `RiskEngine`, opt-in for Research only, and its Research-only durable state boundary. Consume only causally available, versioned evidence and reservation-aware exposure. The gate returns a risk assessment and cannot create intents/orders. Side effects remain in the existing adapter/repository; no HTTP in risk calculation. No production caller opts in.

Pump-gap threshold and evidence-age limits are intentionally unset until a versioned Research policy and registered producer/provenance are approved. Without a complete approved policy, evidence, and risk-period identity, opted-in new BUY evaluation fails closed and S09 is not qualification eligible. Never infer values from Production policy. Existing eligible protective exits bypass this additional gate and continue through the existing registered path. The current gate contract does not register or qualify a producer and is not wired to a running agent.

Jangan menciptakan layanan paralel bila fungsi ekuivalen sudah ada; perubahan dependency direction atau persistence material memerlukan ADR.

## Planned Files / Artifacts

Implementation must adapt to the existing Research risk authority and durable state store. Do not add strategy config/module artifacts unless later evidence shows the strategy protocol is required.

Path baru adalah panduan, bukan bukti file sudah ada. Periksa file ekuivalen sebelum membuat modul baru; catat path aktual pada handoff.

## Interfaces & Contracts

The owning interface is the existing Research risk authority and durable store. Exact fields, units, provenance and versioning must be frozen before an evaluable policy is enabled.

Input harus membawa identity dan versi yang disebut di atas. Output memisahkan hasil valid, abstain/excluded/blocked yang sah, dan error teknis. Nilai unknown tidak boleh dikonversi ke nol. Pin enum/field/unit pada contract test; API baru tidak boleh hanya ditulis sebagai contoh tanpa implementation/test.

## Data / Persistence Impact

Research risk gate is stateful only at the approved persistence boundary; it does not produce alpha intents.

Tidak ada implicit migration database legacy. Artifact/file additions pada scope di atas diberi version/hash. Jika implementasi ternyata membutuhkan schema mutation, revisi migration section melalui CR sebelum melakukannya.

## API / External Contract Impact

Interface utama berupa Python contract, file artifact atau CLI pada Planned Files. Bila CLI diperkenalkan, dokumentasikan --help, required inputs, structured outcomes dan dry-run; no external HTTP API is introduced.

No unlisted provider contract changes are authorized by this sprint.

## UI / UX Behavior

Not applicable: no new graphical UI. Machine/report consumer receives explicit status and reason; no-data is distinct from a zero-valued successful result.

## Implementation Steps

S09-01-AC0 now has an opt-in `RiskEngine` contract and regression fixture with no order side effect. Complete the remaining acceptance, producer/policy qualification, and independent review; do not infer operational readiness from this interface slice.

1. Inspect dependency handoffs and actual module paths; confirm one owner and independent reviewer. Do not mark fresh code complete from historical evidence.
2. For `S09-01-AC1`, prove unknown/stale and configured breach inputs block new BUY while eligible registered exits remain allowed.
3. For `S09-01-AC2`, prove separately authorized reset after all positions close starts from remaining equity, survives restart and preserves the old period's breach and trade records.
4. For `S09-01-AC3`, prove absent policy/provenance fails closed and cannot produce qualification evidence.
5. Integrate through the public boundary using actual output of dependency fixture; verify the declared contract and failure outcome rather than mock call counts alone.
6. Run the relevant tests below, inspect diff and record output/exit/source SHA. Refactor only after the contract remains green.
7. Commit scoped code/tests; prepare handoff with acceptance-to-evidence links, migrations and deviations; submit exact SHA for independent review.

## Required Tests

Positive contract: **S09-01-AC0**, mapped test through the existing Research risk-authority interface; prove the valid configured policy path has no order side effect.

| Acceptance | Planned test identity / map to existing equivalent | Assertion |
|---|---|---|
| S09-01-AC1 | Map actual regression tests | Unknown/stale and breached inputs block new BUY; registered exits stay eligible |
| S09-01-AC2 | `test_shadow_new_risk_period_preserves_breaches_and_closed_trades`, `test_shadow_risk_period_reset_requires_closed_portfolio`, `test_shadow_failed_period_reset_restores_in_memory_state` | Authorized reset after positions close starts from remaining equity, preserves prior breach/trade history after restart, and restores old state after failed persistence |
| S09-01-AC3 | Map actual policy/provenance tests | Missing policy/provenance fails closed; no qualification output |

Unit/contract tests prove the listed inputs, outputs and guards. Integration tests pass real artifact/record output from prerequisite fixture into this capability. Stateful boundaries also require temp-root/DB failure-injection and retry tests; pure transforms use golden/future-perturbation instead of artificial concurrency tests.

At implementation, collect the mapped tests and run them by actual module path; no planned name is assumed to exist yet.

Record focused command and results; run affected regression gates. Shared-contract/migration/checkpoint/release changes require full suite. Follow `docs/specs/20-testing-strategy.md` for environment and optional-DL separation.

## Failure / Edge Cases

- Case 1: Unknown data quality fail closed. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 2: Existing exposure ditangani registered exit policy. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 3: Gate reset tidak menghapus historical breach. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Interrupted publish: preserve prior valid output and expose incomplete/failed status. For pure functions without publish, deterministic exception/result replaces this case.
- Same input on retry: no new semantic output/version or duplicate state transition.

## Security / Privacy / Safety

Strategies cannot mutate ledger, bypass risk or import live order API. Config implementation allowlist only.

Trust boundary assessment: no new public authentication surface; verified local input remains mandatory and existing secret/PII controls apply.

## Concurrency / Idempotency

Use the existing risk authority and Research persistence boundary; no local decision engine or independent authority.

## Performance Constraints

Bound resource use by the owning input batch/run/queue limits. Measure rows/events/trials and peak memory/latency on representative fixture; do not claim hardware capacity from unit tests.

Record baseline, identify algorithmic hotspot, then propose a versioned threshold for host activation. No fabricated elapsed-time acceptance. Research model search obeys ADR-003 budgets.

## Observability

Emit `S09-01` scope, input identities, output/run identity, config/policy version and reason code. For each listed guard, tests must assert the diagnostic identifies what was rejected without logging private payloads. Record elapsed/resource observations only outside content-addressed identities.

## Migration / Backward Compatibility

Freeze policy versions; retain immutable prior risk periods and breach history; never silently retune an active policy.

Existing code paths are preserved unless this sprint explicitly owns their behavior change. Material incompatibility requires documented consumers, schema/version transition and rollback evidence before review.

## Rollback / Recovery

Disable use of the new candidate/output version and keep the last verified compatible version. Do not overwrite historical artifacts; rebuild/retry from the same verified immutable inputs. For code-only pure changes, revert scoped commit after checking downstream compatibility.

## Acceptance Criteria

- [ ] **S09-01-AC0** Research gate integrates with the existing risk authority and cannot create orders or alpha intents. (Implementation present; review pending.)
- [ ] **S09-01-AC1** Unknown/stale evidence and configured breaches block new BUY exposure; eligible protective exits remain available. (RiskEngine contract tests present; runtime wiring/producer qualification and review pending.)
- [ ] **S09-01-AC2** New risk period requires separate explicit operator approval, requires positions to be closed, starts from remaining equity, and preserves prior breach-period and closed-trade records across restart.
- [ ] **S09-01-AC3** Missing/unapproved policy thresholds or pump-gap provenance fail closed and block S09 qualification; no Production values are inferred. (Missing/incomplete policy/evidence fails closed; registered producer and qualification path remain external gates.)
- [ ] Public contract matches this sprint and downstream can consume its actual verified output.
- [ ] Failure diagnostics are explicit and no forbidden side effect exists.

## Definition of Done

- [ ] All acceptance criteria mapped to evidence; no required tests skipped silently.
- [ ] Focused and affected integration/regression checks pass; full suite where required by scope.
- [ ] No unrelated capability or policy relaxation introduced.
- [ ] Contracts/docs updated if implementation reveals an approved deviation.
- [ ] Self-reviewed diff and handoff record contain exact source SHA, environment, commands and risks.
- [ ] Independent reviewer verifies spec and quality on that same SHA; no unresolved Critical/Important findings.
- [ ] Coordinator updates manifest and regenerates status/waves only after review PASS.

Historical import note: unchecked boxes describe the gate for future work/reverification; they do not replace imported DONE evidence.

## Reviewer Checklist

- Attempt to disprove: Unknown data quality fail closed. Inspect fixture and actual production path.
- Attempt to disprove: Existing exposure ditangani registered exit policy. Inspect fixture and actual production path.
- Attempt to disprove: Gate reset tidak menghapus historical breach. Inspect fixture and actual production path.
- Verify provenance and units at the boundary, not only test count or mock calls.
- Check downstream side effects, compatibility, state rollback and no scope creep.
- Verify budget, resource and paper-only policy are not bypassed.

## Commit Guidance

Branch: `feat/s09-01-tail-risk-abstention`. Commit: `feat(s09-01): tail risk abstention` for future implementation. Documentation changes use `docs(...)`. Never stage original Task15 WIP wholesale.

## Handoff Requirements

Create `docs/sprints/handoffs/S09-01-HANDOFF.md` from template. Record owner/reviewer identities, branch, code SHA, files, contracts, migration, RED/GREEN commands, exact test results, AC mappings, deviations and known risks. Specify next eligible consumers: none required. A code commit and later evidence commit must state their relationship explicitly.

## Ready-to-Run Implementation Prompt

```text
Implement S09-01 only: Tail risk abstention.
Read AGENTS.md, docs/sprints/strategies/S09-01-tail-risk-abstention.md and every Required Reading path listed in it.
Read sprint-manifest.json and verify dependencies DONE; check external gates before execution.
If status is historical DONE, do not rebuild: only reopen under a documented defect/change request.
Inspect actual files and any scoped WIP before creating equivalents.
Goal: Research-only tail-risk gating integrated with the existing risk authority, preserving breach history and keeping eligible exits available.
Contract: Unknown/stale or breached evidence blocks new BUY exposure; no strategy intent/order authority; absent versioned policy or pump-gap provenance fails closed.
Use behavior-driven RED -> GREEN for each AC, then affected integration/regression verification.
Never implement downstream capabilities, loosen gates, use real trading keys or modify live DBs.
Commit scoped changes, record exact SHA/commands/AC evidence in handoff, self-review.
Stop at REVIEW for an independent reviewer; coordinator alone records DONE after PASS.
If blocked, report root cause and preserve work; do not fabricate test or review evidence.
```
