# Strategy Research Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mengembangkan bot sinyal Indodax saat ini menjadi lab riset reproducible yang mengumpulkan data, menjalankan banyak strategi/ML/DL secara background saat resource tersedia, mengevaluasi net-of-cost, dan mempromosikan hanya kandidat yang lolos historical + forward paper gates.

**Architecture:** Pertahankan runtime bot lama di modul datar `src/*.py` selama Phase 0. Tambahkan package berdampingan `src/indodax_lab/` dengan aliran immutable wire → bronze → silver → gold, judge event-driven, model registry, dan paper shadow. ASUS menjalankan collector/sentry/paper ringan; Lenovo menjalankan backtest/training melalui durable local queue dan idle guard.

**Tech Stack:** Python 3.11–3.13, pytest/Hypothesis, pandas/pandas-ta, PyArrow/Parquet, DuckDB, SQLite, scikit-learn, XGBoost, Optuna, APScheduler/systemd, psutil; PyTorch hanya pada optional DL environment.

## Global Constraints

- Design source of truth: [`../specs/2026-08-06-strategy-research-lab-design.md`](../specs/2026-08-06-strategy-research-lab-design.md).
- Dataset source of truth: [`../../research/dataset-feature-contracts.md`](../../research/dataset-feature-contracts.md).
- Scope tetap read-only market/account access + paper/shadow. Jangan menambahkan endpoint buy, sell, cancel, atau withdraw.
- Jangan memindahkan seluruh `src/*.py` ke package baru dalam satu perubahan. Compatibility bridge harus kecil dan diuji.
- Jangan mengubah atau menghapus `logs/paper_trades.db` dan `logs/positions.db` yang sudah ada; migrasi harus copy/backup-first dan idempotent.
- Unit/integration tests tidak boleh membutuhkan network, Telegram, API secret, waktu nyata, atau timezone lokal.
- Gunakan UTC aware timestamps dan `Decimal`/integer units untuk ledger; `float64` hanya untuk feature/model analytics.
- Semua signal memakai closed data dan earliest next-event/next-open fill. Same-bar TP+SL ambigu = SL first.
- Semua tuning memakai train + inner validation. `2024`, `2025`, dan forward paper tidak boleh menjadi tuner objective setelah dibuka sesuai split policy.
- R01/RL tidak diimplementasikan dalam plan ini; ia memerlukan design/approval terpisah setelah supervised/classical lab stabil. Sentiment/on-chain multimodal juga tetap deferred.
- Setiap task menggunakan red → green → refactor, menjalankan command verifikasi yang disebutkan, lalu commit kecil. Jangan menggabungkan task yang belum lolos checkpoint.
- Data/model besar berada di `lab-data/` dan `lab-artifacts/`, bukan Git.
- Jangan membuka PR atau merge sampai pemilik meminta. Plan ini hanya mengotorisasi implementasi pada branch kerja yang dipilih saat eksekusi.

---

## Tranche A — Phase 0: Trust the Existing Base

### Task 1: Tambahkan test harness dan CI tanpa secret

**Files:**

- Create: `requirements-dev.txt`
- Create: `pyproject.toml`
- Create: `tests/conftest.py`
- Create: `tests/unit/test_repository_smoke.py`
- Create: `.github/workflows/ci.yml`
- Modify: `.gitignore`

- [ ] **Step 1: Tulis smoke test yang membuktikan modul baseline dapat diimpor**

```python
# tests/conftest.py
import os

os.environ.setdefault("INDODAX_API_KEY", "test-read-only-key")
os.environ.setdefault("INDODAX_SECRET_KEY", "test-secret")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:test-token")
os.environ.setdefault("TELEGRAM_CHAT_ID", "123")
```

```python
# tests/unit/test_repository_smoke.py
def test_baseline_modules_import() -> None:
    import config
    import indodax_api
    import risk_manager
    import signal_logic

    assert config.APP_CONFIG.app_name == "IndoBot Signal (IBS)"
    assert callable(indodax_api.fetch_ohlcv)
    assert callable(risk_manager.calculate_trading_plan)
    assert callable(signal_logic.evaluate_signal)
```

- [ ] **Step 2: Jalankan test dan konfirmasi gagal karena pytest config/dependency belum ada**

Run: `python -m pytest tests/unit/test_repository_smoke.py -q`
Expected: FAIL bila pytest belum tersedia atau `src` belum ada pada import path.

- [ ] **Step 3: Tambahkan dependency/tool configuration minimal**

```text
# requirements-dev.txt
-r requirements.txt
pytest>=8,<10
pytest-cov>=5,<8
hypothesis>=6,<7
ruff>=0.8,<1
```

```toml
# pyproject.toml
[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
addopts = "-ra --strict-markers"

[tool.ruff]
target-version = "py311"
line-length = 100
extend-exclude = [
  "src/config.py",
  "src/indodax_api.py",
  "src/main.py",
  "src/paper_trader.py",
  "src/position_tracker.py",
  "src/risk_manager.py",
  "src/signal_cache.py",
  "src/signal_logic.py",
  "src/ta_processor.py",
  "src/telegram_bot.py",
]

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]
```

Flat baseline modules are temporarily excluded from repo-wide lint to avoid mixing a mechanical cleanup with Phase 0 correctness fixes. New `src/indodax_lab/` code and all tests remain linted; legacy modules get focused behavior tests whenever modified.

- [ ] **Step 4: Tambahkan CI read-only**

`.github/workflows/ci.yml` harus checkout, setup Python 3.11, install `requirements-dev.txt`, lalu menjalankan:

```bash
python -m pytest -q
ruff check src tests
```

- [ ] **Step 5: Ignore runtime artifacts**

Tambahkan `lab-data/`, `lab-artifacts/`, `.pytest_cache/`, `.ruff_cache/`, dan `__pycache__/` tanpa menghapus rule lama.

- [ ] **Step 6: Verifikasi dan commit**

Run: `python -m pytest tests/unit/test_repository_smoke.py -q && ruff check src tests`
Expected: PASS.

```bash
git add requirements-dev.txt pyproject.toml tests .github/workflows/ci.yml .gitignore
git commit -m "test: add offline test harness and CI"
```

### Task 2: Perbaiki kontradiksi RR bullish

**Files:**

- Modify: `src/config.py`
- Create: `tests/unit/test_risk_config.py`
- Create: `tests/unit/test_risk_manager.py`

- [ ] **Step 1: Tulis invariant test yang saat ini gagal**

```python
# tests/unit/test_risk_config.py
from config import RISK_CONFIG


def test_default_bull_rr_can_pass_gate() -> None:
    configured_rr = RISK_CONFIG.tp_atr_multiplier / RISK_CONFIG.sl_atr_multiplier
    assert configured_rr >= RISK_CONFIG.min_rr_ratio
```

Run: `python -m pytest tests/unit/test_risk_config.py -q`
Expected: FAIL karena `2.5 / 1.5 < 2.0`.

- [ ] **Step 2: Jadikan config koheren**

Di `RiskConfig`, ubah `tp_atr_multiplier` menjadi `3.0` dan comment menjadi “gross RR 1:2 sebelum biaya”. Jangan menurunkan `min_rr_ratio` tanpa design amendment.

- [ ] **Step 3: Tambahkan kalkulasi plan test**

Buat factory `SignalDecision`/`TAResult` minimal di test dan buktikan `calculate_trading_plan()` tidak mengembalikan `None`, RR `>=2`, serta actual risk tidak melebihi configured max untuk saldo Rp500.000.

- [ ] **Step 4: Verifikasi seluruh risk path**

Run: `python -m pytest tests/unit/test_risk_config.py tests/unit/test_risk_manager.py -q`
Expected: PASS.

```bash
git add src/config.py tests/unit/test_risk_config.py tests/unit/test_risk_manager.py
git commit -m "fix: make bullish risk reward gate reachable"
```

### Task 3: Koreksi parser Trade API v2 dan timestamp unit

**Files:**

- Modify: `src/indodax_api.py`
- Create: `tests/fixtures/indodax/my_trades_v2.json`
- Create: `tests/unit/test_indodax_trade_v2.py`

- [ ] **Step 1: Simpan fixture resmi yang diperkecil**

```json
{
  "data": [
    {
      "tradeId": "72057594037936570",
      "orderId": "aaveidr-limit-3568",
      "clientOrderId": "clientx-1",
      "symbol": "aaveidr",
      "price": "1564455",
      "qty": "0.1",
      "quoteQty": "156445.5",
      "commission": "468",
      "commissionAsset": "idr",
      "isBuyer": false,
      "isMaker": false,
      "time": 1723442692520
    }
  ]
}
```

- [ ] **Step 2: Tulis test parser murni sebelum menyentuh HTTP**

Test wajib membuktikan side `sell`, amount `0.1`, quote quantity, commission, maker flag, dan timestamp `1723442692520` tetap millisecond pada contract raw.

Run: `python -m pytest tests/unit/test_indodax_trade_v2.py -q`
Expected: FAIL karena parser masih membaca `type`, `amount`, dan contract lama.

- [ ] **Step 3: Perluas `TradeRecord` dengan compatibility property**

```python
@dataclass
class TradeRecord:
    pair: str
    trade_id: str
    order_id: str
    price: float
    amount: float
    quote_amount: float
    commission: float
    commission_asset: str
    is_buyer: bool
    is_maker: bool
    timestamp_ms: int

    @property
    def trade_type(self) -> str:
        return "buy" if self.is_buyer else "sell"

    @property
    def timestamp(self) -> float:
        return self.timestamp_ms / 1000.0
```

- [ ] **Step 4: Ekstrak `_parse_my_trades_v2(payload, pair)`**

Parser memakai `isBuyer`, `qty`, `quoteQty`, `commission`, `commissionAsset`, `isMaker`, dan `time`. `fetch_recent_trades()` hanya mengurus signed request lalu memanggil parser. Jangan mock `_SESSION` di parser unit test.

- [ ] **Step 5: Update consumer dan test sort**

`is_pair_already_held()` memakai `timestamp_ms` untuk sort dan `trade_type` compatibility property. Tambahkan test record newest-buy/newest-sell.

- [ ] **Step 6: Verifikasi**

Run: `python -m pytest tests/unit/test_indodax_trade_v2.py -q`
Expected: PASS tanpa network.

```bash
git add src/indodax_api.py tests/fixtures/indodax/my_trades_v2.json tests/unit/test_indodax_trade_v2.py
git commit -m "fix: parse Indodax Trade API v2 contract"
```

