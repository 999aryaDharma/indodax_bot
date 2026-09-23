# Trading Bot Research Lab — documentation entry point

## Frozen architecture precedence — 2026-09-21

The canonical target is [Frozen Systems](production/FROZEN-SYSTEMS.md): live Production Main plus the separate Research Workbench. Production Main on ASUS reads and operates against the real Indodax account; Research execution, shadow agents and tournaments also run on ASUS but remain isolated from Production state and authority. Lenovo handles ML/DL training and tuning. These owner-confirmed boundaries supersede conflicting older scope/host/UI statements below. Control-plane read API/UI work does not grant new trading authority or alter the running system.

Start current planning at [implementation program](implementation/README.md), [current state](implementation/CURRENT-STATE.md), [parity](implementation/RUNTIME-PARITY.md) and [LUNA-NEXT](implementation/handoff/LUNA-NEXT.md). The repaired sprint manifest remains the sole status/DAG authority. Historical Task15 WIP wording below describes the old planning baseline; current source exists and its review status must be checked, not assumed absent or complete.

Dokumentasi planning v2, 14 September 2026. Proyek **PARTIALLY IMPLEMENTED**. Production Main is live; Research Workbench, shadow and tournament environments are isolated research runtimes.

Mulai dari [master specification](specs/00-master-product-technical-spec.md), lalu [audit keadaan aktual](quality/repository-audit.md), [feature map](sprints/FEATURE-MAP.md), dan [sprint index](sprints/00-sprint-index.md).

## Cara menggunakan

1. Pemilik produk: baca master, roadmap, risk/open-decisions register dan release gates.
2. Implementer: baca `AGENTS.md`, manifest, satu sprint yang READY, serta Required Reading sprint itu.
3. Reviewer: checkout SHA handoff, baca checklist sprint, uji acceptance beserta failure path.
4. Operator: baca runbook sebelum mengaktifkan service atau memindahkan data.

Status berasal dari [manifest](sprints/sprint-manifest.json); seluruh 35 task lama dipetakan di [legacy crosswalk](sprints/LEGACY-TASK-CROSSWALK.md). Task 1–14 diimpor sebagai DONE berdasarkan evidence historis dan final review percakapan; bukan klaim test dijalankan ulang pada sesi dokumentasi ini. WIP Task 15 berada di worktree implementasi awal dan belum dianggap DONE.

## Peta dokumen

| Lokasi | Isi |
|---|---|
| `specs/` | Master, arsitektur, model data, subsystem contracts, roadmap |
| `sprints/` | Feature map, 92 unit kapabilitas, DAG, status, waves, handoffs |
| `research/` | Kontrak dataset rinci dan evidence checkpoint yang dipertahankan |
| `decisions/` | ADR, policy, batas ruang lingkup dan conflict resolutions |
| `quality/` | Audit repo, traceability, risk, validasi, release gates |
| `agent/` | Panduan Codex/Antigravity dan prompt operasional |
| `templates/` | Handoff, review, perubahan, eksperimen, insiden |
| `runbooks/` | Instalasi terkontrol, backup/restore, insiden, pengumpulan evidence |
| `production/` | Target infra real-money, security, OMS/reconciliation, SLO/DR, live release gates |
| `../.agents/` | Aturan kolaborasi, roles, workflows, orchestrator specification |

`docs/superpowers/` dipertahankan sebagai arsip baseline desain/plan. Bagian yang konflik mengikuti precedence master dan ADR v2. Dokumen baru tidak menyatakan provider terms, fee, kapasitas host, atau profitabilitas sudah diverifikasi saat ini.

Jalankan `python docs/quality/validate_planning.py` dari root repo untuk memeriksa struktur, DAG, status, reading links, dan pemetaan requirement.


## Production target

Dokumen [production infrastructure](production/README.md) adalah target future real-money yang fail-closed.
Ia tidak mengubah status proyek saat ini: research/shadow belum diotorisasi untuk live order execution.
