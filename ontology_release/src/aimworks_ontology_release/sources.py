from __future__ import annotations

import importlib.util
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import requests
from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS

from .io import guess_rdf_format
from .normalize import humanize_identifier
from .utils import ensure_dir, local_name, make_literal


@dataclass
class SourceRecord:
    iri: str
    label: str
    source_id: str
    source_title: str
    record_type: str
    priority: float
    synonyms: list[str]
    definition: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


BUILTIN_SOURCES: dict[str, list[dict[str, Any]]] = {
    "emmo_core": [
        {"iri": "https://w3id.org/emmo#EMMO_2480b72b_db8d_460f_9a5f_c2912f979046", "label": "Agent", "type": "class", "synonyms": ["actor", "performer"], "definition": "EMMO class for an agent."},
        {"iri": "https://w3id.org/emmo#EMMO_5c68497d_2544_4cd4_897b_1ea783c9f6fe", "label": "Tool", "type": "class", "synonyms": ["instrument", "device", "apparatus"], "definition": "EMMO class for a tool."},
        {"iri": "https://w3id.org/emmo#EMMO_194e367c_9783_4bf5_96d0_9ad597d48d9a", "label": "DataSet", "type": "class", "synonyms": ["data", "dataset"], "definition": "EMMO class for a dataset."},
        {"iri": "https://w3id.org/emmo#EMMO_472a0ca2_58bf_4618_b561_6fe68bd9fd49", "label": "Procedure", "type": "class", "synonyms": ["process", "workflow"], "definition": "EMMO class for a procedure."},
        {"iri": "https://w3id.org/emmo#EMMO_ae2d1a96_bfa1_409a_a7d2_03d69e8a125a", "label": "hasParticipant", "type": "object_property", "synonyms": ["has input", "has participant"], "definition": "Relates a process to a participant."},
        {"iri": "https://w3id.org/emmo#EMMO_cd24eb82_a11c_4a31_96ea_32f870c5580a", "label": "hasAgent", "type": "object_property", "synonyms": ["uses agent"], "definition": "Relates an occurrence to an agent."},
        {"iri": "https://w3id.org/emmo#EMMO_a592c856_4103_43cf_8635_1982a1e5d5de", "label": "hasResourceIdentifier", "type": "datatype_property", "synonyms": ["identifier", "has identifier"], "definition": "Associates a resource with an identifier."},
    ],
    "echo": [
        {"iri": "https://w3id.org/emmo/domain/electrochemistry#electrochemistry_f4ce4df2_d7e6_470f_8eab_3a911adaaf0f", "label": "ElectrochemicalMeasurementProcess", "type": "class", "synonyms": ["measurement", "electrochemical measurement"], "definition": "Electrochemical measurement process."},
        {"iri": "https://w3id.org/emmo/domain/electrochemistry#electrochemistry_ebdb68e9_c4b5_4d57_a042_c0f51d446755", "label": "ElectrochemicalMaterial", "type": "class", "synonyms": ["material", "matter"], "definition": "Material relevant to electrochemistry."},
        {"iri": "https://w3id.org/emmo/domain/electrochemistry#electrochemistry_2a40b878_7d09_49db_91b2_d0ee30192284", "label": "StandardHydrogenElectrode", "type": "controlled_vocabulary_term", "synonyms": ["reference electrode", "SHE"], "definition": "Standard hydrogen electrode."},
        {"iri": "https://w3id.org/emmo/domain/electrochemistry#electrochemistry_3f9b2956_1465_4fe0_b0df_5e4784dac3b6", "label": "ElectricPotentialMeasuringSystem", "type": "class", "synonyms": ["potentiostat", "instrument"], "definition": "Measuring system for electric potential."},
        {"iri": "https://w3id.org/emmo/domain/electrochemistry#electrochemistry_9d2f09fa_7d56_4f36_9d70_4978f0f86711", "label": "ElectrochemicalCell", "type": "class", "synonyms": ["cell"], "definition": "Electrochemical cell."},
    ],
    "qudt_schema": [
        {"iri": "http://qudt.org/schema/qudt/QuantityValue", "label": "QuantityValue", "type": "class", "synonyms": ["quantity value"], "definition": "QUDT quantity value class."},
        {"iri": "http://qudt.org/schema/qudt/unit", "label": "unit", "type": "object_property", "synonyms": ["has unit"], "definition": "Links a quantity value to a unit."},
        {"iri": "http://qudt.org/schema/qudt/quantityKind", "label": "quantityKind", "type": "object_property", "synonyms": ["has quantity kind"], "definition": "Links a quantity value to a quantity kind."},
        {"iri": "http://qudt.org/schema/qudt/numericValue", "label": "numericValue", "type": "datatype_property", "synonyms": ["value"], "definition": "Numeric value of a quantity."},
    ],
    "qudt_units": [
        {"iri": "http://qudt.org/vocab/unit/OHM", "label": "Ohm", "type": "controlled_vocabulary_term", "synonyms": ["ohm"], "definition": "Unit of electrical resistance."},
        {"iri": "http://qudt.org/vocab/unit/BAR", "label": "Bar", "type": "controlled_vocabulary_term", "synonyms": ["bar"], "definition": "Unit of pressure."},
        {"iri": "http://qudt.org/vocab/unit/HZ", "label": "Hertz", "type": "controlled_vocabulary_term", "synonyms": ["hz"], "definition": "Unit of frequency."},
        {"iri": "http://qudt.org/vocab/unit/V", "label": "Volt", "type": "controlled_vocabulary_term", "synonyms": ["v"], "definition": "Unit of electric potential."},
        {"iri": "http://qudt.org/vocab/unit/MilliV", "label": "Millivolt", "type": "controlled_vocabulary_term", "synonyms": ["mv"], "definition": "Unit of electric potential."},
        {"iri": "http://qudt.org/vocab/unit/W", "label": "Watt", "type": "controlled_vocabulary_term", "synonyms": ["w"], "definition": "Unit of power."},
        {"iri": "http://qudt.org/vocab/unit/PERCENT", "label": "Percent", "type": "controlled_vocabulary_term", "synonyms": ["%"], "definition": "Unitless ratio scaled by 100."},
        {"iri": "http://qudt.org/vocab/unit/UNITLESS", "label": "Unitless", "type": "controlled_vocabulary_term", "synonyms": ["dimensionless"], "definition": "Unitless quantity."},
        {"iri": "http://qudt.org/vocab/unit/MilliA-PER-CentiM2", "label": "Milliampere per Square Centimetre", "type": "controlled_vocabulary_term", "synonyms": ["mA/cm2", "current density"], "definition": "Current density unit."},
        {"iri": "http://qudt.org/vocab/unit/S-PER-M", "label": "Siemens per Metre", "type": "controlled_vocabulary_term", "synonyms": ["S/m"], "definition": "Conductivity unit."},
        {"iri": "http://qudt.org/vocab/unit/SEC", "label": "Second", "type": "controlled_vocabulary_term", "synonyms": ["s"], "definition": "Time unit."},
        {"iri": "http://qudt.org/vocab/unit/MIN", "label": "Minute", "type": "controlled_vocabulary_term", "synonyms": ["min"], "definition": "Time unit."},
        {"iri": "http://qudt.org/vocab/unit/HR", "label": "Hour", "type": "controlled_vocabulary_term", "synonyms": ["h", "hr"], "definition": "Time unit."},
    ],
    "qudt_quantitykinds": [
        {"iri": "http://qudt.org/vocab/quantitykind/ElectricCurrentDensity", "label": "Electric Current Density", "type": "controlled_vocabulary_term", "synonyms": ["current density"], "definition": "Electric current density quantity kind."},
        {"iri": "http://qudt.org/vocab/quantitykind/Resistance", "label": "Resistance", "type": "controlled_vocabulary_term", "synonyms": ["electrical resistance"], "definition": "Resistance quantity kind."},
        {"iri": "http://qudt.org/vocab/quantitykind/OxygenTransportResistance", "label": "Oxygen Transport Resistance", "type": "controlled_vocabulary_term", "synonyms": ["oxygen transport resistance"], "definition": "Oxygen transport resistance quantity kind."},
        {"iri": "http://qudt.org/vocab/quantitykind/Conductivity", "label": "Conductivity", "type": "controlled_vocabulary_term", "synonyms": ["electrical conductivity"], "definition": "Conductivity quantity kind."},
        {"iri": "http://qudt.org/vocab/quantitykind/DiffusionCoefficient", "label": "Diffusion Coefficient", "type": "controlled_vocabulary_term", "synonyms": ["diffusivity"], "definition": "Diffusion coefficient quantity kind."},
        {"iri": "http://qudt.org/vocab/quantitykind/Dimensionless", "label": "Dimensionless", "type": "controlled_vocabulary_term", "synonyms": ["unitless"], "definition": "Dimensionless quantity kind."},
        {"iri": "http://qudt.org/vocab/quantitykind/MassFraction", "label": "Mass Fraction", "type": "controlled_vocabulary_term", "synonyms": ["weight fraction"], "definition": "Mass fraction quantity kind."},
        {"iri": "http://qudt.org/vocab/quantitykind/Time", "label": "Time", "type": "controlled_vocabulary_term", "synonyms": ["duration"], "definition": "Time quantity kind."},
        {"iri": "http://qudt.org/vocab/quantitykind/Pressure", "label": "Pressure", "type": "controlled_vocabulary_term", "synonyms": ["pressure"], "definition": "Pressure quantity kind."},
        {"iri": "http://qudt.org/vocab/quantitykind/Frequency", "label": "Frequency", "type": "controlled_vocabulary_term", "synonyms": ["frequency"], "definition": "Frequency quantity kind."},
        {"iri": "http://qudt.org/vocab/quantitykind/ElectricPotential", "label": "Electric Potential", "type": "controlled_vocabulary_term", "synonyms": ["voltage", "potential"], "definition": "Electric potential quantity kind."},
        {"iri": "http://qudt.org/vocab/quantitykind/Porosity", "label": "Porosity", "type": "controlled_vocabulary_term", "synonyms": ["porosity"], "definition": "Porosity quantity kind."},
        {"iri": "http://qudt.org/vocab/quantitykind/Length", "label": "Length", "type": "controlled_vocabulary_term", "synonyms": ["thickness"], "definition": "Length quantity kind."},
    ],
    "chebi": [
        {"iri": "http://purl.obolibrary.org/obo/CHEBI_15377", "label": "water", "type": "controlled_vocabulary_term", "synonyms": ["H2O"], "definition": "Water."},
        {"iri": "http://purl.obolibrary.org/obo/CHEBI_15379", "label": "dioxygen", "type": "controlled_vocabulary_term", "synonyms": ["oxygen", "O2"], "definition": "Molecular oxygen."},
        {"iri": "http://purl.obolibrary.org/obo/CHEBI_18276", "label": "hydrogen", "type": "controlled_vocabulary_term", "synonyms": ["H2"], "definition": "Molecular hydrogen."},
        {"iri": "http://purl.obolibrary.org/obo/CHEBI_33363", "label": "platinum", "type": "controlled_vocabulary_term", "synonyms": ["Pt"], "definition": "Platinum."},
    ],
    "provo": [
        {"iri": "http://www.w3.org/ns/prov#Agent", "label": "Agent", "type": "class", "synonyms": ["agent"], "definition": "Something responsible for an activity."},
        {"iri": "http://www.w3.org/ns/prov#Entity", "label": "Entity", "type": "class", "synonyms": ["data", "thing"], "definition": "A physical, digital, conceptual, or other kind of thing."},
        {"iri": "http://www.w3.org/ns/prov#Activity", "label": "Activity", "type": "class", "synonyms": ["process", "measurement"], "definition": "Something that occurs over a period of time."},
        {"iri": "http://www.w3.org/ns/prov#used", "label": "used", "type": "object_property", "synonyms": ["uses", "has input"], "definition": "Usage relation."},
        {"iri": "http://www.w3.org/ns/prov#wasGeneratedBy", "label": "wasGeneratedBy", "type": "object_property", "synonyms": ["has output"], "definition": "Generation relation."},
        {"iri": "http://www.w3.org/ns/prov#wasAssociatedWith", "label": "wasAssociatedWith", "type": "object_property", "synonyms": ["associated with"], "definition": "Association relation."},
    ],
    "dcterms": [
        {"iri": "http://purl.org/dc/terms/title", "label": "title", "type": "annotation_property", "synonyms": ["name"], "definition": "A name given to the resource."},
        {"iri": "http://purl.org/dc/terms/description", "label": "description", "type": "annotation_property", "synonyms": ["comment"], "definition": "An account of the resource."},
        {"iri": "http://purl.org/dc/terms/creator", "label": "creator", "type": "annotation_property", "synonyms": ["author"], "definition": "An entity primarily responsible."},
        {"iri": "http://purl.org/dc/terms/contributor", "label": "contributor", "type": "annotation_property", "synonyms": ["contributor"], "definition": "An entity responsible for contributions."},
        {"iri": "http://purl.org/dc/terms/created", "label": "created", "type": "annotation_property", "synonyms": ["creation date"], "definition": "Date of creation."},
        {"iri": "http://purl.org/dc/terms/modified", "label": "modified", "type": "annotation_property", "synonyms": ["modified date"], "definition": "Date of modification."},
        {"iri": "http://purl.org/dc/terms/license", "label": "license", "type": "annotation_property", "synonyms": ["licence"], "definition": "License."},
        {"iri": "http://purl.org/dc/terms/source", "label": "source", "type": "annotation_property", "synonyms": ["derived from"], "definition": "Source resource."},
        {"iri": "http://purl.org/dc/terms/identifier", "label": "identifier", "type": "annotation_property", "synonyms": ["id"], "definition": "Identifier."},
    ],
    "vann": [
        {"iri": "http://purl.org/vocab/vann/preferredNamespacePrefix", "label": "preferredNamespacePrefix", "type": "annotation_property", "synonyms": ["namespace prefix"], "definition": "Preferred namespace prefix."},
        {"iri": "http://purl.org/vocab/vann/preferredNamespaceUri", "label": "preferredNamespaceUri", "type": "annotation_property", "synonyms": ["namespace uri"], "definition": "Preferred namespace URI."},
    ],
    "oeo": [
        {"iri": "http://openenergy-platform.org/ontology/oeo/OEO_00010039", "label": "catalyst", "type": "class", "synonyms": ["catalyst"], "definition": "Catalyst concept in OEO."},
    ],
}


