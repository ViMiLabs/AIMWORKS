from __future__ import annotations

from pathlib import Path

from rdflib import Graph

from .utils import ensure_dir


FORMAT_MAP = {
    ".jsonld": "json-ld",
    ".json": "json-ld",
    ".ttl": "turtle",
    ".rdf": "xml",
    ".owl": "xml",
    ".xml": "xml",
    ".nt": "nt",
    ".n3": "n3",
}


def guess_rdf_format(path: Path) -> str:
    return FORMAT_MAP.get(path.suffix.lower(), "turtle")


def load_graph(path: Path, rdf_format: str | None = None) -> Graph:
    graph = Graph()
    graph.parse(path, format=rdf_format or guess_rdf_format(path))
    return graph


def save_graph(graph: Graph, path: Path, rdf_format: str | None = None) -> Path:
    ensure_dir(path.parent)
    graph.serialize(destination=str(path), format=rdf_format or guess_rdf_format(path), encoding="utf-8")
    return path


def graph_from_text(text: str, rdf_format: str = "turtle") -> Graph:
    graph = Graph()
    graph.parse(data=text, format=rdf_format)
    return graph
