from indodax_lab.paths import LabPaths


def test_from_env_uses_explicit_project_root_defaults(monkeypatch, tmp_path):
    """Changing the process directory must not change the default lab roots."""
    monkeypatch.delenv("INDODAX_LAB_DATA_DIR", raising=False)
    monkeypatch.delenv("INDODAX_LAB_ARTIFACT_DIR", raising=False)

    paths = LabPaths.from_env(tmp_path / "research-project")

    assert paths.data_root == tmp_path / "research-project" / "lab-data"
    assert paths.artifact_root == tmp_path / "research-project" / "lab-artifacts"


def test_from_env_uses_environment_output_overrides(monkeypatch, tmp_path):
    """Changing either output environment variable changes only that output root."""
    data_root = tmp_path / "external-data"
    artifact_root = tmp_path / "external-artifacts"
    monkeypatch.setenv("INDODAX_LAB_DATA_DIR", str(data_root))
    monkeypatch.setenv("INDODAX_LAB_ARTIFACT_DIR", str(artifact_root))

    paths = LabPaths.from_env(tmp_path / "research-project")

    assert paths.data_root == data_root
    assert paths.artifact_root == artifact_root
