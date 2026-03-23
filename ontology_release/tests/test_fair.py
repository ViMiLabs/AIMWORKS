from __future__ import annotations

from aimworks_ontology_release.fair import compute_fair_readiness


def test_fair_readiness_is_not_artificially_perfect(mini_ontology_file, tmp_path):
    reports_dir = tmp_path / "output" / "reports"
    reports_dir.mkdir(parents=True)
    result = compute_fair_readiness(mini_ontology_file, reports_dir)
    assert result["findable"] < 100
    assert result["accessible"] < 100
    assert any(row["label"] == "Release bundle" and row["value"] == "not built in docs-only run" for row in result["publication_assets"])
    assert any(row["label"] == "FOOPS! FAIR assessment" for row in result["transparency_hooks"])
