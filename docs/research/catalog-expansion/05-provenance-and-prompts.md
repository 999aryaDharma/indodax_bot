# Provenance riset dan prompt agent

## Status bukti
Link berikut adalah lead sumber primer dari pencarian sebelumnya, bukan bukti hasil telah direplikasi. Isi penuh, dataset, biaya, lisensi dan applicability Indodax belum diaudit untuk paket ini. Rumus baseline kartu adalah rancangan eksperimen lokal, bukan salinan persis paper. Tidak ada klaim tren paling populer atau strategi terbukti untung.

| Lead | URL | Dipakai untuk audit |
|---|---|---|
| Size–Momentum Puzzle in Cryptocurrencies | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6628860 | H02: universe, period, ukuran vs liquidity, short exposure |
| Resolving Latency and Inventory Risk in Market Making | https://arxiv.org/abs/2505.12465 | Deferred market making: latency, inventory, simulator assumptions |
| Navigating Fill Probability vs Post-Fill Returns | https://arxiv.org/abs/2502.18625 | H03/S08: adverse selection, cost/fill validity |

## Mengadopsi plan publik
Setiap source record wajib URL, author jika terverifikasi, version/commit, tanggal akses, publication date terverifikasi, license/terms, dataset periode/universe, aturan entry/exit/sizing, assumptions fee/fill, original results vs reproduced results, adaptation delta dan availability limitations.

PUBLIC_IDEA -> SPECIFIED -> LICENSE_CHECKED (bila menyalin kode/data) -> OFFLINE_REPRODUCED -> LOCAL_ADAPTED -> OUT_OF_SAMPLE -> FORWARD. Stage dapat BLOCKED atau ARCHIVED; tidak melompati stage dengan screenshot profit.

Ide dapat ditulis ulang sebagai spesifikasi independen dengan atribusi. Source tersedia publik tidak berarti kode/data bebas disalin; lisensi unknown memblokir reuse kode, bukan pembacaan ide. Script TradingView harus diaudit repaint/lookahead, kapan pivot diketahui, closed-bar confirmation, costs, unavailable security series, dan revision history. Jangan menjalankan script download tanpa review.

## Prompt awal di VS Code
```text
Baca AGENTS.md, docs/specs/22-catalog-expansion-and-rl.md,
docs/specs/23-rl-allocation-feasibility.md dan manifest terbaru.
Integrasi EXP-00 sudah dilakukan. Jangan buat ID/sprint duplikat.
Periksa dependency sprint C13-01/C14-01/S10-01/C15-01/M07-01.
Kerjakan hanya sprint resmi yang READY setelah external data/budget gate
terpenuhi. Jika belum READY, lanjut prerequisite yang sah dari manifest.
R01-01 tetap spike experimental, tidak dijalankan otomatis.
```

## Prompt implementasi satu unit
```text
Kerjakan hanya unit EXP-01 (H01), setelah EXP-00 terintegrasi dan sprint
resminya READY serta data/dependency gates terverifikasi.
Baca sprint resmi, kartu H01 dan kontrak eksperimen bersama.
Petakan proposed files ke kode aktual. Bangun golden dan negative tests
H01-A sampai H01-F; buktikan behavior RED, implementasikan, lalu GREEN.
Uji public replay dan future perturbation; no API order, no fake lineage,
no same-close fill. Jangan memperluas ke H02 atau parameter search.
Commit scoped changes, tulis acceptance-to-evidence handoff pada SHA aktual
lalu REVIEW independen. Tanpa reviewer, berhenti pada REVIEW pending.
```

Untuk H02/H03/O01/O02 ganti unit dan acceptance yang dirujuk; tetap satu unit aktif. Goal besar mengarahkan tujuan, sprint lokal membatasi perubahan yang dapat diverifikasi model kecil.
