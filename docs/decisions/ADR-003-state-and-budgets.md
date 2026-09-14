# ADR-003 — Separate state machines and bounded experiments

Status: ACCEPTED planning clarification. Date: 2026-09-14.

Context: job failures, invalid runs, bad strategies and sprint status describe different things. Mixing them causes retry loops or premature promotion. Older prose gives family cap two revisions while ML task gives one model revision.

Decision: retain separate sprint, job, run validity, evaluator outcome and candidate lifecycle states. Retry is for technical failure after a root fix, not for negative returns. NEAR_MISS allows at most one model/horizon revision under its remaining trial budget; family-level aggregate never exceeds two revision rounds on the same snapshot. The stricter applicable cap wins. All failed trials count; new seeds cannot reset a budget. A version bump does not reset family ancestry.

HARD_FAIL archives; INVALID_RUN can requeue same immutable config under bounded retry; REGIME_EDGE proposes a new reviewed causal hypothesis; PASS freezes then opens the next eligible gate. Changes after holdout exposure are new challengers and inherit exposure information.

Default budgets: classical 24 coarse +12 refinement, ML 30 trials, DL 12 configs ×50 max epochs/patience7, graph/LOB8 configs. Their numeric values are research policy defaults, not evidence of good hyperparameters. Owner can change only through versioned policy and consequences recorded before new experiments.

Sprint review may take at most five fix rounds; unresolved load-bearing issue then BLOCKED and escalated with evidence. A new agent does not reset that counter.
