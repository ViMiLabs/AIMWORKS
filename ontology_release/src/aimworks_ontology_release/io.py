from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .utils import COMMON_CONTEXT, dump_json, ensure_dir, load_json, write_text


def load_json_document(path: str | Path) -> Any:
    return load_json(Path(path))


def iter_document_items(document: Any) -> list[dict[str, Any]]:
    if isinstance(document, list):
        return [item for item in document if isinstance(item, dict)]
    if isinstance(document, dict):
        graph = document.get("@graph")
        if isinstance(graph, list):
            return [item for item in graph if isinstance(item, dict)]
        return [document]
    return []


def merge_document_items(document: Any) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    anonymous: list[dict[str, Any]] = []
    for item in iter_document_items(document):
        identifier = item.get("@id")
        if not isinstance(identifier, str):
            anonymous.append(item)
            continue
        current = merged.setdefault(identifier, {"@id": identifier})
        for key, value in item.items():
            if key == "@id":
                continue
            existing = current.get(key)
            if existing is None:
                current[key] = value
                continue
            current[key] = _merge_values(existing, value)
    return list(merged.values()) + anonymous


def _merge_values(left: Any, right: Any) -> Any:
    left_values = left if isinstance(left, list) else [left]
    right_values = right if isinstance(right, list) else [right]
    result = left_values[:]
    for value in right_values:
        if value not in result:
            result.append(value)
    return result


def dump_jsonld_items(path: str | Path, items: list[dict[str, Any]]) -> Path:
    return dump_json(Path(path), {"@context": COMMON_CONTEXT, "@graph": items})


def prefixify(uri: str) -> str:
    for prefix, base in COMMON_CONTEXT.items():
        if uri.startswith(base):
            local = uri[len(base) :]
            if local and all(ch.isalnum() or ch in "._-" for ch in local):
                return f"{prefix}:{local}"
    return f"<{uri}>"


def literal_to_turtle(value: Any) -> str:
    if isinstance(value, dict):
        if "@id" in value:
            return prefixify(str(value["@id"]))
        literal = json.dumps(str(value.get("@value", "")), ensure_ascii=False)
        language = value.get("@language")
        datatype = value.get("@type")
        if language:
            return f"{literal}@{language}"
        if datatype:
            return f"{literal}^^{prefixify(str(datatype))}"
        return literal
    if isinstance(value, str) and value.startswith("http"):
        return prefixify(value)
    return json.dumps(str(value), ensure_ascii=False)


def items_to_turtle(items: list[dict[str, Any]]) -> str:
    prefixes = "\n".join(f"@prefix {prefix}: <{base}> ." for prefix, base in COMMON_CONTEXT.items())
    blocks: list[str] = [prefixes, ""]
    for item in items:
        identifier = item.get("@id")
        if not isinstance(identifier, str):
            continue
        predicate_chunks: list[str] = []
        types = item.get("@type")
        if types:
            type_values = types if isinstance(types, list) else [types]
            predicate_chunks.append("a " + ", ".join(literal_to_turtle(value) for value in type_values))
        for key, value in item.items():
            if key in {"@id", "@type"}:
                continue
            values = value if isinstance(value, list) else [value]
            predicate_chunks.append(f"{prefixify(key)} " + ", ".join(literal_to_turtle(entry) for entry in values))
        if not predicate_chunks:
            blocks.append(f"{prefixify(identifier)} .")
        else:
            blocks.append(f"{prefixify(identifier)}\n  " + " ;\n  ".join(predicate_chunks) + " .")
            blocks.append("")
    return "\n".join(blocks).strip() + "\n"


def dump_turtle_items(path: str | Path, items: list[dict[str, Any]]) -> Path:
    return write_text(Path(path), items_to_turtle(items))


def copy_file(source: str | Path, target: str | Path) -> Path:
    ensure_dir(Path(target).parent)
    shutil.copy2(source, target)
    return Path(target)