### Task 4: Betulkan fee/cost-basis paper trading

**Files:**

- Modify: `src/paper_trader.py`
- Create: `src/paper_accounting.py`
- Create: `tests/unit/test_paper_accounting.py`
- Create: `tests/integration/test_paper_db_migration.py`

- [ ] **Step 1: Tulis round-trip accounting test**

Untuk cash budget Rp100.000, entry Rp10.000, buy fee 0,2%, exit Rp11.000, sell fee 0,4%, test harus membuktikan:

```text
buy_fee       = 200
buy_notional  = 99_800
base_qty      = 9.98
sell_notional = 109_780
sell_fee      = 439.12
net_credit    = 109_340.88
pnl           = 9_340.88
```

Run: `python -m pytest tests/unit/test_paper_accounting.py -q`
Expected: FAIL karena model lama menyimpan effective IDR sebagai cost basis.

- [ ] **Step 2: Implement pure Decimal accounting**

```python
# src/paper_accounting.py
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class BuyFill:
    cash_debit: Decimal
    fee: Decimal
    notional: Decimal
    base_qty: Decimal


def account_buy(cash_budget: Decimal, price: Decimal, fee_rate: Decimal) -> BuyFill:
    fee = cash_budget * fee_rate
    notional = cash_budget - fee
    return BuyFill(cash_budget, fee, notional, notional / price)
```

Tambahkan `SellFill`/`account_sell()` dan `realized_pnl = net_credit - buy.cash_debit`.

- [ ] **Step 3: Buat migration idempotent**

Tambahkan kolom nullable `gross_cash_debit`, `base_qty`, `buy_notional`, `buy_fee`, `sell_notional`, `sell_fee`, `net_cash_credit`, `cost_model_id`. Gunakan `PRAGMA table_info` sebelum `ALTER TABLE`; jangan menulis ulang existing rows tanpa explicit migration rule.

- [ ] **Step 4: Gunakan fields baru untuk trade baru**

`open_trade()` menyimpan gross debit dan quantity. `close_trade()` menghitung proceeds dari quantity, lalu PnL terhadap gross debit. Legacy rows tetap terbaca dengan `accounting_status=LEGACY_ESTIMATE` pada report.

- [ ] **Step 5: Verifikasi pure math dan temp SQLite migration**

Run: `python -m pytest tests/unit/test_paper_accounting.py tests/integration/test_paper_db_migration.py -q`
Expected: PASS; integration test hanya memakai `tmp_path`.

```bash
git add src/paper_accounting.py src/paper_trader.py tests/unit/test_paper_accounting.py tests/integration/test_paper_db_migration.py
git commit -m "fix: preserve paper cash cost basis and fees"
```

### Task 5: Pisahkan observasi sinyal dari callback dan resolve intrabar

**Files:**

- Create: `src/signal_observer.py`
- Modify: `src/main.py`
- Modify: `src/paper_trader.py`
- Create: `tests/unit/test_barrier_resolution.py`
- Create: `tests/integration/test_signal_observation.py`

- [ ] **Step 1: Tulis barrier test**

```python
def test_same_bar_stop_and_target_is_stop_first() -> None:
    result = resolve_barriers(
        bar_high=112, bar_low=88, stop_loss=90, take_profit=110
    )
    assert result.reason == "SL"
    assert result.fill_price == 90
```

Tambahkan cases TP-only, SL-only, dan no-touch.

- [ ] **Step 2: Implement pure resolver**

`resolve_barriers()` menerima OHLC/high-low yang sudah final dan `same_bar_policy="SL_FIRST"`. Tidak memanggil API atau DB.

- [ ] **Step 3: Tambahkan `signal_observations`**

Simpan setiap evaluated candidate dengan `decision_ts`, pair, strategy/version, score, pass/fail, reason, planned entry/SL/TP, dataset/runtime version, dan later outcome. Manual Telegram callback disimpan pada field/table terpisah dan tidak menentukan apakah observation ada.

- [ ] **Step 4: Wire sebelum Telegram callback**

Pada `_process_pair()`, record decision deterministically setelah evaluation/risk plan. Jika shadow policy mengizinkan, buka paper observation otomatis; tombol user hanya mencatat action intent.

- [ ] **Step 5: Ubah monitor menggunakan closed 15m candle range**

Polling ticker boleh tetap untuk display, tetapi outcome canonical memakai bar high/low sejak last evaluated close. Simpan last processed bar ID agar restart tidak menutup dua kali.

- [ ] **Step 6: Verifikasi**

Run: `python -m pytest tests/unit/test_barrier_resolution.py tests/integration/test_signal_observation.py -q`
Expected: PASS dan callback tidak diperlukan untuk membuat observation.

```bash
git add src/signal_observer.py src/main.py src/paper_trader.py tests/unit/test_barrier_resolution.py tests/integration/test_signal_observation.py
git commit -m "fix: record all signals and resolve intrabar outcomes"
```

### Task 6: Phase 0 regression checkpoint

**Files:**

- Create: `tests/regression/test_phase0_invariants.py`
- Create: `docs/research/phase0-verification.md`

- [ ] **Step 1: Gabungkan invariant P0 dalam satu regression test**

Test mencakup RR reachable, API v2 fields/units, paper round-trip reconciliation, observation tanpa callback, same-bar SL-first, dan no-network marker.

- [ ] **Step 2: Jalankan seluruh suite**

Run: `python -m pytest -q`
Expected: PASS.

Run: `ruff check src tests`
Expected: PASS.

- [ ] **Step 3: Tulis evidence, bukan klaim**

`phase0-verification.md` menyimpan exact command, exit code, test count, Git SHA, dan known limitations. Jangan memasukkan secret atau DB user.

- [ ] **Step 4: Commit dan berhenti untuk review checkpoint**

```bash
git add tests/regression/test_phase0_invariants.py docs/research/phase0-verification.md
git commit -m "test: establish phase zero trust checkpoint"
```

**Checkpoint A:** Jangan lanjut ke Tranche B bila Phase 0 belum PASS atau migration belum diuji pada salinan DB.

---

## Tranche B — Phase 1: Contracts, Data Lake, and Quality

### Task 7: Buat package lab, runtime paths, dan dependency isolation

**Files:**

- Create: `requirements-research.txt`
- Create: `src/indodax_lab/__init__.py`
- Create: `src/indodax_lab/paths.py`
- Create: `src/indodax_lab/contracts/__init__.py`
- Create: `src/indodax_lab/contracts/common.py`
- Create: `src/indodax_lab/contracts/market.py`
- Modify: `.github/workflows/ci.yml`
- Create: `tests/unit/lab/test_paths.py`
- Create: `tests/unit/lab/test_contracts.py`

- [ ] **Step 1: Tulis path/contract tests**

Test memastikan env `INDODAX_LAB_DATA_DIR` dan `INDODAX_LAB_ARTIFACT_DIR` mengontrol output, default berada di project `lab-data/`/`lab-artifacts/`, timezone-naive datetime ditolak, dan pair `BTCIDR` dinormalisasi ke `btc_idr` hanya melalui adapter.

- [ ] **Step 2: Tambahkan research dependencies terpisah**

```text
# requirements-research.txt
-r requirements.txt
pyarrow>=17,<25
duckdb>=1.1,<2
pydantic>=2.8,<3
PyYAML>=6,<7
scikit-learn>=1.5,<2
xgboost>=2.1,<4
optuna>=4,<5
scipy>=1.13,<2
psutil>=6,<8
```

Lock file dibuat pada integration branch setelah compatibility test; jangan memasukkan PyTorch ke runtime ASUS.

- [ ] **Step 2a: Upgrade CI research job**

Setelah file ini ada, CI non-DL job meng-install `requirements-dev.txt` dan `requirements-research.txt` sebelum menjalankan all non-DL tests. Keep network calls mocked/offline.

- [ ] **Step 3: Implement paths tanpa bergantung current working directory**

```python
@dataclass(frozen=True)
class LabPaths:
    data_root: Path
    artifact_root: Path

    @classmethod
    def from_env(cls, project_root: Path) -> "LabPaths":
        return cls(
            Path(os.getenv("INDODAX_LAB_DATA_DIR", project_root / "lab-data")),
            Path(os.getenv("INDODAX_LAB_ARTIFACT_DIR", project_root / "lab-artifacts")),
        )
```

- [ ] **Step 4: Implement Pydantic/domain contracts**

`CanonicalPair`, `UtcTimestamp`, `QualityStatus`, `CandleRecord`, dan `TradeEvent` harus cocok dengan dataset contract. Decimal value tidak di-cast diam-diam ke float.

- [ ] **Step 5: Verifikasi dan commit**

Run: `python -m pytest tests/unit/lab/test_paths.py tests/unit/lab/test_contracts.py -q`
Expected: PASS.

```bash
git add requirements-research.txt src/indodax_lab tests/unit/lab .github/workflows/ci.yml
git commit -m "feat: add lab contracts and isolated research runtime"
```

### Task 8: Implement Parquet writer, partitioning, dan atomic manifest

**Files:**

- Create: `src/indodax_lab/data/__init__.py`
- Create: `src/indodax_lab/data/parquet_store.py`
- Create: `src/indodax_lab/data/manifest.py`
- Create: `src/indodax_lab/data/checksums.py`
- Create: `tests/unit/lab/data/test_parquet_store.py`
- Create: `tests/unit/lab/data/test_manifest.py`

- [ ] **Step 1: Tulis deterministic storage tests**

Test menulis dua partitions ke `tmp_path`, memastikan sort key canonical, ZSTD compression, UTC schema, checksum stabil, `.partial` hilang setelah success, dan manifest berubah bila satu byte source berubah.

- [ ] **Step 2: Implement explicit Arrow schema**

Jangan mengandalkan pandas dtype inference. `CANDLE_SCHEMA_V1` harus mendeklarasikan Decimal dan `timestamp("us", tz="UTC")` sesuai kontrak.

- [ ] **Step 3: Implement atomic write**

Write ke sibling `.partial`, `fsync`, validate row count/schema, rename, lalu masukkan SHA-256 dan size ke manifest. Failure meninggalkan status `FAILED_RETRYABLE`, bukan manifest success.

- [ ] **Step 4: Content-address snapshot**

Canonical JSON manifest memakai sorted keys/no volatile paths. `dataset_snapshot_id = sha256(canonical_manifest_without_id)`.

- [ ] **Step 5: Verifikasi dan commit**

