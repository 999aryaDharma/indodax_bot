# Phase 2 Tournament Verification

## Overview

The Wave 1 tournament integrates classical machine learning models (M01, M02, M03, M04, M05, M06) and rule-based strategies (C01, C02, C03, C04, C07, C10, S01, S02) into a deterministic evaluation checkpoint.

## Governance & Safety Notice

> **IMPORTANT DISCLAIMER**: Tiny CI offline tournament results do not constitute evidence of live market profitability (QA-01-AC3). All tournament evaluations are conducted in paper research mode under synthetic data conditions.

## Follow-up Action Mapping

Evaluation outcomes directly determine scheduler DAG follow-up actions per JOB-03 repeat policies:
- **PASS**: Advanced to shadow forward trading (`ADVANCE_TO_SHADOW`).
- **HARD_FAIL**: Retries permanently blocked (`BLOCK_RETRIES`). Requires new hypothesis/CR.
- **NEAR_MISS**: Retry permitted only with a new version increment (`REQUIRE_NEW_VERSION`).
- **INVALID_RUN**: Retry permitted with exponential backoff under retry budget cap (`RETRY_WITH_BACKOFF`).
