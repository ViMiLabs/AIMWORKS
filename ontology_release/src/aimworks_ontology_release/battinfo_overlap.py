from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from .normalize import humanize_identifier, normalize_label
from .utils import local_name, write_json, write_text

BATTINFO_URL = "https://raw.githubusercontent.com/BIG-MAP/BattINFO/master/battinfo-inferred.ttl"
LOCAL_NAMESPACE = "https://w3id.org/h2kg/hydrogen-ontology#"
LABEL_KEYS = (
    "http://www.w3.org/2004/02/skos/core#prefLabel",
    "http://www.w3.org/2000/01/rdf-schema#label",
)
ALT_LABEL_KEY = "http://www.w3.org/2004/02/skos/core#altLabel"
MAPPING_KEYS = (
    "http://www.w3.org/2004/02/skos/core#exactMatch",
    "http://www.w3.org/2004/02/skos/core#closeMatch",
    "http://www.w3.org/2004/02/skos/core#broadMatch",
    "http://www.w3.org/2004/02/skos/core#narrowMatch",
    "http://www.w3.org/2002/07/owl#equivalentClass",
    "http://www.w3.org/2002/07/owl#equivalentProperty",
    "http://www.w3.org/2000/01/rdf-schema#subClassOf",
    "http://www.w3.org/2000/01/rdf-schema#subPropertyOf",
)
SKIP_ALT_PATTERN = re.compile(r"^\s*(?:\d+(?:\.\d+)?\s*[A-Za-z/%-]+|[A-Z]{1,4}\d*|[A-Za-z]?\d+[A-Za-z/%-]*)\s*$")


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _literal_text(value: Any) -> str | None:
    if isinstance(value, dict):
        text = value.get("@value") or value.get("@id")
        return text if isinstance(text, str) else None
    return value if isinstance(value, str) else None


def _namespace_group(iri: str) -> str:
    lowered = iri.lower()
    if "/domain/electrochemistry" in lowered:
        return "electrochemistry"
    if "/domain/chemical-substance" in lowered:
        return "chemical_substance"
    if "/domain/characterisation-methodology/chameo" in lowered:
        return "chameo"
    if "/domain/battery" in lowered:
        return "battery"
    if "w3id.org/emmo#" in lowered:
        return "emmo"
    return "other"


def _safe_alt_label(label: str) -> bool:
    if len(label.strip()) < 5:
        return False
    return not SKIP_ALT_PATTERN.match(label)


def _external_links(node: dict[str, Any]) -> list[str]:
    links: list[str] = []
    for key in MAPPING_KEYS:
        for value in _as_list(node.get(key)):
            iri = _literal_text(value)
            if isinstance(iri, str) and iri.startswith("http") and not iri.startswith(LOCAL_NAMESPACE):
                links.append(iri)
    return sorted(set(links))


def _h2kg_terms(payload: Any) -> list[dict[str, Any]]:
    nodes = payload.get("@graph", []) if isinstance(payload, dict) else payload
    rows: list[dict[str, Any]] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = node.get("@id")
        if not isinstance(node_id, str) or not node_id.startswith(LOCAL_NAMESPACE):
            continue
        labels: list[str] = []
        for key in LABEL_KEYS:
            for value in _as_list(node.get(key)):
                text = _literal_text(value)
                if isinstance(text, str):
                    labels.append(text)
        alt_labels = []
        for value in _as_list(node.get(ALT_LABEL_KEY)):
            text = _literal_text(value)
            if isinstance(text, str):
                alt_labels.append(text)
        if not labels and not alt_labels:
            continue
        types = [item for item in _as_list(node.get("@type")) if isinstance(item, str)]
        rows.append(
            {
                "id": node_id,
                "label": labels[0] if labels else humanize_identifier(local_name(node_id)),
                "alt_labels": alt_labels,
                "term_type": local_name(types[0]) if types else "term",
                "external_links": _external_links(node),
            }
        )
    return rows


def _load_battinfo_text(root: Path, source_config: dict[str, Any] | None = None, battinfo_text: str | None = None) -> tuple[str | None, str, str]:
    if battinfo_text:
        return battinfo_text, "provided", "inline"
    cache_file = root / "cache" / "sources" / "battinfo-inferred.ttl"
    if cache_file.exists():
        return cache_file.read_text(encoding="utf-8"), "cache", str(cache_file)
    url = BATTINFO_URL
    if source_config:
        battinfo_cfg = source_config.get("sources", {}).get("battinfo", {})
        url = str(battinfo_cfg.get("fetch", {}).get("url") or url)
    try:
        with urlopen(url, timeout=45) as response:
            return response.read().decode("utf-8", errors="replace"), "remote", url
    except Exception as exc:  # pragma: no cover - exercised in offline environments
        return None, "unavailable", f"{url} ({exc})"


