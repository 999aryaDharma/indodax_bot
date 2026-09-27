# Plan — activate and implement READY sprints C12-01, S07-01, RW2-02

Owner activation recorded 2026-09-27: owner answered "Aktifkan semua, kerjakan"
for the three READY sprints (EXTENSION/CORE backlog activation gate satisfied by
that answer). Process: subagent-driven development — one implementation owner
at a time, per-task independent review, coordinator integrates and owns all
manifest transitions.

## Tasks

1. **C12-01** Relative strength rotation — spec
   `docs/sprints/strategies/C12-01-relative-strength-rotation.md` — branch
   `feat/c12-01-relative-strength-rotation` — worktree `.worktrees/feat-c12-01`
2. **S07-01** Small-cap rotation — spec
   `docs/sprints/strategies/S07-01-small-cap-rotation.md` — branch per manifest
   `recommended_branch`
3. **RW2-02** Model registry and offline training services — spec
   `docs/sprints/research-workbench/RW2-02-model-registry-and-offline-training-services.md`
   — branch per manifest `recommended_branch`

## Preflight shared-path scan

| Pair | Shared paths | Finding | Ruling |
|---|---|---|---|
| C12-01 ↔ S07-01 | `src/indodax_lab/strategies/__init__.py`, possibly `strategies/registry.py` | both add exports/registrations to the same files | Ruling: serial claims only — S07-01 is claimed after C12-01 is DONE and integrated (single writer per shared path). Cost if wrong: merge conflict, resolved per protocol (understand both behaviors, never blind ours/theirs). |
| C12-01 ↔ RW2-02 | none expected (`strategies/c12.py`+config vs `models/`+services) | clean | still serial — SDD skill forbids parallel implementers |
| S07-01 ↔ RW2-02 | none expected | clean | still serial |

Spec self-consistency is deferred to the per-task reviewer: the sprint spec is
the binding authority and is reviewed against the diff, not pre-digested here.

## Process rulings

- Ruling: one implementation subagent at a time — SDD skill "never dispatch
  multiple implementation subagents in parallel", reinforced by protocol
  single-writer-per-shared-path. Cost if wrong: n/a (serial is conservative).
- Ruling: integration into `feat/feat-02-finalization` by fast-forward only,
  and only after the independent task review passes on the sprint-branch SHA
  (fast-forward keeps the reviewed SHA identical, so no re-review of content).
- Ruling: manifest transitions are coordinator-only (READY→IN_PROGRESS on
  claim, IN_PROGRESS→REVIEW when handoff lands, REVIEW→DONE only with
  reviewed_handoff evidence + identified independent reviewer).
- Ruling: scratch workspace `.superpowers/sdd/ready-sprints/` is the SDD
  ledger/report home; `.superpowers/` added to `.gitignore` (chore commit).
