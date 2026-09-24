# Bot Trade Program documentation handoff

Date: 2026-09-24. Owner: Codex /root. Delivery: documentation only. Base SHA: `f176f59e1863845ffae9089a45c4a2f90b3d7a81`.

## Scope

Accepted [program contract](../../implementation/BOT-TRADE-PROGRAM.md), CR and ADR-010; DATA-07, PM-07/08/09, API-04 and UI-03 sprint specifications; amendments to existing PLANNED Workbench/runtime/release tasks; manifest and generated projections. Completed task status/evidence is preserved; their generated Unlocks lists change where necessary.

The owner's follow-up adds [ASUS capacity cross-check](../../implementation/ASUS-BOT-CAPACITY-CROSSCHECK.md), fresh authorized read-only SSH inventory, and unverified capacity acceptance cases for JOB-02/OPS-01/QA-03 and consuming tasks. REVIEW task historic checkmarks do not cover the new cases.

Implementation details and path inventories live in each sprint spec. DATA-07 reuses existing jobs/admission as well as collection/registry, so JOB-01/JOB-02 must be DONE before it is READY. PM-07 consumes verified PM-05 release ownership. These explicit interface prerequisites tighten the high-level dependency sketch without authorizing new runtime work.

## Checks and environment

- Local Windows PowerShell; Python `C:/Users/User/miniconda3/envs/ML/python.exe`.
- `python docs/quality/validate_planning.py --refresh --self-test`: PASS, 132 nodes, 257 edges, zero cycles, 7/7 negative mutations rejected; 35 DONE, 59 REVIEW, 38 PLANNED, zero READY.
- `git diff --check -- docs`: PASS.
- SSH host metadata/resource checks on `asus-server`: both commands exited 0 at 21:07:34–21:07:54 WITA. Exact command families, bytes and interpretation are in the cross-check. No credentials, trading DB/account endpoints or configuration payloads accessed; no service changes or benchmark runs.
- Product tests not run: no product code changed. No claim of runtime parity, capacity, profitability or deployment readiness.

## Review and external gates

Documentation source commit: `faf7750` (full SHA is available through Git). Review round 1 by `/root/docs_review` began against that exact commit and found conflicting RW6 allocation ordering. The follow-up corrects RW6 and its manifest contract to policy priority, strategy ID, intent ID, and clarifies that overlapping owners reject Production-compatible qualification. The reviewer then hit its session usage limit before issuing a complete verdict. Independent review remains **PENDING**, not PASS; preserve round count 1 and re-review the correction commit before approval. Future implementation tasks are not DONE.

Additional owner-authorized disk inspection distinguishes physical 500 GB storage from the root LV: projects has approximately 279 GiB available and Docker volume 47 GiB. Image/cache accounting and privileged-directory limitations are documented without cleanup or migration. Mount-aware capacity ACs were added to JOB-02/OPS-01/QA-03.

Combined-workspace validation after another Codex added its own API-05/UI-04 planning: `python docs/quality/validate_planning.py --self-test` PASS, 134 nodes, 264 edges, zero cycles, 7/7 negative mutations rejected. `git diff --check -- docs` PASS. Those other tasks/ADR-011 and their readiness are not owned or reviewed by this delivery; only this packet's manifest fields are staged in its follow-up commit.

External gates: current provider history/capabilities and fee evidence; model/runtime eligibility; independent dependency review; realistic ASUS mixed-load latency/memory/thermal/disk/recovery proof; G0–G7 and per-candidate plus aggregate portfolio qualification. No safe agent/pair count is established by the snapshot.

## Preservation and rollback

User changes in AGENTS.md, dashboard.pen and design-prototype/ are excluded. Revert only the documentation packet if needed; do not reset user files or alter runtime financial history. No push/merge/deployment performed.
