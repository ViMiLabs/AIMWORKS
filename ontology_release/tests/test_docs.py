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
    quality_page = (output_dir / "docs" / "pages" / "quality-dashboard.html").read_text(encoding="utf-8")
    assert "FAIR Signals" in quality_page
    assert "FOOPS! Assessment" in quality_page
    assert "not built in docs-only run" in quality_page
