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
        {"dimension": "Findable", "score": findable},
        {"dimension": "Accessible", "score": accessible},
        {"dimension": "Interoperable", "score": interoperable},
        {"dimension": "Reusable", "score": reusable},
    ]
    overall = round(sum(item["score"] for item in dimensions) / len(dimensions), 1)
    blockers = validation["mapping_issues"] + validation["namespace_violations"]
    if validation["metadata_missing"]:
        blockers.extend(validation["metadata_missing"])
    if not validation["shacl_conforms"]:
        blockers.append("SHACL validation still reports unresolved constraints.")
    release_ready = overall >= 75 and not blockers
    return {"dimensions": dimensions, "overall": overall, "release_ready": release_ready, "blockers": blockers}


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
    fair_lines.extend(f"- {item['dimension']}: {item['score']} / 100" for item in scores["dimensions"])
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
    release_lines.extend(f"- {item['dimension']}: {item['score']} / 100" for item in scores["dimensions"])
    release_lines.extend(["", "## Required Follow-up", ""])
    if scores["blockers"]:
        release_lines.extend(f"- {item}" for item in scores["blockers"])
    else:
        release_lines.append("- None.")
    write_text(root / "output" / "reports" / "release_readiness_report.md", "\n".join(release_lines) + "\n")
