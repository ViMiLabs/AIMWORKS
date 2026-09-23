from __future__ import annotations

"""Normalize the contact-free DECODE manual workflow overlay."""

import csv
import hashlib
import io
import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from .utils import dump_json, load_json, write_text


DECODE_NS = "https://w3id.org/h2kg/decode/workflow/"
H2KG = "https://w3id.org/h2kg/hydrogen-ontology#"
PROV_WAS_INFORMED_BY = "http://www.w3.org/ns/prov#wasInformedBy"

NEW_METHOD_IDS = {
    "CEA-Exp-tem-eds-analysis-CL",
    "CIEMAT-Exp-effective-proton-conductivity",
    "CIEMAT-Exp-single-cell-polarization-eis",
    "DTU-Mod-machine-learning-force-fields",
    "FZJ-Mod-StarDist-TEMSeg",
    "FZJ-Mod-StarPlatin-TEMSeg",
    "HTE-Exp-cell-testing",
    "HTE-Mod-pemfc-4-fold-cell-benchtop-test",
    "ICPEES-CNRS-Unistra-Exp-clsm-acidic-supported-electrodes",
    "ICPEES-CNRS-Unistra-Exp-n2-adsorption-ex-situ",
    "ICPEES-CNRS-Unistra-PSI-Exp-in-situ-ftir-atr-configuration-nanostructured",
    "NEL-Exp-large-scale-durability-test",
    "NEL-Exp-oer-her-catalyst-activity-alkaline",
    "NEL-Exp-pewe-single-cell-benchtop-test",
    "NEL-Exp-ptl-bulk-resistance",
    "NEL-Exp-ptl-porosity-contact-angle",
}

# Reviewed punctuation/truncation reconciliations. Other existing records must
# match a GraphML workflow title after deterministic normalization.
EXISTING_WORKFLOW_OVERRIDES = {
    "HZB-Exp-fib-gdl-mpl-catalyst": "fib-measurements-on-gdl-or-mpl-and-catalyst-materials",
    "HZB-Exp-lab-ct-gdl-mpl": "lab-ct-measurements-on-gdl-or-mpl-materials",
    "HZB-Exp-synch-ct-gdl-mpl": "synch-ct-measurements-on-gdl-or-mpl-materials",
    "ICPEES-CNRS-Unistra-Exp-clsm-acidic-unsupported-electrodes": "confocal-laser-scanning-microscope-clsm-and-fluorescent-probes-for-local-ph-assessment-in-acidic-med",
    "PSI-Exp-cl-saturation-determination-saxs-sans": "determination-of-cl-saturation-by-saxs-or-sans",
}

