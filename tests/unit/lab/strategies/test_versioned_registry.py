"""Behavioral tests for durable, versioned strategy registration (RW2-01)."""

import hashlib
import sqlite3
from decimal import Decimal

import pytest

from indodax_lab.contracts.identity import ArtifactRef
from indodax_lab.strategies.base import StrategySpecification
from indodax_lab.strategies.registry import StrategyRegistry
from indodax_lab.strategies.store import StrategyService, StrategyStore


def test_same_version_specification_metadata_change_rejects() -> None:
    """All behavior-defining spec fields, not only parameters, bind a version."""
    original = StrategySpecification(
        strategy_id="C02",
        version="1.0.0",
        family="trend_pullback",
        timeframes=["1h"],
        parameters={"desired_qty": Decimal("0.1")},
        risk_profile={"stop_loss_pct": 0.02},
        split="train",
    )
    changed = original.model_copy(update={"risk_profile": {"stop_loss_pct": 0.03}})
    registry = StrategyRegistry()
    registry.register(original, lambda frame: [])

    with pytest.raises(ValueError, match="PARAMETER_OR_LOGIC_CHANGE_REQUIRES_VERSION_BUMP"):
        registry.register(changed, lambda frame: [])


def _service(tmp_path):
    return StrategyService(StrategyStore(tmp_path / "strategies.sqlite"))


def test_rw2_01_0_published_same_version_change_rejects(tmp_path) -> None:
    service = _service(tmp_path)
    manifest = service.builtin_manifest("C02")
    draft = service.create_draft(manifest)
    published = service.publish(draft.id, draft.revision)

    changed = manifest.model_copy(
        deep=True,
        update={"parameters": {**manifest.parameters, "atr_multiplier": 2.0}},
    )
    changed_draft = service.create_draft(changed)
    with pytest.raises(ValueError, match="IMMUTABLE_VERSION_CONFLICT"):
        service.publish(changed_draft.id, changed_draft.revision)

    assert service.get(published).parameters == manifest.parameters


def test_rw2_01_0_published_same_version_source_change_rejects(tmp_path, monkeypatch) -> None:
    service = _service(tmp_path)
    original = service.builtin_manifest("C02")
    draft = service.create_draft(original)
    service.publish(draft.id, draft.revision)
    changed_source = original.implementation_artifact_ref.sha256.encode() + b"\nsource-change"
    digest = hashlib.sha256(changed_source).hexdigest()
    source_ref = ArtifactRef(kind="strategy_source", id="C02", version=digest[:16], sha256=digest)
    monkeypatch.setattr(
        StrategyService,
        "_source",
        staticmethod(lambda component_id: (source_ref, changed_source)),
    )

    changed = service.builtin_manifest("C02")
    changed_draft = service.create_draft(changed)
    with pytest.raises(ValueError, match="IMMUTABLE_VERSION_CONFLICT"):
        service.publish(changed_draft.id, changed_draft.revision)


def test_rw2_01_1_stale_draft_revision_cannot_overwrite_edit(tmp_path) -> None:
    service = _service(tmp_path)
    draft = service.create_draft(service.builtin_manifest("C07"))
    current = service.update_draft(
        draft.id, draft.revision, {**service.get_draft(draft.id).parameters, "rsi_oversold": 28.0}
    )

    with pytest.raises(ValueError, match="STALE_DRAFT_REVISION"):
        service.update_draft(
            draft.id,
            draft.revision,
            {**service.get_draft(draft.id).parameters, "rsi_oversold": 25.0},
        )
    assert service.get_draft(draft.id).parameters["rsi_oversold"] == 28.0
    assert current.revision == 2


def test_rw2_01_1_revision_cas_holds_across_service_connections(tmp_path) -> None:
    first = _service(tmp_path)
    second = StrategyService(StrategyStore(tmp_path / "strategies.sqlite"))
    draft = first.create_draft(first.builtin_manifest("C02"))
    first.update_draft(
        draft.id,
        draft.revision,
        {**first.get_draft(draft.id).parameters, "atr_multiplier": 1.7},
    )

    with pytest.raises(ValueError, match="STALE_DRAFT_REVISION"):
        second.update_draft(
            draft.id,
            draft.revision,
            {**second.get_draft(draft.id).parameters, "atr_multiplier": 1.8},
        )


def test_publish_failure_keeps_draft_and_publication_visibility_atomic(tmp_path) -> None:
    service = _service(tmp_path)
    draft = service.create_draft(service.builtin_manifest("C07"))
    service.store._conn.execute(
        """CREATE TRIGGER fail_publication BEFORE INSERT ON strategy_publications
           BEGIN SELECT RAISE(ABORT, 'injected'); END"""
    )

    with pytest.raises(sqlite3.IntegrityError, match="injected"):
        service.publish(draft.id, draft.revision)
    assert (
        service.store._conn.execute("SELECT COUNT(*) FROM strategy_publications").fetchone()[0] == 0
    )
    assert service.get_draft(draft.id).strategy_id == "C07"

    service.store._conn.execute("DROP TRIGGER fail_publication")
    assert service.publish(draft.id, draft.revision).id == "C07"


