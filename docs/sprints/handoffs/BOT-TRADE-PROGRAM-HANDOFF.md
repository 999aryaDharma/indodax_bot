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

Documentation commit SHA and independent review verdict will be recorded after the commit is reviewed. Review round 1 pending. Future implementation tasks are not DONE.

External gates: current provider history/capabilities and fee evidence; model/runtime eligibility; independent dependency review; realistic ASUS mixed-load latency/memory/thermal/disk/recovery proof; G0–G7 and per-candidate plus aggregate portfolio qualification. No safe agent/pair count is established by the snapshot.

## Preservation and rollback

User changes in AGENTS.md, dashboard.pen and design-prototype/ are excluded. Revert only the documentation packet if needed; do not reset user files or alter runtime financial history. No push/merge/deployment performed.
