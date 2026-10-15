from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from rdflib import BNode, Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import DCTERMS, OWL, PROV, SKOS

from .utils import (
    COMMON_CONTEXT,
    ensure_dir,
    legacy_source_identifier,
    portable_legacy_iri,
    write_text,
)


H2KG = Namespace("https://w3id.org/h2kg/hydrogen-ontology#")
PROFILE = Namespace("https://w3id.org/h2kg/hydrogen-ontology/profile/")
QUDT = Namespace("http://qudt.org/schema/qudt/")
SH = Namespace("http://www.w3.org/ns/shacl#")

NORMALIZATION_CHARACTERISTICS = {
    "CarbonMass",
    "SampleMass",
    "CatalystMass",
    "PtMass",
    "GeometricArea",
}


def build_semantic_profile_release(
    source: Graph,
    taxonomy: Graph,
    decisions: list[Any],
    config: dict[str, Any],
    ontology_dir: str | Path,
    reports_dir: str | Path,
) -> dict[str, Any]:
    """Migrate legacy class-to-class workflow assertions to SHACL profiles.

    H2KG v1 used reusable vocabulary resources as if they were workflow
    occurrences.  This builder records every such assertion, emits a
    role-compatible profile constraint, and keeps the canonical taxonomy free
    of occurrence-level assertions.
    """

    ontology_dir = ensure_dir(Path(ontology_dir))
    reports_dir = ensure_dir(Path(reports_dir))
    decision_by_iri = {str(decision.iri): decision for decision in decisions}
    active_iris = {
        iri
        for iri, decision in decision_by_iri.items()
        if decision.disposition == "active_local_class"
    }
    replacements = {
        iri: str(decision.replacement_iri)
        for iri, decision in decision_by_iri.items()
        if decision.replacement_iri
    }
    object_properties = {
        predicate
        for predicate in source.subjects(RDF.type, OWL.ObjectProperty)
        if isinstance(predicate, URIRef)
    }
    object_properties.update(
        {
            H2KG.usesSoftware,
            H2KG.usesReferenceElectrode,
            H2KG.hasReferenceScale,
            H2KG.hasMeasurementSubject,
        }
    )

    graph = Graph()
    _bind_namespaces(graph)
    profile_ontology = URIRef("https://w3id.org/h2kg/hydrogen-ontology/profiles")
    graph.add((profile_ontology, RDF.type, OWL.Ontology))
    graph.add((profile_ontology, OWL.imports, URIRef(str(config["version_iri"]))))
    graph.add((profile_ontology, OWL.versionInfo, Literal(str(config["version"]))))
    graph.add((profile_ontology, DCTERMS.title, Literal("H2KG workflow-use profiles", lang="en")))
    graph.add(
        (
            profile_ontology,
            DCTERMS.description,
            Literal(
                "Value-free SHACL profiles that represent contextual workflow use without changing the intrinsic taxonomy of H2KG concepts.",
                lang="en",
            ),
        )
    )

    rows: list[dict[str, Any]] = []
    emitted_constraints: set[tuple[str, tuple[str, ...], str]] = set()
    direct_record_constraints: set[tuple[str, str, str]] = set()
    parameter_targets: set[str] = set()

    assertions = sorted(
        (
            subject,
            predicate,
            obj,
        )
        for subject, predicate, obj in source
        if isinstance(subject, URIRef)
        and str(subject) in decision_by_iri
        and predicate in object_properties
        and isinstance(obj, (URIRef, BNode))
    )
    for subject, predicate, obj in assertions:
        source_iri = replacements.get(str(subject), str(subject))
        source_decision = decision_by_iri.get(source_iri, decision_by_iri[str(subject)])
        raw_target_iri = str(obj)
        target_iri = (
            replacements.get(raw_target_iri, portable_legacy_iri(raw_target_iri))
            if isinstance(obj, URIRef)
            else str(obj)
        )
        target_decision = decision_by_iri.get(target_iri)
        migration = _migration_for_assertion(
            source,
            source_decision,
            predicate,
            obj,
            target_decision,
        )
        if str(migration.get("constraint_target", "")).startswith("file:"):
            migration["constraint_target"] = portable_legacy_iri(str(migration["constraint_target"]))
        row_id = _stable_id(str(subject), str(predicate), target_iri)
        shape_iri = str(PROFILE[f"Shape_{_fragment(source_iri)}"])
        property_shape_iri = str(PROFILE[f"Property_{row_id}"])
        row = {
            "migration_id": row_id,
            "source_iri": str(subject),
            "canonical_source_iri": source_iri,
            "source_label": source_decision.label,
            "source_intrinsic_role": source_decision.corrected_semantic_role,
            "legacy_predicate_iri": str(predicate),
            "legacy_predicate": _fragment(str(predicate)),
            "target_iri": target_iri,
            "canonical_target_iri": target_iri,
            "legacy_target_identifier": legacy_source_identifier(raw_target_iri),
            "target_label": _label(source, obj, target_decision),
            "target_intrinsic_role": (
                target_decision.corrected_semantic_role
                if target_decision
                else _external_role(source, obj)
            ),
            "migration_outcome": migration["outcome"],
            "canonical_predicate_iri": migration.get("predicate", ""),
            "display_relation": migration["display"],
            "path_iris": migration.get("path", []),
            "path_label": " / ".join(_fragment(value) for value in migration.get("path", [])),
            "profile_shape_iri": shape_iri if migration.get("path") else "",
            "property_shape_iri": property_shape_iri if migration.get("path") else "",
            "status": migration["status"],
            "rationale": migration["rationale"],
        }
        rows.append(row)

        if source_iri not in active_iris or not migration.get("path"):
            continue
        path = tuple(migration["path"])
        constraint_target = str(migration.get("constraint_target", target_iri))
        constraint_key = (source_iri, path, constraint_target)
        if constraint_key in emitted_constraints:
            continue
        emitted_constraints.add(constraint_key)
        _add_profile_constraint(
            graph,
            URIRef(shape_iri),
            URIRef(source_iri),
            URIRef(property_shape_iri),
            [URIRef(value) for value in path],
            URIRef(constraint_target) if constraint_target else None,
            migration["display"],
            migration["rationale"],
            source,
            obj,
            quantity_guidance=migration.get("quantity_guidance", False),
        )

        record_class = migration.get("record_class")
        if record_class:
            record_predicate = path[0]
            direct_key = (source_iri, record_predicate, str(record_class))
            if direct_key not in direct_record_constraints:
                direct_record_constraints.add(direct_key)
                record_shape = URIRef(PROFILE[f"Record_{_stable_id(*direct_key)}"])
                _add_profile_constraint(
                    graph,
                    URIRef(shape_iri),
                    URIRef(source_iri),
                    record_shape,
                    [URIRef(record_predicate)],
                    URIRef(str(record_class)),
                    f"uses {_label_for_class(record_class)} record",
                    "The intermediate record preserves contextual workflow role separately from scientific identity.",
                    source,
                    obj,
                )

        if migration["outcome"] == "parameter_record_property_path":
            parameter_targets.add(constraint_target)

    scope_note = Literal(
        "This characteristic can be selected as a workflow parameter through a Parameter record; contextual parameter use does not alter its intrinsic classification.",
        lang="en",
    )
    for iri in sorted(parameter_targets):
        taxonomy.add((URIRef(iri), SKOS.scopeNote, scope_note))

    audits = _class_audit(decisions, rows)
    workflow_ttl = ontology_dir / "h2kg-v2-workflow-profiles.ttl"
    workflow_jsonld = ontology_dir / "h2kg-v2-workflow-profiles.jsonld"
    complete_ttl = ontology_dir / "h2kg-v2-complete.ttl"
    complete_jsonld = ontology_dir / "h2kg-v2-complete.jsonld"
    migration_json = ontology_dir / "relation_migration_registry.json"
    migration_csv = ontology_dir / "relation_migration_registry.csv"
    usage_json = ontology_dir / "workflow_usage_registry.json"
    usage_csv = ontology_dir / "workflow_usage_registry.csv"
    audit_json = ontology_dir / "semantic_role_audit.json"
    audit_csv = ontology_dir / "semantic_role_audit.csv"
    validation_json = reports_dir / "semantic_role_validation.json"

    _serialize(graph, workflow_ttl, "turtle")
    _serialize(graph, workflow_jsonld, "json-ld")
    complete = Graph()
    _bind_namespaces(complete)
    for triple in taxonomy:
        complete.add(triple)
    for triple in graph:
        complete.add(triple)
    _serialize(complete, complete_ttl, "turtle")
    _serialize(complete, complete_jsonld, "json-ld")

    generated_at = datetime.now(timezone.utc).isoformat()
    registry_header = {
        "schema_version": "h2kg-semantic-role-migration/v1",
        "ontology_version": str(config["version"]),
        "generated_at": generated_at,
        "legacy_assertion_count": len(rows),
        "migrated_assertion_count": len(rows),
    }
    write_text(migration_json, json.dumps({**registry_header, "migrations": rows}, indent=2, ensure_ascii=False))
    _write_csv(migration_csv, rows)
    usage_rows = [row for row in rows if row.get("profile_shape_iri")]
    write_text(
        usage_json,
        json.dumps(
            {
                "schema_version": "h2kg-workflow-usage-registry/v1",
                "ontology_version": str(config["version"]),
                "generated_at": generated_at,
                "usage_count": len(usage_rows),
                "usage_edges": usage_rows,
            },
            indent=2,
            ensure_ascii=False,
        ),
    )
    _write_csv(usage_csv, usage_rows)
    write_text(
        audit_json,
        json.dumps(
            {
                "schema_version": "h2kg-semantic-role-audit/v1",
                "ontology_version": str(config["version"]),
                "generated_at": generated_at,
                "classes": audits,
            },
            indent=2,
            ensure_ascii=False,
        ),
    )
    _write_csv(audit_csv, audits)

    validation = _validate_semantic_release(
        taxonomy,
        graph,
        complete,
        decisions,
        rows,
        workflow_ttl,
        workflow_jsonld,
        complete_ttl,
        complete_jsonld,
        object_properties,
    )
    write_text(validation_json, json.dumps(validation, indent=2, ensure_ascii=False))
    if not validation["conforms"]:
        raise ValueError("H2KG semantic-role validation failed: " + "; ".join(validation["errors"][:8]))

    return {
        "version": str(config["version"]),
        "workflow_profiles_ttl": str(workflow_ttl),
        "workflow_profiles_jsonld": str(workflow_jsonld),
        "complete_ttl": str(complete_ttl),
        "complete_jsonld": str(complete_jsonld),
        "relation_migration_registry": str(migration_json),
        "workflow_usage_registry": str(usage_json),
        "semantic_role_audit": str(audit_json),
        "validation": str(validation_json),
        "legacy_assertion_count": len(rows),
        "workflow_usage_count": len(usage_rows),
        "parameter_property_path_count": sum(
            1 for row in rows if row["migration_outcome"] == "parameter_record_property_path"
        ),
        "unsupported_legacy_assertion_count": sum(
            1 for row in rows if row["status"] == "unsupported-documented"
        ),
        "conforms": validation["conforms"],
    }


