from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote

try:
    from rdflib import Graph
    from rdflib.namespace import RDF, RDFS, OWL
except Exception:  # pragma: no cover
    Graph = None  # type: ignore[assignment]
    RDF = None  # type: ignore[assignment]
    RDFS = None  # type: ignore[assignment]
    OWL = None  # type: ignore[assignment]

from .classify import classify_resources
from .hdo import load_hdo_alignment_report
from .io import load_json_document, merge_document_items
from .mapper import propose_mappings
from .normalize import best_description, best_label
from .odk import load_odk_manifest
from .utils import (
    canonical_qname,
    default_release_profile,
    dump_json,
    ensure_dir,
    html_paragraphs,
    load_json,
    short_text,
    try_load_yaml,
    write_text,
)

H2KG_NS = "https://w3id.org/h2kg/hydrogen-ontology#"
H2KG_ONTOLOGY_IRI = "https://w3id.org/h2kg/hydrogen-ontology"
SKOS_ALT_LABEL = "http://www.w3.org/2004/02/skos/core#altLabel"
SKOS_EXAMPLE = "http://www.w3.org/2004/02/skos/core#example"
DCTERMS_DESCRIPTION = "http://purl.org/dc/terms/description"
RDFS_COMMENT = "http://www.w3.org/2000/01/rdf-schema#comment"
RDFS_SUBCLASS = "http://www.w3.org/2000/01/rdf-schema#subClassOf"
RDFS_SUBPROPERTY = "http://www.w3.org/2000/01/rdf-schema#subPropertyOf"
RDFS_DOMAIN = "http://www.w3.org/2000/01/rdf-schema#domain"
RDFS_RANGE = "http://www.w3.org/2000/01/rdf-schema#range"
RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"


