from __future__ import annotations

"""Preserve and publish DECODE GraphML workflows as an H2KG-aligned data layer.

This module deliberately does not alter the H2KG TBox.  It assigns stable DECODE
occurrence IRIs to source GraphML nodes, preserves every source edge, and applies
only explicit mappings from the reviewed configuration file.
"""

import csv
import hashlib
import io
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from .scorer import lexical_score
from .utils import COMMON_CONTEXT, SKOS_ALT_LABEL, SKOS_PREF_LABEL, dump_json, ensure_dir, load_json, try_load_yaml, write_text
from .decode_multiscale_interface import append_multiscale_interface, build_decode_multiscale_model_interface


DECODE_NS = "https://w3id.org/h2kg/decode/workflow/"
H2KG = COMMON_CONTEXT["h2kg"]
RDF_TYPE = COMMON_CONTEXT["rdf"] + "type"
RDFS_LABEL = COMMON_CONTEXT["rdfs"] + "label"
PROV = COMMON_CONTEXT["prov"]
DECODE_MAPPING = DECODE_NS + "mappedToAnchor"
DECODE_SOURCE_DEPENDENCY = DECODE_NS + "sourceDependency"
DECODE_EDGE_PROJECTION = DECODE_NS + "SemanticProjection"
DECODE_DERIVED_FROM_OCCURRENCE = DECODE_NS + "derivedFromOccurrence"
DECODE_SOURCE_DEPENDENCY_ID = DECODE_NS + "sourceDependencyId"
DECODE_PROJECTION_OUTCOME = DECODE_NS + "projectionOutcome"
DECODE_PROJECTION_PATTERN = DECODE_NS + "projectionPattern"
DECODE_SEMANTIC_SOURCE = DECODE_NS + "semanticSource"
DECODE_SEMANTIC_TARGET = DECODE_NS + "semanticTarget"
DECODE_SEMANTIC_PREDICATE = DECODE_NS + "semanticPredicate"
PROV_WAS_DERIVED_FROM = PROV + "wasDerivedFrom"
PROV_WAS_INFORMED_BY = PROV + "wasInformedBy"
GRAPHML_NS = "{http://graphml.graphdrawing.org/xmlns}"
YED_NS = "{http://www.yworks.com/xml/graphml}"

ACTIVITY_ROLES = {"Manufacturing", "Measurement", "Process"}
EDGE_OUTCOMES = {"h2kg_direct", "h2kg_reified", "prov_derivation", "decode_structural_only"}


def ingest_decode_graphml_directory(
    source_dir: str | Path,
    snapshot_path: str | Path,
) -> dict[str, Any]:
    """Create a frozen, normalized structural snapshot from a GraphML directory."""
    source_dir = Path(source_dir)
    snapshot_path = Path(snapshot_path)
    graphml_paths = sorted(source_dir.glob("*.graphml"), key=lambda path: path.name.lower())
    if not graphml_paths:
        raise FileNotFoundError(f"No GraphML files found in {source_dir}")

    workflows = [_parse_graphml(path) for path in graphml_paths]
    snapshot = {
        "schema_version": "1.0",
        "generated_on": date.today().isoformat(),
        "source_directory_name": source_dir.name,
        "raw_graphml_redistributed": False,
        "workflows": workflows,
        "counts": {
            "workflow_count": len(workflows),
            "node_count": sum(len(workflow["nodes"]) for workflow in workflows),
            "edge_count": sum(len(workflow["edges"]) for workflow in workflows),
        },
    }
    dump_json(snapshot_path, snapshot)
    return {"status": "ingested", "snapshot": str(snapshot_path), **snapshot["counts"]}


def build_decode_workflow_release(
    snapshot_path: str | Path,
    output_root: str | Path,
    mapping_config_path: str | Path,
    ontology_path: str | Path | None = None,
    include_multiscale_interface: bool = False,
) -> dict[str, Any]:
    """Build static DECODE workflow artefacts from the immutable normalized snapshot."""
    snapshot_path = Path(snapshot_path)
    output_root = Path(output_root)
    if not snapshot_path.exists():
        return {"status": "skipped_missing_snapshot", "snapshot": str(snapshot_path)}
    snapshot = load_json(snapshot_path)
    mapping_config = try_load_yaml(
        Path(mapping_config_path),
        {"mappings": [], "semantic_projections": [], "default_alignment": {}, "alias_curation": []},
    )
    mappings = _index_mappings(mapping_config.get("mappings", []))
    semantic_projections = _index_semantic_projections(mapping_config.get("semantic_projections", []))
    target = ensure_dir(output_root / "decode")
    workflows_dir = ensure_dir(target / "workflows")
    graph, matrix_rows = _federate(
        snapshot,
        mappings,
        semantic_projections,
        mapping_config.get("default_alignment", {}),
    )
    interface: dict[str, Any] = {"status": "not_requested"}
    if include_multiscale_interface:
        interface = build_decode_multiscale_model_interface(
            snapshot_path.parent / "decode_multiscale_model_interface.json",
            snapshot_path,
            output_root,
        )
        append_multiscale_interface(graph, interface)
    _build_edge_alignment(graph, semantic_projections)
    semantic_overview = _build_semantic_overview(graph)
    role_conflicts = semantic_overview["role_conflicts"]
    duplicate_audit = _duplicate_occurrence_audit(graph, role_conflicts)
    graph["semantic_overview"] = semantic_overview
    graph["duplicate_occurrence_audit"] = duplicate_audit
    graph["semantic_role_conflicts"] = role_conflicts
    graph["counts"].update(
        {
            "semantic_overview_node_count": len(semantic_overview["nodes"]),
            "semantic_overview_source_edge_count": len(semantic_overview["source_edges"]),
            "semantic_role_conflict_count": len(role_conflicts),
            "duplicate_occurrence_group_count": len(duplicate_audit),
            "workflows_with_duplicate_occurrences": len({row["workflow_id"] for row in duplicate_audit}),
        }
    )
    validation = _validate_federated_graph(snapshot, graph)
    if interface.get("status") == "generated":
        validation["multiscale_interface"] = interface["validation"]
    anchor_candidates = _anchor_candidates(snapshot, mappings)
    registry = _concept_registry(snapshot, graph, ontology_path)

    generated: list[Path] = [
        dump_json(target / "decode_federated_graph.json", graph),
        dump_json(target / "decode_workflow_catalog.json", graph["workflows"]),
        dump_json(target / "decode_validation_report.json", validation),
        _write_mapping_matrix(target / "decode_mapping_matrix.csv", matrix_rows),
        _write_mapping_matrix_markdown(target / "decode_mapping_matrix.md", matrix_rows),
        _write_anchor_candidates(target / "decode_anchor_candidates.csv", anchor_candidates),
        dump_json(target / "decode_concept_registry.json", registry),
        _write_concept_registry(target / "decode_concept_registry.csv", registry["concepts"]),
        _write_semantic_role_audit(target / "decode_semantic_role_audit.csv", registry["concepts"]),
        dump_json(target / "decode_edge_registry.json", graph["edge_registry"]),
        _write_edge_registry(target / "decode_edge_registry.csv", graph["edge_registry"]),
        dump_json(target / "decode_duplicate_occurrence_audit.json", duplicate_audit),
        _write_duplicate_occurrence_audit(target / "decode_duplicate_occurrence_audit.csv", duplicate_audit),
        dump_json(target / "decode_semantic_role_conflicts.json", role_conflicts),
        _write_semantic_role_conflict_audit(target / "decode_semantic_role_conflicts.csv", role_conflicts),
        write_text(target / "README.md", _readme(graph, validation)),
    ]
    for workflow in graph["workflows"]:
        workflow_id = workflow["id"]
        structural = {
            "schema_version": graph["schema_version"],
            "workflow": workflow,
            "nodes": [node for node in graph["nodes"] if node.get("workflow_id") == workflow_id],
            "projection_nodes": [node for node in graph.get("projection_nodes", []) if node.get("workflow_id") == workflow_id],
            "anchors": [
                anchor
                for anchor in graph["anchors"]
                if any(node_id.startswith(f"{workflow_id}::") for node_id in anchor.get("occurrence_ids", []))
            ],
            "source_edges": [edge for edge in graph["source_edges"] if edge["workflow_id"] == workflow_id],
            "anchor_edges": [edge for edge in graph["anchor_edges"] if edge["workflow_id"] == workflow_id],
            "semantic_edges": [edge for edge in graph["semantic_edges"] if edge["workflow_id"] == workflow_id],
            "edge_registry": [row for row in graph["edge_registry"] if row["workflow_id"] == workflow_id],
            "download_note": "Raw GraphML is not redistributed; this is a normalized structural projection.",
        }
        json_path = dump_json(workflows_dir / f"{workflow_id}.json", structural)
        jsonld_path = dump_json(workflows_dir / f"{workflow_id}.jsonld", _workflow_jsonld(structural))
        ttl_path = write_text(workflows_dir / f"{workflow_id}.ttl", _workflow_turtle(structural))
        generated.extend([json_path, jsonld_path, ttl_path])
    return {
        "status": "generated",
        "output_dir": str(target),
        "workflow_count": len(graph["workflows"]),
        "source_node_count": len(graph["nodes"]),
        "source_edge_count": len(graph["source_edges"]),
        "mapped_occurrence_count": len(graph["anchor_edges"]),
        "approved_anchor_count": sum(1 for anchor in graph["anchors"] if anchor["state"] == "approved_h2kg"),
        "reviewed_anchor_count": sum(1 for anchor in graph["anchors"] if anchor["state"] == "reviewed_decode"),
        "semantic_role_conflict_count": len(role_conflicts),
        "semantic_projection_count": len(graph["semantic_edges"]),
        "edge_classification_count": len(graph["edge_registry"]),
        "concept_registry_count": registry["counts"]["concept_count"],
        "validation_status": validation["status"],
        "multiscale_interface": interface,
        "generated_files": [str(path) for path in generated],
    }


