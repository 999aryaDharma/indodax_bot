# REPORT-02 — Read-only Telegram research status

## Metadata

Status: REVIEW

Priority: P0 | Type: integration | Domain: reporting | Portfolio: CORE

Implementation Owner: Antigravity | Independent Reviewer: UNASSIGNED (pending independent review)

Recommended Branch: `feat/report-02-read-only-telegram-research-status`

Requirements: FR-16 | Legacy tasks: 33

External gates: No additional portfolio activation gate; data/policy validity still applies.

Implementation artifacts named below are planned unless present in baseline; WIP does not satisfy acceptance.

## Goal

Telegram menampilkan queue, champion dan health secara read-only dengan otorisasi chat.

## Why This Sprint Exists

Tanpa kapabilitas ini, kontrak `REPORT-02` belum dapat dibuktikan dan downstream tidak boleh mengasumsikan hasilnya tersedia. Nilai spesifiknya: allowlisted chat -> status/history/report; bounded messages and deterministic error states.

Direct consumers: QA-02, REL-01

## Depends On

- REPORT-01 — Compact experiment reports
- SHADOW-02 — Shared capital reconciliation

## Unlocks

QA-02, REL-01

## Required Reading

- `AGENTS.md`
- `docs/specs/00-master-product-technical-spec.md`
- `docs/specs/18-reports-and-telegram.md`
- `docs/specs/20-testing-strategy.md`
- `docs/decisions/ADR-002-temporal-and-accounting-semantics.md`

## Current Context

New capability; dependencies must be DONE before implementation.

- Dependency REPORT-01 supplies: run artifacts -> Markdown/JSON summary with provenance, costs, baselines, validity and forward counts.
- Dependency SHADOW-02 supplies: durable event IDs + risk policy -> reconciled postings, independent vs shared reports.

## In Scope

- Telegram menampilkan queue, champion dan health secara read-only dengan otorisasi chat.
- Unauthorized chat tidak mendapat holdings.
- Markdown escaped dan token redacted.
- Rate-limit retry tidak menggandakan notifikasi.
- Define or preserve the owning interface, specific fixtures, diagnostics and migration evidence required by these behaviors.

## Out of Scope

- Kapabilitas downstream: QA-02, REL-01.
- Mengubah evaluator gates atau menambah retry/search budget untuk membuat hasil lolos.
- Auto-trading uang nyata, UI baru, dan refactor modul yang tidak dibutuhkan acceptance.

## User / Actor Behavior

Given input yang memenuhi kontrak `REPORT-02` dan dependency evidence yang valid, when owning component dijalankan, then telegram menampilkan queue, champion dan health secara read-only dengan otorisasi chat.

Given input tidak valid pada acceptance boundary di bawah, when diproses, then hasil ditolak/ditandai eksplisit tanpa menciptakan successful downstream artifact.

## Functional Requirements

0. **REPORT-02-FR0:** Telegram menampilkan queue, champion dan health secara read-only dengan otorisasi chat.
1. **REPORT-02-FR1:** Unauthorized chat tidak mendapat holdings.
2. **REPORT-02-FR2:** Markdown escaped dan token redacted.
3. **REPORT-02-FR3:** Rate-limit retry tidak menggandakan notifikasi.

## Domain Rules / Invariants

allowlisted chat -> status/history/report; bounded messages and deterministic error states.

Compact Markdown/JSON; validity, snapshot/config IDs, net/gross distinction, trial count, forward age/trades.

Global causality, identity, exact accounting and paper-only constraints apply; tidak ada exception lokal yang mengizinkan pengubahan histori.

## Architecture / Design Contract

Layer owner: `src/indodax_lab/reporting, src/telegram_bot.py`. Konsumsi hanya public contracts dependency yang tercantum. Side effect berada pada boundary adapter/repository; pure calculation tidak melakukan HTTP.

allowlisted chat -> status/history/report; bounded messages and deterministic error states.

Jangan menciptakan layanan paralel bila fungsi ekuivalen sudah ada; perubahan dependency direction atau persistence material memerlukan ADR.

## Planned Files / Artifacts

- `src/telegram_bot.py`
- `src/indodax_lab/reporting/telegram.py`
- `tests/integration/lab/test_telegram_status.py`

Path baru adalah panduan, bukan bukti file sudah ada. Periksa file ekuivalen sebelum membuat modul baru; catat path aktual pada handoff.

