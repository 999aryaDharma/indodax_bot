# Target production architecture

## Objective

Pisahkan research plane, control plane dan execution plane sehingga bug training, dashboard, atau research worker tidak bisa menempatkan atau menggandakan order.

~~~text
Research workstation / Lenovo
        |
        | immutable hashed candidate bundle
        v
Artifact registry
        |
        v
Production trading node <---- market/account data ----> Indodax
        |
        +---- encrypted evidence / backup
        |
        +---- telemetry ----> Watchdog / ASUS ----> alerts
~~~

## Production trading node

Urutan logical modules:

~~~text
Market Gateway
 -> Data Quality + Clock Guard
 -> Feature Runtime
 -> Frozen Strategy / Model Runtime
 -> Portfolio Constructor
 -> Independent Risk Engine
 -> OMS
 -> Venue Adapter
 -> Fill Normalizer
 -> Double-entry Ledger
 -> Reconciler
~~~

Hanya venue adapter boleh melakukan private order-write. Dashboard/API mengakses audited control plane, tidak pernah exchange adapter secara langsung.

## Research workstation

Owns backfill, experiment generation, ML/DL training, sealed evaluation, dan candidate packaging. Production tidak boleh import mutable research working directory.

Candidate bundle minimal menyimpan model/strategy ID dan version, Git SHA, feature schema/hash, cost/risk/execution policy versions, environment identity, training/validation/sealed evidence refs, artifact checksum/signature, dan compatibility metadata.

## Watchdog node

ASUS X441U kelak cocok sebagai lightweight independent observer untuk heartbeat production node, exchange reachability, stale-data alarm, reconciliation alarm dan backup freshness.

ASUS tidak boleh share SQLite WAL melalui NFS/SMB dan tidak boleh menjadi second unsupervised order writer.

## State ownership

| State | Authoritative owner |
|---|---|
| Raw market evidence | immutable market-data store |
| Candidate artifact | artifact registry |
| Desired exposure | portfolio constructor |
| Approved exposure | risk engine |
| Order lifecycle | OMS |
| Exchange truth | reconciler via venue read API |
| Financial accounting | double-entry ledger |
| Operator mode | audited control plane |

UI tidak pernah menjadi financial source of truth.

## Execution modes

DISABLED -> READ_ONLY -> SHADOW -> MANUAL_APPROVAL -> AUTONOMOUS_LIMITED -> AUTONOMOUS.

HALTED dan RECOVERY dapat dimasuki dari mode mana pun. Transisi bersifat durable audit event; browser toggle tidak boleh melompati gate.
