# Coordination and handoff protocol

## Claims and ownership

Before editing, coordinator records sprint ID, owner, branch/worktree, base SHA, requested paths and review owner in a handoff/work log. Claims are exclusive for that sprint. Shared paths (`sprint-manifest.json`, main.py, telegram_bot.py, pyproject.toml, CI, central registry and migrations) need explicit single-writer ownership even when DAG nodes are independent. Actual implementation of a lock service is outside this documentation task.

## Two-agent lifecycle

Implementer claims READY → IN_PROGRESS; commits scoped work → REVIEW with exact SHA packet. Reviewer returns PASS or CHANGES_REQUESTED with reproducible findings. Implementer fixes only those contracts and updates SHA/evidence. Reviewer verifies new diff and affected invariants. Coordinator releases claim and marks DONE only after final PASS. A third person/agent can coordinate; cannot substitute self-review for independent review.

## Interruptions and conflicts

If owner disappears, preserve dirty worktree and record last heartbeat/time; do not reset/clean. Coordinator may reassign after inspecting state, but new owner resumes from recorded WIP and same fix-round count. Merge conflicts require understanding both intended behaviors and rerunning affected acceptance, never blindly ours/theirs. If dependency changes while work runs, rebase review target deliberately and reverify.

## Status versus artifacts

Manifest changes are serialized. Projection files are updated together and validated. Code SHA differs from subsequent evidence SHA; record both. A DONE imported before this planning system remains labeled historical. No commit implies push or remote backup. No documentation daemon is running.
