# Backup, restore and incident runbook

## Backup plan

Protect immutable manifests and their reachable data, local registry/ledger consistent SQLite backup, approved configs and environment locks. Secret backup is separately access-controlled and excluded from ordinary evidence. Do not copy a live SQLite DB alone while WAL writes are active; use supported backup API or quiesced verified snapshot. Keep at least one independent fault-domain copy according to owner-approved budget/retention. No retention duration or RPO/RTO is claimed established yet.

## Restore rehearsal

Use new empty root, verify backup checksums, load schemas with expected version, run SQLite integrity/foreign-key checks, verify reachable artifact closure, replay deterministic fixture, then compare ledger/checkpoint identities. Record elapsed restore and newest recoverable event to establish RTO/RPO. Fail rehearsal on missing artifacts even if DB opens.

## Incidents

| Symptom | Immediate containment | Evidence and recovery |
|---|---|---|
| Sequence gap/stale feed | Mark non-reliable and stop affected entries | Keep gap record; recover snapshot, durable flush and revalidate continuity |
| Disk full | Stop admissions and incomplete publisher | Preserve partial failure; free only confirmed unreferenced artifacts; retry same identity |
| Ledger imbalance | Halt paper and invalidate affected run | Preserve journal; replay from verified checkpoint; no manual PnL patch |
| Unknown fee/source license | Block promoted runs/acquisition | Gather official evidence and version schedule/source policy |
| Worker lost heartbeat | Fence old claim before requeue | Verify committed outputs, cap retry and avoid duplicate metrics |
| Model mismatch/corrupt bytes | Reject load; preserve current champion/cash | Restore verified compatible bundle and check sample schema |
| Secret exposure suspected | Stop affected transport and notify owner through authorized workflow | Redact evidence; owner-led rotation; audit access before resume |

Use incident template. Cleanup never deletes artifacts referenced by champion, frozen/sealed run or retained audit until reviewed retention policy explicitly permits it. This document schedules no backups by itself.