Run: `python -m pytest tests/unit/lab/data/test_parquet_store.py tests/unit/lab/data/test_manifest.py -q`
Expected: PASS.

```bash
git add src/indodax_lab/data tests/unit/lab/data
git commit -m "feat: add immutable parquet snapshots and manifests"
```

### Task 9: Bangun candle adapter/backfill yang menyimpan wire payload

**Files:**

- Create: `src/indodax_lab/data/indodax_candles.py`
- Create: `src/indodax_lab/data/wire_store.py`
- Create: `src/indodax_lab/cli/backfill_candles.py`
- Create: `tests/fixtures/indodax/history_v2_pascal.json`
- Create: `tests/fixtures/indodax/history_v2_columns.json`
- Create: `tests/unit/lab/data/test_indodax_candles.py`
- Create: `tests/integration/lab/test_candle_backfill.py`

- [ ] **Step 1: Buat fixtures untuk kedua response shape yang sudah didukung baseline**

Fixture list-of-dicts memakai `Time/Open/High/Low/Close/Volume`; fixture columnar memakai `t/o/h/l/c/v`. Sertakan duplicate, out-of-order row, dan satu malformed row untuk error-policy tests.

- [ ] **Step 2: Tulis parser tests tanpa HTTP**

Parser harus menghasilkan canonical `btc_idr`, `venue_symbol=BTCIDR`, timestamps UTC, Decimal OHLCV, stable source event IDs, dan explicit reject list. Malformed row tidak boleh silently menjadi zero price.

- [ ] **Step 3: Implement wire-first adapter**

```python
class IndodaxCandleAdapter:
    def parse(self, payload: object, *, pair: str, interval: str, ingested_at: datetime) -> ParseBatch:
        if isinstance(payload, list):
            return parse_pascal_rows(payload, pair=pair, interval=interval, ingested_at=ingested_at)
        if isinstance(payload, dict):
            return parse_columnar(payload, pair=pair, interval=interval, ingested_at=ingested_at)
        raise InvalidCandlePayload(type(payload).__name__)
```

HTTP client menyimpan status/headers/body checksum ke wire store **sebelum** parse. Redact header credentials; public endpoint tidak memerlukan account key.

- [ ] **Step 4: Implement idempotent window backfill CLI**

```bash
PYTHONPATH=src python -m indodax_lab.cli.backfill_candles \
  --pair btc_idr --interval 1h \
  --from 2023-01-01T00:00:00Z --to 2023-02-01T00:00:00Z \
  --dry-run
```

`--dry-run` hanya menampilkan window/request count. Normal mode respects rate limit, resumes completed partitions, dan tidak menimpa checksum berbeda.

- [ ] **Step 5: Test end-to-end dengan fake transport**

Integration test inject fake HTTP transport, menghasilkan wire + bronze Parquet + manifest, dan memastikan rerun tidak menduplikasi row.

- [ ] **Step 6: Verifikasi dan commit**

Run: `python -m pytest tests/unit/lab/data/test_indodax_candles.py tests/integration/lab/test_candle_backfill.py -q`
Expected: PASS.

```bash
git add src/indodax_lab/data src/indodax_lab/cli tests/fixtures/indodax/history_v2_* tests/unit/lab/data tests/integration/lab
git commit -m "feat: add auditable Indodax candle backfill"
```

### Task 10: Tambahkan data sentry dan snapshot quality gate

**Files:**

- Create: `src/indodax_lab/data/quality.py`
- Create: `src/indodax_lab/data/sentry.py`
- Create: `src/indodax_lab/cli/validate_snapshot.py`
- Create: `tests/unit/lab/data/test_quality.py`
- Create: `tests/integration/lab/test_snapshot_validation.py`

- [ ] **Step 1: Tulis failing tests untuk invariants**

Cases wajib: duplicate key, timestamp mundur, gap interval, high di bawah close, low di atas open, negative volume, naive timestamp, stale final bar, dan checksum mismatch.

- [ ] **Step 2: Implement structured findings**

```python
@dataclass(frozen=True)
class QualityFinding:
    code: str
    severity: Literal["WARN", "FAIL"]
    pair: str
    start_ts: datetime
    end_ts: datetime
    row_count: int
    details: dict[str, str]
```

Tidak ada free-form exception sebagai satu-satunya output. `FAIL` membuat partition `QUARANTINED`; raw wire tetap dipertahankan.

- [ ] **Step 3: Implement deterministic quality report**

Report berisi expected/actual rows, gap ranges, duplicate count, invariant counts, min/max timestamp, coverage, source checksums, status, dan policy version.

- [ ] **Step 4: Implement CLI exit codes**

`0=PASS`, `2=WARN`, `3=FAIL`, `4=invalid invocation`. Worker hanya membangun silver snapshot dari PASS atau explicitly-approved WARN.

- [ ] **Step 5: Verifikasi**

Run: `python -m pytest tests/unit/lab/data/test_quality.py tests/integration/lab/test_snapshot_validation.py -q`
Expected: PASS.

```bash
git add src/indodax_lab/data src/indodax_lab/cli/validate_snapshot.py tests/unit/lab/data tests/integration/lab/test_snapshot_validation.py
git commit -m "feat: add fail-closed market data sentry"
```

### Task 11: Mulai forward public trade dan order-book collection

**Files:**

- Modify: `requirements-research.txt`
- Create: `src/indodax_lab/data/stream_protocol.py`
- Create: `src/indodax_lab/data/indodax_stream.py`
- Create: `src/indodax_lab/data/book_recovery.py`
- Create: `src/indodax_lab/cli/collect_market_stream.py`
- Create: `tests/fixtures/indodax/stream/public_trade.json`
- Create: `tests/fixtures/indodax/stream/book_snapshot.json`
- Create: `tests/fixtures/indodax/stream/book_update.json`
- Create: `tests/fixtures/indodax/stream/heartbeat.json`
- Create: `tests/fixtures/indodax/stream/duplicate_sequence.json`
- Create: `tests/fixtures/indodax/stream/gap_sequence.json`
- Create: `tests/unit/lab/data/test_stream_parser.py`
- Create: `tests/unit/lab/data/test_book_recovery.py`

- [ ] **Step 1: Pin WebSocket client only in research environment**

Tambahkan `websockets>=13,<17` ke `requirements-research.txt`. Collector tidak mengimpor scikit-learn/XGBoost/PyTorch.

- [ ] **Step 2: Capture fixtures dari documented message shapes**

Simpan fixture trade, snapshot, incremental update, heartbeat, duplicate sequence, gap sequence, dan reconnect. Jangan memasukkan account/private stream payload.

- [ ] **Step 3: Tulis state-machine tests**

State yang diharapkan: `DISCONNECTED → SYNCING → RELIABLE → GAP → RECOVERING → RELIABLE`. Feature eligibility hanya true pada `RELIABLE` session.

- [ ] **Step 4: Implement protocol adapter + append-only writer**

Parser menghasilkan `TradeEvent`/`BookEvent`; recovery meminta snapshot/offset sesuai official protocol. Bila recovery tidak didukung/berhasil, mulai `book_session_id` baru dan quarantine gap window.

- [ ] **Step 5: Implement graceful shutdown/reconnect**

Flush batch atomically, persist last acknowledged sequence, exponential backoff with jitter, heartbeat timeout, dan SIGTERM handling. Tidak ada unbounded in-memory queue.

- [ ] **Step 6: Verifikasi fixture replay**

Run: `python -m pytest tests/unit/lab/data/test_stream_parser.py tests/unit/lab/data/test_book_recovery.py -q`
Expected: PASS; no network.

```bash
git add requirements-research.txt src/indodax_lab/data src/indodax_lab/cli/collect_market_stream.py tests/fixtures/indodax/stream tests/unit/lab/data
git commit -m "feat: collect forward trades and reliable book sessions"
```

### Task 12: Implement point-in-time universe builder

**Files:**

- Create: `configs/universe/default_v1.yaml`
- Create: `src/indodax_lab/universe/__init__.py`
- Create: `src/indodax_lab/universe/contracts.py`
- Create: `src/indodax_lab/universe/eligibility.py`
- Create: `src/indodax_lab/universe/coingecko_adapter.py`
- Create: `src/indodax_lab/cli/build_universe.py`
- Create: `tests/unit/lab/universe/test_eligibility.py`
- Create: `tests/integration/lab/test_universe_snapshot.py`

- [ ] **Step 1: Encode policy dari design spec**

Config memuat listing age, zero-volume ratio, median spread, depth-to-order multiple, cap rank boundary, source TTL, dan fallback `LIQUIDITY_ONLY`. Nilai berbeda big/small-cap harus explicit.

- [ ] **Step 2: Tulis tests anti-survivorship**

Test membuktikan delisted pair tetap ada pada historical snapshot, newly listed pair belum eligible, missing historical cap menjadi `LIQUIDITY_ONLY`, dan current cap tidak boleh mengisi tanggal masa lalu.

- [ ] **Step 3: Implement pure eligibility**

```python
def classify_pair(metrics: UniverseMetrics, policy: UniversePolicy) -> UniverseDecision:
    """Pure point-in-time classification; no provider/network calls."""
```

Reason codes contoh: `LISTING_TOO_YOUNG`, `SPREAD_TOO_WIDE`, `DEPTH_TOO_LOW`, `CAP_HISTORY_MISSING`, `DATA_QUALITY_FAIL`.

- [ ] **Step 4: Provider adapter menyimpan raw + source timestamp**

CoinGecko adapter boleh memberi cap metadata, tetapi snapshot builder menolak payload yang `available_at` melewati `as_of_date` policy. Rate/quota errors tidak diubah menjadi angka nol.

- [ ] **Step 5: Verifikasi**

Run: `python -m pytest tests/unit/lab/universe tests/integration/lab/test_universe_snapshot.py -q`
Expected: PASS.

```bash
git add configs/universe src/indodax_lab/universe src/indodax_lab/cli/build_universe.py tests/unit/lab/universe tests/integration/lab/test_universe_snapshot.py
git commit -m "feat: add point-in-time dynamic universe"
```

### Task 13: Implement time bars lalu event-bar challengers

**Files:**

- Create: `configs/bars/time_v1.yaml`
- Create: `configs/bars/event_v1.yaml`
- Create: `src/indodax_lab/data/bars.py`
- Create: `src/indodax_lab/data/event_bars.py`
- Create: `src/indodax_lab/cli/build_bars.py`
- Create: `tests/unit/lab/data/test_time_bars.py`
- Create: `tests/unit/lab/data/test_event_bars.py`

