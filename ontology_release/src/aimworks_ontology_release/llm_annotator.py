from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any

from .classify import classify_resources
from .io import load_json_document, merge_document_items
from .normalize import best_description, best_label
from .utils import SKOS_DEFINITION, ensure_dir, local_name, write_text


def draft_annotations(
    input_path: str | Path,
    output_dir: str | Path,
    draft_llm: bool = False,
    config_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    output_dir = ensure_dir(Path(output_dir))
    items = {item["@id"]: item for item in merge_document_items(load_json_document(input_path)) if isinstance(item.get("@id"), str)}
    classifications = [entry for entry in classify_resources(input_path, output_dir, Path(config_path).parent if config_path else None) if entry.kind in {"class", "object_property", "datatype_property"}]
    rows: list[dict[str, Any]] = []
    for entry in classifications:
        item = items[entry.iri]
        if item.get(SKOS_DEFINITION):
            continue
        label = best_label(item)
        heuristic_definition = f"{label} is a release-ready H2KG {entry.kind.replace('_', ' ')} that should remain reviewable and human-readable."
        heuristic_comment = f"Drafted annotation for {local_name(entry.iri)} based on local term structure and ontology scope."
        source = "heuristic"
        if draft_llm:
            llm_result = _call_provider(label, entry.kind, best_description(item), config_path)
            heuristic_definition = llm_result["definition"]
            heuristic_comment = llm_result["comment"]
            source = llm_result["source"]
        rows.append(
            {
                "iri": entry.iri,
                "label": label,
                "kind": entry.kind,
                "draft_definition": heuristic_definition,
                "draft_comment": heuristic_comment,
                "source": source,
                "approved": "no",
            }
        )
    _write_review_files(output_dir, rows)
    return rows


def apply_approved_annotations(*_: Any, **__: Any) -> int:
    return 0


def _call_provider(label: str, kind: str, description: str, config_path: str | Path | None) -> dict[str, str]:
    base_url = None
    api_key = None
    model = "gpt-4.1-mini"
    if config_path and Path(config_path).exists():
        try:
            import yaml  # type: ignore

            with Path(config_path).open("r", encoding="utf-8") as handle:
                config = yaml.safe_load(handle) or {}
            provider = config.get("provider", {})
            base_url = provider.get("base_url")
            api_key = os.getenv(provider.get("api_key_env", "OPENAI_API_KEY"))
            model = provider.get("model", model)
        except Exception:
            pass
    if not base_url or not api_key:
        return {
            "definition": f"{label} is a reviewed draft description for an H2KG {kind.replace('_', ' ')}.",
            "comment": f"No live LLM provider was configured, so this draft was produced from local heuristics for {label}.",
            "source": "heuristic_fallback",
        }
    try:
        import requests  # type: ignore

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "Draft concise ontology annotations for review. Return strict JSON with keys definition and comment.",
                },
                {
                    "role": "user",
                    "content": f"Label: {label}\nKind: {kind}\nExisting description: {description or 'none'}",
                },
            ],
            "temperature": 0.1,
        }
        response = requests.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=45,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        data = json.loads(content)
        return {
            "definition": str(data["definition"]),
            "comment": str(data["comment"]),
            "source": "llm",
        }
    except Exception:
        return {
            "definition": f"{label} is a reviewed draft description for an H2KG {kind.replace('_', ' ')}.",
            "comment": f"LLM drafting fell back to a local draft for {label}.",
            "source": "heuristic_fallback",
        }


def _write_review_files(output_dir: Path, rows: list[dict[str, Any]]) -> None:
    csv_path = output_dir / "annotation_drafts.csv"
    jsonl_path = output_dir / "annotation_drafts.jsonl"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["iri", "label", "kind", "draft_definition", "draft_comment", "source", "approved"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    lines = [json.dumps(row, ensure_ascii=False) for row in rows]
    write_text(jsonl_path, "\n".join(lines) + ("\n" if lines else ""))
