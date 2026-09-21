# Production Main — SOP and Release Gates

**Status:** FROZEN v1.0

Passing tests is necessary but never sufficient for real-money activation. Gates are cumulative.

## G0 — Repository truth

Required:
- reproducible fresh checkout;
- full CI green on the release SHA;
- strict lint/type/static checks for production modules;
- dependency lock/environment identity;
- secret/history scan;
- no critical dependency/security finding;
- protected release refs;
- auditable candidate/release provenance.

## G1 — Trusted data and judge

Required:
- causal/point-in-time data;
- no future/target leakage;
- train-only transforms;
- historical cost/fee policy versioned;
- unknown cost periods fail closed;
- deterministic ledger replay;
- simulator covers rejects, latency, partial fills and conservative fills;
- dataset quality evidence.

## G2 — Candidate evidence

Required:
- immutable candidate;
- strategy/model/config hashes;
- train/validation/sealed-test separation;
- failed trials retained;
- parameter-stability and cost-stress evidence;
- no test-period retuning;
- exact Git/environment identity.

## G3 — Forward shadow

Minimum:
- **>= 90 calendar days AND >= 100 closed forward trades**;
- no unresolved risk breach;
- no unresolved ledger/reconciliation incident;
- restart/recovery demonstrated;
- fee/slippage and regime evidence;
- candidate unchanged throughout qualification.

A 24-hour soak may prove infrastructure continuity but never replaces G3.

## G4 — Operational readiness

Required on target host:
- CPU/RAM/disk/network/API/fsync benchmark;
- p50/p95/p99 latency evidence;
- systemd/process supervision;
- liveness/readiness;
- clock/NTP guard;
- telemetry + alerts tested;
- backup and real restore drill;
- measured RPO/RTO;
- network/DNS/429/5xx/process-kill/disk-full/clock-jump drills;
- secret rotation rehearsal;
- current venue minimum order, fee/tax and API behavior verified.

## G5 — Private read-only venue proof

Use a dedicated Indodax key with view permission only; trade and withdrawal disabled.

Required:
- real account auth succeeds;
- balance/open-order/order-history/fill-history reads proven;
- timestamp/recvWindow behavior proven;
- auth failure, rate limit and outage handling observed;
- private payload redaction verified;
- production ledger/OMS reconciliation against venue truth over an extended run;
- cursor restart behavior proven;
- fee/tax evidence understood.

G5 never requires order-write credentials.

## G6 — Manual micro-live

Only after G0-G5 pass.

Required:
- one reviewed candidate;
- tiny bounded capital;
- narrow allowlisted universe;
- explicit human approval per order;
- fresh market + clock + reconciliation + risk revalidation immediately before write;
- order-write key has **no withdrawal permission**;
- fill-to-ledger-to-OMS-to-reconciliation closes correctly;
- operator present;
- incident procedure tested.

## G7 — Autonomous limited

Only after successful G6 evidence.

Required:
- bounded capital;
- bounded pairs/universe;
- bounded order notional/rate/daily loss/drawdown;
- immutable candidate;
- no online learning;
- no automatic model promotion;
- central risk authority;
- continuous reconciliation;
- auto-halt on stale market/model mismatch/reconciliation breach/UNKNOWN state;
- production observability and recovery proven.

## Restart SOP

Every startup:
1. enter RECOVERY;
2. verify release/candidate identity;
3. verify durable OMS and ledger integrity;
4. restore risk/high-water/kill state;
5. resolve UNKNOWN orders;
6. fetch venue balance/open orders/recent fills;
7. reconcile from durable cursor;
8. verify clock and market freshness;
9. verify alerts/telemetry;
10. only then permit transition to READ_ONLY/SHADOW/MANUAL_APPROVAL/AUTONOMOUS_LIMITED.

## Incident SOP

If financial or order state is uncertain:
- HALT NEW ORDERS;
- preserve evidence;
- do not invent or overwrite financial truth;
- reconcile venue vs OMS vs ledger;
- require explicit recovery signoff.

HALT does **not** imply automatic flattening.

## Promotion boundary from Research

Research can only submit a `request_promotion(candidate_id)` style request. Production promotion is a separate governed action. No MCP/LLM/dashboard action may directly bypass G0-G7.
