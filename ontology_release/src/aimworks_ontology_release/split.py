from __future__ import annotations

from typing import Any

from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from .classify import ResourceClassification
from .io import save_graph
from .utils import gather_bnode_closure, write_json, write_text


SCHEMA_CATEGORIES = {"ontology_header", "class", "object_property", "datatype_property", "annotation_property"}


def _copy_subjects(source: Graph, target: Graph, subjects: set[Any]) -> None:
    closure = gather_bnode_closure(source, subjects)
    for subject in subjects | closure:
        for triple in source.triples((subject, None, None)):
            target.add(triple)


def split_graph(
    graph: Graph,
    classifications: dict[str, ResourceClassification],
) -> tuple[dict[str, Graph], dict[str, Any]]:
    schema_subjects: set[Any] = set()
    vocab_subjects: set[Any] = set()
    example_subjects: set[Any] = set()

    for subject in set(graph.subjects()):
        record = classifications.get(str(subject))
        if not record:
            continue
        if record.category in SCHEMA_CATEGORIES:
            schema_subjects.add(subject)
        elif record.category == "controlled_vocabulary_term":
            vocab_subjects.add(subject)
        elif record.category in {"example_individual", "ephemeral_generated_instance", "quantity_value_data_node"}:
            example_subjects.add(subject)

    schema_graph = Graph()
    vocab_graph = Graph()
    examples_graph = Graph()
    for prefix, namespace in graph.namespaces():
        schema_graph.bind(prefix, namespace)
        vocab_graph.bind(prefix, namespace)
        examples_graph.bind(prefix, namespace)

    _copy_subjects(graph, schema_graph, schema_subjects)
    _copy_subjects(graph, vocab_graph, vocab_subjects)
    _copy_subjects(graph, examples_graph, example_subjects)

    report = {
        "schema_subject_count": len(schema_subjects),
        "controlled_vocabulary_subject_count": len(vocab_subjects),
        "example_subject_count": len(example_subjects),
        "schema_triples": len(schema_graph),
        "controlled_vocabulary_triples": len(vocab_graph),
        "examples_triples": len(examples_graph),
        "notes": [
            "Schema output preserves ontology headers, classes, and properties.",
            "Controlled vocabulary output keeps named, curated terms typed by local vocabulary-like classes.",
            "Examples output captures example individuals, quantity values, blank-node closures, and ephemeral data-like resources.",
        ],
    }
    return {"schema": schema_graph, "controlled_vocabulary": vocab_graph, "examples": examples_graph}, report


def write_split_outputs(graphs: dict[str, Graph], report: dict[str, Any], root: str | Any) -> None:
    root_path = root if hasattr(root, "joinpath") else None
    if root_path is None:
        raise TypeError("root must be a pathlib.Path-like object")
    save_graph(graphs["schema"], root_path / "output" / "ontology" / "schema.ttl", "turtle")
    save_graph(graphs["schema"], root_path / "output" / "ontology" / "schema.jsonld", "json-ld")
    save_graph(graphs["controlled_vocabulary"], root_path / "output" / "ontology" / "controlled_vocabulary.ttl", "turtle")
    save_graph(graphs["examples"], root_path / "output" / "examples" / "examples.ttl", "turtle")
    write_json(root_path / "output" / "reports" / "split_report.json", report)
    report_lines = [
        "# Split Report",
        "",
        f"- Schema subjects: **{report['schema_subject_count']}**",
        f"- Controlled vocabulary subjects: **{report['controlled_vocabulary_subject_count']}**",
        f"- Example or data-like subjects: **{report['example_subject_count']}**",
        f"- Schema triples: **{report['schema_triples']}**",
        f"- Controlled vocabulary triples: **{report['controlled_vocabulary_triples']}**",
        f"- Example triples: **{report['examples_triples']}**",
        "",
        "## Notes",
        "",
    ]
    report_lines.extend(f"- {item}" for item in report["notes"])
    write_text(root_path / "output" / "reports" / "split_report.md", "\n".join(report_lines) + "\n")
