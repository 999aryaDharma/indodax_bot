# ASUS capacity cross-check — Bot Trade Program

Date: 2026-09-24. Classification: documentation/code cross-check plus owner-authorized read-only SSH inventory at 21:07:34–21:07:54 WITA; no benchmark or host mutation. Capacity verdict: **NOT YET QUALIFIED** for combined Production + WebSocket + multi-pair/multi-strategy shadow.

## Evidence and limits

Sources: [recorded host inventory](../decisions/CR-20260924-asus-production-and-research-host.md), [shared-runtime design](../production/research-workbench/SHARED-MARKET-RUNTIME.md), and `src/indodax_lab/orchestration/resources.py` inspected in this checkout.

| Item | Recorded fact | Planning consequence |
|---|---|---|
| CPU | Owner baseline i3-6006U ~2 GHz; inventory confirms 2 cores / 4 threads | Do not create one process or inference worker per strategy; SMT is not four independent compute cores |
| RAM | 4 GB nominal; 3.7 GiB visible; 1.9 GiB available at 00:24 WITA | Existing MEDIUM default requires 2.0 GB free and HIGH 4.0 GB; defaults are not host-qualified, and unit conversion must be explicit before comparison |
| Swap | 3.7 GiB total, 1.7 GiB used; final two one-second samples had zero swap-in/out | Swap occupancy alone does not prove current thrashing, and swap is not additional model capacity; sustained activity must be measured |
| Storage | 98 GiB root; 29 GiB free at snapshot | Historical backfill, raw WebSocket records, journals and checkpoints compete for the same disk; bound intake, retention and archive backlog |
| Co-tenants | Several Docker services; one restarting container | Benchmark with actual co-tenants and Production activity, not only an idle synthetic process |
| Qualification | OPS-01 and QA-03 are REVIEW; old fixtures are not mixed-load proof | Do not publish a supported agent/pair count or enable larger deployment from documentation alone |

### Fresh SSH inventory

The table above preserves the earlier snapshot. A new read-only SSH check on `asus-server`, authorized by the owner during this task, confirms Ubuntu 22.04.5 LTS, kernel 5.15.0-187-generic and Intel Core i3-6006U @ 2 GHz, 2 physical cores / 4 threads. Results at 21:07:34–21:07:54 WITA (13:07:34–13:07:54 UTC):

- RAM total 3,988,918,272 bytes; available 2,037,891,072 bytes (1.90 GiB). Available RAM includes reclaimable cache; free-only memory was 304,742,400 bytes.
- Swap total 3,991,924,736 bytes; used 1,873,608,704 bytes (1.74 GiB). Four interval rows of `vmstat 1 5` reported zero swap-in/out; the first row is a since-boot average and is not an interval measurement.
- Root volume total 105,089,261,568 bytes; available 27,972,718,592 bytes (26.05 GiB); 72% used, inode use 26%.
- Load average 1.63 / 1.81 / 1.93. Four interval CPU-idle samples were 71%, 66%, 74%, 66%; this is not sustained spare throughput proof.
- `x86_pkg_temp` and ACPI temperature both reported 65°C, PCH 57.5°C. Exposed per-core/package throttle counters were zero. Other generic thermal zones were not used as valid CPU thermal evidence.
- PSI memory `some avg10=0.09`, `full avg10=0.04`; I/O `some avg10=1.68`, `full avg10=1.45`. These snapshots must not be substituted for workload latency measurements.
- Docker listed 30 containers: 29 Up and `bimbel_queue` Restarting. `rbta-service` and `rbta-hotfix-replay` were Up/healthy. Names/status alone do not verify their trading configuration or release identity.
- Two failed systemd session scopes were listed; no failed trading service was identified by that listing. Running services include two GitHub Actions runners and Docker, so bursty build/deploy co-tenant load belongs in qualification scenarios.

Commands used only host metadata/resource reads: `date -Is`, `uname -r`, `lscpu`, `free -b`, `df -B1 /`, `df -i /`, `uptime`, `vmstat 1 5`, `ps -eo comm,pcpu,pmem,rss --sort=-rss`, `systemctl --failed`, `systemctl list-units --type=service --state=running`, `docker stats --no-stream` with name/CPU/memory/PID fields, `docker ps` with name/status fields, `/etc/os-release`, thermal-zone type/temp and thermal-throttle counters, and `/proc/pressure/{cpu,memory,io}`. Both SSH calls exited 0. No environment/config secrets, container inspect payloads, logs, trading database or account/order endpoints were accessed.

