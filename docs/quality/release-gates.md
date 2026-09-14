# Release gates

| Gate | Prerequisite evidence | Failure behavior |
|---|---|---|
| Data | Verified provider bytes, sentry recomputation, typed source references, fixed cutoff | BLOCKED_DATA, no feature promotion |
| Judge | Cost intervals, exact ledger, conservative fill, risk and deterministic replay | INVALID_RUN; no candidate rank |
| Features/labels | Availability, golden values, warmup, separated target, purge/exposure | Dataset rejected |
| Tournament | Classical+M01/M02 comparable, all trials, policy outcomes and bounded queue | No advanced default promotion |
| Security | No real order credentials; safe artifacts/paths; allowlist; independent audit | Release blocked |
| Operational | Measured host profile, backup restore, transfer integrity, service restart and rollback | Activation blocked |
| Software RC | Required CORE sprints and REL-01 review/evidence | Remains candidate |
| Champion | Historical eligibility plus 90 days and100 closed forward trades, risk gates | Keep existing champion or cash; no early replacement |

Optional extension/experimental candidates are excluded from initial release completeness, but if explicitly activated all their own gates apply. A software RC may exist while champion forward qualification remains pending; report this distinction clearly. No checklist allows deployment or merge not authorized by the current task.
