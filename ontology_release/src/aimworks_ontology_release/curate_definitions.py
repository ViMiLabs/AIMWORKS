from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .io import iter_document_items, load_json_document, merge_document_items
from .normalize import best_label
from .utils import deep_get, default_release_profile, ensure_dir, local_name, try_load_yaml

DCTERMS_DESCRIPTION = "http://purl.org/dc/terms/description"
RDFS_COMMENT = "http://www.w3.org/2000/01/rdf-schema#comment"
RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"
SKOS_DEFINITION = "http://www.w3.org/2004/02/skos/core#definition"
SKOS_PREF_LABEL = "http://www.w3.org/2004/02/skos/core#prefLabel"
OWL_CLASS = "http://www.w3.org/2002/07/owl#Class"
OWL_OBJECT_PROPERTY = "http://www.w3.org/2002/07/owl#ObjectProperty"
OWL_DATATYPE_PROPERTY = "http://www.w3.org/2002/07/owl#DatatypeProperty"

LOCAL_RELATIONS = {
    "hasParameter": "https://w3id.org/h2kg/hydrogen-ontology#hasParameter",
    "measures": "https://w3id.org/h2kg/hydrogen-ontology#measures",
    "usesInstrument": "https://w3id.org/h2kg/hydrogen-ontology#usesInstrument",
    "hasInputMaterial": "https://w3id.org/h2kg/hydrogen-ontology#hasInputMaterial",
    "hasOutputMaterial": "https://w3id.org/h2kg/hydrogen-ontology#hasOutputMaterial",
    "hasInputData": "https://w3id.org/h2kg/hydrogen-ontology#hasInputData",
    "hasOutputData": "https://w3id.org/h2kg/hydrogen-ontology#hasOutputData",
    "hasQuantityValue": "https://w3id.org/h2kg/hydrogen-ontology#hasQuantityValue",
    "normalizedTo": "https://w3id.org/h2kg/hydrogen-ontology#normalizedTo",
    "ofProperty": "https://w3id.org/h2kg/hydrogen-ontology#ofProperty",
}

WEAK_DESCRIPTION_TOKENS = (
    "proposed new",
    "used in this paper",
    "in this paper",
    "reported as",
    "reported in",
    "reported by",
    "not present in ontology",
    "not found as",
    "numeric values not extracted",
    "used for fitting",
    "catch-all",
    "comparison model",
    "baseline ",
    "as referenced/compared in the paper",
    "label:",
    "description:",
    "ontology_iri:",
    "proposed:",
    "desc:",
    "desc=",
)

