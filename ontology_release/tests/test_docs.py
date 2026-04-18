from __future__ import annotations

import json
import os

from aimworks_ontology_release.docs import build_docs


def test_docs_generation(mini_ontology_file, output_dir):
    (output_dir / "review").mkdir()
    (output_dir / "reports").mkdir()
    fair_snapshot = {
        "generated_at": "2026-04-13T10:00:00+00:00",
        "findable": 78,
        "accessible": 62,
        "interoperable": 71,
        "reusable": 66,
        "summary": "Quality checks use a public-first interpretation of publication readiness.",
        "artifacts": [],
        "publication_evidence": {
            "publication_status": "local-build",
            "resolver_status": "prepared",
            "docs_publication_status": "prepared",
            "artifact_publication_status": "prepared",
        },
        "fair_signals": [{"label": "F / Findable", "status": "watch", "value": "78 / 100", "detail": "Internal release-readiness signal."}],
        "transparency_hooks": [{"label": "FOOPS! FAIR assessment", "status": "unavailable", "value": "external service unreachable", "detail": "External service could not be reached."}],
        "validation_signals": [
            {"label": "Overall validation status", "status": "good", "value": "pass", "detail": "Combined validation checks."},
            {"label": "SHACL conforms", "status": "good", "value": "True", "detail": "SHACL check passed."},
            {"label": "OWL consistency hook", "status": "optional", "value": "not enabled in current environment (owlready2 not installed)", "detail": "Optional OWL reasoner hook."},
            {"label": "Missing definitions", "status": "good", "value": "0", "detail": "Release-time missing definitions or comments on local schema terms."},
        ],
        "publication_assets": [{"label": "Release bundle", "status": "watch", "value": "not built in docs-only run", "detail": "Bundle stage was not executed."}],
        "section_explanations": {"fair_signals": "FAIR signals use a public-first release interpretation rather than treating local build artifacts as public publication proof."},
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
    assert "Current Release Status" in quality_page
    assert "Report Freshness" in quality_page
    assert "External Service Status" in quality_page
    assert "Publication Establishment" in quality_page
    assert "OPTIONAL" in quality_page
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
    assert "Optional Local QC Hooks" in developer_page


def test_docs_quality_dashboard_flags_stale_report_inputs(mini_ontology_file, output_dir):
    reports_dir = output_dir / "reports"
    odk_dir = output_dir / "odk"
    reports_dir.mkdir()
    odk_dir.mkdir()
    (reports_dir / "fair_readiness_report.json").write_text("{}", encoding="utf-8")
    (reports_dir / "validation_report.json").write_text("{}", encoding="utf-8")
    (reports_dir / "hdo_alignment_report.json").write_text(json.dumps({"summary": {}}), encoding="utf-8")
    (odk_dir / "manifest.json").write_text(json.dumps({"status": "enabled", "parity": {"status": "aligned"}, "imports": [], "artifacts": []}), encoding="utf-8")
    os.utime(reports_dir / "fair_readiness_report.json", (1700000000, 1700000000))
    os.utime(reports_dir / "validation_report.json", (1700000600, 1700000600))
    os.utime(reports_dir / "hdo_alignment_report.json", (1700001200, 1700001200))
    os.utime(odk_dir / "manifest.json", (1700001800, 1700001800))

    fair_snapshot = {
        "generated_at": "2026-04-13T10:00:00+00:00",
        "findable": 86,
        "accessible": 85,
        "interoperable": 100,
        "reusable": 100,
        "summary": "Internal FAIR signals are local release-readiness indicators.",
        "publication_evidence": {
            "publication_status": "local-build",
            "resolver_status": "prepared",
            "docs_publication_status": "prepared",
            "artifact_publication_status": "prepared",
        },
        "artifacts": [],
        "fair_signals": [],
        "transparency_hooks": [],
        "validation_signals": [{"label": "Overall validation status", "status": "good", "value": "pass", "detail": "ok"}, {"label": "SHACL conforms", "status": "good", "value": "True", "detail": "ok"}],
        "publication_assets": [],
        "section_explanations": {},
        "foops": {"status": "unavailable", "message": ""},
        "oops": {"status": "unavailable", "message": ""},
    }

    build_docs(mini_ontology_file, output_dir / "docs", fair_snapshot=fair_snapshot)
    quality_page = (output_dir / "docs" / "pages" / "quality-dashboard.html").read_text(encoding="utf-8")
    assert "out of sync" in quality_page
