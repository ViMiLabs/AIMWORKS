from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .classify import classify_resources
from .io import dump_jsonld_items, dump_turtle_items, load_json_document, merge_document_items
from .normalize import best_description, best_label
from .utils import (
    H2KG_APPLIES_TO_PROFILE,
    OWL_ONTOLOGY,
    RDFS_IS_DEFINED_BY,
    default_release_profile,
    dump_json,
    ensure_dir,
    local_name,
    profile_registry,
    short_text,
    try_load_yaml,
    write_text,
)


SCHEMA_KINDS = {
    "class",
    "object_property",
    "datatype_property",
    "annotation_property",
    "controlled_vocabulary_term",
}


def build_profile_modules(
    input_path: str | Path,
    output_dir: str | Path,
    config_dir: str | Path | None = None,
) -> dict[str, Any]:
    input_path = Path(input_path)
    output_dir = ensure_dir(Path(output_dir))
    config_root = Path(config_dir or input_path.parent.parent / "config")
    profile = try_load_yaml(config_root / "release_profile.yaml", default_release_profile())
    project = profile["project"]
    registry = profile_registry(profile)
    core_profile = registry["core"]
    pemfc_profile = registry["pemfc"]
    pemwe_profile = registry["pemwe"]
    source_namespace = str(project["namespace_uri"])
    source_ontology_iri = str(project["ontology_iri"])
    merged = merge_document_items(load_json_document(input_path))
    classifications = {entry.iri: entry for entry in classify_resources(input_path, output_dir.parent / "review", config_root)}

    local_schema_items: list[dict[str, Any]] = []
    assignments: dict[str, set[str]] = {}
    for item in merged:
        identifier = item.get("@id")
        if not isinstance(identifier, str):
            continue
        classification = classifications.get(identifier)
        if not classification:
            continue
        if identifier == source_ontology_iri:
            continue
        if not identifier.startswith(source_namespace):
            continue
        if classification.kind not in SCHEMA_KINDS:
            continue
        local_schema_items.append(item)
        assignments[identifier] = _assign_profiles(item, registry)

    core_header = _profile_header(project, core_profile, imports=[], prefix=project.get("namespace_prefix", "h2kg"))
    pemfc_header = _profile_header(project, pemfc_profile, imports=pemfc_profile.get("imports", [core_profile["ontology_iri"]]), prefix="h2kg-pemfc")
    pemwe_header = _profile_header(project, pemwe_profile, imports=pemwe_profile.get("imports", [core_profile["ontology_iri"]]), prefix="h2kg-pemwe")

    core_items = [core_header] + [_tag_item(item, {pemfc_profile["ontology_iri"], pemwe_profile["ontology_iri"]}, core_profile["ontology_iri"]) for item in local_schema_items]
    pemfc_items = [pemfc_header] + [
        _tag_item(item, assignments.get(str(item.get("@id")), {"pemfc"}), pemfc_profile["ontology_iri"], iri_by_key={"pemfc": pemfc_profile["ontology_iri"], "pemwe": pemwe_profile["ontology_iri"]})
        for item in local_schema_items
        if "pemfc" in assignments.get(str(item.get("@id")), set())
    ]
    pemwe_items = [pemwe_header] + [
        _tag_item(item, assignments.get(str(item.get("@id")), {"pemwe"}), pemwe_profile["ontology_iri"], iri_by_key={"pemfc": pemfc_profile["ontology_iri"], "pemwe": pemwe_profile["ontology_iri"]})
        for item in local_schema_items
        if "pemwe" in assignments.get(str(item.get("@id")), set())
    ]

    dump_turtle_items(output_dir / "core_schema.ttl", core_items)
    dump_jsonld_items(output_dir / "core_schema.jsonld", core_items)
    dump_turtle_items(output_dir / "pemfc_schema.ttl", pemfc_items)
    dump_jsonld_items(output_dir / "pemfc_schema.jsonld", pemfc_items)
    dump_turtle_items(output_dir / "pemwe_schema.ttl", pemwe_items)
    dump_jsonld_items(output_dir / "pemwe_schema.jsonld", pemwe_items)

    report = {
        "core_ontology_iri": core_profile["ontology_iri"],
        "pemfc_ontology_iri": pemfc_profile["ontology_iri"],
        "pemwe_ontology_iri": pemwe_profile["ontology_iri"],
        "core_term_count": max(0, len(core_items) - 1),
        "pemfc_term_count": max(0, len(pemfc_items) - 1),
        "pemwe_term_count": max(0, len(pemwe_items) - 1),
        "shared_terms": sum(1 for value in assignments.values() if value == {"pemfc", "pemwe"}),
        "pemfc_only_terms": sum(1 for value in assignments.values() if value == {"pemfc"}),
        "pemwe_only_terms": sum(1 for value in assignments.values() if value == {"pemwe"}),
        "samples": _sample_assignments(local_schema_items, assignments),
    }
    dump_json(output_dir.parent / "reports" / "profile_module_report.json", report)
    write_text(output_dir.parent / "reports" / "profile_module_report.md", _report_markdown(report))
    return report


