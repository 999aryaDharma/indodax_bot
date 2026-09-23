# ADR-009 — ASUS hosts Production Main and Research Runtime

Status: ACCEPTED by the owner, 2026-09-24. Change request: [CR-20260924](CR-20260924-asus-production-and-research-host.md).

## Context

The owner corrected the previous host allocation: ASUS is the Production Main server and also remains the Research Workbench execution host for experiments, backtests, shadow agents and tournaments. Lenovo is the owner's daily laptop and handles ML/DL model training and tuning. ASUS hardware limits are shared across existing services and both product domains; live inventory and capacity are not yet qualified.

## Decision

1. ASUS runs Production Main and Research Runtime as distinct processes and authority domains on the same physical host.
2. Production Main is the live real-trading authority and owns its immutable running release, production read models, risk/OMS/ledger state and server-side Indodax credentials. Research Runtime has no access to those credentials or Production write paths.
3. Research Runtime on ASUS owns its public market-data feed, experiments/backtests, research/shadow state, isolated tournament accounts, local evidence and CPU inference for admitted artifacts. It does not supply authoritative Production feed or account state.
4. Lenovo runs ML/DL training and tuning. Candidate/model artifacts are exported immutably and imported through a receiving-side verification boundary before any ASUS runtime may load them. No shared SQLite/WAL, live remote writer, automatic promotion or unverified model deserialization is allowed.
5. Production and Research resource budgets are separate. Admission on the shared ASUS host must reserve measured Production headroom; under pressure, optional Research work is deferred or stopped first. The host is not qualified by owner-reported CPU/RAM figures alone.
6. OPS-01 service lifecycle and QA-03 capacity/recovery qualification must prove the co-resident topology, including representative combined load, restart isolation, durability and recovery. REL-01 cannot treat the host as qualified without that evidence.
7. This decision changes host placement only. Owner-confirmed Production Main remains live on ASUS; existing execution and production safety gates remain governed by its backend. Research/shadow/tournament state stays isolated, and G0–G7 continue to govern candidate qualification and release changes.

## Supersession

ADR-009 supersedes ADR-008 only where ADR-008 states that Production Main runs on a separate host or that ASUS has no Production Main role. ADR-008's shared market runtime, feed recovery, bounded fan-out, ASUS Research Runtime, tournament isolation and Lenovo training/tuning separation remain accepted. ADR-004 and older architecture text are superseded on host placement only.

## Consequences and open implementation details

- ASUS co-location creates a measured resource/failure-domain constraint, not a shared state boundary. No HA or independent host redundancy is implied.
- Production and Research may have separate market gateways/connections even though they share hardware. A Research feed must not be relabeled as Production truth.
- The artifact transfer channel, signing policy, exact sandboxing mechanism and capacity thresholds must be chosen by scoped implementation work. Until then, no signature claim or deployment readiness is implied.
- A read-only Production API/dashboard may be developed independently. ASUS installation remains gated on inventory, service isolation, rollback, network exposure and combined-host qualification.

## Rollback

For documentation, revert the scoped CR/ADR updates while preserving prior evidence. Runtime rollback must stop only the affected service and preserve both domains' local durable state; it may not rewind or merge their databases.