- [ ] **Step 1: Tulis time-bar aggregation tests**

Trade fixture harus menghasilkan exact OHLC, base/quote volume, trade count, buy/sell volume, end-exclusive close time, dan `available_at` setelah final event/lag.

- [ ] **Step 2: Implement time bars sebagai baseline**

Build 1m dari trades bila complete; resample 5m/15m/1h/4h/1d dari smallest reliable source. Jika official candles dan trade-derived candles berbeda, report delta dan pilih source via config—jangan merge diam-diam.

- [ ] **Step 3: Tulis event-bar tests**

Test CUSUM event timestamps, range threshold, cumulative volume/dollar threshold, deterministic boundary, dan reset behavior.

- [ ] **Step 4: Implement event bars sebagai separate `bar_type`**

Thresholds hanya di-fit/ditentukan dari train period atau fixed config. Full-sample volatility tidak boleh menentukan CUSUM threshold historical.

- [ ] **Step 5: Verifikasi**

Run: `python -m pytest tests/unit/lab/data/test_time_bars.py tests/unit/lab/data/test_event_bars.py -q`
Expected: PASS.

```bash
git add configs/bars src/indodax_lab/data/bars.py src/indodax_lab/data/event_bars.py src/indodax_lab/cli/build_bars.py tests/unit/lab/data/test_*bars.py
git commit -m "feat: build time and information-driven bars"
```

### Task 14: Phase 1 data pipeline checkpoint

**Files:**

- Create: `tests/integration/lab/test_raw_to_silver_pipeline.py`
- Create: `tests/regression/test_phase1_snapshot.py`
- Create: `docs/research/phase1-data-verification.md`

- [ ] **Step 1: Build a tiny offline golden pipeline**

Fixture replay harus berjalan wire → bronze → sentry → time bars → universe → immutable snapshot. Assert exact row counts, known OHLC, quality status, universe decisions, dan snapshot ID.

- [ ] **Step 2: Resource smoke test**

Jalankan fixture 24 jam dengan batch size production-like dan catat peak RSS/runtime. Test tidak menetapkan threshold hardware yang palsu; threshold ASUS ditetapkan setelah measurement pertama dan disimpan dalam config.

- [ ] **Step 3: Full verification**

Run: `python -m pytest tests/unit/lab/data tests/unit/lab/universe tests/integration/lab tests/regression/test_phase1_snapshot.py -q`
Expected: PASS.

- [ ] **Step 4: Commit evidence dan stop**

```bash
git add tests/integration/lab/test_raw_to_silver_pipeline.py tests/regression/test_phase1_snapshot.py docs/research/phase1-data-verification.md
git commit -m "test: establish reproducible phase one snapshot"
```

**Checkpoint B:** Jangan memulai feature/model tournament pada snapshot yang belum PASS dan dapat direproduksi.

---

## Tranche C — Features, Labels, Judge, and Classical Wave 1

### Task 15: Implement versioned feature registry dan `tabular_bar_v1`

**Files:**

- Create: `configs/features/tabular_bar_v1.yaml`
- Create: `src/indodax_lab/features/__init__.py`
- Create: `src/indodax_lab/features/registry.py`
- Create: `src/indodax_lab/features/technical.py`
- Create: `src/indodax_lab/features/liquidity.py`
- Create: `src/indodax_lab/features/context.py`
- Create: `src/indodax_lab/features/builder.py`
- Create: `src/indodax_lab/cli/build_features.py`
- Create: `tests/fixtures/features/golden_ohlcv.csv`
- Create: `tests/unit/lab/features/test_registry.py`
- Create: `tests/unit/lab/features/test_technical.py`
- Create: `tests/unit/lab/features/test_availability.py`

- [ ] **Step 1: Copy exact Wave 1 feature definitions from dataset contract**

Registry harus memuat name, family, formula/implementation, params, lookback, availability, lag, dtype, missing policy, dan normalization. Loader menolak duplicate name, bfill, insufficient lookback, dan content change tanpa version bump.

- [ ] **Step 2: Tulis golden indicator tests**

Hitung expected values untuk EMA ratio/slope, RSI, StochRSI K/D, MACD/ATR, ADX/DI spread, BB z/width, ATR%, Donchian position, volume z-score, VWAP deviation pada fixture. Simpan tolerance explicit; jangan snapshot seluruh DataFrame tanpa explanation.

- [ ] **Step 3: Implement normalized features**

```python
def ema_ratio(close: pd.Series, fast: int, slow: int) -> pd.Series:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    return ema_fast.div(ema_slow).sub(1.0)
```

Gunakan stable internal names walaupun indicator library mengganti column names. Raw IDR MACD/ATR tidak masuk cross-asset model tanpa normalization.

- [ ] **Step 4: Implement as-of multi-timeframe/context join**

Builder hanya memilih rows dengan `available_at <= decision_ts`. Daily/4h partial bars dilarang. Point-in-time eligible universe dipakai untuk rank/breadth.

- [ ] **Step 5: Add warmup/missingness behavior**

Rows sebelum lookback memadai mendapat null + reason `INSUFFICIENT_LOOKBACK`; builder baru menandai row eligible ketika required core features tersedia. Tidak ada bfill.

- [ ] **Step 6: Verifikasi**

Run: `python -m pytest tests/unit/lab/features -q`
Expected: PASS.

```bash
git add configs/features src/indodax_lab/features src/indodax_lab/cli/build_features.py tests/fixtures/features tests/unit/lab/features
git commit -m "feat: build versioned technical and market features"
```

### Task 16: Implement labels, purged splits, dan training materializer

**Files:**

- Create: `configs/labels/net_return_v1.yaml`
- Create: `configs/labels/triple_barrier_v1.yaml`
- Create: `configs/splits/annual_v1.yaml`
- Create: `src/indodax_lab/labels/__init__.py`
- Create: `src/indodax_lab/labels/net_return.py`
- Create: `src/indodax_lab/labels/triple_barrier.py`
- Create: `src/indodax_lab/labels/splits.py`
- Create: `src/indodax_lab/labels/materialize.py`
- Create: `src/indodax_lab/cli/build_training_dataset.py`
- Create: `tests/unit/lab/labels/test_net_return.py`
- Create: `tests/unit/lab/labels/test_triple_barrier.py`
- Create: `tests/unit/lab/labels/test_purged_split.py`
- Create: `tests/integration/lab/test_training_materialization.py`

- [ ] **Step 1: Tulis next-open net-return tests**

Signal close tidak boleh menjadi fill. Test exact buy/sell fees, spread/slippage, edge margin, `label_available_at`, dan net return yang lebih kecil dari gross.

- [ ] **Step 2: Tulis Triple Barrier tests**

Cases: upper first, lower first, vertical expiry, same-bar both=lower first, volatility available at decision, and label end timestamp.

- [ ] **Step 3: Implement label builders dari execution interface**

Label tidak menghitung biaya sendiri secara ad hoc; ia memanggil versioned execution/cost interface. Setiap row menyimpan `cost_schedule_id` dan `execution_model_version`.

- [ ] **Step 4: Implement purged expanding walk-forward**

Purge sample bila `label_end_ts` melewati fold boundary. Embargo minimal max horizon. Store assignment table `sample_id, fold_id, role` agar training tidak membentuk split sendiri.

- [ ] **Step 5: Materialize dengan strict separation**

Feature table dan label table tetap terpisah. Training join menolak label column pada inference feature list, availability violation, duplicate sample, missing universe/cost snapshot, atau checksum mismatch.

- [ ] **Step 6: Verifikasi**

Run: `python -m pytest tests/unit/lab/labels tests/integration/lab/test_training_materialization.py -q`
Expected: PASS.

```bash
git add configs/labels configs/splits src/indodax_lab/labels src/indodax_lab/cli/build_training_dataset.py tests/unit/lab/labels tests/integration/lab/test_training_materialization.py
git commit -m "feat: add cost-aware labels and purged time splits"
```

### Task 17: Implement cost schedules dan double-entry research ledger

**Files:**

- Create: `configs/costs/indodax_idr_v1.yaml`
- Create: `src/indodax_lab/backtest/__init__.py`
- Create: `src/indodax_lab/backtest/costs.py`
- Create: `src/indodax_lab/backtest/ledger.py`
- Create: `src/indodax_lab/backtest/orders.py`
- Create: `tests/unit/lab/backtest/test_cost_schedule.py`
- Create: `tests/unit/lab/backtest/test_ledger.py`
- Create: `tests/property/lab/test_ledger_invariants.py`

- [ ] **Step 1: Encode time-valid cost schedule**

YAML memisahkan service fee, tax, exchange/CFX component, side, maker/taker, minimum order, `valid_from`, `valid_to`, dan source URL. Angka schedule aktif harus diverifikasi saat task dieksekusi; historical unknown menjadi `BLOCKED_POLICY`, bukan diisi dengan schedule hari ini.

- [ ] **Step 2: Tulis lookup/overlap tests**

Schedule overlap pada key sama harus gagal. Event sebelum/di/akhir validity range memilih schedule tepat atau `UnknownCostSchedule`.

- [ ] **Step 3: Implement double-entry postings**

Accounts minimum: `CASH_IDR`, `ASSET:<symbol>`, `FEE_EXPENSE`, `REALIZED_PNL`. Setiap transaction debit=credit dalam integer minor units/Decimal quantization. Order/fill menyimpan gross notional, quantity, fee, role, timestamp, dan source event.

- [ ] **Step 4: Property tests**

Hypothesis generates buy/partial sell/final sell paths. Invariants: cash + marked positions − fees = equity, quantity never negative, postings balance, higher fee cannot improve fixed-path PnL.

- [ ] **Step 5: Verifikasi**

Run: `python -m pytest tests/unit/lab/backtest/test_cost_schedule.py tests/unit/lab/backtest/test_ledger.py tests/property/lab/test_ledger_invariants.py -q`
Expected: PASS.

```bash
git add configs/costs src/indodax_lab/backtest tests/unit/lab/backtest tests/property/lab
git commit -m "feat: add time-valid costs and balanced research ledger"
```

### Task 18: Implement deterministic event-driven backtester

**Files:**

