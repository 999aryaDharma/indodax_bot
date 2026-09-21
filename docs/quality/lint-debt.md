# Ruff lint debt baseline

Date: 2026-09-21

The first CI run that reached full-repository Ruff after the test-suite repair reported **1101
findings**, with 387 marked automatically fixable. These findings pre-date and span the research
implementation broadly; converting them all in the same safety-hardening change would create a
large non-semantic diff and unnecessary regression risk.

This is not treated as "lint clean".

Current CI policy is intentionally staged:

1. Run Ruff fatal correctness rules (E9, F63, F7, F82) across all `src` and `tests`.
2. Run the complete configured Ruff ruleset on newly introduced safety-boundary files.
3. Keep full pytest mandatory.
4. Reduce the remaining style/modernization debt in dedicated refactor batches, with tests green
   before and after each batch.
5. Expand strict-lint scope as each subsystem reaches zero-debt.

Production release gates must not weaken fatal static checks. Full repository style cleanup remains
required before claiming repository-wide Ruff cleanliness, but it is not allowed to block critical
runtime correctness fixes by forcing an unrelated 1000+ finding rewrite.