def _to_source_records(source_id: str, source_title: str, priority: float, rows: list[dict[str, Any]]) -> list[SourceRecord]:
    return [
        SourceRecord(
            iri=row["iri"],
            label=row["label"],
            source_id=source_id,
            source_title=source_title,
            record_type=row["type"],
            priority=priority,
            synonyms=row.get("synonyms", []),
            definition=row.get("definition", ""),
        )
        for row in rows
    ]


def _record_type(graph: Graph, subject: URIRef) -> str:
    rdf_types = set(graph.objects(subject, RDF.type))
    if OWL.Class in rdf_types or RDFS.Class in rdf_types:
        return "class"
    if OWL.ObjectProperty in rdf_types:
        return "object_property"
    if OWL.DatatypeProperty in rdf_types:
        return "datatype_property"
    if OWL.AnnotationProperty in rdf_types:
        return "annotation_property"
    return "controlled_vocabulary_term"


def _parse_rdf_source(path: Path, source_id: str, source_title: str, priority: float) -> list[SourceRecord]:
    graph = Graph()
    graph.parse(path, format=guess_rdf_format(path))
    records: list[SourceRecord] = []
    for subject in sorted(set(graph.subjects()), key=str):
        if not isinstance(subject, URIRef):
            continue
        record_type = _record_type(graph, subject)
        if record_type == "controlled_vocabulary_term" and not list(graph.objects(subject, RDF.type)):
            continue
        label = next((str(obj) for obj in graph.objects(subject, RDFS.label)), humanize_identifier(local_name(subject)))
        definition = next((str(obj) for obj in graph.objects(subject, SKOS.definition)), "")
        records.append(
            SourceRecord(
                iri=str(subject),
                label=label,
                source_id=source_id,
                source_title=source_title,
                record_type=record_type,
                priority=priority,
                synonyms=[],
                definition=definition,
            )
        )
    return records


