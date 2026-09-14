# Operator runbook — preparation and activation

Status: target procedure; service units and new CLIs named in future sprints may not exist yet. Inspect `--help` and actual completed sprint handoff before running commands. Do not run proposed commands against production blindly.

## Prepare

Record code SHA, selected host profile, CPU/RAM/GPU/disk, current workloads, Python version and locked dependencies. Confirm process user and private secret file permissions. Use absolute configured roots, never code checkout as runtime database directory. Collector/paper must import without torch. On a test root, run completed fixture pipeline and verify IDs. Provider endpoints/rate limits/licensing/costs require current evidence at activation time.

## Activate

Only after OPS-01 and release gates pass with user activation instruction: stop conflicting old writer, preserve consistent checkpoint/backup, install reviewed profile-specific unit and env reference, start one process, observe health/lag/rejects, then add dependent services. No `curl | sh`; no secrets printed to terminals/logs. Research training is admitted by measured resource guard.

## Verify

Compare durable artifact/checkpoint identities, queue heartbeat, event lag, sentry status and ledger reconciliation. Telegram test uses authorized chat only. Service active status alone is not data correctness. Record activation time, SHA and commands in release evidence.

## Pause and rollback

Block new admissions; graceful SIGTERM to flush; verify final durable checkpoint. Pin prior compatible code/model/config, restore only after checking migration compatibility on a copy, replay from verified point and compare equity/IDs. Never restore a snapshot into an active writer. If no compatible rollback exists, keep service stopped and preserve evidence.
