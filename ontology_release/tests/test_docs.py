from __future__ import annotations

from aimworks_ontology_release.docs import build_docs


def test_docs_generation(mini_ontology_file, output_dir):
    (output_dir / "review").mkdir()
    (output_dir / "reports").mkdir()
    fair_snapshot = {
        "findable": 78,
        "accessible": 62,
        "interoperable": 71,
        "reusable": 66,
        "summary": "Quality checks are based on the built release candidate and external services when available.",
        "artifacts": ["Machine-readable source", "w3id artifacts"],
        "fair_signals": [{"label": "F / Findable", "status": "watch", "value": "78 / 100", "detail": "Internal release-readiness signal."}],
        "transparency_hooks": [{"label": "FOOPS! FAIR assessment", "status": "watch", "value": "service unavailable", "detail": "External service could not be reached."}],
        "validation_signals": [{"label": "Missing definitions", "status": "good", "value": "0", "detail": "Release-time missing definitions or comments on local schema terms."}],
        "publication_assets": [{"label": "Release bundle", "status": "watch", "value": "not built in docs-only run", "detail": "Bundle stage was not executed."}],
        "section_explanations": {"fair_signals": "Internal FAIR signals estimate release readiness from locally built ontology artifacts."},
        "foops": {"status": "unavailable", "message": "External service could not be reached.", "dimensions": {}, "failed_checks": []},
        "oops": {"status": "disabled", "message": "Disabled in this run.", "pitfalls": []},
    }
    summary = build_docs(mini_ontology_file, output_dir / "docs", fair_snapshot=fair_snapshot)
    assert summary["schema_count"] >= 2
    assert (output_dir / "docs" / "index.html").exists()
    assert (output_dir / "docs" / "pages" / "class-index.html").exists()
    home_page = (output_dir / "docs" / "index.html").read_text(encoding="utf-8")
    assert "PEMFC Profile" in home_page
    assert "PEMWE Profile" in home_page
    assert "./pemfc/index.html" in home_page
    assert "./pemwe/index.html" in home_page
    assert (output_dir / "docs" / "pemfc" / "index.html").exists()
    assert (output_dir / "docs" / "pemfc" / "hydrogen-ontology.html").exists()
    assert (output_dir / "docs" / "pemwe" / "index.html").exists()
    assert (output_dir / "docs" / "pemwe" / "hydrogen-ontology.html").exists()
    assert (output_dir / "docs" / "pages" / "import-guide.html").exists()
    assert (output_dir / "docs" / "pages" / "import-catalog.html").exists()
    assert (output_dir / "docs" / "pages" / "developer-guide.html").exists()
    assert (output_dir / "docs" / "pages" / "architecture-workflow.html").exists()
    quality_page = (output_dir / "docs" / "pages" / "quality-dashboard.html").read_text(encoding="utf-8")
    assert "FAIR Signals" in quality_page
    assert "FOOPS! Assessment" in quality_page
    assert "ODK / ROBOT QC" in quality_page
    assert "not built in docs-only run" in quality_page
    release_page = (output_dir / "docs" / "pages" / "release.html").read_text(encoding="utf-8")
    assert "ODK Release Artefacts" in release_page
    assert "ODK and HDO Integration" in release_page
    import_page = (output_dir / "docs" / "pages" / "import-guide.html").read_text(encoding="utf-8")
    assert "run.bat make refresh-imports" in import_page
    assert "HDO is the preferred Helmholtz-community source" in import_page
    developer_page = (output_dir / "docs" / "pages" / "developer-guide.html").read_text(encoding="utf-8")
    assert "ontology_release/odk/src/ontology/run.bat make prepare_release" in developer_page
    assert "When to Use HDO vs EMMO vs PROV / DCTERMS" in developer_page
