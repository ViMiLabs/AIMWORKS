from __future__ import annotations

from pathlib import Path
from typing import Any

from .classify import classify_resources
from .io import load_json_document, merge_document_items
from .normalize import best_description, best_label


def extract_local_term_profiles(
    input_path: str | Path,
    output_dir: str | Path,
    config_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    classifications = {entry.iri: entry for entry in classify_resources(input_path, output_dir, config_dir)}
    document = load_json_document(input_path)
    merged = merge_document_items(document)
    profiles: list[dict[str, Any]] = []
    for item in merged:
        identifier = item.get("@id")
        if not isinstance(identifier, str) or identifier not in classifications:
            continue
        info = classifications[identifier]
        profiles.append(
            {
                "iri": identifier,
                "label": best_label(item),
                "description": best_description(item),
                "kind": info.kind,
                "is_local": info.is_local,
                "predicates": sorted(key for key in item.keys() if key not in {"@id", "@type"}),
            }
        )
    return profiles
