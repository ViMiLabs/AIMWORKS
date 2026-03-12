from __future__ import annotations

from typing import Any

from .extract import LocalTerm
from .index import SourceIndex
from .normalize import normalize_label, token_set
from .sources import SourceRecord


def compatible_types(term_type: str, rules: dict[str, Any]) -> set[str]:
    compatibility = rules.get("type_compatibility", {})
    return set(compatibility.get(term_type, [term_type]))


def generate_candidates(
    term: LocalTerm,
    source_index: SourceIndex,
    rules: dict[str, Any],
    limit: int = 5,
) -> list[SourceRecord]:
    wanted_types = compatible_types(term.term_type, rules)
    tokens = token_set(term.label or term.local_name)
    candidate_pool: list[SourceRecord] = []

    exact = source_index.by_label.get(normalize_label(term.label), []) + source_index.by_label.get(normalize_label(term.local_name), [])
    candidate_pool.extend(exact)
    for token in tokens:
        candidate_pool.extend(source_index.by_token.get(token, []))
    if not candidate_pool:
        for record_type in wanted_types:
            candidate_pool.extend(source_index.by_type.get(record_type, []))

    unique: dict[str, SourceRecord] = {}
    for record in candidate_pool:
        if record.record_type in wanted_types:
            unique.setdefault(record.iri, record)
    return list(unique.values())[: max(limit * 8, limit)]