def _migration_for_assertion(
    source: Graph,
    source_decision: Any,
    predicate: URIRef,
    obj: URIRef | BNode,
    target_decision: Any | None,
) -> dict[str, Any]:
    source_role = source_decision.corrected_semantic_role
    target_role = target_decision.corrected_semantic_role if target_decision else _external_role(source, obj)
    target_name = target_decision.local_name if target_decision else _fragment(str(obj))
    target_class = str(target_decision.iri) if target_decision else str(obj)
    predicate_name = _fragment(str(predicate))

    if predicate == H2KG.hasQuantityValue:
        return {
            "outcome": "quantity_value_guidance",
            "predicate": str(H2KG.hasQuantityValue),
            "path": [str(H2KG.hasQuantityValue)],
            "constraint_target": str(QUDT.QuantityValue),
            "display": "has quantity value guidance",
            "status": "migrated-profile",
            "rationale": "A legacy class-level quantity-value template is expressed as optional QUDT guidance on property occurrences.",
            "quantity_guidance": True,
        }

    if predicate == H2KG.hasParameter:
        if target_name in NORMALIZATION_CHARACTERISTICS or target_role == "NormalizationBasis":
            if target_role == "NormalizationBasis":
                return _direct(
                    H2KG.normalizedTo,
                    target_class,
                    "uses normalization basis",
                    "normalization_basis_record",
                    "A normalization-basis specification remains an information record rather than a scientific property.",
                )
            return _path(
                [H2KG.normalizedTo, H2KG.ofProperty],
                target_class,
                "normalizes to property",
                "normalization_record_property_path",
                "The intrinsic quantity is reached through a normalization-basis record.",
                H2KG.NormalizationBasis,
            )
        if target_role == "Characteristic":
            return _path(
                [H2KG.hasParameter, H2KG.ofProperty],
                target_class,
                "uses as parameter",
                "parameter_record_property_path",
                "The characteristic is selected contextually through a Parameter record and remains a Property in the taxonomy.",
                H2KG.Parameter,
            )
        if target_role == "Matter":
            return _direct(
                H2KG.hasInputMaterial,
                target_class,
                "uses input material",
                "parameter_material_to_input_material",
                "A material cannot be a Parameter record; it is represented as a material input.",
            )
        if target_role == "Data":
            return _direct(
                H2KG.hasInputData,
                target_class,
                "uses input data",
                "parameter_data_to_input_data",
                "A dataset cannot be a Parameter record; it is represented as data input.",
            )
        if target_role in {"Process", "Manufacturing", "Measurement"}:
            return _direct(
                H2KG.hasSubProcess,
                target_class,
                "has subprocess",
                "parameter_activity_to_subprocess",
                "An activity cannot be a Parameter record; it is represented as a subprocess profile requirement.",
            )
        if target_role in {"Specification", "ReferenceScale"}:
            return _direct(
                H2KG.hasReferenceScale,
                target_class,
                "uses reference scale",
                "parameter_specification_to_reference_scale",
                "The referenced specification is represented through the dedicated reference-scale relation.",
            )
        if target_role in {"Parameter", "ParameterRecord"}:
            return _direct(
                H2KG.hasParameter,
                target_class,
                "has parameter record",
                "genuine_parameter_record",
                "The target is intrinsically a parameter record.",
            )
        return _unsupported(
            "unsupported_parameter_target",
            f"The legacy hasParameter target has intrinsic role {target_role or 'unknown'} and no defensible canonical parameter path.",
        )

    if predicate == H2KG.usesInstrument:
        if target_role in {"Instrument", "ReferenceElectrode"}:
            return _direct(
                H2KG.usesInstrument,
                target_class,
                "uses instrument",
                "instrument_use",
                "The target is intrinsically an instrument or instrument component used in the activity.",
            )
        if target_role == "SoftwareArtifact":
            return _direct(
                H2KG.usesSoftware,
                target_class,
                "uses software",
                "instrument_software_to_uses_software",
                "Software is represented through usesSoftware rather than usesInstrument.",
            )
        if target_role in {"Process", "Measurement", "Manufacturing"}:
            return _direct(
                H2KG.hasSubProcess,
                target_class,
                "has subprocess",
                "instrument_activity_to_subprocess",
                "A method or measurement cannot be an instrument; it is represented as a subprocess.",
            )
        if target_role == "Matter" and source_role == "Measurement":
            return _direct(
                H2KG.hasMeasurementSubject,
                target_class,
                "has measurement subject",
                "instrument_matter_to_measurement_subject",
                "A material or electrochemical component investigated by a measurement is represented as its measurement subject.",
            )
        if target_role == "Matter":
            return _direct(
                PROV.used,
                target_class,
                "uses equipment or component",
                "instrument_component_to_prov_used",
                "The activity uses the component, but the component is not intrinsically an Instrument class.",
            )
        if target_role == "External":
            return _direct(
                H2KG.usesInstrument,
                target_class,
                "uses instrument",
                "external_instrument_use",
                "The imported target is retained as the instrument class supplied by the source ontology.",
            )
        return _unsupported(
            "unsupported_instrument_target",
            f"The legacy usesInstrument target has intrinsic role {target_role or 'unknown'}.",
        )

    if predicate in {H2KG.measures, H2KG.hasProperty}:
        if target_role == "Characteristic":
            return _direct(
                H2KG.measures,
                target_class,
                "measures property",
                "measurement_property",
                "The measurement targets a property occurrence whose class identifies the measured characteristic.",
            )
        if target_role in {"Measurement", "Process"}:
            return _direct(
                H2KG.hasSubProcess,
                target_class,
                "has subprocess",
                "measurement_target_to_subprocess",
                "A measurement or process cannot be the value of measures; it is represented as a subprocess.",
            )
        return _unsupported(
            "unsupported_measures_target",
            f"The legacy measures target has intrinsic role {target_role or 'unknown'} rather than Characteristic.",
        )

    if predicate == H2KG.referenceElectrode:
        if source_role == "Characteristic":
            return _direct(
                H2KG.hasReferenceScale,
                str(H2KG.ReferenceScale),
                "uses reference scale",
                "reference_electrode_to_reference_scale",
                "For a reported potential characteristic, the legacy electrode label identifies the reference scale used to express the value.",
            )
        return _direct(
            H2KG.usesReferenceElectrode,
            target_class,
            "uses reference electrode",
            "reference_electrode_use",
            "For a measurement, the physical reference electrode is part of the measurement arrangement.",
        )

    if predicate == H2KG.normalizedTo:
        if target_name == "PeakPowerDensity":
            return _unsupported(
                "unsupported_normalization_target",
                "Peak power density is a result characteristic, not a scientifically defensible normalization basis for platinum utilization.",
            )
        if target_role == "Characteristic":
            return _path(
                [H2KG.normalizedTo, H2KG.ofProperty],
                target_class,
                "normalizes to property",
                "normalization_record_property_path",
                "The normalization quantity is reached through a NormalizationBasis record.",
                H2KG.NormalizationBasis,
            )
        if target_role == "NormalizationBasis":
            return _direct(
                H2KG.normalizedTo,
                target_class,
                "uses normalization basis",
                "normalization_basis_record",
                "The target is intrinsically a normalization-basis specification.",
            )
        return _unsupported(
            "unsupported_normalization_target",
            f"The target has intrinsic role {target_role or 'unknown'} and cannot serve as a normalization basis without additional evidence.",
        )

    if predicate == H2KG.ofProperty and source_role != "DataPoint":
        return _unsupported(
            "property_to_property_legacy_assertion",
            "A Property class cannot itself be an information record that points to another Property through ofProperty.",
        )

    display = _humanize(predicate_name)
    return _direct(
        predicate,
        target_class,
        display,
        "direct_profile_relation",
        "The source relation is retained as a value-free SHACL workflow-use constraint rather than an OWL class assertion.",
    )


