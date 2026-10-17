from __future__ import annotations

"""Normalize generated example records to the H2KG 2.2 role model."""

import json
from pathlib import Path
from typing import Any

from rdflib import Graph

from .io import dump_turtle_items, iter_document_items
from .utils import COMMON_CONTEXT, dump_json, ensure_dir, load_json


H2KG = COMMON_CONTEXT["h2kg"]
RDFS = COMMON_CONTEXT["rdfs"]
DCTERMS = COMMON_CONTEXT["dcterms"]

PARAMETER = H2KG + "Parameter"
DATA_POINT = H2KG + "DataPoint"
OF_PROPERTY = H2KG + "ofProperty"
HAS_QUANTITY_VALUE = H2KG + "hasQuantityValue"
LABEL = RDFS + "label"
DESCRIPTION = DCTERMS + "description"

PILOT_EXAMPLE_STEMS = {
    "afm_example",
    "fib_sem_example",
    "ic_sem_example",
    "neutron_tomo_example",
    "sem_pilot_example",
    "synchrotron_xray_tomo_example",
    "tem_pilot_example",
    "xps_example",
    "xrd_example",
}


def normalize_generated_example_instances(
    output_root: str | Path,
    taxonomy_registry_path: str | Path,
) -> dict[str, Any]:
    """Replace dual-typed value nodes with explicit record/property pairs.

    The source-grounded content and occurrence IRIs are retained.  A stable
    property-occurrence IRI is added behind every Parameter or DataPoint record
    so contextual workflow role and intrinsic scientific identity are not
    conflated.
    """

    output_root = Path(output_root)
    taxonomy_registry_path = Path(taxonomy_registry_path)
    if not taxonomy_registry_path.exists():
        report = {
            "schema_version": "h2kg-instance-role-normalization/v1",
            "profile_version": "2.2.0",
            "status": "skipped_missing_taxonomy_registry",
            "taxonomy_registry": str(taxonomy_registry_path),
            "file_pair_count": 0,
            "parameter_record_count": 0,
            "result_record_count": 0,
            "property_occurrence_count": 0,
            "moved_quantity_value_count": 0,
            "files": [],
        }
        dump_json(
            ensure_dir(output_root / "reports") / "example_instance_role_normalization.json",
            report,
        )
        return report
    registry = load_json(taxonomy_registry_path)
    characteristic_iris = {
        str(row["iri"])
        for row in registry.get("terms", [])
        if row.get("disposition", "active_local_class") == "active_local_class"
        and row.get("corrected_semantic_role") == "Characteristic"
    }
    profile_fallbacks = {
        str(row["iri"]): str(row["profile_fallback_iri"])
        for row in registry.get("terms", [])
        if row.get("disposition") != "active_local_class"
        and row.get("profile_fallback_iri")
    }
    # Generic Property is accepted for deliberately generic capture templates.
    characteristic_iris.add(H2KG + "Property")

    rows: list[dict[str, Any]] = []
    examples_root = output_root / "examples"
    for jsonld_path in sorted(examples_root.rglob("*.jsonld")):
        if jsonld_path.stem not in PILOT_EXAMPLE_STEMS:
            continue
        ttl_path = jsonld_path.with_suffix(".ttl")
        if not ttl_path.exists():
            continue
        rows.append(
            normalize_example_pair(
                jsonld_path,
                ttl_path,
                characteristic_iris,
                profile_fallbacks,
            )
        )

    report = {
        "schema_version": "h2kg-instance-role-normalization/v1",
        "profile_version": "2.2.0",
        "status": "passed" if all(row["conforms"] for row in rows) else "failed",
        "file_pair_count": len(rows),
        "parameter_record_count": sum(row["parameter_record_count"] for row in rows),
        "result_record_count": sum(row["result_record_count"] for row in rows),
        "property_occurrence_count": sum(row["property_occurrence_count"] for row in rows),
        "moved_quantity_value_count": sum(row["moved_quantity_value_count"] for row in rows),
        "profile_fallback_count": sum(row["profile_fallback_count"] for row in rows),
        "files": rows,
    }
    report_path = ensure_dir(output_root / "reports") / "example_instance_role_normalization.json"
    dump_json(report_path, report)
    if report["status"] != "passed":
        raise ValueError("Generated H2KG examples failed parameter/property role normalization.")
    return report


