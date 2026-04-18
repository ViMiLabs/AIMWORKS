from __future__ import annotations

from pathlib import Path
from typing import Any

from .classify import classify_resources
from .io import dump_jsonld_items, dump_turtle_items, load_json_document, merge_document_items
from .normalize import best_description, best_label
from .utils import (
    OWL_ONTOLOGY,
    RDFS_COMMENT,
    RDFS_IS_DEFINED_BY,
    RDFS_LABEL,
    SKOS_DEFINITION,
    default_metadata_defaults,
    default_release_profile,
    ensure_dir,
    humanize,
    local_name,
    try_load_yaml,
    write_text,
)

SCHEMA_DEFINITIONS: dict[str, str] = {
    "Agent": "A person, organization, software system, or other actor that bears responsibility for an activity, resource, or assertion in H2KG.",
    "Instrument": "A device or apparatus used to perform, control, or monitor a measurement, manufacturing step, or experimental operation.",
    "Parameter": "A condition, setting, or specified variable used to characterize how a process, measurement, or material state is defined.",
    "Unit": "A unit of measure used to express the magnitude of a quantity value in H2KG.",
    "Process": "A temporally extended activity or operation that unfolds through one or more steps and may involve materials, instruments, parameters, and outputs.",
    "Manufacturing": "A process that prepares, fabricates, modifies, or assembles a material, component, or device.",
    "Data": "A recorded informational entity that captures observations, derived results, metadata, or other digitally expressed content.",
    "Data Point": "An individual recorded value or observation within a dataset, measurement series, or derived data collection.",
    "Matter": "A material entity, substance, mixture, component, or physical artefact used, produced, or studied in the domain.",
    "Metadata": "Information that describes the provenance, identity, structure, context, or management of another resource.",
    "Measurement": "A process that determines, estimates, or records the value of a property under specified conditions.",
    "Property": "A characteristic, attribute, or measurable feature of an entity, material, process, or system.",
    "Normalization Basis": "The basis with respect to which a quantitative result or property is normalized.",
    "hasParameter": "An object property that relates a process, measurement, or resource to a parameter used to characterize its conditions or settings.",
    "hasProperty": "An object property that relates a resource to a property that it bears, reports, or is described in terms of.",
    "usesInstrument": "An object property that relates a process or measurement to an instrument used in carrying it out.",
    "hasInputMaterial": "An object property that relates a process to a material that serves as an input to that process.",
    "hasOutputMaterial": "An object property that relates a process to a material produced by that process.",
    "hasOutputData": "An object property that relates a process or measurement to data generated as its output.",
    "hasInputData": "An object property that relates a process, analysis, or transformation to data used as its input.",
    "measures": "An object property that relates a measurement to the property it determines or quantifies.",
    "ofProperty": "An object property that relates a result, value, or derived statement to the property that it is about.",
    "fromMeasurement": "An object property that relates data, a result, or a derived statement to the measurement from which it originates.",
    "isPartOf": "An object property that relates an entity to a larger entity of which it is a constituent part.",
    "hasIdentifier": "A datatype property that relates a resource to a literal identifier used to denote or reference it.",
    "hasSubProcess": "An object property that relates a process to a subprocess that forms part of its execution.",
    "atCurrentDensity": "An object property that relates an observation, result, or condition to the current-density setting at which it applies.",
    "hasPart": "An object property that relates a composite entity to one of its constituent parts.",
    "hasQuantityValue": "An object property that relates a parameter, property, or data point to a quantity-value node that carries its numeric value and unit.",
    "referenceElectrode": "An object property that relates an electrochemical setup or measurement to the reference electrode used in that context.",
    "isSubProcessOf": "An object property that relates a subprocess to the larger process of which it forms a part.",
    "normalizedTo": "An object property that relates a quantitative result or property to the basis against which it is normalized.",
}

SCHEMA_COMMENTS: dict[str, str] = {
    "Agent": "Core H2KG class for responsible actors and provenance-bearing entities.",
    "Instrument": "Core H2KG class for experimental and processing apparatus.",
    "Parameter": "Core H2KG class for reusable condition and setting concepts.",
    "Unit": "Core H2KG class for measurement units used with quantity values.",
    "Process": "Core H2KG class for activities and operations in the experimental workflow.",
    "Manufacturing": "Core H2KG class for fabrication, preparation, and assembly processes.",
    "Data": "Core H2KG class for recorded informational outputs and data artefacts.",
    "Data Point": "Core H2KG class for individual recorded observations or values.",
    "Matter": "Core H2KG class for material entities and physical artefacts.",
    "Metadata": "Core H2KG class for descriptive information about resources and activities.",
    "Measurement": "Core H2KG class for value-determining experimental activities.",
    "Property": "Core H2KG class for characteristics that can be observed, measured, or reported.",
    "Normalization Basis": "Core H2KG class for normalization reference concepts such as area, mass, or active surface area.",
}


