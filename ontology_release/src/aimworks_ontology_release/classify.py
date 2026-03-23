from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .io import dump_jsonld_items, load_json_document, merge_document_items
from .normalize import best_label, lexical_signature, looks_like_ephemeral, looks_like_quantity_value
from .utils import (
    OWL_ANNOTATION_PROPERTY,
    OWL_CLASS,
    OWL_DATATYPE_PROPERTY,
    OWL_OBJECT_PROPERTY,
    OWL_ONTOLOGY,
    RDFS_CLASS,
    deep_get,
    default_release_profile,
    dump_json,
    ensure_dir,
    humanize,
    local_name,
    try_load_yaml,
)


@dataclass
class ResourceClassification:
    iri: str
    label: str
    kind: str
    confidence: float
    reasons: list[str]
    is_local: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def classify_resources(
    input_path: str | Path,
    output_dir: str | Path,
    config_dir: str | Path | None = None,
) -> list[ResourceClassification]:
    input_path = Path(input_path)
    output_dir = ensure_dir(Path(output_dir))
    profile = try_load_yaml(Path(config_dir or input_path.parent.parent / "config") / "release_profile.yaml", default_release_profile())
    namespace_uri = deep_get(profile, "project", "namespace_uri", default="https://w3id.org/h2kg/hydrogen-ontology#")
    ontology_iri = deep_get(profile, "project", "ontology_iri", default="https://w3id.org/h2kg/hydrogen-ontology")
    merged = merge_document_items(load_json_document(input_path))
    results = [_classify_item(item, ontology_iri, namespace_uri) for item in merged if isinstance(item.get("@id"), str)]
    dump_json(output_dir / "classification_report.json", [item.to_dict() for item in results])
    dump_jsonld_items(output_dir / "classification_snapshot.jsonld", [item for item in merged if isinstance(item.get("@id"), str)])
    return results


def _classify_item(item: dict[str, Any], ontology_iri: str, namespace_uri: str) -> ResourceClassification:
    identifier = str(item.get("@id", ""))
    label = best_label(item)
    is_local = identifier == ontology_iri or identifier.startswith(namespace_uri)
    types = item.get("@type", [])
    type_values = types if isinstance(types, list) else [types]
    reasons: list[str] = []
    if OWL_ONTOLOGY in type_values or identifier == ontology_iri:
        return ResourceClassification(identifier, label, "ontology_header", 1.0, ["Explicit ontology header."], is_local)
    if OWL_CLASS in type_values or RDFS_CLASS in type_values:
        return ResourceClassification(identifier, label, "class", 1.0, ["Explicit owl:Class or rdfs:Class."], is_local)
    if OWL_OBJECT_PROPERTY in type_values:
        return ResourceClassification(identifier, label, "object_property", 1.0, ["Explicit owl:ObjectProperty."], is_local)
    if OWL_DATATYPE_PROPERTY in type_values:
        return ResourceClassification(identifier, label, "datatype_property", 1.0, ["Explicit owl:DatatypeProperty."], is_local)
    if OWL_ANNOTATION_PROPERTY in type_values:
        return ResourceClassification(identifier, label, "annotation_property", 1.0, ["Explicit owl:AnnotationProperty."], is_local)
    if looks_like_quantity_value(item):
        reasons.append("QUDT quantity value indicators detected.")
        return ResourceClassification(identifier, label, "quantity_value_data_node", 0.95, reasons, is_local)
    if not is_local:
        return ResourceClassification(identifier, label, "external_resource", 0.8, ["External namespace resource."], is_local)
    local = local_name(identifier)
    signature = lexical_signature(item)
    if any(token in signature for token in ["basis", "type", "design", "presence", "ratio", "electrode"]) and "measurement" not in signature:
        reasons.append("Looks like a controlled vocabulary or reference term.")
        return ResourceClassification(identifier, label, "controlled_vocabulary_term", 0.72, reasons, is_local)
    if looks_like_ephemeral(identifier):
        reasons.append("Identifier looks generated or instance-like.")
        return ResourceClassification(identifier, label, "ephemeral_generated_instance", 0.85, reasons, is_local)
    if any(key in item for key in ["https://w3id.org/h2kg/hydrogen-ontology#hasQuantityValue", "https://w3id.org/h2kg/hydrogen-ontology#hasParameter"]):
        reasons.append("Operational measurement or process structure detected.")
        return ResourceClassification(identifier, label, "example_individual", 0.78, reasons, is_local)
    reasons.append(f"Defaulted to example individual for local non-schema term `{humanize(local)}`.")
    return ResourceClassification(identifier, label, "example_individual", 0.6, reasons, is_local)
