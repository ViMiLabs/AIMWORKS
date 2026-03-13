from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS

from .normalize import humanize_identifier
from .utils import as_uri_text, is_local_iri, local_name, namespace_of


@dataclass
class LocalTerm:
    iri: str
    local_name: str
    label: str
    term_type: str
    category: str
    definition: str
    comment: str
    deprecated: bool
    superclasses: list[str]
    domains: list[str]
    ranges: list[str]
    types: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _first_text(graph: Graph, subject: URIRef, predicates: list[URIRef]) -> str:
    for predicate in predicates:
        for obj in graph.objects(subject, predicate):
            return str(obj)
    return ""


def extract_local_terms(
    graph: Graph,
    namespace_policy: dict[str, Any],
    classifications: dict[str, Any],
) -> list[LocalTerm]:
    terms: list[LocalTerm] = []
    for subject in sorted(set(graph.subjects()), key=str):
        if not isinstance(subject, URIRef):
            continue
        iri = str(subject)
        if not is_local_iri(subject, namespace_policy):
            continue
        record = classifications.get(iri)
        if not record or record.category in {"ontology_header", "example_individual", "ephemeral_generated_instance", "quantity_value_data_node"}:
            continue
        label = _first_text(graph, subject, [RDFS.label, SKOS.prefLabel]) or humanize_identifier(local_name(subject))
        definition = _first_text(graph, subject, [SKOS.definition])
        comment = _first_text(graph, subject, [RDFS.comment])
        term = LocalTerm(
            iri=iri,
            local_name=local_name(subject),
            label=label,
            term_type=record.term_type,
            category=record.category,
            definition=definition,
            comment=comment,
            deprecated=any(str(obj).lower() == "true" for obj in graph.objects(subject, OWL.deprecated)),
            superclasses=[as_uri_text(obj) for obj in graph.objects(subject, RDFS.subClassOf)],
            domains=[as_uri_text(obj) for obj in graph.objects(subject, RDFS.domain)],
            ranges=[as_uri_text(obj) for obj in graph.objects(subject, RDFS.range)],
            types=[as_uri_text(obj) for obj in graph.objects(subject, RDF.type)],
        )
        terms.append(term)
    return terms


def collect_namespace_rows(graph: Graph) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for subject in set(graph.subjects()):
        if isinstance(subject, URIRef):
            counts[namespace_of(str(subject))] = counts.get(namespace_of(str(subject)), 0) + 1
    rows = [{"prefix": "", "namespace": namespace, "count": count} for namespace, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]
    return rows


def collect_examples(graph: Graph, classifications: dict[str, Any], limit: int = 40) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for subject in sorted(set(graph.subjects()), key=str):
        iri = str(subject)
        record = classifications.get(iri)
        if not record or record.category not in {"example_individual", "controlled_vocabulary_term", "quantity_value_data_node"}:
            continue
        rows.append(
            {
                "iri": iri,
                "kind": record.category,
                "label": _first_text(graph, subject, [RDFS.label, SKOS.prefLabel]) or humanize_identifier(local_name(subject)),
                "notes": "; ".join(record.reasons[:2]),
            }
        )
        if len(rows) >= limit:
            break
    return rows