MANUAL_DESCRIPTION_OVERRIDES = {
    "https://w3id.org/h2kg/hydrogen-ontology#Agent": (
        "A class representing an agent that is responsible for carrying out a process, producing data, "
        "or contributing to the provenance of a resource in H2KG."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#Instrument": (
        "A class representing an instrument used to perform, support, or control a measurement or "
        "manufacturing process in H2KG."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#Parameter": (
        "A class representing a parameter specified as an input, setting, or condition for a process "
        "or measurement in H2KG."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#Unit": (
        "A class representing a unit used to express the value of a quantity in H2KG."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#Process": (
        "A class representing a process that transforms material, produces data, or changes the state "
        "of a system in H2KG."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#Manufacturing": (
        "A class representing a manufacturing process that prepares, assembles, coats, or otherwise "
        "fabricates a material or device in H2KG."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#Data": (
        "A class representing data produced, used, or referenced by a process or measurement in H2KG."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#DataPoint": (
        "A class representing a single data point that links a value to the property and measurement "
        "context it belongs to in H2KG."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#Matter": (
        "A class representing a material entity that participates in a process, measurement, or device "
        "configuration in H2KG."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#Metadata": (
        "A class representing metadata used to describe the provenance, identity, structure, or context "
        "of another resource in H2KG."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#Measurement": (
        "A class representing a measurement process that determines one or more properties of a material, "
        "device, or system in H2KG."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#Property": (
        "A class representing a property that can be measured, computed, or otherwise assigned to a material, "
        "process, or system in H2KG."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#hasParameter": (
        "An object property relating a process or measurement to a parameter that specifies one of its "
        "inputs, settings, or operating conditions."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#hasProperty": (
        "An object property relating a measurement to a property that is determined, reported, or otherwise "
        "associated with that measurement."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#usesInstrument": (
        "An object property relating a process or measurement to an instrument used to carry it out or support it."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#hasInputMaterial": (
        "An object property relating a process or measurement to a material entity that serves as an input."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#hasOutputMaterial": (
        "An object property relating a process to a material entity produced as an output."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#hasOutputData": (
        "An object property relating a measurement or process to data generated as an output."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#hasInputData": (
        "An object property relating a process or measurement to data used as an input."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#measures": (
        "An object property relating a measurement to a property that it determines."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#ofProperty": (
        "An object property relating a data point to the property represented by that data point."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#fromMeasurement": (
        "An object property relating a data point to the measurement from which it was generated."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#isPartOf": (
        "An object property relating an entity or process to a larger entity or process of which it forms a part."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#hasSubProcess": (
        "An object property relating a process to a subprocess that forms part of its overall execution."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#atCurrentDensity": (
        "An object property relating a data point to the current-density value at which it is reported."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#hasPart": (
        "An object property relating an entity or process to a constituent part."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#hasQuantityValue": (
        "An object property relating a parameter, property, or data point to the quantity value that expresses it."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#referenceElectrode": (
        "An object property relating an electrochemical measurement setup or process to the reference electrode it uses."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#isSubProcessOf": (
        "An object property relating a subprocess to the larger process of which it forms a part."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#normalizedTo": (
        "An object property relating a property or result to the basis used for its normalization."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#hasIdentifier": (
        "A datatype property relating a resource to a literal identifier used to distinguish or reference it."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#MEAPolarization": (
        "A measurement process that records membrane electrode assembly polarization behavior to determine "
        "current density, power density, mass activity, and related electrochemical performance properties under "
        "controlled operating conditions."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#ECSAByDoubleLayerCapacitance": (
        "A measurement process that determines electrochemically active surface area from double-layer "
        "capacitance measurements using an electrochemical workstation and generating an experiment dataset."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#RRDEAssembly": (
        "An instrument corresponding to a rotating ring-disk electrode assembly and used in rotating ring-disk "
        "voltammetry and related electrochemical measurements."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#RDERotator": (
        "An instrument corresponding to a rotating disk electrode rotator and used in linear sweep voltammetry "
        "and related rotating-electrode measurements."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#MEAAssembly": (
        "A material entity corresponding to a membrane electrode assembly and used as an input in "
        "electrochemical impedance spectroscopy, fuel-cell polarization measurement, and related electrochemical testing."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#MEAAssemblyProcess": (
        "A manufacturing process that assembles membrane electrode assembly components into an MEA using a "
        "protonated membrane, anode gas diffusion electrode, cathode gas diffusion electrode, torque wrench, and hot press."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#DynamicHydrogenElectrode": (
        "An instrument corresponding to a dynamic hydrogen electrode and used as a reference electrode in "
        "electrochemical measurements."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#SHE": (
        "An instrument corresponding to a standard hydrogen electrode and used as a reference electrode in "
        "electrochemical measurements."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#SCE": (
        "An instrument corresponding to a saturated calomel electrode and used as a reference electrode in "
        "electrochemical measurements."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#AgAgCl": (
        "An instrument corresponding to a silver/silver chloride reference electrode and used as a reference "
        "electrode in electrochemical measurements."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#FiberOpticOxygenProbe": (
        "An instrument corresponding to a fiber-optic oxygen probe and used in in-plane effective diffusivity measurement."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#HighVoltagePowerSupply": (
        "An instrument corresponding to a high-voltage power supply and used in electrospray deposition and "
        "microelectrode water electrolyzer polarization measurement."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#RamanSpectrometer": (
        "An instrument corresponding to a Raman spectrometer and used in Raman spectroscopy measurement."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#XYMovingStage": (
        "An instrument corresponding to an XY moving stage and used in electrospray deposition, direct ink writing, "
        "and apparatus specification measurement."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#pHMeter": (
        "An instrument corresponding to a pH meter and used in surface basicity measurement."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#ChronopotentiometryMeasurement": (
        "A measurement process that applies constant current to determine cell voltage and cell-voltage increase rate over time."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#InPlaneEffectiveDiffusivityMeasurement": (
        "A measurement process that determines the in-plane effective oxygen diffusion coefficient from radial oxygen-transport "
        "measurements using a fiber-optic oxygen probe and generating oxygen concentration time-series data."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#PycnometryMeasurement": (
        "A measurement process that determines true density using a helium pycnometer."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#RamanSpectroscopyMeasurement": (
        "A measurement process that uses Raman spectroscopy to determine Raman band positions and intensity ratios "
        "using a Raman spectrometer."
    ),
    "https://w3id.org/h2kg/hydrogen-ontology#SurfaceBasicityMeasurement": (
        "A measurement process that determines changes in surface basicity from pH measurements after contact between "
        "a material and solution."
    ),
}


