from __future__ import annotations

"""Controlled H2KG integration and release artefacts for the ITC model profile."""

import csv
import io
from copy import deepcopy
from collections import Counter
from pathlib import Path
from typing import Any

from .io import dump_jsonld_items, dump_turtle_items, merge_document_items
from .utils import COMMON_CONTEXT, dump_json, ensure_dir, load_json, write_text


H2KG = COMMON_CONTEXT["h2kg"]
QUDT = COMMON_CONTEXT["qudt"]
UNIT = COMMON_CONTEXT["unit"]
QK = COMMON_CONTEXT["quantitykind"]
SKOS = COMMON_CONTEXT["skos"]
DCTERMS = COMMON_CONTEXT["dcterms"]
RDFS = COMMON_CONTEXT["rdfs"]

PREF_LABEL = SKOS + "prefLabel"
ALT_LABEL = SKOS + "altLabel"
NOTATION = SKOS + "notation"
DESCRIPTION = DCTERMS + "description"
SOURCE = DCTERMS + "source"
IDENTIFIER = DCTERMS + "identifier"
HAS_PARAMETER = H2KG + "hasParameter"
HAS_INPUT_DATA = H2KG + "hasInputData"
HAS_OUTPUT_DATA = H2KG + "hasOutputData"
HAS_PART = H2KG + "hasPart"
OF_PROPERTY = H2KG + "ofProperty"
HAS_QUANTITY_VALUE = H2KG + "hasQuantityValue"
QUDT_UNIT = QUDT + "unit"
QUDT_QUANTITY_KIND = QUDT + "quantityKind"
QUDT_QUANTITY_VALUE = QUDT + "QuantityValue"
RDF_TYPE = COMMON_CONTEXT["rdf"] + "type"

MODEL_LOCAL_NAME = "InkToCompositionModel"
WORKFLOW_ID = "iet-ink-to-composition-model"
MODEL_SOURCE_OCCURRENCE = f"{WORKFLOW_ID}::n22"

GROUPS = {
    "InkToCompositionModelInputDataset": (
        "Ink-to-Composition Model input dataset",
        "A value-free schema dataset grouping property-valued inputs expected by the Ink-to-Composition Model.",
    ),
    "InkToCompositionModelScalarResultDataset": (
        "Ink-to-Composition Model scalar-result dataset",
        "A value-free schema dataset grouping scalar property fields produced by the Ink-to-Composition Model.",
    ),
    "CCLWaterRetentionCurveDataset": (
        "CCL water-retention-curve dataset",
        "A dataset profile containing the capillary-pressure axis and corresponding CCL water-saturation array.",
    ),
    "CCLRefinedPoreSizeDistributionDataset": (
        "CCL refined pore-size-distribution dataset",
        "A dataset profile containing a pore-radius axis and corresponding refined CCL pore-size distribution.",
    ),
    "CCLContactAngleDistributionDataset": (
        "CCL contact-angle-distribution dataset",
        "A dataset profile containing a contact-angle-cosine axis and corresponding CCL contact-angle distribution.",
    ),
}

ARRAY_GROUPS = {
    "CCLWaterRetentionCurveDataset": ["IO_SIM_CapillaryPressureRange", "IO_CMP_CCLWaterRetentionCurve"],
    "CCLRefinedPoreSizeDistributionDataset": [
        "IO_SIM_PoreSizeRange",
        "IO_CMP_CCLRefinedPoreSizeDistributionContactAngleDistribution_PSD",
    ],
    "CCLContactAngleDistributionDataset": [
        "IO_SIM_ContactAngleRange",
        "IO_CMP_CCLRefinedPoreSizeDistributionContactAngleDistribution_CAD",
    ],
}


