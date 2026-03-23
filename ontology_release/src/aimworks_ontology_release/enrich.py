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
    schema_items = [item for item in enriched if item.get("@id") == ontology_iri or (classifications.get(str(item.get("@id"))) and classifications[str(item.get("@id"))].kind in {"class", "object_property", "datatype_property"})]
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
    if kind == "class":
        return f"Class representing {label.lower()} in the H2KG PEMFC catalyst-layer application ontology."
    if kind == "object_property":
        return f"Object property used to relate two resources within the H2KG PEMFC catalyst-layer application ontology."
    return f"Datatype property used to attach literal metadata or values related to {label.lower()}."


def _comment_for(label: str, kind: str) -> str:
    if kind == "class":
        return f"{label} is a local H2KG concept preserved for PEMFC catalyst-layer domain modelling."
    return f"{label} is a local H2KG relation preserved for backward-compatible release preparation."


def _metadata_report(schema_items: list[dict[str, Any]]) -> str:
    annotated = sum(1 for item in schema_items if item.get(SKOS_DEFINITION))
    return f"""# Metadata Enrichment Report

- Enriched schema resources: {len(schema_items)}
- Resources with definitions after enrichment: {annotated}
- Ontology header metadata normalized: yes
- Stable namespace metadata added: yes
"""
