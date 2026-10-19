from __future__ import annotations

"""Reproducible evaluation artifacts for the H2KG/DECODE concept application."""

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from rdflib import Graph, URIRef

from .utils import dump_json, ensure_dir, load_json, write_text


H2KG = "https://w3id.org/h2kg/hydrogen-ontology#"
QUDT_NAMESPACES = {
    "schema": "http://qudt.org/schema/qudt/",
    "unit": "http://qudt.org/vocab/unit/",
    "quantity_kind": "http://qudt.org/vocab/quantitykind/",
}
ACTIVITY_ROLES = {"Process", "Measurement", "Manufacturing"}


def build_application_evaluation(
    output_root: str | Path,
    itc_registry_path: str | Path,
    candidate_cache_path: str | Path,
) -> dict[str, Any]:
    output_root = Path(output_root)
    required = [
        output_root / "decode" / "decode_federated_graph.json",
        output_root / "decode" / "decode_concept_registry.json",
        output_root / "ontology" / "taxonomy_registry.json",
        Path(itc_registry_path),
        Path(candidate_cache_path),
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        return {"status": "skipped_missing_inputs", "missing": missing}
    evaluation_dir = ensure_dir(output_root / "evaluation")
    graph = load_json(output_root / "decode" / "decode_federated_graph.json")
    concept_registry = load_json(output_root / "decode" / "decode_concept_registry.json")
    taxonomy_registry = load_json(output_root / "ontology" / "taxonomy_registry.json")
    itc_registry = load_json(Path(itc_registry_path))

    coverage_rows, coverage_summary = _coverage_rows(concept_registry)
    crosswalk_rows, crosswalk_summary = _itc_crosswalk(concept_registry, itc_registry)
    task_rows, result_rows, task_summary = _retrieval_evaluation(graph, itc_registry)
    benchmark_rows, benchmark_summary = _benchmark_diagnostic(
        output_root,
        Path(candidate_cache_path),
    )

    files = [
        _write_csv(evaluation_dir / "decode_public_coverage.csv", coverage_rows),
        dump_json(evaluation_dir / "decode_public_coverage.json", {"summary": coverage_summary, "rows": coverage_rows}),
        _write_csv(evaluation_dir / "itc_decode_population_crosswalk.csv", crosswalk_rows),
        dump_json(evaluation_dir / "itc_decode_population_crosswalk.json", {"summary": crosswalk_summary, "rows": crosswalk_rows}),
        _write_csv(evaluation_dir / "retrieval_tasks.csv", task_rows),
        _write_csv(evaluation_dir / "retrieval_results.csv", result_rows),
        dump_json(evaluation_dir / "retrieval_evaluation.json", {"summary": task_summary, "tasks": task_rows, "results": result_rows}),
        _write_csv(evaluation_dir / "tib_resource_diagnostic.csv", benchmark_rows),
        dump_json(evaluation_dir / "tib_resource_diagnostic.json", benchmark_summary),
    ]
    audit_workbook = _audit_workbook(
        evaluation_dir / "independent_semantic_audit_instrument.xlsx",
        concept_registry,
        graph,
        taxonomy_registry,
        itc_registry,
        output_root,
    )
    files.append(audit_workbook)
    comparison_workbook = _comparison_workbook(
        evaluation_dir / "hdo_edo_task_comparison_instrument.xlsx",
        task_rows,
    )
    files.append(comparison_workbook)

    summary = {
        "status": "passed",
        "schema_version": "h2kg-application-evaluation/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "coverage": coverage_summary,
        "itc_decode_crosswalk": crosswalk_summary,
        "retrieval": task_summary,
        "benchmark_diagnostic": benchmark_summary,
        "independent_semantic_audit_status": "awaiting_independent_review",
        "independent_judgments_completed": 0,
        "files": [str(path) for path in files],
    }
    files.append(dump_json(evaluation_dir / "evaluation_summary.json", summary))
    files.append(write_text(evaluation_dir / "README.md", _readme(summary)))
    return summary


def _coverage_rows(registry: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    reasons: Counter[str] = Counter()
    for concept in registry.get("concepts", []):
        state = str(concept.get("mapping_state", ""))
        if state == "approved_h2kg":
            reason = "public_h2kg_outcome"
        else:
            reason = _local_reason(concept)
        reasons[reason] += 1
        rows.append(
            {
                "concept_id": concept.get("concept_id", ""),
                "source_label": concept.get("source_label", ""),
                "native_category": concept.get("native_category", ""),
                "semantic_role": concept.get("semantic_role", ""),
                "mapping_state": state,
                "decision": concept.get("decision", ""),
                "anchor_iri": concept.get("anchor_iri", ""),
                "occurrence_count": concept.get("occurrence_count", 0),
                "workflow_count": len(concept.get("workflow_ids", [])),
                "coverage_reason": reason,
                "diagnostic_status": "automated_descriptive_category_not_promotion_decision",
            }
        )
    total = len(rows)
    public = sum(1 for row in rows if row["mapping_state"] == "approved_h2kg")
    summary = {
        "canonical_source_concepts": total,
        "public_h2kg_outcomes": public,
        "decode_local_outcomes": total - public,
        "public_h2kg_percent": round(100 * public / total, 2) if total else 0.0,
        "decode_local_percent": round(100 * (total - public) / total, 2) if total else 0.0,
        "reason_counts": dict(sorted(reasons.items())),
        "interpretation": (
            "Coverage is counted over canonical source concepts. DECODE-local does not mean scientifically invalid; "
            "it means no public H2KG identity is asserted in this release."
        ),
    }
    return rows, summary


def _local_reason(concept: dict[str, Any]) -> str:
    label = str(concept.get("source_label", "")).casefold()
    descriptions = " ".join(str(value) for value in concept.get("source_descriptions", [])).casefold()
    role = str(concept.get("semantic_role", ""))
    if not label.strip() or label.strip() in {"unknown", "not supplied", "n/a", "none"}:
        return "source_semantics_insufficient_for_public_identity"
    if role in ACTIVITY_ROLES and any(
        token in label for token in ("model", "workflow", "analysis", "prediction", "fitting", "calculation", "simulation")
    ):
        return "workflow_specific_activity"
    if any(token in label for token in ("aged", "corrected", "fitted", "predicted", "raw", "classified", "normalized")):
        return "contextualized_or_derived_concept"
    if not descriptions.strip() or descriptions.strip() == label.strip():
        return "source_semantics_insufficient_for_public_identity"
    return "domain_concept_without_asserted_public_h2kg_term"


def _itc_crosswalk(
    registry: dict[str, Any],
    itc: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_anchor: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for concept in registry.get("concepts", []):
        by_anchor[str(concept.get("anchor_iri", ""))].append(concept)
    rows: list[dict[str, Any]] = []
    overlap_occurrences = 0
    overlap_fields = 0
    for field in itc.get("fields", []):
        iri = H2KG + str(field["h2kg_local_name"])
        matches = by_anchor.get(iri, [])
        occurrences = sum(int(match.get("occurrence_count", 0)) for match in matches)
        overlap_occurrences += occurrences
        if matches:
            overlap_fields += 1
        rows.append(
            {
                "io_id": field["io_id"],
                "direction": field["direction"],
                "preferred_label": field["preferred_label"],
                "h2kg_iri": iri,
                "present_in_573_source_concepts": str(bool(matches)).lower(),
                "matching_source_concept_count": len(matches),
                "source_occurrence_count": occurrences,
                "concept_ids": " | ".join(str(match.get("concept_id", "")) for match in matches),
                "workflow_ids": " | ".join(
                    sorted({workflow for match in matches for workflow in match.get("workflow_ids", [])})
                ),
                "population_layer": "source_concept_registry" if matches else "itc_profile_overlay_only",
            }
        )
    summary = {
        "itc_field_count": len(rows),
        "fields_overlapping_source_concept_registry": overlap_fields,
        "profile_overlay_only_fields": len(rows) - overlap_fields,
        "source_occurrences_covered_by_overlapping_fields": overlap_occurrences,
        "denominator_note": (
            "The 573 denominator contains canonical concepts derived from source workflow occurrences. "
            "The 44 ITC fields are a public profile vocabulary; fields absent from source occurrences are not members of that denominator."
        ),
    }
    return rows, summary


def _retrieval_evaluation(
    graph: dict[str, Any],
    itc: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    workflows = {str(row["id"]): row for row in graph.get("workflows", [])}
    nodes = {str(row["id"]): row for row in graph.get("nodes", [])}
    source_edges = list(graph.get("source_edges", []))
    target_to_edges: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in source_edges:
        target_to_edges[str(edge.get("target", ""))].append(edge)

    fields = list(itc.get("fields", []))
    field_by_anchor = {H2KG + str(field["h2kg_local_name"]): field for field in fields}
    accepted_outputs: list[dict[str, Any]] = []
    baseline_outputs: list[dict[str, Any]] = []
    for node in nodes.values():
        if node.get("workflow_id") == "iet-multiscale-model-interface":
            continue
        anchor = str(node.get("anchor_id", ""))
        field = field_by_anchor.get(anchor)
        if not field:
            continue
        producing_edges = [
            edge
            for edge in target_to_edges.get(str(node["id"]), [])
            if str(nodes.get(str(edge.get("source", "")), {}).get("semantic_role", "")) in ACTIVITY_ROLES
        ]
        if not producing_edges:
            continue
        accepted_outputs.append({"node": node, "field": field, "edges": producing_edges})
        accepted_labels = {
            _norm(field["preferred_label"]),
            _norm(field["source_label"]),
            *(_norm(value) for value in field.get("alternate_labels", [])),
        }
        if _norm(node.get("label", "")) in accepted_labels:
            baseline_outputs.append({"node": node, "field": field, "edges": producing_edges})

    expected_ids = {str(item["node"]["id"]) for item in accepted_outputs}
    baseline_ids = {str(item["node"]["id"]) for item in baseline_outputs}
    results: list[dict[str, Any]] = []
    for item in sorted(accepted_outputs, key=lambda value: str(value["node"]["id"])):
        node = item["node"]
        workflow = workflows.get(str(node.get("workflow_id", "")), {})
        results.append(
            {
                "task_id": "RQ1",
                "system": "semantic_anchor_query",
                "result_id": node["id"],
                "result_label": node.get("label", ""),
                "workflow_id": node.get("workflow_id", ""),
                "workflow_title": workflow.get("title", ""),
                "expected_relevance": "relevant",
                "evidence": "Output occurrence shares a public ITC field anchor and has an explicit producing activity edge.",
            }
        )
    for item in sorted(baseline_outputs, key=lambda value: str(value["node"]["id"])):
        node = item["node"]
        results.append(
            {
                "task_id": "RQ1",
                "system": "exact_label_baseline",
                "result_id": node["id"],
                "result_label": node.get("label", ""),
                "workflow_id": node.get("workflow_id", ""),
                "workflow_title": workflows.get(str(node.get("workflow_id", "")), {}).get("title", ""),
                "expected_relevance": "relevant",
                "evidence": "Normalized source label exactly equals a curated ITC preferred, source, or alternate label.",
            }
        )

    distribution_anchors = {
        H2KG + "CCLRefinedPoreSizeDistributionData",
        H2KG + "PoreRadiusAxisData",
    }
    derived_nodes = [node for node in nodes.values() if node.get("workflow_id") == "iet-multiscale-model-interface"]
    semantic_distribution = [node for node in derived_nodes if node.get("anchor_id") in distribution_anchors]
    lexical_distribution = [
        node for node in derived_nodes
        if "pore" in _norm(node.get("label", "")) and any(token in _norm(node.get("label", "")) for token in ("radius", "size"))
    ]
    for system, candidates in (("semantic_role_and_anchor_query", semantic_distribution), ("label_token_baseline", lexical_distribution)):
        for node in sorted(candidates, key=lambda value: str(value["id"])):
            relevant = str(node.get("anchor_id", "")) in distribution_anchors
            results.append(
                {
                    "task_id": "RQ2",
                    "system": system,
                    "result_id": node["id"],
                    "result_label": node.get("label", ""),
                    "workflow_id": node.get("workflow_id", ""),
                    "workflow_title": workflows.get(str(node.get("workflow_id", "")), {}).get("title", ""),
                    "expected_relevance": "relevant" if relevant else "false_positive",
                    "evidence": "Curated value shape and intrinsic role distinguish array Data from scalar Property.",
                }
            )

    normalized_fields = [field for field in fields if field.get("normalization_basis") == "CarbonMass"]
    for field in normalized_fields:
        results.append(
            {
                "task_id": "RQ3",
                "system": "semantic_normalization_query",
                "result_id": field["io_id"],
                "result_label": field["preferred_label"],
                "workflow_id": "iet-multiscale-model-interface",
                "workflow_title": "IET multiscale model interface (PDF-derived schema)",
                "expected_relevance": "relevant",
                "evidence": "Registry and SHACL profile require normalizedTo a CarbonMass occurrence.",
            }
        )
        if "carbon" in _norm(field["preferred_label"]):
            results.append(
                {
                    "task_id": "RQ3",
                    "system": "label_only_baseline",
                    "result_id": field["io_id"],
                    "result_label": field["preferred_label"],
                    "workflow_id": "iet-multiscale-model-interface",
                    "workflow_title": "IET multiscale model interface (PDF-derived schema)",
                    "expected_relevance": "relevant",
                    "evidence": "The preferred label explicitly contains carbon.",
                }
            )

    accepted_variable = next(
        node for node in derived_nodes if node.get("source_id") == "IO_CMP_CCLWaterRetentionCurve"
    )
    itc_model = next(node for node in derived_nodes if node.get("source_id") == "itc")
    ctp_model = next(node for node in derived_nodes if node.get("source_id") == "ctp")
    accepted_edge_ids = [
        edge["id"]
        for edge in source_edges
        if (edge.get("source"), edge.get("target"))
        in {
            (itc_model["id"], accepted_variable["id"]),
            (accepted_variable["id"], ctp_model["id"]),
        }
    ]
    results.extend(
        [
            {
                "task_id": "RQ4",
                "system": "semantic_handoff_query",
                "result_id": "ITC--CCLWaterSaturationData--CTP",
                "result_label": "ITC to CTP through CCL water-saturation data",
                "workflow_id": "iet-multiscale-model-interface",
                "workflow_title": "IET multiscale model interface (PDF-derived schema)",
                "expected_relevance": "accepted_connection",
                "evidence": "Two explicit directed source edges: " + " | ".join(accepted_edge_ids),
            },
            {
                "task_id": "RQ4",
                "system": "semantic_handoff_query",
                "result_id": "rejected::mean-radius--pore-size-distribution",
                "result_label": "Geometric-mean pore radius is not a pore-size-distribution dataset",
                "workflow_id": "iet-multiscale-model-interface",
                "workflow_title": "IET multiscale model interface (PDF-derived schema)",
                "expected_relevance": "rejected_connection",
                "evidence": "Scalar Property and array Data have incompatible roles and value shapes despite shared pore/radius tokens.",
            },
        ]
    )

    tasks = [
        _task("RQ1", "Find source methods producing a quantity required by the ITC interface.", "Explicit output edge plus shared approved H2KG anchor.", "Exact normalized label."),
        _task("RQ2", "Retrieve pore-radius distribution data without returning scalar mean-radius properties.", "Approved Data anchor and array value shape.", "Pore/radius label tokens."),
        _task("RQ3", "Retrieve ITC quantities normalized to carbon mass rather than catalyst mass.", "normalizedTo CarbonMass in the profile registry and SHACL.", "Preferred label contains carbon."),
        _task("RQ4", "Traverse one accepted ITC-to-CTP handoff and reject one lexical false link.", "Explicit directed source edges plus compatible anchor role and value shape.", "Shared words only."),
    ]
    summary = {
        "task_count": len(tasks),
        "result_row_count": len(results),
        "rq1_semantic_result_count": len(expected_ids),
        "rq1_exact_label_result_count": len(baseline_ids),
        "rq1_semantic_only_result_count": len(expected_ids - baseline_ids),
        "rq2_semantic_result_count": len(semantic_distribution),
        "rq2_label_baseline_result_count": len(lexical_distribution),
        "rq2_label_false_positive_count": sum(
            1 for node in lexical_distribution if node.get("anchor_id") not in distribution_anchors
        ),
        "rq3_carbon_normalized_field_count": len(normalized_fields),
        "evaluation_status": "registry_derived_expected_sets_complete; independent_relevance_assessment_pending",
        "independent_precision_recall_claimed": False,
    }
    return tasks, results, summary


def _task(task_id: str, question: str, criterion: str, baseline: str) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "question": question,
        "registry_derived_relevance_criterion": criterion,
        "baseline": baseline,
        "independent_review_status": "pending",
    }


def _benchmark_diagnostic(output_root: Path, cache_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ontology_rows = _read_csv(output_root / "benchmarks" / "tib_collections" / "ontology_benchmark.csv")
    selected = [
        row for row in ontology_rows
        if str(row.get("ontology_id", "")).casefold() in {
            "battinfo", "qudt", "quantitykind", "unit", "qudtdatatypeschema", "datatype", "prefix", "qkdv", "constant", "soqk", "sou"
        }
    ]
    rows: list[dict[str, Any]] = []
    for row in selected:
        ontology_id = str(row.get("ontology_id", ""))
        family = "BattINFO" if ontology_id.casefold() == "battinfo" else "QUDT"
        interpretation = (
            "Domain-class lexical/hierarchy correspondence; imported EMMO content must not be treated as native BattINFO coverage."
            if family == "BattINFO"
            else "Class-overlap percentage is not a reuse metric because H2KG normally references QUDT quantity kinds and units as external resources."
        )
        rows.append({**row, "diagnostic_family": family, "interpretation": interpretation})

    complete_path = output_root / "ontology" / "h2kg-v2-complete.ttl"
    graph = Graph().parse(complete_path, format="turtle") if complete_path.exists() else Graph()
    qudt_references: dict[str, set[str]] = {key: set() for key in QUDT_NAMESPACES}
    for triple in graph:
        for term in triple:
            if not isinstance(term, URIRef):
                continue
            value = str(term)
            for key, namespace in QUDT_NAMESPACES.items():
                if value.startswith(namespace):
                    qudt_references[key].add(value)

    cache = load_json(cache_path)
    battinfo_candidates = [
        row for row in cache.get("candidates", []) if str(row.get("ontology_id", "")).casefold() == "battinfo"
    ]
    imported = sum(1 for row in battinfo_candidates if row.get("imported"))
    defining = sum(1 for row in battinfo_candidates if row.get("is_defining_ontology"))
    summary = {
        "qudt": {
            "class_overlap_interpretation": "not_a_reuse_metric",
            "complete_distribution_reference_counts": {key: len(values) for key, values in qudt_references.items()},
            "complete_distribution_unique_qudt_iris": len(set().union(*qudt_references.values())),
        },
        "battinfo": {
            "cached_candidate_count": len(battinfo_candidates),
            "cached_imported_candidate_count": imported,
            "cached_defining_ontology_candidate_count": defining,
            "native_source_rdf_in_frozen_package": False,
            "diagnostic_status": "candidate_provenance_diagnosed; native_BattINFO_RDF_hierarchy_comparison_pending",
        },
        "focused_hdo_edo_comparison": {
            "status": "instrument_generated; execution_and_independent_assessment_pending",
            "reason": "Neither comparator is a native row in the frozen three-collection snapshot, so collection percentages cannot substitute for task-based comparison.",
        },
    }
    return rows, summary


def _audit_workbook(
    path: Path,
    concepts: dict[str, Any],
    graph: dict[str, Any],
    taxonomy: dict[str, Any],
    itc: dict[str, Any],
    output_root: Path,
) -> Path:
    workbook = Workbook()
    status = workbook.active
    status.title = "Audit status"
    _append_rows(
        status,
        [
            {
                "status": "awaiting_independent_review",
                "completed_judgments": 0,
                "required_reviewer_independence": "Reviewer must not be an author of the mapping or taxonomy decisions under assessment.",
                "allowed_verdicts": "accept | reject | unresolved",
                "adjudication_rule": "Two independent judgments; disagreements adjudicated by a third named assessor.",
            }
        ],
    )
    instructions = workbook.create_sheet("Instructions")
    _append_rows(
        instructions,
        [
            {"step": 1, "instruction": "Assess scientific identity and relation direction from the supplied evidence, not lexical similarity alone."},
            {"step": 2, "instruction": "Enter reviewer_id, verdict, rationale, and correction proposal without changing protected source identifiers."},
            {"step": 3, "instruction": "Record unresolved when source evidence is insufficient; do not force a public H2KG mapping."},
            {"step": 4, "instruction": "Do not interpret an empty reviewer column as acceptance."},
        ],
    )

    itc_rows = []
    for field in itc.get("fields", []):
        itc_rows.append(
            {
                "io_id": field["io_id"],
                "direction": field["direction"],
                "preferred_label": field["preferred_label"],
                "source_label": field["source_label"],
                "definition": field["definition"],
                "role": field["semantic_role"],
                "unit": field["reported_unit"],
                "page": field["page"],
                "h2kg_iri": H2KG + field["h2kg_local_name"],
                "source_sha256": itc["source"]["sha256"],
                **_blank_review_columns(),
            }
        )
    _append_rows(workbook.create_sheet("ITC 44 fields"), itc_rows)

    public_concepts = [row for row in concepts.get("concepts", []) if row.get("mapping_state") == "approved_h2kg"]
    local_concepts = [row for row in concepts.get("concepts", []) if row.get("mapping_state") != "approved_h2kg"]
    sampled_local = _stratified_sample(local_concepts, "semantic_role", 120)
    concept_rows = []
    for concept in [*public_concepts, *sampled_local]:
        concept_rows.append(
            {
                "sample_stratum": "all_public" if concept.get("mapping_state") == "approved_h2kg" else "stratified_local",
                "concept_id": concept.get("concept_id", ""),
                "label": concept.get("source_label", ""),
                "native_category": concept.get("native_category", ""),
                "semantic_role": concept.get("semantic_role", ""),
                "mapping_state": concept.get("mapping_state", ""),
                "anchor_iri": concept.get("anchor_iri", ""),
                "rationale": concept.get("rationale", ""),
                "neighbor_context": " | ".join(concept.get("neighbor_context", [])),
                **_blank_review_columns(),
            }
        )
    _append_rows(workbook.create_sheet("DECODE concept sample"), concept_rows)

    edge_rows = []
    by_outcome: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in graph.get("edge_registry", []):
        by_outcome[str(edge.get("projection_outcome", ""))].append(edge)
    edge_limits = {"h2kg_direct": 50, "h2kg_reified": 50, "prov_derivation": 23, "decode_structural_only": 50}
    for outcome, limit in edge_limits.items():
        for edge in _stable_sample(by_outcome.get(outcome, []), limit):
            edge_rows.append(
                {
                    "projection_outcome": outcome,
                    "source_dependency_id": edge.get("source_dependency_id", ""),
                    "workflow_id": edge.get("workflow_id", ""),
                    "source_label": edge.get("source_label", ""),
                    "target_label": edge.get("target_label", ""),
                    "source_role": edge.get("source_semantic_role", ""),
                    "target_role": edge.get("target_semantic_role", ""),
                    "semantic_predicates": edge.get("semantic_predicates", ""),
                    "semantic_direction": edge.get("semantic_direction", ""),
                    "rationale": edge.get("rationale", ""),
                    **_blank_review_columns(),
                }
            )
    _append_rows(workbook.create_sheet("DECODE edge sample"), edge_rows)

    term_rows = []
    active_terms = [row for row in taxonomy.get("terms", []) if row.get("disposition") == "active_local_class"]
    for term in _stratified_sample(active_terms, "top_branch", 150):
        term_rows.append(
            {
                "iri": term.get("iri", ""),
                "label": term.get("label", ""),
                "definition": term.get("definition", ""),
                "parent_iri": term.get("parent_iri", ""),
                "top_branch": term.get("top_branch", ""),
                "correction_action": term.get("correction_action", ""),
                "rationale": term.get("rationale", ""),
                **_blank_review_columns(),
            }
        )
    _append_rows(workbook.create_sheet("H2KG term sample"), term_rows)

    alignment_path = output_root / "ontology" / "external_alignment_registry.json"
    mappings = load_json(alignment_path).get("mappings", []) if alignment_path.exists() else []
    mapping_rows = []
    for mapping in mappings:
        mapping_rows.append(
            {
                "local_iri": mapping.get("local_iri", ""),
                "local_label": mapping.get("local_label", ""),
                "relation": mapping.get("relation", ""),
                "target_iri": mapping.get("target_iri", ""),
                "target_label": mapping.get("target_label", ""),
                "ontology": mapping.get("tib_ontology_id", ""),
                "confidence": mapping.get("confidence", ""),
                "rationale": mapping.get("rationale", ""),
                **_blank_review_columns(),
            }
        )
    _append_rows(workbook.create_sheet("External mappings"), mapping_rows)
    _format_workbook(workbook)
    ensure_dir(path.parent)
    workbook.save(path)
    return path


def _comparison_workbook(path: Path, tasks: list[dict[str, Any]]) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Task comparison"
    rows = []
    for task in tasks:
        for resource in ("H2KG 2.2", "HDO", "EMMO Electrochemistry Domain Ontology"):
            rows.append(
                {
                    "task_id": task["task_id"],
                    "task": task["question"],
                    "resource": resource,
                    "representation_present": "" if resource != "H2KG 2.2" else "see retrieval_results.csv",
                    "retrieved_identifiers": "",
                    "missing_representation": "",
                    "assessor_id": "",
                    "assessment": "pending",
                    "rationale": "",
                }
            )
    _append_rows(sheet, rows)
    note = workbook.create_sheet("Status")
    _append_rows(
        note,
        [{"status": "pending", "note": "This instrument prevents collection-level percentages from being used as a substitute for task-based HDO/EDO comparison."}],
    )
    _format_workbook(workbook)
    ensure_dir(path.parent)
    workbook.save(path)
    return path


def _blank_review_columns() -> dict[str, str]:
    return {
        "reviewer_id": "",
        "reviewer_verdict": "",
        "reviewer_rationale": "",
        "suggested_correction": "",
        "adjudication_status": "pending",
    }


def _stratified_sample(rows: list[dict[str, Any]], key: str, total: int) -> list[dict[str, Any]]:
    groups: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(key, "unspecified"))].append(row)
    if not groups or total <= 0:
        return []
    result: list[dict[str, Any]] = []
    remaining = total
    ordered_keys = sorted(groups)
    for index, group_key in enumerate(ordered_keys):
        groups_left = len(ordered_keys) - index
        allocation = min(len(groups[group_key]), max(1, remaining // groups_left))
        sampled = _stable_sample(groups[group_key], allocation)
        result.extend(sampled)
        remaining -= len(sampled)
    if remaining > 0:
        selected = {_stable_id(row) for row in result}
        rest = [row for row in rows if _stable_id(row) not in selected]
        result.extend(_stable_sample(rest, remaining))
    return result[:total]


def _stable_sample(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: hashlib.sha256(_stable_id(row).encode("utf-8")).hexdigest())[:limit]


def _stable_id(row: dict[str, Any]) -> str:
    for key in ("iri", "concept_id", "source_dependency_id", "id", "io_id", "local_iri"):
        if row.get(key):
            return str(row[key])
    return json.dumps(row, sort_keys=True, ensure_ascii=False)


def _append_rows(sheet: Any, rows: list[dict[str, Any]]) -> None:
    if not rows:
        sheet.append(["status"])
        sheet.append(["no rows"])
        return
    headers = list(rows[0])
    sheet.append(headers)
    for row in rows:
        sheet.append([_cell(row.get(header, "")) for header in headers])


def _format_workbook(workbook: Workbook) -> None:
    fill = PatternFill("solid", fgColor="17324D")
    for sheet in workbook.worksheets:
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]:
            cell.font = Font(color="FFFFFF", bold=True)
            cell.fill = fill
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        for column in range(1, min(sheet.max_column, 30) + 1):
            values = [str(sheet.cell(row=row, column=column).value or "") for row in range(1, min(sheet.max_row, 100) + 1)]
            sheet.column_dimensions[get_column_letter(column)].width = min(55, max(12, max(map(len, values), default=12) + 2))
        for row in sheet.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = Alignment(wrap_text=True, vertical="top")


def _cell(value: Any) -> Any:
    if isinstance(value, (list, tuple, set)):
        return " | ".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> Path:
    ensure_dir(path.parent)
    fields = list(rows[0]) if rows else ["status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _cell(value) for key, value in row.items()})
    return path


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _norm(value: Any) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(value).casefold()).split())


def _readme(summary: dict[str, Any]) -> str:
    coverage = summary["coverage"]
    crosswalk = summary["itc_decode_crosswalk"]
    retrieval = summary["retrieval"]
    return f"""# H2KG application evaluation package

This package separates reproducible machine checks from independent scientific assessment.

## Completed reproducible checks

- DECODE concepts: {coverage['public_h2kg_outcomes']} public H2KG outcomes and {coverage['decode_local_outcomes']} DECODE-local outcomes out of {coverage['canonical_source_concepts']} canonical source concepts.
- ITC overlap: {crosswalk['fields_overlapping_source_concept_registry']} of 44 ITC fields occur in the 573-concept source registry; {crosswalk['profile_overlay_only_fields']} are profile-overlay-only fields.
- Retrieval: {retrieval['task_count']} named tasks with registry-derived expected sets and a label-only baseline.
- QUDT and BattINFO are diagnosed separately from collection-level percentages.

## Not yet completed

Independent scientific assessment is **pending**. The workbooks contain blank reviewer and adjudication columns by design. Empty cells must never be interpreted as acceptance, and this package does not report precision, recall, or inter-rater agreement before independent judgments exist.
"""
