from __future__ import annotations

from difflib import SequenceMatcher

from .normalize import normalize_token


def lexical_score(left: str, right: str) -> float:
    left_norm = normalize_token(left)
    right_norm = normalize_token(right)
    if not left_norm or not right_norm:
        return 0.0
    try:
        from rapidfuzz import fuzz  # type: ignore

        return fuzz.token_sort_ratio(left_norm, right_norm) / 100.0
    except Exception:
        return SequenceMatcher(a=left_norm, b=right_norm).ratio()


def score_candidate(local_label: str, target_label: str, local_kind: str, target_kind: str) -> float:
    if not local_kind.startswith(target_kind.split("_")[0]) and local_kind != target_kind:
        compatible = {
            ("class", "class"),
            ("object_property", "object_property"),
            ("datatype_property", "datatype_property"),
            ("controlled_vocabulary_term", "class"),
            ("controlled_vocabulary_term", "object_property"),
        }
        if (local_kind, target_kind) not in compatible:
            return 0.0
    base = lexical_score(local_label, target_label)
    if local_label.lower() == target_label.lower():
        base += 0.08
    return min(base, 1.0)
