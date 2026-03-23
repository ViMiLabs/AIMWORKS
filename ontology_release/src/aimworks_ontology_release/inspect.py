from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .io import iter_document_items, load_json_document, merge_document_items
from .normalize import best_description, best_label
from .utils import (
    OWL_CLASS,
    OWL_DATATYPE_PROPERTY,
    OWL_OBJECT_PROPERTY,
    OWL_ONTOLOGY,
    QUDT_QUANTITY_VALUE,
    RDFS_CLASS,
    RDFS_COMMENT,
    RDFS_LABEL,
    SKOS_DEFINITION,
    default_release_profile,
    dump_json,
    ensure_dir,
    short_text,
    today_iso,
    try_load_yaml,
    uri_namespace,
    write_text,
)


def inspect_ontology(
    input_path: str | Path,
    output_dir: str | Path,
    config_dir: str | Path | None = None,
) -> dict[str, Any]:
    input_path = Path(input_path)
    output_dir = ensure_dir(Path(output_dir))
    profile = try_load_yaml(Path(config_dir or input_path.parent.parent / "config") / "release_profile.yaml", default_release_profile())
    ontology_iri = profile["project"]["ontology_iri"]
    document = load_json_document(input_path)
    items = iter_document_items(document)
    merged = merge_document_items(document)
    namespace_counter: Counter[str] = Counter()
    type_counter: Counter[str] = Counter()
    predicate_counter: Counter[str] = Counter()
    imported: set[str] = set()
    duplicate_ids: Counter[str] = Counter()
    schema_items: list[dict[str, Any]] = []
    local_nodes = 0
    local_namespace = profile["project"]["namespace_uri"]
    for item in items:
        identifier = item.get("@id")
        if isinstance(identifier, str):
            duplicate_ids[identifier] += 1
        for key, value in item.items():
            if key not in {"@id", "@type"}:
                predicate_counter[key] += 1
                if key == "http://www.w3.org/2002/07/owl#imports":
                    values = value if isinstance(value, list) else [value]
                    for entry in values:
                        imported.add(str(entry.get("@id")) if isinstance(entry, dict) else str(entry))
            if key.startswith("http"):
                namespace_counter[uri_namespace(key)] += 1
        identifier = item.get("@id", "")
        if isinstance(identifier, str) and identifier.startswith(local_namespace):
            local_nodes += 1
            namespace_counter[uri_namespace(identifier)] += 1
        types = item.get("@type", [])
        type_values = types if isinstance(types, list) else [types]
        for type_value in type_values:
            if isinstance(type_value, str):
                type_counter[type_value] += 1
        if any(t in {OWL_CLASS, RDFS_CLASS, OWL_OBJECT_PROPERTY, OWL_DATATYPE_PROPERTY} for t in type_values):
            schema_items.append(item)
    schema_labels = sum(1 for item in schema_items if item.get(RDFS_LABEL))
    schema_comments = sum(1 for item in schema_items if item.get(RDFS_COMMENT))
    schema_definitions = sum(1 for item in schema_items if item.get(SKOS_DEFINITION))
    ontology_headers = [item for item in merged if item.get("@id") == ontology_iri or OWL_ONTOLOGY in (item.get("@type") if isinstance(item.get("@type"), list) else [item.get("@type")])]
    blockers: list[str] = []
    if not ontology_headers:
        blockers.append("No explicit owl:Ontology header was found.")
    if schema_labels < len(schema_items):
        blockers.append(f"{len(schema_items) - schema_labels} schema terms are missing rdfs:label annotations.")
    if schema_definitions < len(schema_items):
        blockers.append(f"{len(schema_items) - schema_definitions} schema terms are missing skos:definition annotations.")
    if any(count > 1 for count in duplicate_ids.values()):
        blockers.append(f"{sum(1 for count in duplicate_ids.values() if count > 1)} duplicated @id values detected in the source JSON-LD.")
    if QUDT_QUANTITY_VALUE in type_counter:
        blockers.append("The ontology contains many QUDT quantity-value nodes that should remain in an example or data module.")
    fair_blockers = [
        "Version IRI and preferred namespace metadata are not consistently declared in the source ontology header.",
        "Schema annotation coverage is incomplete for labels, comments, and definitions.",
        "The source graph mixes schema and data-like resources, which reduces release clarity.",
    ]
    report = {
        "generated_on": today_iso(),
        "input": str(input_path),
        "ontology_iri": ontology_iri,
        "counts": {
            "raw_item_count": len(items),
            "merged_item_count": len(merged),
            "local_node_count": local_nodes,
            "class_count": type_counter.get(OWL_CLASS, 0) + type_counter.get(RDFS_CLASS, 0),
            "object_property_count": type_counter.get(OWL_OBJECT_PROPERTY, 0),
            "datatype_property_count": type_counter.get(OWL_DATATYPE_PROPERTY, 0),
            "quantity_value_count": type_counter.get(QUDT_QUANTITY_VALUE, 0),
        },
        "schema_annotation_coverage": {
            "schema_term_count": len(schema_items),
            "label_count": schema_labels,
            "comment_count": schema_comments,
            "definition_count": schema_definitions,
        },
        "imports": sorted(imported),
        "namespace_usage": namespace_counter.most_common(20),
        "top_types": type_counter.most_common(20),
        "top_predicates": predicate_counter.most_common(20),
        "duplicate_ids": sorted([identifier for identifier, count in duplicate_ids.items() if count > 1]),
        "release_blockers": blockers,
        "fair_blockers": fair_blockers,
        "sample_schema_terms": [
            {
                "iri": item.get("@id", ""),
                "label": best_label(item),
                "description": short_text(best_description(item)),
            }
            for item in schema_items[:20]
        ],
    }
    dump_json(output_dir / "inspection_report.json", report)
    markdown = _inspection_markdown(report)
    write_text(output_dir / "inspection_report.md", markdown)
    return report


def _inspection_markdown(report: dict[str, Any]) -> str:
    counts = report["counts"]
    coverage = report["schema_annotation_coverage"]
    namespaces = "\n".join(f"- `{namespace}`: {count}" for namespace, count in report["namespace_usage"])
    blockers = "\n".join(f"- {line}" for line in report["release_blockers"]) or "- None detected"
    fair_blockers = "\n".join(f"- {line}" for line in report["fair_blockers"]) or "- None detected"
    imports = "\n".join(f"- `{item}`" for item in report["imports"]) or "- None declared"
    return f"""# Inspection Report

Generated on {report['generated_on']}.

## Ontology Summary

- Ontology IRI: `{report['ontology_iri']}`
- Raw JSON-LD nodes: {counts['raw_item_count']}
- Merged node count: {counts['merged_item_count']}
- Local `h2kg` nodes: {counts['local_node_count']}
- Explicit classes: {counts['class_count']}
- Explicit object properties: {counts['object_property_count']}
- Explicit datatype properties: {counts['datatype_property_count']}
- QUDT quantity value nodes: {counts['quantity_value_count']}

## Schema Annotation Coverage

- Schema terms inspected: {coverage['schema_term_count']}
- With labels: {coverage['label_count']}
- With comments: {coverage['comment_count']}
- With definitions: {coverage['definition_count']}

## Imported Ontologies

{imports}

## Namespace Usage

{namespaces}

## Likely Release Blockers

{blockers}

## Likely FAIR Blockers

{fair_blockers}
"""
