from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, RDF, RDFS, SKOS

from .utils import QUDT, read_csv, write_csv, write_json, write_text

QUDT_UNIT_CLASS = URIRef("http://qudt.org/schema/qudt/Unit")
QUDT_QUANTITY_VALUE_CLASS = URIRef("http://qudt.org/schema/qudt/QuantityValue")
QUDT_UCUM_CODE = URIRef("http://qudt.org/schema/qudt/ucumCode")


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
    return cleaned or "value"


def _normalize_unit_label(value: str) -> str:
    text = _clean_text(value)
    text = text.replace("µ", "u").replace("μ", "u").replace("Ω", "Ohm").replace("°C", "degC")
    text = text.replace("−", "-").replace("–", "-").replace("—", "-")
    text = text.replace("·", " ").replace("*", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip().casefold()


def _normalize_alias(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _clean_text(value).casefold())


def _normalize_unit_rows(units_rows: list[dict[str, str]], fill_rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    units_by_key: dict[str, dict[str, str]] = {}
    for row in units_rows:
        key = _clean_text(row.get("unit_key"))
        if not key:
            continue
        normalized = dict(row)
        normalized["unit_label"] = _clean_text(row.get("unit_label"))
        normalized["ucum_code"] = _clean_text(row.get("ucum_code"))
        normalized["qudt_unit_iri"] = _clean_text(row.get("qudt_unit_iri"))
        units_by_key[key] = normalized

    for row in fill_rows:
        key = _clean_text(row.get("unit_key"))
        if not key or key not in units_by_key:
            continue
        status = _clean_text(row.get("status"))
        if not status.startswith("filled"):
            continue
        if not units_by_key[key].get("qudt_unit_iri"):
            units_by_key[key]["qudt_unit_iri"] = _clean_text(row.get("qudt_unit_iri"))
        if not units_by_key[key].get("ucum_code"):
            units_by_key[key]["ucum_code"] = _clean_text(row.get("matched_ucum")) or _clean_text(row.get("ucum_code"))

    # Safe lexical fallbacks for common unitless cases that are stable in PEMFC GT data.
    for row in units_by_key.values():
        label_norm = _normalize_unit_label(row.get("unit_label", ""))
        if label_norm in {"1", "unitless", "dimensionless"} and not row.get("qudt_unit_iri"):
            row["qudt_unit_iri"] = "http://qudt.org/vocab/unit/UNITLESS"
        elif label_norm in {"%", "percent"} and not row.get("qudt_unit_iri"):
            row["qudt_unit_iri"] = "http://qudt.org/vocab/unit/PERCENT"

    return units_by_key


def _parse_iri_list(value: str) -> list[str]:
    text = _clean_text(value)
    if not text:
        return []
    candidates = [part.strip() for part in re.split(r"[;|]", text)]
    return [item for item in candidates if item.startswith("http://") or item.startswith("https://")]


def _resolve_unit_source_dir(root: Path, configured: str | Path | None) -> Path | None:
    if configured is None or not _clean_text(configured):
        return None
    candidate = Path(configured)
    if candidate.is_absolute():
        return candidate if candidate.exists() else None
    local = (root / candidate).resolve()
    if local.exists():
        return local
    # When running profile workspaces, allow paths relative to the package root.
    try:
        package_root = root.parents[3]
        fallback = (package_root / candidate).resolve()
        if fallback.exists():
            return fallback
    except IndexError:
        pass
    return None


def _resolve_optional_file(root: Path, configured: str | Path | None) -> Path | None:
    if configured is None or not _clean_text(configured):
        return None
    candidate = Path(configured)
    if candidate.is_absolute():
        return candidate if candidate.exists() else None
    local = (root / candidate).resolve()
    if local.exists():
        return local
    try:
        package_root = root.parents[3]
        fallback = (package_root / candidate).resolve()
        if fallback.exists():
            return fallback
    except IndexError:
        pass
    return None


def _local_term_graphs(schema_graph: Graph, controlled_vocabulary_graph: Graph) -> dict[str, Graph]:
    index: dict[str, Graph] = {}
    for graph in (schema_graph, controlled_vocabulary_graph):
        for subject in set(graph.subjects()):
            if isinstance(subject, URIRef):
                index[str(subject)] = graph
    return index


def _term_label(graph: Graph, subject: URIRef) -> str:
    for predicate in (RDFS.label, SKOS.prefLabel):
        for obj in graph.objects(subject, predicate):
            return _clean_text(obj)
    return _slugify(str(subject).rsplit("#", 1)[-1]).replace("_", " ")


def _term_aliases(graph: Graph, subject: URIRef) -> list[str]:
    aliases: list[str] = []
    seen: set[str] = set()
    for predicate in (RDFS.label, SKOS.prefLabel, SKOS.altLabel):
        for obj in graph.objects(subject, predicate):
            text = _clean_text(obj)
            if text and text not in seen:
                seen.add(text)
                aliases.append(text)
    fallback = _slugify(str(subject).rsplit("#", 1)[-1]).replace("_", " ")
    if fallback and fallback not in seen:
        aliases.append(fallback)
    return aliases


def _ensure_quantity_value_node(graph: Graph, term: URIRef, namespace_policy: dict[str, Any]) -> URIRef:
    has_quantity_value = URIRef(f"{namespace_policy['term_namespace']}hasQuantityValue")
    existing = [obj for obj in graph.objects(term, has_quantity_value) if isinstance(obj, URIRef)]
    if existing:
        return existing[0]
    qv_iri = URIRef(f"{namespace_policy['term_namespace']}_{_slugify(str(term).rsplit('#', 1)[-1])}_QV")
    graph.add((term, has_quantity_value, qv_iri))
    graph.add((qv_iri, RDF.type, QUDT_QUANTITY_VALUE_CLASS))
    graph.add((qv_iri, RDFS.label, Literal(f"{_term_label(graph, term)} unit descriptor", lang="en")))
    return qv_iri


def _existing_unit_objects(graph: Graph, term: URIRef, namespace_policy: dict[str, Any]) -> list[URIRef]:
    rows: list[URIRef] = []
    for obj in graph.objects(term, QUDT.unit):
        if isinstance(obj, URIRef):
            rows.append(obj)
    has_quantity_value = URIRef(f"{namespace_policy['term_namespace']}hasQuantityValue")
    for qv in graph.objects(term, has_quantity_value):
        for obj in graph.objects(qv, QUDT.unit):
            if isinstance(obj, URIRef):
                rows.append(obj)
    return rows


def _existing_quantity_kind_objects(graph: Graph, term: URIRef, namespace_policy: dict[str, Any]) -> list[URIRef]:
    rows: list[URIRef] = []
    for obj in graph.objects(term, QUDT.quantityKind):
        if isinstance(obj, URIRef):
            rows.append(obj)
    has_quantity_value = URIRef(f"{namespace_policy['term_namespace']}hasQuantityValue")
    for qv in graph.objects(term, has_quantity_value):
        for obj in graph.objects(qv, QUDT.quantityKind):
            if isinstance(obj, URIRef):
                rows.append(obj)
    return rows


def _identity_key(unit_row: dict[str, str]) -> tuple[str, str]:
    qudt_iri = _clean_text(unit_row.get("qudt_unit_iri"))
    if qudt_iri:
        return ("qudt", qudt_iri)
    ucum_code = _clean_text(unit_row.get("ucum_code"))
    if ucum_code:
        return ("ucum", ucum_code)
    return ("label", _normalize_unit_label(unit_row.get("unit_label", "")))


def _preferred_quantity_kind(observations: list[dict[str, str]]) -> str:
    counter = Counter(_clean_text(row.get("quantity_kind_iri")) for row in observations if _clean_text(row.get("quantity_kind_iri")))
    if not counter:
        return ""
    return counter.most_common(1)[0][0]


def _build_local_unit(
    graph: Graph,
    term: URIRef,
    unit_row: dict[str, str],
    namespace_policy: dict[str, Any],
    unit_iri_override: str = "",
    source_label: str = "cleaned_v4 unit registry",
) -> URIRef:
    label = (
        _clean_text(unit_row.get("unit_label"))
        or _clean_text(unit_row.get("preferred_unit_label"))
        or _clean_text(unit_row.get("raw_unit_examples"))
        or "Local reviewed unit"
    )
    if unit_iri_override:
        unit_iri = URIRef(unit_iri_override)
    else:
        slug = _slugify(f"{term.rsplit('#', 1)[-1]}_{label}")
        unit_iri = URIRef(f"{namespace_policy['term_namespace']}_Unit_{slug}")
    graph.add((unit_iri, RDF.type, QUDT_UNIT_CLASS))
    graph.add((unit_iri, RDFS.label, Literal(label, lang="en")))
    graph.add(
        (
            unit_iri,
            RDFS.comment,
            Literal(
                "Locally curated PEMFC unit placeholder generated from cleaned GT evidence because no reviewed QUDT unit mapping was available.",
                lang="en",
            ),
        )
    )
    ucum_code = _clean_text(unit_row.get("ucum_code")) or _clean_text(unit_row.get("preferred_ucum_code"))
    if ucum_code:
        graph.add((unit_iri, QUDT_UCUM_CODE, Literal(ucum_code)))
    raw_examples = _clean_text(unit_row.get("raw_unit_examples"))
    if raw_examples:
        graph.add((unit_iri, SKOS.notation, Literal(raw_examples)))
    graph.add((unit_iri, DCTERMS.source, Literal(source_label)))
    return unit_iri


def _append_review_row(review_rows: list[dict[str, Any]], row: dict[str, Any]) -> None:
    term_iri = _clean_text(row.get("term_iri"))
    review_rows[:] = [item for item in review_rows if _clean_text(item.get("term_iri")) != term_iri]
    review_rows.append(row)


def _propagate_units_by_alias(
    schema_graph: Graph,
    controlled_vocabulary_graph: Graph,
    namespace_policy: dict[str, Any],
    review_rows: list[dict[str, Any]],
) -> dict[str, int]:
    term_graph_index = _local_term_graphs(schema_graph, controlled_vocabulary_graph)
    has_quantity_value = URIRef(f"{namespace_policy['term_namespace']}hasQuantityValue")
    alias_index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    propagated_qudt_units = 0
    propagated_local_units = 0

    def term_signature(term_iri: str, graph: Graph) -> dict[str, Any] | None:
        subject = URIRef(term_iri)
        units = list(dict.fromkeys(str(obj) for obj in _existing_unit_objects(graph, subject, namespace_policy)))
        if len(units) != 1:
            return None
        quantity_kinds = list(dict.fromkeys(str(obj) for obj in _existing_quantity_kind_objects(graph, subject, namespace_policy)))
        aliases = _term_aliases(graph, subject)
        return {
            "term_iri": term_iri,
            "term_label": _term_label(graph, subject),
            "primary_label_norm": _normalize_alias(_term_label(graph, subject)),
            "unit_iri": units[0],
            "quantity_kind_iri": quantity_kinds[0] if quantity_kinds else "",
            "aliases": aliases,
        }

    for term_iri, graph in sorted(term_graph_index.items()):
        signature = term_signature(term_iri, graph)
        if signature is None:
            continue
        for alias in signature["aliases"]:
            normalized = _normalize_alias(alias)
            if normalized:
                alias_index[normalized].append(signature)

    for term_iri, graph in sorted(term_graph_index.items()):
        subject = URIRef(term_iri)
        if _existing_unit_objects(graph, subject, namespace_policy):
            continue
        quantity_nodes = [obj for obj in graph.objects(subject, has_quantity_value) if isinstance(obj, URIRef)]

        aliases = _term_aliases(graph, subject)
        matched_signatures: dict[tuple[str, str, str], dict[str, Any]] = {}
        matched_aliases: set[str] = set()
        for alias in aliases:
            normalized = _normalize_alias(alias)
            if not normalized:
                continue
            for signature in alias_index.get(normalized, []):
                if signature["term_iri"] == term_iri:
                    continue
                matched_aliases.add(alias)
                key = (signature["unit_iri"], signature["quantity_kind_iri"], signature["term_iri"])
                matched_signatures[key] = signature

        quantity_kinds = [str(obj) for obj in _existing_quantity_kind_objects(graph, subject, namespace_policy)]
        target_primary_label_norm = _normalize_alias(_term_label(graph, subject))
        prioritized_signatures = list(matched_signatures.values())
        exact_primary_matches = [item for item in prioritized_signatures if item.get("primary_label_norm") == target_primary_label_norm]
        used_exact_primary_match = False
        if len(exact_primary_matches) == 1:
            prioritized_signatures = exact_primary_matches
            used_exact_primary_match = True
        elif quantity_kinds:
            same_quantity_kind = [item for item in prioritized_signatures if item.get("quantity_kind_iri") in quantity_kinds]
            if len(same_quantity_kind) == 1:
                prioritized_signatures = same_quantity_kind

        unique_signatures = {
            (item["unit_iri"], item["quantity_kind_iri"], item["term_iri"]): item for item in prioritized_signatures
        }

        if len(unique_signatures) == 1:
            signature = next(iter(unique_signatures.values()))
            qv_node = quantity_nodes[0] if quantity_nodes else _ensure_quantity_value_node(graph, subject, namespace_policy)
            unit_iri = signature["unit_iri"]
            graph.add((qv_node, QUDT.unit, URIRef(unit_iri)))
            if not quantity_kinds and signature["quantity_kind_iri"]:
                graph.add((qv_node, QUDT.quantityKind, URIRef(signature["quantity_kind_iri"])))

            unit_label = ""
            if unit_iri.startswith("http://qudt.org/") or unit_iri.startswith("https://qudt.org/"):
                unit_label = unit_iri.rsplit("/", 1)[-1]
            else:
                for obj in graph.objects(URIRef(unit_iri), RDFS.label):
                    unit_label = _clean_text(obj)
                    break
            if not unit_label:
                unit_label = unit_iri.rsplit("#", 1)[-1]

            matched_alias = _term_label(graph, subject) if used_exact_primary_match else (sorted(matched_aliases, key=len, reverse=True)[0] if matched_aliases else aliases[0])
            if unit_iri.startswith("http://qudt.org/") or unit_iri.startswith("https://qudt.org/"):
                decision = "assert_alias_qudt_unit"
                propagated_qudt_units += 1
            else:
                decision = "assert_alias_local_reviewed_unit"
                propagated_local_units += 1

            _append_review_row(
                review_rows,
                {
                    "term_iri": term_iri,
                    "term_label": _term_label(graph, subject),
                    "decision": decision,
                    "support_count": 0,
                    "consensus_ratio": "",
                    "quantity_kind_iri": quantity_kinds[0] if quantity_kinds else signature["quantity_kind_iri"],
                    "preferred_unit_label": unit_label,
                    "preferred_qudt_unit_iri": unit_iri if unit_iri.startswith("http://qudt.org/") or unit_iri.startswith("https://qudt.org/") else "",
                    "preferred_ucum_code": "",
                    "local_unit_iri": unit_iri if not (unit_iri.startswith("http://qudt.org/") or unit_iri.startswith("https://qudt.org/")) else "",
                    "note": f"Applied unit through exact alias match `{matched_alias}` from `{signature['term_label']}`.",
                },
            )
            continue

        note = "No curated unit was found through direct or alias-based matching."
        decision = "review_missing_unit_after_alias_check"
        if len(unique_signatures) > 1:
            decision = "review_ambiguous_alias_unit_match"
            note = "Multiple alias-based unit candidates were found; manual review is required."
        _append_review_row(
            review_rows,
            {
                "term_iri": term_iri,
                "term_label": _term_label(graph, subject),
                "decision": decision,
                "support_count": 0,
                "consensus_ratio": "",
                "quantity_kind_iri": quantity_kinds[0] if quantity_kinds else "",
                "preferred_unit_label": "",
                "preferred_qudt_unit_iri": "",
                "preferred_ucum_code": "",
                "local_unit_iri": "",
                "note": note,
            },
        )

    review_rows.sort(key=lambda row: (_clean_text(row.get("decision", "")), _clean_text(row.get("term_label", "")), _clean_text(row.get("term_iri", ""))))
    return {
        "alias_qudt_units_linked": propagated_qudt_units,
        "alias_local_units_linked": propagated_local_units,
    }


def _load_curated_unit_rows(path: Path) -> list[dict[str, str]]:
    rows = read_csv(path)
    return [
        row
        for row in rows
        if _clean_text(row.get("term_iri"))
        and _clean_text(row.get("decision")) in {"assert_qudt_unit", "assert_local_reviewed_unit"}
    ]


def _apply_curated_units(
    schema_graph: Graph,
    controlled_vocabulary_graph: Graph,
    namespace_policy: dict[str, Any],
    curated_rows: list[dict[str, str]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    term_graph_index = _local_term_graphs(schema_graph, controlled_vocabulary_graph)
    applied_rows: list[dict[str, Any]] = []
    terms_enriched = 0
    qudt_units_linked = 0
    local_units_created = 0

    for row in curated_rows:
        term_iri = _clean_text(row.get("term_iri"))
        graph = term_graph_index.get(term_iri)
        if graph is None:
            continue
        term_ref = URIRef(term_iri)
        existing_units = _existing_unit_objects(graph, term_ref, namespace_policy)
        if existing_units:
            applied_rows.append(
                {
                    **row,
                    "decision": "skip_existing_unit",
                    "note": "Existing ontology unit assertion preserved.",
                }
            )
            continue

        quantity_kind_iri = _clean_text(row.get("quantity_kind_iri"))
        qv_node = _ensure_quantity_value_node(graph, term_ref, namespace_policy)
        decision = _clean_text(row.get("decision"))
        note = _clean_text(row.get("note"))

        if decision == "assert_qudt_unit" and _clean_text(row.get("preferred_qudt_unit_iri")):
            unit_iri = URIRef(_clean_text(row.get("preferred_qudt_unit_iri")))
            graph.add((qv_node, QUDT.unit, unit_iri))
            if quantity_kind_iri:
                graph.add((qv_node, QUDT.quantityKind, URIRef(quantity_kind_iri)))
            terms_enriched += 1
            qudt_units_linked += 1
            applied_rows.append({**row, "note": note})
            continue

        if decision == "assert_local_reviewed_unit" and _clean_text(row.get("preferred_unit_label")):
            local_unit = _build_local_unit(
                graph,
                term_ref,
                row,
                namespace_policy,
                unit_iri_override=_clean_text(row.get("local_unit_iri")),
                source_label="PEMFC curated unit registry",
            )
            graph.add((qv_node, QUDT.unit, local_unit))
            if quantity_kind_iri:
                graph.add((qv_node, QUDT.quantityKind, URIRef(quantity_kind_iri)))
            terms_enriched += 1
            local_units_created += 1
            applied_rows.append({**row, "local_unit_iri": str(local_unit), "note": note})

    report = {
        "terms_examined": len(curated_rows),
        "terms_enriched": terms_enriched,
        "qudt_units_linked": qudt_units_linked,
        "local_units_created": local_units_created,
        "review_rows": len(applied_rows),
    }
    return report, applied_rows


def enrich_units_from_cleaned_dataset(
    schema_graph: Graph,
    controlled_vocabulary_graph: Graph,
    release_profile: dict[str, Any],
    namespace_policy: dict[str, Any],
    root: Path,
    evidence_dir: str | Path | None = None,
) -> dict[str, Any]:
    cfg = release_profile.get("unit_enrichment", {})
    curated_units_path = _resolve_optional_file(root, cfg.get("curated_units_path"))
    enabled = bool(cfg.get("enabled", False) or evidence_dir or curated_units_path)
    resolved_dir = _resolve_unit_source_dir(root, evidence_dir or cfg.get("evidence_dir"))
    if resolved_dir is None and curated_units_path is not None:
        curated_rows = _load_curated_unit_rows(curated_units_path)
        summary, applied_rows = _apply_curated_units(
            schema_graph,
            controlled_vocabulary_graph,
            namespace_policy,
            curated_rows,
        )
        alias_summary = _propagate_units_by_alias(
            schema_graph,
            controlled_vocabulary_graph,
            namespace_policy,
            applied_rows,
        )
        report = {
            "enabled": enabled,
            "applied": True,
            "source": "curated_unit_registry",
            "evidence_dir": "",
            "curated_units_path": str(curated_units_path),
            **summary,
            **alias_summary,
            "terms_enriched": summary["terms_enriched"] + alias_summary["alias_qudt_units_linked"] + alias_summary["alias_local_units_linked"],
            "qudt_units_linked": summary["qudt_units_linked"] + alias_summary["alias_qudt_units_linked"],
            "local_units_created": summary["local_units_created"] + alias_summary["alias_local_units_linked"],
            "review_rows": len(applied_rows),
        }
        write_unit_enrichment_outputs(report, applied_rows, root)
        return report

    if not enabled or not resolved_dir:
        report = {
            "enabled": enabled,
            "applied": False,
            "source": "none",
            "evidence_dir": str(evidence_dir or cfg.get("evidence_dir") or ""),
            "curated_units_path": str(curated_units_path or ""),
            "reason": "No cleaned evidence directory was configured or found.",
            "terms_examined": 0,
            "terms_enriched": 0,
            "qudt_units_linked": 0,
            "local_units_created": 0,
            "review_rows": 0,
        }
        write_unit_enrichment_outputs(report, [], root)
        return report

    datapoints_path = resolved_dir / "datapoints.csv"
    units_path = resolved_dir / "units.csv"
    if not datapoints_path.exists() or not units_path.exists():
        report = {
            "enabled": True,
            "applied": False,
            "source": "cleaned_evidence",
            "evidence_dir": str(resolved_dir),
            "curated_units_path": str(curated_units_path or ""),
            "reason": "Cleaned datapoints.csv or units.csv is missing.",
            "terms_examined": 0,
            "terms_enriched": 0,
            "qudt_units_linked": 0,
            "local_units_created": 0,
            "review_rows": 0,
        }
        write_unit_enrichment_outputs(report, [], root)
        return report

    datapoint_rows = read_csv(datapoints_path)
    unit_rows = read_csv(units_path)
    fill_rows = read_csv(resolved_dir / "qudt_fill_report_iter4.csv") if (resolved_dir / "qudt_fill_report_iter4.csv").exists() else []
    units_by_key = _normalize_unit_rows(unit_rows, fill_rows)
    term_graph_index = _local_term_graphs(schema_graph, controlled_vocabulary_graph)
    supported_prefix = namespace_policy["term_namespace"]

    evidence_by_term: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in datapoint_rows:
        unit_key = _clean_text(row.get("unit_key"))
        if not unit_key or unit_key not in units_by_key:
            continue
        term_iris: list[str] = []
        of_property = _clean_text(row.get("of_property_iri"))
        if of_property.startswith(supported_prefix):
            term_iris.append(of_property)
        for iri in _parse_iri_list(row.get("has_condition_iris", "")):
            if iri.startswith(supported_prefix):
                term_iris.append(iri)
        if not term_iris:
            continue

        unit_row = units_by_key[unit_key]
        for term_iri in term_iris:
            evidence_by_term[term_iri].append(
                {
                    "term_iri": term_iri,
                    "unit_key": unit_key,
                    "unit_label": _clean_text(unit_row.get("unit_label")),
                    "raw_unit_examples": _clean_text(unit_row.get("raw_unit_examples")),
                    "qudt_unit_iri": _clean_text(unit_row.get("qudt_unit_iri")),
                    "ucum_code": _clean_text(unit_row.get("ucum_code")),
                    "quantity_kind_iri": _clean_text(row.get("quantity_kind_iri")),
                    "datapoint_kind": _clean_text(row.get("datapoint_kind")),
                    "source_file": _clean_text(row.get("source_file")),
                    "needs_mapping": _clean_text(unit_row.get("needs_mapping")),
                }
            )

    min_observations = int(cfg.get("min_observations", 1))
    min_ratio = float(cfg.get("min_consensus_ratio", 0.8))
    create_local_units = bool(cfg.get("create_local_units", True))

    review_rows: list[dict[str, Any]] = []
    terms_enriched = 0
    qudt_units_linked = 0
    local_units_created = 0

    for term_iri, observations in sorted(evidence_by_term.items()):
        graph = term_graph_index.get(term_iri)
        if graph is None:
            continue
        term_ref = URIRef(term_iri)
        existing_units = _existing_unit_objects(graph, term_ref, namespace_policy)
        if existing_units:
            review_rows.append(
                {
                    "term_iri": term_iri,
                    "term_label": _term_label(graph, term_ref),
                    "decision": "skip_existing_unit",
                    "support_count": len(observations),
                    "consensus_ratio": 1.0,
                    "quantity_kind_iri": _preferred_quantity_kind(observations),
                    "preferred_unit_label": "",
                    "preferred_qudt_unit_iri": str(existing_units[0]),
                    "preferred_ucum_code": "",
                    "local_unit_iri": "",
                    "note": "Existing ontology unit assertion preserved.",
                }
            )
            continue

        identity_counter = Counter(_identity_key(item) for item in observations)
        if not identity_counter:
            continue
        preferred_identity, support_count = identity_counter.most_common(1)[0]
        consensus_ratio = support_count / max(len(observations), 1)
        preferred_rows = [item for item in observations if _identity_key(item) == preferred_identity]
        preferred_unit = preferred_rows[0]
        quantity_kind_iri = _preferred_quantity_kind(observations)

        decision = "review_multi_unit"
        note = ""
        local_unit_iri = ""
        preferred_unit_iri = preferred_unit.get("qudt_unit_iri", "")
        preferred_ucum_code = preferred_unit.get("ucum_code", "")

        if support_count < min_observations:
            decision = "review_low_support"
            note = "Not enough cleaned datapoint support to assert a term-level unit."
        elif len(identity_counter) > 1 and consensus_ratio < min_ratio:
            decision = "review_multi_unit"
            note = "Multiple competing units remain for this term in the cleaned PEMFC evidence."
        elif preferred_identity[0] == "qudt" and preferred_unit_iri:
            qv_node = _ensure_quantity_value_node(graph, term_ref, namespace_policy)
            graph.add((qv_node, QUDT.unit, URIRef(preferred_unit_iri)))
            if quantity_kind_iri:
                graph.add((qv_node, QUDT.quantityKind, URIRef(quantity_kind_iri)))
            decision = "assert_qudt_unit"
            terms_enriched += 1
            qudt_units_linked += 1
        elif preferred_identity[0] in {"ucum", "label"} and create_local_units:
            qv_node = _ensure_quantity_value_node(graph, term_ref, namespace_policy)
            local_unit = _build_local_unit(graph, term_ref, preferred_unit, namespace_policy)
            graph.add((qv_node, QUDT.unit, local_unit))
            if quantity_kind_iri:
                graph.add((qv_node, QUDT.quantityKind, URIRef(quantity_kind_iri)))
            decision = "assert_local_reviewed_unit"
            local_unit_iri = str(local_unit)
            terms_enriched += 1
            local_units_created += 1
            note = "QUDT mapping unavailable; attached reviewed local unit placeholder derived from cleaned PEMFC evidence."
        else:
            decision = "review_unresolved_unit"
            note = "No safe QUDT assertion was available and local unit creation is disabled."

        review_rows.append(
            {
                "term_iri": term_iri,
                "term_label": _term_label(graph, term_ref),
                "decision": decision,
                "support_count": support_count,
                "consensus_ratio": round(consensus_ratio, 3),
                "quantity_kind_iri": quantity_kind_iri,
                "preferred_unit_label": preferred_unit.get("unit_label", ""),
                "preferred_qudt_unit_iri": preferred_unit_iri,
                "preferred_ucum_code": preferred_ucum_code,
                "local_unit_iri": local_unit_iri,
                "note": note,
            }
        )

    report = {
        "enabled": True,
        "applied": True,
        "source": "cleaned_evidence",
        "evidence_dir": str(resolved_dir),
        "curated_units_path": str(curated_units_path or ""),
        "terms_examined": len(evidence_by_term),
        "terms_enriched": terms_enriched,
        "qudt_units_linked": qudt_units_linked,
        "local_units_created": local_units_created,
        "review_rows": len(review_rows),
        "min_observations": min_observations,
        "min_consensus_ratio": min_ratio,
        "create_local_units": create_local_units,
    }
    alias_summary = _propagate_units_by_alias(
        schema_graph,
        controlled_vocabulary_graph,
        namespace_policy,
        review_rows,
    )
    report["alias_qudt_units_linked"] = alias_summary["alias_qudt_units_linked"]
    report["alias_local_units_linked"] = alias_summary["alias_local_units_linked"]
    report["terms_enriched"] += alias_summary["alias_qudt_units_linked"] + alias_summary["alias_local_units_linked"]
    report["qudt_units_linked"] += alias_summary["alias_qudt_units_linked"]
    report["local_units_created"] += alias_summary["alias_local_units_linked"]
    report["review_rows"] = len(review_rows)
    write_unit_enrichment_outputs(report, review_rows, root)
    return report


def write_unit_enrichment_outputs(report: dict[str, Any], review_rows: list[dict[str, Any]], root: Path) -> None:
    write_json(root / "output" / "reports" / "unit_enrichment_report.json", report)
    write_csv(
        root / "output" / "review" / "unit_evidence_review.csv",
        review_rows,
        [
            "term_iri",
            "term_label",
            "decision",
            "support_count",
            "consensus_ratio",
            "quantity_kind_iri",
            "preferred_unit_label",
            "preferred_qudt_unit_iri",
            "preferred_ucum_code",
            "local_unit_iri",
            "note",
        ],
    )
    lines = [
        "# Unit Enrichment Report",
        "",
        f"- Enabled: `{report.get('enabled', False)}`",
        f"- Applied: `{report.get('applied', False)}`",
        f"- Source: `{report.get('source', 'none')}`",
        f"- Evidence directory: `{report.get('evidence_dir', '')}`",
        f"- Curated units path: `{report.get('curated_units_path', '')}`",
        f"- Terms examined: **{report.get('terms_examined', 0)}**",
        f"- Terms enriched: **{report.get('terms_enriched', 0)}**",
        f"- QUDT units linked: **{report.get('qudt_units_linked', 0)}**",
        f"- Local reviewed units created: **{report.get('local_units_created', 0)}**",
        f"- Alias-propagated QUDT units: **{report.get('alias_qudt_units_linked', 0)}**",
        f"- Alias-propagated local reviewed units: **{report.get('alias_local_units_linked', 0)}**",
        f"- Review rows: **{report.get('review_rows', 0)}**",
        "",
    ]
    reason = report.get("reason")
    if reason:
        lines.extend(["## Status", "", reason, ""])
    else:
        lines.extend(
            [
                "## Policy",
                "",
                "- QUDT-backed units are asserted directly when cleaned PEMFC evidence is stable enough.",
                "- Curated local PEMFC units are retained when no reviewed QUDT mapping is available yet.",
                "- Exact ontology labels and alternative labels are checked conservatively to propagate units to duplicate or sibling terms.",
                "- Ambiguous multi-unit terms remain in the review CSV instead of being forced into the ontology.",
                "",
            ]
        )
    write_text(root / "output" / "reports" / "unit_enrichment_report.md", "\n".join(lines) + "\n")
