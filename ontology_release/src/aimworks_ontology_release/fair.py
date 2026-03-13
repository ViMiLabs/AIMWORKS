from __future__ import annotations

from pathlib import Path
from typing import Any

from rdflib import Graph
from rdflib.namespace import DCTERMS, OWL, RDF

from .utils import read_json, write_text


def compute_fair_scores(root: Path) -> dict[str, Any]:
    inspection = read_json(root / "output" / "reports" / "inspection_report.json")
    validation = read_json(root / "output" / "reports" / "validation_report.json")
    schema_graph = Graph()
    schema_graph.parse(root / "output" / "ontology" / "schema.ttl", format="turtle")
    ontology_nodes = list(schema_graph.subjects(RDF.type, OWL.Ontology)) or list(schema_graph.subjects())
    ontology_node = ontology_nodes[0] if ontology_nodes else None
    schema_ttl = (root / "output" / "ontology" / "schema.ttl").exists()
    schema_jsonld = (root / "output" / "ontology" / "schema.jsonld").exists()
    docs_index = (root / "output" / "docs" / "index.html").exists()
    w3id_ready = (root / "output" / "w3id" / ".htaccess").exists()
    citation_ready = (root / "CITATION.cff").exists() and (root / ".zenodo.json").exists()
    mappings_ready = (root / "output" / "mappings" / "alignments.ttl").exists()
    examples_ready = (root / "output" / "examples" / "examples.ttl").exists()
    has_title = bool(ontology_node and list(schema_graph.objects(ontology_node, DCTERMS.title)))
    has_description = bool(ontology_node and list(schema_graph.objects(ontology_node, DCTERMS.description)))
    has_version_iri = bool(ontology_node and list(schema_graph.objects(ontology_node, OWL.versionIRI)))
    has_version_info = bool(ontology_node and list(schema_graph.objects(ontology_node, OWL.versionInfo)))
    has_license = bool(ontology_node and list(schema_graph.objects(ontology_node, DCTERMS.license)))
    has_provenance = bool(ontology_node and list(schema_graph.objects(ontology_node, DCTERMS.source)))

    findable = sum(
        [
            25 if inspection["ontology_iri"] else 0,
            20 if has_version_iri else 0,
            20 if has_title and has_description else 0,
            20 if citation_ready else 0,
            15 if docs_index else 0,
        ]
    )
    accessible = sum([35 if schema_ttl and schema_jsonld else 0, 35 if docs_index else 0, 30 if w3id_ready else 0])
    interoperable = sum([40 if inspection["external_namespaces"] else 0, 35 if mappings_ready else 0, 25 if not validation["namespace_violations"] else 0])
    reusable = sum(
        [
            25 if has_license else 0,
            20 if has_provenance or citation_ready else 0,
            20 if inspection["definition_coverage"] >= 0.6 else 0,
            20 if has_version_info else 0,
            15 if examples_ready else 0,
        ]
    )

    dimensions = [
        {"acronym": "F", "dimension": "Findable", "score": findable},
        {"acronym": "A", "dimension": "Accessible", "score": accessible},
        {"acronym": "I", "dimension": "Interoperable", "score": interoperable},
        {"acronym": "R", "dimension": "Reusable", "score": reusable},
    ]
    overall = round(sum(item["score"] for item in dimensions) / len(dimensions), 1)
    blockers = validation["mapping_issues"] + validation["namespace_violations"]
    if validation["metadata_missing"]:
        blockers.extend(validation["metadata_missing"])
    if not validation["shacl_conforms"]:
        blockers.append("SHACL validation still reports unresolved constraints.")
    release_ready = overall >= 75 and not blockers
    oops_result = validation.get("oops_checks", {})
    foops_result = validation.get("foops_checks", {})
    transparency_checks = [
        {
            "label": "OOPS! ontology pitfall scan",
            "status": oops_result.get("status", "not_reported"),
            "details": oops_result.get("details", "No OOPS! result was recorded."),
            "counted_in_score": False,
            "service_url": oops_result.get("service_url", ""),
        },
        {
            "label": "FOOPS! FAIR assessment",
            "status": foops_result.get("status", "not_reported"),
            "details": foops_result.get("details", "No FOOPS! result was recorded."),
            "counted_in_score": False,
            "service_url": foops_result.get("service_url", ""),
            "catalogue_url": foops_result.get("catalogue_url", ""),
        },
    ]
    external_scores = {
        "foops": {
            "status": foops_result.get("status", "not_reported"),
            "overall_score": foops_result.get("overall_score"),
            "dimension_scores": foops_result.get("dimension_scores", []),
            "details": foops_result.get("details", "No FOOPS! result was recorded."),
            "service_url": foops_result.get("service_url", ""),
            "catalogue_url": foops_result.get("catalogue_url", ""),
            "mode": foops_result.get("mode", ""),
        },
        "oops": {
            "status": oops_result.get("status", "not_reported"),
            "pitfall_count": oops_result.get("pitfall_count"),
            "severity_counts": oops_result.get("severity_counts", {}),
            "details": oops_result.get("details", "No OOPS! result was recorded."),
            "service_url": oops_result.get("service_url", ""),
        },
    }
    return {
        "dimensions": dimensions,
        "overall": overall,
        "release_ready": release_ready,
        "blockers": blockers,
        "transparency_checks": transparency_checks,
        "external_scores": external_scores,
    }