def _assign_profiles(item: dict[str, Any], registry: dict[str, dict[str, Any]]) -> set[str]:
    signature = " ".join(
        [
            best_label(item).lower(),
            short_text(best_description(item) or "", limit=800).lower(),
            local_name(str(item.get("@id", ""))).lower(),
        ]
    )
    scores = {"pemfc": 0, "pemwe": 0}
    for key in ("pemfc", "pemwe"):
        indicators = registry.get(key, {}).get("indicators", [])
        for token in indicators:
            if str(token).lower() in signature:
                scores[key] += 1
    if scores["pemfc"] == 0 and scores["pemwe"] == 0:
        return {"pemfc", "pemwe"}
    if scores["pemfc"] == scores["pemwe"]:
        return {"pemfc", "pemwe"}
    return {"pemfc"} if scores["pemfc"] > scores["pemwe"] else {"pemwe"}


def _profile_header(project: dict[str, Any], profile_cfg: dict[str, Any], imports: list[str], prefix: str) -> dict[str, Any]:
    version = str(project.get("version", "1.0.0"))
    ontology_iri = str(profile_cfg["ontology_iri"])
    imports_values = [{"@id": iri} for iri in imports if isinstance(iri, str) and iri]
    header: dict[str, Any] = {
        "@id": ontology_iri,
        "@type": [OWL_ONTOLOGY],
        "http://purl.org/dc/terms/title": [{"@value": str(profile_cfg.get("title", ontology_iri)), "@language": "en"}],
        "http://purl.org/dc/terms/description": [
            {
                "@value": f"Profile ontology module for {profile_cfg.get('title', ontology_iri)}. This module preserves stable H2KG core term IRIs and scopes terms for profile publication.",
                "@language": "en",
            }
        ],
        "http://www.w3.org/2002/07/owl#versionInfo": [{"@value": version, "@language": "en"}],
        "http://www.w3.org/2002/07/owl#versionIRI": [{"@id": f"{ontology_iri}/releases/{version}"}],
        "http://purl.org/vocab/vann/preferredNamespacePrefix": [{"@value": prefix}],
        "http://purl.org/vocab/vann/preferredNamespaceUri": [{"@id": str(profile_cfg["namespace_uri"])}],
    }
    if imports_values:
        header["http://www.w3.org/2002/07/owl#imports"] = imports_values
    return header


def _tag_item(
    item: dict[str, Any],
    profile_keys_or_iris: set[str],
    defined_by_iri: str,
    iri_by_key: dict[str, str] | None = None,
) -> dict[str, Any]:
    updated = deepcopy(item)
    iri_by_key = iri_by_key or {}
    profile_iris: list[str] = []
    for value in sorted(profile_keys_or_iris):
        iri = iri_by_key.get(value, value)
        if iri not in profile_iris:
            profile_iris.append(iri)
    existing = updated.get(H2KG_APPLIES_TO_PROFILE, [])
    entries = existing if isinstance(existing, list) else [existing]
    for iri in profile_iris:
        entry = {"@id": iri}
        if entry not in entries:
            entries.append(entry)
    updated[H2KG_APPLIES_TO_PROFILE] = entries
    updated[RDFS_IS_DEFINED_BY] = [{"@id": defined_by_iri}]
    return updated


def _sample_assignments(items: list[dict[str, Any]], assignments: dict[str, set[str]]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for item in items[:30]:
        identifier = str(item.get("@id", ""))
        assigned = sorted(assignments.get(identifier, {"pemfc", "pemwe"}))
        samples.append({"iri": identifier, "label": best_label(item), "profiles": assigned})
    return samples


def _report_markdown(report: dict[str, Any]) -> str:
    sample_lines = "\n".join(
        f"- {entry['label']} (`{entry['iri']}`) -> {', '.join(entry['profiles'])}" for entry in report.get("samples", [])
    )
    return f"""# Profile Module Report

- Shared core ontology IRI: `{report['core_ontology_iri']}`
- PEMFC profile ontology IRI: `{report['pemfc_ontology_iri']}`
- PEMWE profile ontology IRI: `{report['pemwe_ontology_iri']}`
- Shared local schema terms: {report['shared_terms']}
- PEMFC-only local schema terms: {report['pemfc_only_terms']}
- PEMWE-only local schema terms: {report['pemwe_only_terms']}
- Core module term count: {report['core_term_count']}
- PEMFC module term count: {report['pemfc_term_count']}
- PEMWE module term count: {report['pemwe_term_count']}

## Assignment Sample

{sample_lines or '- none'}
"""