# References to retained GraphML workflows that have no manual JSON row.
REFERENCE_WORKFLOW_ALIASES = {
    "BOSCH-Exp-hg-porosimetry-gdl": "hg-porosimetry-gdl",
    "CEA-Exp-electrical-conductivity": "electrical-conductivity",
    "CEA-Exp-electrical-contact-resistance": "electrical-contact-resistance",
    "CEA-Mod-mpl-coating-gdl-modeling": "modeling-of-mpl-coating-of-gdl",
    "CIEMAT-Exp-mechanical-properties-small-punch-nanoindentation": "mechanical-properties-of-catalyst-layers-gdls-and-meas-by-small-punch-and-nanoindentation",
    "CNRS-Unistra-Exp-irras-operando-in-situ-ftir": "irras-operando-or-in-situ-ftir",
    "CNRS-Unistra-Exp-operando-in-situ-xps-dip-and-pull": "dip-and-pull-operando-or-in-situ-xps",
    "CNRS-Unistra-Exp-operando-in-situ-xps-thin-windows": "thin-windows-operando-or-in-situ-xps",
    "FZJ-IET-2-Exp-turbiscan-transmission-backscattering-stability-testing": "turbiscan-transmission-and-backscattering-stability-testing",
    "FZJ-IET-3-Mod-mea-water-transport-ccl-eis-model": "iet-1d-mea-with-water-transport-in-ccl-eis-model",
    "FZJ-IET-3-Mod-mea-water-transport-eis-model": "iet-1d-mea-with-water-transport-eis-model",
    "FZJ-IET-3-Mod-molecular-dynamics-electrode-ionomer": "molecular-dynamics-for-the-electrode-electrolyte-interface-in-presence-of-ionomer",
    "FZJ-IET-3-Mod-particle-population-degradation-coupled-performance-fitting": "0d-particle-population-degradation-model-coupled-with-performance-model-fitting",
    "FZJ-IET-3-Mod-particle-population-degradation-coupled-performance-prediction": "0d-particle-population-degradation-model-coupled-with-performance-model-prediction",
    "FZJ-IET-3-Mod-particle-population-degradation-prediction": "0d-particle-population-degradation-model-prediction",
    "FZJ-IET-4-Exp-eis-pewe": "eis-on-pewe-cells",
    "FZJ-IET-4-Exp-ultrasonic-spray-deposition-catalytic-layers": "ultrasonic-spray-deposition-for-catalytic-layers",
    "HZB-Exp-neutron-imaging": "neutron-imaging",
    "ICPEES-CNRS-Unistra-Exp-ast-nanostructured-electrodes": "accelerated-stress-test-ast-on-nanostructured-electrodes",
    "ICPEES-CNRS-Unistra-Exp-clsm-acidic-gde": "confocal-laser-scanning-microscope-clsm-and-fluorescent-probes-for-local-ph-assessment-in-acidic-med2",
    "ICPEES-CNRS-Unistra-Exp-clsm-alkaline-gde": "confocal-laser-scanning-microscope-clsm-and-fluorescent-probes-for-local-ph-assessment-in-alkaline-m2",
    "ICPEES-CNRS-Unistra-Exp-clsm-alkaline-unsupported-electrodes": "confocal-laser-scanning-microscope-clsm-and-fluorescent-probes-for-local-ph-assessment-in-alkaline-m",
    "ICPEES-CNRS-Unistra-Exp-electrochemistry-rde-cell": "model-electrochemistry-in-a-rde-cell",
    "ICPEES-CNRS-Unistra-Mod-molecular-dynamics-metalwalls": "molecular-dynamics-for-the-electrode-electrolyte-interface-metalwalls",
    "ICPEES-CNRS-Unistra-PSI-Exp-cl-for-rde": "cl-for-rde",
    "ICPEES-CNRS-Unistra-PSI-Exp-operando-in-situ-xas-photon-out": "operando-or-in-situ-xas-photon-out",
    "ICPEES-CNRS-Unistra-PSI-Exp-operando-saxs-waxs": "operando-saxs-or-waxs-small-or-wide-angle-x-ray-spectroscopy",
    "INPT-Mod-cl-process-model": "inpt-cl-process-model",
    "INPT-Mod-image-based-ccl-transport-property-computation": "image-based-ccl-effective-transport-property-computation-from-numerical-simulations",
    "PSI-Exp-cl-assessment-three-electrode-cell-xas-xanes-exafs-xrd": "three-electrode-cell-assesement-of-cl-by-xas-xanes-exafs-xrd",
    "PSI-Exp-rrde": "rotating-ring-disk-electrode-rrde",
    "ULEI-Exp-rrde-acidic": "rrde-on-model-electrodes-in-acidic-solutions",
    "ULEI-Exp-rrde-alkaline": "rrde-on-model-electrodes-in-alkaline-solutions",
    "ULEI-Mod-diffusion-theory": "diffusion-theory",
    "ULEI-Mod-rde-simulation-comsol": "rde-simulation-in-comsol",
    "ULEI-Mod-rrde-simulation-comsol": "rrde-simulation-in-comsol",
    "ULEI-Mod-rrde-theory": "rrde-theory",
}

REFERENCE_TITLE_ALIASES = {
    "Fitting Version of the Hierachical Model": "ULEI-FZJ-IET-3-Mod-fitting-version-hierachical-model",
}

DISPLAY_REPLACEMENTS = {
    "assessement": "assessment",
    "spectrocopy": "spectroscopy",
    "Hierachical": "Hierarchical",
    "nulloparticle": "nanoparticle",
}

NOVEL_IO_MAPPINGS = {
    "adsorbate conformation on electrode nanostructured": ("Data", "data", ""),
    "ccl 2d tem images raw": ("Data", "data", H2KG + "MicrostructureImageDataset"),
    "cell h2 outlet pressure": ("Parameter", "component", ""),
    "degradation rate of cell voltage": ("Property", "device", ""),
    "lre species distribution nanostructured": ("Data", "data", ""),
    "linear sweep voltammetry": ("Data", "data", ""),
    "ptl contact angle": ("Property", "component", ""),
    "ptl bulk resistance": ("Property", "component", ""),
}