def normalize_example_pair(
    jsonld_path: Path,
    ttl_path: Path,
    characteristic_iris: set[str],
    profile_fallbacks: dict[str, str] | None = None,
) -> dict[str, Any]:
    document = load_json(jsonld_path)
    items = iter_document_items(document)
    additions: list[dict[str, Any]] = []
    parameter_records = 0
    result_records = 0
    moved_values = 0
    fallback_count = 0
    profile_fallbacks = profile_fallbacks or {}

    for item in items:
        identifier = item.get("@id")
        if not isinstance(identifier, str):
            continue
        source_types = _string_values(item.get("@type"))
        types = [profile_fallbacks.get(value, value) for value in source_types]
        fallback_count += sum(
            1 for value in source_types if profile_fallbacks.get(value, value) != value
        )
        characteristic_types = sorted(set(types) & characteristic_iris)

        if PARAMETER in types and characteristic_types:
            parameter_records += 1
            item["@type"] = [value for value in types if value not in characteristic_types]
            occurrence = _property_occurrence(item, characteristic_types, "parameter")
            moved_values += _move_quantity_values(item, occurrence)
            item[OF_PROPERTY] = [{"@id": occurrence["@id"]}]
            additions.append(occurrence)

        if DATA_POINT not in types:
            continue
        direct_targets = [
            profile_fallbacks.get(str(value.get("@id")), str(value.get("@id")))
            for value in _object_values(item.get(OF_PROPERTY))
            if isinstance(value.get("@id"), str)
            and profile_fallbacks.get(str(value.get("@id")), str(value.get("@id")))
            in characteristic_iris
        ]
        if not direct_targets:
            continue
        result_records += 1
        occurrence = _property_occurrence(item, sorted(set(direct_targets)), "result")
        moved_values += _move_quantity_values(item, occurrence)
        item[OF_PROPERTY] = [{"@id": occurrence["@id"]}]
        additions.append(occurrence)

    existing_ids = {item.get("@id") for item in items}
    items.extend(item for item in additions if item["@id"] not in existing_ids)
    if isinstance(document, dict) and isinstance(document.get("@graph"), list):
        document["@graph"] = items
    else:
        document = {"@context": COMMON_CONTEXT, "@graph": items}
    dump_json(jsonld_path, document)
    dump_turtle_items(ttl_path, items)

    json_graph = Graph().parse(jsonld_path, format="json-ld")
    ttl_graph = Graph().parse(ttl_path, format="turtle")
    direct_parameter_characteristics = [
        item.get("@id")
        for item in items
        if PARAMETER in _string_values(item.get("@type"))
        and set(_string_values(item.get("@type"))) & characteristic_iris
    ]
    direct_result_classes = [
        item.get("@id")
        for item in items
        if DATA_POINT in _string_values(item.get("@type"))
        and any(
            value.get("@id") in characteristic_iris
            for value in _object_values(item.get(OF_PROPERTY))
        )
    ]
    conforms = (
        set(json_graph) == set(ttl_graph)
        and not direct_parameter_characteristics
        and not direct_result_classes
    )
    return {
        "jsonld": str(jsonld_path),
        "turtle": str(ttl_path),
        "parameter_record_count": parameter_records,
        "result_record_count": result_records,
        "property_occurrence_count": len(additions),
        "moved_quantity_value_count": moved_values,
        "profile_fallback_count": fallback_count,
        "rdf_statement_count": len(json_graph),
        "direct_parameter_characteristic_count": len(direct_parameter_characteristics),
        "direct_datapoint_class_target_count": len(direct_result_classes),
        "conforms": conforms,
    }


def _property_occurrence(
    record: dict[str, Any],
    characteristic_types: list[str],
    context: str,
) -> dict[str, Any]:
    record_id = str(record["@id"])
    occurrence_id = _child_iri(record_id, "property-occurrence")
    source_label = _first_literal(record.get(LABEL))
    label = source_label or record_id.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
    return {
        "@id": occurrence_id,
        "@type": characteristic_types,
        LABEL: [{"@language": "en", "@value": f"{label} property occurrence"}],
        DESCRIPTION: [
            {
                "@language": "en",
                "@value": (
                    f"A scientific property occurrence referenced by the {context} record; "
                    "its type denotes intrinsic scientific identity rather than workflow role."
                ),
            }
        ],
    }


def _move_quantity_values(source: dict[str, Any], target: dict[str, Any]) -> int:
    values = source.pop(HAS_QUANTITY_VALUE, None)
    if values is None:
        return 0
    target[HAS_QUANTITY_VALUE] = values if isinstance(values, list) else [values]
    return len(target[HAS_QUANTITY_VALUE])


def _child_iri(identifier: str, suffix: str) -> str:
    if "#" in identifier:
        base, fragment = identifier.rsplit("#", 1)
        return f"{base}#{fragment}-{suffix}"
    return identifier.rstrip("/") + "/" + suffix


def _string_values(value: Any) -> list[str]:
    values = value if isinstance(value, list) else [value] if value else []
    return [str(item) for item in values if isinstance(item, str)]


def _object_values(value: Any) -> list[dict[str, Any]]:
    values = value if isinstance(value, list) else [value] if value else []
    return [item for item in values if isinstance(item, dict)]


def _first_literal(value: Any) -> str:
    for item in _object_values(value):
        if "@value" in item:
            return str(item["@value"])
    return ""
