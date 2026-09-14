# Agent execution guide

The shared entry point for Codex and Antigravity is root `AGENTS.md`, followed by `.agents/README.md`. Product contracts are tool-independent. Tool-specific automatic instruction loading is not assumed: include these paths in the first prompt if necessary.

Start with FEAT-01 after confirming docs branch integration and original Task15 WIP location. Use `.agents/workflows/next-sprint.md`. Assign one implementation owner and a different reviewer; never have both edit the same feature concurrently.

A documentation branch can be reviewed/cherry-picked into the implementation branch with conflicts resolved deliberately. Do not cherry-pick uncommitted product code from the reverse direction or lose WIP. No push or merge is claimed by local commit creation.

[Prompt guide](prompt-guide.md) · [Curator prompts](curator-prompts.md) · [Coordination](../../.agents/coordination/protocol.md)
