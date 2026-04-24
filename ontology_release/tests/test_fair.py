from __future__ import annotations

import json

from aimworks_ontology_release.fair import compute_fair_readiness


def test_fair_readiness_is_not_artificially_perfect(mini_ontology_file, tmp_path):
    reports_dir = tmp_path / "output" / "reports"
    config_dir = tmp_path / "config"
    reports_dir.mkdir(parents=True)
    config_dir.mkdir(parents=True)
    (config_dir / "release_profile.yaml").write_text(
        """
project:
  publication_status: local-build
  docs_publication_status: prepared
  artifact_publication_status: prepared
  resolver_status: prepared
""".strip(),
        encoding="utf-8",
    )
    result = compute_fair_readiness(mini_ontology_file, reports_dir, config_dir)
    assert result["findable"] < 100
    assert result["accessible"] < 100
    assert any(row["label"] == "Release bundle" and row["value"] == "not built in docs-only run" for row in result["publication_assets"])
    assert any(row["label"] == "FOOPS! FAIR assessment" for row in result["transparency_hooks"])


def test_fair_readiness_can_reach_full_internal_score_without_external_services(mini_ontology_file, tmp_path):
    reports_dir = tmp_path / "output" / "reports"
    docs_dir = tmp_path / "output" / "docs"
    w3id_dir = tmp_path / "output" / "w3id"
    bundle_dir = tmp_path / "output" / "release_bundle"
    odk_dir = tmp_path / "output" / "odk" / "artifacts"
    config_dir = tmp_path / "config"
    reports_dir.mkdir(parents=True)
    docs_dir.mkdir(parents=True)
    w3id_dir.mkdir(parents=True)
    bundle_dir.mkdir(parents=True)
    odk_dir.mkdir(parents=True)
    config_dir.mkdir(parents=True)
    (docs_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    (w3id_dir / ".htaccess").write_text("RewriteEngine On\n", encoding="utf-8")
    (bundle_dir / "RELEASE_NOTES.md").write_text("# Release\n", encoding="utf-8")
    (odk_dir / "base.owl").write_text("<rdf:RDF/>", encoding="utf-8")
    (tmp_path / "CITATION.cff").write_text("cff-version: 1.2.0\n", encoding="utf-8")
    (tmp_path / ".zenodo.json").write_text(json.dumps({"title": "H2KG"}), encoding="utf-8")
    (config_dir / "release_profile.yaml").write_text(
        """
project:
  publication_status: local-build
  docs_publication_status: prepared
  artifact_publication_status: prepared
  resolver_status: prepared
""".strip(),
        encoding="utf-8",
    )

    result = compute_fair_readiness(mini_ontology_file, reports_dir, config_dir)

    assert result["findable"] < 100
    assert result["accessible"] < 100
    assert result["publication_evidence"]["resolver_status"] == "prepared"
    assert any(row["label"] == "FOOPS! FAIR assessment" and row["status"] in {"optional", "unavailable"} for row in result["transparency_hooks"])
    assert any(row["label"] == "OWL consistency hook" and row["status"] == "optional" for row in result["validation_signals"])


def test_fair_readiness_requires_explicit_publication_establishment_for_full_findable_and_accessible(mini_ontology_file, tmp_path):
    reports_dir = tmp_path / "output" / "reports"
    docs_dir = tmp_path / "output" / "docs"
    w3id_dir = tmp_path / "output" / "w3id"
    bundle_dir = tmp_path / "output" / "release_bundle"
    odk_dir = tmp_path / "output" / "odk" / "artifacts"
    config_dir = tmp_path / "config"
    reports_dir.mkdir(parents=True)
    docs_dir.mkdir(parents=True)
    w3id_dir.mkdir(parents=True)
    bundle_dir.mkdir(parents=True)
    odk_dir.mkdir(parents=True)
    config_dir.mkdir(parents=True)
    (docs_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    (w3id_dir / ".htaccess").write_text("RewriteEngine On\n", encoding="utf-8")
    (bundle_dir / "RELEASE_NOTES.md").write_text("# Release\n", encoding="utf-8")
    (odk_dir / "base.owl").write_text("<rdf:RDF/>", encoding="utf-8")
    (tmp_path / "CITATION.cff").write_text("cff-version: 1.2.0\n", encoding="utf-8")
    (tmp_path / ".zenodo.json").write_text(json.dumps({"title": "H2KG"}), encoding="utf-8")
    (config_dir / "release_profile.yaml").write_text(
        """
project:
  publication_status: published
  docs_publication_status: published
  artifact_publication_status: published
  resolver_status: established
""".strip(),
        encoding="utf-8",
    )

    result = compute_fair_readiness(mini_ontology_file, reports_dir, config_dir)

    assert result["findable"] == 100
    assert result["accessible"] == 100
    assert result["publication_evidence"]["resolver_status"] == "established"