- Create: `src/indodax_lab/backtest/events.py`
- Create: `src/indodax_lab/backtest/execution.py`
- Create: `src/indodax_lab/backtest/risk.py`
- Create: `src/indodax_lab/backtest/engine.py`
- Create: `src/indodax_lab/backtest/metrics.py`
- Create: `src/indodax_lab/backtest/result.py`
- Create: `src/indodax_lab/cli/run_backtest.py`
- Create: `tests/fixtures/backtest/tiny_market_path.json`
- Create: `tests/unit/lab/backtest/test_execution.py`
- Create: `tests/unit/lab/backtest/test_risk.py`
- Create: `tests/integration/lab/test_backtest_golden.py`

- [ ] **Step 1: Define strategy/judge event contracts**

```python
@dataclass(frozen=True)
class SignalIntent:
    decision_ts: datetime
    pair: str
    side: Literal["LONG", "FLAT"]
    strength: float
    stop_loss: Decimal | None
    take_profit: Decimal | None
    strategy_id: str
    strategy_version: str
```

Strategy tidak boleh memutasi ledger atau menentukan fill.

- [ ] **Step 2: Tulis fill-model tests**

Cases: next-open fill, spread/slippage, min order reject, insufficient depth, partial fill, precision rounding, same-bar stop/target, stale data fail-closed, and cost stress 1.5×/2×.

- [ ] **Step 3: Implement event loop dengan injected clock/data**

Urutan stable: market event → pending fills → stops/targets → strategy decision → risk gate → new orders → mark/equity. Stable pair/order ordering harus menghasilkan run identik.

- [ ] **Step 4: Implement independent dan shared ledgers**

Independent run mulai Rp500.000 per strategy. Shared run hanya satu Rp500.000 total, maksimal dua concurrent positions, min order, cash conflict, dan portfolio kill switches.

- [ ] **Step 5: Implement result/metrics contract**

Simpan trades, rejected orders, equity curve, net/gross returns, fees/slippage, drawdown, exposure, turnover, expectancy, PF, win rate, holding time, per-year/regime/tier/asset, dan reproducibility manifest.

- [ ] **Step 6: Golden replay**

Fixture kecil memiliki expected exact fills/postings/equity. Run dua kali dengan snapshot/config/seed/Git SHA sama harus value-identical.

- [ ] **Step 7: Verifikasi**

Run: `python -m pytest tests/unit/lab/backtest tests/integration/lab/test_backtest_golden.py -q`
Expected: PASS.

```bash
git add src/indodax_lab/backtest src/indodax_lab/cli/run_backtest.py tests/fixtures/backtest tests/unit/lab/backtest tests/integration/lab/test_backtest_golden.py
git commit -m "feat: add deterministic cost-aware backtest judge"
```

### Task 19: Implement strategy protocol, registry, C01, dan C07

**Files:**

- Create: `research/catalog/wave1.yaml`
- Create: `configs/strategies/C01_donchian_v1.yaml`
- Create: `configs/strategies/C07_bollinger_reversion_v1.yaml`
- Create: `src/indodax_lab/strategies/__init__.py`
- Create: `src/indodax_lab/strategies/base.py`
- Create: `src/indodax_lab/strategies/registry.py`
- Create: `src/indodax_lab/strategies/c01_donchian.py`
- Create: `src/indodax_lab/strategies/c07_bollinger_reversion.py`
- Create: `tests/unit/lab/strategies/test_registry.py`
- Create: `tests/unit/lab/strategies/test_c01_donchian.py`
- Create: `tests/unit/lab/strategies/test_c07_bollinger.py`

- [ ] **Step 1: Implement declarative registry validation**

Required: ID/version/family/universe/timeframes/signal timing/execution timing/parameters/risk profile/split/status. Unknown config fields fail; logic/parameter change requires version bump.

- [ ] **Step 2: Define stateless protocol**

```python
@dataclass(frozen=True)
class RegisteredStrategy:
    specification: StrategySpecification
    decide: Callable[[DecisionFrame], list[SignalIntent]]
```

`DecisionFrame` hanya berisi rows dengan availability valid dan eligible universe.

- [ ] **Step 3: TDD C01**

Breakout N-bar, volume/liquidity gate, ATR stop, no future high, long-only. Test signal tepat pada next decision setelah breakout dan no signal on incomplete bar.

- [ ] **Step 4: TDD C07**

Bollinger/RSI reversion hanya pada sideways/regime gate, spread/liquidity eligible, ATR stop/target. Test tidak membeli falling knife di strong downtrend.

- [ ] **Step 5: Run golden judge comparisons**

Run both on same fixture/snapshot and assert independent ledgers and deterministic manifests.

- [ ] **Step 6: Verifikasi dan commit**

Run: `python -m pytest tests/unit/lab/strategies -q`
Expected: PASS.

```bash
git add research/catalog configs/strategies src/indodax_lab/strategies tests/unit/lab/strategies
git commit -m "feat: add strategy registry and first wave baselines"
```

### Task 20: Implement sisa classical Wave 1

**Files:**

- Create: `configs/strategies/C02_ema_pullback_v1.yaml`
- Create: `configs/strategies/C03_tsmom_v1.yaml`
- Create: `configs/strategies/C04_xsmom_v1.yaml`
- Create: `configs/strategies/C10_regime_ensemble_v1.yaml`
- Create: `configs/strategies/S01_liquid_breakout_v1.yaml`
- Create: `configs/strategies/S02_squeeze_v1.yaml`
- Create: `src/indodax_lab/strategies/c02_ema_pullback.py`
- Create: `src/indodax_lab/strategies/c03_tsmom.py`
- Create: `src/indodax_lab/strategies/c04_xsmom.py`
- Create: `src/indodax_lab/strategies/c10_regime_ensemble.py`
- Create: `src/indodax_lab/strategies/s01_liquid_breakout.py`
- Create: `src/indodax_lab/strategies/s02_squeeze.py`
- Create: `tests/unit/lab/strategies/test_c02_ema_pullback.py`
- Create: `tests/unit/lab/strategies/test_c03_tsmom.py`
- Create: `tests/unit/lab/strategies/test_c04_xsmom.py`
- Create: `tests/unit/lab/strategies/test_c10_regime_ensemble.py`
- Create: `tests/unit/lab/strategies/test_s01_liquid_breakout.py`
- Create: `tests/unit/lab/strategies/test_s02_squeeze.py`
- Create: `tests/regression/test_wave1_classical.py`

- [ ] **Step 1: Implement satu strategy per red/green cycle**

Urutan: C02 EMA pullback, C03 time-series momentum, C04 point-in-time cross-sectional momentum, C10 regime ensemble, S01 liquidity-screened breakout, S02 squeeze expansion. Jangan commit enam untested strategies sekaligus; gunakan one-strategy subcommits bila branch policy mengizinkan.

- [ ] **Step 2: Enforce small-cap guards**

S01/S02 wajib memeriksa spread, depth-to-order, zero-volume ratio, listing age, no-chase cap, dan stress-cost result. Pair dengan missing depth tidak dianggap liquid.

- [ ] **Step 3: Cross-sectional universe test**

C04 ranks only eligible pairs at each timestamp. Delisted pair remains in historical decisions; current universe must not rewrite history.

- [ ] **Step 4: Regime ensemble test**

C10 hanya memilih child strategy dari regime feature yang available at decision time; tidak memilih berdasarkan future winner.

- [ ] **Step 5: Wave 1 regression**

Setiap strategy menghasilkan stable decision hash/trade count/equity on golden snapshot. Regression update memerlukan documented judge/strategy version change.

- [ ] **Step 6: Verifikasi dan commit**

Run: `python -m pytest tests/unit/lab/strategies tests/regression/test_wave1_classical.py -q`
Expected: PASS.

```bash
git add configs/strategies src/indodax_lab/strategies tests/unit/lab/strategies tests/regression/test_wave1_classical.py
git commit -m "feat: complete classical wave one candidates"
```

### Task 21: Implement experiment registry, evaluation gates, dan lifecycle

**Files:**

- Create: `configs/evaluation/promotion_v1.yaml`
- Create: `src/indodax_lab/evaluation/__init__.py`
- Create: `src/indodax_lab/evaluation/registry.py`
- Create: `src/indodax_lab/evaluation/metrics.py`
- Create: `src/indodax_lab/evaluation/gates.py`
- Create: `src/indodax_lab/evaluation/multiple_testing.py`
- Create: `src/indodax_lab/evaluation/lifecycle.py`
- Create: `src/indodax_lab/cli/evaluate_runs.py`
- Create: `tests/unit/lab/evaluation/test_gates.py`
- Create: `tests/unit/lab/evaluation/test_lifecycle.py`
- Create: `tests/unit/lab/evaluation/test_multiple_testing.py`

- [ ] **Step 1: Create DuckDB registry schema**

Tables: `experiments`, `runs`, `artifacts`, `metrics`, `gate_results`, `trial_budget`, `lineage`, `promotion_events`. Store failed trials too. Unique run key includes config/dataset/split/cost/execution/seed/Git hashes.

- [ ] **Step 2: TDD hard gates**

Lookahead/data FAIL/unknown fee/ledger imbalance/drawdown breach must override robust score. Metrics include net expectancy, PF, cost stress, parameter stability, concentration, regimes, capacity, and minimum evidence.

- [ ] **Step 3: Implement result taxonomy**

```text
INVALID_RUN -> repair/retry same config
HARD_FAIL   -> REJECTED, no tuner queue
NEAR_MISS   -> hypothesis review if budget remains
REGIME_EDGE -> versioned regime challenger
PASS        -> frozen next gate
```

Max two revision rounds per family/snapshot. `HARD_FAIL` cannot become `NEAR_MISS` by changing seed alone.

- [ ] **Step 4: Implement DSR/PBO only when statistically meaningful**

Function returns `NOT_ENOUGH_TRIALS/BLOCKS` rather than fake number. Unit tests use published/simple synthetic examples and tolerance.

- [ ] **Step 5: Verifikasi**

Run: `python -m pytest tests/unit/lab/evaluation -q`
Expected: PASS.

```bash
git add configs/evaluation src/indodax_lab/evaluation src/indodax_lab/cli/evaluate_runs.py tests/unit/lab/evaluation
git commit -m "feat: add auditable experiment lifecycle and gates"
```

**Checkpoint C:** Judge + eight classical candidates must run reproducibly before M01/M02 are allowed to claim improvement.

---

## Tranche D — Phase 2: ML Baselines, Tournament, and Background Workers

### Task 22: Implement leak-free preprocessing dan cost-aware execution mapper

**Files:**

