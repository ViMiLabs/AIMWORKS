from __future__ import annotations

from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

from .sources import builtin_source_terms, load_sources
from .utils import package_root

try:
    from rdflib import Graph
    from rdflib.namespace import OWL, RDF, RDFS
except Exception:  # pragma: no cover
    Graph = None  # type: ignore[assignment]
    OWL = None  # type: ignore[assignment]
    RDF = None  # type: ignore[assignment]
    RDFS = None  # type: ignore[assignment]


def build_source_index(config_dir: str | Path | None = None) -> list[dict[str, Any]]:
    sources = load_sources(config_dir)
    config_base = Path(config_dir or package_root())
    enabled = {source.identifier for source in sources if source.enabled}
    terms = [term for term in builtin_source_terms() if term["source"] in enabled or term["source"] == "foaf"]
    for source in sources:
        if not source.enabled or not source.local_cache:
            continue
        terms.extend(_load_cached_source_terms(source.identifier, Path(source.local_cache), config_base))
    return terms


def _load_cached_source_terms(source_id: str, cache_path: Path, config_base: Path) -> list[dict[str, Any]]:
    if not cache_path.is_absolute():
        cache_path = config_base.parent / cache_path if config_base.name == "config" else config_base / cache_path
    if not cache_path.exists():
        return []
    if Graph is None:
        return _load_cached_source_terms_fallback(source_id, cache_path)
    graph = Graph()
    try:
        format_hint = "turtle" if cache_path.suffix.lower() in {".ttl", ".turtle"} else "json-ld" if cache_path.suffix.lower() == ".jsonld" else None
        graph.parse(cache_path, format=format_hint)
    except Exception:
        return []
    terms: list[dict[str, Any]] = []
    for subject, _, obj in graph.triples((None, RDF.type, None)):
        kind = _kind_from_object(obj)
        if not kind:
            continue
        label = _first_literal(graph, subject, RDFS.label) or str(subject).rsplit("/", 1)[-1].rsplit("#", 1)[-1]
        description = _first_literal(graph, subject, RDFS.comment)
        terms.append(
            {
                "iri": str(subject),
                "label": label,
                "kind": kind,
                "source": source_id,
                "description": description,
                "synonyms": [],
            }
        )
    return terms


def _load_cached_source_terms_fallback(source_id: str, cache_path: Path) -> list[dict[str, Any]]:
    if cache_path.suffix.lower() not in {".owl", ".rdf", ".xml"}:
        return []
    try:
        tree = ET.parse(cache_path)
        root = tree.getroot()
    except Exception:
        return []
    ns = {
        "owl": "http://www.w3.org/2002/07/owl#",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    }
    terms: list[dict[str, Any]] = []
    for tag, kind in [("owl:Class", "class"), ("owl:ObjectProperty", "object_property"), ("owl:DatatypeProperty", "datatype_property"), ("owl:AnnotationProperty", "annotation_property")]:
        for element in root.findall(tag, ns):
            iri = element.attrib.get(f"{{{ns['rdf']}}}about", "")
            if not iri:
                continue
            label = element.findtext("rdfs:label", default="", namespaces=ns) or iri.rsplit("/", 1)[-1].rsplit("#", 1)[-1]
            description = element.findtext("rdfs:comment", default="", namespaces=ns)
            terms.append({"iri": iri, "label": label, "kind": kind, "source": source_id, "description": description, "synonyms": []})
    return terms


def _kind_from_object(obj: Any) -> str:
    if obj in {OWL.Class, RDFS.Class}:
        return "class"
    if obj == OWL.ObjectProperty:
        return "object_property"
    if obj == OWL.DatatypeProperty:
        return "datatype_property"
    if obj == OWL.AnnotationProperty:
        return "annotation_property"
    return ""


def _first_literal(graph: Graph, subject: Any, predicate: Any) -> str:
    for value in graph.objects(subject, predicate):
        if value:
            return str(value)
    return ""