def _maybe_fetch(fetch_cfg: dict[str, Any], cache_dir: Path, timeout: int) -> Path | None:
    local_path = fetch_cfg.get("path")
    if local_path:
        path = Path(local_path)
        if path.exists():
            return path
    if not fetch_cfg.get("allow_remote"):
        return None
    url = fetch_cfg.get("url")
    if not url:
        return None
    cache_file = fetch_cfg.get("cache_file", "source.ttl")
    target = cache_dir / cache_file
    if target.exists():
        return target
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    ensure_dir(target.parent)
    target.write_bytes(response.content)
    return target


def load_source_records(source_config: dict[str, Any], root: Path) -> tuple[list[SourceRecord], list[str]]:
    cache_dir = root / source_config.get("cache_directory", "cache/sources")
    timeout = int(source_config.get("default_timeout_seconds", 15))
    records: list[SourceRecord] = []
    notes: list[str] = []
    for source_id, cfg in source_config.get("sources", {}).items():
        if not cfg.get("enabled", False):
            continue
        records.extend(_to_source_records(source_id, cfg["title"], float(cfg["priority"]), BUILTIN_SOURCES.get(source_id, [])))
        try:
            path = _maybe_fetch(cfg.get("fetch", {}), cache_dir, timeout)
            if path:
                parsed = _parse_rdf_source(path, source_id, cfg["title"], float(cfg["priority"]))
                if parsed:
                    records.extend(parsed)
                    notes.append(f"Loaded additional records for {source_id} from {path}.")
        except Exception as exc:
            if not cfg.get("optional", False):
                notes.append(f"Could not load additional source content for {source_id}: {exc}")
            else:
                notes.append(f"Skipped optional source {source_id}: {exc}")
    return records, notes