- Create: `src/indodax_lab/models/__init__.py`
- Create: `src/indodax_lab/models/contracts.py`
- Create: `src/indodax_lab/models/preprocessing.py`
- Create: `src/indodax_lab/models/calibration.py`
- Create: `src/indodax_lab/models/execution_mapper.py`
- Create: `tests/unit/lab/models/test_preprocessing.py`
- Create: `tests/unit/lab/models/test_calibration.py`
- Create: `tests/unit/lab/models/test_execution_mapper.py`

- [ ] **Step 1: Tulis fold-isolation tests**

Masukkan extreme values hanya di validation/test dan buktikan train median/scaler/winsor thresholds tidak berubah. Feature order mismatch dan extra/missing feature harus fail closed.

- [ ] **Step 2: Implement sklearn-compatible train-only pipeline**

Pipeline: missing indicator + median imputer (train) → optional robust scaler → optional train-only correlation pruning. Serialize fitted feature order/statistics; tree model tetap memakai same contract walau scaling dimatikan.

- [ ] **Step 3: Tulis calibration tests**

Calibrator di-fit pada dedicated inner validation, bukan training labels yang sama dan bukan sealed test. Report Brier/log loss/reliability bins; too-small calibration set returns explicit blocked status.

- [ ] **Step 4: Implement abstain/no-trade mapper**

```python
def should_trade(
    expected_net_return: float,
    estimated_round_trip_cost: float,
    safety_margin: float,
) -> bool:
    return expected_net_return > estimated_round_trip_cost + safety_margin
```

For probability model, map calibrated probability + expected payoff to expected edge. Threshold/safety margin dituning hanya pada inner validation dan versioned.

- [ ] **Step 5: Verifikasi**

Run: `python -m pytest tests/unit/lab/models/test_preprocessing.py tests/unit/lab/models/test_calibration.py tests/unit/lab/models/test_execution_mapper.py -q`
Expected: PASS.

```bash
git add src/indodax_lab/models tests/unit/lab/models
git commit -m "feat: add leak-free model preprocessing and abstention"
```

### Task 23: Train M01 logistic/elastic-net dan M02 XGBoost

**Files:**

- Create: `configs/models/M01_logistic_v1.yaml`
- Create: `configs/models/M02_xgboost_v1.yaml`
- Create: `src/indodax_lab/models/m01_logistic.py`
- Create: `src/indodax_lab/models/m02_xgboost.py`
- Create: `src/indodax_lab/models/tuning.py`
- Create: `src/indodax_lab/models/artifacts.py`
- Create: `src/indodax_lab/models/trainer.py`
- Create: `src/indodax_lab/cli/train_model.py`
- Create: `tests/unit/lab/models/test_m01_logistic.py`
- Create: `tests/unit/lab/models/test_m02_xgboost.py`
- Create: `tests/unit/lab/models/test_tuning_budget.py`
- Create: `tests/integration/lab/test_ml_walk_forward.py`

- [ ] **Step 1: Encode bounded search spaces**

M01 searches regularization/penalty/class weight within valid solver combinations. M02 searches depth, learning rate, estimators with early stopping, subsample, column sample, min child weight, and regularization. Search space/version is config, not notebook code.

- [ ] **Step 2: TDD trial budget**

Max 30 trials per model/horizon/snapshot, one revision round only after `NEAR_MISS`, failed trials recorded, and sealed fold never appears in Optuna objective. Resume uses study ID + config hash.

- [ ] **Step 3: Implement fold training**

For each inner fold: fit preprocessor/model, predict validation, calibrate only through nested/held calibration segment, apply cost-aware mapper, and calculate trading utility. Aggregate score penalizes instability and poor calibration.

- [ ] **Step 4: Refit frozen finalist**

After selection, refit on allowed expanding train data with exact frozen config. Run finalist across 3 seeds only where model has stochasticity; report median/worst, do not select best seed.

- [ ] **Step 5: Persist complete artifact bundle**

Weights/model, manifest, feature order, preprocessor, calibrator, execution threshold, training metrics, environment lock hash. Manifest includes dataset/feature/label/split/Git/config/cost/execution IDs and best iteration—not just model pickle.

- [ ] **Step 6: Compare against required baselines**

Integration test/report includes cash, buy-and-hold, naive momentum/reversion, best classical, M01, and M02 on identical outer folds/costs. Accuracy-only leaderboard is prohibited.

- [ ] **Step 7: Verifikasi**

Run: `python -m pytest tests/unit/lab/models tests/integration/lab/test_ml_walk_forward.py -q`
Expected: PASS on tiny fixture within CI budget.

```bash
git add configs/models src/indodax_lab/models src/indodax_lab/cli/train_model.py tests/unit/lab/models tests/integration/lab/test_ml_walk_forward.py
git commit -m "feat: add bounded walk-forward ML baselines"
```

### Task 24: Implement durable job queue dan resource/idle guard

**Files:**

- Create: `configs/schedules/default_v1.yaml`
- Create: `src/indodax_lab/orchestration/__init__.py`
- Create: `src/indodax_lab/orchestration/jobs.py`
- Create: `src/indodax_lab/orchestration/queue.py`
- Create: `src/indodax_lab/orchestration/locks.py`
- Create: `src/indodax_lab/orchestration/resources.py`
- Create: `src/indodax_lab/orchestration/worker.py`
- Create: `src/indodax_lab/cli/run_worker.py`
- Create: `tests/unit/lab/orchestration/test_queue.py`
- Create: `tests/unit/lab/orchestration/test_resources.py`
- Create: `tests/integration/lab/test_worker_resume.py`

- [ ] **Step 1: Define job state machine**

`PENDING`, `RUNNING`, `SUCCESS`, `FAILED_RETRYABLE`, `FAILED_FINAL`, `BLOCKED_DATA`, `BLOCKED_POLICY`, `CANCELLED`, `STALE`. Each job has idempotency key, resource class, attempt count, heartbeat, checkpoint, input/output IDs, and parent job.

- [ ] **Step 2: TDD durable claim/heartbeat/recovery**

SQLite WAL transaction claims one job; two workers cannot claim same row. Missing heartbeat makes job STALE then requeue only when retry policy allows. Partial artifact never marks success.

- [ ] **Step 3: Implement resource guard with injectable probes**

LOW/MEDIUM/HIGH/GPU checks include CPU load, available RAM, AC power, user idle time, disk, temperature when sensor exists, and GPU availability. Default DL: AC connected, idle ≥10 minutes, free RAM ≥4 GB, configured safe thermal threshold. Missing thermal sensor is explicit `UNKNOWN`, governed by policy—not assumed safe.

- [ ] **Step 4: Enforce host concurrency**

ASUS: collector + sentry + paper only. Lenovo: one HIGH/GPU or two MEDIUM. File/DB locks enforce one writer per partition/registry transaction; different run IDs may parallelize.

- [ ] **Step 5: Implement checkpoints and SIGTERM**

Worker stops cleanly, writes atomic checkpoint, releases claim, and resumes from stable fold/trial boundary. A killed epoch may restart from last model checkpoint but cannot duplicate registry metrics.

- [ ] **Step 6: Verifikasi**

Run: `python -m pytest tests/unit/lab/orchestration tests/integration/lab/test_worker_resume.py -q`
Expected: PASS.

```bash
git add configs/schedules src/indodax_lab/orchestration src/indodax_lab/cli/run_worker.py tests/unit/lab/orchestration tests/integration/lab/test_worker_resume.py
git commit -m "feat: add durable idle-aware research workers"
```

### Task 25: Wire background DAG dan evaluator-controlled repeat policy

**Files:**

- Create: `src/indodax_lab/orchestration/dag.py`
- Create: `src/indodax_lab/orchestration/policies.py`
- Create: `src/indodax_lab/cli/schedule_research.py`
- Create: `tests/unit/lab/orchestration/test_dag.py`
- Create: `tests/unit/lab/orchestration/test_repeat_policy.py`

- [ ] **Step 1: Encode DAG**

```text
wire_ingest -> bronze_validate -> silver_snapshot -> feature/label build
-> classical/ML runs -> evaluate -> shadow queue/report
```

Missing/failed parent blocks children; retrying job reuses immutable inputs.

- [ ] **Step 2: TDD bad-result behavior**

- `INVALID_RUN`: same config may requeue after dependency fix.
- `HARD_FAIL`: archive; no train/tune job emitted.
- `NEAR_MISS`: emit hypothesis review, then at most bounded new version if approved/policy eligible.
- `PASS`: freeze and enqueue next gate.

Assert machine idle alone never reopens `HARD_FAIL`.

- [ ] **Step 3: Implement periodic triggers without overlapping work**

Data sentry continuous/daily; universe daily; classical nightly/idle; ML weekly/new snapshot; evaluator after batch. Idempotency key includes cadence window + input snapshot.

- [ ] **Step 4: Verifikasi**

Run: `python -m pytest tests/unit/lab/orchestration/test_dag.py tests/unit/lab/orchestration/test_repeat_policy.py -q`
Expected: PASS.

```bash
git add src/indodax_lab/orchestration src/indodax_lab/cli/schedule_research.py tests/unit/lab/orchestration
git commit -m "feat: automate bounded research evaluate repeat cycle"
```

### Task 26: Implement champion/challenger forward paper shadow

**Files:**

- Create: `configs/paper/shadow_v1.yaml`
- Create: `src/indodax_lab/paper/__init__.py`
- Create: `src/indodax_lab/paper/contracts.py`
- Create: `src/indodax_lab/paper/runner.py`
- Create: `src/indodax_lab/paper/portfolio.py`
- Create: `src/indodax_lab/paper/reconciliation.py`
- Create: `src/indodax_lab/cli/run_shadow.py`
- Create: `tests/unit/lab/paper/test_portfolio.py`
- Create: `tests/integration/lab/test_shadow_replay.py`
- Create: `tests/integration/lab/test_shadow_restart.py`

- [ ] **Step 1: Define immutable prediction/decision records**

Store model/strategy version, feature row/sample IDs, decision timestamp, raw forecast, calibration, estimated cost, abstain threshold, risk decision, and planned order. Manual user action is separate metadata.

- [ ] **Step 2: Implement independent and shared Rp500k shadow ledgers**

Independent measures candidate edge. Shared ledger resolves cash/signal conflicts, max two positions, correlation/exposure, min order, and kill switches. Never sum independent ledger profits as one portfolio.

- [ ] **Step 3: Replay/restart tests**

One-day fixture produces same postings/outcomes after restart; processed event IDs prevent duplicate entry/exit. Data stale/unknown fee/universe/model mismatch fails closed.

- [ ] **Step 4: Champion replacement gate**