def write_fair_reports(scores: dict[str, Any], root: Path) -> None:
    fair_lines = [
        "# FAIR Readiness Report",
        "",
        f"- Overall FAIR readiness score: **{scores['overall']} / 100**",
        f"- Release ready: **{scores['release_ready']}**",
        "",
        "## Dimension Scores",
        "",
    ]
    fair_lines.extend(f"- {item['acronym']} ({item['dimension']}): {item['score']} / 100" for item in scores["dimensions"])
    fair_lines.extend(["", "## External Transparency Hooks", ""])
    fair_lines.append("- OOPS! and FOOPS! are reported separately for transparency and are not added to the numeric F/A/I/R score.")
    fair_lines.extend(f"- {item['label']}: **{item['status']}**. {item['details']}" for item in scores.get("transparency_checks", []))
    foops = scores.get("external_scores", {}).get("foops", {})
    oops = scores.get("external_scores", {}).get("oops", {})
    fair_lines.extend(["", "## External Service Results", ""])
    if foops.get("overall_score") is not None:
        fair_lines.append(f"- FOOPS! overall score: **{foops['overall_score']} / 100**")
        for row in foops.get("dimension_scores", []):
            score = "not assessed" if row.get("score") is None else f"{row['score']} / 100"
            fair_lines.append(f"- FOOPS! {row['acronym']} ({row['dimension']}): {score}")
    else:
        fair_lines.append("- FOOPS! did not return a score in this run.")
    if oops.get("pitfall_count") is not None:
        fair_lines.append(f"- OOPS! pitfall count: **{oops['pitfall_count']}**")
        fair_lines.extend(f"- OOPS! {level}: {count}" for level, count in sorted(oops.get("severity_counts", {}).items()))
    else:
        fair_lines.append("- OOPS! did not return a pitfall count in this run.")
    fair_lines.extend(["", "## Blocking Issues", ""])
    if scores["blockers"]:
        fair_lines.extend(f"- {item}" for item in scores["blockers"])
    else:
        fair_lines.append("- No blocking issues detected.")
    write_text(root / "output" / "reports" / "fair_readiness_report.md", "\n".join(fair_lines) + "\n")

    release_lines = [
        "# Release Readiness Report",
        "",
        f"- Release ready: **{scores['release_ready']}**",
        f"- Overall readiness score: **{scores['overall']} / 100**",
        "",
        "## Criteria",
        "",
    ]
    release_lines.extend(f"- {item['acronym']} ({item['dimension']}): {item['score']} / 100" for item in scores["dimensions"])
    release_lines.extend(["", "## External Transparency Hooks", ""])
    release_lines.append("- OOPS! and FOOPS! are tracked separately from the numeric FAIR score so the base F/A/I/R calculation stays reproducible offline.")
    release_lines.extend(f"- {item['label']}: **{item['status']}**. {item['details']}" for item in scores.get("transparency_checks", []))
    release_lines.extend(["", "## External Service Results", ""])
    if foops.get("overall_score") is not None:
        release_lines.append(f"- FOOPS! overall score: **{foops['overall_score']} / 100**")
        for row in foops.get("dimension_scores", []):
            score = "not assessed" if row.get("score") is None else f"{row['score']} / 100"
            release_lines.append(f"- FOOPS! {row['acronym']} ({row['dimension']}): {score}")
    else:
        release_lines.append("- FOOPS! did not return a score in this run.")
    if oops.get("pitfall_count") is not None:
        release_lines.append(f"- OOPS! pitfall count: **{oops['pitfall_count']}**")
        release_lines.extend(f"- OOPS! {level}: {count}" for level, count in sorted(oops.get("severity_counts", {}).items()))
    else:
        release_lines.append("- OOPS! did not return a pitfall count in this run.")
    release_lines.extend(["", "## Required Follow-up", ""])
    if scores["blockers"]:
        release_lines.extend(f"- {item}" for item in scores["blockers"])
    else:
        release_lines.append("- None.")
    write_text(root / "output" / "reports" / "release_readiness_report.md", "\n".join(release_lines) + "\n")
