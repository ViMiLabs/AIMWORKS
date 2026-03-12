from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

try:
    from rapidfuzz import fuzz
except Exception:  # pragma: no cover
    fuzz = None

from .extract import LocalTerm
from .normalize import normalize_label, token_set
from .sources import SourceRecord


@dataclass
class ScoredCandidate:
    record: SourceRecord
    score: float
    lexical_score: float
    token_overlap: float
    relation: str
    rationale: str


def lexical_similarity(left: str, right: str) -> float:
    if fuzz is not None:
        return float(fuzz.token_sort_ratio(left, right))
    return SequenceMatcher(a=left, b=right).ratio() * 100


def _relation_for(term: LocalTerm, record: SourceRecord, score: float, rules: dict[str, Any]) -> str:
    thresholds = rules.get("thresholds", {})
    relation_cfg = rules.get("relations", {})
    if term.term_type == "class":
        if score >= thresholds.get("equivalent", 96) and record.record_type == "class":
            return relation_cfg.get("strong_class", "owl:equivalentClass")
        if record.source_id in {"qudt_units", "qudt_quantitykinds", "chebi"} or term.category == "controlled_vocabulary_term":
            return "skos:exactMatch" if score >= thresholds.get("equivalent", 96) else relation_cfg.get("vocabulary", "skos:closeMatch")
        return relation_cfg.get("default_class", "rdfs:subClassOf")
    if term.term_type in {"object_property", "datatype_property", "annotation_property"}:
        if score >= thresholds.get("equivalent", 96):
            return relation_cfg.get("strong_property", "owl:equivalentProperty")
        return relation_cfg.get("default_property", "rdfs:subPropertyOf")
    return relation_cfg.get("vocabulary", "skos:closeMatch")


def score_candidate(term: LocalTerm, record: SourceRecord, rules: dict[str, Any]) -> ScoredCandidate:
    term_label = normalize_label(term.label or term.local_name)
    lexical_targets = [normalize_label(record.label), *[normalize_label(item) for item in record.synonyms]]
    lexical_scores = [lexical_similarity(term_label, candidate) for candidate in lexical_targets if candidate]
    lexical = max(lexical_scores) if lexical_scores else 0.0
    term_tokens = token_set(term.label or term.local_name)
    record_tokens = token_set(record.label)
    synonym_tokens = set().union(*(token_set(item) for item in record.synonyms)) if record.synonyms else set()
    overlap_base = record_tokens | synonym_tokens
    overlap = len(term_tokens & overlap_base) / max(len(term_tokens | overlap_base), 1)

    weights = rules.get("weights", {})
    source_boosts = rules.get("source_boosts", {})
    score = (
        lexical * float(weights.get("lexical_similarity", 0.65))
        + overlap * 100 * float(weights.get("token_overlap", 0.15))
        + source_boosts.get(record.source_id, record.priority) * 100 * float(weights.get("source_priority", 0.2))
    )

    label_text = term_label
    lexical_policies = rules.get("lexical_policies", {})
    if any(token in label_text for token in lexical_policies.get("chemical_tokens", [])) and record.source_id == "chebi":
        score += 8
    if any(token in label_text for token in lexical_policies.get("quantity_kind_tokens", [])) and record.source_id == "qudt_quantitykinds":
        score += 8
    if any(token in label_text for token in lexical_policies.get("unit_tokens", [])) and record.source_id == "qudt_units":
        score += 8
    if any(token in label_text for token in lexical_policies.get("provenance_tokens", [])) and record.source_id in {"provo", "dcterms", "vann"}:
        score += 8
    if "reference electrode" in label_text and record.source_id == "echo":
        score += 10
    if term.term_type == "class" and record.source_id in {"emmo_core", "echo"}:
        score += 4

    relation = _relation_for(term, record, score, rules)
    rationale = f"lexical={lexical:.1f}; token_overlap={overlap:.2f}; source={record.source_id}"
    return ScoredCandidate(record=record, score=round(score, 2), lexical_score=round(lexical, 2), token_overlap=round(overlap, 3), relation=relation, rationale=rationale)
