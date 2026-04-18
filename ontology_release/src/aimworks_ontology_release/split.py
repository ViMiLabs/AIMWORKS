from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .classify import classify_resources
from .io import dump_jsonld_items, dump_turtle_items, load_json_document, merge_document_items
from .normalize import best_label
from .utils import ensure_dir, write_text


def split_ontology(
    input_path: str | Path,
    output_dir: str | Path,
    config_dir: str | Path | None = None,
) -> dict[str, Any]:
    output_dir = ensure_dir(Path(output_dir))
    classifications = classify_resources(input_path, output_dir.parent / "review", config_dir)
    kind_by_iri = {entry.iri: entry for entry in classifications}
    merged = merge_document_items(load_json_document(input_path))
    schema_items: list[dict[str, Any]] = []
    vocab_items: list[dict[str, Any]] = []
    example_items: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for item in merged:
        identifier = item.get("@id")
        if not isinstance(identifier, str) or identifier not in kind_by_iri:
            continue
        classification = kind_by_iri[identifier]
        kind = classification.kind
        if kind in {"ontology_header", "class", "object_property", "datatype_property", "annotation_property"}:
            if classification.is_local:
                schema_items.append(item)
                counts["schema"] += 1
        elif kind == "controlled_vocabulary_term" and classification.is_local:
            vocab_items.append(item)
            counts["vocabulary"] += 1
        elif kind in {"example_individual", "ephemeral_generated_instance", "quantity_value_data_node"} and classification.is_local:
            example_items.append(item)
            counts["examples"] += 1
    dump_turtle_items(output_dir / "schema.ttl", schema_items)
    dump_jsonld_items(output_dir / "schema.jsonld", schema_items)
    dump_turtle_items(output_dir / "controlled_vocabulary.ttl", vocab_items)
    dump_turtle_items(output_dir.parent / "examples" / "examples.ttl", example_items)
    report = {
        "schema_count": counts["schema"],
        "vocabulary_count": counts["vocabulary"],
        "example_count": counts["examples"],
        "schema_preview": [best_label(item) for item in schema_items[:15]],
        "vocabulary_preview": [best_label(item) for item in vocab_items[:15]],
        "example_preview": [best_label(item) for item in example_items[:15]],
    }
    write_text(output_dir.parent / "reports" / "split_report.md", _split_report(report))
    return report


def _split_report(report: dict[str, Any]) -> str:
    return f"""# Split Report

- Schema resources: {report['schema_count']}
- Controlled vocabulary resources: {report['vocabulary_count']}
- Example or data-like resources: {report['example_count']}

## Schema Preview

{chr(10).join(f"- {item}" for item in report['schema_preview']) or '- None'}

## Controlled Vocabulary Preview

{chr(10).join(f"- {item}" for item in report['vocabulary_preview']) or '- None'}

## Example Preview

{chr(10).join(f"- {item}" for item in report['example_preview']) or '- None'}
"""
