from __future__ import annotations

"""Build a PDF-derived, H2KG-aligned DECODE multiscale-model interface schema.

The resulting package is deliberately separate from immutable DECODE GraphML
sources.  It captures a documented model interface and the explicit handoffs
between its stages without turning PDF values into asserted observations.
"""

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .utils import COMMON_CONTEXT, dump_json, ensure_dir, load_json, write_text


DECODE_NS = "https://w3id.org/h2kg/decode/workflow/"
H2KG = COMMON_CONTEXT["h2kg"]
PROV = COMMON_CONTEXT["prov"]
QUDT = COMMON_CONTEXT["qudt"]
RDF = COMMON_CONTEXT["rdf"]
RDFS = COMMON_CONTEXT["rdfs"]
SKOS = COMMON_CONTEXT["skos"]
DCTERMS = COMMON_CONTEXT["dcterms"]
XSD = COMMON_CONTEXT["xsd"]

WORKFLOW_ID = "iet-multiscale-model-interface"
WORKFLOW_IRI = f"{DECODE_NS}{WORKFLOW_ID}"
GRAPHML_NS = "http://graphml.graphdrawing.org/xmlns"
ET.register_namespace("", GRAPHML_NS)

STAGES = {
    "ITC": {
        "id": "iet-ink-to-composition-model",
        "label": "IET ink to composition model",
    },
    "CTP": {
        "id": "iet-composition-to-property-model",
        "label": "IET composition to property model",
    },
    "PTP": {
        "id": "iet-1d-performance-model-for-mea-prediction",
        "label": "IET 1D Performance model for MEA (prediction)",
    },
}

# Only unambiguous QUDT unit IRIs are emitted. All other reported units remain
# explicit schema metadata until their compound-unit interpretation is reviewed.
SAFE_QUDT_UNITS = {
    "[Pa]": "http://qudt.org/vocab/unit/PA",
    "[m]": "http://qudt.org/vocab/unit/M",
    "[K]": "http://qudt.org/vocab/unit/K",
    "[J]": "http://qudt.org/vocab/unit/J",
    "[s]": "http://qudt.org/vocab/unit/SEC",
    "[°]": "http://qudt.org/vocab/unit/DEG",
}


def build_decode_multiscale_model_interface(
    manifest_path: str | Path,
    decode_snapshot_path: str | Path,
    output_root: str | Path,
) -> dict[str, Any]:
    """Generate the interface package and a graph fragment for DECODE Explorer."""
    manifest_path = Path(manifest_path)
    decode_snapshot_path = Path(decode_snapshot_path)
    output_root = Path(output_root)
    if not manifest_path.exists():
        return {"status": "skipped_missing_manifest", "manifest": str(manifest_path)}

    manifest = load_json(manifest_path)
    variables = list(manifest.get("variables", []))
    _validate_manifest(variables)
    source_labels = _source_labels(decode_snapshot_path)
    variable_index = _index_variables(variables)
    fragment = _build_fragment(manifest, variable_index)
    target = ensure_dir(output_root / "decode" / "modeling_interface")
    coverage = _coverage_rows(variables, source_labels)
    validation = _validation_report(variables, fragment, coverage)

    graphml_path = _write_graphml(target / "iet_multiscale_model_interface.graphml", fragment)
    jsonld_path = dump_json(target / "iet_multiscale_model_interface.jsonld", _jsonld_document(manifest, variable_index, fragment))
    ttl_path = write_text(target / "iet_multiscale_model_interface.ttl", _turtle_document(manifest, variable_index, fragment))
    shapes_path = write_text(target / "iet_multiscale_model_interface_shapes.ttl", _shacl_shapes())
    manifest_copy = dump_json(target / "iet_multiscale_model_interface_manifest.json", manifest)
    coverage_path = _write_csv(target / "iet_multiscale_model_interface_coverage_audit.csv", coverage)
    mapping_path = _write_csv(target / "iet_multiscale_model_interface_mapping_matrix.csv", _mapping_rows(variable_index))
    validation_path = dump_json(target / "iet_multiscale_model_interface_validation.json", validation)
    readme_path = write_text(target / "README.md", _readme(validation))

    workflow = fragment["workflow"]
    workflow["downloads"] = [
        {"href": "../decode/modeling_interface/iet_multiscale_model_interface.graphml", "label": "Download derived interface GraphML"},
        {"href": "../decode/modeling_interface/iet_multiscale_model_interface.jsonld", "label": "Download H2KG-aligned JSON-LD schema"},
        {"href": "../decode/modeling_interface/iet_multiscale_model_interface.ttl", "label": "Download H2KG-aligned Turtle schema"},
        {"href": "../decode/modeling_interface/iet_multiscale_model_interface_shapes.ttl", "label": "Download extraction SHACL shapes"},
        {"href": "../decode/modeling_interface/iet_multiscale_model_interface_mapping_matrix.csv", "label": "Download interface mapping matrix"},
        {"href": "../decode/modeling_interface/iet_multiscale_model_interface_coverage_audit.csv", "label": "Download PDF-to-DECODE coverage audit"},
        {"href": "../decode/modeling_interface/iet_multiscale_model_interface_validation.json", "label": "Download interface validation report"},
    ]
    return {
        "status": "generated",
        "workflow": workflow,
        "nodes": fragment["nodes"],
        "source_edges": fragment["source_edges"],
        "anchor_edges": fragment["anchor_edges"],
        "semantic_edges": fragment["semantic_edges"],
        "anchors": fragment["anchors"],
        "validation": validation,
        "output_dir": str(target),
        "generated_files": [
            str(path)
            for path in [graphml_path, jsonld_path, ttl_path, shapes_path, manifest_copy, coverage_path, mapping_path, validation_path, readme_path]
        ],
    }


