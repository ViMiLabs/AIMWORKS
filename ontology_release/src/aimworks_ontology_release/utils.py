from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = Path(__file__).resolve().parents[1]

COMMON_CONTEXT: dict[str, str] = {
    "h2kg": "https://w3id.org/h2kg/hydrogen-ontology#",
    "h2kg-pemfc": "https://w3id.org/h2kg/pemfc/hydrogen-ontology#",
    "h2kg-pemwe": "https://w3id.org/h2kg/pemwe/hydrogen-ontology#",
    "holy": "http://purl.org/holy/ns#",
    "emmo": "https://w3id.org/emmo#",
    "electrochemistry": "https://w3id.org/emmo/domain/electrochemistry#",
    "pemfc": "https://w3id.org/emmo/domain/pemfc#",
    "owl": "http://www.w3.org/2002/07/owl#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "dcterms": "http://purl.org/dc/terms/",
    "prov": "http://www.w3.org/ns/prov#",
    "vann": "http://purl.org/vocab/vann/",
    "qudt": "http://qudt.org/schema/qudt/",
    "unit": "http://qudt.org/vocab/unit/",
    "quantitykind": "http://qudt.org/vocab/quantitykind/",
    "chebi": "http://purl.obolibrary.org/obo/CHEBI_",
    "oeo": "http://openenergy-platform.org/ontology/oeo/",
    "foaf": "http://xmlns.com/foaf/0.1/",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
}

OWL_CLASS = "http://www.w3.org/2002/07/owl#Class"
OWL_OBJECT_PROPERTY = "http://www.w3.org/2002/07/owl#ObjectProperty"
OWL_DATATYPE_PROPERTY = "http://www.w3.org/2002/07/owl#DatatypeProperty"
OWL_ANNOTATION_PROPERTY = "http://www.w3.org/2002/07/owl#AnnotationProperty"
OWL_ONTOLOGY = "http://www.w3.org/2002/07/owl#Ontology"
OWL_EQUIVALENT_CLASS = "http://www.w3.org/2002/07/owl#equivalentClass"
OWL_EQUIVALENT_PROPERTY = "http://www.w3.org/2002/07/owl#equivalentProperty"
RDFS_CLASS = "http://www.w3.org/2000/01/rdf-schema#Class"
RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"
RDFS_COMMENT = "http://www.w3.org/2000/01/rdf-schema#comment"
RDFS_SUBCLASS = "http://www.w3.org/2000/01/rdf-schema#subClassOf"
RDFS_SUBPROPERTY = "http://www.w3.org/2000/01/rdf-schema#subPropertyOf"
RDFS_DOMAIN = "http://www.w3.org/2000/01/rdf-schema#domain"
RDFS_RANGE = "http://www.w3.org/2000/01/rdf-schema#range"
RDFS_IS_DEFINED_BY = "http://www.w3.org/2000/01/rdf-schema#isDefinedBy"
SKOS_DEFINITION = "http://www.w3.org/2004/02/skos/core#definition"
SKOS_PREF_LABEL = "http://www.w3.org/2004/02/skos/core#prefLabel"
SKOS_ALT_LABEL = "http://www.w3.org/2004/02/skos/core#altLabel"
QUDT_QUANTITY_VALUE = "http://qudt.org/schema/qudt/QuantityValue"
QUDT_NUMERIC_VALUE = "http://qudt.org/schema/qudt/numericValue"
QUDT_UNIT = "http://qudt.org/schema/qudt/unit"
QUDT_QUANTITY_KIND = "http://qudt.org/schema/qudt/quantityKind"
H2KG_APPLIES_TO_PROFILE = "https://w3id.org/h2kg/hydrogen-ontology#appliesToProfile"


def package_root() -> Path:
    return PACKAGE_ROOT


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> Path:
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8")
    return path


def load_json(path: Path) -> Any:
    return json.loads(read_text(path))


def dump_json(path: Path, data: Any) -> Path:
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path


def try_load_yaml(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    try:
        import yaml  # type: ignore

        with path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle)
        return _deep_merge(deepcopy(default), loaded) if isinstance(loaded, dict) else deepcopy(default)
    except Exception:
        return deepcopy(default)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _deep_merge(dict(base[key]), value)
        else:
            base[key] = value
    return base


