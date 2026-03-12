from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS

from .utils import QUDT, as_uri_text, is_local_iri, local_name


@dataclass
class ResourceClassification:
    iri: str
    category: str
    term_type: str
    local: bool
    score: float
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def explicit_term_type(graph: Graph, subject: URIRef | BNode) -> str:
    rdf_types = set(graph.objects(subject, RDF.type))
    if OWL.Ontology in rdf_types:
        return "ontology_header"
    if OWL.Class in rdf_types or RDFS.Class in rdf_types:
        return "class"
    if OWL.ObjectProperty in rdf_types:
        return "object_property"
    if OWL.DatatypeProperty in rdf_types:
        return "datatype_property"
    if OWL.AnnotationProperty in rdf_types:
        return "annotation_property"
    return "other"


def _matches_any(value: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in patterns)


def _typed_by_anchor(graph: Graph, subject: URIRef | BNode, anchors: list[str]) -> bool:
    for rdf_type in graph.objects(subject, RDF.type):
        if local_name(rdf_type) in anchors:
            return True
    return False


def classify_resource(
    graph: Graph,
    subject: URIRef | BNode,
    namespace_policy: dict[str, Any],
    rules: dict[str, Any],
) -> ResourceClassification:
    iri = as_uri_text(subject)
    local = is_local_iri(subject, namespace_policy)
    reasons: list[str] = []
    explicit = explicit_term_type(graph, subject)
    if explicit != "other":
        reasons.append(f"explicit rdf:type {explicit}")
        return ResourceClassification(iri, explicit, explicit, local, 1.0, reasons)

    if isinstance(subject, BNode):
        reasons.append("blank node")
        return ResourceClassification(iri, "ephemeral_generated_instance", "other", False, 0.95, reasons)

    identifier = local_name(subject)
    classification_rules = rules.get("classification", {})
    if _matches_any(identifier, classification_rules.get("ephemeral_identifier_patterns", [])):
        reasons.append("identifier matches ephemeral pattern")
        return ResourceClassification(iri, "ephemeral_generated_instance", "other", local, 0.9, reasons)

    if any(str(obj).startswith(str(QUDT)) for obj in graph.objects(subject, None)):
        reasons.append("uses QUDT predicate/object")
        return ResourceClassification(iri, "quantity_value_data_node", "other", local, 0.92, reasons)

    if any(local_name(obj) == "QuantityValue" for obj in graph.objects(subject, RDF.type)):
        reasons.append("typed as QuantityValue")
        return ResourceClassification(iri, "quantity_value_data_node", "other", local, 0.96, reasons)

    if _matches_any(identifier, classification_rules.get("quantity_value_patterns", [])):
        if any(isinstance(obj, Literal) for _, _, obj in graph.triples((subject, None, None))):
            reasons.append("identifier resembles quantity value and has literal assertions")
            return ResourceClassification(iri, "quantity_value_data_node", "other", local, 0.85, reasons)

    outgoing = list(graph.predicate_objects(subject))
    if local and (
        _typed_by_anchor(graph, subject, classification_rules.get("controlled_vocabulary_anchor_classes", []))
        or (list(graph.objects(subject, RDFS.label)) or list(graph.objects(subject, SKOS.prefLabel)))
        and len(outgoing) <= 8
    ):
        reasons.append("typed by anchor class or concise labeled individual")
        return ResourceClassification(iri, "controlled_vocabulary_term", "controlled_vocabulary_term", local, 0.82, reasons)

    if local:
        reasons.append("local named individual-like resource")
        return ResourceClassification(iri, "example_individual", "example_individual", local, 0.72, reasons)

    reasons.append("external reference")
    return ResourceClassification(iri, "external_reference", "other", False, 0.5, reasons)


def classify_resources(
    graph: Graph,
    namespace_policy: dict[str, Any],
    rules: dict[str, Any],
) -> dict[str, ResourceClassification]:
    classifications: dict[str, ResourceClassification] = {}
    for subject in set(graph.subjects()):
        record = classify_resource(graph, subject, namespace_policy, rules)
        classifications[record.iri] = record
    return classifications