Challenger requires sealed historical pass plus at least 90 days and 100 pooled closed forward trades, whichever longer, with no policy breach. Champion is not overwritten during challenger training.

- [ ] **Step 5: Verifikasi**

Run: `python -m pytest tests/unit/lab/paper tests/integration/lab/test_shadow_replay.py tests/integration/lab/test_shadow_restart.py -q`
Expected: PASS.

```bash
git add configs/paper src/indodax_lab/paper src/indodax_lab/cli/run_shadow.py tests/unit/lab/paper tests/integration/lab/test_shadow_*.py
git commit -m "feat: add reconciled champion challenger shadow trading"
```

### Task 27: Phase 2 tournament checkpoint

**Files:**

- Create: `tests/regression/test_wave1_tournament.py`
- Create: `docs/research/phase2-tournament-verification.md`
- Create: `research/reports/.gitkeep`

- [ ] **Step 1: Run tiny/full-profile separation**

CI runs tiny deterministic tournament. Lenovo run uses immutable real snapshot and writes compact metrics/report only; raw data/model weights stay outside Git.

- [ ] **Step 2: Assert lifecycle outcomes**

Fixture batch must include one `INVALID_RUN`, one `HARD_FAIL`, one `NEAR_MISS`, and one `PASS`; verify emitted follow-up jobs exactly match policy.

- [ ] **Step 3: Full verification**

Run: `python -m pytest tests/unit/lab tests/integration/lab tests/regression/test_wave1_tournament.py -q`
Expected: PASS.

- [ ] **Step 4: Commit evidence and stop**

```bash
git add tests/regression/test_wave1_tournament.py docs/research/phase2-tournament-verification.md research/reports/.gitkeep
git commit -m "test: establish classical and ML tournament checkpoint"
```

**Checkpoint D:** DL tasks tetap BLOCKED sampai M01/M02 + classical baselines stabil, feature/label leakage tests PASS, dan resource probe Lenovo terdokumentasi.

---

## Tranche E — Phase 3: Selective Deep Learning and Experimental Models

### Task 28: Buat optional DL environment, sequence dataset, dan D01 MLP baseline

**Files:**

- Create: `requirements-dl.txt`
- Create: `configs/models/D01_mlp_v1.yaml`
- Create: `src/indodax_lab/models/dl/__init__.py`
- Create: `src/indodax_lab/models/dl/dataset.py`
- Create: `src/indodax_lab/models/dl/training.py`
- Create: `src/indodax_lab/models/dl/checkpoint.py`
- Create: `src/indodax_lab/models/dl/d01_mlp.py`
- Create: `tests/unit/lab/models/dl/test_sequence_dataset.py`
- Create: `tests/unit/lab/models/dl/test_early_stopping.py`
- Create: `tests/integration/lab/test_d01_training_smoke.py`
- Modify: `pyproject.toml`
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Isolate PyTorch**

```text
# requirements-dl.txt
-r requirements-research.txt
torch>=2.4,<3
```

Resolve platform/CUDA wheel and lock on Lenovo only after hardware detection. ASUS must never install/import this file.

- [ ] **Step 1a: Register and isolate DL tests**

Register marker `dl`. Core CI runs `pytest -m "not dl"`; separate CPU DL smoke job installs `requirements-dl.txt` and runs `pytest -m dl`. Mark every test that imports PyTorch. This keeps ASUS/core environments free of PyTorch without silently dropping DL verification.

- [ ] **Step 2: TDD sequence materialization**

Build chronological windows with `sample_id`, feature order, masks, no cross-pair/session leakage, no window across data gap, and target outside input. Padding mask prevents zeros becoming market observation.

- [ ] **Step 3: Implement shared training recipe**

```python
@dataclass(frozen=True)
class TrainingRecipe:
    max_epochs: int = 50
    patience: int = 7
    min_delta: float = 1e-4
    batch_size: int = 256
    gradient_clip_norm: float = 1.0
    seed: int = 42
```

Epoch 50 adalah cap. Save best validation checkpoint, optimizer/scheduler state, epoch, config/data hashes, and RNG states. Resume refuses hash mismatch.

- [ ] **Step 4: Implement D01 before sequence architecture**

D01 consumes the same tabular features as M01/M02. This isolates benefit of nonlinear NN from benefit of sequence representation. Tune at most 12 configs; early stop; finalist evaluated across 3 fixed seeds and summarized median/worst.

- [ ] **Step 5: Verify CPU smoke**

Run: `python -m pytest tests/unit/lab/models/dl tests/integration/lab/test_d01_training_smoke.py -q`
Expected: PASS on tiny CPU fixture; no GPU required.

```bash
git add requirements-dl.txt configs/models/D01_mlp_v1.yaml src/indodax_lab/models/dl tests/unit/lab/models/dl tests/integration/lab/test_d01_training_smoke.py pyproject.toml .github/workflows/ci.yml
git commit -m "feat: add checkpointed DL training and MLP baseline"
```

### Task 29: Implement D02 TCN, D03 ResNet-LSTM, dan D04 compact iTransformer

**Files:**

- Create: `configs/models/D02_tcn_v1.yaml`
- Create: `configs/models/D03_resnet_lstm_v1.yaml`
- Create: `configs/models/D04_itransformer_v1.yaml`
- Create: `src/indodax_lab/models/dl/d02_tcn.py`
- Create: `src/indodax_lab/models/dl/d03_resnet_lstm.py`
- Create: `src/indodax_lab/models/dl/d04_itransformer.py`
- Create: `tests/unit/lab/models/dl/test_d02_shapes.py`
- Create: `tests/unit/lab/models/dl/test_d03_shapes.py`
- Create: `tests/unit/lab/models/dl/test_d04_shapes.py`
- Create: `tests/integration/lab/test_sequence_models_smoke.py`

- [ ] **Step 1: Shape/mask tests first**

Assert batch/sequence/feature dimensions, padding mask behavior, finite logits/loss, deterministic eval, and no prediction from target/future tokens.

- [ ] **Step 2: Implement compact TCN sequence baseline**

Causal/dilated 1D convolutions dengan residual blocks, mask-safe pooling, dan parameter budget tercatat. D02 menguji nilai sequence representation sebelum recurrent/attention complexity.

- [ ] **Step 3: Implement compact ResNet-LSTM**

Residual 1D temporal blocks → LSTM/GRU head → classification/regression head. Keep parameter budget configured and reported. D03 first uses Triple Barrier/event-bar task because that is its registered hypothesis.

- [ ] **Step 4: Implement compact iTransformer challenger**

Variates are tokens, time axis embedded per config, with causal/availability-safe input construction. Do not copy a large generic Transformer merely because GPU exists.

- [ ] **Step 5: Use same evaluator/cost mapper**

Both output forecasts, not trades. Calibration, abstention, cost model, folds, baselines, and artifacts are identical to M01/M02. Compare compute time/energy/operational complexity as metrics.

- [ ] **Step 6: Enforce budget**

At most 12 configs × 50 max epochs, patience 7, top frozen config across 3 seeds. A negative/unstable valid result is `HARD_FAIL`, not automatic extra epochs.

- [ ] **Step 7: Verifikasi**

Run: `python -m pytest tests/unit/lab/models/dl tests/integration/lab/test_sequence_models_smoke.py -q`
Expected: PASS.

```bash
git add configs/models/D02_tcn_v1.yaml configs/models/D03_resnet_lstm_v1.yaml configs/models/D04_itransformer_v1.yaml src/indodax_lab/models/dl tests/unit/lab/models/dl tests/integration/lab/test_sequence_models_smoke.py
git commit -m "feat: add bounded TCN ResNet LSTM and iTransformer challengers"
```

### Task 30: Add gated G01 cross-asset graph dan F01 Kronos adapters

**Files:**

- Create: `configs/models/G01_cross_asset_gat_v1.yaml`
- Create: `configs/models/F01_kronos_v1.yaml`
- Create: `src/indodax_lab/models/graph/__init__.py`
- Create: `src/indodax_lab/models/graph/g01_cross_asset.py`
- Create: `src/indodax_lab/models/foundation/__init__.py`
- Create: `src/indodax_lab/models/foundation/provenance.py`
- Create: `src/indodax_lab/models/foundation/f01_kronos.py`
- Create: `tests/unit/lab/models/test_graph_availability.py`
- Create: `tests/unit/lab/models/test_foundation_provenance.py`

- [ ] **Step 1: Gate G01 on panel quality**

Graph nodes are eligible pairs at each decision time. Edges use rolling/train-only correlation or configured economic relation available then. Full-sample adjacency/future universe test must fail.

- [ ] **Step 2: Require simple cross-asset baselines**

Compare G01 with rank momentum, regularized panel regression, M02, and a no-edge MLP using identical samples. Max 8 configs, patience 7, 3-seed finalist.

- [ ] **Step 3: Implement external artifact provenance gate**

```python
@dataclass(frozen=True)
class FoundationArtifactProvenance:
    model_name: str
    revision: str
    sha256: str
    license_id: str
    released_at: datetime
    declared_pretraining_cutoff: datetime | None
    declared_sources: tuple[str, ...]
```

Missing revision/checksum/license blocks loading. Unknown cutoff sets `EXPLORATORY` and blocks promotion.

- [ ] **Step 4: Stage F01 adaptation**

Run in order: zero-shot → frozen representation/linear probe → parameter-efficient adapter fine-tune. Full fine-tune is not default and requires separate resource/design approval. Evaluation emphasizes data after declared cutoff/release.

- [ ] **Step 5: Tests remain offline**

Use fake lightweight foundation adapter; CI never downloads weights. Actual weight acquisition is an explicit Lenovo setup step with checksum/license evidence.

- [ ] **Step 6: Verifikasi**

Run: `python -m pytest tests/unit/lab/models/test_graph_availability.py tests/unit/lab/models/test_foundation_provenance.py -q`
Expected: PASS.

```bash
git add configs/models/G01_cross_asset_gat_v1.yaml configs/models/F01_kronos_v1.yaml src/indodax_lab/models/graph src/indodax_lab/models/foundation tests/unit/lab/models/test_graph_availability.py tests/unit/lab/models/test_foundation_provenance.py
git commit -m "feat: add provenance-gated graph and foundation challengers"
```

### Task 31: Add L01 DeepLOB baseline dan L02 TLOB-style challenger only after data gate

**Files:**

