# Security Boundary and Attack Resistance Evidence (QA-02)

## Scope and Intent
This audit proves that sensitive credential access, artifact loaders, and destructive execution paths are strictly closed in the Indodax Research Lab release candidate. The project is strictly for academic research and paper/shadow trading.

## Threat Model and Security Guarantees

| Boundary / Asset | Threat Vector | Defense Mechanism | Verified Invariant |
|---|---|---|---|
| **Trade & Withdrawal Credentials** | Accidental or malicious execution of real orders or withdrawal of exchange funds. | `audit_no_trade_withdraw_keys()` enforces fail-closed zero-tolerance. Scanning rejects any key matching `TRADE_KEY`, `TRADE_SECRET`, `WITHDRAW_KEY`, `WITHDRAWAL_SECRET`. | **Zero live credentials**. Lab operates exclusively in paper/shadow mode. No real orders, no withdrawals. |
| **Artifact Loader & Storage** | Directory traversal attacks (`../../`) attempting to read or overwrite system files outside artifact roots. | `safe_resolve_artifact_path()` checks for `..` tokens and verifies `target.resolve().is_relative_to(base_dir)`. Rejects fail-closed with `PathTraversalError`. | **Path containment guaranteed**. All artifact reads/writes are strictly contained within designated directories. |
| **Model Deserialization** | Remote code execution via Python `pickle` deserialization. | `verify_artifact_bytes_safe()` explicitly scans for Python pickle opcodes (`\x80\x04`, `c__builtin__`, `cos`, etc.) and forbids them fail-closed (`SecurityViolationError`). Persistence uses plain JSON with schema validation and checksum verification (`PortableBundleLoader`). | **No arbitrary code execution**. Pickles strictly forbidden. Plain JSON / Parquet only. |
| **Reporting & Telegram** | Unauthorized disclosure of lab holdings, positions, cash, or active strategy IDs to external parties. | `ReadOnlyTelegramReporter` strictly enforces chat allowlists. Unauthorized chat IDs receive `UnauthorizedChatError` without leaking holdings or portfolio details. Markdown characters are escaped; bot tokens and secrets are redacted. | **Chat allowlist enforced**. Holdings confidential and inaccessible to non-allowlisted chats. |

## Verification Test Results

Tests executed via `tests/security/test_lab_boundaries.py`:
- `test_qa_02_valid_contract`: Proves overall security audit runner succeeds on clean research configuration, verifying all boundaries.
- `test_qa_02_contract_1`: Proves traversal attacks (`../../etc/passwd`, `..\..\windows\win.ini`, etc.) and malicious pickle payloads are rejected fail-closed.
- `test_qa_02_contract_2`: Proves discovery of any live trading or withdrawal credentials triggers immediate fail-closed error (`SecurityViolationError`).
- `test_qa_02_contract_3`: Proves unauthorized Telegram chats cannot query status, holdings, or balances.

## Summary Status
- Critical Vulnerabilities: 0
- High Severity Findings: 0
- Verification Status: **PASSED** (all gates met for QA-02).
