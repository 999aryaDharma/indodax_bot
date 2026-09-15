# Model Blocker Truthfulness Report

**Date:** 2026-09-16
**Branch:** dev
**HEAD:** b11f6fd

## 1. Executive Summary

Berdasarkan audit independen dan eksekusi tes aktual, status kesiapan dari setiap keluarga model adalah sebagai berikut:

| Model Family | Model ID | Status | Reason / Evidence |
|---|---|---|---|
| Regularized Linear | M01 (Logistic) | **READY** | 5/5 unit tests PASS. Elastic-net regularizer, SAGA solver, held-out isotonic/sigmoid calibration, cash/naive utility benchmarking. |
| Gradient Boosting | M02 (XGBoost) | **QUALIFIED (Environment-Dependent)** | 5/5 unit tests PASS di Windows ML conda env (xgboost 2.0.3). Terblokir di macOS arm64 jika libomp tidak terinstall. |
| Deep Learning | D01 (MLP) | **READY (Offline Smoke Verified)** | PyTorch 2.6.0+cu124 aktif. 4/4 integration smoke tests PASS (`test_d01_training_smoke.py`). |
| Deep Learning | D02–D04 (TCN, ResNet-LSTM, iTransformer) | **BLOCKED on Dataset Pipeline** | Memerlukan assembly training dataset sekuensial penuh (DL-02 sequence dataset) dengan split 2021–2023 / 2024 / 2025. |
| Limit Order Book | L01 (DeepLOB), L02 (TLOB) | **BLOCKED on Real LOB Data** | Folder `lab-data-*` hanya berisi data time-bar (candles), belum ada data feed order book depth (LOB). Dilarang mensimulasikan LOB menggunakan proxy volume. |
| Reinforcement Learning | R01 (Allocator) | **BLOCKED on Prerequisites** | Memerlukan simulator execution feed yang fully-reconciled dengan fill authority. |
| Graph / Foundation | G01, F01 | **BLOCKED on Prerequisites** | Memerlukan cross-asset graph relation dataset dan foundation provenance weights gate. |

---

## 2. Command & Test Evidence

### M01 Logistic Baseline
```powershell
python -B -m pytest tests/unit/lab/models/test_m01_logistic.py -v
```
**Output:**
```
tests/unit/lab/models/test_m01_logistic.py::test_m01_01_valid_contract PASSED
tests/unit/lab/models/test_m01_logistic.py::test_m01_01_contract_1 PASSED
tests/unit/lab/models/test_m01_logistic.py::test_m01_01_contract_2 PASSED
tests/unit/lab/models/test_m01_logistic.py::test_m01_01_contract_3 PASSED
tests/unit/lab/models/test_m01_logistic.py::test_m01_01_config_yaml_and_unfitted_guards PASSED
5 passed in 2.51s
```

### M02 XGBoost
```powershell
python -B -m pytest tests/unit/lab/models/test_m02_xgboost.py -v
```
**Output:**
```
tests/unit/lab/models/test_m02_xgboost.py::test_m02_01_valid_contract PASSED
tests/unit/lab/models/test_m02_xgboost.py::test_m02_01_contract_1 PASSED
tests/unit/lab/models/test_m02_xgboost.py::test_m02_01_contract_2 PASSED
tests/unit/lab/models/test_m02_xgboost.py::test_m02_01_contract_3 PASSED
tests/unit/lab/models/test_m02_xgboost.py::test_m02_01_config_yaml_and_unfitted_guards PASSED
5 passed in 2.21s
```

### D01 MLP (PyTorch)
```powershell
python -B -m pytest tests/integration/lab/test_d01_training_smoke.py -v
```
**Output:**
```
tests/integration/lab/test_d01_training_smoke.py::test_d01_01_valid_contract PASSED
tests/integration/lab/test_d01_training_smoke.py::test_d01_01_contract_1 PASSED
tests/integration/lab/test_d01_training_smoke.py::test_d01_01_contract_2 PASSED
tests/integration/lab/test_d01_training_smoke.py::test_d01_01_contract_3 PASSED
4 passed in 7.58s
```

---

## 3. Strict Boundary Rules

1. **No Premature Promotion:** Model M01/M02/D01 yang lolos test suite tetap berstatus riset paper/shadow saja.
2. **Label Fidelity Binding:** Target pelatihan saat ini menggunakan open-price proxy v2 (`promotion_eligible=False`, `execution_fidelity=RESEARCH_PRICE_PROXY_ONLY`).
3. **No Fabricated Performance:** Tidak ada klaim Sharpe, PnL, atau win rate yang dipublikasikan tanpa backtest run yang mengikat judge authority dan ledger reconciliation.
