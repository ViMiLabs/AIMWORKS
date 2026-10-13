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
            "publication_status": "published",
            "resolver_status": "established",
            "docs_publication_status": "published",
            "artifact_publication_status": "published",
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
    assert (output_dir / "docs" / "hydrogen-ontology.html").exists()
    assert (output_dir / "docs" / "data" / "explorer.json").exists()
    assert (output_dir / "docs" / "assets" / "explorer.css").exists()
    assert (output_dir / "docs" / "assets" / "explorer.js").exists()
    assert (output_dir / "docs" / "source" / "h2kg-asserted-source.jsonld").exists()
    assert (output_dir / "docs" / "pages" / "explore.html").exists()
    assert (output_dir / "docs" / "pages" / "reference.html").exists()
    assert (output_dir / "docs" / "pages" / "core-reference.html").exists()
    assert (output_dir / "docs" / "pages" / "class-index.html").exists()
    home_page = (output_dir / "docs" / "index.html").read_text(encoding="utf-8")
    assert "PEMFC Profile" in home_page
    assert "PEMWE Profile" in home_page
    assert "./pemfc/index.html" in home_page
    assert "./pemwe/index.html" in home_page
    assert "./pages/explore.html" in home_page
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
    assert "Asserted Source" in release_page
    assert "h2kg-asserted-source.jsonld" in release_page
    assert "download='h2kg-asserted-source.jsonld'" in release_page
    assert "ODK and HDO Integration" in release_page
    assert "Publication Establishment" in release_page
    namespace_page = (output_dir / "docs" / "hydrogen-ontology.html").read_text(encoding="utf-8")
    assert "H2KG Namespace Reference" in namespace_page
    assert 'id="Parameter"' in namespace_page
    assert "Open in Explorer" in namespace_page
    reference_page = (output_dir / "docs" / "pages" / "reference.html").read_text(encoding="utf-8")
    assert "H2KG Namespace Reference" in reference_page
    core_reference_page = (output_dir / "docs" / "pages" / "core-reference.html").read_text(encoding="utf-8")
    assert "Core H2KG Reference" in core_reference_page
    assert "Full namespace" in core_reference_page
    explore_page = (output_dir / "docs" / "pages" / "explore.html").read_text(encoding="utf-8")
    assert "Whole-Ontology Search" in explore_page
    assert 'data-explorer-root' in explore_page
    assert "Search the ontology" in explore_page
    assert "Download Excel (.xls)" in explore_page
    assert 'value="relations" data-explorer-view checked' in explore_page
    assert 'value="taxonomy" data-explorer-view' in explore_page
    assert 'value="combined" data-explorer-view' in explore_page
    explorer_data = json.loads((output_dir / "docs" / "data" / "explorer.json").read_text(encoding="utf-8"))
    local_nodes = {item["iri"]: item for item in explorer_data["nodes"] if item.get("local")}
    assert "https://w3id.org/h2kg/hydrogen-ontology#Parameter" in local_nodes
    assert any(link["predicate"] == "subclassOf" for link in explorer_data["links"])
    assert any(link["predicate"] == "range" for link in explorer_data["links"])
    assert any(module["id"] == "schema" for module in explorer_data["modules"])
    explorer_js = (output_dir / "docs" / "assets" / "explorer.js").read_text(encoding="utf-8")
    assert "downloadRelationsAsExcel" in explorer_js
    assert "showHoverCardForNode" in explorer_js
    assert 'state.viewMode = viewMode' in explorer_js
    assert 'link.module === "taxonomy"' in explorer_js
    pemfc_reference_page = (output_dir / "docs" / "pemfc" / "hydrogen-ontology.html").read_text(encoding="utf-8")
    assert "Profile Reference Scope" in pemfc_reference_page
    assert "Reference Contents" in pemfc_reference_page
    assert 'id="Parameter"' in pemfc_reference_page or 'id="ExampleMeasurement"' in pemfc_reference_page
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
            "publication_status": "published",
            "resolver_status": "established",
            "docs_publication_status": "published",
            "artifact_publication_status": "published",
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


