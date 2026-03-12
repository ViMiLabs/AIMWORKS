from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .normalize import normalize_label, token_set
from .sources import SourceRecord


@dataclass
class SourceIndex:
    records: list[SourceRecord]
    by_label: dict[str, list[SourceRecord]]
    by_token: dict[str, list[SourceRecord]]
    by_type: dict[str, list[SourceRecord]]


def build_source_index(records: list[SourceRecord]) -> SourceIndex:
    by_label: dict[str, list[SourceRecord]] = {}
    by_token: dict[str, list[SourceRecord]] = {}
    by_type: dict[str, list[SourceRecord]] = {}
    for record in records:
        key = normalize_label(record.label)
        by_label.setdefault(key, []).append(record)
        for synonym in record.synonyms:
            by_label.setdefault(normalize_label(synonym), []).append(record)
        for token in token_set(record.label):
            by_token.setdefault(token, []).append(record)
        for synonym in record.synonyms:
            for token in token_set(synonym):
                by_token.setdefault(token, []).append(record)
        by_type.setdefault(record.record_type, []).append(record)
    return SourceIndex(records=records, by_label=by_label, by_token=by_token, by_type=by_type)
