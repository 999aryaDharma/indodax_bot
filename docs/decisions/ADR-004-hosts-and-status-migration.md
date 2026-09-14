# ADR-004 — Preserve work and qualify imported evidence

Status: ACCEPTED planning baseline. Date: 2026-09-14.

Documentation worktree branches from `8a8e9f2` into `docs/trading-bot-master-plan-20260914`. Original `feat/strategy-research-lab-implementation-20260806` remains unchanged including untracked Task15 code/tests. No cherry-pick or WIP commit is implied.

Tasks1–14 map to historical DONE capabilities. Basis: committed code/test history, Phase0/Phase1 evidence and completed final-review reports supplied in conversation. Reviewer individual identity is not recoverable and must not be fabricated. Source documents include exact code SHA and command results; this session verifies docs only. Future changes require fresh affected test/review evidence.

Task15 is split FEAT-01…04. New manifest starts FEAT-01 READY with WIP explicitly unverified, not IN_PROGRESS under a fictitious active agent. COST-01 is also structurally READY. READY means dependencies DONE; execution additionally obeys external data, policy and resource gates.

Host roles preserve prior ASUS-light/Lenovo-heavy design but deployment capacity and actual available hosts must be audited before activation. Local DBs only; cross-host immutable transfer. No network-shared SQLite WAL, distributed scheduler or production throughput claim is implied.
