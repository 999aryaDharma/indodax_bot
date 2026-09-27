# S09 pump-gap historical range measurement v1

Status: descriptive historical-price evidence only. It does not set a policy threshold or qualify a live producer.

## Measurement

For each adjacent, contiguous, closed 1-hour candle pair, compute the upward close-to-close return:

```text
pump_gap_fraction = current_close / previous_close - 1
```

Report positive returns as percentiles. Candles are included only when both rows pass bronze quality checks and are closed. No gaps are filled or backfilled.

## Verified input and result

- Source root: `lab-data-fetch2/` (`indodax-history-v2` hourly bronze candles).
- Range: 2021-01-01 00:00 UTC through 2026-01-01 00:00 UTC, covering calendar years 2021–2025.
- Input integrity: 120 snapshot manifests and all 120 referenced Parquet partitions passed SHA-256, byte-size and row-count checks. All 87,648 candle rows were `PASS` and closed; each pair had 43,823 adjacent returns and zero chronology gaps.
- Partition-tree SHA-256: `4fb684f16b0629ff5025333e57a14c08e3d1c14c2f7f1e659633a9fe589024db`.
- Reproduce: `C:/Users/User/miniconda3/envs/ML/python.exe scripts/research/measure_s09_pump_gap_ranges.py --output docs/research/s09-pump-gap-historical-range-v1.json`.
- Environment: Python 3.12.13, PyArrow 24.0.0.

| Pair | Positive returns / all | Positive return p50 | p90 | p95 | p99 | Maximum |
|---|---:|---:|---:|---:|---:|---:|
| BTC/IDR | 21,647 / 43,823 (49.40%) | 0.2074% | 0.8184% | 1.1838% | 2.2848% | 7.8302% |
| ETH/IDR | 21,913 / 43,823 (50.00%) | 0.2895% | 1.1071% | 1.5769% | 2.9399% | 12.2767% |

Yearly positive-return p95 ranges from 0.8205% to 1.6651% for BTC/IDR and 0.9089% to 2.2537% for ETH/IDR. Full pair/year quantiles and row counts are in the JSON output.

## Limits and S09 disposition

This measures historical candle price movement, not pump-gap predictive value or strategy profitability. It does not measure feed delivery age: historical `available_at - close_time` is about 101 million seconds at the median, because these candles were ingested long after the event. The archive has no point-in-time realtime pump-gap producer, source registration or feed-age observations. Therefore it is useful for describing a candidate historical range, but cannot justify a live evidence-age limit, producer qualification or activation. Keep the numeric threshold and maximum input age unset; S09 remains fail-closed and IN_PROGRESS until a causally available producer is registered, its live freshness/ranges are measured, and the owner approves a versioned Research policy.
