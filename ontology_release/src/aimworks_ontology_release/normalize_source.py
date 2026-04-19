from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .io import iter_document_items, load_json_document, merge_document_items
from .utils import ensure_dir

DCTERMS_DESCRIPTION = "http://purl.org/dc/terms/description"
RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"
H2KG_INSTRUMENT = "https://w3id.org/h2kg/hydrogen-ontology#Instrument"
DYNAMIC_HYDROGEN_ELECTRODE = "https://w3id.org/h2kg/hydrogen-ontology#DynamicHydrogenElectrode"
OWL_ANNOTATION_PROPERTY = "http://www.w3.org/2002/07/owl#AnnotationProperty"
H2KG_APPLIES_TO_PROFILE = "https://w3id.org/h2kg/hydrogen-ontology#appliesToProfile"
H2KG_NUMBER_OF_SPRAY_PASSES = "https://w3id.org/h2kg/hydrogen-ontology#NumberOfSprayPasses"
H2KG_PASSES = "https://w3id.org/h2kg/hydrogen-ontology#Passes"
H2KG_ROTATING_RING_DISK_VOLTAMMETRY = "https://w3id.org/h2kg/hydrogen-ontology#RotatingRingDiskVoltammetry"
H2KG_ROTATING_DISK_VOLTAMMETRY = "https://w3id.org/h2kg/hydrogen-ontology#RotatingDiskVoltammetry"


def normalize_source_document(
    input_path: str | Path,
    output_dir: str | Path,
    write_in_place: bool = True,
) -> dict[str, Any]:
    input_path = Path(input_path)
    output_dir = ensure_dir(Path(output_dir))

    document = load_json_document(input_path)
    original_items = iter_document_items(document)
    duplicate_counts = Counter(
        identifier for identifier in (item.get("@id") for item in original_items) if isinstance(identifier, str)
    )
    duplicate_ids = sorted(identifier for identifier, count in duplicate_counts.items() if count > 1)

    normalized_items = merge_document_items(document)
    repairs = _apply_targeted_repairs(normalized_items)

    target_path = input_path if write_in_place else output_dir / input_path.name
    target_path.write_text(json.dumps(normalized_items, indent=2, ensure_ascii=False), encoding="utf-8")

    report = {
        "target_path": str(target_path),
        "original_item_count": len(original_items),
        "normalized_item_count": len(normalized_items),
        "duplicate_group_count": len(duplicate_ids),
        "duplicate_ids": duplicate_ids,
        "repairs": repairs,
    }
    (output_dir / "source_normalization_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return report


def _apply_targeted_repairs(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    repairs: list[dict[str, Any]] = []

    alias_repairs = [
        _replace_iri_reference(items, H2KG_PASSES, H2KG_NUMBER_OF_SPRAY_PASSES, "replaced legacy Passes reference with NumberOfSprayPasses"),
        _replace_iri_reference(
            items,
            H2KG_ROTATING_DISK_VOLTAMMETRY,
            H2KG_ROTATING_RING_DISK_VOLTAMMETRY,
            "replaced unresolved RotatingDiskVoltammetry reference with RotatingRingDiskVoltammetry",
        ),
    ]
    repairs.extend(repair for repair in alias_repairs if repair is not None)

    items_by_iri = {item["@id"]: item for item in items if isinstance(item.get("@id"), str)}

    dhe = items_by_iri.get(DYNAMIC_HYDROGEN_ELECTRODE)
    if dhe is not None:
        changed = False
        types = _as_list(dhe.get("@type"))
        if H2KG_INSTRUMENT not in types:
            types.append(H2KG_INSTRUMENT)
            dhe["@type"] = types
            changed = True
        description = _first_literal(dhe.get(DCTERMS_DESCRIPTION))
        if not description:
            dhe[DCTERMS_DESCRIPTION] = [
                {
                    "@language": "en",
                    "@value": "An instrument corresponding to a dynamic hydrogen electrode and used as a reference electrode in electrochemical measurements.",
                }
            ]
            changed = True
        if changed:
            repairs.append(
                {
                    "iri": DYNAMIC_HYDROGEN_ELECTRODE,
                    "actions": ["added local Instrument type", "added ontology-style description"],
                }
            )
    applies_to_profile = items_by_iri.get(H2KG_APPLIES_TO_PROFILE)
    if applies_to_profile is None:
        items.append(
            {
                "@id": H2KG_APPLIES_TO_PROFILE,
                "@type": [OWL_ANNOTATION_PROPERTY],
                RDFS_LABEL: [
                    {
                        "@language": "en",
                        "@value": "appliesToProfile",
                    }
                ],
                DCTERMS_DESCRIPTION: [
                    {
                        "@language": "en",
                        "@value": "An annotation property stating which H2KG application profile or profiles explicitly include a term in their published module.",
                    }
                ],
            }
        )
        repairs.append(
            {
                "iri": H2KG_APPLIES_TO_PROFILE,
                "actions": ["added annotation property definition for profile-module tagging"],
            }
        )
    return repairs


def _replace_iri_reference(items: list[dict[str, Any]], source_iri: str, target_iri: str, message: str) -> dict[str, Any] | None:
    replacement_count = 0

    def rewrite(value: Any) -> Any:
        nonlocal replacement_count
        if isinstance(value, dict):
            updated: dict[str, Any] = {}
            for key, nested in value.items():
                if key == "@id" and nested == source_iri:
                    updated[key] = target_iri
                    replacement_count += 1
                else:
                    updated[key] = rewrite(nested)
            return updated
        if isinstance(value, list):
            return [rewrite(item) for item in value]
        return value

    for index, item in enumerate(items):
        items[index] = rewrite(item)

    if replacement_count:
        return {"iri": source_iri, "replacement_iri": target_iri, "actions": [message], "replacement_count": replacement_count}
    return None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value[:]
    return [value]


def _first_literal(values: Any) -> str:
    for value in _as_list(values):
        if isinstance(value, dict) and "@value" in value:
            text = str(value["@value"]).strip()
            if text:
                return text
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""
