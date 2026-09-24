# Dynamic shared-pool documentation amendment

Date: 2026-09-24. Source HEAD: `3d59484fc2f5d6a7e9d27916b052f01eaa3f534e`.

Scope: owner-approved replacement of fixed agent capital quotas with shared-pool allocation; candidate-owned adaptive sizing/exits under central risk limits; verified venue minima, rounding and feasible exits. Records the three selected agents, total IDR 500,000 and unresolved numerical risk settings. Updates CR, ADR-010, program, PM-08 spec and only its manifest contract/acceptance text. No status/DAG or runtime change.

Checks (Windows PowerShell, ML Python): `python docs/quality/validate_planning.py` PASS (134 nodes, 264 edges, zero cycles); `git diff --check -- docs` PASS. Runtime tests are not applicable to this documentation change. Concurrent API/UI documentation edits are excluded from this slice.

Review: independent exact-commit review pending; no sprint marked DONE. The documentation commit containing this handoff is the review target. Numerical per-trade/aggregate limits, API-route minimum evidence, candidate bindings, shared-capital evaluation, staged release and host qualification remain open before activation. No live state/host change, push or deployment.