def enrich_ontology(
    input_path: str | Path,
    output_dir: str | Path,
    config_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    input_path = Path(input_path)
    output_dir = ensure_dir(Path(output_dir))
    config_root = Path(config_dir or input_path.parent.parent / "config")
    metadata_defaults = try_load_yaml(config_root / "metadata_defaults.yaml", default_metadata_defaults())
    profile = try_load_yaml(config_root / "release_profile.yaml", default_release_profile())
    ontology_iri = profile["project"]["ontology_iri"]
    namespace_uri = profile["project"]["namespace_uri"]
    merged = merge_document_items(load_json_document(input_path))
    classifications = {entry.iri: entry for entry in classify_resources(input_path, output_dir.parent / "review", config_root)}
    enriched: list[dict[str, Any]] = []
    for item in merged:
        identifier = item.get("@id")
        if not isinstance(identifier, str):
            continue
        updated = dict(item)
        kind = classifications.get(identifier)
        if identifier == ontology_iri or (kind and kind.kind == "ontology_header"):
            updated.setdefault("@type", [OWL_ONTOLOGY])
            updated = _enrich_ontology_header(updated, profile, metadata_defaults)
        elif identifier.startswith(namespace_uri) and kind and kind.kind in {"class", "object_property", "datatype_property"}:
            updated = _enrich_local_schema_term(updated, ontology_iri, kind.kind)
        enriched.append(updated)
    schema_items = [
        item
        for item in enriched
        if item.get("@id") == ontology_iri
        or (
            classifications.get(str(item.get("@id")))
            and classifications[str(item.get("@id"))].is_local
            and classifications[str(item.get("@id"))].kind in {"class", "object_property", "datatype_property"}
        )
    ]
    dump_turtle_items(output_dir / "schema.ttl", schema_items)
    dump_jsonld_items(output_dir / "schema.jsonld", schema_items)
    write_text(output_dir.parent / "reports" / "metadata_report.md", _metadata_report(schema_items))
    return enriched


def _enrich_ontology_header(item: dict[str, Any], profile: dict[str, Any], metadata_defaults: dict[str, Any]) -> dict[str, Any]:
    ontology = metadata_defaults["ontology"]
    project = profile["project"]
    item.setdefault("http://purl.org/dc/terms/title", [{"@value": ontology["title"], "@language": ontology["language"]}])
    item.setdefault("http://purl.org/dc/terms/description", [{"@value": ontology["description"], "@language": ontology["language"]}])
    item.setdefault("http://purl.org/dc/terms/abstract", [{"@value": ontology["abstract"], "@language": ontology["language"]}])
    item.setdefault("http://purl.org/dc/terms/creator", [{"@value": name, "@language": "en"} for name in ontology["creators"]])
    item.setdefault("http://purl.org/dc/terms/contributor", [{"@value": name, "@language": "en"} for name in ontology["contributors"]])
    item.setdefault("http://purl.org/dc/terms/created", [{"@value": ontology["created"]}])
    item["http://purl.org/dc/terms/modified"] = [{"@value": ontology["modified"]}]
    item.setdefault("http://purl.org/dc/terms/license", [{"@id": project["license"]}])
    item["http://www.w3.org/2002/07/owl#versionIRI"] = [{"@id": project["version_iri"]}]
    item["http://www.w3.org/2002/07/owl#versionInfo"] = [{"@value": project["version"], "@language": "en"}]
    item["http://www.w3.org/2002/07/owl#priorVersion"] = [{"@id": project["prior_version"]}]
    item["http://purl.org/vocab/vann/preferredNamespacePrefix"] = [{"@value": project["namespace_prefix"]}]
    item["http://purl.org/vocab/vann/preferredNamespaceUri"] = [{"@id": project["namespace_uri"]}]
    item[RDFS_COMMENT] = [{"@value": ontology["description"], "@language": ontology["language"]}]
    return item


def _enrich_local_schema_term(item: dict[str, Any], ontology_iri: str, kind: str) -> dict[str, Any]:
    label = best_label(item) or humanize(local_name(str(item.get("@id"))))
    description = best_description(item)
    if not item.get(RDFS_LABEL):
        item[RDFS_LABEL] = [{"@value": label, "@language": "en"}]
    if not item.get(SKOS_DEFINITION):
        item[SKOS_DEFINITION] = [{"@value": _definition_for(label, kind), "@language": "en"}]
    if not item.get(RDFS_COMMENT):
        item[RDFS_COMMENT] = [{"@value": _comment_for(label, kind), "@language": "en"}]
    item[RDFS_IS_DEFINED_BY] = [{"@id": ontology_iri}]
    return item


def _definition_for(label: str, kind: str) -> str:
    if label in SCHEMA_DEFINITIONS:
        return SCHEMA_DEFINITIONS[label]
    if kind == "class":
        return f"Class representing {label.lower()} in the H2KG PEMFC catalyst-layer application ontology."
    if kind == "object_property":
        return f"Object property used to relate two resources within the H2KG PEMFC catalyst-layer application ontology."
    return f"Datatype property used to attach literal metadata or values related to {label.lower()}."


def _comment_for(label: str, kind: str) -> str:
    if label in SCHEMA_COMMENTS:
        return SCHEMA_COMMENTS[label]
    if kind == "object_property":
        return f"Core H2KG relation for {label.lower()}."
    if kind == "datatype_property":
        return f"Core H2KG datatype relation for {label.lower()}."
    if kind == "class":
        return f"Core H2KG class for {label.lower()}."
    return f"Core H2KG schema term for {label.lower()}."


def _metadata_report(schema_items: list[dict[str, Any]]) -> str:
    annotated = sum(1 for item in schema_items if item.get(SKOS_DEFINITION))
    return f"""# Metadata Enrichment Report

- Enriched schema resources: {len(schema_items)}
- Resources with definitions after enrichment: {annotated}
- Ontology header metadata normalized: yes
- Stable namespace metadata added: yes
"""
