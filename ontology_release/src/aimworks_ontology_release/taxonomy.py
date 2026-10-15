from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml
from pyshacl import validate as shacl_validate
from rdflib import BNode, Graph, Literal, Namespace, RDF, RDFS, SKOS, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import DCTERMS, OWL, PROV, XSD

from .semantic_profiles import build_semantic_profile_release
from .utils import COMMON_CONTEXT, ensure_dir, legacy_source_identifier, portable_legacy_iri, write_text


H2KG_ONTOLOGY = URIRef("https://w3id.org/h2kg/hydrogen-ontology")
H2KG = Namespace("https://w3id.org/h2kg/hydrogen-ontology#")
QUDT = Namespace("http://qudt.org/schema/qudt/")
SH = Namespace("http://www.w3.org/ns/shacl#")

ROLE_NAMES = {
    "Agent",
    "Matter",
    "Manufacturing",
    "Process",
    "Measurement",
    "Instrument",
    "Parameter",
    "Data",
    "DataPoint",
    "Property",
    "Metadata",
    "NormalizationBasis",
    "ReferenceElectrode",
    "Unit",
}

PROPERTY_TYPES = {OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty}
MAPPING_PREDICATES = {
    OWL.equivalentClass,
    OWL.sameAs,
    SKOS.exactMatch,
    SKOS.closeMatch,
    SKOS.broadMatch,
    SKOS.narrowMatch,
    SKOS.relatedMatch,
    RDFS.seeAlso,
}
ANNOTATION_PREDICATES = {
    RDFS.label,
    RDFS.comment,
    SKOS.prefLabel,
    SKOS.altLabel,
    SKOS.notation,
    SKOS.definition,
    SKOS.scopeNote,
    DCTERMS.description,
    DCTERMS.source,
    DCTERMS.identifier,
    DCTERMS.provenance,
    DCTERMS.created,
    DCTERMS.modified,
    OWL.deprecated,
}


@dataclass(frozen=True)
class TaxonomyDecision:
    iri: str
    local_name: str
    label: str
    alt_labels: tuple[str, ...]
    notations: tuple[str, ...]
    definition: str
    definition_status: str
    source_roles: tuple[str, ...]
    corrected_semantic_role: str
    disposition: str
    parent_iri: str
    parent_label: str
    secondary_parent_iris: tuple[str, ...]
    top_branch: str
    ancestor_path: tuple[str, ...]
    module: str
    technology_applicability: tuple[str, ...]
    replacement_iri: str
    review_status: str
    migration_action: str
    reviewer_decision: str
    rationale: str


