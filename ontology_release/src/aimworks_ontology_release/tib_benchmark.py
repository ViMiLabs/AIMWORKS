from __future__ import annotations

import csv
import json
import re
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests

from .io import load_json_document, merge_document_items
from .utils import (
    OWL_DATATYPE_PROPERTY,
    OWL_OBJECT_PROPERTY,
    RDFS_LABEL,
    SKOS_ALT_LABEL,
    SKOS_PREF_LABEL,
    dump_json,
    ensure_dir,
    humanize,
    write_text,
)

H2KG_NS = "https://w3id.org/h2kg/hydrogen-ontology#"
TIB_API = "https://api.terminology.tib.eu/api"
SNAPSHOT_FORMAT = "h2kg-tib-terminology-snapshot/v1"

ROLE_WORDS = {
    "analysis", "data", "dataset", "imaging", "instrument", "measurement", "method", "process", "software",
}
ACRONYM_EXPANSIONS = {
    "afm": "atomic force microscopy",
    "fib": "focused ion beam",
    "fibsem": "focused ion beam scanning electron microscopy",
    "mea": "membrane electrode assembly",
    "pemfc": "proton exchange membrane fuel cell",
    "pemwe": "proton exchange membrane water electrolysis",
    "rrde": "rotating ring disk electrode",
    "sem": "scanning electron microscopy",
    "tem": "transmission electron microscopy",
    "xps": "x ray photoelectron spectroscopy",
    "xrd": "x ray diffraction",
    "xray": "x ray",
}
TIB_FAMILY = {
    "chebi": "materials and chemicals",
    "rxno": "materials and chemicals",
    "cheminf": "materials and chemicals",
    "chmo": "methods and characterization",
    "bao": "methods and characterization",
    "cao": "methods and characterization",
    "cif": "methods and characterization",
    "ms": "methods and characterization",
    "voc4cat": "methods and characterization",
    "emmo": "upper and materials ontologies",
    "bfo": "upper and materials ontologies",
    "afo": "upper and materials ontologies",
    "mop": "upper and materials ontologies",
    "om": "units and quantities",
    "m4i": "data and provenance",
    "edam": "data and provenance",
    "obi": "data and provenance",
}


