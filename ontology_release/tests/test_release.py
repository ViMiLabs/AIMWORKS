from __future__ import annotations

from aimworks_ontology_release.release import run_pipeline


def test_release_bundle_generation(temp_project):
    run_pipeline("input/sample.ttl", root=temp_project, stage="release")
    assert (temp_project / "output" / "ontology" / "schema.ttl").exists()
    assert (temp_project / "output" / "mappings" / "alignments.ttl").exists()
    assert (temp_project / "output" / "w3id" / ".htaccess").exists()
    assert (temp_project / "output" / "publication" / "hydrogen-ontology.html").exists()
    assert (temp_project / "output" / "publication" / "2026.3.0" / "ontology.ttl").exists()
    assert (temp_project / "output" / "release_bundle" / "manifest.json").exists()
    assert (temp_project / "output" / "release_bundle" / "publication" / "source" / "ontology.ttl").exists()
    assert (temp_project / "output" / "release_bundle" / "docs" / "pages" / "quality-dashboard.html").exists()
    assert (temp_project / "output" / "release_bundle" / "docs" / "pages" / "queries.html").exists()
    assert (temp_project / "output" / "release_bundle" / "docs" / "pages" / "visualizations.html").exists()
    assert (temp_project / "output" / "release_bundle" / "docs" / "pages" / "import-catalog.html").exists()
    assert (temp_project / "output" / "release_bundle" / "docs" / "pages" / "namespace-policy.html").exists()
    assert (temp_project / "output" / "release_bundle" / "docs" / "pages" / "deprecation-policy.html").exists()
    assert (temp_project / "output" / "release_bundle" / "docs" / "pages" / "worked-examples.html").exists()
    assert (temp_project / "output" / "release_bundle" / "docs" / "pages" / "cite.html").exists()
    assert (temp_project / "output" / "release_bundle" / "reports" / "changelog_report.md").exists()
    assert (temp_project / "output" / "release_bundle" / "reports" / "import_catalog.json").exists()
