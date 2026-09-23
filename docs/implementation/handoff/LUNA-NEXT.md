# LUNA-NEXT — PM-03 & PM-04 Execution

## TASK ID

- PM-03 — Recovery mode and durable operator risk governance (Priority P0, production-main)
- PM-04 — Venue parser cancellation and supported order semantics (Priority P0, production-main)

## STATUS

- RW0-01: DONE (SHA `627c53f`)
- RP-01: DONE (SHA `5d9629e`)
- PM-01: DONE (SHA `99c3a0c`)
- RW1-01: DONE (SHA `9060726`, independent review PASS Round 2 by subagent 1f7c3297)
- LED-01: DONE (SHA `4933dcb`, independent review PASS Round 2 by subagent 0326e570)
- PM-02: DONE (SHA `ed7dcdc`, independent review PASS Round 2 by subagent 913ea7ee)
- PM-03: READY (P0, production-main) — Unlocked by PM-01 + PM-02
- PM-04: READY (P0, production-main) — Unlocked by PM-01 + PM-02

## ACTIVE WORK

Claiming **PM-03** and **PM-04** for implementation in sequence/parallel:
1. PM-03: Recovery mode and durable operator risk governance (`src/indodax_lab/execution/recovery_service.py`, `src/indodax_lab/risk/operator_governance.py`)
2. PM-04: Venue parser cancellation and supported order semantics (`src/indodax_lab/execution/venue_parser.py`, `src/indodax_lab/execution/order_semantics.py`)
