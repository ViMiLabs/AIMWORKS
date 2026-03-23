from __future__ import annotations

import re
from typing import Any

from .utils import (
    QUDT_NUMERIC_VALUE,
    QUDT_QUANTITY_KIND,
    QUDT_QUANTITY_VALUE,
    QUDT_UNIT,
    RDFS_COMMENT,
    RDFS_LABEL,
    SKOS_ALT_LABEL,
    SKOS_DEFINITION,
    SKOS_PREF_LABEL,
    humanize,
    local_name,
    normalize_token,
)


def value_list(item: dict[str, Any], key: str) -> list[Any]:
    raw = item.get(key, [])
    if isinstance(raw, list):
        return raw
    return [raw]


def literal_text(value: Any) -> str:
    if isinstance(value, dict):
        if "@value" in value:
            return str(value["@value"])
        if "@id" in value:
            return str(value["@id"])
    return str(value)


def first_literal(item: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        for value in value_list(item, key):
            text = literal_text(value).strip()
            if text:
                return text
    return ""


def best_label(item: dict[str, Any]) -> str:
    label = first_literal(item, [RDFS_LABEL, SKOS_PREF_LABEL, SKOS_ALT_LABEL])
    if label:
        return label
    identifier = str(item.get("@id", ""))
    return humanize(local_name(identifier))


def best_description(item: dict[str, Any]) -> str:
    return first_literal(
        item,
        [
            SKOS_DEFINITION,
            RDFS_COMMENT,
            "http://purl.org/dc/terms/description",
        ],
    )


def looks_like_ephemeral(identifier: str) -> bool:
    name = local_name(identifier)
    if re.fullmatch(r"[0-9._-]+", name):
        return True
    if len(re.findall(r"\d", name)) >= 4:
        return True
    if any(token in name.lower() for token in ["uuid", "sample_", "row_", "generated", "temp"]):
        return True
    return False


def looks_like_quantity_value(item: dict[str, Any]) -> bool:
    types = item.get("@type", [])
    type_values = types if isinstance(types, list) else [types]
    if QUDT_QUANTITY_VALUE in type_values:
        return True
    return any(key in item for key in [QUDT_NUMERIC_VALUE, QUDT_UNIT, QUDT_QUANTITY_KIND])


def lexical_signature(item: dict[str, Any]) -> str:
    return normalize_token(best_label(item))
