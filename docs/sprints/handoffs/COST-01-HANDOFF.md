# COST-01 handoff

## Recovery audit addendum (2026-09-23)

The provenance section below is retained as historical source evidence; its claims
are not accepted as current verification. Current audited implementation is on
`fix/feat-01-immutable-params` at code SHA
`627a74c994f29ecffd6e8270a1c459d731c7acd8` (base cost remediation
`a42b242b99c286911c5968ea2f59ce932387ebac`). COST-01 remains REVIEW.

- Corrected handoff's invalid historical code SHA: original implementation is
  `9c9504fc113e79488c73258f6cc93e04fdd56f46`; historical SHA was not used as fresh
  test evidence.
- `lookup_cost` uses `fee_basis_ts`; limit orders bind fees at decision/order-creation
  time, market orders at execution time. Execution, replay sizing, labels, and
  paper/shadow callers have been migrated. Unverified fee schedules block lookup;
  labels exclude those samples.
- Canonical config contains 28 intervals, all `evidence_verified: false`. Fee-source
  evidence is still incomplete, so this config cannot support fee claims or
  promotion. The reviewer independently verified fail-closed behavior on the exact
  code SHA; the external evidence blocker still prevents a status transition.
- TDD: resting-limit boundary test failed before caller migration (`event_ts`
  unexpected keyword); passed after. Unverified-label exclusion test also passes.
- Verification on this exact code SHA: `C:\Users\User\miniconda3\envs\ML\python.exe
  -m pytest -q -p no:cacheprovider` → 998 passed, 2 skipped (Linux `/proc` resource
  smoke and Windows symlink privilege), 3 sklearn `OptimizeWarning`s. Focused COST /
  execution / label / paper suite → 48 passed. `rtk ruff check` on `costs.py` and
  `test_cost_schedule.py` passed; broader touched legacy modules have pre-existing
  lint debt. `git diff --check` passed.
- Independent exact-SHA review: PASS for code/spec quality, no Critical or Important
  findings, by `/root/cost01_independent_review`; targeted reviewer run 11 passed.
  Reviewer did not rerun full suite; full-suite result above is owner evidence. See
  `COST-01-REVIEW.md`.