def ingest_decode_manual_json(
    source_path: str | Path,
    overlay_path: str | Path,
    base_snapshot_path: str | Path,
) -> dict[str, Any]:
    """Create a sanitized overlay and 16 source-backed workflow records."""
    source_path = Path(source_path)
    overlay_path = Path(overlay_path)
    raw = source_path.read_bytes()
    source_digest = hashlib.sha256(raw).hexdigest()
    source = json.loads(raw.decode("utf-8-sig"))
    records = source.get("methods", []) if isinstance(source, dict) else []
    if not isinstance(records, list):
        raise ValueError("Manual DECODE JSON must contain a methods array.")
    base = load_json(Path(base_snapshot_path))
    methods, duplicate_audit = _deduplicate_methods(records)
    existing_by_title = {_normal(workflow["title"]): workflow for workflow in base.get("workflows", [])}
    existing_by_id = {workflow["id"]: workflow for workflow in base.get("workflows", [])}

    reconciliation: list[dict[str, Any]] = []
    method_to_workflow: dict[str, str] = {}
    for method in methods:
        method_id = method["method_id"]
        if method_id in NEW_METHOD_IDS:
            workflow_id = "manual-" + _slug(method_id)
            outcome = "new_manual_workflow"
            evidence = "Identifier is absent from the immutable 120-workflow GraphML snapshot."
        else:
            workflow_id = EXISTING_WORKFLOW_OVERRIDES.get(method_id, "")
            if not workflow_id:
                raw_names = [*method.get("original_names", []), method["name"]]
                match = next((existing_by_title.get(_normal(name)) for name in raw_names if existing_by_title.get(_normal(name))), None)
                workflow_id = str(match["id"]) if match else ""
            if not workflow_id or workflow_id not in existing_by_id:
                raise ValueError(f"No explicit existing-workflow reconciliation for {method_id}")
            outcome = "matched_graphml_workflow"
            evidence = "Method name or reviewed spelling/truncation override identifies the preserved GraphML workflow."
        method_to_workflow[method_id] = workflow_id
        reconciliation.append(
            {
                "method_id": method_id,
                "display_name": method["name"],
                "original_names": method.get("original_names", []),
                "outcome": outcome,
                "workflow_id": workflow_id,
                "evidence": evidence,
                "source_type": method["type"],
                "semantic_activity_role": _method_role(method),
                "flags": _method_flags(method),
            }
        )

    mapped_existing = {row["workflow_id"] for row in reconciliation if row["outcome"] == "matched_graphml_workflow"}
    retained = sorted(set(existing_by_id) - mapped_existing)
    reference_resolution = _resolve_references(methods, method_to_workflow, existing_by_id)
    dependencies = _build_dependencies(
        methods,
        method_to_workflow,
        reference_resolution,
        _base_io_index(base),
    )
    new_methods = [method for method in methods if method["method_id"] in NEW_METHOD_IDS]
    existing_concepts = _existing_concept_index(base)
    new_workflows = [
        _manual_workflow(method, method_to_workflow[method["method_id"]], existing_concepts)
        for method in new_methods
    ]
    for workflow in new_workflows:
        workflow["source_filename"] = source_path.name
        workflow["source_sha256"] = source_digest
    _append_linked_method_context(new_workflows, dependencies, methods, existing_by_id)

    io_occurrences = [
        (direction, label)
        for method in new_methods
        for direction, field in (("input", "inputs"), ("output", "outputs"))
        for label in method[field]
    ]
    novel_concepts = sorted(
        {
            node["label"]
            for workflow in new_workflows
            for node in workflow["nodes"]
            if node.get("source_field") in {"input", "output"}
            and _normal(node["label"]) in NOVEL_IO_MAPPINGS
            and node.get("mapping_override", {}).get("state") != "approved_h2kg"
        },
        key=str.lower,
    )
    overlay = {
        "schema_version": "1.0",
        "generated_on": date.today().isoformat(),
        "source_filename": source_path.name,
        "source_sha256": source_digest,
        "source_provenance": "Sanitized scientific overlay derived from the named manual DECODE JSON source.",
        "raw_source_redistributed": False,
        "privacy_policy": "Personal names, contact fields, and email addresses are excluded from all public artifacts.",
        "methods": methods,
        "new_workflows": new_workflows,
        "reconciliation": {
            "methods": reconciliation,
            "duplicate_groups": duplicate_audit,
            "retained_graphml_workflow_ids": retained,
            "reference_resolution": reference_resolution,
        },
        "workflow_dependencies": dependencies,
        "promotion_candidates": [
            {
                "label": label,
                "recommended_role": NOVEL_IO_MAPPINGS[_normal(label)][0],
                "current_decision": "reviewed_decode_anchor",
                "review_status": "candidate_for_later_controlled_vocabulary_review",
            }
            for label in novel_concepts
        ],
        "counts": {
            "source_record_count": len(records),
            "unique_method_count": len(methods),
            "duplicate_group_count": len(duplicate_audit),
            "matched_method_count": sum(row["outcome"] == "matched_graphml_workflow" for row in reconciliation),
            "new_method_count": len(new_workflows),
            "retained_graphml_workflow_count": len(retained),
            "resolved_reference_value_count": sum(row["resolved"] for row in reference_resolution),
            "resolved_missing_reference_value_count": sum(
                row["resolved"] and row["was_missing_from_manual_methods"] for row in reference_resolution
            ),
            "unresolved_reference_value_count": sum(not row["resolved"] for row in reference_resolution),
            "new_core_node_count": sum(workflow["core_node_count"] for workflow in new_workflows),
            "new_core_edge_count": sum(workflow["core_edge_count"] for workflow in new_workflows),
            "new_context_node_count": sum(len(workflow["nodes"]) - workflow["core_node_count"] for workflow in new_workflows),
            "new_context_edge_count": sum(len(workflow["edges"]) - workflow["core_edge_count"] for workflow in new_workflows),
            "new_io_occurrence_count": len(io_occurrences),
            "new_unique_io_concept_count": len({_normal(label) for _, label in io_occurrences}),
            "workflow_dependency_count": len(dependencies),
            "published_workflow_dependency_count": sum(row["publication_status"] != "audit_only" for row in dependencies),
        },
    }
    _validate_overlay(overlay)
    dump_json(overlay_path, overlay)
    return {"status": "ingested", "overlay": str(overlay_path), **overlay["counts"]}