def apply_decode_alias_curation(
    ontology_path: str | Path,
    mapping_config_path: str | Path,
) -> dict[str, Any]:
    """Apply only explicitly curated DECODE aliases to the H2KG source document."""
    ontology_path = Path(ontology_path)
    items = load_json(ontology_path)
    if not isinstance(items, list):
        raise ValueError(f"Expected a JSON-LD array in {ontology_path}")
    config = try_load_yaml(Path(mapping_config_path), {"alias_curation": []})
    by_iri = {str(item.get("@id", "")): item for item in items if isinstance(item, dict)}
    added: list[dict[str, str]] = []
    for entry in config.get("alias_curation", []):
        if not isinstance(entry, dict):
            continue
        target = str(entry.get("target_iri", ""))
        item = by_iri.get(target)
        if item is None:
            raise ValueError(f"Alias target is not present in H2KG source: {target}")
        existing = {value.lower() for value in _literal_values(item.get(SKOS_ALT_LABEL, []))}
        aliases = entry.get("aliases", [])
        if not isinstance(aliases, list):
            aliases = [aliases]
        for alias in aliases:
            alias = str(alias).strip()
            if alias and alias.lower() not in existing:
                item.setdefault(SKOS_ALT_LABEL, []).append({"@language": "en", "@value": alias})
                existing.add(alias.lower())
                added.append({"target_iri": target, "alias": alias})
    dump_json(ontology_path, items)
    return {"status": "updated", "ontology": str(ontology_path), "added_aliases": added, "count": len(added)}


