# Production node build sheet

Status: DESIGN / NOT LIVE-READY. Current host allocation follows [ADR-009](../decisions/ADR-009-asus-production-and-research-runtime.md): ASUS is the Production Main host and also runs a separate Research Runtime. Co-resident capacity and deployment remain unqualified.

Dokumen ini adalah deployment skeleton for the existing live Production Main on ASUS. It does not authorize modifying live operation, credentials, deployment or execution policy; changes still require their scoped approvals and frozen release gates.

## Host roles

### ASUS `asus-server`
ASUS X441U/X441UV (`asus-server`) hosts Production Main and Research Runtime as separate services and authority domains. Production Main owns its frozen release and state; Research Runtime owns public collection, shared research features, qualified CPU inference, Tournament/Portfolio Shadow and research evidence. They use separate identities, roots, local databases, credentials and measured resource budgets. Neither service trains models. No shared SQLite WAL or second writer.

### Lenovo daily laptop
Runs ML/DL model training and tuning. It stages immutable model outputs for receiving-side verification on ASUS; Lenovo does not receive Production credentials or manage the ASUS Production process.

Baseline dari pemilik: Ubuntu Server 22.04.5 LTS x86_64; i3-6006U 2 core/4 thread ~2 GHz; RAM 4 GB; swap ~3.7 GB; tanpa compute GPU. Root/LVM ~98 GB dan usage ~51% adalah observasi historis untuk diukur ulang. Ethernet diprioritaskan atas Wi-Fi; Tailscale untuk administration/immutable transfer. Host berbagi CPU/RAM/disk/network dengan layanan lain. Swap adalah kapasitas darurat dan aktivitas swap memicu overload handling.

