# CR-OPS-03-APPLY-COORDINATION — serialize reachability changes with deletion

Status: PROPOSED
Owner: Project owner; date: 2026-09-27
Requested outcome: prevent cleanup from unlinking an artifact that becomes reachable after the cleaner's final registry check.
Current limitation: OPS-03 revalidates reachability and filesystem identity immediately before unlink, but a lifecycle transition or file replacement can race between that check and unlink. The current registry resolver is injected; there is no authoritative Champion/SEALED_PASS adapter or shared writer lock in this repository.
Why now: independent delta review confirmed this remaining Important finding at `d01d4f3ce2050979c6deb5fa4aea59bd450f5053`.

## Alternatives and tradeoffs

1. **Shared host lock (recommended if all writers can be enumerated):** define one local cross-process lock contract; cleanup holds it from final registry read through unlink; every lifecycle promotion, artifact publication/replacement, and registry path update affecting the storage root must take the same lock. Smaller persistence change, but correctness depends on complete adoption by every writer.
2. **Registry deletion claim/tombstone (stronger, recommended if artifacts have multiple writers):** authoritative artifact registry atomically claims an expired, unreferenced artifact as `DELETING`; promotion/reference creation rejects claimed artifacts; cleanup unlinks then records completion. Interrupted cleanup resumes from the durable claim. Requires a central registry, state/schema changes, and writer integration, but gives explicit crash recovery and prevents a newly reachable artifact from racing deletion.
3. **Operational quiescence only:** stop every producer and lifecycle writer during an approved cleanup window. Lowest code cost, but no enforceable evidence/current supervisor contract exists; manual discipline alone is insufficient for unattended apply.

## Scope and impact

Affects OPS-03 FR0/FR1/FR3, its Python apply contract, storage publication/lifecycle writers, integration tests, and possibly EVAL-03 lifecycle state. No Production keys/orders/account authority changes. Research artifact data only. No dataset licensing, financial budget, or model evaluation semantics change. No legacy records are rewritten.

Before implementation: choose option, identify every writer to the storage roots, define lock/claim ownership and crash behavior, then update OPS-03 and affected owner specs; add an ADR if the registry lifecycle becomes a new source of truth. Manifest stays unchanged until acceptance evidence and independent PASS.

## Acceptance evidence

- A deterministic interleaving test pauses cleanup after reachability inspection while another actor attempts to publish/promote the same artifact; the writer must block or the deletion claim must make the transition fail.
- After cleanup completes, the artifact cannot be reachable from Champion/SEALED_PASS state.
- Crash/failure injection after claim/lock acquisition and after unlink proves bounded release/recovery and idempotent rerun.
- Every writer to covered roots is enumerated and shown to use the same lock/claim contract; no mock-only integration proof.
- OPS-03 focused/integration checks and independent review pass on the exact commit.

## Rollback

Disable apply and keep audit/dry-run. For shared locks, retain the lock contract until all writers are reverted together. For tombstones, preserve claims/history; recovery tooling may complete or safely release a claim only after proving the artifact is unreferenced. Never delete tombstone/audit history to roll back.

## Owner decision

Pending. Select shared host lock, registry deletion claim/tombstone, or hold OPS-03 apply for separately scheduled integration.

## Repository evidence (2026-09-28)

- `CandidateRecord` in `src/indodax_lab/evaluation/lifecycle.py` stores candidate identity/config/stage but no artifact ID or path; transition writes are transactionally recorded by `CandidateLifecycleManager.transition_candidate`.
- Immutable artifact publication is called from `data/publication.py`, CLI dataset builders/backfill, `universe/snapshot.py`, `universe/coingecko_adapter.py`, data wire/sentry stores, and `orchestration/queue.py` (which has its own `_publish_artifact`). These are not currently wrapped by one retention coordination contract.
- Therefore there is no existing complete Champion/SEALED_PASS -> artifact-path index to adapt, and a cleaner-only lock would not serialize lifecycle transitions or all publishers. Option 1 requires centralizing/wrapping all of these write paths. Option 2 requires a new authoritative artifact reachability index linked transactionally to candidate transitions and publication.
- Manifest recheck on 2026-09-28: DONE 63, REVIEW 44, PLANNED 25, IN_PROGRESS 2 (`S08-01`, `S09-01`), READY none. No alternate eligible sprint can be selected under the coordinator protocol while those dependency gates remain unsettled.