def _parse_battinfo_entities(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("<") and " rdf:type " in line:
            match = re.match(r"(<[^>]+>)\s+rdf:type\s+([^;]+?)\s*;", line)
            if match:
                current = {"id": match.group(1), "record_type": match.group(2).strip(), "pref_label": None, "alt_labels": []}
                pref_match = re.search(r"prefLabel>\s+\"([^\"]+)\"@en", line)
                if pref_match:
                    current["pref_label"] = pref_match.group(1)
                current["alt_labels"].extend(re.findall(r"altLabel>\s+\"([^\"]+)\"@en", line))
                if line.strip().endswith("."):
                    rows.append(current)
                    current = None
                continue
        if current is None:
            continue
        pref_match = re.search(r"prefLabel>\s+\"([^\"]+)\"@en", line)
        if pref_match:
            current["pref_label"] = pref_match.group(1)
        current["alt_labels"].extend(re.findall(r"altLabel>\s+\"([^\"]+)\"@en", line))
        if line.strip().endswith("."):
            rows.append(current)
            current = None
    return [row for row in rows if row.get("pref_label")]


def analyze_battinfo_overlap(
    payload: Any,
    root: Path,
    source_config: dict[str, Any] | None = None,
    battinfo_text: str | None = None,
) -> dict[str, Any]:
    report = {
        "status": "skipped",
        "source_origin": "",
        "source_location": "",
        "battinfo_entity_count": 0,
        "h2kg_local_term_count": 0,
        "exact_pref_overlap_count": 0,
        "exact_alt_overlap_count": 0,
        "reuse_directly_count": 0,
        "map_only_count": 0,
        "keep_local_count": 0,
        "reuse_directly": [],
        "map_only": [],
        "keep_local": [],
        "notes": [],
        "namespace_breakdown": {},
    }
    text, origin, location = _load_battinfo_text(root, source_config=source_config, battinfo_text=battinfo_text)
    report["source_origin"] = origin
    report["source_location"] = location
    h2kg_terms = _h2kg_terms(payload)
    report["h2kg_local_term_count"] = len(h2kg_terms)
    if not text:
        report["notes"].append("BattINFO overlap analysis was skipped because the inferred BattINFO source could not be loaded.")
        return report

    battinfo_rows = _parse_battinfo_entities(text)
    report["battinfo_entity_count"] = len(battinfo_rows)
    by_pref = {normalize_label(row["pref_label"]): row for row in battinfo_rows}
    by_alt: dict[str, dict[str, Any]] = {}
    for row in battinfo_rows:
        for alt_label in row["alt_labels"]:
            if _safe_alt_label(alt_label):
                by_alt.setdefault(normalize_label(alt_label), row)

    reuse_directly: list[dict[str, Any]] = []
    map_only: list[dict[str, Any]] = []
    keep_local: list[dict[str, Any]] = []
    namespace_breakdown: dict[str, int] = {}

    for term in h2kg_terms:
        label_key = normalize_label(term["label"])
        exact = by_pref.get(label_key)
        if exact:
            report["exact_pref_overlap_count"] += 1
            namespace_group = _namespace_group(exact["id"])
            row = {
                "h2kg_label": term["label"],
                "h2kg_id": term["id"],
                "term_type": term["term_type"],
                "target_label": exact["pref_label"],
                "target_iri": exact["id"].strip("<>"),
                "target_record_type": exact["record_type"],
                "namespace_group": namespace_group,
                "existing_external_links": term["external_links"],
            }
            namespace_breakdown[namespace_group] = namespace_breakdown.get(namespace_group, 0) + 1
            if namespace_group == "battery" or term["external_links"]:
                row["reason"] = "Exact overlap exists in the BattINFO inferred stack, but the term should stay mapped rather than reused directly."
                map_only.append(row)
            else:
                row["reason"] = "Exact canonical label overlap with a BattINFO-exposed upstream term and no current external alignment on the local H2KG term."
                reuse_directly.append(row)
            continue

        alt_match = by_alt.get(label_key)
        if alt_match:
            report["exact_alt_overlap_count"] += 1
            map_only.append(
                {
                    "h2kg_label": term["label"],
                    "h2kg_id": term["id"],
                    "term_type": term["term_type"],
                    "target_label": alt_match["pref_label"],
                    "target_iri": alt_match["id"].strip("<>"),
                    "target_record_type": alt_match["record_type"],
                    "namespace_group": _namespace_group(alt_match["id"]),
                    "existing_external_links": term["external_links"],
                    "reason": "The local H2KG label matches a BattINFO alternative label exactly; keep the local term mapped unless you deliberately replace it with the upstream IRI.",
                }
            )
            continue

        keep_local.append(
            {
                "h2kg_label": term["label"],
                "h2kg_id": term["id"],
                "term_type": term["term_type"],
                "reason": "No strong BattINFO overlap was detected; keep the local H2KG term unless another upstream ontology is a better authority.",
            }
        )

    report["status"] = "ok"
    report["reuse_directly"] = sorted(reuse_directly, key=lambda item: (item["namespace_group"], item["h2kg_label"]))
    report["map_only"] = sorted(map_only, key=lambda item: (item["namespace_group"], item["h2kg_label"]))
    report["keep_local"] = sorted(keep_local, key=lambda item: item["h2kg_label"])
    report["reuse_directly_count"] = len(report["reuse_directly"])
    report["map_only_count"] = len(report["map_only"])
    report["keep_local_count"] = len(report["keep_local"])
    report["namespace_breakdown"] = dict(sorted(namespace_breakdown.items()))
    report["notes"].extend(
        [
            "BattINFO is treated here as a benchmark and secondary mapping target, not as the primary authority for PEMFC-specific modeling.",
            "Reuse-directly candidates point to the BattINFO-exposed upstream IRIs themselves, which often belong to EMMO, electrochemistry, CHAMEO, or chemical-substance modules.",
            "Fuzzy lexical BattINFO suggestions are intentionally excluded from the main categories here because they produced too many false positives to be considered rigorous.",
        ]
    )
    return report


def write_battinfo_overlap_outputs(report: dict[str, Any], root: Path) -> None:
    write_json(root / "output" / "reports" / "battinfo_overlap_report.json", report)
    source_origin = report.get("source_origin", "")
    source_location = report.get("source_location", "")
    battinfo_entity_count = report.get("battinfo_entity_count", 0)
    h2kg_local_term_count = report.get("h2kg_local_term_count", 0)
    exact_pref_overlap_count = report.get("exact_pref_overlap_count", 0)
    exact_alt_overlap_count = report.get("exact_alt_overlap_count", 0)
    reuse_directly_count = report.get("reuse_directly_count", 0)
    map_only_count = report.get("map_only_count", 0)
    keep_local_count = report.get("keep_local_count", 0)
    lines = [
        "# BattINFO Overlap Report",
        "",
        f"- Status: **{report['status']}**",
        f"- Source origin: `{source_origin}`",
        f"- Source location: `{source_location}`",
        f"- BattINFO entities parsed: **{battinfo_entity_count}**",
        f"- H2KG local terms reviewed: **{h2kg_local_term_count}**",
        f"- Exact prefLabel overlaps: **{exact_pref_overlap_count}**",
        f"- Exact altLabel overlaps: **{exact_alt_overlap_count}**",
        f"- Reuse directly: **{reuse_directly_count}**",
        f"- Map only: **{map_only_count}**",
        f"- Keep local: **{keep_local_count}**",
        "",
    ]
    if report.get("notes"):
        lines.extend(["## Notes", ""])
        lines.extend(f"- {item}" for item in report["notes"])
        lines.append("")
    if report.get("namespace_breakdown"):
        lines.extend(["## Reuse Breakdown", ""])
        lines.extend(f"- {key}: {value}" for key, value in report["namespace_breakdown"].items())
        lines.append("")

    def emit_rows(title: str, rows: list[dict[str, Any]], limit: int = 40) -> None:
        lines.extend([f"## {title}", ""])
        if not rows:
            lines.extend(["No terms in this category.", ""])
            return
        for row in rows[:limit]:
            lines.extend(
                [
                    f"- **{row['h2kg_label']}**",
                    f"  H2KG IRI: `{row['h2kg_id']}`",
                    f"  Suggested target: `{row.get('target_iri', '')}`",
                    f"  Namespace group: `{row.get('namespace_group', '')}`",
                    f"  Reason: {row['reason']}",
                ]
            )
        if len(rows) > limit:
            lines.append(f"- ... {len(rows) - limit} additional terms omitted from markdown summary; see the JSON report for the full list.")
        lines.append("")

    emit_rows("Reuse Directly", report.get("reuse_directly", []))
    emit_rows("Map Only", report.get("map_only", []))
    emit_rows("Keep Local", report.get("keep_local", []), limit=20)
    write_text(root / "output" / "reports" / "battinfo_overlap_report.md", "\n".join(lines) + "\n")