def _direct(
    predicate: URIRef,
    target: str,
    display: str,
    outcome: str,
    rationale: str,
) -> dict[str, Any]:
    return {
        "outcome": outcome,
        "predicate": str(predicate),
        "path": [str(predicate)],
        "constraint_target": target,
        "display": display,
        "status": "migrated-profile",
        "rationale": rationale,
    }


def _path(
    path: Iterable[URIRef],
    target: str,
    display: str,
    outcome: str,
    rationale: str,
    record_class: URIRef,
) -> dict[str, Any]:
    values = [str(value) for value in path]
    return {
        "outcome": outcome,
        "predicate": values[0],
        "path": values,
        "constraint_target": target,
        "record_class": str(record_class),
        "display": display,
        "status": "migrated-profile",
        "rationale": rationale,
    }


def _unsupported(outcome: str, rationale: str) -> dict[str, Any]:
    return {
        "outcome": outcome,
        "predicate": "",
        "path": [],
        "constraint_target": "",
        "display": "legacy assertion documented; not asserted",
        "status": "unsupported-documented",
        "rationale": rationale,
    }


def _add_profile_constraint(
    graph: Graph,
    shape: URIRef,
    target_class: URIRef,
    property_shape: URIRef,
    path: list[URIRef],
    value_class: URIRef | None,
    name: str,
    description: str,
    source: Graph,
    legacy_target: URIRef | BNode,
    *,
    quantity_guidance: bool = False,
) -> None:
    graph.add((shape, RDF.type, SH.NodeShape))
    graph.add((shape, SH.targetClass, target_class))
    graph.add((shape, RDFS.label, Literal(f"{_fragment(str(target_class))} workflow profile", lang="en")))
    graph.add((shape, SH.property, property_shape))
    graph.add((property_shape, RDF.type, SH.PropertyShape))
    graph.add((property_shape, SH.name, Literal(name, lang="en")))
    graph.add((property_shape, SH.description, Literal(description, lang="en")))
    if len(path) == 1:
        graph.add((property_shape, SH.path, path[0]))
    else:
        path_nodes = [URIRef(f"{property_shape}/path/{index}") for index in range(len(path))]
        path_head = path_nodes[0]
        for index, (path_node, predicate) in enumerate(zip(path_nodes, path)):
            graph.add((path_node, RDF.first, predicate))
            graph.add(
                (
                    path_node,
                    RDF.rest,
                    path_nodes[index + 1] if index + 1 < len(path_nodes) else RDF.nil,
                )
            )
        graph.add((property_shape, SH.path, path_head))
    if value_class:
        graph.add((property_shape, SH["class"], value_class))
    graph.add((property_shape, SH.severity, SH.Info))
    if quantity_guidance:
        for unit in source.objects(legacy_target, QUDT.unit):
            graph.add((property_shape, QUDT.unit, unit))
        for quantity_kind in source.objects(legacy_target, QUDT.quantityKind):
            graph.add((property_shape, QUDT.quantityKind, quantity_kind))


