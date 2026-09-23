from __future__ import annotations

"""Build the H2KG-aligned DECODE ontology and occurrence graph.

The exported graph deliberately combines a small DECODE TBox with the complete
workflow ABox. H2KG remains an imported, independently maintained ontology.
"""

import hashlib
import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import quote

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, OWL, PROV, RDF, RDFS, SKOS, XSD

from .utils import dump_json, ensure_dir, try_load_yaml


ONTOLOGY_IRI = URIRef("https://w3id.org/h2kg/decode/ontology")
DECODE = Namespace("https://w3id.org/h2kg/decode/ontology#")
DECODE_WORKFLOW = Namespace("https://w3id.org/h2kg/decode/workflow/")
H2KG = Namespace("https://w3id.org/h2kg/hydrogen-ontology#")
H2KG_ONTOLOGY = URIRef("https://w3id.org/h2kg/hydrogen-ontology")

RIGHTS_NOTICE = (
    "License pending confirmation by DECODE governance; no open reuse license "
    "is asserted for this release."
)

SUPPORT_CLASSES = {
    "WorkflowDefinition": PROV.Plan,
    "SourceOccurrence": PROV.Entity,
    "SourceEdge": PROV.Entity,
    "SemanticProjection": PROV.Entity,
    "WorkflowDependency": PROV.Entity,
}

OBJECT_PROPERTIES = {
    "hasSourceOccurrence": (DECODE.WorkflowDefinition, DECODE.SourceOccurrence),
    "hasSourceEdge": (DECODE.WorkflowDefinition, DECODE.SourceEdge),
    "hasSemanticProjection": (DECODE.WorkflowDefinition, DECODE.SemanticProjection),
    "sourceOccurrence": (DECODE.SourceEdge, DECODE.SourceOccurrence),
    "targetOccurrence": (DECODE.SourceEdge, DECODE.SourceOccurrence),
    "mappedToAnchor": (DECODE.SourceOccurrence, OWL.Class),
    "semanticSource": (DECODE.SemanticProjection, RDFS.Resource),
    "semanticTarget": (DECODE.SemanticProjection, RDFS.Resource),
    "semanticPredicate": (DECODE.SemanticProjection, RDF.Property),
    "upstreamWorkflow": (DECODE.WorkflowDependency, DECODE.WorkflowDefinition),
    "downstreamWorkflow": (DECODE.WorkflowDependency, DECODE.WorkflowDefinition),
    "handoffAnchor": (DECODE.WorkflowDependency, OWL.Class),
}

DATATYPE_PROPERTIES = {
    "sourceNodeId": XSD.string,
    "sourceDependencyId": XSD.string,
    "sourceWorkflowId": XSD.string,
    "sourceKind": XSD.string,
    "nativeCategory": XSD.string,
    "projectionOutcome": XSD.string,
    "projectionPattern": XSD.string,
    "publicationStatus": XSD.string,
    "definitionStatus": XSD.string,
    "reviewStatus": XSD.string,
    "confidence": XSD.string,
    "reciprocityState": XSD.string,
    "semanticDependencyAsserted": XSD.boolean,
}


