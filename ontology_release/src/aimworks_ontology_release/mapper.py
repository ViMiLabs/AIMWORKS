from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .candidates import generate_candidates
from .hdo import generate_hdo_alignment_report
from .normalize import normalize_token
from .utils import (
    OWL_EQUIVALENT_CLASS,
    OWL_EQUIVALENT_PROPERTY,
    RDFS_SUBCLASS,
    RDFS_SUBPROPERTY,
    default_mapping_rules,
    dump_json,
    ensure_dir,
    local_name,
    try_load_yaml,
    write_text,
)

RELATION_MAP = {
    "owl:equivalentClass": OWL_EQUIVALENT_CLASS,
    "owl:equivalentProperty": OWL_EQUIVALENT_PROPERTY,
    "rdfs:subClassOf": RDFS_SUBCLASS,
    "rdfs:subPropertyOf": RDFS_SUBPROPERTY,
    "skos:exactMatch": "http://www.w3.org/2004/02/skos/core#exactMatch",
    "skos:closeMatch": "http://www.w3.org/2004/02/skos/core#closeMatch",
}

GENERIC_ELECTROCHEMICAL_MEASUREMENT_IRI = "https://w3id.org/emmo/domain/electrochemistry#electrochemistry_7729c34e_1ae9_403d_b933_1765885e7f29"
GENERIC_ELECTROCHEMICAL_MEASUREMENT_LABEL = normalize_token("Electrochemical measurement")
QUDT_SCAFFOLD_TARGETS = {
    "http://qudt.org/schema/qudt/QuantityValue",
    "http://qudt.org/schema/qudt/quantityValue",
}
DEPRECATION_MARKERS = ("obsolete", "deprecated", "deprecat", "deprected", "depreciated")
PROVENANCE_INDICATORS = (
    "provenance",
    "license",
    "creator",
    "issued",
    "identifier",
    "agent",
    "record",
    "metadata",
)
HDO_LOCAL_SCOPE_TOKENS = (
    "dataset",
    "data point",
    "metadata",
    "identifier",
    "pid",
    "record",
    "schema",
    "validation",
    "digital object",
    "information profile",
    "provenance",
    "specification",
    "software",
)
HDO_TARGET_SCOPE_TOKENS = (
    "dataset",
    "data",
    "metadata",
    "identifier",
    "schema",
    "validation",
    "profile",
    "file",
    "database",
    "repository",
    "software",
    "digital object",
    "digital system",
    "digital infrastructure",
    "specification",
    "fair data",
)