Detail input hardware, batas resource, benchmark rule/ML/DL dan thermal-soak ada di [Shared Market Runtime](research-workbench/SHARED-MARKET-RUNTIME.md#m-resource-governance-and-asus-qualification). Nilai CPU/RAM/model/queue limits harus berasal dari qualification, bukan spesifikasi laptop. ASUS menyimpan runtime artifacts dan recent evidence, bukan historical data lake. Optional watchdog/backup Production Main memerlukan failure-domain/resource qualification tersendiri.

## OS baseline

Gunakan supported Ubuntu LTS atau distribution lain yang mempunyai lifecycle/security update jelas. Catat exact OS image, kernel, Python runtime dan package lock sebagai release evidence.

Sebelum activation:
- automatic security update policy ditentukan;
- NTP/clock sync terverifikasi;
- SMART/storage health terukur;
- thermal behavior terukur;
- reboot/recovery drill dilakukan;
- filesystem free-space alert aktif.

## Service account

Buat dedicated unprivileged user, misalnya `indodaxbot`.

Rules:
- no interactive password login;
- no sudo untuk runtime;
- read-only access ke release bundle;
- write hanya ke state/log directories yang dibutuhkan;
- secret directory permission minimal;
- dashboard process tidak dapat membaca venue secret.

## Filesystem layout

~~~text
/srv/indodax-bot/
  releases/
    <release-id>/
  current -> releases/<release-id>
  state/
    ledger/
    oms/
    risk/
    reconciliation/
  logs/
  evidence/
  backups/
  secrets/
~~~

Release directory immutable setelah deployment. Runtime state tidak disimpan di dalam Git working tree.

SQLite/WAL hanya boleh berada di local filesystem. Jangan menaruh SQLite WAL di NFS/SMB/Tailscale share.

## Persistence choice

Untuk shadow dan bounded single-process micro-live, SQLite dengan WAL + FULL synchronous dapat diterima jika hanya ada satu writer authority dan restore drill lulus.

Jika OMS, ledger dan reconciler menjadi multi-process writers atau dipisah lintas host, migrasikan durable state ke transactional server database seperti PostgreSQL sebelum menambah concurrency. Jangan menggunakan shared SQLite sebagai pseudo-cluster.

## Planned services

Production service definitions below target ASUS Production Main with separate Production roots and identity. Research on ASUS uses `lab-shadow.service` (feed + features + shadow, one optional inference child); `lab-collector.service` is collection-only and mutually exclusive for the same feed/root; `lab-worker.service` remains Lenovo-only for qualified training/tuning jobs. At the audited `dev` SHA, `cli.shadow` and `cli.collector` are missing, while `cli.collect_market_stream` exists. [Entrypoint/cutover contract](research-workbench/SHARED-MARKET-RUNTIME.md#concrete-entrypoints-and-cutover) remains implementation work. This document does not activate services.

~~~text
indodax-market.service
indodax-trader.service
indodax-reconciler.service
indodax-control-api.service
indodax-backup.timer
indodax-healthcheck.timer
~~~

Untuk fase awal, OMS + ledger + venue adapter sebaiknya satu supervised trading process agar order state dan ledger transaction boundary lebih sederhana.

## systemd hardening baseline

Setelah path dan runtime stabil, service production seharusnya mengevaluasi directives berikut:

~~~text
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
LockPersonality=true
MemoryDenyWriteExecute=true
ReadWritePaths=/srv/indodax-bot/state /srv/indodax-bot/logs
~~~

Jangan menyalin directives secara buta; beberapa ML/native libraries dapat membutuhkan adjustment. Hardening diuji di shadow sebelum live.

## Network boundary

Production order writer:
- outbound HTTPS hanya ke dependency yang benar-benar dibutuhkan;
- admin via private overlay/VPN;
- tidak expose SSH publik;
- dashboard/control API tidak expose private venue secret;
- prefer Ethernet;
- DNS, TLS, route dan clock failures diklasifikasikan terpisah.

Jika venue mendukung IP allow-list pada activation time, gunakan.

## Secret layout

Contoh ownership:

~~~text
/srv/indodax-bot/secrets/
  account-read.env
  order-write.env
~~~

Withdrawal key tidak dibuat untuk bot.

Account-read dan order-write dipisah jika exchange mendukungnya. File permission minimum dan owner hanya runtime identity terkait.

## Release layout

Setiap release bundle harus mencakup:
- Git SHA;
- application version;
- Python/environment lock identity;
- candidate/model checksums;
- feature schema ID;
- cost schedule version;
- risk policy version;
- execution policy version;
- migration compatibility;
- evidence links.

Deployment menggunakan symlink atomic `current` hanya setelah preflight checks. Financial DB tidak pernah di-rollback bersama code.

## Startup preflight

Trading service start dalam READ_ONLY/RECOVERY dan melakukan:

1. verify release checksums;
2. verify config/candidate compatibility;
3. verify durable DB integrity;
4. restore risk halt/high-water state;
5. verify clock health;
6. fetch venue balances/open orders/recent fills;
7. reconcile unresolved order state;
8. verify market-data freshness;
9. only then enter authorized mode.

Kegagalan salah satu step meninggalkan service HALTED/READ_ONLY.

## Shutdown

Graceful shutdown:
- stop accepting new intents;
- persist causal checkpoint;
- finish or mark pending write as UNKNOWN;
- flush journal;
- write shutdown audit event.

Forced termination harus aman untuk recovery melalui reconciliation pada startup berikutnya.

## Backup

Minimum backup set:
- ledger/OMS/reconciliation DB;
- candidate/release bundle;
- risk/cost/execution config;
- reconciled venue cursor;
- audit incidents.

Backup target harus berbeda failure domain dari production disk. Backup success belum dianggap cukup sebelum restore test.

## Resource policy

Jangan menetapkan CPU/RAM limit dari tebakan. Jalankan representative shadow workload dan record:
- peak RSS;
- CPU saturation;
- disk write latency;
- SQLite checkpoint latency;
- API/inference latency;
- restart recovery duration.

Set systemd/container limits setelah ada headroom yang terukur. OOM pada trader adalah HALT-class event.

## Rollout sequence

1. SHADOW di production-shaped host.
2. private READ_ONLY reconciliation.
3. MANUAL_APPROVAL micro-live.
4. AUTONOMOUS_LIMITED dengan capital/universe sangat terbatas.
5. broader autonomy hanya setelah evidence review.

Tidak ada deploy yang sekaligus mengubah software, model, risk limits dan capital size tanpa isolated evidence.
