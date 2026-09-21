# Production Main — Implementation Roadmap and Open Gap Register

**Architecture:** frozen.  
**Implementation:** incomplete by design; this document tracks remaining work.

## Priority P0 — financial/execution correctness

1. **Indodax real order parser**
   - share one canonical parser between read-only and write adapters;
   - correctly derive original/remaining/executed quantities from real Indodax payloads;
   - add fixture tests using venue-shaped payloads.

2. **Cancel uncertainty**
   - a successful cancel response plus inconclusive post-cancel financial state must not synthesize zero-fill CANCELLED truth;
   - preserve UNKNOWN/CANCEL_PENDING uncertainty until order/fill evidence is conclusive.

3. **Fill atomicity**
   - overfill validation must occur before irreversible financial mutation;
   - define transactional/saga recovery for ledger + OMS.

4. **Fill idempotency**
   - persist fill-to-OMS application identity;
   - duplicate venue fills must never increment OMS quantity twice.

5. **Durable production ledger**
   - separate from research/paper in-memory ledger;
   - transactional durable journal;
   - processed fill IDs;
   - cash/positions/capital flows;
   - integrity + revision checks;
   - restart/replay tests.

6. **Mandatory pre-write reconciliation authority**
   - every real write requires fresh healthy reconciliation evidence;
   - freshness age and scope are explicit;
   - UNKNOWN count must be zero.

## Priority P1 — control/governance

7. **Safe startup**
   - restart always enters RECOVERY;
   - previous mode is desired state only.

8. **Trusted durable control state**
   - mode store with integrity/version/event journal/operator/reason;
   - approval store with tamper evidence;
   - approval token reverified immediately before execution.

9. **Manual approval re-risk**
   - fresh equity, cash, positions, market, reconciliation and risk assessment after approval and before submit.

10. **Kill-switch reset**
    - remove fail-open defaults;
    - operator CLI must call governed reset path instead of unlinking sentinel directly.

11. **Risk durability**
    - production kill-switch/throttle/risk state persistence mandatory;
    - persistence failure halts new orders;
    - enforce all declared autonomous limits including hard daily notional loss caps.

12. **Order semantics**
    - initial production scope should explicitly support a small reviewed subset, preferably LIMIT + one proven TIF;
    - reject unsupported internal order semantics rather than relying on venue defaults.

## Priority P1/P2 — release/security/CI

13. Expand release bundle to bind candidate/model/feature/risk/execution/cost/dependency identities.
14. Add authenticity/signing mechanism if release signatures are claimed.
15. Expand strict CI to all canonical production modules.
16. Add Git-history secret scanning, dependency/CVE audit and SBOM.
17. Remove documentation claims that exceed code/evidence.

## Operational evidence after code blockers

18. Complete G5 view-only integration.
19. Build production-shaped shadow using the exact runtime path with a non-writing venue boundary.
20. Provision target Linux host and systemd.
21. Wire persistent metrics/logs/alerts.
22. Complete backup/restore and disaster drills; measure RPO/RTO.
23. Accumulate G3 forward evidence.
24. Run G6 manual micro-live.
25. Only then consider G7 AUTONOMOUS_LIMITED.

## Explicit non-goals until later

- unrestricted autonomous mode;
- active-active writers;
- direct RL execution;
- automatic model promotion;
- dashboard-owned financial state;
- withdrawal capability.