def propose_mappings(
    input_path: str | Path,
    output_dir: str | Path,
    config_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    output_dir = ensure_dir(Path(output_dir))
    reports_dir = ensure_dir(output_dir.parent / "reports")
    mappings_dir = ensure_dir(output_dir.parent / "mappings")
    config_path = Path(config_dir or Path(input_path).parent.parent / "config") / "mapping_rules.yaml"
    rules = try_load_yaml(config_path, default_mapping_rules())
    candidates = generate_candidates(input_path, output_dir, config_dir)
    thresholds = rules["policies"]
    manual = rules.get("manual_overrides", {})
    hdo_indicators = [normalize_token(text) for text in rules.get("term_hints", {}).get("hdo_indicators", [])]

    accepted: list[dict[str, Any]] = []
    exploratory: list[dict[str, Any]] = []
    rejected_counts: dict[str, int] = {}

    for candidate in candidates:
        local_fragment = local_name(candidate["local_iri"])
        override = manual.get(local_fragment)
        if override:
            accepted.append(
                {
                    **_public_row(candidate),
                    "relation": override["relation"],
                    "target_iri": override["target"],
                    "score": 0.99,
                    "status": "manual_override",
                    "rationale": override["rationale"],
                }
            )
            continue

        reject_reason = _reject_reason(candidate, hdo_indicators)
        if reject_reason:
            rejected_counts[reject_reason] = rejected_counts.get(reject_reason, 0) + 1
            exploratory.append(
                {
                    **_public_row(candidate),
                    "relation": "",
                    "status": f"rejected_{reject_reason}",
                    "rationale": _rejection_rationale(reject_reason),
                }
            )
            continue

        adjusted_score = _adjust_score(candidate, hdo_indicators)
        relation, rationale, accepted_candidate = _accepted_relation(candidate, adjusted_score, thresholds)
        row = {
            **_public_row(candidate),
            "score": adjusted_score,
            "relation": relation,
            "rationale": rationale,
            "status": "accepted" if accepted_candidate else "exploratory_candidate",
        }
        if accepted_candidate:
            accepted.append(row)
        else:
            exploratory.append(row)

    accepted = _dedupe_rows(accepted)
    exploratory = _dedupe_rows(exploratory)

    _write_review_csv(output_dir / "mapping_review.csv", accepted)
    _write_review_csv(output_dir / "mapping_exploratory.csv", exploratory)
    _write_alignments_ttl(mappings_dir / "alignments.ttl", accepted)
    summary = _mapping_summary(accepted, exploratory, rejected_counts)
    dump_json(reports_dir / "alignment_summary.json", summary)
    write_text(reports_dir / "alignment_report.md", _alignment_report(accepted, exploratory, summary))
    generate_hdo_alignment_report(input_path, accepted, reports_dir, config_dir)
    return accepted


def _public_row(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "local_iri": candidate["local_iri"],
        "local_label": candidate["local_label"],
        "local_kind": candidate["local_kind"],
        "target_iri": candidate["target_iri"],
        "target_label": candidate["target_label"],
        "target_kind": candidate["target_kind"],
        "source": candidate["source"],
        "score": candidate["score"],
    }


def _adjust_score(candidate: dict[str, Any], hdo_indicators: list[str]) -> float:
    adjusted_score = float(candidate["score"])
    if candidate.get("source") == "hdo" and _is_hdo_scoped_local_term(candidate, hdo_indicators):
        adjusted_score = round(min(0.995, adjusted_score + 0.08), 3)
    return adjusted_score


def _accepted_relation(candidate: dict[str, Any], adjusted_score: float, thresholds: dict[str, Any]) -> tuple[str, str, bool]:
    local_kind = candidate["local_kind"]
    target_kind = candidate["target_kind"]
    if adjusted_score >= thresholds["equivalence_threshold"]:
        relation = "owl:equivalentClass" if _maps_as_class(local_kind, target_kind) else "owl:equivalentProperty"
        return relation, "High lexical similarity and compatible kind support a strong equivalence proposal.", True
    if adjusted_score >= thresholds["subclass_threshold"]:
        relation = "rdfs:subClassOf" if _maps_as_class(local_kind, target_kind) else "rdfs:subPropertyOf"
        rationale = "Conservative anchoring favors specialization over strict equivalence."
        if candidate.get("source") == "hdo":
            rationale = "Conservative HDO anchoring favors specialization only for true data-governance and metadata-management concepts."
        return relation, rationale, True
    if adjusted_score >= thresholds["exact_match_threshold"]:
        return "skos:exactMatch", "Strong lexical match without enough evidence for OWL equivalence.", True
    if adjusted_score >= thresholds["close_match_threshold"]:
        rationale = "Filtered lexical similarity suggests a review-worthy soft alignment."
        if candidate.get("source") == "hdo":
            rationale = "Filtered HDO lexical similarity suggests a review-worthy soft alignment for a true data or metadata concept."
        return "skos:closeMatch", rationale, True
    return "", "Below the configured close-match threshold; kept only as exploratory output.", False


def _reject_reason(candidate: dict[str, Any], hdo_indicators: list[str]) -> str | None:
    if not _kind_compatible(candidate["local_kind"], candidate["target_kind"]):
        return "kind_mismatch"
    if _is_deprecated_target(candidate):
        return "deprecated_target"
    if candidate.get("source") == "hdo" and not _is_hdo_scoped_local_term(candidate, hdo_indicators):
        return "hdo_scope"
    if candidate.get("source") == "hdo" and not _is_hdo_target_compatible(candidate):
        return "hdo_scope"
    if candidate.get("source") in {"prov-o", "dcterms"} and not _is_provenance_scoped_local_term(candidate):
        return "metadata_scope"
    if candidate.get("source") == "qudt-schema" and _is_qudt_scaffold_reuse(candidate):
        return "qudt_scaffold"
    if candidate.get("source") == "emmo-electrochemistry" and _is_generic_electrochemical_measurement(candidate):
        return "generic_electrochemical_measurement"
    if candidate.get("source") == "chebi" and normalize_token(candidate["local_label"]) != normalize_token(candidate["target_label"]):
        return "chemical_non_exact"
    return None


def _kind_compatible(local_kind: str, target_kind: str) -> bool:
    if local_kind == "class":
        return target_kind == "class"
    if local_kind == "controlled_vocabulary_term":
        return target_kind == "class"
    if local_kind == "object_property":
        return target_kind == "object_property"
    if local_kind == "datatype_property":
        return target_kind == "datatype_property"
    return False


def _maps_as_class(local_kind: str, target_kind: str) -> bool:
    return local_kind in {"class", "controlled_vocabulary_term"} and target_kind == "class"


def _is_deprecated_target(candidate: dict[str, Any]) -> bool:
    text = normalize_token(f"{candidate.get('target_label', '')} {candidate.get('target_description', '')}")
    return any(marker in text for marker in DEPRECATION_MARKERS)


def _is_qudt_scaffold_reuse(candidate: dict[str, Any]) -> bool:
    if candidate["target_iri"] not in QUDT_SCAFFOLD_TARGETS:
        return False
    local_fragment = local_name(candidate["local_iri"])
    local_label = normalize_token(candidate["local_label"])
    return local_fragment != "hasQuantityValue" and "quantity value" not in local_label


def _is_generic_electrochemical_measurement(candidate: dict[str, Any]) -> bool:
    return candidate["target_iri"] == GENERIC_ELECTROCHEMICAL_MEASUREMENT_IRI or normalize_token(candidate["target_label"]) == GENERIC_ELECTROCHEMICAL_MEASUREMENT_LABEL


def _is_hdo_scoped_local_term(candidate: dict[str, Any], hdo_indicators: list[str]) -> bool:
    label = normalize_token(candidate.get("local_label", ""))
    description = normalize_token(candidate.get("local_description", ""))
    if not any(indicator and (indicator in label or indicator in description) for indicator in hdo_indicators):
        return False
    if not any(token in label or token in description for token in HDO_LOCAL_SCOPE_TOKENS):
        return False
    excluded = (
        "measurement",
        "instrument",
        "electrode",
        "solution",
        "acid",
        "hydroxide",
        "mass fraction",
        "ratio",
        "concentration",
        "temperature",
        "pressure",
        "duration",
        "property",
        "material",
        "process",
    )
    return not any(token in label for token in excluded)


def _is_hdo_target_compatible(candidate: dict[str, Any]) -> bool:
    target_label = normalize_token(candidate.get("target_label", ""))
    target_description = normalize_token(candidate.get("target_description", ""))
    return any(token in target_label or token in target_description for token in HDO_TARGET_SCOPE_TOKENS)


def _is_provenance_scoped_local_term(candidate: dict[str, Any]) -> bool:
    haystack = normalize_token(
        " ".join(
            [
                candidate.get("local_label", ""),
                candidate.get("local_description", ""),
                " ".join(candidate.get("local_predicates", [])),
            ]
        )
    )
    return any(token in haystack for token in PROVENANCE_INDICATORS)


def _dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row["local_iri"], row["target_iri"], row["status"])
        if key not in unique or float(row["score"]) > float(unique[key]["score"]):
            unique[key] = row
    return sorted(unique.values(), key=lambda item: (item["local_label"], -float(item["score"]), item["target_label"]))


