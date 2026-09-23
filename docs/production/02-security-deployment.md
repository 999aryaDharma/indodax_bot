# Security, secrets and deployment contract

## Credential classes

Pisahkan scope bila venue mendukungnya:

1. Public: market data, tanpa secret.
2. Account-read: balances, orders dan trades untuk reconciliation.
3. Order-write: create/cancel; hanya venue adapter.
4. Withdrawal: **forbidden pada seluruh bot host**.

Jangan gunakan personal all-powerful key untuk kenyamanan.

## Secret handling

- Secret tidak boleh committed, dilog, dimasukkan model artifact, atau dikirim ke dashboard client.
- .env hanya development convenience. Production injection harus memakai secret file/manager dengan permission ketat.
- Rotate setelah dugaan compromise, accidental logging, perubahan operator, atau policy periodik.
- Redact auth header, nonce, signature dan private payload dari exported evidence.
- Prefer least privilege dan IP restriction jika venue mendukungnya pada saat activation.
- Trading process berjalan sebagai dedicated unprivileged OS user.
- Remote administration private-network only.

## Artifact trust boundary

Allowed: locally produced, hashed and reviewed JSON, ONNX/UBJ, atau format lain yang telah diaudit.

Forbidden by default: arbitrary pickle/joblib, runtime download-and-execute, trust_remote_code, strategy Python upload dari public dashboard, dan mutable alias tanpa content hash.

## Repository controls

Sebelum live: protect main dan release refs, require green CI + independent review, larang direct push release, gunakan immutable tag/artifact, lakukan secret scan dan dependency audit.

Branch protection adalah GitHub repository setting; file repo saja tidak menegakkannya.

## Deployment topology

Minimum credible topology:

- primary production node: dedicated execution authority, SSD-backed, wired networking preferred;
- ASUS Research Runtime / Shadow Edge: public feed, shared features/inference dan paper state; tidak memiliki account/order-write credential pada composition shadow;
- independent production watchdog/backup: failure domain dan resource harus dikualifikasi; workload di ASUS yang sama bukan independent HA;
- Lenovo/research workstation: tidak punya order-write permission;
- backup target pada failure domain berbeda dari production disk.

Battery ASUS mengurangi satu failure mode saja; tidak menghapus disk, NIC, ISP, kernel, process atau venue failure.

Host roles mengikuti [ADR-008](../decisions/ADR-008-shared-market-runtime-and-asus-edge.md) dan [Shared Market Runtime](research-workbench/SHARED-MARKET-RUNTIME.md). Lenovo memiliki training; ASUS tidak menerima training jobs atau sweep. Public WebSocket token bukan private exchange key dan tidak memberi otoritas order. Token tetap tidak dicetak ke log; target injection memakai environment/file dengan permission minimum.

ASUS memakai satu runtime bersama dan, ketika diperlukan, satu inference subprocess dengan batas memory/deadline. Kandidat tidak menerima socket/HTTP client, arbitrary Python import, Docker socket atau kredensial. Candidate/manifes/model diverifikasi sebelum load; native/ONNX/quantized serving hanya setelah loader dan CPU parity qualification. Registered/LIVE model label tidak memberi izin deployment atau real-money execution.

## Supervision

Service supervisor harus memiliki bounded restart, readiness terpisah dari liveness, graceful termination, idempotent restart, durable checkpoint, dan stale-worker fencing.

Tidak ada shared SQLite WAL lintas host. Clock/NTP health adalah trading dependency. Jika order-write outcome uncertain, restart dimulai dalam read-only recovery dan reconciliation dilakukan sebelum order baru.
