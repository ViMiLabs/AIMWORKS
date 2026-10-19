from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import shutil
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

import requests
from rapidfuzz import fuzz

from .tib_benchmark import ACRONYM_EXPANSIONS, H2KG_NS, ROLE_WORDS, normalized_label
from .utils import dump_json, ensure_dir, write_text


TIB_API = "https://api.terminology.tib.eu/api"
SNAPSHOT_FORMAT = "h2kg-tib-collection-snapshot/v1"
CANDIDATE_FORMAT = "h2kg-tib-collection-candidates/v1"
BENCHMARK_FORMAT = "h2kg-tib-collection-benchmark/v2"
HARMONIZATION_FORMAT = "h2kg-tib-auto-harmonization/v2"
DEFAULT_COLLECTIONS = ("NFDI4CAT", "NFDI4ENERGY", "NFDI4ING")
UNASSESSED_NATIVE_ONTOLOGIES = {
    "battinfo": "native_evidence_unavailable",
}
COLLECTION_DISPLAY_NAMES = {
    "nfdi4cat": "NFDI4Cat",
    "nfdi4energy": "NFDI4Energy",
    "nfdi4ing": "NFDI4Ing",
}
OUTCOMES = (
    "exact_iri_reuse",
    "machine_exact_equivalent",
    "h2kg_narrower",
    "h2kg_broader",
    "related_non_equivalent",
    "ambiguous_abstained",
    "unmatched",
)
OUTCOME_RANK = {name: index for index, name in enumerate(OUTCOMES)}
DECISION_RANK = {
    "exact_iri_reuse": 0,
    "machine_exact_equivalent": 1,
    "h2kg_narrower": 2,
    "h2kg_broader": 3,
    "related_non_equivalent": 4,
    "ambiguous_abstained": 5,
    "unmatched": 6,
}

ONTOLOGY_PRIORITY = {
    "emmo": 0,
    "chmo": 1,
    "voc4cat": 2,
    "chebi": 3,
    "obi": 4,
    "afo": 5,
    "m4i": 6,
    "qudt": 7,
    "quantitykind": 8,
    "prov": 9,
    "edam": 10,
}

ROLE_HINTS = {
    "Measurement": {
        "assay", "characterization", "diffraction", "imaging", "measurement", "microscopy",
        "spectrometry", "spectroscopy", "test", "tomography",
    },
    "Instrument": {
        "analyser", "analyzer", "apparatus", "detector", "diffractometer", "equipment",
        "instrument", "microscope", "spectrometer",
    },
    "Data": {
        "curve", "data", "dataset", "document", "file", "graph", "image", "map", "record",
        "spectrum", "table",
    },
    "Characteristic": {
        "acidity", "angle", "area", "capacitance", "capacity", "concentration", "conductivity",
        "count", "density", "diameter", "distance", "energy", "flux", "fraction", "humidity",
        "length", "mass", "parameter", "percent", "percentage", "porosity", "potential", "pressure",
        "property", "quality", "quantity", "radius", "ratio", "rate", "resistance", "size", "speed",
        "temperature", "thickness", "time", "tortuosity", "value", "voltage", "volume", "wavelength",
    },
    "Matter": {
        "assembly", "catalyst", "cell", "chemical", "component", "electrode", "electrolyte",
        "material", "membrane", "mixture", "object", "sample", "specimen", "substance",
    },
    "Agent": {"agent", "institution", "organization", "person", "researcher"},
    "Process": {
        "analysis", "calculation", "coating", "cutting", "deposition", "doping", "drying", "etching",
        "fabrication", "leaching", "manufacturing", "method", "milling", "model", "operation",
        "preparation", "procedure", "process", "reconstruction", "simulation", "synthesis", "technique",
        "treatment",
    },
}

ROLE_LABEL_PRIORITY = (
    "Instrument",
    "Measurement",
    "Data",
    "Characteristic",
    "Agent",
    "Process",
    "Matter",
)

GENUS_ROLE_PATTERNS = {
    "Instrument": (r"\b(?:instrument|apparatus|device|detector|microscope|spectrometer)\b",),
    "Measurement": (r"\b(?:measurement|assay|characteri[sz]ation|microscopy|spectroscopy|tomography)\b",),
    "Data": (r"\b(?:data set|dataset|data|record|image|spectrum|curve|table)\b",),
    "Characteristic": (r"\b(?:property|characteristic|quantity|parameter|ratio|fraction|value)\b",),
    "Matter": (r"\b(?:material|substance|mixture|component|sample|specimen|assembly)\b",),
    "Agent": (r"\b(?:agent|person|organization|institution)\b",),
    "Process": (r"\b(?:process|procedure|operation|technique|method|deposition|etching|preparation|synthesis)\b",),
}

GENERIC_SCOPE_TOKENS = {
    "activity", "characteristic", "class", "concept", "data", "entity", "information", "material",
    "measurement", "method", "object", "parameter", "process", "property", "quantity", "result",
    "sample", "technique", "thing", "value", "agent",
}

# These qualifiers often change the denotation of a scientific term rather
# than merely changing its spelling.  They therefore block automatic exact
# equivalence unless both preferred labels express the same qualifier.
MATERIAL_STATE_AND_FORM_TOKENS = {
    "aqueous", "dispersion", "emulsion", "film", "foam", "gas", "gaseous", "gel", "ink",
    "ion", "ionic", "liquid", "mixture", "molecule", "molecular", "nanoparticle", "particle",
    "powder", "precursor", "slurry", "solid", "solution", "suspension", "vapour", "vapor",
}

# A shared token from this set is not sufficient evidence for a taxonomic
# direction.  This prevents correspondences such as AcidValue -> P-value and
# Agent -> differentiation agent.
GENERIC_DIRECTION_TOKENS = GENERIC_SCOPE_TOKENS | {
    "amount", "assessment", "component", "device", "dimension", "item", "kind", "model",
    "number", "quality", "record", "relation", "role", "setting", "system", "term", "type", "unit",
}

ENTITY_GRANULARITY_MARKERS = {
    "profile": "data",
    "distribution": "data",
    "dataset": "data",
    "data": "data",
    "image": "data",
    "spectrum": "data",
    "curve": "data",
    "instrument": "instrument",
    "microscope": "instrument",
    "spectrometer": "instrument",
    "measurement": "measurement",
    "assay": "measurement",
    "microscopy": "measurement",
    "spectroscopy": "measurement",
    "parameter": "parameter",
    "setting": "parameter",
    "property": "property",
    "quality": "property",
    "agent": "agent",
    "role": "role",
    "unit": "unit",
    "value": "value",
}

CONFLICT_PAIRS = (
    ("radius", "diameter"),
    ("input", "output"),
    ("anode", "cathode"),
    ("primary", "secondary"),
    ("hydrophilic", "hydrophobic"),
    ("mass", "volume"),
    ("instrument", "dataset"),
    ("instrument", "measurement"),
    ("parameter", "dataset"),
)