**Interpretation:** about 1.90 GiB available RAM and an already shared two-core CPU warrant bounded admission and incremental tests. Container memory limits are not reserved capacity, and their sum is not available host memory. This inspection does not justify a fixed supported strategy/pair/model count. The existing MEDIUM/HIGH defaults still require measured host-specific qualification, not lowering thresholds merely to admit work.

### Physical disk and mount-specific capacity correction

The owner's follow-up correctly distinguishes the 500 GB physical disk from the root filesystem. Additional read-only inspection at 21:10:06–21:11:43 WITA returned:

| Device / mount | Provisioning / observed usage |
|---|---|
| Physical `/dev/sda` | 500,107,862,016 bytes (500 GB decimal) |
| Root LV `/` | 100 GiB logical volume; ext4 reports 98 GiB total, 67 GiB used, approximately 26.05 GiB available |
| Projects LV `/srv/storage` | 300 GiB logical volume; ext4 reports 295 GiB total, 1.1 GiB used, 279 GiB available |
| Docker LV `/var/lib/docker` | 50 GiB logical volume; ext4 reports 49 GiB total, 360 MiB used, 47 GiB available |
| EFI and boot | Approximately 1.05 GiB and 2 GiB partitions |

Thus root available space is **not** whole-machine available space. LVM free extents remain unknown: `sudo -n pvs/vgs/lvs` required a password and were not escalated through another mechanism. No resize, remount, relocation or deletion was performed.

Largest reported usage categories:

- Docker daemon reports 104 images, 43.93 GB total, 29.45 GB reclaimable; build cache 4.818 GB total, 2.803 GB reclaimable. These are daemon accounting figures; shared layers/cache can overlap and reclaimable is not a deletion recommendation or guaranteed recovered bytes.
- Accessible directory scan reports approximately 4.9 GiB under `/home/kesawa`, chiefly two Actions runner directories at 2.3 GiB each; `/srv/rbta-iso/data` approximately 4.1 GiB; `/var/log/journal` approximately 1.7 GiB; `/srv/bimbel-staging` approximately 880 MiB.
- Docker reports `DockerRootDir=/var/lib/docker` and `driver-type=io.containerd.snapshotter.v1`. `/var/lib/containerd` exists with root-only access; its size could not be read. Containerd image storage is a plausible explanation for high image accounting with low Docker-mount use, but exact physical attribution is **unverified**. The permission-denied `du` result of 4 KiB is directory metadata, not its content size.
- Directory scans are partial because root-only paths are unreadable and scans were time-bounded at idle I/O priority. They do not reconcile all root filesystem bytes. No secret/config or trading data file contents were read.

Added commands: `lsblk -b -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS`, `df -hT`, `docker system df`, narrowly formatted `docker info`, permission metadata and bounded `du -x` directory-size scans. Root/srv/data storage remains in place.

**Required planning correction:** OPS-01/JOB-02 must resolve the actual filesystem for each configured data, journal, model, temporary and archive path; enforce per-mount free-space/inode and I/O budgets. `/srv/storage` is a candidate for a separately reviewed Research data root, not automatic approval to move Production state. Separate logical volumes still share the same physical disk and contend for I/O. New path selection or migration requires explicit ownership, permissions, byte verification and rollback; no capacity plan may assume 279 GiB of projects space is already available at a root-resident path.

## Required topology

Production and Research remain separate processes, identities, roots, local state stores, credentials and resource budgets on ASUS. Production independently owns its feed health/account truth. Deduplication is within each authority plane, not shared financial state or a shared Research feed health flag.

Research owns one centrally managed subscription set for the union of admitted input requirements, with a protocol-compliant bounded number of connections; there is no WebSocket connection per strategy. Reuse durable canonical events, bounded feature windows, and compatible feature snapshots. Load/infer a model once per compatible artifact/schema/input/trigger identity within the Research plane; candidate-specific model state and financial state remain isolated. Production can reuse code but independently owns its execution inputs and budgets.