def test_docs_merge_taxonomy_property_domains_and_ranges(mini_ontology_file, output_dir):
    ontology_dir = output_dir / "ontology"
    ontology_dir.mkdir()
    (ontology_dir / "h2kg-v2-taxonomy.ttl").write_text(
        """@prefix h2kg: <https://w3id.org/h2kg/hydrogen-ontology#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
h2kg:Process a owl:Class ; skos:prefLabel \"Process\" ; skos:definition \"A test process.\" .
h2kg:SoftwareArtifact a owl:Class ; skos:prefLabel \"Software artifact\" ; skos:definition \"A test software artifact.\" .
h2kg:usesSoftware a owl:ObjectProperty ;
  rdfs:label \"uses software\" ;
  rdfs:domain h2kg:Process ;
  rdfs:range h2kg:SoftwareArtifact ;
  skos:definition \"Relates a process to software it uses.\" .
""",
        encoding="utf-8",
    )
    (ontology_dir / "taxonomy_registry.json").write_text(
        json.dumps(
            {
                "version": "test",
                "review_status": "test",
                "terms": [
                    {
                        "iri": "https://w3id.org/h2kg/hydrogen-ontology#Process",
                        "local_name": "Process",
                        "label": "Process",
                        "definition": "A test process.",
                        "disposition": "active_local_class",
                        "parent_iri": "",
                        "parent_label": "",
                        "ancestor_path": [],
                        "top_branch": "Process",
                        "module": "core",
                        "corrected_semantic_role": "Process",
                    },
                    {
                        "iri": "https://w3id.org/h2kg/hydrogen-ontology#SoftwareArtifact",
                        "local_name": "SoftwareArtifact",
                        "label": "Software artifact",
                        "definition": "A test software artifact.",
                        "disposition": "active_local_class",
                        "parent_iri": "",
                        "parent_label": "",
                        "ancestor_path": [],
                        "top_branch": "InformationEntity",
                        "module": "core",
                        "corrected_semantic_role": "SoftwareArtifact",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    build_docs(mini_ontology_file, output_dir / "docs")

    property_page = (output_dir / "docs" / "pages" / "property-index.html").read_text(encoding="utf-8")
    assert "uses software" in property_page
    assert "Process" in property_page
    assert "SoftwareArtifact" in property_page


def test_docs_merge_validated_external_alignment_registry(mini_ontology_file, output_dir):
    ontology_dir = output_dir / "ontology"
    ontology_dir.mkdir()
    local = "https://w3id.org/h2kg/hydrogen-ontology#ElectrochemicalMeasurement"
    target = "https://w3id.org/emmo/domain/electrochemistry#electrochemical-measurement"
    (ontology_dir / "taxonomy_registry.json").write_text(
        json.dumps(
            {
                "terms": [
                    {
                        "iri": local,
                        "label": "Electrochemical measurement",
                        "definition": "A test electrochemical measurement class.",
                        "disposition": "active_local_class",
                        "parent_iri": "https://w3id.org/h2kg/hydrogen-ontology#Measurement",
                        "parent_label": "Measurement",
                        "ancestor_path": ["https://w3id.org/h2kg/hydrogen-ontology#Process"],
                        "top_branch": "Process",
                        "module": "core",
                        "corrected_semantic_role": "Measurement",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (ontology_dir / "external_alignment_registry.json").write_text(
        json.dumps(
            {
                "mappings": [
                    {
                        "local_iri": local,
                        "local_label": "Electrochemical measurement",
                        "local_kind": "class",
                        "relation": "rdfs:subClassOf",
                        "target_iri": target,
                        "target_label": "Electrochemical measurement",
                        "target_kind": "class",
                        "source": "emmo-electrochemistry",
                        "status": "manual_override",
                        "rationale": "Reviewed test bridge.",
                    }
                ],
                "pending_review_mappings": [
                    {
                        "local_iri": "https://w3id.org/h2kg/hydrogen-ontology#Process",
                        "local_label": "Process",
                        "local_kind": "class",
                        "relation": "skos:closeMatch",
                        "target_iri": "https://example.org/unreviewed-process",
                        "target_label": "Unreviewed process candidate",
                        "target_kind": "class",
                        "source": "automatic-test-candidate",
                        "status": "accepted",
                        "reviewer_decision": "pending-human-review",
                        "rationale": "Automatic candidate that must not be published.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    summary = build_docs(mini_ontology_file, output_dir / "docs")
    explorer = json.loads((output_dir / "docs" / "data" / "explorer.json").read_text(encoding="utf-8"))

    assert summary["mapping_count"] == 1
    assert any(
        link["source"] == local
        and link["target"] == target
        and link["module"] == "alignments"
        for link in explorer["links"]
    )
    assert not any(
        link["target"] == "https://example.org/unreviewed-process"
        for link in explorer["links"]
    )