def _class_audit(decisions: list[Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    incoming: dict[str, Counter[str]] = defaultdict(Counter)
    outgoing: dict[str, Counter[str]] = defaultdict(Counter)
    contextual_roles: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        source_iri = row["canonical_source_iri"]
        target_iri = row["canonical_target_iri"]
        predicate = row["legacy_predicate"]
        outgoing[source_iri][predicate] += 1
        incoming[target_iri][predicate] += 1
        if row["display_relation"]:
            contextual_roles[target_iri].add(row["display_relation"])
    result = []
    for decision in decisions:
        if decision.disposition != "active_local_class":
            continue
        result.append(
            {
                "iri": decision.iri,
                "label": decision.label,
                "intrinsic_top_branch": decision.top_branch,
                "intrinsic_role": decision.corrected_semantic_role,
                "source_roles": " | ".join(decision.source_roles),
                "incoming_legacy_predicates": _counter_text(incoming[decision.iri]),
                "outgoing_legacy_predicates": _counter_text(outgoing[decision.iri]),
                "contextual_workflow_roles": " | ".join(sorted(contextual_roles[decision.iri])),
                "migration_decision": "single-intrinsic-placement-with-contextual-profile-roles",
            }
        )
    return result


def _validate_semantic_release(
    taxonomy: Graph,
    profiles: Graph,
    complete: Graph,
    decisions: list[Any],
    rows: list[dict[str, Any]],
    workflow_ttl: Path,
    workflow_jsonld: Path,
    complete_ttl: Path,
    complete_jsonld: Path,
    object_properties: set[URIRef],
) -> dict[str, Any]:
    errors: list[str] = []
    active = {
        URIRef(decision.iri)
        for decision in decisions
        if decision.disposition == "active_local_class"
    }
    characteristic = {
        URIRef(decision.iri)
        for decision in decisions
        if decision.disposition == "active_local_class" and decision.top_branch == "Characteristic"
    }
    conflations = sorted(
        str(iri)
        for iri in characteristic
        if (iri, RDF.type, H2KG.Parameter) in taxonomy or (iri, RDF.type, H2KG.Parameter) in complete
    )
    if conflations:
        errors.append(f"{len(conflations)} Characteristic classes remain typed as Parameter.")

    direct_class_assertions = sorted(
        (str(subject), str(predicate), str(obj))
        for subject, predicate, obj in complete
        if predicate in object_properties and subject in active and obj in active
    )
    if direct_class_assertions:
        errors.append(f"{len(direct_class_assertions)} H2KG object-property assertions still connect OWL classes.")

    unresolved = [row for row in rows if not row.get("migration_outcome") or not row.get("rationale")]
    if unresolved:
        errors.append(f"{len(unresolved)} legacy assertions lack a documented migration outcome.")

    parameter_rows = [row for row in rows if row["legacy_predicate_iri"] == str(H2KG.hasParameter)]
    migrated_parameter_rows = [
        row
        for row in parameter_rows
        if row["migration_outcome"] != "genuine_parameter_record"
        or row["canonical_target_iri"] == str(H2KG.Parameter)
    ]
    direct_parameter_class_targets = [
        row
        for row in parameter_rows
        if row["target_intrinsic_role"] == "Characteristic"
        and row["migration_outcome"]
        not in {"parameter_record_property_path", "normalization_record_property_path"}
    ]
    if direct_parameter_class_targets:
        errors.append(
            f"{len(direct_parameter_class_targets)} characteristic parameter targets were not migrated through Parameter/ofProperty."
        )

    workflow_graph_ttl = Graph().parse(workflow_ttl, format="turtle")
    workflow_graph_jsonld = Graph().parse(workflow_jsonld, format="json-ld")
    complete_graph_ttl = Graph().parse(complete_ttl, format="turtle")
    complete_graph_jsonld = Graph().parse(complete_jsonld, format="json-ld")
    workflow_isomorphic = set(workflow_graph_ttl) == set(workflow_graph_jsonld)
    complete_isomorphic = set(complete_graph_ttl) == set(complete_graph_jsonld)
    if not workflow_isomorphic:
        errors.append("Workflow-profile Turtle and JSON-LD are not RDF-isomorphic.")
    if not complete_isomorphic:
        errors.append("Complete-distribution Turtle and JSON-LD are not RDF-isomorphic.")

    file_uris = sorted(
        {
            str(term)
            for triple in complete
            for term in triple
            if isinstance(term, URIRef) and str(term).startswith("file:")
        }
    )
    if file_uris:
        errors.append(f"Complete distribution contains {len(file_uris)} local file IRIs.")
    registry_file_uris = sorted(
        {
            value
            for row in rows
            for value in row.values()
            if isinstance(value, str) and value.startswith("file:")
        }
    )
    if registry_file_uris:
        errors.append(f"Migration registries contain {len(registry_file_uris)} local file IRIs.")

    outcome_counts = Counter(row["migration_outcome"] for row in rows)
    status_counts = Counter(row["status"] for row in rows)
    return {
        "schema_version": "h2kg-semantic-role-validation/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "conforms": not errors,
        "errors": errors,
        "metrics": {
            "active_class_count": len(active),
            "legacy_assertion_count": len(rows),
            "migrated_legacy_assertion_count": len(rows) - len(unresolved),
            "migration_coverage_percent": round(100 * (len(rows) - len(unresolved)) / max(1, len(rows)), 2),
            "characteristic_parameter_conflation_count": len(conflations),
            "canonical_class_object_assertion_count": len(direct_class_assertions),
            "has_parameter_legacy_count": len(parameter_rows),
            "has_parameter_migrated_count": len(migrated_parameter_rows),
            "unsupported_documented_count": status_counts.get("unsupported-documented", 0),
            "workflow_profile_shape_count": len(set(profiles.subjects(RDF.type, SH.NodeShape))),
            "workflow_property_shape_count": len(set(profiles.subjects(RDF.type, SH.PropertyShape))),
        },
        "outcome_counts": dict(sorted(outcome_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "workflow_serializations_isomorphic": workflow_isomorphic,
        "complete_serializations_isomorphic": complete_isomorphic,
        "file_uris": file_uris,
        "registry_file_uris": registry_file_uris,
    }


def _external_role(source: Graph, resource: URIRef | BNode) -> str:
    roles = {_fragment(str(value)) for value in source.objects(resource, RDF.type)}
    for role in (
        "ReferenceElectrode",
        "Instrument",
        "Measurement",
        "Manufacturing",
        "Process",
        "Data",
        "Matter",
        "Property",
        "Parameter",
        "Metadata",
    ):
        if role in roles:
            return "Characteristic" if role == "Property" else role
    if any(str(value) == str(QUDT.QuantityValue) for value in source.objects(resource, RDF.type)):
        return "QuantityValue"
    return "External"


def _label(source: Graph, resource: URIRef | BNode, decision: Any | None) -> str:
    if decision:
        return str(decision.label)
    for predicate in (SKOS.prefLabel, RDFS.label):
        value = source.value(resource, predicate)
        if value:
            return str(value)
    return _fragment(str(resource))


def _label_for_class(resource: URIRef | str) -> str:
    return _humanize(_fragment(str(resource))).casefold()


def _fragment(iri: str) -> str:
    return iri.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _humanize(value: str) -> str:
    expanded = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value.replace("_", " "))
    return " ".join(part for part in expanded.split() if part).lower()


def _stable_id(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:16]


def _counter_text(counter: Counter[str]) -> str:
    return " | ".join(f"{key}:{value}" for key, value in sorted(counter.items()))


def _bind_namespaces(graph: Graph) -> None:
    graph.bind("h2kg", H2KG)
    graph.bind("profile", PROFILE)
    graph.bind("sh", SH)
    graph.bind("owl", OWL)
    graph.bind("rdfs", RDFS)
    graph.bind("skos", SKOS)
    graph.bind("dcterms", DCTERMS)
    graph.bind("prov", PROV)
    graph.bind("qudt", QUDT)


def _serialize(graph: Graph, path: Path, format_: str) -> None:
    ensure_dir(path.parent)
    if format_ == "json-ld":
        payload = graph.serialize(format="json-ld", context=COMMON_CONTEXT, auto_compact=True, indent=2)
    else:
        payload = graph.serialize(format=format_)
    write_text(path, str(payload))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    ensure_dir(path.parent)
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            serialized = {
                key: " | ".join(str(value) for value in item) if isinstance(item, list) else item
                for key, item in row.items()
            }
            writer.writerow(serialized)
