from __future__ import annotations

from pathlib import Path
from typing import Any

from .extract import extract_local_term_profiles
from .normalize import normalize_token
from .utils import default_mapping_rules, dump_json, ensure_dir, try_load_yaml, write_text


def generate_hdo_alignment_report(
    input_path: str | Path,
    mappings: list[dict[str, Any]],
    output_dir: str | Path,
    config_dir: str | Path | None = None,
) -> dict[str, Any]:
    output_dir = ensure_dir(Path(output_dir))
    rules = try_load_yaml(Path(config_dir or Path(input_path).parent.parent / "config") / "mapping_rules.yaml", default_mapping_rules())
    local_terms = [
        term
        for term in extract_local_term_profiles(input_path, output_dir, config_dir)
        if term["is_local"] and term["kind"] in {"class", "object_property", "datatype_property", "controlled_vocabulary_term"}
    ]
    hdo_indicators = [normalize_token(text) for text in rules.get("term_hints", {}).get("hdo_indicators", [])]
    reviewed_terms = [term for term in local_terms if _should_review_against_hdo(term, hdo_indicators)]
    hdo_mappings = [row for row in mappings if row.get("source") == "hdo"]
    aligned_iris = {row["local_iri"] for row in hdo_mappings}
    overlap_rows = [row for row in mappings if row.get("source") in {"prov-o", "dcterms", "emmo-core", "emmo-electrochemistry"} and row["local_iri"] in {term["iri"] for term in reviewed_terms}]
    stayed_local = []
    for term in reviewed_terms:
        if term["iri"] in aligned_iris:
            continue
        stayed_local.append(
            {
                "iri": term["iri"],
                "label": term["label"],
                "kind": term["kind"],
                "reason": _local_reason(term),
            }
        )
    report = {
        "summary": {
            "reviewed_against_hdo": len(reviewed_terms),
            "aligned_to_hdo": len(hdo_mappings),
            "reused_from_hdo": len(hdo_mappings),
            "stayed_local": len(stayed_local),
            "overlap_with_other_standards": len(overlap_rows),
        },
        "reviewed_terms": reviewed_terms[:80],
        "aligned_terms": hdo_mappings[:80],
        "stayed_local_terms": stayed_local[:80],
        "overlap_notes": [
            {
                "local_label": row["local_label"],
                "source": row["source"],
                "target_iri": row["target_iri"],
                "relation": row["relation"],
            }
            for row in overlap_rows[:80]
        ],
        "guidance": {
            "hdo_role": "Primary alignment source for Helmholtz-community data, metadata, identifier, digital-object, information-profile, schema, validation, and provenance-record concepts.",
            "division_of_labor": {
                "hdo": "Digital asset, metadata management, identifier, validation, and information-governance concepts.",
                "emmo": "Scientific, process, material, and electrochemistry semantics.",
                "qudt": "Quantity kinds, quantity values, and units.",
                "chebi": "Chemical entities.",
                "prov_dcterms": "Publication provenance and release metadata.",
            },
        },
        "cache_note": "Direct HDO term reuse becomes stronger when a real HDO cache file is available at cache/sources/hdo.ttl.",
    }
    dump_json(output_dir / "hdo_alignment_report.json", report)
    write_text(output_dir / "hdo_alignment_report.md", _report_markdown(report))
    return report


def load_hdo_alignment_report(reports_dir: str | Path) -> dict[str, Any]:
    path = Path(reports_dir) / "hdo_alignment_report.json"
    if path.exists():
        import json

        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "summary": {
            "reviewed_against_hdo": 0,
            "aligned_to_hdo": 0,
            "reused_from_hdo": 0,
            "stayed_local": 0,
            "overlap_with_other_standards": 0,
        },
        "reviewed_terms": [],
        "aligned_terms": [],
        "stayed_local_terms": [],
        "overlap_notes": [],
        "guidance": {
            "hdo_role": "HDO is intended as the primary alignment source for Helmholtz-community data and metadata-management concepts.",
            "division_of_labor": {},
        },
        "cache_note": "HDO alignment report has not been generated yet.",
    }


def _should_review_against_hdo(term: dict[str, Any], indicators: list[str]) -> bool:
    haystack = normalize_token(f"{term.get('label', '')} {term.get('description', '')}")
    return any(indicator and indicator in haystack for indicator in indicators)


def _local_reason(term: dict[str, Any]) -> str:
    label = normalize_token(term.get("label", ""))
    if "data point" in label:
        return "Kept local pending a more precise HDO term-level match while retaining H2KG experimental granularity."
    if any(token in label for token in ["schema", "validation", "identifier", "metadata", "data"]):
        return "Candidate for future direct HDO reuse; currently kept local until the HDO cache and parity review are accepted."
    return "Remains local because the current H2KG term carries profile-specific semantics beyond the generic HDO anchor."


def _report_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    aligned = "\n".join(
        f"- `{row['local_label']}` -> `{row['relation']}` -> `{row['target_iri']}`"
        for row in report["aligned_terms"][:25]
    )
    stayed = "\n".join(
        f"- `{row['label']}`: {row['reason']}"
        for row in report["stayed_local_terms"][:25]
    )
    overlaps = "\n".join(
        f"- `{row['local_label']}` also aligns with `{row['source']}` via `{row['relation']}`"
        for row in report["overlap_notes"][:25]
    )
    return f"""# HDO Alignment Report

## Summary

- Reviewed against HDO: {summary['reviewed_against_hdo']}
- Aligned to HDO: {summary['aligned_to_hdo']}
- Reused directly from HDO: {summary['reused_from_hdo']}
- Kept local after HDO review: {summary['stayed_local']}
- Overlap with PROV-O / DCTERMS / EMMO anchors: {summary['overlap_with_other_standards']}

## HDO-Aligned Terms

{aligned or '- No direct HDO-aligned terms were generated in this run.'}

## Terms Kept Local

{stayed or '- No reviewed terms remained local in this run.'}

## Cross-Standard Overlap Notes

{overlaps or '- No overlap notes recorded in this run.'}

## Guidance

- HDO role: {report['guidance']['hdo_role']}
- Cache note: {report['cache_note']}
"""
