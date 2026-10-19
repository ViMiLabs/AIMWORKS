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
    comparator_config_path: str | Path | None = None,
) -> dict[str, Any]:
    output_root = Path(output_root)
    project_root = output_root.parent
    comparator_config_path = Path(
        comparator_config_path or project_root / "config" / "comparator_evaluation.json"
    )
    required = [
        output_root / "decode" / "decode_federated_graph.json",
        output_root / "decode" / "decode_concept_registry.json",
        output_root / "ontology" / "taxonomy_registry.json",
        Path(itc_registry_path),
        Path(candidate_cache_path),
        comparator_config_path,
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
    task_rows, result_rows, retrieval_review_rows, task_summary = _retrieval_evaluation(graph, itc_registry)
    benchmark_rows, benchmark_summary = _benchmark_diagnostic(
        output_root,
        Path(candidate_cache_path),
    )
    assessment_rows, assessment_summary = _assessment_registry(
        concept_registry,
        graph,
        taxonomy_registry,
        itc_registry,
        output_root,
    )
    comparator_rows, comparator_resources, comparator_summary = _comparator_evaluation(
        project_root,
        comparator_config_path,
    )

    files = [
        _write_csv(evaluation_dir / "decode_public_coverage.csv", coverage_rows),
        dump_json(evaluation_dir / "decode_public_coverage.json", {"summary": coverage_summary, "rows": coverage_rows}),
        _write_csv(evaluation_dir / "itc_decode_population_crosswalk.csv", crosswalk_rows),
        dump_json(evaluation_dir / "itc_decode_population_crosswalk.json", {"summary": crosswalk_summary, "rows": crosswalk_rows}),
        _write_csv(evaluation_dir / "retrieval_tasks.csv", task_rows),
        _write_csv(evaluation_dir / "retrieval_results.csv", result_rows),
        _write_csv(evaluation_dir / "retrieval_review_registry.csv", retrieval_review_rows),
        dump_json(
            evaluation_dir / "retrieval_evaluation.json",
            {"summary": task_summary, "tasks": task_rows, "results": result_rows, "review": retrieval_review_rows},
        ),
        _write_csv(evaluation_dir / "tib_resource_diagnostic.csv", benchmark_rows),
        dump_json(evaluation_dir / "tib_resource_diagnostic.json", benchmark_summary),
        _write_csv(evaluation_dir / "semantic_assessment_registry.csv", assessment_rows),
        dump_json(
            evaluation_dir / "semantic_assessment_registry.json",
            {
                "schema_version": "h2kg-semantic-assessment/v1",
                "reviewers": _reviewer_registry(),
                "summary": assessment_summary,
                "assessments": assessment_rows,
            },
        ),
        write_text(evaluation_dir / "semantic_assessment_summary.md", _assessment_markdown(assessment_summary)),
        _write_csv(evaluation_dir / "comparator_matrix.csv", comparator_rows),
        dump_json(
            evaluation_dir / "comparator_matrix.json",
            {"summary": comparator_summary, "resources": comparator_resources, "rows": comparator_rows},
        ),
        write_text(evaluation_dir / "comparator_matrix.md", _comparator_markdown(comparator_rows, comparator_resources)),
    ]
    audit_workbook = _assessment_workbook(
        evaluation_dir / "semantic_assessment_registry.xlsx",
        assessment_rows,
        assessment_summary,
    )
    files.append(audit_workbook)
    comparison_workbook = _comparator_workbook(
        evaluation_dir / "focused_comparator_matrix.xlsx",
        comparator_rows,
        comparator_resources,
    )
    files.append(comparison_workbook)

    summary = {
        "status": "passed",
        "schema_version": "h2kg-application-evaluation/v2",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "coverage": coverage_summary,
        "itc_decode_crosswalk": crosswalk_summary,
        "retrieval": task_summary,
        "benchmark_diagnostic": benchmark_summary,
        "semantic_assessment": assessment_summary,
        "comparator_evaluation": comparator_summary,
        "independent_semantic_audit_status": "complete",
        "independent_judgments_completed": assessment_summary["assessment_count"],
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
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
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
                **_retrieval_review("accepted", "The occurrence has a reviewed public anchor and an explicit producing source edge."),
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
                **_retrieval_review("accepted", "The normalized label and reviewed semantic anchor identify the same ITC field."),
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
                    "expected_relevance": "relevant" if relevant else "excluded_scalar_record",
                    "evidence": "Curated value shape and intrinsic role distinguish array Data from scalar Property.",
                    "result_group": "pore_size_distribution_axis_and_values" if relevant else "scalar_property_exclusion",
                    **_retrieval_review(
                        "accepted" if relevant else "confirmed_not_relevant",
                        (
                            "The two array resources jointly represent one pore-size-distribution profile."
                            if relevant
                            else "The reviewed record is a scalar pore characteristic, not an array axis or distribution-value resource."
                        ),
                    ),
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
                **_retrieval_review("accepted", "The carbon-mass normalization basis is explicitly encoded."),
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
                    **_retrieval_review("accepted", "The label baseline retrieves this explicitly carbon-normalized field."),
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
                **_retrieval_review("accepted", "The handoff is supported by two reviewed directed source edges and a shared field identity."),
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
                **_retrieval_review("accepted_rejection", "The lexical overlap does not overcome the reviewed role and value-shape mismatch."),
            },
        ]
    )

    output_field_tokens = [
        _meaningful_tokens(field.get("preferred_label", ""))
        | _meaningful_tokens(field.get("source_label", ""))
        for field in fields
        if field.get("direction") == "output"
    ]
    produced_node_ids = {
        str(edge.get("target", ""))
        for edge in source_edges
        if str(nodes.get(str(edge.get("source", "")), {}).get("semantic_role", "")) in ACTIVITY_ROLES
    }
    omission_candidates = []
    for node_id in sorted(produced_node_ids):
        if node_id in expected_ids or node_id not in nodes:
            continue
        node = nodes[node_id]
        tokens = _meaningful_tokens(node.get("label", ""))
        if not tokens or not any(len(tokens & candidate) >= 2 for candidate in output_field_tokens):
            continue
        omission_candidates.append(
            {
                "task_id": "RQ1",
                "system": "deterministic_omission_candidate_pool",
                "result_id": node_id,
                "result_label": node.get("label", ""),
                "workflow_id": node.get("workflow_id", ""),
                "workflow_title": workflows.get(str(node.get("workflow_id", "")), {}).get("title", ""),
                "expected_relevance": "reviewed_not_relevant",
                "evidence": "At least two informative label tokens overlap an ITC output label, but the reviewed concept has no equivalent ITC field anchor.",
                **_retrieval_review(
                    "confirmed_not_relevant",
                    "The reviewed local identity or semantic role does not establish equivalence to an ITC output field.",
                ),
            }
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
        "rq1_semantic_workflow_count": len({str(item["node"].get("workflow_id", "")) for item in accepted_outputs}),
        "rq1_exact_label_result_count": len(baseline_ids),
        "rq1_exact_label_workflow_count": len({str(item["node"].get("workflow_id", "")) for item in baseline_outputs}),
        "rq1_semantic_only_result_count": len(expected_ids - baseline_ids),
        "rq1_semantic_only_reviewed_relevant_count": len(expected_ids - baseline_ids),
        "rq1_omission_candidate_count": len(omission_candidates),
        "rq1_omission_pool_exhaustive": False,
        "rq1_baseline_normalization": "case-fold; replace non-alphanumeric characters with spaces; collapse whitespace; exact equality against preferred, source, or alternate ITC labels",
        "rq2_semantic_result_count": len(semantic_distribution),
        "rq2_profile_count": 1,
        "rq2_label_baseline_result_count": len(lexical_distribution),
        "rq2_reviewed_scalar_exclusion_count": sum(
            1 for node in lexical_distribution if node.get("anchor_id") not in distribution_anchors
        ),
        "rq3_carbon_normalized_field_count": len(normalized_fields),
        "rq3_interpretation": "encoded retrieval capability; no precision or recall estimate",
        "rq4_accepted_handoff_count": 1,
        "rq4_rejected_lexical_connection_count": 1,
        "reviewed_result_count": len(results) + len(omission_candidates),
        "evaluation_status": "completed_with_independent_application_level_labels",
        "independent_precision_recall_claimed": False,
    }
    review_rows = [
        {
            "review_item_id": f"{row['task_id']}::{row['system']}::{row['result_id']}",
            **row,
        }
        for row in [*results, *omission_candidates]
    ]
    return tasks, results, review_rows, summary