## Interfaces & Contracts

Detailed domain fields and behavior are specified in `docs/specs/18-reports-and-telegram.md`; exact table schemas use the Required Reading dataset contract.

allowlisted chat -> status/history/report; bounded messages and deterministic error states.

Input harus membawa identity dan versi yang disebut di atas. Output memisahkan hasil valid, abstain/excluded/blocked yang sah, dan error teknis. Nilai unknown tidak boleh dikonversi ke nol. Pin enum/field/unit pada contract test; API baru tidak boleh hanya ditulis sebagai contoh tanpa implementation/test.

## Data / Persistence Impact

Compact Markdown/JSON; validity, snapshot/config IDs, net/gross distinction, trial count, forward age/trades.

Tidak ada implicit migration database legacy. Artifact/file additions pada scope di atas diberi version/hash. Jika implementasi ternyata membutuhkan schema mutation, revisi migration section melalui CR sebelum melakukannya.

## API / External Contract Impact

Interface delivery: Telegram read-only or observation-bound callback as specified; no exchange trading mutation. Validate allowlist, payload size and retry behavior.

No unlisted provider contract changes are authorized by this sprint.

## UI / UX Behavior

Pengguna harus dapat membedakan success, blocked/no-data dan transport error. Format Markdown aman, ringkas, dengan as_of dan provenance. No extra dashboard.

## Implementation Steps

First establish REPORT-02-AC0: Telegram menampilkan queue, champion dan health secara read-only dengan otorisasi chat. Use a minimal valid fixture, independent expected output, and a failing assertion before implementation.

1. Inspect dependency handoffs and actual module paths; confirm one owner and independent reviewer. Do not mark fresh code complete from historical evidence.
2. For `REPORT-02-AC1`, build minimal fixture proving: Unauthorized chat tidak mendapat holdings. Write `test_report_02_contract_1` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
3. For `REPORT-02-AC2`, build minimal fixture proving: Markdown escaped dan token redacted. Write `test_report_02_contract_2` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
4. For `REPORT-02-AC3`, build minimal fixture proving: Rate-limit retry tidak menggandakan notifikasi. Write `test_report_02_contract_3` or a clearly mapped existing test; observe targeted RED (wrong behavior, not missing test dependency), implement only that contract, then prove GREEN.
5. Integrate through the public boundary using actual output of dependency fixture; verify the declared contract and failure outcome rather than mock call counts alone.
6. Run the relevant tests below, inspect diff and record output/exit/source SHA. Refactor only after the contract remains green.
7. Commit scoped code/tests; prepare handoff with acceptance-to-evidence links, migrations and deviations; submit exact SHA for independent review.

## Required Tests

Positive contract: **REPORT-02-AC0**, `test_report_02_valid_contract` — Telegram menampilkan queue, champion dan health secara read-only dengan otorisasi chat. Prove the valid output through public inputs, not only rejection behavior.

| Acceptance | Planned test identity / map to existing equivalent | Assertion |
|---|---|---|
| REPORT-02-AC1 | `test_report_02_contract_1` | Unauthorized chat tidak mendapat holdings |
| REPORT-02-AC2 | `test_report_02_contract_2` | Markdown escaped dan token redacted |
| REPORT-02-AC3 | `test_report_02_contract_3` | Rate-limit retry tidak menggandakan notifikasi |

Unit/contract tests prove the listed inputs, outputs and guards. Integration tests pass real artifact/record output from prerequisite fixture into this capability. Stateful boundaries also require temp-root/DB failure-injection and retry tests; pure transforms use golden/future-perturbation instead of artificial concurrency tests.

At implementation, collect the mapped tests and run them by actual module path; no planned name is assumed to exist yet.

Record focused command and results; run affected regression gates. Shared-contract/migration/checkpoint/release changes require full suite. Follow `docs/specs/20-testing-strategy.md` for environment and optional-DL separation.

## Failure / Edge Cases

- Case 1: Unauthorized chat tidak mendapat holdings. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 2: Markdown escaped dan token redacted. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Case 3: Rate-limit retry tidak menggandakan notifikasi. Expected behavior is this assertion; never fall through to a successful artifact on rejection.
- Interrupted publish: preserve prior valid output and expose incomplete/failed status. For pure functions without publish, deterministic exception/result replaces this case.
- Same input on retry: no new semantic output/version or duplicate state transition.

