# Rencana implementasi agent — CR-CATALOG-01

Goal: mengintegrasikan backlog lalu membangun lima unit yang dapat diuji mandiri. Architecture: extend registry/feature/judge/evaluator aktual; jangan membuat simulator atau ledger kedua. Stack: Python, pytest dan toolchain repo; dependencies optional tidak bocor ke runtime bot ringan.

Spec: seluruh kartu `03-candidate-specifications.md` dan kontrak `02-experiment-contract.md`. Pekerjaan dipisah per unit review; jangan menjalankan semua sekaligus.

## EXP-00 — Integrasi planning dan kontrak (sudah diterapkan ke manifest)

Dependency: audit manifest terbaru pada checkout lokal, bukan status percakapan. Baca master, spec strategies, ADR-003, tiap dependency di kartu.

Files: manifest, feature map, requirement traceability, status projections, spec strategies dan sprint baru di `docs/sprints/strategies/` atau domain owner sesuai tipe. Ikuti heading template sprint repo. Paket usulan ini tidak dihitung sebagai sprint DONE.

- [ ] Audit ID/fitur aktual dan scoped WIP; pertahankan kode user.
- [ ] Catat alokasi ancestry budget seluruh lima unit, reservasi ID, serta dependency exact-ID yang ada.
- [ ] Petakan available_at, abstain vs exit, partial-fill first timestamp dan cost quote ke public type aktual; konflik dicatat ADR, tidak diselesaikan lewat fallback.
- [ ] Buat lima sprint dari kartu dengan acceptance/test mapping dan gate data. Semua berstatus PLANNED sampai prerequisite DONE; data L2/cap gate tetap eksplisit meskipun dependencies selesai.
- [ ] Update manifest dan projections melalui mekanisme repo, validasi zero cycle/dangling refs dan status konsisten.
- [ ] Jalankan `python docs/quality/validate_planning.py --self-test` dan `git diff --check`; commit hanya file scoped; submit review. Tidak menjalankan strategi.

## File map implementasi yang diusulkan
Path harus dipetakan ke equivalent aktual sebelum RED; jangan mengasumsikan API dari nama file.

| Unit | Module baru bila belum ada | Config | Test |
|---|---|---|---|
| EXP-01 / H01 | src/indodax_lab/strategies/cross_sectional_reversal.py | configs/strategies/exp_h01.yaml | tests/unit/lab/strategies/test_cross_sectional_reversal.py |
| EXP-02 / H02 | src/indodax_lab/strategies/size_conditioned.py | configs/strategies/exp_h02.yaml | tests/unit/lab/strategies/test_size_conditioned.py |
| EXP-03 / H03 | src/indodax_lab/strategies/microprice.py | configs/strategies/exp_h03.yaml | tests/unit/lab/strategies/test_microprice.py |
| EXP-04 / O01 | src/indodax_lab/strategies/risk_contribution.py | configs/strategies/exp_o01.yaml | tests/unit/lab/strategies/test_risk_contribution.py |
| EXP-05 / O02 | src/indodax_lab/models/conformal_filter.py | configs/strategies/exp_o02.yaml | tests/unit/lab/models/test_conformal_filter.py |

Modules tidak boleh melakukan HTTP atau mengakses ledger. Config berisi semua baseline dari kartu, strict schema, logic/source IDs dan budget ancestry. Jangan menyalin implementation library eksternal sebelum cek lisensi.

## Siklus setiap task EXP-01 sampai EXP-05
Setiap task consumes frame/artifact dependency pada kartunya dan produces canonical intent atau filtered/allocated intent dengan reason+lineage. Sebelum coding, dokumentasikan nama tipe/metode aktual yang mengimplementasikan interface tersebut di handoff.

- [ ] Baca hanya kartu pilihan, kontrak bersama, dependency handoff dan affected modules.
- [ ] Bangun golden fixture literal sesuai kartu melalui public API; bandingkan expected numbers secara independen dari fungsi produksi.
- [ ] Tambah negative cases dari setiap acceptance kartu; beri nama semantik seperti `test_microprice_stale_quote_abstains` dan `test_conformal_quantile_uses_finite_sample_rank`.
- [ ] Run file test aktual dengan `python -m pytest <test-path> -q`; dokumentasikan behavior RED. Missing dependency/import saja bukan bukti guard rusak.
- [ ] Implementasi minimal pure transform, adapter registry dan strict config. Run ulang focused tests sampai GREEN.
- [ ] Tambah `tests/integration/lab/strategies/test_exp_h01_replay.py` atau unit ID terkait: real approved fixture -> feature/frame -> registered candidate -> public judge -> immutable result. Tidak boleh bypass quality dengan ID buatan.
- [ ] Uji SAME-01/TIME-01/DATA-01/COST-01/BUDGET-01; untuk pure math jangan menambah artificial concurrency test.
- [ ] Jalankan focused + affected regression sesuai testing spec; perubahan shared contract wajib full suite. Lint/diff-check; catat environment dan exact code SHA.
- [ ] Commit scope, buat handoff acceptance->test->command/exit; submit reviewer independen. Status REVIEW sampai verdict spec+quality PASS.

## EXP-06 — Pilot pembandingan
Dependency: unit pilihan review PASS dan SIM/EVAL/SPLIT gates selesai; tidak wajib menunggu unit BLOCKED_DATA. Tidak ada trading nyata.

- [ ] Preregister satu config baseline tiap unit dan keluarga pembanding sebelum membuka hasil; total pilot <=6 configs/unit dan sisa ADR-003 budget.
- [ ] Freeze shared eligible dataset/folds/capital/cost serta exclusion report; jika data tidak cukup, laporkan BLOCKED_DATA atau INSUFFICIENT_EVIDENCE.
- [ ] Jalankan judge melalui CLI aktual yang ditemukan dari repo; jangan menciptakan command seolah sudah tersedia.
- [ ] Persist semua outcome, net metric, cost stress, parameter lineage, fold/regime results dan trial count.
- [ ] Ablation satu perubahan saja: H01 regime, H02 cohort interaction, H03 signal vs no-signal benchmark, O01 vs C11, O02 filter on/off. Semua dihitung trial.
- [ ] Evaluator menerapkan gate existing; jangan tuning pada sealed holdout. Buat laporan per unit dengan keputusan archive/freeze/insufficient evidence.

## Handoff dan rollback
Handoff wajib menyatakan implemented/verified/reviewed/backtested sebagai empat status berbeda, path aktual, source SHA, commands, AC map, data exclusions, budget spent/remaining, reviewer findings dan next task. Bila reviewer tidak tersedia, simpan REVIEW pending; self-review tidak dihitung independen. Revert scoped code/config version bila gagal; preserve historical artifacts dan budget ledger.

## Current execution IDs

EXP-01 -> C13-01; EXP-02 -> C14-01; EXP-03 -> S10-01; EXP-04 -> C15-01; EXP-05 -> M07-01. Sprint resmi adalah sumber instruksi implementasi; EXP-06 tetap eksperimen dengan activation gate, bukan scheduler otomatis.