def curate_source_definitions(
    input_path: str | Path,
    output_dir: str | Path,
    config_dir: str | Path | None = None,
    write_in_place: bool = True,
) -> dict[str, Any]:
    input_path = Path(input_path)
    output_dir = ensure_dir(Path(output_dir))
    profile = try_load_yaml(
        Path(config_dir or input_path.parent.parent / "config") / "release_profile.yaml",
        default_release_profile(),
    )
    namespace_uri = deep_get(profile, "project", "namespace_uri", default="https://w3id.org/h2kg/hydrogen-ontology#")
    local_priority = list(
        deep_get(
            profile,
            "separation",
            "local_schema_priority",
            default=["Process", "Manufacturing", "Measurement", "Instrument", "Matter", "Parameter", "Property", "Data"],
        )
    )

    document = load_json_document(input_path)
    original_items = iter_document_items(document)
    merged_items = merge_document_items(document)
    merged_by_iri = {item["@id"]: item for item in merged_items if isinstance(item.get("@id"), str)}
    reverse_index = _build_reverse_index(merged_items)

    updates: dict[str, dict[str, Any]] = {}
    for iri, item in merged_by_iri.items():
        if not iri.startswith(namespace_uri):
            continue
        semantic_type = _semantic_type(item, namespace_uri, local_priority)
        if not semantic_type:
            continue
        current_description = _current_description(item)
        manual_override = MANUAL_DESCRIPTION_OVERRIDES.get(iri, "")
        reason = _description_status(current_description)
        if manual_override and current_description != manual_override:
            reason = "manual_override"
        if reason == "keep":
            reason = _consistency_reason(semantic_type, current_description)
        if reason == "keep":
            continue
        generated = _generate_description(item, semantic_type, current_description, merged_by_iri, reverse_index)
        if not generated:
            continue
        updates[iri] = {
            "label": best_label(item),
            "semantic_type": semantic_type,
            "old_description": current_description,
            "new_description": generated,
            "reason": reason,
        }

    changed = 0
    for item in original_items:
        iri = item.get("@id")
        if not isinstance(iri, str) or iri not in updates:
            continue
        item[DCTERMS_DESCRIPTION] = [{"@value": updates[iri]["new_description"], "@language": "en"}]
        changed += 1

    target_path = input_path if write_in_place else output_dir / input_path.name
    serialized = _updated_document(document, original_items)
    target_path.write_text(json.dumps(serialized, indent=2, ensure_ascii=False), encoding="utf-8")

    report = {
        "updated_count": len(updates),
        "written_item_count": changed,
        "target_path": str(target_path),
        "updates": [
            {
                "iri": iri,
                **payload,
            }
            for iri, payload in sorted(updates.items(), key=lambda item: (item[1]["semantic_type"], item[1]["label"]))
        ],
    }
    (output_dir / "definition_curation_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return report


def _build_reverse_index(items: list[dict[str, Any]]) -> dict[str, dict[str, list[str]]]:
    reverse: dict[str, dict[str, list[str]]] = {}
    tracked_predicates = set(LOCAL_RELATIONS.values())
    for item in items:
        source = item.get("@id")
        if not isinstance(source, str):
            continue
        for predicate in tracked_predicates:
            raw_values = item.get(predicate, [])
            values = raw_values if isinstance(raw_values, list) else [raw_values]
            for value in values:
                if not isinstance(value, dict) or "@id" not in value:
                    continue
                target = str(value["@id"])
                reverse.setdefault(target, {}).setdefault(predicate, []).append(source)
    return reverse


def _semantic_type(item: dict[str, Any], namespace_uri: str, local_priority: list[str]) -> str:
    types = item.get("@type", [])
    type_values = types if isinstance(types, list) else [types]
    local_types = {
        local_name(type_value)
        for type_value in type_values
        if isinstance(type_value, str) and type_value.startswith(namespace_uri)
    }
    for candidate in local_priority:
        if candidate in local_types:
            return candidate
    if OWL_OBJECT_PROPERTY in type_values:
        return "ObjectProperty"
    if OWL_DATATYPE_PROPERTY in type_values:
        return "DatatypeProperty"
    if OWL_CLASS in type_values:
        return "Class"
    return ""


def _current_description(item: dict[str, Any]) -> str:
    for key in [DCTERMS_DESCRIPTION, SKOS_DEFINITION, RDFS_COMMENT]:
        values = item.get(key, [])
        value_list = values if isinstance(values, list) else [values]
        for value in value_list:
            if isinstance(value, dict) and "@value" in value and str(value["@value"]).strip():
                return str(value["@value"]).strip()
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _description_status(text: str) -> str:
    if not text:
        return "missing"
    lower = text.lower()
    if any(token in lower for token in WEAK_DESCRIPTION_TOKENS):
        return "weak"
    if any(
        lower.startswith(prefix)
        for prefix in (
            "a parameter specifying ",
            "a property denoting ",
            "a measurement process that ",
            "an instrument corresponding to ",
            "a manufacturing process ",
            "a material entity corresponding to ",
            "a dataset containing ",
            "a data resource used to represent ",
            "a normalization basis corresponding to ",
            "metadata describing ",
        )
    ):
        return "keep"
    if len(text) < 35:
        return "weak"
    if lower.startswith("a instrument "):
        return "weak"
    if "instrument used for " in lower:
        return "weak"
    if " process for " in lower and " for determining " in lower:
        return "weak"
    if any(
        phrase in lower
        for phrase in (
            "measurement process corresponding to",
            "manufacturing process corresponding to",
            "data resource corresponding to",
        )
    ):
        return "weak"
    return "keep"


def _consistency_reason(semantic_type: str, text: str) -> str:
    if semantic_type == "Parameter" and text and not text.startswith("A parameter specifying "):
        return "normalize"
    if semantic_type == "Property" and text and not text.startswith("A property denoting "):
        return "normalize"
    return "keep"


def _generate_description(
    item: dict[str, Any],
    semantic_type: str,
    current_description: str,
    merged_by_iri: dict[str, dict[str, Any]],
    reverse_index: dict[str, dict[str, list[str]]],
) -> str:
    manual_override = MANUAL_DESCRIPTION_OVERRIDES.get(str(item.get("@id", "")))
    if manual_override:
        return manual_override
    label = best_label(item)
    phrase = _label_phrase(label)
    topic = _topic_phrase(label)
    if semantic_type == "Parameter":
        return _parameter_description(item, phrase, current_description, merged_by_iri, reverse_index)
    if semantic_type == "Property":
        return _property_description(item, phrase, current_description, merged_by_iri, reverse_index)
    if semantic_type == "Measurement":
        return _measurement_description(item, topic, merged_by_iri)
    if semantic_type == "Instrument":
        return _instrument_description(item, label, topic, reverse_index, merged_by_iri)
    if semantic_type == "Manufacturing":
        return _manufacturing_description(item, topic, merged_by_iri)
    if semantic_type == "Matter":
        return _matter_description(item, label, topic, reverse_index, merged_by_iri)
    if semantic_type == "Data":
        return _data_description(item, label, topic, reverse_index, merged_by_iri)
    if semantic_type == "NormalizationBasis":
        return f"A normalization basis corresponding to {phrase} and used as the reference basis for reporting quantitative results or properties."
    if semantic_type == "Metadata":
        return f"Metadata describing {phrase} and used to provide provenance, identity, or contextual information for another resource."
    return ""


def _parameter_description(
    item: dict[str, Any],
    phrase: str,
    current_description: str,
    merged_by_iri: dict[str, dict[str, Any]],
    reverse_index: dict[str, dict[str, list[str]]],
) -> str:
    normalized = _normalize_role_description(current_description, "A parameter specifying ")
    if normalized:
        return normalized
    contexts = _reverse_labels(item["@id"], LOCAL_RELATIONS["hasParameter"], reverse_index, merged_by_iri)
    context_text = ""
    if contexts:
        context_text = f" used to characterize { _format_list(contexts) }"
    return f"A parameter specifying {phrase}{context_text}."


def _property_description(
    item: dict[str, Any],
    phrase: str,
    current_description: str,
    merged_by_iri: dict[str, dict[str, Any]],
    reverse_index: dict[str, dict[str, list[str]]],
) -> str:
    normalized = _normalize_role_description(current_description, "A property denoting ")
    if normalized:
        return normalized
    bases = _object_labels(item, LOCAL_RELATIONS["normalizedTo"], merged_by_iri)
    measurements = _reverse_labels(item["@id"], LOCAL_RELATIONS["measures"], reverse_index, merged_by_iri)
    basis_text = f" normalized to { _format_list(bases) }" if bases else ""
    measurement_text = f" and determined in { _format_list(measurements) }" if measurements else ""
    return f"A property denoting {phrase}{basis_text}{measurement_text}."


def _measurement_description(item: dict[str, Any], topic: str, merged_by_iri: dict[str, dict[str, Any]]) -> str:
    properties = _object_labels(item, LOCAL_RELATIONS["measures"], merged_by_iri)
    instruments = _object_labels(item, LOCAL_RELATIONS["usesInstrument"], merged_by_iri)
    outputs = _object_labels(item, LOCAL_RELATIONS["hasOutputData"], merged_by_iri)
    property_text = f" to determine { _format_list(properties) }" if properties else ""
    instrument_text = f" using { _format_list(instruments) }" if instruments else ""
    output_text = f" and generating { _format_list(outputs) }" if outputs else ""
    return f"A measurement process that uses {topic}{property_text}{instrument_text}{output_text}."


def _instrument_description(
    item: dict[str, Any],
    label: str,
    topic: str,
    reverse_index: dict[str, dict[str, list[str]]],
    merged_by_iri: dict[str, dict[str, Any]],
) -> str:
    contexts = _reverse_labels(item["@id"], LOCAL_RELATIONS["usesInstrument"], reverse_index, merged_by_iri)
    topic_with_article = _with_article(topic)
    if contexts:
        return f"An instrument corresponding to {topic_with_article} and used in { _format_list(contexts) }."
    return f"An instrument corresponding to {topic_with_article}."


def _manufacturing_description(item: dict[str, Any], topic: str, merged_by_iri: dict[str, dict[str, Any]]) -> str:
    inputs = _object_labels(item, LOCAL_RELATIONS["hasInputMaterial"], merged_by_iri)
    outputs = _object_labels(item, LOCAL_RELATIONS["hasOutputMaterial"], merged_by_iri)
    instruments = _object_labels(item, LOCAL_RELATIONS["usesInstrument"], merged_by_iri)
    input_text = f" using { _format_list(inputs) }" if inputs else ""
    instrument_text = f" with { _format_list(instruments) }" if instruments else ""
    output_text = f" and producing { _format_list(outputs) }" if outputs else ""
    return f"A manufacturing process for {topic}{input_text}{instrument_text}{output_text}."


def _matter_description(
    item: dict[str, Any],
    label: str,
    topic: str,
    reverse_index: dict[str, dict[str, list[str]]],
    merged_by_iri: dict[str, dict[str, Any]],
) -> str:
    inputs = _reverse_labels(item["@id"], LOCAL_RELATIONS["hasInputMaterial"], reverse_index, merged_by_iri)
    outputs = _reverse_labels(item["@id"], LOCAL_RELATIONS["hasOutputMaterial"], reverse_index, merged_by_iri)
    topic_with_article = _with_article(topic)
    if inputs:
        return f"A material entity corresponding to {topic_with_article} and used as an input in { _format_list(inputs) }."
    if outputs:
        return f"A material entity corresponding to {topic_with_article} and produced in { _format_list(outputs) }."
    return f"A material entity corresponding to {topic_with_article}."


def _data_description(
    item: dict[str, Any],
    label: str,
    topic: str,
    reverse_index: dict[str, dict[str, list[str]]],
    merged_by_iri: dict[str, dict[str, Any]],
) -> str:
    sources = _reverse_labels(item["@id"], LOCAL_RELATIONS["hasOutputData"], reverse_index, merged_by_iri)
    if label.endswith("Dataset"):
        dataset_topic = _topic_phrase(label[: -len("Dataset")].strip() or label)
        source_text = f" generated by { _format_list(sources) }" if sources else ""
        return f"A dataset containing data on {dataset_topic}{source_text}."
    source_text = f" generated by { _format_list(sources) }" if sources else ""
    return f"A data resource used to represent {topic}{source_text}."


def _object_labels(item: dict[str, Any], predicate: str, merged_by_iri: dict[str, dict[str, Any]]) -> list[str]:
    raw_values = item.get(predicate, [])
    values = raw_values if isinstance(raw_values, list) else [raw_values]
    labels: list[str] = []
    for value in values:
        if not isinstance(value, dict) or "@id" not in value:
            continue
        target = merged_by_iri.get(str(value["@id"]))
        if not target:
            continue
        label = best_label(target)
        if label not in labels:
            labels.append(label)
    return labels[:3]


def _reverse_labels(
    iri: str,
    predicate: str,
    reverse_index: dict[str, dict[str, list[str]]],
    merged_by_iri: dict[str, dict[str, Any]],
) -> list[str]:
    labels: list[str] = []
    for source in reverse_index.get(iri, {}).get(predicate, []):
        item = merged_by_iri.get(source)
        if not item:
            continue
        label = best_label(item)
        if label not in labels:
            labels.append(label)
    return labels[:3]


def _format_list(values: list[str]) -> str:
    cleaned = [value for value in values if value]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return f"{', '.join(cleaned[:-1])}, and {cleaned[-1]}"


def _label_phrase(label: str) -> str:
    phrase = _noun_phrase(label)
    return phrase or "the corresponding concept"


def _topic_phrase(label: str) -> str:
    phrase = _noun_phrase(_humanize_identifier_like(label))
    return phrase or "the corresponding concept"


def _noun_phrase(label: str) -> str:
    words = label.strip().split()
    if not words:
        return ""
    normalized: list[str] = []
    for word in words:
        if _preserve_token(word):
            normalized.append(word)
        else:
            normalized.append(word.lower())
    return " ".join(normalized)


def _preserve_token(word: str) -> bool:
    if not word:
        return False
    letters = [ch for ch in word if ch.isalpha()]
    if letters and all(ch.isupper() for ch in letters):
        return True
    if any(ch.isdigit() for ch in word):
        return True
    if any(ch in "/+-–" for ch in word):
        return True
    return False


def _humanize_identifier_like(label: str) -> str:
    compact = label.replace("_", " ").strip()
    if " " in compact:
        return compact
    if any(sep in compact for sep in ["/", "-", "–"]):
        return compact
    text = compact
    for token in ["MEA", "RRDE", "ECSA", "HFR", "XRD", "XPS", "SEM", "TEM", "AFM", "DLS", "NMR", "FTIR", "DRT"]:
        text = text.replace(token, token + " ")
    text = text.replace("By", " by ")
    pieces: list[str] = []
    for idx, ch in enumerate(text):
        if idx > 0:
            prev = text[idx - 1]
            next_ch = text[idx + 1] if idx + 1 < len(text) else ""
            if ch.isupper() and (prev.islower() or prev.isdigit()):
                pieces.append(" ")
            elif ch.isdigit() and prev.isalpha():
                pieces.append(" ")
            elif ch.isupper() and prev.isupper() and next_ch.islower():
                pieces.append(" ")
        pieces.append(ch)
    return " ".join("".join(pieces).split())


def _with_article(phrase: str) -> str:
    normalized = phrase.strip()
    if not normalized:
        return "the corresponding concept"
    if normalized.isupper() or "/" in normalized:
        return normalized
    first = normalized[0].lower()
    article = "an" if first in {"a", "e", "i", "o", "u"} else "a"
    return f"{article} {normalized}"


def _normalize_role_description(text: str, opener: str) -> str:
    normalized = " ".join(text.split()).strip()
    if not normalized:
        return ""
    lower = normalized.lower()
    canonical_prefix = ""
    if lower.startswith("a parameter specifying "):
        canonical_prefix = "A parameter specifying "
    elif lower.startswith("a property denoting "):
        canonical_prefix = "A property denoting "
    if canonical_prefix:
        body = normalized[len(canonical_prefix) :]
        body = re.sub(r"^(desc|proposed)\s*:\s*", "", body, flags=re.IGNORECASE)
        return _ensure_sentence(f"{canonical_prefix}{body.rstrip('.')}")
    normalized = re.sub(r"^(a|an|the)\s+", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"^(desc|proposed)\s*:\s*", "", normalized, flags=re.IGNORECASE)
    normalized = normalized.rstrip(".")
    if normalized and len(normalized) > 1 and normalized[0].isupper() and normalized[1].islower():
        normalized = normalized[0].lower() + normalized[1:]
    return _ensure_sentence(f"{opener}{normalized}")


def _ensure_sentence(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    return stripped if stripped.endswith(".") else f"{stripped}."


def _updated_document(document: Any, original_items: list[dict[str, Any]]) -> Any:
    if isinstance(document, list):
        return original_items
    if isinstance(document, dict) and isinstance(document.get("@graph"), list):
        updated = dict(document)
        updated["@graph"] = original_items
        return updated
    if isinstance(document, dict) and original_items:
        return original_items[0]
    return document