def _mapping_summary(accepted: list[dict[str, Any]], exploratory: list[dict[str, Any]], rejected_counts: dict[str, int]) -> dict[str, Any]:
    accepted_by_relation = {
        "manual_override": sum(1 for row in accepted if row["status"] == "manual_override"),
        "exact_match": sum(1 for row in accepted if row["relation"] == "skos:exactMatch"),
        "subclass_anchor": sum(1 for row in accepted if row["relation"] in {"rdfs:subClassOf", "rdfs:subPropertyOf"}),
        "equivalence_anchor": sum(1 for row in accepted if row["relation"] in {"owl:equivalentClass", "owl:equivalentProperty"}),
        "close_match": sum(1 for row in accepted if row["relation"] == "skos:closeMatch"),
    }
    exploratory_by_status: dict[str, int] = {}
    for row in exploratory:
        exploratory_by_status[row["status"]] = exploratory_by_status.get(row["status"], 0) + 1
    return {
        "accepted_count": len(accepted),
        "exploratory_count": len(exploratory),
        "accepted_by_relation": accepted_by_relation,
        "rejected_by_rule": rejected_counts,
        "exploratory_by_status": exploratory_by_status,
        "accepted_by_source": _counts_by_field(accepted, "source"),
        "exploratory_by_source": _counts_by_field(exploratory, "source"),
    }