- Create: `configs/models/L01_deeplob_v1.yaml`
- Create: `configs/models/L02_tlob_v1.yaml`
- Create: `src/indodax_lab/features/lob.py`
- Create: `src/indodax_lab/models/lob/__init__.py`
- Create: `src/indodax_lab/models/lob/dataset.py`
- Create: `src/indodax_lab/models/lob/l01_deeplob.py`
- Create: `src/indodax_lab/models/lob/l02_tlob.py`
- Create: `tests/unit/lab/features/test_lob_features.py`
- Create: `tests/unit/lab/models/lob/test_lob_data_gate.py`
- Create: `tests/integration/lab/test_lob_models_smoke.py`

- [ ] **Step 1: Implement data gate before model code can run**

Require ≥90 days PASS sessions, minimum effective event count, multiple regimes, sequence gap rate threshold, timestamp/latency coverage, and spread/depth labels. Failure returns `BLOCKED_DATA`.

- [ ] **Step 2: Build LOB features and sequences within reliable sessions**

Features match dataset contract: spread, microprice, imbalance L1/L5/L10, depth, OFI, trade imbalance, cancel/insert, book slopes. A sequence never crosses session/recovery gap.

- [ ] **Step 3: Establish simple baselines**

Naive majority, logistic, and simple MLP are mandatory. L01 DeepLOB reproduction runs before L02. Model F1/accuracy without spread-aware profitability is insufficient.

- [ ] **Step 4: Implement spread-aware label/execution evaluation**

Movement threshold incorporates average/realized spread and execution horizon; use actual Indodax liquidity assumptions, not stock FI-2010 result claims.

- [ ] **Step 5: Enforce max 8 configs/model and three-seed finalist**

No model runs while data gate blocked. Tests use tiny synthetic PASS session.

- [ ] **Step 6: Verifikasi**

Run: `python -m pytest tests/unit/lab/features/test_lob_features.py tests/unit/lab/models/lob tests/integration/lab/test_lob_models_smoke.py -q`
Expected: PASS on fixture and `BLOCKED_DATA` on insufficient coverage fixture.

```bash
git add configs/models/L01_deeplob_v1.yaml configs/models/L02_tlob_v1.yaml src/indodax_lab/features/lob.py src/indodax_lab/models/lob tests/unit/lab/features/test_lob_features.py tests/unit/lab/models/lob tests/integration/lab/test_lob_models_smoke.py
git commit -m "feat: add data-gated spread-aware LOB research"
```

**Checkpoint E:** Tidak ada D/G/F/L model yang menjadi champion hanya karena metric prediksi lebih tinggi. Ia harus mengalahkan baseline net-of-cost, stabil lintas fold/seed, dan lulus forward gate.

---

## Tranche F — Operations, Reporting, and Codex Research Automation

### Task 32: Install systemd services/timers untuk ASUS dan worker profile Lenovo

**Files:**

- Create: `deploy/indodax-lab-collector.service`
- Create: `deploy/indodax-lab-sentry.service`
- Create: `deploy/indodax-lab-shadow.service`
- Create: `deploy/indodax-lab-schedule.service`
- Create: `deploy/indodax-lab-schedule.timer`
- Create: `deploy/indodax-lab-worker.service`
- Create: `deploy/install-lab-services.sh`
- Create: `docs/research/operations-runbook.md`
- Create: `tests/unit/lab/orchestration/test_service_commands.py`

- [ ] **Step 1: Test service command generation**

Services use absolute project/venv paths supplied to installer, least-privilege user, `Restart=on-failure`, explicit env file, working directory, and no trade secrets in unit files. Test parser validates command modules exist.

- [ ] **Step 2: Separate host profiles**

ASUS enables collector/sentry/shadow/scheduler only. Lenovo enables worker only. Installer requires `--profile asus|lenovo` and `--dry-run`; it must not enable/start services without explicit `--apply`.

- [ ] **Step 3: Add health and disk guards**

Services emit structured heartbeat. Scheduler pauses ingest/training before disk exhaustion using configured thresholds; retention never deletes raw/snapshot referenced by registry.

- [ ] **Step 4: Document deploy/rollback/recovery**

Runbook covers envs, rsync + checksums from ASUS to Lenovo, DB backup, service start/stop/status, stale job recovery, snapshot quarantine, rollback, and log redaction.

- [ ] **Step 5: Verifikasi**

Run: `python -m pytest tests/unit/lab/orchestration/test_service_commands.py -q`
Run: `bash -n deploy/install-lab-services.sh`
Expected: PASS; do not run `--apply` in CI.

```bash
git add deploy/indodax-lab-* deploy/install-lab-services.sh docs/research/operations-runbook.md tests/unit/lab/orchestration/test_service_commands.py
git commit -m "ops: add separated lab service profiles"
```

### Task 33: Build compact reports dan Telegram read-only status

**Files:**

- Create: `src/indodax_lab/evaluation/reporting.py`
- Create: `src/indodax_lab/cli/report_status.py`
- Modify: `src/telegram_bot.py`
- Create: `tests/unit/lab/evaluation/test_reporting.py`
- Create: `tests/unit/test_telegram_lab_status.py`

- [ ] **Step 1: Create deterministic report JSON/Markdown**

Report includes input/version IDs, gross/net/cost metrics, stress, folds, regimes/tiers/assets, trial count/budget, result taxonomy, data/model drift, resource time, and next allowed action. No raw secret/account identifier.

- [ ] **Step 2: Add read-only Telegram `/lab` command**

Command reads compact status artifact only: data freshness, jobs running/queued/failed, champion/challengers, last gate result, kill switch. It cannot enqueue, tune, promote, or trade.

- [ ] **Step 3: Verify Markdown/HTML escaping and stale state**

Tests cover missing report, stale heartbeat, long strategy names, and no secret leakage.

- [ ] **Step 4: Verifikasi**

Run: `python -m pytest tests/unit/lab/evaluation/test_reporting.py tests/unit/test_telegram_lab_status.py -q`
Expected: PASS.

```bash
git add src/indodax_lab/evaluation/reporting.py src/indodax_lab/cli/report_status.py src/telegram_bot.py tests/unit/lab/evaluation/test_reporting.py tests/unit/test_telegram_lab_status.py
git commit -m "feat: expose read-only research lab status"
```

### Task 34: Add Codex curator prompts dengan branch-only governance

**Files:**

- Create: `configs/codex/hypothesis_curator_v1.md`
- Create: `configs/codex/run_review_v1.md`
- Create: `configs/codex/challenger_implementation_v1.md`
- Create: `src/indodax_lab/orchestration/codex_payload.py`
- Create: `docs/research/codex-automation-runbook.md`
- Create: `tests/unit/lab/orchestration/test_codex_payload.py`

- [ ] **Step 1: Generate minimal sanitized payload**

Payload includes compact metrics, failed gates, trial budget, relevant manifest/config hashes, allowed files, acceptance criteria, and branch/worktree instruction. It excludes `.env`, account payload, raw credentials, user DB, and model/data binaries.

- [ ] **Step 2: Encode governance in prompts**

Codex may propose hypothesis, docs, tests, and code on isolated branch/worktree. It must not trade, alter champion/promotion registry directly, auto-merge, force-push, delete data, or bypass `HARD_FAIL`/budget gates.

- [ ] **Step 3: Test prompt manually before scheduling**

Run one curator prompt on a synthetic failed report. Review scope, generated tests, branch target, and absence of secrets. Record approved prompt hash.

- [ ] **Step 4: Schedule only after manual pass**

Twice-weekly/manual cadence may create review artifacts or draft branch/PR only when requested by owner. Market-critical collector/paper scheduling remains systemd/APScheduler, not Codex UI automation.

- [ ] **Step 5: Verifikasi**

Run: `python -m pytest tests/unit/lab/orchestration/test_codex_payload.py -q`
Expected: PASS.

```bash
git add configs/codex src/indodax_lab/orchestration/codex_payload.py docs/research/codex-automation-runbook.md tests/unit/lab/orchestration/test_codex_payload.py
git commit -m "docs: govern Codex background research curation"
```

### Task 35: Final end-to-end verification dan release candidate

**Files:**

- Create: `tests/regression/test_lab_end_to_end.py`
- Create: `docs/research/release-readiness.md`
- Modify: `docs/doc.md`
- Modify: `docs/api.md`

- [ ] **Step 1: End-to-end offline replay**

Fixture must execute wire → bronze → quality → silver → universe → features → labels → split → classical/M01 tiny run → evaluator → shadow → report. Assert immutable IDs, no leakage, balanced ledger, and expected lifecycle.

- [ ] **Step 2: Run full verification suite**

```bash
python -m pytest -m "not dl" -q
ruff check src tests
python -m compileall -q src
```

Pada environment DL Lenovo, jalankan juga `python -m pytest -m dl -q`. Expected: semua command exit `0`.

- [ ] **Step 3: Run dependency/security sanity**

Use configured dependency audit tool if available; verify no credential/private DB/model/data artifact is staged. Confirm services contain no trade endpoint/permission.

- [ ] **Step 4: Verify reproducibility twice**

Run the golden end-to-end test twice from clean artifact temp dirs. Snapshot/run/report hashes must match except explicitly excluded volatile timestamps, which are stored outside content hash.

- [ ] **Step 5: Write readiness matrix**

For each acceptance criterion mark PASS/BLOCKED with command/artifact evidence. DL/LOB may remain `BLOCKED_DATA` without blocking classical/ML paper lab; live trading remains OUT OF SCOPE.

- [ ] **Step 6: Update baseline docs**

Document new `/lab` command, data directories, research commands, and corrected Trade API v2 fields. Remove contradictory old claims only when verified by tests/source.

- [ ] **Step 7: Commit release candidate**

```bash
git add tests/regression/test_lab_end_to_end.py docs/research/release-readiness.md docs/doc.md docs/api.md
git commit -m "test: verify strategy research lab end to end"
```

**Final checkpoint:** Request code review using `superpowers:requesting-code-review`, address findings, rerun all verification, then use `superpowers:finishing-a-development-branch` to choose merge/PR/keep/discard. Do not enable services or merge without owner approval.

## Execution Handoff

Recommended implementation order is strict: A → B → C → D; E is gate-dependent; F starts after the corresponding runtime is stable. At every checkpoint, attach evidence and stop if a hard invariant fails.

Execution modes:

1. **Subagent-driven (recommended):** use `superpowers:subagent-driven-development`, one fresh worker per task, with spec and quality review between tasks.
2. **Inline/separate session:** use `superpowers:executing-plans`, execute task-by-task with the same checkpoints and no scope bundling.
