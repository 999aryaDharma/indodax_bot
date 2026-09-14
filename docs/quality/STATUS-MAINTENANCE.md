# Maintaining status projections

`sprint-manifest.json` is authoritative. Change status only with current handoff/review evidence. The validator supports `--refresh` to recompute structural READY states for PLANNED/READY entries and regenerate index, feature map, full edge list, waves, status-count summary and requirement traceability. It preserves IN_PROGRESS/REVIEW/BLOCKED/PAUSED/CANCELLED/DONE and never manufactures DONE.

Update status text in each sprint Metadata together; validator checks consistency. `--refresh` updates that metadata from manifest automatically. Historical evidence/status documents remain immutable context. Status model prose references initial conditions; refreshed summary uses current data in `STATUS-SUMMARY.md`.

Review mutation diff, run validator, commit the status change and evidence references together. If dependencies of active/done work change, investigate affected code/evidence manually; automatic readiness calculation cannot invalidate scientific results correctly without human review.