def test_published_source_bytes_are_verified_before_return(tmp_path) -> None:
    service = _service(tmp_path)
    draft = service.create_draft(service.builtin_manifest("C02"))
    ref = service.publish(draft.id, draft.revision)
    source_hash = service.get(ref).implementation_artifact_ref.sha256
    service.store._conn.execute(
        "UPDATE strategy_blobs SET content = ? WHERE sha256 = ?", (b"corrupt", source_hash)
    )

    with pytest.raises(ValueError, match="STRATEGY_SOURCE_HASH_MISMATCH"):
        service.get(ref)


def test_rw2_01_2_unknown_source_and_executable_yaml_reject(tmp_path) -> None:
    service = _service(tmp_path)
    manifest = service.builtin_manifest("C02")
    unsafe = manifest.model_copy(
        deep=True,
        update={
            "implementation_artifact_ref": ArtifactRef(
                kind="strategy-source",
                id="os",
                version="1",
                sha256="0" * 64,
            )
        },
    )
    with pytest.raises(ValueError, match="UNAPPROVED_STRATEGY_SOURCE"):
        service.create_draft(unsafe)

    with pytest.raises(ValueError, match="UNKNOWN_CONFIG_FIELDS"):
        service.load_manifest_yaml(
            "strategy_id: C02\nversion: '1.0.0'\nimplementation_module: os\n"
        )


def test_rw2_01_3_clone_preserves_parent_and_source(tmp_path) -> None:
    service = _service(tmp_path)
    original_manifest = service.builtin_manifest("C07")
    original = service.create_draft(original_manifest)
    published = service.publish(original.id, original.revision)

    clone = service.clone(published)
    assert service.get_draft_parent(clone.id) == published
    clone_manifest = service.get_draft(clone.id)
    assert clone_manifest.version != original_manifest.version
    service.update_draft(
        clone.id,
        clone.revision,
        {**service.get_draft(clone.id).parameters, "bb_std": 2.2},
    )
    clone_ref = service.publish(clone.id, clone.revision + 1)
    assert service.get(published).parameters == original_manifest.parameters
    assert service.get(clone_ref).parameters["bb_std"] == 2.2


def test_rw2_01_program_4_component_metadata_yaml_and_durable_reload(tmp_path) -> None:
    service = _service(tmp_path)
    components = service.component_metadata()
    assert {component.component_id for component in components} == {"C02", "C07"}
    assert all(component.parameter_schema_version for component in components)
    assert all("import_path" not in component.model_dump(mode="json") for component in components)

    manifest = service.builtin_manifest("C02")
    roundtrip = service.load_manifest_yaml(service.export_manifest_yaml(manifest))
    assert roundtrip == manifest
    draft = service.create_draft(roundtrip)
    ref = service.publish(draft.id, draft.revision)
    service.store.close()

    reopened = _service(tmp_path)
    assert reopened.get(ref) == manifest


def test_seed_manifests_bind_selected_pairs_without_pair_dispatch(tmp_path) -> None:
    service = _service(tmp_path)
    refs = service.seed_manifests()
    manifests = [service.get(ref) for ref in refs]

    assert {(manifest.strategy_id, manifest.parameters["pair"]) for manifest in manifests} == {
        ("BTC-C07", "btc_idr"),
        ("ETH-C02", "eth_idr"),
        ("SOL-C02", "sol_idr"),
    }
    assert {ref.id for ref in refs} == {
        "BTC-C07",
        "ETH-C02",
        "SOL-C02",
    }
    assert service.seed_manifests() == refs


@pytest.mark.parametrize("component_id", ["C02", "C07"])
def test_seed_manifest_preserves_yaml_strategy_and_risk_defaults(tmp_path, component_id) -> None:
    service = _service(tmp_path)
    source_spec = StrategyRegistry().load_specification_from_yaml(
        f"configs/strategies/{component_id}_v1.yaml"
    )
    manifest = service.builtin_manifest(component_id)

    assert {key: value for key, value in manifest.parameters.items() if key != "risk_profile"} == (
        source_spec.parameters
    )
    assert {
        key: float(value) for key, value in manifest.parameters["risk_profile"].items()
    } == source_spec.risk_profile


def test_registry_builtin_registration_uses_allowlist(tmp_path) -> None:
    registry = StrategyRegistry()
    spec = registry.load_specification_from_yaml("configs/strategies/C02_v1.yaml")
    registered = registry.register_builtin(spec)
    assert registered.specification.strategy_id == "C02"

    unlisted = spec.model_copy(update={"strategy_id": "UNKNOWN"})
    with pytest.raises(ValueError, match="UNKNOWN_BUILTIN_STRATEGY_ID"):
        registry.register_builtin(unlisted)
