# CR-20260924 — ASUS Production Main and Research Runtime co-location

Status: ACCEPTED owner clarification, 2026-09-24. This records the owner's correction to the host model; it does not certify ASUS capacity or authorize runtime activation/deployment.

## Request and decision

The owner clarified that ASUS is the Production Main server and continues to host Research Workbench execution, including experiments, backtests, isolated shadow agents, tournaments and related research evaluation. The Lenovo daily laptop performs ML/DL model training and tuning. This supersedes the earlier proposal for a separate Production host and any reading that moved Research Runtime, shadow or tournament execution to Lenovo.

## Impact and required boundaries

- ASUS hosts Production Main and Research Runtime on one physical machine. Keep them as separate services, identities, configuration roots, local databases, resource budgets and authority domains. Do not share SQLite/WAL, secrets, ledgers, candidate state or write authority.
- Production Main is live and independently owns its release, risk/OMS/ledger authority, Indodax account access and any Production credentials. Research remains a separate research/shadow environment and cannot access Production secrets or write Production state. Existing release and risk governance remains unchanged.
- ASUS Research Runtime owns the shared public market-data runtime for its admitted research/shadow consumers. Production Main independently verifies its own market-data health and does not treat Research feed state as Production truth.
- Lenovo is the ML/DL training and tuning host. Model outputs cross to ASUS only as immutable, identified artifacts through a staged verification/import boundary owned by the receiving runtime. This CR does not define a transport protocol or claim signatures exist.
- Because workloads share ASUS hardware, qualification must measure co-resident Production and Research loads and prove that optional Research work is deferred/stopped before Production safety or durability is impaired. QA-03 and OPS-01 evidence must use the selected ASUS host and realistic mixed load before release/deployment.
- ASUS inventory is now captured below, but workload capacity remains unqualified. Unknown or unsafe resource headroom blocks workload admission and deployment; it does not change the owner's host assignment.

## Read-only ASUS inventory snapshot

Captured over SSH from `asus-server` on 2026-09-24 at 00:24 WITA. Commands: `cat /etc/os-release; nproc; lscpu --parse=cpu,core,socket; uptime; free -h; df -h /; df -ih /; systemctl --failed; docker ps; docker stats --no-stream; vmstat 1 3`.

- Ubuntu Server 22.04.5 LTS, kernel `5.15.0-187-generic`; 4 logical CPUs (2 physical cores).
- RAM: 3.7 GiB total, 1.9 GiB available in this sample; swap: 3.7 GiB total, 1.7 GiB used.
- Root volume: 98 GiB, 65 GiB used, 29 GiB available (70%); inode use 24%.
- Load average: 1.45 / 1.73 / 1.77. `vmstat` showed 79% then 71–73% idle CPU and no swap-in/out during the last two one-second samples.
- Several Docker workloads were active; one container reported `Restarting`. `systemctl --failed` listed no failed units.
- This is a point-in-time inventory, not a stress test, thermal soak, isolation test or capacity approval. Production and Research resource limits still need qualification under combined realistic load.

## Alternatives and compatibility

The prior separate Production-host proposal is rejected because it conflicts with the owner's deployment target. Keeping Lenovo as a training/tuning workstation and ASUS as a shared physical host preserves the existing process boundaries and immutable-artifact transfer model while matching the clarified topology. No shared database or cross-host writer is introduced.

## Required document and plan updates

ADR-009 supersedes only ADR-008's separate-Production-host allocation and the earlier host-placement clauses in the frozen/system/implementation documents. The shared WebSocket runtime design, isolated tournament semantics, live Production authority, G0–G7 and research/shadow isolation remain in force. Existing API/UI implementation status is unaffected. QA-03 must qualify combined ASUS workloads; its existing dependency into REL-01 remains the release gate.

## Rollback and validation

This CR changes documentation and future qualification scope only. Revert the scoped documentation commit to roll it back; preserve runtime evidence and all unrelated user work. Run `python docs/quality/validate_planning.py --refresh --self-test` and `git diff --check`. These checks do not qualify ASUS, deploy services, or authorize live trading.
