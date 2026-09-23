# Production Main — Frozen Architecture v1.0

**Status:** FROZEN ARCHITECTURE  
**Branch:** `dev`  
**Freeze date:** 2026-09-21  
**Implementation baseline reviewed:** `c2567f59609050a533f1eab3545a763974d81a28`

This directory is the canonical architecture contract for the real-money production system. If older production/research documents conflict with this directory, this directory wins unless an explicit architecture decision supersedes it.

## 1. Purpose and boundary

Production Main is deliberately conservative. It consumes only reviewed, immutable candidate artifacts produced by Research Workbench. It does not provide a live strategy editor, model trainer, hyperparameter tuner, dataset editor, or online-learning path.

**Research is maximally customizable. Production is minimally customizable.**

Production may change only through a reviewed release.

## 2. Canonical runtime

```text
Indodax market/account evidence
        |
        v
Market Gateway
        |
Data Quality + Clock Guard
        |
Frozen Feature Runtime
        |
Frozen Strategy / Model Candidate
        |
Portfolio Constructor
        |
Independent Risk Engine
        |
PRE-WRITE AUTHORITY GATE
  - mode permits write
  - market + clock healthy
  - fresh reconciliation healthy
  - zero unresolved UNKNOWN orders
  - release/candidate identity verified
  - risk approval fresh
        |
        v
Durable OMS
        |
Indodax Venue Adapter
        |
Venue fills / order truth
        |
Fill Normalizer
        |
Durable Double-Entry Production Ledger
        |
Reconciler
        |
Audit / Metrics / Alerts
```

Only the Venue Adapter may issue exchange order writes. Dashboard, MCP, Telegram, research workers and strategy code never call Indodax order-write endpoints directly.

## 3. Authoritative state ownership

| State | Authority |
|---|---|
| Market evidence | canonical market-data store/gateway |
| Candidate identity | immutable candidate/release registry |
| Desired exposure | portfolio constructor |
| Approved exposure | independent risk engine |
| Order lifecycle | durable OMS |
| Venue truth | read-only venue evidence + reconciler |
| Financial accounting | durable double-entry production ledger |
| Execution mode | audited control-plane store |
| Approval evidence | durable signed/audited approval store |
| Operator UI | view/control client only, never source of financial truth |

## 4. Execution modes

Canonical modes:

```text
DISABLED
  -> RECOVERY
  -> READ_ONLY
  -> SHADOW
  -> MANUAL_APPROVAL
  -> AUTONOMOUS_LIMITED

ANY MODE -> HALTED
HALTED -> RECOVERY
```

There is no unrestricted `AUTONOMOUS` mode in frozen v1.0.

A process restart must enter **RECOVERY**, even if the previously requested mode was `AUTONOMOUS_LIMITED`. The prior mode may be remembered as desired state but may not be restored until recovery checks pass.

## 5. Candidate contract

Production receives a frozen candidate/release containing at minimum:

- candidate ID + version;
- strategy/pipeline manifest hash;
- model artifact hashes;
- feature schema/hash;
- supported pair/universe + timeframe;
- execution assumptions and allowed order semantics;
- risk policy hash;
- cost-policy identity;
- dataset/evidence references;
- Git SHA;
- dependency/environment identity;
- release digest/signature/provenance evidence;
- forward-shadow qualification evidence.

Production must fail closed on missing or mismatched identity.

No candidate mutates itself. Retraining or parameter changes create a **new candidate version**.

## 6. Real-money safety invariants

1. No withdrawal capability or withdrawal permission for the bot.
2. No blind retry after uncertain order submission.
3. `UNKNOWN` order state blocks new exposure until conclusively reconciled.
4. Reconciliation health is a mandatory write prerequisite, not an optional background check.
5. Fill ingestion is idempotent by venue fill identity.
6. Ledger + OMS must survive process restart without financial ambiguity.
7. Overfill, non-finite values, model mismatch, stale market data, unsafe clock, corrupted durable state and release mismatch fail closed.
8. Manual approval must be bound to the exact order/candidate and revalidated immediately before submission.
9. Kill-switch reset requires positive operator authorization plus fresh system-health evidence.
10. The UI cannot bypass backend safety gates.

## 7. Host responsibilities

**Lenovo workstation**
- research;
- historical data;
- training;
- backtests;
- candidate packaging;
- artifact signing/building.

**Production execution node**
- minimal Linux runtime;
- one authoritative writer;
- durable production state;
- exchange credentials;
- reconciliation;
- telemetry.

**ASUS X441U**
- Research Workbench runtime/shadow edge under [ADR-008](../../decisions/ADR-008-shared-market-runtime-and-asus-edge.md): public collection, shared features and selected CPU inference, isolated tournament and separate portfolio shadow;
- training remains on Lenovo; Production Main runs under a separate execution authority;
- optional observer/backup duties need independent resource/failure-domain qualification; co-resident workload is not independent HA;
- no shared SQLite WAL;
- no Production Main order-write credentials or second writer. See the [ASUS runtime design](../research-workbench/SHARED-MARKET-RUNTIME.md).

HA starts with one authoritative writer + observer. Automatic failover requires lease/epoch/fencing design and measured drills.

## 8. Observability

Mandatory telemetry domains:

- market freshness/gaps/clock;
- candidate/model identity and inference latency;
- risk/exposure/drawdown/rejections;
- OMS submit/ack/cancel/UNKNOWN;
- fill/fee/slippage;
- ledger integrity;
- reconciliation deltas/cursor age;
- process/CPU/RAM/disk/fsync/network/NTP;
- backup freshness and restore evidence.

Healthy state should be quiet. Warning/HALT/CRITICAL states receive progressively stronger presentation.

## 9. Change policy

Architecture in this directory is frozen v1.0. Changes require an ADR or explicit architecture revision. Normal implementation work, bug fixes, tests and operational evidence do not require changing the architecture unless they alter a boundary or invariant.

See:
- `SOP-AND-GATES.md`
- `IMPLEMENTATION-ROADMAP.md`
