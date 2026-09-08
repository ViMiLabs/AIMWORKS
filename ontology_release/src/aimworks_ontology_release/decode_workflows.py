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


DECODE_NS = "https://w3id.org/h2kg/decode/workflow/"
H2KG = COMMON_CONTEXT["h2kg"]
RDF_TYPE = COMMON_CONTEXT["rdf"] + "type"
RDFS_LABEL = COMMON_CONTEXT["rdfs"] + "label"
PROV = COMMON_CONTEXT["prov"]
DECODE_MAPPING = DECODE_NS + "mappedToAnchor"
DECODE_SOURCE_DEPENDENCY = DECODE_NS + "sourceDependency"
GRAPHML_NS = "{http://graphml.graphdrawing.org/xmlns}"
YED_NS = "{http://www.yworks.com/xml/graphml}"


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
    validation = _validate_federated_graph(snapshot, graph)
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
        write_text(target / "README.md", _readme(graph, validation)),
    ]
    for workflow in graph["workflows"]:
        workflow_id = workflow["id"]
        structural = {
            "schema_version": graph["schema_version"],
            "workflow": workflow,
            "nodes": [node for node in graph["nodes"] if node.get("workflow_id") == workflow_id],
            "source_edges": [edge for edge in graph["source_edges"] if edge["workflow_id"] == workflow_id],
            "anchor_edges": [edge for edge in graph["anchor_edges"] if edge["workflow_id"] == workflow_id],
            "semantic_edges": [edge for edge in graph["semantic_edges"] if edge["workflow_id"] == workflow_id],
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
        "concept_registry_count": registry["counts"]["concept_count"],
        "validation_status": validation["status"],
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
        source_dependency_ids = {
            (edge["source_id"], edge["target_id"]): edge["id"]
            for edge in workflow_source_edges
        }
        source_edges.extend({**edge, "workflow_id": workflow_id, "type": "source_dependency"} for edge in workflow_source_edges)
        for projection_key, projection in semantic_projections.items():
            projection_workflow, source_node_id, target_node_id = projection_key
            if projection_workflow != workflow_id:
                continue
            source_dependency_id = source_dependency_ids.get((source_node_id, target_node_id))
            if source_dependency_id is None:
                raise ValueError(
                    "A reviewed semantic projection must cite a preserved directed "
                    f"DECODE dependency: {workflow_id}::{source_node_id} -> {target_node_id}."
                )
            semantic_edges.append(
                {
                    "id": f"semantic::{workflow_id}::{source_node_id}::{target_node_id}",
                    "workflow_id": workflow_id,
                    "source": f"{workflow_id}::{source_node_id}",
                    "target": f"{workflow_id}::{target_node_id}",
                    "predicate": projection["predicate"],
                    "label": projection.get("label") or _last_segment(projection["predicate"]),
                    "type": "approved_semantic_projection",
                    "source_dependency_id": source_dependency_id,
                    "evidence": projection.get("evidence", "Explicit reviewed semantic projection."),
                }
            )
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


def _validate_federated_graph(snapshot: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    source_pairs = {
        (workflow["id"], edge["source"], edge["target"])
        for workflow in snapshot.get("workflows", [])
        for edge in workflow.get("edges", [])
    }
    preserved_pairs = {(edge["workflow_id"], edge["source"], edge["target"]) for edge in graph["source_edges"]}
    node_ids = {node["id"] for node in graph["nodes"]}
    invalid_edges = [edge["id"] for edge in graph["source_edges"] if edge["source"] not in node_ids or edge["target"] not in node_ids]
    invalid_semantic_edges = [edge["id"] for edge in graph["semantic_edges"] if edge["source"] not in node_ids or edge["target"] not in node_ids]
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
    status = "passed" if source_pairs == preserved_pairs and not invalid_edges and not invalid_semantic_edges and not untraceable_semantic_edges and not unexpected_cross_links else "failed"
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
        "mapping_policy": "Cross-workflow traversal is available only through explicit approved_h2kg or reviewed_decode anchor mappings.",
    }


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
    role = str(role_by_category.get(visual_category, "")).strip()
    category = _normal(source_node.get("native_category", "")) or visual_category
    anchor_key = f"{_slug(source_node['label'])}-{_slug(category)}"
    return {
        "state": "reviewed_decode",
        "decision": "reviewed_decode_anchor",
        "anchor_iri": f"{DECODE_NS}anchor/{anchor_key}",
        "anchor_label": source_node["label"],
        "canonical_role_iri": role,
        "semantic_role": _last_segment(role) if role else "contextual DECODE concept",
        "confidence": "reviewed_structural",
        "evidence": (
            "DECODE-specific concept retained as a stable reviewed anchor. "
            "Its source topology is preserved; no H2KG synonym or new public term was asserted."
        ),
    }


def _concept_registry(
    snapshot: dict[str, Any],
    graph: dict[str, Any],
    ontology_path: str | Path | None,
) -> dict[str, Any]:
    """Create an auditable, concept-level register from occurrence-level decisions."""
    nodes_by_id = {node["id"]: node for node in graph["nodes"]}
    neighbors: dict[str, set[str]] = defaultdict(set)
    for edge in graph["source_edges"]:
        source = nodes_by_id.get(edge["source"])
        target = nodes_by_id.get(edge["target"])
        if source and target:
            neighbors[source["id"]].add(target["label"])
            neighbors[target["id"]].add(source["label"])

    h2kg_terms = _load_h2kg_terms(ontology_path)
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for node in graph["nodes"]:
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
        "semantic_role", "confidence", "evidence",
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
        "anchor_iri", "canonical_role_iri", "semantic_role", "confidence", "rationale",
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


def _workflow_jsonld(structural: dict[str, Any]) -> dict[str, Any]:
    workflow = structural["workflow"]
    items: list[dict[str, Any]] = [{"@id": workflow["iri"], "@type": [PROV + "Bundle"], RDFS_LABEL: [workflow["title"]]}]
    for node in structural["nodes"]:
        item = {
            "@id": node["iri"],
            "@type": [PROV + "Entity"],
            RDFS_LABEL: [node["label"]],
            DECODE_SOURCE_DEPENDENCY: [],
            "https://w3id.org/h2kg/decode/workflow/sourceNodeId": [node["source_id"]],
        }
        if node.get("anchor_id"):
            item[DECODE_MAPPING] = [{"@id": node["anchor_id"]}]
        items.append(item)
    for edge in structural["source_edges"]:
        source_iri = next(node["iri"] for node in structural["nodes"] if node["id"] == edge["source"])
        target_iri = next(node["iri"] for node in structural["nodes"] if node["id"] == edge["target"])
        next(item for item in items if item["@id"] == source_iri)[DECODE_SOURCE_DEPENDENCY].append({"@id": target_iri})
    return {"@context": {**COMMON_CONTEXT, "decode": DECODE_NS}, "@graph": items}


def _workflow_turtle(structural: dict[str, Any]) -> str:
    lines = [
        "@prefix decode: <https://w3id.org/h2kg/decode/workflow/> .",
        "@prefix h2kg: <https://w3id.org/h2kg/hydrogen-ontology#> .",
        "@prefix prov: <http://www.w3.org/ns/prov#> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "",
    ]
    for node in structural["nodes"]:
        lines.append(f"<{node['iri']}> a prov:Entity ; rdfs:label {_ttl_literal(node['label'])} .")
        if node.get("anchor_id"):
            lines.append(f"<{node['iri']}> decode:mappedToAnchor <{node['anchor_id']}> .")
    for edge in structural["source_edges"]:
        source = next(node["iri"] for node in structural["nodes"] if node["id"] == edge["source"])
        target = next(node["iri"] for node in structural["nodes"] if node["id"] == edge["target"])
        lines.append(f"<{source}> decode:sourceDependency <{target}> .")
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
- Structural validation: {validation['status']}

## Mapping states

- `approved_h2kg`: an explicit reviewed mapping to an existing H2KG IRI.
- `reviewed_decode`: a reviewed DECODE anchor pending a future H2KG vocabulary decision.
- `unresolved`: retained without cross-workflow merging.

Raw GraphML files are not redistributed in this package. The normalized JSON, JSON-LD and Turtle projections preserve source node IDs and directed dependencies for review and reuse.
"""
