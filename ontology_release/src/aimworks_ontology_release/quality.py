from __future__ import annotations

import copy
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ID = "@id"
TYPE = "@type"
RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"
RDFS_COMMENT = "http://www.w3.org/2000/01/rdf-schema#comment"
SKOS_ALTLABEL = "http://www.w3.org/2004/02/skos/core#altLabel"
SKOS_DEFINITION = "http://www.w3.org/2004/02/skos/core#definition"
LOCAL_NS = "https://w3id.org/h2kg/hydrogen-ontology#"

NUMERIC_SUFFIX = re.compile(r"^(?P<base>.+)_(?P<suffix>\d+)$")
TABLE_FIGURE_PATTERN = re.compile(r"^(?:table|figure|fig\.?|scheme|eq\.?|equation)\s*[a-z0-9.-]+$", re.IGNORECASE)
PURE_NUMBER_PATTERN = re.compile(r"^[+-]?\d+(?:\.\d+)?$")
VALUE_UNIT_PATTERN = re.compile(
    r"""
    \b\d+(?:\.\d+)?\s*
    (?:
        %|
        °C|degC|K|
        mV|V|kV|keV|eV|
        nA|uA|µA|mA|A|
        nm|um|µm|mm|cm|m|cm2|cm\^2|m2|
        s|ms|min|h|hr|hrs|
        rpm|Hz|kHz|MHz|GHz|
        Pa|kPa|MPa|bar|mbar|
        mol|mmol|M|mM|
        wt%|vol%|at%|
        sccm|L|mL
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)
CONCENTRATION_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s*(?:M|mM|mol\/L|mmol\/L)\b", re.IGNORECASE)
GENERIC_UNIT_ONLY = {
    "v",
    "mv",
    "kv",
    "ev",
    "kev",
    "a",
    "ma",
    "ua",
    "µa",
    "na",
    "nm",
    "um",
    "µm",
    "mm",
    "cm",
    "m",
    "cm2",
    "cm^2",
    "m2",
    "s",
    "ms",
    "min",
    "h",
    "hr",
    "hrs",
    "rpm",
    "hz",
    "khz",
    "mhz",
    "ghz",
    "pa",
    "kpa",
    "mpa",
    "bar",
    "mbar",
    "mol",
    "mmol",
    "m",
    "mm",
    "ml",
    "l",
    "wt%",
    "vol%",
    "at%",
    "sccm",
}
RICHNESS_PREDICATES = (SKOS_DEFINITION, RDFS_COMMENT, SKOS_ALTLABEL)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _literal_text(value: Any) -> str:
    if isinstance(value, dict):
        if "@value" in value:
            return str(value["@value"])
        if "@id" in value:
            return str(value["@id"])
    return str(value)


def _norm_text(value: Any) -> str:
    return re.sub(r"\s+", " ", _literal_text(value)).strip().casefold()


def _json_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _unique_values(values: list[Any]) -> list[Any]:
    seen: set[str] = set()
    output: list[Any] = []
    for value in values:
        key = _json_key(value)
        if key in seen:
            continue
        seen.add(key)
        output.append(copy.deepcopy(value))
    return output


def _node_id(node: dict[str, Any]) -> str:
    raw = node.get(ID, "")
    return raw if isinstance(raw, str) else ""


def _local_name(iri: str) -> str:
    if "#" in iri:
        return iri.rsplit("#", 1)[-1]
    return iri.rsplit("/", 1)[-1]


def _strip_numeric_suffix(iri: str) -> str:
    match = NUMERIC_SUFFIX.match(iri)
    return match.group("base") if match else iri


def _is_local_named_term(iri: str) -> bool:
    return iri.startswith(LOCAL_NS) and not _local_name(iri).startswith("_")


def _node_types(node: dict[str, Any]) -> list[str]:
    return sorted({_literal_text(value) for value in _as_list(node.get(TYPE)) if _literal_text(value).strip()})


def _node_labels(node: dict[str, Any]) -> list[Any]:
    return _as_list(node.get(RDFS_LABEL))


def _node_alt_labels(node: dict[str, Any]) -> list[Any]:
    return _as_list(node.get(SKOS_ALTLABEL))


def _iter_ref_ids(value: Any) -> list[str]:
    refs: list[str] = []
    if isinstance(value, dict):
        ref = value.get("@id")
        if isinstance(ref, str):
            refs.append(ref)
        for nested in value.values():
            refs.extend(_iter_ref_ids(nested))
    elif isinstance(value, list):
        for item in value:
            refs.extend(_iter_ref_ids(item))
    return refs


def _edge_counts(nodes: list[dict[str, Any]]) -> tuple[dict[str, int], dict[str, int]]:
    inbound: Counter[str] = Counter()
    outbound: Counter[str] = Counter()
    ids = {_node_id(node) for node in nodes if _node_id(node)}
    for node in nodes:
        source_id = _node_id(node)
        if not source_id:
            continue
        for key, value in node.items():
            if key == ID:
                continue
            refs = [ref for ref in _iter_ref_ids(value) if ref in ids]
            outbound[source_id] += len(refs)
            for ref in refs:
                inbound[ref] += 1
    return dict(inbound), dict(outbound)


def _node_score(node: dict[str, Any], inbound: dict[str, int], outbound: dict[str, int]) -> int:
    iri = _node_id(node)
    description_score = sum(6 for key in (SKOS_DEFINITION, RDFS_COMMENT) if _as_list(node.get(key)))
    alt_label_score = min(len(_node_alt_labels(node)), 6)
    label_score = 4 if _node_labels(node) else 0
    type_score = 4 if _node_types(node) else 0
    edge_score = inbound.get(iri, 0) + outbound.get(iri, 0)
    return description_score + alt_label_score + label_score + type_score + edge_score


def _term_pair_reason(base: dict[str, Any], duplicate: dict[str, Any]) -> tuple[str, list[str]]:
    reasons = ["Local name matches after numeric suffix stripping."]
    base_types = _node_types(base)
    duplicate_types = _node_types(duplicate)
    if base_types and duplicate_types and base_types != duplicate_types:
        reasons.append("Type sets differ.")
        return "review", reasons
    if base_types == duplicate_types and base_types:
        reasons.append("Type sets match.")
    base_labels = {_norm_text(value) for value in _node_labels(base)}
    duplicate_labels = {_norm_text(value) for value in _node_labels(duplicate)}
    if base_labels and duplicate_labels and base_labels == duplicate_labels:
        reasons.append("Primary labels match.")
    elif base_labels and duplicate_labels and base_labels.isdisjoint(duplicate_labels):
        reasons.append("Primary labels differ; keeping as review only if types also differ.")
    return "auto_merge", reasons


def _candidate_helper_mappings(base: dict[str, Any], duplicate: dict[str, Any]) -> dict[str, str]:
    mappings: dict[str, str] = {}
    base_targets: dict[str, list[str]] = defaultdict(list)
    duplicate_targets: dict[str, list[str]] = defaultdict(list)
    for key, value in base.items():
        if key == ID:
            continue
        base_targets[key].extend([ref for ref in _iter_ref_ids(value) if ref.startswith(LOCAL_NS)])
    for key, value in duplicate.items():
        if key == ID:
            continue
        duplicate_targets[key].extend([ref for ref in _iter_ref_ids(value) if ref.startswith(LOCAL_NS)])
    for key, dup_refs in duplicate_targets.items():
        if key not in base_targets:
            continue
        base_refs = base_targets[key]
        base_by_stem = {_strip_numeric_suffix(ref): ref for ref in base_refs}
        for dup_ref in dup_refs:
            stem = _strip_numeric_suffix(dup_ref)
            target = base_by_stem.get(stem)
            if target and target != dup_ref:
                mappings[dup_ref] = target
    return mappings


def _rewrite_value(value: Any, mapping: dict[str, str], counter: Counter[str]) -> Any:
    if isinstance(value, dict):
        updated = {}
        for key, nested in value.items():
            if key == "@id" and isinstance(nested, str) and nested in mapping:
                counter[nested] += 1
                updated[key] = mapping[nested]
            else:
                updated[key] = _rewrite_value(nested, mapping, counter)
        return updated
    if isinstance(value, list):
        return [_rewrite_value(item, mapping, counter) for item in value]
    return value


def _rewrite_node_references(node: dict[str, Any], mapping: dict[str, str], counter: Counter[str]) -> dict[str, Any]:
    updated: dict[str, Any] = {}
    for key, value in node.items():
        if key == ID:
            updated[key] = value
            continue
        updated[key] = _rewrite_value(value, mapping, counter)
    return updated


def _merge_lists(left: list[Any], right: list[Any]) -> list[Any]:
    return _unique_values(left + right)


def _merge_node_into(target: dict[str, Any], source: dict[str, Any]) -> list[Any]:
    extra_labels = []
    for label in _node_labels(source):
        if not any(_norm_text(label) == _norm_text(existing) for existing in _node_labels(target)):
            extra_labels.append(copy.deepcopy(label))
    source_alt = _node_alt_labels(source)
    for key, value in source.items():
        if key in {ID, RDFS_LABEL, SKOS_ALTLABEL}:
            continue
        if key == TYPE:
            target[key] = _merge_lists(_as_list(target.get(key)), _as_list(value))
            continue
        if key not in target:
            target[key] = copy.deepcopy(value)
            continue
        left = _as_list(target.get(key))
        right = _as_list(value)
        if left or right:
            target[key] = _merge_lists(left, right)
    if source_alt:
        target[SKOS_ALTLABEL] = _merge_lists(_node_alt_labels(target), source_alt)
    return extra_labels


def _is_paper_specific_alt_label(text: str) -> tuple[bool, str]:
    stripped = re.sub(r"\s+", " ", text).strip()
    if not stripped:
        return True, "empty"
    lowered = stripped.casefold()
    if TABLE_FIGURE_PATTERN.match(stripped):
        return True, "table_figure_reference"
    if PURE_NUMBER_PATTERN.match(stripped):
        return True, "numeric_literal"
    if lowered in GENERIC_UNIT_ONLY:
        return True, "unit_only"
    if VALUE_UNIT_PATTERN.search(stripped):
        return True, "value_with_unit"
    if CONCENTRATION_PATTERN.search(stripped):
        return True, "concentration_literal"
    if "%" in stripped and re.search(r"\d", stripped):
        return True, "percentage_literal"
    return False, ""


def _clean_labels(node: dict[str, Any], removal_counter: Counter[str], removed_examples: list[dict[str, str]]) -> None:
    primary_labels = _unique_values(_node_labels(node))
    extra_primary = primary_labels[1:]
    if primary_labels:
        node[RDFS_LABEL] = [primary_labels[0]]
    elif RDFS_LABEL in node:
        node.pop(RDFS_LABEL, None)

    alt_candidates = _node_alt_labels(node) + extra_primary
    preferred_norm = {_norm_text(value) for value in primary_labels[:1]}
    kept: list[Any] = []
    seen_norm: set[str] = set()
    for value in alt_candidates:
        text = _literal_text(value).strip()
        norm = _norm_text(value)
        if not norm or norm in preferred_norm or norm in seen_norm:
            removal_counter["duplicate_or_same_as_label"] += 1
            if len(removed_examples) < 80:
                removed_examples.append({"term": _node_id(node), "label": text, "reason": "duplicate_or_same_as_label"})
            continue
        is_bad, reason = _is_paper_specific_alt_label(text)
        if is_bad:
            removal_counter[reason] += 1
            if len(removed_examples) < 80:
                removed_examples.append({"term": _node_id(node), "label": text, "reason": reason})
            continue
        kept.append(copy.deepcopy(value))
        seen_norm.add(norm)
    if kept:
        node[SKOS_ALTLABEL] = kept
    else:
        node.pop(SKOS_ALTLABEL, None)


def _payload_nodes(payload: Any) -> tuple[list[dict[str, Any]], str]:
    if isinstance(payload, list):
        return payload, "list"
    if isinstance(payload, dict) and isinstance(payload.get("@graph"), list):
        return payload["@graph"], "graph"
    raise ValueError("JSON-LD payload must be a list of nodes or an object containing @graph.")


def _rebuild_payload(original: Any, nodes: list[dict[str, Any]], payload_kind: str) -> Any:
    if payload_kind == "list":
        return nodes
    updated = copy.deepcopy(original)
    updated["@graph"] = nodes
    return updated


def clean_jsonld_payload(payload: Any, source_name: str = "") -> tuple[Any, dict[str, Any]]:
    original_nodes, payload_kind = _payload_nodes(payload)
    nodes = copy.deepcopy(original_nodes)
    inbound, outbound = _edge_counts(nodes)
    nodes_by_id = {_node_id(node): node for node in nodes if _node_id(node)}

    grouped_duplicates: dict[str, list[str]] = defaultdict(list)
    for iri in list(nodes_by_id):
        if not _is_local_named_term(iri):
            continue
        match = NUMERIC_SUFFIX.match(iri)
        if not match:
            continue
        base_iri = match.group("base")
        if base_iri in nodes_by_id:
            grouped_duplicates[base_iri].append(iri)

    auto_merges: list[dict[str, Any]] = []
    review_pairs: list[dict[str, Any]] = []
    reference_mapping: dict[str, str] = {}
    helper_mapping: dict[str, str] = {}
    for base_iri, duplicate_iris in sorted(grouped_duplicates.items()):
        base_node = nodes_by_id[base_iri]
        for duplicate_iri in sorted(duplicate_iris):
            duplicate_node = nodes_by_id[duplicate_iri]
            decision, reasons = _term_pair_reason(base_node, duplicate_node)
            pair = {
                "canonical_iri": base_iri,
                "duplicate_iri": duplicate_iri,
                "decision": decision,
                "reasons": reasons,
                "canonical_types": _node_types(base_node),
                "duplicate_types": _node_types(duplicate_node),
                "canonical_label": _literal_text(_node_labels(base_node)[0]) if _node_labels(base_node) else "",
                "duplicate_label": _literal_text(_node_labels(duplicate_node)[0]) if _node_labels(duplicate_node) else "",
                "canonical_score": _node_score(base_node, inbound, outbound),
                "duplicate_score": _node_score(duplicate_node, inbound, outbound),
                "canonical_inbound": inbound.get(base_iri, 0),
                "duplicate_inbound": inbound.get(duplicate_iri, 0),
                "canonical_outbound": outbound.get(base_iri, 0),
                "duplicate_outbound": outbound.get(duplicate_iri, 0),
            }
            if decision == "auto_merge":
                auto_merges.append(pair)
                reference_mapping[duplicate_iri] = base_iri
                helper_mapping.update(_candidate_helper_mappings(base_node, duplicate_node))
            else:
                review_pairs.append(pair)

    rewrite_counter: Counter[str] = Counter()
    all_mapping = {**helper_mapping, **reference_mapping}
    if all_mapping:
        nodes = [_rewrite_node_references(node, all_mapping, rewrite_counter) for node in nodes]
        nodes_by_id = {_node_id(node): node for node in nodes if _node_id(node)}

    removed_node_ids: set[str] = set()
    merged_helper_nodes = 0
    for pair in auto_merges:
        canonical = nodes_by_id.get(pair["canonical_iri"])
        duplicate = nodes_by_id.get(pair["duplicate_iri"])
        if canonical is None or duplicate is None:
            continue
        extra_labels = _merge_node_into(canonical, duplicate)
        if extra_labels:
            canonical[SKOS_ALTLABEL] = _merge_lists(_node_alt_labels(canonical), extra_labels)
        removed_node_ids.add(pair["duplicate_iri"])

    for duplicate_iri, canonical_iri in helper_mapping.items():
        canonical = nodes_by_id.get(canonical_iri)
        duplicate = nodes_by_id.get(duplicate_iri)
        if canonical is None or duplicate is None or duplicate_iri in removed_node_ids:
            continue
        _merge_node_into(canonical, duplicate)
        removed_node_ids.add(duplicate_iri)
        merged_helper_nodes += 1

    cleaned_nodes = [node for node in nodes if _node_id(node) not in removed_node_ids]

    alt_label_removals: Counter[str] = Counter()
    removed_examples: list[dict[str, str]] = []
    for node in cleaned_nodes:
        iri = _node_id(node)
        if _is_local_named_term(iri):
            _clean_labels(node, alt_label_removals, removed_examples)

    suspicious_remaining: list[dict[str, str]] = []
    for node in cleaned_nodes:
        iri = _node_id(node)
        if not _is_local_named_term(iri):
            continue
        for value in _node_alt_labels(node):
            text = _literal_text(value).strip()
            if re.search(r"\d", text) or "_" in text:
                suspicious_remaining.append({"term": iri, "label": text})
                if len(suspicious_remaining) >= 60:
                    break
        if len(suspicious_remaining) >= 60:
            break

    rebuilt = _rebuild_payload(payload, cleaned_nodes, payload_kind)
    report = {
        "source": source_name,
        "status": "cleaned",
        "duplicate_term_pairs_detected": sum(len(values) for values in grouped_duplicates.values()),
        "auto_merged_terms": len(auto_merges),
        "manual_review_pairs": len(review_pairs),
        "helper_nodes_merged": merged_helper_nodes,
        "reference_rewrites": sum(rewrite_counter.values()),
        "alt_labels_removed": int(sum(alt_label_removals.values())),
        "alt_label_removal_reasons": dict(sorted(alt_label_removals.items())),
        "removed_alt_label_examples": removed_examples,
        "review_pairs": review_pairs[:40],
        "auto_merge_examples": auto_merges[:40],
        "suspicious_remaining_alt_labels": suspicious_remaining,
        "changed": bool(auto_merges or removed_node_ids or alt_label_removals),
    }
    return rebuilt, report


def clean_jsonld_file(path: Path, write_back: bool = True) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cleaned_payload, report = clean_jsonld_payload(payload, source_name=str(path))
    if write_back and report.get("changed"):
        path.write_text(json.dumps(cleaned_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def write_quality_outputs(report: dict[str, Any], root: Path) -> None:
    json_path = root / "output" / "reports" / "term_quality_report.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [
        "# Term Quality Report",
        "",
        f"- Source: `{report.get('source', '')}`",
        f"- Status: `{report.get('status', 'unknown')}`",
        f"- Duplicate term pairs detected: **{report.get('duplicate_term_pairs_detected', 0)}**",
        f"- Auto-merged terms: **{report.get('auto_merged_terms', 0)}**",
        f"- Manual review pairs: **{report.get('manual_review_pairs', 0)}**",
        f"- Helper nodes merged: **{report.get('helper_nodes_merged', 0)}**",
        f"- Reference rewrites: **{report.get('reference_rewrites', 0)}**",
        f"- Alt labels removed: **{report.get('alt_labels_removed', 0)}**",
        "",
    ]
    if report.get("alt_label_removal_reasons"):
        lines.extend(["## Alt Label Removal Reasons", ""])
        for reason, count in sorted(report["alt_label_removal_reasons"].items()):
            lines.append(f"- {reason}: {count}")
        lines.append("")
    if report.get("review_pairs"):
        lines.extend(["## Manual Review Pairs", ""])
        for row in report["review_pairs"]:
            lines.append(
                f"- `{row['duplicate_iri']}` -> `{row['canonical_iri']}`: {', '.join(row.get('reasons', []))}"
            )
        lines.append("")
    if report.get("removed_alt_label_examples"):
        lines.extend(["## Removed Alt Label Examples", ""])
        for row in report["removed_alt_label_examples"][:20]:
            lines.append(f"- `{row['term']}` removed `{row['label']}` ({row['reason']})")
        lines.append("")
    if report.get("suspicious_remaining_alt_labels"):
        lines.extend(["## Suspicious Remaining Alt Labels", ""])
        for row in report["suspicious_remaining_alt_labels"][:20]:
            lines.append(f"- `{row['term']}` still has `{row['label']}`")
        lines.append("")
    md_path = root / "output" / "reports" / "term_quality_report.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
