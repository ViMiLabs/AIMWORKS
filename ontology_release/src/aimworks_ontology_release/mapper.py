from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .candidates import generate_candidates
from .normalize import normalize_token
from .utils import (
    OWL_EQUIVALENT_CLASS,
    OWL_EQUIVALENT_PROPERTY,
    RDFS_SUBCLASS,
    RDFS_SUBPROPERTY,
    SKOS_DEFINITION,
    default_mapping_rules,
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


def propose_mappings(
    input_path: str | Path,
    output_dir: str | Path,
    config_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    output_dir = ensure_dir(Path(output_dir))
    config_path = Path(config_dir or Path(input_path).parent.parent / "config") / "mapping_rules.yaml"
    rules = try_load_yaml(config_path, default_mapping_rules())
    candidates = generate_candidates(input_path, output_dir, config_dir)
    selected: list[dict[str, Any]] = []
    thresholds = rules["policies"]
    manual = rules.get("manual_overrides", {})
    for candidate in candidates:
        local_fragment = local_name(candidate["local_iri"])
        override = manual.get(local_fragment)
        if override:
            selected.append(
                {
                    **candidate,
                    "relation": override["relation"],
                    "target_iri": override["target"],
                    "score": 0.99,
                    "rationale": override["rationale"],
                    "status": "manual_override",
                }
            )
            continue
        relation = "skos:closeMatch"
        rationale = "Lexical similarity with a compatible external term."
        if candidate["score"] >= thresholds["equivalence_threshold"]:
            relation = "owl:equivalentClass" if candidate["local_kind"] == "class" else "owl:equivalentProperty"
            rationale = "High lexical similarity and compatible kind support a strong equivalence proposal."
        elif candidate["score"] >= thresholds["subclass_threshold"]:
            relation = "rdfs:subClassOf" if candidate["local_kind"] == "class" else "rdfs:subPropertyOf"
            rationale = "Conservative anchoring favors specialization over strict equivalence."
        elif candidate["score"] >= thresholds["exact_match_threshold"]:
            relation = "skos:exactMatch"
            rationale = "Strong lexical match without enough evidence for OWL equivalence."
        selected.append({**candidate, "relation": relation, "rationale": rationale, "status": "proposed"})
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for row in selected:
        key = (row["local_iri"], row["target_iri"])
        if key not in unique or row["score"] > unique[key]["score"]:
            unique[key] = row
    rows = sorted(unique.values(), key=lambda item: (item["local_label"], -item["score"]))
    _write_review_csv(output_dir / "mapping_review.csv", rows)
    _write_alignments_ttl(output_dir.parent / "mappings" / "alignments.ttl", rows)
    write_text(output_dir.parent / "reports" / "alignment_report.md", _alignment_report(rows))
    return rows


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
        relation = RELATION_MAP[row["relation"]]
        lines.append(f"<{row['local_iri']}> <{relation}> <{row['target_iri']}> .")
    write_text(path, "\n".join(lines) + "\n")


def _alignment_report(rows: list[dict[str, Any]]) -> str:
    equivalent = sum(1 for row in rows if row["relation"].startswith("owl:equivalent"))
    subclass = sum(1 for row in rows if row["relation"].startswith("rdfs:sub"))
    close_match = sum(1 for row in rows if row["relation"].startswith("skos:"))
    lines = "\n".join(
        f"- `{row['local_label']}` -> `{row['relation']}` -> `{row['target_iri']}` ({row['score']})"
        for row in rows[:25]
    )
    return f"""# Alignment Report

## Summary

- Proposed mappings: {len(rows)}
- Strong equivalence candidates: {equivalent}
- Subclass or subproperty anchors: {subclass}
- SKOS soft matches: {close_match}

## Representative Mappings

{lines or '- No mappings generated.'}

## Policy Notes

- Generic process, material, measurement, and property concepts are anchored conservatively to EMMO and ECHO.
- Units and quantity-value semantics reuse QUDT when possible.
- Metadata and provenance terms prefer DCTERMS, FOAF, and PROV-O.
- Local PEMFC catalyst-layer terms remain in the `h2kg` namespace for v1 unless a later migration policy is explicitly enabled.
"""