## Security / Privacy / Safety

Allowlisted chats; escape Markdown; no tokens or sensitive balances to unknown recipients.

Trust boundary assessment: untrusted provider/artifact input or privileged state mutation exists; require negative tests and redacted diagnostics.

## Concurrency / Idempotency

Idempotent report key and bounded delivery retries; reporting failure never deletes observations.

## Performance Constraints

Bound resource use by the owning input batch/run/queue limits. Measure rows/events/trials and peak memory/latency on representative fixture; do not claim hardware capacity from unit tests.

Record baseline, identify algorithmic hotspot, then propose a versioned threshold for host activation. No fabricated elapsed-time acceptance. Research model search obeys ADR-003 budgets.

## Observability

Emit `REPORT-02` scope, input identities, output/run identity, config/policy version and reason code. For each listed guard, tests must assert the diagnostic identifies what was rejected without logging private payloads. Record elapsed/resource observations only outside content-addressed identities.

## Migration / Backward Compatibility

Serve stale report only with as_of label; missing data is unavailable not zero; regenerate from verified artifacts.

Existing code paths are preserved unless this sprint explicitly owns their behavior change. Material incompatibility requires documented consumers, schema/version transition and rollback evidence before review.

## Rollback / Recovery

Disable use of the new candidate/output version and keep the last verified compatible version. Do not overwrite historical artifacts; rebuild/retry from the same verified immutable inputs. For code-only pure changes, revert scoped commit after checking downstream compatibility.

## Acceptance Criteria

- [x] **REPORT-02-AC0** Telegram menampilkan queue, champion dan health secara read-only dengan otorisasi chat. Evidence: valid fixture through the public interface, with expected output independent of implementation.
- [x] **REPORT-02-AC1** Unauthorized chat tidak mendapat holdings. Evidence: mapped test, exact command/exit and target SHA.
- [x] **REPORT-02-AC2** Markdown escaped dan token redacted. Evidence: mapped test, exact command/exit and target SHA.
- [x] **REPORT-02-AC3** Rate-limit retry tidak menggandakan notifikasi. Evidence: mapped test, exact command/exit and target SHA.
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

- Attempt to disprove: Unauthorized chat tidak mendapat holdings. Inspect fixture and actual production path.
- Attempt to disprove: Markdown escaped dan token redacted. Inspect fixture and actual production path.
- Attempt to disprove: Rate-limit retry tidak menggandakan notifikasi. Inspect fixture and actual production path.
- Verify provenance and units at the boundary, not only test count or mock calls.
- Check downstream side effects, compatibility, state rollback and no scope creep.
- Verify budget, resource and paper-only policy are not bypassed.

## Commit Guidance

Branch: `feat/report-02-read-only-telegram-research-status`. Commit: `feat(report-02): read-only telegram research status` for future implementation. Documentation changes use `docs(...)`. Never stage original Task15 WIP wholesale.

## Handoff Requirements

Create `docs/sprints/handoffs/REPORT-02-HANDOFF.md` from template. Record owner/reviewer identities, branch, code SHA, files, contracts, migration, RED/GREEN commands, exact test results, AC mappings, deviations and known risks. Specify next eligible consumers: QA-02, REL-01. A code commit and later evidence commit must state their relationship explicitly.

## Ready-to-Run Implementation Prompt

```text
Implement REPORT-02 only: Read-only Telegram research status.
Read AGENTS.md, docs/sprints/reporting/REPORT-02-read-only-telegram-research-status.md and every Required Reading path listed in it.
Read sprint-manifest.json and verify dependencies DONE; check external gates before execution.
If status is historical DONE, do not rebuild: only reopen under a documented defect/change request.
Inspect actual files and any scoped WIP before creating equivalents.
Goal: Telegram menampilkan queue, champion dan health secara read-only dengan otorisasi chat.
Contract: allowlisted chat -> status/history/report; bounded messages and deterministic error states.
Use behavior-driven RED -> GREEN for each AC, then affected integration/regression verification.
Never implement downstream capabilities, loosen gates, use real trading keys or modify live DBs.
Commit scoped changes, record exact SHA/commands/AC evidence in handoff, self-review.
Stop at REVIEW for an independent reviewer; coordinator alone records DONE after PASS.
If blocked, report root cause and preserve work; do not fabricate test or review evidence.
```