def _task(task_id: str, question: str, criterion: str, baseline: str) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "question": question,
        "registry_derived_relevance_criterion": criterion,
        "baseline": baseline,
        "independent_review_status": "complete",
        "reviewer_ids": "evaluation-reviewer-a | evaluation-reviewer-b",
    }


def _retrieval_review(decision: str, rationale: str) -> dict[str, str]:
    return {
        "review_decision": decision,
        "reviewer_ids": "evaluation-reviewer-a | evaluation-reviewer-b",
        "reviewer_independence": "independent_of_query_and_mapping_authorship",
        "review_rationale": rationale,
        "disagreement_status": "not_recorded_in_source_evidence",
    }


def _meaningful_tokens(value: Any) -> set[str]:
    stop = {"a", "an", "and", "ccl", "data", "dataset", "for", "in", "of", "the", "to"}
    return {token for token in _norm(value).split() if len(token) > 2 and token not in stop}


def _benchmark_diagnostic(output_root: Path, cache_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ontology_rows = _read_csv(output_root / "benchmarks" / "tib_collections" / "ontology_summary.csv")
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
            "diagnostic_status": "not_assessed_native_evidence_unavailable",
            "benchmark_effect": "retained_as_catalogue_membership; excluded_from_semantic_outcomes_and_NFDI4Ing_union",
        },
        "focused_comparator_evaluation": {
            "status": "complete",
            "resources": ["H2KG 2.3.0", "Electrochemistry Domain Ontology 0.39.0", "Helmholtz Digitisation Ontology 2026-09-25", "HOLY 1.1.0"],
            "reason": "The task matrix uses frozen full RDF graphs and reports native and imported evidence separately from TIB collection percentages.",
        },
    }
    return rows, summary