def refresh_tib_snapshot(
    snapshot_path: str | Path,
    *,
    session: requests.Session | None = None,
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    """Capture a versioned TIB catalogue snapshot for reproducible comparison."""
    client = session or requests.Session()
    response = client.get(f"{TIB_API}/ontologies", params={"size": 1000}, timeout=90)
    response.raise_for_status()
    ontologies = response.json().get("_embedded", {}).get("ontologies", [])
    cleaned = [_catalogue_record(item) for item in ontologies if isinstance(item, dict) and item.get("ontologyId")]
    snapshot = {
        "format": SNAPSHOT_FORMAT,
        "retrieved_at": retrieved_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "api": {"base_url": TIB_API, "catalogue_endpoint": f"{TIB_API}/ontologies"},
        "ontologies": sorted(cleaned, key=lambda item: item["ontology_id"]),
    }
    dump_json(Path(snapshot_path), snapshot)
    return snapshot


def build_tib_benchmark_package(
    input_path: str | Path,
    output_root: str | Path,
    snapshot_path: str | Path,
    *,
    refresh: bool = False,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    """Build reviewed benchmark artifacts from a dated TIB snapshot.

    Refreshing is deliberate. Normal release generation remains offline and uses the
    stored catalogue and candidate cache, making published counts reproducible.
    """
    output_root = Path(output_root)
    target = ensure_dir(output_root / "benchmarks" / "tib_terminology")
    snapshot_path = Path(snapshot_path)
    if refresh:
        snapshot = refresh_tib_snapshot(snapshot_path, session=session)
    elif snapshot_path.exists():
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    else:
        return _write_missing_snapshot_package(target, snapshot_path)

    terms = extract_local_h2kg_terms(input_path)
    candidate_path = target / "candidate_mappings.json"
    if refresh or not candidate_path.exists():
        candidates, discovery_failures = discover_candidates(terms, snapshot, session=session)
        dump_json(candidate_path, candidates)
        dump_json(target / "discovery_failures.json", discovery_failures)
    else:
        candidates = json.loads(candidate_path.read_text(encoding="utf-8"))
        failure_path = target / "discovery_failures.json"
        discovery_failures = json.loads(failure_path.read_text(encoding="utf-8")) if failure_path.exists() else []

    review_path = target / "reviewed_mapping_matrix.csv"
    existing_decisions = _load_review_decisions(review_path)
    rows = build_review_rows(terms, candidates, existing_decisions)
    _write_csv(review_path, rows, REVIEW_COLUMNS)
    _write_csv(target / "accepted_mappings.csv", [row for row in rows if row["review_decision"] == "accept"], REVIEW_COLUMNS)
    _write_csv(target / "rejected_candidates.csv", [row for row in rows if row["review_decision"] == "reject"], REVIEW_COLUMNS)
    _write_csv(target / "unmatched_h2kg_terms.csv", unmatched_rows(terms, rows), UNMATCHED_COLUMNS)

    summary = build_summary(terms, rows, snapshot)
    summary["discovery_failure_count"] = len(discovery_failures)
    dump_json(target / "benchmark_summary.json", summary)
    _write_csv(target / "category_summary.csv", summary["category_summary"], CATEGORY_COLUMNS)
    _write_csv(target / "major_resource_summary.csv", summary["major_resource_summary"], RESOURCE_COLUMNS)
    write_text(target / "README.md", benchmark_readme(snapshot_path, summary))
    write_text(target / "manuscript_reporting.md", manuscript_reporting(summary))
    write_text(target / "matching_rules.md", matching_rules())
    return summary


def extract_local_h2kg_terms(input_path: str | Path) -> list[dict[str, str]]:
    items = merge_document_items(load_json_document(input_path))
    terms: list[dict[str, str]] = []
    for item in items:
        iri = item.get("@id")
        if not isinstance(iri, str) or not iri.startswith(H2KG_NS):
            continue
        labels = _literal_values(item, RDFS_LABEL) + _literal_values(item, SKOS_PREF_LABEL)
        if not labels:
            labels = [humanize(iri.rsplit("#", 1)[-1])]
        aliases = _literal_values(item, SKOS_ALT_LABEL)
        terms.append({
            "h2kg_iri": iri,
            "h2kg_label": labels[0],
            "aliases": " | ".join(dict.fromkeys(aliases)),
            "h2kg_category": _h2kg_category(item),
        })
    return sorted(terms, key=lambda row: (row["h2kg_category"], row["h2kg_label"], row["h2kg_iri"]))


def discover_candidates(
    terms: list[dict[str, str]],
    snapshot: dict[str, Any],
    *,
    session: requests.Session | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    def discover_for_term(term: dict[str, str]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        client = session or requests.Session()
        labels = [term["h2kg_label"], *[value.strip() for value in term["aliases"].split("|") if value.strip()]]
        seen: set[str] = set()
        result: list[dict[str, Any]] = []
        failures: list[dict[str, str]] = []
        for source_label in labels:
            try:
                response = _search_with_retry(client, source_label)
            except requests.RequestException as error:
                failures.append({"h2kg_iri": term["h2kg_iri"], "h2kg_label": term["h2kg_label"], "query": source_label, "error": str(error)})
                continue
            for hit in response.json().get("response", {}).get("docs", []):
                candidate = _candidate_record(term, source_label, hit)
                if not candidate or candidate["mapping_key"] in seen:
                    continue
                seen.add(candidate["mapping_key"])
                result.append(candidate)
        return result, failures

    # A supplied session is normally a deterministic test double. The live
    # service uses a small worker pool to avoid both excessive latency and load.
    if session is not None:
        batches = [discover_for_term(term) for term in terms]
    else:
        # TIB is a shared public service. Two workers stay below the observed
        # connection threshold while keeping a complete refresh practical.
        with ThreadPoolExecutor(max_workers=2) as executor:
            batches = list(executor.map(discover_for_term, terms))
    return (
        [candidate for batch, _ in batches for candidate in batch],
        [failure for _, failures in batches for failure in failures],
    )


def _search_with_retry(client: requests.Session, query: str) -> requests.Response:
    last_error: requests.RequestException | None = None
    for attempt in range(4):
        try:
            response = client.get(
                f"{TIB_API}/search",
                # Omitting an ontology filter deliberately searches the complete
                # TIB corpus. Passing every ontology identifier exceeds the
                # service URL limit and fails for otherwise valid queries.
                params={"q": query, "local": "true", "rows": 30},
                timeout=45,
            )
            response.raise_for_status()
            return response
        except requests.RequestException as error:
            last_error = error
            if attempt < 3:
                time.sleep(2 ** attempt)
    assert last_error is not None
    raise last_error


def build_review_rows(
    terms: list[dict[str, str]],
    candidates: list[dict[str, Any]],
    decisions: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    term_index = {term["h2kg_iri"]: term for term in terms}
    rows: list[dict[str, str]] = []
    for candidate in candidates:
        if candidate["match_strength"] == "related_not_equivalent":
            continue
        term = term_index[candidate["h2kg_iri"]]
        prior = decisions.get(candidate["mapping_key"], {})
        rows.append({
            **{column: "" for column in REVIEW_COLUMNS},
            **term,
            "tib_ontology_id": candidate["tib_ontology_id"],
            "tib_family": candidate["tib_family"],
            "tib_iri": candidate["tib_iri"],
            "tib_label": candidate["tib_label"],
            "tib_definition": candidate["tib_definition"],
            "tib_kind": candidate["tib_kind"],
            "match_strength": candidate["match_strength"],
            "semantic_role_compatibility": candidate["semantic_role_compatibility"],
            "candidate_rationale": candidate["candidate_rationale"],
            "review_decision": prior.get("review_decision", "pending_manual_review"),
            "reviewer": prior.get("reviewer", ""),
            "review_date": prior.get("review_date", ""),
            "review_rationale": prior.get("review_rationale", ""),
            "mapping_key": candidate["mapping_key"],
        })
    return sorted(rows, key=lambda row: (row["h2kg_category"], row["h2kg_label"], row["tib_ontology_id"], row["tib_label"]))


def build_summary(terms: list[dict[str, str]], rows: list[dict[str, str]], snapshot: dict[str, Any]) -> dict[str, Any]:
    accepted = [row for row in rows if row["review_decision"] == "accept"]
    candidates = [row for row in rows if row["semantic_role_compatibility"] == "compatible"]
    by_category: list[dict[str, Any]] = []
    by_resource: list[dict[str, Any]] = []
    for category, category_terms in _group_by(terms, "h2kg_category").items():
        term_iris = {term["h2kg_iri"] for term in category_terms}
        category_candidates = [row for row in candidates if row["h2kg_iri"] in term_iris]
        category_accepted = [row for row in accepted if row["h2kg_iri"] in term_iris]
        candidate_iris = {row["h2kg_iri"] for row in category_candidates}
        accepted_iris = {row["h2kg_iri"] for row in category_accepted}
        examples = "; ".join(sorted(dict.fromkeys(row["h2kg_label"] for row in category_candidates))[:3])
        sources = "; ".join(sorted(dict.fromkeys(row["tib_ontology_id"] for row in category_candidates))[:5])
        by_category.append({
            "h2kg_category": category,
            "h2kg_terms_assessed": len(term_iris),
            "accepted_terms": len(accepted_iris),
            "pending_candidate_terms": len(candidate_iris - accepted_iris),
            "unmatched_terms": len(term_iris - candidate_iris),
            "principal_tib_sources": sources or "-",
            "representative_h2kg_terms": examples or "-",
        })
    key_resources = ["emmo", "chmo", "chebi", "qudt", "prov", "edam", "voc4cat", "m4i", "om"]
    for ontology_id in key_resources:
        resource_rows = [row for row in candidates if row["tib_ontology_id"] == ontology_id]
        by_resource.append({
            "tib_resource": ontology_id,
            "candidate_h2kg_terms": len({row["h2kg_iri"] for row in resource_rows}),
            "accepted_h2kg_terms": len({row["h2kg_iri"] for row in accepted if row["tib_ontology_id"] == ontology_id}),
            "representative_correspondences": "; ".join(
                f"{row['h2kg_label']} = {row['tib_label']}" for row in resource_rows[:3]
            ) or "-",
        })
    return {
        "benchmark": "H2KG--TIB Terminology Benchmark",
        "snapshot_format": snapshot.get("format"),
        "tib_retrieved_at": snapshot.get("retrieved_at"),
        "tib_ontology_count": len(snapshot.get("ontologies", [])),
        "h2kg_local_terms_assessed": len(terms),
        "candidate_rows": len(rows),
        "compatible_candidate_terms": len({row["h2kg_iri"] for row in candidates}),
        "accepted_terms": len({row["h2kg_iri"] for row in accepted}),
        "pending_manual_review_rows": sum(row["review_decision"] == "pending_manual_review" for row in rows),
        "category_summary": by_category,
        "major_resource_summary": by_resource,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }


def unmatched_rows(terms: list[dict[str, str]], rows: list[dict[str, str]]) -> list[dict[str, str]]:
    candidate_iris = {row["h2kg_iri"] for row in rows if row["semantic_role_compatibility"] == "compatible"}
    return [{**term, "reason": "No compatible exact or normalized-equivalent TIB candidate was discovered."} for term in terms if term["h2kg_iri"] not in candidate_iris]


def normalized_label(value: str, *, remove_role_words: bool = False) -> str:
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value).lower().replace("-", " ")
    tokens: list[str] = []
    for token in re.sub(r"[^a-z0-9 ]+", " ", value).split():
        tokens.extend(ACRONYM_EXPANSIONS.get(token, token).split())
    if remove_role_words:
        tokens = [token for token in tokens if token not in ROLE_WORDS]
    return " ".join(tokens)


def _candidate_record(term: dict[str, str], source_label: str, hit: dict[str, Any]) -> dict[str, Any] | None:
    tib_label = _first_text(hit.get("label") or hit.get("prefLabel") or hit.get("name"))
    tib_iri = _first_text(hit.get("iri") or hit.get("@id") or hit.get("id"))
    if not tib_label or not tib_iri:
        return None
    exact = normalized_label(source_label) == normalized_label(tib_label)
    normalized = normalized_label(source_label, remove_role_words=True) == normalized_label(tib_label, remove_role_words=True)
    if exact:
        strength = "exact_label"
    elif normalized and len(normalized_label(source_label, remove_role_words=True).split()) >= 2:
        strength = "normalized_equivalent_label"
    else:
        strength = "related_not_equivalent"
    ontology_id = _first_text(hit.get("ontology") or hit.get("ontologyId") or hit.get("ontology_name")) or "unknown"
    tib_kind = _tib_kind(hit)
    role = _role_compatibility(term["h2kg_category"], tib_kind)
    key = f"{term['h2kg_iri']}|{tib_iri}"
    return {
        "mapping_key": key,
        "h2kg_iri": term["h2kg_iri"],
        "tib_ontology_id": ontology_id,
        "tib_family": TIB_FAMILY.get(ontology_id, "other domain resources"),
        "tib_iri": tib_iri,
        "tib_label": tib_label,
        "tib_definition": _first_text(hit.get("description") or hit.get("definition") or hit.get("comment")),
        "tib_kind": tib_kind,
        "match_strength": strength,
        "semantic_role_compatibility": role,
        "candidate_rationale": f"{strength.replace('_', ' ')} after label normalization from '{source_label}'.",
    }


def _h2kg_category(item: dict[str, Any]) -> str:
    types = {value for value in _as_list(item.get("@type")) if isinstance(value, str)}
    if OWL_OBJECT_PROPERTY in types or OWL_DATATYPE_PROPERTY in types:
        return "object/data properties"
    base_category = {
        "Agent": "metadata/provenance",
        "Data": "datasets",
        "DataPoint": "datasets",
        "Instrument": "instruments",
        "Manufacturing": "manufacturing/processes",
        "Matter": "materials",
        "Measurement": "measurements",
        "Metadata": "metadata/provenance",
        "Parameter": "parameters",
        "Process": "manufacturing/processes",
        "Property": "properties",
        "Unit": "parameters",
    }.get(str(item.get("@id", "")).rsplit("#", 1)[-1])
    if base_category:
        return base_category
    local_types = {value.rsplit("#", 1)[-1] for value in types if value.startswith(H2KG_NS)}
    for expected, category in [
        ("Matter", "materials"), ("Manufacturing", "manufacturing/processes"), ("Process", "manufacturing/processes"),
        ("Measurement", "measurements"), ("Instrument", "instruments"), ("Parameter", "parameters"),
        ("Data", "datasets"), ("DataPoint", "datasets"), ("Property", "properties"),
        ("Metadata", "metadata/provenance"), ("Agent", "metadata/provenance"),
    ]:
        if expected in local_types:
            return category
    return "other local vocabulary"


def _role_compatibility(h2kg_category: str, tib_kind: str) -> str:
    if h2kg_category == "object/data properties":
        return "compatible" if tib_kind == "property" else "incompatible"
    if tib_kind == "property":
        return "incompatible"
    if tib_kind == "unknown":
        return "review_required"
    return "compatible"


def _tib_kind(hit: dict[str, Any]) -> str:
    value = " ".join(str(part) for part in _as_list(hit.get("type") or hit.get("types") or hit.get("kind"))).lower()
    if "property" in value:
        return "property"
    if any(token in value for token in ["class", "concept", "individual"]):
        return "term"
    return "unknown"


def _catalogue_record(item: dict[str, Any]) -> dict[str, Any]:
    config = item.get("config") if isinstance(item.get("config"), dict) else {}
    return {
        "ontology_id": str(item["ontologyId"]),
        "title": str(config.get("title") or ""),
        "version": item.get("version") or config.get("version"),
        "loaded": item.get("loaded"),
        "updated": item.get("updated"),
        "number_of_terms": int(item.get("numberOfTerms") or 0),
        "number_of_properties": int(item.get("numberOfProperties") or 0),
        "number_of_individuals": int(item.get("numberOfIndividuals") or 0),
    }


def _load_review_decisions(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {row["mapping_key"]: row for row in csv.DictReader(handle) if row.get("mapping_key")}


def _write_missing_snapshot_package(target: Path, snapshot_path: Path) -> dict[str, Any]:
    message = (
        "# H2KG--TIB Terminology Benchmark\n\n"
        "No frozen TIB snapshot is available yet. Run the benchmark command with `--refresh` "
        f"to create `{snapshot_path}` and populate the reviewed mapping package.\n"
    )
    write_text(target / "README.md", message)
    return {"status": "skipped_missing_snapshot", "snapshot": str(snapshot_path), "target": str(target)}


def _write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _group_by(rows: list[dict[str, str]], key: str) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row[key]].append(row)
    return dict(sorted(grouped.items()))


def _literal_values(item: dict[str, Any], predicate: str) -> list[str]:
    result: list[str] = []
    for value in _as_list(item.get(predicate)):
        if isinstance(value, dict) and "@value" in value:
            result.append(str(value["@value"]))
        elif isinstance(value, str):
            result.append(value)
    return result


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else ([] if value is None else [value])


def _first_text(value: Any) -> str:
    for item in _as_list(value):
        if isinstance(item, dict):
            item = item.get("@value") or item.get("value") or item.get("@id")
        if item:
            return str(item)
    return ""


def benchmark_readme(snapshot_path: Path, summary: dict[str, Any]) -> str:
    return f"""# H2KG--TIB Terminology Benchmark

This package compares local public H2KG vocabulary against the TIB Terminology Service catalogue frozen at `{summary.get('tib_retrieved_at', 'unknown')}`. It assesses `{summary.get('h2kg_local_terms_assessed', 0)}` local H2KG terms across `{summary.get('tib_ontology_count', 0)}` TIB ontologies.

`reviewed_mapping_matrix.csv` is the review surface. Machine-generated candidates are deliberately marked `pending_manual_review`; only rows marked `accept` count as validated semantic correspondences. The package preserves rejected candidates and unmatched H2KG terms so lexical similarity is not confused with semantic alignment.

The normal release regenerates this package from the frozen snapshot at `{snapshot_path}`. Use the explicit refresh command only when intentionally creating a new dated comparison snapshot.
"""


def matching_rules() -> str:
    return """# Matching Rules

Candidates are discovered from preferred labels and H2KG alternative labels. Normalization lowercases labels, separates CamelCase, standardizes punctuation, and expands controlled acronyms such as SEM, TEM, AFM, XRD, and XPS. A normalized-equivalent match may remove generic role words such as `Measurement`, `Imaging`, `Instrument`, `Dataset`, `Process`, and `Software` only when at least two substantive tokens remain.

Broad, narrower, and token-overlap candidates are recorded as `related_not_equivalent` and excluded from the review matrix and all overlap counts. In particular, a parameter such as `AFM Scan Speed` is not an equivalent match to a generic `atomic force microscopy` method. Object and datatype properties can only match TIB properties. All remaining candidates require a documented human accept/reject decision before being reported as semantic correspondences.
"""


def manuscript_reporting(summary: dict[str, Any]) -> str:
    rows = summary.get("category_summary", [])
    table = "\n".join(
        f"| {row['h2kg_category']} | {row['h2kg_terms_assessed']} | {row['accepted_terms']} | {row['pending_candidate_terms']} | {row['unmatched_terms']} | {row['principal_tib_sources']} | {row['representative_h2kg_terms']} |"
        for row in rows
    )
    return f"""# Manuscript Reporting: H2KG--TIB Benchmark

## Methods wording

> We benchmarked the local public H2KG vocabulary against the ontologies indexed by the TIB Terminology Service using the dated catalogue snapshot `{summary.get('tib_retrieved_at', 'unknown')}`. Candidate correspondences were generated from preferred labels and synonyms using controlled normalization, then assessed for semantic-role compatibility. Candidates were classified as exact label equivalence, normalized label equivalence, related but non-equivalent, or no suitable match. Only correspondences with a documented human accept decision are reported as validated semantic mappings. The benchmark is interpreted as a complementarity assessment rather than a comparison of ontology size or quality.

## Results table (populate accepted counts after manual review)

| H2KG category | Terms assessed | Accepted | Pending candidates | No compatible candidate | Principal TIB sources | Representative H2KG terms |
|---|---:|---:|---:|---:|---|---|
{table}

## Reporting note

The current package contains `{summary.get('pending_manual_review_rows', 0)}` machine-proposed rows pending human review. Do not report `pending candidates` as validated semantic overlap. The supplementary package contains the full review matrix, rejected candidates, matching rules, snapshot metadata, and unmatched H2KG terms.
"""


REVIEW_COLUMNS = [
    "mapping_key", "h2kg_iri", "h2kg_label", "aliases", "h2kg_category", "tib_ontology_id", "tib_family", "tib_iri", "tib_label", "tib_definition", "tib_kind", "match_strength", "semantic_role_compatibility", "candidate_rationale", "review_decision", "reviewer", "review_date", "review_rationale",
]
UNMATCHED_COLUMNS = ["h2kg_iri", "h2kg_label", "aliases", "h2kg_category", "reason"]
CATEGORY_COLUMNS = ["h2kg_category", "h2kg_terms_assessed", "accepted_terms", "pending_candidate_terms", "unmatched_terms", "principal_tib_sources", "representative_h2kg_terms"]
RESOURCE_COLUMNS = ["tib_resource", "candidate_h2kg_terms", "accepted_h2kg_terms", "representative_correspondences"]