def build_docs(
    input_path: str | Path,
    output_dir: str | Path,
    config_dir: str | Path | None = None,
    fair_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    output_dir = ensure_dir(Path(output_dir))
    ensure_dir(output_dir / "pages")
    ensure_dir(output_dir / "assets")
    ensure_dir(output_dir / "data")
    ensure_dir(output_dir / "pemfc")
    ensure_dir(output_dir / "pemwe")
    write_text(output_dir / ".nojekyll", "")
    profile = try_load_yaml(Path(config_dir or Path(input_path).parent.parent / "config") / "release_profile.yaml", default_release_profile())
    project = profile["project"]
    items = {item["@id"]: item for item in merge_document_items(load_json_document(input_path)) if isinstance(item.get("@id"), str)}
    classes, properties, examples = _term_views(input_path, output_dir.parent / "review", config_dir, items)
    mappings = propose_mappings(input_path, output_dir.parent / "review", config_dir)
    mapping_summary = _load_alignment_summary(output_dir.parent / "reports")
    namespace_terms = _reference_terms_from_artifact(output_dir.parent / "ontology" / "core_schema.ttl", items, mappings)
    core_terms = _reference_terms_from_artifact(output_dir.parent / "ontology" / "schema.ttl", items, mappings)
    pemfc_terms = _reference_terms_from_artifact(output_dir.parent / "ontology" / "pemfc_schema.ttl", items, mappings)
    pemwe_terms = _reference_terms_from_artifact(output_dir.parent / "ontology" / "pemwe_schema.ttl", items, mappings)
    if not namespace_terms:
        namespace_terms = _reference_terms_from_items(
            items,
            mappings,
            lambda iri, item: iri == H2KG_ONTOLOGY_IRI or iri.startswith(H2KG_NS),
        )
    if not core_terms:
        core_terms = _reference_terms_from_items(
            items,
            mappings,
            lambda iri, item: iri == H2KG_ONTOLOGY_IRI or any(
                type_iri in {
                    str(OWL.Class) if OWL is not None else "http://www.w3.org/2002/07/owl#Class",
                    str(OWL.ObjectProperty) if OWL is not None else "http://www.w3.org/2002/07/owl#ObjectProperty",
                    str(OWL.DatatypeProperty) if OWL is not None else "http://www.w3.org/2002/07/owl#DatatypeProperty",
                    str(OWL.AnnotationProperty) if OWL is not None else "http://www.w3.org/2002/07/owl#AnnotationProperty",
                    str(RDFS.Class) if RDFS is not None else "http://www.w3.org/2000/01/rdf-schema#Class",
                }
                for type_iri in (item.get("@type", []) if isinstance(item.get("@type", []), list) else [item.get("@type")])
                if isinstance(type_iri, str)
            ),
        )
    if not pemfc_terms:
        pemfc_terms = namespace_terms
    if not pemwe_terms:
        pemwe_terms = namespace_terms
    summary = {
        "schema_count": len(classes) + len(properties),
        "vocabulary_count": sum(1 for item in examples if "basis" in item["label"].lower() or "type" in item["label"].lower()),
        "example_count": len(examples),
        "mapping_count": len(mappings),
    }
    explorer = _build_explorer_dataset(namespace_terms, items)
    odk = load_odk_manifest(output_dir.parent)
    hdo = load_hdo_alignment_report(output_dir.parent / "reports")
    release = _release_snapshot_for_docs(output_dir, fair_snapshot, odk)

    page_specs: list[tuple[Path, str, str]] = [
        (output_dir / "hydrogen-ontology.html", "H2KG Namespace Reference", _namespace_reference_body(project, namespace_terms, output_dir / "hydrogen-ontology.html", output_dir)),
        (output_dir / "pages" / "user-guide.html", "User Guide", _user_guide_body()),
        (output_dir / "pages" / "ontology-overview.html", "Ontology Overview", _overview_body(project, summary, odk, hdo)),
        (output_dir / "pages" / "explore.html", "Explore H2KG", _explore_body(project, explorer, output_dir / "pages" / "explore.html", output_dir)),
        (output_dir / "pages" / "reference.html", "H2KG Namespace Reference", _namespace_reference_body(project, namespace_terms, output_dir / "pages" / "reference.html", output_dir)),
        (output_dir / "pages" / "core-reference.html", "Core H2KG Reference", _core_reference_body(project, core_terms, output_dir / "pages" / "core-reference.html", output_dir)),
        (output_dir / "pages" / "class-index.html", "Class Index", _class_body(classes)),
        (output_dir / "pages" / "property-index.html", "Property Index", _property_body(properties)),
        (output_dir / "pages" / "alignment.html", "Alignment", _alignment_body(mappings, mapping_summary)),
        (output_dir / "pages" / "examples.html", "Examples", _examples_body(examples)),
        (output_dir / "pages" / "quality-dashboard.html", "Quality Dashboard", _quality_body(release, odk, hdo)),
        (output_dir / "pages" / "release.html", "Release", _release_body(release, odk, hdo, output_dir / "pages" / "release.html", output_dir)),
        (output_dir / "pages" / "import-guide.html", "Import Guide", _import_guide_body(odk, hdo)),
        (output_dir / "pages" / "import-catalog.html", "Import Catalog", _import_catalog_body(odk)),
        (output_dir / "pages" / "developer-guide.html", "Developer Guide", _developer_body(odk, hdo)),
        (output_dir / "pages" / "architecture-workflow.html", "Architecture Workflow", _architecture_body(project, odk, hdo)),
        (output_dir / "pemfc" / "index.html", "PEMFC Profile", _profile_home_body(project, "pemfc", odk, hdo, output_dir / "pemfc" / "index.html", output_dir)),
        (output_dir / "pemfc" / "hydrogen-ontology.html", "PEMFC Reference", _profile_reference_body(project, "pemfc", pemfc_terms, odk, hdo, output_dir / "pemfc" / "hydrogen-ontology.html", output_dir)),
        (output_dir / "pemwe" / "index.html", "PEMWE Profile", _profile_home_body(project, "pemwe", odk, hdo, output_dir / "pemwe" / "index.html", output_dir)),
        (output_dir / "pemwe" / "hydrogen-ontology.html", "PEMWE Reference", _profile_reference_body(project, "pemwe", pemwe_terms, odk, hdo, output_dir / "pemwe" / "hydrogen-ontology.html", output_dir)),
    ]
    for path, title, body in page_specs:
        extra_head = ""
        if path.name == "explore.html":
            explorer_css = _relative_href(path, output_dir / "assets" / "explorer.css")
            explorer_js = _relative_href(path, output_dir / "assets" / "explorer.js")
            extra_head = (
                f'<link rel="stylesheet" href="{explorer_css}">\n'
                '  <script src="https://cdn.jsdelivr.net/npm/cytoscape@3.29.2/dist/cytoscape.min.js"></script>\n'
                f'  <script defer src="{explorer_js}"></script>'
            )
        write_text(path, _page_template(project, title, body, path, output_dir, extra_head=extra_head))

    write_text(output_dir / "index.html", _legacy_profile_home())
    _copy_site_assets(output_dir, project)
    _copy_odk_artifacts(output_dir)
    write_text(output_dir / "assets" / "style.css", _style_css())
    write_text(output_dir / "assets" / "explorer.css", _explorer_css())
    write_text(output_dir / "assets" / "explorer.js", _explorer_js())
    dump_json(
        output_dir / "search-index.json",
        {
            "classes": classes,
            "properties": properties,
            "examples": examples,
            "mappings": mappings,
            "mapping_summary": mapping_summary,
            "odk": {"status": odk.get("status"), "parity": odk.get("parity", {}).get("status")},
            "hdo": hdo.get("summary", {}),
        },
    )
    dump_json(output_dir / "data" / "explorer.json", explorer)
    return summary


def _term_views(
    input_path: str | Path,
    review_dir: Path,
    config_dir: str | Path | None,
    items: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    classes: list[dict[str, Any]] = []
    properties: list[dict[str, Any]] = []
    examples: list[dict[str, Any]] = []
    mappings = propose_mappings(input_path, review_dir, config_dir)
    mapping_index: dict[str, list[str]] = {}
    for mapping in mappings:
        mapping_index.setdefault(mapping["local_iri"], []).append(f"{mapping['relation']} {mapping['target_iri']}")
    for classification in classify_resources(input_path, review_dir, config_dir):
        item = items.get(classification.iri, {"@id": classification.iri})
        view = {
            "iri": classification.iri,
            "label": best_label(item),
            "description": short_text(best_description(item) or "No description available in the source ontology."),
            "domain": _first_iri(item.get("http://www.w3.org/2000/01/rdf-schema#domain")),
            "range": _first_iri(item.get("http://www.w3.org/2000/01/rdf-schema#range")),
            "mappings": mapping_index.get(classification.iri, []),
        }
        if classification.kind == "class" and classification.is_local:
            classes.append(view)
        elif classification.kind in {"object_property", "datatype_property"} and classification.is_local:
            properties.append(view)
        elif classification.is_local and classification.kind in {"controlled_vocabulary_term", "example_individual", "ephemeral_generated_instance", "quantity_value_data_node"} and len(examples) < 60:
            examples.append(view)
    classes.sort(key=lambda item: item["label"])
    properties.sort(key=lambda item: item["label"])
    examples.sort(key=lambda item: item["label"])
    return classes, properties, examples


def _first_iri(value: Any) -> str:
    values = value if isinstance(value, list) else [value] if value is not None else []
    for entry in values:
        if isinstance(entry, dict) and "@id" in entry:
            return str(entry["@id"])
        if isinstance(entry, str):
            return entry
    return ""


def _reference_terms_from_artifact(
    artifact_path: Path,
    items: dict[str, dict[str, Any]],
    mappings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    selected = _artifact_subjects(artifact_path)
    mapping_index: dict[str, list[dict[str, str]]] = {}
    for mapping in mappings:
        mapping_index.setdefault(mapping["local_iri"], []).append(
            {
                "relation": mapping["relation"],
                "target_iri": mapping["target_iri"],
                "target_label": mapping.get("target_label", ""),
            }
        )
    records: dict[str, dict[str, Any]] = {}
    for iri in selected:
        item = items.get(iri, {"@id": iri})
        parents = _parent_links(item)
        records[iri] = {
            "iri": iri,
            "anchor": _term_anchor_for_iri(iri),
            "label": best_label(item),
            "description": best_description(item) or "No description available in the source ontology.",
            "alt_labels": _literal_values(item.get(SKOS_ALT_LABEL)),
            "examples": _literal_values(item.get(SKOS_EXAMPLE)),
            "notes": _literal_values(item.get(RDFS_COMMENT)),
            "domain": _iri_values(item.get(RDFS_DOMAIN)),
            "range": _iri_values(item.get(RDFS_RANGE)),
            "parents": parents,
            "subclasses": [],
            "subproperties": [],
            "mappings": mapping_index.get(iri, []),
            "type_labels": _type_labels(item),
            "category": _reference_category(item, iri),
        }
    for record in records.values():
        for parent in record["parents"]:
            parent_iri = parent["iri"]
            if parent_iri in records:
                child = {"iri": record["iri"], "label": record["label"], "anchor": record["anchor"]}
                if parent["relation"] == "subclassOf":
                    records[parent_iri]["subclasses"].append(child)
                elif parent["relation"] == "subPropertyOf":
                    records[parent_iri]["subproperties"].append(child)
    return sorted(records.values(), key=lambda item: (_reference_category_order(item["category"]), item["label"].lower()))


def _reference_terms_from_items(
    items: dict[str, dict[str, Any]],
    mappings: list[dict[str, Any]],
    include: Any,
) -> list[dict[str, Any]]:
    selected = {iri for iri, item in items.items() if include(iri, item)}
    if not selected:
        return []
    mapping_index: dict[str, list[dict[str, str]]] = {}
    for mapping in mappings:
        mapping_index.setdefault(mapping["local_iri"], []).append(
            {
                "relation": mapping["relation"],
                "target_iri": mapping["target_iri"],
                "target_label": mapping.get("target_label", ""),
            }
        )
    records: dict[str, dict[str, Any]] = {}
    for iri in selected:
        item = items.get(iri, {"@id": iri})
        parents = _parent_links(item)
        records[iri] = {
            "iri": iri,
            "anchor": _term_anchor_for_iri(iri),
            "label": best_label(item),
            "description": best_description(item) or "No description available in the source ontology.",
            "alt_labels": _literal_values(item.get(SKOS_ALT_LABEL)),
            "examples": _literal_values(item.get(SKOS_EXAMPLE)),
            "notes": _literal_values(item.get(RDFS_COMMENT)),
            "domain": _iri_values(item.get(RDFS_DOMAIN)),
            "range": _iri_values(item.get(RDFS_RANGE)),
            "parents": parents,
            "subclasses": [],
            "subproperties": [],
            "mappings": mapping_index.get(iri, []),
            "type_labels": _type_labels(item),
            "category": _reference_category(item, iri),
        }
    for record in records.values():
        for parent in record["parents"]:
            parent_iri = parent["iri"]
            if parent_iri in records:
                child = {"iri": record["iri"], "label": record["label"], "anchor": record["anchor"]}
                if parent["relation"] == "subclassOf":
                    records[parent_iri]["subclasses"].append(child)
                elif parent["relation"] == "subPropertyOf":
                    records[parent_iri]["subproperties"].append(child)
    return sorted(records.values(), key=lambda item: (_reference_category_order(item["category"]), item["label"].lower()))


def _artifact_subjects(artifact_path: Path) -> set[str]:
    if Graph is None or not artifact_path.exists():
        return set()
    graph = Graph().parse(artifact_path)
    subjects: set[str] = set()
    for subject in graph.subjects():
        iri = str(subject)
        if iri == H2KG_ONTOLOGY_IRI or iri.startswith(H2KG_NS):
            subjects.add(iri)
    return subjects


def _literal_values(value: Any) -> list[str]:
    values = value if isinstance(value, list) else [value] if value is not None else []
    seen: list[str] = []
    for entry in values:
        if isinstance(entry, dict):
            candidate = entry.get("@value") or entry.get("value") or entry.get("@id")
        else:
            candidate = entry
        if isinstance(candidate, str) and candidate.strip() and candidate not in seen:
            seen.append(candidate.strip())
    return seen


def _iri_values(value: Any) -> list[dict[str, str]]:
    values = value if isinstance(value, list) else [value] if value is not None else []
    seen: list[dict[str, str]] = []
    seen_iris: set[str] = set()
    for entry in values:
        candidate = ""
        if isinstance(entry, dict):
            candidate = str(entry.get("@id", "")).strip()
        elif isinstance(entry, str):
            candidate = entry.strip()
        if candidate and candidate not in seen_iris:
            seen_iris.add(candidate)
            seen.append({"iri": candidate, "label": _short_label(candidate), "anchor": _term_anchor_for_iri(candidate)})
    return seen


def _parent_links(item: dict[str, Any]) -> list[dict[str, str]]:
    parents: list[dict[str, str]] = []
    for predicate, relation in ((RDFS_SUBCLASS, "subclassOf"), (RDFS_SUBPROPERTY, "subPropertyOf")):
        for parent in _iri_values(item.get(predicate)):
            parents.append({"relation": relation, **parent})
    return parents


def _type_labels(item: dict[str, Any]) -> list[str]:
    types = item.get("@type", [])
    if isinstance(types, str):
        types = [types]
    labels = []
    for iri in types:
        if not isinstance(iri, str):
            continue
        label = _short_label(iri)
        if label not in labels:
            labels.append(label)
    return labels


def _reference_category(item: dict[str, Any], iri: str) -> str:
    if iri == H2KG_ONTOLOGY_IRI:
        return "Ontology"
    types = item.get("@type", [])
    if isinstance(types, str):
        types = [types]
    type_set = {t for t in types if isinstance(t, str)}
    if "http://www.w3.org/2002/07/owl#ObjectProperty" in type_set:
        return "Object Properties"
    if "http://www.w3.org/2002/07/owl#DatatypeProperty" in type_set:
        return "Datatype Properties"
    if "http://www.w3.org/2002/07/owl#Class" in type_set:
        return "Classes"
    semantic_order = [
        ("https://w3id.org/h2kg/hydrogen-ontology#Measurement", "Measurements"),
        ("https://w3id.org/h2kg/hydrogen-ontology#Instrument", "Instruments"),
        ("https://w3id.org/h2kg/hydrogen-ontology#Matter", "Materials"),
        ("https://w3id.org/h2kg/hydrogen-ontology#Parameter", "Parameters"),
        ("https://w3id.org/h2kg/hydrogen-ontology#Property", "Properties"),
        ("https://w3id.org/h2kg/hydrogen-ontology#Manufacturing", "Manufacturing / Processes"),
        ("https://w3id.org/h2kg/hydrogen-ontology#Data", "Data / Metadata"),
        ("https://w3id.org/h2kg/hydrogen-ontology#Metadata", "Data / Metadata"),
        ("https://w3id.org/h2kg/hydrogen-ontology#DataPoint", "Data / Metadata"),
        ("https://w3id.org/h2kg/hydrogen-ontology#NormalizationBasis", "Normalization Bases"),
    ]
    for semantic_iri, label in semantic_order:
        if semantic_iri in type_set:
            return label
    return "Other Terms"


def _reference_category_order(category: str) -> int:
    order = {
        "Ontology": 0,
        "Classes": 1,
        "Object Properties": 2,
        "Datatype Properties": 3,
        "Measurements": 4,
        "Instruments": 5,
        "Materials": 6,
        "Parameters": 7,
        "Properties": 8,
        "Manufacturing / Processes": 9,
        "Data / Metadata": 10,
        "Normalization Bases": 11,
        "Other Terms": 12,
    }
    return order.get(category, 99)


def _fragment_for_iri(iri: str) -> str:
    return iri.rsplit("#", 1)[-1] if "#" in iri else iri.rstrip("/").rsplit("/", 1)[-1]


def _term_anchor_for_iri(iri: str) -> str:
    fragment = _fragment_for_iri(iri)
    return fragment or "term"


def _section_anchor(text: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in text).strip("-")
    return slug or "section"


def _short_label(iri: str) -> str:
    if iri == H2KG_ONTOLOGY_IRI:
        return "Hydrogen ontology"
    fragment = _fragment_for_iri(iri)
    return fragment or iri


def _page_template(
    project: dict[str, Any],
    page_title: str,
    body: str,
    page_path: Path,
    docs_root: Path,
    extra_head: str = "",
) -> str:
    home_link = _relative_href(page_path, docs_root / "index.html")
    css_href = _relative_href(page_path, docs_root / "assets" / "style.css")
    asset_base = _relative_href(page_path, docs_root / "assets")
    hero_brand = _hero_brand(project, asset_base)
    nav = f"""
    <nav class="nav">
      <a href="{home_link}">Home</a>
      <a href="{_relative_href(page_path, docs_root / 'pages' / 'user-guide.html')}">User Guide</a>
      <a href="{_relative_href(page_path, docs_root / 'pages' / 'ontology-overview.html')}">Overview</a>
      <a href="{_relative_href(page_path, docs_root / 'pages' / 'explore.html')}">Explore</a>
      <a href="{_relative_href(page_path, docs_root / 'hydrogen-ontology.html')}">Reference</a>
      <a href="{_relative_href(page_path, docs_root / 'pages' / 'architecture-workflow.html')}">Architecture</a>
      <a href="{_relative_href(page_path, docs_root / 'pages' / 'class-index.html')}">Classes</a>
      <a href="{_relative_href(page_path, docs_root / 'pages' / 'property-index.html')}">Properties</a>
      <a href="{_relative_href(page_path, docs_root / 'pages' / 'alignment.html')}">Alignments</a>
      <a href="{_relative_href(page_path, docs_root / 'pages' / 'examples.html')}">Examples</a>
      <a href="{_relative_href(page_path, docs_root / 'pages' / 'import-guide.html')}">Import</a>
      <a href="{_relative_href(page_path, docs_root / 'pages' / 'import-catalog.html')}">Import Catalog</a>
      <a href="{_relative_href(page_path, docs_root / 'pages' / 'quality-dashboard.html')}">Quality</a>
      <a href="{_relative_href(page_path, docs_root / 'pages' / 'developer-guide.html')}">Developer</a>
      <a href="{_relative_href(page_path, docs_root / 'pages' / 'release.html')}">Release</a>
    </nav>
    """
    support_block = _support_block(project, asset_base)
    acknowledgement_block = _acknowledgement_block(project, asset_base)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{page_title} | {project['title']}</title>
  <link rel="stylesheet" href="{css_href}">
  {extra_head}
</head>
<body>
  <header class="hero">
    <div class="wrap">
      <div class="hero-head">
        <div class="hero-copy">
          <p class="eyebrow">{project['short_title']}</p>
          <h1>{page_title}</h1>
          <p class="subtitle">{project.get('subtitle', '')}</p>
        </div>
        {hero_brand}
      </div>
      {support_block}
      {nav}
    </div>
  </header>
  <main class="wrap content">
    {body}
  </main>
  <footer class="footer">
    <div class="wrap">
      {acknowledgement_block}
      <p>{project['title']} | Version {project['version']} | {project['namespace_uri']}</p>
    </div>
  </footer>
</body>
</html>
"""


def _legacy_profile_home() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>H2KG - Ontology for Hydrogen Electrochemical Systems</title>
  <style>
    :root {
      --ink: #10242d;
      --muted: #52656e;
      --line: rgba(16,36,45,0.12);
      --accent: #0d7f83;
      --accent-2: #c86a2b;
      --paper: rgba(255,255,255,0.84);
      --shadow: 0 22px 64px rgba(16,36,45,0.12);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Aptos", "Trebuchet MS", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at 12% 16%, rgba(13,127,131,0.16), transparent 24%),
        radial-gradient(circle at 86% 12%, rgba(200,106,43,0.16), transparent 24%),
        linear-gradient(180deg, #eef7f6 0%, #f8f1e7 100%);
    }
    main { max-width: 1180px; margin: 0 auto; padding: 2rem 1rem 3.5rem; }
    h1, h2 { font-family: "Iowan Old Style", Georgia, serif; letter-spacing: -0.02em; }
    h1 { margin: 0 0 0.8rem; font-size: clamp(2.3rem, 5vw, 4.6rem); line-height: 0.96; max-width: 11ch; text-wrap: balance; }
    p { color: var(--muted); line-height: 1.55; }
    .hero { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(300px, 0.8fr); gap: 1.2rem; align-items: end; }
    .eyebrow { display: inline-block; padding: 0.35rem 0.7rem; border-radius: 999px; background: rgba(255,255,255,0.72); border: 1px solid var(--line); color: var(--accent); font-size: 0.74rem; letter-spacing: 0.14em; text-transform: uppercase; }
    .brand { display: flex; gap: 1rem; align-items: center; margin-bottom: 1rem; }
    .brand img { width: 82px; height: auto; display: block; }
    .hero-card { background: linear-gradient(145deg, rgba(255,255,255,0.78), rgba(255,250,243,0.88)); border: 1px solid var(--line); border-radius: 1.4rem; padding: 1.15rem; box-shadow: var(--shadow); backdrop-filter: blur(10px); }
    .hero-metrics { display: grid; gap: 0.85rem; }
    .metric { display: grid; gap: 0.2rem; }
    .metric strong { color: var(--ink); }
    .grid { display: grid; gap: 1rem; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); margin-top: 1.7rem; }
    .card { background: var(--paper); border: 1px solid var(--line); border-radius: 1.4rem; padding: 1.2rem; box-shadow: var(--shadow); backdrop-filter: blur(10px); }
    .links { display: flex; gap: 0.6rem; flex-wrap: wrap; margin-top: 0.8rem; }
    a {
      text-decoration: none;
      color: white;
      background: linear-gradient(135deg, #10242d, var(--accent));
      border-radius: 999px;
      padding: 0.55rem 0.9rem;
      font-size: 0.92rem;
      font-weight: 700;
      box-shadow: 0 10px 24px rgba(16,36,45,0.15);
    }
    .ghost { color: var(--ink); background: rgba(255,255,255,0.72); border: 1px solid var(--line); box-shadow: none; }
    code { background: rgba(15,109,122,0.08); padding: 0.1rem 0.35rem; border-radius: 4px; }
    @media (max-width: 860px) {
      .hero { grid-template-columns: 1fr; }
      h1 { max-width: 13ch; }
    }
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <div>
        <div class="brand">
          <img src="./pemfc/assets/h2kg-logo.png" alt="H2KG logo">
          <span class="eyebrow">AIMWORKS ontology release</span>
        </div>
        <h1>H2KG for hydrogen electrochemical systems</h1>
        <p>Modern release pages, profile documentation, and machine-readable ontology artifacts for PEMFC and PEMWE research.</p>
        <div class="links">
          <a href="./pages/explore.html">Explore H2KG</a>
          <a href="./hydrogen-ontology.html">Open full reference</a>
          <a href="./pemfc/index.html">Explore PEMFC</a>
          <a href="./pemwe/index.html">Explore PEMWE</a>
          <a class="ghost" href="./pages/release.html">Open release overview</a>
        </div>
      </div>
      <aside class="hero-card hero-metrics">
        <div class="metric"><strong>Shared core</strong><span>Stable H2KG namespace with profile-specific PEMFC and PEMWE views.</span></div>
        <div class="metric"><strong>Standards-aligned</strong><span>EMMO, HDO, QUDT, ChEBI, PROV-O, and DCTERMS integration through the AIMWORKS release pipeline.</span></div>
        <div class="metric"><strong>Publication-ready</strong><span>GitHub Pages documentation, downloadable ontology artefacts, mappings, and quality reports.</span></div>
      </aside>
    </section>
    <div class="grid">
      <article class="card">
        <h2>PEMFC Profile</h2>
        <p>Profile documentation for proton exchange membrane fuel cell experiments, materials, processes, measurements, and data assets.</p>
        <p><strong>Ontology IRI:</strong> <code>https://w3id.org/h2kg/pemfc/hydrogen-ontology</code></p>
        <div class="links">
          <a href="./pemfc/index.html">Open profile home</a>
          <a class="ghost" href="./pemfc/hydrogen-ontology.html">Open reference</a>
          <a class="ghost" href="./pages/core-reference.html">Shared core schema</a>
        </div>
      </article>
      <article class="card">
        <h2>PEMWE Profile</h2>
        <p>Profile documentation for proton exchange membrane water electrolysis experiments, materials, processes, measurements, and data assets.</p>
        <p><strong>Ontology IRI:</strong> <code>https://w3id.org/h2kg/pemwe/hydrogen-ontology</code></p>
        <div class="links">
          <a href="./pemwe/index.html">Open profile home</a>
          <a class="ghost" href="./pemwe/hydrogen-ontology.html">Open reference</a>
          <a class="ghost" href="./pages/core-reference.html">Shared core schema</a>
        </div>
      </article>
    </div>
  </main>
</body>
</html>
"""


def _user_guide_body() -> str:
    return """
    <section class="prose">
      <p>The H2KG application ontology is published conservatively. The recommended maintenance workflow is inspect, split, review mappings, enrich metadata, validate, build docs, then publish.</p>
      <p>Maintain local H2KG terms under the <code>h2kg</code> namespace unless a future migration policy is approved and redirect artifacts are prepared.</p>
      <p>Use QUDT for quantity kinds and units, ChEBI for chemicals when resolvable, and PROV-O plus DCTERMS for release metadata and provenance.</p>
    </section>
    """


def _overview_body(project: dict[str, Any], summary: dict[str, Any], odk: dict[str, Any], hdo: dict[str, Any]) -> str:
    profiles = project.get("profiles", {})
    profile_lines = []
    for key in ("core", "pemfc", "pemwe"):
        profile_cfg = profiles.get(key, {})
        iri = str(profile_cfg.get("ontology_iri", "")).strip()
        if iri:
            profile_lines.append(f"{key.upper()} ontology IRI: {iri}")
    paragraphs = [
        f"{project['title']} is an EMMO-aligned application ontology rather than a broad hydrogen-economy ontology.",
        "Its primary scope is hydrogen electrochemical systems, including PEMFC and PEMWE experiments, materials, processes, measurements, data, and provenance.",
        f"The current release snapshot contains {summary['schema_count']} schema terms and preserves the original h2kg identifiers by default.",
        *profile_lines,
    ]
    architecture = """
    <section class="grid">
      <article class="card">
        <h2>Release Architecture</h2>
        <p>AIMWORKS remains the domain-specific release and documentation layer, while ODK is introduced as a nested standard ontology engineering and QC backend.</p>
        <p>PEMFC and PEMWE profile modules remain AIMWORKS outputs in shadow mode, and ODK does not change public H2KG IRIs unless a later promotion step is explicitly approved.</p>
      </article>
      <article class="card">
        <h2>ODK Shadow Mode</h2>
        <p>Status: <strong>{status}</strong></p>
        <p>Primary artefact: <strong>{artifact}</strong> | Reasoner: <strong>{reasoner}</strong></p>
        <p>{message}</p>
      </article>
      <article class="card">
        <h2>Semantic Division of Labor</h2>
        <p><strong>HDO</strong> is the primary alignment source for Helmholtz-community digital-data concepts such as metadata, identifiers, digital objects, schemas, and validation.</p>
        <p><strong>EMMO / ECHO</strong> remain the scientific and electrochemistry anchors, <strong>QUDT</strong> covers quantities and units, <strong>ChEBI</strong> covers chemistry, and <strong>PROV-O / DCTERMS</strong> remain publication metadata anchors.</p>
        <p class="muted">Reviewed against HDO in the current run: {reviewed}</p>
      </article>
    </section>
    """.format(
        status=escape(str(odk.get("status", "not built"))),
        artifact=escape(str(odk.get("primary_artifact", "base"))),
        reasoner=escape(str(odk.get("reasoner", "ELK"))),
        message=escape(str(odk.get("parity", {}).get("message", "ODK shadow parity has not been computed yet."))),
        reviewed=escape(str(hdo.get("summary", {}).get("reviewed_against_hdo", 0))),
    )
    return f'<section class="prose">{html_paragraphs(paragraphs)}</section>{architecture}'


def _explore_term_href(page_path: Path, docs_root: Path, iri: str) -> str:
    base = _relative_href(page_path, docs_root / "pages" / "explore.html")
    return f"{base}?iri={quote(iri, safe='')}"


def _node_module(record: dict[str, Any]) -> str:
    category = str(record.get("category", ""))
    if category in {"Ontology", "Classes", "Object Properties", "Datatype Properties"}:
        return "schema"
    return "vocabulary"


def _deprecated_status(item: dict[str, Any]) -> str:
    values = item.get("http://www.w3.org/2002/07/owl#deprecated")
    for value in _literal_values(values):
        if value.lower() in {"true", "1", "yes"}:
            return "Deprecated"
    return "Active"


def _node_search_text(record: dict[str, Any], item: dict[str, Any]) -> str:
    bits = [
        record.get("label", ""),
        record.get("anchor", ""),
        canonical_qname(record.get("iri", ""), ""),
        record.get("iri", ""),
        record.get("description", ""),
        *record.get("alt_labels", []),
        *record.get("examples", []),
        *record.get("notes", []),
        *record.get("type_labels", []),
    ]
    for relation_key in ("parents", "domain", "range"):
        for relation in record.get(relation_key, []):
            bits.append(relation.get("label", ""))
            bits.append(relation.get("iri", ""))
    for mapping in record.get("mappings", []):
        bits.append(mapping.get("target_label", ""))
        bits.append(mapping.get("target_iri", ""))
        bits.append(mapping.get("relation", ""))
    values: list[str] = []
    seen: set[str] = set()
    for bit in bits:
        text = str(bit or "").strip()
        if text and text not in seen:
            seen.add(text)
            values.append(text)
    return " ".join(values)


def _external_node_record(iri: str, label: str = "", description: str = "") -> dict[str, Any]:
    qname = canonical_qname(iri, "")
    local_name = _fragment_for_iri(iri)
    resolved_label = label.strip() or (qname if qname and ":" in qname else _short_label(iri))
    return {
        "id": iri,
        "iri": iri,
        "anchor": _term_anchor_for_iri(iri),
        "label": resolved_label,
        "localName": local_name,
        "qname": qname or iri,
        "description": description.strip() or "External aligned term linked from the current H2KG release.",
        "alt_labels": [],
        "examples": [],
        "notes": [],
        "type_labels": ["External"],
        "category": "External Terms",
        "display_class": "External",
        "modules": ["alignments"],
        "local": False,
        "deprecated": "Active",
        "mapping_labels": [],
        "search_text": " ".join(part for part in [resolved_label, local_name, qname, iri, description] if part),
    }


def _link_record(source: str, target: str, predicate: str, value: str, module: str, edge_family: str) -> dict[str, Any]:
    return {
        "source": source,
        "target": target,
        "predicate": predicate,
        "value": value,
        "module": module,
        "edgeFamily": edge_family,
    }


def _build_explorer_dataset(terms: list[dict[str, Any]], items: dict[str, dict[str, Any]]) -> dict[str, Any]:
    local_records = {term["iri"]: term for term in terms}
    nodes: dict[str, dict[str, Any]] = {}
    links: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    ignored_type_iris = {
        "http://www.w3.org/2002/07/owl#Ontology",
        "http://www.w3.org/2002/07/owl#Class",
        "http://www.w3.org/2002/07/owl#ObjectProperty",
        "http://www.w3.org/2002/07/owl#DatatypeProperty",
        "http://www.w3.org/2002/07/owl#AnnotationProperty",
        "http://www.w3.org/2000/01/rdf-schema#Class",
    }

    for iri, record in local_records.items():
        item = items.get(iri, {"@id": iri})
        modules = {_node_module(record)}
        if record.get("mappings"):
            modules.add("alignments")
        if any(not relation.get("iri", "").startswith(H2KG_NS) and relation.get("iri") != H2KG_ONTOLOGY_IRI for relation in [*record.get("parents", []), *record.get("domain", []), *record.get("range", [])]):
            modules.add("alignments")
        qname = canonical_qname(iri, "")
        nodes[iri] = {
            "id": iri,
            "iri": iri,
            "anchor": record["anchor"],
            "label": record["label"],
            "localName": _fragment_for_iri(iri),
            "qname": qname or iri,
            "description": record["description"],
            "alt_labels": record.get("alt_labels", []),
            "examples": record.get("examples", []),
            "notes": record.get("notes", []),
            "type_labels": record.get("type_labels", []),
            "category": record["category"],
            "display_class": record.get("type_labels", [record["category"]])[0] if record.get("type_labels") else record["category"],
            "modules": sorted(modules),
            "local": True,
            "deprecated": _deprecated_status(item),
            "mapping_labels": [str(mapping.get("target_label", "")).strip() for mapping in record.get("mappings", []) if str(mapping.get("target_label", "")).strip()],
        }
        nodes[iri]["search_text"] = _node_search_text(record, item)

    def ensure_external(iri: str, label: str = "", description: str = "") -> None:
        if not iri or iri in nodes or iri.startswith(H2KG_NS) or iri == H2KG_ONTOLOGY_IRI:
            return
        nodes[iri] = _external_node_record(iri, label=label, description=description)

    def add_link(source: str, target: str, predicate: str, value: str, module: str, edge_family: str) -> None:
        if not source or not target or source == target:
            return
        key = (source, target, predicate, module)
        if key not in links:
            links[key] = _link_record(source, target, predicate, value, module, edge_family)

    for iri, record in local_records.items():
        item = items.get(iri, {"@id": iri})
        for relation in record.get("parents", []):
            target_iri = relation.get("iri", "")
            ensure_external(target_iri, relation.get("label", ""))
            add_link(iri, target_iri, relation.get("relation", ""), relation.get("relation", ""), "schema", relation.get("relation", "schema"))
        for relation_key, predicate in ((record.get("domain", []), "domain"), (record.get("range", []), "range")):
            for relation in relation_key:
                target_iri = relation.get("iri", "")
                ensure_external(target_iri, relation.get("label", ""))
                add_link(iri, target_iri, predicate, predicate, "schema", predicate)
        for mapping in record.get("mappings", []):
            target_iri = str(mapping.get("target_iri", "")).strip()
            ensure_external(target_iri, str(mapping.get("target_label", "")).strip(), f"Reviewed {mapping.get('relation', 'mapping')} target.")
            add_link(iri, target_iri, str(mapping.get("relation", "mapping")), canonical_qname(target_iri, ""), "alignments", "mapping")
        types = item.get("@type", [])
        if isinstance(types, str):
            types = [types]
        for type_iri in types:
            if not isinstance(type_iri, str) or type_iri in ignored_type_iris:
                continue
            ensure_external(type_iri, _short_label(type_iri))
            add_link(iri, type_iri, "type", "type", "vocabulary", "type")
        for predicate, value in item.items():
            if not isinstance(predicate, str) or not predicate.startswith(H2KG_NS):
                continue
            for relation in _iri_values(value):
                target_iri = relation.get("iri", "")
                ensure_external(target_iri, relation.get("label", ""))
                add_link(
                    iri,
                    target_iri,
                    predicate,
                    canonical_qname(predicate, _fragment_for_iri(predicate)),
                    "vocabulary",
                    "object_property",
                )

    degrees: dict[str, int] = {iri: 0 for iri in nodes}
    for link in links.values():
        degrees[link["source"]] = degrees.get(link["source"], 0) + 1
        degrees[link["target"]] = degrees.get(link["target"], 0) + 1
    for iri, node in nodes.items():
        node["degree"] = degrees.get(iri, 0)

    module_map: dict[str, dict[str, Any]] = {
        "schema": {
            "id": "schema",
            "label": "Asserted schema",
            "description": "Classes, properties, domains, ranges, and asserted taxonomy links.",
            "nodeCount": sum(1 for node in nodes.values() if "schema" in node.get("modules", [])),
            "edgeCount": sum(1 for link in links.values() if link["module"] == "schema"),
        },
        "vocabulary": {
            "id": "vocabulary",
            "label": "Controlled vocabulary",
            "description": "Curated local H2KG terms outside the compact core schema layer.",
            "nodeCount": sum(1 for node in nodes.values() if "vocabulary" in node.get("modules", [])),
            "edgeCount": sum(1 for link in links.values() if link["module"] == "vocabulary"),
        },
        "alignments": {
            "id": "alignments",
            "label": "Reviewed alignments",
            "description": "Reviewed mappings and directly linked external semantic anchors.",
            "nodeCount": sum(1 for node in nodes.values() if "alignments" in node.get("modules", [])),
            "edgeCount": sum(1 for link in links.values() if link["module"] == "alignments"),
        },
    }

    return {
        "profileLabel": "Whole H2KG namespace",
        "referencePage": "hydrogen-ontology.html",
        "overview": {
            "localNodeCount": sum(1 for node in nodes.values() if node.get("local")),
            "externalNodeCount": sum(1 for node in nodes.values() if not node.get("local")),
            "edgeCount": len(links),
        },
        "modules": list(module_map.values()),
        "nodes": sorted(nodes.values(), key=lambda node: (not bool(node.get("local")), str(node.get("label", "")).lower())),
        "links": sorted(links.values(), key=lambda link: (link["module"], link["source"], link["predicate"], link["target"])),
    }


def _explore_body(project: dict[str, Any], explorer: dict[str, Any], page_path: Path, docs_root: Path) -> str:
    reference_link = _relative_href(page_path, docs_root / "hydrogen-ontology.html")
    release_link = _relative_href(page_path, docs_root / "pages" / "release.html")
    data_href = _relative_href(page_path, docs_root / "data" / "explorer.json")
    modules = explorer.get("modules", [])
    module_html = "".join(
        f"""
        <label class="explorer-module">
          <input type="checkbox" data-explorer-module value="{escape(str(module.get('id', '')))}" checked>
          <span>
            <strong>{escape(str(module.get('label', 'module')))}</strong>
            <small>{escape(str(module.get('description', '')))}</small>
          </span>
          <span class="explorer-module__meta">{module.get('edgeCount', 0)} links</span>
        </label>
        """
        for module in modules
    )
    overview = explorer.get("overview", {})
    return f"""
    <section class="grid">
      <article class="card">
        <p class="eyebrow">Explore</p>
        <h2>Whole-Ontology Search</h2>
        <p>Search the published H2KG namespace with precise ranked suggestions, confirm whether a term exists, and inspect its directly connected graph context without leaving the release package.</p>
        <div class="button-row">
          <a class="inline-button" href="{reference_link}">Open full reference</a>
          <a class="inline-button" href="{release_link}">Release context</a>
        </div>
      </article>
      <article class="card">
        <h2>Explorer Scope</h2>
        <ul class="stats">
          <li><strong>Search scope:</strong> local H2KG terms by default</li>
          <li><strong>Local terms:</strong> {overview.get('localNodeCount', 0)}</li>
          <li><strong>External anchors:</strong> {overview.get('externalNodeCount', 0)}</li>
          <li><strong>Visible link surface:</strong> {overview.get('edgeCount', 0)}</li>
        </ul>
        <p class="muted">The graph starts with the selected term and its direct visible neighborhood. Expansion is progressive and reversible.</p>
      </article>
    </section>
    <section class="explorer-shell" data-explorer-root data-explorer-data="{data_href}" data-reference-page="{reference_link}">
      <aside class="explorer-sidebar">
        <article class="card explorer-panel">
          <p class="eyebrow">Find a term</p>
          <h2>Search</h2>
          <p class="muted">Results prioritize exact ontology term matches, canonical local names, qnames, and curated descriptions before broader descriptive matches.</p>
          <div class="explorer-field">
            <label for="explorer-search-input">Search the ontology</label>
            <input id="explorer-search-input" type="search" data-explorer-search placeholder="e.g., ionomer, FixedBedReactor, acid base titration measurement">
          </div>
          <div class="explorer-note" data-explorer-search-status>Suggested starting points appear here when the search box is empty.</div>
          <label class="explorer-toggle">
            <input type="checkbox" data-explorer-toggle="includeExternalSearch">
            Include aligned external terms in suggestions
          </label>
          <label class="explorer-toggle">
            <input type="checkbox" data-explorer-toggle="showExternalNeighbors">
            Show directly linked external terms in the graph
          </label>
          <div class="explorer-results" data-explorer-results>
            <div class="explorer-empty">Start typing to search the published ontology.</div>
          </div>
        </article>
        <article class="card explorer-panel">
          <p class="eyebrow">Graph filters</p>
          <h3>Release modules</h3>
          <div class="explorer-module-grid">{module_html}</div>
          <div class="explorer-toolbar">
            <button type="button" class="inline-button inline-button--ghost" data-explorer-action="undo" disabled>Undo</button>
            <button type="button" class="inline-button inline-button--ghost" data-explorer-action="reset">Reset graph</button>
            <button type="button" class="inline-button inline-button--ghost" data-explorer-action="clear">Clear</button>
          </div>
        </article>
        <article class="card explorer-panel">
          <p class="eyebrow">Traversal</p>
          <h3>History</h3>
          <div class="explorer-trail" data-explorer-trail>
            <div class="explorer-empty">The traversal trail appears after you select a term.</div>
          </div>
        </article>
      </aside>
      <section class="explorer-main">
        <article class="card explorer-panel">
          <div class="explorer-panel__head">
            <div>
              <p class="eyebrow">Graph</p>
              <h2>Direct neighborhood</h2>
            </div>
            <div class="explorer-kpis">
              <div><span>Visible nodes</span><strong data-explorer-count="nodes">0</strong></div>
              <div><span>Visible links</span><strong data-explorer-count="edges">0</strong></div>
              <div><span>Expanded nodes</span><strong data-explorer-count="expanded">0</strong></div>
            </div>
          </div>
          <p class="explorer-note" data-explorer-graph-note>Select a term to render its graph neighborhood.</p>
          <div class="explorer-chart" data-explorer-chart></div>
        </article>
        <div class="explorer-detail-grid">
          <article class="card explorer-panel">
            <p class="eyebrow">Selected term</p>
            <div data-explorer-inspector>
              <div class="explorer-empty">Pick a term to inspect its stable IRI, definition, and graph role.</div>
            </div>
          </article>
          <article class="card explorer-panel">
            <p class="eyebrow">Visible relations</p>
            <div data-explorer-relations>
              <div class="explorer-empty">Visible relations will appear here after you select a term.</div>
            </div>
          </article>
        </div>
      </section>
    </section>
    """


def _class_body(classes: list[dict[str, Any]]) -> str:
    cards = "".join(
        f"<article class='term-card'><h2>{item['label']}</h2><p class='iri'>{item['iri']}</p><p>{item['description']}</p><p><strong>Mappings:</strong> {', '.join(item['mappings']) or 'None'}</p></article>"
        for item in classes
    )
    return f"<section class='list-grid'>{cards}</section>"


def _property_body(properties: list[dict[str, Any]]) -> str:
    cards = "".join(
        f"<article class='term-card'><h2>{item['label']}</h2><p class='iri'>{item['iri']}</p><p>{item['description']}</p><p><strong>Domain:</strong> {item['domain'] or 'not asserted'}</p><p><strong>Range:</strong> {item['range'] or 'not asserted'}</p></article>"
        for item in properties
    )
    return f"<section class='list-grid'>{cards}</section>"


def _load_alignment_summary(reports_dir: Path) -> dict[str, Any]:
    path = reports_dir / "alignment_summary.json"
    if path.exists():
        return load_json(path)
    return {
        "accepted_count": 0,
        "exploratory_count": 0,
        "accepted_by_relation": {},
        "rejected_by_rule": {},
        "accepted_by_source": {},
    }


def _alignment_body(mappings: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    stats = f"""
    <section class='grid'>
      <article class='card'><h2>Accepted Alignments</h2><p><strong>{summary.get('accepted_count', len(mappings))}</strong> review-ready mappings are included in the published alignment layer.</p></article>
      <article class='card'><h2>Exploratory Candidates</h2><p><strong>{summary.get('exploratory_count', 0)}</strong> exploratory candidates are kept out of the published TTL and remain internal review material only.</p></article>
    </section>
    """
    cards = "".join(
        f"<article class='term-card'><h2>{item['local_label']}</h2><p class='iri'>{item['local_iri']}</p><p><strong>{item['relation']}</strong> {item['target_iri']}</p><p>{item['rationale']}</p></article>"
        for item in mappings[:60]
    )
    return stats + f"<section class='list-grid'>{cards}</section>"


def _examples_body(examples: list[dict[str, Any]]) -> str:
    cards = "".join(
        f"<article class='term-card'><h2>{item['label']}</h2><p class='iri'>{item['iri']}</p><p>{item['description']}</p></article>"
        for item in examples[:60]
    )
    return f"<section class='list-grid'>{cards}</section>"


def _namespace_reference_body(project: dict[str, Any], terms: list[dict[str, Any]], page_path: Path, docs_root: Path) -> str:
    release_link = _relative_href(page_path, docs_root / "pages" / "release.html")
    core_link = _relative_href(page_path, docs_root / "pages" / "core-reference.html")
    pemfc_link = _relative_href(page_path, docs_root / "pemfc" / "hydrogen-ontology.html")
    pemwe_link = _relative_href(page_path, docs_root / "pemwe" / "hydrogen-ontology.html")
    explore_link = _relative_href(page_path, docs_root / "pages" / "explore.html")
    return f"""
    <section class="grid">
      <article class="card">
        <h2>H2KG Namespace Reference</h2>
        <p>This page is the canonical human-readable reference for the full H2KG namespace. It is intended to be the future browser landing page for <code>{escape(project.get('ontology_iri', H2KG_ONTOLOGY_IRI))}</code> once the namespace is registered in w3id.</p>
        <p><strong>Ontology IRI:</strong> <code>{escape(project.get('ontology_iri', H2KG_ONTOLOGY_IRI))}</code></p>
        <p><strong>Namespace:</strong> <code>{escape(project.get('namespace_uri', H2KG_NS))}</code></p>
        <p><strong>Rendered terms:</strong> {len(terms)}</p>
        <div class="button-row">
          <a class="inline-button" href="{explore_link}">Explore / Search</a>
          <a class="inline-button" href="{release_link}">Release</a>
          <a class="inline-button" href="{core_link}">Core schema</a>
        </div>
      </article>
      <article class="card">
        <h2>Resolver Readiness</h2>
        <p>When <code>/h2kg/hydrogen-ontology</code> is registered in w3id, browser requests should resolve to this page, while RDF-aware requests should resolve to the full namespace artefacts rather than the smaller schema-only subset.</p>
        <p class="muted">Profile-specific namespace views remain available separately for PEMFC and PEMWE.</p>
        <div class="button-row">
          <a class="inline-button" href="{pemfc_link}">PEMFC reference</a>
          <a class="inline-button" href="{pemwe_link}">PEMWE reference</a>
        </div>
      </article>
    </section>
    {_reference_sections(terms, page_path, docs_root)}
    """


def _core_reference_body(project: dict[str, Any], terms: list[dict[str, Any]], page_path: Path, docs_root: Path) -> str:
    release_link = _relative_href(page_path, docs_root / "pages" / "release.html")
    namespace_link = _relative_href(page_path, docs_root / "hydrogen-ontology.html")
    explore_link = _relative_href(page_path, docs_root / "pages" / "explore.html")
    return f"""
    <section class="grid">
      <article class="card">
        <h2>Core H2KG Reference</h2>
        <p>This page captures the compact shared H2KG schema subset: ontology header, schema classes, and schema properties. It is useful as a concise architectural reference, but it is not the resolver target for the full H2KG namespace.</p>
        <p><strong>Ontology IRI:</strong> <code>{escape(project.get('ontology_iri', H2KG_ONTOLOGY_IRI))}</code></p>
        <p><strong>Namespace:</strong> <code>{escape(project.get('namespace_uri', H2KG_NS))}</code></p>
        <p><strong>Term count:</strong> {len(terms)}</p>
        <div class="button-row">
          <a class="inline-button" href="{explore_link}">Explore / Search</a>
          <a class="inline-button" href="{release_link}">Release</a>
          <a class="inline-button" href="{namespace_link}">Full namespace</a>
        </div>
      </article>
      <article class="card">
        <h2>Schema Scope</h2>
        <p>This page remains valuable for ontology engineering, governance, and lightweight schema browsing. The future resolver target for <code>/h2kg/hydrogen-ontology</code> should instead be the full namespace reference page.</p>
        <p class="muted">Current state: documentation, machine artefacts, and resolver infrastructure are publicly established, and the full namespace reference page is the active resolver target.</p>
      </article>
    </section>
    {_reference_sections(terms, page_path, docs_root)}
    """


def _profile_reference_body(project: dict[str, Any], profile_key: str, terms: list[dict[str, Any]], odk: dict[str, Any], hdo: dict[str, Any], page_path: Path, docs_root: Path) -> str:
    profiles = project.get("profiles", {})
    profile_cfg = profiles.get(profile_key, {})
    release_link = _relative_href(page_path, docs_root / "pages" / "release.html")
    quality_link = _relative_href(page_path, docs_root / "pages" / "quality-dashboard.html")
    namespace_link = _relative_href(page_path, docs_root / "hydrogen-ontology.html")
    explore_link = _relative_href(page_path, docs_root / "pages" / "explore.html")
    title = escape(str(profile_cfg.get('title', profile_key.upper())))
    return f"""
    <section class="grid">
      <article class="card">
        <h2>{title}</h2>
        <p>{escape(_profile_description(profile_key, profile_cfg))}</p>
        <p><strong>Ontology IRI:</strong> <code>{escape(str(profile_cfg.get('ontology_iri', '')))}</code></p>
        <p><strong>Namespace:</strong> <code>{escape(str(profile_cfg.get('namespace_uri', '')))}</code></p>
        <p><strong>Rendered terms:</strong> {len(terms)}</p>
        <div class="button-row">
          <a class="inline-button" href="{explore_link}">Explore / Search</a>
          <a class="inline-button" href="{release_link}">Release</a>
          <a class="inline-button" href="{quality_link}">Quality</a>
        </div>
      </article>
      <article class="card">
        <h2>Profile Reference Scope</h2>
        <p>This page presents the {title} as a structured reference, grouping all profile-visible terms into navigable sections instead of one flat list. It is the intended future human-readable landing page for the {title} namespace.</p>
        <p class="muted">ODK shadow-mode status: {escape(_shadow_mode_summary(odk))}</p>
        <p class="muted">HDO-reviewed terms in the current run: {hdo.get('summary', {}).get('reviewed_against_hdo', 0)}</p>
        <div class="button-row">
          <a class="inline-button" href="{namespace_link}">Full H2KG namespace</a>
        </div>
      </article>
    </section>
    {_reference_sections(terms, page_path, docs_root)}
    """


def _reference_sections(terms: list[dict[str, Any]], page_path: Path, docs_root: Path) -> str:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for term in terms:
        grouped.setdefault(term["category"], []).append(term)
    toc = "".join(
        f"<li><a href='#{_section_anchor(category)}'>{escape(category)}</a> <span class='muted'>({len(entries)})</span></li>"
        for category, entries in sorted(grouped.items(), key=lambda item: _reference_category_order(item[0]))
    )
    sections = "".join(
        f"""
        <section class="reference-section" id="{_section_anchor(category)}">
          <div class="reference-section-head">
            <h2>{escape(category)}</h2>
            <p class="muted">{len(entries)} terms</p>
          </div>
          {''.join(_reference_term_block(term, _explore_term_href(page_path, docs_root, term["iri"])) for term in entries)}
        </section>
        """
        for category, entries in sorted(grouped.items(), key=lambda item: _reference_category_order(item[0]))
    )
    return f"""
    <section class="grid">
      <article class="card reference-toc">
        <h2>Reference Contents</h2>
        <ul class="toc-list">{toc}</ul>
      </article>
    </section>
    {sections}
    """


def _reference_term_block(term: dict[str, Any], explore_href: str = "") -> str:
    meta_rows = [
        ("IRI", f"<code>{escape(term['iri'])}</code>"),
        ("Type", escape(', '.join(term.get("type_labels", [])) or term["category"])),
    ]
    if explore_href:
        meta_rows.append(("Explore", f"<a class='inline-button inline-button--small' href='{escape(explore_href)}'>Open in Explorer</a>"))
    if term.get("alt_labels"):
        meta_rows.append(("altLabel", escape("; ".join(term["alt_labels"]))))
    parent_rows = _reference_relation_text(term.get("parents", []))
    subclass_rows = _reference_relation_text(term.get("subclasses", []))
    subproperty_rows = _reference_relation_text(term.get("subproperties", []))
    domain_rows = _reference_relation_text(term.get("domain", []))
    range_rows = _reference_relation_text(term.get("range", []))
    mapping_rows = "".join(_reference_mapping_item(item) for item in term.get("mappings", []))
    note_block = "".join(f"<p>{escape(note)}</p>" for note in term.get("notes", []))
    example_block = "".join(f"<p>{escape(example)}</p>" for example in term.get("examples", []))
    legacy_anchor = _section_anchor(term["anchor"])
    alias_anchor = f"<span id=\"{escape(legacy_anchor)}\" class=\"anchor-alias\" aria-hidden=\"true\"></span>" if legacy_anchor != term["anchor"] else ""
    return f"""
    <article class="reference-term" id="{escape(term['anchor'])}">
      {alias_anchor}
      <h3>{escape(term['label'])}</h3>
      <dl class="reference-meta">
        {''.join(f'<div><dt>{escape(label)}</dt><dd>{value}</dd></div>' for label, value in meta_rows)}
      </dl>
      <p class="reference-definition">{escape(term['description'])}</p>
      <dl class="reference-relations">
        {_reference_relation_row('subclassOf / subPropertyOf', parent_rows)}
        {_reference_relation_row('subclasses', subclass_rows)}
        {_reference_relation_row('subproperties', subproperty_rows)}
        {_reference_relation_row('domain', domain_rows)}
        {_reference_relation_row('range', range_rows)}
      </dl>
      {_reference_mapping_block(mapping_rows)}
      {_reference_optional_block('Note', note_block)}
      {_reference_optional_block('Example', example_block)}
    </article>
    """


def _reference_relation_row(label: str, html: str) -> str:
    if not html:
        return ""
    return f"<div><dt>{escape(label)}</dt><dd>{html}</dd></div>"


def _reference_relation_text(values: list[dict[str, str]]) -> str:
    if not values:
        return ""
    return ", ".join(
        f"<a href='#{escape(item.get('anchor') or _term_anchor_for_iri(item['iri']))}'>{escape(item['label'])}</a>"
        if item.get("iri", "").startswith(H2KG_NS) or item.get("iri") == H2KG_ONTOLOGY_IRI
        else f"<code>{escape(item['iri'])}</code>"
        for item in values
    )


def _reference_mapping_block(rows: str) -> str:
    if not rows:
        return ""
    return f"<section class='reference-subblock'><h4>Mappings</h4><ul>{rows}</ul></section>"


def _reference_mapping_item(item: dict[str, Any]) -> str:
    target_label = str(item.get("target_label", "")).strip()
    suffix = f" <span class='muted'>({escape(target_label)})</span>" if target_label else ""
    return f"<li><strong>{escape(str(item.get('relation', 'mapping')))}</strong> <code>{escape(str(item.get('target_iri', '')))}</code>{suffix}</li>"


def _reference_optional_block(title: str, content: str) -> str:
    if not content:
        return ""
    return f"<section class='reference-subblock'><h4>{escape(title)}</h4>{content}</section>"


def _release_body(release: dict[str, Any], odk: dict[str, Any], hdo: dict[str, Any], page_path: Path, docs_root: Path) -> str:
    artifacts = "".join(f"<li>{escape(str(item))}</li>" for item in release.get("artifacts", []))
    odk_base = _relative_href(page_path, docs_root / "odk")
    odk_artifacts = _odk_artifact_cards(odk, odk_base)
    gates = _render_rows(odk.get("promotion_gates", []))
    parity = odk.get("parity", {})
    publication = release.get("publication_evidence", {})
    promotion_state = str(odk.get("promotion_state", "shadow"))
    publication_established = publication.get("publication_status") == "published" and publication.get("resolver_status") == "established"
    artifacts_fallback = (
        "<li>Public release artefacts are established and synchronized with the current resolver-backed publication.</li>"
        if publication_established
        else "<li>Local release artefacts are prepared, but public publication establishment is still pending.</li>"
    )
    odk_intro = (
        "ODK artefacts are now promoted and serve as the accepted machine release surface for comparison, QC, and downstream tooling."
        if promotion_state == "promoted"
        else "ODK remains in shadow mode. These machine artefacts are generated in parallel for comparison, QC, and downstream tooling."
    )
    odk_status = "promoted" if promotion_state == "promoted" else f"{escape(str(odk.get('mode', 'shadow')))} (informational)"
    return f"""
    <section class="grid">
      <article class="card">
        <h2>Release Readiness</h2>
        <p>{escape(str(release.get('summary', 'No release summary available.')))}</p>
        <p>The detailed quality and transparency view is published on the <a href="quality-dashboard.html">Quality Dashboard</a>.</p>
      </article>
      <article class="card">
        <h2>FAIR Snapshot</h2>
        <ul class="stats">
          <li><strong>{release.get('findable', 0)}</strong>/100 Findable</li>
          <li><strong>{release.get('accessible', 0)}</strong>/100 Accessible</li>
          <li><strong>{release.get('interoperable', 0)}</strong>/100 Interoperable</li>
          <li><strong>{release.get('reusable', 0)}</strong>/100 Reusable</li>
        </ul>
      </article>
      <article class="card">
        <h2>AIMWORKS Artifacts</h2>
        <ul>{artifacts or artifacts_fallback}</ul>
      </article>
    </section>
    <section class="stack">
      <article class="card">
        <h2>ODK Release Artefacts</h2>
        <p class="muted">{escape(odk_intro)}</p>
        {odk_artifacts}
      </article>
      <article class="card">
        <h2>ODK Release Status</h2>
        <ul class="stats">
          <li><strong>Current authority:</strong> {escape(str(odk.get('authority', 'AIMWORKS pipeline')))}</li>
          <li><strong>ODK status:</strong> {odk_status}</li>
          <li><strong>Reasoner:</strong> {escape(str(odk.get('reasoner', 'ELK')))}</li>
          <li><strong>ODK version:</strong> {escape(str(odk.get('odk_version', 'shadow scaffold')))}</li>
          <li><strong>Parity:</strong> {escape(str(parity.get('status', 'under review')))}</li>
        </ul>
        <p>{escape(_shadow_mode_summary(odk))}</p>
        {gates}
      </article>
      <article class="card">
        <h2>Publication Establishment</h2>
        {_render_rows(_publication_rows(publication))}
      </article>
      <article class="card">
        <h2>ODK and HDO Integration</h2>
        <ul class="stats">
          <li><strong>HDO import status:</strong> {_hdo_import_status(odk)}</li>
          <li><strong>Last refresh:</strong> {_hdo_import_refresh(odk)}</li>
          <li><strong>Included in current ODK build:</strong> {_hdo_import_included(odk)}</li>
          <li><strong>HDO-reviewed local terms:</strong> {hdo.get('summary', {}).get('reviewed_against_hdo', 0)}</li>
          <li><strong>Aligned to HDO:</strong> {hdo.get('summary', {}).get('aligned_to_hdo', 0)}</li>
        </ul>
        <p>HDO is the primary alignment source for data, metadata, digital-object, information-profile, identifier, schema, and validation concepts in H2KG.</p>
        <p class="muted">{escape(str(hdo.get('cache_note', '')))}</p>
      </article>
    </section>
    """


def _quality_body(release: dict[str, Any], odk: dict[str, Any], hdo: dict[str, Any]) -> str:
    explanations = release.get("section_explanations", {})
    freshness = release.get("freshness", {})
    publication = release.get("publication_evidence", {})
    current_status_rows = [
        {
            "label": "Overall validation",
            "status": _row_status(release.get("validation_signals", []), "Overall validation status", "watch"),
            "value": _row_value(release.get("validation_signals", []), "Overall validation status", "not assessed"),
            "detail": _row_detail(release.get("validation_signals", []), "Overall validation status", ""),
        },
        {
            "label": "SHACL",
            "status": _row_status(release.get("validation_signals", []), "SHACL conforms", "watch"),
            "value": _row_value(release.get("validation_signals", []), "SHACL conforms", "not assessed"),
            "detail": _row_detail(release.get("validation_signals", []), "SHACL conforms", ""),
        },
        {
            "label": "ODK parity",
            "status": "good" if odk.get("parity", {}).get("status") == "aligned" else "watch",
            "value": odk.get("parity", {}).get("status", "under review"),
            "detail": _shadow_mode_summary(odk),
        },
        {
            "label": "Publication establishment",
            "status": "good" if publication.get("publication_status") == "published" and publication.get("resolver_status") == "established" else "watch",
            "value": "published" if publication.get("publication_status") == "published" else "pending",
            "detail": "Public FAIR credit requires explicitly established publication and resolver infrastructure, not just local build artefacts.",
        },
        {
            "label": "Release build freshness",
            "status": freshness.get("status", "watch"),
            "value": freshness.get("value", "unknown"),
            "detail": freshness.get("detail", "Report freshness has not been computed."),
        },
    ]
    odk_rows = [
        {
            "label": "ROBOT status",
            "status": odk.get("robot_summary", {}).get("status", "watch"),
            "value": odk.get("robot_summary", {}).get("reasoning_status", "not built"),
            "detail": odk.get("robot_summary", {}).get("detail", ""),
        },
        {
            "label": "ROBOT errors",
            "status": "good" if odk.get("robot_summary", {}).get("errors", 0) == 0 else "action",
            "value": str(odk.get("robot_summary", {}).get("errors", 0)),
            "detail": "Shadow-mode ROBOT summary from the nested ODK workbench.",
        },
        {
            "label": "ROBOT warnings",
            "status": "watch" if odk.get("robot_summary", {}).get("warnings", 0) else "good",
            "value": str(odk.get("robot_summary", {}).get("warnings", 0)),
            "detail": "Warnings indicate shadow scaffolding or follow-up work still required before promotion.",
        },
        {
            "label": "Import refresh health",
            "status": "good" if all(item.get("required") is False or item.get("enabled") for item in odk.get("imports", [])) else "action",
            "value": f"{sum(1 for item in odk.get('imports', []) if item.get('enabled'))} configured",
            "detail": "Imports are tracked through the nested ODK workbench and surfaced here alongside H2KG-specific checks.",
        },
        {
            "label": "Parity status",
            "status": "good" if odk.get("parity", {}).get("status") == "aligned" else "watch",
            "value": odk.get("parity", {}).get("status", "under review"),
            "detail": odk.get("parity", {}).get("message", ""),
        },
        {
            "label": "IRI drift",
            "status": "good" if not odk.get("parity", {}).get("iri_drift", False) else "action",
            "value": "none" if not odk.get("parity", {}).get("iri_drift", False) else "detected",
            "detail": "Shadow mode should preserve existing H2KG identifiers.",
        },
        {
            "label": "HDO review coverage",
            "status": "good" if hdo.get("summary", {}).get("reviewed_against_hdo", 0) > 0 else "watch",
            "value": str(hdo.get("summary", {}).get("reviewed_against_hdo", 0)),
            "detail": "Local H2KG terms reviewed against HDO for data, metadata, identifier, schema, validation, and digital-object semantics.",
        },
        {
            "label": "HDO mapping coverage",
            "status": "good" if hdo.get("summary", {}).get("aligned_to_hdo", 0) > 0 else "watch",
            "value": str(hdo.get("summary", {}).get("aligned_to_hdo", 0)),
            "detail": "Mappings or reuse proposals that currently point to HDO anchors.",
        },
        {
            "label": "H2KG terms still local after HDO review",
            "status": "optional" if hdo.get("summary", {}).get("stayed_local", 0) > 0 else "good",
            "value": str(hdo.get("summary", {}).get("stayed_local", 0)),
            "detail": "Informational count of reviewed terms intentionally kept local until direct HDO reuse is accepted or a more precise HDO target is loaded.",
        },
    ]
    return f"""
    <section class="prose">
      <p>{escape(str(release.get('summary', 'No quality summary available.')))}</p>
    </section>
    <section class="grid">
      <article class="card">
        <h2>Current Release Status</h2>
        <p class="muted">This summary shows the current release state using a public-first FAIR interpretation together with the current ODK governance and QC state.</p>
        {_render_rows(current_status_rows)}
      </article>
      <article class="card">
        <h2>Report Freshness</h2>
        <p class="muted">These timestamps help confirm that the dashboard is rendering one coherent build rather than mixing older report files.</p>
        {_render_rows(freshness.get('rows', []))}
      </article>
    </section>
    <section class="stack">
      <article class="card">
        <h2>FAIR Signals</h2>
        <p class="muted">{escape(str(explanations.get('fair_signals', 'FAIR signals use a public-first release interpretation rather than treating local build artifacts as proof of public publication.')))}</p>
        {_render_rows(release.get('fair_signals', []))}
      </article>
      <article class="card">
        <h2>External Service Status</h2>
        <p class="muted">{escape(str(explanations.get('transparency_hooks', 'External assessment hooks report what third-party services returned, or state clearly when they were unavailable.')))}</p>
        {_render_rows(release.get('transparency_hooks', []))}
      </article>
      <article class="card">
        <h2>ODK / ROBOT QC</h2>
        <p class="muted">ODK / ROBOT signals reflect standard ontology engineering QC and are reported in addition to H2KG-specific FAIR and publication checks.</p>
        {_render_rows(odk_rows)}
      </article>
      <article class="card">
        <h2>FOOPS! Assessment</h2>
        <p class="muted">FOOPS! is an external FAIR-oriented ontology validator. It is informative when reachable, but not authoritative for release gating. In file mode it does not run accessibility checks.</p>
        {_foops_details(release.get('foops', {}))}
      </article>
      <article class="card">
        <h2>OOPS! Pitfalls</h2>
        <p class="muted">OOPS! is an external ontology pitfall scanner. Service errors are shown as external availability problems rather than as ontology defects or zero pitfalls.</p>
        {_oops_details(release.get('oops', {}))}
      </article>
      <article class="card">
        <h2>Validation Signals</h2>
        <p class="muted">{escape(str(explanations.get('validation_signals', 'Validation signals summarize local structural and metadata checks against the release candidate ontology.')))}</p>
        {_render_rows(release.get('validation_signals', []))}
      </article>
      <article class="card">
        <h2>Publication Assets</h2>
        <p class="muted">{escape(str(explanations.get('publication_assets', 'Publication asset rows show whether files were generated in the current run rather than assuming they exist.')))}</p>
        {_render_rows(release.get('publication_assets', []))}
      </article>
      <article class="card">
        <h2>Publication Establishment</h2>
        <p class="muted">These rows separate locally prepared publication artifacts from explicitly established public publication infrastructure.</p>
        {_render_rows(_publication_rows(publication))}
      </article>
    </section>
    """


def _import_guide_body(odk: dict[str, Any], hdo: dict[str, Any]) -> str:
    return f"""
    <section class="grid">
      <article class="card">
        <h2>Nested ODK Import Flow</h2>
        <p>Imports are refreshed through the nested ODK workbench and then surfaced through the AIMWORKS release pipeline.</p>
        <ol class="ordered">
          <li>Open <code>ontology_release/odk/src/ontology/</code>.</li>
          <li>Run <code>run.bat make refresh-imports</code>.</li>
          <li>Review generated import modules under <code>ontology_release/odk/src/ontology/imports/</code>.</li>
          <li>Run the normal AIMWORKS release pipeline so the refreshed import status is copied into <code>output/odk/</code> and reflected in the site.</li>
        </ol>
      </article>
      <article class="card">
        <h2>Shadow Mode Context</h2>
        <p>ODK is currently operating in <strong>{escape(str(odk.get('mode', 'shadow')))}</strong> mode. The AIMWORKS pipeline remains authoritative while ODK manages standard machine artefacts and import/QC infrastructure in parallel.</p>
        <p><strong>HDO role:</strong> HDO is the preferred Helmholtz-community source for data-management, metadata, identifier, digital-object, information-profile, schema, and validation concepts.</p>
        <p class="muted">Current HDO-reviewed term count: {hdo.get('summary', {}).get('reviewed_against_hdo', 0)}</p>
      </article>
    </section>
    """


def _import_catalog_body(odk: dict[str, Any]) -> str:
    rows = []
    for item in odk.get("imports", []):
        rows.append(
            f"""
            <tr>
              <td>{escape(str(item.get('title', item.get('id', ''))))}</td>
              <td><code>{escape(str(item.get('source_iri', '')))}</code></td>
              <td><code>{escape(str(item.get('local_cache', '')))}</code></td>
              <td><code>{escape(str(item.get('product_id', '')))}</code></td>
              <td>{'required' if item.get('required') else 'optional'}</td>
              <td>{escape(str(item.get('last_refresh_status', '')))}</td>
              <td>{'yes' if item.get('included_in_release') else 'no'}</td>
              <td>{escape(str(item.get('semantic_role', '')))}</td>
            </tr>
            """
        )
    body = "".join(rows) or "<tr><td colspan='8'>No ODK import data available.</td></tr>"
    return f"""
    <section class="card">
      <h2>ODK-Managed Import Catalog</h2>
      <div class="table-wrap">
        <table class="catalog-table">
          <thead>
            <tr>
              <th>Import</th>
              <th>Source IRI</th>
              <th>Local cache</th>
              <th>ODK product</th>
              <th>Requirement</th>
              <th>Last refresh</th>
              <th>Included</th>
              <th>Semantic role</th>
            </tr>
          </thead>
          <tbody>{body}</tbody>
        </table>
      </div>
    </section>
    """


def _developer_body(odk: dict[str, Any], hdo: dict[str, Any]) -> str:
    commands = """
    <ul class="command-list">
      <li><code>ontology_release/odk/src/ontology/run.bat make odkversion</code></li>
      <li><code>ontology_release/odk/src/ontology/run.bat make test</code></li>
      <li><code>ontology_release/odk/src/ontology/run.bat make refresh-imports</code></li>
      <li><code>ontology_release/odk/src/ontology/run.bat make prepare_release</code></li>
      <li><code>ontology_release/odk/src/ontology/run.bat make validate_profile_h2kg-edit.owl</code></li>
    </ul>
    """
    return f"""
    <section class="grid">
      <article class="card">
        <h2>ODK Operations</h2>
        <p>The nested ODK project lives under <code>ontology_release/odk/</code>. Its outputs are copied into <code>ontology_release/output/odk/</code> and then rendered through the AIMWORKS docs site.</p>
        {commands}
      </article>
      <article class="card">
        <h2>Ownership Boundary</h2>
        <p>ODK handles edit-file lifecycle, imports, ROBOT-oriented QC, and standard machine releases. The Python release pipeline still owns schema/example separation, mappings, FAIR reporting, custom docs, profile modules, w3id assets, and the release bundle.</p>
        <p><strong>Architecture note:</strong> ODK is nested and intentionally not allowed to overwrite the AIMWORKS repo-root workflow structure.</p>
      </article>
      <article class="card">
        <h2>Current ODK Status</h2>
        <p>Status: <strong>{escape(str(odk.get('status', 'not built')))}</strong></p>
        <p>Last built: <strong>{escape(str(odk.get('last_built', 'unknown')))}</strong></p>
      </article>
      <article class="card">
        <h2>When to Use HDO vs EMMO vs PROV / DCTERMS</h2>
        <ul class="stats">
          <li><strong>HDO first:</strong> data, metadata, identifier, digital object, information profile, schema, validation, and provenance-record concepts.</li>
          <li><strong>EMMO / ECHO first:</strong> scientific process, material, measurement, and electrochemistry semantics.</li>
          <li><strong>QUDT first:</strong> quantity kinds, quantity values, and units.</li>
          <li><strong>ChEBI first:</strong> chemical entities.</li>
          <li><strong>PROV-O / DCTERMS first:</strong> publication provenance and ontology release metadata.</li>
        </ul>
        <p class="muted">Current HDO-aligned terms in this run: {hdo.get('summary', {}).get('aligned_to_hdo', 0)}</p>
      </article>
      <article class="card">
        <h2>Optional Local QC Hooks</h2>
        <p>Optional local checks are non-blocking and currently not required for release promotion.</p>
        <ul class="stats">
          <li><strong>OWL consistency hook:</strong> install <code>owlready2</code> to enable it locally.</li>
          <li><strong>EMMO checks:</strong> install <code>EMMOntoPy</code> to enable them locally.</li>
          <li><strong>CI default:</strong> these hooks remain optional unless the project explicitly promotes them into required CI dependencies.</li>
        </ul>
      </article>
    </section>
    """


def _architecture_body(project: dict[str, Any], odk: dict[str, Any], hdo: dict[str, Any]) -> str:
    return f"""
    <section class="grid">
      <article class="card">
        <h2>AIMWORKS Layer</h2>
        <p>AIMWORKS remains the domain-specific documentation and release layer for H2KG, including FAIR reporting, profile generation for PEMFC and PEMWE, w3id assets, release bundles, and custom HTML docs.</p>
      </article>
      <article class="card">
        <h2>ODK Layer</h2>
        <p>ODK now runs as a nested shadow-mode ontology engineering backend for edit-file management, import refresh, ROBOT-oriented QC, and standard machine artefacts such as <code>base</code>, <code>full</code>, and <code>simple</code>.</p>
        <p>Current status: <strong>{escape(str(odk.get('mode', 'shadow')))}</strong>. Public H2KG IRIs remain unchanged.</p>
      </article>
      <article class="card">
        <h2>Profile Modules</h2>
        <p>The <code>pemfc</code> and <code>pemwe</code> profiles remain AIMWORKS outputs in v1. ODK does not replace them or publish a competing documentation site.</p>
        <p>{escape(str(project.get('title', 'H2KG')))} keeps the current profile-oriented website while gaining a standards-based machine release and QC backend.</p>
      </article>
      <article class="card">
        <h2>HDO Integration</h2>
        <p>HDO is integrated as the Helmholtz-community anchor for digital-data concepts, complementing EMMO/ECHO, QUDT, ChEBI, and PROV-O / DCTERMS.</p>
        <p><strong>Reviewed against HDO:</strong> {hdo.get('summary', {}).get('reviewed_against_hdo', 0)} | <strong>Aligned:</strong> {hdo.get('summary', {}).get('aligned_to_hdo', 0)}</p>
      </article>
    </section>
    """


def _profile_home_body(project: dict[str, Any], profile_key: str, odk: dict[str, Any], hdo: dict[str, Any], page_path: Path, docs_root: Path) -> str:
    profiles = project.get("profiles", {})
    profile_cfg = profiles.get(profile_key, {})
    parity_status = odk.get("parity", {}).get("status", "under review")
    import_link = _relative_href(page_path, docs_root / "pages" / "import-guide.html")
    quality_link = _relative_href(page_path, docs_root / "pages" / "quality-dashboard.html")
    release_link = _relative_href(page_path, docs_root / "pages" / "release.html")
    reference_link = _relative_href(page_path, page_path.parent / "hydrogen-ontology.html")
    return f"""
    <section class="grid">
      <article class="card">
        <h2>{escape(str(profile_cfg.get('title', profile_key.upper())))}</h2>
        <p>{escape(_profile_description(profile_key, profile_cfg))}</p>
        <p>Ontology IRI: <code>{escape(str(profile_cfg.get('ontology_iri', '')))}</code></p>
        <p>Namespace: <code>{escape(str(profile_cfg.get('namespace_uri', '')))}</code></p>
        <p>This profile remains an AIMWORKS-generated public view while ODK runs in parallel as a machine release and QC backend.</p>
        <div class="button-row">
          <a class="inline-button" href="{reference_link}">Open reference</a>
          <a class="inline-button" href="{release_link}">Release</a>
          <a class="inline-button" href="{quality_link}">Quality</a>
        </div>
      </article>
      <article class="card">
        <h2>Machine Release Backend</h2>
        <ul class="stats">
          <li><strong>Status:</strong> {escape(str(odk.get('status', 'not built')))}</li>
          <li><strong>Last built:</strong> {escape(str(odk.get('last_built', 'unknown')))}</li>
          <li><strong>Reasoner:</strong> {escape(str(odk.get('reasoner', 'ELK')))}</li>
          <li><strong>Primary artefact:</strong> {escape(str(odk.get('primary_artifact', 'base')))}</li>
          <li><strong>Parity:</strong> {escape(str(parity_status))}</li>
        </ul>
        <p>Standard ODK machine artefacts and ROBOT QC are generated in parallel with the AIMWORKS release pipeline.</p>
        <p class="muted">Managed imports include HDO, EMMO, QUDT, ChEBI, PROV-O, and DCTERMS. HDO is the preferred anchor for data and metadata-management concepts.</p>
        <div class="button-row">
          <a class="inline-button" href="{release_link}">Release</a>
          <a class="inline-button" href="{quality_link}">Quality</a>
          <a class="inline-button" href="{import_link}">Import</a>
        </div>
      </article>
    </section>
    """


def _reference_body(project: dict[str, Any], profile_key: str, odk: dict[str, Any], hdo: dict[str, Any], page_path: Path, docs_root: Path) -> str:
    profiles = project.get("profiles", {})
    profile_cfg = profiles.get(profile_key, {})
    ontology_base = docs_root.parent / "ontology"
    canonical_file = ontology_base / f"{profile_key}_schema.ttl"
    if not canonical_file.exists():
        canonical_file = ontology_base / "schema.ttl"
    canonical_href = _relative_href(page_path, canonical_file)
    odk_base = _relative_href(page_path, docs_root.parent / "odk")
    parity = odk.get("parity", {})
    return f"""
    <section class="grid">
      <article class="card">
        <h2>Profile Metadata</h2>
        <p><strong>Title:</strong> {escape(str(profile_cfg.get('title', profile_key.upper())))}</p>
        <p><strong>Scope:</strong> {escape(_profile_description(profile_key, profile_cfg))}</p>
        <p><strong>Ontology IRI:</strong> <code>{escape(str(profile_cfg.get('ontology_iri', '')))}</code></p>
        <p><strong>Namespace:</strong> <code>{escape(str(profile_cfg.get('namespace_uri', '')))}</code></p>
      </article>
      <article class="card">
        <h2>Machine Artefacts</h2>
        <ul class="stats">
          <li><a href="{canonical_href}">Canonical AIMWORKS ontology download</a></li>
          {_artifact_line(odk, 'base', odk_base)}
          {_artifact_line(odk, 'full', odk_base)}
          {_artifact_line(odk, 'simple', odk_base)}
        </ul>
        <p>ODK artefacts are machine-oriented companion releases. Example and data-like content remain outside ODK v1.</p>
        <p>HDO is used as a primary alignment source for data, metadata, digital-object, and process-management concepts.</p>
        <p class="muted">HDO-reviewed H2KG terms in this run: {hdo.get('summary', {}).get('reviewed_against_hdo', 0)}</p>
        {_shadow_note(parity)}
      </article>
    </section>
    """


def _release_snapshot_for_docs(output_dir: Path, fair_snapshot: dict[str, Any] | None, odk: dict[str, Any]) -> dict[str, Any]:
    release = dict(
        fair_snapshot
        or {
            "generated_at": "",
            "findable": 0,
            "accessible": 0,
            "interoperable": 0,
            "reusable": 0,
            "summary": "Release summary unavailable.",
            "artifacts": [],
            "fair_signals": [],
            "transparency_hooks": [],
            "validation_signals": [],
            "publication_assets": [],
            "section_explanations": {},
        }
    )
    publication_assets = [dict(item) for item in release.get("publication_assets", [])]
    for asset in publication_assets:
        if asset.get("label") == "HTML reference page":
            asset["value"] = "published" if release.get("publication_evidence", {}).get("docs_published") else "prepared"
            asset["status"] = "good" if asset["value"] == "published" else "watch"
        elif asset.get("label") == "Release bundle" and (output_dir.parent / "release_bundle" / "RELEASE_NOTES.md").exists():
            asset["value"] = "published" if release.get("publication_evidence", {}).get("artifacts_published") else "prepared"
            asset["status"] = "good" if asset["value"] == "published" else "watch"
    release["publication_assets"] = publication_assets
    release["freshness"] = _report_freshness(output_dir, release, odk)
    return release


def _render_rows(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p>No data available.</p>"
    items = "".join(
        f"<li><strong>{escape(str(item.get('label', 'Metric')))}</strong> <span class='badge {escape(str(item.get('status', 'watch')))}'>{escape(str(item.get('status', 'watch')).upper())}</span> <span class='value'>{escape(str(item.get('value', '')))}</span><br><span class='muted'>{escape(str(item.get('detail', '')))}</span></li>"
        for item in rows
    )
    return f"<ul class='metric-list'>{items}</ul>"


def _publication_rows(publication: dict[str, Any]) -> list[dict[str, Any]]:
    publication_status = publication.get("publication_status", "local-build")
    resolver_status = publication.get("resolver_status", "prepared")
    docs_status = publication.get("docs_publication_status", "prepared")
    artifact_status = publication.get("artifact_publication_status", "prepared")
    return [
        {
            "label": "Overall publication status",
            "status": "good" if publication_status == "published" else "watch",
            "value": str(publication_status),
            "detail": "This is the canonical release-state signal for whether the current ontology publication is treated as publicly established.",
        },
        {
            "label": "Resolver status",
            "status": "good" if resolver_status == "established" else "watch",
            "value": str(resolver_status),
            "detail": "The public resolver status tracks whether the ontology namespace is established through the configured persistent identifier service.",
        },
        {
            "label": "Documentation publication status",
            "status": "good" if docs_status == "published" and publication_status == "published" else "watch",
            "value": str(docs_status),
            "detail": "Documentation publication tracks whether the human-readable HTML documentation is publicly established as part of the current release.",
        },
        {
            "label": "Machine artefact publication status",
            "status": "good" if artifact_status == "published" and publication_status == "published" else "watch",
            "value": str(artifact_status),
            "detail": "Machine artefact publication tracks whether the ontology serializations and release bundle are treated as publicly established release artifacts.",
        },
    ]


def _shadow_mode_summary(odk: dict[str, Any]) -> str:
    parity = odk.get("parity", {})
    promotion_state = odk.get("promotion_state", "shadow")
    if parity.get("status") == "aligned" and not parity.get("iri_drift", False):
        if promotion_state != "promoted":
            return "ODK shadow artefacts are technically aligned and show no IRI drift, but shadow mode remains the active governance state until promotion is explicitly approved."
        return "ODK artefacts are technically aligned, show no IRI drift, and have been explicitly promoted out of shadow mode."
    return str(parity.get("message", "ODK parity has not yet been reviewed."))


def _foops_details(assessment: dict[str, Any]) -> str:
    dimensions = assessment.get("dimensions", {})
    rows = [
        {"label": "Status", "status": "good" if assessment.get("status") == "assessed" else "unavailable" if assessment.get("status") == "unavailable" else "optional", "value": assessment.get("status", "unknown"), "detail": assessment.get("message", "")},
        {"label": "Overall score", "status": "good" if (assessment.get("overall_score") or 0) >= 70 else "watch" if assessment.get("overall_score") is not None else "unavailable", "value": f"{assessment.get('overall_score')} / 100" if assessment.get("overall_score") is not None else "not assessed", "detail": "Returned directly by the FOOPS! service when reachable."},
        {"label": "F / Findable", "status": "good" if dimensions.get("findable") is not None and dimensions.get("findable") >= 70 else "action" if dimensions.get("findable") is not None else "unavailable", "value": f"{dimensions.get('findable')} / 100" if dimensions.get("findable") is not None else "not assessed", "detail": "Returned directly by the FOOPS! service when reachable."},
        {"label": "A / Accessible", "status": "unavailable" if dimensions.get("accessible") is None else "good" if dimensions.get("accessible") >= 70 else "watch", "value": f"{dimensions.get('accessible')} / 100" if dimensions.get("accessible") is not None else "not assessed", "detail": "In file mode this dimension is commonly not assessed by FOOPS! and is not used to penalize the internal Accessible score."},
        {"label": "I / Interoperable", "status": "good" if dimensions.get("interoperable") is not None and dimensions.get("interoperable") >= 70 else "action" if dimensions.get("interoperable") is not None else "unavailable", "value": f"{dimensions.get('interoperable')} / 100" if dimensions.get("interoperable") is not None else "not assessed", "detail": "Returned directly by the FOOPS! service when reachable."},
        {"label": "R / Reusable", "status": "good" if dimensions.get("reusable") is not None and dimensions.get("reusable") >= 70 else "action" if dimensions.get("reusable") is not None else "unavailable", "value": f"{dimensions.get('reusable')} / 100" if dimensions.get("reusable") is not None else "not assessed", "detail": "Returned directly by the FOOPS! service when reachable."},
    ]
    failed_checks = assessment.get("failed_checks", [])
    if failed_checks:
        rows.extend(
            {
                "label": f"FOOPS! follow-up {index + 1}",
                "status": "watch",
                "value": item.get("label", "check"),
                "detail": item.get("detail", ""),
            }
            for index, item in enumerate(failed_checks[:8])
        )
    return _render_rows(rows)


def _oops_details(assessment: dict[str, Any]) -> str:
    rows = [
        {"label": "Status", "status": "good" if assessment.get("status") == "assessed" else "unavailable" if assessment.get("status") == "unavailable" else "optional", "value": assessment.get("status", "unknown"), "detail": assessment.get("message", "")},
        {"label": "Pitfall count", "status": "good" if assessment.get("status") == "assessed" and assessment.get("pitfall_count", 0) == 0 else "watch" if assessment.get("status") == "assessed" else "unavailable", "value": str(assessment.get("pitfall_count", "not assessed")) if assessment.get("status") == "assessed" else "not assessed", "detail": "Returned directly by the OOPS! service when the scan succeeds."},
    ]
    for item in assessment.get("pitfalls", [])[:8]:
        code = item.get("code") or "Pitfall"
        name = item.get("name", "Unnamed pitfall")
        detail = item.get("description", "")
        rows.append({"label": code, "status": "action", "value": name, "detail": detail})
    return _render_rows(rows)


def _report_freshness(output_dir: Path, release: dict[str, Any], odk: dict[str, Any]) -> dict[str, Any]:
    fair_report = output_dir.parent / "reports" / "fair_readiness_report.json"
    validation_report = output_dir.parent / "reports" / "validation_report.json"
    hdo_report = output_dir.parent / "reports" / "hdo_alignment_report.json"
    odk_manifest = output_dir.parent / "odk" / "manifest.json"
    tracked = [
        ("FAIR snapshot", fair_report),
        ("Validation snapshot", validation_report),
        ("HDO snapshot", hdo_report),
        ("ODK snapshot", odk_manifest),
    ]
    rows: list[dict[str, Any]] = []
    timestamps: list[float] = []
    missing: list[str] = []
    for label, path in tracked:
        if path.exists():
            ts = path.stat().st_mtime
            timestamps.append(ts)
            rows.append(
                {
                    "label": label,
                    "status": "good",
                    "value": _fmt_timestamp(ts),
                    "detail": f"Loaded from {path.relative_to(output_dir.parent)}.",
                }
            )
        else:
            missing.append(label)
            rows.append(
                {
                    "label": label,
                    "status": "action",
                    "value": "missing",
                    "detail": f"Expected file {path.relative_to(output_dir.parent)} was not found during docs generation.",
                }
            )
    if missing:
        status = "action"
        value = "missing inputs"
        detail = f"One or more report inputs are missing: {', '.join(missing)}."
    elif timestamps and max(timestamps) - min(timestamps) > 300:
        status = "watch"
        value = "out of sync"
        detail = "Report timestamps differ by more than five minutes, so the page may be mixing build generations."
    else:
        status = "good"
        value = "in sync"
        detail = "FAIR, validation, HDO, and ODK snapshots were generated close enough together to represent one coherent build."
    if odk.get("last_built"):
        rows.append(
            {
                "label": "ODK artefact build time",
                "status": "good",
                "value": str(odk.get("last_built")),
                "detail": "Reported directly by the ODK manifest.",
            }
        )
    if release.get("generated_at"):
        rows.append(
            {
                "label": "FAIR snapshot build time",
                "status": "good",
                "value": str(release.get("generated_at")),
                "detail": "Reported directly by the FAIR readiness snapshot.",
            }
        )
    return {"status": status, "value": value, "detail": detail, "rows": rows}


def _fmt_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).astimezone().isoformat(timespec="seconds")


def _row_value(rows: list[dict[str, Any]], label: str, default: str) -> str:
    for item in rows:
        if item.get("label") == label:
            return str(item.get("value", default))
    return default


def _row_status(rows: list[dict[str, Any]], label: str, default: str) -> str:
    for item in rows:
        if item.get("label") == label:
            return str(item.get("status", default))
    return default


def _row_detail(rows: list[dict[str, Any]], label: str, default: str) -> str:
    for item in rows:
        if item.get("label") == label:
            return str(item.get("detail", default))
    return default


def _support_block(project: dict[str, Any], asset_base: str) -> str:
    acknowledgements = project.get("acknowledgements", {})
    support_copy = str(acknowledgements.get("support_copy", "")).strip()
    initiatives = acknowledgements.get("initiatives", [])
    if not support_copy and not initiatives:
        return ""
    chips = "".join(_initiative_chip(item, asset_base) for item in initiatives if isinstance(item, dict))
    copy_html = f"<p class='hero-support-copy'>{escape(support_copy)}</p>" if support_copy else ""
    chips_html = f"<div class='support-strip'>{chips}</div>" if chips else ""
    return f"<div class='hero-support'>{copy_html}{chips_html}</div>"


def _hero_brand(project: dict[str, Any], asset_base: str) -> str:
    logo = f"{asset_base}/h2kg-logo.png"
    alt = escape(f"{project['short_title']} logo")
    return f"<div class='hero-brand'><img src='{logo}' alt='{alt}'><span class='hero-brand-mark'>Ontology release</span></div>"


def _profile_description(profile_key: str, profile_cfg: dict[str, Any]) -> str:
    custom = str(profile_cfg.get("subtitle", "")).strip()
    if custom:
        return custom
    if profile_key == "pemfc":
        return "Proton exchange membrane fuel cell profile for experiments, materials, processes, measurements, and data."
    if profile_key == "pemwe":
        return "Proton exchange membrane water electrolysis profile for experiments, materials, processes, measurements, and data."
    return "Shared core profile for hydrogen electrochemical systems."


def _acknowledgement_block(project: dict[str, Any], asset_base: str) -> str:
    acknowledgements = project.get("acknowledgements", {})
    initiatives = acknowledgements.get("initiatives", [])
    funding_notice = acknowledgements.get("funding_notice", [])
    if not initiatives and not funding_notice:
        return ""
    brands = "".join(_initiative_brand(item, asset_base) for item in initiatives if isinstance(item, dict))
    paragraphs = "".join(f"<p>{escape(str(item))}</p>" for item in funding_notice if str(item).strip())
    return f"""
      <section class="acknowledgement" aria-labelledby="acknowledgement-title">
        <div class="acknowledgement-brand">
          <p id="acknowledgement-title" class="eyebrow">Acknowledgement</p>
          <div class="acknowledgement-brand-grid">{brands}</div>
        </div>
        <div class="acknowledgement-copy">
          {paragraphs}
        </div>
      </section>
    """


def _initiative_chip(item: dict[str, Any], asset_base: str) -> str:
    name = escape(str(item.get("name", "")))
    url = escape(str(item.get("url", "#")))
    logo = _asset_src(item, asset_base)
    if logo:
        alt = escape(str(item.get("logo_alt", item.get("name", "logo"))))
        return f"<a class='support-chip support-chip-logo' href='{url}' target='_blank' rel='noopener noreferrer'><img src='{logo}' alt='{alt}'><span>{name}</span></a>"
    return f"<a class='support-chip' href='{url}' target='_blank' rel='noopener noreferrer'>{name}</a>"


def _initiative_brand(item: dict[str, Any], asset_base: str) -> str:
    name = escape(str(item.get("name", "")))
    url = escape(str(item.get("url", "#")))
    logo = _asset_src(item, asset_base)
    if logo:
        alt = escape(str(item.get("logo_alt", item.get("name", "logo"))))
        visual = f"<img src='{logo}' alt='{alt}'>"
    else:
        visual = f"<span>{name}</span>"
    return f"<a class='acknowledgement-brand-item' href='{url}' target='_blank' rel='noopener noreferrer'>{visual}</a>"


def _asset_src(item: dict[str, Any], asset_base: str) -> str:
    logo = str(item.get("logo", "")).strip()
    if not logo:
        return ""
    return f"{asset_base}/{escape(Path(logo).name)}"


def _copy_site_assets(output_dir: Path, project: dict[str, Any]) -> None:
    asset_dir = ensure_dir(output_dir / "assets")
    source_dir = Path(__file__).resolve().parents[2] / "templates" / "site" / "assets"
    for filename in ("h2kg-logo.png",):
        source_path = source_dir / filename
        if source_path.exists():
            shutil.copyfile(source_path, asset_dir / filename)
    acknowledgements = project.get("acknowledgements", {})
    for item in acknowledgements.get("initiatives", []):
        if not isinstance(item, dict):
            continue
        logo = str(item.get("logo", "")).strip()
        if not logo:
            continue
        source_path = source_dir / Path(logo).name
        target_path = asset_dir / Path(logo).name
        if source_path.exists():
            shutil.copyfile(source_path, target_path)


def _copy_odk_artifacts(output_dir: Path) -> None:
    source_dir = output_dir.parent / "odk" / "artifacts"
    target_dir = ensure_dir(output_dir / "odk" / "artifacts")
    if not source_dir.exists():
        return
    for artifact in source_dir.iterdir():
        if artifact.is_file():
            shutil.copyfile(artifact, target_dir / artifact.name)


def _odk_artifact_cards(odk: dict[str, Any], odk_base: str) -> str:
    if not odk.get("artifacts"):
        return "<p>No ODK artefacts available.</p>"
    cards = []
    for artifact in odk.get("artifacts", []):
        links = []
        for fmt in artifact.get("formats", []):
            filename = fmt.get("filename", "")
            href = f"{odk_base}/artifacts/{escape(str(filename))}"
            label = escape(str(fmt.get("format", ""))).upper()
            links.append(f"<a class='inline-button' href='{href}'>{label}</a>")
        cards.append(
            f"""
            <article class="term-card">
              <h3>{escape(str(artifact.get('title', artifact.get('name', 'artifact'))))}</h3>
              <p>{escape(str(artifact.get('description', '')))}</p>
              <p class="muted">Generated: {escape(str(artifact.get('generated_at', '')))} | Size: {artifact.get('size_bytes', 0)} bytes</p>
              <div class="button-row">{''.join(links)}</div>
            </article>
            """
        )
    return f"<section class='list-grid'>{''.join(cards)}</section>"


def _artifact_line(odk: dict[str, Any], name: str, odk_base: str) -> str:
    for artifact in odk.get("artifacts", []):
        if artifact.get("name") != name:
            continue
        first = artifact.get("formats", [{}])[0]
        href = f"{odk_base}/artifacts/{escape(str(first.get('filename', '')))}"
        return f"<li><a href=\"{href}\">ODK {escape(name)}</a></li>"
    return f"<li>ODK {escape(name)} unavailable</li>"


def _shadow_note(parity: dict[str, Any]) -> str:
    if parity.get("status") == "aligned":
        return "<p class='muted'>ODK shadow-mode artefacts are currently aligned with the curated release baseline.</p>"
    return "<p class='muted'>ODK artefacts are currently shadow-mode outputs for comparison and QC.</p>"


def _hdo_import_record(odk: dict[str, Any]) -> dict[str, Any]:
    for item in odk.get("imports", []):
        if item.get("id") == "hdo":
            return item
    return {}


def _hdo_import_status(odk: dict[str, Any]) -> str:
    item = _hdo_import_record(odk)
    return escape(str(item.get("status", "not configured")))


def _hdo_import_refresh(odk: dict[str, Any]) -> str:
    item = _hdo_import_record(odk)
    return escape(str(item.get("last_refresh_status", "not recorded")))


def _hdo_import_included(odk: dict[str, Any]) -> str:
    item = _hdo_import_record(odk)
    return "yes" if item.get("included_in_release") else "no"


def _relative_href(page_path: Path, target_path: Path) -> str:
    return Path(os.path.relpath(target_path, page_path.parent)).as_posix()


def _explorer_css() -> str:
    return """
.inline-button--small { padding: 0.34rem 0.62rem; font-size: 0.82rem; }
.inline-button--ghost {
  background: rgba(255,255,255,0.78);
  color: var(--ink);
  cursor: pointer;
  font: inherit;
}
.explorer-shell {
  display: grid;
  grid-template-columns: minmax(300px, 360px) minmax(0, 1fr);
  gap: 1rem;
  align-items: start;
}
.explorer-sidebar, .explorer-main, .explorer-detail-grid { display: grid; gap: 1rem; }
.explorer-panel h2, .explorer-panel h3 { margin: 0; }
.explorer-panel__head {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 1rem;
}
.explorer-kpis {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.55rem;
  min-width: 260px;
}
.explorer-kpis div,
.explorer-result__meta span,
.explorer-module__meta,
.explorer-chip {
  border: 1px solid var(--line);
  border-radius: 999px;
  background: rgba(255,255,255,0.7);
}
.explorer-kpis div { padding: 0.55rem 0.7rem; text-align: center; }
.explorer-kpis span { display: block; color: var(--muted); font-size: 0.76rem; }
.explorer-kpis strong { display: block; margin-top: 0.1rem; font-size: 1.05rem; }
.explorer-field { display: grid; gap: 0.35rem; margin: 0.85rem 0 0.75rem; }
.explorer-field label { font-weight: 700; }
.explorer-field input[type="search"] {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 0.8rem 0.9rem;
  font: inherit;
  background: rgba(255,255,255,0.78);
  color: var(--ink);
}
.explorer-note {
  margin-top: 0.7rem;
  color: var(--muted);
  line-height: 1.55;
  font-size: 0.94rem;
}
.explorer-toggle {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  margin-top: 0.8rem;
  color: var(--ink);
}
.explorer-results { display: grid; gap: 0.55rem; margin-top: 0.9rem; }
.explorer-result {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 16px;
  background: rgba(255,255,255,0.86);
  padding: 0.8rem 0.9rem;
  text-align: left;
  cursor: pointer;
  font: inherit;
  color: var(--ink);
  transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
}
.explorer-result:hover,
.explorer-result.is-highlighted,
.explorer-trail button:hover,
.explorer-trail button.is-active {
  transform: translateY(-1px);
  box-shadow: 0 10px 24px rgba(17, 29, 36, 0.08);
  border-color: rgba(15,109,122,0.24);
}
.explorer-result.is-active { border-color: rgba(15,109,122,0.32); background: rgba(244, 251, 251, 0.92); }
.explorer-result strong { display: block; }
.explorer-result small { color: var(--muted); }
.explorer-result__meta { display: flex; flex-wrap: wrap; gap: 0.35rem; margin: 0.45rem 0; }
.explorer-result__meta span,
.explorer-module__meta,
.explorer-chip { padding: 0.18rem 0.5rem; font-size: 0.76rem; color: var(--muted); }
.explorer-empty {
  border: 1px dashed rgba(19,33,41,0.18);
  border-radius: 16px;
  padding: 0.95rem;
  color: var(--muted);
  background: rgba(255,255,255,0.42);
}
.explorer-module-grid { display: grid; gap: 0.65rem; margin-top: 0.85rem; }
.explorer-module {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 0.7rem;
  align-items: start;
  border: 1px solid rgba(19,33,41,0.08);
  border-radius: 16px;
  padding: 0.75rem 0.8rem;
  background: rgba(255,255,255,0.72);
}
.explorer-module strong,
.explorer-inspector strong,
.explorer-relations th,
.explorer-relations td:first-child { color: var(--ink); }
.explorer-module small { display: block; margin-top: 0.15rem; color: var(--muted); line-height: 1.45; }
.explorer-toolbar { display: flex; flex-wrap: wrap; gap: 0.6rem; margin-top: 0.9rem; }
.explorer-toolbar button[disabled] { opacity: 0.55; cursor: not-allowed; transform: none; }
.explorer-trail { display: flex; flex-wrap: wrap; gap: 0.55rem; }
.explorer-trail button {
  border: 1px solid var(--line);
  border-radius: 999px;
  background: rgba(255,255,255,0.72);
  padding: 0.48rem 0.75rem;
  cursor: pointer;
  font: inherit;
  color: var(--ink);
}
.explorer-chart {
  min-height: 520px;
  border: 1px solid rgba(19,33,41,0.08);
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(255,255,255,0.9), rgba(248,244,237,0.72));
}
.explorer-detail-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.explorer-inspector { display: grid; gap: 0.8rem; }
.explorer-inspector__section { padding-top: 0.7rem; border-top: 1px solid rgba(19,33,41,0.08); }
.explorer-inspector__section:first-child { padding-top: 0; border-top: 0; }
.explorer-inspector p { margin: 0.3rem 0 0; color: var(--muted); line-height: 1.6; }
.explorer-chip-row { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.5rem; }
.explorer-relations { width: 100%; border-collapse: collapse; font-size: 0.95rem; }
.explorer-relations th,
.explorer-relations td { text-align: left; padding: 0.55rem 0.45rem; border-bottom: 1px solid rgba(19,33,41,0.08); vertical-align: top; }
.explorer-relations th { font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); }
@media (max-width: 1100px) {
  .explorer-shell,
  .explorer-detail-grid { grid-template-columns: 1fr; }
  .explorer-kpis { min-width: 0; }
}
@media (max-width: 760px) {
  .explorer-panel__head { flex-direction: column; }
  .explorer-kpis { grid-template-columns: repeat(3, minmax(0, 1fr)); width: 100%; }
  .explorer-chart { min-height: 420px; }
}
"""


def _explorer_js() -> str:
    return r"""
document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector("[data-explorer-root]");
  if (!root) return;

  const dataPath = root.dataset.explorerData;
  const referencePage = root.dataset.referencePage || "../hydrogen-ontology.html";
  const searchInputEl = root.querySelector("[data-explorer-search]");
  const searchStatusEl = root.querySelector("[data-explorer-search-status]");
  const resultsEl = root.querySelector("[data-explorer-results]");
  const trailEl = root.querySelector("[data-explorer-trail]");
  const graphNoteEl = root.querySelector("[data-explorer-graph-note]");
  const inspectorEl = root.querySelector("[data-explorer-inspector]");
  const relationsEl = root.querySelector("[data-explorer-relations]");
  const chartEl = root.querySelector("[data-explorer-chart]");
  const countNodesEl = root.querySelector('[data-explorer-count="nodes"]');
  const countEdgesEl = root.querySelector('[data-explorer-count="edges"]');
  const countExpandedEl = root.querySelector('[data-explorer-count="expanded"]');
  const undoButtonEl = root.querySelector('[data-explorer-action="undo"]');

  const STARTER_LABELS = [
    "measurement",
    "property",
    "parameter",
    "matter",
    "instrument",
    "manufacturing",
    "process",
    "data",
    "metadata"
  ];
  const MAX_SUGGESTIONS = 14;

  let payload = null;
  let cy = null;
  let currentSuggestions = [];

  const state = {
    selectedId: null,
    seedId: null,
    expandedIds: new Set(),
    trail: [],
    history: [],
    highlightedIndex: 0
  };

  const escapeHtml = (value) => String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
  const normalize = (value) => String(value || "").trim().toLowerCase();
  const stripKey = (value) => normalize(value).replace(/[^a-z0-9]+/g, "");
  const activeModules = () => Array.from(root.querySelectorAll("[data-explorer-module]:checked")).map((input) => input.value);
  const toggleEnabled = (name) => Boolean(root.querySelector(`[data-explorer-toggle="${name}"]`)?.checked);
  const nodeQname = (node) => String(node.qname || node.localName || node.iri || "");
  const nodeAnchorHref = (node) => `${referencePage}#${encodeURIComponent(node.anchor || node.localName || "")}`;

  function levenshtein(left, right) {
    if (left === right) return 0;
    if (!left.length) return right.length;
    if (!right.length) return left.length;
    const previous = Array.from({ length: right.length + 1 }, (_, index) => index);
    for (let i = 1; i <= left.length; i += 1) {
      let diagonal = previous[0];
      previous[0] = i;
      for (let j = 1; j <= right.length; j += 1) {
        const stored = previous[j];
        const cost = left[i - 1] === right[j - 1] ? 0 : 1;
        previous[j] = Math.min(previous[j] + 1, previous[j - 1] + 1, diagonal + cost);
        diagonal = stored;
      }
    }
    return previous[right.length];
  }

  function fuzzyBonus(query, candidate) {
    const q = stripKey(query);
    const c = stripKey(candidate);
    if (!q || !c || Math.abs(q.length - c.length) > 3) return 0;
    const distance = levenshtein(q, c);
    if (distance === 0) return 28;
    if (distance === 1) return 16;
    if (distance === 2) return 8;
    return 0;
  }

  function isSearchableNode(node) {
    const localName = String(node.localName || "");
    if (node.category === "Ontology" || localName.startsWith("_") || /_QV$/i.test(localName)) return false;
    return true;
  }

  function searchCandidates() {
    const allowExternal = toggleEnabled("includeExternalSearch");
    return (payload?.nodes || []).filter((node) => {
      if (!isSearchableNode(node)) return false;
      if (!allowExternal && !node.local) return false;
      return true;
    });
  }

  function starterSuggestions(view) {
    const candidates = view.nodes.filter((node) => isSearchableNode(node) && node.local);
    const starters = [];
    const seen = new Set();
    STARTER_LABELS.forEach((target) => {
      const match = candidates.find((node) => {
        const label = normalize(node.label);
        const localName = normalize(node.localName);
        return label === target || localName === target;
      });
      if (match && !seen.has(match.id)) {
        starters.push(match);
        seen.add(match.id);
      }
    });
    return starters.length
      ? starters
      : candidates.sort((left, right) => (Number(right.degree || 0) - Number(left.degree || 0)) || left.label.localeCompare(right.label)).slice(0, MAX_SUGGESTIONS);
  }

  function scoreNode(node, query) {
    const q = normalize(query);
    if (!q) return 0;
    const label = normalize(node.label);
    const localName = normalize(node.localName || "");
    const qname = normalize(nodeQname(node));
    const iri = normalize(node.iri || "");
    const details = normalize(node.search_text || node.description || "");
    const altLabels = normalize((node.alt_labels || []).join(" "));
    const examples = normalize((node.examples || []).join(" "));
    const notes = normalize((node.notes || []).join(" "));
    const displayClass = normalize(node.display_class || "");
    const mappingText = normalize((node.mapping_labels || []).join(" "));
    let score = 0;

    if (label === q || localName === q || qname === q) score += 180;
    if (label.startsWith(q) || localName.startsWith(q) || qname.startsWith(q)) score += 95;
    if (label.includes(q) || localName.includes(q) || qname.includes(q)) score += 70;
    if (details.includes(q)) score += 28;
    if (altLabels.includes(q)) score += 20;
    if (displayClass.includes(q)) score += 18;
    if (examples.includes(q) || notes.includes(q)) score += 12;
    if (iri.includes(q)) score += 12;
    if (mappingText.includes(q)) score += 9;
    if (node.local) score += 18;
    if ((node.modules || []).includes("vocabulary")) score += 12;
    if ((node.modules || []).includes("schema")) score += 8;
    score += Math.max(
      fuzzyBonus(q, label),
      fuzzyBonus(q, localName),
      fuzzyBonus(q, qname),
      fuzzyBonus(q, displayClass),
      0
    );
    score += Math.min(Number(node.degree || 0), 60) / 25;
    return score;
  }

  function searchResults(query) {
    const q = normalize(query);
    if (!q) return [];
    return searchCandidates()
      .map((node) => ({ node, score: scoreNode(node, q) }))
      .filter((row) => row.score > 0)
      .sort((left, right) => {
        if (right.score !== left.score) return right.score - left.score;
        if (left.node.local !== right.node.local) return left.node.local ? -1 : 1;
        return left.node.label.localeCompare(right.node.label);
      })
      .slice(0, MAX_SUGGESTIONS)
      .map((row) => row.node);
  }

  function updateTrail(nodeId) {
    if (!nodeId) return;
    state.trail = state.trail.filter((value) => value !== nodeId);
    state.trail.push(nodeId);
    if (state.trail.length > 10) {
      state.trail = state.trail.slice(state.trail.length - 10);
    }
  }

  function captureSnapshot() {
    return {
      selectedId: state.selectedId,
      seedId: state.seedId,
      expandedIds: Array.from(state.expandedIds),
      trail: state.trail.slice(),
      highlightedIndex: state.highlightedIndex,
      searchValue: searchInputEl.value,
      activeModules: activeModules(),
      toggles: Object.fromEntries(Array.from(root.querySelectorAll("[data-explorer-toggle]")).map((input) => [input.dataset.explorerToggle, input.checked]))
    };
  }

  function pushHistorySnapshot() {
    state.history.push(captureSnapshot());
    if (state.history.length > 30) {
      state.history = state.history.slice(state.history.length - 30);
    }
  }

  function applySnapshot(snapshot) {
    if (!snapshot) return;
    searchInputEl.value = snapshot.searchValue || "";
    const selectedModules = new Set(snapshot.activeModules || []);
    root.querySelectorAll("[data-explorer-module]").forEach((input) => {
      input.checked = selectedModules.has(input.value);
    });
    root.querySelectorAll("[data-explorer-toggle]").forEach((input) => {
      input.checked = Boolean(snapshot.toggles?.[input.dataset.explorerToggle]);
    });
    state.selectedId = snapshot.selectedId || null;
    state.seedId = snapshot.seedId || null;
    state.expandedIds = new Set(snapshot.expandedIds || []);
    state.trail = Array.isArray(snapshot.trail) ? snapshot.trail.slice(-10) : [];
    state.highlightedIndex = Number.isInteger(snapshot.highlightedIndex) ? snapshot.highlightedIndex : 0;
  }

  function runUndoable(action) {
    pushHistorySnapshot();
    action();
    renderAll();
  }

  function undoLastStep() {
    if (!state.history.length) return;
    applySnapshot(state.history.pop());
    renderAll();
  }

  function selectNode(nodeId, options = {}) {
    if (!nodeId) return;
    const reset = options.reset !== false;
    state.selectedId = nodeId;
    state.seedId = state.seedId || nodeId;
    if (reset) {
      state.expandedIds = new Set([nodeId]);
    } else {
      state.expandedIds.add(nodeId);
    }
    updateTrail(nodeId);
  }

  function buildBaseView() {
    const selectedModules = new Set(activeModules());
    const nodes = (payload.nodes || []).filter((node) => (node.modules || []).some((moduleId) => selectedModules.has(moduleId)));
    const nodeMap = new Map(nodes.map((node) => [node.id, node]));
    const links = (payload.links || []).filter((link) => selectedModules.has(link.module) && nodeMap.has(link.source) && nodeMap.has(link.target));
    const adjacency = new Map();
    links.forEach((link) => {
      if (!adjacency.has(link.source)) adjacency.set(link.source, []);
      if (!adjacency.has(link.target)) adjacency.set(link.target, []);
      adjacency.get(link.source).push(link);
      adjacency.get(link.target).push(link);
    });
    return { nodes, nodeMap, links, adjacency };
  }

  function buildExpandedGraph(view) {
    const center = view.nodeMap.get(state.selectedId);
    if (!center) {
      return { center: null, nodes: [], links: [], nodeMap: new Map(), meta: { expandedCount: 0 } };
    }
    const expanded = new Set(Array.from(state.expandedIds).filter((id) => view.nodeMap.has(id)));
    expanded.add(center.id);
    const visibleIds = new Set([center.id]);
    const visibleLinks = new Map();
    Array.from(expanded).forEach((sourceId) => {
      (view.adjacency.get(sourceId) || []).forEach((link) => {
        const neighborId = link.source === sourceId ? link.target : link.source;
        const neighbor = view.nodeMap.get(neighborId);
        if (!neighbor) return;
        if (!toggleEnabled("showExternalNeighbors") && !neighbor.local && neighbor.id !== center.id) return;
        visibleIds.add(link.source);
        visibleIds.add(link.target);
        visibleLinks.set(`${link.source}|${link.target}|${link.predicate}|${link.module}`, link);
      });
    });
    const nodes = Array.from(visibleIds)
      .map((id) => view.nodeMap.get(id))
      .filter(Boolean)
      .sort((left, right) => {
        if (left.id === center.id) return -1;
        if (right.id === center.id) return 1;
        if (left.local !== right.local) return left.local ? -1 : 1;
        return left.label.localeCompare(right.label);
      });
    const nodeMap = new Map(nodes.map((node) => [node.id, node]));
    const links = Array.from(visibleLinks.values()).filter((link) => nodeMap.has(link.source) && nodeMap.has(link.target));
    return { center, nodes, links, nodeMap, meta: { expandedCount: expanded.size } };
  }

  function ensureCy() {
    if (cy) return cy;
    cy = cytoscape({
      container: chartEl,
      elements: [],
      style: [
        {
          selector: "node",
          style: {
            "background-color": (ele) => ele.data("isCenter") ? "#c86a2b" : ele.data("isLocal") ? "#0f6d7a" : "#9a6d4f",
            "label": "data(label)",
            "font-size": 11,
            "text-wrap": "wrap",
            "text-max-width": 120,
            "color": "#132129",
            "text-valign": "bottom",
            "text-margin-y": 8,
            "width": (ele) => ele.data("isCenter") ? 38 : 28,
            "height": (ele) => ele.data("isCenter") ? 38 : 28,
            "border-width": 1.4,
            "border-color": "rgba(19,33,41,0.18)"
          }
        },
        {
          selector: "edge",
          style: {
            "line-color": "rgba(19,33,41,0.24)",
            "target-arrow-color": "rgba(19,33,41,0.24)",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            "arrow-scale": 0.9,
            "width": 1.6,
            "label": "data(label)",
            "font-size": 9,
            "color": "rgba(19,33,41,0.74)",
            "text-background-color": "rgba(255,255,255,0.92)",
            "text-background-opacity": 1,
            "text-background-padding": 2,
            "text-rotation": "autorotate"
          }
        },
        {
          selector: ":selected",
          style: {
            "overlay-color": "#0f6d7a",
            "overlay-opacity": 0.08
          }
        }
      ]
    });
    cy.on("tap", "node", (event) => {
      runUndoable(() => {
        state.seedId = state.seedId || event.target.id();
        selectNode(event.target.id(), { reset: false });
      });
    });
    return cy;
  }

  function runLayout(graph) {
    const instance = ensureCy();
    if (!graph.nodes.length) return;
    const dense = graph.nodes.length > 28 || graph.links.length > 34;
    instance.layout(
      dense
        ? { name: "circle", animate: false, fit: true, padding: 55 }
        : {
            name: "cose",
            animate: false,
            fit: true,
            padding: 34,
            nodeRepulsion: 320000,
            idealEdgeLength: 120,
            edgeElasticity: 110,
            gravity: 0.24,
            numIter: 850,
            coolingFactor: 0.95
          }
    ).run();
    const centerNode = instance.getElementById(graph.center.id);
    if (centerNode && centerNode.nonempty()) {
      instance.center(centerNode);
    }
  }

  function buildCyElements(graph) {
    const nodes = graph.nodes.map((node) => ({
      data: {
        id: node.id,
        label: node.label,
        isLocal: node.local,
        isCenter: node.id === graph.center?.id
      }
    }));
    const edges = graph.links.map((link) => ({
      data: {
        id: `${link.source}|${link.target}|${link.predicate}|${link.module}`,
        source: link.source,
        target: link.target,
        label: String(link.value || link.predicate || "")
      }
    }));
    return [...nodes, ...edges];
  }

  function renderSearchStatus(mode, rows, query) {
    if (mode === "starter") {
      searchStatusEl.textContent = "Suggested starting points from the published whole-ontology release. Choose one to seed the graph.";
      return;
    }
    const scopeText = toggleEnabled("includeExternalSearch") ? "local and aligned external" : "local";
    searchStatusEl.textContent = `${rows.length} ${scopeText} suggestion${rows.length === 1 ? "" : "s"} for "${query.trim()}".`;
  }

  function renderResults(rows, mode) {
    currentSuggestions = rows;
    if (!rows.length) {
      resultsEl.innerHTML = `<div class="explorer-empty">${mode === "starter" ? "No starter terms are available with the current filters." : "No ontology terms match the current query."}</div>`;
      return;
    }
    resultsEl.innerHTML = rows.map((node, index) => `
      <button class="explorer-result ${node.id === state.seedId ? "is-active" : ""} ${index === state.highlightedIndex ? "is-highlighted" : ""}" type="button" data-explorer-result="${escapeHtml(node.id)}">
        <strong>${escapeHtml(node.label)}</strong>
        <small>${escapeHtml(node.display_class || node.category)}</small>
        <div class="explorer-result__meta">
          <span>${escapeHtml(node.localName || nodeQname(node) || node.iri)}</span>
          <span>${escapeHtml((node.modules || []).join(", "))}</span>
          <span>${node.local ? "Local" : "External"}</span>
        </div>
        <small>${escapeHtml(String(node.description || "").slice(0, 170))}</small>
      </button>
    `).join("");
    resultsEl.querySelectorAll("[data-explorer-result]").forEach((button) => {
      button.addEventListener("click", () => {
        runUndoable(() => {
          state.seedId = button.dataset.explorerResult;
          selectNode(button.dataset.explorerResult, { reset: true });
        });
      });
    });
  }

  function renderTrail(view) {
    const rows = state.trail.map((id) => view.nodeMap.get(id)).filter(Boolean);
    if (!rows.length) {
      trailEl.innerHTML = '<div class="explorer-empty">The traversal trail appears after you select a term.</div>';
      return;
    }
    trailEl.innerHTML = rows.map((node) => `
      <button type="button" class="${node.id === state.selectedId ? "is-active" : ""}" data-explorer-trail="${escapeHtml(node.id)}">${escapeHtml(node.label)}</button>
    `).join("");
    trailEl.querySelectorAll("[data-explorer-trail]").forEach((button) => {
      button.addEventListener("click", () => {
        runUndoable(() => {
          selectNode(button.dataset.explorerTrail, { reset: false });
        });
      });
    });
  }

  function renderInspector(node, graph) {
    if (!node) {
      inspectorEl.innerHTML = '<div class="explorer-empty">Pick a term to inspect its stable IRI, definition, and graph role.</div>';
      return;
    }
    const referenceHref = node.local ? nodeAnchorHref(node) : node.iri;
    inspectorEl.innerHTML = `
      <div class="explorer-inspector">
        <div class="explorer-inspector__section">
          <strong>${escapeHtml(node.label)}</strong>
          <div class="explorer-chip-row">
            <span class="explorer-chip">${node.local ? "Local H2KG" : "External aligned"}</span>
            <span class="explorer-chip">${escapeHtml(node.display_class || node.category)}</span>
            <span class="explorer-chip">${escapeHtml(node.deprecated || "Active")}</span>
          </div>
        </div>
        <div class="explorer-inspector__section">
          <strong>Stable IRI</strong>
          <p><code>${escapeHtml(node.iri)}</code></p>
          <div class="button-row">
            <a class="inline-button inline-button--small" href="${escapeHtml(referenceHref)}">Open reference</a>
            <button type="button" class="inline-button inline-button--small inline-button--ghost" data-copy-iri="${escapeHtml(node.iri)}">Copy IRI</button>
          </div>
        </div>
        <div class="explorer-inspector__section">
          <strong>Definition</strong>
          <p>${escapeHtml(node.description || "No definition recorded.")}</p>
        </div>
        <div class="explorer-inspector__section">
          <strong>Graph role</strong>
          <p>${escapeHtml(node.id === graph.center?.id ? "Current focus term." : "Visible through the current expanded neighborhood.")} Direct links in the explorer dataset: ${escapeHtml(String(node.degree || 0))}. Modules: ${escapeHtml((node.modules || []).join(", "))}.</p>
        </div>
      </div>
    `;
    inspectorEl.querySelectorAll("[data-copy-iri]").forEach((button) => {
      button.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(button.dataset.copyIri || "");
          button.textContent = "Copied";
          setTimeout(() => { button.textContent = "Copy IRI"; }, 1000);
        } catch (_error) {
          button.textContent = "Copy failed";
        }
      });
    });
  }

  function renderRelations(graph) {
    if (!graph.center) {
      relationsEl.innerHTML = '<div class="explorer-empty">Visible relations will appear here after you select a term.</div>';
      return;
    }
    const rows = graph.links
      .map((link) => ({
        source: graph.nodeMap.get(link.source)?.label || link.source,
        predicate: String(link.value || link.predicate || ""),
        target: graph.nodeMap.get(link.target)?.label || link.target,
        module: link.module,
        kind: link.edgeFamily
      }))
      .sort((left, right) => left.predicate.localeCompare(right.predicate) || left.target.localeCompare(right.target));
    if (!rows.length) {
      relationsEl.innerHTML = '<div class="explorer-empty">No visible relations remain with the current graph filters.</div>';
      return;
    }
    relationsEl.innerHTML = `
      <table class="explorer-relations">
        <thead>
          <tr><th>Source</th><th>Predicate</th><th>Target</th><th>Module</th></tr>
        </thead>
        <tbody>
          ${rows.map((row) => `
            <tr>
              <td>${escapeHtml(row.source)}</td>
              <td><code>${escapeHtml(row.predicate)}</code></td>
              <td>${escapeHtml(row.target)}</td>
              <td>${escapeHtml(row.module)}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  }

  function renderGraph(graph) {
    countNodesEl.textContent = String(graph.nodes.length);
    countEdgesEl.textContent = String(graph.links.length);
    countExpandedEl.textContent = String(graph.meta.expandedCount || 0);
    if (!graph.center) {
      graphNoteEl.textContent = "Search for a term or choose a suggested starting point to render the ontology graph.";
      if (cy) cy.elements().remove();
      return;
    }
    graphNoteEl.textContent = `Showing the direct visible neighborhood for ${graph.center.label}. Click a visible node to recenter and expand the exploration trail.`;
    const instance = ensureCy();
    instance.elements().remove();
    instance.add(buildCyElements(graph));
    runLayout(graph);
  }

  function syncSelection(view, suggestions, mode) {
    if (!view.nodeMap.size) {
      state.selectedId = null;
      state.seedId = null;
      state.expandedIds = new Set();
      return;
    }
    if (state.seedId && !view.nodeMap.has(state.seedId)) state.seedId = null;
    if (state.selectedId && !view.nodeMap.has(state.selectedId)) {
      state.selectedId = null;
      state.expandedIds = new Set();
    }
    if (!state.selectedId && mode === "starter") return;
    if (!state.selectedId && state.seedId && view.nodeMap.has(state.seedId)) {
      selectNode(state.seedId, { reset: false });
    }
    if (!state.seedId && suggestions.length) state.seedId = suggestions[0].id;
  }

  function currentSuggestionMode(query) {
    return normalize(query) ? "search" : "starter";
  }

  function currentSuggestionsForView(view, query) {
    return currentSuggestionMode(query) === "search" ? searchResults(query) : starterSuggestions(view);
  }

  function renderAll() {
    if (!payload) return;
    const view = buildBaseView();
    if (undoButtonEl) undoButtonEl.disabled = state.history.length === 0;
    const query = searchInputEl.value;
    const mode = currentSuggestionMode(query);
    const suggestions = currentSuggestionsForView(view, query);
    syncSelection(view, suggestions, mode);
    if (state.highlightedIndex >= suggestions.length) {
      state.highlightedIndex = Math.max(0, suggestions.length - 1);
    }
    renderSearchStatus(mode, suggestions, query);
    renderResults(suggestions, mode);
    renderTrail(view);
    const graph = buildExpandedGraph(view);
    renderGraph(graph);
    renderInspector(graph.center, graph);
    renderRelations(graph);
  }

  function applyDeepLink() {
    const params = new URLSearchParams(window.location.search);
    const iri = params.get("iri");
    if (!iri || !payload) return;
    const match = (payload.nodes || []).find((node) => node.iri === iri);
    if (!match) return;
    state.seedId = match.id;
    selectNode(match.id, { reset: true });
  }

  searchInputEl.addEventListener("input", () => {
    state.highlightedIndex = 0;
    renderAll();
  });
  searchInputEl.addEventListener("keydown", (event) => {
    if (!currentSuggestions.length) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      state.highlightedIndex = Math.min(state.highlightedIndex + 1, currentSuggestions.length - 1);
      renderAll();
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      state.highlightedIndex = Math.max(state.highlightedIndex - 1, 0);
      renderAll();
    }
    if (event.key === "Enter") {
      event.preventDefault();
      const node = currentSuggestions[state.highlightedIndex];
      if (!node) return;
      runUndoable(() => {
        state.seedId = node.id;
        selectNode(node.id, { reset: true });
      });
    }
  });

  root.querySelectorAll("[data-explorer-module], [data-explorer-toggle]").forEach((input) => {
    input.addEventListener("change", renderAll);
  });
  root.querySelectorAll("[data-explorer-action]").forEach((button) => {
    button.addEventListener("click", () => {
      if (button.dataset.explorerAction === "undo") {
        undoLastStep();
      }
      if (button.dataset.explorerAction === "reset") {
        runUndoable(() => {
          const seed = state.seedId || state.selectedId;
          if (!seed) return;
          state.selectedId = seed;
          state.expandedIds = new Set([seed]);
          updateTrail(seed);
        });
      }
      if (button.dataset.explorerAction === "clear") {
        runUndoable(() => {
          searchInputEl.value = "";
          state.selectedId = null;
          state.seedId = null;
          state.expandedIds = new Set();
          state.trail = [];
          state.highlightedIndex = 0;
        });
      }
    });
  });

  fetch(dataPath)
    .then((response) => response.json())
    .then((data) => {
      payload = data;
      applyDeepLink();
      renderAll();
    })
    .catch((error) => {
      console.error("Failed to load explorer dataset", error);
      resultsEl.innerHTML = '<div class="explorer-empty">The explorer dataset could not be loaded.</div>';
      graphNoteEl.textContent = "The ontology graph is unavailable because the explorer dataset could not be loaded.";
    });
});
"""


def _style_css() -> str:
    return """
:root {
  --bg: #f5efe4;
  --panel: rgba(255, 251, 245, 0.88);
  --panel-strong: rgba(255, 255, 255, 0.92);
  --ink: #132129;
  --muted: rgba(19, 33, 41, 0.76);
  --accent: #0f6d7a;
  --accent-2: #c86a2b;
  --line: rgba(19, 33, 41, 0.1);
  --shadow: 0 18px 48px rgba(17, 29, 36, 0.1);
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: "Aptos", "Segoe UI", sans-serif;
  color: var(--ink);
  background:
    radial-gradient(circle at 12% 10%, rgba(15,109,122,0.15), transparent 24%),
    radial-gradient(circle at 84% 8%, rgba(200,106,43,0.16), transparent 22%),
    linear-gradient(180deg, #f7fbfb 0%, #f5efe4 100%);
}
.wrap { width: min(1120px, calc(100% - 2rem)); margin: 0 auto; }
.hero {
  position: relative;
  overflow: hidden;
  padding: 3.4rem 0 2.2rem;
  border-bottom: 1px solid var(--line);
  background:
    linear-gradient(135deg, rgba(15,109,122,0.12), rgba(200,106,43,0.08)),
    linear-gradient(180deg, rgba(255,255,255,0.55), rgba(255,255,255,0.15));
}
.hero::after {
  content: "";
  position: absolute;
  inset: auto -10% -120px auto;
  width: 320px;
  height: 320px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(200,106,43,0.16), transparent 68%);
  pointer-events: none;
}
.hero-head {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 1.2rem;
  align-items: start;
}
.hero-brand {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  min-width: 0;
  padding: 0;
  background: transparent;
  border: 0;
  box-shadow: none;
}
.hero-brand img {
    width: 168px;
    height: auto;
    object-fit: contain;
    display: block;
    filter: drop-shadow(0 10px 22px rgba(17, 29, 36, 0.12));
  }
.hero-brand-mark {
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 0.64rem;
  color: rgba(19, 33, 41, 0.68);
  font-weight: 700;
  text-align: center;
}
.hero-copy {
  max-width: 58rem;
}
.eyebrow {
  text-transform: uppercase;
  letter-spacing: 0.18em;
  font-size: 0.75rem;
  color: var(--accent);
  margin: 0 0 0.85rem;
}
h1, h2, h3 {
  font-family: "Iowan Old Style", Georgia, serif;
  letter-spacing: -0.03em;
}
h1 {
  margin: 0;
  font-size: clamp(2rem, 4vw, 3.35rem);
  line-height: 0.98;
  max-width: 14ch;
  text-wrap: balance;
}
.subtitle {
  max-width: 50rem;
  margin: 0.8rem 0 0;
  font-size: 1rem;
  color: var(--muted);
}
.hero-support { margin-top: 1rem; display: grid; gap: 0.85rem; }
.hero-support-copy { max-width: 60rem; margin: 0; color: var(--muted); }
.support-strip { display: flex; flex-wrap: wrap; gap: 0.75rem; }
.support-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.45rem 0.8rem;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: rgba(255,255,255,0.76);
  color: var(--ink);
  text-decoration: none;
  font-weight: 600;
  backdrop-filter: blur(8px);
}
.support-chip img { height: 1.25rem; width: auto; display: block; }
.nav { display: flex; flex-wrap: wrap; gap: 0.75rem; margin-top: 1.15rem; }
.nav a, .inline-button {
  color: var(--ink);
  text-decoration: none;
  padding: 0.52rem 0.86rem;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: rgba(255,255,255,0.62);
  backdrop-filter: blur(8px);
}
.nav a:hover, .inline-button:hover, .support-chip:hover, .acknowledgement-brand-item:hover { transform: translateY(-1px); }
.content { padding: 2rem 0 4rem; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; }
.stack { display: grid; gap: 1rem; }
.card, .term-card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 22px;
  padding: 1.05rem 1.15rem;
  box-shadow: var(--shadow);
  backdrop-filter: blur(10px);
}
.list-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem; }
.prose { max-width: 70rem; line-height: 1.68; }
.stats { list-style: none; padding: 0; margin: 0; }
.stats li { padding: 0.25rem 0; }
.metric-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 0.8rem; }
.metric-list li { padding: 0.85rem 0; border-top: 1px solid rgba(21,32,37,0.08); }
.metric-list li:first-child { border-top: 0; padding-top: 0; }
.badge { display: inline-block; margin-left: 0.4rem; padding: 0.1rem 0.45rem; border-radius: 999px; font-size: 0.72rem; letter-spacing: 0.06em; }
.badge.good { background: rgba(44,138,72,0.12); color: #22663a; }
.badge.watch { background: rgba(198,130,36,0.14); color: #8b5f0a; }
.badge.action { background: rgba(176,51,51,0.12); color: #8a2323; }
.badge.optional { background: rgba(54, 102, 173, 0.12); color: #2d568f; }
.badge.unavailable { background: rgba(96, 104, 116, 0.14); color: #4c5561; }
.value { font-weight: 700; margin-left: 0.4rem; }
.muted { color: var(--muted); }
.iri { font-size: 0.86rem; color: var(--accent); word-break: break-word; }
code { background: rgba(15,109,122,0.08); padding: 0.1rem 0.35rem; border-radius: 4px; }
.footer { border-top: 1px solid var(--line); padding: 1.5rem 0 2rem; }
.button-row { display: flex; flex-wrap: wrap; gap: 0.65rem; margin-top: 0.8rem; }
.ordered { margin: 0; padding-left: 1.2rem; }
.ordered li { margin-bottom: 0.45rem; }
.command-list { margin: 0; padding-left: 1.2rem; }
.command-list li { margin-bottom: 0.45rem; }
.table-wrap { overflow-x: auto; }
.catalog-table { width: 100%; border-collapse: collapse; }
.catalog-table th, .catalog-table td { text-align: left; padding: 0.65rem; border-bottom: 1px solid rgba(21,32,37,0.08); vertical-align: top; }
.catalog-table th { font-size: 0.82rem; letter-spacing: 0.05em; text-transform: uppercase; color: rgba(21,32,37,0.72); }
.toc-list { margin: 0; padding-left: 1.15rem; display: grid; gap: 0.35rem; }
.reference-section { display: grid; gap: 1rem; margin-top: 1.4rem; }
.reference-section-head { display: flex; align-items: baseline; justify-content: space-between; gap: 1rem; }
.reference-section-head h2 { margin: 0; }
.reference-term {
  background: var(--panel-strong);
  border: 1px solid var(--line);
  border-radius: 20px;
  padding: 1.2rem;
  box-shadow: var(--shadow);
  scroll-margin-top: 1rem;
}
.anchor-alias {
  display: block;
  height: 0;
  overflow: hidden;
  visibility: hidden;
}
.reference-term h3 { margin: 0 0 0.4rem; font-size: 1.4rem; }
.reference-definition { margin: 0.9rem 0 0; line-height: 1.7; color: var(--ink); }
.reference-meta, .reference-relations { margin: 0.8rem 0 0; display: grid; gap: 0.4rem; }
.reference-meta div, .reference-relations div {
  display: grid;
  grid-template-columns: 190px minmax(0, 1fr);
  gap: 0.8rem;
  padding-top: 0.35rem;
  border-top: 1px solid rgba(21,32,37,0.08);
}
.reference-meta dt, .reference-relations dt { font-weight: 700; color: var(--ink); }
.reference-meta dd, .reference-relations dd { margin: 0; color: var(--muted); }
.reference-subblock { margin-top: 0.95rem; padding-top: 0.75rem; border-top: 1px solid rgba(21,32,37,0.08); }
.reference-subblock h4 {
  margin: 0 0 0.35rem;
  font-size: 0.92rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--accent);
}
.reference-subblock ul { margin: 0; padding-left: 1.1rem; }
.reference-subblock p { margin: 0.25rem 0 0; }
.acknowledgement {
  display: grid;
  grid-template-columns: minmax(220px, 280px) minmax(0, 1fr);
  gap: 1rem 1.5rem;
  padding: 0 0 1.25rem;
  margin-bottom: 1.25rem;
  border-bottom: 1px solid rgba(21,32,37,0.08);
}
.acknowledgement-brand-grid { display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: center; }
.acknowledgement-brand-item {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 3rem;
  padding: 0.45rem 0.8rem;
  border-radius: 14px;
  border: 1px solid var(--line);
  background: rgba(255,255,255,0.78);
  color: var(--ink);
  text-decoration: none;
  font-weight: 700;
  backdrop-filter: blur(8px);
}
.acknowledgement-brand-item img { display: block; max-height: 1.6rem; width: auto; }
.acknowledgement-copy p { margin: 0 0 0.85rem; }
.acknowledgement-copy p:last-child { margin-bottom: 0; }
@media (max-width: 760px) {
  .acknowledgement { grid-template-columns: 1fr; }
  .hero-head { grid-template-columns: 1fr; }
  .hero-brand { justify-self: start; min-width: 0; width: fit-content; }
  .hero-brand img { width: 126px; }
  h1 { max-width: 13ch; }
  .reference-meta div, .reference-relations div { grid-template-columns: 1fr; gap: 0.2rem; }
}
"""
