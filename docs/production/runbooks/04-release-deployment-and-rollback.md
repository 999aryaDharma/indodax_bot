# Runbook 04: Release Deployment and Rollback Governance

## Purpose

This runbook defines the verified deployment and rollback procedures for shipping hardened releases to a production node.

## Prerequisites & Pre-Flight Checks

Before any deployment, the candidate commit must satisfy all release gates:
1. **Target Branch:** Work is merged to `dev` and audited before promotion to release branch.
2. **Full CI Green:** `pytest` suite passes with zero unexpected skips and zero failures.
3. **Architecture Boundary Verified:**
   ```bash
   pytest tests/architecture/test_canonical_runtime_boundary.py -v
   ```
4. **No Secrets / Keys in Repo:** Git tree and config files must be audited for absence of private trade/withdraw secrets:
   ```bash
   pytest tests/unit/lab/security/ -v
   ```

## Deployment Procedure

### 1. Build and Verify Immutable Release Bundle

Generate the signed `ReleaseBundle`:
```python
from indodax_lab.verification.release_bundle import create_release_bundle

bundle = create_release_bundle(
    bundle_id="rel_20260921_01",
    git_commit_sha="<TARGET_GIT_SHA>",
    config_payload=open("config/production.json", "rb").read(),
    schema_payload=open("schema/oms_schema.sql", "rb").read(),
    author="lead_engineer",
)
with open("release_bundle.json", "w") as f:
    f.write(bundle.model_dump_json(indent=2))
```

### 2. Verify on Target Node

On the production node:
```python
from indodax_lab.verification.release_bundle import ReleaseBundle, verify_release_bundle

bundle = ReleaseBundle.model_validate_json(open("release_bundle.json").read())
verify_release_bundle(
    bundle,
    expected_git_sha="<TARGET_GIT_SHA>",
    config_payload=open("config/production.json", "rb").read(),
    schema_payload=open("schema/oms_schema.sql", "rb").read(),
)
print("Release bundle cryptographically verified.")
```

### 3. Progressive Promotion

Never jump directly from `DISABLED` to `AUTONOMOUS_LIMITED`. Follow the institutional mode progression:
1. **`DISABLED`:** Deploy files, verify SQLite schemas, verify database migrations.
2. **`READ_ONLY`:** Run MarketGateway, ClockGuard, and read-only reconciliation. Verify market feed freshness and balance matching.
3. **`SHADOW`:** Run shadow simulated orders. Compare simulated fills with exchange order book depth.
4. **`MANUAL_APPROVAL`:** Operator manually signs off each proposed order via CLI token.
5. **`AUTONOMOUS_LIMITED`:** Enabled only after 24h of clean shadow/manual approval cycles.

---

## Rollback Procedure

If anomalous behavior, unexpected exceptions, or severe slippage occurs:

### Step 1: Trip the Emergency Kill Switch
```bash
touch /var/run/indodax_bot/emergency_kill_switch
```

### Step 2: Switch Execution Mode to `DISABLED`
```python
pipeline.set_mode(ExecutionMode.DISABLED)
```

### Step 3: Checkpoint and Backup SQLite Databases
```bash
cp /data/oms_orders.sqlite3 /data/backups/oms_orders_pre_rollback.sqlite3
cp /data/reconciliation.sqlite3 /data/backups/reconciliation_pre_rollback.sqlite3
```

### Step 4: Checkout Previous Blessed Git SHA
```bash
git checkout <PREVIOUS_BLESSED_SHA>
```

### Step 5: Verify Bundle Integrity for Previous Release
```python
verify_release_bundle(previous_bundle, ...)
```

### Step 6: Boot Up in `READ_ONLY` Mode
Start the process in `READ_ONLY` mode and verify complete reconciliation before disarming the kill switch.