def today_iso() -> str:
    return date.today().isoformat()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def uri_namespace(uri: str) -> str:
    if "#" in uri:
        return uri.rsplit("#", 1)[0] + "#"
    if "/" in uri:
        return uri.rstrip("/").rsplit("/", 1)[0] + "/"
    return uri


def local_name(uri: str) -> str:
    if "#" in uri:
        return uri.rsplit("#", 1)[1]
    return uri.rstrip("/").rsplit("/", 1)[-1]


def canonical_qname(uri: str, fallback: str = "") -> str:
    if not uri:
        return fallback
    for prefix, base in sorted(COMMON_CONTEXT.items(), key=lambda item: len(item[1]), reverse=True):
        if uri.startswith(base):
            local = uri[len(base) :]
            return f"{prefix}:{local}" if local else f"{prefix}:"
    if fallback and not re.match(r"^ns\d+:", fallback):
        return fallback
    return fallback or uri


def humanize(text: str) -> str:
    if not text:
        return text
    value = text.replace("_", " ").replace("-", " ")
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    if not value:
        return text
    return value[0].upper() + value[1:]


def normalize_token(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def short_text(text: str, limit: int = 220) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def html_paragraphs(lines: list[str]) -> str:
    return "\n".join(f"<p>{escape(line)}</p>" for line in lines if line)


def deep_get(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def default_release_profile() -> dict[str, Any]:
    return {
        "project": {
            "title": "H2KG PEMFC Catalyst Layer Application Ontology",
            "short_title": "H2KG PEMFC Catalyst Layer Ontology",
            "subtitle": "EMMO-aligned ontology for PEMFC catalyst-layer experiments",
            "description": "Application ontology for low-Pt PEMFC cathode catalyst-layer experiments, materials, measurements, quantity values, and FAIR provenance.",
            "ontology_iri": "https://w3id.org/h2kg/hydrogen-ontology",
            "namespace_prefix": "h2kg",
            "namespace_uri": "https://w3id.org/h2kg/hydrogen-ontology#",
            "repository_url": "https://github.com/aimworks/AIMWORKS",
            "docs_url": "https://aimworks.github.io/AIMWORKS/ontology_release/output/docs/",
            "version": "1.0.0",
            "version_tag": "v1.0.0",
            "version_iri": "https://w3id.org/h2kg/hydrogen-ontology/releases/1.0.0",
            "prior_version": "https://w3id.org/h2kg/hydrogen-ontology",
            "license": "https://creativecommons.org/licenses/by/4.0/",
            "acknowledgements": {
                "support_copy": "Supported through the DECODE project, the Helmholtz Metadata Collaboration (HMC), and AIMWORKS, connecting FAIR ontology publication with reusable metadata infrastructure.",
                "initiatives": [
                    {
                        "name": "DECODE",
                        "url": "https://decode-energy.eu/",
                        "logo": "decode-logo.png",
                        "logo_alt": "DECODE project logo",
                    },
                    {"name": "HMC", "url": "https://helmholtz-metadaten.de/", "logo": "hmc-logo.png", "logo_alt": "Helmholtz Metadata Collaboration logo"},
                    {
                        "name": "AIMWORKS",
                        "url": "https://helmholtz-metadaten.de/inf-projects/aimworks",
                        "logo": "aimworks-logo.png",
                        "logo_alt": "AIMWORKS logo",
                    },
                ],
                "funding_notice": [
                    "This publication is part of the DECODE project that has received funding from the European Union's Horizon Europe research and innovation programme under grant agreement No 101135537. Views and opinions expressed are however those of the author(s) only and do not necessarily reflect those of the European Union or HADEA. Neither the European Union nor the granting authority can be held responsible for them.",
                    "This work was also partially funded by the Helmholtz Metadata Collaboration (HMC), an incubator platform of the Helmholtz Association within its Information and Data Science strategic initiative, through the Initiative and Networking Fund (INF) - AIMWORKS (grant no. ZT-I-PF-3-099, project no. D.B.002807).",
                ],
            },
            "profiles": {
                "core": {
                    "title": "H2KG Shared Core Ontology",
                    "ontology_iri": "https://w3id.org/h2kg/hydrogen-ontology",
                    "namespace_uri": "https://w3id.org/h2kg/hydrogen-ontology#",
                },
                "pemfc": {
                    "title": "H2KG PEMFC Application Ontology",
                    "ontology_iri": "https://w3id.org/h2kg/pemfc/hydrogen-ontology",
                    "namespace_uri": "https://w3id.org/h2kg/pemfc/hydrogen-ontology#",
                    "imports": ["https://w3id.org/h2kg/hydrogen-ontology"],
                    "indicators": [
                        "pemfc",
                        "cathode",
                        "anode",
                        "gas diffusion layer",
                        "catalyst layer",
                        "reference electrode",
                    ],
                },
                "pemwe": {
                    "title": "H2KG PEMWE Application Ontology",
                    "ontology_iri": "https://w3id.org/h2kg/pemwe/hydrogen-ontology",
                    "namespace_uri": "https://w3id.org/h2kg/pemwe/hydrogen-ontology#",
                    "imports": ["https://w3id.org/h2kg/hydrogen-ontology"],
                    "indicators": [
                        "pemwe",
                        "electrolyzer",
                        "electrolysis",
                        "oxygen evolution",
                        "hydrogen evolution",
                    ],
                },
            },
        },
        "maintainers": {
            "creator": ["AIMWORKS Maintainers"],
            "contributor": ["Electrochemistry Research Group"],
            "publisher": ["AIMWORKS"],
        },
        "release": {
            "preserve_term_iris": True,
            "preserve_hash_namespace": True,
            "build_docs": True,
            "build_release_bundle": True,
            "validate_with_shacl": True,
            "fair_check": True,
            "generate_w3id": True,
            "emit_jsonld": True,
            "emit_ttl": True,
        },
        "external_assessment": {
            "enabled": False,
            "oops_enabled": False,
            "foops_enabled": False,
            "foops_mode": "file",
            "oops_service": "https://oops.linkeddata.es/rest",
            "foops_service": "https://foops.linkeddata.es/FAIR_validator.html",
            "foops_file_service": "https://foops.linkeddata.es/assessOntologyFile",
            "foops_uri_service": "https://foops.linkeddata.es/assessOntology",
            "timeout_seconds": 45,
            "retries": 3,
            "backoff_seconds": 2,
            "use_env_proxies": False,
            "public_uri": "",
        },
        "separation": {
            "publish_examples": True,
            "publish_controlled_vocabulary": True,
            "treat_quantity_values_as_examples": True,
            "treat_generated_nodes_as_examples": True,
            "local_schema_priority": [
                "Agent",
                "Process",
                "Manufacturing",
                "Measurement",
                "Instrument",
                "Matter",
                "Parameter",
                "Property",
                "Data",
                "DataPoint",
                "Metadata",
                "NormalizationBasis",
                "ReferenceElectrode",
                "Unit",
            ],
        },
    }


def profile_registry(release_profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    project = release_profile.get("project", {})
    profiles = project.get("profiles", {})
    if isinstance(profiles, dict) and profiles:
        return profiles
    return default_release_profile()["project"]["profiles"]


def default_metadata_defaults() -> dict[str, Any]:
    return {
        "ontology": {
            "title": "H2KG PEMFC Catalyst Layer Application Ontology",
            "subtitle": "EMMO-aligned ontology for low-Pt PEMFC catalyst-layer experiments and related provenance",
            "abstract": "Application ontology for low-Pt PEMFC cathode catalyst layer experiments, materials, manufacturing conditions, measurements, quantities, and release metadata.",
            "description": "The ontology captures PEMFC catalyst-layer experimental concepts, parameters, properties, measurements, instruments, materials, and FAIR provenance.",
            "created": "2026-03-19",
            "modified": "2026-03-19",
            "language": "en",
            "creators": ["AIMWORKS Maintainers"],
            "contributors": ["Electrochemistry Research Group"],
            "source": ["ONTOLOGY_extended.jsonld"],
        },
        "term_annotations": {
            "label_language": "en",
            "comment_language": "en",
            "definition_language": "en",
            "add_is_defined_by": True,
            "infer_labels_from_local_names": True,
            "infer_comments_for_unannotated_schema_terms": True,
            "infer_definitions_for_unannotated_schema_terms": True,
        },
    }


def default_mapping_rules() -> dict[str, Any]:
    return {
        "policies": {
            "conservative_mode": True,
            "equivalence_threshold": 0.96,
            "subclass_threshold": 0.82,
            "close_match_threshold": 0.72,
            "exact_match_threshold": 0.88,
            "reuse_existing_external_terms": True,
            "forbid_cross_kind_mappings": True,
            "prefer_subclass_over_equivalence": True,
        },
        "manual_overrides": {
            "Agent": {
                "relation": "rdfs:subClassOf",
                "target": "http://www.w3.org/ns/prov#Agent",
                "rationale": "Agent should remain local while anchored in PROV-O.",
            },
            "Measurement": {
                "relation": "rdfs:subClassOf",
                "target": "https://w3id.org/emmo/domain/electrochemistry#electrochemistry_7729c34e_1ae9_403d_b933_1765885e7f29",
                "rationale": "Measurement is better treated as a local specialization of electrochemical measurement practice.",
            },
            "hasQuantityValue": {
                "relation": "rdfs:subPropertyOf",
                "target": "http://qudt.org/schema/qudt/quantityValue",
                "rationale": "Quantity-value relations should reuse QUDT semantics where possible.",
            },
        },
        "term_hints": {
            "quantity_value_indicators": ["QuantityValue", "numericValue", "unit", "quantityKind"],
            "chemical_indicators": ["platinum", "ionomer", "solvent", "oxygen", "hydrogen", "nafion"],
            "pemfc_indicators": [
                "membrane electrode assembly",
                "catalyst layer",
                "gas diffusion layer",
                "reference electrode",
                "oxygen transport",
            ],
        },
    }


def default_namespace_policy() -> dict[str, Any]:
    return {
        "policy": {
            "active_strategy": "preserve_hash_namespace",
            "preserve_existing_term_iris": True,
            "allow_future_namespace_migration": True,
            "current_ontology_iri": "https://w3id.org/h2kg/hydrogen-ontology",
            "current_namespace_prefix": "h2kg",
            "current_namespace_uri": "https://w3id.org/h2kg/hydrogen-ontology#",
            "publication_base_html": "https://aimworks.github.io/AIMWORKS/ontology_release/output/docs/",
            "publication_base_rdf": "https://raw.githubusercontent.com/aimworks/AIMWORKS/main/ontology_release/output/ontology/",
            "slash_namespace_uri": "https://w3id.org/h2kg/hydrogen-ontology/",
            "version_path_template": "releases/{version}",
            "migration": {
                "enabled": False,
                "target_namespace_uri": None,
                "generate_alias_map": True,
                "generate_redirect_templates": True,
            },
        }
    }


def default_source_registry() -> dict[str, Any]:
    return {
        "sources": [
            {"id": "emmo-core", "title": "EMMO Core", "enabled": True, "priority": 100, "required": True},
            {"id": "emmo-electrochemistry", "title": "EMMO Electrochemistry / ECHO", "enabled": True, "priority": 95, "required": True},
            {"id": "qudt-schema", "title": "QUDT Schema", "enabled": True, "priority": 90, "required": True},
            {"id": "qudt-units", "title": "QUDT Units", "enabled": True, "priority": 90, "required": True},
            {"id": "qudt-quantitykinds", "title": "QUDT Quantity Kinds", "enabled": True, "priority": 90, "required": True},
            {"id": "chebi", "title": "ChEBI", "enabled": True, "priority": 85, "required": False},
            {"id": "prov-o", "title": "PROV-O", "enabled": True, "priority": 80, "required": True},
            {"id": "dcterms", "title": "Dublin Core Terms", "enabled": True, "priority": 80, "required": True},
            {"id": "vann", "title": "VANN", "enabled": True, "priority": 70, "required": True},
            {"id": "oeo", "title": "Open Energy Ontology", "enabled": False, "priority": 20, "required": False},
            {"id": "pemfc-external", "title": "Optional PEMFC-specific Source Ontology", "enabled": False, "priority": 99, "required": False},
        ]
    }