def append_multiscale_interface(graph: dict[str, Any], interface: dict[str, Any]) -> None:
    """Add a derived schema to the explorer graph without changing source counts."""
    if interface.get("status") != "generated":
        return
    graph["workflows"].append(interface["workflow"])
    graph["nodes"].extend(interface["nodes"])
    graph["source_edges"].extend(interface["source_edges"])
    graph["anchor_edges"].extend(interface["anchor_edges"])
    graph["semantic_edges"].extend(interface["semantic_edges"])
    graph["anchors"].extend(interface["anchors"])
    graph["anchor_index"].update({anchor["id"]: anchor["occurrence_ids"] for anchor in interface["anchors"]})
    graph["derived_interfaces"] = [
        {
            "id": WORKFLOW_ID,
            "description": "Value-free PDF-derived extraction schema. It is not an immutable supplied GraphML source.",
            "validation": interface["validation"],
        }
    ]
    graph["counts"].update(
        {
            "derived_workflow_count": 1,
            "derived_interface_node_count": len(interface["nodes"]),
            "derived_interface_edge_count": len(interface["source_edges"]),
        }
    )


def _validate_manifest(variables: list[dict[str, Any]]) -> None:
    if len(variables) != 290:
        raise ValueError(f"Expected 290 PDF interface occurrences, found {len(variables)}")
    identifiers = {str(row.get("io_id", "")) for row in variables}
    if len(identifiers) != 170 or "" in identifiers:
        raise ValueError(f"Expected 170 unique non-empty IO identifiers, found {len(identifiers)}")
    expected = {("ITC", "input"): 24, ("ITC", "output"): 20, ("CTP", "input"): 94, ("CTP", "output"): 14, ("PTP", "input"): 109, ("PTP", "output"): 29}
    actual = Counter((str(row.get("stage")), str(row.get("direction"))) for row in variables)
    if actual != expected:
        raise ValueError(f"Unexpected PDF stage counts: {dict(actual)}")


def _source_labels(snapshot_path: Path) -> set[str]:
    if not snapshot_path.exists():
        return set()
    snapshot = load_json(snapshot_path)
    stage_ids = {stage["id"] for stage in STAGES.values()}
    return {
        _normal(node.get("label", ""))
        for workflow in snapshot.get("workflows", [])
        if workflow.get("id") in stage_ids
        for node in workflow.get("nodes", [])
    }


