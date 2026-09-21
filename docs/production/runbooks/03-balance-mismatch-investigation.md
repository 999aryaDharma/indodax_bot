# Runbook 03: Balance Mismatch and Reconciliation Investigation

## Purpose

This runbook guides operators through diagnosing and remediating balance discrepancies flagged during read-only reconciliation cycles.

## Guiding Principles

1. **Reconciliation Status is Authoritative:** If `ReconciliationReport.healthy` is `False`, all new order submissions are halted (`HALT_NEW_ORDERS`).
2. **Never Edit Historical Ledger Direct:** The `ResearchLedger` is an append-only double-entry journal. Never modify existing SQLite rows or delete transactions.
3. **No Blind Flattening:** Do not blindly liquidate positions without understanding the mismatch source.

## Diagnosis Workflow

### 1. Check Reconciliation Report Issues

Inspect the diagnostic report produced by `ReconciliationEngine`:
```text
Issue Codes:
- ASSET_BALANCE_MISMATCH: Base asset held in ledger != exchange account balance
- QUOTE_BALANCE_MISMATCH: IDR cash in ledger != exchange IDR total
- INTERNAL_OPEN_ORDER_MISSING_AT_VENUE: Bot expects an open order that Indodax has already filled or cancelled
- UNEXPECTED_VENUE_OPEN_ORDER: An open order exists on Indodax that the bot did not create
- VENUE_FILL_MISSING_FROM_LEDGER: Fills occurred on Indodax that were not ingested into ledger
- LEDGER_FILL_MISSING_AT_VENUE: A ledger fill does not exist in venue trade history
```

### 2. Common Root Causes & Actions

#### Scenario A: `VENUE_FILL_MISSING_FROM_LEDGER`
- **Cause:** Order executed on exchange, but execution worker crashed before ingesting the fill.
- **Remedy:**
  1. Use `VenueFillIngester.ingest_fills` on recent fills fetched from `Trade API v2 (myTrades)`.
  2. Re-run reconciliation.
  3. Cursor advances once verified.

#### Scenario B: `ASSET_BALANCE_MISMATCH` or `QUOTE_BALANCE_MISMATCH`
- **Cause 1: External Deposit or Withdrawal**
  - An external deposit or withdrawal occurred on the Indodax account outside the trading bot.
  - **Remedy:** Post a capital adjustment entry to the ledger (`Posting(AccountType.CASH, ...)` or `Posting(AccountType.CAPITAL, ...)`).
- **Cause 2: Fee Currency Discrepancy**
  - Exchange charged fee in base asset (e.g. BTC) instead of quote currency (IDR).
  - **Remedy:** Non-quote commissions fail closed by design until multi-currency fee valuation is audited. Verify commission asset in the raw fill.

#### Scenario C: `UNEXPECTED_VENUE_OPEN_ORDER`
- **Cause:** Human operator manually placed an order via the Indodax mobile app or web interface, or another bot is sharing the same API keys.
- **Remedy:**
  - Dedicated API keys are mandatory for the trading bot.
  - Cancel the rogue order manually on the exchange, or adopt it into the OMS store if authorized.

### 3. Re-certification

Re-run the reconciliation coordinator:
```python
result = coordinator.run(..., auto_ingest_fills=True)
if result.report.healthy:
    print("Reconciliation restored to HEALTHY. Durable cursor advanced.")
```