One supervised Research composition uses bounded in-process consumers and the existing design's optional bounded inference child. One writer per local SQLite store; batch immutable publication without skipping durability. Candidate count, pair count, unique feature sets, model footprints, trigger rates, journal rate and network channels all affect capacity. Top 10 display size is not an active-agent limit.

Training/tuning stays on Lenovo. Backtests remain on ASUS as selected by the owner, but jobs are deferred when the measured admission budget is unavailable. Historical backfill is also optional admission-controlled work, never unlimited download alongside live workloads. Do not silently move execution to another host or enable a service.

## Implementation ownership and acceptance

| Owner | Required addition |
|---|---|
| DATA-07 | Existing JOB-01/JOB-02 admission and bounded rate/window processing; yield/defer on insufficient host headroom; reuse existing data and preserve durable resume |
| RP-04 | Shared subscription ownership, bounded fan-out and slow-consumer handling; no agent-specific polling loop or unbounded event backlog |
| RW5-01 | New agent admission reserves measured incremental resources; slow agent pauses with gap evidence without corrupting another agent or blocking Production |
| RW6-01 / PM-08 | Benchmark central capital arbitration and exact candidate set with Production-like fill/checkpoint rates |
| JOB-02 | Extend the existing admission owner with fresh finite CPU/RAM/disk/thermal/swap and deadline evidence; unknown required sensors block new work; no separate competing governor |
| OPS-01 | Separate measured service budgets and containment; Research sheds optional work before Production deadlines, ledger durability or safety are impaired |
| QA-03 | Qualify the exact mixed workload and publish measured safe limits plus rejected overload scenarios |
| PM-06 | Refuse integrated release qualification without applicable capacity evidence for its workload fingerprint |

The affected REVIEW task handoffs remain historical evidence; these additional cases are unverified and do not inherit old checked boxes or PASS statements.

## Qualification procedure

1. Refresh read-only host/process/storage/thermal inventory under a separately authorized qualification run. Pin code, models, runtime policy, co-tenants, candidate set, pair/channel/timeframe set, feature schemas and trigger frequency. Pre-register Production freshness, decision/reconciliation latency, recovery and memory/disk limits before load tests.
2. On an isolated representative replay environment, start with the intended Production candidate set plus Research 1 pair / 1 rule agent. Then 3 pairs / 3 agents, then 5 pairs / 10 agents. Advance only after the previous workload passes. These are test dimensions, not deployment targets or certified limits.
3. Continue the existing shared-runtime matrix only as headroom permits: more rule agents; shared classical ML artifacts; one small CPU DL artifact only after its measured peak load/inference footprint fits. Vary order-book traffic, feature count, trigger rate, partial fills, write/checkpoint cadence, dashboard reads and backfill/backtest coexistence independently.
4. Run 30-minute load windows, several-hour thermal runs and a 24h+ isolated shadow soak. Replay observed bursts at 1x/2x/5x/10x with explicit synthetic-load labels; injected failures run in isolated test namespaces, never against live orders or services.
5. Record CPU, peak RSS/available bytes, swap-in/out, throttling, disk reserve/growth/write latency, queue items/bytes/event lag, inference p50/p95/p99, Production decision and reconciliation latency, missed deadlines, recovery and archive backlog. Report source timestamps and unknown sensors explicitly.
6. Pass requires registered budgets met under realistic mixed load, zero silent critical event loss, no sustained swapping, bounded queues, no accounting violation, successful restore/recovery and demonstrated Research shedding before Production deadlines fail. Budget breaches reject new admission or pause/defer affected Research work. Unrecoverable feed/storage pressure yields explicit unavailable/paused state, not healthy fake continuity.
7. Publish measured maximum admitted workload and its fingerprint, headroom, rejection reasons and expiry/change conditions. Hardware, co-tenant, model, feature, trigger or runtime changes require requalification. No generic numeric capacity is inferred from CPU/RAM specifications.

## Conclusion

The proposed topology can be constrained to this host, but present evidence cannot establish how many agents/pairs/models it can safely run. The program therefore remains capacity-gated. Existing 24h+ infrastructure soak also does not replace the 90-day AND 100-closed-trade strategy qualification gate.