def _parse_graphml(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    root = ET.fromstring(raw)
    graph = root.find(f"{GRAPHML_NS}graph")
    if graph is None:
        raise ValueError(f"GraphML graph element missing: {path}")
    workflow_id = _slug(path.stem)
    workflow_iri = f"{DECODE_NS}{workflow_id}"
    nodes = []
    for element in graph.findall(f"{GRAPHML_NS}node"):
        source_id = element.attrib["id"]
        description = _data_text(element, "d4")
        label, native_category = _source_label_and_category(description, element)
        nodes.append(
            {
                "id": f"{workflow_id}::{source_id}",
                "iri": f"{workflow_iri}/node/{source_id}",
                "source_id": source_id,
                "label": label,
                "native_category": native_category,
                "description": description,
                "shape": _node_shape(element),
            }
        )
    edges = []
    for index, element in enumerate(graph.findall(f"{GRAPHML_NS}edge")):
        source = element.attrib["source"]
        target = element.attrib["target"]
        edge_id = element.attrib.get("id", f"edge-{index}")
        edges.append(
            {
                "id": f"{workflow_id}::{edge_id}",
                "source_id": source,
                "target_id": target,
                "source": f"{workflow_id}::{source}",
                "target": f"{workflow_id}::{target}",
                "description": _data_text(element, "d8"),
            }
        )
    return {
        "id": workflow_id,
        "iri": workflow_iri,
        "title": _humanize_filename(path.stem),
        "source_filename": path.name,
        "source_sha256": digest,
        "method_family": _method_family(path.stem),
        "directed": graph.attrib.get("edgedefault", "directed") == "directed",
        "nodes": nodes,
        "edges": edges,
    }


def _federate(
    snapshot: dict[str, Any],
    mappings: dict[tuple[str, str], dict[str, Any]],
    semantic_projections: dict[tuple[str, str, str], dict[str, Any]],
    default_alignment: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    nodes: list[dict[str, Any]] = []
    source_edges: list[dict[str, Any]] = []
    anchor_edges: list[dict[str, Any]] = []
    semantic_edges: list[dict[str, Any]] = []
    anchors: dict[str, dict[str, Any]] = {}
    matrix_rows: list[dict[str, str]] = []
    workflows: list[dict[str, Any]] = []
    for source_workflow in snapshot.get("workflows", []):
        workflow_id = source_workflow["id"]
        workflow_nodes = source_workflow.get("nodes", [])
        mapped_count = 0
        for source_node in workflow_nodes:
            mapping = mappings.get((_normal(source_node["label"]), _normal(source_node.get("native_category", ""))))
            if mapping is None:
                mapping = mappings.get((_normal(source_node["label"]), ""))
            if mapping is None:
                mapping = _default_decode_mapping(source_node, default_alignment)
            if mapping is not None:
                mapping = _with_semantic_role(mapping, source_node, default_alignment)
            mapping_state = mapping.get("state", "unresolved") if mapping else "unresolved"
            anchor_id = mapping.get("anchor_iri") if mapping else None
            decision = mapping.get("decision", _default_decision(mapping_state)) if mapping else "unresolved"
            node = {
                **source_node,
                "kind": "occurrence",
                "workflow_id": workflow_id,
                "visual_category": _visual_category(source_node),
                "mapping_state": mapping_state,
                "anchor_id": anchor_id,
                "decision": decision,
                "canonical_role_iri": mapping.get("canonical_role_iri", "") if mapping else "",
                "semantic_role": mapping.get("semantic_role", "") if mapping else "",
                "role_assignment": mapping.get("role_assignment", "") if mapping else "",
                "confidence": mapping.get("confidence", "unreviewed") if mapping else "unreviewed",
                "mapping_evidence": mapping.get("evidence", "No reviewed mapping decision.") if mapping else "No reviewed mapping decision.",
            }
            nodes.append(node)
            matrix_rows.append(
                {
                    "workflow_id": workflow_id,
                    "source_filename": source_workflow["source_filename"],
                    "source_node_id": source_node["source_id"],
                    "source_label": source_node["label"],
                    "native_category": source_node.get("native_category", ""),
                    "mapping_state": mapping_state,
                    "decision": decision,
                    "anchor_iri": anchor_id or "",
                    "anchor_label": mapping.get("anchor_label", "") if mapping else "",
                    "canonical_role_iri": node["canonical_role_iri"],
                    "semantic_role": node["semantic_role"],
                    "role_assignment": node["role_assignment"],
                    "confidence": node["confidence"],
                    "evidence": node["mapping_evidence"],
                }
            )
            if anchor_id:
                mapped_count += 1
                anchor = anchors.setdefault(
                    anchor_id,
                    {
                        "id": anchor_id,
                        "kind": "anchor",
                        "label": mapping.get("anchor_label") or _last_segment(anchor_id),
                        "state": mapping_state,
                        "decision": decision,
                        "canonical_role_iri": node["canonical_role_iri"],
                        "semantic_role": node["semantic_role"],
                        "confidence": node["confidence"],
                        "evidence": mapping.get("evidence", ""),
                        "occurrence_ids": [],
                    },
                )
                anchor["occurrence_ids"].append(source_node["id"])
                anchor_edges.append(
                    {
                        "id": f"anchor::{source_node['id']}::{_short_hash(anchor_id)}",
                        "workflow_id": workflow_id,
                        "source": source_node["id"],
                        "target": anchor_id,
                        "type": "occurrence_anchor_mapping",
                    }
                )
        workflow_source_edges = source_workflow.get("edges", [])
        source_edges.extend({**edge, "workflow_id": workflow_id, "type": "source_dependency", "source_kind": "source_graphml"} for edge in workflow_source_edges)
        workflows.append(
            {
                "id": workflow_id,
                "iri": source_workflow["iri"],
                "title": source_workflow["title"],
                "source_filename": source_workflow["source_filename"],
                "source_sha256": source_workflow["source_sha256"],
                "method_family": source_workflow["method_family"],
                "source_status": "preserved",
                "mapping_status": "mapped" if mapped_count else "unresolved",
                "source_node_count": len(workflow_nodes),
                "source_edge_count": len(source_workflow.get("edges", [])),
                "mapped_anchor_count": mapped_count,
                "cross_workflow_connection_count": 0,
            }
        )
    for workflow in workflows:
        workflow["cross_workflow_connection_count"] = sum(
            max(0, len(anchors[anchor_id]["occurrence_ids"]) - 1)
            for anchor_id in {node.get("anchor_id") for node in nodes if node.get("workflow_id") == workflow["id"] and node.get("anchor_id")}
        )
    graph = {
        "schema_version": "1.0",
        "generated_on": date.today().isoformat(),
        "description": "Federated DECODE workflow occurrence graph. Source GraphML dependencies are preserved; mappings are explicit reviewed decisions.",
        "raw_graphml_redistributed": False,
        "workflows": workflows,
        "nodes": nodes,
        "anchors": sorted(anchors.values(), key=lambda item: (item["label"].lower(), item["id"])),
        "source_edges": source_edges,
        "anchor_edges": anchor_edges,
        "semantic_edges": semantic_edges,
        "anchor_index": {anchor_id: anchor["occurrence_ids"] for anchor_id, anchor in anchors.items()},
        "counts": {
            "workflow_count": len(workflows),
            "source_node_count": len(nodes),
            "source_edge_count": len(source_edges),
            "mapped_occurrence_count": len(anchor_edges),
            "anchor_count": len(anchors),
            "semantic_projection_count": len(semantic_edges),
        },
    }
    return graph, matrix_rows


def _build_edge_alignment(
    graph: dict[str, Any],
    explicit_projections: dict[tuple[str, str, str], dict[str, Any]],
) -> None:
    """Classify every preserved dependency without altering its source topology."""
    nodes_by_id = {node["id"]: node for node in graph["nodes"]}
    source_keys = {
        (edge["workflow_id"], nodes_by_id[edge["source"]]["source_id"], nodes_by_id[edge["target"]]["source_id"])
        for edge in graph["source_edges"]
        if edge["source"] in nodes_by_id and edge["target"] in nodes_by_id
    }
    unknown_overrides = sorted(set(explicit_projections) - source_keys)
    if unknown_overrides:
        raise ValueError(
            "A reviewed semantic projection must cite a preserved directed DECODE dependency: "
            + "; ".join("::".join(key) for key in unknown_overrides)
        )

    projection_nodes: dict[str, dict[str, Any]] = {}
    semantic_edges: list[dict[str, Any]] = []
    registry: list[dict[str, Any]] = []
    for edge in graph["source_edges"]:
        source = nodes_by_id[edge["source"]]
        target = nodes_by_id[edge["target"]]
        override = explicit_projections.get((edge["workflow_id"], source["source_id"], target["source_id"]))
        classification = _classify_decode_edge(edge, source, target, override, projection_nodes)
        semantic_edges.extend(classification["semantic_edges"])
        registry.append(classification["registry"])

    graph["projection_nodes"] = sorted(projection_nodes.values(), key=lambda node: node["id"])
    graph["semantic_edges"] = semantic_edges
    graph["edge_registry"] = registry
    outcome_counts = Counter(row["projection_outcome"] for row in registry)
    graph["counts"].update(
        {
            "semantic_projection_count": len(semantic_edges),
            "edge_classification_count": len(registry),
            "edge_outcome_counts": dict(sorted(outcome_counts.items())),
            "property_value_proxy_count": len(projection_nodes),
        }
    )


def _classify_decode_edge(
    edge: dict[str, Any],
    source: dict[str, Any],
    target: dict[str, Any],
    override: dict[str, Any] | None,
    projection_nodes: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Project one source dependency using H2KG roles, PROV-O, or structural retention."""
    source_role = str(source.get("semantic_role", ""))
    target_role = str(target.get("semantic_role", ""))
    semantic_edges: list[dict[str, Any]] = []

    def direct(
        predicate: str,
        semantic_source: str,
        semantic_target: str,
        outcome: str,
        pattern: str,
        rationale: str,
        confidence: str = "rule_curated",
        review_status: str = "classified",
    ) -> None:
        semantic_edges.append(
            _semantic_edge(
                edge,
                semantic_source,
                semantic_target,
                predicate,
                outcome,
                pattern,
                rationale,
                confidence,
                review_status,
            )
        )

    if override:
        semantic_source = f"{edge['workflow_id']}::{override.get('semantic_source_node_id', source['source_id'])}"
        semantic_target = f"{edge['workflow_id']}::{override.get('semantic_target_node_id', target['source_id'])}"
        semantic_source, semantic_target = _normalise_predicate_direction(
            str(override["predicate"]), semantic_source, semantic_target, source, target
        )
        direct(
            str(override["predicate"]),
            semantic_source,
            semantic_target,
            "h2kg_direct",
            "explicit_override",
            str(override.get("evidence", "Explicit reviewed semantic projection.")),
            "reviewed",
            "reviewed",
        )
    elif source_role == "Measurement" and target_role == "Property":
        direct(H2KG + "measures", source["id"], target["anchor_id"], "h2kg_direct", "measurement_property", "Measurement occurrence measures the mapped property.")
    elif source_role == "Property" and target_role == "Measurement":
        direct(H2KG + "measures", target["id"], source["anchor_id"], "h2kg_direct", "measurement_property_reversed", "Source property is a measured outcome; H2KG direction is measurement to property.")
    elif _is_activity(source) and _is_activity(target):
        direct(PROV_WAS_INFORMED_BY, target["id"], source["id"], "prov_derivation", "activity_sequence", "Target activity follows the source activity in the preserved workflow.")
    elif _is_activity(target):
        if source_role == "Matter":
            direct(H2KG + "hasInputMaterial", target["id"], source["id"], "h2kg_direct", "activity_input_material", "Activity consumes the source material; H2KG direction is activity to material.")
        elif source_role == "Parameter":
            direct(H2KG + "hasParameter", target["id"], source["id"], "h2kg_direct", "activity_parameter", "Activity uses the source parameter; H2KG direction is activity to parameter.")
        elif source_role == "Instrument":
            direct(H2KG + "usesInstrument", target["id"], source["id"], "h2kg_direct", "activity_instrument", "Activity uses the source instrument; H2KG direction is activity to instrument.")
        elif source_role == "Data":
            direct(H2KG + "hasInputData", target["id"], source["id"], "h2kg_direct", "activity_input_data", "Activity consumes the source data; H2KG direction is activity to data.")
        elif source_role == "Metadata":
            direct(H2KG + "hasMetadata", target["id"], source["id"], "h2kg_direct", "activity_metadata", "Source metadata describes the activity; H2KG direction is described resource to metadata.")
        elif source_role == "Property":
            proxy = _property_value_proxy(source, projection_nodes)
            direct(H2KG + "hasInputData", target["id"], proxy["id"], "h2kg_reified", "property_value_input", "Property-valued source is reified as a DataPoint consumed by the activity.")
            direct(H2KG + "ofProperty", proxy["id"], source["anchor_id"], "h2kg_reified", "property_value_type", "Reified DataPoint is typed by the source property anchor.")
    elif _is_activity(source):
        if target_role == "Matter":
            direct(H2KG + "hasOutputMaterial", source["id"], target["id"], "h2kg_direct", "activity_output_material", "Activity produces the target material.")
        elif target_role == "Parameter":
            direct(H2KG + "hasParameter", source["id"], target["id"], "h2kg_direct", "activity_parameter", "Target parameter describes the activity.")
        elif target_role == "Instrument":
            direct(H2KG + "usesInstrument", source["id"], target["id"], "h2kg_direct", "activity_instrument", "Target instrument is used by the activity.")
        elif target_role == "Data":
            direct(H2KG + "hasOutputData", source["id"], target["id"], "h2kg_direct", "activity_output_data", "Activity produces the target data.")
        elif target_role == "Metadata":
            direct(H2KG + "hasMetadata", source["id"], target["id"], "h2kg_direct", "activity_metadata", "Target metadata describes the activity.")
        elif target_role == "Property":
            proxy = _property_value_proxy(target, projection_nodes)
            direct(H2KG + "hasOutputData", source["id"], proxy["id"], "h2kg_reified", "property_value_output", "Activity produces a DataPoint representing the target property.")
            direct(H2KG + "ofProperty", proxy["id"], target["anchor_id"], "h2kg_reified", "property_value_type", "Reified DataPoint is typed by the target property anchor.")
    elif source_role == "Data" and target_role == "Data":
        direct(PROV_WAS_DERIVED_FROM, target["id"], source["id"], "prov_derivation", "data_derivation", "Target data is derived from source data in the preserved workflow.")
    elif source_role == "Property" and target_role == "Property":
        source_proxy = _property_value_proxy(source, projection_nodes)
        target_proxy = _property_value_proxy(target, projection_nodes)
        direct(PROV_WAS_DERIVED_FROM, target_proxy["id"], source_proxy["id"], "h2kg_reified", "property_value_derivation", "Property-valued workflow dependency is represented as provenance between DataPoint proxies.")
        direct(H2KG + "ofProperty", source_proxy["id"], source["anchor_id"], "h2kg_reified", "property_value_type", "Source DataPoint proxy is typed by its property anchor.")
        direct(H2KG + "ofProperty", target_proxy["id"], target["anchor_id"], "h2kg_reified", "property_value_type", "Target DataPoint proxy is typed by its property anchor.")
    elif source_role == "Data" and target_role == "Property":
        proxy = _property_value_proxy(target, projection_nodes)
        direct(PROV_WAS_DERIVED_FROM, proxy["id"], source["id"], "h2kg_reified", "data_to_property_value", "Property-valued result is reified as a DataPoint derived from source data.")
        direct(H2KG + "ofProperty", proxy["id"], target["anchor_id"], "h2kg_reified", "property_value_type", "Reified DataPoint is typed by the target property anchor.")
    elif source_role == "Property" and target_role == "Data":
        proxy = _property_value_proxy(source, projection_nodes)
        direct(PROV_WAS_DERIVED_FROM, target["id"], proxy["id"], "h2kg_reified", "property_value_to_data", "Target data is derived from a reified property-valued source.")
        direct(H2KG + "ofProperty", proxy["id"], source["anchor_id"], "h2kg_reified", "property_value_type", "Reified DataPoint is typed by the source property anchor.")

    if not semantic_edges:
        rationale = "The preserved dependency has no activity or data-flow context sufficient for a scientifically defensible H2KG or PROV-O predicate."
        outcome, pattern, confidence, review_status = "decode_structural_only", "structural_dependency", "context_required", "classified"
    else:
        outcome = semantic_edges[0]["projection_outcome"]
        pattern = semantic_edges[0]["projection_pattern"]
        confidence = semantic_edges[0]["confidence"]
        review_status = semantic_edges[0]["review_status"]
        rationale = semantic_edges[0]["evidence"]
    return {
        "semantic_edges": semantic_edges,
        "registry": {
            "source_dependency_id": edge["id"],
            "workflow_id": edge["workflow_id"],
            "source_kind": edge.get("source_kind", "source_graphml"),
            "source_occurrence_id": source["id"],
            "source_graphml_id": source["source_id"],
            "source_label": source["label"],
            "source_semantic_role": source_role,
            "source_anchor_iri": source.get("anchor_id", ""),
            "target_occurrence_id": target["id"],
            "target_graphml_id": target["source_id"],
            "target_label": target["label"],
            "target_semantic_role": target_role,
            "target_anchor_iri": target.get("anchor_id", ""),
            "source_description": edge.get("description", ""),
            "projection_outcome": outcome,
            "projection_pattern": pattern,
            "semantic_predicates": "; ".join(sorted({item["predicate"] for item in semantic_edges})),
            "semantic_edge_ids": [item["id"] for item in semantic_edges],
            "semantic_direction": _semantic_direction(edge, semantic_edges),
            "confidence": confidence,
            "review_status": review_status,
            "rationale": rationale,
        },
    }


def _is_activity(node: dict[str, Any]) -> bool:
    return str(node.get("semantic_role", "")) in ACTIVITY_ROLES


def _normalise_predicate_direction(
    predicate: str,
    semantic_source: str,
    semantic_target: str,
    source: dict[str, Any],
    target: dict[str, Any],
) -> tuple[str, str]:
    """Apply H2KG direction to a reviewed predicate while retaining source provenance."""
    local_name = _last_segment(predicate)
    reversible_inputs = {
        ("hasInputMaterial", "Matter"),
        ("hasParameter", "Parameter"),
        ("usesInstrument", "Instrument"),
        ("hasInputData", "Data"),
        ("hasMetadata", "Metadata"),
        ("measures", "Property"),
    }
    if (local_name, str(source.get("semantic_role", ""))) in reversible_inputs and _is_activity(target):
        return semantic_target, semantic_source
    return semantic_source, semantic_target


def _property_value_proxy(node: dict[str, Any], projection_nodes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    proxy_id = f"projection::datapoint::{node['id']}"
    return projection_nodes.setdefault(
        proxy_id,
        {
            "id": proxy_id,
            "iri": f"{node['iri']}/data-point",
            "label": f"{node['label']} value",
            "kind": "value_proxy",
            "workflow_id": node["workflow_id"],
            "source_occurrence_id": node["id"],
            "source_anchor_iri": node.get("anchor_id", ""),
            "canonical_role_iri": H2KG + "DataPoint",
            "semantic_role": "DataPoint",
            "rdf_type": H2KG + "DataPoint",
            "description": "Derived semantic projection node. It represents a value of the preserved DECODE property occurrence and is not a source GraphML node.",
        },
    )


def _semantic_edge(
    source_edge: dict[str, Any],
    source: str,
    target: str,
    predicate: str,
    outcome: str,
    pattern: str,
    evidence: str,
    confidence: str,
    review_status: str,
) -> dict[str, Any]:
    return {
        "id": f"semantic::{source_edge['id']}::{_short_hash(source + '|' + target + '|' + predicate + '|' + pattern)}",
        "workflow_id": source_edge["workflow_id"],
        "source": source,
        "target": target,
        "predicate": predicate,
        "label": _last_segment(predicate),
        "type": "semantic_projection",
        "source_dependency_id": source_edge["id"],
        "projection_outcome": outcome,
        "projection_pattern": pattern,
        "evidence": evidence,
        "confidence": confidence,
        "review_status": review_status,
    }


def _semantic_direction(source_edge: dict[str, Any], semantic_edges: list[dict[str, Any]]) -> str:
    if not semantic_edges:
        return "not_projected"
    if len(semantic_edges) > 1:
        return "reified_projection"
    semantic = semantic_edges[0]
    if semantic["source"] == source_edge["source"] and semantic["target"] == source_edge["target"]:
        return "same_as_source"
    if semantic["source"] == source_edge["target"] and semantic["target"] == source_edge["source"]:
        return "reversed_from_source"
    return "derived_projection"


def _validate_federated_graph(snapshot: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    source_pairs = {
        (workflow["id"], edge["source"], edge["target"])
        for workflow in snapshot.get("workflows", [])
        for edge in workflow.get("edges", [])
    }
    preserved_pairs = {
        (edge["workflow_id"], edge["source"], edge["target"])
        for edge in graph["source_edges"]
        if edge.get("source_kind", "source_graphml") == "source_graphml"
    }
    node_ids = {node["id"] for node in graph["nodes"]}
    projection_node_ids = {node["id"] for node in graph.get("projection_nodes", [])}
    anchor_ids = {anchor["id"] for anchor in graph["anchors"]}
    semantic_endpoint_ids = node_ids | projection_node_ids | anchor_ids
    invalid_edges = [edge["id"] for edge in graph["source_edges"] if edge["source"] not in node_ids or edge["target"] not in node_ids]
    invalid_semantic_edges = [
        edge["id"]
        for edge in graph["semantic_edges"]
        if edge["source"] not in semantic_endpoint_ids or edge["target"] not in semantic_endpoint_ids
    ]
    source_dependency_ids = {edge["id"] for edge in graph["source_edges"]}
    untraceable_semantic_edges = [
        edge["id"]
        for edge in graph["semantic_edges"]
        if edge.get("source_dependency_id") not in source_dependency_ids
    ]
    unexpected_cross_links = [
        edge["id"]
        for edge in graph["source_edges"]
        if edge["source"].split("::", 1)[0] != edge["target"].split("::", 1)[0]
    ]
    overview = graph.get("semantic_overview", {})
    overview_occurrence_ids = {
        occurrence_id
        for node in overview.get("nodes", [])
        for occurrence_id in node.get("occurrence_ids", [])
    }
    overview_source_edge_ids = [
        source_edge_id
        for edge in overview.get("source_edges", [])
        for source_edge_id in edge.get("source_dependency_ids", [])
    ]
    missing_overview_occurrence_ids = sorted(node_ids - overview_occurrence_ids)
    unexpected_overview_occurrence_ids = sorted(overview_occurrence_ids - node_ids)
    missing_overview_source_edge_ids = sorted(source_dependency_ids - set(overview_source_edge_ids))
    duplicated_overview_source_edge_ids = sorted(
        edge_id for edge_id, count in Counter(overview_source_edge_ids).items() if count != 1
    )
    semantic_role_conflicts = graph.get("semantic_role_conflicts", [])
    edge_registry = graph.get("edge_registry", [])
    registry_ids = [row.get("source_dependency_id", "") for row in edge_registry]
    invalid_registry_outcomes = [
        row.get("source_dependency_id", "")
        for row in edge_registry
        if row.get("projection_outcome") not in EDGE_OUTCOMES
    ]
    missing_edge_classifications = sorted(source_dependency_ids - set(registry_ids))
    duplicate_edge_classifications = sorted(
        edge_id for edge_id, count in Counter(registry_ids).items() if count != 1
    )
    registry_semantic_edge_ids = {
        edge_id
        for row in edge_registry
        for edge_id in row.get("semantic_edge_ids", [])
    }
    unregistered_semantic_edge_ids = sorted(
        edge["id"] for edge in graph["semantic_edges"] if edge["id"] not in registry_semantic_edge_ids
    )
    status = "passed" if (
        source_pairs == preserved_pairs
        and not invalid_edges
        and not invalid_semantic_edges
        and not untraceable_semantic_edges
        and not unexpected_cross_links
        and not missing_overview_occurrence_ids
        and not unexpected_overview_occurrence_ids
        and not missing_overview_source_edge_ids
        and not duplicated_overview_source_edge_ids
        and not semantic_role_conflicts
        and not missing_edge_classifications
        and not duplicate_edge_classifications
        and not invalid_registry_outcomes
        and not unregistered_semantic_edge_ids
    ) else "failed"
    return {
        "status": status,
        "source_workflow_count": len(snapshot.get("workflows", [])),
        "source_node_count": sum(len(workflow.get("nodes", [])) for workflow in snapshot.get("workflows", [])),
        "source_edge_count": len(source_pairs),
        "preserved_source_edge_count": len(preserved_pairs),
        "missing_source_pairs": sorted(source_pairs - preserved_pairs),
        "unexpected_source_pairs": sorted(preserved_pairs - source_pairs),
        "invalid_source_edge_ids": invalid_edges,
        "invalid_semantic_edge_ids": invalid_semantic_edges,
        "untraceable_semantic_edge_ids": untraceable_semantic_edges,
        "unexpected_cross_workflow_source_edge_ids": unexpected_cross_links,
        "missing_semantic_overview_occurrence_ids": missing_overview_occurrence_ids,
        "unexpected_semantic_overview_occurrence_ids": unexpected_overview_occurrence_ids,
        "missing_semantic_overview_source_edge_ids": missing_overview_source_edge_ids,
        "duplicated_semantic_overview_source_edge_ids": duplicated_overview_source_edge_ids,
        "semantic_role_conflicts": semantic_role_conflicts,
        "edge_classification_count": len(edge_registry),
        "missing_edge_classifications": missing_edge_classifications,
        "duplicated_edge_classifications": duplicate_edge_classifications,
        "invalid_edge_registry_outcomes": invalid_registry_outcomes,
        "unregistered_semantic_edge_ids": unregistered_semantic_edge_ids,
        "edge_outcome_counts": dict(sorted(Counter(row.get("projection_outcome", "") for row in edge_registry).items())),
        "mapping_policy": "Cross-workflow traversal is available only through explicit approved_h2kg or reviewed_decode anchor mappings.",
    }


def _build_semantic_overview(graph: dict[str, Any]) -> dict[str, Any]:
    """Create a derived, provenance-preserving view over shared semantic anchors."""
    nodes_by_id = {node["id"]: node for node in graph["nodes"]}
    anchors_by_id = {anchor["id"]: anchor for anchor in graph["anchors"]}
    overview_nodes: dict[str, dict[str, Any]] = {}

    def overview_id(node: dict[str, Any]) -> str:
        return str(node.get("anchor_id") or f"unresolved::{node['id']}")

    for occurrence in graph["nodes"]:
        node_id = overview_id(occurrence)
        anchor = anchors_by_id.get(node_id)
        overview = overview_nodes.setdefault(
            node_id,
            {
                "id": node_id,
                "kind": "semantic_anchor" if anchor else "unresolved_occurrence",
                "label": anchor["label"] if anchor else occurrence["label"],
                "state": anchor["state"] if anchor else occurrence["mapping_state"],
                "decision": anchor["decision"] if anchor else occurrence["decision"],
                "canonical_role_iri": anchor.get("canonical_role_iri", "") if anchor else occurrence.get("canonical_role_iri", ""),
                "semantic_role": anchor.get("semantic_role", "") if anchor else occurrence.get("semantic_role", ""),
                "confidence": anchor.get("confidence", "unreviewed") if anchor else occurrence.get("confidence", "unreviewed"),
                "evidence": anchor.get("evidence", "") if anchor else occurrence.get("mapping_evidence", ""),
                "occurrence_ids": [],
                "workflow_ids": [],
                "visual_categories": [],
                "semantic_roles": [],
                "canonical_role_iris": [],
            },
        )
        overview["occurrence_ids"].append(occurrence["id"])
        overview["workflow_ids"].append(occurrence["workflow_id"])
        overview["visual_categories"].append(occurrence["visual_category"])
        if occurrence.get("semantic_role"):
            overview["semantic_roles"].append(occurrence["semantic_role"])
        if occurrence.get("canonical_role_iri"):
            overview["canonical_role_iris"].append(occurrence["canonical_role_iri"])

    for node in overview_nodes.values():
        node["occurrence_ids"].sort()
        node["workflow_ids"] = sorted(set(node["workflow_ids"]))
        node["visual_categories"] = sorted(set(node["visual_categories"]))
        node["semantic_roles"] = sorted(set(node["semantic_roles"]))
        node["canonical_role_iris"] = sorted(set(node["canonical_role_iris"]))
        node["role_conflict"] = len(node["canonical_role_iris"]) > 1
        node["conflicting_canonical_role_iris"] = list(node["canonical_role_iris"]) if node["role_conflict"] else []
        if node["role_conflict"]:
            node["semantic_role"] = "Mixed role"
            node["canonical_role_iri"] = ""
        node["occurrence_count"] = len(node["occurrence_ids"])

    source_edges: dict[tuple[str, str], dict[str, Any]] = {}
    for edge in graph["source_edges"]:
        source = overview_id(nodes_by_id[edge["source"]])
        target = overview_id(nodes_by_id[edge["target"]])
        record = source_edges.setdefault(
            (source, target),
            {
                "id": f"semantic-overview::source::{_short_hash(source + '|' + target)}",
                "source": source,
                "target": target,
                "type": "aggregated_source_dependency",
                "source_dependency_ids": [],
                "occurrence_pairs": [],
                "workflow_ids": [],
            },
        )
        record["source_dependency_ids"].append(edge["id"])
        record["occurrence_pairs"].append(
            {
                "source_occurrence_id": edge["source"],
                "target_occurrence_id": edge["target"],
                "source_dependency_id": edge["id"],
                "workflow_id": edge["workflow_id"],
            }
        )
        record["workflow_ids"].append(edge["workflow_id"])

    semantic_edges: dict[tuple[str, str, str], dict[str, Any]] = {}
    for edge in graph["semantic_edges"]:
        # Reified value projections can terminate at a derived DataPoint proxy or
        # semantic anchor. They are rendered in the source view and registry;
        # this occurrence-only overview intentionally aggregates direct edges.
        if edge["source"] not in nodes_by_id or edge["target"] not in nodes_by_id:
            continue
        source = overview_id(nodes_by_id[edge["source"]])
        target = overview_id(nodes_by_id[edge["target"]])
        predicate = edge["predicate"]
        record = semantic_edges.setdefault(
            (source, target, predicate),
            {
                "id": f"semantic-overview::projection::{_short_hash(source + '|' + target + '|' + predicate)}",
                "source": source,
                "target": target,
                "predicate": predicate,
                "label": edge["label"],
                "type": "approved_semantic_projection",
                "semantic_projection_ids": [],
                "source_dependency_ids": [],
                "workflow_ids": [],
                "projection_outcomes": [],
            },
        )
        record["semantic_projection_ids"].append(edge["id"])
        record["source_dependency_ids"].append(edge["source_dependency_id"])
        record["workflow_ids"].append(edge["workflow_id"])
        record["projection_outcomes"].append(edge["projection_outcome"])

    for edge in [*source_edges.values(), *semantic_edges.values()]:
        edge["workflow_ids"] = sorted(set(edge["workflow_ids"]))
        edge["occurrence_count"] = len(edge.get("source_dependency_ids", []))
        if "projection_outcomes" in edge:
            outcomes = sorted(set(edge["projection_outcomes"]))
            edge["projection_outcomes"] = outcomes
            edge["projection_outcome"] = outcomes[0] if len(outcomes) == 1 else "mixed"

    role_conflicts = [
        {
            "anchor_id": node["id"],
            "label": node["label"],
            "state": node["state"],
            "semantic_roles": node["semantic_roles"],
            "canonical_role_iris": node["conflicting_canonical_role_iris"],
            "occurrence_ids": node["occurrence_ids"],
        }
        for node in overview_nodes.values()
        if node["role_conflict"]
    ]
    return {
        "description": "Derived semantic overview. Every node and edge retains occurrence- and source-dependency provenance.",
        "nodes": sorted(overview_nodes.values(), key=lambda node: (node["label"].lower(), node["id"])),
        "source_edges": sorted(source_edges.values(), key=lambda edge: edge["id"]),
        "semantic_edges": sorted(semantic_edges.values(), key=lambda edge: edge["id"]),
        "role_conflicts": sorted(role_conflicts, key=lambda row: row["anchor_id"]),
    }


def _duplicate_occurrence_audit(
    graph: dict[str, Any],
    role_conflicts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Record repeated source labels within a workflow without treating them as duplicates in source data."""
    nodes_by_id = {node["id"]: node for node in graph["nodes"]}
    conflicting_anchor_ids = {row["anchor_id"] for row in role_conflicts}
    edges_by_node: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in graph["source_edges"]:
        edges_by_node[edge["source"]].append(edge)
        edges_by_node[edge["target"]].append(edge)

    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for node in graph["nodes"]:
        groups[(node["workflow_id"], _normal(node["label"]), _normal(node.get("native_category", "")))].append(node)

    audit: list[dict[str, Any]] = []
    for (workflow_id, _, _), occurrences in groups.items():
        if len(occurrences) < 2:
            continue
        contexts: set[tuple[tuple[str, ...], tuple[str, ...]]] = set()
        for occurrence in occurrences:
            incoming = sorted(
                nodes_by_id[edge["source"]]["label"]
                for edge in edges_by_node[occurrence["id"]]
                if edge["target"] == occurrence["id"]
            )
            outgoing = sorted(
                nodes_by_id[edge["target"]]["label"]
                for edge in edges_by_node[occurrence["id"]]
                if edge["source"] == occurrence["id"]
            )
            contexts.add((tuple(incoming), tuple(outgoing)))
        anchor_ids = sorted({occurrence.get("anchor_id", "") for occurrence in occurrences if occurrence.get("anchor_id")})
        audit.append(
            {
                "id": f"duplicate-occurrence::{workflow_id}::{_short_hash(occurrences[0]['label'] + '|' + occurrences[0].get('native_category', ''))}",
                "workflow_id": workflow_id,
                "source_label": occurrences[0]["label"],
                "native_category": occurrences[0].get("native_category", ""),
                "occurrence_ids": sorted(occurrence["id"] for occurrence in occurrences),
                "occurrence_count": len(occurrences),
                "anchor_ids": anchor_ids,
                "collapse_eligible": len(anchor_ids) == 1,
                "semantic_role_conflict": any(anchor_id in conflicting_anchor_ids for anchor_id in anchor_ids),
                "context_classification": "same_direct_label_context" if len(contexts) == 1 else "distinct_branch_context",
                "direct_context_patterns": [
                    {"incoming_labels": list(incoming), "outgoing_labels": list(outgoing)}
                    for incoming, outgoing in sorted(contexts)
                ],
            }
        )
    return sorted(audit, key=lambda row: (row["workflow_id"], row["source_label"].lower(), row["native_category"]))


def _default_decision(mapping_state: str) -> str:
    if mapping_state == "approved_h2kg":
        return "existing_h2kg_mapping"
    if mapping_state == "reviewed_decode":
        return "reviewed_decode_anchor"
    return "unresolved"


def _default_decode_mapping(source_node: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any] | None:
    """Return a stable DECODE anchor only when the explicit fallback policy permits it."""
    if not policy.get("enabled", False):
        return None
    visual_category = _visual_category(source_node)
    role_by_category = policy.get("role_by_visual_category", {})
    category = _normal(source_node.get("native_category", "")) or visual_category
    anchor_key = f"{_slug(source_node['label'])}-{_slug(category)}"
    return {
        "state": "reviewed_decode",
        "decision": "reviewed_decode_anchor",
        "anchor_iri": f"{DECODE_NS}anchor/{anchor_key}",
        "anchor_label": source_node["label"],
        # The role is assigned after label-aware curation.  The GraphML visual
        # category remains source metadata and is only a final fallback.
        "canonical_role_iri": "",
        "semantic_role": "",
        "confidence": "reviewed_structural",
        "evidence": (
            "DECODE-specific concept retained as a stable reviewed anchor. "
            "Its source topology is preserved; no H2KG synonym or new public term was asserted."
        ),
    }


def _with_semantic_role(
    mapping: dict[str, Any],
    source_node: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    """Complete display-role metadata without changing a reviewed anchor decision."""
    result = dict(mapping)
    role = str(result.get("canonical_role_iri", "")).strip()
    if role:
        result.setdefault("role_assignment", "explicit_mapping")
    else:
        curation = policy.get("semantic_role_curation", {})
        override = _role_override(source_node, curation.get("overrides", []))
        if override:
            role = str(override.get("canonical_role_iri", "")).strip()
            result["role_assignment"] = str(override.get("id", "curated_override"))
        if not role:
            rule = _role_rule(source_node, curation.get("rules", []))
            if rule:
                role = str(rule.get("canonical_role_iri", "")).strip()
                result["role_assignment"] = str(rule.get("id", "curated_rule"))
        if not role:
            role = str(policy.get("role_by_visual_category", {}).get(_visual_category(source_node), "")).strip()
            result["role_assignment"] = "visual_category_fallback"
        if role:
            result["canonical_role_iri"] = role
    if role and not str(result.get("semantic_role", "")).strip():
        result["semantic_role"] = _last_segment(role)
    return result


def _role_override(source_node: dict[str, Any], overrides: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the most specific explicit semantic-role decision for a source concept."""
    label = _normal(source_node.get("label", ""))
    native_category = _normal(source_node.get("native_category", ""))
    for override in overrides:
        if not isinstance(override, dict):
            continue
        if _normal(str(override.get("source_label", ""))) != label:
            continue
        expected_category = _normal(str(override.get("native_category", "")))
        if expected_category and expected_category != native_category:
            continue
        return override
    return None


def _role_rule(source_node: dict[str, Any], rules: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Apply ordered, reviewable role rules without changing source topology."""
    label = str(source_node.get("label", ""))
    native_category = _normal(source_node.get("native_category", ""))
    visual_category = _visual_category(source_node)
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        native_categories = {_normal(str(value)) for value in rule.get("native_categories", [])}
        visual_categories = {_normal(str(value)) for value in rule.get("visual_categories", [])}
        if native_categories and native_category not in native_categories:
            continue
        if visual_categories and _normal(visual_category) not in visual_categories:
            continue
        pattern = str(rule.get("pattern", "")).strip()
        if pattern and not re.search(pattern, label, flags=re.IGNORECASE):
            continue
        if str(rule.get("canonical_role_iri", "")).strip():
            return rule
    return None


def _concept_registry(
    snapshot: dict[str, Any],
    graph: dict[str, Any],
    ontology_path: str | Path | None,
) -> dict[str, Any]:
    """Create an auditable, concept-level register from occurrence-level decisions."""
    registry_nodes = [node for node in graph["nodes"] if not node.get("is_derived_interface", False)]
    nodes_by_id = {node["id"]: node for node in registry_nodes}
    neighbors: dict[str, set[str]] = defaultdict(set)
    for edge in graph["source_edges"]:
        source = nodes_by_id.get(edge["source"])
        target = nodes_by_id.get(edge["target"])
        if source and target:
            neighbors[source["id"]].add(target["label"])
            neighbors[target["id"]].add(source["label"])

    h2kg_terms = _load_h2kg_terms(ontology_path)
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for node in registry_nodes:
        groups[(_normal(node["label"]), _normal(node.get("native_category", "")))].append(node)

    concepts: list[dict[str, Any]] = []
    for key, occurrences in sorted(groups.items(), key=lambda item: (item[1][0]["label"].lower(), item[0][1])):
        representative = occurrences[0]
        decisions = {node["decision"] for node in occurrences}
        if len(decisions) != 1:
            raise ValueError(f"Inconsistent DECODE decisions for {representative['label']!r}: {sorted(decisions)}")
        candidates = _h2kg_candidates(representative["label"], h2kg_terms)
        concepts.append(
            {
                "concept_id": f"{DECODE_NS}concept/{_slug(representative['label'])}-{_slug(key[1] or representative['visual_category'])}",
                "source_label": representative["label"],
                "native_category": representative.get("native_category", ""),
                "visual_category": representative["visual_category"],
                "occurrence_count": len(occurrences),
                "workflow_ids": sorted({node["workflow_id"] for node in occurrences}),
                "source_descriptions": sorted({node.get("description", "") for node in occurrences if node.get("description", "")}),
                "neighbor_context": sorted({label for node in occurrences for label in neighbors[node["id"]]})[:20],
                "decision": representative["decision"],
                "mapping_state": representative["mapping_state"],
                "anchor_iri": representative.get("anchor_id", ""),
                "canonical_role_iri": representative.get("canonical_role_iri", ""),
                "semantic_role": representative.get("semantic_role", ""),
                "role_assignment": representative.get("role_assignment", ""),
                "confidence": representative.get("confidence", "unreviewed"),
                "rationale": representative.get("mapping_evidence", ""),
                "candidate_h2kg_terms": candidates,
            }
        )
    counts = Counter(concept["decision"] for concept in concepts)
    return {
        "schema_version": "1.0",
        "generated_on": date.today().isoformat(),
        "description": "Concept-level DECODE-to-H2KG curation register. Candidate matches are not accepted mappings.",
        "counts": {"concept_count": len(concepts), "outcomes": dict(sorted(counts.items()))},
        "concepts": concepts,
    }


def _load_h2kg_terms(ontology_path: str | Path | None) -> list[dict[str, Any]]:
    if ontology_path is None or not Path(ontology_path).exists():
        return []
    items = load_json(Path(ontology_path))
    if not isinstance(items, list):
        return []
    terms: list[dict[str, Any]] = []
    for item in items:
        iri = str(item.get("@id", ""))
        if not iri.startswith(H2KG):
            continue
        labels = _literal_values(item.get(RDFS_LABEL, [])) + _literal_values(item.get(SKOS_PREF_LABEL, []))
        label = next((value for value in labels if value), "")
        if label:
            terms.append({"iri": iri, "label": label, "alt_labels": _literal_values(item.get(SKOS_ALT_LABEL, []))})
    return terms


def _literal_values(values: Any) -> list[str]:
    values = values if isinstance(values, list) else [values]
    return [str(value.get("@value", "")).strip() for value in values if isinstance(value, dict) and value.get("@value")]


def _h2kg_candidates(label: str, terms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scored: list[tuple[float, dict[str, Any]]] = []
    for term in terms:
        names = [term["label"], *term["alt_labels"]]
        score = max((lexical_score(label, name) for name in names), default=0.0)
        if score >= 0.55:
            scored.append((score, term))
    return [
        {"iri": term["iri"], "label": term["label"], "score": round(score, 3)}
        for score, term in sorted(scored, key=lambda item: (-item[0], item[1]["label"]))[:3]
    ]


def _index_mappings(entries: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict) or not entry.get("source_label") or not entry.get("anchor_iri"):
            continue
        state = entry.get("state", "unresolved")
        if state not in {"approved_h2kg", "reviewed_decode"}:
            continue
        result[(_normal(str(entry["source_label"])), _normal(str(entry.get("native_category", ""))))] = entry
    return result


def _index_semantic_projections(entries: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    result: dict[tuple[str, str, str], dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if all(isinstance(entry.get(key), str) and entry[key] for key in ("workflow_id", "source_node_id", "target_node_id", "predicate")):
            result[(entry["workflow_id"], entry["source_node_id"], entry["target_node_id"])] = entry
    return result


def _anchor_candidates(
    snapshot: dict[str, Any],
    mappings: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, str]]:
    occurrences: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for workflow in snapshot.get("workflows", []):
        for node in workflow.get("nodes", []):
            key = (_normal(node["label"]), _normal(node.get("native_category", "")))
            if key in mappings or (key[0], "") in mappings:
                continue
            occurrences[key].append((workflow["id"], node["source_id"]))
    candidates: list[dict[str, str]] = []
    for (normalized_label, normalized_category), nodes in occurrences.items():
        workflow_ids = sorted({workflow_id for workflow_id, _ in nodes})
        if len(workflow_ids) < 2:
            continue
        representative = next(
            node
            for workflow in snapshot.get("workflows", [])
            for node in workflow.get("nodes", [])
            if _normal(node["label"]) == normalized_label and _normal(node.get("native_category", "")) == normalized_category
        )
        candidates.append(
            {
                "source_label": representative["label"],
                "native_category": representative.get("native_category", ""),
                "visual_category": _visual_category(representative),
                "occurrence_count": str(len(nodes)),
                "workflow_count": str(len(workflow_ids)),
                "workflow_ids": "; ".join(workflow_ids),
                "recommended_state": "review_required",
                "note": "Candidate only. It does not create a cross-workflow link until an explicit mapping entry is reviewed and added.",
            }
        )
    return sorted(candidates, key=lambda item: (-int(item["workflow_count"]), item["source_label"].lower()))


def _data_text(element: ET.Element, key: str) -> str:
    data = next((item for item in element.findall(f"{GRAPHML_NS}data") if item.attrib.get("key") == key), None)
    return "".join(data.itertext()).strip() if data is not None else ""


def _node_shape(element: ET.Element) -> str:
    shape = element.find(f".//{YED_NS}Shape")
    return shape.attrib.get("type", "") if shape is not None else ""


def _source_label_and_category(description: str, element: ET.Element) -> tuple[str, str]:
    lines = [line.strip() for line in description.splitlines() if line.strip()]
    label = lines[0] if lines else "".join(element.itertext()).strip() or element.attrib["id"]
    internal = next((line for line in lines if line.lower().startswith("internal key:")), "")
    payload = internal.split(":", 1)[1].strip() if ":" in internal else ""
    category = ""
    if ":" in payload and not payload.endswith("0"):
        _, category = payload.rsplit(":", 1)
    return label, category.strip()


def _method_family(name: str) -> str:
    text = _normal(name)
    family_keywords = (
        ("tomography", ("tomography", "tomogram", "x ray ct", "neutron", "fib sem")),
        ("microscopy", ("sem", "tem", "afm", "microscopy", "clsm", "fib")),
        ("spectroscopy_scattering", ("xps", "xas", "saxs", "sans", "ftir", "raman", "waxs", "spectroscopy")),
        ("electrochemical_testing", ("eis", "polarization", "cyclic", "voltamm", "rde", "rrde", "electrochemical", "ast")),
        ("manufacturing_assembly", ("ink", "coating", "decal", "assembly", "ccm", "gde", "printing", "manufactur")),
        ("simulation_modelling", ("model", "simulation", "fitting", "prediction", "digital twin", "dft")),
    )
    for family, keywords in family_keywords:
        if any(keyword in text for keyword in keywords):
            return family
    return "other"


def _visual_category(node: dict[str, Any]) -> str:
    category = _normal(str(node.get("native_category", "")))
    label = _normal(str(node.get("label", "")))
    if category in {"material", "component"}:
        return "material" if category == "material" else "component"
    if category == "meso" or any(token in label for token in ("voxel data", "image data", "dataset", "tomography data")):
        return "data"
    if category in {"device", "lre"}:
        return "device"
    if any(token in label for token in ("model", "simulation", "fitting", "theory", "digital twin", "calculation")):
        return "model"
    if any(token in label for token in ("coating", "deposition", "preparation", "assembly", "manufacturing", "printing", "mixing")):
        return "process"
    if node.get("shape") == "hexagon":
        return "method"
    return "other"


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "workflow"


def _normal(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _humanize_filename(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("_", " ")).strip()


def _last_segment(iri: str) -> str:
    return iri.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _short_hash(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:10]


def _write_mapping_matrix(path: Path, rows: list[dict[str, str]]) -> Path:
    fields = [
        "workflow_id", "source_filename", "source_node_id", "source_label", "native_category",
        "mapping_state", "decision", "anchor_iri", "anchor_label", "canonical_role_iri",
        "semantic_role", "role_assignment", "confidence", "evidence",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return write_text(path, buffer.getvalue())


def _write_mapping_matrix_markdown(path: Path, rows: list[dict[str, str]]) -> Path:
    counts = Counter(row["mapping_state"] for row in rows)
    lines = [
        "# DECODE Mapping Matrix",
        "",
        "This matrix records explicit curation decisions. Unreviewed lexical similarity is not a mapping and does not create a cross-workflow connection.",
        "",
        "| State | Occurrences |",
        "| --- | ---: |",
        *[f"| {state} | {count} |" for state, count in sorted(counts.items())],
        "",
        "| Workflow | Source node | Label | Native category | State | Shared anchor | Evidence |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append("| {workflow_id} | {source_node_id} | {source_label} | {native_category} | {mapping_state} | {anchor_iri} | {evidence} |".format(**{key: value.replace("|", "\\|") for key, value in row.items()}))
    return write_text(path, "\n".join(lines) + "\n")


def _write_semantic_role_audit(path: Path, concepts: list[dict[str, Any]]) -> Path:
    """Export all role decisions independently from mapping equivalence decisions."""
    fields = [
        "source_label", "native_category", "visual_category", "occurrence_count", "workflow_ids",
        "semantic_role", "canonical_role_iri", "role_assignment", "decision", "mapping_state",
        "anchor_iri", "confidence", "rationale",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    for concept in concepts:
        row = dict(concept)
        row["workflow_ids"] = "; ".join(concept.get("workflow_ids", []))
        writer.writerow({field: row.get(field, "") for field in fields})
    return write_text(path, buffer.getvalue())


def _write_anchor_candidates(path: Path, rows: list[dict[str, str]]) -> Path:
    fields = ["source_label", "native_category", "visual_category", "occurrence_count", "workflow_count", "workflow_ids", "recommended_state", "note"]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return write_text(path, buffer.getvalue())


def _write_concept_registry(path: Path, rows: list[dict[str, Any]]) -> Path:
    fields = [
        "concept_id", "source_label", "native_category", "visual_category", "occurrence_count",
        "workflow_ids", "source_descriptions", "neighbor_context", "decision", "mapping_state",
        "anchor_iri", "canonical_role_iri", "semantic_role", "role_assignment", "confidence", "rationale",
        "candidate_h2kg_terms",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        flattened = dict(row)
        for key in ("workflow_ids", "source_descriptions", "neighbor_context"):
            flattened[key] = "; ".join(str(value) for value in row[key])
        flattened["candidate_h2kg_terms"] = json.dumps(row["candidate_h2kg_terms"], ensure_ascii=False)
        writer.writerow(flattened)
    return write_text(path, buffer.getvalue())


def _write_duplicate_occurrence_audit(path: Path, rows: list[dict[str, Any]]) -> Path:
    fields = [
        "id", "workflow_id", "source_label", "native_category", "occurrence_ids",
        "occurrence_count", "anchor_ids", "collapse_eligible", "context_classification",
        "semantic_role_conflict", "direct_context_patterns",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        flattened = dict(row)
        for key in ("occurrence_ids", "anchor_ids"):
            flattened[key] = "; ".join(str(value) for value in row[key])
        flattened["direct_context_patterns"] = json.dumps(row["direct_context_patterns"], ensure_ascii=False)
        writer.writerow(flattened)
    return write_text(path, buffer.getvalue())


def _write_semantic_role_conflict_audit(path: Path, rows: list[dict[str, Any]]) -> Path:
    fields = ["anchor_id", "label", "state", "semantic_roles", "canonical_role_iris", "occurrence_ids"]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        flattened = dict(row)
        for key in ("semantic_roles", "canonical_role_iris", "occurrence_ids"):
            flattened[key] = "; ".join(str(value) for value in row[key])
        writer.writerow(flattened)
    return write_text(path, buffer.getvalue())


def _write_edge_registry(path: Path, rows: list[dict[str, Any]]) -> Path:
    """Write a one-row-per-source-edge semantic decision register."""
    fields = [
        "source_dependency_id", "workflow_id", "source_kind", "source_occurrence_id",
        "source_graphml_id", "source_label", "source_semantic_role", "source_anchor_iri",
        "target_occurrence_id", "target_graphml_id", "target_label", "target_semantic_role",
        "target_anchor_iri", "source_description", "projection_outcome", "projection_pattern",
        "semantic_predicates", "semantic_edge_ids", "semantic_direction", "confidence",
        "review_status", "rationale",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        flattened = dict(row)
        flattened["semantic_edge_ids"] = "; ".join(row.get("semantic_edge_ids", []))
        writer.writerow({field: flattened.get(field, "") for field in fields})
    return write_text(path, buffer.getvalue())


def _workflow_jsonld(structural: dict[str, Any]) -> dict[str, Any]:
    workflow = structural["workflow"]
    items: list[dict[str, Any]] = [{"@id": workflow["iri"], "@type": [PROV + "Bundle"], RDFS_LABEL: [workflow["title"]]}]
    entities = [*structural["nodes"], *structural.get("projection_nodes", [])]
    iri_by_id = {node["id"]: node["iri"] for node in entities}
    iri_by_id.update({anchor["id"]: anchor["id"] for anchor in structural.get("anchors", [])})
    for node in structural["nodes"]:
        types = [PROV + "Entity"]
        if node.get("canonical_role_iri"):
            types.append(node["canonical_role_iri"])
        item = {
            "@id": node["iri"],
            "@type": types,
            RDFS_LABEL: [node["label"]],
            DECODE_SOURCE_DEPENDENCY: [],
            "https://w3id.org/h2kg/decode/workflow/sourceNodeId": [node["source_id"]],
        }
        if node.get("anchor_id"):
            item[DECODE_MAPPING] = [{"@id": node["anchor_id"]}]
        items.append(item)
    for proxy in structural.get("projection_nodes", []):
        item = {
            "@id": proxy["iri"],
            "@type": [PROV + "Entity", H2KG + "DataPoint"],
            RDFS_LABEL: [proxy["label"]],
            DECODE_DERIVED_FROM_OCCURRENCE: [{"@id": iri_by_id[proxy["source_occurrence_id"]]}],
        }
        if proxy.get("source_anchor_iri"):
            item[H2KG + "ofProperty"] = [{"@id": proxy["source_anchor_iri"]}]
        items.append(item)
    for anchor in structural.get("anchors", []):
        if anchor["id"].startswith(H2KG):
            continue
        role = anchor.get("canonical_role_iri")
        if role:
            items.append({"@id": anchor["id"], "@type": [role], RDFS_LABEL: [anchor["label"]]})
    for edge in structural["source_edges"]:
        source_iri = iri_by_id[edge["source"]]
        target_iri = iri_by_id[edge["target"]]
        next(item for item in items if item["@id"] == source_iri)[DECODE_SOURCE_DEPENDENCY].append({"@id": target_iri})
    for edge in structural["semantic_edges"]:
        source_iri = iri_by_id[edge["source"]]
        target_iri = iri_by_id[edge["target"]]
        source_item = next(item for item in items if item["@id"] == source_iri)
        source_item.setdefault(edge["predicate"], []).append({"@id": target_iri})
        projection_iri = f"{workflow['iri']}/projection/{_short_hash(edge['id'])}"
        items.append(
            {
                "@id": projection_iri,
                "@type": [DECODE_EDGE_PROJECTION],
                DECODE_SOURCE_DEPENDENCY_ID: [edge["source_dependency_id"]],
                DECODE_PROJECTION_OUTCOME: [edge["projection_outcome"]],
                DECODE_PROJECTION_PATTERN: [edge["projection_pattern"]],
                DECODE_SEMANTIC_SOURCE: [{"@id": source_iri}],
                DECODE_SEMANTIC_TARGET: [{"@id": target_iri}],
                DECODE_SEMANTIC_PREDICATE: [{"@id": edge["predicate"]}],
            }
        )
    return {"@context": {**COMMON_CONTEXT, "decode": DECODE_NS}, "@graph": items}


def _workflow_turtle(structural: dict[str, Any]) -> str:
    workflow = structural["workflow"]
    lines = [
        "@prefix decode: <https://w3id.org/h2kg/decode/workflow/> .",
        "@prefix h2kg: <https://w3id.org/h2kg/hydrogen-ontology#> .",
        "@prefix prov: <http://www.w3.org/ns/prov#> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "",
    ]
    entities = [*structural["nodes"], *structural.get("projection_nodes", [])]
    iri_by_id = {node["id"]: node["iri"] for node in entities}
    iri_by_id.update({anchor["id"]: anchor["id"] for anchor in structural.get("anchors", [])})
    for node in structural["nodes"]:
        types = ["prov:Entity"]
        if node.get("canonical_role_iri"):
            types.append(f"<{node['canonical_role_iri']}>")
        lines.append(f"<{node['iri']}> a {', '.join(types)} ; rdfs:label {_ttl_literal(node['label'])} .")
        if node.get("anchor_id"):
            lines.append(f"<{node['iri']}> decode:mappedToAnchor <{node['anchor_id']}> .")
    for proxy in structural.get("projection_nodes", []):
        lines.append(f"<{proxy['iri']}> a h2kg:DataPoint, prov:Entity ; rdfs:label {_ttl_literal(proxy['label'])} .")
        lines.append(f"<{proxy['iri']}> decode:derivedFromOccurrence <{iri_by_id[proxy['source_occurrence_id']]}> .")
        if proxy.get("source_anchor_iri"):
            lines.append(f"<{proxy['iri']}> h2kg:ofProperty <{proxy['source_anchor_iri']}> .")
    for anchor in structural.get("anchors", []):
        if not anchor["id"].startswith(H2KG) and anchor.get("canonical_role_iri"):
            lines.append(f"<{anchor['id']}> a <{anchor['canonical_role_iri']}> ; rdfs:label {_ttl_literal(anchor['label'])} .")
    for edge in structural["source_edges"]:
        source = iri_by_id[edge["source"]]
        target = iri_by_id[edge["target"]]
        lines.append(f"<{source}> decode:sourceDependency <{target}> .")
    for edge in structural["semantic_edges"]:
        source = iri_by_id[edge["source"]]
        target = iri_by_id[edge["target"]]
        lines.append(f"<{source}> <{edge['predicate']}> <{target}> .")
        projection = f"{workflow['iri']}/projection/{_short_hash(edge['id'])}"
        lines.append(f"<{projection}> a decode:SemanticProjection ; decode:sourceDependencyId {_ttl_literal(edge['source_dependency_id'])} ; decode:projectionOutcome {_ttl_literal(edge['projection_outcome'])} ; decode:projectionPattern {_ttl_literal(edge['projection_pattern'])} ; decode:semanticSource <{source}> ; decode:semanticTarget <{target}> ; decode:semanticPredicate <{edge['predicate']}> .")
    return "\n".join(lines) + "\n"


def _ttl_literal(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


def _readme(graph: dict[str, Any], validation: dict[str, Any]) -> str:
    return f"""# DECODE Federated Workflow Layer

This release contains a normalized structural projection of DECODE GraphML workflows. It is a separate data layer aligned to H2KG; it does not change the H2KG ontology TBox or the TBox-only H2KG Explore page.

- Source workflows: {graph['counts']['workflow_count']}
- Preserved source occurrences: {graph['counts']['source_node_count']}
- Preserved directed source dependencies: {graph['counts']['source_edge_count']}
- Explicitly mapped occurrences: {graph['counts']['mapped_occurrence_count']}
- Shared reviewed anchors: {graph['counts']['anchor_count']}
- Semantic-overview nodes: {graph['counts']['semantic_overview_node_count']}
- Repeated source-concept groups: {graph['counts']['duplicate_occurrence_group_count']}
- Semantic role conflicts: {graph['counts']['semantic_role_conflict_count']}
- Classified source dependencies: {graph['counts'].get('edge_classification_count', 0)}
- H2KG/PROV semantic projection triples: {graph['counts'].get('semantic_projection_count', 0)}
- Derived property-value DataPoint proxies: {graph['counts'].get('property_value_proxy_count', 0)}
- Structural validation: {validation['status']}

## Mapping states

- `approved_h2kg`: an explicit reviewed mapping to an existing H2KG IRI.
- `reviewed_decode`: a reviewed DECODE anchor pending a future H2KG vocabulary decision.
- `unresolved`: retained without cross-workflow merging.

Raw GraphML files are not redistributed in this package. The normalized JSON, JSON-LD and Turtle projections preserve source node IDs and directed dependencies for review and reuse.

`decode_duplicate_occurrence_audit.csv` documents every repeated source label within a workflow. `decode_semantic_role_conflicts.csv` records any incompatible roles assigned to a shared anchor and causes validation to fail. The semantic overview is a derived visualization only: every aggregate edge records the exact preserved source-dependency IDs it represents.

`decode_edge_registry.csv` classifies every source dependency as `h2kg_direct`, `h2kg_reified`, `prov_derivation`, or `decode_structural_only`. Source dependencies are never relabelled or removed. A semantic projection may reverse direction where required by H2KG, and `DataPoint` proxies are created only for property-valued workflow variables.
"""
