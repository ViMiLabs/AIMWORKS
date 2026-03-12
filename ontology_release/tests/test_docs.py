from __future__ import annotations

from aimworks_ontology_release.release import run_pipeline


def test_docs_generation(temp_project):
    run_pipeline("input/sample.ttl", root=temp_project, stage="docs")
    assert (temp_project / "output" / "docs" / "index.html").exists()
    assert (temp_project / "output" / "docs" / "hydrogen-ontology.html").exists()
    assert (temp_project / "output" / "docs" / "pages" / "class-index.html").exists()
    assert (temp_project / "output" / "docs" / "pages" / "property-index.html").exists()
    assert (temp_project / "output" / "publication" / "source" / "ontology.ttl").exists()
    assert (temp_project / "output" / "publication" / "latest" / "ontology.ttl").exists()
