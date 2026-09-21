# ADR-007 — One local transactional execution store per namespace

Status: ACCEPTED planning decision, 2026-09-21. Implementation remains PLANNED; production activation remains forbidden.

Context: current ledger mutation/persistence, OMS transition and fill-applied identity use separate commits. Replay repair does not eliminate the crash window between OMS increment and identity record. Snapshot checksums alone do not prove journal linkage or revision freshness.

Decision: one authoritative local SQLite transaction per namespace applies normalized fill, exact ledger postings, OMS cumulative quantity/event, unique fill identity and audit. Memory updates publish only after commit. Event cursor advances atomically with completed event effects or via an explicit persisted resumable event envelope; never before fill effects. Optimistic revision checks and one writer prevent stale-state commits. Transaction content is verified against linked snapshot/replay on startup. Identical fill replay is no-op; conflicting duplicate, unmatched/overfill or inconsistent state halts/quarantines.

Alternative: cross-store saga could preserve separate databases but expands financial ambiguity and recovery complexity. Prefer a single local store because single-host/single-writer is already the approved deployment. No shared SQLite WAL across hosts.

Migration: offline copy current OMS/journal/snapshots/applied IDs into a new versioned namespace, reconcile and verify linkage, preserve originals read-only, refuse cutover on ambiguity. Never edit a runtime DB in tests. Shadow namespaces reuse transaction semantics while production uses separate authority and real reconciliation. Rollback before activation selects old read-only evidence; an activated financial history is never rolled back by deleting committed fills.