def refresh_collection_snapshot(
    snapshot_path: str | Path,
    collections: Iterable[str] = DEFAULT_COLLECTIONS,
    *,
    session: requests.Session | None = None,
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    """Freeze TIB catalogue metadata and collection membership."""

    requested = {_collection_key(value): str(value) for value in collections}
    client = session or requests.Session()
    payload = _request_json(
        client,
        f"{TIB_API}/ontologies",
        {"page": 0, "size": 1000},
        timeout=90,
    )
    ontologies = payload.get("_embedded", {}).get("ontologies", [])
    records: list[dict[str, Any]] = []
    memberships: dict[str, list[str]] = {key: [] for key in requested}
    for item in ontologies:
        if not isinstance(item, dict) or not item.get("ontologyId"):
            continue
        record = _catalogue_record(item)
        target_memberships = [
            collection for collection in record["collections"] if _collection_key(collection) in requested
        ]
        if not target_memberships:
            continue
        record["target_collections"] = sorted(target_memberships, key=str.casefold)
        records.append(record)
        for collection in target_memberships:
            memberships[_collection_key(collection)].append(record["ontology_id"])

    canonical_collections = {
        key: {
            "requested_name": requested[key],
            "catalogue_name": _preferred_collection_name(
                [name for record in records for name in record["target_collections"] if _collection_key(name) == key],
                requested[key],
            ),
            "ontology_ids": sorted(set(memberships[key])),
        }
        for key in sorted(requested)
    }
    snapshot = {
        "format": SNAPSHOT_FORMAT,
        "retrieved_at": retrieved_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "api": {
            "base_url": TIB_API,
            "catalogue_endpoint": f"{TIB_API}/ontologies",
            "class_endpoint_template": f"{TIB_API}/v2/ontologies/{{ontology_id}}/classes",
            "search_endpoint": f"{TIB_API}/search",
        },
        "collections": canonical_collections,
        "ontologies": sorted(records, key=lambda row: row["ontology_id"]),
        "unique_ontology_count": len({row["ontology_id"] for row in records}),
    }
    dump_json(Path(snapshot_path), snapshot)
    return snapshot


def load_active_h2kg_classes(registry_path: str | Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    registry_path = Path(registry_path)
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    terms: list[dict[str, Any]] = []
    for term in payload.get("terms", []):
        if term.get("disposition") != "active_local_class":
            continue
        iri = str(term.get("iri", ""))
        if not iri.startswith(H2KG_NS):
            continue
        source_roles = [str(value) for value in term.get("source_roles", []) if value]
        terms.append(
            {
                "h2kg_iri": iri,
                "h2kg_local_name": str(term.get("local_name", iri.rsplit("#", 1)[-1])),
                "h2kg_label": str(term.get("label", "")),
                "h2kg_alt_labels": [str(value) for value in term.get("alt_labels", []) if value],
                "h2kg_definition": str(term.get("definition", "")),
                "h2kg_role": _h2kg_role(term),
                "h2kg_top_branch": str(term.get("top_branch", "")),
                "h2kg_parent_label": str(term.get("parent_label", "")),
                "h2kg_ancestor_path": [str(value) for value in term.get("ancestor_path", [])],
                "h2kg_source_roles": source_roles,
                "h2kg_module": str(term.get("module", "")),
            }
        )
    return sorted(terms, key=lambda row: (row["h2kg_label"].casefold(), row["h2kg_iri"])), payload


def refresh_candidate_cache(
    terms: list[dict[str, Any]],
    snapshot: dict[str, Any],
    cache_path: str | Path,
    *,
    session: requests.Session | None = None,
    max_aliases: int = 3,
) -> dict[str, Any]:
    """Query TIB once per unique H2KG label and enrich plausible candidates."""

    cache_path = Path(cache_path)
    prior = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    query_cache: dict[str, Any] = dict(prior.get("queries", {}))
    detail_cache: dict[str, Any] = dict(prior.get("details", {}))
    prior_candidates = [dict(row) for row in prior.get("candidates", [])]
    target_ontologies = {record["ontology_id"] for record in snapshot.get("ontologies", [])}
    appears_in_targets = target_ontologies

    term_queries: dict[str, list[str]] = {}
    query_labels: list[str] = []
    for term in terms:
        expanded = _term_query_labels(term, max_aliases=max_aliases)
        term_queries[term["h2kg_iri"]] = expanded
        query_labels.extend(expanded)
    query_by_key: dict[str, str] = {}
    for label in query_labels:
        key = _query_key(label)
        previous = query_by_key.get(key)
        if previous is None or (len(label), label.casefold(), label) < (len(previous), previous.casefold(), previous):
            query_by_key[key] = label
    query_labels = sorted(query_by_key.values(), key=str.casefold)
    missing_queries = [
        label
        for label in query_labels
        if _query_key(label) not in query_cache or query_cache[_query_key(label)].get("status") != "ok"
    ]

    def persist_partial(phase: str) -> None:
        dump_json(
            cache_path,
            {
                "format": CANDIDATE_FORMAT,
                "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "snapshot_sha256": _json_sha256(snapshot),
                "taxonomy_class_count": len(terms),
                "complete": False,
                "phase": phase,
                "query_count": len(query_cache),
                "detail_count": len(detail_cache),
                "queries": query_cache,
                "details": detail_cache,
                "candidates": prior_candidates,
            },
        )

    def run_search(labels: tuple[str, ...]) -> list[tuple[str, dict[str, Any]]]:
        client = session or requests.Session()
        if len(labels) == 1:
            query_text = labels[0]
        else:
            query_text = " OR ".join(f'"{_escape_query_phrase(label)}"' for label in labels)
        def search(query: str) -> list[dict[str, Any]]:
            response = _request_json(
                client,
                f"{TIB_API}/search",
                {
                    "q": query,
                    "type": "class",
                    "local": "true",
                    "rows": max(100, min(500, 100 * len(labels))),
                },
                timeout=60,
            )
            return [
                hit
                for hit in (
                    _compact_search_hit(item) for item in response.get("response", {}).get("docs", [])
                )
                if hit.get("iri") and hit.get("label")
            ]

        try:
            hits = search(query_text)
            return [
                (
                    label,
                    {
                        "status": "ok",
                        "batched_query": query_text if len(labels) > 1 else "",
                        "hits": [
                            hit
                            for hit in hits
                            if _labels_equivalent(label, str(hit.get("label", "")))
                            or _lexical_similarity(label, str(hit.get("label", ""))) >= 62
                        ],
                    },
                )
                for label in labels
            ]
        except requests.RequestException as first_error:
            if len(labels) > 1:
                recovered: list[tuple[str, dict[str, Any]]] = []
                for label in labels:
                    recovered.extend(run_search((label,)))
                return recovered
            # TIB's Solr endpoint occasionally rejects an otherwise valid bare
            # query. A quoted exact-phrase retry is semantically equivalent and
            # prevents transient parser failures from becoming benchmark data.
            label = labels[0]
            quoted_query = f'"{_escape_query_phrase(label)}"'
            try:
                hits = search(quoted_query)
                return [
                    (
                        label,
                        {
                            "status": "ok",
                            "fallback": "quoted_exact_phrase",
                            "hits": [
                                hit
                                for hit in hits
                                if _labels_equivalent(label, str(hit.get("label", "")))
                                or _lexical_similarity(label, str(hit.get("label", ""))) >= 62
                            ],
                        },
                    )
                ]
            except requests.RequestException as fallback_error:
                try:
                    hits = []
                    page = 0
                    while True:
                        payload = _request_json(
                            client,
                            f"{TIB_API}/v2/classes",
                            {"search": label, "page": page, "size": 500},
                            timeout=90,
                        )
                        hits.extend(
                            _compact_v2_class_hit(item)
                            for item in payload.get("elements", [])
                            if isinstance(item, dict)
                        )
                        total_pages = int(payload.get("totalPages") or 0)
                        page += 1
                        if page >= total_pages:
                            break
                    return [
                        (
                            label,
                            {
                                "status": "ok",
                                "fallback": "v2_global_class_search",
                                "hits": [
                                    hit
                                    for hit in hits
                                    if hit.get("iri")
                                    and hit.get("label")
                                    and (
                                        _labels_equivalent(label, str(hit.get("label", "")))
                                        or _lexical_similarity(label, str(hit.get("label", ""))) >= 62
                                    )
                                ],
                            },
                        )
                    ]
                except requests.RequestException as v2_error:
                    error = (
                        f"bare query: {first_error}; quoted fallback: {fallback_error}; "
                        f"v2 global fallback: {v2_error}"
                    )
            return [
                (label, {"status": "error", "error": error, "hits": []})
            ]

    request_groups = (
        [(label,) for label in missing_queries]
        if session is not None
        else [tuple(missing_queries[index : index + 4]) for index in range(0, len(missing_queries), 4)]
    )
    for offset in range(0, len(request_groups), 50):
        query_batch = request_groups[offset : offset + 50]
        if session is not None:
            batches = [run_search(labels) for labels in query_batch]
        else:
            with ThreadPoolExecutor(max_workers=6) as executor:
                batches = list(executor.map(run_search, query_batch))
        for batch in batches:
            for label, result in batch:
                query_cache[_query_key(label)] = {"query": label, **result}
        persist_partial("search")

    raw_candidates: dict[tuple[str, str, str], dict[str, Any]] = {
        (
            str(candidate.get("h2kg_iri", "")),
            str(candidate.get("ontology_id", "")).casefold(),
            str(candidate.get("iri", "")),
        ): candidate
        for candidate in prior_candidates
        if candidate.get("h2kg_iri") and candidate.get("ontology_id") and candidate.get("iri")
    }
    for term in terms:
        labels = term_queries[term["h2kg_iri"]]
        for source_label in labels:
            query = query_cache.get(_query_key(source_label), {})
            for hit in query.get("hits", []):
                ontology_id = str(hit.get("ontology_id", "")).casefold()
                similarity = _lexical_similarity(source_label, str(hit.get("label", "")))
                exactish = _labels_equivalent(source_label, str(hit.get("label", "")))
                if ontology_id not in target_ontologies and not exactish:
                    continue
                if not exactish and similarity < 62:
                    continue
                key = (term["h2kg_iri"], ontology_id, str(hit["iri"]))
                candidate = {
                    **hit,
                    "h2kg_iri": term["h2kg_iri"],
                    "source_query": source_label,
                    "lexical_similarity": similarity,
                }
                previous = raw_candidates.get(key)
                if previous is None or candidate["lexical_similarity"] > previous["lexical_similarity"]:
                    raw_candidates[key] = candidate

    detail_requests = sorted(
        {
            (candidate["ontology_id"], candidate["iri"])
            for candidate in raw_candidates.values()
            if candidate.get("ontology_id")
            and _labels_equivalent(str(candidate.get("source_query", "")), str(candidate.get("label", "")))
            and not _candidate_has_detail_evidence(candidate)
            and (
                _detail_key(candidate["ontology_id"], candidate["iri"]) not in detail_cache
                or detail_cache[_detail_key(candidate["ontology_id"], candidate["iri"])].get("status") != "ok"
            )
        }
    )

    def run_detail(request: tuple[str, str]) -> tuple[str, dict[str, Any]]:
        ontology_id, iri = request
        client = session or requests.Session()
        encoded = quote(quote(iri, safe=""), safe="")
        try:
            payload = _request_json(
                client,
                f"{TIB_API}/v2/ontologies/{ontology_id}/classes/{encoded}",
                {},
                timeout=60,
            )
            return _detail_key(ontology_id, iri), {"status": "ok", **_compact_class_detail(payload)}
        except requests.RequestException as error:
            return _detail_key(ontology_id, iri), {"status": "error", "error": str(error)}

    for offset in range(0, len(detail_requests), 100):
        detail_batch = detail_requests[offset : offset + 100]
        if session is not None:
            details = [run_detail(request) for request in detail_batch]
        else:
            with ThreadPoolExecutor(max_workers=6) as executor:
                details = list(executor.map(run_detail, detail_batch))
        for key, detail in details:
            detail_cache[key] = detail
        persist_partial("class-details")

    candidates: list[dict[str, Any]] = []
    for candidate in raw_candidates.values():
        detail = detail_cache.get(_detail_key(candidate["ontology_id"], candidate["iri"]), {})
        merged = {**candidate}
        if detail.get("status") == "ok":
            merged.update({key: value for key, value in detail.items() if key != "status"})
        defined_by = {str(value).casefold() for value in merged.get("defined_by", [])}
        appears_in = {str(value).casefold() for value in merged.get("appears_in", [])}
        if detail.get("status") == "ok":
            merged["native_to_ontology"] = bool(
                merged.get("is_defining_ontology")
                or candidate["ontology_id"] in defined_by
            )
        else:
            # Search requests use local=true, so the hit belongs natively to
            # the ontology named by TIB rather than arriving through an import.
            merged["native_to_ontology"] = candidate["ontology_id"] in target_ontologies
        merged["appears_in_target_ontologies"] = sorted(appears_in & appears_in_targets)
        candidates.append(merged)

    compact_queries = {
        key: {
            field: value
            for field, value in row.items()
            if field in {"query", "status", "error", "fallback", "failed_ontologies"}
        }
        for key, row in query_cache.items()
    }
    query_failures = sum(row.get("status") != "ok" for row in query_cache.values())
    detail_failures = sum(row.get("status") != "ok" for row in detail_cache.values())
    complete = query_failures == 0 and detail_failures == 0
    result = {
        "format": CANDIDATE_FORMAT,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "snapshot_sha256": _json_sha256(snapshot),
        "taxonomy_class_count": len(terms),
        "complete": complete,
        "compacted": complete,
        "phase": "complete" if complete else "retrieval-failed",
        "query_count": len(query_cache),
        "query_failure_count": query_failures,
        "detail_count": len(detail_cache),
        "detail_failure_count": detail_failures,
        "queries": compact_queries if complete else query_cache,
        "details": {} if complete else detail_cache,
        "candidates": sorted(
            candidates,
            key=lambda row: (row["h2kg_iri"], row.get("ontology_id", ""), row.get("iri", "")),
        ),
    }
    dump_json(cache_path, result)
    return result


def _assessment_failures(
    terms: list[dict[str, Any]],
    candidate_cache: dict[str, Any],
) -> list[dict[str, Any]]:
    query_cache = candidate_cache.get("queries", {})
    rows: list[dict[str, Any]] = []
    for term in terms:
        failures: list[dict[str, Any]] = []
        successful_queries = 0
        for label in _term_query_labels(term):
            record = query_cache.get(_query_key(label), {})
            if not record:
                continue
            if record.get("status") == "ok":
                successful_queries += 1
            else:
                failures.append(
                    {
                        "query": label,
                        "status": str(record.get("status") or "missing"),
                        "error": str(record.get("error") or "No cached TIB response."),
                    }
                )
        if failures:
            rows.append(
                {
                    "h2kg_iri": term["h2kg_iri"],
                    "h2kg_label": term["h2kg_label"],
                    "h2kg_role": term["h2kg_role"],
                    "h2kg_top_branch": term["h2kg_top_branch"],
                    "failed_query_count": len(failures),
                    "successful_query_count": successful_queries,
                    "failed_queries": " | ".join(row["query"] for row in failures),
                    "errors": " | ".join(dict.fromkeys(row["error"] for row in failures)),
                    "benchmark_treatment": "publication_blocked_no_semantic_outcome_assigned",
                }
            )
    return rows


def _retrieval_failure_rows(candidate_cache: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, record in sorted(candidate_cache.get("queries", {}).items()):
        if record.get("status") == "ok":
            continue
        rows.append(
            {
                "retrieval_type": "search_query",
                "retrieval_key": key,
                "query_or_iri": str(record.get("query") or key),
                "status": str(record.get("status") or "missing"),
                "error": str(record.get("error") or "No successful cached TIB response."),
                "publication_effect": "blocking",
            }
        )
    for key, record in sorted(candidate_cache.get("details", {}).items()):
        if record.get("status") == "ok":
            continue
        rows.append(
            {
                "retrieval_type": "class_detail",
                "retrieval_key": key,
                "query_or_iri": key.partition("|")[2],
                "status": str(record.get("status") or "missing"),
                "error": str(record.get("error") or "No successful cached TIB class response."),
                "publication_effect": "blocking",
            }
        )
    return rows


def _compact_completed_candidate_cache(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload.get("complete") or payload.get("compacted"):
        return payload
    compacted = dict(payload)
    compacted["compacted"] = True
    compacted["queries"] = {
        key: {
            field: value
            for field, value in row.items()
            if field in {"query", "status", "error", "fallback", "failed_ontologies"}
        }
        for key, row in payload.get("queries", {}).items()
    }
    compacted["details"] = {}
    return compacted


def build_collection_benchmark(
    taxonomy_registry_path: str | Path,
    output_root: str | Path,
    snapshot_path: str | Path,
    candidate_cache_path: str | Path,
    *,
    collections: Iterable[str] = DEFAULT_COLLECTIONS,
    refresh: bool = False,
    retry_failures: bool = False,
    session: requests.Session | None = None,
    existing_mapping_path: str | Path | None = None,
    existing_harmonization_path: str | Path | None = None,
    correction_registry_path: str | Path | None = None,
    require_complete: bool = True,
) -> dict[str, Any]:
    """Build the automated, collection-aware benchmark and reporting package."""

    output_root = Path(output_root)
    target = ensure_dir(output_root / "benchmarks" / "tib_collections")
    taxonomy_registry_path = Path(taxonomy_registry_path)
    snapshot_path = Path(snapshot_path)
    candidate_cache_path = Path(candidate_cache_path)
    if not taxonomy_registry_path.exists():
        message = f"""# H2KG--TIB Collection Benchmark

The offline release did not run this benchmark because the taxonomy registry is unavailable.

- Taxonomy registry: `{taxonomy_registry_path}`

Generate the H2KG taxonomy before running the collection benchmark.
"""
        write_text(target / "README.md", message)
        return {
            "status": "skipped_missing_taxonomy_registry",
            "taxonomy_registry": str(taxonomy_registry_path),
            "target": str(target),
        }
    terms, taxonomy_registry = load_active_h2kg_classes(taxonomy_registry_path)

    if refresh:
        snapshot = refresh_collection_snapshot(snapshot_path, collections, session=session)
        candidate_cache = refresh_candidate_cache(terms, snapshot, candidate_cache_path, session=session)
    elif retry_failures:
        if not snapshot_path.exists() or not candidate_cache_path.exists():
            return _write_missing_collection_cache(target, snapshot_path, candidate_cache_path)
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        candidate_cache = refresh_candidate_cache(terms, snapshot, candidate_cache_path, session=session)
    else:
        if not snapshot_path.exists() or not candidate_cache_path.exists():
            return _write_missing_collection_cache(target, snapshot_path, candidate_cache_path)
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        candidate_cache = json.loads(candidate_cache_path.read_text(encoding="utf-8"))
        if candidate_cache.get("complete") and not candidate_cache.get("compacted"):
            candidate_cache = _compact_completed_candidate_cache(candidate_cache)
            dump_json(candidate_cache_path, candidate_cache)

    assessment_failures = _assessment_failures(terms, candidate_cache)
    retrieval_failures = _retrieval_failure_rows(candidate_cache)
    _write_csv(target / "assessment_failures.csv", assessment_failures, ASSESSMENT_FAILURE_COLUMNS)
    _write_csv(target / "retrieval_failures.csv", retrieval_failures, RETRIEVAL_FAILURE_COLUMNS)
    dump_json(
        target / "retrieval_status.json",
        {
            "complete": not retrieval_failures and bool(candidate_cache.get("complete")),
            "query_failures": int(candidate_cache.get("query_failure_count") or 0),
            "detail_failures": int(candidate_cache.get("detail_failure_count") or 0),
            "failure_count": len(retrieval_failures),
            "publication_status": "blocked" if retrieval_failures else "complete",
        },
    )
    if require_complete and (retrieval_failures or not candidate_cache.get("complete")):
        write_text(
            target / "README.md",
            "# H2KG--TIB Collection Benchmark\n\n"
            "Publication is blocked because the frozen TIB retrieval is incomplete. "
            "See `retrieval_failures.csv`; no failed request has been converted into a semantic outcome.\n",
        )
        raise RuntimeError(
            f"TIB benchmark publication blocked by {len(retrieval_failures)} retrieval failures; "
            "rerun with --refresh after the service recovers."
        )

    existing_mappings = _load_existing_mappings(existing_mapping_path)
    decision_rows = classify_candidates(terms, candidate_cache.get("candidates", []), snapshot, existing_mappings)
    baseline_rows = [
        {
            **row,
            "outcome": row.get("previous_outcome", row.get("outcome", "related_non_equivalent")),
            "final_outcome": row.get("previous_outcome", row.get("outcome", "related_non_equivalent")),
        }
        for row in decision_rows
    ]
    deprecated_class_count = sum(
        1
        for term in taxonomy_registry.get("terms", [])
        if str(term.get("disposition", "")).startswith("deprecated_")
    )
    baseline_summaries = summarize_decisions(
        terms,
        baseline_rows,
        snapshot,
        legacy_policy=True,
        deprecated_class_count=deprecated_class_count,
    )
    summaries = summarize_decisions(
        terms,
        decision_rows,
        snapshot,
        deprecated_class_count=deprecated_class_count,
    )
    _validate_publishable_summaries(summaries)
    summaries["benchmark_summary"]["failed_query_count"] = int(candidate_cache.get("query_failure_count") or 0)
    summaries["benchmark_summary"]["incomplete_h2kg_class_count"] = 0
    summaries["benchmark_summary"]["baseline_h2kg_active_classes_assessed"] = baseline_summaries["benchmark_summary"]["h2kg_active_classes_assessed"]
    summaries["benchmark_summary"]["final_h2kg_active_classes_assessed"] = summaries["benchmark_summary"]["h2kg_active_classes_assessed"]
    summaries["benchmark_summary"]["active_class_count_change"] = (
        summaries["benchmark_summary"]["final_h2kg_active_classes_assessed"]
        - summaries["benchmark_summary"]["baseline_h2kg_active_classes_assessed"]
    )
    summaries["benchmark_summary"]["baseline_collection_summary"] = baseline_summaries["collection_summary"]
    existing_harmonization: dict[str, Any] = {}
    if existing_harmonization_path and Path(existing_harmonization_path).exists():
        existing_harmonization = json.loads(Path(existing_harmonization_path).read_text(encoding="utf-8"))
    harmonization = build_harmonization_registry(
        terms,
        decision_rows,
        snapshot,
        taxonomy_registry,
        existing_harmonization=existing_harmonization,
    )
    corrections = _load_correction_registry(correction_registry_path)
    ambiguity_history = [
        row
        for row in decision_rows
        if row.get("previous_outcome") == "ambiguous_abstained"
        and row.get("final_outcome") != "ambiguous_abstained"
    ]
    exact_label_review = [row for row in decision_rows if _decision_has_exact_label(row)]
    pre_post_rows = _pre_post_comparison_rows(baseline_summaries, summaries)
    ontology_publication_rows = _ontology_publication_rows(summaries["ontology_summary"])

    _write_csv(target / "candidate_decisions.csv", decision_rows, DECISION_COLUMNS)
    _write_csv(target / "collection_summary.csv", summaries["collection_summary"], SUMMARY_COLUMNS)
    _write_csv(target / "ontology_summary.csv", summaries["ontology_summary"], ONTOLOGY_SUMMARY_COLUMNS)
    _write_csv(target / "category_summary.csv", summaries["category_summary"], CATEGORY_SUMMARY_COLUMNS)
    _write_csv(target / "h2kg_collection_coverage.csv", summaries["class_collection_rows"], CLASS_COVERAGE_COLUMNS)
    _write_csv(target / "imported_availability.csv", summaries["imported_availability"], IMPORT_COLUMNS)
    _write_csv(target / "ontology_benchmark.csv", ontology_publication_rows, ONTOLOGY_PUBLICATION_COLUMNS)
    _write_csv(target / "exact_label_review.csv", exact_label_review, DECISION_COLUMNS)
    _write_csv(target / "ambiguity_resolution_history.csv", ambiguity_history, DECISION_COLUMNS)
    _write_csv(target / "pre_post_harmonization.csv", pre_post_rows, PRE_POST_COLUMNS)
    _write_csv(target / "h2kg_corrections.csv", corrections, CORRECTION_COLUMNS)
    dump_json(target / "benchmark_summary.json", summaries["benchmark_summary"])
    dump_json(target / "automatic_harmonization_registry.json", harmonization)
    dump_json(target / "h2kg_corrections.json", {"corrections": corrections})
    write_text(target / "matching_rules.md", collection_matching_rules())
    write_text(target / "manuscript_table.md", manuscript_table(summaries, snapshot))
    write_text(target / "ontology_benchmark.md", _ontology_publication_markdown(ontology_publication_rows))
    write_text(target / "README.md", collection_readme(summaries, snapshot, snapshot_path, candidate_cache_path))
    write_text(target / "tib_collection_benchmark.html", benchmark_html(summaries, snapshot))
    _write_benchmark_workbooks(
        target,
        summaries,
        decision_rows,
        assessment_failures,
        retrieval_failures,
        snapshot,
        harmonization,
        ontology_publication_rows,
        exact_label_review,
        ambiguity_history,
        pre_post_rows,
        corrections,
    )

    docs_assets = ensure_dir(output_root / "docs" / "benchmarks" / "tib_collections")
    for name in [
        "h2kg_tib_collection_benchmark.xlsx",
        "h2kg_tib_manuscript_tables.xlsx",
        "candidate_decisions.csv",
        "collection_summary.csv",
        "ontology_summary.csv",
        "ontology_benchmark.csv",
        "ontology_benchmark.md",
        "category_summary.csv",
        "h2kg_collection_coverage.csv",
        "imported_availability.csv",
        "assessment_failures.csv",
        "retrieval_failures.csv",
        "retrieval_status.json",
        "exact_label_review.csv",
        "ambiguity_resolution_history.csv",
        "pre_post_harmonization.csv",
        "h2kg_corrections.csv",
        "h2kg_corrections.json",
        "automatic_harmonization_registry.json",
        "benchmark_summary.json",
        "manuscript_table.md",
        "matching_rules.md",
        "README.md",
        "tib_collection_benchmark.html",
    ]:
        shutil.copy2(target / name, docs_assets / name)
    docs_target = ensure_dir(output_root / "docs" / "pages") / "tib-benchmark.html"
    write_text(docs_target, benchmark_html(summaries, snapshot, docs_mode=True))
    return summaries["benchmark_summary"]


def classify_candidates(
    terms: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    snapshot: dict[str, Any],
    existing_mappings: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Classify candidate correspondences without a human-review state."""

    terms_by_iri = {term["h2kg_iri"]: term for term in terms}
    target_ontologies = {record["ontology_id"] for record in snapshot.get("ontologies", [])}
    assessed: list[dict[str, Any]] = []
    for candidate in candidates:
        term = terms_by_iri.get(candidate.get("h2kg_iri"))
        ontology_id = str(candidate.get("ontology_id", "")).casefold()
        if term is None or ontology_id not in target_ontologies:
            continue
        assessed.append(_assess_candidate(term, candidate, snapshot))

    # Previously generated machine mappings are deliberately not fed back as
    # evidence.  Otherwise a weak mapping from an earlier release can make
    # itself authoritative forever. Explicitly configured mappings remain
    # eligible evidence and take precedence for their exact IRI pair.
    manual_pairs: set[tuple[str, str]] = set()
    for mapping in existing_mappings or []:
        mapping_status = str(mapping.get("status", "")).casefold()
        decision_status = str(mapping.get("decision_status", "")).casefold()
        if mapping_status == "machine_safe" or decision_status == "accepted-machine-safe":
            continue
        term = terms_by_iri.get(str(mapping.get("local_iri", "")))
        ontology_id = str(mapping.get("tib_ontology_id") or mapping.get("source") or "").casefold()
        if term is None or ontology_id not in target_ontologies:
            continue
        relation = str(mapping.get("relation", ""))
        outcome = {
            "skos:exactMatch": "machine_exact_equivalent",
            "owl:equivalentClass": "machine_exact_equivalent",
            "rdfs:subClassOf": "h2kg_narrower",
            "skos:broadMatch": "h2kg_narrower",
            "skos:narrowMatch": "h2kg_broader",
            "skos:closeMatch": "related_non_equivalent",
        }.get(relation, "related_non_equivalent")
        pair = (term["h2kg_iri"], str(mapping.get("target_iri", "")))
        manual_pairs.add(pair)
        assessed.append(
            {
                **{column: "" for column in DECISION_COLUMNS},
                "mapping_key": f"{term['h2kg_iri']}|{ontology_id}|{mapping.get('target_iri', '')}",
                **term,
                "collection_memberships": " | ".join(_ontology_collections(snapshot, ontology_id)),
                "ontology_id": ontology_id,
                "external_iri": str(mapping.get("target_iri", "")),
                "external_label": str(mapping.get("target_label", "")),
                "external_definition": "",
                "external_role": "",
                "external_parent_labels": "",
                "native_to_ontology": True,
                "appears_in_ontologies": ontology_id,
                "lexical_similarity": float(mapping.get("score") or 100),
                "role_compatible": True,
                "definition_conflict": False,
                "previous_outcome": outcome,
                "final_outcome": outcome,
                "outcome": outcome,
                "rule_id": "MANUAL-MAPPING-000",
                "confidence": "high",
                "scope_evidence": "Explicitly reviewed H2KG mapping registry.",
                "decision_basis": "Configured or human-reviewed H2KG external mapping; manual decision takes precedence for this IRI pair.",
                "evidence_source": "existing_reviewed_alignment_registry",
                "safe_for_harmonization": False,
            }
        )

    if manual_pairs:
        assessed = [
            row
            for row in assessed
            if (
                (row["h2kg_iri"], row["external_iri"]) not in manual_pairs
                or row.get("evidence_source") == "existing_reviewed_alignment_registry"
            )
        ]

    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in assessed:
        key = (row["h2kg_iri"], row["ontology_id"], row["external_iri"])
        previous = deduped.get(key)
        if previous is None or _decision_sort_key(row) < _decision_sort_key(previous):
            deduped[key] = row
    adjudicated = _adjudicate_equivalence_collisions(list(deduped.values()))
    return sorted(adjudicated, key=lambda row: (row["h2kg_iri"], row["ontology_id"], _decision_sort_key(row)))


def summarize_decisions(
    terms: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    snapshot: dict[str, Any],
    *,
    incomplete_term_iris: set[str] | None = None,
    legacy_policy: bool = False,
    deprecated_class_count: int = 0,
) -> dict[str, Any]:
    denominator = len(terms)
    incomplete_term_iris = incomplete_term_iris or set()
    terms_by_iri = {term["h2kg_iri"]: term for term in terms}
    ontology_by_id = {record["ontology_id"]: record for record in snapshot.get("ontologies", [])}
    decisions_by_pair: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in decisions:
        if row.get("native_to_ontology"):
            decisions_by_pair[(row["h2kg_iri"], row["ontology_id"])].append(row)
    pair_resolver = _resolve_pair_legacy if legacy_policy else _resolve_pair
    collection_resolver = _resolve_collection_legacy if legacy_policy else _resolve_collection
    shared_target_conflicts = _shared_exact_target_pairs(decisions, resolver=pair_resolver)

    ontology_outcomes: dict[tuple[str, str], tuple[str, dict[str, Any] | None]] = {}
    ontology_summary: list[dict[str, Any]] = []
    collection_members = _collection_members(snapshot)
    for collection, ontology_ids in collection_members.items():
        for ontology_id in ontology_ids:
            if ontology_id in UNASSESSED_NATIVE_ONTOLOGIES:
                record = ontology_by_id.get(ontology_id, {})
                ontology_summary.append(
                    _summary_row(
                        scope_type="ontology",
                        collection=collection,
                        ontology_id=ontology_id,
                        ontology_title=str(record.get("title", "")),
                        ontology_version=str(record.get("version") or ""),
                        tib_reported_term_count=int(record.get("number_of_terms") or 0),
                        member_ontology_count=1,
                        denominator=0,
                        counts=Counter(),
                        assessment_status="not_assessed_native_evidence_unavailable",
                        native_evidence_status=UNASSESSED_NATIVE_ONTOLOGIES[ontology_id],
                        assessed_member_ontology_count=0,
                    )
                )
                continue
            counts = Counter()
            for term in terms:
                outcome, best = pair_resolver(decisions_by_pair.get((term["h2kg_iri"], ontology_id), []))
                if (
                    outcome in {"exact_iri_reuse", "machine_exact_equivalent"}
                    and (term["h2kg_iri"], ontology_id) in shared_target_conflicts
                ):
                    outcome = "ambiguous_abstained" if legacy_policy else "related_non_equivalent"
                    best = {
                        **(best or {}),
                        "decision_basis": (
                            "The same external class is an equivalence candidate for multiple H2KG classes; "
                            + ("the legacy matcher abstained." if legacy_policy else "equivalence was conservatively withheld.")
                        ),
                    }
                if outcome == "unmatched" and term["h2kg_iri"] in incomplete_term_iris:
                    if not legacy_policy:
                        raise RuntimeError("Retrieval failure reached final semantic summarization.")
                    outcome = "ambiguous_abstained"
                    best = {
                        "ontology_id": ontology_id,
                        "external_iri": "",
                        "external_label": "",
                        "decision_basis": "One or more TIB searches failed; the matcher abstained instead of reporting unmatched.",
                    }
                ontology_outcomes[(term["h2kg_iri"], ontology_id)] = (outcome, best)
                counts[outcome] += 1
            record = ontology_by_id.get(ontology_id, {})
            ontology_summary.append(
                _summary_row(
                    scope_type="ontology",
                    collection=collection,
                    ontology_id=ontology_id,
                    ontology_title=str(record.get("title", "")),
                    ontology_version=str(record.get("version") or ""),
                    tib_reported_term_count=int(record.get("number_of_terms") or 0),
                    member_ontology_count=1,
                    denominator=denominator,
                    counts=counts,
                )
            )

    unique_ontology_ids = {ontology_id for values in collection_members.values() for ontology_id in values}
    assessed_unique_ontology_ids = unique_ontology_ids - set(UNASSESSED_NATIVE_ONTOLOGIES)
    expected_unique_ontology_class_decisions = denominator * len(assessed_unique_ontology_ids)
    if len(ontology_outcomes) != expected_unique_ontology_class_decisions:
        raise ValueError(
            "Ontology-level benchmark did not assign every active H2KG class exactly once for every unique "
            f"ontology: expected {expected_unique_ontology_class_decisions}, "
            f"found {len(ontology_outcomes)}."
        )
    assessed_membership_count = sum(
        sum(1 for ontology_id in values if ontology_id not in UNASSESSED_NATIVE_ONTOLOGIES)
        for values in collection_members.values()
    )
    ontology_class_assignments = denominator * assessed_membership_count

    class_collection_rows: list[dict[str, Any]] = []
    collection_summary: list[dict[str, Any]] = []
    category_summary: list[dict[str, Any]] = []
    for collection, ontology_ids in collection_members.items():
        assessed_ontology_ids = [
            ontology_id for ontology_id in ontology_ids if ontology_id not in UNASSESSED_NATIVE_ONTOLOGIES
        ]
        counts = Counter()
        category_counts: dict[str, Counter] = defaultdict(Counter)
        for term in terms:
            outcomes = [ontology_outcomes[(term["h2kg_iri"], ontology_id)] for ontology_id in assessed_ontology_ids]
            outcome, best = collection_resolver(outcomes)
            counts[outcome] += 1
            category_counts[term["h2kg_top_branch"]][outcome] += 1
            class_collection_rows.append(
                {
                    **term,
                    "collection": collection,
                    "outcome": outcome,
                    "best_ontology_id": best.get("ontology_id", "") if best else "",
                    "best_external_iri": best.get("external_iri", "") if best else "",
                    "best_external_label": best.get("external_label", "") if best else "",
                    "decision_basis": best.get("decision_basis", "No candidate in a member ontology.") if best else "No candidate in a member ontology.",
                }
            )
        collection_summary.append(
            _summary_row(
                scope_type="collection",
                collection=collection,
                ontology_id="ALL",
                ontology_title=f"{collection} union (native classes, IRIs deduplicated)",
                ontology_version=str(snapshot.get("retrieved_at", "")),
                tib_reported_term_count=sum(int(ontology_by_id.get(value, {}).get("number_of_terms") or 0) for value in ontology_ids),
                member_ontology_count=len(ontology_ids),
                denominator=denominator,
                counts=counts,
                assessed_member_ontology_count=len(assessed_ontology_ids),
            )
        )
        for category, category_counter in sorted(category_counts.items()):
            category_denominator = sum(1 for term in terms if term["h2kg_top_branch"] == category)
            row = {
                "collection": collection,
                "h2kg_top_branch": category,
                "h2kg_classes_assessed": category_denominator,
            }
            for outcome_name in OUTCOMES:
                row[f"{outcome_name}_count"] = category_counter[outcome_name]
                row[f"{outcome_name}_percent"] = _percent(category_counter[outcome_name], category_denominator)
            category_summary.append(row)

    imported_availability: list[dict[str, Any]] = []
    for row in decisions:
        for ontology_id in str(row.get("appears_in_ontologies", "")).split(" | "):
            ontology_id = ontology_id.strip().casefold()
            if not ontology_id or ontology_id == row["ontology_id"]:
                continue
            for collection, ontology_ids in collection_members.items():
                if ontology_id in ontology_ids:
                    imported_availability.append(
                        {
                            "collection": collection,
                            "hosting_ontology_id": ontology_id,
                            "defining_ontology_id": row["ontology_id"],
                            "h2kg_iri": row["h2kg_iri"],
                            "h2kg_label": row["h2kg_label"],
                            "external_iri": row["external_iri"],
                            "external_label": row["external_label"],
                            "outcome": row["outcome"],
                        }
                    )

    benchmark_summary = {
        "format": BENCHMARK_FORMAT,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "tib_retrieved_at": snapshot.get("retrieved_at"),
        "h2kg_active_classes_assessed": denominator,
        "deprecated_h2kg_classes_excluded": deprecated_class_count,
        "collections": sorted(collection_members),
        "unique_target_ontologies": len({value for values in collection_members.values() for value in values}),
        "assessed_unique_target_ontologies": len(assessed_unique_ontology_ids),
        "catalogue_collection_memberships": sum(len(values) for values in collection_members.values()),
        "assessed_collection_memberships": assessed_membership_count,
        "unassessed_ontologies": dict(UNASSESSED_NATIVE_ONTOLOGIES),
        "candidate_decisions": len(decisions),
        "collection_summary": collection_summary,
        "ontology_rows": len(ontology_summary),
        "unique_ontology_class_decisions": len(ontology_outcomes),
        "expected_unique_ontology_class_decisions": expected_unique_ontology_class_decisions,
        "ontology_class_assignments": ontology_class_assignments,
        "expected_ontology_class_assignments": denominator * assessed_membership_count,
        "classification_policy": (
            "legacy machine-safe tiered coverage with abstention"
            if legacy_policy
            else "evidence-weighted zero-semantic-abstention coverage; native classes are primary"
        ),
        "percent_denominator": "All active local H2KG classes",
    }
    return {
        "benchmark_summary": benchmark_summary,
        "collection_summary": collection_summary,
        "ontology_summary": sorted(ontology_summary, key=lambda row: (row["collection"], row["ontology_id"])),
        "category_summary": category_summary,
        "class_collection_rows": class_collection_rows,
        "imported_availability": sorted(
            {tuple(row.items()): row for row in imported_availability}.values(),
            key=lambda row: (row["collection"], row["hosting_ontology_id"], row["h2kg_label"]),
        ),
    }


def build_harmonization_registry(
    terms: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    snapshot: dict[str, Any],
    taxonomy_registry: dict[str, Any],
    *,
    existing_harmonization: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create deterministic safe mappings and non-destructive label actions."""

    term_by_iri = {term["h2kg_iri"]: term for term in terms}
    rows_by_pair: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in decisions:
        if row.get("native_to_ontology") and str(row.get("ontology_id", "")).casefold() not in UNASSESSED_NATIVE_ONTOLOGIES:
            rows_by_pair[(row["h2kg_iri"], row["ontology_id"])].append(row)
    publishable_rows: list[dict[str, Any]] = []
    shared_target_conflicts = _shared_exact_target_pairs(decisions)
    for rows in rows_by_pair.values():
        outcome, best = _resolve_pair(rows)
        if (
            outcome in {
                "exact_iri_reuse",
                "machine_exact_equivalent",
                "h2kg_narrower",
                "h2kg_broader",
            }
            and best
            and best.get("safe_for_harmonization")
            and best.get("confidence") == "high"
            and (
                outcome not in {"exact_iri_reuse", "machine_exact_equivalent"}
                or (best["h2kg_iri"], best["ontology_id"]) not in shared_target_conflicts
            )
        ):
            publishable_rows.append(best)

    ontology_by_id = {
        str(record.get("ontology_id", "")).casefold(): record
        for record in snapshot.get("ontologies", [])
        if record.get("ontology_id")
    }
    snapshot_sha256 = _json_sha256(snapshot)
    relation_for_outcome = {
        "machine_exact_equivalent": "skos:exactMatch",
        "h2kg_narrower": "skos:broadMatch",
        "h2kg_broader": "skos:narrowMatch",
    }
    mappings: list[dict[str, Any]] = []
    iri_reuse: list[dict[str, Any]] = []
    for row in publishable_rows:
        ontology = ontology_by_id.get(str(row["ontology_id"]).casefold(), {})
        common = {
            "local_iri": row["h2kg_iri"],
            "local_label": row["h2kg_label"],
            "target_iri": row["external_iri"],
            "target_label": row["external_label"],
            "tib_ontology_id": row["ontology_id"],
            "tib_ontology_title": str(ontology.get("title", row["ontology_id"])),
            "tib_ontology_version": str(ontology.get("version") or "version-not-reported-in-TIB-snapshot"),
            "tib_catalogue_url": f"https://terminology.tib.eu/ts/ontologies/{row['ontology_id']}",
            "collections": [value.strip() for value in row["collection_memberships"].split("|") if value.strip()],
            "outcome": row["outcome"],
            "confidence": row["confidence"],
            "rule_id": row["rule_id"],
            "status": "machine_safe",
            "publication_status": "asserted" if row["outcome"] != "exact_iri_reuse" else "iri-reused-no-triple",
            "decision_status": "automated-strict-gate",
            "decision_basis": row["decision_basis"],
            "scope_evidence": row.get("scope_evidence", ""),
            "snapshot_retrieved_at": snapshot.get("retrieved_at"),
            "snapshot_sha256": snapshot_sha256,
        }
        if row["outcome"] == "exact_iri_reuse":
            iri_reuse.append(common)
            continue
        mappings.append(
            {
                **common,
                "relation": relation_for_outcome[row["outcome"]],
            }
        )

    # A pair receives at most one SKOS mapping predicate.  This also keeps
    # repeated collection membership from producing duplicate assertions.
    relation_priority = {"skos:exactMatch": 0, "skos:broadMatch": 1, "skos:narrowMatch": 2}
    mappings_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    for row in mappings:
        key = (row["local_iri"], row["target_iri"])
        previous = mappings_by_pair.get(key)
        if previous is None or relation_priority[row["relation"]] < relation_priority[previous["relation"]]:
            mappings_by_pair[key] = row
    mappings = list(mappings_by_pair.values())

    exact_rows = [
        row
        for row in publishable_rows
        if row.get("outcome") in {"exact_iri_reuse", "machine_exact_equivalent"}
    ]

    labels_in_use = {term["h2kg_label"].casefold(): term["h2kg_iri"] for term in terms}
    by_term: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in exact_rows:
        by_term[row["h2kg_iri"]].append(row)
    label_change_candidates: list[dict[str, Any]] = []
    for iri, rows in sorted(by_term.items()):
        term = term_by_iri[iri]
        if term.get("h2kg_role") != "Measurement":
            continue
        candidates = sorted(rows, key=_canonical_target_sort_key)
        target = candidates[0]
        old_label = term["h2kg_label"]
        new_label = _display_label(str(target["external_label"]))
        if re.search(r"[a-z][A-Z]", new_label):
            continue
        if normalized_label(old_label) == normalized_label(new_label):
            continue
        if normalized_label(old_label, remove_role_words=True) != normalized_label(new_label, remove_role_words=True):
            continue
        collision = labels_in_use.get(new_label.casefold())
        if collision and collision != iri:
            continue
        label_change_candidates.append(
            {
                "local_iri": iri,
                "old_preferred_label": old_label,
                "new_preferred_label": new_label,
                "add_alt_label": old_label,
                "target_iri": target["external_iri"],
                "target_ontology_id": target["ontology_id"],
                "status": "machine_safe",
                "rationale": "Controlled role-word normalization with compatible semantic role and unique external target.",
            }
        )
    current_label_change_iris = {row["local_iri"] for row in label_change_candidates}
    for row in (existing_harmonization or {}).get("label_changes", []):
        iri = str(row.get("local_iri", ""))
        if iri in current_label_change_iris:
            continue
        term = term_by_iri.get(iri)
        if not term or row.get("status") != "machine_safe":
            continue
        old_label = str(row.get("old_preferred_label", ""))
        new_label = str(row.get("new_preferred_label", ""))
        if normalized_label(term["h2kg_label"]) != normalized_label(new_label):
            continue
        if old_label.casefold() not in {str(value).casefold() for value in term.get("h2kg_alt_labels", [])}:
            continue
        retained = dict(row)
        retained["new_preferred_label"] = term["h2kg_label"]
        retained["rationale"] = (
            "Previously applied machine-safe preferred-label normalization retained for stable taxonomy display; "
            "the current benchmark may classify its external target more conservatively."
        )
        label_change_candidates.append(retained)
    deduped_label_candidates = {
        (row["local_iri"], str(row["new_preferred_label"]).casefold()): row
        for row in label_change_candidates
    }
    label_change_candidates = list(deduped_label_candidates.values())
    proposed_label_counts = Counter(
        str(row["new_preferred_label"]).casefold() for row in label_change_candidates
    )
    collision_free = [
        row
        for row in label_change_candidates
        if proposed_label_counts[str(row["new_preferred_label"]).casefold()] == 1
    ]
    label_changes_by_iri: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in collision_free:
        label_changes_by_iri[row["local_iri"]].append(row)
    label_changes = [
        sorted(
            rows,
            key=lambda row: (
                ONTOLOGY_PRIORITY.get(str(row.get("target_ontology_id", "")).casefold(), 100),
                len(str(row.get("new_preferred_label", ""))),
                str(row.get("new_preferred_label", "")).casefold(),
            ),
        )[0]
        for rows in label_changes_by_iri.values()
    ]

    return {
        "format": HARMONIZATION_FORMAT,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "snapshot_retrieved_at": snapshot.get("retrieved_at"),
        "snapshot_sha256": _json_sha256(snapshot),
        "taxonomy_version": taxonomy_registry.get("version"),
        "taxonomy_source_sha256": taxonomy_registry.get("source_sha256"),
        "policy": "preserve-h2kg-iris; strict-exact-and-high-confidence-directional-skos; no-automatic-imports",
        "mappings": sorted(mappings, key=lambda row: (row["local_iri"], row["tib_ontology_id"], row["target_iri"])),
        "exact_iri_reuse": sorted(iri_reuse, key=lambda row: (row["local_iri"], row["tib_ontology_id"])),
        "label_changes": sorted(label_changes, key=lambda row: row["local_iri"]),
        "non_asserted_evidence_counts": dict(
            sorted(
                Counter(
                    str(row.get("outcome", ""))
                    for row in decisions
                    if not row.get("safe_for_harmonization")
                    or row.get("confidence") != "high"
                    or row.get("outcome") == "related_non_equivalent"
                ).items()
            )
        ),
        "owl_imports_added": [],
    }


def apply_harmonization_registry(
    benchmark_registry_path: str | Path,
    config_registry_path: str | Path,
) -> dict[str, Any]:
    """Install the generated safe overlay without editing the asserted v1 source."""

    source = Path(benchmark_registry_path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("format") not in {"h2kg-tib-auto-harmonization/v1", HARMONIZATION_FORMAT}:
        raise ValueError(f"Unsupported harmonization registry: {payload.get('format')}")
    unsafe = [row for row in payload.get("mappings", []) if row.get("status") != "machine_safe"]
    unsafe.extend(row for row in payload.get("label_changes", []) if row.get("status") != "machine_safe")
    if unsafe:
        raise ValueError("Harmonization registry contains non-machine-safe decisions.")
    supported_relations = {"skos:exactMatch", "skos:broadMatch", "skos:narrowMatch"}
    invalid_relations = [
        row
        for row in payload.get("mappings", [])
        if payload.get("format") == HARMONIZATION_FORMAT and row.get("relation") not in supported_relations
    ]
    if invalid_relations:
        raise ValueError("Harmonization registry contains a non-SKOS or unsupported automatic relation.")
    target = Path(config_registry_path)
    dump_json(target, payload)
    return {
        "status": "applied",
        "source": str(source),
        "target": str(target),
        "mapping_count": len(payload.get("mappings", [])),
        "label_change_count": len(payload.get("label_changes", [])),
        "owl_imports_added": 0,
    }


def _assess_candidate(
    term: dict[str, Any],
    candidate: dict[str, Any],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    external_label = str(candidate.get("label", ""))
    synonyms = [str(value) for value in candidate.get("synonyms", []) if value]
    h2kg_labels = [term["h2kg_label"], *term.get("h2kg_alt_labels", [])]
    external_labels = [external_label, *synonyms]
    exact_iri = term["h2kg_iri"] == candidate.get("iri")
    exact_preferred_label = normalized_label(term["h2kg_label"]) == normalized_label(external_label)
    controlled_preferred_equivalent = _controlled_equivalent(term["h2kg_label"], external_label)
    exact_alias = any(
        normalized_label(left) == normalized_label(right)
        for left in h2kg_labels
        for right in external_labels
        if left != term["h2kg_label"] or right != external_label
    )
    exact_label = exact_preferred_label or exact_alias
    normalized_equivalent = controlled_preferred_equivalent or any(
        _controlled_equivalent(left, right) for left in h2kg_labels for right in external_labels
    )
    role_evidence = _external_role_evidence(candidate)
    external_role = str(role_evidence["role"])
    role_compatible = _roles_compatible(term["h2kg_role"], external_role)
    definition_conflict = _definition_conflict(
        " ".join([term["h2kg_label"], term.get("h2kg_definition", "")]),
        " ".join([external_label, str(candidate.get("definition", ""))]),
    )
    similarity = max(
        [_lexical_similarity(left, right) for left in h2kg_labels for right in external_labels] or [0.0]
    )
    active_native_class = (
        bool(candidate.get("native_to_ontology", True))
        and not bool(candidate.get("is_obsolete"))
        and str(candidate.get("type") or "class").casefold() == "class"
    )
    state_conflict, state_basis = _material_state_or_form_conflict(term, candidate)
    granularity_conflict, granularity_basis = _granularity_conflict(term, candidate)
    scope_supported, scope_basis = _equivalence_scope_supported(
        term,
        candidate,
        role_evidence,
        exact_preferred_label=exact_preferred_label,
        controlled_preferred_equivalent=controlled_preferred_equivalent,
        alias_only=not exact_preferred_label and not controlled_preferred_equivalent,
    )
    directional_outcome, directional_confidence, directional_basis = _directional_scope_relation(
        term,
        candidate,
        role_evidence,
    )
    previous_outcome = _legacy_candidate_outcome(term, candidate)

    if exact_iri and active_native_class:
        outcome = "exact_iri_reuse"
        rule_id = "EQUIV-IRI-001"
        confidence = "high"
        basis = "The H2KG class and TIB entity use the same stable IRI."
    elif (
        (exact_label or normalized_equivalent)
        and active_native_class
        and role_compatible
        and not definition_conflict
        and not state_conflict
        and not granularity_conflict
        and scope_supported
    ):
        outcome = "machine_exact_equivalent"
        rule_id = "EQUIV-SCOPE-002"
        confidence = "high"
        basis = (
            "Equivalent preferred/alternate labels are supported by active native-class status, "
            f"compatible semantic roles, compatible state and granularity, and {scope_basis}."
        )
    elif (
        directional_outcome
        and active_native_class
        and role_compatible
        and not definition_conflict
        and not granularity_conflict
    ):
        outcome = directional_outcome
        rule_id = (
            "SUBSUMPTION-H2KG-NARROWER-003"
            if outcome == "h2kg_narrower"
            else "SUBSUMPTION-H2KG-BROADER-004"
        )
        confidence = directional_confidence
        basis = directional_basis
    elif exact_label or normalized_equivalent:
        outcome = "related_non_equivalent"
        rule_id = "RELATED-EXACT-LABEL-SAFEGUARD-005"
        confidence = "high"
        failed_checks = []
        if not active_native_class:
            failed_checks.append("active native OWL-class status")
        if not role_compatible:
            failed_checks.append("semantic-role compatibility")
        if definition_conflict:
            failed_checks.append("non-conflicting scope")
        if state_conflict:
            failed_checks.append(state_basis)
        if granularity_conflict:
            failed_checks.append(granularity_basis)
        if not scope_supported:
            failed_checks.append("definition or hierarchy support")
        basis = "Lexical identity was retained as related because it failed " + ", ".join(
            failed_checks or ["the conservative equivalence gate"]
        ) + "."
    elif role_compatible and similarity >= 70 and not definition_conflict:
        outcome = "related_non_equivalent"
        rule_id = "RELATED-ROLE-LEXICAL-006"
        confidence = "medium"
        basis = "Role-compatible lexical correspondence was found without equivalence-grade evidence."
    else:
        outcome = "related_non_equivalent"
        rule_id = "RELATED-CANDIDATE-007"
        confidence = "low"
        basis = "TIB returned the class as a search candidate, but equivalence was not established."

    ontology_id = str(candidate.get("ontology_id", "")).casefold()
    appears_in = sorted({str(value).casefold() for value in candidate.get("appears_in", []) if value})
    return {
        "mapping_key": f"{term['h2kg_iri']}|{ontology_id}|{candidate.get('iri', '')}",
        **term,
        "collection_memberships": " | ".join(_ontology_collections(snapshot, ontology_id)),
        "ontology_id": ontology_id,
        "external_iri": str(candidate.get("iri", "")),
        "external_label": external_label,
        "external_definition": str(candidate.get("definition", "")),
        "external_role": external_role,
        "external_role_confidence": role_evidence["confidence"],
        "external_role_evidence": json.dumps(role_evidence, ensure_ascii=False, sort_keys=True),
        "external_parent_labels": " | ".join(candidate.get("ancestor_labels", [])),
        "external_direct_parent_iris": " | ".join(candidate.get("direct_parent_iris", [])),
        "external_ancestor_iris": " | ".join(candidate.get("ancestor_iris", [])),
        "external_type": str(candidate.get("type") or "class"),
        "external_obsolete": bool(candidate.get("is_obsolete")),
        "native_to_ontology": bool(candidate.get("native_to_ontology", True)),
        "appears_in_ontologies": " | ".join(appears_in),
        "lexical_similarity": round(float(similarity), 2),
        "role_compatible": role_compatible,
        "definition_conflict": definition_conflict,
        "material_state_conflict": state_conflict,
        "granularity_conflict": granularity_conflict,
        "previous_outcome": previous_outcome,
        "final_outcome": outcome,
        "outcome": outcome,
        "rule_id": rule_id,
        "confidence": confidence,
        "scope_evidence": scope_basis,
        "decision_basis": basis,
        "evidence_source": "tib_api_automatic",
        "safe_for_harmonization": (
            confidence == "high"
            and outcome in {
                "exact_iri_reuse",
                "machine_exact_equivalent",
                "h2kg_narrower",
                "h2kg_broader",
            }
        ),
    }


def _resolve_pair(rows: list[dict[str, Any]]) -> tuple[str, dict[str, Any] | None]:
    if not rows:
        return "unmatched", None
    ordered = sorted(rows, key=_decision_sort_key)
    best = ordered[0]
    same_rank = [row for row in ordered if OUTCOME_RANK[row["outcome"]] == OUTCOME_RANK[best["outcome"]]]
    if best["outcome"] in {"exact_iri_reuse", "machine_exact_equivalent"}:
        distinct_targets = {row["external_iri"] for row in same_rank}
        if len(distinct_targets) > 1:
            return "related_non_equivalent", {
                **best,
                "outcome": "related_non_equivalent",
                "final_outcome": "related_non_equivalent",
                "rule_id": "RELATED-EQUIVALENCE-COLLISION-008",
                "decision_basis": "Multiple equivalence-grade targets exist in the same ontology; no unique canonical equivalence target was established.",
                "safe_for_harmonization": False,
            }
    return best["outcome"], best


def _resolve_pair_legacy(rows: list[dict[str, Any]]) -> tuple[str, dict[str, Any] | None]:
    if not rows:
        return "unmatched", None
    ordered = sorted(rows, key=_legacy_decision_sort_key)
    best = ordered[0]
    same_rank = [row for row in ordered if OUTCOME_RANK[row["outcome"]] == OUTCOME_RANK[best["outcome"]]]
    if best["outcome"] in {"exact_iri_reuse", "machine_exact_equivalent"}:
        distinct_targets = {row["external_iri"] for row in same_rank}
        if len(distinct_targets) > 1:
            return "ambiguous_abstained", {
                **best,
                "decision_basis": "Multiple equivalence-grade targets exist in the same ontology; the legacy matcher abstained.",
                "safe_for_harmonization": False,
            }
    return best["outcome"], best


def _shared_exact_target_pairs(
    decisions: list[dict[str, Any]],
    *,
    resolver: Any = _resolve_pair,
) -> set[tuple[str, str]]:
    rows_by_pair: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in decisions:
        if row.get("native_to_ontology"):
            rows_by_pair[(row["h2kg_iri"], row["ontology_id"])].append(row)
    targets: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for pair, rows in rows_by_pair.items():
        outcome, best = resolver(rows)
        if outcome in {"exact_iri_reuse", "machine_exact_equivalent"} and best:
            targets[(best["ontology_id"], best["external_iri"])].append(pair)
    conflicts: set[tuple[str, str]] = set()
    for pairs in targets.values():
        if len({h2kg_iri for h2kg_iri, _ in pairs}) > 1:
            conflicts.update(pairs)
    return conflicts


def _resolve_collection(
    outcomes: list[tuple[str, dict[str, Any] | None]],
) -> tuple[str, dict[str, Any] | None]:
    available = [(outcome, row) for outcome, row in outcomes if outcome != "unmatched"]
    if not available:
        return "unmatched", None
    for preferred in ("exact_iri_reuse", "machine_exact_equivalent"):
        matches = [(outcome, row) for outcome, row in available if outcome == preferred]
        if matches:
            return preferred, sorted((row for _, row in matches if row), key=_canonical_target_sort_key)[0]
    hierarchy = {outcome for outcome, _ in available if outcome in {"h2kg_narrower", "h2kg_broader"}}
    if len(hierarchy) > 1:
        row = next((row for _, row in available if row), None)
        return "related_non_equivalent", {
            **(row or {}),
            "outcome": "related_non_equivalent",
            "final_outcome": "related_non_equivalent",
            "rule_id": "RELATED-DIRECTION-CONFLICT-009",
            "decision_basis": "Member ontologies provide conflicting hierarchy directions; collection-level subsumption is not defensible.",
        }
    if hierarchy:
        selected = next(iter(hierarchy))
        rows = [row for outcome, row in available if outcome == selected and row]
        return selected, sorted(rows, key=_legacy_decision_sort_key)[0]
    for preferred in ("related_non_equivalent", "ambiguous_abstained"):
        rows = [row for outcome, row in available if outcome == preferred and row]
        if rows:
            return preferred, sorted(rows, key=_legacy_decision_sort_key)[0]
    return "unmatched", None


def _resolve_collection_legacy(
    outcomes: list[tuple[str, dict[str, Any] | None]],
) -> tuple[str, dict[str, Any] | None]:
    available = [(outcome, row) for outcome, row in outcomes if outcome != "unmatched"]
    if not available:
        return "unmatched", None
    for preferred in ("exact_iri_reuse", "machine_exact_equivalent"):
        matches = [(outcome, row) for outcome, row in available if outcome == preferred]
        if matches:
            return preferred, sorted((row for _, row in matches if row), key=_canonical_target_sort_key)[0]
    hierarchy = {outcome for outcome, _ in available if outcome in {"h2kg_narrower", "h2kg_broader"}}
    if len(hierarchy) > 1:
        return "ambiguous_abstained", next((row for _, row in available if row), None)
    if hierarchy:
        selected = next(iter(hierarchy))
        rows = [row for outcome, row in available if outcome == selected and row]
        return selected, sorted(rows, key=_decision_sort_key)[0]
    for preferred in ("ambiguous_abstained", "related_non_equivalent"):
        rows = [row for outcome, row in available if outcome == preferred and row]
        if rows:
            return preferred, sorted(rows, key=_decision_sort_key)[0]
    return "unmatched", None


def _summary_row(
    *,
    scope_type: str,
    collection: str,
    ontology_id: str,
    ontology_title: str,
    ontology_version: str,
    tib_reported_term_count: int,
    member_ontology_count: int,
    denominator: int,
    counts: Counter,
    assessment_status: str = "assessed",
    native_evidence_status: str = "available",
    assessed_member_ontology_count: int | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "scope_type": scope_type,
        "collection": collection,
        "ontology_id": ontology_id,
        "ontology_title": ontology_title,
        "ontology_version": ontology_version,
        "tib_reported_term_count": tib_reported_term_count,
        "member_ontology_count": member_ontology_count,
        "assessed_member_ontology_count": (
            member_ontology_count if assessed_member_ontology_count is None else assessed_member_ontology_count
        ),
        "h2kg_classes_assessed": denominator,
        "assessment_status": assessment_status,
        "native_evidence_status": native_evidence_status,
    }
    for outcome in OUTCOMES:
        row[f"{outcome}_count"] = counts[outcome] if assessment_status == "assessed" else None
        row[f"{outcome}_percent"] = (
            _percent(counts[outcome], denominator) if assessment_status == "assessed" else None
        )
    row["strict_coverage_percent"] = (
        _percent(counts["exact_iri_reuse"] + counts["machine_exact_equivalent"], denominator)
        if assessment_status == "assessed" else None
    )
    row["hierarchical_coverage_percent"] = (
        _percent(counts["h2kg_narrower"] + counts["h2kg_broader"], denominator)
        if assessment_status == "assessed" else None
    )
    return row


def _external_role(candidate: dict[str, Any]) -> str:
    return str(_external_role_evidence(candidate)["role"])


def _external_role_evidence(candidate: dict[str, Any]) -> dict[str, Any]:
    scores: Counter[str] = Counter()
    signals: dict[str, list[str]] = defaultdict(list)

    def add_token_evidence(text: str, weight: float, source: str) -> None:
        # TIB labels frequently use CamelCase (for example,
        # ScanningElectronMicroscopy).  Tokenizing the raw lowercase string
        # hides its scientific head noun and can turn a method into an
        # instrument solely because its definition mentions a microscope.
        tokens = set(re.findall(r"[a-z0-9]+", normalized_label(text)))
        for role, hints in ROLE_HINTS.items():
            matches = sorted(tokens & hints)
            if not matches:
                continue
            contribution = weight * min(len(matches), 2)
            scores[role] += contribution
            signals[role].append(f"{source}:{','.join(matches)}(+{contribution:g})")

    label = str(candidate.get("label", ""))
    definition = str(candidate.get("definition", ""))
    add_token_evidence(label, 8.0, "preferred-label")
    head = re.findall(r"[a-z0-9]+", normalized_label(label))[-1:] or []
    if head:
        add_token_evidence(head[0], 6.0, "label-head")

    definition_genus = " ".join(re.findall(r"[a-z0-9]+", definition.casefold())[:24])
    for role, patterns in GENUS_ROLE_PATTERNS.items():
        if any(re.search(pattern, definition_genus) for pattern in patterns):
            scores[role] += 7.0
            signals[role].append("definition-genus(+7)")
    add_token_evidence(definition, 1.5, "definition")

    ancestors = list(
        dict.fromkeys(
            [str(value) for value in candidate.get("direct_parent_labels", []) if value]
            + [str(value) for value in candidate.get("ancestor_labels", []) if value]
        )
    )
    for index, ancestor in enumerate(ancestors):
        weight = 5.0 if index == 0 else 2.5 if index == 1 else max(0.25, 1.5 / (index + 1))
        add_token_evidence(ancestor, weight, f"ancestor-{index + 1}")

    ontology_id = str(candidate.get("ontology_id", "")).casefold()
    convention_role = {
        "chebi": "Matter",
        "qudt": "Characteristic",
        "quantitykind": "Characteristic",
        "prov": "Agent",
    }.get(ontology_id)
    if convention_role:
        scores[convention_role] += 2.0
        signals[convention_role].append(f"ontology-convention:{ontology_id}(+2)")

    if not scores:
        return {"role": "Unknown", "confidence": "none", "scores": {}, "signals": {}}
    ordered = sorted(
        scores,
        key=lambda role: (-scores[role], ROLE_LABEL_PRIORITY.index(role)),
    )
    role = ordered[0]
    top = float(scores[role])
    second = float(scores[ordered[1]]) if len(ordered) > 1 else 0.0
    confidence = "high" if top >= 12 and top - second >= 4 else "medium" if top >= 7 and top > second else "low"
    return {
        "role": role,
        "confidence": confidence,
        "scores": {key: round(float(value), 3) for key, value in sorted(scores.items())},
        "signals": {key: value for key, value in sorted(signals.items())},
    }


def _h2kg_role(term: dict[str, Any]) -> str:
    corrected = str(term.get("corrected_semantic_role", ""))
    source_roles = [str(value) for value in term.get("source_roles", [])]
    if "Instrument" in source_roles or corrected == "Instrument":
        return "Instrument"
    if "Measurement" in source_roles or corrected == "Measurement":
        return "Measurement"
    if "Data" in source_roles or corrected in {"Data", "DataPoint", "ParameterRecord", "Metadata"}:
        return "Data"
    if corrected == "Characteristic" or any(value in {"Parameter", "Property", "Unit"} for value in source_roles):
        return "Characteristic"
    if corrected == "Matter":
        return "Matter"
    if corrected == "Agent":
        return "Agent"
    if corrected in {"Process", "Manufacturing"}:
        return "Process"
    top_branch = str(term.get("top_branch", ""))
    return {"InformationEntity": "Data", "Characteristic": "Characteristic"}.get(top_branch, top_branch or "Unknown")


def _roles_compatible(h2kg_role: str, external_role: str) -> bool:
    if h2kg_role == external_role:
        return True
    if h2kg_role == "Measurement" and external_role == "Process":
        return True
    if h2kg_role == "Process" and external_role == "Measurement":
        return True
    return False


def _equivalence_scope_supported(
    term: dict[str, Any],
    candidate: dict[str, Any],
    role_evidence: dict[str, Any],
    *,
    exact_preferred_label: bool,
    controlled_preferred_equivalent: bool,
    alias_only: bool,
) -> tuple[bool, str]:
    left = str(term.get("h2kg_definition", "")).strip()
    right = str(candidate.get("definition", "")).strip()
    ancestors = list(
        dict.fromkeys(
            [str(value) for value in candidate.get("direct_parent_labels", []) if value]
            + [str(value) for value in candidate.get("ancestor_labels", []) if value]
        )
    )
    left_tokens = _scope_tokens(left)
    right_tokens = _scope_tokens(right)
    shared = sorted(left_tokens & right_tokens)
    preferred_tokens = _direction_tokens(str(term.get("h2kg_label", "")))
    external_tokens = _direction_tokens(str(candidate.get("label", "")))

    if exact_preferred_label:
        # A one-word preferred label is often ontology-dependent (Agent,
        # Process, Property, and similar upper-level terms).  One shared word
        # in two definitions is not sufficient to make those scopes exact.
        # Multi-token scientific labels can pass with one independent shared
        # scope term; short labels require at least two.
        if left and right and (
            len(shared) >= 2
            or (len(preferred_tokens) >= 2 and shared)
        ):
            return True, f"preferred-label identity plus shared definition scope ({', '.join(shared[:6])})"
        return False, "preferred-label identity lacks sufficiently specific shared definition scope"

    if controlled_preferred_equivalent:
        if len(shared) >= 2:
            return True, f"controlled role-word normalization plus shared definition scope ({', '.join(shared[:6])})"
        if (
            len(preferred_tokens & external_tokens) >= 2
            and ancestors
            and role_evidence.get("confidence") == "high"
        ):
            return True, f"controlled role-word normalization plus nearest external hierarchy context ({ancestors[0]})"
        return False, "role-word normalization lacks sufficiently specific definition or hierarchy evidence"

    if alias_only:
        # Existing aliases can be intentionally broad search terms.  Treat
        # them as candidate-generation evidence only; exact publication must
        # be supported by the preferred labels themselves.  Preferred-label
        # token containment is still assessed separately for broad/narrow
        # mappings.
        return False, "alias identity is discovery evidence only under the strict publication policy"
    return False, "no independent definition or hierarchy support"


def _scope_tokens(value: str) -> set[str]:
    stop = {
        "a", "an", "and", "as", "at", "by", "for", "from", "in", "is", "of", "on", "or",
        "that", "the", "through", "to", "using", "used", "which", "with", "denotes",
        "corresponding", "defined", "represents",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.casefold())
        if len(token) > 2 and token not in stop and token not in GENERIC_SCOPE_TOKENS
    }


def _material_state_or_form_conflict(
    term: dict[str, Any],
    candidate: dict[str, Any],
) -> tuple[bool, str]:
    h2kg_markers = _token_set(str(term.get("h2kg_label", ""))) & MATERIAL_STATE_AND_FORM_TOKENS
    external_markers = _token_set(str(candidate.get("label", ""))) & MATERIAL_STATE_AND_FORM_TOKENS
    if h2kg_markers == external_markers:
        return False, "compatible material state or form"
    if h2kg_markers or external_markers:
        return True, (
            "material-state/form compatibility "
            f"(H2KG: {', '.join(sorted(h2kg_markers)) or 'unspecified'}; "
            f"external: {', '.join(sorted(external_markers)) or 'unspecified'})"
        )
    return False, "no material-state/form qualifier conflict"


def _granularity_conflict(
    term: dict[str, Any],
    candidate: dict[str, Any],
) -> tuple[bool, str]:
    h2kg_kind = _h2kg_granularity(term)
    external_kind = _external_granularity(candidate)
    incompatible = {
        ("data", "measurement"),
        ("data", "instrument"),
        ("data", "parameter"),
        ("data", "property"),
        ("instrument", "measurement"),
        ("parameter", "instrument"),
        ("property", "measurement"),
        ("property", "instrument"),
        ("instrument", "role"),
        ("measurement", "role"),
        ("data", "role"),
        ("parameter", "role"),
        ("property", "role"),
        ("parameter", "unit"),
        ("property", "unit"),
        ("parameter", "value"),
        ("property", "value"),
        ("agent", "role"),
        ("value", "data"),
    }
    if h2kg_kind and external_kind and (
        (h2kg_kind, external_kind) in incompatible
        or (external_kind, h2kg_kind) in incompatible
    ):
        return True, f"entity/value granularity compatibility ({h2kg_kind} versus {external_kind})"
    return False, "compatible entity/value granularity"


def _h2kg_granularity(term: dict[str, Any]) -> str:
    # Loaded benchmark terms carry the registry roles under the prefixed key;
    # direct unit tests and legacy callers may still provide source_roles.
    source_roles = {
        str(value)
        for value in (
            term.get("h2kg_source_roles", [])
            or term.get("source_roles", [])
        )
    }
    for role, kind in (
        ("Instrument", "instrument"),
        ("Measurement", "measurement"),
        ("DataPoint", "value"),
        ("Data", "data"),
        ("Parameter", "parameter"),
        ("Property", "property"),
        ("Unit", "unit"),
    ):
        if role in source_roles:
            return kind
    return {
        "Instrument": "instrument",
        "Measurement": "measurement",
        "Data": "data",
        "Agent": "agent",
    }.get(str(term.get("h2kg_role", "")), "")


def _external_granularity(candidate: dict[str, Any]) -> str:
    label_tokens = _token_set(str(candidate.get("label", "")))
    hierarchy_labels = [
        normalized_label(str(value))
        for value in (
            list(candidate.get("direct_parent_labels", []))
            + list(candidate.get("ancestor_labels", []))
        )
        if value
    ]
    definition_normalized = normalized_label(str(candidate.get("definition", "")))
    if any(label == "role" or label.endswith(" role") for label in hierarchy_labels) and (
        re.search(r"\bis (?:an? )?role\b", definition_normalized)
        or "agent" in label_tokens
    ):
        return "role"
    definition_head = set(
        re.findall(r"[a-z0-9]+", definition_normalized)[:20]
    )
    for token in reversed(re.findall(r"[a-z0-9]+", normalized_label(str(candidate.get("label", ""))))):
        if token in ENTITY_GRANULARITY_MARKERS:
            return ENTITY_GRANULARITY_MARKERS[token]
    for token in (
        "instrument", "microscope", "spectrometer", "measurement", "assay", "microscopy",
        "spectroscopy", "dataset", "data", "image", "spectrum", "curve", "parameter",
        "setting", "property", "quality", "role", "unit", "value",
    ):
        if token not in label_tokens | definition_head:
            continue
        if token in ENTITY_GRANULARITY_MARKERS:
            return ENTITY_GRANULARITY_MARKERS[token]
    return ""


def _directional_scope_relation(
    term: dict[str, Any],
    candidate: dict[str, Any],
    role_evidence: dict[str, Any],
) -> tuple[str, str, str]:
    """Return a conservative subsumption relation and its evidence strength."""

    h2kg_label = str(term.get("h2kg_label", ""))
    external_label = str(candidate.get("label", ""))
    h2kg_tokens = _direction_tokens(h2kg_label)
    external_tokens = _direction_tokens(external_label)
    if not h2kg_tokens or not external_tokens or not (h2kg_tokens & external_tokens):
        return "", "", ""

    h2kg_definition_tokens = _token_set(str(term.get("h2kg_definition", "")))
    external_definition_tokens = _token_set(str(candidate.get("definition", "")))
    external_hierarchy_tokens = _token_set(
        " ".join(
            [str(value) for value in candidate.get("direct_parent_labels", [])]
            + [str(value) for value in candidate.get("ancestor_labels", [])[:3]]
        )
    )
    non_subclass_forms = {
        "dispersion", "emulsion", "film", "ink", "mixture", "powder", "solution", "suspension", "slurry",
    }
    unsafe_relational_qualifiers = {
        "adduct", "aspartate", "complex", "inhibitor", "ligase", "salt",
    }

    if external_tokens < h2kg_tokens:
        extra = h2kg_tokens - external_tokens
        # A solution/dispersion containing a chemical is related to that
        # chemical, not automatically a subclass of it.
        if extra & non_subclass_forms and not external_tokens <= non_subclass_forms:
            return "", "", ""
        local_support = external_tokens <= (h2kg_definition_tokens | h2kg_tokens)
        external_support = bool(candidate.get("definition")) or bool(external_hierarchy_tokens)
        if not local_support or not external_support:
            return "", "", ""
        h2kg_phrase = normalized_label(h2kg_label)
        external_phrase = normalized_label(external_label)
        preferred_label_genus = (
            h2kg_phrase == external_phrase
            or h2kg_phrase.endswith(f" {external_phrase}")
        )
        high = (
            role_evidence.get("confidence") in {"high", "medium"}
            and external_tokens <= h2kg_definition_tokens
            and bool(candidate.get("definition"))
            and _semantic_head(h2kg_label) == _semantic_head(external_label)
            and preferred_label_genus
        )
        confidence = "high" if high else "medium"
        return (
            "h2kg_narrower",
            confidence,
            "H2KG adds explicit scientifically meaningful restrictions "
            f"({', '.join(sorted(extra))}); the external genus is supported by the H2KG definition "
            "and external definition or hierarchy.",
        )

    if h2kg_tokens < external_tokens:
        extra = external_tokens - h2kg_tokens
        if extra & unsafe_relational_qualifiers:
            return "", "", ""
        if extra & non_subclass_forms:
            return "", "", ""
        external_support = h2kg_tokens <= (external_definition_tokens | external_tokens)
        if not external_support or not candidate.get("definition"):
            return "", "", ""
        explicit_phase_specialization = bool(extra) and extra <= {"gas", "gaseous", "liquid", "solid", "vapour", "vapor"}
        genus_support = bool(h2kg_tokens & external_hierarchy_tokens)
        high = explicit_phase_specialization or genus_support
        confidence = "high" if high else "medium"
        return (
            "h2kg_broader",
            confidence,
            "The external class adds explicit restrictions "
            f"({', '.join(sorted(extra))}) to the H2KG concept; its definition or hierarchy supports that specialization.",
        )

    return "", "", ""


def _direction_tokens(value: str) -> set[str]:
    return {
        token
        for token in _token_set(value)
        if len(token) > 1 and token not in (GENERIC_DIRECTION_TOKENS - {"activity"})
    }


def _semantic_head(value: str) -> str:
    tokens = [
        token
        for token in re.findall(r"[a-z0-9]+", normalized_label(value).casefold())
        if token not in GENERIC_DIRECTION_TOKENS
    ]
    return tokens[-1] if tokens else ""


def _token_set(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", normalized_label(value).casefold()))


def _legacy_external_role(candidate: dict[str, Any]) -> str:
    labels = [
        str(candidate.get("label", "")),
        str(candidate.get("definition", "")),
        *[str(value) for value in candidate.get("ancestor_labels", [])],
    ]
    tokens = set(re.findall(r"[a-z0-9]+", " ".join(labels).casefold()))
    own_tokens = set(re.findall(r"[a-z0-9]+", str(candidate.get("label", "")).casefold()))
    ordered = ("Instrument", "Data", "Measurement", "Characteristic", "Agent", "Matter", "Process")
    for role in ordered:
        if own_tokens & ROLE_HINTS[role]:
            return role
    for role in ordered:
        if tokens & ROLE_HINTS[role]:
            return role
    return "Unknown"


def _legacy_candidate_outcome(term: dict[str, Any], candidate: dict[str, Any]) -> str:
    external_label = str(candidate.get("label", ""))
    synonyms = [str(value) for value in candidate.get("synonyms", []) if value]
    h2kg_labels = [term["h2kg_label"], *term.get("h2kg_alt_labels", [])]
    external_labels = [external_label, *synonyms]
    exact_iri = term["h2kg_iri"] == candidate.get("iri")
    exact_label = any(
        normalized_label(left) == normalized_label(right)
        for left in h2kg_labels
        for right in external_labels
    )
    normalized_equivalent = any(
        _controlled_equivalent(left, right) for left in h2kg_labels for right in external_labels
    )
    external_role = _legacy_external_role(candidate)
    role_compatible = _roles_compatible(term["h2kg_role"], external_role)
    definition_conflict = _definition_conflict(
        " ".join([term["h2kg_label"], term.get("h2kg_definition", "")]),
        " ".join([external_label, str(candidate.get("definition", ""))]),
    )
    similarity = max(
        [_lexical_similarity(left, right) for left in h2kg_labels for right in external_labels] or [0.0]
    )
    h_tokens = _semantic_tokens(term["h2kg_label"])
    e_tokens = _semantic_tokens(external_label)
    if exact_iri:
        return "exact_iri_reuse"
    if (exact_label or normalized_equivalent) and role_compatible and not definition_conflict:
        return "machine_exact_equivalent"
    if exact_label or normalized_equivalent:
        return "ambiguous_abstained"
    if role_compatible and e_tokens and e_tokens < h_tokens:
        return "h2kg_narrower"
    if role_compatible and h_tokens and h_tokens < e_tokens:
        return "h2kg_broader"
    if role_compatible and similarity >= 70 and not definition_conflict:
        return "related_non_equivalent"
    if similarity >= 70:
        return "ambiguous_abstained"
    return "related_non_equivalent"


def _adjudicate_equivalence_collisions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = [dict(row) for row in rows]

    def downgrade(row: dict[str, Any], rule_id: str, rationale: str) -> None:
        row["final_outcome"] = "related_non_equivalent"
        row["outcome"] = "related_non_equivalent"
        row["rule_id"] = rule_id
        row["confidence"] = "high"
        row["decision_basis"] = rationale
        row["safe_for_harmonization"] = False

    by_local_ontology: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in result:
        if row.get("outcome") in {"exact_iri_reuse", "machine_exact_equivalent"}:
            by_local_ontology[(row["h2kg_iri"], row["ontology_id"])].append(row)
    for candidates in by_local_ontology.values():
        distinct_targets = {row["external_iri"] for row in candidates}
        if len(distinct_targets) <= 1:
            continue
        exact_iri_rows = [row for row in candidates if row["outcome"] == "exact_iri_reuse"]
        keep = exact_iri_rows[0] if len(exact_iri_rows) == 1 else None
        for row in candidates:
            if row is keep:
                continue
            downgrade(
                row,
                "RELATED-MULTIPLE-CANONICAL-TARGETS-010",
                "Multiple active equivalence candidates occur in the same ontology and no unique canonical target was established.",
            )

    by_external: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in result:
        if row.get("outcome") in {"exact_iri_reuse", "machine_exact_equivalent"}:
            by_external[(row["ontology_id"], row["external_iri"])].append(row)
    for candidates in by_external.values():
        local_iris = {row["h2kg_iri"] for row in candidates}
        if len(local_iris) <= 1:
            continue
        exact_iri_rows = [row for row in candidates if row["outcome"] == "exact_iri_reuse"]
        keep = exact_iri_rows[0] if len(exact_iri_rows) == 1 else None
        for row in candidates:
            if row is keep:
                continue
            downgrade(
                row,
                "RELATED-MANY-TO-ONE-COLLISION-011",
                "The external class is an equivalence candidate for multiple active H2KG classes; equivalence was withheld pending duplicate consolidation.",
            )
    return result


def _controlled_equivalent(left: str, right: str) -> bool:
    left_full = normalized_label(left)
    right_full = normalized_label(right)
    if left_full == right_full:
        return True
    left_reduced = normalized_label(left, remove_role_words=True)
    right_reduced = normalized_label(right, remove_role_words=True)
    return left_reduced == right_reduced and len(left_reduced.split()) >= 2


def _labels_equivalent(left: str, right: str) -> bool:
    return normalized_label(left) == normalized_label(right) or _controlled_equivalent(left, right)


def _semantic_tokens(value: str) -> set[str]:
    tokens = set(normalized_label(value, remove_role_words=True).split())
    return {token for token in tokens if len(token) > 1}


def _lexical_similarity(left: str, right: str) -> float:
    return float(fuzz.token_set_ratio(normalized_label(left), normalized_label(right)))


def _definition_conflict(left: str, right: str) -> bool:
    left_tokens = set(normalized_label(left).split())
    right_tokens = set(normalized_label(right).split())
    for first, second in CONFLICT_PAIRS:
        if first in left_tokens and second in right_tokens and second not in left_tokens and first not in right_tokens:
            return True
        if second in left_tokens and first in right_tokens and first not in left_tokens and second not in right_tokens:
            return True
    return False


def _decision_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        DECISION_RANK.get(str(row.get("outcome", "unmatched")), len(DECISION_RANK)),
        -float(row.get("lexical_similarity") or 0),
        ONTOLOGY_PRIORITY.get(str(row.get("ontology_id", "")).casefold(), 100),
        str(row.get("external_iri", "")),
    )


def _legacy_decision_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    legacy_rank = {
        "exact_iri_reuse": 0,
        "machine_exact_equivalent": 1,
        "h2kg_narrower": 2,
        "h2kg_broader": 3,
        "ambiguous_abstained": 4,
        "related_non_equivalent": 5,
        "unmatched": 6,
    }
    return (
        legacy_rank.get(str(row.get("outcome", "unmatched")), len(legacy_rank)),
        -float(row.get("lexical_similarity") or 0),
        ONTOLOGY_PRIORITY.get(str(row.get("ontology_id", "")).casefold(), 100),
        str(row.get("external_iri", "")),
    )


def _canonical_target_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        ONTOLOGY_PRIORITY.get(str(row.get("ontology_id", "")).casefold(), 100),
        -float(row.get("lexical_similarity") or 0),
        len(str(row.get("external_label", ""))),
        str(row.get("external_iri", "")),
    )


def _request_json(
    client: requests.Session,
    url: str,
    params: dict[str, Any],
    *,
    timeout: int,
) -> dict[str, Any]:
    last_error: requests.RequestException | None = None
    for attempt in range(4):
        try:
            response = client.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise requests.RequestException(f"TIB returned a non-object response for {url}")
            return payload
        except requests.RequestException as error:
            last_error = error
            if attempt < 3:
                time.sleep(2 ** attempt)
    assert last_error is not None
    raise last_error


def _catalogue_record(item: dict[str, Any]) -> dict[str, Any]:
    config = item.get("config") if isinstance(item.get("config"), dict) else {}
    collections = config.get("collection") or []
    if isinstance(collections, str):
        collections = [collections]
    return {
        "ontology_id": str(item["ontologyId"]).casefold(),
        "title": str(config.get("title") or item.get("title") or ""),
        "version": item.get("version") or config.get("version"),
        "ontology_iri": str(item.get("ontologyIri") or config.get("id") or ""),
        "file_location": str(config.get("fileLocation") or config.get("file_location") or ""),
        "loaded": item.get("loaded"),
        "updated": item.get("updated"),
        "number_of_terms": int(item.get("numberOfTerms") or 0),
        "number_of_properties": int(item.get("numberOfProperties") or 0),
        "number_of_individuals": int(item.get("numberOfIndividuals") or 0),
        "collections": sorted({str(value) for value in collections if value}, key=str.casefold),
    }


def _compact_search_hit(hit: dict[str, Any]) -> dict[str, Any]:
    return {
        "ontology_id": str(hit.get("ontology_name") or hit.get("ontology") or "").casefold(),
        "iri": str(hit.get("iri") or ""),
        "label": _first_text(hit.get("label")),
        "definition": _first_text(hit.get("description") or hit.get("definition")),
        "synonyms": _text_list(hit.get("synonym") or hit.get("synonyms")),
        "type": _first_text(hit.get("type")),
    }


def _compact_v2_class_hit(payload: dict[str, Any]) -> dict[str, Any]:
    detail = _compact_class_detail(payload)
    type_values = _text_list(payload.get("type"))
    ontology_id = str(payload.get("ontologyId") or "").casefold()
    if not ontology_id:
        defining = detail.get("defined_by", [])
        ontology_id = str(defining[0]).casefold() if defining else ""
    return {
        "ontology_id": ontology_id,
        "iri": str(payload.get("iri") or ""),
        "label": _first_text(payload.get("label")),
        "definition": str(detail.get("definition") or ""),
        "synonyms": _text_list(payload.get("synonym")),
        "type": "class" if "class" in {value.casefold() for value in type_values} else _first_text(type_values),
        **detail,
        "native_to_ontology": bool(payload.get("isDefiningOntology", True)),
    }


def _compact_class_detail(payload: dict[str, Any]) -> dict[str, Any]:
    linked = payload.get("linkedEntities") if isinstance(payload.get("linkedEntities"), dict) else {}
    ancestor_iris = [str(value) for value in payload.get("hierarchicalAncestor", []) if value]
    ancestor_labels: list[str] = []
    for iri in ancestor_iris:
        record = linked.get(iri, {}) if isinstance(linked.get(iri), dict) else {}
        label = _first_text(record.get("label"))
        if label:
            ancestor_labels.append(label)
    direct_parent_iris = [str(value) for value in payload.get("directParent", []) if value]
    direct_parent_labels = []
    for iri in direct_parent_iris:
        record = linked.get(iri, {}) if isinstance(linked.get(iri), dict) else {}
        label = _first_text(record.get("label"))
        if label:
            direct_parent_labels.append(label)
    definition = payload.get("definition")
    if isinstance(definition, list):
        definition = " | ".join(
            str(value.get("value") if isinstance(value, dict) else value)
            for value in definition
            if value
        )
    return {
        "iri": str(payload.get("iri") or ""),
        "label": _first_text(payload.get("label")),
        "definition": str(definition or ""),
        "synonyms": _text_list(payload.get("synonym")),
        "defined_by": [str(value).casefold() for value in payload.get("definedBy", []) if value],
        "appears_in": [str(value).casefold() for value in payload.get("appearsIn", []) if value],
        "imported": bool(payload.get("imported")),
        "is_defining_ontology": bool(payload.get("isDefiningOntology")),
        "is_obsolete": bool(payload.get("isObsolete")),
        "direct_parent_iris": direct_parent_iris,
        "direct_parent_labels": direct_parent_labels,
        "ancestor_iris": ancestor_iris,
        "ancestor_labels": ancestor_labels,
        "replaced_by": _text_list(payload.get("replacedBy") or payload.get("termReplacedBy")),
    }


def _load_existing_mappings(path: str | Path | None) -> list[dict[str, Any]]:
    if not path:
        return []
    path = Path(path)
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [dict(row) for row in payload.get("mappings", [])]


def _collection_members(snapshot: dict[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for record in snapshot.get("collections", {}).values():
        raw_name = str(record.get("catalogue_name") or record.get("requested_name") or "")
        name = COLLECTION_DISPLAY_NAMES.get(_collection_key(raw_name), raw_name)
        result[name] = sorted({str(value).casefold() for value in record.get("ontology_ids", [])})
    return dict(sorted(result.items(), key=lambda item: item[0].casefold()))


def _ontology_collections(snapshot: dict[str, Any], ontology_id: str) -> list[str]:
    result = []
    for collection, ontology_ids in _collection_members(snapshot).items():
        if ontology_id.casefold() in ontology_ids:
            result.append(collection)
    return sorted(result, key=str.casefold)


def _collection_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).casefold())


def _preferred_collection_name(values: list[str], fallback: str) -> str:
    return sorted(set(values), key=lambda value: (len(value), value.casefold()))[0] if values else fallback


def _term_query_labels(term: dict[str, Any], *, max_aliases: int = 3) -> list[str]:
    labels = [term["h2kg_label"], *term.get("h2kg_alt_labels", [])[:max_aliases]]
    expanded = [str(label) for label in labels if label]
    for label in tuple(expanded):
        reduced = normalized_label(label, remove_role_words=True)
        if reduced and len(reduced.split()) >= 2:
            expanded.append(reduced)
    return list(dict.fromkeys(expanded))


def _query_key(label: str) -> str:
    return normalized_label(label)


def _escape_query_phrase(label: str) -> str:
    return str(label).replace("\\", "\\\\").replace('"', '\\"')


def _detail_key(ontology_id: str, iri: str) -> str:
    return f"{ontology_id.casefold()}|{iri}"


def _candidate_has_detail_evidence(candidate: dict[str, Any]) -> bool:
    return any(
        key in candidate
        for key in (
            "is_defining_ontology",
            "is_obsolete",
            "defined_by",
            "direct_parent_iris",
            "ancestor_iris",
        )
    )


def _json_sha256(payload: Any) -> str:
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def _validate_publishable_summaries(summaries: dict[str, Any]) -> None:
    benchmark = summaries["benchmark_summary"]
    if int(benchmark.get("unique_ontology_class_decisions", -1)) != int(
        benchmark.get("expected_unique_ontology_class_decisions", -2)
    ):
        raise ValueError("Unique ontology-level class decision coverage is incomplete.")
    if int(benchmark.get("ontology_class_assignments", -1)) != int(
        benchmark.get("expected_ontology_class_assignments", -2)
    ):
        raise ValueError("Ontology-level class assignment coverage is incomplete.")
    for group in ("collection_summary", "ontology_summary", "category_summary"):
        for row in summaries[group]:
            if row.get("assessment_status") == "not_assessed_native_evidence_unavailable":
                if row.get("ontology_id") not in UNASSESSED_NATIVE_ONTOLOGIES:
                    raise ValueError(f"Unexpected unassessed ontology row: {row}")
                continue
            denominator = int(row["h2kg_classes_assessed"])
            total = sum(int(row[f"{outcome}_count"]) for outcome in OUTCOMES)
            if total != denominator:
                raise ValueError(f"{group} row does not cover its denominator: {row}")
            if int(row["ambiguous_abstained_count"]) != 0:
                raise ValueError(f"Publishable benchmark retains semantic abstentions: {row}")


def _load_correction_registry(path: str | Path | None) -> list[dict[str, Any]]:
    if not path:
        return []
    source = Path(path)
    if not source.exists():
        return []
    payload = json.loads(source.read_text(encoding="utf-8"))
    rows = []
    for record in payload.get("corrections", []):
        rows.append(
            {
                "correction_id": str(record.get("correction_id", "")),
                "local_iri": str(record.get("local_iri", "")),
                "local_name": str(record.get("local_name", "")),
                "action": str(record.get("action", "")),
                "previous_value": str(record.get("previous_value", "")),
                "final_value": str(record.get("final_value", "")),
                "preferred_label_override": str(record.get("preferred_label_override", "")),
                "definition_override": str(record.get("definition_override", "")),
                "scope_note": str(record.get("scope_note", "")),
                "required_parent": str(record.get("required_parent", "")),
                "confidence": str(record.get("confidence", "")),
                "evidence": " | ".join(str(value) for value in record.get("evidence", [])),
                "rationale": str(record.get("rationale", "")),
                "status": str(record.get("status", "")),
            }
        )
    return rows


def _decision_has_exact_label(row: dict[str, Any]) -> bool:
    local_labels = [str(row.get("h2kg_label", ""))]
    alt_labels = row.get("h2kg_alt_labels", [])
    if isinstance(alt_labels, str):
        alt_labels = [value.strip() for value in alt_labels.split("|") if value.strip()]
    local_labels.extend(str(value) for value in alt_labels)
    external_labels = [str(row.get("external_label", ""))]
    return any(
        normalized_label(left) == normalized_label(right)
        for left in local_labels
        for right in external_labels
        if left and right
    )


def _pre_post_comparison_rows(
    baseline: dict[str, Any],
    final: dict[str, Any],
) -> list[dict[str, Any]]:
    baseline_by_collection = {row["collection"]: row for row in baseline["collection_summary"]}
    rows: list[dict[str, Any]] = []
    for final_row in final["collection_summary"]:
        initial = baseline_by_collection[final_row["collection"]]
        for outcome in OUTCOMES:
            before_count = int(initial[f"{outcome}_count"])
            after_count = int(final_row[f"{outcome}_count"])
            before_percent = float(initial[f"{outcome}_percent"])
            after_percent = float(final_row[f"{outcome}_percent"])
            rows.append(
                {
                    "collection": final_row["collection"],
                    "outcome": outcome,
                    "baseline_count": before_count,
                    "baseline_percent": before_percent,
                    "final_count": after_count,
                    "final_percent": after_percent,
                    "count_change": after_count - before_count,
                    "percentage_point_change": round(after_percent - before_percent, 4),
                }
            )
    return rows


def _independent_percentages(counts: list[int], denominator: int, decimals: int = 2) -> list[float]:
    if not denominator:
        return [0.0 for _ in counts]
    return [round(100.0 * count / denominator, decimals) for count in counts]


def _ontology_publication_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda item: (item["collection"].casefold(), item["ontology_title"].casefold(), item["ontology_id"])):
        assessed = row.get("assessment_status", "assessed") == "assessed"
        counts = [int(row[f"{outcome}_count"] or 0) for outcome in OUTCOMES]
        percentages = _independent_percentages(counts, int(row["h2kg_classes_assessed"] or 0), decimals=2)
        published = {
            "Collection": row["collection"],
            "Ontology ID": row["ontology_id"],
            "Ontology title": row["ontology_title"],
            "Version": row["ontology_version"],
            "TIB link": f"https://terminology.tib.eu/ts/ontologies/{row['ontology_id']}",
            "TIB-reported terms": row["tib_reported_term_count"],
            "Assessment status": row.get("assessment_status", "assessed"),
            "Native evidence status": row.get("native_evidence_status", "available"),
            "H2KG classes assessed": row["h2kg_classes_assessed"] if assessed else "",
        }
        for outcome, count, percent in zip(OUTCOMES, counts, percentages):
            published[PUBLICATION_OUTCOME_LABELS[outcome]] = f"{count} ({percent:.2f}%)" if assessed else ""
        output.append(published)
    return output


def _collection_publication_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        counts = [int(row[f"{outcome}_count"]) for outcome in OUTCOMES]
        percentages = _independent_percentages(counts, int(row["h2kg_classes_assessed"]), decimals=2)
        published = {
            "Collection": row["collection"],
            "Member ontologies": row["member_ontology_count"],
            "Assessed ontologies": row.get("assessed_member_ontology_count", row["member_ontology_count"]),
            "H2KG classes assessed": row["h2kg_classes_assessed"],
        }
        for outcome, count, percent in zip(OUTCOMES, counts, percentages):
            published[PUBLICATION_OUTCOME_LABELS[outcome]] = f"{count} ({percent:.2f}%)"
        output.append(published)
    return output


def _ontology_publication_markdown(rows: list[dict[str, Any]]) -> str:
    headers = ONTOLOGY_PUBLICATION_COLUMNS
    lines = [
        "# Supplementary Ontology-Level H2KG-TIB Benchmark",
        "",
        "Each percentage uses the final active H2KG class count as denominator. Collection names are repeated for machine readability.",
        "",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" if index < 5 else "---:" for index in range(len(headers))) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(header, "")).replace("|", "\\|") for header in headers) + " |")
    return "\n".join(lines) + "\n"


def _percent(count: int, denominator: int) -> float:
    return round((100.0 * count / denominator), 4) if denominator else 0.0


def _first_text(value: Any) -> str:
    for item in value if isinstance(value, list) else ([] if value is None else [value]):
        if isinstance(item, dict):
            item = item.get("value") or item.get("@value") or item.get("label")
        if item:
            return str(item)
    return ""


def _text_list(value: Any) -> list[str]:
    result: list[str] = []
    for item in value if isinstance(value, list) else ([] if value is None else [value]):
        if isinstance(item, dict):
            item = item.get("value") or item.get("@value")
        if item:
            result.append(str(item))
    return list(dict.fromkeys(result))


def _display_label(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    if not value:
        return value
    return value[0].upper() + value[1:]


def _write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(
            {
                column: re.sub(r"[ \t]+(?=\r?\n|$)", "", value) if isinstance(value, str) else value
                for column, value in row.items()
            }
            for row in rows
        )


def _write_missing_collection_cache(target: Path, snapshot_path: Path, candidate_path: Path) -> dict[str, Any]:
    message = f"""# H2KG--TIB Collection Benchmark

The offline release did not run this benchmark because its frozen inputs are incomplete.

- Snapshot: `{snapshot_path}`
- Candidate cache: `{candidate_path}`

Run `tib-collection-benchmark --refresh` deliberately to create a dated API snapshot. Normal release generation never queries TIB implicitly.
"""
    write_text(target / "README.md", message)
    return {
        "status": "skipped_missing_collection_cache",
        "snapshot": str(snapshot_path),
        "candidate_cache": str(candidate_path),
        "target": str(target),
    }


def collection_matching_rules() -> str:
    return """# Automated H2KG--TIB Collection Matching Rules

The primary denominator is every active local H2KG class in the frozen taxonomy registry. Deprecated compatibility classes and ontology properties are excluded. TIB imported classes are excluded from primary per-ontology coverage and reported separately.

External roles are inferred from weighted evidence. The preferred label and its head noun carry the highest lexical weight, followed by the definition genus, direct parent, nearest ancestors, ontology convention, and then distant ancestors. Incidental words in distant ancestors cannot override stronger local evidence. This prevents, for example, CHMO atomic layer deposition from becoming Matter because one ancestor is named `sample deposition`.

`machine_exact_equivalent` requires an active, native, non-obsolete class; preferred-label or synonym identity after controlled normalization; compatible semantic roles; non-conflicting definitions; independent definition or hierarchy support; and one canonical target. Exact labels alone never establish equivalence. Strict semantic-token containment with compatible roles supports `h2kg_narrower` and `h2kg_broader`. A discovered candidate that lacks defensible equivalence or direction is `related_non_equivalent`; no candidate after a successful complete search is `unmatched`.

Multiple equivalence targets and many-to-one equivalence collisions are conservatively downgraded to related unless a stable IRI uniquely resolves the collision. The matcher changes no H2KG IRI and never creates a collection-wide OWL import. It exports only high-confidence machine-safe mappings to the external bridge: equivalence as `skos:exactMatch`, an H2KG specialization as `skos:broadMatch`, and an H2KG generalization as `skos:narrowMatch`. Related candidates remain non-asserted benchmark evidence.

`ambiguous_abstained` remains a visible reporting column for methodological continuity, but its value must be zero in a publishable build. Any failed search or class-evidence request blocks publication and is written to `retrieval_failures.csv`; a technical failure is never converted into a semantic result. The pipeline uses deterministic rules and no embedding or free-form LLM adjudication.
"""


def collection_readme(
    summaries: dict[str, Any],
    snapshot: dict[str, Any],
    snapshot_path: Path,
    candidate_cache_path: Path,
) -> str:
    summary = summaries["benchmark_summary"]
    return f"""# H2KG--TIB Collection Benchmark

This package benchmarks `{summary['h2kg_active_classes_assessed']}` active local H2KG classes against the ontologies assigned to NFDI4Cat, NFDI4Energy, and NFDI4Ing in the TIB catalogue snapshot retrieved at `{snapshot.get('retrieved_at')}`.

Primary percentages use native classes only. Imported availability is documented separately. BattINFO remains one of the 165 catalogue-membership rows but is marked not assessed because native frozen evidence is unavailable; it contributes no semantic outcome and is excluded from the NFDI4Ing union. Every assessed row assigns each H2KG class to exactly one outcome. Percentages are rounded independently, so displayed totals may differ from 100% by 0.01 percentage point while exact counts remain authoritative.

TIB catalogue term/property/individual counts are retained as descriptive metadata. They may include imported resources and are never used as the H2KG overlap denominator.

The analysis is fully automated and conservative. Exact machine decisions are not described as human-validated equivalence. A publishable build contains zero semantic abstentions: uncertain candidates are reported as related, and failed API retrieval blocks publication.

## Files

- `collection_summary.csv`: collection-level percentages.
- `ontology_summary.csv`: manuscript-ready percentages for every ontology under each collection.
- `ontology_benchmark.csv` and `.md`: the complete 165-row count-and-percentage supplementary table.
- `h2kg_tib_collection_benchmark.xlsx`: complete documented benchmark.
- `h2kg_tib_manuscript_tables.xlsx`: compact manuscript tables.
- `candidate_decisions.csv`: evidence for every discovered correspondence.
- `retrieval_failures.csv`: blocking API failures; empty in a publishable build.
- `ambiguity_resolution_history.csv`: every former semantic abstention and its deterministic final result.
- `pre_post_harmonization.csv`: collection-level baseline/final comparison.
- `h2kg_corrections.csv`: high-confidence internal corrections applied before the final benchmark.
- `h2kg_collection_coverage.csv`: class-level collection outcomes.
- `imported_availability.csv`: secondary import-inclusive evidence.
- `automatic_harmonization_registry.json`: exact, machine-safe mappings and non-destructive label actions.

Frozen inputs: `{snapshot_path}` and `{candidate_cache_path}`.
"""


def manuscript_table(summaries: dict[str, Any], snapshot: dict[str, Any]) -> str:
    outcome_columns = [name.replace("_", " ") + " (%)" for name in OUTCOMES]

    collection_columns = ["Collection", "Catalogue members", "Assessed members", "H2KG classes", *outcome_columns]
    collection_rows = [
        "| " + " | ".join(collection_columns) + " |",
        "| " + " | ".join(["---", "---:", "---:", "---:", *["---:" for _ in OUTCOMES]]) + " |",
    ]
    for row in summaries["collection_summary"]:
        collection_rows.append(
            "| "
            + " | ".join(
                [
                    row["collection"],
                    str(row["member_ontology_count"]),
                    str(row.get("assessed_member_ontology_count", row["member_ontology_count"])),
                    str(row["h2kg_classes_assessed"]),
                    *[f"{row[f'{name}_percent']:.2f}" for name in OUTCOMES],
                ]
            )
            + " |"
        )

    ontology_columns = ["Collection", "Ontology", "Assessment status", "TIB-reported terms", "H2KG classes", *outcome_columns]
    ontology_rows = [
        "| " + " | ".join(ontology_columns) + " |",
        "| " + " | ".join(["---", "---", "---", "---:", "---:", *["---:" for _ in OUTCOMES]]) + " |",
    ]
    for row in summaries["ontology_summary"]:
        assessed = row.get("assessment_status", "assessed") == "assessed"
        ontology_rows.append(
            "| "
            + " | ".join(
                [
                    row["collection"],
                    f"{row['ontology_id']} - {row['ontology_title']}",
                    str(row.get("assessment_status", "assessed")),
                    str(row["tib_reported_term_count"]),
                    str(row["h2kg_classes_assessed"]) if assessed else "",
                    *([f"{row[f'{name}_percent']:.2f}" for name in OUTCOMES] if assessed else ["" for _ in OUTCOMES]),
                ]
            )
            + " |"
        )
    return f"""# Manuscript Table: Automated H2KG Coverage in TIB Collections

TIB catalogue snapshot: `{snapshot.get('retrieved_at')}`. Percentages use `{summaries['benchmark_summary']['h2kg_active_classes_assessed']}` active H2KG classes as the denominator. Primary ontology rows count native classes only; imported availability is reported separately in the benchmark package.

## Collection-level summary

{chr(10).join(collection_rows)}

## Ontology-level supplementary table

{chr(10).join(ontology_rows)}

**Interpretation.** `exact_iri_reuse` and `machine_exact_equivalent` form strict coverage. Broader, narrower, and related classes indicate semantic complementarity rather than equivalence. `ambiguous_abstained` is retained as a transparent column but is zero in assessed rows; technical retrieval failures block publication. `unmatched` indicates that no candidate was discovered after the complete frozen-snapshot search. BattINFO is not assessed because the frozen evidence contains no native BattINFO graph.

**Catalogue-count note.** `TIB-reported terms` reproduces the catalogue metadata and may include imported terms. It is descriptive only and is not used as the overlap denominator.
"""


def benchmark_html(
    summaries: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    docs_mode: bool = False,
) -> str:
    collection_rows = _html_summary_rows(summaries["collection_summary"])
    ontology_rows = _html_summary_rows(summaries["ontology_summary"], link_ontologies=True)
    prefix = "../benchmarks/tib_collections/" if docs_mode else ""
    title = "H2KG-TIB Collection Benchmark"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{ --ink:#173042; --muted:#5f6f79; --teal:#137f82; --sand:#f3eadb; --line:#d7dedf; --paper:#fffdf8; }}
    * {{ box-sizing:border-box; }} body {{ margin:0; font-family:Aptos,"Segoe UI",sans-serif; color:var(--ink); background:linear-gradient(135deg,#f5faf8,#f8f2e9); }}
    main {{ max-width:1500px; margin:auto; padding:36px 28px 64px; }} h1 {{ font-size:clamp(2rem,4vw,3.7rem); margin:0 0 10px; line-height:1; }}
    .lede {{ max-width:920px; color:var(--muted); font-size:1.08rem; }} .actions {{ display:flex; flex-wrap:wrap; gap:10px; margin:24px 0; }}
    .actions a {{ color:white; background:var(--teal); padding:10px 14px; border-radius:6px; text-decoration:none; font-weight:700; }}
    section {{ background:rgba(255,255,255,.92); border:1px solid var(--line); border-radius:14px; margin-top:20px; padding:20px; box-shadow:0 12px 35px rgba(23,48,66,.07); }}
    .table-wrap {{ overflow:auto; max-height:68vh; }} table {{ border-collapse:collapse; width:100%; font-size:.86rem; }} th {{ position:sticky; top:0; background:var(--ink); color:white; text-align:left; }}
    th,td {{ padding:8px 10px; border-bottom:1px solid var(--line); white-space:nowrap; }} tr:nth-child(even) td {{ background:#f8faf9; }} .num {{ text-align:right; font-variant-numeric:tabular-nums; }}
    .filters {{ display:flex; flex-wrap:wrap; gap:12px; margin:12px 0 16px; }} .filters label {{ font-weight:700; }}
    .filters select,.filters input {{ margin-left:6px; padding:8px 10px; border:1px solid var(--line); border-radius:6px; min-width:190px; }}
    code {{ background:var(--sand); padding:2px 5px; border-radius:4px; }}
  </style>
</head>
<body><main>
  <p>H2KG quality evidence</p><h1>{title}</h1>
  <p class="lede">Automated, role-aware comparison of {summaries['benchmark_summary']['h2kg_active_classes_assessed']} active H2KG classes against NFDI4Cat, NFDI4Energy, and NFDI4Ing. Native ontology classes define the primary percentages; imported availability is kept separate.</p>
  <p><strong>TIB snapshot:</strong> {html.escape(str(snapshot.get('retrieved_at', 'unknown')))}</p>
  <div class="actions">
    <a href="{prefix}h2kg_tib_collection_benchmark.xlsx" download>Complete Excel benchmark</a>
    <a href="{prefix}h2kg_tib_manuscript_tables.xlsx" download>Manuscript Excel tables</a>
    <a href="{prefix}candidate_decisions.csv" download>Decision evidence</a>
    <a href="{prefix}ontology_benchmark.csv" download>Ontology table CSV</a>
    <a href="{prefix}pre_post_harmonization.csv" download>Pre/post comparison</a>
    <a href="{prefix}retrieval_failures.csv" download>Retrieval audit</a>
    <a href="{prefix}manuscript_table.md" download>Manuscript table</a>
  </div>
  <section><h2>Collection summary</h2><div class="table-wrap">{_html_table_header('collection-table')}{collection_rows}</tbody></table></div></section>
  <section><h2>Ontology-by-ontology summary</h2><p>Every assessed row assigns all active H2KG classes exactly once. BattINFO remains visible as a not-assessed catalogue membership. Percentages are rounded independently; exact counts are authoritative.</p>
    <div class="filters"><label>Collection<select id="collection-filter"><option value="">All collections</option><option>NFDI4Cat</option><option>NFDI4Energy</option><option>NFDI4Ing</option></select></label><label>Ontology<input id="ontology-filter" type="search" placeholder="ID or title"></label></div>
    <div class="table-wrap">{_html_table_header('ontology-table')}{ontology_rows}</tbody></table></div></section>
  <section><h2>Interpretation boundary</h2><p>Strict coverage combines <code>exact_iri_reuse</code> and <code>machine_exact_equivalent</code>. Hierarchical and related results are not equivalence. The visible <code>ambiguous_abstained</code> column is zero in this publishable build; incomplete retrieval would block publication instead of becoming a semantic result. This benchmark measures terminological complementarity, not ontology quality or scientific correctness.</p></section>
</main><script>
const collectionFilter=document.getElementById('collection-filter');
const ontologyFilter=document.getElementById('ontology-filter');
function filterRows(){{
  const collection=collectionFilter.value.toLowerCase();
  const query=ontologyFilter.value.trim().toLowerCase();
  document.querySelectorAll('#ontology-table tbody tr').forEach(row=>{{
    const matchesCollection=!collection||row.dataset.collection.toLowerCase()===collection;
    const matchesQuery=!query||row.textContent.toLowerCase().includes(query);
    row.hidden=!(matchesCollection&&matchesQuery);
  }});
}}
collectionFilter.addEventListener('change',filterRows); ontologyFilter.addEventListener('input',filterRows);
</script></body></html>"""


def _html_table_header(table_id: str) -> str:
    headers = ["Collection", "Ontology", *[name.replace("_", " ") for name in OUTCOMES]]
    return f'<table id="{table_id}"><thead><tr>' + "".join(f"<th>{html.escape(value)}</th>" for value in headers) + "</tr></thead><tbody>"


def _html_summary_rows(rows: list[dict[str, Any]], *, link_ontologies: bool = False) -> str:
    output = []
    for row in rows:
        ontology = row["ontology_title"] if row["ontology_id"] == "ALL" else f"{row['ontology_id']} - {row['ontology_title']}"
        ontology_cell = html.escape(ontology)
        if link_ontologies and row["ontology_id"] != "ALL":
            url = f"https://terminology.tib.eu/ts/ontologies/{quote(str(row['ontology_id']))}"
            ontology_cell = f'<a href="{html.escape(url)}">{ontology_cell}</a>'
        cells = [html.escape(str(row["collection"])), ontology_cell]
        assessed = row.get("assessment_status", "assessed") == "assessed"
        if assessed:
            percentages = _independent_percentages(
                [int(row[f"{name}_count"]) for name in OUTCOMES],
                int(row["h2kg_classes_assessed"]),
                decimals=2,
            )
            cells.extend(
                f"{int(row[f'{name}_count'])} ({percent:.2f}%)"
                for name, percent in zip(OUTCOMES, percentages)
            )
        else:
            cells.extend(["not assessed" for _ in OUTCOMES])
        rendered_cells = []
        for index, value in enumerate(cells):
            css_class = "num" if index >= 2 else ""
            rendered_cells.append(f'<td class="{css_class}">{value}</td>')
        output.append(
            f'<tr data-collection="{html.escape(str(row["collection"]))}">'
            + "".join(rendered_cells)
            + "</tr>"
        )
    return "".join(output)


def _write_benchmark_workbooks(
    target: Path,
    summaries: dict[str, Any],
    decisions: list[dict[str, Any]],
    assessment_failures: list[dict[str, Any]],
    retrieval_failures: list[dict[str, Any]],
    snapshot: dict[str, Any],
    harmonization: dict[str, Any],
    ontology_publication_rows: list[dict[str, Any]],
    exact_label_review: list[dict[str, Any]],
    ambiguity_history: list[dict[str, Any]],
    pre_post_rows: list[dict[str, Any]],
    corrections: list[dict[str, Any]],
) -> None:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError as error:  # pragma: no cover - dependency guard
        raise RuntimeError("Excel output requires openpyxl>=3.1.5. Install the project dependencies.") from error

    def add_sheet(workbook: Any, title: str, rows: list[dict[str, Any]], columns: list[str]) -> None:
        sheet = workbook.create_sheet(title=title[:31])
        sheet.append(columns)
        for row in rows:
            sheet.append([_excel_value(row.get(column, "")) for column in columns])
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        header_fill = PatternFill("solid", fgColor="173042")
        for cell in sheet[1]:
            cell.font = Font(color="FFFFFF", bold=True)
            cell.fill = header_fill
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        for index, column in enumerate(columns, start=1):
            sample = [str(sheet.cell(row=row, column=index).value or "") for row in range(1, min(sheet.max_row, 200) + 1)]
            width = min(max(max((len(value) for value in sample), default=8) + 2, 10), 55)
            sheet.column_dimensions[get_column_letter(index)].width = width
            if column.endswith("_percent"):
                for row_index in range(2, sheet.max_row + 1):
                    sheet.cell(row=row_index, column=index).number_format = "0.00\"%\""

    def add_readme(workbook: Any) -> None:
        sheet = workbook.active
        sheet.title = "Read me"
        rows = [
            ("H2KG-TIB collection benchmark", "Automated, role-aware, native-class-first comparison."),
            ("TIB snapshot", snapshot.get("retrieved_at", "")),
            ("H2KG denominator", summaries["benchmark_summary"]["h2kg_active_classes_assessed"]),
            ("Primary policy", "Native ontology classes only; imported availability is separate."),
            ("BattINFO", "Catalogue membership retained; semantic outcomes excluded because native frozen evidence is unavailable."),
            ("Rounding", "Display percentages are rounded independently; exact counts are authoritative."),
            ("TIB catalogue counts", "Descriptive metadata; may include imports and are not overlap denominators."),
            ("Strict coverage", "exact_iri_reuse + machine_exact_equivalent"),
            ("Publication gate", "Retrieval failures block generation; semantic abstentions must be zero."),
            ("Caution", "Machine-accepted correspondences are deterministic evidence classifications, not human-validated equivalence."),
        ]
        for key, value in rows:
            sheet.append([key, value])
        sheet.column_dimensions["A"].width = 28
        sheet.column_dimensions["B"].width = 95
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="137F82")

    def add_grouped_ontology_sheet(workbook: Any, title: str) -> None:
        sheet = workbook.create_sheet(title=title[:31])
        sheet.append(ONTOLOGY_PUBLICATION_COLUMNS)
        for row in ontology_publication_rows:
            sheet.append([_excel_value(row.get(column, "")) for column in ONTOLOGY_PUBLICATION_COLUMNS])
        sheet.freeze_panes = "A2"
        header_fill = PatternFill("solid", fgColor="173042")
        group_fills = (PatternFill("solid", fgColor="E8F3F1"), PatternFill("solid", fgColor="F7EFE1"))
        for cell in sheet[1]:
            cell.font = Font(color="FFFFFF", bold=True)
            cell.fill = header_fill
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        start = 2
        groups: list[tuple[int, int]] = []
        while start <= sheet.max_row:
            value = sheet.cell(start, 1).value
            end = start
            while end + 1 <= sheet.max_row and sheet.cell(end + 1, 1).value == value:
                end += 1
            groups.append((start, end))
            start = end + 1
        for group_index, (start, end) in enumerate(groups):
            if end > start:
                sheet.merge_cells(start_row=start, start_column=1, end_row=end, end_column=1)
            sheet.cell(start, 1).alignment = Alignment(vertical="center", horizontal="center", text_rotation=90)
            for row_index in range(start, end + 1):
                for column_index in range(1, len(ONTOLOGY_PUBLICATION_COLUMNS) + 1):
                    sheet.cell(row_index, column_index).fill = group_fills[group_index % len(group_fills)]
        tib_link_column = ONTOLOGY_PUBLICATION_COLUMNS.index("TIB link") + 1
        for row_index in range(2, sheet.max_row + 1):
            cell = sheet.cell(row_index, tib_link_column)
            if cell.value:
                cell.hyperlink = str(cell.value)
                cell.style = "Hyperlink"
        for index, column in enumerate(ONTOLOGY_PUBLICATION_COLUMNS, start=1):
            width = 20 if column in PUBLICATION_OUTCOME_LABELS.values() else 24
            if column == "Ontology title":
                width = 42
            elif column == "TIB link":
                width = 42
            elif column == "Collection":
                width = 15
            sheet.column_dimensions[get_column_letter(index)].width = width
        sheet.auto_filter.ref = f"B1:{get_column_letter(len(ONTOLOGY_PUBLICATION_COLUMNS))}{sheet.max_row}"

    def add_collection_publication_sheet(workbook: Any, title: str) -> None:
        rows = _collection_publication_rows(summaries["collection_summary"])
        add_sheet(workbook, title, rows, COLLECTION_PUBLICATION_COLUMNS)

    full = Workbook()
    add_readme(full)
    add_sheet(full, "Collection summary", summaries["collection_summary"], SUMMARY_COLUMNS)
    add_grouped_ontology_sheet(full, "Ontology benchmark")
    add_sheet(full, "Ontology data", summaries["ontology_summary"], ONTOLOGY_SUMMARY_COLUMNS)
    add_sheet(full, "Category summary", summaries["category_summary"], CATEGORY_SUMMARY_COLUMNS)
    add_sheet(full, "Class coverage", summaries["class_collection_rows"], CLASS_COVERAGE_COLUMNS)
    add_sheet(full, "Candidate decisions", decisions, DECISION_COLUMNS)
    add_sheet(full, "Assessment failures", assessment_failures, ASSESSMENT_FAILURE_COLUMNS)
    add_sheet(full, "Retrieval failures", retrieval_failures, RETRIEVAL_FAILURE_COLUMNS)
    add_sheet(full, "Exact-label review", exact_label_review, DECISION_COLUMNS)
    add_sheet(full, "Ambiguity history", ambiguity_history, DECISION_COLUMNS)
    add_sheet(full, "Pre-post comparison", pre_post_rows, PRE_POST_COLUMNS)
    add_sheet(full, "H2KG corrections", corrections, CORRECTION_COLUMNS)
    add_sheet(full, "Imported availability", summaries["imported_availability"], IMPORT_COLUMNS)
    add_sheet(full, "TIB catalogue", snapshot.get("ontologies", []), CATALOGUE_COLUMNS)
    add_sheet(full, "Safe mappings", harmonization.get("mappings", []), HARMONIZATION_MAPPING_COLUMNS)
    add_sheet(full, "Safe label changes", harmonization.get("label_changes", []), LABEL_CHANGE_COLUMNS)
    full.save(target / "h2kg_tib_collection_benchmark.xlsx")

    manuscript = Workbook()
    add_readme(manuscript)
    add_collection_publication_sheet(manuscript, "Collection summary")
    add_grouped_ontology_sheet(manuscript, "Ontology benchmark")
    add_sheet(manuscript, "H2KG branch summary", summaries["category_summary"], CATEGORY_SUMMARY_COLUMNS)
    manuscript.save(target / "h2kg_tib_manuscript_tables.xlsx")


def _excel_value(value: Any) -> Any:
    if isinstance(value, (list, tuple, set)):
        return " | ".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


DECISION_COLUMNS = [
    "mapping_key", "h2kg_iri", "h2kg_local_name", "h2kg_label", "h2kg_alt_labels",
    "h2kg_definition", "h2kg_role", "h2kg_top_branch", "h2kg_parent_label", "h2kg_module",
    "collection_memberships", "ontology_id", "external_iri", "external_label", "external_definition",
    "external_role", "external_role_confidence", "external_role_evidence", "external_parent_labels",
    "external_direct_parent_iris", "external_ancestor_iris", "external_type", "external_obsolete",
    "native_to_ontology", "appears_in_ontologies", "lexical_similarity", "role_compatible",
    "definition_conflict", "material_state_conflict", "granularity_conflict", "previous_outcome",
    "final_outcome", "outcome", "rule_id", "confidence",
    "scope_evidence", "decision_basis", "evidence_source", "safe_for_harmonization",
]

PUBLICATION_OUTCOME_LABELS = {
    "exact_iri_reuse": "Exact IRI reuse",
    "machine_exact_equivalent": "Machine exact equivalent",
    "h2kg_narrower": "H2KG narrower",
    "h2kg_broader": "H2KG broader",
    "related_non_equivalent": "Related non-equivalent",
    "ambiguous_abstained": "Ambiguous abstained",
    "unmatched": "Unmatched",
}
ONTOLOGY_PUBLICATION_COLUMNS = [
    "Collection", "Ontology ID", "Ontology title", "Version", "TIB link", "TIB-reported terms",
    "Assessment status", "Native evidence status", "H2KG classes assessed",
    *[PUBLICATION_OUTCOME_LABELS[outcome] for outcome in OUTCOMES],
]
COLLECTION_PUBLICATION_COLUMNS = [
    "Collection", "Member ontologies", "Assessed ontologies", "H2KG classes assessed",
    *[PUBLICATION_OUTCOME_LABELS[outcome] for outcome in OUTCOMES],
]

SUMMARY_BASE_COLUMNS = [
    "scope_type", "collection", "ontology_id", "ontology_title", "ontology_version",
    "member_ontology_count", "assessed_member_ontology_count", "tib_reported_term_count",
    "assessment_status", "native_evidence_status", "h2kg_classes_assessed",
]
SUMMARY_METRIC_COLUMNS = [item for outcome in OUTCOMES for item in (f"{outcome}_count", f"{outcome}_percent")]
SUMMARY_COLUMNS = [*SUMMARY_BASE_COLUMNS, *SUMMARY_METRIC_COLUMNS, "strict_coverage_percent", "hierarchical_coverage_percent"]
ONTOLOGY_SUMMARY_COLUMNS = SUMMARY_COLUMNS
CATEGORY_SUMMARY_COLUMNS = [
    "collection", "h2kg_top_branch", "h2kg_classes_assessed", *SUMMARY_METRIC_COLUMNS,
]
CLASS_COVERAGE_COLUMNS = [
    "collection", "h2kg_iri", "h2kg_local_name", "h2kg_label", "h2kg_role", "h2kg_top_branch",
    "outcome", "best_ontology_id", "best_external_iri", "best_external_label", "decision_basis",
]
IMPORT_COLUMNS = [
    "collection", "hosting_ontology_id", "defining_ontology_id", "h2kg_iri", "h2kg_label",
    "external_iri", "external_label", "outcome",
]
ASSESSMENT_FAILURE_COLUMNS = [
    "h2kg_iri", "h2kg_label", "h2kg_role", "h2kg_top_branch", "failed_query_count",
    "successful_query_count", "failed_queries", "errors", "benchmark_treatment",
]
RETRIEVAL_FAILURE_COLUMNS = [
    "retrieval_type", "retrieval_key", "query_or_iri", "status", "error", "publication_effect",
]
PRE_POST_COLUMNS = [
    "collection", "outcome", "baseline_count", "baseline_percent", "final_count", "final_percent",
    "count_change", "percentage_point_change",
]
CORRECTION_COLUMNS = [
    "correction_id", "local_iri", "local_name", "action", "previous_value", "final_value",
    "preferred_label_override", "definition_override", "scope_note", "required_parent", "confidence",
    "evidence", "rationale", "status",
]
CATALOGUE_COLUMNS = [
    "ontology_id", "title", "version", "ontology_iri", "file_location", "loaded", "updated",
    "number_of_terms", "number_of_properties", "number_of_individuals", "collections", "target_collections",
]
HARMONIZATION_MAPPING_COLUMNS = [
    "local_iri", "local_label", "relation", "target_iri", "target_label", "tib_ontology_id",
    "tib_ontology_title", "tib_ontology_version", "tib_catalogue_url", "collections", "outcome",
    "confidence", "rule_id", "status", "publication_status", "decision_basis", "scope_evidence",
    "snapshot_retrieved_at", "snapshot_sha256",
]
LABEL_CHANGE_COLUMNS = [
    "local_iri", "old_preferred_label", "new_preferred_label", "add_alt_label", "target_iri",
    "target_ontology_id", "status", "rationale",
]