def build_taxonomy_release(
    input_path: str | Path,
    output_root: str | Path,
    config_dir: str | Path | None = None,
    *,
    auto_harmonization_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the H2KG class taxonomy, workflow profiles, and compatibility layer.

    The asserted v1 source remains immutable. The clean v2 graph promotes reusable
    vocabulary concepts to OWL classes and keeps legacy role assertions and direct
    class-neighborhood links in a separately published compatibility graph.
    """

    input_path = Path(input_path)
    output_root = ensure_dir(Path(output_root))
    ontology_dir = ensure_dir(output_root / "ontology")
    reports_dir = ensure_dir(output_root / "reports")
    config_root = Path(config_dir or input_path.parent.parent / "config")
    config_path = config_root / "taxonomy.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    controlled_corrections = _load_controlled_corrections(config_root / "tib_h2kg_corrections.json")

    source = Graph().parse(input_path, format="json-ld")
    auto_harmonization = (
        auto_harmonization_override
        if auto_harmonization_override is not None
        else _load_auto_harmonization(config_dir or input_path.parent.parent / "config")
    )
    clean, compatibility, decisions = _build_graphs(
        source,
        config,
        auto_harmonization,
        controlled_corrections,
    )
    resources = _resource_dispositions(source, clean, decisions, config)

    clean.add(
        (
            H2KG_ONTOLOGY,
            RDFS.seeAlso,
            URIRef("https://vimilabs.github.io/AIMWORKS/ontology/h2kg-v2-external-bridge.ttl"),
        )
    )

    clean.add(
        (
            H2KG_ONTOLOGY,
            RDFS.seeAlso,
            URIRef("https://vimilabs.github.io/AIMWORKS/pages/tib-benchmark.html"),
        )
    )

    semantic_profiles = build_semantic_profile_release(
        source,
        clean,
        decisions,
        config,
        ontology_dir,
        reports_dir,
    )

    clean_ttl = ontology_dir / "h2kg-v2-taxonomy.ttl"
    clean_jsonld = ontology_dir / "h2kg-v2-taxonomy.jsonld"
    compatibility_ttl = ontology_dir / "h2kg-v2-compatibility.ttl"
    compatibility_jsonld = ontology_dir / "h2kg-v2-compatibility.jsonld"
    shapes_ttl = ontology_dir / "h2kg-v2-taxonomy-shapes.ttl"
    registry_json = ontology_dir / "taxonomy_registry.json"
    registry_csv = ontology_dir / "taxonomy_registry.csv"
    resource_registry_json = ontology_dir / "resource_disposition_registry.json"
    resource_registry_csv = ontology_dir / "resource_disposition_registry.csv"
    validation_path = reports_dir / "taxonomy_validation.json"
    competency_path = reports_dir / "taxonomy_competency_report.json"
    report_path = reports_dir / "taxonomy_report.md"

    _serialize_graph(clean, clean_ttl, "turtle")
    _serialize_graph(clean, clean_jsonld, "json-ld")
    _serialize_graph(compatibility, compatibility_ttl, "turtle")
    _serialize_graph(compatibility, compatibility_jsonld, "json-ld")
    shapes = _taxonomy_shapes_graph()
    _serialize_graph(shapes, shapes_ttl, "turtle")
    shacl_conforms, _, shacl_text = shacl_validate(
        data_graph=clean,
        shacl_graph=shapes,
        inference="none",
        abort_on_first=False,
        allow_infos=True,
        allow_warnings=True,
    )
    registry_payload = {
        "schema_version": "h2kg-taxonomy-registry/v2",
        "ontology_iri": str(H2KG_ONTOLOGY),
        "version": str(config.get("version", "2.1.0")),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_sha256": _sha256(input_path),
        "taxonomy_config_sha256": _sha256(config_path),
        "review_status": str(config.get("review_status", "domain-expert-reviewed")),
        "top_branches": [str(H2KG[name]) for name in config.get("top_branches", [])],
        "terms": [asdict(decision) for decision in decisions],
    }
    write_text(registry_json, json.dumps(registry_payload, indent=2, ensure_ascii=False))
    _write_registry_csv(registry_csv, decisions)
    write_text(
        resource_registry_json,
        json.dumps(
            {
                "schema_version": "h2kg-resource-disposition-registry/v2",
                "ontology_iri": str(H2KG_ONTOLOGY),
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "resources": resources,
            },
            indent=2,
            ensure_ascii=False,
        ),
    )
    _write_dict_csv(resource_registry_csv, resources)

    bridge = _build_external_bridge(
        output_root,
        config_dir or input_path.parent.parent / "config",
        config,
        auto_harmonization,
    )
    competency = _run_competency_checks(clean, compatibility, decisions)
    write_text(competency_path, json.dumps(competency, indent=2, ensure_ascii=False))

    validation = _validate_taxonomy(
        clean,
        compatibility,
        decisions,
        resources,
        clean_ttl,
        clean_jsonld,
        config,
        bridge,
        competency,
        semantic_profiles,
        bool(shacl_conforms),
        str(shacl_text),
    )
    write_text(validation_path, json.dumps(validation, indent=2, ensure_ascii=False))
    write_text(report_path, _taxonomy_report(validation, decisions))
    if not validation["conforms"]:
        raise ValueError("H2KG taxonomy validation failed: " + "; ".join(validation["errors"][:8]))

    return {
        "ontology_iri": str(H2KG_ONTOLOGY),
        "version": str(config.get("version", "2.1.0")),
        "active_local_classes": validation["counts"]["active_local_classes"],
        "deprecated_compatibility_classes": validation["counts"]["deprecated_compatibility_classes"],
        "new_structural_classes": validation["counts"]["new_structural_classes"],
        "subclass_axioms": validation["counts"]["subclass_axioms"],
        "top_branch_counts": validation["top_branch_counts"],
        "conforms": validation["conforms"],
        "taxonomy_ttl": str(clean_ttl),
        "taxonomy_jsonld": str(clean_jsonld),
        "compatibility_ttl": str(compatibility_ttl),
        "compatibility_jsonld": str(compatibility_jsonld),
        "taxonomy_shapes": str(shapes_ttl),
        "registry": str(registry_json),
        "resource_registry": str(resource_registry_json),
        "external_bridge": bridge,
        "semantic_profiles": semantic_profiles,
        "competency_report": str(competency_path),
        "validation": str(validation_path),
        "publication_ready": validation["publication_ready"],
    }


def _build_graphs(
    source: Graph,
    config: dict[str, Any],
    auto_harmonization: dict[str, Any] | None = None,
    controlled_corrections: dict[str, dict[str, Any]] | None = None,
) -> tuple[Graph, Graph, list[TaxonomyDecision]]:
    clean = Graph()
    compatibility = Graph()
    _bind_namespaces(clean, source)
    _bind_namespaces(compatibility, source)

    structural = config.get("structural_classes", {})
    replacements = {str(key): str(value) for key, value in config.get("duplicate_replacements", {}).items()}
    parent_overrides = {str(key): str(value) for key, value in config.get("parent_overrides", {}).items()}
    intrinsic_definition_overrides = {
        str(key): value
        for key, value in config.get("intrinsic_definition_overrides", {}).items()
    }
    controlled_corrections = controlled_corrections or {}
    candidates = _class_candidates(source, structural)
    property_resources = _property_resources(source)

    _copy_ontology_header(source, clean, config)
    _copy_properties(source, clean)
    _add_support_properties(clean)
    _add_taxonomy_annotation_properties(clean)

    records: dict[str, dict[str, Any]] = {}
    source_roles_by_name: dict[str, tuple[str, ...]] = {}
    for subject in sorted(candidates, key=str):
        local_name = _local_name(subject)
        roles = _source_roles(source, subject)
        source_roles_by_name[local_name] = roles
        label = _best_label(source, subject, local_name)
        records[local_name] = {
            "subject": subject,
            "label": label,
            "alt_labels": _literal_values(source, subject, SKOS.altLabel),
            "notations": _literal_values(source, subject, SKOS.notation),
            "roles": roles,
            "source_definition": _best_definition(source, subject),
            "source_exists": any(True for _ in source.triples((subject, None, None))),
        }

    for local_name, spec in structural.items():
        records.setdefault(
            str(local_name),
            {
                "subject": H2KG[str(local_name)],
                "label": str(spec.get("label", _humanize(local_name))),
                "alt_labels": tuple(),
                "notations": tuple(),
                "roles": tuple(),
                "source_definition": "",
                "source_exists": False,
            },
        )

    label_changes = {
        str(row.get("local_iri", "")): row
        for row in (auto_harmonization or {}).get("label_changes", [])
        if row.get("status") == "machine_safe" and row.get("local_iri") and row.get("new_preferred_label")
    }
    for record in records.values():
        change = label_changes.get(str(record["subject"]))
        if not change:
            continue
        old_label = str(record["label"])
        new_label = str(change["new_preferred_label"]).strip()
        if not new_label or new_label.casefold() == old_label.casefold():
            continue
        record["label"] = new_label
        record["alt_labels"] = tuple(dict.fromkeys([*record.get("alt_labels", ()), old_label]))

    for local_name, correction in controlled_corrections.items():
        record = records.get(local_name)
        if not record:
            raise ValueError(f"Controlled correction targets unknown H2KG class {local_name}.")
        preferred_label = str(correction.get("preferred_label_override", "")).strip()
        if preferred_label:
            record["label"] = preferred_label
            record["alt_labels"] = tuple(
                value
                for value in record.get("alt_labels", ())
                if "�" not in str(value) and str(value).casefold() != preferred_label.casefold()
            )

    parent_by_name: dict[str, str] = {}
    for local_name, record in records.items():
        if local_name in replacements:
            parent_by_name[local_name] = ""
            continue
        if local_name in structural:
            parent_by_name[local_name] = str(structural[local_name].get("parent") or "")
            continue
        parent_by_name[local_name] = _select_parent(
            local_name,
            str(record["label"]),
            tuple(record["roles"]),
            parent_overrides,
            config.get("classification_rules", {}),
        )

    decisions: list[TaxonomyDecision] = []
    for local_name in sorted(records, key=lambda value: records[value]["label"].casefold()):
        record = records[local_name]
        subject = URIRef(record["subject"])
        replacement_name = replacements.get(local_name, "")
        deprecated = bool(replacement_name)
        parent_name = parent_by_name.get(local_name, "")
        label = str(record["label"])
        if local_name in structural:
            label = str(structural[local_name].get("label", label))
        if local_name == "CatalystLayerThickness":
            label = "Catalyst Layer Thickness"
        corrected_role = _corrected_semantic_role(local_name, parent_by_name)
        corrected_from_source_role = _needs_corrected_definition(
            tuple(record["roles"]),
            corrected_role,
            str(record.get("source_definition", "")),
        )
        correction = controlled_corrections.get(local_name, {})
        intrinsic_override = intrinsic_definition_overrides.get(local_name, {})

        if local_name in structural:
            definition = str(structural[local_name].get("definition", "")).strip()
            definition_status = "curated-structural"
        else:
            source_definition = str(record.get("source_definition", "")).strip()
            if source_definition and not _looks_placeholder(source_definition) and not corrected_from_source_role:
                definition = source_definition
                definition_status = "source-curated"
            else:
                definition = _generated_definition(label, parent_name, record["roles"], structural)
                definition_status = "expert-draft-role-corrected" if corrected_from_source_role else "expert-draft"

        if correction:
            required_parent = str(correction.get("required_parent", ""))
            if required_parent and parent_name != required_parent:
                raise ValueError(
                    f"Controlled correction {correction.get('correction_id')} expected {local_name} "
                    f"under {required_parent}, found {parent_name or 'no parent'}."
                )
            replacement_definition = str(
                correction.get("definition_override") or correction.get("final_value", "")
            ).strip()
            if replacement_definition:
                definition = replacement_definition
                definition_status = "curated-controlled-correction"

        intrinsic_definition = str(intrinsic_override.get("definition", "")).strip()
        if intrinsic_definition:
            definition = intrinsic_definition
            definition_status = "curated-intrinsic-definition"

        if deprecated:
            replacement = H2KG[replacement_name]
            clean.add((subject, RDF.type, OWL.Class))
            clean.add((subject, RDFS.label, Literal(label, lang="en")))
            clean.add((subject, SKOS.prefLabel, Literal(label, lang="en")))
            clean.add((subject, SKOS.definition, Literal(definition, lang="en")))
            clean.add((subject, OWL.deprecated, Literal(True, datatype=XSD.boolean)))
            clean.add((subject, DCTERMS.isReplacedBy, replacement))
            disposition = "deprecated_compatibility_class"
            parent_iri = ""
            parent_label = ""
            top_branch = "Compatibility"
            ancestor_path: tuple[str, ...] = tuple()
            rationale = f"Deprecated duplicate retained for IRI compatibility; use {replacement_name}."
        else:
            clean.add((subject, RDF.type, OWL.Class))
            clean.set((subject, RDFS.label, Literal(label, lang="en")))
            clean.set((subject, SKOS.prefLabel, Literal(label, lang="en")))
            clean.set((subject, SKOS.definition, Literal(definition, lang="en")))
            _copy_term_annotations(source, subject, clean)
            if (
                correction.get("definition_override")
                or correction.get("final_value")
                or intrinsic_definition
            ):
                clean.set((subject, DCTERMS.description, Literal(definition, lang="en")))
            scope_note = str(
                intrinsic_override.get("scope_note") or correction.get("scope_note", "")
            ).strip()
            if scope_note:
                clean.set((subject, SKOS.scopeNote, Literal(scope_note, lang="en")))
            for alt_label in record.get("alt_labels", ()):
                if str(alt_label).casefold() != label.casefold():
                    clean.add((subject, SKOS.altLabel, Literal(str(alt_label), lang="en")))
            if parent_name:
                clean.add((subject, RDFS.subClassOf, H2KG[parent_name]))
            _add_upper_alignment(clean, local_name)
            disposition = "active_local_class"
            parent_iri = str(H2KG[parent_name]) if parent_name else ""
            parent_label = str(structural.get(parent_name, {}).get("label", _humanize(parent_name))) if parent_name else ""
            ancestor_names = _ancestor_names(local_name, parent_by_name, replacements)
            top_branch = ancestor_names[-1] if ancestor_names else local_name
            ancestor_path = tuple(str(H2KG[name]) for name in reversed(ancestor_names))
            rationale = _decision_rationale(record["roles"], parent_name, local_name in parent_overrides, local_name in structural)

        module, technologies = _module_for(label, local_name, config.get("module_rules", {}))
        migration_action = _migration_action(record, deprecated, local_name in structural)
        review_status = str(config.get("review_status", "domain-expert-reviewed"))
        reviewer_decision = str(config.get("reviewer_decision", "approved-domain-expert-review"))
        _add_taxonomy_annotations(
            clean,
            subject,
            module=module,
            technologies=technologies,
            top_branch=top_branch,
            corrected_role=corrected_role,
            definition_status=definition_status,
            review_status=review_status,
            migration_action=migration_action,
            reviewer_decision=reviewer_decision,
            source_exists=bool(record.get("source_exists")),
        )
        decisions.append(
            TaxonomyDecision(
                iri=str(subject),
                local_name=local_name,
                label=label,
                alt_labels=tuple(record.get("alt_labels", ())),
                notations=tuple(record.get("notations", ())),
                definition=definition,
                definition_status=definition_status,
                source_roles=tuple(record["roles"]),
                corrected_semantic_role=corrected_role,
                disposition=disposition,
                parent_iri=parent_iri,
                parent_label=parent_label,
                secondary_parent_iris=tuple(),
                top_branch=top_branch,
                ancestor_path=ancestor_path,
                module=module,
                technology_applicability=technologies,
                replacement_iri=str(H2KG[replacement_name]) if replacement_name else "",
                review_status=review_status,
                migration_action=migration_action,
                reviewer_decision=reviewer_decision,
                rationale=rationale,
            )
        )

    _build_compatibility_graph(source, compatibility, clean, config)
    return clean, compatibility, decisions


def _class_candidates(source: Graph, structural: dict[str, Any]) -> set[URIRef]:
    result: set[URIRef] = set()
    properties = _property_resources(source)
    role_iris = {H2KG[name] for name in ROLE_NAMES}
    for subject in source.subjects(RDF.type, OWL.Class):
        if isinstance(subject, URIRef) and str(subject).startswith(str(H2KG)):
            result.add(subject)
    for role in role_iris:
        for subject in source.subjects(RDF.type, role):
            if not isinstance(subject, URIRef) or not str(subject).startswith(str(H2KG)):
                continue
            if subject in properties or _is_quantity_value(source, subject):
                continue
            local_name = _local_name(subject)
            if local_name.startswith("_") or local_name.startswith("ITCQuantityGuidance_") or local_name.endswith("_QV"):
                continue
            # DataPoint resources in the asserted source are profile fields or
            # result records. They remain information-layer constructs rather
            # than being promoted to reusable scientific classes.
            if role == H2KG.DataPoint:
                continue
            result.add(subject)
    result.update(H2KG[str(name)] for name in structural)
    return result


def _property_resources(source: Graph) -> set[URIRef]:
    result: set[URIRef] = set()
    for property_type in PROPERTY_TYPES:
        result.update(subject for subject in source.subjects(RDF.type, property_type) if isinstance(subject, URIRef))
    return result


def _is_quantity_value(source: Graph, subject: URIRef) -> bool:
    return (subject, RDF.type, QUDT.QuantityValue) in source or _local_name(subject).endswith("_QV")


def _source_roles(source: Graph, subject: URIRef) -> tuple[str, ...]:
    values = {
        _local_name(role)
        for role in source.objects(subject, RDF.type)
        if isinstance(role, URIRef) and str(role).startswith(str(H2KG)) and _local_name(role) in ROLE_NAMES
    }
    return tuple(sorted(values))


def _select_parent(
    local_name: str,
    label: str,
    roles: tuple[str, ...],
    overrides: dict[str, str],
    rules: dict[str, Any],
) -> str:
    if local_name in overrides:
        return overrides[local_name]
    role_set = set(roles)
    text = f"{_humanize(local_name)} {label}".casefold()

    # Correct known ontological-kind errors from the role-typed v1 source.
    # These decisions use the scientific identity expressed by the term, not
    # the workflow slot in which the source happened to place it.
    if "Measurement" in role_set:
        if any(marker in text for marker in (" simulation", "simulation ", "model execution")):
            return "ModelExecution"
        if "specification" in text or "recipe definition" in text:
            return "WorkflowProfile"
        if any(
            marker in text
            for marker in (
                " compilation",
                "property lookup",
                "literature review",
                " calculation",
                "reported material property",
                " statement extraction",
            )
        ) or text.rstrip().endswith((" analysis", " estimation", " assessment", " extraction")):
            return "Analysis"
    if "Data" in role_set and (text.strip().endswith("model") or "neural network model" in text):
        return "MachineLearningModel"

    if role_set & {"Parameter", "Property"}:
        family = "Characteristic"
    elif "DataPoint" in role_set:
        return "DataPoint"
    elif "Data" in role_set:
        family = "Data"
    elif "Measurement" in role_set:
        family = "Measurement"
    elif "Manufacturing" in role_set:
        family = "Manufacturing"
    elif "Process" in role_set:
        family = "Process"
    elif "Instrument" in role_set:
        family = "Instrument"
    elif "Matter" in role_set:
        family = "Matter"
    elif "Metadata" in role_set:
        return "Metadata"
    elif "NormalizationBasis" in role_set:
        return "NormalizationBasis"
    elif "ReferenceElectrode" in role_set:
        return "ReferenceElectrode"
    elif "Unit" in role_set:
        return "Unit"
    elif "Agent" in role_set:
        return "Agent"
    else:
        family = "InformationEntity"

    family_rules = rules.get(family, [])
    for rule in family_rules:
        keywords = [str(value).casefold() for value in rule.get("keywords", [])]
        if not keywords or any(_keyword_matches(text, keyword) for keyword in keywords):
            return str(rule["parent"])
    defaults = {
        "Matter": "MaterialEntity",
        "Manufacturing": "MaterialProcessing",
        "Process": "Process",
        "Measurement": "CharacterizationMeasurement",
        "Instrument": "Instrument",
        "Data": "Dataset",
        "Characteristic": "QuantitativeCharacteristic",
        "InformationEntity": "InformationEntity",
    }
    return defaults[family]


def _keyword_matches(text: str, keyword: str) -> bool:
    """Match taxonomy rules on normalized tokens, with explicit prefix stems.

    Plain rule values match complete tokens or phrases. A trailing ``*`` marks
    an intentional word-prefix rule. This prevents accidental classifications
    such as ``wavelength`` matching ``length`` or ``model`` matching ``mode``.
    """

    normalized_text = re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()
    raw_keyword = keyword.casefold().strip()
    prefix_match = raw_keyword.endswith("*")
    normalized_keyword = re.sub(r"[^a-z0-9]+", " ", raw_keyword.rstrip("*")).strip()
    if not normalized_keyword:
        return False
    if prefix_match:
        tokens = normalized_text.split()
        keyword_tokens = normalized_keyword.split()
        if len(keyword_tokens) == 1:
            return any(token.startswith(keyword_tokens[0]) for token in tokens)
        prefix = " ".join(keyword_tokens[:-1])
        final_stem = keyword_tokens[-1]
        return any(
            " ".join(tokens[index : index + len(keyword_tokens) - 1]) == prefix
            and tokens[index + len(keyword_tokens) - 1].startswith(final_stem)
            for index in range(len(tokens) - len(keyword_tokens) + 1)
        )
    return f" {normalized_keyword} " in f" {normalized_text} "


def _copy_ontology_header(source: Graph, target: Graph, config: dict[str, Any]) -> None:
    allowed_imports = {str(value).rstrip("#") for value in config.get("allowed_foundational_imports", [])}
    for predicate, obj in source.predicate_objects(H2KG_ONTOLOGY):
        if predicate in {OWL.versionIRI, OWL.versionInfo, DCTERMS.hasVersion, DCTERMS.isVersionOf}:
            continue
        if predicate == OWL.imports:
            # Domain ontologies are aligned selectively in the external bridge.
            # The clean taxonomy imports only explicitly allowlisted foundations.
            continue
        target.add((H2KG_ONTOLOGY, predicate, obj))
    for import_iri in sorted(allowed_imports):
        target.add((H2KG_ONTOLOGY, OWL.imports, URIRef(import_iri)))
    target.add((H2KG_ONTOLOGY, RDF.type, OWL.Ontology))
    target.set((H2KG_ONTOLOGY, OWL.versionInfo, Literal(str(config.get("version", "2.1.0")))))
    target.set((H2KG_ONTOLOGY, OWL.versionIRI, URIRef(str(config.get("version_iri")))))
    target.set((H2KG_ONTOLOGY, DCTERMS.title, Literal("H2KG Application Ontology for Hydrogen Electrochemical Systems", lang="en")))
    target.set(
        (
            H2KG_ONTOLOGY,
            DCTERMS.description,
            Literal(
                "A modular ontology for materials, components, processes, measurements, information entities, characteristics, and provenance in hydrogen electrochemical research.",
                lang="en",
            ),
        )
    )


def _copy_properties(source: Graph, target: Graph) -> None:
    properties = _property_resources(source)
    bad_inverse_subjects = {H2KG.hasOutputData, H2KG.hasOutputMaterial}
    for subject in properties:
        for predicate, obj in source.predicate_objects(subject):
            if predicate == OWL.inverseOf and subject in bad_inverse_subjects and obj == PROV.wasGeneratedBy:
                continue
            if subject == H2KG.referenceElectrode and predicate in {RDFS.domain, RDFS.range}:
                # The v1 property conflated a physical reference electrode with
                # an electrochemical reference scale. Keep it resolvable, but do
                # not carry its incompatible range into the clean taxonomy.
                continue
            if subject == H2KG.ofProperty and predicate == RDFS.domain:
                # Parameter records and DataPoint records both identify a
                # property occurrence.  InformationEntity is their shared
                # canonical domain.
                continue
            target.add((subject, predicate, obj))
    target.add((H2KG.hasOutputData, RDFS.subPropertyOf, PROV.generated))
    target.add((H2KG.hasOutputMaterial, RDFS.subPropertyOf, PROV.generated))
    for relation in (H2KG.hasInputData, H2KG.hasInputMaterial, H2KG.usesInstrument, H2KG.hasParameter):
        target.add((relation, RDFS.subPropertyOf, PROV.used))
    target.add((H2KG.referenceElectrode, OWL.deprecated, Literal(True, datatype=XSD.boolean)))
    target.add((H2KG.referenceElectrode, DCTERMS.isReplacedBy, H2KG.usesReferenceElectrode))
    target.add((H2KG.referenceElectrode, DCTERMS.isReplacedBy, H2KG.hasReferenceScale))
    target.add((H2KG.hasProperty, OWL.deprecated, Literal(True, datatype=XSD.boolean)))
    target.add((H2KG.hasProperty, DCTERMS.isReplacedBy, H2KG.measures))
    target.set((H2KG.ofProperty, RDFS.domain, H2KG.InformationEntity))
    target.set((H2KG.ofProperty, RDFS.range, H2KG.Property))
    target.set((H2KG.hasQuantityValue, RDFS.domain, H2KG.Property))
    target.set((H2KG.hasQuantityValue, RDFS.range, QUDT.QuantityValue))
    canonical_property_definitions = {
        H2KG.ofProperty: (
            "Relates an information record, such as a Parameter or DataPoint, to the property occurrence that the record specifies or reports."
        ),
        H2KG.hasParameter: (
            "Relates a process or measurement occurrence to a Parameter record that specifies one selected workflow condition."
        ),
        H2KG.hasQuantityValue: (
            "Relates a property occurrence to its QUDT quantity-value representation."
        ),
    }
    for predicate, definition in canonical_property_definitions.items():
        value = Literal(definition, lang="en")
        target.set((predicate, SKOS.definition, value))
        target.set((predicate, DCTERMS.description, value))


def _add_support_properties(target: Graph) -> None:
    definitions = {
        "usesSoftware": (
            "uses software",
            "Relates a process to a software artifact used to execute, control, process, analyze, simulate, or visualize its data.",
            H2KG.Process,
            H2KG.SoftwareArtifact,
        ),
        "usesReferenceElectrode": (
            "uses reference electrode",
            "Relates an electrochemical measurement to the reference electrode used in its measurement arrangement.",
            H2KG.Measurement,
            H2KG.ReferenceElectrode,
        ),
        "hasReferenceScale": (
            "has reference scale",
            "Relates an information entity or result record to the reference scale against which a potential or related quantity is expressed.",
            H2KG.InformationEntity,
            H2KG.ReferenceScale,
        ),
        "hasMeasurementSubject": (
            "has measurement subject",
            "Relates a measurement to the material, specimen, component, or system whose characteristics are investigated.",
            H2KG.Measurement,
            H2KG.Matter,
        ),
    }
    for local_name, (label, definition, domain, range_) in definitions.items():
        subject = H2KG[local_name]
        target.add((subject, RDF.type, OWL.ObjectProperty))
        target.add((subject, RDFS.label, Literal(label, lang="en")))
        target.add((subject, SKOS.definition, Literal(definition, lang="en")))
        target.add((subject, RDFS.domain, domain))
        target.add((subject, RDFS.range, range_))
    target.add((H2KG.usesSoftware, RDFS.subPropertyOf, PROV.used))
    target.add((H2KG.usesReferenceElectrode, RDFS.subPropertyOf, PROV.used))


def _add_taxonomy_annotation_properties(target: Graph) -> None:
    definitions = {
        "taxonomyModule": ("taxonomy module", "Identifies the H2KG module in which a reusable class is maintained."),
        "technologyApplicability": (
            "technology applicability",
            "Identifies a hydrogen or electrochemical technology profile in which a reusable class is explicitly applicable.",
        ),
        "taxonomyTopBranch": ("taxonomy top branch", "Identifies the top-level H2KG branch reached by a class."),
        "canonicalSemanticRole": (
            "canonical semantic role",
            "Records the canonical H2KG semantic role assigned after separating scientific identity from a contextual workflow role.",
        ),
        "definitionStatus": ("definition status", "Records whether a definition is curated, generated as an expert draft, or retained for compatibility."),
        "reviewStatus": ("review status", "Records the governance review state of an H2KG resource."),
        "migrationAction": ("migration action", "Records how a resource is handled during migration to the H2KG v2 taxonomy."),
        "reviewerDecision": ("reviewer decision", "Records the current domain-review decision for a taxonomy placement."),
    }
    for local_name, (label, definition) in definitions.items():
        subject = H2KG[local_name]
        target.add((subject, RDF.type, OWL.AnnotationProperty))
        target.add((subject, RDFS.label, Literal(label, lang="en")))
        target.add((subject, SKOS.definition, Literal(definition, lang="en")))


def _add_taxonomy_annotations(
    target: Graph,
    subject: URIRef,
    *,
    module: str,
    technologies: tuple[str, ...],
    top_branch: str,
    corrected_role: str,
    definition_status: str,
    review_status: str,
    migration_action: str,
    reviewer_decision: str,
    source_exists: bool,
) -> None:
    target.set((subject, H2KG.taxonomyModule, Literal(module)))
    target.set((subject, H2KG.taxonomyTopBranch, Literal(top_branch)))
    target.set((subject, H2KG.canonicalSemanticRole, Literal(corrected_role)))
    target.set((subject, H2KG.definitionStatus, Literal(definition_status)))
    target.set((subject, H2KG.reviewStatus, Literal(review_status)))
    target.set((subject, H2KG.migrationAction, Literal(migration_action)))
    target.set((subject, H2KG.reviewerDecision, Literal(reviewer_decision)))
    for technology in technologies:
        target.add((subject, H2KG.technologyApplicability, Literal(technology)))
    provenance = (
        "Migrated from the asserted H2KG v1 source through the versioned taxonomy registry."
        if source_exists
        else "Added as curated H2KG v2 taxonomy scaffolding through the versioned taxonomy registry."
    )
    target.add((subject, DCTERMS.provenance, Literal(provenance, lang="en")))


def _copy_term_annotations(source: Graph, subject: URIRef, target: Graph) -> None:
    for predicate, obj in source.predicate_objects(subject):
        if predicate in ANNOTATION_PREDICATES or predicate in MAPPING_PREDICATES:
            if predicate in {RDFS.label, SKOS.prefLabel, SKOS.definition}:
                continue
            target.add((subject, predicate, obj))


def _add_upper_alignment(target: Graph, local_name: str) -> None:
    subject = H2KG[local_name]
    if local_name == "Process":
        target.add((subject, RDFS.subClassOf, PROV.Activity))
    elif local_name in {"Matter", "InformationEntity", "Characteristic"}:
        target.add((subject, RDFS.subClassOf, PROV.Entity))
    elif local_name == "Agent":
        target.add((subject, RDFS.subClassOf, PROV.Agent))


def _build_compatibility_graph(source: Graph, target: Graph, taxonomy: Graph, config: dict[str, Any]) -> None:
    compatibility_iri = URIRef("https://w3id.org/h2kg/hydrogen-ontology/compatibility")
    for subject, predicate, obj in source:
        if subject == H2KG_ONTOLOGY:
            continue
        if predicate == OWL.inverseOf and subject in {H2KG.hasOutputData, H2KG.hasOutputMaterial} and obj == PROV.wasGeneratedBy:
            continue
        portable_subject = _portable_legacy_term(subject)
        portable_predicate = _portable_legacy_term(predicate)
        portable_object = _portable_legacy_term(obj)
        target.add((portable_subject, portable_predicate, portable_object))
        for original, portable in ((subject, portable_subject), (obj, portable_object)):
            if isinstance(original, URIRef) and str(original).startswith("file:"):
                target.add((portable, DCTERMS.identifier, Literal(legacy_source_identifier(str(original)))))

    # Preserve every source workflow assertion and add an explicit corrected
    # projection where a legacy relation encoded a contextual role too broadly.
    for activity, used_resource in source.subject_objects(H2KG.usesInstrument):
        if not isinstance(used_resource, URIRef):
            continue
        if _is_descendant(taxonomy, used_resource, H2KG.SoftwareArtifact):
            target.add((activity, H2KG.usesSoftware, used_resource))
        elif _is_descendant(taxonomy, used_resource, H2KG.ReferenceElectrode):
            target.add((activity, H2KG.usesReferenceElectrode, used_resource))
    for activity, subject in source.subject_objects(H2KG.hasInputMaterial):
        if (activity, RDF.type, H2KG.Measurement) in source:
            target.add((activity, H2KG.hasMeasurementSubject, subject))
    for activity, characteristic in source.subject_objects(H2KG.hasProperty):
        target.add((activity, H2KG.measures, characteristic))

    target.add((compatibility_iri, RDF.type, OWL.Ontology))
    target.add((compatibility_iri, OWL.imports, URIRef(str(config.get("version_iri", H2KG_ONTOLOGY)))))
    target.add((compatibility_iri, OWL.versionInfo, Literal(str(config.get("version", "2.1.0")))))
    target.add((compatibility_iri, DCTERMS.title, Literal("H2KG 2.1 Legacy Compatibility Layer", lang="en")))
    target.add(
        (
            compatibility_iri,
            DCTERMS.description,
            Literal(
                "A download-only migration artifact preserving legacy H2KG role assertions and direct workflow-neighborhood relations. It is not part of the canonical ontology distribution and does not drive Explore.",
                lang="en",
            ),
        )
    )


def _portable_legacy_term(term: Any) -> Any:
    if isinstance(term, URIRef):
        return URIRef(portable_legacy_iri(str(term)))
    return term


def _bind_namespaces(target: Graph, source: Graph) -> None:
    for prefix, namespace in source.namespaces():
        target.bind(prefix, namespace)
    target.bind("h2kg", H2KG)
    target.bind("owl", OWL)
    target.bind("rdfs", RDFS)
    target.bind("skos", SKOS)
    target.bind("dcterms", DCTERMS)
    target.bind("prov", PROV)
    target.bind("qudt", QUDT)
    target.bind("sh", SH)


def _taxonomy_shapes_graph() -> Graph:
    graph = Graph()
    _bind_namespaces(graph, Graph())
    shape = H2KG.TaxonomyClassShape
    graph.add((shape, RDF.type, SH.NodeShape))
    graph.add((shape, SH.targetClass, OWL.Class))

    label_shape = BNode()
    graph.add((shape, SH.property, label_shape))
    graph.add((label_shape, SH.path, SKOS.prefLabel))
    graph.add((label_shape, SH.minCount, Literal(1)))
    graph.add((label_shape, SH.maxCount, Literal(1)))
    graph.add((label_shape, SH.message, Literal("Every H2KG class must have exactly one preferred label.")))

    definition_shape = BNode()
    graph.add((shape, SH.property, definition_shape))
    graph.add((definition_shape, SH.path, SKOS.definition))
    graph.add((definition_shape, SH.minCount, Literal(1)))
    graph.add((definition_shape, SH.maxCount, Literal(1)))
    graph.add((definition_shape, SH.message, Literal("Every H2KG class must have a definition.")))

    required_annotations = {
        H2KG.taxonomyModule: "Every H2KG class must have exactly one taxonomy module.",
        H2KG.taxonomyTopBranch: "Every H2KG class must identify exactly one top-level taxonomy branch.",
        H2KG.canonicalSemanticRole: "Every H2KG class must have exactly one canonical semantic role.",
        H2KG.definitionStatus: "Every H2KG class must have exactly one definition status.",
        H2KG.reviewStatus: "Every H2KG class must have exactly one review status.",
        H2KG.migrationAction: "Every H2KG class must have exactly one migration action.",
        H2KG.reviewerDecision: "Every H2KG class must have exactly one reviewer decision.",
        DCTERMS.provenance: "Every H2KG class must record migration provenance.",
    }
    for path, message in required_annotations.items():
        property_shape = BNode()
        graph.add((shape, SH.property, property_shape))
        graph.add((property_shape, SH.path, path))
        graph.add((property_shape, SH.minCount, Literal(1)))
        graph.add((property_shape, SH.maxCount, Literal(1)))
        graph.add((property_shape, SH.message, Literal(message)))
    return graph


def _best_label(graph: Graph, subject: URIRef, fallback: str) -> str:
    for predicate in (SKOS.prefLabel, RDFS.label):
        values = sorted((str(value) for value in graph.objects(subject, predicate)), key=len)
        if values:
            return values[0].strip()
    return _humanize(fallback)


def _best_definition(graph: Graph, subject: URIRef) -> str:
    for predicate in (SKOS.definition, DCTERMS.description, RDFS.comment):
        values = [str(value).strip() for value in graph.objects(subject, predicate) if str(value).strip()]
        if values:
            return max(values, key=len)
    return ""


def _literal_values(graph: Graph, subject: URIRef, predicate: URIRef) -> tuple[str, ...]:
    values = {str(value).strip() for value in graph.objects(subject, predicate) if str(value).strip()}
    return tuple(sorted(values, key=str.casefold))


def _looks_placeholder(value: str) -> bool:
    text = value.casefold()
    markers = (
        "proposed_new_term",
        "not present",
        "definition pending",
        "placeholder",
        "todo",
        "tbd",
        "requires review",
    )
    return len(value.strip()) < 24 or any(marker in text for marker in markers)


def _generated_definition(
    label: str,
    parent_name: str,
    roles: Iterable[str],
    structural: dict[str, Any],
) -> str:
    parent_label = str(structural.get(parent_name, {}).get("label", _humanize(parent_name))).casefold()
    article = "an" if parent_label[:1] in {"a", "e", "i", "o", "u"} else "a"
    role_set = set(roles)
    if parent_name in {"ModelExecution", "Simulation"}:
        return f"{article.capitalize()} {parent_label} that executes or evaluates {label.casefold()} to generate predicted or fitted scientific data."
    if parent_name in {"Analysis", "DataProcessing"}:
        return f"An {parent_label} that evaluates or transforms scientific information through {label.casefold()}."
    if parent_name in {"WorkflowProfile", "Specification", "ParameterRecord"}:
        return f"{article.capitalize()} {parent_label} that specifies the expected scientific content or conditions identified as {label}."
    if parent_name in {"ModelArtifact", "MachineLearningModel"}:
        return f"{article.capitalize()} {parent_label} that represents the computational model identified as {label}."
    if parent_name in {"SoftwareArtifact", "ScientificSoftware", "ImageAnalysisSoftware"}:
        return f"{article.capitalize()} {parent_label} used in scientific workflows under the name {label}."
    if parent_name == "NormalizationBasis":
        return f"A normalization basis identifying {label.casefold()} as the reference quantity for a normalized value."
    if role_set & {"Parameter", "Property"}:
        return f"{article.capitalize()} {parent_label} that represents {label.casefold()} for a material, component, process, measurement, or hydrogen-electrochemical system."
    if "Measurement" in role_set:
        return f"{article.capitalize()} {parent_label} that applies {label.casefold()} to acquire scientific data about a material, component, or system."
    if "Manufacturing" in role_set:
        return f"{article.capitalize()} {parent_label} used to prepare, modify, or assemble matter through {label.casefold()}."
    if "Process" in role_set:
        return f"{article.capitalize()} {parent_label} that performs {label.casefold()} within a scientific workflow."
    if "Instrument" in role_set:
        return f"{article.capitalize()} {parent_label} used to perform or support {label.casefold()} in a scientific workflow."
    if "Data" in role_set or "DataPoint" in role_set:
        return f"{article.capitalize()} {parent_label} that records or organizes information identified as {label}."
    if "Matter" in role_set:
        return f"{article.capitalize()} {parent_label} identified as {label} and used or produced in a hydrogen-electrochemical workflow."
    return f"{article.capitalize()} {parent_label or 'scientific concept'} representing {label} in the H2KG domain model."


def _ancestor_names(local_name: str, parents: dict[str, str], replacements: dict[str, str]) -> list[str]:
    result: list[str] = []
    seen = {local_name}
    current = parents.get(local_name, "")
    while current:
        if current in seen:
            raise ValueError(f"Taxonomy cycle detected while resolving {local_name}: {current}")
        seen.add(current)
        result.append(current)
        current = parents.get(current, "")
    return result


def _module_for(label: str, local_name: str, rules: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
    text = f"{label} {_humanize(local_name)}".casefold()
    matched: list[str] = []
    for module, keywords in rules.items():
        if any(str(keyword).casefold() in text for keyword in keywords):
            matched.append(str(module))
    if "electrochemistry-extension" in matched:
        return "electrochemistry-extension", tuple(sorted(matched))
    if len(matched) == 1:
        return matched[0], tuple(matched)
    if len(matched) > 1:
        return "shared-hydrogen", tuple(sorted(matched))
    return "core", tuple()


def _corrected_semantic_role(local_name: str, parents: dict[str, str]) -> str:
    role_priority = (
        "ReferenceElectrode",
        "Instrument",
        "Measurement",
        "Manufacturing",
        "ModelExecution",
        "Simulation",
        "Analysis",
        "Process",
        "ImageAnalysisSoftware",
        "ScientificSoftware",
        "SoftwareArtifact",
        "MachineLearningModel",
        "ModelArtifact",
        "ParameterRecord",
        "WorkflowProfile",
        "NormalizationBasis",
        "ReferenceScale",
        "Specification",
        "DataPoint",
        "Metadata",
        "Data",
        "Characteristic",
        "Unit",
        "Matter",
        "Agent",
    )
    current = local_name
    seen: set[str] = set()
    path: set[str] = set()
    while current and current not in seen:
        seen.add(current)
        path.add(current)
        current = parents.get(current, "")
    for role in role_priority:
        if role in path:
            if role in {"ReferenceElectrode"}:
                return "Instrument"
            if role in {"ModelExecution", "Simulation", "Analysis"}:
                return "Process"
            if role in {"ImageAnalysisSoftware", "ScientificSoftware"}:
                return "SoftwareArtifact"
            if role == "MachineLearningModel":
                return "ModelArtifact"
            if role == "ReferenceScale":
                return "Specification"
            return role
    return "Class"


def _needs_corrected_definition(
    source_roles: tuple[str, ...],
    corrected_role: str,
    source_definition: str = "",
) -> bool:
    if not source_roles:
        return False
    expected_roles = {
        "Matter": {"Matter"},
        "Manufacturing": {"Manufacturing"},
        "Process": {"Process"},
        "Measurement": {"Measurement"},
        "Instrument": {"Instrument", "ReferenceElectrode"},
        "ParameterRecord": {"Parameter"},
        "Data": {"Data"},
        "DataPoint": {"DataPoint"},
        "Metadata": {"Metadata"},
        "SoftwareArtifact": set(),
        "ModelArtifact": set(),
        "WorkflowProfile": set(),
        "Specification": set(),
        "Characteristic": {"Property"},
        "NormalizationBasis": {"NormalizationBasis"},
        "Unit": {"Unit"},
        "Agent": {"Agent"},
    }
    if corrected_role == "Characteristic" and "Parameter" in source_roles:
        definition = source_definition.casefold()
        role_markers = (
            "parameter specifying",
            "input parameter",
            "workflow parameter",
            "measurement setting",
            "model setting",
            "acquisition setting",
            "used as a parameter",
        )
        if not definition or any(marker in definition for marker in role_markers):
            return True
        # A source definition that already defines the scientific quantity can
        # be retained even though the v1 source happened to type it Parameter.
        return False
    return not bool(set(source_roles) & expected_roles.get(corrected_role, set()))


def _migration_action(record: dict[str, Any], deprecated: bool, structural: bool) -> str:
    if deprecated:
        return "deprecate-and-link-to-canonical-iri"
    if structural and not record.get("source_exists"):
        return "add-taxonomy-scaffold-class"
    if record.get("roles"):
        return "promote-role-typed-vocabulary-to-owl-class"
    return "preserve-existing-class"


def _decision_rationale(roles: Iterable[str], parent: str, override: bool, structural: bool) -> str:
    if structural:
        return "Curated structural class required to provide a complete navigable H2KG hierarchy."
    if override:
        return f"Curated parent override assigns the concept to {parent}."
    role_text = ", ".join(roles) or "untyped local vocabulary"
    return f"Role-aware taxonomy rule maps source role(s) {role_text} to {parent}."


def _serialize_graph(graph: Graph, path: Path, format_: str) -> None:
    ensure_dir(path.parent)
    if format_ == "json-ld":
        payload = graph.serialize(format="json-ld", context=COMMON_CONTEXT, auto_compact=True, indent=2)
    else:
        payload = graph.serialize(format=format_)
    write_text(path, str(payload))


def _write_registry_csv(path: Path, decisions: list[TaxonomyDecision]) -> None:
    ensure_dir(path.parent)
    fieldnames = list(asdict(decisions[0]).keys()) if decisions else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for decision in decisions:
            row = asdict(decision)
            for key in (
                "alt_labels",
                "notations",
                "source_roles",
                "secondary_parent_iris",
                "ancestor_path",
                "technology_applicability",
            ):
                row[key] = " | ".join(row[key])
            writer.writerow(row)


def _write_dict_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    ensure_dir(path.parent)
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for source_row in rows:
            row = dict(source_row)
            for key, value in row.items():
                if isinstance(value, (list, tuple, set)):
                    row[key] = " | ".join(str(item) for item in value)
            writer.writerow(row)


def _resource_dispositions(
    source: Graph,
    clean: Graph,
    decisions: list[TaxonomyDecision],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Assign one explicit release disposition to every local RDF resource."""

    decision_by_iri = {decision.iri: decision for decision in decisions}
    local_iris = {
        value
        for triple in source
        for value in triple
        if isinstance(value, URIRef)
        and (str(value) == str(H2KG_ONTOLOGY) or str(value).startswith(str(H2KG)))
    }
    local_iris.update(
        value
        for triple in clean
        for value in triple
        if isinstance(value, URIRef)
        and (str(value) == str(H2KG_ONTOLOGY) or str(value).startswith(str(H2KG)))
    )
    source_subjects = {subject for subject in source.subjects() if isinstance(subject, URIRef)}
    source_properties = _property_resources(source)
    clean_properties = _property_resources(clean)
    rows: list[dict[str, Any]] = []

    for subject in sorted(local_iris, key=str):
        iri = str(subject)
        local_name = _local_name(subject)
        decision = decision_by_iri.get(iri)
        source_types = sorted(
            str(value)
            for value in source.objects(subject, RDF.type)
            if isinstance(value, URIRef)
        )
        source_exists = subject in source_subjects or any(subject in triple for triple in source)
        if decision is not None:
            disposition = decision.disposition
            corrected_kind = "owl:Class"
            rationale = decision.rationale
            label = decision.label
            review_status = decision.review_status
        elif subject == H2KG_ONTOLOGY:
            disposition = "ontology_header"
            corrected_kind = "owl:Ontology"
            rationale = "The stable H2KG ontology identifier and release metadata resource."
            label = _best_label(source, subject, "H2KG")
            review_status = "schema-reviewed"
        elif subject in source_properties or subject in clean_properties:
            if (subject, RDF.type, OWL.ObjectProperty) in source or (subject, RDF.type, OWL.ObjectProperty) in clean:
                disposition = "object_property"
                corrected_kind = "owl:ObjectProperty"
            elif (subject, RDF.type, OWL.DatatypeProperty) in source or (subject, RDF.type, OWL.DatatypeProperty) in clean:
                disposition = "datatype_property"
                corrected_kind = "owl:DatatypeProperty"
            else:
                disposition = "annotation_property"
                corrected_kind = "owl:AnnotationProperty"
            rationale = "Schema relation retained as a property rather than promoted to a class."
            label = _best_label(clean if any(clean.triples((subject, None, None))) else source, subject, local_name)
            review_status = "schema-reviewed"
        elif (subject, RDF.type, H2KG.DataPoint) in source or local_name.startswith("ITCQuantityGuidance_"):
            disposition = "profile_or_workflow_field"
            corrected_kind = "profile construct"
            rationale = "Contextual field retained in the profile/compatibility layer and excluded from the reusable class taxonomy."
            label = _best_label(source, subject, local_name)
            review_status = "compatibility-preserved"
        elif _is_quantity_value(source, subject) or local_name.startswith("_") or local_name.endswith("_QV"):
            disposition = "named_individual"
            corrected_kind = "qudt:QuantityValue individual"
            rationale = "Quantity-value or generated value record retained as an individual, not an OWL class."
            label = _best_label(source, subject, local_name)
            review_status = "compatibility-preserved"
        elif local_name == "UNKNOWN" or subject not in source_subjects:
            disposition = "source_metadata_only"
            corrected_kind = "unresolved source marker"
            rationale = "Legacy source marker is retained only for audit provenance and is excluded from the clean taxonomy."
            label = _best_label(source, subject, local_name)
            review_status = "deprecated-source-marker"
        else:
            disposition = "named_individual"
            corrected_kind = "owl:NamedIndividual"
            rationale = "Contextual source resource retained as an individual pending a more specific profile disposition."
            label = _best_label(source, subject, local_name)
            review_status = str(config.get("review_status", "domain-expert-reviewed"))

        rows.append(
            {
                "iri": iri,
                "local_name": local_name,
                "label": label,
                "source_types": source_types,
                "corrected_kind": corrected_kind,
                "disposition": disposition,
                "source_exists": source_exists,
                "review_status": review_status,
                "rationale": rationale,
            }
        )
    return rows


def _load_auto_harmonization(config_dir: str | Path) -> dict[str, Any]:
    path = Path(config_dir) / "tib_auto_harmonization.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("format") not in {
        "h2kg-tib-auto-harmonization/v1",
        "h2kg-tib-auto-harmonization/v2",
    }:
        raise ValueError(f"Unsupported TIB harmonization registry format: {payload.get('format')}")
    if payload.get("owl_imports_added"):
        raise ValueError("The automatic TIB harmonization registry may not add owl:imports.")
    unsafe = [row for row in payload.get("mappings", []) if row.get("status") != "machine_safe"]
    unsafe.extend(row for row in payload.get("label_changes", []) if row.get("status") != "machine_safe")
    if unsafe:
        raise ValueError("The automatic TIB harmonization registry contains non-machine-safe rows.")
    if payload.get("format") == "h2kg-tib-auto-harmonization/v2":
        supported = {"skos:exactMatch", "skos:broadMatch", "skos:narrowMatch"}
        invalid = [row for row in payload.get("mappings", []) if row.get("relation") not in supported]
        if invalid:
            raise ValueError("The automatic TIB harmonization registry contains an unsupported relation.")
    return payload


