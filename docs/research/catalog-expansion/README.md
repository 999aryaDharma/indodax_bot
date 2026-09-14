# Perluasan katalog riset — paket kerja agent

Tanggal: 2026-09-14. Status: spesifikasi terintegrasi, DOCUMENTED / NOT IMPLEMENTED.

Paket ini merinci penambahan hipotesis setelah baseline Wave 1, untuk lab trading Indodax paper/shadow LONG/FLAT. Proyek ini tidak dinyatakan sebagai skripsi; label riset akademis pada prompt percakapan sebelumnya bukan requirement pemilik.

## Urutan baca
1. `AGENTS.md`, master spec dan manifest sprint aktif.
2. [CR dan audit katalog](01-change-and-dedup.md).
3. [Kontrak eksperimen](02-experiment-contract.md).
4. [Kartu kandidat](03-candidate-specifications.md).
5. [Task dan gate implementasi](04-agent-task-plan.md).
6. [Sumber dan prompt](05-provenance-and-prompts.md).

## Batas otoritas
Manifest `docs/sprints/sprint-manifest.json` adalah status authority. Integrasi documentation EXP-00 sudah diterapkan; C13-01, C14-01, S10-01, C15-01 dan M07-01 berstatus PLANNED, tidak READY. Alias EXP-H01/H02/H03/O01/O02 dipertahankan untuk membaca kartu, bukan ID registrasi kedua. Jangan mengulang EXP-00.

## Hasil yang diharapkan
Agent dapat mengimplementasikan satu unit dengan input/output, rumus, parameter beku, golden case, kasus negatif, dan acceptance yang dapat dipetakan ke bukti. Tidak ada klaim kandidat profitable atau sudah diuji. Parameter di paket ini adalah baseline engineering untuk diregistrasi sebelum eksperimen, bukan hasil optimasi pasar.

## Integration update — authoritative current state

The proposal stage above is historical. User requested technical integration: EXP-00 documentation integration has now been applied to manifest as C13-01, C14-01, S10-01, C15-01 and M07-01. Use the official sprint specs and docs/specs/22-catalog-expansion-and-rl.md; do not repeat EXP-00 or create duplicate IDs. Implementation remains PLANNED. R01-01 now reads spec 23.