def merge_manual_overlay(snapshot: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Return a combined build snapshot without modifying either source object."""
    return {
        **snapshot,
        "schema_version": "1.1",
        "workflows": [*snapshot.get("workflows", []), *overlay.get("new_workflows", [])],
        "manual_overlay": {
            "source_filename": overlay.get("source_filename", ""),
            "source_sha256": overlay.get("source_sha256", ""),
            "raw_source_redistributed": False,
            "counts": overlay.get("counts", {}),
        },
        "workflow_dependencies": overlay.get("workflow_dependencies", []),
    }


def write_manual_overlay_release(target: Path, overlay: dict[str, Any]) -> list[Path]:
    files = [
        dump_json(target / "decode_manual_overlay.json", overlay),
        dump_json(target / "decode_manual_reconciliation.json", overlay.get("reconciliation", {})),
        dump_json(target / "decode_promotion_candidates.json", overlay.get("promotion_candidates", [])),
    ]
    files.append(_write_rows(target / "decode_manual_reconciliation.csv", overlay.get("reconciliation", {}).get("methods", [])))
    files.append(_write_rows(target / "decode_manual_reference_resolution.csv", overlay.get("reconciliation", {}).get("reference_resolution", [])))
    files.append(_write_rows(target / "decode_promotion_candidates.csv", overlay.get("promotion_candidates", [])))
    return files


def _deduplicate_methods(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record.get("method_id", "")).strip()].append(record)
    if "" in grouped:
        raise ValueError("Every manual record must have a method_id.")
    methods: list[dict[str, Any]] = []
    duplicate_audit: list[dict[str, Any]] = []
    for method_id in sorted(grouped):
        group = grouped[method_id]
        original_names = _unique(str(record.get("name", "")).strip() for record in group)
        canonical_name = "StarDist-TEM nanoparticle segmentation" if method_id == "FZJ-Mod-StarDist-TEMSeg" else _correct(original_names[-1])
        source_types = _unique(str(record.get("type", "")).strip() for record in group)
        method = {
            "method_id": method_id,
            "name": canonical_name,
            "original_names": original_names,
            "type": _correct(source_types[0]).strip() if source_types else "",
            "original_types": source_types,
            "partner_organization": _unique(str(record.get("partner", "")).strip() for record in group if record.get("partner")),
            "decode_tasks": _unique(str(record.get("decode_task", "")).strip() for record in group if record.get("decode_task")),
            "inputs": _split_and_union(group, "inputs"),
            "outputs": _split_and_union(group, "outputs"),
            "input_method": _unique(value for record in group for value in _as_list(record.get("input_method"))),
            "output_method": _unique(value for record in group for value in _as_list(record.get("output_method"))),
            "used_in_t2.5": any(record.get("used_in_t2.5") is True for record in group),
            "source_record_count": len(group),
        }
        methods.append(method)
        if len(group) > 1:
            exact = len({json.dumps(_scientific_record(record), sort_keys=True, ensure_ascii=False) for record in group}) == 1
            duplicate_audit.append(
                {
                    "method_id": method_id,
                    "source_record_count": len(group),
                    "outcome": "exact_duplicate_collapsed" if exact else "reviewed_union_merge",
                    "canonical_name": canonical_name,
                    "original_names": original_names,
                    "retained_tasks": method["decode_tasks"],
                    "retained_used_in_t2.5": method["used_in_t2.5"],
                }
            )
    return methods, duplicate_audit


def _scientific_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: record.get(key)
        for key in (
            "name", "type", "inputs", "outputs", "partner", "comments", "method_id",
            "decode_task", "input_method", "used_in_t2.5", "output_method",
            "exp_date_of_completion_ref", "exp_date_of_completion_var",
        )
    }


def _split_and_union(group: list[dict[str, Any]], field: str) -> list[str]:
    values: list[str] = []
    for record in group:
        for raw in _as_list(record.get(field)):
            if _normal(raw) == "i c ratio monomer concentration in the electrolyte":
                values.extend(["I/C-ratio", "Monomer concentration in the electrolyte"])
            else:
                values.append(_correct(raw.strip()))
    return _unique(values)


def _resolve_references(
    methods: list[dict[str, Any]],
    method_to_workflow: dict[str, str],
    existing_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    method_ids = {method["method_id"] for method in methods}
    values = sorted(
        {
            value
            for method in methods
            for field in ("input_method", "output_method")
            for value in method[field]
        },
        key=str.lower,
    )
    rows: list[dict[str, Any]] = []
    for value in values:
        canonical_method_id = REFERENCE_TITLE_ALIASES.get(value, value)
        if canonical_method_id in method_ids:
            workflow_id = method_to_workflow[canonical_method_id]
            resolution = "manual_method_identifier" if canonical_method_id == value else "reviewed_title_alias"
        else:
            workflow_id = REFERENCE_WORKFLOW_ALIASES.get(value, "")
            resolution = "reviewed_graphml_identifier_alias"
        resolved = bool(workflow_id and (workflow_id in existing_by_id or workflow_id.startswith("manual-")))
        rows.append(
            {
                "source_reference": value,
                "canonical_method_id": canonical_method_id if canonical_method_id in method_ids else "",
                "workflow_id": workflow_id,
                "resolution": resolution if resolved else "unresolved",
                "resolved": resolved,
                "was_missing_from_manual_methods": value not in method_ids,
            }
        )
    unresolved = [row["source_reference"] for row in rows if not row["resolved"]]
    if unresolved:
        raise ValueError("Unresolved manual method references: " + "; ".join(unresolved))
    return rows


def _build_dependencies(
    methods: list[dict[str, Any]],
    method_to_workflow: dict[str, str],
    reference_resolution: list[dict[str, Any]],
    base_io: dict[str, dict[str, list[str]]],
) -> list[dict[str, Any]]:
    methods_by_id = {method["method_id"]: method for method in methods}
    resolution = {row["source_reference"]: row for row in reference_resolution}
    declarations: dict[tuple[str, str], set[str]] = defaultdict(set)
    source_records: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for method in methods:
        current = method["method_id"]
        for value in method["output_method"]:
            target = _reference_key(value, resolution)
            declarations[(current, target)].add("output_method")
            source_records[(current, target)].append({"record": current, "field": "output_method", "value": value})
        for value in method["input_method"]:
            source = _reference_key(value, resolution)
            declarations[(source, current)].add("input_method")
            source_records[(source, current)].append({"record": current, "field": "input_method", "value": value})
    rows: list[dict[str, Any]] = []
    for index, ((upstream, downstream), declared_by) in enumerate(sorted(declarations.items())):
        upstream_io = _method_io(upstream, methods_by_id, method_to_workflow, base_io)
        downstream_io = _method_io(downstream, methods_by_id, method_to_workflow, base_io)
        downstream_inputs = {_normal(label): label for label in downstream_io["inputs"]}
        handoffs = _unique(
            downstream_inputs[_normal(label)]
            for label in upstream_io["outputs"]
            if _normal(label) in downstream_inputs
        )
        reciprocal = declared_by == {"input_method", "output_method"}
        if reciprocal:
            publication_status = "published_confirmed"
            state = "confirmed_reciprocal" if handoffs else "confirmed_dependency_without_exact_handoff"
        elif handoffs:
            publication_status = "published_pending_review"
            state = "grounded_one_sided"
        else:
            publication_status = "audit_only"
            state = "ungrounded_one_sided"
        rows.append(
            {
                "id": f"manual-dependency-{index:04d}-{_short_hash(upstream + '|' + downstream)}",
                "upstream_method_id": upstream.removeprefix("graphml:"),
                "downstream_method_id": downstream.removeprefix("graphml:"),
                "upstream_workflow_id": _key_workflow(upstream, method_to_workflow),
                "downstream_workflow_id": _key_workflow(downstream, method_to_workflow),
                "declarations": sorted(declared_by),
                "reciprocity_state": state,
                "handoff_labels": handoffs,
                "predicate": PROV_WAS_INFORMED_BY,
                "publication_status": publication_status,
                "source_records": source_records[(upstream, downstream)],
                "review_rationale": _dependency_rationale(state),
                "both_methods_in_manual_json": (
                    upstream in methods_by_id
                    and downstream in methods_by_id
                    and not any(record["value"] in REFERENCE_TITLE_ALIASES for record in source_records[(upstream, downstream)])
                ),
            }
        )
    return rows


def _base_io_index(base: dict[str, Any]) -> dict[str, dict[str, list[str]]]:
    result: dict[str, dict[str, list[str]]] = {}
    for workflow in base.get("workflows", []):
        nodes = {node["id"]: node for node in workflow.get("nodes", [])}
        exact = [node for node in nodes.values() if _normal(node["label"]) == _normal(workflow["title"])]
        candidates = exact or [
            node for node in nodes.values()
            if str(node.get("native_category", "")).lower() in {"method", "model", "process"}
            or str(node.get("shape", "")).lower() == "hexagon"
        ]
        if not candidates:
            result[workflow["id"]] = {"inputs": [], "outputs": []}
            continue
        method = max(candidates, key=lambda node: _token_overlap(node["label"], workflow["title"]))
        inputs = [nodes[edge["source"]]["label"] for edge in workflow.get("edges", []) if edge["target"] == method["id"] and edge["source"] in nodes]
        outputs = [nodes[edge["target"]]["label"] for edge in workflow.get("edges", []) if edge["source"] == method["id"] and edge["target"] in nodes]
        result[workflow["id"]] = {"inputs": _unique(inputs), "outputs": _unique(outputs)}
    return result


def _method_io(
    key: str,
    methods_by_id: dict[str, dict[str, Any]],
    method_to_workflow: dict[str, str],
    base_io: dict[str, dict[str, list[str]]],
) -> dict[str, list[str]]:
    if key in methods_by_id:
        return {"inputs": methods_by_id[key]["inputs"], "outputs": methods_by_id[key]["outputs"]}
    return base_io.get(_key_workflow(key, method_to_workflow), {"inputs": [], "outputs": []})


def _reference_key(value: str, resolution: dict[str, dict[str, Any]]) -> str:
    row = resolution[value]
    return row["canonical_method_id"] or "graphml:" + row["workflow_id"]


def _key_workflow(key: str, method_to_workflow: dict[str, str]) -> str:
    return key.removeprefix("graphml:") if key.startswith("graphml:") else method_to_workflow[key]


def _dependency_rationale(state: str) -> str:
    if state == "confirmed_reciprocal":
        return "Both method records declare the dependency and exact reviewed input/output handoff labels are shared."
    if state == "confirmed_dependency_without_exact_handoff":
        return "Both records declare the dependency; no exact handoff is asserted, so only PROV dependency is published."
    if state == "grounded_one_sided":
        return "One record declares the dependency and an exact reviewed handoff grounds a pending-review link."
    return "One-sided declaration lacks an exact reviewed handoff and is retained for audit only."


def _manual_workflow(
    method: dict[str, Any],
    workflow_id: str,
    existing_concepts: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    workflow_iri = DECODE_NS + workflow_id
    method_mapping = _method_mapping(method)
    nodes = [
        {
            "id": f"{workflow_id}::method",
            "iri": f"{workflow_iri}/node/method",
            "source_id": "method",
            "label": method["name"],
            "source_label": method["original_names"][0],
            "original_labels": method["original_names"],
            "native_category": "model" if _method_role(method) == "Process" else ("process" if _method_role(method) == "Manufacturing" else "method"),
            "description": f"Manual DECODE method record: {method['method_id']}",
            "shape": "hexagon",
            "source_kind": "source_manual_json",
            "source_field": "method",
            "mapping_override": method_mapping,
        }
    ]
    edges: list[dict[str, Any]] = []
    for direction, field in (("input", "inputs"), ("output", "outputs")):
        for position, label in enumerate(method[field]):
            source_id = f"{direction}-{_slug(label)}-{_short_hash(direction + '|' + label)}"
            mapping, native_category = _io_mapping(label, existing_concepts)
            original_label = "I/C-ratio; Monomer concentration in the electrolyte" if label in {
                "I/C-ratio", "Monomer concentration in the electrolyte"
            } else label
            node = {
                "id": f"{workflow_id}::{source_id}",
                "iri": f"{workflow_iri}/node/{source_id}",
                "source_id": source_id,
                "label": label,
                "source_label": original_label,
                "original_labels": [original_label],
                "native_category": native_category,
                "description": f"Manual DECODE {direction} field; original label: {original_label}",
                "shape": "ellipse",
                "source_kind": "source_manual_json",
                "source_field": direction,
                "source_position": position,
            }
            if mapping:
                node["mapping_override"] = mapping
            nodes.append(node)
            edge_source, edge_target = (source_id, "method") if direction == "input" else ("method", source_id)
            edge_id = f"core-{direction}-{position:03d}"
            edges.append(
                {
                    "id": f"{workflow_id}::{edge_id}",
                    "source_id": edge_source,
                    "target_id": edge_target,
                    "source": f"{workflow_id}::{edge_source}",
                    "target": f"{workflow_id}::{edge_target}",
                    "description": f"Manual JSON {direction} dependency.",
                    "source_kind": "source_manual_json",
                    "source_field": direction,
                }
            )
    return {
        "id": workflow_id,
        "iri": workflow_iri,
        "title": method["name"],
        "source_filename": "sanitized manual DECODE JSON overlay",
        "source_sha256": "provided-by-overlay",
        "source_kind": "source_manual_json",
        "source_format": "json",
        "source_status": "manual_source_preserved",
        "method_family": _manual_method_family(method),
        "directed": True,
        "external_method_id": method["method_id"],
        "alternate_titles": method["original_names"],
        "decode_tasks": method["decode_tasks"],
        "partner_organization": method["partner_organization"],
        "search_terms": [
            method["method_id"],
            *method["original_names"],
            *method["inputs"],
            *method["outputs"],
            *method["input_method"],
            *method["output_method"],
            *method["partner_organization"],
        ],
        "nodes": nodes,
        "edges": edges,
        "core_node_count": len(nodes),
        "core_edge_count": len(edges),
    }


def _append_linked_method_context(
    workflows: list[dict[str, Any]],
    dependencies: list[dict[str, Any]],
    methods: list[dict[str, Any]],
    existing_by_id: dict[str, dict[str, Any]],
) -> None:
    by_workflow = {workflow["id"]: workflow for workflow in workflows}
    methods_by_id = {method["method_id"]: method for method in methods}
    for dependency in dependencies:
        if dependency["publication_status"] == "audit_only" or not dependency["handoff_labels"]:
            continue
        upstream_id = dependency["upstream_workflow_id"]
        downstream_id = dependency["downstream_workflow_id"]
        if downstream_id in by_workflow:
            workflow = by_workflow[downstream_id]
            linked = _linked_method_node(workflow, dependency["upstream_method_id"], "upstream", methods_by_id, existing_by_id)
            for label in dependency["handoff_labels"]:
                target = _find_field_node(workflow, "input", label)
                if target:
                    _append_context_edge(workflow, linked, target, dependency, "upstream_handoff")
        if upstream_id in by_workflow:
            workflow = by_workflow[upstream_id]
            linked = _linked_method_node(workflow, dependency["downstream_method_id"], "downstream", methods_by_id, existing_by_id)
            for label in dependency["handoff_labels"]:
                source = _find_field_node(workflow, "output", label)
                if source:
                    _append_context_edge(workflow, source, linked, dependency, "downstream_handoff")


def _linked_method_node(
    workflow: dict[str, Any],
    method_or_workflow_id: str,
    direction: str,
    methods_by_id: dict[str, dict[str, Any]],
    existing_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    source_id = f"linked-{direction}-{_slug(method_or_workflow_id)}-{_short_hash(method_or_workflow_id)}"
    existing = next((node for node in workflow["nodes"] if node["source_id"] == source_id), None)
    if existing:
        return existing
    method = methods_by_id.get(method_or_workflow_id)
    base = existing_by_id.get(method_or_workflow_id)
    label = method["name"] if method else (base["title"] if base else method_or_workflow_id)
    role = _method_role(method) if method else ("Process" if "mod" in method_or_workflow_id.lower() else "Measurement")
    node = {
        "id": f"{workflow['id']}::{source_id}",
        "iri": f"{workflow['iri']}/node/{source_id}",
        "source_id": source_id,
        "label": label,
        "source_label": label,
        "original_labels": [label],
        "native_category": "model" if role == "Process" else ("process" if role == "Manufacturing" else "method"),
        "description": f"Linked {direction} method from a reviewed manual JSON handoff declaration.",
        "shape": "hexagon",
        "source_kind": "source_manual_json_context",
        "source_field": f"linked_{direction}_method",
        "is_linked_context": True,
        "mapping_override": _reviewed_mapping(label, role, "Manual method dependency context."),
    }
    workflow["nodes"].append(node)
    return node


def _append_context_edge(
    workflow: dict[str, Any],
    source: dict[str, Any],
    target: dict[str, Any],
    dependency: dict[str, Any],
    pattern: str,
) -> None:
    edge_id = f"{workflow['id']}::context-{_short_hash(dependency['id'] + '|' + source['source_id'] + '|' + target['source_id'])}"
    if any(edge["id"] == edge_id for edge in workflow["edges"]):
        return
    workflow["edges"].append(
        {
            "id": edge_id,
            "source_id": source["source_id"],
            "target_id": target["source_id"],
            "source": source["id"],
            "target": target["id"],
            "description": f"Reviewed linked-method context through {', '.join(dependency['handoff_labels'])}.",
            "source_kind": "source_manual_json_context",
            "source_field": pattern,
            "workflow_dependency_id": dependency["id"],
        }
    )


def _find_field_node(workflow: dict[str, Any], direction: str, label: str) -> dict[str, Any] | None:
    return next(
        (node for node in workflow["nodes"] if node.get("source_field") == direction and _normal(node["label"]) == _normal(label)),
        None,
    )


def _method_mapping(method: dict[str, Any]) -> dict[str, Any]:
    if method["method_id"] == "ICPEES-CNRS-Unistra-Exp-n2-adsorption-ex-situ":
        return {
            "state": "approved_h2kg",
            "anchor_iri": H2KG + "NitrogenPhysisorptionMeasurement",
            "anchor_label": "Nitrogen physisorption measurement",
            "canonical_role_iri": H2KG + "Measurement",
            "semantic_role": "Measurement",
            "decision": "existing_h2kg_mapping",
            "confidence": "reviewed",
            "evidence": "Reviewed mapping to the existing public H2KG nitrogen-physisorption measurement class.",
        }
    return _reviewed_mapping(
        method["name"],
        _method_role(method),
        "Reviewed manual DECODE method role; public vocabulary promotion is deferred.",
    )


def _io_mapping(label: str, existing_concepts: dict[str, list[dict[str, Any]]]) -> tuple[dict[str, Any] | None, str]:
    key = _normal(label)
    novel = NOVEL_IO_MAPPINGS.get(key)
    if novel:
        role, category, h2kg_iri = novel
        if h2kg_iri:
            return {
                "state": "approved_h2kg",
                "anchor_iri": h2kg_iri,
                "anchor_label": "Microstructure image dataset",
                "canonical_role_iri": H2KG + role,
                "semantic_role": role,
                "decision": "existing_h2kg_mapping",
                "confidence": "reviewed",
                "evidence": "Reviewed existing H2KG mapping for the manual JSON field.",
            }, category
        return _reviewed_mapping(
            label,
            role,
            "Reviewed DECODE anchor pending controlled H2KG vocabulary review.",
        ), category
    matches = existing_concepts.get(key, [])
    if not matches:
        raise ValueError(f"Manual I/O concept has no reviewed existing or novel mapping decision: {label}")
    return None, str(matches[0].get("native_category", "other"))


def _reviewed_mapping(label: str, role: str, evidence: str) -> dict[str, Any]:
    return {
        "state": "reviewed_decode",
        "anchor_iri": f"{DECODE_NS}anchor/{_slug(label)}-{_short_hash(_normal(label) + '|' + role)}",
        "anchor_label": label,
        "canonical_role_iri": H2KG + role,
        "semantic_role": role,
        "decision": "reviewed_decode_anchor",
        "confidence": "reviewed",
        "evidence": evidence,
    }


def _method_role(method: dict[str, Any] | None) -> str:
    if not method:
        return "Process"
    if method["method_id"] == "CIEMAT-Exp-effective-proton-conductivity":
        return "Process"
    source_type = str(method.get("type", "")).strip()
    if source_type == "Manufacturing":
        return "Manufacturing"
    if source_type == "Experiment":
        return "Measurement"
    return "Process"


def _method_flags(method: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    if method["method_id"] == "HTE-Mod-pemfc-4-fold-cell-benchtop-test" and method["type"] == "Experiment":
        flags.append("identifier_mod_token_conflicts_with_experiment_role")
    if method["method_id"] == "CIEMAT-Exp-effective-proton-conductivity":
        flags.append("experiment_source_type_curated_as_analysis_process")
    return flags


def _manual_method_family(method: dict[str, Any]) -> str:
    role = _method_role(method)
    name = _normal(method["name"])
    if "tem" in name or "clsm" in name or "ftir" in name:
        return "imaging_characterization"
    if role == "Manufacturing":
        return "manufacturing"
    if role == "Process":
        return "simulation_modelling"
    return "electrochemical_measurement"


def _existing_concept_index(base: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for workflow in base.get("workflows", []):
        for node in workflow.get("nodes", []):
            index[_normal(node["label"])].append(node)
    return index


def _validate_overlay(overlay: dict[str, Any]) -> None:
    counts = overlay["counts"]
    expected = {
        "source_record_count": 102,
        "unique_method_count": 95,
        "duplicate_group_count": 7,
        "matched_method_count": 79,
        "new_method_count": 16,
        "retained_graphml_workflow_count": 41,
        "resolved_missing_reference_value_count": 38,
        "unresolved_reference_value_count": 0,
        "new_core_node_count": 115,
        "new_core_edge_count": 99,
        "new_io_occurrence_count": 99,
        "new_unique_io_concept_count": 62,
    }
    mismatches = {key: (counts.get(key), value) for key, value in expected.items() if counts.get(key) != value}
    if mismatches:
        raise ValueError(f"Manual overlay count regression: {mismatches}")
    forbidden = {"contact", "decode_contact", "email", "emails"}
    if any(forbidden.intersection(method) for method in overlay["methods"]):
        raise ValueError("Personal contact fields must not enter the sanitized overlay.")
    email_pattern = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
    if email_pattern.search(json.dumps(overlay, ensure_ascii=False)):
        raise ValueError("An email address was detected in the sanitized overlay.")


def _write_rows(path: Path, rows: list[dict[str, Any]]) -> Path:
    if not rows:
        return write_text(path, "")
    fields = sorted({key for row in rows for key in row})
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value
                for key, value in row.items()
            }
        )
    return write_text(path, buffer.getvalue())


def _correct(value: str) -> str:
    result = value.strip()
    for source, target in DISPLAY_REPLACEMENTS.items():
        result = result.replace(source, target)
    return result


def _normal(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "item"


def _short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _unique(values: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        key = _normal(text)
        if text and key not in seen:
            seen.add(key)
            result.append(text)
    return result


def _token_overlap(left: str, right: str) -> tuple[int, int]:
    left_tokens = set(_normal(left).split())
    right_tokens = set(_normal(right).split())
    return len(left_tokens & right_tokens), -abs(len(left_tokens) - len(right_tokens))
