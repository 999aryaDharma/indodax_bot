# Accounting audit fixes — dev — 2026-09-15

Status: scoped working-tree review complete; committed-SHA review pending.
Base: `0c788c0d432eb67440c9fdfb41b2e9f21ada4f41`.
User authorized fixes directly on `dev`. No branch switch, commit, push,
manifest change, service activation, or trading operation was performed.

## Implemented scope

- AUD-001: paper allocations require positive finite cash and price, BUY-only
  entry semantics and UTC time. Construct the position and result before
  changing balances or processed event IDs.
- AUD-002, partial: research ledger stages cash, inventory, fees and PnL,
  verifies balanced postings, then publishes the staged transaction. Both BUY
  and SELL reject fee-inclusive negative cash. Risk sizing subtracts existing
  marked pair exposure from its position cap.
- Existing `requirements.txt` edits preserved byte-for-byte (SHA-256:
  `01e97526e4b9fd5ef2110aa308609ea70dad0d6084335ea55ad27d53b9f9630c`).

## Evidence

Interpreter: `C:/Users/User/miniconda3/envs/ML/python.exe`, Python 3.12.13.
Commands used `-B`, `-p no:cacheprovider`; temporary state was separate from
runtime databases. No dependencies installed.

| Command suffix after Python | Exit | Result |
| --- | --- | --- |
| `-B -m pytest tests/unit/lab/backtest/test_accounting_failure_atomicity.py -q -p no:cacheprovider --tb=short` before fixes | 1 | 7 failures, 2 passed after correcting fixture side spelling; failures demonstrate actual defects |
| Same file after adding existing-exposure cases, before risk fix | 1 | 2 failures, 9 passed |
| Same file after fixes and additional failure/UTC cases | 0 | 13 passed |
| `-B -m pytest tests/unit/lab/backtest tests/unit/lab/paper -q -p no:cacheprovider -o tmp_path_retention_policy=all --basetemp <new unique temp path> --tb=short` | 0 | 45 passed before the two additional failure/UTC cases |
| `git diff --check` | 0 | No whitespace errors in tracked working diff; CRLF conversion warnings only |
| Same backtest/paper regression with a new unique temp path after all 13 new cases | 0 | 47 passed, no skips |

The initial unprivileged regression had 22 passes and one temporary-directory
PermissionError, not a PASS. Escalated execution used a newly generated temp
path and resolved this environment restriction.

Independent reviewer `/root/accounting_fix_review` inspected the working diff:
no scoped Critical/Important finding. It ran all 13 new cases, independently
checked SELL failure atomicity and retry, and noted one Minor: Position objects
are replaced after successful fills. This snapshot behavior is now documented;
no repository caller relying on retained position identity was found. Reviewer
combined regression had two temp-permission errors; it did not claim full PASS.

## Remaining boundaries

This is not closure of the complete audit. AUD-002 still needs pending-order
reservation and execution-time fee/price sizing coverage. Independent risk
exits/barriers, causal execution, temporal features/labels, artifact identity,
transfer/retry safety, model evidence, governance and environment findings
remain open. In-memory staging is not a durable database transaction or a
cross-thread/cross-process lock. No manifest sprint was marked DONE.

Overall branch verdict remains BLOCKED pending the remaining audit work.
