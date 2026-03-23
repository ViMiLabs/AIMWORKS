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
    assert (temp_project / "output" / "docs" / "pages" / "get-started.html").exists()
    assert (temp_project / "output" / "docs" / "pages" / "architecture-workflow.html").exists()
    assert (temp_project / "output" / "docs" / "pages" / "emmo-alignment.html").exists()
    assert (temp_project / "output" / "docs" / "pages" / "module-index.html").exists()
    assert (temp_project / "output" / "docs" / "pages" / "metrics.html").exists()
    assert (temp_project / "output" / "docs" / "pages" / "developer-guide.html").exists()
    assert (temp_project / "output" / "docs" / "pages" / "h2kg-vs-battinfo.html").exists()
    assert (temp_project / "output" / "docs" / "pages" / "queries.html").exists()
    assert (temp_project / "output" / "docs" / "pages" / "quality-dashboard.html").exists()
    assert (temp_project / "output" / "docs" / "pages" / "visualizations.html").exists()
    assert (temp_project / "output" / "docs" / "assets" / "visuals.css").exists()
    assert (temp_project / "output" / "docs" / "assets" / "visuals.js").exists()
    assert (temp_project / "output" / "docs" / "data" / "import_catalog.json").exists()
    assert (temp_project / "output" / "docs" / "data" / "graph_explorer.json").exists()
    assert (temp_project / "output" / "docs" / "data" / "module_index.json").exists()
    assert (temp_project / "output" / "docs" / "data" / "ontology_stats.json").exists()
    assert (temp_project / "output" / "docs" / "data" / "engineering_workflow.json").exists()
    assert (temp_project / "output" / "docs" / "data" / "emmo_alignment.json").exists()
    assert (temp_project / "output" / "docs" / "data" / "stable_access.json").exists()
    assert (temp_project / "output" / "docs" / "data" / "release_assets.json").exists()
    assert (temp_project / "output" / "docs" / "data" / "example_measurement.jsonld").exists()
    assert (temp_project / "output" / "docs" / "data" / "example_measurement.csv").exists()
    assert (temp_project / "output" / "docs" / "data" / "example_release_notebook.ipynb").exists()
    assert (temp_project / "output" / "publication" / "source" / "ontology.ttl").exists()
    assert (temp_project / "output" / "publication" / "source" / "asserted.ttl").exists()
    assert (temp_project / "output" / "publication" / "source" / "catalog-v001.xml").exists()
    assert (temp_project / "output" / "publication" / "source" / "modules" / "core.ttl").exists()
    assert (temp_project / "output" / "publication" / "inferred" / "full_inferred.ttl").exists()
    assert (temp_project / "output" / "publication" / "latest" / "ontology.ttl").exists()
    queries_page = (temp_project / "output" / "docs" / "pages" / "queries.html").read_text(encoding="utf-8")
    assert "Query Console" in queries_page
    assert "Run query" in queries_page
    assert "data-query-source" in queries_page
    assert "data-run-preset" in queries_page
    quality_page = (temp_project / "output" / "docs" / "pages" / "quality-dashboard.html").read_text(encoding="utf-8")
    assert "https://oops.linkeddata.es/" in quality_page
    assert "https://foops.linkeddata.es/FAIR_validator.html" in quality_page
    visuals_page = (temp_project / "output" / "docs" / "pages" / "visualizations.html").read_text(encoding="utf-8")
    assert "Ontology Explorer" in visuals_page
    assert "data-visual-explorer" in visuals_page
    assert "Show directly linked external terms" in visuals_page
    assert "Search across the published local ontology terms" in visuals_page
    assert "Traversal history" in visuals_page
    assert "Undo last step" in visuals_page
    assert "cytoscape.min.js" in visuals_page
    reference_page = (temp_project / "output" / "docs" / "hydrogen-ontology.html").read_text(encoding="utf-8")
    assert "Controlled Vocabulary" in reference_page
    assert "<th>Class</th><th>Quantity kind</th><th>Unit</th><th>Definition</th><th>Mappings</th>" in reference_page
    assert "Unit Review Notes" in reference_page
    assert "Referenced ontologies" in reference_page
    assert "https://w3id.org/battinfo" in reference_page
    architecture_page = (temp_project / "output" / "docs" / "pages" / "architecture-workflow.html").read_text(encoding="utf-8")
    assert "Asserted vs Inferred" in architecture_page
    assert "catalog-v001.xml" in architecture_page
    emmo_page = (temp_project / "output" / "docs" / "pages" / "emmo-alignment.html").read_text(encoding="utf-8")
    assert "EMMO Universe" in emmo_page
    assert "Schema-level alignment coverage" in emmo_page
    assert "Vocabulary mapping coverage" in emmo_page
    release_page = (temp_project / "output" / "docs" / "pages" / "release.html").read_text(encoding="utf-8")
    assert "Human-Readable vs Machine-Readable Artifacts" in release_page
    assert "source/asserted.ttl" in release_page
    assert "Tagged Release Assets" in release_page
    home_page = (temp_project / "output" / "docs" / "index.html").read_text(encoding="utf-8")
    assert "Current Access Patterns" in home_page
    assert "GitHub Releases and Packaging" in home_page


def test_contributor_homepage_links_stay_out_of_referenced_ontologies(temp_project):
    sample_path = temp_project / "input" / "sample.ttl"
    sample_path.write_text(
        sample_path.read_text(encoding="utf-8")
        + """

<https://w3id.org/h2kg/hydrogen-ontology>
  <http://xmlns.com/foaf/0.1/homepage> <https://www.fz-juelich.de/en/iet/iet-3/divisions-1/artificial-material-intelligence> ;
  <http://www.w3.org/2000/01/rdf-schema#seeAlso> <https://www.fz-juelich.de/en/iet/iet-3/divisions-1/artificial-material-intelligence> .
""",
        encoding="utf-8",
    )

    run_pipeline("input/sample.ttl", root=temp_project, stage="docs")

    reference_page = (temp_project / "output" / "docs" / "hydrogen-ontology.html").read_text(encoding="utf-8")
    assert "Contributors" in reference_page
    assert "https://www.fz-juelich.de/en/iet/iet-3/divisions-1/artificial-material-intelligence" in reference_page
    assert "<h3>Referenced ontologies</h3>" in reference_page
    assert "<li><a href=\"https://www.fz-juelich.de/en/iet/iet-3/divisions-1/artificial-material-intelligence\"><code>https://www.fz-juelich.de/en/iet/iet-3/divisions-1/artificial-material-intelligence</code></a></li>" not in reference_page