def _index_variables(variables: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in variables:
        identifier = str(row["io_id"])
        record = indexed.setdefault(
            identifier,
            {
                "io_id": identifier,
                "label": str(row["label"]),
                "reported_unit": str(row["reported_unit"]),
                "value_shape": str(row["value_shape"]),
                "occurrences": [],
            },
        )
        if record["label"] != str(row["label"]):
            raise ValueError(f"Identifier {identifier} has inconsistent labels")
        record["occurrences"].append(row)
    for record in indexed.values():
        record["stages"] = sorted({str(row["stage"]) for row in record["occurrences"]})
        record["directions"] = sorted({str(row["direction"]) for row in record["occurrences"]})
        record["is_model_output"] = "output" in record["directions"]
        record["semantic_role"] = "Data" if record["is_model_output"] or record["value_shape"] == "array" else "Parameter"
        record["canonical_role_iri"] = H2KG + record["semantic_role"]
        record["rdf_type"] = H2KG + ("Data" if record["value_shape"] == "array" else ("DataPoint" if record["is_model_output"] else "Parameter"))
        record["iri"] = f"{WORKFLOW_IRI}/variable/{record['io_id']}"
        record["anchor_iri"] = f"{DECODE_NS}interface/variable/{record['io_id']}"
        record["property_iri"] = f"{WORKFLOW_IRI}/property/{record['io_id']}"
    return indexed


def _build_fragment(manifest: dict[str, Any], variables: dict[str, dict[str, Any]]) -> dict[str, Any]:
    workflow = {
        "id": WORKFLOW_ID,
        "iri": WORKFLOW_IRI,
        "title": "IET multiscale model interface (PDF-derived schema)",
        "source_filename": str(manifest.get("source", {}).get("filename", "Modeling methods inputs outputs FZJ.pdf")),
        "source_sha256": str(manifest.get("source", {}).get("sha256", "")),
        "method_family": "modeling_interface_schema",
        "source_status": "derived_pdf_schema",
        "mapping_status": "reviewed_schema",
        "source_node_count": 3 + len(variables),
        "source_edge_count": 0,
        "mapped_anchor_count": len(variables),
        "cross_workflow_connection_count": 0,
        "is_derived": True,
    }
    nodes: list[dict[str, Any]] = []
    anchors: list[dict[str, Any]] = []
    anchor_edges: list[dict[str, Any]] = []
    source_edges: list[dict[str, Any]] = []
    semantic_edges: list[dict[str, Any]] = []
    model_ids: dict[str, str] = {}
    for stage, details in STAGES.items():
        node_id = f"{WORKFLOW_ID}::model::{stage.lower()}"
        model_ids[stage] = node_id
        nodes.append(
            {
                "id": node_id,
                "source_id": stage.lower(),
                "iri": f"{WORKFLOW_IRI}/model/{stage.lower()}",
                "label": details["label"],
                "description": f"PDF-defined {stage} computational model stage in the DECODE multiscale interface schema.",
                "native_category": "model",
                "shape": "hexagon",
                "workflow_id": WORKFLOW_ID,
                "kind": "occurrence",
                "is_derived_interface": True,
                "visual_category": "model",
                "mapping_state": "reviewed_decode",
                "anchor_id": f"{DECODE_NS}interface/model/{stage.lower()}",
                "decision": "reviewed_decode_anchor",
                "canonical_role_iri": H2KG + "Process",
                "semantic_role": "Process",
                "confidence": "reviewed_pdf_schema",
                "mapping_evidence": "Computational model named in the PDF-derived DECODE interface schema; represented as an H2KG Process without asserting a public H2KG method term.",
            }
        )
        anchors.append(
            {
                "id": f"{DECODE_NS}interface/model/{stage.lower()}",
                "kind": "anchor",
                "label": details["label"],
                "state": "reviewed_decode",
                "decision": "reviewed_decode_anchor",
                "canonical_role_iri": H2KG + "Process",
                "semantic_role": "Process",
                "confidence": "reviewed_pdf_schema",
                "evidence": "PDF-defined computational-model schema anchor.",
                "occurrence_ids": [node_id],
            }
        )
        anchor_edges.append(_anchor_edge(node_id, f"{DECODE_NS}interface/model/{stage.lower()}", WORKFLOW_ID))

    for record in variables.values():
        node_id = f"{WORKFLOW_ID}::variable::{record['io_id']}"
        record["node_id"] = node_id
        source_pages = ", ".join(str(row["pdf_page"]) for row in record["occurrences"])
        nodes.append(
            {
                "id": node_id,
                "source_id": record["io_id"],
                "iri": record["iri"],
                "label": record["label"],
                "description": f"PDF interface variable {record['io_id']}; expected {record['value_shape']} value; reported unit {record['reported_unit']}; PDF page(s) {source_pages}.",
                "native_category": "data" if record["semantic_role"] == "Data" else "component",
                "shape": "ellipse",
                "workflow_id": WORKFLOW_ID,
                "kind": "occurrence",
                "is_derived_interface": True,
                "visual_category": "data" if record["semantic_role"] == "Data" else "component",
                "mapping_state": "reviewed_decode",
                "anchor_id": record["anchor_iri"],
                "decision": "reviewed_decode_anchor",
                "canonical_role_iri": record["canonical_role_iri"],
                "semantic_role": record["semantic_role"],
                "confidence": "reviewed_pdf_schema",
                "mapping_evidence": "PDF-defined interface field retained as a reviewed DECODE anchor pending a term-specific H2KG vocabulary decision.",
            }
        )
        anchors.append(
            {
                "id": record["anchor_iri"],
                "kind": "anchor",
                "label": record["label"],
                "state": "reviewed_decode",
                "decision": "reviewed_decode_anchor",
                "canonical_role_iri": record["canonical_role_iri"],
                "semantic_role": record["semantic_role"],
                "confidence": "reviewed_pdf_schema",
                "evidence": f"Stable DECODE interface anchor for PDF identifier {record['io_id']}; no public H2KG synonym has been asserted.",
                "occurrence_ids": [node_id],
            }
        )
        anchor_edges.append(_anchor_edge(node_id, record["anchor_iri"], WORKFLOW_ID))

    for record in variables.values():
        for occurrence in record["occurrences"]:
            stage = str(occurrence["stage"])
            if occurrence["direction"] == "input":
                predicate = H2KG + ("hasInputData" if record["semantic_role"] == "Data" else "hasParameter")
                source, target = record["node_id"], model_ids[stage]
            else:
                predicate = H2KG + "hasOutputData"
                source, target = model_ids[stage], record["node_id"]
            edge_id = f"{WORKFLOW_ID}::edge::{stage.lower()}::{occurrence['direction']}::{record['io_id']}"
            edge = {
                "id": edge_id,
                "source_id": edge_id,
                "source": source,
                "target": target,
                "workflow_id": WORKFLOW_ID,
                "type": "pdf_interface_relation",
                "source_kind": "pdf_interface",
                "label": _local_name(predicate),
                "description": f"PDF page {occurrence['pdf_page']} {stage} {occurrence['direction']} relation for {record['io_id']}.",
                "predicate": predicate,
            }
            source_edges.append(edge)
            semantic_edges.append(
                {
                    "id": f"semantic::{edge_id}",
                    "workflow_id": WORKFLOW_ID,
                    "source": source,
                    "target": target,
                    "predicate": predicate,
                    "label": _local_name(predicate),
                    "type": "approved_semantic_projection",
                    "source_dependency_id": edge_id,
                    "evidence": edge["description"],
                }
            )
    workflow["source_edge_count"] = len(source_edges)
    return {"workflow": workflow, "nodes": nodes, "anchors": anchors, "anchor_edges": anchor_edges, "source_edges": source_edges, "semantic_edges": semantic_edges}


def _anchor_edge(node_id: str, anchor_id: str, workflow_id: str) -> dict[str, str]:
    return {"id": f"anchor::{node_id}", "workflow_id": workflow_id, "source": node_id, "target": anchor_id, "type": "occurrence_anchor_mapping"}


def _coverage_rows(variables: list[dict[str, Any]], source_labels: set[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in variables:
        label = str(row["label"])
        exact = _normal(label) in source_labels
        rows.append(
            {
                "io_id": str(row["io_id"]),
                "label": label,
                "stage": str(row["stage"]),
                "direction": str(row["direction"]),
                "pdf_page": str(row["pdf_page"]),
                "coverage_status": "exact_existing_decode_label" if exact else "pdf_interface_schema_field",
                "evidence": "Exact normalized label is present in one of the three original DECODE workflows." if exact else "Field is represented in the derived PDF interface schema; no exact label match was found in the three original DECODE workflows.",
            }
        )
    return rows


def _mapping_rows(variables: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for record in sorted(variables.values(), key=lambda item: item["io_id"]):
        rows.append(
            {
                "io_id": record["io_id"],
                "label": record["label"],
                "stages": "; ".join(record["stages"]),
                "directions": "; ".join(record["directions"]),
                "value_shape": record["value_shape"],
                "reported_unit": record["reported_unit"],
                "qudt_unit_iri": SAFE_QUDT_UNITS.get(record["reported_unit"], ""),
                "mapping_decision": "reviewed_decode_anchor",
                "canonical_role_iri": record["canonical_role_iri"],
                "semantic_role": record["semantic_role"],
                "anchor_iri": record["anchor_iri"],
                "rationale": "PDF-specific interface concept retained as a reviewed DECODE anchor until a reusable H2KG vocabulary decision is approved.",
            }
        )
    return rows


def _validation_report(variables: list[dict[str, Any]], fragment: dict[str, Any], coverage: list[dict[str, str]]) -> dict[str, Any]:
    stage_sets: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in variables:
        stage_sets[(str(row["stage"]), str(row["direction"]))].add(str(row["io_id"]))
    itc_ctp = sorted(stage_sets[("ITC", "output")] & stage_sets[("CTP", "input")])
    ctp_ptp = sorted(stage_sets[("CTP", "output")] & stage_sets[("PTP", "input")])
    itc_ptp = sorted(stage_sets[("ITC", "output")] & stage_sets[("PTP", "input")])
    return {
        "status": "passed",
        "value_free_schema": True,
        "source_pdf_redistributed": False,
        "occurrence_count": len(variables),
        "unique_identifier_count": len({row["io_id"] for row in variables}),
        "stage_counts": {f"{stage}_{direction}": len(values) for (stage, direction), values in sorted(stage_sets.items())},
        "handoffs": {"itc_to_ctp": itc_ctp, "ctp_to_ptp": ctp_ptp, "itc_to_ptp_direct_reuse": itc_ptp},
        "derived_graph": {"node_count": len(fragment["nodes"]), "edge_count": len(fragment["source_edges"])},
        "coverage": dict(Counter(row["coverage_status"] for row in coverage)),
        "from_measurement_assertions": 0,
        "unsupported_qudt_units_retained_as_reported_metadata": sorted({str(row["reported_unit"]) for row in variables if str(row["reported_unit"]) not in SAFE_QUDT_UNITS and str(row["reported_unit"]) != "[-]"}),
    }


def _write_graphml(path: Path, fragment: dict[str, Any]) -> Path:
    root = ET.Element(f"{{{GRAPHML_NS}}}graphml")
    for key_id, name in [("label", "label"), ("description", "description"), ("semantic_role", "semantic_role"), ("io_id", "io_id"), ("predicate", "predicate"), ("source_kind", "source_kind")]:
        ET.SubElement(root, f"{{{GRAPHML_NS}}}key", {"id": key_id, "for": "all", "attr.name": name, "attr.type": "string"})
    graph = ET.SubElement(root, f"{{{GRAPHML_NS}}}graph", {"id": WORKFLOW_ID, "edgedefault": "directed"})
    for node in fragment["nodes"]:
        item = ET.SubElement(graph, f"{{{GRAPHML_NS}}}node", {"id": node["source_id"]})
        for key, value in [("label", node["label"]), ("description", node["description"]), ("semantic_role", node["semantic_role"]), ("io_id", node.get("source_id", ""))]:
            data = ET.SubElement(item, f"{{{GRAPHML_NS}}}data", {"key": key})
            data.text = str(value)
    for index, edge in enumerate(fragment["source_edges"]):
        item = ET.SubElement(graph, f"{{{GRAPHML_NS}}}edge", {"id": f"e{index}", "source": _graphml_source_id(edge["source"]), "target": _graphml_source_id(edge["target"])})
        for key, value in [("label", edge["label"]), ("predicate", edge["predicate"]), ("source_kind", edge["source_kind"]), ("description", edge["description"])]:
            data = ET.SubElement(item, f"{{{GRAPHML_NS}}}data", {"key": key})
            data.text = str(value)
    ensure_dir(path.parent)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    return path


def _graphml_source_id(node_id: str) -> str:
    return node_id.rsplit("::", 1)[-1]


def _jsonld_document(manifest: dict[str, Any], variables: dict[str, dict[str, Any]], fragment: dict[str, Any]) -> dict[str, Any]:
    graph: list[dict[str, Any]] = [
        {
            "@id": WORKFLOW_IRI,
            "@type": ["prov:Bundle"],
            "rdfs:label": "IET multiscale model interface (PDF-derived schema)",
            "dcterms:description": "Value-free, PDF-derived DECODE extraction schema for the ITC, CTP, and PTP model chain.",
            "decode:sourcePdfFilename": manifest.get("source", {}).get("filename", ""),
            "decode:sourcePdfSha256": manifest.get("source", {}).get("sha256", ""),
        }
    ]
    model_iris = {stage: f"{WORKFLOW_IRI}/model/{stage.lower()}" for stage in STAGES}
    for stage, details in STAGES.items():
        model = {"@id": model_iris[stage], "@type": ["h2kg:Process", "prov:Activity"], "rdfs:label": details["label"]}
        inputs = [row for row in manifest["variables"] if row["stage"] == stage and row["direction"] == "input"]
        outputs = [row for row in manifest["variables"] if row["stage"] == stage and row["direction"] == "output"]
        parameter_iris = [variables[row["io_id"]]["iri"] for row in inputs if variables[row["io_id"]]["semantic_role"] == "Parameter"]
        input_data_iris = [variables[row["io_id"]]["iri"] for row in inputs if variables[row["io_id"]]["semantic_role"] == "Data"]
        if parameter_iris:
            model["h2kg:hasParameter"] = parameter_iris
        if input_data_iris:
            model["h2kg:hasInputData"] = input_data_iris
        if outputs:
            model["h2kg:hasOutputData"] = [variables[row["io_id"]]["iri"] for row in outputs]
        graph.append(model)
    for record in variables.values():
        entry: dict[str, Any] = {
            "@id": record["iri"],
            "@type": [_compact_iri(record["rdf_type"])],
            "rdfs:label": record["label"],
            "skos:definition": f"PDF-defined interface field {record['io_id']} for the DECODE IET multiscale model chain.",
            "dcterms:identifier": record["io_id"],
            "decode:expectedValueShape": record["value_shape"],
            "decode:reportedUnit": record["reported_unit"],
            "decode:stages": record["stages"],
        }
        qudt_unit = SAFE_QUDT_UNITS.get(record["reported_unit"])
        if qudt_unit:
            entry["qudt:unit"] = qudt_unit
        generated_by = [model_iris[row["stage"]] for row in record["occurrences"] if row["direction"] == "output"]
        if generated_by:
            entry["prov:wasGeneratedBy"] = generated_by
        if record["rdf_type"] == H2KG + "DataPoint":
            entry["h2kg:ofProperty"] = record["property_iri"]
            graph.append(
                {
                    "@id": record["property_iri"],
                    "@type": ["h2kg:Property"],
                    "rdfs:label": record["label"],
                    "skos:definition": f"Property described by PDF interface variable {record['io_id']}.",
                    "decode:reviewStatus": "pending reusable H2KG vocabulary decision",
                }
            )
        graph.append(entry)
    return {"@context": {**COMMON_CONTEXT, "decode": DECODE_NS}, "@graph": graph}


def _turtle_document(manifest: dict[str, Any], variables: dict[str, dict[str, Any]], fragment: dict[str, Any]) -> str:
    lines = [
        "@prefix h2kg: <https://w3id.org/h2kg/hydrogen-ontology#> .",
        "@prefix decode: <https://w3id.org/h2kg/decode/workflow/> .",
        "@prefix prov: <http://www.w3.org/ns/prov#> .",
        "@prefix qudt: <http://qudt.org/schema/qudt/> .",
        "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .",
        "@prefix dcterms: <http://purl.org/dc/terms/> .",
        "",
        f"<{WORKFLOW_IRI}> a prov:Bundle ;",
        '  rdfs:label "IET multiscale model interface (PDF-derived schema)" ;',
        '  dcterms:description "Value-free DECODE extraction schema; it does not assert the PDF baseline values." .',
        "",
    ]
    model_iris = {stage: f"{WORKFLOW_IRI}/model/{stage.lower()}" for stage in STAGES}
    for stage, details in STAGES.items():
        inputs = [row for row in manifest["variables"] if row["stage"] == stage and row["direction"] == "input"]
        outputs = [row for row in manifest["variables"] if row["stage"] == stage and row["direction"] == "output"]
        lines.extend([f"<{model_iris[stage]}> a h2kg:Process, prov:Activity ;", f'  rdfs:label "{_ttl(details["label"])}" ;'])
        parameter_iris = [variables[row["io_id"]]["iri"] for row in inputs if variables[row["io_id"]]["semantic_role"] == "Parameter"]
        input_data_iris = [variables[row["io_id"]]["iri"] for row in inputs if variables[row["io_id"]]["semantic_role"] == "Data"]
        predicates: list[tuple[str, list[str]]] = [("h2kg:hasParameter", parameter_iris), ("h2kg:hasInputData", input_data_iris), ("h2kg:hasOutputData", [variables[row["io_id"]]["iri"] for row in outputs])]
        predicates = [(predicate, values) for predicate, values in predicates if values]
        for index, (predicate, values) in enumerate(predicates):
            separator = " ;" if index < len(predicates) - 1 else " ."
            lines.append(f"  {predicate} " + ", ".join(f"<{value}>" for value in values) + separator)
        if not predicates:
            lines[-1] = lines[-1].rstrip(" ;") + " ."
        lines.append("")
    for record in variables.values():
        statements = [f"a {_compact_iri(record['rdf_type'])}", f'rdfs:label "{_ttl(record["label"])}"', f'dcterms:identifier "{_ttl(record["io_id"])}"', f'decode:expectedValueShape "{_ttl(record["value_shape"])}"', f'decode:reportedUnit "{_ttl(record["reported_unit"])}"']
        unit = SAFE_QUDT_UNITS.get(record["reported_unit"])
        if unit:
            statements.append(f"qudt:unit <{unit}>")
        if record["rdf_type"] == H2KG + "DataPoint":
            statements.append(f"h2kg:ofProperty <{record['property_iri']}>")
        generated_by = [model_iris[row["stage"]] for row in record["occurrences"] if row["direction"] == "output"]
        if generated_by:
            statements.append("prov:wasGeneratedBy " + ", ".join(f"<{value}>" for value in generated_by))
        lines.append(f"<{record['iri']}> " + " ;\n  ".join(statements) + " .\n")
        if record["rdf_type"] == H2KG + "DataPoint":
            lines.extend([f"<{record['property_iri']}> a h2kg:Property ;", f'  rdfs:label "{_ttl(record["label"])}" ;', f'  skos:definition "Property described by PDF interface variable {record["io_id"]}." .', ""])
    return "\n".join(lines)


def _shacl_shapes() -> str:
    return """@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix h2kg: <https://w3id.org/h2kg/hydrogen-ontology#> .
@prefix decode: <https://w3id.org/h2kg/decode/workflow/> .

decode:ModelInputParameterShape a sh:NodeShape ;
  sh:targetClass h2kg:Parameter ;
  sh:property [ sh:path decode:expectedValueShape ; sh:minCount 1 ] ;
  sh:property [ sh:path decode:reportedUnit ; sh:minCount 1 ] .

decode:ModelOutputDataShape a sh:NodeShape ;
  sh:targetClass h2kg:Data ;
  sh:property [ sh:path decode:expectedValueShape ; sh:minCount 1 ] .

decode:ModelOutputDataPointShape a sh:NodeShape ;
  sh:targetClass h2kg:DataPoint ;
  sh:property [ sh:path h2kg:ofProperty ; sh:minCount 1 ] .
"""


def _readme(validation: dict[str, Any]) -> str:
    return f"""# IET Multiscale Model Interface Schema

This package is a value-free extraction and curation schema derived from the
documented ITC -> CTP -> PTP interface. It does not redistribute the source PDF
or assert its baseline values.

- PDF interface occurrences: `{validation['occurrence_count']}`
- Unique `IO_*` identifiers: `{validation['unique_identifier_count']}`
- ITC -> CTP explicit identifier handoffs: `{len(validation['handoffs']['itc_to_ctp'])}`
- CTP -> PTP explicit identifier handoffs: `{len(validation['handoffs']['ctp_to_ptp'])}`
- `fromMeasurement` assertions: `0`

Use the GraphML file for visual workflow inspection, JSON-LD/Turtle for semantic
interchange, the SHACL file for extraction validation, and the coverage audit to
distinguish pre-existing DECODE labels from PDF-specific schema fields.
"""


def _write_csv(path: Path, rows: list[dict[str, str]]) -> Path:
    ensure_dir(path.parent)
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _normal(value: str) -> str:
    return " ".join(value.casefold().replace("-", " ").split())


def _local_name(iri: str) -> str:
    return iri.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _compact_iri(iri: str) -> str:
    return "h2kg:" + _local_name(iri) if iri.startswith(H2KG) else f"<{iri}>"


def _ttl(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
