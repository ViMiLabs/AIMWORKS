from __future__ import annotations

from pathlib import Path
from typing import Any

from .extract import extract_local_term_profiles
from .index import build_source_index
from .scorer import score_candidate


def generate_candidates(
    input_path: str | Path,
    output_dir: str | Path,
    config_dir: str | Path | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    local_terms = [
        term
        for term in extract_local_term_profiles(input_path, output_dir, config_dir)
        if term["is_local"] and term["kind"] in {"class", "object_property", "datatype_property", "controlled_vocabulary_term"}
    ]
    external_terms = build_source_index(config_dir)
    candidates: list[dict[str, Any]] = []
    for local in local_terms:
        scored: list[dict[str, Any]] = []
        for target in external_terms:
            score = score_candidate(local["label"], target["label"], local["kind"], target["kind"])
            if score <= 0.55:
                continue
            scored.append(
                {
                    "local_iri": local["iri"],
                    "local_label": local["label"],
                    "local_kind": local["kind"],
                    "target_iri": target["iri"],
                    "target_label": target["label"],
                    "target_kind": target["kind"],
                    "source": target["source"],
                    "score": round(score, 3),
                }
            )
        scored.sort(key=lambda row: row["score"], reverse=True)
        candidates.extend(scored[:limit])
    return candidates
