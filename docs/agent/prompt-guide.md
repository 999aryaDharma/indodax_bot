# Agent prompt guide

## Start one sprint

```text
Read AGENTS.md, docs/sprints/sprint-manifest.json and .agents/workflows/next-sprint.md.
Select FEAT-01 only if dependencies remain DONE and no other owner has claimed it.
Inspect original Task15 WIP before reuse; preserve unrelated untracked files.
Read the FEAT-01 sprint and its Required Reading.
Implement only its acceptance contracts with RED -> GREEN, then affected verification.
Commit scoped files, write exact-SHA handoff and stop at REVIEW for an independent agent.
No downstream implementation, no gate changes and no real trading.
```

## Review another agent

```text
Act as independent reviewer for the sprint ID and committed SHA in the handoff.
Read AGENTS.md, its sprint checklist and .agents/workflows/review-sprint.md.
Verify spec compliance and quality separately. Inspect actual code and reproduce targeted tests.
List Critical/Important/Minor findings with location, failure mechanism and required regression.
Do not approve from test count alone or modify unrelated features.
```

## Continue after an interruption

```text
Recover the chosen sprint from manifest, handoff, worktree and actual git status.
Do not reset or clean WIP. Confirm owner and reviewer, current SHA and accumulated fix rounds.
Resume only incomplete acceptance/finding work; preserve completed evidence with its target SHA.
If independent review is unavailable, report REVIEW pending rather than DONE.
```

Every sprint includes its own ready-to-run prompt. Prefer that specific prompt after selection; do not ask an agent to implement the entire 92-sprint portfolio in one unbounded change.