def _counts_by_field(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get(field, ""))
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _rejection_rationale(reason: str) -> str:
    messages = {
        "kind_mismatch": "Rejected because the local term kind and external target kind are not semantically compatible.",
        "deprecated_target": "Rejected because the external target is marked as deprecated or obsolete.",
        "hdo_scope": "Rejected because the local term is outside the narrow HDO data and metadata scope.",
        "metadata_scope": "Rejected because the local term is outside the provenance and publication-metadata scope.",
        "qudt_scaffold": "Rejected because QUDT quantity-value scaffolding is not a suitable target for this domain concept.",
        "generic_electrochemical_measurement": "Rejected because generic electrochemical measurement is too broad for automatic proposal here.",
        "chemical_non_exact": "Rejected because ChEBI mappings are limited to exact or manually curated chemical matches in this phase.",
    }
    return messages.get(reason, "Rejected by mapping policy.")


def _write_review_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    ensure_dir(path.parent)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "local_iri",
                "local_label",
                "local_kind",
                "relation",
                "target_iri",
                "target_label",
                "target_kind",
                "source",
                "score",
                "status",
                "rationale",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_alignments_ttl(path: Path, rows: list[dict[str, Any]]) -> None:
    lines = [
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .",
        "",
    ]
    for row in rows:
        relation_iri = RELATION_MAP.get(row["relation"])
        if not relation_iri:
            continue
        lines.append(f"<{row['local_iri']}> <{relation_iri}> <{row['target_iri']}> .")
    write_text(path, "\n".join(lines) + "\n")


def _alignment_report(accepted: list[dict[str, Any]], exploratory: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    accepted_examples = "\n".join(
        f"- `{row['local_label']}` -> `{row['relation']}` -> `{row['target_iri']}` ({row['score']})"
        for row in accepted[:25]
    )
    source_examples = []
    for source in sorted({row["source"] for row in accepted}):
        example_rows = [row for row in accepted if row["source"] == source][:5]
        if not example_rows:
            continue
        source_examples.append(
            f"### {source}\n\n"
            + "\n".join(
                f"- `{row['local_label']}` -> `{row['relation']}` -> `{row['target_label']}` ({row['score']})"
                for row in example_rows
            )
        )
    exploratory_examples = "\n".join(
        f"- `{row['local_label']}` -> `{row['target_label']}` [{row['status']}]"
        for row in exploratory[:25]
    )
    rejected_lines = "\n".join(
        f"- `{reason}`: {count}"
        for reason, count in summary["rejected_by_rule"].items()
    )
    return f"""# Alignment Report

## Summary

- Accepted review-ready mappings: {summary['accepted_count']}
- Exploratory mappings: {summary['exploratory_count']}
- Manual overrides: {summary['accepted_by_relation']['manual_override']}
- Accepted exact matches: {summary['accepted_by_relation']['exact_match']}
- Accepted subclass or subproperty anchors: {summary['accepted_by_relation']['subclass_anchor']}
- Accepted equivalence anchors: {summary['accepted_by_relation']['equivalence_anchor']}
- Accepted close matches: {summary['accepted_by_relation']['close_match']}

## Rejected Candidate Counts

{rejected_lines or '- No rule-based rejections were recorded.'}

## Representative Accepted Mappings

{accepted_examples or '- No accepted mappings generated.'}

## Accepted Mappings by Source

{chr(10).join(source_examples) or '- No accepted mappings grouped by source.'}

## Exploratory Output

Exploratory mappings are preserved in `output/review/mapping_exploratory.csv` for internal research only. They are excluded from the published alignment TTL and should not be treated as accepted ontology alignments.

{exploratory_examples or '- No exploratory mappings generated.'}

## Policy Notes

- HDO is restricted to true data, metadata, identifier, digital-object, schema, validation, and information-profile concepts.
- QUDT scaffold targets such as `QuantityValue` are excluded for domain concepts unless explicitly curated.
- ChEBI remains limited to exact or manually curated chemical matches.
- Generic electrochemical measurement anchors are blocked for automatic proposals unless explicitly curated.
"""
