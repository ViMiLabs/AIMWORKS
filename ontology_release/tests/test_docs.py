from __future__ import annotations

from aimworks_ontology_release.release import run_pipeline


def test_docs_generation(temp_project):
    run_pipeline("input/sample.ttl", root=temp_project, stage="docs")
    assert (temp_project / "output" / "docs" / "index.html").exists()
    assert (temp_project / "output" / "docs" / "hydrogen-ontology.html").exists()
    assert (temp_project / "output" / "docs" / "pages" / "class-index.html").exists()
    assert (temp_project / "output" / "docs" / "pages" / "property-index.html").exists()
    assert (temp_project / "output" / "docs" / "pages" / "scope-and-faq.html").exists()
    assert (temp_project / "output" / "docs" / "pages" / "modeling-patterns.html").exists()
    assert (temp_project / "output" / "docs" / "pages" / "import-catalog.html").exists()
    assert (temp_project / "output" / "docs" / "pages" / "namespace-policy.html").exists()
    assert (temp_project / "output" / "docs" / "pages" / "deprecation-policy.html").exists()
    assert (temp_project / "output" / "docs" / "pages" / "import-guide.html").exists()
    assert (temp_project / "output" / "docs" / "pages" / "cite.html").exists()
    assert (temp_project / "output" / "docs" / "pages" / "worked-examples.html").exists()
    assert (temp_project / "output" / "docs" / "pages" / "changelog.html").exists()
    assert (temp_project / "output" / "docs" / "pages" / "queries.html").exists()
    assert (temp_project / "output" / "docs" / "pages" / "quality-dashboard.html").exists()
    assert (temp_project / "output" / "docs" / "pages" / "visualizations.html").exists()
    assert (temp_project / "output" / "docs" / "data" / "import_catalog.json").exists()
    assert (temp_project / "output" / "docs" / "data" / "example_measurement.jsonld").exists()
    assert (temp_project / "output" / "docs" / "data" / "example_measurement.csv").exists()
    assert (temp_project / "output" / "docs" / "data" / "example_release_notebook.ipynb").exists()
    assert (temp_project / "output" / "publication" / "source" / "ontology.ttl").exists()
    assert (temp_project / "output" / "publication" / "latest" / "ontology.ttl").exists()
    queries_page = (temp_project / "output" / "docs" / "pages" / "queries.html").read_text(encoding="utf-8")
    assert "Query Console" in queries_page
    assert "Run query" in queries_page
    assert "data-query-source" in queries_page
    assert "data-run-preset" in queries_page
    quality_page = (temp_project / "output" / "docs" / "pages" / "quality-dashboard.html").read_text(encoding="utf-8")
    assert "https://oops.linkeddata.es/" in quality_page
    assert "https://foops.linkeddata.es/FAIR_validator.html" in quality_page
