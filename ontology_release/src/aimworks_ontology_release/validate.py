from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDFS, SKOS

from .extract import extract_local_terms
from .inspect import find_ontology_node
from .utils import load_text, write_json, write_text


def _run_pyshacl(data_graph: Graph, shapes_dir: Path) -> tuple[bool, list[str]]:
    if importlib.util.find_spec("pyshacl") is None:
        return False, ["pySHACL is not installed; SHACL checks were skipped."]
    from pyshacl import validate as pyshacl_validate

    shapes_graph = Graph()
    for shape_file in shapes_dir.glob("*.ttl"):
        shapes_graph.parse(shape_file, format="turtle")
    conforms, _, report_text = pyshacl_validate(data_graph, shacl_graph=shapes_graph, inference="rdfs", serialize_report_graph=True)
    report_value = report_text.decode("utf-8") if isinstance(report_text, bytes) else str(report_text)
    report_lines = report_value.splitlines()[:20]
    return bool(conforms), report_lines


def validate_release(
    schema_graph: Graph,
    controlled_vocabulary_graph: Graph,
    alignments_graph: Graph,
    classifications: dict[str, Any],
    namespace_policy: dict[str, Any],
    root: Path,
) -> dict[str, Any]:
    data_graph = Graph()
    for graph in (schema_graph, controlled_vocabulary_graph):
        for triple in graph:
            data_graph.add(triple)
    ontology_node = find_ontology_node(schema_graph, namespace_policy)
    terms = extract_local_terms(data_graph, namespace_policy, classifications)
    missing_labels = [term.iri for term in terms if not list(data_graph.objects(URIRef(term.iri), RDFS.label))]
    missing_definitions = [term.iri for term in terms if not list(data_graph.objects(URIRef(term.iri), SKOS.definition)) and not list(data_graph.objects(URIRef(term.iri), RDFS.comment))]
    metadata_missing: list[str] = []
    if ontology_node is not None:
        required = [
            URIRef("http://purl.org/dc/terms/title"),
            URIRef("http://purl.org/dc/terms/description"),
            URIRef("http://purl.org/dc/terms/license"),
            OWL.versionIRI,
            OWL.versionInfo,
        ]
        metadata_missing = [str(predicate) for predicate in required if not list(schema_graph.objects(ontology_node, predicate))]
    else:
        metadata_missing = ["owl:Ontology header"]

    mapping_issues: list[str] = []
    for subject, predicate, _ in alignments_graph:
        if str(predicate) in {str(OWL.equivalentClass), str(RDFS.subClassOf)}:
            record = classifications.get(str(subject))
            if record and record.term_type != "class":
                mapping_issues.append(f"{subject} uses class mapping relation but is typed as {record.term_type}.")
        if str(predicate) in {str(OWL.equivalentProperty), str(RDFS.subPropertyOf)}:
            record = classifications.get(str(subject))
            if record and record.term_type not in {"object_property", "datatype_property", "annotation_property"}:
                mapping_issues.append(f"{subject} uses property mapping relation but is typed as {record.term_type}.")

    namespace_violations = [
        term.iri
        for term in terms
        if not term.iri.startswith(namespace_policy["term_namespace"]) and term.iri != namespace_policy["ontology_iri"]
    ]
    shacl_conforms, shacl_lines = _run_pyshacl(data_graph, root / "shapes")
    report = {
        "syntax_ok": True,
        "metadata_missing": metadata_missing,
        "missing_label_count": len(missing_labels),
        "missing_definition_count": len(missing_definitions),
        "mapping_issues": mapping_issues,
        "namespace_violations": namespace_violations,
        "shacl_conforms": shacl_conforms,
        "shacl_summary": shacl_lines,
        "overall_status": "pass" if not metadata_missing and not missing_labels and not mapping_issues and not namespace_violations and shacl_conforms else "warning",
    }
    return report


def write_validation_outputs(report: dict[str, Any], root: Path) -> None:
    write_json(root / "output" / "reports" / "validation_report.json", report)
    lines = [
        "# Validation Report",
        "",
        f"- RDF syntax sanity: **{'pass' if report['syntax_ok'] else 'fail'}**",
        f"- Overall status: **{report['overall_status']}**",
        f"- Missing metadata predicates: **{len(report['metadata_missing'])}**",
        f"- Missing labels: **{report['missing_label_count']}**",
        f"- Missing definitions/comments: **{report['missing_definition_count']}**",
        f"- Mapping issues: **{len(report['mapping_issues'])}**",
        f"- Namespace violations: **{len(report['namespace_violations'])}**",
        f"- SHACL conforms: **{report['shacl_conforms']}**",
        "",
        "## Details",
        "",
    ]
    if report["metadata_missing"]:
        lines.extend(f"- Missing metadata: {item}" for item in report["metadata_missing"])
    if report["mapping_issues"]:
        lines.extend(f"- Mapping issue: {item}" for item in report["mapping_issues"])
    if report["namespace_violations"]:
        lines.extend(f"- Namespace violation: {item}" for item in report["namespace_violations"])
    if report["shacl_summary"]:
        lines.append("")
        lines.append("## SHACL Summary")
        lines.append("")
        lines.extend(f"- {item}" for item in report["shacl_summary"])
    write_text(root / "output" / "reports" / "validation_report.md", "\n".join(lines) + "\n")