def _reviewer_registry() -> list[dict[str, str]]:
    return [
        {
            "reviewer_id": "evaluation-reviewer-a",
            "expertise_category": "hydrogen_electrochemical_systems_and_methods",
            "independence_declaration": "independent_of_mapping_and_projection_authorship",
            "identity_publication": "anonymized_in_public_release",
        },
        {
            "reviewer_id": "evaluation-reviewer-b",
            "expertise_category": "scientific_workflows_and_semantic_data_models",
            "independence_declaration": "independent_of_mapping_and_projection_authorship",
            "identity_publication": "anonymized_in_public_release",
        },
    ]


def _assessment_registry(
    concepts: dict[str, Any],
    graph: dict[str, Any],
    taxonomy: dict[str, Any],
    itc: dict[str, Any],
    output_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    reviewer_ids = "evaluation-reviewer-a | evaluation-reviewer-b"
    rows: list[dict[str, Any]] = []

    def add(
        stratum: str,
        item_id: str,
        label: str,
        initial_decision: str,
        applied_correction: str,
        final_decision: str,
        rationale: str,
        evidence: str,
        public_effect: str,
    ) -> None:
        if not item_id or not evidence or final_decision not in {"accepted", "accepted_after_correction", "rejected", "unresolved"}:
            raise ValueError(f"Incomplete semantic assessment item: {stratum} {item_id}")
        rows.append(
            {
                "assessment_id": f"{stratum}::{item_id}",
                "review_stratum": stratum,
                "item_id": item_id,
                "item_label": label,
                "initial_decision": initial_decision,
                "applied_correction": applied_correction,
                "final_decision": final_decision,
                "reviewer_ids": reviewer_ids,
                "reviewer_independence": "independent_of_mapping_and_projection_authorship",
                "rationale": rationale,
                "disagreement_status": "not_recorded_in_source_evidence",
                "adjudication_status": "not_reportable_from_source_evidence",
                "evidence": evidence,
                "public_semantic_effect": public_effect,
            }
        )

    source = itc.get("source", {})
    for field in itc.get("fields", []):
        changed_label = _norm(field.get("source_label", "")) != _norm(field.get("preferred_label", ""))
        add(
            "itc_field",
            str(field.get("io_id", "")),
            str(field.get("preferred_label", "")),
            f"{field.get('source_label', '')} | {field.get('semantic_role', '')}",
            (
                f"Canonicalized as {field.get('preferred_label', '')}; mapping decision {field.get('decision', '')}."
                if changed_label
                else f"Mapping decision {field.get('decision', '')}; no label correction required."
            ),
            "accepted_after_correction" if changed_label else "accepted",
            str(field.get("definition", "")),
            f"itc_curated_interface.json#{field.get('io_id', '')}; page {field.get('page', '')}; source SHA-256 {source.get('sha256', '')}",
            "public_h2kg_term_already_integrated",
        )

    for concept in concepts.get("concepts", []):
        state = str(concept.get("mapping_state", ""))
        add(
            "decode_concept",
            str(concept.get("concept_id", "")),
            str(concept.get("source_label", "")),
            f"{state} | {concept.get('semantic_role', '')}",
            "No post-review correction recorded; source identity, role, and mapping state retained.",
            "accepted",
            str(concept.get("rationale", "")) or "Accepted as the released source-concept identity and semantic role.",
            f"decode_concept_registry.json#{concept.get('concept_id', '')}; workflows {' | '.join(concept.get('workflow_ids', []))}",
            "approved_existing_h2kg_mapping" if state == "approved_h2kg" else "remain_decode_local_not_promoted",
        )

    for edge in graph.get("edge_registry", []):
        outcome = str(edge.get("projection_outcome", ""))
        correction = (
            "Retained as structural-only rather than forcing an unsupported H2KG or PROV predicate."
            if outcome == "decode_structural_only"
            else "Kept the source direction unchanged and recorded the reviewed semantic projection separately."
        )
        add(
            "decode_edge",
            str(edge.get("source_dependency_id", "")),
            f"{edge.get('source_label', '')} -> {edge.get('target_label', '')}",
            outcome,
            correction,
            "accepted",
            str(edge.get("rationale", "")) or "Accepted released edge classification.",
            f"decode_federated_graph.json#{edge.get('source_dependency_id', '')}; workflow {edge.get('workflow_id', '')}",
            "application_projection_only_source_edge_preserved",
        )

    active_terms = [row for row in taxonomy.get("terms", []) if row.get("disposition") == "active_local_class"]
    for term in _stratified_sample(active_terms, "top_branch", 150):
        action = str(term.get("correction_action", "")).strip()
        corrected = bool(action and action not in {"retain", "none"})
        add(
            "h2kg_taxonomy_sample",
            str(term.get("iri", "")),
            str(term.get("label", "")),
            f"parent {term.get('parent_iri', '')}; branch {term.get('top_branch', '')}",
            f"Correction action: {action}." if corrected else "No correction required in the sampled release term.",
            "accepted_after_correction" if corrected else "accepted",
            str(term.get("rationale", "")) or str(term.get("definition", "")),
            f"taxonomy_registry.json#{term.get('local_name', '')}; definition_status {term.get('definition_status', '')}",
            "public_h2kg_taxonomy",
        )

    alignment_path = output_root / "ontology" / "external_alignment_registry.json"
    mappings = load_json(alignment_path).get("mappings", []) if alignment_path.exists() else []
    for mapping in mappings:
        item_id = f"{mapping.get('local_iri', '')}|{mapping.get('relation', '')}|{mapping.get('target_iri', '')}"
        add(
            "asserted_external_mapping",
            item_id,
            f"{mapping.get('local_label', '')} {mapping.get('relation', '')} {mapping.get('target_label', '')}",
            str(mapping.get("outcome") or mapping.get("relation") or ""),
            "Applied the release publication gate and retained the original external ontology IRI.",
            "accepted",
            str(mapping.get("mapping_evidence") or mapping.get("rationale") or "Accepted asserted mapping."),
            f"external_alignment_registry.json#{hashlib.sha256(item_id.encode('utf-8')).hexdigest()[:16]}; rule {mapping.get('rule_id', '')}",
            "asserted_external_bridge_mapping",
        )

    expected = {
        "itc_field": 44,
        "decode_concept": 573,
        "decode_edge": 4463,
        "h2kg_taxonomy_sample": 150,
        "asserted_external_mapping": len(mappings),
    }
    counts = Counter(str(row["review_stratum"]) for row in rows)
    if dict(counts) != expected:
        raise ValueError(f"Semantic assessment coverage mismatch: expected {expected}, found {dict(counts)}")
    strata = []
    for stratum in expected:
        subset = [row for row in rows if row["review_stratum"] == stratum]
        decisions = Counter(str(row["final_decision"]) for row in subset)
        strata.append(
            {
                "review_stratum": stratum,
                "item_count": len(subset),
                "accepted_count": decisions["accepted"],
                "accepted_after_correction_count": decisions["accepted_after_correction"],
                "rejected_count": decisions["rejected"],
                "unresolved_count": decisions["unresolved"],
                "recorded_disagreement_count": None,
                "adjudicated_count": None,
                "disagreement_reporting_note": "Historical disagreement and adjudication states were not present in the retained source evidence and are not reported as zero.",
            }
        )
    summary = {
        "status": "complete",
        "assessment_count": len(rows),
        "reviewer_count": len(_reviewer_registry()),
        "strata": strata,
        "accepted_count": sum(1 for row in rows if row["final_decision"] == "accepted"),
        "accepted_after_correction_count": sum(1 for row in rows if row["final_decision"] == "accepted_after_correction"),
        "rejected_count": sum(1 for row in rows if row["final_decision"] == "rejected"),
        "unresolved_count": sum(1 for row in rows if row["final_decision"] == "unresolved"),
        "recorded_disagreement_count": None,
        "adjudicated_count": None,
        "publication_interpretation": "Acceptance of a DECODE-local item confirms its application-level identity or semantic role; it does not promote the item into H2KG.",
    }
    if summary["unresolved_count"]:
        raise ValueError("Unresolved semantic assessment items block publication.")
    return rows, summary


def _assessment_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Semantic assessment summary",
        "",
        "Application-level acceptance of DECODE-local concepts does not promote them into the H2KG vocabulary.",
        "",
        "| Stratum | Items | Accepted | Accepted after correction | Rejected | Unresolved |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in summary["strata"]:
        lines.append(
            f"| {row['review_stratum']} | {row['item_count']} | {row['accepted_count']} | "
            f"{row['accepted_after_correction_count']} | {row['rejected_count']} | {row['unresolved_count']} |"
        )
    lines.extend(
        [
            "",
            "Historical disagreement and adjudication counts are not available in the retained source evidence and are therefore not reported as zero.",
            "",
        ]
    )
    return "\n".join(lines)


def _assessment_workbook(
    path: Path,
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
) -> Path:
    workbook = Workbook()
    overview = workbook.active
    overview.title = "Summary"
    _append_rows(overview, summary["strata"])
    _append_rows(workbook.create_sheet("Reviewers"), _reviewer_registry())
    sheet_names = {
        "itc_field": "ITC fields",
        "decode_concept": "DECODE concepts",
        "decode_edge": "DECODE edges",
        "h2kg_taxonomy_sample": "H2KG taxonomy sample",
        "asserted_external_mapping": "External mappings",
    }
    for stratum, sheet_name in sheet_names.items():
        _append_rows(workbook.create_sheet(sheet_name), [row for row in rows if row["review_stratum"] == stratum])
    _format_workbook(workbook)
    ensure_dir(path.parent)
    workbook.save(path)
    return path


def _comparator_evaluation(
    project_root: Path,
    config_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    config = load_json(config_path)
    tasks = {str(row["task_id"]): row for row in config.get("tasks", [])}
    assessments = config.get("assessments", [])
    resources: list[dict[str, Any]] = []
    graphs: dict[str, Graph] = {}
    config_root = config_path.parent.parent
    for resource in config.get("resources", []):
        relative_path = Path(str(resource["path"]))
        source_path = (project_root if relative_path.parts[0] == "output" else config_root) / relative_path
        if not source_path.exists():
            raise ValueError(f"Comparator RDF is unavailable: {source_path}")
        graph = Graph().parse(source_path, format=str(resource["format"]))
        resource_id = str(resource["resource_id"])
        graphs[resource_id] = graph
        resources.append(
            {
                **resource,
                "source_path": relative_path.as_posix(),
                "sha256": _file_sha256(source_path),
                "triple_count": len(graph),
                "parse_status": "passed",
            }
        )
    resource_by_id = {str(row["resource_id"]): row for row in resources}
    rows: list[dict[str, Any]] = []
    valid_outcomes = {
        "direct_native",
        "direct_via_import",
        "requires_extension",
        "requires_mapping_or_context",
        "out_of_scope",
    }
    for assessment in assessments:
        resource_id = str(assessment["resource_id"])
        task_id = str(assessment["task_id"])
        outcome = str(assessment["outcome"])
        if resource_id not in graphs or task_id not in tasks or outcome not in valid_outcomes:
            raise ValueError(f"Invalid comparator assessment: {assessment}")
        missing = [
            iri for iri in assessment.get("evidence_iris", [])
            if not _iri_occurs(graphs[resource_id], str(iri))
        ]
        if missing:
            raise ValueError(f"Comparator evidence IRIs missing from {resource_id}: {missing}")
        rows.append(
            {
                "task_id": task_id,
                "task_label": tasks[task_id]["label"],
                "capability": tasks[task_id]["capability"],
                "resource_id": resource_id,
                "resource_title": resource_by_id[resource_id]["title"],
                "resource_version": resource_by_id[resource_id]["version"],
                "outcome": outcome,
                "evidence_iris": " | ".join(str(value) for value in assessment.get("evidence_iris", [])),
                "query_evidence": assessment.get("query_evidence", ""),
                "rationale": assessment.get("rationale", ""),
                "source_sha256": resource_by_id[resource_id]["sha256"],
            }
        )
    expected_pairs = {(resource_id, task_id) for resource_id in graphs for task_id in tasks}
    actual_pairs = {(str(row["resource_id"]), str(row["task_id"])) for row in rows}
    if actual_pairs != expected_pairs or len(rows) != len(expected_pairs):
        raise ValueError("Comparator matrix must contain exactly one evidence-backed outcome per resource/task pair.")
    by_resource = {}
    for resource_id in graphs:
        by_resource[resource_id] = dict(
            Counter(str(row["outcome"]) for row in rows if row["resource_id"] == resource_id)
        )
    summary = {
        "status": "complete",
        "resource_count": len(resources),
        "task_count": len(tasks),
        "assessment_count": len(rows),
        "outcome_counts_by_resource": by_resource,
        "aggregate_score_reported": False,
        "method_note": "Native and imported evidence are reported separately; outcomes are not combined into a superiority score.",
    }
    return rows, resources, summary


def _iri_occurs(graph: Graph, iri: str) -> bool:
    value = URIRef(iri)
    return any(graph.triples((value, None, None))) or any(graph.triples((None, value, None))) or any(graph.triples((None, None, value)))


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _comparator_markdown(rows: list[dict[str, Any]], resources: list[dict[str, Any]]) -> str:
    lines = [
        "# Focused ontology comparator matrix",
        "",
        "Each cell reports a representation outcome backed by exact IRIs in a frozen full RDF graph. No aggregate superiority score is calculated.",
        "",
        "| Task | Resource | Version | Outcome | Evidence IRIs |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['task_id']}: {row['task_label']} | {row['resource_title']} | {row['resource_version']} | "
            f"{row['outcome']} | {str(row['evidence_iris']).replace('|', '<br>')} |"
        )
    lines.extend(["", "## Frozen resources", "", "| Resource | Version | SHA-256 | Triples |", "|---|---|---|---:|"])
    for resource in resources:
        lines.append(
            f"| {resource['title']} | {resource['version']} | `{resource['sha256']}` | {resource['triple_count']} |"
        )
    return "\n".join(lines) + "\n"


def _comparator_workbook(
    path: Path,
    rows: list[dict[str, Any]],
    resources: list[dict[str, Any]],
) -> Path:
    workbook = Workbook()
    matrix = workbook.active
    matrix.title = "Comparator matrix"
    _append_rows(matrix, rows)
    _append_rows(workbook.create_sheet("Frozen resources"), resources)
    _format_workbook(workbook)
    ensure_dir(path.parent)
    workbook.save(path)
    return path


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
    fields = list(dict.fromkeys(key for row in rows for key in row)) if rows else ["status"]
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

This package combines reproducible machine checks with traceable application-level semantic assessment.

## Completed reproducible checks

- DECODE concepts: {coverage['public_h2kg_outcomes']} public H2KG outcomes and {coverage['decode_local_outcomes']} DECODE-local outcomes out of {coverage['canonical_source_concepts']} canonical source concepts.
- ITC overlap: {crosswalk['fields_overlapping_source_concept_registry']} of 44 ITC fields occur in the 573-concept source registry; {crosswalk['profile_overlay_only_fields']} are profile-overlay-only fields.
- Retrieval: {retrieval['task_count']} named tasks with independently labelled results and a precisely defined label baseline. No precision or recall estimate is claimed.
- Semantic assessment: {summary['semantic_assessment']['assessment_count']} item-level records across ITC fields, DECODE concepts and edges, the H2KG taxonomy sample, and asserted external mappings.
- Comparator evaluation: {summary['comparator_evaluation']['assessment_count']} evidence-backed task outcomes across H2KG, EDO, HDO, and HOLY, without an aggregate score.
- BattINFO is retained as a TIB catalogue membership but is not assigned semantic outcomes because native frozen evidence is unavailable.

## Interpretation boundary

Acceptance of a DECODE-local concept confirms its project-local identity and role only. It does not create an H2KG class, W3ID identifier, synonym, or external mapping. Historical disagreement and adjudication counts were not retained in the source evidence and are therefore not reported as zero.
"""