- External blocker: authoritative, complete fee matrix and effective boundaries
  remain unverified. Do not mark DONE, do not use live fees, and do not enable live
  trading. Public Indodax guidance directs members to the authenticated profile for
  maker/taker buy/sell fee details ([fee menu](https://help.indodax.com/hc/en-us/articles/40043754266265-Where-can-I-find-the-Indodax-Trading-Fee-menu));
  its public fee page documents the tax change and limit-order fee timing
  ([transaction fees](https://help.indodax.com/hc/en-us/articles/4416646599705-Details-of-Transaction-Fees-on-INDODAX)),
  and the public CFX rate change ([CFX update](https://blog.indodax.com/penurunan-biaya-cfx/)).
  These public sources do not disclose the complete account-applicable trading-fee
  matrix for all historical intervals; historical fixtures cannot fill that gap.

Status: REVIEW

## Owner evidence update (2026-09-24)

Owner confirmed the following values were read directly from the INDODAX app's
Trading Fees screen in PRO mode. This is a current observation, not evidence of
the rates' historical effective start dates:

| Market | Side | Maker: service / tax / CFX = all-in | Taker: service / tax / CFX = all-in |
|---|---|---|---|
| IDR | Buy | 0.10% / 0% / 0.0111% = 0.1111% | 0.20% / 0% / 0.0111% = 0.2111% |
| IDR | Sell | 0.10% / 0.21% / 0.0111% = 0.3211% | 0.20% / 0.21% / 0.0111% = 0.4211% |
| USDT | Buy | 0.03% / 0.21% / 0.0222% = 0.2622% | 0.06% / 0.21% / 0.0222% = 0.2922% |
| USDT | Sell | 0.03% / 0.21% / 0.0222% = 0.2622% | 0.06% / 0.21% / 0.0222% = 0.2922% |

The public [INDODAX fee article](https://help.indodax.com/hc/id/articles/4416646599705-Rincian-Biaya-Transaksi-di-INDODAX)
corroborates the fee components, market/side/order-role coverage, PMK 50/2025
tax effective time, and Pro minimum. This owner observation supports current
matrix values only. Prior intervals and the effective start of this exact
matrix remain unverified; keep their schedules fail-closed and COST-01 in REVIEW.

## Evidence recovery audit (2026-09-24)

The following official sources are available and establish only the scopes noted:

- INDODAX [trading-fee details](https://help.indodax.com/hc/id/articles/4416646599705-Rincian-Biaya-Transaksi-di-INDODAX): tax change under PMK 50/2025 effective 2025-08-01, tax components across maker/taker and IDR/USDT, PRO minimum, current fee detail location, and order-created-time fee behavior for resting limits. It does not publish a complete dated historical trading-fee matrix.
- INDODAX [PPN 12% adjustment](https://blog.indodax.com/?p=30884): 2025-01-01 rates, including IDR buy tax 0.12%, USDT buy/sell tax 0.22%, and IDR CFX adjustment to 0.0224%.
- INDODAX [return to 11% VAT](https://blog.indodax.com/implementasi-ppn-12/): correction effective 2025-02-13 11:00 WIB and PRO IDR/USDT matrix image. This reveals the configured `indodax_idr_2025h1_*` interval (2025-01-01 through 2025-08-01) spans two tax regimes; the fee schedule must be split and reconciled before it can be evidence-verified.
- INDODAX [CFX implementation notice](https://blog.indodax.com/en_US/penerapan-fee-cfx/): CFX/all-in schedule applies to all IDR and USDT pairs from 2024-10-31 23:59:59 WIB; article images contain the announced Pro matrix.
- INDODAX [CFX reduction notice](https://blog.indodax.com/penurunan-biaya-cfx/): CFX rates IDR 0.0111% / USDT 0.0222% effective 2026-03-01 00:00 WIB and confirms old CFX rates remain for limits created before the boundary.
- Kementerian Keuangan [JDIH PMK 50/2025](https://jdih.kemenkeu.go.id/dok/pmk-50-tahun-2025): official regulation metadata confirms the effective date 2025-08-01; the regulation supports tax treatment, not exchange service fees.

### Unverified matrix and period inventory

`configs/costs/indodax_idr_v1.yaml` contains 28 IDR rows across seven intervals; every row remains `evidence_verified: false`. It contains no USDT rows. The following coverage is therefore still unproven as a complete schedule keyed by market × side × maker/taker × components × effective boundary:

| Configured interval | Missing or incomplete evidence |
|---|---|
| IDR 2021-01-01–2022-05-01 | Historical service/tax/CFX (or explicit zero) rates and exact bounds for buy/sell maker/taker. Existing “Historical Fee Schedule 2021” label is not a retrievable official source. |
| IDR 2022-05-01–2024-10-31 23:59:59 WIB | Complete service/tax rates and boundary for both sides and roles; PMK reference alone cannot verify Indodax maker/taker service fees. |
| IDR/USDT from 2024-10-31 23:59:59 WIB | The CFX launch source establishes the boundary and CFX component, but archived Pro fee matrix evidence is still required for all components and roles in each affected interval. Current YAML models IDR only. |
| IDR/USDT 2025-01-01–2025-02-13 11:00 WIB | The temporary 12% PPN regime and exact all-in matrices need an explicit interval; current YAML does not end the interval at this boundary. |
| IDR/USDT 2025-02-13 11:00 WIB–2025-08-01 00:00 WIB | Corrected 11% regime matrix and exact all-in components need a separate verified interval; current YAML retains 12% buy tax/old component values through August. |
| IDR/USDT from 2025-08-01 00:00 WIB–2026-03-01 00:00 WIB | PMK 50 verifies tax rule; complete market/side/role service and CFX matrix/bounds still need archived INDODAX evidence. Current YAML has IDR only. |
| IDR/USDT from 2026-03-01 00:00 WIB onward | CFX component boundary is public. Owner's app screenshot supports the current PRO rates (dated observation 2026-09-24) but does not prove those rates began on 2026-03-01 or 2026-09-21. Need official dated matrix/boundary, including minimum-order rule scope. Current YAML has IDR only and uses 2026-09-21 as an unverified start. |

Owner should provide dated, attributable INDODAX evidence (official archived fee notice/matrix or support confirmation) for the missing service/tax/CFX values and exact effective boundaries, plus historical PRO-versus-Lite applicability and minimum-order rule where the simulator models it. For any interval that cannot be sourced, keep it explicitly unknown/unverified and excluded from fee-based performance claims; do not infer backward from today's app view. The supplied current screenshot is not historical evidence. No credentials or live account were accessed.

## Owner summary and public matrix-image audit (2026-09-24)

The owner supplied a three-era summary in conversation (2021, 2022–2024, 2025–2026). It is retained as a lead only: it has no dated source or exact market × side × maker/taker cells, and its 2025–2026 aggregate ranges do not match the detailed dated INDODAX matrix published for the PMK 50/2025 transition or the current app screenshot. Do not use the ranges “maker 0%–0.15% all-in” or “taker 0.20%–0.30% all-in” as verified fees.

I downloaded and visually checked the matrix images embedded in INDODAX's public announcements; source images were inspected from the official article pages and were not added to the repository:

- [INDODAX PPN 12% adjustment, 2024-12-30](https://blog.indodax.com/?p=30884), effective 2025-01-01: image gives a full PRO matrix. IDR buy maker/taker all-in 0.242%/0.342% (service 0.10%/0.20%, tax 0.12%, CFX 0.0224%); IDR sell 0.222%/0.322% (tax 0.10%, CFX 0.0224%); USDT buy and sell maker/taker 0.294%/0.324% (service 0.03%/0.06%, tax 0.22%, CFX 0.0448%). This supports the 2025-01-01 regime only, through the next effective change.
- [INDODAX PMK 50/2025 fee adjustment, 2025-07-31](https://blog.indodax.com/?p=32644), effective 2025-08-01 00:00 WIB: image gives full PRO matrix. IDR buy 0.122%/0.222% (service 0.10%/0.20%, tax 0%, CFX 0.0222%); IDR sell 0.332%/0.432% (tax 0.21%); USDT buy and sell 0.284%/0.344% (service 0.03%/0.06%, tax 0.21%, CFX 0.0444%).
- The [2025-02-13 PPN correction notice](https://blog.indodax.com/implementasi-ppn-12/) gives its effective time and says the correction affects the fee structure and CFX refund, but the currently accessible article graphic does not provide a usable dated replacement matrix. The 2025H1 config interval therefore remains unfit for verification: split it at 2025-02-13 11:00 WIB, obtain the complete new matrix, and resolve the CFX component after the correction rather than carrying January values forward.
- The [2024 CFX implementation notice](https://blog.indodax.com/en_US/penerapan-fee-cfx/) text gives the 2024-10-31 23:59:59 WIB boundary and covers all IDR/USDT pairs. Its currently served embedded fee-menu image displays tax values matching the later PMK 50 regime rather than the 2024-10 tax regime. Treat that mutable image as stale for historical tax/service matrix proof; the article's dated text remains evidence for the CFX launch boundary, and the 2026 notice documents the former CFX rates.
- [INDODAX CFX reduction](https://blog.indodax.com/penurunan-biaya-cfx/) establishes the new CFX component (IDR 0.0111%, USDT 0.0222%) and old component (IDR 0.0222%, USDT 0.0444%) from 2026-03-01 00:00 WIB. Together with the current owner app observation, this corroborates the current matrix values; it does not prove the full current service/tax matrix's effective start or the 2026-09-21 minimum-order boundary.

The owner summary's “2022–2024 maker 0% + tax 0.21%” also collapses distinct tax cells: INDODAX's [2025 tax report](https://blog.indodax.com/?p=33702) summarizes the PMK 68 regime from 2022-05-01 as IDR buy PPN 0.11%, IDR sell PPh 0.10%, and USDT buy/sell 0.11% PPN + 0.10% PPh. Exact maker/taker service fees and full boundaries still need period-matched exchange evidence. The earlier 2021 summary (0% maker / 0.3% taker) is directionally consistent with old INDODAX announcements, but those examples do not prove the complete continuous interval now encoded, its tax/market scope, or exact boundary.

Owner action remains: provide the archived/source-backed complete matrix for (1) 2021 through 2022-05-01, (2) 2022-05-01 through the 2024 CFX boundary, (3) the corrected 2025-02-13 through 2025-08-01 regime, and (4) dated evidence tying the post-2026-03-01/current complete matrix and PRO minimum-order rule to their exact effective boundaries. USDT rows must be represented in the versioned schedule. The already published 2025-01-01 and 2025-08-01 matrices may be used only for their own documented intervals; do not project them backward or forward across an unverified change.

## Identity
- Sprint ID: COST-01 — Time-valid exchange cost schedules
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/cost-01-time-valid-exchange-cost-schedules`
- Base SHA: `faf1698`
- Code SHA: `9c9504feea4ca33320f7724fe282a5bc651ec30f`
- Evidence SHA relation: recorded in this handoff

## Files and contracts
- Planned files:
  - `configs/costs/indodax_idr_v1.yaml` (newly created)
  - `src/indodax_lab/backtest/__init__.py` (newly created)
  - `src/indodax_lab/backtest/costs.py` (newly created)
  - `tests/unit/lab/backtest/test_cost_schedule.py` (newly created)
- Contract:
  - `market, side, role, event_ts -> service/tax/exchange components and min notional with sources; [valid_from,valid_to)`.
  - All rates Decimal, exact accounting, no negative or non-finite rates.
  - Overlapping schedule intervals for the same market/side/role rejected.
  - Boundary end belongs to next interval.
  - Unknown period raises UnknownCostScheduleError (never falls back to today's fee).
- Migration and compatibility:
  - Additive backtest subsystem; backward compatible.
  - Dependencies: DATA-01 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| COST-01-AC0 (RED) | `test_cost_01_valid_contract` | `python -m pytest tests/unit/lab/backtest/test_cost_schedule.py` | Exit 1 (`NotImplementedError`) | working tree |
| COST-01-AC0 (GREEN) | `test_cost_01_valid_contract` | `python -m pytest tests/unit/lab/backtest/test_cost_schedule.py::test_cost_01_valid_contract` | Exit 0 (Passed, resolves historical and current schedules) | working tree |
| COST-01-AC1 | `test_cost_01_contract_1` | `python -m pytest tests/unit/lab/backtest/test_cost_schedule.py::test_cost_01_contract_1` | Exit 0 (Passed, rejects overlapping intervals) | working tree |
| COST-01-AC2 | `test_cost_01_contract_2` | `python -m pytest tests/unit/lab/backtest/test_cost_schedule.py::test_cost_01_contract_2` | Exit 0 (Passed, boundary end selects next interval) | working tree |
| COST-01-AC3 | `test_cost_01_contract_3` | `python -m pytest tests/unit/lab/backtest/test_cost_schedule.py::test_cost_01_contract_3` | Exit 0 (Passed, unknown period raises UnknownCostScheduleError) | working tree |

All 5 tests in `tests/unit/lab/backtest/test_cost_schedule.py` passed (0.42s).
Combined verification with previous capabilities (29 tests total) passed (1.33s).

## Review
- Spec verdict: PASS (meets all functional requirements of COST-01 and specs/08-costs-ledger-and-execution.md).
- Quality verdict: PASS (zero network, strictly immutable schemas, Decimal precision, UTC-aware).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for COST-01.
- Next unlocked capabilities: LED-01 (Balanced research postings), SIM-01 (Conservative execution simulator).


Owner clarified on 2026-09-24 that the three-era summary is an estimate, not official historical evidence. It supplies no replacement dated matrix or effective-boundary evidence. The owner evidence requests listed above therefore remain open; COST-01 remains REVIEW.


## Owner-approved capability/data-gate split (2026-09-25)

The owner requested COST-01 stop blocking downstream implementation. Scope is the capability to resolve verified schedules and to reject unverified/unknown intervals without fabricated fees. Treat that capability as independently closable; do not describe unknown tariffs as verified.

Current inspection still finds all 28 configured IDR rows `evidence_verified: false`, no configured USDT rows, and unresolved official matrix/effective-boundary gaps listed above. Synthetic contract fixtures are not actual Indodax tariff proof. These gaps block fee-based net-performance claims/promotion for affected dates/pairs/roles. They do not block SIM-01 implementation/review on explicit fixtures that do not claim representative historical net profitability. Unknown-period runs must fail/abstain or report unavailable; never substitute zero/current fee or silently shorten the requested period.

Focused verification on current working code 2026-09-25: `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest tests/unit/lab/backtest/test_cost_schedule.py tests/unit/lab/backtest/test_indodax_cost_boundaries.py tests/unit/lab/backtest/test_execution.py -q -p no:cacheprovider` -> 17 passed. Initial sandbox invocation errored before test execution because shared `%TEMP%/pytest-of-User` was inaccessible; approved elevated rerun passed. Prior exact implementation SHA/review evidence above remains the code basis; no COST implementation changes occurred in this clarification.

Requested disposition: close the capability sprint only after independent review of the revised criterion/scope and exact documentation SHA; retain historical tariff evidence as a named downstream external gate. Manifest status has not yet transitioned pending review.


## Focused re-verification for capability close-out (2026-09-25)

These tests isolate COST-01 and do not rely on concurrent SIM implementation edits:

- Command: `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest tests/unit/lab/backtest/test_cost_schedule.py tests/unit/lab/backtest/test_indodax_cost_boundaries.py -q -p no:cacheprovider`
- Result: 11 passed in 0.51s on source snapshot `101e5d3ab4d42b7669f357c479105606ce4915a5`; tested code/config blob IDs: costs.py `619fe5def46323ac9398b4cd7b4231ca082287e7`, cost config `ed50d565134de8bb0894e86a2784895a52a6cbe0`. COST code/config/test files were clean and unchanged; concurrent SIM-01 edits were not in this focused test invocation.
- Coverage includes independent expected fee fixture resolution, overlap rejection, interval boundaries, limit order-creation fee basis, unknown/unverified schedule rejection, invalid values, published tax/CFX boundaries and observed current PRO minimum boundary.

These tests prove code behavior and boundary handling only. The published/observed rates do not verify the full active/historical matrix, and no unverified schedule yields a successful canonical lookup. The complete historical tariff matrix remains an external result/promotion blocker.
