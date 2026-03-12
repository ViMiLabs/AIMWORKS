from __future__ import annotations

from collections import Counter
from typing import Any

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS

from .classify import ResourceClassification, classify_resources
from .extract import collect_namespace_rows, extract_local_terms
from .utils import as_uri_text, is_local_iri, write_json, write_text


REQUIRED_METADATA = [
    "http://purl.org/dc/terms/title",
    "http://purl.org/dc/terms/description",
    "http://purl.org/dc/terms/license",
    "http://www.w3.org/2002/07/owl#versionIRI",
    "http://www.w3.org/2002/07/owl#versionInfo",
]


def find_ontology_node(graph: Graph, namespace_policy: dict[str, Any]) -> URIRef | None:
    for subject in graph.subjects(RDF.type, OWL.Ontology):
        if isinstance(subject, URIRef):
            return subject
    ontology_iri = namespace_policy.get("ontology_iri")
    if ontology_iri and (URIRef(ontology_iri), None, None) in graph:
        return URIRef(ontology_iri)
    return None


def inspect_graph(
    graph: Graph,
    namespace_policy: dict[str, Any],
    rules: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, ResourceClassification]]:
    classifications = classify_resources(graph, namespace_policy, rules)
    ontology_node = find_ontology_node(graph, namespace_policy)
    local_schema_terms = extract_local_terms(graph, namespace_policy, classifications)
    category_counts = Counter(record.category for record in classifications.values())
    local_term_count = sum(1 for record in classifications.values() if record.local)

    label_count = 0
    definition_count = 0
    for term in local_schema_terms:
        subject = URIRef(term.iri)
        if list(graph.objects(subject, RDFS.label)) or list(graph.objects(subject, SKOS.prefLabel)):
            label_count += 1
        if list(graph.objects(subject, RDFS.comment)) or list(graph.objects(subject, SKOS.definition)):
            definition_count += 1

    metadata_present = []
    metadata_missing = []
    imported_ontologies: list[str] = []
    if ontology_node is not None:
        for predicate in REQUIRED_METADATA:
            values = list(graph.objects(ontology_node, URIRef(predicate)))
            if values:
                metadata_present.append(predicate)
            else:
                metadata_missing.append(predicate)
        imported_ontologies = [as_uri_text(obj) for obj in graph.objects(ontology_node, OWL.imports)]
    else:
        metadata_missing = REQUIRED_METADATA.copy()

    blockers: list[str] = []
    fair_blockers: list[str] = []
    if ontology_node is None:
        blockers.append("No owl:Ontology header was found.")
    if metadata_missing:
        blockers.append(f"Missing ontology metadata predicates: {', '.join(predicate.rsplit('/', 1)[-1] for predicate in metadata_missing)}.")
    if local_schema_terms and label_count / len(local_schema_terms) < 0.85:
        blockers.append("Schema label coverage is below 85%.")
    if local_schema_terms and definition_count / len(local_schema_terms) < 0.60:
        fair_blockers.append("Schema definition or comment coverage is below 60%.")
    if not imported_ontologies:
        fair_blockers.append("No owl:imports declarations were found for reused external vocabularies.")
    if local_term_count == 0:
        blockers.append("No local ontology terms were detected inside the configured namespace.")

    report = {
        "ontology_iri": as_uri_text(ontology_node) or namespace_policy.get("ontology_iri", ""),
        "namespace_mode": namespace_policy.get("namespace_mode", "hash"),
        "triple_count": len(graph),
        "local_term_count": local_term_count,
        "category_counts": dict(category_counts),
        "schema_term_count": len(local_schema_terms),
        "label_coverage": round(label_count / len(local_schema_terms), 3) if local_schema_terms else 1.0,
        "definition_coverage": round(definition_count / len(local_schema_terms), 3) if local_schema_terms else 1.0,
        "metadata_present": metadata_present,
        "metadata_missing": metadata_missing,
        "imports": imported_ontologies,
        "namespace_rows": collect_namespace_rows(graph),
        "likely_release_blockers": blockers,
        "likely_fair_blockers": fair_blockers,
        "external_namespaces": sorted(
            {
                row["namespace"]
                for row in collect_namespace_rows(graph)
                if not row["namespace"].startswith(namespace_policy.get("term_namespace", ""))
                and row["namespace"] != namespace_policy.get("ontology_iri", "")
            }
        ),
    }
    return report, classifications


def write_inspection_reports(report: dict[str, Any], root: str | Any) -> None:
    root_path = root if hasattr(root, "joinpath") else None
    if root_path is None:
        raise TypeError("root must be a pathlib.Path-like object")
    md_lines = [
        "# Inspection Report",
        "",
        f"- Ontology IRI: `{report['ontology_iri']}`",
        f"- Namespace mode: `{report['namespace_mode']}`",
        f"- Triples inspected: **{report['triple_count']}**",
        f"- Local terms detected: **{report['local_term_count']}**",
        f"- Schema terms detected: **{report['schema_term_count']}**",
        f"- Label coverage: **{report['label_coverage']:.1%}**",
        f"- Definition/comment coverage: **{report['definition_coverage']:.1%}**",
        "",
        "## Classification Counts",
        "",
    ]
    for key, value in sorted(report["category_counts"].items()):
        md_lines.append(f"- {key}: {value}")
    md_lines.extend(["", "## Imports", ""])
    if report["imports"]:
        md_lines.extend(f"- {item}" for item in report["imports"])
    else:
        md_lines.append("- None found")
    md_lines.extend(["", "## Likely Release Blockers", ""])
    if report["likely_release_blockers"]:
        md_lines.extend(f"- {item}" for item in report["likely_release_blockers"])
    else:
        md_lines.append("- None detected")
    md_lines.extend(["", "## Likely FAIR Blockers", ""])
    if report["likely_fair_blockers"]:
        md_lines.extend(f"- {item}" for item in report["likely_fair_blockers"])
    else:
        md_lines.append("- None detected")
    write_text(root_path / "output" / "reports" / "inspection_report.md", "\n".join(md_lines) + "\n")
    write_json(root_path / "output" / "reports" / "inspection_report.json", report)
