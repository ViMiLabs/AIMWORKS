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
    limit: int = 12,
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
                    "local_description": local.get("description", ""),
                    "local_kind": local["kind"],
                    "local_predicates": local.get("predicates", []),
                    "target_iri": target["iri"],
                    "target_label": target["label"],
                    "target_description": target.get("description", ""),
                    "target_kind": target["kind"],
                    "source": target["source"],
                    "score": round(score, 3),
                }
            )
        # RDF graph iteration order is not stable across parsers or operating
        # systems. Use explicit tie-breakers so reviewed mapping output is
        # reproducible in local builds and CI.
        scored.sort(
            key=lambda row: (
                -float(row["score"]),
                str(row["source"]),
                str(row["target_iri"]),
            )
        )
        candidates.extend(scored[:limit])
    return candidates
