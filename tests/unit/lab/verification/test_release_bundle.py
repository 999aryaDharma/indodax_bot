"""Tests for ReleaseBundle creation and cryptographic verification."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from indodax_lab.verification.release_bundle import (
    ReleaseBundleIntegrityError,
    create_release_bundle,
    verify_release_bundle,
)

NOW = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)


def test_release_bundle_creation_and_verification_success() -> None:
    git_sha = "a1b2c3d4e5f67890"
    config_data = '{"max_drawdown": 0.15, "pairs": ["btc_idr"]}'
    schema_data = "CREATE TABLE orders (id TEXT PRIMARY KEY);"

    bundle = create_release_bundle(
        bundle_id="bundle_v1.0.0",
        git_commit_sha=git_sha,
        config_payload=config_data,
        schema_payload=schema_data,
        author="operator_arya",
        packaged_at=NOW,
    )

    assert bundle.bundle_id == "bundle_v1.0.0"
    assert bundle.git_commit_sha == git_sha
    assert len(bundle.config_hash) == 64
    assert len(bundle.schema_hash) == 64

    # Verify against exact matching data
    is_valid = verify_release_bundle(
        bundle,
        expected_git_sha=git_sha,
        config_payload=config_data,
        schema_payload=schema_data,
    )
    assert is_valid is True


def test_release_bundle_verification_fails_on_tampered_config() -> None:
    git_sha = "a1b2c3d4e5f67890"
    config_data = '{"max_drawdown": 0.15}'
    tampered_config = '{"max_drawdown": 0.99}'  # Tampered config!
    schema_data = "CREATE TABLE orders (id TEXT);"

    bundle = create_release_bundle(
        bundle_id="bundle_v1.0.0",
        git_commit_sha=git_sha,
        config_payload=config_data,
        schema_payload=schema_data,
        author="operator_arya",
        packaged_at=NOW,
    )

    with pytest.raises(ReleaseBundleIntegrityError, match="CONFIG_HASH_MISMATCH"):
        verify_release_bundle(
            bundle,
            expected_git_sha=git_sha,
            config_payload=tampered_config,
            schema_payload=schema_data,
        )


def test_release_bundle_verification_fails_on_git_sha_mismatch() -> None:
    git_sha = "a1b2c3d4e5f67890"
    config_data = '{"mode": "AUTONOMOUS_LIMITED"}'
    schema_data = "CREATE TABLE test (id INT);"

    bundle = create_release_bundle(
        bundle_id="bundle_v1.0.0",
        git_commit_sha=git_sha,
        config_payload=config_data,
        schema_payload=schema_data,
        author="operator_arya",
    )

    with pytest.raises(ReleaseBundleIntegrityError, match="GIT_SHA_MISMATCH"):
        verify_release_bundle(
            bundle,
            expected_git_sha="different_git_commit_sha",
            config_payload=config_data,
            schema_payload=schema_data,
        )