def build_decode_ontology(
    graph_data: dict[str, Any],
    concept_registry: dict[str, Any],
    target_dir: str | Path,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    """Serialize a merged DECODE vocabulary and workflow graph as TTL/JSON-LD."""
    target = ensure_dir(Path(target_dir))
    resolved_config_path = Path(config_path) if config_path else Path("decode_ontology.yaml")
    config = try_load_yaml(
        resolved_config_path,
        {"ontology": {}, "definition_overrides": {}},
    )
    definition_candidates = _load_definition_candidates(config, resolved_config_path)
    rdf_graph = _new_graph()
    _add_header(rdf_graph, graph_data, config)
    _declare_support_vocabulary(rdf_graph)

    concepts_by_anchor: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for concept in concept_registry.get("concepts", []):
        anchor = str(concept.get("anchor_iri", ""))
        if anchor:
            concepts_by_anchor[anchor].append(concept)

    _add_decode_classes(
        rdf_graph, graph_data, concepts_by_anchor, config, definition_candidates
    )
    workflow_iris = _add_workflows(rdf_graph, graph_data)
    resource_iris = _add_occurrences(rdf_graph, graph_data, workflow_iris)
    _add_source_edges(rdf_graph, graph_data, workflow_iris, resource_iris)
    _add_semantic_projections(rdf_graph, graph_data, workflow_iris, resource_iris)
    _add_workflow_dependencies(rdf_graph, graph_data, workflow_iris, resource_iris)

    ttl_path = target / "decode-h2kg-aligned-ontology.ttl"
    jsonld_path = target / "decode-h2kg-aligned-ontology.jsonld"
    rdf_graph.serialize(destination=ttl_path, format="turtle")
    context = {
        "decode": str(DECODE),
        "decode-workflow": str(DECODE_WORKFLOW),
        "h2kg": str(H2KG),
        "dcterms": str(DCTERMS),
        "owl": str(OWL),
        "prov": str(PROV),
        "rdf": str(RDF),
        "rdfs": str(RDFS),
        "skos": str(SKOS),
        "xsd": str(XSD),
    }
    rdf_graph.serialize(
        destination=jsonld_path,
        format="json-ld",
        context=context,
        auto_compact=True,
        indent=2,
    )

    validation = validate_decode_ontology(
        rdf_graph,
        graph_data,
        ttl_path,
        jsonld_path,
    )
    definition_registry = _definition_registry(
        graph_data, concepts_by_anchor, config, definition_candidates
    )
    definition_registry_path = dump_json(
        target / "decode_ontology_definition_registry.json", definition_registry
    )
    validation["definition_candidate_source_record_count"] = int(
        config.get("_definition_candidate_registry_meta", {}).get(
            "source_record_count", len(definition_candidates)
        )
    )
    validation["definition_candidate_unique_label_count"] = len(definition_candidates)
    validation["definition_override_count"] = len(config.get("definition_overrides", {}))
    validation["definition_registry_counts"] = definition_registry["counts"]
    validation_path = dump_json(target / "decode_ontology_validation_report.json", validation)
    if validation["status"] != "passed":
        raise ValueError(
            "DECODE ontology validation failed: "
            + "; ".join(validation.get("errors", []))
        )
    return {
        "status": "generated",
        "ontology_iri": str(ONTOLOGY_IRI),
        "workflow_count": len(graph_data.get("workflows", [])),
        "source_occurrence_count": len(graph_data.get("nodes", [])),
        "source_edge_count": len(graph_data.get("source_edges", [])),
        "workflow_dependency_count": len(graph_data.get("workflow_dependencies", [])),
        "active_decode_class_count": validation["active_decode_class_count"],
        "triple_count": len(rdf_graph),
        "generated_files": [
            str(ttl_path),
            str(jsonld_path),
            str(validation_path),
            str(definition_registry_path),
        ],
    }


def build_decode_ontology_from_release(
    decode_dir: str | Path,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build the merged ontology from an already generated DECODE release."""
    decode_dir = Path(decode_dir)
    graph_data = json.loads(
        (decode_dir / "decode_federated_graph.json").read_text(encoding="utf-8")
    )
    registry = json.loads(
        (decode_dir / "decode_concept_registry.json").read_text(encoding="utf-8")
    )
    return build_decode_ontology(graph_data, registry, decode_dir, config_path)


def _new_graph() -> Graph:
    graph = Graph()
    for prefix, namespace in {
        "decode": DECODE,
        "decode-workflow": DECODE_WORKFLOW,
        "h2kg": H2KG,
        "dcterms": DCTERMS,
        "owl": OWL,
        "prov": PROV,
        "rdf": RDF,
        "rdfs": RDFS,
        "skos": SKOS,
        "xsd": XSD,
    }.items():
        graph.bind(prefix, namespace)
    return graph


def _add_header(graph: Graph, graph_data: dict[str, Any], config: dict[str, Any]) -> None:
    metadata = config.get("ontology", {})
    version = str(metadata.get("version", date.today().isoformat()))
    issued = str(metadata.get("issued", date.today().isoformat()))
    version_iri = URIRef(f"{ONTOLOGY_IRI}/releases/{version}")
    graph.add((ONTOLOGY_IRI, RDF.type, OWL.Ontology))
    graph.add((ONTOLOGY_IRI, OWL.imports, H2KG_ONTOLOGY))
    graph.add((ONTOLOGY_IRI, OWL.versionIRI, version_iri))
    graph.add((ONTOLOGY_IRI, OWL.versionInfo, Literal(version)))
    graph.add((ONTOLOGY_IRI, DCTERMS.title, Literal("DECODE H2KG-Aligned Workflow Ontology", lang="en")))
    graph.add(
        (
            ONTOLOGY_IRI,
            DCTERMS.description,
            Literal(
                "An H2KG-aligned ontology and provenance-preserving occurrence graph for "
                "DECODE hydrogen-technology workflows.",
                lang="en",
            ),
        )
    )
    graph.add((ONTOLOGY_IRI, DCTERMS.issued, Literal(issued, datatype=XSD.date)))
    graph.add((ONTOLOGY_IRI, DCTERMS.rights, Literal(RIGHTS_NOTICE, lang="en")))
    graph.add((ONTOLOGY_IRI, DCTERMS.creator, Literal("DECODE consortium")))
    graph.add((ONTOLOGY_IRI, DCTERMS.creator, Literal("H2KG development team")))
    graph.add((ONTOLOGY_IRI, DECODE.definitionStatus, Literal("expert-draft")))
    seed = str(metadata.get("definition_seed_sha256", "")).strip()
    if seed:
        graph.add((ONTOLOGY_IRI, DECODE.definitionSeedSha256, Literal(seed)))
    graph.add(
        (
            ONTOLOGY_IRI,
            DECODE.sourceWorkflowCount,
            Literal(len(graph_data.get("workflows", [])), datatype=XSD.integer),
        )
    )


def _declare_support_vocabulary(graph: Graph) -> None:
    labels = {
        "WorkflowDefinition": "workflow definition",
        "SourceOccurrence": "source occurrence",
        "SourceEdge": "source edge",
        "SemanticProjection": "semantic projection",
        "WorkflowDependency": "workflow dependency",
    }
    for name, parent in SUPPORT_CLASSES.items():
        iri = DECODE[name]
        graph.add((iri, RDF.type, OWL.Class))
        graph.add((iri, RDFS.label, Literal(labels[name], lang="en")))
        graph.add((iri, RDFS.subClassOf, parent))
        graph.add((iri, RDFS.isDefinedBy, ONTOLOGY_IRI))
    for name, (domain, range_) in OBJECT_PROPERTIES.items():
        iri = DECODE[name]
        graph.add((iri, RDF.type, OWL.ObjectProperty))
        graph.add((iri, RDFS.label, Literal(_humanize(name), lang="en")))
        graph.add((iri, RDFS.domain, domain))
        graph.add((iri, RDFS.range, range_))
        graph.add((iri, RDFS.isDefinedBy, ONTOLOGY_IRI))
    for name, range_ in DATATYPE_PROPERTIES.items():
        iri = DECODE[name]
        graph.add((iri, RDF.type, OWL.DatatypeProperty))
        graph.add((iri, RDFS.label, Literal(_humanize(name), lang="en")))
        graph.add((iri, RDFS.range, range_))
        graph.add((iri, RDFS.isDefinedBy, ONTOLOGY_IRI))
    for name in ("definitionSeedSha256", "sourceWorkflowCount"):
        graph.add((DECODE[name], RDF.type, OWL.AnnotationProperty))
        graph.add((DECODE[name], RDFS.isDefinedBy, ONTOLOGY_IRI))


def _add_decode_classes(
    graph: Graph,
    graph_data: dict[str, Any],
    concepts_by_anchor: dict[str, list[dict[str, Any]]],
    config: dict[str, Any],
    definition_candidates: dict[str, dict[str, Any]],
) -> None:
    for anchor in graph_data.get("anchors", []):
        if anchor.get("state") != "reviewed_decode":
            continue
        iri = URIRef(anchor["id"])
        label = str(anchor.get("label", "DECODE concept"))
        role_iri = str(anchor.get("canonical_role_iri", "")).strip()
        graph.add((iri, RDF.type, OWL.Class))
        graph.add((iri, SKOS.prefLabel, Literal(label, lang="en")))
        graph.add((iri, RDFS.label, Literal(label, lang="en")))
        if role_iri:
            graph.add((iri, RDFS.subClassOf, URIRef(role_iri)))
        graph.add((iri, RDFS.isDefinedBy, ONTOLOGY_IRI))
        graph.add((iri, DECODE.definitionStatus, Literal("expert-draft")))
        concepts = concepts_by_anchor.get(anchor["id"], [])
        definition = _definition_for_anchor(anchor, concepts, config, definition_candidates)
        graph.add((iri, SKOS.definition, Literal(definition, lang="en")))
        for concept in concepts:
            source_label = str(concept.get("source_label", "")).strip()
            if source_label and source_label.casefold() != label.casefold():
                graph.add((iri, SKOS.altLabel, Literal(source_label, lang="en")))
            for workflow_id in concept.get("workflow_ids", []):
                graph.add((iri, DCTERMS.source, URIRef(f"{DECODE_WORKFLOW}{workflow_id}")))

    for alias in graph_data.get("deprecated_anchor_aliases", []):
        old_iri = URIRef(alias["deprecated_iri"])
        replacement = URIRef(alias["canonical_iri"])
        graph.add((old_iri, RDF.type, OWL.Class))
        graph.add((old_iri, OWL.deprecated, Literal(True, datatype=XSD.boolean)))
        graph.add((old_iri, DCTERMS.isReplacedBy, replacement))
        graph.add((old_iri, SKOS.prefLabel, Literal(alias.get("label", "deprecated DECODE anchor"), lang="en")))
        if alias.get("relation") == "equivalentClass":
            graph.add((old_iri, OWL.equivalentClass, replacement))
        else:
            graph.add((old_iri, SKOS.closeMatch, replacement))


def _add_workflows(graph: Graph, graph_data: dict[str, Any]) -> dict[str, URIRef]:
    workflow_iris: dict[str, URIRef] = {}
    for workflow in graph_data.get("workflows", []):
        iri = URIRef(workflow["iri"])
        workflow_iris[workflow["id"]] = iri
        graph.add((iri, RDF.type, DECODE.WorkflowDefinition))
        graph.add((iri, RDF.type, PROV.Plan))
        graph.add((iri, RDFS.label, Literal(workflow["title"], lang="en")))
        graph.add((iri, DCTERMS.identifier, Literal(workflow["id"])))
        graph.add((iri, DECODE.sourceWorkflowId, Literal(workflow["id"])))
        graph.add((iri, DECODE.sourceKind, Literal(workflow.get("source_kind", "source_graphml"))))
        graph.add((iri, DCTERMS.description, Literal(_workflow_definition(workflow), lang="en")))
        source_hash = str(workflow.get("source_sha256", "")).strip()
        if source_hash:
            graph.add((iri, DCTERMS.provenance, Literal(f"Source SHA-256: {source_hash}")))
        for title in workflow.get("alternate_titles", []):
            if str(title).strip():
                graph.add((iri, SKOS.altLabel, Literal(str(title).strip(), lang="en")))
    return workflow_iris


def _add_occurrences(
    graph: Graph,
    graph_data: dict[str, Any],
    workflow_iris: dict[str, URIRef],
) -> dict[str, URIRef]:
    resource_iris: dict[str, URIRef] = {}
    for node in graph_data.get("nodes", []):
        iri = URIRef(node["iri"])
        resource_iris[node["id"]] = iri
        graph.add((iri, RDF.type, DECODE.SourceOccurrence))
        anchor = str(node.get("anchor_id", "")).strip()
        if anchor:
            graph.add((iri, RDF.type, URIRef(anchor)))
            graph.add((iri, DECODE.mappedToAnchor, URIRef(anchor)))
        graph.add((iri, RDFS.label, Literal(str(node.get("label", node["source_id"])), lang="en")))
        graph.add((iri, DECODE.sourceNodeId, Literal(str(node.get("source_id", "")))))
        graph.add((iri, DECODE.sourceWorkflowId, Literal(str(node.get("workflow_id", "")))))
        graph.add((iri, DECODE.nativeCategory, Literal(str(node.get("native_category", "")))))
        workflow = workflow_iris.get(str(node.get("workflow_id", "")))
        if workflow:
            graph.add((workflow, DECODE.hasSourceOccurrence, iri))
            graph.add((iri, PROV.hadPrimarySource, workflow))
    for node in graph_data.get("projection_nodes", []):
        iri = URIRef(node["iri"])
        resource_iris[node["id"]] = iri
        graph.add((iri, RDF.type, URIRef(node.get("rdf_type", str(H2KG.DataPoint)))))
        graph.add((iri, RDFS.label, Literal(node.get("label", "derived value proxy"), lang="en")))
        source_occurrence = resource_iris.get(str(node.get("source_occurrence_id", "")))
        if source_occurrence:
            graph.add((iri, PROV.wasDerivedFrom, source_occurrence))
    return resource_iris


def _add_source_edges(
    graph: Graph,
    graph_data: dict[str, Any],
    workflow_iris: dict[str, URIRef],
    resource_iris: dict[str, URIRef],
) -> None:
    for edge in graph_data.get("source_edges", []):
        edge_iri = _record_iri("source-edge", edge["id"])
        source = resource_iris[edge["source"]]
        target = resource_iris[edge["target"]]
        workflow = workflow_iris[edge["workflow_id"]]
        graph.add((edge_iri, RDF.type, DECODE.SourceEdge))
        graph.add((edge_iri, DECODE.sourceOccurrence, source))
        graph.add((edge_iri, DECODE.targetOccurrence, target))
        graph.add((edge_iri, DECODE.sourceDependencyId, Literal(edge["id"])))
        graph.add((edge_iri, DECODE.sourceWorkflowId, Literal(edge["workflow_id"])))
        graph.add((edge_iri, DECODE.sourceKind, Literal(edge.get("source_kind", "source_graphml"))))
        graph.add((workflow, DECODE.hasSourceEdge, edge_iri))
        graph.add((edge_iri, PROV.hadPrimarySource, workflow))


def _add_semantic_projections(
    graph: Graph,
    graph_data: dict[str, Any],
    workflow_iris: dict[str, URIRef],
    resource_iris: dict[str, URIRef],
) -> None:
    for edge in graph_data.get("semantic_edges", []):
        source = _resource(edge["source"], resource_iris)
        target = _resource(edge["target"], resource_iris)
        predicate = URIRef(edge["predicate"])
        projection = _record_iri("semantic-projection", edge["id"])
        graph.add((source, predicate, target))
        graph.add((projection, RDF.type, DECODE.SemanticProjection))
        graph.add((projection, DECODE.semanticSource, source))
        graph.add((projection, DECODE.semanticTarget, target))
        graph.add((projection, DECODE.semanticPredicate, predicate))
        graph.add((projection, DECODE.sourceDependencyId, Literal(edge["source_dependency_id"])))
        graph.add((projection, DECODE.projectionOutcome, Literal(edge.get("projection_outcome", ""))))
        graph.add((projection, DECODE.projectionPattern, Literal(edge.get("projection_pattern", ""))))
        graph.add((projection, DECODE.confidence, Literal(edge.get("confidence", ""))))
        graph.add((projection, DECODE.reviewStatus, Literal(edge.get("review_status", ""))))
        workflow = workflow_iris.get(edge.get("workflow_id", ""))
        if workflow:
            graph.add((workflow, DECODE.hasSemanticProjection, projection))


def _add_workflow_dependencies(
    graph: Graph,
    graph_data: dict[str, Any],
    workflow_iris: dict[str, URIRef],
    resource_iris: dict[str, URIRef],
) -> None:
    for row in graph_data.get("workflow_dependencies", []):
        dependency = _record_iri("workflow-dependency", row["id"])
        upstream = workflow_iris.get(str(row.get("upstream_workflow_id", "")))
        downstream = workflow_iris.get(str(row.get("downstream_workflow_id", "")))
        graph.add((dependency, RDF.type, DECODE.WorkflowDependency))
        graph.add((dependency, DCTERMS.identifier, Literal(row["id"])))
        graph.add((dependency, DECODE.publicationStatus, Literal(row.get("publication_status", ""))))
        graph.add((dependency, DECODE.reciprocityState, Literal(row.get("reciprocity_state", ""))))
        graph.add((dependency, DCTERMS.description, Literal(row.get("review_rationale", ""), lang="en")))
        if upstream:
            graph.add((dependency, DECODE.upstreamWorkflow, upstream))
        if downstream:
            graph.add((dependency, DECODE.downstreamWorkflow, downstream))
        for anchor in row.get("handoff_anchor_iris", []):
            graph.add((dependency, DECODE.handoffAnchor, URIRef(anchor)))
        source_occurrence = resource_iris.get(str(row.get("source", "")))
        target_occurrence = resource_iris.get(str(row.get("target", "")))
        if source_occurrence:
            graph.add((dependency, DECODE.sourceOccurrence, source_occurrence))
        if target_occurrence:
            graph.add((dependency, DECODE.targetOccurrence, target_occurrence))
        if row.get("publication_status") != "audit_only" and upstream and downstream:
            graph.add((downstream, PROV.wasInformedBy, upstream))
            graph.add((dependency, DECODE.semanticDependencyAsserted, Literal(True, datatype=XSD.boolean)))
        else:
            graph.add((dependency, DECODE.semanticDependencyAsserted, Literal(False, datatype=XSD.boolean)))


def validate_decode_ontology(
    graph: Graph,
    graph_data: dict[str, Any],
    ttl_path: Path,
    jsonld_path: Path,
) -> dict[str, Any]:
    ttl_graph = Graph().parse(ttl_path, format="turtle")
    jsonld_graph = Graph().parse(jsonld_path, format="json-ld")
    errors: list[str] = []
    expected = {
        "workflow_count": len(graph_data.get("workflows", [])),
        "source_occurrence_count": len(graph_data.get("nodes", [])),
        "source_edge_count": len(graph_data.get("source_edges", [])),
        "workflow_dependency_count": len(graph_data.get("workflow_dependencies", [])),
    }
    actual = {
        "workflow_count": len(set(graph.subjects(RDF.type, DECODE.WorkflowDefinition))),
        "source_occurrence_count": len(set(graph.subjects(RDF.type, DECODE.SourceOccurrence))),
        "source_edge_count": len(set(graph.subjects(RDF.type, DECODE.SourceEdge))),
        "workflow_dependency_count": len(set(graph.subjects(RDF.type, DECODE.WorkflowDependency))),
    }
    for key, value in expected.items():
        if actual[key] != value:
            errors.append(f"{key}: expected {value}, found {actual[key]}")
    if set(ttl_graph) != set(jsonld_graph):
        errors.append("Turtle and JSON-LD triple sets differ")
    if (ONTOLOGY_IRI, OWL.imports, H2KG_ONTOLOGY) not in graph:
        errors.append("H2KG owl:imports statement is missing")
    if any(graph.objects(ONTOLOGY_IRI, DCTERMS.license)):
        errors.append("A license was asserted although DECODE licensing is pending")
    if not any(graph.objects(ONTOLOGY_IRI, DCTERMS.rights)):
        errors.append("Pending-license rights notice is missing")
    audit_only = {
        row["id"] for row in graph_data.get("workflow_dependencies", [])
        if row.get("publication_status") == "audit_only"
    }
    dependency_assertion_errors = []
    for row in graph_data.get("workflow_dependencies", []):
        if row["id"] not in audit_only:
            continue
        dependency = _record_iri("workflow-dependency", row["id"])
        if (dependency, DECODE.semanticDependencyAsserted, Literal(True, datatype=XSD.boolean)) in graph:
            dependency_assertion_errors.append(row["id"])
    if dependency_assertion_errors:
        errors.append("Audit-only dependencies produced prov:wasInformedBy assertions")
    active_classes = {
        URIRef(anchor["id"]) for anchor in graph_data.get("anchors", [])
        if anchor.get("state") == "reviewed_decode"
    }
    missing_definitions = [str(iri) for iri in active_classes if not any(graph.objects(iri, SKOS.definition))]
    placeholder_definitions = [
        str(iri) for iri in active_classes
        for definition in graph.objects(iri, SKOS.definition)
        if "concept denoted" in str(definition).casefold()
    ]
    if missing_definitions:
        errors.append(f"{len(missing_definitions)} active DECODE classes lack definitions")
    if placeholder_definitions:
        errors.append(f"{len(placeholder_definitions)} active DECODE classes use placeholder definitions")
    return {
        "status": "passed" if not errors else "failed",
        "ontology_iri": str(ONTOLOGY_IRI),
        "expected": expected,
        "actual": actual,
        "active_decode_class_count": len(active_classes),
        "deprecated_anchor_count": len(graph_data.get("deprecated_anchor_aliases", [])),
        "semantic_projection_count": len(graph_data.get("semantic_edges", [])),
        "published_workflow_dependency_count": sum(
            row.get("publication_status") != "audit_only"
            for row in graph_data.get("workflow_dependencies", [])
        ),
        "audit_only_workflow_dependency_count": len(audit_only),
        "ttl_triple_count": len(ttl_graph),
        "jsonld_triple_count": len(jsonld_graph),
        "equivalent_serializations": set(ttl_graph) == set(jsonld_graph),
        "missing_definition_iris": missing_definitions,
        "placeholder_definition_iris": placeholder_definitions,
        "audit_only_dependency_assertion_errors": dependency_assertion_errors,
        "errors": errors,
    }


def _definition_registry(
    graph_data: dict[str, Any],
    concepts_by_anchor: dict[str, list[dict[str, Any]]],
    config: dict[str, Any],
    definition_candidates: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    rows = []
    for anchor in graph_data.get("anchors", []):
        if anchor.get("state") != "reviewed_decode":
            continue
        concepts = concepts_by_anchor.get(anchor["id"], [])
        candidate = definition_candidates.get(_normal(str(anchor.get("label", ""))))
        rows.append(
            {
                "anchor_iri": anchor["id"],
                "preferred_label": anchor.get("label", ""),
                "semantic_role": anchor.get("semantic_role", ""),
                "canonical_role_iri": anchor.get("canonical_role_iri", ""),
                "definition": _definition_for_anchor(
                    anchor, concepts, config, definition_candidates
                ),
                "definition_status": "expert-draft",
                "candidate_definition_status": (
                    candidate.get("candidate_status", "")
                    if candidate
                    else "not-in-supplied-draft"
                ),
                "candidate_supplied_role": candidate.get("supplied_role", "") if candidate else "",
                "candidate_role_compatible": (
                    _normal(str(candidate.get("supplied_role", "")))
                    == _normal(str(anchor.get("semantic_role", "")))
                    if candidate
                    else None
                ),
                "candidate_definition": candidate.get("candidate_definition", "") if candidate else "",
                "workflow_ids": sorted({wid for concept in concepts for wid in concept.get("workflow_ids", [])}),
                "source_labels": sorted({concept.get("source_label", "") for concept in concepts}),
            }
        )
    return {
        "schema_version": "1.0",
        "generated_on": date.today().isoformat(),
        "ontology_iri": str(ONTOLOGY_IRI),
        "definition_status": "expert-draft",
        "definition_seed_sha256": config.get("ontology", {}).get("definition_seed_sha256", ""),
        "counts": {
            "active_decode_class_count": len(rows),
            "classes_with_supplied_candidate": sum(
                row["candidate_definition_status"] != "not-in-supplied-draft" for row in rows
            ),
            "classes_without_supplied_candidate": sum(
                row["candidate_definition_status"] == "not-in-supplied-draft" for row in rows
            ),
            "candidate_role_conflict_count": sum(
                row["candidate_role_compatible"] is False for row in rows
            ),
        },
        "definitions": rows,
    }


def _definition_for_anchor(
    anchor: dict[str, Any],
    concepts: list[dict[str, Any]],
    config: dict[str, Any],
    definition_candidates: dict[str, dict[str, Any]],
) -> str:
    label = str(anchor.get("label", "DECODE concept")).strip()
    overrides = config.get("definition_overrides", {})
    override = overrides.get(label) or overrides.get(_normal(label))
    if override:
        return str(override).strip()
    role = str(anchor.get("semantic_role", "Metadata"))
    context = []
    candidate = definition_candidates.get(_normal(label))
    if candidate and candidate.get("source_context"):
        context.append(str(candidate["source_context"]))
    for concept in concepts:
        context.extend(concept.get("neighbor_context", []))
    return _expert_definition(label, role, context)


def _load_definition_candidates(
    config: dict[str, Any],
    config_path: Path,
) -> dict[str, dict[str, Any]]:
    """Load supplied definition candidates without trusting their proposed roles."""
    configured = str(config.get("definition_candidate_registry", "")).strip()
    if not configured:
        return {}
    path = Path(configured)
    if not path.is_absolute():
        path = config_path.parent / path
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    expected_hash = str(config.get("ontology", {}).get("definition_seed_sha256", "")).strip()
    actual_hash = str(payload.get("source_sha256", "")).strip()
    if expected_hash and actual_hash != expected_hash:
        raise ValueError(
            "DECODE definition candidate registry does not match the configured source fingerprint"
        )
    config["_definition_candidate_registry_meta"] = {
        "source_record_count": int(payload.get("source_record_count", 0)),
        "source_sha256": actual_hash,
    }
    return {
        _normal(str(entry.get("label", ""))): entry
        for entry in payload.get("entries", [])
        if str(entry.get("label", "")).strip()
    }


def _expert_definition(label: str, role: str, context: list[str]) -> str:
    subject = _clean_definition_subject(label)
    lower = subject[:1].lower() + subject[1:] if subject else "the represented concept"
    if role == "Measurement":
        if re.search(r"\b(test|testing|measurement|microscop|spectroscop|tomograph|porosimetr|adsorption|eis|xps|xas|ftir|saxs|waxs|edx)\b", label, re.I):
            return f"A measurement procedure that applies {lower} to acquire or derive observations about hydrogen-electrochemical materials, components, or operating cells."
        return f"A measurement procedure used in DECODE workflows to characterize {lower} under specified experimental conditions."
    if role == "Manufacturing":
        return f"A manufacturing or specimen-preparation process that performs {lower} to produce or condition a material, electrode, membrane-electrode assembly, or test specimen."
    if role == "Process":
        if re.search(r"\b(model|simulation|dft|molecular dynamics|force field)\b", label, re.I):
            return f"A computational process that represents {lower} to calculate, fit, or predict behavior relevant to hydrogen-electrochemical systems."
        if re.search(r"\b(analysis|extraction|segmentation|reconstruction|fitting|calculation)\b", label, re.I):
            return f"A data-transformation or analysis process that performs {lower} to derive structured data or scientific properties from workflow inputs."
        return f"A workflow process that performs {lower} as part of material preparation, data transformation, analysis, or model execution."
    if role == "Matter":
        return f"A material entity, specimen, component, or assembly characterized as {lower} and used or produced in a hydrogen-technology workflow."
    if role == "Instrument":
        return f"An instrument, apparatus, or experimental platform configured for {lower} in a hydrogen-technology workflow."
    if role == "Parameter":
        return f"A specified input or operating parameter representing {lower}, used to configure, constrain, or report a process, measurement, or computational model."
    if role == "Property":
        return f"A measurable, calculated, or derived property representing {lower} for a material, component, interface, or electrochemical system."
    if role == "Data":
        if re.search(r"\b(curve|distribution|profile|map|image|spectrum|spectra|dataset|data)\b", label, re.I):
            return f"A structured data artifact containing {lower}, generated, transformed, or consumed by a DECODE measurement, analysis, or modeling workflow."
        return f"A data artifact recording {lower} as an input, intermediate result, or output of a hydrogen-technology workflow."
    return f"Contextual metadata describing {lower} and retained to support interpretation and provenance of a DECODE workflow record."


def _workflow_definition(workflow: dict[str, Any]) -> str:
    title = str(workflow.get("title", "workflow"))
    source_kind = str(workflow.get("source_kind", "source_graphml"))
    if source_kind == "derived_schema":
        return f"A derived DECODE workflow plan for {title}, preserving the reviewed model-stage input and output interfaces."
    if source_kind == "source_manual_json":
        return f"A DECODE workflow plan for {title}, normalized from the sanitized manual workflow overlay while preserving its declared inputs and outputs."
    return f"A DECODE workflow plan for {title}, preserving the nodes and directed dependencies of the source GraphML workflow."


def _resource(identifier: str, resources: dict[str, URIRef]) -> URIRef:
    if identifier in resources:
        return resources[identifier]
    if identifier.startswith("http://") or identifier.startswith("https://"):
        return URIRef(identifier)
    return _record_iri("resource", identifier)


def _record_iri(kind: str, identifier: str) -> URIRef:
    digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()[:16]
    tail = quote(identifier.rsplit("::", 1)[-1], safe="-._~")[:80]
    return URIRef(f"{DECODE_WORKFLOW}{kind}/{tail}-{digest}")


def _clean_definition_subject(label: str) -> str:
    cleaned = re.sub(r"\s+", " ", label).strip().rstrip(".")
    return cleaned or "the represented concept"


def _normal(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _humanize(value: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", " ", value).lower()