def integrate_itc_terms(
    ontology_path: str | Path,
    review_path: str | Path,
    *,
    write_in_place: bool = False,
) -> dict[str, Any]:
    """Add or update the reviewed ITC terms without changing H2KG properties."""
    ontology_path = Path(ontology_path)
    review = load_json(Path(review_path))
    validation = validate_review_registry(review)
    document = load_json(ontology_path)
    items = merge_document_items(document)
    existing = {item.get("@id"): item for item in items if isinstance(item.get("@id"), str)}
    generated = _profile_items(review)
    added = 0
    updated = 0
    for item in generated:
        iri = item["@id"]
        current = existing.get(iri)
        if current is None:
            items.append(item)
            existing[iri] = item
            added += 1
        else:
            _replace_managed_values(current, item)
            updated += 1
    if write_in_place:
        dump_json(ontology_path, items)
    return {
        "status": "integrated" if write_in_place else "preview",
        "ontology": str(ontology_path),
        "added_resource_count": added,
        "updated_resource_count": updated,
        "managed_resource_count": len(generated),
        "validation": validation,
    }


def build_itc_pilot_package(
    ontology_path: str | Path,
    output_root: str | Path,
    review_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build the public value-free profile and review package from one registry."""
    ontology_path = Path(ontology_path)
    review_path = Path(review_path or ontology_path.parent / "itc_expert_review.json")
    if not review_path.exists():
        return {
            "status": "skipped_missing_review",
            "review": str(review_path),
        }
    review = load_json(review_path)
    validation = validate_review_registry(review)
    ontology_items = {
        item.get("@id"): item
        for item in merge_document_items(load_json(ontology_path))
        if isinstance(item.get("@id"), str)
    }
    expected = _profile_items(review)
    missing = sorted(item["@id"] for item in expected if item["@id"] not in ontology_items)
    if missing:
        raise ValueError(f"ITC terms are not integrated into the H2KG source: {missing[:5]}")

    package = ensure_dir(Path(output_root) / "examples" / "itc_pilot")
    refreshed_profile_items: list[dict[str, Any]] = []
    for generated in expected:
        current = deepcopy(ontology_items[generated["@id"]])
        _replace_managed_values(current, generated)
        refreshed_profile_items.append(current)
    profile_items = _canonical_profile_items(refreshed_profile_items)
    jsonld_path = dump_jsonld_items(package / "itc_h2kg_profile.jsonld", profile_items)
    ttl_path = dump_turtle_items(package / "itc_h2kg_profile.ttl", profile_items)
    shapes_path = write_text(package / "itc_h2kg_profile_shapes.ttl", _shacl_profile(review))
    mapping_rows = _mapping_rows(review)
    mapping_csv = _write_csv(package / "itc_mapping_matrix.csv", mapping_rows)
    mapping_md = write_text(package / "itc_mapping_matrix.md", _mapping_markdown(mapping_rows))
    audit_path = _write_csv(package / "itc_duplicate_reuse_audit.csv", _reuse_audit(review, ontology_items))
    overlay = build_decode_itc_overlay(review)
    overlay_path = dump_json(package / "itc_decode_semantic_overlay.json", overlay)

    rdf_validation = _validate_serializations(jsonld_path, ttl_path)
    report = {
        **validation,
        **rdf_validation,
        "status": "passed" if not missing and rdf_validation["equivalent_rdf_statements"] else "failed",
        "missing_h2kg_resources": missing,
        "value_free": True,
        "source_pdf_redistributed": False,
        "decode_source_topology_modified": False,
        "explore_iri": H2KG + MODEL_LOCAL_NAME,
    }
    validation_path = dump_json(package / "itc_validation_report.json", report)
    readme_path = write_text(package / "README.md", _readme(report, review))
    return {
        "status": report["status"],
        "output_dir": str(package),
        "validation": report,
        "overlay": overlay,
        "generated_files": [
            str(path)
            for path in [jsonld_path, ttl_path, shapes_path, mapping_csv, mapping_md, audit_path, overlay_path, validation_path, readme_path]
        ],
    }


def validate_review_registry(review: dict[str, Any]) -> dict[str, Any]:
    fields = list(review.get("fields", []))
    identifiers = [str(field.get("io_id", "")) for field in fields]
    directions = Counter(str(field.get("direction", "")) for field in fields)
    decisions = Counter(str(field.get("decision", "")) for field in fields)
    workflow_roles = Counter(_workflow_role(field) for field in fields)
    intrinsic_roles = Counter(_intrinsic_role(field) for field in fields)
    duplicate_ids = sorted(identifier for identifier, count in Counter(identifiers).items() if count != 1)
    required = {
        "io_id", "direction", "preferred_label", "source_label", "notation", "reported_unit",
        "value_shape", "semantic_role", "h2kg_local_name", "decision", "definition", "page",
        "quantity_kind", "unit", "alternate_labels",
    }
    incomplete = sorted(field.get("io_id", "") for field in fields if required - set(field))
    invalid_roles = sorted(field["io_id"] for field in fields if field.get("semantic_role") not in {"Parameter", "Property", "Data"})
    symbols_as_aliases = sorted(
        field["io_id"]
        for field in fields
        if field.get("notation") and field.get("notation") in field.get("alternate_labels", [])
    )
    rejected_as_aliases = sorted(
        field["io_id"]
        for field in fields
        if set(field.get("rejected_legacy_labels", [])) & set(field.get("alternate_labels", []))
    )
    valid = (
        len(fields) == 44
        and len(set(identifiers)) == 44
        and directions == {"input": 24, "output": 20}
        and decisions == {"new_h2kg_term": 40, "existing_h2kg_mapping": 4}
        and not duplicate_ids
        and not incomplete
        and not invalid_roles
        and not symbols_as_aliases
        and not rejected_as_aliases
    )
    if not valid:
        raise ValueError(
            "Invalid ITC expert registry: "
            f"fields={len(fields)}, directions={dict(directions)}, decisions={dict(decisions)}, "
            f"duplicates={duplicate_ids}, incomplete={incomplete}, roles={invalid_roles}"
        )
    return {
        "status": "passed",
        "input_count": directions["input"],
        "output_count": directions["output"],
        "unique_identifier_count": len(set(identifiers)),
        "new_term_count": decisions["new_h2kg_term"],
        "reused_term_count": decisions["existing_h2kg_mapping"],
        "workflow_role_counts": dict(sorted(workflow_roles.items())),
        "intrinsic_role_counts": dict(sorted(intrinsic_roles.items())),
        "symbols_used_as_alt_labels": symbols_as_aliases,
        "rejected_legacy_labels_used_as_alt_labels": rejected_as_aliases,
        "source_sha256": review["source"]["sha256"],
    }


def build_decode_itc_overlay(review: dict[str, Any]) -> dict[str, Any]:
    """Return a derived profile overlay; no source occurrence or edge is added."""
    validate_review_registry(review)
    fields = {field["io_id"]: field for field in review["fields"]}
    model_iri = review["model"]["iri"]
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    def add_node(iri: str, label: str, role: str, description: str, io_id: str = "") -> None:
        nodes.append({
            "id": iri,
            "label": label,
            "semantic_role": role,
            "canonical_role_iri": H2KG + role,
            "description": description,
            "io_id": io_id,
            "mapping_state": "approved_h2kg",
        })

    def add_edge(source: str, predicate: str, target: str) -> None:
        edges.append({
            "id": f"itc-profile::{len(edges) + 1}",
            "source": source,
            "target": target,
            "predicate": predicate,
            "label": predicate.rsplit("#", 1)[-1],
        })

    add_node(model_iri, review["model"]["preferred_label"], "Process", review["model"]["definition"])
    for local_name, (label, definition) in GROUPS.items():
        add_node(H2KG + local_name, label, "Data", definition)
    for field in review["fields"]:
        iri = H2KG + field["h2kg_local_name"]
        add_node(iri, field["preferred_label"], _intrinsic_role(field), field["definition"], field["io_id"])
    for field in review["fields"]:
        iri = H2KG + field["h2kg_local_name"]
        if _workflow_role(field) == "Parameter":
            record_iri = f"https://w3id.org/h2kg/profiles/itc/parameter/{field['io_id']}"
            add_node(
                record_iri,
                f"{field['preferred_label']} parameter record",
                "Parameter",
                "A value-free ITC profile record that gives this property a contextual model-input role.",
                field["io_id"],
            )
            add_edge(model_iri, HAS_PARAMETER, record_iri)
            add_edge(record_iri, OF_PROPERTY, iri)
    input_properties = [field for field in review["fields"] if field["direction"] == "input" and _workflow_role(field) == "InputDataPoint"]
    result_properties = [field for field in review["fields"] if field["direction"] == "output" and _intrinsic_role(field) == "Property"]
    input_dataset = H2KG + "InkToCompositionModelInputDataset"
    result_dataset = H2KG + "InkToCompositionModelScalarResultDataset"
    add_edge(model_iri, HAS_INPUT_DATA, input_dataset)
    add_edge(model_iri, HAS_OUTPUT_DATA, result_dataset)
    for local_name in ARRAY_GROUPS:
        add_edge(model_iri, HAS_OUTPUT_DATA, H2KG + local_name)
    for field, suffix, dataset in [
        *((field, "InputField", input_dataset) for field in input_properties),
        *((field, "ResultField", result_dataset) for field in result_properties),
    ]:
        field_iri = H2KG + f"ITC{field['h2kg_local_name']}{suffix}"
        add_node(field_iri, f"ITC {field['preferred_label']} {suffix.replace('Field', ' field').lower()}", "Data", "A value-free ITC profile field template; it is not an observation or experimental instance.", field["io_id"])
        add_edge(dataset, HAS_PART, field_iri)
        add_edge(field_iri, OF_PROPERTY, H2KG + field["h2kg_local_name"])
    for group, identifiers in ARRAY_GROUPS.items():
        for identifier in identifiers:
            add_edge(H2KG + group, HAS_PART, H2KG + fields[identifier]["h2kg_local_name"])
    return {
        "profile_id": review["profile_id"],
        "workflow_id": WORKFLOW_ID,
        "badge": "Expert-reviewed ITC profile",
        "source_occurrence_id": MODEL_SOURCE_OCCURRENCE,
        "source_sha256": review["source"]["sha256"],
        "nodes": nodes,
        "edges": edges,
    }


def apply_itc_mapping_overrides(snapshot: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    """Apply reviewed mappings without changing source labels, IDs, or edges."""
    validate_review_registry(review)
    snapshot = deepcopy(snapshot)
    fields = {field["io_id"]: field for field in review["fields"]}
    label_counts = Counter(field["source_label"].strip().casefold() for field in review["fields"])
    exact_label_fields = {
        field["source_label"].strip().casefold(): field
        for field in review["fields"]
        if label_counts[field["source_label"].strip().casefold()] == 1
    }
    legacy_labels = [
        (label.strip().casefold(), field)
        for field in review["fields"]
        for label in field.get("rejected_legacy_labels", [])
    ]
    legacy_counts = Counter(label for label, _field in legacy_labels)
    exact_label_fields.update({label: field for label, field in legacy_labels if legacy_counts[label] == 1})
    node_field_ids = {
        "n1": "IO_CMP_ICRatio",
        "n2": "IO_MAT_IonomerDensityDry",
        "n3": "IO_MAT_IonomerInitialFilmThickness",
        "n5": "IO_CMP_IonomerCatalystDispersionParameter",
        "n6": "IO_MAT_CatalystActiveParticleDiameter",
        "n7": "IO_CMP_CatalystSupportRatio",
        "n8": "IO_MAT_CatalystActiveParticleDensity",
        "n11": "IO_MAT_CatalystActiveParticleContactAngle",
        "n12": "IO_MAT_CatalystSupportContactAngle",
        "n16": "IO_CMP_CCLEffectiveIonomerCoverage",
        "n17": "IO_CMP_CCLIonomerEffectiveFilmThickness",
    }
    for workflow in snapshot.get("workflows", []):
        for node in workflow.get("nodes", []):
            source_id = str(node.get("source_id", ""))
            exact_field = exact_label_fields.get(str(node.get("label", "")).strip().casefold())
            if exact_field is not None:
                node["mapping_override"] = _mapping_override(
                    H2KG + exact_field["h2kg_local_name"],
                    exact_field["preferred_label"],
                    _intrinsic_role(exact_field),
                    f"Unambiguous exact-label mapping confirmed by the expert ITC registry for {exact_field['io_id']}.",
                )
            if str(node.get("label", "")).strip().casefold() in {
                review["model"]["preferred_label"].casefold(),
                *(label.casefold() for label in review["model"]["alternate_labels"]),
            }:
                node["mapping_override"] = _mapping_override(
                    review["model"]["iri"],
                    review["model"]["preferred_label"],
                    "Process",
                    "Expert-reviewed ITC model anchor; the source occurrence remains unchanged.",
                )
            if workflow.get("id") != WORKFLOW_ID:
                continue
            workflow["expert_profile"] = {
                "id": review["profile_id"],
                "badge": "Expert-reviewed ITC profile",
                "source_sha256": review["source"]["sha256"],
            }
            if source_id == "n22":
                node["mapping_override"] = _mapping_override(
                    review["model"]["iri"],
                    review["model"]["preferred_label"],
                    "Process",
                    "Expert-reviewed ITC model anchor; the original GraphML occurrence remains unchanged.",
                )
            elif source_id in node_field_ids:
                field = fields[node_field_ids[source_id]]
                correction = " Corrected expert semantics supersede the historical source label for mapping only." if field.get("rejected_legacy_labels") else ""
                node["mapping_override"] = _mapping_override(
                    H2KG + field["h2kg_local_name"],
                    field["preferred_label"],
                    _intrinsic_role(field),
                    f"Expert-reviewed mapping for stable identifier {field['io_id']}.{correction}",
                )
    return snapshot


def attach_itc_profile_overlay(graph: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    """Attach a derived visual overlay while keeping source graph counts fixed."""
    overlay = build_decode_itc_overlay(review)
    graph.setdefault("expert_profile_overlays", []).append(overlay)
    for workflow in graph.get("workflows", []):
        if workflow.get("id") == WORKFLOW_ID:
            workflow["expert_profile"] = {
                "id": review["profile_id"],
                "badge": overlay["badge"],
                "field_count": len(review["fields"]),
                "source_sha256": review["source"]["sha256"],
            }
            workflow.setdefault("downloads", []).extend([
                {"href": "../examples/itc_pilot/itc_h2kg_profile.jsonld", "label": "Download expert-reviewed ITC JSON-LD profile"},
                {"href": "../examples/itc_pilot/itc_h2kg_profile.ttl", "label": "Download expert-reviewed ITC Turtle profile"},
                {"href": "../examples/itc_pilot/itc_mapping_matrix.csv", "label": "Download ITC mapping matrix"},
                {"href": "../examples/itc_pilot/itc_validation_report.json", "label": "Download ITC validation report"},
            ])
    return overlay


def _mapping_override(anchor_iri: str, label: str, role: str, evidence: str) -> dict[str, Any]:
    return {
        "state": "approved_h2kg",
        "decision": "existing_h2kg_mapping",
        "anchor_iri": anchor_iri,
        "anchor_label": label,
        "canonical_role_iri": H2KG + role,
        "semantic_role": role,
        "role_assignment": "expert_review",
        "confidence": "expert_reviewed",
        "evidence": evidence,
    }


def _profile_items(review: dict[str, Any]) -> list[dict[str, Any]]:
    source_iri = review["source"]["scientific_source"]
    fields = list(review["fields"])
    items: list[dict[str, Any]] = []
    model = review["model"]
    model_item = _term_item(model["iri"], model["preferred_label"], model["definition"], "Process", source_iri, model["alternate_labels"])
    parameters = [field for field in fields if _workflow_role(field) == "Parameter"]
    model_item[HAS_PARAMETER] = [{"@id": H2KG + field["h2kg_local_name"]} for field in parameters]
    model_item[HAS_INPUT_DATA] = [{"@id": H2KG + "InkToCompositionModelInputDataset"}]
    model_item[HAS_OUTPUT_DATA] = [
        {"@id": H2KG + "InkToCompositionModelScalarResultDataset"},
        {"@id": H2KG + "CCLWaterRetentionCurveDataset"},
        {"@id": H2KG + "CCLRefinedPoreSizeDistributionDataset"},
        {"@id": H2KG + "CCLContactAngleDistributionDataset"},
    ]
    items.append(model_item)

    for field in fields:
        iri = H2KG + field["h2kg_local_name"]
        item = _term_item(iri, field["preferred_label"], field["definition"], _intrinsic_role(field), source_iri, field["alternate_labels"])
        item[NOTATION] = [{"@value": field["notation"]}]
        item[IDENTIFIER] = [{"@value": field["io_id"]}]
        item[HAS_QUANTITY_VALUE] = [{"@id": _guidance_iri(field)}]
        items.append(item)
        guidance = {
            "@id": _guidance_iri(field),
            "@type": [QUDT_QUANTITY_VALUE],
            DESCRIPTION: [{"@language": "en", "@value": _guidance_description(field)}],
            QUDT_UNIT: [{"@id": UNIT + field["unit"]}],
            QUDT_QUANTITY_KIND: [{"@id": QK + field["quantity_kind"]}],
            SOURCE: [{"@id": source_iri}],
        }
        items.append(guidance)

    input_properties = [field for field in fields if field["direction"] == "input" and _workflow_role(field) == "InputDataPoint"]
    result_properties = [field for field in fields if field["direction"] == "output" and _intrinsic_role(field) == "Property"]
    field_items: list[dict[str, Any]] = []
    group_parts: dict[str, list[str]] = {key: [] for key in GROUPS}
    for field, suffix, group in [
        *((field, "InputField", "InkToCompositionModelInputDataset") for field in input_properties),
        *((field, "ResultField", "InkToCompositionModelScalarResultDataset") for field in result_properties),
    ]:
        local_name = f"ITC{field['h2kg_local_name']}{suffix}"
        field_iri = H2KG + local_name
        field_items.append({
            "@id": field_iri,
            "@type": [H2KG + "DataPoint"],
            PREF_LABEL: [{"@language": "en", "@value": f"ITC {field['preferred_label']} {suffix.replace('Field', ' field').lower()}"}],
            DESCRIPTION: [{"@language": "en", "@value": "A value-free schema-template field in the expert-reviewed ITC profile; it does not assert an observation or experimental result."}],
            IDENTIFIER: [{"@value": field["io_id"]}],
            OF_PROPERTY: [{"@id": H2KG + field["h2kg_local_name"]}],
            SOURCE: [{"@id": source_iri}],
        })
        group_parts[group].append(field_iri)
    for group, identifiers in ARRAY_GROUPS.items():
        group_parts[group].extend(H2KG + next(field["h2kg_local_name"] for field in fields if field["io_id"] == identifier) for identifier in identifiers)
    for local_name, (label, definition) in GROUPS.items():
        group_item = _term_item(H2KG + local_name, label, definition, "Data", source_iri, [])
        group_item[HAS_PART] = [{"@id": iri} for iri in group_parts[local_name]]
        items.append(group_item)
    items.extend(field_items)
    return items


def _term_item(iri: str, label: str, definition: str, role: str, source: str, aliases: list[str]) -> dict[str, Any]:
    item: dict[str, Any] = {
        "@id": iri,
        "@type": [H2KG + role],
        PREF_LABEL: [{"@language": "en", "@value": label}],
        RDFS + "label": [{"@language": "en", "@value": label}],
        DESCRIPTION: [{"@language": "en", "@value": definition}],
        SOURCE: [{"@id": source}],
    }
    if aliases:
        item[ALT_LABEL] = [{"@language": "en", "@value": alias} for alias in aliases]
    return item


def _intrinsic_role(field: dict[str, Any]) -> str:
    """All scalar scientific quantities are Properties, regardless of use."""

    return "Property" if field.get("semantic_role") == "Parameter" else str(field.get("semantic_role", ""))


def _workflow_role(field: dict[str, Any]) -> str:
    if field.get("direction") == "input" and field.get("semantic_role") == "Parameter":
        return "Parameter"
    if field.get("direction") == "input" and _intrinsic_role(field) == "Property":
        return "InputDataPoint"
    if field.get("direction") == "output" and _intrinsic_role(field) == "Property":
        return "OutputDataPoint"
    return "InputData" if field.get("direction") == "input" else "OutputData"


def _canonical_profile_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove legacy class-to-class workflow assertions from the profile module."""

    result = deepcopy(items)
    workflow_predicates = {
        HAS_PARAMETER,
        HAS_INPUT_DATA,
        HAS_OUTPUT_DATA,
        HAS_PART,
        OF_PROPERTY,
    }
    relation = DCTERMS + "relation"
    for item in result:
        quantity_guidance = item.pop(HAS_QUANTITY_VALUE, None)
        for predicate in workflow_predicates:
            item.pop(predicate, None)
        if quantity_guidance:
            item[relation] = quantity_guidance
    return result


def _replace_managed_values(current: dict[str, Any], generated: dict[str, Any]) -> None:
    managed = {"@type", PREF_LABEL, ALT_LABEL, RDFS + "label", DESCRIPTION, SOURCE, NOTATION, IDENTIFIER, HAS_QUANTITY_VALUE, HAS_PARAMETER, HAS_INPUT_DATA, HAS_OUTPUT_DATA, HAS_PART, OF_PROPERTY, QUDT_UNIT, QUDT_QUANTITY_KIND}
    for key in managed:
        if key in generated:
            current[key] = generated[key]


def _guidance_iri(field: dict[str, Any]) -> str:
    return H2KG + "ITCQuantityGuidance_" + field["h2kg_local_name"]


def _guidance_description(field: dict[str, Any]) -> str:
    suffix = " Values are normalized per unit carbon mass." if field.get("normalization_basis") == "CarbonMass" else ""
    return f"Value-free QUDT guidance for {field['preferred_label']}; the expert source reports {field['reported_unit']}.{suffix}"


def _mapping_rows(review: dict[str, Any]) -> list[dict[str, Any]]:
    return [{
        "io_id": field["io_id"],
        "direction": field["direction"],
        "source_label": field["source_label"],
        "preferred_label": field["preferred_label"],
        "symbol": field["notation"],
        "intrinsic_role": _intrinsic_role(field),
        "workflow_role": _workflow_role(field),
        "decision": field["decision"],
        "h2kg_iri": H2KG + field["h2kg_local_name"],
        "reported_unit": field["reported_unit"],
        "qudt_unit": UNIT + field["unit"],
        "qudt_quantity_kind": QK + field["quantity_kind"],
        "definition": field["definition"],
        "page": field["page"],
    } for field in review["fields"]]


def _reuse_audit(review: dict[str, Any], ontology_items: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [{
        "io_id": field["io_id"],
        "decision": field["decision"],
        "h2kg_iri": H2KG + field["h2kg_local_name"],
        "resource_present": str(H2KG + field["h2kg_local_name"] in ontology_items).lower(),
        "rejected_legacy_labels": "; ".join(field.get("rejected_legacy_labels", [])),
        "public_alt_labels": "; ".join(field.get("alternate_labels", [])),
    } for field in review["fields"]]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> Path:
    ensure_dir(path.parent)
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _mapping_markdown(rows: list[dict[str, Any]]) -> str:
    lines = ["# ITC expert-review mapping matrix", "", "| IO identifier | Direction | Preferred term | Intrinsic role | Workflow role | Outcome | H2KG IRI |", "|---|---|---|---|---|---|---|"]
    lines.extend(f"| `{row['io_id']}` | {row['direction']} | {row['preferred_label']} | {row['intrinsic_role']} | {row['workflow_role']} | {row['decision']} | `{row['h2kg_iri']}` |" for row in rows)
    return "\n".join(lines) + "\n"


def _validate_serializations(jsonld_path: Path, ttl_path: Path) -> dict[str, Any]:
    try:
        from rdflib import Graph
        jsonld_graph = Graph().parse(jsonld_path, format="json-ld")
        ttl_graph = Graph().parse(ttl_path, format="turtle")
        return {
            "jsonld_triple_count": len(jsonld_graph),
            "turtle_triple_count": len(ttl_graph),
            "equivalent_rdf_statements": set(jsonld_graph) == set(ttl_graph),
        }
    except Exception as exc:  # pragma: no cover - dependency/environment failure
        return {"jsonld_triple_count": 0, "turtle_triple_count": 0, "equivalent_rdf_statements": False, "rdf_error": str(exc)}


def _shacl_profile(review: dict[str, Any]) -> str:
    parameters = [field for field in review["fields"] if _workflow_role(field) == "Parameter"]
    parameter_shapes = " ".join(
        f"[ sh:class h2kg:{field['h2kg_local_name']} ]" for field in parameters
    )
    return f"""@prefix h2kg: <{H2KG}> .
@prefix rdf: <{COMMON_CONTEXT['rdf']}> .
@prefix sh: <http://www.w3.org/ns/shacl#> .

h2kg:InkToCompositionModelProfileShape a sh:NodeShape ;
  sh:targetClass h2kg:InkToCompositionModel ;
  sh:property [ sh:path h2kg:hasParameter ; sh:minCount 16 ; sh:class h2kg:Parameter ] ;
  sh:property [ sh:path h2kg:hasInputData ; sh:qualifiedMinCount 1 ; sh:qualifiedValueShape [ sh:class h2kg:InkToCompositionModelInputDataset ] ] ;
  sh:property [ sh:path h2kg:hasOutputData ; sh:qualifiedMinCount 1 ; sh:qualifiedValueShape [ sh:class h2kg:InkToCompositionModelScalarResultDataset ] ] ;
  sh:property [ sh:path h2kg:hasOutputData ; sh:qualifiedMinCount 1 ; sh:qualifiedValueShape [ sh:class h2kg:CCLWaterRetentionCurveDataset ] ] ;
  sh:property [ sh:path h2kg:hasOutputData ; sh:qualifiedMinCount 1 ; sh:qualifiedValueShape [ sh:class h2kg:CCLRefinedPoreSizeDistributionDataset ] ] ;
  sh:property [ sh:path h2kg:hasOutputData ; sh:qualifiedMinCount 1 ; sh:qualifiedValueShape [ sh:class h2kg:CCLContactAngleDistributionDataset ] ] .

h2kg:InkToCompositionModelParameterRecordShape a sh:NodeShape ;
  sh:targetObjectsOf h2kg:hasParameter ;
  sh:class h2kg:Parameter ;
  sh:property [
    sh:path h2kg:ofProperty ; sh:minCount 1 ; sh:maxCount 1 ;
    sh:node [ sh:or ( {parameter_shapes} ) ]
  ] .
"""


def _readme(report: dict[str, Any], review: dict[str, Any]) -> str:
    return f"""# Expert-reviewed Ink-to-Composition Model profile

This value-free profile integrates {report['unique_identifier_count']} reviewed ITC interface concepts into H2KG while preserving the original DECODE GraphML workflow. It contains {report['input_count']} inputs and {report['output_count']} outputs. Four terms reuse existing H2KG IRIs and 40 terms are controlled additions.

Scientific source: {review['source']['scientific_source']}

Source fingerprint: `{review['source']['sha256']}`. The reviewed PDF is not redistributed.

Explore: `https://vimilabs.github.io/AIMWORKS/pages/explore.html?iri={H2KG}{MODEL_LOCAL_NAME}`

Symbols are represented with `skos:notation`; rejected historical labels are retained only in the audit. The Turtle and JSON-LD files contain the reviewed vocabulary module and quantity guidance. Contextual model-input and output expectations are expressed in SHACL, so no scientific Property class is reclassified as a Parameter.
"""