def _load_controlled_corrections(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("format") != "h2kg-tib-controlled-corrections/v1":
        raise ValueError(f"Unsupported H2KG correction registry format: {payload.get('format')}")
    corrections: dict[str, dict[str, Any]] = {}
    for record in payload.get("corrections", []):
        if record.get("status") != "applied" or record.get("confidence") != "high":
            continue
        local_name = str(record.get("local_name", "")).strip()
        if not local_name:
            raise ValueError("A controlled H2KG correction lacks local_name.")
        if local_name in corrections:
            raise ValueError(f"Duplicate controlled correction for {local_name}.")
        corrections[local_name] = dict(record)
    return corrections


def _build_external_bridge(
    output_root: Path,
    config_dir: str | Path,
    config: dict[str, Any],
    auto_harmonization: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Publish a conservative, versioned SKOS bridge plus reviewed mappings."""

    ontology_dir = ensure_dir(output_root / "ontology")
    reports_dir = ensure_dir(output_root / "reports")
    bridge_ttl = ontology_dir / "h2kg-v2-external-bridge.ttl"
    bridge_jsonld = ontology_dir / "h2kg-v2-external-bridge.jsonld"
    registry_json = ontology_dir / "external_alignment_registry.json"
    registry_csv = ontology_dir / "external_alignment_registry.csv"
    sssom_tsv = ontology_dir / "h2kg-tib-asserted-mappings.sssom.tsv"
    changelog_csv = ontology_dir / "h2kg-tib-alignment-changelog.csv"
    previous_registry: dict[str, Any] = {}
    if registry_json.exists():
        previous_registry = json.loads(registry_json.read_text(encoding="utf-8"))
    config_root = Path(config_dir)
    collection_snapshot_path = config_root.parent / "input" / "tib_collection_snapshot.json"
    legacy_snapshot_path = config_root.parent / "input" / "tib_terminology_snapshot.json"
    collection_snapshot: dict[str, Any] = {}
    legacy_snapshot: dict[str, Any] = {}
    if collection_snapshot_path.exists():
        collection_snapshot = json.loads(collection_snapshot_path.read_text(encoding="utf-8"))
    if legacy_snapshot_path.exists():
        legacy_snapshot = json.loads(legacy_snapshot_path.read_text(encoding="utf-8"))
    snapshot = collection_snapshot or legacy_snapshot
    snapshot_sha256 = str((auto_harmonization or {}).get("snapshot_sha256") or _json_payload_sha256(snapshot))
    snapshot_date = str(snapshot.get("retrieved_at", "snapshot-not-available"))
    snapshot_slug = re.sub(r"[^0-9]", "", snapshot_date[:10]) or "undated"
    version = str(config.get("version", "2.1.0"))
    immutable_stem = f"h2kg-external-bridge-{snapshot_slug}-{snapshot_sha256[:12]}"
    bridge_iri = URIRef("https://vimilabs.github.io/AIMWORKS/ontology/h2kg-v2-external-bridge.ttl")
    version_iri = URIRef(
        f"https://vimilabs.github.io/AIMWORKS/ontology/releases/{version}/{immutable_stem}.ttl"
    )
    graph = Graph()
    _bind_namespaces(graph, Graph())
    graph.add((bridge_iri, RDF.type, OWL.Ontology))
    graph.add((bridge_iri, OWL.imports, URIRef(str(config.get("version_iri", H2KG_ONTOLOGY)))))
    graph.add((bridge_iri, OWL.versionIRI, version_iri))
    graph.add((bridge_iri, OWL.versionInfo, Literal(version)))
    graph.add((bridge_iri, DCTERMS.title, Literal("H2KG External Semantic Alignment Bridge", lang="en")))
    graph.add((bridge_iri, DCTERMS.created, Literal(datetime.now(timezone.utc).replace(microsecond=0).isoformat(), datatype=XSD.dateTime)))
    graph.add((bridge_iri, DCTERMS.identifier, Literal(snapshot_sha256)))
    graph.add((bridge_iri, DCTERMS.source, URIRef("https://api.terminology.tib.eu/api")))
    graph.add((bridge_iri, RDFS.seeAlso, URIRef("https://vimilabs.github.io/AIMWORKS/pages/tib-benchmark.html")))
    graph.add(
        (
            bridge_iri,
            DCTERMS.description,
            Literal(
                "Versioned exact, broader, and narrower mappings from H2KG to original ontology IRIs discovered through the TIB Terminology Service. Related benchmark evidence is published separately and no external ontology collection is imported wholesale.",
                lang="en",
            ),
        )
    )

    tib_by_id = {
        str(item.get("ontology_id", "")).casefold(): item
        for item in snapshot.get("ontologies", [])
        if item.get("ontology_id")
    }
    for item in legacy_snapshot.get("ontologies", []):
        if item.get("ontology_id"):
            tib_by_id.setdefault(str(item["ontology_id"]).casefold(), item)
    source_to_tib = {
        "chebi": "chebi",
        "emmo-core": "emmo",
        "emmo-electrochemistry": "emmo",
        "qudt-schema": "qudt",
        "qudt-units": "unit",
        "qudt-quantitykinds": "quantitykind",
        "prov-o": "prov",
        "dcterms": "dcterms",
        "chmo": "chmo",
        "obi": "obi",
        "edam": "edam",
        "voc4cat": "voc4cat",
    }
    mapping_rules_path = Path(config_dir) / "mapping_rules.yaml"
    mapping_rules = yaml.safe_load(mapping_rules_path.read_text(encoding="utf-8")) if mapping_rules_path.exists() else {}
    current_manual_overrides = {
        str(local_name): {
            "relation": str(spec.get("relation", "")),
            "target": str(spec.get("target", "")),
        }
        for local_name, spec in (mapping_rules or {}).get("manual_overrides", {}).items()
    }
    superseded_manual_mappings = {
        (
            str(spec.get("local", "")),
            str(spec.get("relation", "")),
            str(spec.get("target", "")),
        )
        for spec in (mapping_rules or {}).get("superseded_manual_mappings", [])
    }
    relation_iris = {
        "owl:equivalentClass": OWL.equivalentClass,
        "owl:equivalentProperty": OWL.equivalentProperty,
        "rdfs:subClassOf": RDFS.subClassOf,
        "rdfs:subPropertyOf": RDFS.subPropertyOf,
        "skos:exactMatch": SKOS.exactMatch,
        "skos:closeMatch": SKOS.closeMatch,
        "skos:broadMatch": SKOS.broadMatch,
        "skos:narrowMatch": SKOS.narrowMatch,
        "skos:relatedMatch": SKOS.relatedMatch,
    }
    registry_rows: list[dict[str, Any]] = []
    pending_review_rows: list[dict[str, Any]] = []
    stale_manual_rows: list[dict[str, str]] = []
    invalid_rows: list[dict[str, str]] = []
    reviewed_statuses = {"manual_override", "human_reviewed", "reviewed", "approved"}
    review_path = output_root / "review" / "mapping_review.csv"
    if review_path.exists():
        with review_path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                local_iri = str(row.get("local_iri", "")).strip()
                target_iri = str(row.get("target_iri", "")).strip()
                relation = str(row.get("relation", "")).strip()
                status = str(row.get("status", "")).strip()
                local_name = _local_name(URIRef(local_iri)) if local_iri else ""
                if status == "manual_override":
                    expected = current_manual_overrides.get(local_name)
                    explicitly_superseded = (local_name, relation, target_iri) in superseded_manual_mappings
                    configured_but_changed = bool(expected) and (
                        expected["relation"] != relation or expected["target"] != target_iri
                    )
                    if explicitly_superseded or configured_but_changed:
                        stale_manual_rows.append(
                            {
                                "local_iri": local_iri,
                                "relation": relation,
                                "target_iri": target_iri,
                                "reason": "Manual mapping no longer matches config/mapping_rules.yaml.",
                            }
                        )
                        continue
                predicate = relation_iris.get(relation)
                if not local_iri or not target_iri or predicate is None or not _is_original_external_iri(target_iri):
                    invalid_rows.append(
                        {
                            "local_iri": local_iri,
                            "relation": relation,
                            "target_iri": target_iri,
                            "reason": "Mapping lacks a local IRI, original target ontology IRI, or supported reviewed relation.",
                        }
                    )
                    continue
                source_id = str(row.get("source", "")).strip()
                tib_id = source_to_tib.get(source_id, source_id)
                tib_record = tib_by_id.get(tib_id.casefold(), {})
                registry_row = {
                    **row,
                    "tib_ontology_id": tib_id,
                    "tib_ontology_title": tib_record.get("title", source_id),
                    "tib_ontology_version": tib_record.get("version") or "version-not-reported-in-TIB-snapshot",
                    "tib_snapshot_retrieved_at": snapshot.get("retrieved_at", "snapshot-not-available"),
                    "tib_snapshot_sha256": snapshot_sha256,
                    "tib_loaded_at": tib_record.get("loaded", "not-indexed-as-separate-resource"),
                    "tib_catalogue_url": f"https://terminology.tib.eu/ts/ontologies/{tib_id}" if tib_id else "",
                    "collections": _snapshot_collections(snapshot, tib_id),
                    "confidence": "high",
                    "rule_id": "MANUAL-REVIEWED-MAPPING",
                    "alignment_category": "reviewed_foundational_alignment",
                    "mapping_evidence": row.get("rationale", ""),
                    "reviewer_decision": (
                        "accepted-configured-review"
                        if status == "manual_override"
                        else "accepted-human-review"
                        if status in reviewed_statuses
                        else "pending-human-review"
                    ),
                }
                if status not in reviewed_statuses:
                    registry_row["publication_status"] = "pending-human-review"
                    pending_review_rows.append(registry_row)
                    continue
                required_values = (
                    registry_row.get("local_iri"),
                    registry_row.get("target_iri"),
                    registry_row.get("relation"),
                    registry_row.get("mapping_evidence"),
                    registry_row.get("reviewer_decision"),
                    registry_row.get("tib_ontology_id"),
                    registry_row.get("tib_ontology_version"),
                    registry_row.get("tib_snapshot_retrieved_at"),
                )
                if not all(str(value or "").strip() for value in required_values):
                    invalid_rows.append(
                        {
                            "local_iri": local_iri,
                            "relation": relation,
                            "target_iri": target_iri,
                            "reason": "Mapping lacks required review or dated TIB provenance fields.",
                        }
                    )
                    continue
                registry_rows.append(registry_row)
                registry_row["publication_status"] = "asserted-reviewed"
                graph.add((URIRef(local_iri), predicate, URIRef(target_iri)))

    represented_local_names = {
        _local_name(URIRef(str(row["local_iri"])))
        for row in registry_rows
        if row.get("local_iri")
    }
    for local_name, spec in sorted(current_manual_overrides.items()):
        if local_name in represented_local_names:
            continue
        full_spec = (mapping_rules or {}).get("manual_overrides", {}).get(local_name, {})
        relation = str(spec.get("relation", ""))
        target_iri = str(spec.get("target", ""))
        predicate = relation_iris.get(relation)
        source_id = str(full_spec.get("source", "")).strip()
        tib_id = source_to_tib.get(source_id, source_id)
        tib_record = tib_by_id.get(tib_id.casefold(), {})
        local_iri = str(H2KG[local_name])
        registry_row = {
            "local_iri": local_iri,
            "local_label": str(config.get("structural_classes", {}).get(local_name, {}).get("label", _humanize(local_name))),
            "local_kind": str(full_spec.get("local_kind", "")),
            "relation": relation,
            "target_iri": target_iri,
            "target_label": str(full_spec.get("target_label", "")),
            "target_kind": str(full_spec.get("target_kind", "")),
            "source": source_id,
            "score": 0.99,
            "status": "manual_override",
            "rationale": str(full_spec.get("rationale", "")),
            "tib_ontology_id": tib_id,
            "tib_ontology_title": tib_record.get("title", source_id),
            "tib_ontology_version": tib_record.get("version") or "version-not-reported-in-TIB-snapshot",
            "tib_snapshot_retrieved_at": snapshot.get("retrieved_at", "snapshot-not-available"),
            "tib_snapshot_sha256": snapshot_sha256,
            "tib_loaded_at": tib_record.get("loaded", "not-indexed-as-separate-resource"),
            "tib_catalogue_url": f"https://terminology.tib.eu/ts/ontologies/{tib_id}" if tib_id else "",
            "collections": _snapshot_collections(snapshot, tib_id),
            "confidence": "high",
            "rule_id": "MANUAL-CONFIGURED-MAPPING",
            "alignment_category": "reviewed_foundational_alignment",
            "mapping_evidence": str(full_spec.get("rationale", "")),
            "reviewer_decision": "accepted-configured-review",
            "publication_status": "asserted-reviewed",
        }
        required_values = (
            registry_row["local_kind"],
            registry_row["target_label"],
            registry_row["target_kind"],
            registry_row["source"],
            registry_row["mapping_evidence"],
            registry_row["tib_ontology_id"],
            registry_row["tib_ontology_version"],
            registry_row["tib_snapshot_retrieved_at"],
        )
        if (
            predicate is None
            or not target_iri
            or not _is_original_external_iri(target_iri)
            or not all(str(value or "").strip() for value in required_values)
        ):
            invalid_rows.append(
                {
                    "local_iri": local_iri,
                    "relation": relation,
                    "target_iri": target_iri,
                    "reason": "Configured v2 mapping lacks required relation, kind, source, evidence, or dated TIB provenance.",
                }
            )
            continue
        registry_rows.append(registry_row)
        graph.add((URIRef(local_iri), predicate, URIRef(target_iri)))

    represented_mappings = {
        (str(row.get("local_iri", "")), str(row.get("relation", "")), str(row.get("target_iri", "")))
        for row in registry_rows
    }
    reviewed_pairs = {
        (str(row.get("local_iri", "")), str(row.get("target_iri", "")))
        for row in registry_rows
    }
    for row in (auto_harmonization or {}).get("mappings", []):
        relation = str(row.get("relation", ""))
        if (
            row.get("status") != "machine_safe"
            or row.get("confidence") != "high"
            or relation not in {"skos:exactMatch", "skos:broadMatch", "skos:narrowMatch"}
        ):
            continue
        local_iri = str(row.get("local_iri", "")).strip()
        target_iri = str(row.get("target_iri", "")).strip()
        mapping_key = (local_iri, relation, target_iri)
        if local_iri and target_iri and not _is_original_external_iri(target_iri):
            invalid_rows.append(
                {
                    "local_iri": local_iri,
                    "relation": relation,
                    "target_iri": target_iri,
                    "reason": "Automatic target is a catalogue page rather than an original ontology IRI.",
                }
            )
            continue
        if (
            not local_iri
            or not target_iri
            or (local_iri, target_iri) in reviewed_pairs
            or mapping_key in represented_mappings
        ):
            continue
        tib_id = str(row.get("tib_ontology_id", "")).casefold()
        tib_record = tib_by_id.get(tib_id, {})
        registry_row = {
            "local_iri": local_iri,
            "local_label": str(row.get("local_label", "")),
            "local_kind": "class",
            "relation": relation,
            "target_iri": target_iri,
            "target_label": str(row.get("target_label", "")),
            "target_kind": "class",
            "source": tib_id,
            "score": "1.0" if relation == "skos:exactMatch" else "0.95",
            "status": "machine_safe",
            "rationale": str(row.get("decision_basis", "Strict automated publication gates passed.")),
            "tib_ontology_id": tib_id,
            "tib_ontology_title": row.get("tib_ontology_title") or tib_record.get("title", tib_id),
            "tib_ontology_version": row.get("tib_ontology_version") or tib_record.get("version") or "version-not-reported-in-TIB-snapshot",
            "tib_snapshot_retrieved_at": row.get("snapshot_retrieved_at") or snapshot.get("retrieved_at", "snapshot-not-available"),
            "tib_snapshot_sha256": row.get("snapshot_sha256") or snapshot_sha256,
            "tib_loaded_at": tib_record.get("loaded", "not-indexed-as-separate-resource"),
            "tib_catalogue_url": row.get("tib_catalogue_url") or f"https://terminology.tib.eu/ts/ontologies/{tib_id}",
            "collections": row.get("collections") or _snapshot_collections(snapshot, tib_id),
            "outcome": str(row.get("outcome", "")),
            "confidence": "high",
            "rule_id": str(row.get("rule_id", "")),
            "alignment_category": "tib_benchmark_alignment",
            "scope_evidence": str(row.get("scope_evidence", "")),
            "mapping_evidence": str(row.get("decision_basis", "Strict automated publication gates passed.")),
            "reviewer_decision": "accepted-machine-safe",
            "publication_status": "asserted-machine-safe",
        }
        required_values = (
            registry_row["tib_ontology_id"],
            registry_row["tib_ontology_version"],
            registry_row["tib_snapshot_retrieved_at"],
            registry_row["tib_snapshot_sha256"],
            registry_row["mapping_evidence"],
            registry_row["rule_id"],
        )
        if not all(str(value or "").strip() for value in required_values):
            invalid_rows.append(
                {
                    "local_iri": local_iri,
                    "relation": relation,
                    "target_iri": target_iri,
                    "reason": "Machine mapping lacks target ontology, rule, evidence, version, or snapshot provenance.",
                }
            )
            continue
        registry_rows.append(registry_row)
        represented_mappings.add(mapping_key)
        reviewed_pairs.add((local_iri, target_iri))
        graph.add((URIRef(local_iri), relation_iris[relation], URIRef(target_iri)))

    exact_iri_reuse = [
        dict(row)
        for row in (auto_harmonization or {}).get("exact_iri_reuse", [])
        if row.get("status") == "machine_safe"
    ]
    invalid_rows.extend(_external_bridge_conflicts(registry_rows))
    external_imports = {
        str(value)
        for value in graph.objects(bridge_iri, OWL.imports)
        if str(value) != str(config.get("version_iri", H2KG_ONTOLOGY))
    }
    if external_imports:
        invalid_rows.append(
            {
                "local_iri": str(bridge_iri),
                "relation": "owl:imports",
                "target_iri": " | ".join(sorted(external_imports)),
                "reason": "The bridge must not import external ontology collections.",
            }
        )

    registry_rows.sort(
        key=lambda row: (
            str(row.get("local_iri", "")),
            str(row.get("relation", "")),
            str(row.get("target_iri", "")),
        )
    )
    _serialize_graph(graph, bridge_ttl, "turtle")
    _serialize_graph(graph, bridge_jsonld, "json-ld")
    immutable_dir = ensure_dir(ontology_dir / "releases" / version)
    immutable_ttl = immutable_dir / f"{immutable_stem}.ttl"
    immutable_jsonld = immutable_dir / f"{immutable_stem}.jsonld"
    _serialize_graph(graph, immutable_ttl, "turtle")
    _serialize_graph(graph, immutable_jsonld, "json-ld")
    turtle_graph = Graph().parse(bridge_ttl, format="turtle")
    jsonld_graph = Graph().parse(bridge_jsonld, format="json-ld")
    serializations_isomorphic = isomorphic(turtle_graph, jsonld_graph)
    if not serializations_isomorphic:
        invalid_rows.append(
            {
                "local_iri": str(bridge_iri),
                "relation": "serialization-parity",
                "target_iri": "",
                "reason": "Turtle and JSON-LD bridge serializations are not RDF-isomorphic.",
            }
        )

    changelog_rows = _external_alignment_changelog(
        previous_registry.get("mappings", []),
        registry_rows,
    )
    _write_sssom(sssom_tsv, registry_rows, str(bridge_iri), version)
    _write_dict_csv(changelog_csv, changelog_rows)
    write_text(
        registry_json,
        json.dumps(
            {
                "schema_version": "h2kg-external-alignment-registry/v3",
                "ontology_iri": str(bridge_iri),
                "version_iri": str(version_iri),
                "h2kg_version": version,
                "tib_snapshot_retrieved_at": snapshot.get("retrieved_at", "snapshot-not-available"),
                "tib_snapshot_sha256": snapshot_sha256,
                "policy": "reviewed mappings plus strict machine-safe SKOS exact/broad/narrow assertions; related evidence is not asserted",
                "mappings": registry_rows,
                "exact_iri_reuse": exact_iri_reuse,
                "pending_review_mappings": pending_review_rows,
                "excluded_stale_manual_mappings": stale_manual_rows,
                "invalid_mappings": invalid_rows,
                "benchmark_evidence": "../benchmarks/tib_collections/candidate_decisions.csv",
                "changelog": changelog_rows,
            },
            indent=2,
            ensure_ascii=False,
        ),
    )
    _write_dict_csv(registry_csv, registry_rows)
    asserted_counts = dict(sorted(Counter(str(row.get("relation", "")) for row in registry_rows).items()))
    category_counts = dict(
        sorted(Counter(str(row.get("alignment_category", "unspecified")) for row in registry_rows).items())
    )
    machine_rows = [row for row in registry_rows if row.get("status") == "machine_safe"]
    reviewed_rows = [row for row in registry_rows if row.get("status") != "machine_safe"]
    tib_asserted_counts = dict(
        sorted(Counter(str(row.get("relation", "")) for row in machine_rows).items())
    )
    report = {
        "h2kg_version": version,
        "bridge_iri": str(bridge_iri),
        "bridge_version_iri": str(version_iri),
        "mapping_count": len(registry_rows),
        "asserted_mapping_counts": asserted_counts,
        "tib_asserted_mapping_counts": tib_asserted_counts,
        "alignment_category_counts": category_counts,
        "tib_benchmark_asserted_mapping_count": len(machine_rows),
        "reviewed_foundational_mapping_count": len(reviewed_rows),
        "mapped_h2kg_class_count": len({row.get("local_iri") for row in registry_rows}),
        "external_ontology_count": len({row.get("tib_ontology_id") for row in registry_rows if row.get("tib_ontology_id")}),
        "exact_iri_reuse_count": len(exact_iri_reuse),
        "pending_review_mapping_count": len(pending_review_rows),
        "excluded_stale_manual_mapping_count": len(stale_manual_rows),
        "invalid_mapping_count": len(invalid_rows),
        "tib_snapshot_retrieved_at": snapshot.get("retrieved_at", "snapshot-not-available"),
        "tib_snapshot_sha256": snapshot_sha256,
        "tib_collection_count": len(snapshot.get("collections", {})),
        "tib_unique_ontology_count": int(snapshot.get("unique_ontology_count") or len(snapshot.get("ontologies", []))),
        "tib_collection_membership_count": sum(
            len(record.get("ontology_ids", [])) for record in snapshot.get("collections", {}).values()
        ),
        "sources": dict(sorted(Counter(row.get("source", "") for row in registry_rows).items())),
        "tib_benchmark_sources": dict(
            sorted(Counter(row.get("source", "") for row in machine_rows).items())
        ),
        "reviewed_foundational_sources": dict(
            sorted(Counter(row.get("source", "") for row in reviewed_rows).items())
        ),
        "turtle": str(bridge_ttl),
        "jsonld": str(bridge_jsonld),
        "immutable_turtle": str(immutable_ttl),
        "immutable_jsonld": str(immutable_jsonld),
        "registry": str(registry_json),
        "sssom": str(sssom_tsv),
        "changelog": str(changelog_csv),
        "machine_safe_mapping_count": len(machine_rows),
        "serializations_isomorphic": serializations_isomorphic,
        "automatic_logical_axiom_count": sum(
            row.get("status") == "machine_safe"
            and row.get("relation") in {
                "owl:equivalentClass", "owl:equivalentProperty", "owl:sameAs",
                "rdfs:subClassOf", "rdfs:subPropertyOf",
            }
            for row in registry_rows
        ),
        "external_import_count": len(external_imports),
        "policy": "conservative SKOS assertion tiers; related evidence is non-asserted; no wholesale TIB collection import",
    }
    write_text(reports_dir / "tib_alignment_readiness.json", json.dumps(report, indent=2, ensure_ascii=False))
    return report


def _json_payload_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _snapshot_collections(snapshot: dict[str, Any], ontology_id: str) -> list[str]:
    ontology_key = str(ontology_id).casefold()
    values: list[str] = []
    for record in snapshot.get("ontologies", []):
        if str(record.get("ontology_id", "")).casefold() != ontology_key:
            continue
        values.extend(str(value) for value in record.get("target_collections", []) if value)
        values.extend(str(value) for value in record.get("collections", []) if value)
    for key, record in snapshot.get("collections", {}).items():
        members = {str(value).casefold() for value in record.get("ontology_ids", [])}
        if ontology_key in members:
            values.append(str(record.get("catalogue_name") or record.get("requested_name") or key))
    return sorted(set(values), key=str.casefold)


def _is_original_external_iri(value: str) -> bool:
    candidate = str(value).strip()
    if not re.match(r"^(?:https?://|urn:)", candidate):
        return False
    lowered = candidate.casefold()
    return "terminology.tib.eu/ts/" not in lowered and "api.terminology.tib.eu/" not in lowered


def _external_bridge_conflicts(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    by_pair: dict[tuple[str, str], set[str]] = defaultdict(set)
    exact_targets: dict[str, set[str]] = defaultdict(set)
    exact_relations = {"skos:exactMatch", "owl:equivalentClass", "owl:sameAs"}
    logical_relations = {
        "owl:equivalentClass", "owl:equivalentProperty", "owl:sameAs",
        "rdfs:subClassOf", "rdfs:subPropertyOf",
    }
    for row in rows:
        local_iri = str(row.get("local_iri", ""))
        target_iri = str(row.get("target_iri", ""))
        relation = str(row.get("relation", ""))
        by_pair[(local_iri, target_iri)].add(relation)
        if relation in exact_relations:
            exact_targets[target_iri].add(local_iri)
        if row.get("status") == "machine_safe" and relation in logical_relations | {"skos:relatedMatch"}:
            errors.append(
                {
                    "local_iri": local_iri,
                    "relation": relation,
                    "target_iri": target_iri,
                    "reason": "Automatic mappings may assert only SKOS exactMatch, broadMatch, or narrowMatch.",
                }
            )
        if not _is_original_external_iri(target_iri):
            errors.append(
                {
                    "local_iri": local_iri,
                    "relation": relation,
                    "target_iri": target_iri,
                    "reason": "Asserted mapping target is not an original ontology IRI.",
                }
            )
        required = (
            row.get("tib_ontology_id"),
            row.get("tib_ontology_version"),
            row.get("tib_snapshot_retrieved_at"),
            row.get("tib_snapshot_sha256"),
            row.get("mapping_evidence"),
        )
        if not all(str(value or "").strip() for value in required):
            errors.append(
                {
                    "local_iri": local_iri,
                    "relation": relation,
                    "target_iri": target_iri,
                    "reason": "Asserted mapping lacks ontology version, evidence, or frozen-snapshot provenance.",
                }
            )
    for (local_iri, target_iri), relations in sorted(by_pair.items()):
        if len(relations) <= 1:
            continue
        errors.append(
            {
                "local_iri": local_iri,
                "relation": " | ".join(sorted(relations)),
                "target_iri": target_iri,
                "reason": "The same IRI pair has contradictory mapping predicates.",
            }
        )
    for target_iri, local_iris in sorted(exact_targets.items()):
        if len(local_iris) <= 1:
            continue
        errors.append(
            {
                "local_iri": " | ".join(sorted(local_iris)),
                "relation": "exact-equivalence-collision",
                "target_iri": target_iri,
                "reason": "Multiple active H2KG classes exact-match the same external class.",
            }
        )
    return errors


def _write_sssom(path: Path, rows: list[dict[str, Any]], mapping_set_id: str, version: str) -> None:
    ensure_dir(path.parent)
    fieldnames = [
        "subject_id", "subject_label", "predicate_id", "object_id", "object_label",
        "mapping_justification", "confidence", "mapping_tool", "mapping_date",
        "subject_source", "object_source", "object_source_version", "mapping_set_id",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            manual = row.get("status") != "machine_safe"
            writer.writerow(
                {
                    "subject_id": row.get("local_iri", ""),
                    "subject_label": row.get("local_label", ""),
                    "predicate_id": row.get("relation", ""),
                    "object_id": row.get("target_iri", ""),
                    "object_label": row.get("target_label", ""),
                    "mapping_justification": (
                        "semapv:ManualMappingCuration" if manual else "semapv:CompositeMatching"
                    ),
                    "confidence": "1.0" if manual else str(row.get("score") or "0.95"),
                    "mapping_tool": "https://github.com/ViMiLabs/AIMWORKS",
                    "mapping_date": datetime.now(timezone.utc).date().isoformat(),
                    "subject_source": f"h2kg:{version}",
                    "object_source": row.get("tib_ontology_id", ""),
                    "object_source_version": row.get("tib_ontology_version", ""),
                    "mapping_set_id": mapping_set_id,
                }
            )


def _external_alignment_changelog(
    previous_rows: list[dict[str, Any]],
    final_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    def pair_index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
        result: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            result[(str(row.get("local_iri", "")), str(row.get("target_iri", "")))].append(row)
        return result

    previous = pair_index(previous_rows)
    final = pair_index(final_rows)
    changelog: list[dict[str, Any]] = []
    for pair in sorted(set(previous) | set(final)):
        old_rows = previous.get(pair, [])
        new_rows = final.get(pair, [])
        old_relations = sorted({str(row.get("relation", "")) for row in old_rows})
        new_relations = sorted({str(row.get("relation", "")) for row in new_rows})
        if old_relations == new_relations:
            status = "retained"
        elif old_rows and new_rows:
            status = "reclassified"
        elif new_rows:
            status = "added"
        else:
            status = "removed"
        exemplar = (new_rows or old_rows)[0]
        changelog.append(
            {
                "change": status,
                "local_iri": pair[0],
                "local_label": exemplar.get("local_label", ""),
                "target_iri": pair[1],
                "target_label": exemplar.get("target_label", ""),
                "previous_relation": " | ".join(old_relations),
                "final_relation": " | ".join(new_relations),
                "previous_status": " | ".join(sorted({str(row.get("status", "")) for row in old_rows})),
                "final_status": " | ".join(sorted({str(row.get("status", "")) for row in new_rows})),
                "rationale": str(exemplar.get("mapping_evidence") or exemplar.get("rationale") or ""),
            }
        )
    return changelog


def _is_descendant(graph: Graph, child: URIRef, ancestor: URIRef) -> bool:
    if child == ancestor:
        return True
    pending = [child]
    visited: set[URIRef] = set()
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        for parent in graph.objects(current, RDFS.subClassOf):
            if not isinstance(parent, URIRef):
                continue
            if parent == ancestor:
                return True
            pending.append(parent)
    return False


def _run_competency_checks(
    taxonomy: Graph,
    compatibility: Graph,
    decisions: list[TaxonomyDecision],
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def record(identifier: str, passed: bool, detail: str, evidence: Iterable[str] = ()) -> None:
        checks.append(
            {
                "id": identifier,
                "passed": bool(passed),
                "detail": detail,
                "evidence": sorted(set(str(value) for value in evidence)),
            }
        )

    electron_methods = (
        H2KG.TransmissionElectronMicroscopyImaging,
        H2KG.ScanningElectronMicroscopyImaging,
        H2KG.SEMImagingMeasurement,
        H2KG.ICSEMImagingMeasurement,
    )
    record(
        "electron-microscopy-method-retrieval",
        all(_is_descendant(taxonomy, method, H2KG.ElectronMicroscopyMeasurement) for method in electron_methods),
        "Representative TEM, SEM, and IC-SEM methods are retrievable below ElectronMicroscopyMeasurement.",
        map(_local_name, electron_methods),
    )

    tomography_methods = (
        H2KG.FIBSEMTomographyMeasurement,
        H2KG.NeutronTomographyMeasurement,
        H2KG.XRayComputedTomographyMeasurement,
    )
    record(
        "tomography-method-retrieval",
        all(_is_descendant(taxonomy, method, H2KG.TomographyMeasurement) for method in tomography_methods),
        "FIB-SEM, neutron, and X-ray tomography methods are retrievable below TomographyMeasurement.",
        map(_local_name, tomography_methods),
    )

    dataset_expectations = {
        H2KG.SEMImageDataset: H2KG.ElectronMicroscopyImageDataset,
        H2KG.XRDPatternDataset: H2KG.DiffractionDataset,
        H2KG.TomographicReconstructionDataset: H2KG.TomographyDataset,
    }
    record(
        "characterization-dataset-retrieval",
        all(_is_descendant(taxonomy, child, parent) for child, parent in dataset_expectations.items()),
        "Representative microscopy, diffraction, and tomography datasets resolve through their dataset branches.",
        (f"{_local_name(child)} -> {_local_name(parent)}" for child, parent in dataset_expectations.items()),
    )

    characteristic_terms = (
        H2KG.CatalystLayerThickness,
        H2KG.CurrentDensity,
        H2KG.IonomerToCarbonRatio,
        H2KG.GasDiffusionLayerPorosity,
    )
    record(
        "canonical-characteristic-identity",
        all(_is_descendant(taxonomy, term, H2KG.Characteristic) for term in characteristic_terms),
        "Quantities used as parameters or results have one canonical identity below Characteristic.",
        map(_local_name, characteristic_terms),
    )

    tem = H2KG.TransmissionElectronMicroscopyImaging
    tem_requirements = (H2KG.usesInstrument, H2KG.hasParameter, H2KG.hasOutputData)
    tem_evidence = [
        f"{_local_name(predicate)}={len(set(compatibility.objects(tem, predicate)))}"
        for predicate in tem_requirements
    ]
    record(
        "tem-workflow-compatibility",
        all(any(compatibility.objects(tem, predicate)) for predicate in tem_requirements)
        and (H2KG.hasMeasurementSubject, RDF.type, OWL.ObjectProperty) in taxonomy,
        "The preserved TEM vocabulary view retains instrument, parameter, and output-data anchors; sample context is expressed on occurrences through hasMeasurementSubject.",
        tem_evidence,
    )

    model = H2KG.InkToCompositionModel
    itc_counts = {
        "parameters": len(set(compatibility.objects(model, H2KG.hasParameter))),
        "input_datasets": len(set(compatibility.objects(model, H2KG.hasInputData))),
        "output_datasets": len(set(compatibility.objects(model, H2KG.hasOutputData))),
    }
    record(
        "itc-profile-retrieval",
        itc_counts["parameters"] >= 16 and itc_counts["input_datasets"] >= 1 and itc_counts["output_datasets"] >= 4,
        "The grouped ITC profile exposes its 16 parameters, input dataset, scalar-result dataset, and three distribution datasets.",
        (f"{key}={value}" for key, value in itc_counts.items()),
    )

    mea_methods = {
        subject
        for subject in compatibility.subjects(H2KG.hasMeasurementSubject, H2KG.MEAAssembly)
        if (subject, RDF.type, H2KG.Measurement) in compatibility
    }
    record(
        "mea-measurement-subject-retrieval",
        bool(mea_methods),
        "Measurements using an MEA input are retrievable through the corrected measurement-subject projection.",
        map(_local_name, mea_methods),
    )

    record(
        "software-use-projection",
        _is_descendant(taxonomy, H2KG.FijiImageJSoftware, H2KG.SoftwareArtifact)
        and (H2KG.usesSoftware, RDF.type, OWL.ObjectProperty) in taxonomy,
        "Fiji/ImageJ is represented below SoftwareArtifact and the dedicated usesSoftware relation is available to profiles and occurrences.",
        ("FijiImageJSoftware -> SoftwareArtifact", "usesSoftware -> owl:ObjectProperty"),
    )

    modules = Counter(item.module for item in decisions if item.disposition == "active_local_class")
    record(
        "technology-module-retrieval",
        modules.get("pemfc", 0) > 0 and modules.get("pemwe", 0) > 0 and modules.get("core", 0) > 0,
        "Core, PEMFC, and PEMWE placements are all represented without duplicating shared concepts.",
        (f"{name}={count}" for name, count in sorted(modules.items())),
    )

    return {
        "schema_version": "h2kg-taxonomy-competency-report/v2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "all_passed": all(check["passed"] for check in checks),
        "passed": sum(1 for check in checks if check["passed"]),
        "total": len(checks),
        "checks": checks,
    }


def _validate_taxonomy(
    graph: Graph,
    compatibility: Graph,
    decisions: list[TaxonomyDecision],
    resources: list[dict[str, Any]],
    ttl_path: Path,
    jsonld_path: Path,
    config: dict[str, Any],
    bridge: dict[str, Any],
    competency: dict[str, Any],
    semantic_profiles: dict[str, Any],
    shacl_conforms: bool,
    shacl_report: str,
) -> dict[str, Any]:
    active = [item for item in decisions if item.disposition == "active_local_class"]
    deprecated = [item for item in decisions if item.disposition == "deprecated_compatibility_class"]
    errors: list[str] = []
    warnings: list[str] = []
    declared_roots = {"Matter", "Process", "InformationEntity", "Characteristic", "Agent"}
    missing_parents = [item.iri for item in active if item.top_branch not in declared_roots]
    orphan_classes = [item.iri for item in active if item.local_name not in declared_roots and not item.parent_iri]
    missing_definitions = [item.iri for item in active if not item.definition.strip()]
    placeholder_definitions = [item.iri for item in active if _looks_placeholder(item.definition)]
    missing_governance = [
        item.iri
        for item in active
        if not item.module or not item.review_status or not item.rationale or not item.corrected_semantic_role
    ]
    active_labels: defaultdict[str, list[str]] = defaultdict(list)
    for item in active:
        active_labels[_normalized_label(item.label)].append(item.iri)
    duplicate_labels = {label: iris for label, iris in active_labels.items() if len(iris) > 1}
    file_uris = sorted({str(value) for triple in graph for value in triple if isinstance(value, URIRef) and str(value).startswith("file:")})
    compatibility_file_uris = sorted(
        {
            str(value)
            for triple in compatibility
            for value in triple
            if isinstance(value, URIRef) and str(value).startswith("file:")
        }
    )
    unclassified_resources = [row["iri"] for row in resources if not row.get("disposition")]
    source_resources = [row for row in resources if row.get("source_exists")]
    source_resources_without_disposition = [row["iri"] for row in source_resources if not row.get("disposition")]
    self_subclasses = sorted(str(subject) for subject in graph.subjects(RDFS.subClassOf, None) if (subject, RDFS.subClassOf, subject) in graph)
    nothing_subclasses = sorted(str(subject) for subject in graph.subjects(RDFS.subClassOf, OWL.Nothing))
    cycles = _taxonomy_cycles(graph)
    asserted_imports = sorted(str(value).rstrip("#") for value in graph.objects(H2KG_ONTOLOGY, OWL.imports))
    allowed_imports = sorted(str(value).rstrip("#") for value in config.get("allowed_foundational_imports", []))
    unapproved_imports = sorted(set(asserted_imports) - set(allowed_imports))
    incompatible_role_types = sorted(
        item.iri
        for item in active
        if any(
            isinstance(type_iri, URIRef)
            and str(type_iri).startswith(str(H2KG))
            and _local_name(type_iri) in ROLE_NAMES
            for type_iri in graph.objects(URIRef(item.iri), RDF.type)
        )
    )

    if missing_parents:
        errors.append(f"{len(missing_parents)} active classes do not resolve to a declared top branch.")
    if orphan_classes:
        errors.append(f"{len(orphan_classes)} non-root active classes lack a primary parent.")
    if missing_definitions:
        errors.append(f"{len(missing_definitions)} active classes lack definitions.")
    if placeholder_definitions:
        errors.append(f"{len(placeholder_definitions)} active classes retain placeholder definitions.")
    if duplicate_labels:
        errors.append(f"{len(duplicate_labels)} normalized preferred-label collisions remain active.")
    if file_uris:
        errors.append(f"{len(file_uris)} local file IRIs occur in the clean taxonomy graph.")
    if compatibility_file_uris:
        errors.append(f"{len(compatibility_file_uris)} local file IRIs occur in the legacy compatibility graph.")
    if unclassified_resources or source_resources_without_disposition:
        errors.append("One or more local resources lack an explicit release disposition.")
    if missing_governance:
        errors.append(f"{len(missing_governance)} active classes lack required governance metadata.")
    if self_subclasses or cycles:
        errors.append("The class taxonomy contains a subclass cycle.")
    if nothing_subclasses:
        errors.append(f"{len(nothing_subclasses)} classes are asserted below owl:Nothing.")
    if incompatible_role_types:
        errors.append(f"{len(incompatible_role_types)} clean taxonomy classes retain legacy role-instance typing.")
    if unapproved_imports:
        errors.append(f"{len(unapproved_imports)} ontology imports are outside the foundational allowlist.")
    if int(bridge.get("invalid_mapping_count", 0)):
        errors.append(f"{bridge['invalid_mapping_count']} external mappings lack required relation, review, or dated TIB provenance fields.")
    if not bridge.get("serializations_isomorphic", False):
        errors.append("External-bridge Turtle and JSON-LD serializations are not RDF-isomorphic.")
    if int(bridge.get("automatic_logical_axiom_count", 0)):
        errors.append("Automatic external mappings introduced OWL/RDFS logical axioms or asserted relatedMatch links.")
    if int(bridge.get("external_import_count", 0)):
        errors.append("The external bridge imports one or more external ontology collections.")
    if not shacl_conforms:
        errors.append("The taxonomy class-label/definition SHACL profile does not conform.")
    if not competency.get("all_passed", False):
        failed = [str(item.get("id")) for item in competency.get("checks", []) if not item.get("passed")]
        errors.append(f"{len(failed)} taxonomy competency checks failed: {', '.join(failed)}.")
    if not semantic_profiles.get("conforms", False):
        errors.append("The parameter-property semantic-role migration did not conform.")

    ttl_graph = Graph().parse(ttl_path, format="turtle")
    json_graph = Graph().parse(jsonld_path, format="json-ld")
    if set(ttl_graph) != set(json_graph):
        errors.append("Turtle and JSON-LD taxonomy serializations are not RDF-isomorphic.")

    top_counts = Counter(item.top_branch for item in active)
    structural_count = sum(1 for item in active if item.migration_action == "add-taxonomy-scaffold-class")
    governance = config.get("governance", {})
    reviewer_signed = str(governance.get("domain_reviewer_status", "pending")).casefold() == "approved"
    reasoner_passed = str(governance.get("external_reasoner_status", "pending")).casefold() == "passed"
    if not reviewer_signed:
        warnings.append("Domain-expert approval is not recorded; publication is blocked.")
    if not reasoner_passed:
        warnings.append("External OWL reasoner validation is not recorded as passed; publication is blocked.")
    if int(bridge.get("excluded_stale_manual_mapping_count", 0)):
        warnings.append(
            f"{bridge['excluded_stale_manual_mapping_count']} stale manual external mapping was excluded because it no longer matches the reviewed mapping configuration."
        )
    publication_ready = not errors and (
        reviewer_signed or not governance.get("require_domain_reviewer_signoff", True)
    ) and (
        reasoner_passed or not governance.get("require_external_reasoner_for_publication", True)
    )
    return {
        "conforms": not errors,
        "publication_ready": publication_ready,
        "publication_status": "approved" if publication_ready else "blocked",
        "errors": errors,
        "warnings": warnings,
        "counts": {
            "active_local_classes": len(active),
            "deprecated_compatibility_classes": len(deprecated),
            "new_structural_classes": structural_count,
            "subclass_axioms": len(set(graph.triples((None, RDFS.subClassOf, None)))),
            "object_properties": len(set(graph.subjects(RDF.type, OWL.ObjectProperty))),
            "datatype_properties": len(set(graph.subjects(RDF.type, OWL.DatatypeProperty))),
            "annotation_properties": len(set(graph.subjects(RDF.type, OWL.AnnotationProperty))),
            "definitions": len(set(graph.subjects(SKOS.definition, None))),
            "source_local_resources": len(source_resources),
            "source_resources_with_disposition": len(source_resources) - len(source_resources_without_disposition),
            "all_registered_resources": len(resources),
            "profile_or_workflow_fields": sum(1 for row in resources if row.get("disposition") == "profile_or_workflow_field"),
            "named_individuals": sum(1 for row in resources if row.get("disposition") == "named_individual"),
            "external_mappings": int(bridge.get("mapping_count", 0)),
            "competency_checks": int(competency.get("total", 0)),
            "competency_checks_passed": int(competency.get("passed", 0)),
            "legacy_workflow_assertions": int(semantic_profiles.get("legacy_assertion_count", 0)),
            "workflow_profile_usages": int(semantic_profiles.get("workflow_usage_count", 0)),
            "parameter_property_paths": int(semantic_profiles.get("parameter_property_path_count", 0)),
        },
        "top_branch_counts": dict(sorted(top_counts.items())),
        "missing_parent_iris": missing_parents,
        "orphan_class_iris": orphan_classes,
        "missing_definition_iris": missing_definitions,
        "placeholder_definition_iris": placeholder_definitions,
        "duplicate_active_labels": duplicate_labels,
        "file_uris": file_uris,
        "compatibility_file_uris": compatibility_file_uris,
        "unclassified_resource_iris": unclassified_resources,
        "source_resources_without_disposition": source_resources_without_disposition,
        "subclass_cycles": cycles,
        "classes_below_owl_nothing": nothing_subclasses,
        "incompatible_role_type_iris": incompatible_role_types,
        "asserted_foundational_imports": asserted_imports,
        "unapproved_imports": unapproved_imports,
        "resolved_legacy_multi_role_classes": [item.iri for item in active if len(item.source_roles) > 1],
        "governance": {
            "domain_reviewer_status": governance.get("domain_reviewer_status", "pending"),
            "external_reasoner_status": governance.get("external_reasoner_status", "pending"),
            "technical_validation": "passed" if not errors else "failed",
        },
        "serialization_parity": set(ttl_graph) == set(json_graph),
        "shacl_conforms": shacl_conforms,
        "shacl_report": shacl_report,
        "competency_checks": competency,
    }


def _taxonomy_cycles(graph: Graph) -> list[list[str]]:
    adjacency: dict[URIRef, set[URIRef]] = defaultdict(set)
    for child, parent in graph.subject_objects(RDFS.subClassOf):
        if (
            isinstance(child, URIRef)
            and isinstance(parent, URIRef)
            and str(child).startswith(str(H2KG))
            and str(parent).startswith(str(H2KG))
        ):
            adjacency[child].add(parent)

    cycles: set[tuple[str, ...]] = set()

    def visit(node: URIRef, path: list[URIRef], visiting: set[URIRef]) -> None:
        if node in visiting:
            start = path.index(node)
            cycle = tuple(sorted(str(value) for value in path[start:]))
            cycles.add(cycle)
            return
        visiting.add(node)
        path.append(node)
        for parent in adjacency.get(node, set()):
            visit(parent, path, visiting)
        path.pop()
        visiting.remove(node)

    for node in adjacency:
        visit(node, [], set())
    return [list(cycle) for cycle in sorted(cycles)]


def _taxonomy_report(validation: dict[str, Any], decisions: list[TaxonomyDecision]) -> str:
    counts = validation["counts"]
    branches = "\n".join(f"- {branch}: {count}" for branch, count in validation["top_branch_counts"].items())
    return f"""# H2KG 2.1 Taxonomy Report

- Validation conforms: {validation['conforms']}
- Active local classes: {counts['active_local_classes']}
- Deprecated compatibility classes: {counts['deprecated_compatibility_classes']}
- Curated structural classes: {counts['new_structural_classes']}
- Asserted subclass axioms: {counts['subclass_axioms']}
- Definitions: {counts['definitions']}
- Turtle/JSON-LD parity: {validation['serialization_parity']}
- Taxonomy SHACL conforms: {validation['shacl_conforms']}
- All source resources classified: {counts['source_resources_with_disposition']} / {counts['source_local_resources']}
- Profile/workflow fields retained outside the class taxonomy: {counts['profile_or_workflow_fields']}
- Named individuals retained outside the class taxonomy: {counts['named_individuals']}
- Selective external mappings: {counts['external_mappings']}
- Competency checks: {counts['competency_checks_passed']} / {counts['competency_checks']}
- Publication ready: {validation['publication_ready']}

## Top-Level Branches

{branches}

## Governance

Every active class has a generated registry row containing its source roles, primary parent, path to a top-level branch, definition status, module, and migration rationale. H2KG is presented publicly as a domain-specific ontology; internal governance evidence and automated external-mapping decisions remain recorded separately in machine-readable registries.

The compatibility graph preserves the v1 role-typed and workflow-neighborhood statements. The clean taxonomy contains reusable classes and schema properties only; profile fields and value records are deliberately excluded from its class count.

## Publication Gates

- Technical validation: {validation['governance']['technical_validation']}
- Domain reviewer: {validation['governance']['domain_reviewer_status']}
- External OWL reasoner: {validation['governance']['external_reasoner_status']}

{chr(10).join(f'- {warning}' for warning in validation['warnings']) or '- No pending gates.'}

## Errors

{chr(10).join(f'- {error}' for error in validation['errors']) or '- None'}
"""


def _local_name(value: URIRef | str) -> str:
    text = str(value)
    return text.rsplit("#", 1)[-1] if "#" in text else text.rstrip("/").rsplit("/", 1)[-1]


def _humanize(value: str) -> str:
    if not value:
        return ""
    value = value.replace("_", " ").replace("-", " ")
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
    value = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", value)
    return " ".join(value.split())


def _normalized_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()
