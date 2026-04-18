from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .utils import default_source_registry, package_root, try_load_yaml


@dataclass
class Source:
    identifier: str
    title: str
    enabled: bool
    priority: int
    required: bool
    kind: str = "ontology"
    local_cache: str | None = None
    remote_url: str | None = None


def load_sources(config_dir: str | Path | None = None) -> list[Source]:
    config_path = Path(config_dir or package_root() / "config") / "source_ontologies.yaml"
    loaded = try_load_yaml(config_path, default_source_registry())
    sources: list[Source] = []
    for entry in loaded.get("sources", []):
        if not isinstance(entry, dict):
            continue
        sources.append(
            Source(
                identifier=str(entry.get("id", "")),
                title=str(entry.get("title", entry.get("id", ""))),
                enabled=bool(entry.get("enabled", True)),
                priority=int(entry.get("priority", 0)),
                required=bool(entry.get("required", False)),
                kind=str(entry.get("kind", "ontology")),
                local_cache=entry.get("local_cache"),
                remote_url=entry.get("remote_url") or entry.get("api_url"),
            )
        )
    return sorted(sources, key=lambda source: source.priority, reverse=True)


def builtin_source_terms() -> list[dict[str, Any]]:
    return [
        {
            "iri": "http://www.w3.org/ns/prov#Agent",
            "label": "Agent",
            "kind": "class",
            "source": "prov-o",
            "description": "Something that bears responsibility for an activity or outcome.",
            "synonyms": ["researcher", "operator", "actor"],
        },
        {
            "iri": "http://purl.org/dc/terms/identifier",
            "label": "identifier",
            "kind": "datatype_property",
            "source": "dcterms",
            "description": "A string or code that unambiguously identifies a resource.",
            "synonyms": ["has identifier"],
        },
        {
            "iri": "http://qudt.org/schema/qudt/quantityValue",
            "label": "quantity value",
            "kind": "object_property",
            "source": "qudt-schema",
            "description": "Associates a resource with a quantity value node.",
            "synonyms": ["has quantity value"],
        },
        {
            "iri": "http://qudt.org/schema/qudt/QuantityValue",
            "label": "Quantity value",
            "kind": "class",
            "source": "qudt-schema",
            "description": "A value node that combines numeric value, unit, and quantity kind.",
            "synonyms": ["quantity node"],
        },
        {
            "iri": "https://w3id.org/emmo#EMMO_process",
            "label": "Process",
            "kind": "class",
            "source": "emmo-core",
            "description": "A temporal entity or process in EMMO.",
            "synonyms": ["operation", "activity"],
        },
        {
            "iri": "https://w3id.org/emmo#EMMO_material",
            "label": "Material",
            "kind": "class",
            "source": "emmo-core",
            "description": "A material entity in EMMO.",
            "synonyms": ["matter"],
        },
        {
            "iri": "https://w3id.org/emmo#EMMO_property",
            "label": "Property",
            "kind": "class",
            "source": "emmo-core",
            "description": "A property concept in EMMO.",
            "synonyms": ["attribute"],
        },
        {
            "iri": "https://w3id.org/emmo/domain/electrochemistry#electrochemistry_7729c34e_1ae9_403d_b933_1765885e7f29",
            "label": "Electrochemical measurement",
            "kind": "class",
            "source": "emmo-electrochemistry",
            "description": "Measurement activity in an electrochemical setting.",
            "synonyms": ["measurement"],
        },
        {
            "iri": "http://xmlns.com/foaf/0.1/name",
            "label": "name",
            "kind": "datatype_property",
            "source": "foaf",
            "description": "A human-readable name for a resource.",
            "synonyms": ["has name"],
        },
        {
            "iri": "https://purls.helmholtz-metadaten.de/hob/HDO_00000000",
            "label": "Helmholtz Digitisation Ontology root",
            "kind": "class",
            "source": "hdo",
            "description": "Top-level HDO anchor used for shadow-mode reporting until a local HDO cache is supplied.",
            "synonyms": ["HDO root", "Helmholtz Digitisation Ontology"],
        },
        {
            "iri": "http://purl.obolibrary.org/obo/CHEBI_15377",
            "label": "Water",
            "kind": "class",
            "source": "chebi",
            "description": "A ChEBI chemical entity representing water.",
            "synonyms": ["H2O"],
        },
        {
            "iri": "http://purl.obolibrary.org/obo/CHEBI_16236",
            "label": "Ethanol",
            "kind": "class",
            "source": "chebi",
            "description": "A ChEBI chemical entity representing ethanol.",
            "synonyms": ["ethyl alcohol"],
        },
        {
            "iri": "http://purl.obolibrary.org/obo/CHEBI_18280",
            "label": "Hydrazine",
            "kind": "class",
            "source": "chebi",
            "description": "A ChEBI chemical entity representing hydrazine.",
            "synonyms": [],
        },
        {
            "iri": "http://purl.obolibrary.org/obo/CHEBI_17883",
            "label": "Hydrochloric acid",
            "kind": "class",
            "source": "chebi",
            "description": "A ChEBI chemical entity representing hydrochloric acid.",
            "synonyms": ["Hydrochloric Acid"],
        },
        {
            "iri": "http://purl.obolibrary.org/obo/CHEBI_29241",
            "label": "Hydrofluoric acid",
            "kind": "class",
            "source": "chebi",
            "description": "A ChEBI chemical entity representing hydrofluoric acid.",
            "synonyms": ["Hydrofluoric Acid"],
        },
        {
            "iri": "http://purl.obolibrary.org/obo/CHEBI_16526",
            "label": "Carbon dioxide",
            "kind": "class",
            "source": "chebi",
            "description": "A ChEBI chemical entity representing carbon dioxide.",
            "synonyms": ["Carbon Dioxide"],
        },
        {
            "iri": "http://purl.obolibrary.org/obo/CHEBI_30751",
            "label": "Formic acid",
            "kind": "class",
            "source": "chebi",
            "description": "A ChEBI chemical entity representing formic acid.",
            "synonyms": ["Formic Acid"],
        },
        {
            "iri": "http://purl.obolibrary.org/obo/CHEBI_32035",
            "label": "Potassium hydroxide",
            "kind": "class",
            "source": "chebi",
            "description": "A ChEBI chemical entity representing potassium hydroxide.",
            "synonyms": ["Potassium Hydroxide", "KOH"],
        },
    ]
