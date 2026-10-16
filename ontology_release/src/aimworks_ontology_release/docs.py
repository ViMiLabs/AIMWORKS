from __future__ import annotations

import json
import os
import re
import shutil
import csv
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
    portable_legacy_iri,
    short_text,
    try_load_yaml,
    write_text,
)

H2KG_NS = "https://w3id.org/h2kg/hydrogen-ontology#"
H2KG_ONTOLOGY_IRI = "https://w3id.org/h2kg/hydrogen-ontology"
SKOS_ALT_LABEL = "http://www.w3.org/2004/02/skos/core#altLabel"
SKOS_NOTATION = "http://www.w3.org/2004/02/skos/core#notation"
SKOS_EXAMPLE = "http://www.w3.org/2004/02/skos/core#example"
DCTERMS_SOURCE = "http://purl.org/dc/terms/source"
DCTERMS_DESCRIPTION = "http://purl.org/dc/terms/description"
RDFS_COMMENT = "http://www.w3.org/2000/01/rdf-schema#comment"
RDFS_SUBCLASS = "http://www.w3.org/2000/01/rdf-schema#subClassOf"
RDFS_SUBPROPERTY = "http://www.w3.org/2000/01/rdf-schema#subPropertyOf"
RDFS_DOMAIN = "http://www.w3.org/2000/01/rdf-schema#domain"
RDFS_RANGE = "http://www.w3.org/2000/01/rdf-schema#range"
RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"
H2KG_HAS_QUANTITY_VALUE = H2KG_NS + "hasQuantityValue"
QUDT_UNIT = "http://qudt.org/schema/qudt/unit"
QUDT_QUANTITY_KIND = "http://qudt.org/schema/qudt/quantityKind"

_VISIBLE_BRAND_PATTERN = re.compile(r"\bH2KG\b")
_PROTECTED_HTML_BLOCK_PATTERN = re.compile(
    r"<(?P<protected_tag>code|pre|script|style)\b[^>]*>.*?</(?P=protected_tag)\s*>",
    flags=re.IGNORECASE | re.DOTALL,
)
_HTML_TAG_PATTERN = re.compile(r"(<[^>]+>)")
_VISIBLE_BRAND_RUNTIME = """
<script data-h2kg-branding>
(() => {
  const brand = (value) => String(value || '').replace(/\\bH2KG\\b/g, 'H₂KG');
  const skipped = new Set(['CODE', 'PRE', 'SCRIPT', 'STYLE']);
  const updateText = (root) => {
    if (!root) return;
    if (root.nodeType === Node.TEXT_NODE) {
      if (!skipped.has(root.parentElement?.tagName)) root.nodeValue = brand(root.nodeValue);
      return;
    }
    if (root.nodeType !== Node.ELEMENT_NODE || skipped.has(root.tagName)) return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      if (!skipped.has(node.parentElement?.tagName)) node.nodeValue = brand(node.nodeValue);
    }
  };
  const start = () => {
    document.title = brand(document.title);
    updateText(document.body);
    new MutationObserver((records) => records.forEach((record) =>
      record.addedNodes.forEach(updateText)
    )).observe(document.body, {childList: true, subtree: true});
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
</script>
""".strip()


def build_docs(
    input_path: str | Path,
    output_dir: str | Path,
    config_dir: str | Path | None = None,
    fair_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    input_path = Path(input_path)
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
    alignment_registry_path = output_dir.parent / "ontology" / "external_alignment_registry.json"
    mappings = propose_mappings(input_path, output_dir.parent / "review", config_dir)
    mappings = _merge_external_alignment_mappings(
        mappings,
        alignment_registry_path,
    )
    mapping_summary = _load_alignment_summary(output_dir.parent / "reports")
    mapping_summary["accepted_count"] = len(mappings)
    alignment_registry = load_json(alignment_registry_path) if alignment_registry_path.exists() else {}
    alignment_report_path = output_dir.parent / "reports" / "tib_alignment_readiness.json"
    alignment_report = load_json(alignment_report_path) if alignment_report_path.exists() else {}
    mapping_summary.update(alignment_report)
    # The whole-ontology Explorer must expose the current asserted source, not
    # a potentially stale compact-module artifact.
    namespace_terms = _reference_terms_from_items(
        items,
        mappings,
        lambda iri, item: iri == H2KG_ONTOLOGY_IRI or iri.startswith(H2KG_NS),
    )
    taxonomy_registry_path = output_dir.parent / "ontology" / "taxonomy_registry.json"
    workflow_usage_registry_path = output_dir.parent / "ontology" / "workflow_usage_registry.json"
    taxonomy_artifact_path = output_dir.parent / "ontology" / "h2kg-v2-taxonomy.ttl"
    taxonomy_registry = load_json(taxonomy_registry_path) if taxonomy_registry_path.exists() else {}
    workflow_usage_registry = (
        load_json(workflow_usage_registry_path)
        if workflow_usage_registry_path.exists()
        else {}
    )
    if taxonomy_registry:
        namespace_terms = _merge_taxonomy_reference_terms(namespace_terms, taxonomy_registry, mappings)
        classes = [
            {
                "iri": str(term.get("iri", "")),
                "label": str(term.get("label", "")),
                "description": str(term.get("definition", "")),
                "domain": "",
                "range": "",
                "mappings": [],
            }
            for term in taxonomy_registry.get("terms", [])
            if term.get("disposition") == "active_local_class"
        ]
        classes.sort(key=lambda item: item["label"].casefold())
    if taxonomy_artifact_path.exists():
        taxonomy_artifact_terms = _reference_terms_from_artifact(taxonomy_artifact_path, items, mappings)
        schema_categories = {"Object Properties", "Datatype Properties", "Annotation Properties"}
        namespace_by_iri = {str(term["iri"]): term for term in namespace_terms}
        for term in taxonomy_artifact_terms:
            if term.get("category") in schema_categories:
                namespace_by_iri[str(term["iri"])] = term
        namespace_terms = sorted(
            namespace_by_iri.values(),
            key=lambda item: (_reference_category_order(str(item.get("category", ""))), str(item.get("label", "")).casefold()),
        )
        properties = [
            {
                "iri": str(term.get("iri", "")),
                "label": str(term.get("label", "")),
                "description": str(term.get("description", "")),
                "domain": ", ".join(_short_label(iri) for iri in _reference_relation_iris(term.get("domain", []))),
                "range": ", ".join(_short_label(iri) for iri in _reference_relation_iris(term.get("range", []))),
                "mappings": term.get("mappings", []),
            }
            for term in taxonomy_artifact_terms
            if term.get("category") in schema_categories
        ]
        properties.sort(key=lambda item: item["label"].casefold())
    core_terms = _reference_terms_from_artifact(output_dir.parent / "ontology" / "schema.ttl", items, mappings)
    pemfc_terms = _reference_terms_from_artifact(output_dir.parent / "ontology" / "pemfc_schema.ttl", items, mappings)
    pemwe_terms = _reference_terms_from_artifact(output_dir.parent / "ontology" / "pemwe_schema.ttl", items, mappings)
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
        "taxonomy_class_count": sum(
            1
            for term in taxonomy_registry.get("terms", [])
            if term.get("disposition") == "active_local_class"
        ),
    }
    explorer = _build_explorer_dataset(
        namespace_terms,
        items,
        taxonomy_registry,
        workflow_usage_registry,
    )
    alignment_evidence = _build_external_alignment_evidence(
        output_dir.parent / "benchmarks" / "tib_collections" / "h2kg_collection_coverage.csv",
        mappings,
    )
    decode_path = output_dir.parent / "decode" / "decode_federated_graph.json"
    decode = load_json(decode_path) if decode_path.exists() else None
    odk = load_odk_manifest(output_dir.parent)
    hdo = load_hdo_alignment_report(output_dir.parent / "reports")
    release = _release_snapshot_for_docs(output_dir, fair_snapshot, odk)

    page_specs: list[tuple[Path, str, str]] = [
        (output_dir / "hydrogen-ontology.html", "H2KG Namespace Reference", _namespace_reference_body(project, namespace_terms, output_dir / "hydrogen-ontology.html", output_dir)),
        (output_dir / "pages" / "user-guide.html", "User Guide", _user_guide_body()),
        (output_dir / "pages" / "ontology-overview.html", "Ontology Overview", _overview_body(project, summary, odk, hdo)),
        (output_dir / "pages" / "explore.html", "Explore H2KG", _explore_body(project, explorer, output_dir / "pages" / "explore.html", output_dir)),
        (output_dir / "pages" / "decode-workflows.html", "Explore DECODE Workflows", _decode_workflows_body(decode, output_dir / "pages" / "decode-workflows.html", output_dir)),
        (output_dir / "pages" / "reference.html", "H2KG Namespace Reference", _namespace_reference_body(project, namespace_terms, output_dir / "pages" / "reference.html", output_dir)),
        (output_dir / "pages" / "core-reference.html", "Core H2KG Reference", _core_reference_body(project, core_terms, output_dir / "pages" / "core-reference.html", output_dir)),
        (output_dir / "pages" / "class-index.html", "Class Index", _class_body(classes)),
        (output_dir / "pages" / "property-index.html", "Property Index", _property_body(properties)),
        (output_dir / "pages" / "alignment.html", "Alignment", _alignment_body(mappings, mapping_summary, alignment_registry)),
        (output_dir / "pages" / "examples.html", "Examples", _examples_body(examples)),
        (output_dir / "pages" / "quality-dashboard.html", "Quality Dashboard", _quality_body(release, odk, hdo)),
        (output_dir / "pages" / "release.html", "Release", _release_body(release, odk, hdo, alignment_report, output_dir / "pages" / "release.html", output_dir)),
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
        if path.name == "decode-workflows.html":
            decode_css = _relative_href(path, output_dir / "assets" / "decode-workflows.css")
            decode_js = _relative_href(path, output_dir / "assets" / "decode-workflows.js")
            extra_head = (
                f'<link rel="stylesheet" href="{decode_css}">\n'
                '  <script src="https://cdn.jsdelivr.net/npm/cytoscape@3.29.2/dist/cytoscape.min.js"></script>\n'
                f'  <script defer src="{decode_js}"></script>'
            )
        write_text(path, _page_template(project, title, body, path, output_dir, extra_head=extra_head))

    write_text(output_dir / "index.html", _legacy_profile_home())
    _copy_site_assets(output_dir, project)
    if decode is not None:
        # Publish normalized projections and reports, never the supplied raw GraphML files.
        shutil.copytree(output_dir.parent / "decode", output_dir / "decode", dirs_exist_ok=True)
    itc_example_dir = output_dir.parent / "examples" / "itc_pilot"
    if itc_example_dir.exists():
        shutil.copytree(itc_example_dir, output_dir / "examples" / "itc_pilot", dirs_exist_ok=True)
    _copy_odk_artifacts(output_dir)
    _copy_taxonomy_artifacts(output_dir)
    _copy_asserted_source_jsonld(input_path, output_dir)
    write_text(output_dir / "assets" / "style.css", _style_css())
    write_text(output_dir / "assets" / "explorer.css", _explorer_css())
    write_text(output_dir / "assets" / "explorer.js", _explorer_js())
    write_text(output_dir / "assets" / "decode-workflows.css", _decode_workflows_css())
    write_text(output_dir / "assets" / "decode-workflows.js", _decode_workflows_js())
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
    dump_json(output_dir / "data" / "external_alignment_evidence.json", alignment_evidence)
    if decode is not None:
        dump_json(output_dir / "data" / "decode_workflow_catalog.json", decode.get("workflows", []))
        dump_json(output_dir / "data" / "decode_workflows.json", decode)
    _modernize_legacy_profile_content(output_dir)
    _normalize_visible_branding(output_dir)
    return summary


def _normalize_visible_branding(output_dir: Path) -> None:
    """Use H₂KG in rendered text without modifying code, paths, or IRIs."""

    for path in output_dir.rglob("*.html"):
        content = path.read_text(encoding="utf-8")
        if "data-h2kg-branding" not in content and "</body>" in content:
            content = content.replace("</body>", f"  {_VISIBLE_BRAND_RUNTIME}\n</body>")
        write_text(path, _subscript_visible_brand_text(content))


def _subscript_visible_brand_text(content: str) -> str:
    chunks: list[str] = []
    cursor = 0
    for match in _PROTECTED_HTML_BLOCK_PATTERN.finditer(content):
        chunks.append(_replace_brand_in_html_text_nodes(content[cursor : match.start()]))
        chunks.append(match.group(0))
        cursor = match.end()
    chunks.append(_replace_brand_in_html_text_nodes(content[cursor:]))
    return "".join(chunks)


def _replace_brand_in_html_text_nodes(content: str) -> str:
    parts = _HTML_TAG_PATTERN.split(content)
    return "".join(
        part if part.startswith("<") else _VISIBLE_BRAND_PATTERN.sub("H₂KG", part)
        for part in parts
    )


def _modernize_legacy_profile_content(output_dir: Path) -> None:
    """Preserve established profile pages while removing superseded v1 wording."""
    replacements = {
        "FAIR, EMMO-aligned documentation": "Domain-specific H2KG documentation",
        "An EMMO-aligned application ontology release profile": "A domain-specific H2KG ontology profile",
        "A release-ready, FAIR-oriented, EMMO-aligned application ontology": "A domain-specific H2KG application ontology",
        "EMMO-aligned ontology": "domain-specific ontology",
        "EMMO-aligned": "domain-specific",
        "domain-review-required": "approved",
        "pending-domain-review": "approved",
        "release candidate": "release",
        "release-candidate": "release",
    }
    for profile_key in ("pemfc", "pemwe"):
        profile_root = output_dir / profile_key
        candidates = list((profile_root / "pages").glob("*.html"))
        candidates.extend((profile_root / "data").glob("*.json"))
        candidates.extend((profile_root / "assets").glob("*.js"))
        for path in candidates:
            content = path.read_text(encoding="utf-8")
            updated = re.sub(
                r"file:///[A-Za-z]:/[A-Za-z0-9._~%+:/-]*",
                lambda match: portable_legacy_iri(match.group(0)),
                content,
            )
            if path.suffix == ".js":
                updated = updated.replace('"file:///"', '"file:" + "///"')
            for old, new in replacements.items():
                updated = updated.replace(old, new)
            if updated != content:
                write_text(path, updated)


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


def _mapping_doc_record(mapping: dict[str, Any]) -> dict[str, Any]:
    collections = mapping.get("collections", [])
    if isinstance(collections, str):
        collections = [value.strip() for value in collections.split("|") if value.strip()]
    return {
        "relation": str(mapping.get("relation", "")),
        "target_iri": str(mapping.get("target_iri", "")),
        "target_label": str(mapping.get("target_label", "")),
        "ontology_id": str(mapping.get("tib_ontology_id") or mapping.get("source") or ""),
        "ontology_title": str(mapping.get("tib_ontology_title", "")),
        "ontology_version": str(mapping.get("tib_ontology_version", "")),
        "collections": [str(value) for value in collections if value],
        "confidence": str(mapping.get("confidence") or mapping.get("score") or ""),
        "evidence": str(mapping.get("mapping_evidence") or mapping.get("rationale") or ""),
        "rule_id": str(mapping.get("rule_id", "")),
        "alignment_category": str(mapping.get("alignment_category", "")),
        "publication_status": str(mapping.get("publication_status", "asserted")),
        "tib_catalogue_url": str(mapping.get("tib_catalogue_url", "")),
        "snapshot_retrieved_at": str(mapping.get("tib_snapshot_retrieved_at", "")),
    }


def _mapping_relation_label(relation: str) -> str:
    return {
        "skos:exactMatch": "exact equivalent",
        "skos:broadMatch": "H2KG narrower than",
        "skos:narrowMatch": "H2KG broader than",
        "skos:relatedMatch": "related to",
        "owl:equivalentClass": "reviewed equivalent class",
        "owl:equivalentProperty": "reviewed equivalent property",
        "rdfs:subClassOf": "reviewed subclass of",
        "rdfs:subPropertyOf": "reviewed subproperty of",
    }.get(relation, relation or "mapping")


def _reference_terms_from_artifact(
    artifact_path: Path,
    items: dict[str, dict[str, Any]],
    mappings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    selected = _artifact_subjects(artifact_path)
    artifact_items = items
    if Graph is not None and artifact_path.exists():
        artifact_graph = Graph().parse(artifact_path)
        serialized = json.loads(str(artifact_graph.serialize(format="json-ld")))
        merged = merge_document_items(list(items.values()) + (serialized if isinstance(serialized, list) else [serialized]))
        artifact_items = {
            str(item["@id"]): item
            for item in merged
            if isinstance(item.get("@id"), str)
        }
    mapping_index: dict[str, list[dict[str, Any]]] = {}
    for mapping in mappings:
        mapping_index.setdefault(mapping["local_iri"], []).append(_mapping_doc_record(mapping))
    records: dict[str, dict[str, Any]] = {}
    for iri in selected:
        item = artifact_items.get(iri, {"@id": iri})
        parents = _parent_links(item)
        records[iri] = {
            "iri": iri,
            "anchor": _term_anchor_for_iri(iri),
            "label": best_label(item),
            "description": best_description(item) or "No description available in the source ontology.",
            "alt_labels": _literal_values(item.get(SKOS_ALT_LABEL)),
            "notations": _literal_values(item.get(SKOS_NOTATION)),
            "sources": _iri_or_literal_values(item.get(DCTERMS_SOURCE)),
            "quantity_guidance": _quantity_guidance(item, artifact_items),
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
    mapping_index: dict[str, list[dict[str, Any]]] = {}
    for mapping in mappings:
        mapping_index.setdefault(mapping["local_iri"], []).append(_mapping_doc_record(mapping))
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
            "notations": _literal_values(item.get(SKOS_NOTATION)),
            "sources": _iri_or_literal_values(item.get(DCTERMS_SOURCE)),
            "quantity_guidance": _quantity_guidance(item, items),
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


def _merge_taxonomy_reference_terms(
    source_terms: list[dict[str, Any]],
    taxonomy_registry: dict[str, Any],
    mappings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Overlay the clean v2 hierarchy on the backward-compatible namespace reference."""

    records = {str(term["iri"]): dict(term) for term in source_terms}
    taxonomy_terms = {
        str(term.get("iri", "")): term
        for term in taxonomy_registry.get("terms", [])
        if term.get("iri")
        and term.get("disposition") in {"active_local_class", "deprecated_compatibility_class"}
    }
    mapping_index: dict[str, list[dict[str, Any]]] = {}
    for mapping in mappings:
        mapping_index.setdefault(str(mapping.get("local_iri", "")), []).append(_mapping_doc_record(mapping))
    for iri, taxonomy in taxonomy_terms.items():
        record = records.get(
            iri,
            {
                "iri": iri,
                "anchor": _term_anchor_for_iri(iri),
                "alt_labels": [],
                "notations": [],
                "sources": [],
                "quantity_guidance": [],
                "examples": [],
                "notes": [],
                "domain": [],
                "range": [],
                "parents": [],
                "subclasses": [],
                "subproperties": [],
                "mappings": [],
            },
        )
        parent_iri = str(taxonomy.get("parent_iri", "")).strip()
        record_mappings = {
            (str(item.get("relation", "")), str(item.get("target_iri", ""))): item
            for item in [*record.get("mappings", []), *mapping_index.get(iri, [])]
            if item.get("relation") and item.get("target_iri")
        }
        record.update(
            {
                "label": str(taxonomy.get("label") or record.get("label") or _short_label(iri)),
                "description": str(taxonomy.get("definition") or record.get("description") or "No definition recorded."),
                "alt_labels": sorted(set(record.get("alt_labels", [])) | set(taxonomy.get("alt_labels", []))),
                "notations": sorted(set(record.get("notations", [])) | set(taxonomy.get("notations", []))),
                "parents": (
                    [{"relation": "subclassOf", "iri": parent_iri, "label": str(taxonomy.get("parent_label", "")), "anchor": _term_anchor_for_iri(parent_iri)}]
                    if parent_iri
                    else []
                ),
                "subclasses": [],
                "mappings": sorted(
                    record_mappings.values(),
                    key=lambda item: (str(item.get("relation", "")), str(item.get("target_iri", ""))),
                ),
                "type_labels": ["Class", str(taxonomy.get("corrected_semantic_role", "Class"))],
                "category": "Classes",
            }
        )
        records[iri] = record

    for iri, taxonomy in taxonomy_terms.items():
        parent_iri = str(taxonomy.get("parent_iri", "")).strip()
        if not parent_iri or parent_iri not in records:
            continue
        records[parent_iri].setdefault("subclasses", []).append(
            {
                "iri": iri,
                "label": str(taxonomy.get("label", "")),
                "anchor": _term_anchor_for_iri(iri),
            }
        )
    for record in records.values():
        record["subclasses"] = sorted(
            {item["iri"]: item for item in record.get("subclasses", [])}.values(),
            key=lambda item: str(item.get("label", "")).casefold(),
        )
    return sorted(
        records.values(),
        key=lambda item: (_reference_category_order(item["category"]), str(item.get("label", "")).casefold()),
    )


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


def _iri_or_literal_values(value: Any) -> list[str]:
    values = value if isinstance(value, list) else [value] if value is not None else []
    result: list[str] = []
    for entry in values:
        candidate = entry.get("@id") or entry.get("@value") if isinstance(entry, dict) else entry
        if isinstance(candidate, str) and candidate.strip() and candidate not in result:
            result.append(candidate.strip())
    return result


def _quantity_guidance(item: dict[str, Any], items: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    guidance: list[dict[str, str]] = []
    for value in item.get(H2KG_HAS_QUANTITY_VALUE, []) if isinstance(item.get(H2KG_HAS_QUANTITY_VALUE), list) else [item.get(H2KG_HAS_QUANTITY_VALUE)]:
        iri = value.get("@id", "") if isinstance(value, dict) else ""
        target = items.get(iri, {})
        if not target:
            continue
        units = _iri_or_literal_values(target.get(QUDT_UNIT))
        kinds = _iri_or_literal_values(target.get(QUDT_QUANTITY_KIND))
        descriptions = _literal_values(target.get(DCTERMS_DESCRIPTION))
        guidance.append({
            "iri": iri,
            "unit": units[0] if units else "",
            "quantity_kind": kinds[0] if kinds else "",
            "description": descriptions[0] if descriptions else "",
        })
    return guidance


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


def _reference_relation_iris(value: Any) -> list[str]:
    """Return relation targets from normalized reference records or JSON-LD."""

    values = value if isinstance(value, list) else [value] if value is not None else []
    result: list[str] = []
    for entry in values:
        if isinstance(entry, dict):
            candidate = entry.get("iri") or entry.get("@id")
        else:
            candidate = entry
        if isinstance(candidate, str) and candidate.strip() and candidate.strip() not in result:
            result.append(candidate.strip())
    return result


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
    if "http://www.w3.org/2002/07/owl#AnnotationProperty" in type_set:
        return "Annotation Properties"
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
        "Annotation Properties": 4,
        "Measurements": 5,
        "Instruments": 6,
        "Materials": 7,
        "Parameters": 8,
        "Properties": 9,
        "Manufacturing / Processes": 10,
        "Data / Metadata": 11,
        "Normalization Bases": 12,
        "Other Terms": 13,
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


def _decode_workflows_body(decode: dict[str, Any] | None, page_path: Path, docs_root: Path) -> str:
    if decode is None:
        return """
<section class="notice"><h2>DECODE workflow bundle not built</h2><p>The DECODE Explorer is generated only after a reviewed GraphML snapshot has been ingested. The H2KG ontology and its TBox-only Explore page remain available independently.</p></section>
"""
    data_href = _relative_href(page_path, docs_root / "data" / "decode_workflows.json")
    catalogue_href = _relative_href(page_path, docs_root / "data" / "decode_workflow_catalog.json")
    h2kg_explore = _relative_href(page_path, docs_root / "pages" / "explore.html")
    ontology_ttl = _relative_href(page_path, docs_root / "decode" / "decode-h2kg-aligned-ontology.ttl")
    ontology_jsonld = _relative_href(page_path, docs_root / "decode" / "decode-h2kg-aligned-ontology.jsonld")
    ontology_validation = _relative_href(page_path, docs_root / "decode" / "decode_ontology_validation_report.json")
    counts = decode.get("counts", {})
    return f"""
<section class="decode-intro">
  <p class="eyebrow">Separate aligned workflow layer</p>
  <h2>Federated DECODE workflow graph</h2>
  <p>The 120 original GraphML workflows remain immutable. Sanitized manual-JSON workflows are added as source-backed overlays, and cross-workflow traversal uses reviewed shared anchors plus a separate evidence-bearing method-dependency layer. The H2KG TBox and its Explore page are unchanged.</p>
  <p>The merged <strong>DECODE H2KG-Aligned Workflow Ontology</strong> publishes the complete catalogue as a provenance-preserving H2KG-aligned graph. DECODE definitions are expert drafts pending human review. The DECODE reuse license is pending governance confirmation; no open license is asserted for these ontology files.</p>
  <div class="decode-ontology-downloads">
    <a href="{escape(ontology_ttl)}" download>Download ontology (Turtle)</a>
    <a href="{escape(ontology_jsonld)}" download>Download ontology (JSON-LD)</a>
    <a href="{escape(ontology_validation)}" download>Download ontology validation</a>
  </div>
  <div class="decode-metrics">
    <span><strong>{counts.get('workflow_count', 0)}</strong> catalogue entries</span>
    <span><strong>{counts.get('base_graphml_workflow_count', 120)}</strong> GraphML sources</span>
    <span><strong>{counts.get('manual_workflow_count', 16)}</strong> manual JSON sources</span>
    <span><strong>{counts.get('derived_workflow_count', 0)}</strong> PDF-derived interface schemas</span>
    <span><strong>{counts.get('source_node_count', 0)}</strong> source occurrences</span>
    <span><strong>{counts.get('source_edge_count', 0)}</strong> preserved dependencies</span>
    <span><strong>{counts.get('edge_classification_count', 0)}</strong> classified dependencies</span>
    <span><strong>{counts.get('anchor_count', 0)}</strong> reviewed shared anchors</span>
    <span><strong>{counts.get('published_workflow_dependency_count', 0)}</strong> published method dependencies</span>
  </div>
</section>
<section id="decode-root" class="decode-root" data-decode-data="{escape(data_href)}" data-decode-catalogue="{escape(catalogue_href)}" data-h2kg-explore="{escape(h2kg_explore)}">
  <div class="decode-search-panel">
    <div class="decode-search-fields">
      <div><label for="decode-search">Search workflows and terms</label><input id="decode-search" type="search" placeholder="Start typing a method, term, partner or H2KG IRI" autocomplete="off"></div>
      <div><label for="decode-family">Method family</label><select id="decode-family"><option value="">All method families</option></select></div>
    </div>
    <p id="decode-catalogue-status" class="decode-search-status" aria-live="polite">Search for a workflow or select a method family to begin.</p>
    <div id="decode-workflow-list" class="decode-workflow-list" hidden></div>
  </div>
  <div class="decode-stage">
    <div class="decode-workspace">
      <div id="decode-controls" class="decode-controls" hidden>
      <fieldset class="decode-view-switch"><legend>Graph view</legend><label><input name="decode-view" value="source" type="radio" checked> Preserved source occurrences</label><label><input name="decode-view" value="semantic" type="radio"> Semantic overview</label></fieldset>
      <label id="decode-source-control"><input id="decode-show-source" type="checkbox" checked> <span id="decode-source-label">Source dependencies</span></label>
      <label id="decode-anchor-control"><input id="decode-show-anchors" type="checkbox" checked> Shared anchors</label>
      <label><input id="decode-show-semantic" type="checkbox" checked> Semantic projections</label>
      <label><input id="decode-show-dependencies" type="checkbox" checked> Workflow dependencies</label>
      <label for="decode-semantic-filter">Projection outcome</label>
      <select id="decode-semantic-filter"><option value="all">All classifications</option><option value="h2kg_direct">H2KG direct</option><option value="h2kg_reified">H2KG reified</option><option value="prov_derivation">PROV derivation</option><option value="decode_structural_only">DECODE structural only</option></select>
      <button id="decode-reset" type="button">Reset graph</button>
      <button id="decode-more" type="button" hidden>Add next connected workflow</button>
      </div>
      <div class="decode-graph-frame">
        <div id="decode-empty-state" class="decode-empty-state"><strong>Select a workflow to open its graph</strong><span>Use the search field or method-family filter above. The complete federated graph is loaded only after selection.</span></div>
        <div id="decode-graph" aria-label="Interactive DECODE workflow graph" hidden></div>
      </div>
      <p id="decode-legend" class="decode-legend" hidden></p>
    </div>
    <aside id="decode-details" class="decode-details"><h2>Workflow details</h2><p>Select a workflow above. Its preserved source topology and reviewed semantic projections will appear in the graph workspace.</p></aside>
  </div>
  <aside id="decode-hovercard" class="decode-hovercard is-hidden" aria-live="polite"></aside>
</section>
"""


def _decode_workflows_css() -> str:
    return """
.decode-intro { margin: 1.2rem 0; padding: 1.2rem; border: 1px solid #c9d9dd; border-radius: 16px; background: linear-gradient(135deg, #eff8f7, #fbf5ea); }
.decode-intro h2 { margin: .15rem 0 .5rem; }
.decode-ontology-downloads { display: flex; flex-wrap: wrap; gap: .65rem; margin: .9rem 0; }
.decode-ontology-downloads a { display: inline-block; padding: .55rem .8rem; border-radius: 8px; background: #126d78; color: #fff; font-weight: 700; text-decoration: none; }
.decode-ontology-downloads a:hover, .decode-ontology-downloads a:focus { background: #0b4f57; }
.decode-metrics { display: flex; flex-wrap: wrap; gap: .6rem; margin-top: .8rem; }
.decode-metrics span { padding: .38rem .65rem; background: #fff; border: 1px solid #d7e1e2; border-radius: 999px; color: #40545c; }
.decode-metrics strong { color: #0d7077; }
.decode-root { position: relative; border: 1px solid #cad9dd; border-radius: 16px; overflow: visible; background: #fff; box-shadow: 0 14px 38px rgba(18,49,57,.08); }
.decode-search-panel { position: relative; z-index: 12; padding: 1rem 1.1rem .8rem; border-bottom: 1px solid #d8e3e5; border-radius: 16px 16px 0 0; background: linear-gradient(110deg, #f4faf9, #fbf8f1); }
.decode-search-fields { display: grid; grid-template-columns: minmax(320px, 1fr) minmax(220px, 320px); gap: 1rem; align-items: end; }
.decode-search-fields label { display: block; margin: 0 0 .35rem; font-size: .82rem; font-weight: 700; color: #34515a; }
.decode-search-fields input, .decode-search-fields select { width: 100%; padding: .65rem .72rem; border: 1px solid #aebfc4; border-radius: 9px; background: #fff; color: #20373f; box-shadow: 0 2px 7px rgba(18,49,57,.04); }
.decode-search-fields input:focus, .decode-search-fields select:focus { outline: 3px solid rgba(13,127,131,.15); border-color: #0d7f83; }
.decode-search-status { min-height: 1.25rem; margin: .55rem 0 0; color: #5c6d73; font-size: .82rem; }
.decode-workflow-list { position: absolute; top: calc(100% - .35rem); left: 1.1rem; width: min(760px, calc(100% - 2.2rem)); max-height: 360px; overflow: auto; display: grid; gap: .45rem; padding: .65rem; border: 1px solid #b9cace; border-radius: 11px; background: rgba(255,255,255,.99); box-shadow: 0 18px 46px rgba(16,36,45,.2); }
.decode-workflow-list[hidden] { display: none; }
.decode-workflow-card { width: 100%; text-align: left; border: 1px solid #d0dddf; padding: .65rem; border-radius: 9px; color: #20373f; background: #fff; cursor: pointer; }
.decode-workflow-card:hover, .decode-workflow-card.active { border-color: #0d7f83; background: #e8f5f4; }
.decode-workflow-card strong, .decode-workflow-card small { display: block; }
.decode-workflow-card small { margin-top: .2rem; color: #5c6d73; line-height: 1.35; }
.decode-stage { display: grid; grid-template-columns: minmax(0, 1fr) 320px; min-height: 690px; }
.decode-workspace { min-width: 0; display: flex; flex-direction: column; background: #fff; border-radius: 0 0 0 16px; overflow: hidden; }
.decode-details { padding: 1rem; background: #f8fbfb; overflow: auto; border-left: 1px solid #d8e3e5; border-radius: 0 0 16px 0; max-height: 790px; }
.decode-controls { display: flex; gap: .7rem; align-items: center; flex-wrap: wrap; padding: .75rem; border-bottom: 1px solid #d8e3e5; font-size: .86rem; }
.decode-controls[hidden] { display: none; }
.decode-controls select { padding: .32rem .45rem; border: 1px solid #b8cbd0; border-radius: 6px; background: #fff; color: #29464e; }
.decode-view-switch { display: inline-flex; gap: .55rem; align-items: center; margin: 0; padding: .25rem .5rem; border: 1px solid #bfd0d3; border-radius: 7px; }.decode-view-switch legend { padding: 0 .18rem; color: #486168; font-size: .75rem; font-weight: 700; }.decode-view-switch label { white-space: nowrap; }
.decode-controls button { border: 1px solid #0d7f83; background: #fff; color: #0d666c; padding: .35rem .6rem; border-radius: 6px; cursor: pointer; font-weight: 700; }
.decode-graph-frame { position: relative; height: clamp(590px, 68vh, 760px); min-height: 590px; background: radial-gradient(circle at 20% 14%, rgba(13,127,131,.08), transparent 26%), #fff; }
#decode-graph { position: absolute; inset: 0; background: transparent; }
#decode-graph[hidden] { display: none; }
.decode-empty-state { position: absolute; inset: 0; display: grid; place-content: center; gap: .55rem; padding: 2rem; text-align: center; color: #526970; background: radial-gradient(circle at 50% 44%, rgba(13,127,131,.1), transparent 25%); }
.decode-empty-state[hidden], .decode-legend[hidden] { display: none; }
.decode-empty-state strong { font-size: 1.25rem; color: #183b43; }.decode-empty-state span { max-width: 560px; line-height: 1.55; }.decode-empty-state.is-loading strong::after { content: ' ...'; }
.decode-legend { margin: 0; padding: .6rem .8rem; border-top: 1px solid #d8e3e5; color: #52656e; font-size: .78rem; line-height: 1.9; }
.decode-legend span { display: inline-block; margin: 0 .4rem 0 0; font-weight: 700; }
.decode-legend .legend-material::before, .decode-legend .legend-component::before, .decode-legend .legend-data::before, .decode-legend .legend-device::before, .decode-legend .legend-process::before, .decode-legend .legend-h2kg::before, .decode-legend .legend-decode::before, .decode-legend .legend-matter::before, .decode-legend .legend-manufacturing::before, .decode-legend .legend-measurement::before, .decode-legend .legend-instrument::before, .decode-legend .legend-parameter::before, .decode-legend .legend-property::before, .decode-legend .legend-metadata::before, .decode-legend .legend-mixed::before, .decode-legend .legend-approved::before, .decode-legend .legend-reviewed::before, .decode-legend .legend-unresolved::before { content: ''; display: inline-block; width: .72rem; height: .72rem; margin-right: .22rem; border-radius: 50%; vertical-align: -.08rem; border: 1px solid rgba(18,39,47,.35); }
.decode-legend .legend-material::before { background: #0f6d7a; }.decode-legend .legend-component::before { background: #487eb0; }.decode-legend .legend-data::before { background: #5ca9c9; }.decode-legend .legend-device::before { background: #72808b; }.decode-legend .legend-process::before { background: #c86a2b; }.decode-legend .legend-h2kg::before { background: #0d7f83; }.decode-legend .legend-decode::before { background: #bd8529; }
.decode-legend .legend-matter::before { background: #0f6d7a; }.decode-legend .legend-manufacturing::before { background: #b45309; }.decode-legend .legend-measurement::before { background: #376caa; }.decode-legend .legend-instrument::before { background: #5d6b76; }.decode-legend .legend-parameter::before { background: #5d66a6; }.decode-legend .legend-property::before { background: #9d5549; }.decode-legend .legend-metadata::before { background: #98a3aa; }.decode-legend .legend-mixed::before { background: #adb8bd; border-color: #a63030; }.decode-legend .legend-approved::before { background: #fff; border: 3px solid #006f73; }.decode-legend .legend-reviewed::before { background: #fff; border: 3px solid #9a650b; }.decode-legend .legend-unresolved::before { background: #fff; border: 2px dashed #718088; }
.legend-source { color: #45555d; }.legend-anchor { color: #a25b00; }.legend-semantic { color: #087f71; }.legend-dependency { color: #7c3aed; }
.decode-details h2 { margin-top: 0; }.decode-details h3 { margin: 1rem 0 .35rem; font-size: .98rem; }.decode-details p, .decode-details li { font-size: .88rem; line-height: 1.45; overflow-wrap: anywhere; }.decode-details ul { padding-left: 1.1rem; }.decode-details a { color: #087279; }.decode-details code { font-size: .76rem; }
.decode-status { display: inline-block; padding: .18rem .4rem; border-radius: 999px; background: #e8f5f4; color: #075e63; font-size: .73rem; font-weight: 700; }.decode-status.unresolved { background: #f5ece5; color: #86521c; }.decode-downloads { display: grid; gap: .35rem; margin-top: .8rem; }
.decode-hovercard { position: fixed; z-index: 30; width: min(380px, calc(100vw - 24px)); max-height: min(440px, calc(100vh - 24px)); overflow: auto; padding: .85rem 1rem; border: 1px solid #b5c7cb; border-radius: 13px; background: rgba(255,255,255,.98); box-shadow: 0 16px 40px rgba(16,36,45,.23); color: #20373f; pointer-events: none; }.decode-hovercard.is-hidden { display: none; }.decode-hovercard h3 { margin: 0 0 .35rem; font-size: 1rem; }.decode-hovercard p { margin: .3rem 0; font-size: .8rem; line-height: 1.35; }.decode-hovercard code { font-size: .72rem; overflow-wrap: anywhere; }.decode-hovercard .decode-status { margin-right: .35rem; }.decode-add-workflow { display: block; width: 100%; margin: .4rem 0; padding: .45rem .55rem; border: 1px solid #a7b9bd; border-radius: 7px; background: #f8fbfb; color: #183139; text-align: left; cursor: pointer; }.decode-add-workflow:hover { border-color: #0d7f83; background: #eaf6f6; }
@media (max-width: 1080px) { .decode-stage { grid-template-columns: 1fr; }.decode-details { border-left: 0; border-top: 1px solid #d8e3e5; border-radius: 0 0 16px 16px; max-height: 300px; }.decode-workspace { border-radius: 0; } }
@media (max-width: 700px) { .decode-search-fields { grid-template-columns: 1fr; gap: .55rem; }.decode-workflow-list { left: .65rem; width: calc(100% - 1.3rem); }.decode-graph-frame { height: 600px; min-height: 600px; }.decode-controls { align-items: flex-start; }.decode-view-switch { display: grid; }.decode-stage { min-height: 0; } }
"""


def _decode_workflows_js_legacy() -> str:
    return r"""
(() => {
  const root = document.getElementById('decode-root');
  if (!root || !window.cytoscape) return;
  const byId = (items) => Object.fromEntries(items.map((item) => [item.id, item]));
  const text = (value) => String(value || '').toLowerCase();
  const escapeHtml = (value) => String(value || '').replace(/[&<>'"]/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const query = (selector) => document.querySelector(selector);
  const graphElement = query('#decode-graph');
  const details = query('#decode-details');
  const showSource = query('#decode-show-source');
  const showAnchors = query('#decode-show-anchors');
  const showSemantic = query('#decode-show-semantic');
  const moreButton = query('#decode-more');
  let data, cy, selectedWorkflow, selectedAnchor, expansion = 12, shown = new Set();

  fetch(root.dataset.decodeData).then((response) => response.json()).then((loaded) => { data = loaded; initialize(); }).catch((error) => { details.innerHTML = `<h2>Workflow data unavailable</h2><p>${escapeHtml(error.message)}</p>`; });

  function initialize() {
    data.nodeById = byId(data.nodes);
    data.anchorById = byId(data.anchors);
    data.workflowById = byId(data.workflows);
    data.edgesByNode = {};
    data.source_edges.forEach((edge) => { (data.edgesByNode[edge.source] ||= []).push(edge); (data.edgesByNode[edge.target] ||= []).push(edge); });
    const families = [...new Set(data.workflows.map((workflow) => workflow.method_family))].sort();
    const family = query('#decode-family');
    families.forEach((name) => family.insertAdjacentHTML('beforeend', `<option value="${escapeHtml(name)}">${escapeHtml(name.replaceAll('_', ' '))}</option>`));
    query('#decode-search').addEventListener('input', renderCatalogue);
    family.addEventListener('change', renderCatalogue);
    [showSource, showAnchors, showSemantic].forEach((input) => input.addEventListener('change', renderGraph));
    query('#decode-reset').addEventListener('click', () => selectWorkflow(selectedWorkflow));
    moreButton.addEventListener('click', () => { expansion += 12; expandAnchor(selectedAnchor); });
    renderCatalogue();
    selectWorkflow(data.workflows[0]?.id);
  }

  function renderCatalogue() {
    const needle = text(query('#decode-search').value);
    const family = query('#decode-family').value;
    const matches = data.workflows.filter((workflow) => {
      const haystack = [workflow.title, workflow.source_filename, workflow.method_family, workflow.mapping_status, workflow.iri].join(' ').toLowerCase();
      return (!needle || haystack.includes(needle)) && (!family || workflow.method_family === family);
    });
    query('#decode-catalogue-status').textContent = `${matches.length} of ${data.workflows.length} workflows`;
    query('#decode-workflow-list').innerHTML = matches.map((workflow) => `<button class="decode-workflow-card ${workflow.id === selectedWorkflow ? 'active' : ''}" data-workflow="${escapeHtml(workflow.id)}"><strong>${escapeHtml(workflow.title)}</strong><small>${escapeHtml(workflow.method_family.replaceAll('_',' '))} | ${workflow.source_node_count} nodes, ${workflow.source_edge_count} edges</small><small>${workflow.mapped_anchor_count} reviewed mappings | ${workflow.cross_workflow_connection_count} cross-workflow links</small></button>`).join('');
    document.querySelectorAll('[data-workflow]').forEach((button) => button.addEventListener('click', () => selectWorkflow(button.dataset.workflow)));
  }

  function selectWorkflow(workflowId) {
    if (!workflowId || !data.workflowById[workflowId]) return;
    selectedWorkflow = workflowId; selectedAnchor = null; expansion = 12;
    shown = new Set(data.nodes.filter((node) => node.workflow_id === workflowId).map((node) => node.id));
    renderCatalogue(); renderGraph(); showWorkflowDetails(data.workflowById[workflowId]);
  }

  function elementSet() {
    const visible = new Set(shown);
    const elements = [];
    [...visible].forEach((id) => { const node = data.nodeById[id]; if (node) elements.push({ group:'nodes', data:{ id:node.id, label:node.label, kind:'occurrence', state:node.mapping_state, workflow:node.workflow_id } }); });
    if (showAnchors.checked) {
      const anchorIds = new Set([...visible].map((id) => data.nodeById[id]?.anchor_id).filter(Boolean));
      anchorIds.forEach((id) => { const anchor = data.anchorById[id]; if (anchor) elements.push({ group:'nodes', data:{ id:anchor.id, label:anchor.label, kind:'anchor', state:anchor.state } }); });
      data.anchor_edges.filter((edge) => visible.has(edge.source) && anchorIds.has(edge.target)).forEach((edge) => elements.push({ group:'edges', data:{ id:edge.id, source:edge.source, target:edge.target, kind:'anchor' } }));
    }
    if (showSource.checked) data.source_edges.filter((edge) => visible.has(edge.source) && visible.has(edge.target)).forEach((edge) => elements.push({ group:'edges', data:{ id:edge.id, source:edge.source, target:edge.target, kind:'source' } }));
    if (showSemantic.checked) data.semantic_edges.filter((edge) => visible.has(edge.source) && visible.has(edge.target)).forEach((edge) => elements.push({ group:'edges', data:{ id:edge.id, source:edge.source, target:edge.target, label:edge.label, kind:'semantic' } }));
    return elements;
  }

  function renderGraph() {
    if (cy) cy.destroy();
    cy = cytoscape({ container:graphElement, elements:elementSet(), style:[
      { selector:'node', style:{ 'label':'data(label)', 'font-size':10, 'text-wrap':'wrap', 'text-max-width':120, 'color':'#1d3138', 'text-valign':'center', 'text-halign':'center', 'border-width':2, 'background-color':'#d9e7e8', 'border-color':'#4f6a70', 'width':62, 'height':62 } },
      { selector:'node[kind = "anchor"]', style:{ 'shape':'round-rectangle', 'background-color':'#fff1d8', 'border-color':'#a96200', 'width':110, 'height':46, 'font-weight':700 } },
      { selector:'node[state = "unresolved"]', style:{ 'background-color':'#f2e9e2', 'border-color':'#936a41' } },
      { selector:'edge[kind = "source"]', style:{ 'width':2, 'line-color':'#596c72', 'target-arrow-color':'#596c72', 'target-arrow-shape':'triangle', 'curve-style':'bezier' } },
      { selector:'edge[kind = "anchor"]', style:{ 'width':1.5, 'line-style':'dashed', 'line-color':'#b87918', 'target-arrow-shape':'none', 'curve-style':'bezier' } },
      { selector:'edge[kind = "semantic"]', style:{ 'width':2.5, 'line-color':'#087f71', 'target-arrow-color':'#087f71', 'target-arrow-shape':'triangle', 'label':'data(label)', 'font-size':9, 'text-background-color':'#fff', 'text-background-opacity':.9, 'text-background-padding':2 } },
      { selector:'edge[kind = "dependency"]', style:{ 'width':3, 'line-color':'#7c3aed', 'target-arrow-color':'#7c3aed', 'target-arrow-shape':'triangle', 'line-style':'dashed', 'label':'data(label)', 'font-size':9, 'text-background-color':'#fff', 'text-background-opacity':.9, 'text-background-padding':2, 'curve-style':'bezier' } },
      { selector:'edge[kind = "dependency"][dependencyStatus = "published_pending_review"]', style:{ 'line-color':'#a16207', 'target-arrow-color':'#a16207', 'line-style':'dotted' } }
    ], layout:{ name:'cose', animate:false, padding:34, idealEdgeLength:100, nodeRepulsion:500000 } });
    cy.on('dbltap', 'node', (event) => { const item = event.target.data(); if (item.kind === 'anchor') expandAnchor(item.id); else expandOccurrence(item.id); });
    cy.on('tap', 'node', (event) => { const item = event.target.data(); if (item.kind === 'anchor') showAnchorDetails(item.id); else showOccurrenceDetails(item.id); });
  }

  function expandOccurrence(id) {
    const occurrence = data.nodeById[id];
    if (!occurrence?.anchor_id) { showOccurrenceDetails(id); return; }
    expansion = 12; expandAnchor(occurrence.anchor_id);
  }

  function expandAnchor(anchorId) {
    const occurrences = data.anchor_index[anchorId] || [];
    selectedAnchor = anchorId;
    occurrences.slice(0, expansion).forEach((id) => {
      shown.add(id);
      (data.edgesByNode[id] || []).forEach((edge) => { shown.add(edge.source); shown.add(edge.target); });
    });
    moreButton.hidden = occurrences.length <= expansion;
    moreButton.textContent = `Show more connected workflows (${Math.max(0, occurrences.length - expansion)} remaining)`;
    renderGraph(); showAnchorDetails(anchorId);
  }

  function downloadLinks(workflow) {
    return `<div class="decode-downloads"><a href="../decode/workflows/${encodeURIComponent(workflow.id)}.json" download>Download normalized workflow JSON</a><a href="../decode/workflows/${encodeURIComponent(workflow.id)}.jsonld" download>Download JSON-LD projection</a><a href="../decode/workflows/${encodeURIComponent(workflow.id)}.ttl" download>Download Turtle projection</a><a href="../decode/decode_mapping_matrix.csv" download>Download mapping matrix</a><a href="../decode/decode_validation_report.json" download>Download validation report</a></div>`;
  }

  function showWorkflowDetails(workflow) {
    details.innerHTML = `<h2>${escapeHtml(workflow.title)}</h2><p><span class="decode-status ${escapeHtml(workflow.mapping_status)}">${escapeHtml(workflow.mapping_status)}</span> <span class="decode-status">source preserved</span></p><p><strong>Source:</strong> ${escapeHtml(workflow.source_filename)}<br><strong>Method family:</strong> ${escapeHtml(workflow.method_family)}<br><strong>Topology:</strong> ${workflow.source_node_count} occurrences and ${workflow.source_edge_count} directed dependencies.</p><p>${workflow.mapped_anchor_count} occurrence mappings and ${workflow.cross_workflow_connection_count} reviewed cross-workflow connections are available. Raw GraphML is not redistributed.</p>${downloadLinks(workflow)}`;
  }

  function showOccurrenceDetails(id) {
    const node = data.nodeById[id]; if (!node) return;
    const workflow = data.workflowById[node.workflow_id];
    const anchorLink = node.anchor_id ? `<p><strong>Shared anchor:</strong> <a href="${root.dataset.h2kgExplore}?iri=${encodeURIComponent(node.anchor_id)}">${escapeHtml(data.anchorById[node.anchor_id]?.label || node.anchor_id)}</a></p>` : '<p><strong>Shared anchor:</strong> none. This occurrence remains isolated until reviewed.</p>';
    details.innerHTML = `<h2>${escapeHtml(node.label)}</h2><p><span class="decode-status ${escapeHtml(node.mapping_state)}">${escapeHtml(node.mapping_state)}</span></p><p><strong>Original GraphML ID:</strong> <code>${escapeHtml(node.source_id)}</code><br><strong>Workflow:</strong> ${escapeHtml(workflow.title)}<br><strong>Native category:</strong> ${escapeHtml(node.native_category || 'not supplied')}</p><p><strong>Source metadata:</strong> ${escapeHtml(node.description || 'not supplied')}</p>${anchorLink}<p><strong>Mapping evidence:</strong> ${escapeHtml(node.mapping_evidence)}</p>${downloadLinks(workflow)}`;
  }

  function showAnchorDetails(anchorId) {
    const anchor = data.anchorById[anchorId]; if (!anchor) return;
    const occurrences = (data.anchor_index[anchorId] || []).map((id) => data.nodeById[id]).filter(Boolean);
    const byFamily = occurrences.reduce((groups, node) => { const workflow = data.workflowById[node.workflow_id]; (groups[workflow.method_family] ||= []).push(node); return groups; }, {});
    const groups = Object.entries(byFamily).sort(([left], [right]) => left.localeCompare(right)).map(([family, nodes]) => { const workflows = [...new Set(nodes.map((node) => node.workflow_id))].map((workflowId) => data.workflowById[workflowId]); return `<li><strong>${escapeHtml(family.replaceAll('_', ' '))}</strong> (${nodes.length} occurrence${nodes.length === 1 ? '' : 's'} across ${workflows.length} workflows)<ul>${workflows.slice(0, 8).map((workflow) => `<li>${escapeHtml(workflow.title)} <span class="decode-status ${escapeHtml(workflow.mapping_status)}">${escapeHtml(workflow.mapping_status)}</span></li>`).join('')}</ul></li>`; }).join('');
    const h2kgLink = anchor.state === 'approved_h2kg' ? `<p><a href="${root.dataset.h2kgExplore}?iri=${encodeURIComponent(anchor.id)}">Inspect this stable H2KG term in H2KG Explore</a></p>` : '';
    details.innerHTML = `<h2>${escapeHtml(anchor.label)}</h2><p><span class="decode-status">${escapeHtml(anchor.state)}</span></p><p><code>${escapeHtml(anchor.id)}</code></p><p>${escapeHtml(anchor.evidence)}</p>${h2kgLink}<h3>Connected workflow occurrences (${occurrences.length})</h3><ul>${groups}</ul><p>Double-clicked expansion is bounded to keep the graph readable; use “show more connected workflows” to reveal additional reviewed occurrences.</p>`;
  }
})();
"""


def _decode_workflows_js_source() -> str:
    """Interactive, federated DECODE workflow graph viewer."""
    return r"""
(() => {
  const root = document.getElementById('decode-root');
  if (!root || !window.cytoscape) return;
  const $ = (selector) => document.querySelector(selector);
  const esc = (value) => String(value || '').replace(/[&<>'"]/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const lower = (value) => String(value || '').toLowerCase();
  const graph = $('#decode-graph'), details = $('#decode-details'), hover = $('#decode-hovercard');
  const sourceToggle = $('#decode-show-source'), anchorToggle = $('#decode-show-anchors'), semanticToggle = $('#decode-show-semantic'), dependencyToggle = $('#decode-show-dependencies'), semanticFilter = $('#decode-semantic-filter'), more = $('#decode-more');
  let data, cy, selectedWorkflow, selectedAnchor, shownWorkflows = new Set();

  fetch(root.dataset.decodeData).then((response) => response.json()).then((loaded) => { data = loaded; initialize(); }).catch((error) => { details.innerHTML = `<h2>Workflow data unavailable</h2><p>${esc(error.message)}</p>`; });

  function index(items) { return Object.fromEntries(items.map((item) => [item.id, item])); }
  function initialize() {
    data.nodeById = index(data.nodes); data.projectionNodeById = index(data.projection_nodes || []); data.anchorById = index(data.anchors); data.workflowById = index(data.workflows); data.edgeRegistryBySource = Object.fromEntries((data.edge_registry || []).map((row) => [row.source_dependency_id, row]));
    data.nodesByWorkflow = {}; data.nodes.forEach((node) => (data.nodesByWorkflow[node.workflow_id] ||= []).push(node.id));
    const family = $('#decode-family');
    [...new Set(data.workflows.map((workflow) => workflow.method_family))].sort().forEach((name) => family.insertAdjacentHTML('beforeend', `<option value="${esc(name)}">${esc(name.replaceAll('_', ' '))}</option>`));
    $('#decode-search').addEventListener('input', renderCatalogue); family.addEventListener('change', renderCatalogue);
    [sourceToggle, anchorToggle, semanticToggle, semanticFilter].forEach((input) => input.addEventListener('change', renderGraph));
    $('#decode-reset').addEventListener('click', () => selectWorkflow(selectedWorkflow));
    more.addEventListener('click', () => addNextConnectedWorkflow(selectedAnchor));
    renderCatalogue(); selectWorkflow(data.workflows[0]?.id);
  }

  function renderCatalogue() {
    const needle = lower($('#decode-search').value), family = $('#decode-family').value;
    const matches = data.workflows.filter((workflow) => (!needle || [workflow.title, workflow.source_filename, workflow.method_family, workflow.mapping_status, workflow.iri].join(' ').toLowerCase().includes(needle)) && (!family || workflow.method_family === family));
    $('#decode-catalogue-status').textContent = `${matches.length} of ${data.workflows.length} workflows`;
    $('#decode-workflow-list').innerHTML = matches.map((workflow) => `<button class="decode-workflow-card ${workflow.id === selectedWorkflow ? 'active' : ''}" data-workflow="${esc(workflow.id)}"><strong>${esc(workflow.title)}</strong><small>${esc(workflow.method_family.replaceAll('_',' '))} | ${workflow.source_node_count} nodes, ${workflow.source_edge_count} edges</small><small>${workflow.mapped_anchor_count} reviewed mappings | ${workflow.cross_workflow_connection_count} cross-workflow links</small></button>`).join('');
    document.querySelectorAll('[data-workflow]').forEach((button) => button.addEventListener('click', () => selectWorkflow(button.dataset.workflow)));
  }

  function selectWorkflow(workflowId) {
    if (!data.workflowById[workflowId]) return;
    selectedWorkflow = workflowId; selectedAnchor = null; shownWorkflows = new Set([workflowId]); more.hidden = true;
    renderCatalogue(); renderGraph(); showWorkflowDetails(data.workflowById[workflowId]);
  }
  function visibleNodeIds() { return new Set([...shownWorkflows].flatMap((workflowId) => data.nodesByWorkflow[workflowId] || [])); }
  function visibleAnchorIds(nodes) { return new Set([...nodes].map((id) => data.nodeById[id]?.anchor_id).filter(Boolean)); }

  function elements() {
    const nodes = visibleNodeIds(), anchors = visibleAnchorIds(nodes), output = [];
    [...nodes].forEach((id) => { const node = data.nodeById[id]; output.push({ group:'nodes', data:{ id, label:node.label, kind:'occurrence', state:node.mapping_state, visual:node.visual_category || 'other', workflow:node.workflow_id } }); });
    if (anchorToggle.checked) {
      [...anchors].forEach((id) => { const anchor = data.anchorById[id]; if (anchor) output.push({ group:'nodes', data:{ id, label:anchor.label, kind:'anchor', state:anchor.state } }); });
      data.anchor_edges.filter((edge) => nodes.has(edge.source) && anchors.has(edge.target)).forEach((edge) => output.push({ group:'edges', data:{ id:edge.id, source:edge.source, target:edge.target, kind:'anchor', label:'maps to' } }));
    }
    if (sourceToggle.checked) data.source_edges.filter((edge) => nodes.has(edge.source) && nodes.has(edge.target)).forEach((edge) => output.push({ group:'edges', data:{ id:edge.id, source:edge.source, target:edge.target, kind:'source', label:edge.label || 'source dependency' } }));
    if (semanticToggle.checked) data.semantic_edges.filter((edge) => nodes.has(edge.source) && nodes.has(edge.target)).forEach((edge) => output.push({ group:'edges', data:{ id:edge.id, source:edge.source, target:edge.target, kind:'semantic', label:edge.label } }));
    return output;
  }

  function renderGraph() {
    if (cy) cy.destroy();
    cy = cytoscape({ container:graph, elements:elements(), style:[
      { selector:'node', style:{ 'label':'data(label)', 'font-size':10, 'text-wrap':'wrap', 'text-max-width':118, 'color':'#183139', 'text-valign':'center', 'text-halign':'center', 'border-width':2, 'background-color':'#a9bcc0', 'border-color':'#50676d', 'width':60, 'height':60 } },
      { selector:'node[visual = "material"], node[visual = "component"]', style:{ 'background-color':'#0f6d7a', 'border-color':'#084f59', 'color':'#fff' } },
      { selector:'node[visual = "data"]', style:{ 'background-color':'#5ca9c9', 'border-color':'#2e7795' } },
      { selector:'node[visual = "device"]', style:{ 'background-color':'#72808b', 'border-color':'#4d5a64', 'color':'#fff' } },
      { selector:'node[visual = "process"], node[visual = "method"]', style:{ 'background-color':'#c86a2b', 'border-color':'#93430d', 'color':'#fff' } },
      { selector:'node[visual = "model"]', style:{ 'background-color':'#6d9c63', 'border-color':'#477442', 'color':'#fff' } },
      { selector:'node[kind = "anchor"][state = "approved_h2kg"]', style:{ 'shape':'round-rectangle', 'background-color':'#0d7f83', 'border-color':'#07575a', 'color':'#fff', 'width':116, 'height':48, 'font-weight':700 } },
      { selector:'node[kind = "anchor"][state = "reviewed_decode"]', style:{ 'shape':'round-rectangle', 'background-color':'#bd8529', 'border-color':'#855c12', 'color':'#fff', 'width':116, 'height':48, 'font-weight':700 } },
      { selector:'node[state = "unresolved"]', style:{ 'background-opacity':.55, 'border-style':'dashed' } },
      { selector:'node.hovered', style:{ 'border-color':'#f59e0b', 'border-width':5, 'z-index':999 } },
      { selector:'edge[kind = "source"]', style:{ 'width':2, 'line-color':'#596c72', 'target-arrow-color':'#596c72', 'target-arrow-shape':'triangle', 'curve-style':'bezier' } },
      { selector:'edge[kind = "anchor"]', style:{ 'width':1.5, 'line-style':'dashed', 'line-color':'#bd8529', 'curve-style':'bezier' } },
      { selector:'edge[kind = "semantic"]', style:{ 'width':2.5, 'line-color':'#087f71', 'target-arrow-color':'#087f71', 'target-arrow-shape':'triangle', 'label':'data(label)', 'font-size':9, 'text-background-color':'#fff', 'text-background-opacity':.9, 'text-background-padding':2 } }
    ], layout:{ name:'cose', animate:false, padding:34, idealEdgeLength:105, nodeRepulsion:520000 } });
    cy.on('dbltap', 'node', (event) => { const item = event.target.data(); const anchorId = item.kind === 'anchor' ? item.id : data.nodeById[item.id]?.anchor_id; if (anchorId) expandAnchor(anchorId); else showOccurrenceDetails(item.id); });
    cy.on('tap', 'node', (event) => event.target.data().kind === 'anchor' ? showAnchorDetails(event.target.id()) : showOccurrenceDetails(event.target.id()));
    cy.on('mouseover', 'node, edge', (event) => { event.target.addClass('hovered'); showHover(event.target, event.originalEvent); });
    cy.on('mousemove', 'node, edge', (event) => moveHover(event.originalEvent));
    cy.on('mouseout', 'node, edge', (event) => { event.target.removeClass('hovered'); hideHover(); });
  }

  function rankedConnectedWorkflows(anchorId) {
    const visibleAnchors = visibleAnchorIds(visibleNodeIds());
    const candidates = new Set((data.anchor_index[anchorId] || []).map((id) => data.nodeById[id]?.workflow_id).filter((id) => id && !shownWorkflows.has(id)));
    return [...candidates].sort((left, right) => { const leftAnchors = new Set((data.nodesByWorkflow[left] || []).map((id) => data.nodeById[id]?.anchor_id).filter(Boolean)); const rightAnchors = new Set((data.nodesByWorkflow[right] || []).map((id) => data.nodeById[id]?.anchor_id).filter(Boolean)); const leftScore = [...leftAnchors].filter((id) => visibleAnchors.has(id)).length, rightScore = [...rightAnchors].filter((id) => visibleAnchors.has(id)).length; return rightScore - leftScore || data.workflowById[left].title.localeCompare(data.workflowById[right].title); });
  }
  function expandAnchor(anchorId) { selectedAnchor = anchorId; const next = rankedConnectedWorkflows(anchorId)[0]; if (next) shownWorkflows.add(next); renderGraph(); showAnchorDetails(anchorId); updateMoreButton(); }
  function addNextConnectedWorkflow(anchorId) { if (anchorId) expandAnchor(anchorId); }
  function updateMoreButton() { const remaining = selectedAnchor ? rankedConnectedWorkflows(selectedAnchor).length : 0; more.hidden = !remaining; more.textContent = `Add next connected workflow (${remaining} remaining)`; }

  function downloads(workflow) { return `<div class="decode-downloads"><a href="../decode/workflows/${encodeURIComponent(workflow.id)}.json" download>Download normalized workflow JSON</a><a href="../decode/workflows/${encodeURIComponent(workflow.id)}.jsonld" download>Download JSON-LD projection</a><a href="../decode/workflows/${encodeURIComponent(workflow.id)}.ttl" download>Download Turtle projection</a><a href="../decode/decode_mapping_matrix.csv" download>Download mapping matrix</a><a href="../decode/decode_validation_report.json" download>Download validation report</a></div>`; }
  function showWorkflowDetails(workflow) { details.innerHTML = `<h2>${esc(workflow.title)}</h2><p><span class="decode-status ${esc(workflow.mapping_status)}">${esc(workflow.mapping_status)}</span> <span class="decode-status">source preserved</span></p><p><strong>Source:</strong> ${esc(workflow.source_filename)}<br><strong>Method family:</strong> ${esc(workflow.method_family)}<br><strong>Topology:</strong> ${workflow.source_node_count} occurrences and ${workflow.source_edge_count} directed dependencies.</p><p>The complete source workflow is visible. Double-click a reviewed occurrence or anchor to add one complete linked workflow.</p>${downloads(workflow)}`; }
  function showOccurrenceDetails(id) { const node = data.nodeById[id]; if (!node) return; const workflow = data.workflowById[node.workflow_id], anchor = data.anchorById[node.anchor_id]; const anchorText = anchor ? `<p><strong>Shared anchor:</strong> ${anchor.state === 'approved_h2kg' ? `<a href="${root.dataset.h2kgExplore}?iri=${encodeURIComponent(anchor.id)}">${esc(anchor.label)}</a>` : esc(anchor.label)}</p>` : '<p><strong>Shared anchor:</strong> unresolved; no cross-workflow join is available.</p>'; const role = node.canonical_role_iri ? `<p><strong>H2KG role:</strong> <a href="${root.dataset.h2kgExplore}?iri=${encodeURIComponent(node.canonical_role_iri)}">${esc(node.semantic_role || node.canonical_role_iri)}</a></p>` : ''; details.innerHTML = `<h2>${esc(node.label)}</h2><p><span class="decode-status ${esc(node.mapping_state)}">${esc(node.mapping_state)}</span></p><p><strong>Decision:</strong> ${esc(node.decision || 'unresolved')}<br><strong>Original GraphML ID:</strong> <code>${esc(node.source_id)}</code><br><strong>Workflow:</strong> ${esc(workflow.title)}<br><strong>Native category:</strong> ${esc(node.native_category || 'not supplied')}</p><p><strong>Source metadata:</strong> ${esc(node.description || 'not supplied')}</p>${anchorText}${role}<p><strong>Mapping evidence:</strong> ${esc(node.mapping_evidence || 'not supplied')}</p>${downloads(workflow)}`; }
  function showAnchorDetails(anchorId) { const anchor = data.anchorById[anchorId]; if (!anchor) return; const workflows = [...new Set((data.anchor_index[anchorId] || []).map((id) => data.nodeById[id]?.workflow_id).filter(Boolean))].map((id) => data.workflowById[id]); const candidates = rankedConnectedWorkflows(anchorId); const h2kg = anchor.state === 'approved_h2kg' ? `<p><a href="${root.dataset.h2kgExplore}?iri=${encodeURIComponent(anchor.id)}">Inspect this stable H2KG term in H2KG Explore</a></p>` : ''; const role = anchor.canonical_role_iri && anchor.state !== 'approved_h2kg' ? `<p><strong>H2KG role:</strong> <a href="${root.dataset.h2kgExplore}?iri=${encodeURIComponent(anchor.canonical_role_iri)}">${esc(anchor.semantic_role || anchor.canonical_role_iri)}</a></p>` : ''; const cards = candidates.slice(0,8).map((workflow) => `<button class="decode-add-workflow" data-add-workflow="${esc(workflow.id)}">Add full workflow: ${esc(workflow.title)}</button>`).join(''); details.innerHTML = `<h2>${esc(anchor.label)}</h2><p><span class="decode-status ${esc(anchor.state)}">${esc(anchor.state)}</span> ${esc(anchor.decision || '')}</p><p><code>${esc(anchor.id)}</code></p><p>${esc(anchor.evidence)}</p>${h2kg}${role}<h3>Linked workflows (${workflows.length})</h3><ul>${workflows.map((workflow) => `<li>${esc(workflow.title)}</li>`).join('')}</ul>${cards ? `<h3>Expand a connected workflow</h3>${cards}` : '<p>All linked workflows are visible.</p>'}`; document.querySelectorAll('[data-add-workflow]').forEach((button) => button.addEventListener('click', () => { shownWorkflows.add(button.dataset.addWorkflow); renderGraph(); showAnchorDetails(anchorId); updateMoreButton(); })); }

  function visibleRelations(id) { return [...cy.$id(id).connectedEdges()].map((edge) => `${edge.data('kind')}: ${edge.data('label') || 'relation'}`).join('; ') || 'none'; }
  function showHover(element, event) { const item = element.data(); if (element.isEdge()) { hover.innerHTML = `<h3>${esc(item.label || item.kind)}</h3><p><strong>Relation layer:</strong> ${esc(item.kind)}</p><p><code>${esc(item.source)}</code> -> <code>${esc(item.target)}</code></p>`; } else if (item.kind === 'anchor') { const anchor = data.anchorById[item.id], workflows = [...new Set((data.anchor_index[item.id] || []).map((id) => data.nodeById[id]?.workflow_id).filter(Boolean))]; hover.innerHTML = `<h3>${esc(anchor.label)}</h3><p><span class="decode-status ${esc(anchor.state)}">${esc(anchor.state)}</span></p><p><code>${esc(anchor.id)}</code></p><p>${workflows.length} linked workflows. Double-click to add the next complete workflow.</p>`; } else { const node = data.nodeById[item.id]; hover.innerHTML = `<h3>${esc(node.label)}</h3><p><span class="decode-status ${esc(node.mapping_state)}">${esc(node.mapping_state)}</span> ${esc(node.visual_category || 'other')}</p><p><strong>GraphML ID:</strong> <code>${esc(node.source_id)}</code><br><strong>Workflow:</strong> ${esc(data.workflowById[node.workflow_id].title)}<br><strong>Native category:</strong> ${esc(node.native_category || 'not supplied')}</p><p><strong>Visible relations:</strong> ${esc(visibleRelations(node.id))}</p>`; } hover.classList.remove('is-hidden'); moveHover(event); }
  function moveHover(event) { if (!event || hover.classList.contains('is-hidden')) return; hover.style.left = `${Math.min((event.clientX || 0) + 14, window.innerWidth - hover.offsetWidth - 10)}px`; hover.style.top = `${Math.min((event.clientY || 0) + 14, window.innerHeight - hover.offsetHeight - 10)}px`; }
  function hideHover() { hover.classList.add('is-hidden'); }
})();
"""


def _decode_workflows_js() -> str:
    """Interactive DECODE explorer with a semantic overview and source-fidelity view."""
    return r"""
(() => {
  const root = document.getElementById('decode-root');
  if (!root || !window.cytoscape) return;
  const $ = (selector) => document.querySelector(selector);
  const esc = (value) => String(value || '').replace(/[&<>'"]/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const lower = (value) => String(value || '').toLowerCase();
  const graph = $('#decode-graph'), details = $('#decode-details'), hover = $('#decode-hovercard'), emptyState = $('#decode-empty-state'), controls = $('#decode-controls'), legend = $('#decode-legend'), resultList = $('#decode-workflow-list');
  const sourceToggle = $('#decode-show-source'), anchorToggle = $('#decode-show-anchors'), semanticToggle = $('#decode-show-semantic'), dependencyToggle = $('#decode-show-dependencies'), semanticFilter = $('#decode-semantic-filter'), more = $('#decode-more');
  let catalogue = [], catalogueById = {}, currentMatches = [], data, graphDataPromise, cy, selectedWorkflow, selectedAnchor, shownWorkflows = new Set(), viewMode = 'source';

  fetch(root.dataset.decodeCatalogue).then((response) => { if (!response.ok) throw new Error(`Catalogue request failed (${response.status})`); return response.json(); }).then((loaded) => { catalogue = Array.isArray(loaded) ? loaded : (loaded.workflows || []); initializeCatalogue(); }).catch((error) => { $('#decode-catalogue-status').textContent = 'Workflow catalogue unavailable.'; details.innerHTML = `<h2>Workflow catalogue unavailable</h2><p>${esc(error.message)}</p>`; setEmptyState('Workflow catalogue unavailable', 'Please reload the page or try again later.', false); });

  function index(items) { return Object.fromEntries((items || []).map((item) => [item.id, item])); }
  function initializeCatalogue() {
    catalogueById = index(catalogue);
    const family = $('#decode-family');
    [...new Set(catalogue.map((workflow) => workflow.method_family))].sort().forEach((name) => family.insertAdjacentHTML('beforeend', `<option value="${esc(name)}">${esc(name.replaceAll('_', ' '))}</option>`));
    $('#decode-search').addEventListener('input', renderCatalogue); family.addEventListener('change', renderCatalogue);
    $('#decode-search').addEventListener('keydown', (event) => { if (event.key === 'Enter' && currentMatches.length) { event.preventDefault(); selectWorkflow(currentMatches[0].id); } });
    [sourceToggle, anchorToggle, semanticToggle, dependencyToggle, semanticFilter].forEach((input) => input.addEventListener('change', () => { if (data && selectedWorkflow) renderGraph(); }));
    document.querySelectorAll('input[name="decode-view"]').forEach((input) => input.addEventListener('change', () => { viewMode = input.value; syncViewControls(); if (data && selectedWorkflow) { renderGraph(); showWorkflowDetails(data.workflowById[selectedWorkflow]); } }));
    $('#decode-reset').addEventListener('click', () => { if (selectedWorkflow) selectWorkflow(selectedWorkflow); });
    more.addEventListener('click', () => addNextConnectedWorkflow(selectedAnchor));
    document.addEventListener('click', (event) => { if (!event.target.closest('.decode-search-panel')) resultList.hidden = true; });
    syncViewControls(); renderCatalogue();
  }
  function hydrateGraphData(loaded) {
    data = loaded;
    data.nodeById = index(data.nodes); data.projectionNodeById = index(data.projection_nodes || []); data.anchorById = index(data.anchors); data.workflowById = index(data.workflows); data.edgeRegistryBySource = Object.fromEntries((data.edge_registry || []).map((row) => [row.source_dependency_id, row]));
    data.semantic_overview ||= { nodes: [], source_edges: [], semantic_edges: [] };
    data.workflow_dependencies ||= []; data.workflowDependencyById = index(data.workflow_dependencies);
    data.overviewNodeById = index(data.semantic_overview.nodes);
    data.nodesByWorkflow = {}; data.nodes.forEach((node) => (data.nodesByWorkflow[node.workflow_id] ||= []).push(node.id));
    data.expert_profile_overlays ||= [];
    data.profileOverlayByWorkflow = Object.fromEntries(data.expert_profile_overlays.map((overlay) => [overlay.workflow_id, overlay]));
    data.profileNodeById = Object.fromEntries(data.expert_profile_overlays.flatMap((overlay) => overlay.nodes || []).map((node) => [node.id, node]));
    return data;
  }
  function loadGraphData() {
    if (data) return Promise.resolve(data);
    if (graphDataPromise) return graphDataPromise;
    setEmptyState('Loading selected workflow', 'Preparing the federated source and semantic graph. This happens only once per page visit.', true);
    graphDataPromise = fetch(root.dataset.decodeData).then((response) => { if (!response.ok) throw new Error(`Graph request failed (${response.status})`); return response.json(); }).then(hydrateGraphData).catch((error) => { graphDataPromise = null; throw error; });
    return graphDataPromise;
  }
  function setEmptyState(title, message, loading) {
    emptyState.hidden = false; emptyState.classList.toggle('is-loading', Boolean(loading));
    emptyState.innerHTML = `<strong>${esc(title)}</strong><span>${esc(message)}</span>`;
    graph.hidden = true; controls.hidden = true; legend.hidden = true;
  }

  function syncViewControls() {
    document.querySelectorAll('input[name="decode-view"]').forEach((input) => { input.checked = input.value === viewMode; });
    $('#decode-anchor-control').hidden = viewMode !== 'source';
    $('#decode-source-label').textContent = viewMode === 'semantic' ? 'Aggregated source dependencies' : 'Source dependencies';
    updateLegend();
  }
  function updateLegend() {
    const legend = $('#decode-legend');
    if (viewMode === 'source') {
      legend.innerHTML = '<strong>Semantic role (node fill):</strong> <span class="legend-matter">matter</span><span class="legend-manufacturing">manufacturing</span><span class="legend-process">process</span><span class="legend-measurement">measurement</span><span class="legend-instrument">instrument</span><span class="legend-parameter">parameter</span><span class="legend-data">data</span><span class="legend-property">property</span><span class="legend-metadata">metadata</span><span class="legend-mixed">mixed / missing role</span><br><strong>Mapping status (border):</strong> <span class="legend-approved">H2KG</span><span class="legend-reviewed">reviewed DECODE</span><span class="legend-unresolved">unresolved</span><br><span class="legend-source">solid arrow</span> preserved source dependency <span class="legend-anchor">dashed link</span> occurrence-to-anchor mapping <span class="legend-semantic">teal arrow</span> H2KG semantic projection <span class="legend-dependency">purple arrow</span> reviewed method dependency';
      return;
    }
    legend.innerHTML = '<strong>Semantic role:</strong> <span class="legend-matter">matter</span><span class="legend-manufacturing">manufacturing</span><span class="legend-process">process</span><span class="legend-measurement">measurement</span><span class="legend-instrument">instrument</span><span class="legend-parameter">parameter</span><span class="legend-data">data</span><span class="legend-property">property</span><span class="legend-metadata">metadata</span><span class="legend-mixed">mixed / missing role</span><br><strong>Mapping status:</strong> <span class="legend-approved">H2KG</span><span class="legend-reviewed">reviewed DECODE</span><span class="legend-unresolved">unresolved</span><br><span class="legend-source">solid arrow</span> provenance-preserving aggregate <span class="legend-semantic">teal arrow</span> H2KG semantic projection <span class="legend-dependency">purple arrow</span> reviewed method dependency';
  }
  function renderCatalogue() {
    const needle = lower($('#decode-search').value), family = $('#decode-family').value;
    if (!needle && !family) { currentMatches = []; resultList.innerHTML = ''; resultList.hidden = true; $('#decode-catalogue-status').textContent = selectedWorkflow ? `Selected: ${catalogueById[selectedWorkflow]?.title || selectedWorkflow}` : 'Search for a workflow or select a method family to begin.'; return; }
    currentMatches = catalogue.filter((workflow) => (!needle || [workflow.title, workflow.source_filename, workflow.method_family, workflow.mapping_status, workflow.iri, workflow.external_method_id, ...(workflow.alternate_titles || []), ...(workflow.search_terms || []), ...(workflow.partner_organization || [])].join(' ').toLowerCase().includes(needle)) && (!family || workflow.method_family === family));
    const visibleMatches = currentMatches.slice(0, 24);
    $('#decode-catalogue-status').textContent = currentMatches.length ? `${currentMatches.length} matching workflow${currentMatches.length === 1 ? '' : 's'}${currentMatches.length > visibleMatches.length ? '; showing the first 24' : ''}. Select one to open its graph.` : 'No matching workflows. Try a broader term or another method family.';
    resultList.innerHTML = visibleMatches.map((workflow) => `<button class="decode-workflow-card ${workflow.id === selectedWorkflow ? 'active' : ''}" data-workflow="${esc(workflow.id)}"><strong>${esc(workflow.title)}</strong><small>${esc(sourceLabel(workflow))} | ${esc(workflow.method_family.replaceAll('_',' '))}</small><small>${workflow.source_node_count} nodes, ${workflow.source_edge_count} edges | ${workflow.mapped_anchor_count} reviewed mappings</small></button>`).join('');
    resultList.hidden = !visibleMatches.length;
    document.querySelectorAll('[data-workflow]').forEach((button) => button.addEventListener('click', () => selectWorkflow(button.dataset.workflow)));
  }
  async function selectWorkflow(workflowId) {
    const summary = catalogueById[workflowId]; if (!summary) return;
    selectedWorkflow = workflowId; selectedAnchor = null; shownWorkflows = new Set([workflowId]); more.hidden = true; resultList.hidden = true;
    $('#decode-catalogue-status').textContent = `Loading ${summary.title} ...`;
    details.innerHTML = `<h2>${esc(summary.title)}</h2><p>Loading the preserved source workflow and reviewed semantic projections.</p>`;
    try {
      await loadGraphData();
      if (!data.workflowById[workflowId]) throw new Error('The selected workflow is not present in the federated graph.');
      emptyState.hidden = true; emptyState.classList.remove('is-loading'); graph.hidden = false; controls.hidden = false; legend.hidden = false;
      $('#decode-catalogue-status').textContent = `Selected: ${summary.title}`;
      renderGraph(); showWorkflowDetails(data.workflowById[workflowId]);
    } catch (error) {
      setEmptyState('Workflow data unavailable', error.message, false);
      details.innerHTML = `<h2>Workflow data unavailable</h2><p>${esc(error.message)}</p>`;
    }
  }
  function visibleNodeIds() { return new Set([...shownWorkflows].flatMap((workflowId) => data.nodesByWorkflow[workflowId] || [])); }
  function overviewId(occurrenceId) { const node = data.nodeById[occurrenceId]; return node?.anchor_id || `unresolved::${occurrenceId}`; }
  function visibleAnchorIds(nodes) { return new Set([...nodes].map((id) => data.nodeById[id]?.anchor_id).filter(Boolean)); }
  function semanticRoleKey(node) {
    if (node.role_conflict) return 'mixed';
    return ({ Matter:'matter', Manufacturing:'manufacturing', Process:'process', Measurement:'measurement', Instrument:'instrument', SoftwareArtifact:'instrument', Parameter:'parameter', Data:'data', DataPoint:'data', Property:'property', Characteristic:'property', Metadata:'metadata' })[node.semantic_role] || 'unknown';
  }
  function semanticRoleText(node) {
    return node.role_conflict ? `Mixed role: ${(node.semantic_roles || []).join(', ') || 'unresolved'}` : (node.semantic_role || 'Missing role');
  }
  function mappingLabel(state) { return ({ approved_h2kg:'H2KG', reviewed_decode:'reviewed DECODE', unresolved:'Unresolved' })[state] || state || 'Unresolved'; }
  function sourceLabel(workflow) { if (workflow.is_derived) return 'Derived schema'; if (workflow.source_kind === 'source_manual_json') return 'Manual JSON source'; return 'GraphML source'; }
  function projectionVisible(edge) { return semanticFilter.value === 'all' || edge.projection_outcome === semanticFilter.value; }
  function addProfileElements(output) {
    if (!semanticToggle.checked) return;
    const overlays = [...shownWorkflows].map((workflowId) => data.profileOverlayByWorkflow[workflowId]).filter(Boolean);
    const nodeIds = new Set(output.filter((item) => item.group === 'nodes').map((item) => item.data.id));
    overlays.forEach((overlay) => {
      (overlay.nodes || []).forEach((node) => {
        if (nodeIds.has(node.id)) return;
        nodeIds.add(node.id);
        output.push({ group:'nodes', data:{ id:node.id, label:node.label, kind:'profile-anchor', state:'approved_h2kg', role:semanticRoleKey(node), profileId:overlay.profile_id } });
      });
      (overlay.edges || []).forEach((edge) => {
        if (nodeIds.has(edge.source) && nodeIds.has(edge.target)) output.push({ group:'edges', data:{ id:edge.id, source:edge.source, target:edge.target, kind:'profile', label:edge.label, profileId:overlay.profile_id } });
      });
    });
  }

  function sourceElements() {
    const nodes = visibleNodeIds(), anchors = visibleAnchorIds(nodes), output = [];
    [...nodes].forEach((id) => { const node = data.nodeById[id]; output.push({ group:'nodes', data:{ id, label:node.label, kind:'occurrence', state:node.mapping_state, visual:node.visual_category || 'other', role:semanticRoleKey(node), workflow:node.workflow_id } }); });
    const semantic = semanticToggle.checked ? data.semantic_edges.filter((edge) => shownWorkflows.has(edge.workflow_id) && projectionVisible(edge)) : [];
    const semanticAnchorIds = new Set(semantic.flatMap((edge) => [edge.source, edge.target]).filter((id) => data.anchorById[id]));
    const proxyIds = new Set(semantic.flatMap((edge) => [edge.source, edge.target]).filter((id) => data.projectionNodeById[id]));
    [...proxyIds].forEach((id) => { const node = data.projectionNodeById[id]; output.push({ group:'nodes', data:{ id, label:node.label, kind:node.kind || 'value_proxy', state:'derived', role:semanticRoleKey(node), workflow:node.workflow_id } }); });
    const anchorNodeIds = new Set([...anchors, ...semanticAnchorIds]);
    if (anchorToggle.checked || semanticAnchorIds.size) {
      [...anchorNodeIds].forEach((id) => { const anchor = data.anchorById[id]; if (anchor) output.push({ group:'nodes', data:{ id, label:anchor.label, kind:'source-anchor', state:anchor.state, role:semanticRoleKey(anchor), anchorId:id } }); });
      if (anchorToggle.checked) data.anchor_edges.filter((edge) => nodes.has(edge.source) && anchorNodeIds.has(edge.target)).forEach((edge) => output.push({ group:'edges', data:{ id:edge.id, source:edge.source, target:edge.target, kind:'anchor', label:'maps to' } }));
    }
    if (sourceToggle.checked) data.source_edges.filter((edge) => nodes.has(edge.source) && nodes.has(edge.target)).forEach((edge) => output.push({ group:'edges', data:{ id:edge.id, source:edge.source, target:edge.target, kind:'source', label:'', sourceDependencyId:edge.id, sourceEdgeIds:[edge.id] } }));
    const visible = new Set(output.filter((item) => item.group === 'nodes').map((item) => item.data.id));
    semantic.filter((edge) => visible.has(edge.source) && visible.has(edge.target)).forEach((edge) => output.push({ group:'edges', data:{ id:edge.id, source:edge.source, target:edge.target, kind:'semantic', label:edge.label, sourceDependencyId:edge.source_dependency_id, sourceEdgeIds:[edge.source_dependency_id], projectionOutcome:edge.projection_outcome, projectionPattern:edge.projection_pattern } }));
    if (dependencyToggle.checked) data.workflow_dependencies.filter((edge) => edge.publication_status !== 'audit_only' && nodes.has(edge.source) && nodes.has(edge.target)).forEach((edge) => output.push({ group:'edges', data:{ id:`dependency::${edge.id}`, source:edge.source, target:edge.target, kind:'dependency', label:'workflow handoff', dependencyId:edge.id, dependencyStatus:edge.publication_status } }));
    addProfileElements(output);
    return output;
  }
  function semanticElements() {
    const visible = visibleNodeIds(), semanticIds = new Set([...visible].map(overviewId)), output = [];
    [...semanticIds].forEach((id) => { const node = data.overviewNodeById[id]; if (node) output.push({ group:'nodes', data:{ id, label:node.label, kind:node.kind, state:node.state, role:semanticRoleKey(node), occurrenceCount:node.occurrence_count, anchorId:data.anchorById[id] ? id : '' } }); });
    if (sourceToggle.checked) data.semantic_overview.source_edges.forEach((edge) => {
      const pairs = (edge.occurrence_pairs || []).filter((pair) => visible.has(pair.source_occurrence_id) && visible.has(pair.target_occurrence_id));
      if (pairs.length && semanticIds.has(edge.source) && semanticIds.has(edge.target)) output.push({ group:'edges', data:{ id:edge.id, source:edge.source, target:edge.target, kind:'source', label:'', sourceEdgeIds:pairs.map((pair) => pair.source_dependency_id), occurrenceCount:pairs.length } });
    });
    if (semanticToggle.checked) data.semantic_overview.semantic_edges.filter(projectionVisible).forEach((edge) => {
      const visibleCount = (edge.workflow_ids || []).filter((workflowId) => shownWorkflows.has(workflowId)).length;
      if (visibleCount && semanticIds.has(edge.source) && semanticIds.has(edge.target)) output.push({ group:'edges', data:{ id:edge.id, source:edge.source, target:edge.target, kind:'semantic', label:edge.label, sourceEdgeIds:edge.source_dependency_ids, occurrenceCount:visibleCount } });
    });
    if (dependencyToggle.checked) data.workflow_dependencies.filter((edge) => edge.publication_status !== 'audit_only' && visible.has(edge.source) && visible.has(edge.target)).forEach((edge) => {
      const source = overviewId(edge.source), target = overviewId(edge.target);
      if (semanticIds.has(source) && semanticIds.has(target)) output.push({ group:'edges', data:{ id:`semantic-dependency::${edge.id}`, source, target, kind:'dependency', label:'workflow handoff', dependencyId:edge.id, dependencyStatus:edge.publication_status } });
    });
    addProfileElements(output);
    return output;
  }
  function elements() { return viewMode === 'semantic' ? semanticElements() : sourceElements(); }

  function renderGraph() {
    if (cy) cy.destroy();
    cy = cytoscape({ container:graph, elements:elements(), style:[
      { selector:'node', style:{ 'label':'data(label)', 'font-size':10, 'text-wrap':'wrap', 'text-max-width':118, 'color':'#183139', 'text-valign':'center', 'text-halign':'center', 'border-width':2, 'background-color':'#a9bcc0', 'border-color':'#50676d', 'width':60, 'height':60 } },
      { selector:'node[kind = "occurrence"][role = "matter"]', style:{ 'background-color':'#0f6d7a', 'color':'#fff' } },
      { selector:'node[kind = "occurrence"][role = "manufacturing"]', style:{ 'background-color':'#b45309', 'color':'#fff' } },
      { selector:'node[kind = "occurrence"][role = "process"]', style:{ 'background-color':'#d49118', 'color':'#183139' } },
      { selector:'node[kind = "occurrence"][role = "measurement"]', style:{ 'background-color':'#376caa', 'color':'#fff' } },
      { selector:'node[kind = "occurrence"][role = "instrument"]', style:{ 'background-color':'#5d6b76', 'color':'#fff' } },
      { selector:'node[kind = "occurrence"][role = "parameter"]', style:{ 'background-color':'#5d66a6', 'color':'#fff' } },
      { selector:'node[kind = "occurrence"][role = "data"]', style:{ 'background-color':'#64b4d5', 'color':'#183139' } },
      { selector:'node[kind = "occurrence"][role = "property"]', style:{ 'background-color':'#9d5549', 'color':'#fff' } },
      { selector:'node[kind = "occurrence"][role = "metadata"]', style:{ 'background-color':'#98a3aa', 'color':'#183139' } },
      { selector:'node[kind = "occurrence"][role = "mixed"], node[kind = "occurrence"][role = "unknown"]', style:{ 'background-color':'#adb8bd', 'color':'#183139' } },
      { selector:'node[kind = "value-proxy"]', style:{ 'shape':'diamond', 'background-color':'#64b4d5', 'border-color':'#087f71', 'border-width':3, 'color':'#183139', 'width':52, 'height':52, 'font-size':9 } },
      { selector:'node[kind = "value_proxy"]', style:{ 'shape':'diamond', 'background-color':'#64b4d5', 'border-color':'#087f71', 'border-width':3, 'color':'#183139', 'width':52, 'height':52, 'font-size':9 } },
      { selector:'node[kind = "parameter_record_proxy"]', style:{ 'shape':'round-diamond', 'background-color':'#5d66a6', 'border-color':'#343a73', 'border-width':3, 'color':'#fff', 'width':58, 'height':58, 'font-size':9 } },
      { selector:'node[kind = "profile-anchor"]', style:{ 'shape':'round-rectangle', 'width':124, 'height':50, 'font-weight':700, 'border-color':'#006f73', 'border-width':4 } },
      { selector:'node[kind = "profile-anchor"][role = "process"]', style:{ 'background-color':'#d49118', 'color':'#183139' } },
      { selector:'node[kind = "profile-anchor"][role = "parameter"]', style:{ 'background-color':'#5d66a6', 'color':'#fff' } },
      { selector:'node[kind = "profile-anchor"][role = "data"]', style:{ 'background-color':'#64b4d5', 'color':'#183139' } },
      { selector:'node[kind = "profile-anchor"][role = "property"]', style:{ 'background-color':'#9d5549', 'color':'#fff' } },
      { selector:'node[kind = "source-anchor"], node[kind = "semantic-anchor"]', style:{ 'shape':'round-rectangle', 'width':124, 'height':50, 'font-weight':700 } },
      { selector:'node[kind = "source-anchor"][state = "approved_h2kg"]', style:{ 'background-color':'#0d7f83', 'border-color':'#07575a', 'color':'#fff' } },
      { selector:'node[kind = "source-anchor"][state = "reviewed_decode"]', style:{ 'background-color':'#bd8529', 'border-color':'#855c12', 'color':'#fff' } },
      { selector:'node[kind = "occurrence"][state = "approved_h2kg"]', style:{ 'border-color':'#006f73', 'border-width':4 } },
      { selector:'node[kind = "occurrence"][state = "reviewed_decode"]', style:{ 'border-color':'#9a650b', 'border-width':4 } },
      { selector:'node[kind = "occurrence"][state = "unresolved"]', style:{ 'border-color':'#a63030', 'border-style':'dashed', 'border-width':3 } },
      { selector:'node[kind = "semantic-anchor"][role = "matter"]', style:{ 'background-color':'#0f6d7a', 'color':'#fff' } },
      { selector:'node[kind = "semantic-anchor"][role = "manufacturing"]', style:{ 'background-color':'#b45309', 'color':'#fff' } },
      { selector:'node[kind = "semantic-anchor"][role = "process"]', style:{ 'background-color':'#d49118', 'color':'#183139' } },
      { selector:'node[kind = "semantic-anchor"][role = "measurement"]', style:{ 'background-color':'#376caa', 'color':'#fff' } },
      { selector:'node[kind = "semantic-anchor"][role = "instrument"]', style:{ 'background-color':'#5d6b76', 'color':'#fff' } },
      { selector:'node[kind = "semantic-anchor"][role = "parameter"]', style:{ 'background-color':'#5d66a6', 'color':'#fff' } },
      { selector:'node[kind = "semantic-anchor"][role = "data"]', style:{ 'background-color':'#64b4d5', 'color':'#183139' } },
      { selector:'node[kind = "semantic-anchor"][role = "property"]', style:{ 'background-color':'#9d5549', 'color':'#fff' } },
      { selector:'node[kind = "semantic-anchor"][role = "metadata"]', style:{ 'background-color':'#98a3aa', 'color':'#183139' } },
      { selector:'node[kind = "semantic-anchor"][role = "mixed"], node[kind = "semantic-anchor"][role = "unknown"], node[kind = "semantic-unresolved"]', style:{ 'background-color':'#adb8bd', 'color':'#183139' } },
      { selector:'node[kind = "semantic-anchor"][state = "approved_h2kg"]', style:{ 'border-color':'#006f73', 'border-width':4 } },
      { selector:'node[kind = "semantic-anchor"][state = "reviewed_decode"]', style:{ 'border-color':'#9a650b', 'border-width':4 } },
      { selector:'node[kind = "semantic-anchor"][role = "mixed"], node[kind = "semantic-anchor"][state = "unresolved"], node[kind = "semantic-unresolved"]', style:{ 'border-color':'#a63030', 'border-style':'dashed', 'border-width':3 } },
      { selector:'node.hovered, node.focused', style:{ 'border-color':'#f59e0b', 'border-width':5, 'z-index':999 } },
      { selector:'edge[kind = "source"]', style:{ 'width':1.25, 'opacity':.45, 'line-color':'#596c72', 'target-arrow-color':'#596c72', 'target-arrow-shape':'triangle', 'curve-style':'bezier' } },
      { selector:'edge[kind = "anchor"]', style:{ 'width':1.5, 'line-style':'dashed', 'line-color':'#bd8529', 'curve-style':'bezier' } },
      { selector:'edge[kind = "semantic"]', style:{ 'width':2.5, 'line-color':'#087f71', 'target-arrow-color':'#087f71', 'target-arrow-shape':'triangle', 'label':'data(label)', 'font-size':9, 'text-background-color':'#fff', 'text-background-opacity':.9, 'text-background-padding':2 } }
      ,{ selector:'edge[kind = "profile"]', style:{ 'width':2.8, 'line-color':'#b45309', 'target-arrow-color':'#b45309', 'target-arrow-shape':'triangle', 'label':'data(label)', 'font-size':9, 'text-background-color':'#fff7ed', 'text-background-opacity':.95, 'text-background-padding':2 } }
    ], layout:{ name:'cose', animate:false, padding:34, idealEdgeLength:105, nodeRepulsion:520000 } });
    cy.on('dbltap', 'node', (event) => { const item = event.target.data(); if (item.kind === 'profile-anchor') return showProfileNodeDetails(item.id); const anchorId = item.anchorId || (item.kind === 'source-anchor' ? item.id : data.nodeById[item.id]?.anchor_id); if (anchorId) expandAnchor(anchorId); else if (item.kind === 'semantic-unresolved') showSemanticNodeDetails(item.id); else if (data.projectionNodeById[item.id]) showProjectionNodeDetails(item.id); else showOccurrenceDetails(item.id); });
    cy.on('tap', 'node', (event) => { const item = event.target.data(); if (item.kind === 'profile-anchor') showProfileNodeDetails(item.id); else if (item.kind === 'semantic-anchor' || item.kind === 'semantic-unresolved') showSemanticNodeDetails(item.id); else if (item.kind === 'source-anchor') showAnchorDetails(item.id); else if (data.projectionNodeById[item.id]) showProjectionNodeDetails(item.id); else showOccurrenceDetails(item.id); });
    cy.on('tap', 'edge', (event) => showEdgeDetails(event.target.data()));
    cy.on('mouseover', 'node, edge', (event) => { event.target.addClass('hovered'); showHover(event.target, event.originalEvent); });
    cy.on('mousemove', 'node, edge', (event) => moveHover(event.originalEvent));
    cy.on('mouseout', 'node, edge', (event) => { event.target.removeClass('hovered'); hideHover(); });
  }

  function rankedConnectedWorkflows(anchorId) {
    const visibleAnchors = visibleAnchorIds(visibleNodeIds());
    const candidates = new Set((data.anchor_index[anchorId] || []).map((id) => data.nodeById[id]?.workflow_id).filter((id) => id && !shownWorkflows.has(id)));
    return [...candidates].sort((left, right) => { const leftAnchors = new Set((data.nodesByWorkflow[left] || []).map((id) => data.nodeById[id]?.anchor_id).filter(Boolean)); const rightAnchors = new Set((data.nodesByWorkflow[right] || []).map((id) => data.nodeById[id]?.anchor_id).filter(Boolean)); const leftScore = [...leftAnchors].filter((id) => visibleAnchors.has(id)).length, rightScore = [...rightAnchors].filter((id) => visibleAnchors.has(id)).length; return rightScore - leftScore || data.workflowById[left].title.localeCompare(data.workflowById[right].title); });
  }
  function expandAnchor(anchorId) { selectedAnchor = anchorId; const next = rankedConnectedWorkflows(anchorId)[0]; if (next) shownWorkflows.add(next); renderGraph(); showAnchorDetails(anchorId); updateMoreButton(); }
  function addNextConnectedWorkflow(anchorId) { if (anchorId) expandAnchor(anchorId); }
  function updateMoreButton() { const remaining = selectedAnchor ? rankedConnectedWorkflows(selectedAnchor).length : 0; more.hidden = !remaining; more.textContent = `Add next connected workflow (${remaining} remaining)`; }

  function downloads(workflow) { const standard = `<a href="../decode/workflows/${encodeURIComponent(workflow.id)}.json" download>Download normalized workflow JSON</a><a href="../decode/workflows/${encodeURIComponent(workflow.id)}.jsonld" download>Download JSON-LD projection</a><a href="../decode/workflows/${encodeURIComponent(workflow.id)}.ttl" download>Download Turtle projection</a><a href="../decode/workflows/${encodeURIComponent(workflow.id)}.validation.json" download>Download workflow validation</a><a href="../decode/decode_mapping_matrix.csv" download>Download mapping matrix</a><a href="../decode/decode_edge_registry.csv" download>Download edge-alignment registry</a><a href="../decode/decode_workflow_dependencies.csv" download>Download workflow dependencies</a><a href="../decode/decode_duplicate_occurrence_audit.csv" download>Download duplicate-occurrence audit</a><a href="../decode/decode_validation_report.json" download>Download release validation</a>`; const extras = (workflow.downloads || []).map((item) => `<a href="${esc(item.href)}" download>${esc(item.label)}</a>`).join(''); return `<div class="decode-downloads">${standard}${extras}</div>`; }
  function showWorkflowDetails(workflow) { const semanticCount = new Set((data.nodesByWorkflow[workflow.id] || []).map(overviewId)).size; const sourceStatus = workflow.is_derived ? 'PDF-derived interface schema; the source workflows are unchanged.' : (viewMode === 'semantic' ? 'Select a canonical node to inspect its source occurrences and branch contexts.' : 'The complete source workflow is visible. Double-click an occurrence or anchor to traverse reviewed cross-workflow connections.'); const profileBadge = workflow.expert_profile ? `<span class="decode-status approved_h2kg">${esc(workflow.expert_profile.badge)}</span>` : ''; details.innerHTML = `<h2>${esc(workflow.title)}</h2><p><span class="decode-status ${esc(workflow.mapping_status)}">${esc(workflow.mapping_status)}</span> <span class="decode-status">${esc(sourceLabel(workflow))}</span> ${profileBadge}</p><p><strong>Source:</strong> ${esc(workflow.source_filename)}<br><strong>Method ID:</strong> ${esc(workflow.external_method_id || 'not supplied')}<br><strong>Partner:</strong> ${esc((workflow.partner_organization || []).join('; ') || 'not supplied')}<br><strong>Method family:</strong> ${esc(workflow.method_family)}<br><strong>Topology:</strong> ${workflow.source_node_count} occurrences and ${workflow.source_edge_count} directed dependencies.<br><strong>Semantic overview:</strong> ${semanticCount} canonical nodes.</p><p>${sourceStatus}</p>${workflow.expert_profile ? `<p>The expert profile is a derived semantic overlay and does not add source nodes or edges.</p>` : ''}${downloads(workflow)}`; }
  function showOccurrenceDetails(id) { const node = data.nodeById[id]; if (!node) return; const workflow = data.workflowById[node.workflow_id], anchor = data.anchorById[node.anchor_id]; const anchorText = anchor ? `<p><strong>Shared anchor:</strong> ${anchor.state === 'approved_h2kg' ? `<a href="${root.dataset.h2kgExplore}?iri=${encodeURIComponent(anchor.id)}">${esc(anchor.label)}</a>` : esc(anchor.label)}</p>` : '<p><strong>Shared anchor:</strong> unresolved; no cross-workflow join is available.</p>'; const role = node.canonical_role_iri ? `<p><strong>Intrinsic H2KG role:</strong> <a href="${root.dataset.h2kgExplore}?iri=${encodeURIComponent(node.canonical_role_iri)}">${esc(node.semantic_role || node.canonical_role_iri)}</a>${node.workflow_role && node.workflow_role !== node.semantic_role ? `<br><strong>Source workflow role:</strong> ${esc(node.workflow_role)}` : ''}</p>` : ''; details.innerHTML = `<h2>${esc(node.label)}</h2><p><span class="decode-status ${esc(node.mapping_state)}">${esc(node.mapping_state)}</span></p><p><strong>Decision:</strong> ${esc(node.decision || 'unresolved')}<br><strong>Source node ID:</strong> <code>${esc(node.source_id)}</code><br><strong>Source kind:</strong> ${esc(node.source_kind || workflow.source_kind || 'source_graphml')}<br><strong>Workflow:</strong> ${esc(workflow.title)}<br><strong>Native category:</strong> ${esc(node.native_category || 'not supplied')}</p><p><strong>Source metadata:</strong> ${esc(node.description || 'not supplied')}</p>${anchorText}${role}<p><strong>Mapping evidence:</strong> ${esc(node.mapping_evidence || 'not supplied')}</p>${downloads(workflow)}`; if (cy) { const selected = cy.$id(id); selected.addClass('focused'); cy.center(selected); } }
  function showProjectionNodeDetails(id) { const node = data.projectionNodeById[id]; if (!node) return; const workflow = data.workflowById[node.workflow_id], source = data.nodeById[node.source_occurrence_id], typeLabel = node.semantic_role || (node.kind === 'parameter_record_proxy' ? 'Parameter' : 'DataPoint'); details.innerHTML = `<h2>${esc(node.label)}</h2><p><span class="decode-status">derived semantic projection</span></p><p><strong>H2KG type:</strong> <a href="${root.dataset.h2kgExplore}?iri=${encodeURIComponent(node.canonical_role_iri)}">${esc(typeLabel)}</a><br><strong>Source occurrence:</strong> <code>${esc(source.source_id)}</code> ${esc(source.label)}<br><strong>Workflow:</strong> ${esc(workflow.title)}</p><p>${esc(node.description)}</p>`; }
  function showProfileNodeDetails(id) { const node = data.profileNodeById[id]; if (!node) return; details.innerHTML = `<h2>${esc(node.label)}</h2><p><span class="decode-status approved_h2kg">Expert-reviewed ITC profile</span></p><p><strong>Semantic role:</strong> ${esc(node.semantic_role)}${node.io_id ? `<br><strong>Stable IO identifier:</strong> <code>${esc(node.io_id)}</code>` : ''}</p><p>${esc(node.description)}</p><p><a href="${root.dataset.h2kgExplore}?iri=${encodeURIComponent(node.id)}">Inspect this public term in H2KG Explore</a></p>`; }
  function showSemanticNodeDetails(id) { const node = data.overviewNodeById[id]; if (!node) return; const visible = visibleNodeIds(), occurrences = node.occurrence_ids.filter((occurrenceId) => visible.has(occurrenceId)); const anchor = data.anchorById[id]; const h2kg = anchor?.state === 'approved_h2kg' ? `<p><a href="${root.dataset.h2kgExplore}?iri=${encodeURIComponent(id)}">Inspect this stable H2KG term in H2KG Explore</a></p>` : ''; const role = node.canonical_role_iri && !node.role_conflict ? `<p><strong>Semantic role:</strong> <a href="${root.dataset.h2kgExplore}?iri=${encodeURIComponent(node.canonical_role_iri)}">${esc(semanticRoleText(node))}</a></p>` : `<p><strong>Semantic role:</strong> ${esc(semanticRoleText(node))}</p>`; const list = occurrences.map((occurrenceId) => { const occurrence = data.nodeById[occurrenceId], workflow = data.workflowById[occurrence.workflow_id]; return `<li><button class="decode-add-workflow" data-inspect-occurrence="${esc(occurrenceId)}"><code>${esc(occurrence.source_id)}</code> in ${esc(workflow.title)}</button></li>`; }).join(''); details.innerHTML = `<h2>${esc(node.label)}</h2><p><span class="decode-status ${esc(node.state)}">${esc(mappingLabel(node.state))}</span> ${esc(node.decision || '')}</p>${role}<p><strong>Semantic overview:</strong> ${occurrences.length} visible source occurrence${occurrences.length === 1 ? '' : 's'} represented by one canonical node.</p><p>${esc(node.evidence || '')}</p>${h2kg}<h3>Inspect preserved source occurrences</h3><ul>${list || '<li>No occurrence is visible.</li>'}</ul>${anchor ? `<p>Double-click this node to add one complete connected workflow through the shared anchor.</p>` : ''}`; document.querySelectorAll('[data-inspect-occurrence]').forEach((button) => button.addEventListener('click', () => { viewMode = 'source'; syncViewControls(); renderGraph(); showOccurrenceDetails(button.dataset.inspectOccurrence); })); }
  function showAnchorDetails(anchorId) { const anchor = data.anchorById[anchorId]; if (!anchor) return; const workflows = [...new Set((data.anchor_index[anchorId] || []).map((id) => data.nodeById[id]?.workflow_id).filter(Boolean))].map((id) => data.workflowById[id]); const candidates = rankedConnectedWorkflows(anchorId); const h2kg = anchor.state === 'approved_h2kg' ? `<p><a href="${root.dataset.h2kgExplore}?iri=${encodeURIComponent(anchor.id)}">Inspect this stable H2KG term in H2KG Explore</a></p>` : ''; const role = anchor.canonical_role_iri && anchor.state !== 'approved_h2kg' ? `<p><strong>H2KG role:</strong> <a href="${root.dataset.h2kgExplore}?iri=${encodeURIComponent(anchor.canonical_role_iri)}">${esc(anchor.semantic_role || anchor.canonical_role_iri)}</a></p>` : ''; const cards = candidates.slice(0,8).map((workflow) => `<button class="decode-add-workflow" data-add-workflow="${esc(workflow.id)}">Add full workflow: ${esc(workflow.title)}</button>`).join(''); details.innerHTML = `<h2>${esc(anchor.label)}</h2><p><span class="decode-status ${esc(anchor.state)}">${esc(mappingLabel(anchor.state))}</span> ${esc(anchor.decision || '')}</p><p><code>${esc(anchor.id)}</code></p><p>${esc(anchor.evidence)}</p>${h2kg}${role}<h3>Linked workflows (${workflows.length})</h3><ul>${workflows.map((workflow) => `<li>${esc(workflow.title)}</li>`).join('')}</ul>${cards ? `<h3>Expand a connected workflow</h3>${cards}` : '<p>All linked workflows are visible.</p>'}`; document.querySelectorAll('[data-add-workflow]').forEach((button) => button.addEventListener('click', () => { shownWorkflows.add(button.dataset.addWorkflow); renderGraph(); showAnchorDetails(anchorId); updateMoreButton(); })); }
  function visibleRelations(id) { return [...cy.$id(id).connectedEdges()].map((edge) => `${edge.data('kind')}: ${edge.data('label') || 'relation'}`).join('; ') || 'none'; }
  function edgeDecision(item) { return data.edgeRegistryBySource[item.sourceDependencyId || item.id]; }
  function edgeDecisionHtml(item) { if (item.kind === 'dependency') { const decision = data.workflowDependencyById[item.dependencyId]; if (!decision) return ''; return `<p><strong>Status:</strong> ${esc(decision.publication_status)}<br><strong>Declarations:</strong> ${esc((decision.declarations || []).join(', '))}<br><strong>Handoff concepts:</strong> ${esc((decision.handoff_labels || []).join('; ') || 'none identified')}<br><strong>Handoff anchors:</strong> ${esc((decision.handoff_anchor_iris || []).join('; ') || 'none')}<br><strong>Evidence:</strong> ${esc(decision.review_rationale)}</p>`; } const decision = edgeDecision(item); if (!decision) return ''; return `<p><strong>Classification:</strong> ${esc(decision.projection_outcome)}<br><strong>Pattern:</strong> ${esc(decision.projection_pattern)}<br><strong>Semantic direction:</strong> ${esc(decision.semantic_direction)}<br><strong>Predicate(s):</strong> ${esc(decision.semantic_predicates || 'none')}<br><strong>Confidence:</strong> ${esc(decision.confidence)}<br><strong>Rationale:</strong> ${esc(decision.rationale)}</p>`; }
  function showEdgeDetails(item) { const relationId = item.kind === 'dependency' ? item.dependencyId : (item.sourceDependencyId || item.id); details.innerHTML = `<h2>${esc(item.label || 'Source dependency')}</h2><p><strong>Relation layer:</strong> ${esc(item.kind)}<br><strong>Display direction:</strong> <code>${esc(item.source)}</code> -> <code>${esc(item.target)}</code><br><strong>Relation ID:</strong> <code>${esc(relationId)}</code></p>${edgeDecisionHtml(item)}`; }
  function showHover(element, event) { const item = element.data(); if (element.isEdge()) { const count = item.occurrenceCount ? `<p><strong>Preserved source dependencies:</strong> ${item.occurrenceCount}</p>` : ''; hover.innerHTML = `<h3>${esc(item.label || item.kind)}</h3><p><strong>Relation layer:</strong> ${esc(item.kind)}</p><p><code>${esc(item.source)}</code> -> <code>${esc(item.target)}</code></p>${edgeDecisionHtml(item)}${count}`; } else if (item.kind === 'profile-anchor') { const node = data.profileNodeById[item.id]; hover.innerHTML = `<h3>${esc(node.label)}</h3><p><span class="decode-status approved_h2kg">Expert-reviewed ITC profile</span></p><p><strong>Semantic role:</strong> ${esc(node.semantic_role)}</p><p>${esc(node.description)}</p>`; } else if (item.kind === 'semantic-anchor' || item.kind === 'semantic-unresolved') { const node = data.overviewNodeById[item.id]; hover.innerHTML = `<h3>${esc(node.label)}</h3><p><span class="decode-status ${esc(node.state)}">${esc(mappingLabel(node.state))}</span></p><p><strong>Semantic role:</strong> ${esc(semanticRoleText(node))}</p><p>${node.occurrence_count} preserved occurrence${node.occurrence_count === 1 ? '' : 's'} represented here. Double-click to expand connected workflows when an anchor is available.</p>`; } else if (item.kind === 'source-anchor') { const anchor = data.anchorById[item.id], workflows = [...new Set((data.anchor_index[item.id] || []).map((id) => data.nodeById[id]?.workflow_id).filter(Boolean))]; hover.innerHTML = `<h3>${esc(anchor.label)}</h3><p><span class="decode-status ${esc(anchor.state)}">${esc(mappingLabel(anchor.state))}</span></p><p><strong>Semantic role:</strong> ${esc(anchor.semantic_role || 'Missing role')}</p><p>${workflows.length} linked workflows. Double-click to add the next complete workflow.</p>`; } else if (data.projectionNodeById[item.id]) { const node = data.projectionNodeById[item.id]; hover.innerHTML = `<h3>${esc(node.label)}</h3><p><strong>Derived semantic node:</strong> H2KG ${esc(node.semantic_role || 'record')} proxy</p><p>${esc(node.description)}</p>`; } else { const node = data.nodeById[item.id], workflow = data.workflowById[node.workflow_id]; hover.innerHTML = `<h3>${esc(node.label)}</h3><p><span class="decode-status ${esc(node.mapping_state)}">${esc(mappingLabel(node.mapping_state))}</span> ${esc(node.visual_category || 'other')}</p><p><strong>Intrinsic semantic role:</strong> ${esc(node.semantic_role || 'Missing role')}${node.workflow_role && node.workflow_role !== node.semantic_role ? `<br><strong>Source workflow role:</strong> ${esc(node.workflow_role)}` : ''}</p><p><strong>Source node ID:</strong> <code>${esc(node.source_id)}</code><br><strong>Source kind:</strong> ${esc(node.source_kind || workflow.source_kind || 'source_graphml')}<br><strong>Workflow:</strong> ${esc(workflow.title)}<br><strong>Native category:</strong> ${esc(node.native_category || 'not supplied')}</p><p><strong>Visible relations:</strong> ${esc(visibleRelations(node.id))}</p>`; } hover.classList.remove('is-hidden'); moveHover(event); }
  function moveHover(event) { if (!event || hover.classList.contains('is-hidden')) return; hover.style.left = `${Math.min((event.clientX || 0) + 14, window.innerWidth - hover.offsetWidth - 10)}px`; hover.style.top = `${Math.min((event.clientY || 0) + 14, window.innerHeight - hover.offsetHeight - 10)}px`; }
  function hideHover() { hover.classList.add('is-hidden'); }
})();
"""


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
      <a href="{_relative_href(page_path, docs_root / 'pages' / 'decode-workflows.html')}">DECODE Workflows</a>
      <a href="{_relative_href(page_path, docs_root / 'hydrogen-ontology.html')}">Reference</a>
      <a href="{_relative_href(page_path, docs_root / 'pages' / 'architecture-workflow.html')}">Architecture</a>
      <a href="{_relative_href(page_path, docs_root / 'pages' / 'class-index.html')}">Classes</a>
      <a href="{_relative_href(page_path, docs_root / 'pages' / 'property-index.html')}">Properties</a>
      <a href="{_relative_href(page_path, docs_root / 'pages' / 'alignment.html')}">Alignments</a>
      <a href="{_relative_href(page_path, docs_root / 'pages' / 'examples.html')}">Examples</a>
      <a href="{_relative_href(page_path, docs_root / 'pages' / 'import-guide.html')}">Import</a>
      <a href="{_relative_href(page_path, docs_root / 'pages' / 'import-catalog.html')}">Import Catalog</a>
      <a href="{_relative_href(page_path, docs_root / 'pages' / 'quality-dashboard.html')}">Quality</a>
      <a href="{_relative_href(page_path, docs_root / 'pages' / 'tib-benchmark.html')}">TIB Benchmark</a>
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
        <div class="metric"><strong>Foundational reuse</strong><span>HDO, EMMO, QUDT, ChEBI, PROV-O, and DCTERMS support shared quantities, chemicals, provenance, and metadata.</span></div>
        <div class="metric"><strong>External alignment</strong><span>Exact, broader, and narrower SKOS mappings point to original ontology IRIs discovered across NFDI4Cat, NFDI4Energy, and NFDI4Ing in TIB.</span></div>
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
      <p>The H2KG domain ontology is published conservatively. The recommended maintenance workflow is inspect, split, review mappings, enrich metadata, validate, build docs, then publish.</p>
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
        f"{project['title']} is a domain ontology focused on hydrogen electrochemical systems rather than the full hydrogen economy.",
        "Its primary scope is hydrogen electrochemical systems, including PEMFC and PEMWE experiments, materials, processes, measurements, data, and provenance.",
        f"The current release snapshot contains {summary['schema_count']} schema terms and preserves the original h2kg identifiers by default.",
        *profile_lines,
    ]
    architecture = """
    <section class="grid">
      <article class="card">
        <h2>Release Architecture</h2>
        <p>AIMWORKS remains the domain-specific release and documentation layer, while ODK is introduced as a nested standard ontology engineering and QC backend.</p>
        <p>PEMFC and PEMWE profile modules remain AIMWORKS outputs in H2KG v2, while the ODK machine backend preserves the established public H2KG IRIs.</p>
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
        *record.get("notations", []),
        *record.get("sources", []),
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
    for guidance in record.get("quantity_guidance", []):
        bits.extend([guidance.get("unit", ""), guidance.get("quantity_kind", ""), guidance.get("description", "")])
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
        "notations": [],
        "sources": [],
        "quantity_guidance": [],
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


def _link_record(
    source: str,
    target: str,
    predicate: str,
    value: str,
    module: str,
    edge_family: str,
    **metadata: Any,
) -> dict[str, Any]:
    return {
        "source": source,
        "target": target,
        "predicate": predicate,
        "value": value,
        "module": module,
        "edgeFamily": edge_family,
        **metadata,
    }


def _build_explorer_dataset(
    terms: list[dict[str, Any]],
    items: dict[str, dict[str, Any]],
    taxonomy_registry: dict[str, Any] | None = None,
    workflow_usage_registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
            "notations": record.get("notations", []),
            "sources": record.get("sources", []),
            "quantity_guidance": record.get("quantity_guidance", []),
            "examples": record.get("examples", []),
            "notes": record.get("notes", []),
            "type_labels": record.get("type_labels", []),
            "category": record["category"],
            "display_class": record.get("type_labels", [record["category"]])[0] if record.get("type_labels") else record["category"],
            "modules": sorted(modules),
            "local": True,
            "deprecated": _deprecated_status(item),
            "mapping_labels": [str(mapping.get("target_label", "")).strip() for mapping in record.get("mappings", []) if str(mapping.get("target_label", "")).strip()],
            "external_alignments": record.get("mappings", []),
            "workflow_usages": [],
            "workflow_badges": [],
        }
        nodes[iri]["search_text"] = _node_search_text(record, item)

    taxonomy_terms = {
        str(term.get("iri", "")): term
        for term in (taxonomy_registry or {}).get("terms", [])
        if term.get("iri")
    }
    for iri, term in taxonomy_terms.items():
        if term.get("disposition") not in {"active_local_class", "deprecated_compatibility_class"}:
            continue
        modules = set(nodes.get(iri, {}).get("modules", []))
        modules.add("taxonomy")
        taxonomy_payload = {
            "taxonomy_parent": term.get("parent_iri", ""),
            "taxonomy_parent_label": term.get("parent_label", ""),
            "taxonomy_path": term.get("ancestor_path", []),
            "taxonomy_top_branch": term.get("top_branch", ""),
            "taxonomy_module": term.get("module", "core"),
            "taxonomy_role": term.get("corrected_semantic_role", "Class"),
            "definition_status": term.get("definition_status", ""),
            "review_status": term.get("review_status", ""),
            "migration_action": term.get("migration_action", ""),
            "replacement_iri": term.get("replacement_iri", ""),
        }
        if iri in nodes:
            nodes[iri].update(taxonomy_payload)
            nodes[iri]["display_class"] = str(term.get("corrected_semantic_role") or "Class")
            nodes[iri]["category"] = "Classes"
            nodes[iri]["type_labels"] = ["Class"]
            nodes[iri]["modules"] = sorted(modules)
            nodes[iri]["description"] = term.get("definition") or nodes[iri].get("description", "")
            nodes[iri]["alt_labels"] = sorted(set(nodes[iri].get("alt_labels", [])) | set(term.get("alt_labels", [])))
            nodes[iri]["notations"] = sorted(set(nodes[iri].get("notations", [])) | set(term.get("notations", [])))
            nodes[iri]["search_text"] = " ".join(
                str(value)
                for value in [
                    nodes[iri].get("search_text", ""),
                    term.get("definition", ""),
                    term.get("parent_label", ""),
                    term.get("top_branch", ""),
                    term.get("module", ""),
                    " ".join(term.get("ancestor_path", [])),
                ]
                if value
            )
            continue
        local_name = str(term.get("local_name") or _fragment_for_iri(iri))
        nodes[iri] = {
            "id": iri,
            "iri": iri,
            "anchor": _term_anchor_for_iri(iri),
            "label": str(term.get("label") or _short_label(iri)),
            "localName": local_name,
            "qname": canonical_qname(iri, "") or iri,
            "description": str(term.get("definition") or "No definition recorded."),
            "alt_labels": term.get("alt_labels", []),
            "notations": term.get("notations", []),
            "sources": [],
            "quantity_guidance": [],
            "examples": [],
            "notes": [],
            "type_labels": ["Class"],
            "category": "Classes",
            "display_class": str(term.get("corrected_semantic_role") or "Class"),
            "modules": sorted(modules),
            "local": True,
            "deprecated": "Deprecated" if term.get("disposition") == "deprecated_compatibility_class" else "Active",
            "mapping_labels": [],
            "external_alignments": [],
            "workflow_usages": [],
            "workflow_badges": [],
            "search_text": " ".join(
                str(value)
                for value in [
                    term.get("label", ""),
                    local_name,
                    term.get("definition", ""),
                    term.get("parent_label", ""),
                    term.get("top_branch", ""),
                    term.get("module", ""),
                    " ".join(term.get("alt_labels", [])),
                    " ".join(term.get("notations", [])),
                ]
                if value
            ),
            **taxonomy_payload,
        }

    def ensure_external(iri: str, label: str = "", description: str = "") -> None:
        if not iri or iri in nodes or iri.startswith(H2KG_NS) or iri == H2KG_ONTOLOGY_IRI:
            return
        nodes[iri] = _external_node_record(iri, label=label, description=description)

    def add_link(
        source: str,
        target: str,
        predicate: str,
        value: str,
        module: str,
        edge_family: str,
        **metadata: Any,
    ) -> None:
        if not source or not target or source == target:
            return
        key = (source, target, predicate, module)
        if key not in links:
            links[key] = _link_record(
                source,
                target,
                predicate,
                value,
                module,
                edge_family,
                **metadata,
            )

    for iri, term in taxonomy_terms.items():
        parent_iri = str(term.get("parent_iri", "")).strip()
        if iri not in nodes or not parent_iri or parent_iri not in nodes:
            continue
        add_link(iri, parent_iri, "subclassOf", "subclassOf", "taxonomy", "taxonomy")

    for iri, record in local_records.items():
        item = items.get(iri, {"@id": iri})
        for relation in record.get("parents", []):
            if relation.get("relation") == "subclassOf" and iri in taxonomy_terms:
                # The v2 taxonomy registry is the authoritative class hierarchy.
                # Avoid rendering a duplicate legacy subclass edge in Combined view.
                continue
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
            add_link(
                iri,
                target_iri,
                str(mapping.get("relation", "mapping")),
                _mapping_relation_label(str(mapping.get("relation", "mapping"))),
                "alignments",
                "mapping",
            )
        types = item.get("@type", [])
        if isinstance(types, str):
            types = [types]
        for type_iri in types:
            if not isinstance(type_iri, str) or type_iri in ignored_type_iris:
                continue
            if iri in taxonomy_terms and type_iri.startswith(H2KG_NS):
                # Local role typing belongs to the legacy compatibility graph,
                # not the canonical class explorer.
                continue
            ensure_external(type_iri, _short_label(type_iri))
            add_link(iri, type_iri, "type", "type", "vocabulary", "type")
        for predicate, value in item.items():
            if not isinstance(predicate, str) or not predicate.startswith(H2KG_NS):
                continue
            for relation in _iri_values(value):
                target_iri = relation.get("iri", "")
                if iri in taxonomy_terms and target_iri in taxonomy_terms:
                    # Canonical workflow-use links are regenerated from SHACL
                    # profiles below.  Never render legacy class assertions.
                    continue
                ensure_external(target_iri, relation.get("label", ""))
                add_link(
                    iri,
                    target_iri,
                    predicate,
                    canonical_qname(predicate, _fragment_for_iri(predicate)),
                    "vocabulary",
                    "object_property",
                )

    badge_labels = {
        "uses as parameter": "Used as parameter",
        "measures property": "Measured property",
        "has output data": "Workflow output",
        "has output material": "Workflow output",
        "uses input data": "Workflow input",
        "uses input material": "Workflow input",
        "normalizes to property": "Normalization property",
        "uses reference scale": "Reference-scale use",
    }
    for usage in (workflow_usage_registry or {}).get("usage_edges", []):
        if usage.get("status") != "migrated-profile":
            continue
        if usage.get("migration_outcome") == "quantity_value_guidance":
            continue
        source_iri = str(usage.get("canonical_source_iri", "")).strip()
        target_iri = str(usage.get("canonical_target_iri", "")).strip()
        if not source_iri or source_iri not in nodes or not target_iri:
            continue
        ensure_external(target_iri, str(usage.get("target_label", "")))
        if target_iri not in nodes:
            continue
        display_relation = str(usage.get("display_relation", "workflow use"))
        path_label = str(usage.get("path_label", ""))
        predicate = f"profile:{usage.get('migration_outcome', 'workflow-use')}:{path_label}"
        add_link(
            source_iri,
            target_iri,
            predicate,
            display_relation,
            "profiles",
            "workflow_usage",
            profilePath=path_label,
            migrationOutcome=str(usage.get("migration_outcome", "")),
            rationale=str(usage.get("rationale", "")),
        )
        usage_record = {
            "source_iri": source_iri,
            "source_label": str(usage.get("source_label", "")),
            "target_iri": target_iri,
            "target_label": str(usage.get("target_label", "")),
            "relation": display_relation,
            "path": path_label,
            "outcome": str(usage.get("migration_outcome", "")),
            "rationale": str(usage.get("rationale", "")),
        }
        for node_iri in (source_iri, target_iri):
            nodes[node_iri].setdefault("workflow_usages", []).append(usage_record)
            modules = set(nodes[node_iri].get("modules", []))
            modules.add("profiles")
            nodes[node_iri]["modules"] = sorted(modules)
        badge = badge_labels.get(display_relation, display_relation.capitalize())
        badges = set(nodes[target_iri].get("workflow_badges", []))
        badges.add(badge)
        nodes[target_iri]["workflow_badges"] = sorted(badges)

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
        "taxonomy": {
            "id": "taxonomy",
            "label": "H2KG 2.1 taxonomy",
            "description": "The complete class hierarchy generated from the approved taxonomy registry.",
            "nodeCount": sum(1 for node in nodes.values() if "taxonomy" in node.get("modules", [])),
            "edgeCount": sum(1 for link in links.values() if link["module"] == "taxonomy"),
        },
        "profiles": {
            "id": "profiles",
            "label": "Workflow use",
            "description": "Contextual use derived from value-free SHACL profiles; it does not change intrinsic taxonomy placement.",
            "nodeCount": sum(1 for node in nodes.values() if "profiles" in node.get("modules", [])),
            "edgeCount": sum(1 for link in links.values() if link["module"] == "profiles"),
        },
    }

    return {
        "profileLabel": "Whole H2KG namespace",
        "referencePage": "hydrogen-ontology.html",
        "overview": {
            "localNodeCount": sum(1 for node in nodes.values() if node.get("local")),
            "externalNodeCount": sum(1 for node in nodes.values() if not node.get("local")),
            "edgeCount": len(links),
            "activeClassCount": sum(1 for term in taxonomy_terms.values() if term.get("disposition") == "active_local_class"),
            "taxonomyVersion": (taxonomy_registry or {}).get("version", "not generated"),
            "taxonomyGovernanceStatus": "approved" if taxonomy_registry else "not generated",
            "workflowUsageCount": len((workflow_usage_registry or {}).get("usage_edges", [])),
        },
        "modules": list(module_map.values()),
        "nodes": sorted(nodes.values(), key=lambda node: (not bool(node.get("local")), str(node.get("label", "")).lower())),
        "links": sorted(links.values(), key=lambda link: (link["module"], link["source"], link["predicate"], link["target"])),
    }


def _explore_body(project: dict[str, Any], explorer: dict[str, Any], page_path: Path, docs_root: Path) -> str:
    reference_link = _relative_href(page_path, docs_root / "hydrogen-ontology.html")
    release_link = _relative_href(page_path, docs_root / "pages" / "release.html")
    data_href = _relative_href(page_path, docs_root / "data" / "explorer.json")
    alignment_evidence_href = _relative_href(page_path, docs_root / "data" / "external_alignment_evidence.json")
    taxonomy_ttl = _relative_href(page_path, docs_root / "ontology" / "h2kg-v2-taxonomy.ttl")
    taxonomy_jsonld = _relative_href(page_path, docs_root / "ontology" / "h2kg-v2-taxonomy.jsonld")
    complete_ttl = _relative_href(page_path, docs_root / "ontology" / "h2kg-v2-complete.ttl")
    complete_jsonld = _relative_href(page_path, docs_root / "ontology" / "h2kg-v2-complete.jsonld")
    taxonomy_registry = _relative_href(page_path, docs_root / "ontology" / "taxonomy_registry.csv")
    migration_registry = _relative_href(page_path, docs_root / "ontology" / "relation_migration_registry.csv")
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
        <p>Search the published H2KG namespace, inspect intrinsic taxonomy placement, and switch to profile-derived workflow use without conflating scientific properties with parameter records.</p>
        <div class="button-row">
          <a class="inline-button" href="{reference_link}">Open full reference</a>
          <a class="inline-button" href="{release_link}">Release context</a>
          <a class="inline-button" href="{taxonomy_ttl}" download>Taxonomy TTL</a>
          <a class="inline-button" href="{taxonomy_jsonld}" download>Taxonomy JSON-LD</a>
          <a class="inline-button" href="{taxonomy_registry}" download>Taxonomy registry</a>
          <a class="inline-button" href="{complete_ttl}" download>Complete TTL</a>
          <a class="inline-button" href="{complete_jsonld}" download>Complete JSON-LD</a>
          <a class="inline-button" href="{migration_registry}" download>Migration registry</a>
        </div>
      </article>
      <article class="card">
        <h2>Explorer Scope</h2>
        <ul class="stats">
          <li><strong>Search scope:</strong> local H2KG terms by default</li>
          <li><strong>Local terms:</strong> {overview.get('localNodeCount', 0)}</li>
          <li><strong>External anchors:</strong> {overview.get('externalNodeCount', 0)}</li>
          <li><strong>Visible link surface:</strong> {overview.get('edgeCount', 0)}</li>
          <li><strong>Active v2 classes:</strong> {overview.get('activeClassCount', 0)}</li>
          <li><strong>Taxonomy version:</strong> {escape(str(overview.get('taxonomyVersion', 'not generated')))}</li>
          <li><strong>Governance status:</strong> {escape(str(overview.get('taxonomyGovernanceStatus', 'not generated')).replace('-', ' '))}</li>
          <li><strong>Profile-derived workflow uses:</strong> {overview.get('workflowUsageCount', 0)}</li>
        </ul>
        <p class="muted">The graph starts with the selected term and its direct visible neighborhood. Expansion is progressive and reversible.</p>
      </article>
    </section>
    <section class="explorer-shell" data-explorer-root data-explorer-data="{data_href}" data-alignment-evidence="{alignment_evidence_href}" data-reference-page="{reference_link}">
      <article class="card explorer-command-bar" aria-label="Graph workspace controls">
        <div class="explorer-command-bar__head">
          <div>
            <p class="eyebrow">Graph workspace</p>
            <h2>View and filter</h2>
            <p class="explorer-command-bar__copy">Choose the semantic perspective before selecting a term. The graph remains centered in the workspace while filters stay available above it.</p>
          </div>
          <div class="explorer-toolbar" aria-label="Graph actions">
            <button type="button" class="inline-button inline-button--ghost" data-explorer-action="undo" disabled>Undo</button>
            <button type="button" class="inline-button inline-button--ghost" data-explorer-action="reset">Reset graph</button>
            <button type="button" class="inline-button inline-button--ghost" data-explorer-action="clear">Clear</button>
          </div>
        </div>
        <div class="explorer-command-bar__controls">
          <fieldset class="explorer-control-group">
            <legend>View mode</legend>
            <div class="explorer-view-switch" role="radiogroup" aria-label="Explorer view">
              <label><input type="radio" name="explorer-view" value="taxonomy" data-explorer-view checked><span>Taxonomy</span></label>
              <label><input type="radio" name="explorer-view" value="relations" data-explorer-view><span>Workflow use</span></label>
              <label><input type="radio" name="explorer-view" value="combined" data-explorer-view><span>Combined</span></label>
            </div>
          </fieldset>
          <label class="explorer-branch-control" for="explorer-taxonomy-branch">
            <span>Taxonomy branch</span>
            <select id="explorer-taxonomy-branch" data-explorer-branch>
              <option value="">All branches</option>
              <option value="Matter">Matter</option>
              <option value="Process">Process</option>
              <option value="InformationEntity">Information entity</option>
              <option value="Characteristic">Characteristic</option>
              <option value="Agent">Agent</option>
            </select>
          </label>
          <details class="explorer-layer-menu">
            <summary>
              <span><small>Data layers</small><strong data-explorer-layer-count>{len(modules)} of {len(modules)} enabled</strong></span>
              <span class="explorer-layer-menu__chevron" aria-hidden="true">+</span>
            </summary>
            <div class="explorer-layer-popover">
              <div class="explorer-layer-popover__head">
                <div>
                  <p class="eyebrow">Graph content</p>
                  <strong>Visible release modules</strong>
                </div>
                <span>All enabled by default</span>
              </div>
              <div class="explorer-module-grid">{module_html}</div>
            </div>
          </details>
        </div>
        <div class="explorer-command-bar__foot">
          <div class="explorer-taxonomy-legend" aria-label="Taxonomy color legend">
            <span data-branch="Matter">Matter</span>
            <span data-branch="Process">Process</span>
            <span data-branch="InformationEntity">Information</span>
            <span data-branch="Characteristic">Characteristic</span>
            <span data-branch="Agent">Agent</span>
          </div>
          <p>Color and shape show intrinsic taxonomy; badges and workflow edges show contextual use.</p>
        </div>
      </article>
      <aside class="explorer-sidebar">
        <article class="card explorer-panel explorer-search-panel">
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
          <p class="eyebrow">Traversal</p>
          <h3>History</h3>
          <div class="explorer-trail" data-explorer-trail>
            <div class="explorer-empty">The traversal trail appears after you select a term.</div>
          </div>
        </article>
      </aside>
      <section class="explorer-main">
        <article class="card explorer-panel explorer-graph-panel">
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
          <nav class="explorer-breadcrumb" data-explorer-breadcrumb aria-label="Taxonomy path">
            <span>Select a taxonomy term to show its hierarchy path.</span>
          </nav>
          <div class="explorer-chart-wrap">
            <div class="explorer-chart" data-explorer-chart></div>
          </div>
        </article>
        <div class="explorer-detail-grid">
          <article class="card explorer-panel">
            <p class="eyebrow">Selected term</p>
            <div data-explorer-inspector>
              <div class="explorer-empty">Pick a term to inspect its stable IRI, definition, and graph role.</div>
            </div>
          </article>
          <article class="card explorer-panel">
            <div class="explorer-panel__head explorer-panel__head--compact">
              <div>
                <p class="eyebrow">Visible relations</p>
              </div>
              <button type="button" class="inline-button inline-button--small inline-button--ghost" data-explorer-download-relations disabled>Download Excel (.xls)</button>
            </div>
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


def _merge_external_alignment_mappings(
    mappings: list[dict[str, Any]],
    registry_path: Path,
) -> list[dict[str, Any]]:
    """Use the reviewed bridge as the authoritative documentation mapping surface."""
    source_rows = mappings
    if registry_path.exists():
        payload = load_json(registry_path)
        # The registry separates asserted mappings from pending review
        # candidates. Only its `mappings` collection is publication-grade.
        source_rows = payload.get("mappings", [])
    reviewed = {
        (str(row.get("local_iri", "")), str(row.get("relation", "")), str(row.get("target_iri", ""))): dict(row)
        for row in source_rows
        if row.get("local_iri") and row.get("relation") and row.get("target_iri")
    }
    return sorted(
        reviewed.values(),
        key=lambda row: (
            str(row.get("local_label", "")).casefold(),
            str(row.get("relation", "")),
            str(row.get("target_iri", "")),
        ),
    )


def _build_external_alignment_evidence(
    coverage_path: Path,
    asserted_mappings: list[dict[str, Any]],
) -> dict[str, Any]:
    asserted_pairs = {
        (str(row.get("local_iri", "")), str(row.get("target_iri", "")))
        for row in asserted_mappings
    }
    ontology_metadata: dict[str, dict[str, str]] = {}
    ontology_summary = coverage_path.parent / "ontology_summary.csv"
    if ontology_summary.exists():
        with ontology_summary.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                ontology_id = str(row.get("ontology_id", ""))
                ontology_metadata.setdefault(
                    ontology_id,
                    {
                        "title": str(row.get("ontology_title", "")),
                        "version": str(row.get("ontology_version", "")),
                    },
                )
    by_iri: dict[str, list[dict[str, Any]]] = {}
    if coverage_path.exists():
        with coverage_path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                outcome = str(row.get("outcome", ""))
                if outcome not in {"related_non_equivalent", "h2kg_narrower", "h2kg_broader"}:
                    continue
                local_iri = str(row.get("h2kg_iri", ""))
                target_iri = str(row.get("best_external_iri", ""))
                if not local_iri or not target_iri or (local_iri, target_iri) in asserted_pairs:
                    continue
                ontology_id = str(row.get("best_ontology_id", ""))
                metadata = ontology_metadata.get(ontology_id, {})
                record = {
                    "outcome": outcome,
                    "relation_label": {
                        "related_non_equivalent": "related, not equivalent",
                        "h2kg_narrower": "candidate broader than H2KG",
                        "h2kg_broader": "candidate narrower than H2KG",
                    }[outcome],
                    "target_iri": target_iri,
                    "target_label": str(row.get("best_external_label", "")),
                    "ontology_id": ontology_id,
                    "ontology_title": metadata.get("title", ""),
                    "ontology_version": metadata.get("version", ""),
                    "collection": str(row.get("collection", "")),
                    "evidence": str(row.get("decision_basis", "")),
                    "tib_catalogue_url": f"https://terminology.tib.eu/ts/ontologies/{ontology_id}",
                    "publication_status": "benchmark-evidence-not-asserted",
                }
                by_iri.setdefault(local_iri, []).append(record)
    for iri, rows in by_iri.items():
        unique = {
            (row["outcome"], row["target_iri"], row["collection"]): row
            for row in rows
        }
        by_iri[iri] = sorted(
            unique.values(),
            key=lambda row: (row["outcome"], row["ontology_id"], row["target_label"].casefold()),
        )
    return {
        "schema_version": "h2kg-external-alignment-evidence/v1",
        "source": "h2kg_collection_coverage.csv",
        "record_count": sum(len(rows) for rows in by_iri.values()),
        "h2kg_term_count": len(by_iri),
        "by_h2kg_iri": dict(sorted(by_iri.items())),
    }


def _alignment_body(
    mappings: list[dict[str, Any]],
    summary: dict[str, Any],
    registry: dict[str, Any],
) -> str:
    machine_mappings = [row for row in mappings if row.get("status") == "machine_safe"]
    machine_exact_count = sum(row.get("relation") == "skos:exactMatch" for row in machine_mappings)
    machine_broad_count = sum(row.get("relation") == "skos:broadMatch" for row in machine_mappings)
    machine_narrow_count = sum(row.get("relation") == "skos:narrowMatch" for row in machine_mappings)
    reviewed_count = sum(row.get("status") != "machine_safe" for row in mappings)
    relation_options = sorted({str(row.get("relation", "")) for row in mappings if row.get("relation")})
    ontology_options = sorted({str(row.get("tib_ontology_id", "")) for row in mappings if row.get("tib_ontology_id")})
    collection_options = sorted(
        {
            str(value)
            for row in mappings
            for value in (
                row.get("collections", [])
                if isinstance(row.get("collections", []), list)
                else str(row.get("collections", "")).split("|")
            )
            if str(value).strip()
        },
        key=str.casefold,
    )
    category_options = sorted(
        {str(row.get("alignment_category", "")) for row in mappings if row.get("alignment_category")},
        key=str.casefold,
    )
    confidence_options = sorted(
        {str(row.get("confidence", "")) for row in mappings if row.get("confidence")},
        key=str.casefold,
    )
    status_options = sorted(
        {str(row.get("publication_status", "")) for row in mappings if row.get("publication_status")},
        key=str.casefold,
    )

    def options(values: list[str]) -> str:
        return "".join(f"<option value='{escape(value)}'>{escape(value)}</option>" for value in values)

    rows = "".join(
        f"""
        <tr data-alignment-row
            data-relation="{escape(str(item.get('relation', '')))}"
            data-ontology="{escape(str(item.get('tib_ontology_id', '')))}"
            data-collection="{escape(' '.join(item.get('collections', [])) if isinstance(item.get('collections', []), list) else str(item.get('collections', '')))}"
            data-category="{escape(str(item.get('alignment_category', '')))}"
            data-confidence="{escape(str(item.get('confidence', '')))}"
            data-status="{escape(str(item.get('publication_status', 'asserted')))}">
          <td><strong>{escape(str(item.get('local_label', '')))}</strong><br><code>{escape(str(item.get('local_iri', '')))}</code></td>
          <td><span class="status-pill good">{escape(_mapping_relation_label(str(item.get('relation', ''))))}</span></td>
          <td><strong>{escape(str(item.get('target_label', '')))}</strong><br><a href="{escape(str(item.get('target_iri', '')))}"><code>{escape(str(item.get('target_iri', '')))}</code></a></td>
          <td><strong>{escape(str(item.get('tib_ontology_id', '')))}</strong><br>{escape(str(item.get('tib_ontology_version', '')))}<br><a href="{escape(str(item.get('tib_catalogue_url', '')))}">TIB catalogue</a></td>
          <td>{escape(', '.join(item.get('collections', [])) if isinstance(item.get('collections', []), list) else str(item.get('collections', '')))}</td>
          <td>{escape(str(item.get('alignment_category', '')).replace('_', ' '))}</td>
          <td>{escape(str(item.get('confidence', '')))}<br><small>{escape(str(item.get('publication_status', 'asserted')))}</small></td>
          <td>{escape(str(item.get('mapping_evidence') or item.get('rationale') or ''))}</td>
        </tr>
        """
        for item in mappings
    )
    return f"""
    <section class='grid'>
      <article class='card'><h2>Asserted mappings</h2><p><strong>{len(mappings)}</strong> mappings are published in the versioned bridge: {len(machine_mappings)} TIB benchmark assertions ({machine_exact_count} exact, {machine_broad_count} H2KG-narrower, and {machine_narrow_count} H2KG-broader) plus {reviewed_count} reviewed foundational assertions.</p></article>
      <article class='card'><h2>Conservative boundary</h2><p>Only exact, broader, and narrower mappings pass into the asserted SKOS bridge. Other benchmark results remain audit evidence.</p></article>
      <article class='card'><h2>Snapshot scope</h2><p>{summary.get('tib_unique_ontology_count', 0)} unique ontologies across {summary.get('tib_collection_membership_count', 0)} collection memberships; snapshot {escape(str(summary.get('tib_snapshot_retrieved_at', 'not available')))}.</p></article>
    </section>
    <section class="card">
      <h2>Downloads and full evidence</h2>
      <p>The bridge is separate from the H2KG taxonomy. It adds no collection-wide imports, preserves original external ontology IRIs, and is published directly through the H2KG release downloads.</p>
      <div class="button-row">
        <a class="inline-button" href="../ontology/h2kg-v2-external-bridge.ttl" download>Turtle</a>
        <a class="inline-button" href="../ontology/h2kg-v2-external-bridge.jsonld" download>JSON-LD</a>
        <a class="inline-button" href="../ontology/h2kg-tib-asserted-mappings.sssom.tsv" download>SSSOM</a>
        <a class="inline-button" href="../ontology/external_alignment_registry.csv" download>Registry CSV</a>
        <a class="inline-button" href="../ontology/h2kg-tib-alignment-changelog.csv" download>Changelog</a>
        <a class="inline-button" href="tib-benchmark.html">Ontology-level benchmark</a>
        <a class="inline-button" href="../benchmarks/tib_collections/h2kg_tib_collection_benchmark.xlsx" download>Audit workbook</a>
      </div>
    </section>
    <section class="card" data-alignment-table-root>
      <h2>Search asserted alignments</h2>
      <div class="alignment-filters">
        <label>Search <input type="search" data-alignment-query placeholder="H2KG term, target, IRI, evidence"></label>
        <label>Relation <select data-alignment-filter="relation"><option value="">All</option>{options(relation_options)}</select></label>
        <label>Ontology <select data-alignment-filter="ontology"><option value="">All</option>{options(ontology_options)}</select></label>
        <label>Collection <select data-alignment-filter="collection"><option value="">All</option>{options(collection_options)}</select></label>
        <label>Category <select data-alignment-filter="category"><option value="">All</option>{options(category_options)}</select></label>
        <label>Confidence <select data-alignment-filter="confidence"><option value="">All</option>{options(confidence_options)}</select></label>
        <label>Publication status <select data-alignment-filter="status"><option value="">All</option>{options(status_options)}</select></label>
      </div>
      <p class="muted"><span data-alignment-visible>{len(mappings)}</span> of {len(mappings)} mappings shown.</p>
      <div class="table-wrap"><table class="catalog-table"><thead><tr><th>H2KG term</th><th>Relation</th><th>External term</th><th>Ontology/version</th><th>Collection</th><th>Category</th><th>Confidence/status</th><th>Evidence</th></tr></thead><tbody>{rows}</tbody></table></div>
    </section>
    <script>
    (() => {{
      const root = document.querySelector('[data-alignment-table-root]');
      if (!root) return;
      const rows = [...root.querySelectorAll('[data-alignment-row]')];
      const query = root.querySelector('[data-alignment-query]');
      const filters = [...root.querySelectorAll('[data-alignment-filter]')];
      const count = root.querySelector('[data-alignment-visible]');
      const apply = () => {{
        const needle = query.value.trim().toLowerCase();
        let visible = 0;
        rows.forEach((row) => {{
          const filterMatch = filters.every((control) => !control.value || (row.dataset[control.dataset.alignmentFilter] || '').toLowerCase().includes(control.value.toLowerCase()));
          const textMatch = !needle || row.textContent.toLowerCase().includes(needle);
          row.hidden = !(filterMatch && textMatch);
          if (!row.hidden) visible += 1;
        }});
        count.textContent = String(visible);
      }};
      query.addEventListener('input', apply);
      filters.forEach((control) => control.addEventListener('change', apply));
    }})();
    </script>
    """


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
        <p class="muted">ODK backend status: {escape(_shadow_mode_summary(odk))}</p>
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
    if term.get("notations"):
        meta_rows.append(("notation", escape("; ".join(term["notations"]))))
    if term.get("sources"):
        meta_rows.append(("source", "<br>".join(f"<a href='{escape(value)}'>{escape(value)}</a>" if value.startswith("http") else escape(value) for value in term["sources"])))
    if term.get("quantity_guidance"):
        guidance = term["quantity_guidance"]
        meta_rows.append(("QUDT guidance", "<br>".join(escape(" | ".join(part for part in [row.get("quantity_kind", ""), row.get("unit", ""), row.get("description", "")] if part)) for row in guidance)))
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


def _release_body(
    release: dict[str, Any],
    odk: dict[str, Any],
    hdo: dict[str, Any],
    alignment: dict[str, Any],
    page_path: Path,
    docs_root: Path,
) -> str:
    artifacts = "".join(f"<li>{escape(str(item))}</li>" for item in release.get("artifacts", []))
    odk_base = _relative_href(page_path, docs_root / "odk")
    odk_artifacts = _odk_artifact_cards(odk, odk_base)
    asserted_source_href = _relative_href(page_path, docs_root / "source" / "h2kg-asserted-source.jsonld")
    gates = _render_rows(odk.get("promotion_gates", []))
    parity = odk.get("parity", {})
    publication = release.get("publication_evidence", {})
    promotion_state = str(odk.get("promotion_state", "shadow"))
    publication_established = publication.get("publication_status") == "published" and publication.get("resolver_status") == "established"
    alignment_links = {
        "ttl": _relative_href(page_path, docs_root / "ontology" / "h2kg-v2-external-bridge.ttl"),
        "jsonld": _relative_href(page_path, docs_root / "ontology" / "h2kg-v2-external-bridge.jsonld"),
        "sssom": _relative_href(page_path, docs_root / "ontology" / "h2kg-tib-asserted-mappings.sssom.tsv"),
        "csv": _relative_href(page_path, docs_root / "ontology" / "external_alignment_registry.csv"),
        "excel": _relative_href(page_path, docs_root / "benchmarks" / "tib_collections" / "h2kg_tib_collection_benchmark.xlsx"),
        "page": _relative_href(page_path, docs_root / "pages" / "alignment.html"),
        "benchmark": _relative_href(page_path, docs_root / "pages" / "tib-benchmark.html"),
    }
    semantic_links = {
        "complete_ttl": _relative_href(page_path, docs_root / "ontology" / "h2kg-v2-complete.ttl"),
        "complete_jsonld": _relative_href(page_path, docs_root / "ontology" / "h2kg-v2-complete.jsonld"),
        "profiles_ttl": _relative_href(page_path, docs_root / "ontology" / "h2kg-v2-workflow-profiles.ttl"),
        "profiles_jsonld": _relative_href(page_path, docs_root / "ontology" / "h2kg-v2-workflow-profiles.jsonld"),
        "audit": _relative_href(page_path, docs_root / "ontology" / "semantic_role_audit.csv"),
        "migration": _relative_href(page_path, docs_root / "ontology" / "relation_migration_registry.csv"),
        "compatibility": _relative_href(page_path, docs_root / "ontology" / "h2kg-v2-compatibility.ttl"),
    }
    principal_sources = sorted(
        alignment.get("tib_benchmark_sources", alignment.get("sources", {})).items(),
        key=lambda item: (-int(item[1]), str(item[0]).casefold()),
    )[:8]
    principal_source_text = ", ".join(f"{source} ({count})" for source, count in principal_sources) or "not available"
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
        <h2>Release Artifacts</h2>
        <ul>{artifacts or artifacts_fallback}</ul>
      </article>
    </section>
    <section class="stack">
      <article class="card">
        <p class="eyebrow">H2KG 2.1</p>
        <h2>Intrinsic taxonomy and contextual workflow use</h2>
        <p>The recommended complete distribution combines the H2KG taxonomy, value-free SHACL workflow profiles, and QUDT guidance. Scientific quantities remain Properties or Characteristics; their use as selected inputs is represented through Parameter records and the <code>hasParameter / ofProperty</code> path.</p>
        <p>The compatibility graph is retained only for migration and may contain legacy class-level workflow assertions. It does not drive canonical outputs or Explore.</p>
        <div class="button-row">
          <a class="inline-button" href="{semantic_links['complete_ttl']}" download>Complete TTL</a>
          <a class="inline-button" href="{semantic_links['complete_jsonld']}" download>Complete JSON-LD</a>
          <a class="inline-button" href="{semantic_links['profiles_ttl']}" download>Workflow profiles TTL</a>
          <a class="inline-button" href="{semantic_links['profiles_jsonld']}" download>Workflow profiles JSON-LD</a>
          <a class="inline-button" href="{semantic_links['audit']}" download>Semantic-role audit</a>
          <a class="inline-button" href="{semantic_links['migration']}" download>Migration registry</a>
          <a class="inline-button inline-button--ghost" href="{semantic_links['compatibility']}" download>Legacy compatibility TTL</a>
        </div>
      </article>
    </section>
    <section class="stack">
      <article class="card">
        <p class="eyebrow">Interoperability</p>
        <h2>External semantic alignment</h2>
        <p>H2KG {escape(str(alignment.get('h2kg_version', '2.1.0')))} publishes a separate semantic bridge derived from the frozen TIB snapshot dated {escape(str(alignment.get('tib_snapshot_retrieved_at', 'not available')))}. The bridge contains <strong>{alignment.get('mapping_count', 0)}</strong> asserted mappings covering <strong>{alignment.get('mapped_h2kg_class_count', 0)}</strong> H2KG classes and <strong>{alignment.get('external_ontology_count', 0)}</strong> external ontologies.</p>
        <ul class="stats">
          <li><strong>Discovery scope:</strong> {alignment.get('tib_collection_count', 0)} TIB collections, {alignment.get('tib_unique_ontology_count', 0)} unique ontologies, {alignment.get('tib_collection_membership_count', 0)} collection memberships</li>
          <li><strong>TIB benchmark assertions:</strong> {alignment.get('tib_benchmark_asserted_mapping_count', alignment.get('machine_safe_mapping_count', 0))} ({escape(', '.join(f'{key}={value}' for key, value in alignment.get('tib_asserted_mapping_counts', {}).items()) or 'none')})</li>
          <li><strong>Reviewed foundational mappings:</strong> {alignment.get('reviewed_foundational_mapping_count', 0)}</li>
          <li><strong>Asserted relations:</strong> {escape(', '.join(f'{key}={value}' for key, value in alignment.get('asserted_mapping_counts', {}).items()) or 'none')}</li>
          <li><strong>Principal benchmark ontologies:</strong> {escape(principal_source_text)}</li>
        </ul>
        <p><strong>Foundational dependencies and reused vocabularies</strong> such as HDO, EMMO, QUDT, ChEBI, PROV-O, and DCTERMS remain distinct from ontologies aligned through the TIB benchmark. Asserted bridge links use the original external ontology IRIs; TIB catalogue URLs are retained only as provenance and discovery links. No NFDI collection is imported wholesale.</p>
        <div class="button-row">
          <a class="inline-button" href="{alignment_links['page']}">Browse alignments</a>
          <a class="inline-button" href="{alignment_links['benchmark']}">Benchmark</a>
          <a class="inline-button" href="{alignment_links['ttl']}" download>Bridge TTL</a>
          <a class="inline-button" href="{alignment_links['jsonld']}" download>Bridge JSON-LD</a>
          <a class="inline-button" href="{alignment_links['sssom']}" download>SSSOM</a>
          <a class="inline-button" href="{alignment_links['csv']}" download>Registry CSV</a>
          <a class="inline-button" href="{alignment_links['excel']}" download>Audit Excel</a>
        </div>
      </article>
    </section>
    <section class="stack">
      <article class="card">
        <h2>ODK Release Artefacts</h2>
        <p class="muted">{escape(odk_intro)}</p>
        {odk_artifacts}
      </article>
      <article class="card">
        <h2>Asserted Source</h2>
        <p class="muted">Supplementary machine-readable JSON-LD serialization of the asserted H2KG source, published for inspection and downstream reuse. This download complements the ODK release artefacts.</p>
        <div class="button-row">
          <a class='inline-button' href='{asserted_source_href}' download='h2kg-asserted-source.jsonld'>JSON-LD</a>
        </div>
      </article>
      <article class="card">
        <h2>ODK Release Status</h2>
        <ul class="stats">
          <li><strong>Current authority:</strong> {escape(str(odk.get('authority', 'ontology release pipeline')))}</li>
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
    semantic_validation = release.get("semantic_role_validation", {})
    semantic_metrics = semantic_validation.get("metrics", {})
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
        {
            "label": "Parameter-property role separation",
            "status": "good" if semantic_validation.get("conforms") else "action",
            "value": f"{semantic_metrics.get('migration_coverage_percent', 0)}% migrated",
            "detail": f"{semantic_metrics.get('migrated_legacy_assertion_count', 0)} of {semantic_metrics.get('legacy_assertion_count', 0)} legacy workflow assertions have documented outcomes; canonical conflations: {semantic_metrics.get('characteristic_parameter_conflation_count', 0)}.",
        },
        {
            "label": "Canonical class-to-class workflow assertions",
            "status": "good" if semantic_metrics.get("canonical_class_object_assertion_count", 1) == 0 else "action",
            "value": str(semantic_metrics.get("canonical_class_object_assertion_count", "not assessed")),
            "detail": "Canonical workflow use is expressed through SHACL paths and occurrence records rather than object-property assertions between OWL classes.",
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
            "detail": "Warnings identify import or technical follow-up work without changing the published H2KG IRIs.",
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
        <h2>TIB Collection Benchmark</h2>
        <p>Review the reproducible H2KG comparison with NFDI4Cat, NFDI4Energy, and NFDI4Ing, including collection- and ontology-level percentages and downloadable Excel evidence.</p>
        <div class="button-row"><a class="inline-button" href="tib-benchmark.html">Open benchmark</a></div>
      </article>
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
        <p class="muted">{escape(str(explanations.get('validation_signals', 'Validation signals summarize structural and metadata checks against the published H2KG release.')))}</p>
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
        <p>ODK runs as the nested H2KG v2 machine-release backend for edit-file management, import refresh, ROBOT-oriented QC, and standard artefacts such as <code>base</code>, <code>full</code>, and <code>simple</code>.</p>
        <p>Current status: <strong>{escape(str(odk.get('mode', 'shadow')))}</strong>. Public H2KG IRIs remain unchanged.</p>
      </article>
      <article class="card">
        <h2>Profile Modules</h2>
        <p>The <code>pemfc</code> and <code>pemwe</code> profiles remain AIMWORKS outputs in H2KG v2. ODK supplies the machine release and QC backend rather than a competing documentation site.</p>
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
        <p>H2KG v2 ODK machine artefacts, ELK reasoning, and ROBOT quality checks are generated in parallel with the AIMWORKS release pipeline.</p>
        <p class="muted">Foundational reuse includes HDO, EMMO, QUDT, ChEBI, PROV-O, and DCTERMS. External TIB alignments are published separately as SKOS exact, broader, and narrower mappings to original ontology IRIs; no NFDI collection is imported wholesale.</p>
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
        <p>ODK artefacts are machine-oriented H2KG v2 releases. Example and data-like content remain in the AIMWORKS profile and workflow packages.</p>
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
    semantic_validation_path = output_dir.parent / "reports" / "semantic_role_validation.json"
    release["semantic_role_validation"] = (
        load_json(semantic_validation_path)
        if semantic_validation_path.exists()
        else {}
    )
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
    semantic_report = output_dir.parent / "reports" / "semantic_role_validation.json"
    odk_manifest = output_dir.parent / "odk" / "manifest.json"
    tracked = [
        ("FAIR snapshot", fair_report),
        ("Validation snapshot", validation_report),
        ("HDO snapshot", hdo_report),
        ("Semantic-role migration", semantic_report),
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
    if timestamps and max(timestamps) - min(timestamps) > 300:
        status = "watch"
        value = "out of sync"
        detail = "Report timestamps differ by more than five minutes, so the page may be mixing build generations."
        if missing:
            detail += f" Missing report inputs: {', '.join(missing)}."
    elif missing:
        status = "action"
        value = "missing inputs"
        detail = f"One or more report inputs are missing: {', '.join(missing)}."
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


def _copy_taxonomy_artifacts(output_dir: Path) -> None:
    source_dir = output_dir.parent / "ontology"
    target_dir = ensure_dir(output_dir / "ontology")
    filenames = (
        "h2kg-v2-taxonomy.ttl",
        "h2kg-v2-taxonomy.jsonld",
        "h2kg-v2-workflow-profiles.ttl",
        "h2kg-v2-workflow-profiles.jsonld",
        "h2kg-v2-complete.ttl",
        "h2kg-v2-complete.jsonld",
        "h2kg-v2-compatibility.ttl",
        "h2kg-v2-compatibility.jsonld",
        "h2kg-v2-taxonomy-shapes.ttl",
        "h2kg-v2-external-bridge.ttl",
        "h2kg-v2-external-bridge.jsonld",
        "h2kg-tib-asserted-mappings.sssom.tsv",
        "h2kg-tib-alignment-changelog.csv",
        "taxonomy_registry.json",
        "taxonomy_registry.csv",
        "resource_disposition_registry.json",
        "resource_disposition_registry.csv",
        "semantic_role_audit.json",
        "semantic_role_audit.csv",
        "relation_migration_registry.json",
        "relation_migration_registry.csv",
        "workflow_usage_registry.json",
        "workflow_usage_registry.csv",
        "external_alignment_registry.json",
        "external_alignment_registry.csv",
    )
    for filename in filenames:
        source = source_dir / filename
        if source.exists():
            shutil.copyfile(source, target_dir / filename)
    releases = source_dir / "releases"
    if releases.exists():
        shutil.copytree(releases, target_dir / "releases", dirs_exist_ok=True)


def _copy_asserted_source_jsonld(input_path: Path, output_dir: Path) -> None:
    target_dir = ensure_dir(output_dir / "source")
    shutil.copyfile(input_path, target_dir / "h2kg-asserted-source.jsonld")


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
            links.append(f"<a class='inline-button' href='{href}' download='{escape(str(filename))}'>{label}</a>")
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
        return "<p class='muted'>ODK machine artefacts are aligned with the curated H2KG v2 release baseline.</p>"
    return "<p class='muted'>ODK machine artefacts are available for release validation and QC.</p>"


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
  grid-template-columns: minmax(290px, 340px) minmax(0, 1fr);
  grid-template-areas:
    "toolbar toolbar"
    "sidebar main";
  gap: 1rem;
  align-items: start;
  width: min(1440px, calc(100vw - 2rem));
  margin-top: 1.35rem;
  margin-left: 50%;
  transform: translateX(-50%);
}
.explorer-shell > * { min-width: 0; }
.explorer-command-bar {
  grid-area: toolbar;
  position: sticky;
  top: 0.75rem;
  z-index: 12;
  padding: 1.05rem 1.2rem;
  border-color: rgba(15,109,122,0.2);
  background:
    linear-gradient(105deg, rgba(239,250,249,0.97), rgba(255,250,242,0.97)),
    var(--panel-strong);
  box-shadow: 0 22px 58px rgba(17,29,36,0.13);
}
.explorer-command-bar__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}
.explorer-command-bar__head .eyebrow { margin-bottom: 0.35rem; }
.explorer-command-bar__head h2 { margin: 0; }
.explorer-command-bar__copy {
  max-width: 52rem;
  margin: 0.35rem 0 0;
  color: var(--muted);
  font-size: 0.9rem;
  line-height: 1.45;
}
.explorer-command-bar__controls {
  display: grid;
  grid-template-columns: minmax(390px, 1.45fr) minmax(190px, 0.65fr) minmax(210px, 0.7fr);
  gap: 0.75rem;
  align-items: end;
  margin-top: 0.9rem;
}
.explorer-control-group {
  min-width: 0;
  margin: 0;
  padding: 0;
  border: 0;
}
.explorer-control-group legend,
.explorer-branch-control > span {
  display: block;
  margin-bottom: 0.38rem;
  color: var(--muted);
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.explorer-branch-control { display: grid; gap: 0; }
.explorer-branch-control select {
  width: 100%;
  min-height: 46px;
  border: 1px solid rgba(19,33,41,0.14);
  border-radius: 13px;
  padding: 0.68rem 0.8rem;
  background: rgba(255,255,255,0.9);
  color: var(--ink);
  font: inherit;
}
.explorer-layer-menu { position: relative; }
.explorer-layer-menu summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.8rem;
  min-height: 46px;
  padding: 0.55rem 0.75rem;
  border: 1px solid rgba(19,33,41,0.14);
  border-radius: 13px;
  background: rgba(255,255,255,0.9);
  cursor: pointer;
  list-style: none;
}
.explorer-layer-menu summary::-webkit-details-marker { display: none; }
.explorer-layer-menu summary small,
.explorer-layer-menu summary strong { display: block; }
.explorer-layer-menu summary small {
  color: var(--muted);
  font-size: 0.7rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.explorer-layer-menu summary strong { margin-top: 0.08rem; font-size: 0.9rem; }
.explorer-layer-menu__chevron {
  display: grid;
  width: 1.65rem;
  height: 1.65rem;
  place-items: center;
  border-radius: 50%;
  background: rgba(15,109,122,0.1);
  color: var(--accent);
  font-size: 1.15rem;
  transition: transform 0.18s ease, background 0.18s ease;
}
.explorer-layer-menu[open] .explorer-layer-menu__chevron {
  transform: rotate(45deg);
  background: rgba(200,106,43,0.14);
  color: var(--accent-2);
}
.explorer-layer-popover {
  position: absolute;
  top: calc(100% + 0.55rem);
  right: 0;
  z-index: 20;
  width: min(430px, calc(100vw - 2.5rem));
  max-height: min(620px, calc(100vh - 11rem));
  overflow: auto;
  padding: 1rem;
  border: 1px solid rgba(19,33,41,0.13);
  border-radius: 18px;
  background: rgba(255,255,255,0.98);
  box-shadow: 0 24px 64px rgba(17,29,36,0.2);
}
.explorer-layer-popover__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  padding-bottom: 0.7rem;
  border-bottom: 1px solid var(--line);
}
.explorer-layer-popover__head .eyebrow { margin-bottom: 0.2rem; }
.explorer-layer-popover__head > span { color: var(--muted); font-size: 0.74rem; }
.explorer-command-bar__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-top: 0.8rem;
  padding-top: 0.7rem;
  border-top: 1px solid rgba(19,33,41,0.08);
}
.explorer-command-bar__foot p {
  margin: 0;
  color: var(--muted);
  font-size: 0.82rem;
  text-align: right;
}
.explorer-sidebar { grid-area: sidebar; }
.explorer-main { grid-area: main; }
.explorer-sidebar, .explorer-main, .explorer-detail-grid { display: grid; gap: 1rem; }
.explorer-search-panel { align-self: start; }
.explorer-graph-panel { min-height: 760px; }
.explorer-panel h2, .explorer-panel h3 { margin: 0; }
  .explorer-panel__head {
    display: flex;
    align-items: start;
    justify-content: space-between;
    gap: 1rem;
  }
  .explorer-panel__head--compact { align-items: center; }
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
.explorer-field select {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 0.72rem 0.85rem;
  font: inherit;
  background: rgba(255,255,255,0.78);
  color: var(--ink);
}
.explorer-view-switch {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.4rem;
  margin: 0;
}
.explorer-view-switch label {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  min-height: 46px;
  border: 1px solid rgba(19,33,41,0.14);
  border-radius: 13px;
  padding: 0.58rem 0.5rem;
  background: rgba(255,255,255,0.88);
  cursor: pointer;
  font-size: 0.88rem;
  font-weight: 750;
  transition: color 0.16s ease, background 0.16s ease, box-shadow 0.16s ease, transform 0.16s ease;
}
.explorer-view-switch input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}
.explorer-view-switch label:hover { transform: translateY(-1px); }
.explorer-view-switch label:has(input:checked) {
  border-color: #0f6d7a;
  background: linear-gradient(135deg, #0f6d7a, #175765);
  color: #fff;
  box-shadow: 0 10px 24px rgba(15,109,122,0.22);
}
.explorer-view-switch label:focus-within { outline: 3px solid rgba(15,109,122,0.22); outline-offset: 2px; }
.explorer-taxonomy-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin: 0;
}
.explorer-taxonomy-legend span {
  border: 1px solid rgba(19,33,41,0.14);
  border-radius: 999px;
  padding: 0.2rem 0.5rem;
  font-size: 0.75rem;
  background: var(--branch-color, #d7dde0);
  color: #102027;
}
.explorer-taxonomy-legend [data-branch="Matter"] { --branch-color: #8dcfc4; }
.explorer-taxonomy-legend [data-branch="Process"] { --branch-color: #f1b46f; }
.explorer-taxonomy-legend [data-branch="InformationEntity"] { --branch-color: #b8a6dc; }
.explorer-taxonomy-legend [data-branch="Characteristic"] { --branch-color: #91c9d8; }
.explorer-taxonomy-legend [data-branch="Agent"] { --branch-color: #b9c0c5; }
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
.explorer-results {
  display: grid;
  gap: 0.55rem;
  max-height: 560px;
  margin-top: 0.9rem;
  padding-right: 0.25rem;
  overflow: auto;
  scrollbar-color: rgba(15,109,122,0.34) transparent;
}
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
.explorer-toolbar { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 0.5rem; margin: 0; }
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
    min-height: 620px;
    border: 1px solid rgba(19,33,41,0.08);
    border-radius: 18px;
    background:
      linear-gradient(rgba(15,109,122,0.035) 1px, transparent 1px),
      linear-gradient(90deg, rgba(15,109,122,0.035) 1px, transparent 1px),
      linear-gradient(180deg, rgba(255,255,255,0.94), rgba(248,244,237,0.76));
    background-size: 28px 28px, 28px 28px, auto;
  }
  .explorer-chart-wrap {
    position: relative;
    margin-top: 0.85rem;
  }
  .explorer-breadcrumb {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.35rem;
    min-height: 2.1rem;
    margin-top: 0.75rem;
    color: var(--muted);
    font-size: 0.86rem;
  }
  .explorer-breadcrumb button,
  .explorer-breadcrumb span {
    border: 0;
    border-radius: 999px;
    padding: 0.3rem 0.58rem;
    background: rgba(15,109,122,0.08);
    color: var(--ink);
    font: inherit;
  }
  .explorer-breadcrumb button { cursor: pointer; }
  .explorer-breadcrumb .separator { padding: 0; background: transparent; color: var(--muted); }
  .explorer-hovercard {
    position: absolute;
    top: 1rem;
    left: 1rem;
    z-index: 4;
    width: min(460px, calc(100% - 2rem));
    max-height: calc(100% - 2rem);
    overflow: auto;
    padding: 0.95rem 1rem;
    border: 1px solid rgba(19,33,41,0.12);
    border-radius: 18px;
    background: rgba(255, 255, 255, 0.94);
    box-shadow: 0 16px 40px rgba(17, 29, 36, 0.14);
    backdrop-filter: blur(12px);
    pointer-events: none;
  }
  .explorer-hovercard.is-hidden { display: none; }
  .explorer-hovercard__head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.75rem;
  }
  .explorer-hovercard__head strong {
    font-size: 1rem;
  }
  .explorer-hovercard__label {
    color: var(--muted);
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .explorer-hovercard__body {
    display: grid;
    gap: 0.6rem;
    margin-top: 0.75rem;
  }
  .explorer-hovercard__triple {
    display: grid;
    gap: 0.25rem;
    padding-top: 0.6rem;
    border-top: 1px solid rgba(19,33,41,0.08);
  }
  .explorer-hovercard__triple:first-child {
    padding-top: 0;
    border-top: 0;
  }
  .explorer-hovercard__spo {
    line-height: 1.55;
    color: var(--ink);
    font-size: 0.96rem;
  }
  .explorer-hovercard__spo strong {
    font-weight: 700;
  }
  .explorer-hovercard__meta {
    color: var(--muted);
    font-size: 0.8rem;
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
@media (max-width: 1180px) {
  .explorer-command-bar__controls {
    grid-template-columns: minmax(380px, 1.25fr) minmax(190px, 0.75fr) minmax(190px, 0.7fr);
  }
}
@media (max-width: 980px) {
  .explorer-shell {
    grid-template-columns: 1fr;
    grid-template-areas:
      "toolbar"
      "sidebar"
      "main";
  }
  .explorer-detail-grid { grid-template-columns: 1fr; }
  .explorer-command-bar { position: relative; top: auto; }
  .explorer-command-bar__controls { grid-template-columns: 1fr 1fr; }
  .explorer-control-group { grid-column: 1 / -1; }
  .explorer-kpis { min-width: 0; }
  .explorer-results { max-height: 360px; }
}
@media (max-width: 760px) {
    .explorer-command-bar__head,
    .explorer-command-bar__foot { align-items: stretch; flex-direction: column; }
    .explorer-command-bar__controls { grid-template-columns: 1fr; }
    .explorer-control-group { grid-column: auto; }
    .explorer-toolbar { justify-content: flex-start; }
    .explorer-command-bar__foot p { text-align: left; }
    .explorer-layer-popover { position: static; width: 100%; max-height: none; margin-top: 0.55rem; }
    .explorer-view-switch { grid-template-columns: 1fr; }
    .explorer-panel__head { flex-direction: column; }
    .explorer-kpis { grid-template-columns: repeat(3, minmax(0, 1fr)); width: 100%; }
    .explorer-graph-panel { min-height: 0; }
    .explorer-chart { min-height: 520px; }
    .explorer-hovercard {
      width: calc(100% - 1.2rem);
      top: 0.6rem;
      left: 0.6rem;
    }
  }
  """


def _explorer_js() -> str:
    return r"""
document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector("[data-explorer-root]");
  if (!root) return;

  const dataPath = root.dataset.explorerData;
  const alignmentEvidencePath = root.dataset.alignmentEvidence;
  const referencePage = root.dataset.referencePage || "../hydrogen-ontology.html";
  const searchInputEl = root.querySelector("[data-explorer-search]");
  const searchStatusEl = root.querySelector("[data-explorer-search-status]");
  const resultsEl = root.querySelector("[data-explorer-results]");
  const trailEl = root.querySelector("[data-explorer-trail]");
  const graphNoteEl = root.querySelector("[data-explorer-graph-note]");
  const inspectorEl = root.querySelector("[data-explorer-inspector]");
  const relationsEl = root.querySelector("[data-explorer-relations]");
  const breadcrumbEl = root.querySelector("[data-explorer-breadcrumb]");
  const branchEl = root.querySelector("[data-explorer-branch]");
  const chartEl = root.querySelector("[data-explorer-chart]");
  const downloadRelationsEl = root.querySelector("[data-explorer-download-relations]");
  const countNodesEl = root.querySelector('[data-explorer-count="nodes"]');
  const countEdgesEl = root.querySelector('[data-explorer-count="edges"]');
  const countExpandedEl = root.querySelector('[data-explorer-count="expanded"]');
  const undoButtonEl = root.querySelector('[data-explorer-action="undo"]');
  const layerMenuEl = root.querySelector(".explorer-layer-menu");
  const layerCountEl = root.querySelector("[data-explorer-layer-count]");

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
  let alignmentEvidencePayload = null;
  let alignmentEvidencePromise = null;
  let cy = null;
  let currentSuggestions = [];

  const state = {
    selectedId: null,
      seedId: null,
      expandedIds: new Set(),
      trail: [],
      history: [],
      highlightedIndex: 0,
      currentGraph: null,
      currentRelations: [],
      hoverCardEl: null,
      viewMode: "taxonomy"
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
  const activeView = () => root.querySelector("[data-explorer-view]:checked")?.value || "taxonomy";
  const activeBranch = () => branchEl?.value || "";
  const toggleEnabled = (name) => Boolean(root.querySelector(`[data-explorer-toggle="${name}"]`)?.checked);
    const branchColor = (branch) => ({
      Matter: "#4aa99b",
      Process: "#d88738",
      InformationEntity: "#8a72bd",
      Characteristic: "#4f9fb4",
      Agent: "#7f8b92",
      Compatibility: "#a6aaad"
    }[branch] || "#9aa4a9");
    const branchShape = (branch) => ({
      Matter: "ellipse",
      Process: "round-rectangle",
      InformationEntity: "diamond",
      Characteristic: "hexagon",
      Agent: "rectangle"
    }[branch] || "ellipse");
    const nodeQname = (node) => String(node.qname || node.localName || node.iri || "");
    const nodeAnchorHref = (node) => `${referencePage}#${encodeURIComponent(node.anchor || node.localName || "")}`;
    const slugify = (value) => stripKey(value).slice(0, 64) || "selection";

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
    const viewMode = activeView();
    const branch = activeBranch();
    return (payload?.nodes || []).filter((node) => {
      if (!isSearchableNode(node)) return false;
      if (!allowExternal && !node.local) return false;
      if (viewMode === "taxonomy" && !(node.modules || []).includes("taxonomy")) return false;
      if (branch && node.taxonomy_top_branch !== branch) return false;
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
    const notations = normalize((node.notations || []).join(" "));
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
    if (notations === q) score += 120;
    if (notations.includes(q)) score += 55;
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
      viewMode: activeView(),
      branch: activeBranch(),
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
    const viewInput = root.querySelector(`[data-explorer-view][value="${snapshot.viewMode || "taxonomy"}"]`);
    if (viewInput) viewInput.checked = true;
    if (branchEl) branchEl.value = snapshot.branch || "";
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
    const viewMode = activeView();
    const branch = activeBranch();
    state.viewMode = viewMode;
    const nodes = (payload.nodes || []).filter((node) => {
      if (!(node.modules || []).some((moduleId) => selectedModules.has(moduleId))) return false;
      if (viewMode === "taxonomy" && !(node.modules || []).includes("taxonomy")) return false;
      if (branch && node.taxonomy_top_branch !== branch) return false;
      return true;
    });
    const nodeMap = new Map(nodes.map((node) => [node.id, node]));
    const links = (payload.links || []).filter((link) => {
      if (!selectedModules.has(link.module) || !nodeMap.has(link.source) || !nodeMap.has(link.target)) return false;
      const isTaxonomy = link.module === "taxonomy" || link.edgeFamily === "taxonomy" || link.predicate === "subclassOf";
      if (viewMode === "taxonomy") return isTaxonomy;
      if (viewMode === "relations") return link.module === "profiles" || link.edgeFamily === "workflow_usage";
      return true;
    });
    const adjacency = new Map();
    links.forEach((link) => {
      if (!adjacency.has(link.source)) adjacency.set(link.source, []);
      if (!adjacency.has(link.target)) adjacency.set(link.target, []);
      adjacency.get(link.source).push(link);
      adjacency.get(link.target).push(link);
    });
    return { nodes, nodeMap, links, adjacency, viewMode, branch };
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
            "background-color": (ele) => branchColor(ele.data("topBranch")),
            "shape": (ele) => branchShape(ele.data("topBranch")),
            "label": "data(label)",
            "font-size": 11,
            "text-wrap": "wrap",
            "text-max-width": 120,
            "color": "#132129",
            "text-valign": "bottom",
            "text-margin-y": 8,
            "width": (ele) => ele.data("isCenter") ? 38 : 28,
            "height": (ele) => ele.data("isCenter") ? 38 : 28,
            "border-width": (ele) => ele.data("isCenter") ? 4 : ele.data("isDeprecated") ? 2.5 : 1.4,
            "border-style": (ele) => ele.data("isDeprecated") ? "dashed" : "solid",
            "border-color": (ele) => ele.data("isCenter") ? "#c86a2b" : "rgba(19,33,41,0.28)"
          }
        },
        {
          selector: "edge",
          style: {
            "line-color": (ele) => ele.data("isTaxonomy") ? "rgba(15,109,122,0.56)" : "rgba(19,33,41,0.24)",
            "target-arrow-color": (ele) => ele.data("isTaxonomy") ? "rgba(15,109,122,0.56)" : "rgba(19,33,41,0.24)",
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
    cy.on("mouseover", "node", (event) => {
      showHoverCardForNode(event.target.id(), event);
    });
    cy.on("mouseover", "edge", (event) => {
      showHoverCardForEdge(event.target.id(), event);
    });
    cy.on("mousemove", "node, edge", (event) => {
      positionHoverCard(event);
    });
    cy.on("mouseout", "node, edge", () => {
      hideHoverCard();
    });
    cy.on("tap", (event) => {
      if (event.target === cy) hideHoverCard();
    });
    return cy;
  }

  function runLayout(graph) {
    const instance = ensureCy();
    if (!graph.nodes.length) return;
    const dense = graph.nodes.length > 28 || graph.links.length > 34;
    instance.layout(
      state.viewMode === "taxonomy"
        ? { name: "breadthfirst", directed: true, animate: false, fit: true, padding: 50, spacingFactor: 1.35 }
        : dense
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
        isCenter: node.id === graph.center?.id,
        isDeprecated: node.deprecated === "Deprecated",
        topBranch: node.taxonomy_top_branch || "",
        semanticRole: node.taxonomy_role || node.display_class || "",
        viewMode: state.viewMode,
        iri: node.iri
      }
    }));
    const edges = graph.links.map((link) => ({
      data: {
        id: `${link.source}|${link.target}|${link.predicate}|${link.module}`,
        source: link.source,
        target: link.target,
        label: String(link.value || link.predicate || ""),
        isTaxonomy: link.module === "taxonomy" || link.edgeFamily === "taxonomy" || link.predicate === "subclassOf"
      }
    }));
    return [...nodes, ...edges];
  }

  function ensureHoverCard() {
    if (state.hoverCardEl) return state.hoverCardEl;
    const container = chartEl.parentElement;
    if (!container) return null;
    const card = document.createElement("div");
    card.className = "explorer-hovercard is-hidden";
    card.setAttribute("aria-hidden", "true");
    container.appendChild(card);
    state.hoverCardEl = card;
    return card;
  }

  function positionHoverCard(event) {
    const card = ensureHoverCard();
    if (!card || card.classList.contains("is-hidden")) return;
    const container = chartEl.parentElement;
    if (!container) return;
    const point = event.renderedPosition || event.position;
    if (!point) return;
    const containerWidth = container.clientWidth;
    const containerHeight = container.clientHeight;
    const cardWidth = Math.min(card.offsetWidth || 360, containerWidth - 16);
    const cardHeight = Math.min(card.offsetHeight || 220, containerHeight - 16);
    const desiredLeft = Math.min(Math.max(point.x + 16, 12), Math.max(12, containerWidth - cardWidth - 12));
    const desiredTop = Math.min(Math.max(point.y + 16, 12), Math.max(12, containerHeight - cardHeight - 12));
    card.style.left = `${desiredLeft}px`;
    card.style.top = `${desiredTop}px`;
  }

  function tripleRowsForNode(nodeId) {
    const graph = state.currentGraph;
    if (!graph) return [];
    return graph.links
      .filter((link) => link.source === nodeId || link.target === nodeId)
      .map((link) => ({
        source: graph.nodeMap.get(link.source)?.label || link.source,
        predicate: String(link.value || link.predicate || ""),
        target: graph.nodeMap.get(link.target)?.label || link.target,
        module: link.module,
        kind: link.edgeFamily,
        path: link.profilePath || "",
        rationale: link.rationale || ""
      }))
      .sort((left, right) => left.predicate.localeCompare(right.predicate) || left.target.localeCompare(right.target));
  }

  function renderHoverCard(title, subtitle, rows) {
    const card = ensureHoverCard();
    if (!card) return;
    const preview = rows.slice(0, 12);
    card.innerHTML = `
      <div class="explorer-hovercard__head">
        <strong>${escapeHtml(title)}</strong>
        <span class="explorer-hovercard__label">${escapeHtml(subtitle)}</span>
      </div>
      <div class="explorer-hovercard__body">
        ${preview.length ? preview.map((row) => `
          <div class="explorer-hovercard__triple">
            <div class="explorer-hovercard__spo"><strong>${escapeHtml(row.source)}</strong> <code>${escapeHtml(row.predicate)}</code> <strong>${escapeHtml(row.target)}</strong></div>
            <div class="explorer-hovercard__meta">${escapeHtml(row.module)}${row.kind ? ` | ${escapeHtml(row.kind)}` : ""}${row.path ? ` | path: ${escapeHtml(row.path)}` : ""}</div>
            ${row.rationale ? `<div class="explorer-hovercard__meta">${escapeHtml(row.rationale)}</div>` : ""}
          </div>
        `).join("") : '<div class="explorer-empty">No visible SPO relations for this selection.</div>'}
        ${rows.length > preview.length ? `<div class="explorer-hovercard__meta">Showing ${preview.length} of ${rows.length} visible relations.</div>` : ""}
      </div>
    `;
    card.classList.remove("is-hidden");
    card.setAttribute("aria-hidden", "false");
  }

  function hideHoverCard() {
    const card = ensureHoverCard();
    if (!card) return;
    card.classList.add("is-hidden");
    card.setAttribute("aria-hidden", "true");
  }

  function showHoverCardForNode(nodeId, event) {
    const graph = state.currentGraph;
    if (!graph) return;
    const node = graph.nodeMap.get(nodeId);
    if (!node) return;
    renderHoverCard(node.label, "Node relations", tripleRowsForNode(nodeId));
    positionHoverCard(event);
  }

  function showHoverCardForEdge(edgeId, event) {
    const graph = state.currentGraph;
    if (!graph) return;
    const link = graph.links.find((item) => `${item.source}|${item.target}|${item.predicate}|${item.module}` === edgeId);
    if (!link) return;
    const row = {
      source: graph.nodeMap.get(link.source)?.label || link.source,
      predicate: String(link.value || link.predicate || ""),
      target: graph.nodeMap.get(link.target)?.label || link.target,
      module: link.module,
      kind: link.edgeFamily,
      path: link.profilePath || "",
      rationale: link.rationale || ""
    };
    renderHoverCard(row.predicate, "Edge relation", [row]);
    positionHoverCard(event);
  }

  function downloadRelationsAsExcel(rows, selectedNode) {
    if (!rows.length) return;
    const tableRows = rows.map((row) => `
      <tr>
        <td>${escapeHtml(row.source)}</td>
        <td>${escapeHtml(row.predicate)}</td>
        <td>${escapeHtml(row.target)}</td>
        <td>${escapeHtml(row.module)}</td>
      </tr>
    `).join("");
    const html = `<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <style>
      table { border-collapse: collapse; font-family: Arial, sans-serif; }
      th, td { border: 1px solid #b8c0c8; padding: 6px 8px; text-align: left; vertical-align: top; }
      th { background: #eef3f5; font-weight: 700; }
      h1 { font-family: Arial, sans-serif; font-size: 18px; }
      p { font-family: Arial, sans-serif; color: #3d4b55; }
    </style>
  </head>
  <body>
    <h1>H2KG Visible Relations</h1>
    <p>Selection: ${escapeHtml(selectedNode?.label || "Current graph selection")}</p>
    <table>
      <thead><tr><th>Source</th><th>Predicate</th><th>Target</th><th>Module</th></tr></thead>
      <tbody>${tableRows}</tbody>
    </table>
  </body>
</html>`;
    const blob = new Blob([html], { type: "application/vnd.ms-excel;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `h2kg-visible-relations-${slugify(selectedNode?.localName || selectedNode?.label || "selection")}.xls`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 0);
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

  function renderBreadcrumb(node) {
    if (!breadcrumbEl) return;
    if (!node || !(node.modules || []).includes("taxonomy")) {
      breadcrumbEl.innerHTML = "<span>No taxonomy path is assigned to this resource.</span>";
      return;
    }
    const allNodes = new Map((payload?.nodes || []).map((item) => [item.id, item]));
    const path = [...(node.taxonomy_path || []), node.id]
      .map((id) => allNodes.get(id))
      .filter(Boolean);
    breadcrumbEl.innerHTML = path.map((item, index) => `
      ${index ? '<span class="separator" aria-hidden="true">/</span>' : ""}
      <button type="button" data-explorer-breadcrumb-node="${escapeHtml(item.id)}">${escapeHtml(item.label)}</button>
    `).join("");
    breadcrumbEl.querySelectorAll("[data-explorer-breadcrumb-node]").forEach((button) => {
      button.addEventListener("click", () => {
        runUndoable(() => {
          state.seedId = state.seedId || button.dataset.explorerBreadcrumbNode;
          selectNode(button.dataset.explorerBreadcrumbNode, { reset: true });
        });
      });
    });
  }

  const alignmentRelationLabel = (relation) => ({
    "skos:exactMatch": "exact equivalent",
    "skos:broadMatch": "H2KG narrower than",
    "skos:narrowMatch": "H2KG broader than",
    "skos:relatedMatch": "related to",
    "owl:equivalentClass": "reviewed equivalent class",
    "owl:equivalentProperty": "reviewed equivalent property",
    "rdfs:subClassOf": "reviewed subclass of",
    "rdfs:subPropertyOf": "reviewed subproperty of"
  })[relation] || relation || "mapping";

  function assertedAlignmentHtml(node) {
    const rows = node.external_alignments || [];
    if (!rows.length) return "";
    return `<div class="explorer-inspector__section"><strong>External alignments</strong>${rows.map((row) => `
      <p><strong>${escapeHtml(alignmentRelationLabel(row.relation))}</strong><br>
      <a href="${escapeHtml(row.target_iri)}">${escapeHtml(row.target_label || row.target_iri)}</a>
      ${row.ontology_id ? `<br>${escapeHtml(row.ontology_id)}${row.ontology_version ? ` · ${escapeHtml(row.ontology_version)}` : ""}` : ""}
      ${row.collections?.length ? `<br>${escapeHtml(row.collections.join(", "))}` : ""}
      ${row.alignment_category ? `<br>Category: ${escapeHtml(row.alignment_category.replaceAll("_", " "))}` : ""}
      ${row.confidence ? `<br>Confidence: ${escapeHtml(row.confidence)}` : ""}
      ${row.evidence ? `<br>${escapeHtml(row.evidence)}` : ""}
      ${row.tib_catalogue_url ? `<br><a href="${escapeHtml(row.tib_catalogue_url)}">TIB catalogue record</a>` : ""}</p>
    `).join("")}</div>`;
  }

  async function renderNonAssertedAlignmentEvidence(node) {
    const target = inspectorEl.querySelector("[data-external-evidence-for]");
    if (!target || !node.local || !alignmentEvidencePath) return;
    if (!alignmentEvidencePromise) {
      alignmentEvidencePromise = fetch(alignmentEvidencePath)
        .then((response) => {
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          return response.json();
        })
        .then((data) => { alignmentEvidencePayload = data; return data; });
    }
    try {
      const data = alignmentEvidencePayload || await alignmentEvidencePromise;
      if (target.dataset.externalEvidenceFor !== node.id) return;
      const rows = data.by_h2kg_iri?.[node.id] || [];
      if (!rows.length) {
        target.innerHTML = '<p>No non-asserted related or directional candidate is recorded for this term in the compact collection-level index.</p>';
        return;
      }
      target.innerHTML = rows.map((row) => `<p><strong>${escapeHtml(row.relation_label)}</strong><br><a href="${escapeHtml(row.target_iri)}">${escapeHtml(row.target_label || row.target_iri)}</a><br>${escapeHtml(row.ontology_id)}${row.ontology_version ? ` · ${escapeHtml(row.ontology_version)}` : ""} · ${escapeHtml(row.collection)}<br>${escapeHtml(row.evidence)}${row.tib_catalogue_url ? `<br><a href="${escapeHtml(row.tib_catalogue_url)}">TIB catalogue record</a>` : ""}</p>`).join("") + '<p><a href="tib-benchmark.html">Open the full ontology-level benchmark</a></p>';
    } catch (_error) {
      target.innerHTML = '<p>Benchmark evidence could not be loaded. The asserted bridge remains available above.</p>';
    }
  }

  function workflowUsageHtml(node) {
    const rows = node.workflow_usages || [];
    if (!rows.length) return '<p>No contextual workflow use is asserted for this class.</p>';
    const unique = new Map();
    rows.forEach((row) => {
      const key = `${row.source_iri}|${row.relation}|${row.target_iri}|${row.path}`;
      unique.set(key, row);
    });
    return Array.from(unique.values()).slice(0, 24).map((row) => `
      <p><strong>${escapeHtml(row.source_label || row.source_iri)}</strong>
      ${escapeHtml(row.relation)}
      <strong>${escapeHtml(row.target_label || row.target_iri)}</strong>
      ${row.path ? `<br>Path: <code>${escapeHtml(row.path)}</code>` : ""}
      ${row.rationale ? `<br>${escapeHtml(row.rationale)}` : ""}</p>
    `).join("");
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
            ${node.taxonomy_top_branch ? `<span class="explorer-chip">${escapeHtml(node.taxonomy_top_branch)}</span>` : ""}
            ${(node.workflow_badges || []).map((badge) => `<span class="explorer-chip">${escapeHtml(badge)}</span>`).join("")}
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
        ${assertedAlignmentHtml(node)}
        ${node.local ? `<div class="explorer-inspector__section"><strong>Benchmark evidence, not asserted</strong><div data-external-evidence-for="${escapeHtml(node.id)}"><p>Loading compact benchmark evidence...</p></div></div>` : ""}
        ${node.taxonomy_parent_label || node.taxonomy_top_branch ? `<div class="explorer-inspector__section"><strong>Intrinsic classification</strong><p>Parent: ${escapeHtml(node.taxonomy_parent_label || "Top-level branch")}<br>Top branch: ${escapeHtml(node.taxonomy_top_branch || "Not assigned")}<br>Semantic role: ${escapeHtml(node.taxonomy_role || "Class")}<br>Module: ${escapeHtml(node.taxonomy_module || "core")}</p></div>` : ""}
        ${node.local ? `<div class="explorer-inspector__section"><strong>Workflow usage</strong>${workflowUsageHtml(node)}</div>` : ""}
        ${node.definition_status ? `<div class="explorer-inspector__section"><strong>Governance</strong><p>Status: approved<br>Definition status: ${escapeHtml(node.definition_status)}<br>Migration: ${escapeHtml(node.migration_action || "none")}</p></div>` : ""}
        ${(node.notations || []).length ? `<div class="explorer-inspector__section"><strong>Notation</strong><p>${escapeHtml(node.notations.join("; "))}</p></div>` : ""}
        ${(node.quantity_guidance || []).length ? `<div class="explorer-inspector__section"><strong>Quantity guidance</strong>${node.quantity_guidance.map((row) => `<p>${escapeHtml([row.quantity_kind, row.unit].filter(Boolean).join(" | "))}<br>${escapeHtml(row.description || "")}</p>`).join("")}</div>` : ""}
        ${(node.sources || []).length ? `<div class="explorer-inspector__section"><strong>Source</strong>${node.sources.map((source) => `<p>${source.startsWith("http") ? `<a href="${escapeHtml(source)}">${escapeHtml(source)}</a>` : escapeHtml(source)}</p>`).join("")}</div>` : ""}
        <div class="explorer-inspector__section">
          <strong>Visualization context</strong>
          <p>${escapeHtml(node.id === graph.center?.id ? "Current focus term." : "Visible through the current expanded neighborhood.")} Direct links in the explorer dataset: ${escapeHtml(String(node.degree || 0))}. Modules: ${escapeHtml((node.modules || []).join(", "))}.</p>
        </div>
      </div>
    `;
    renderNonAssertedAlignmentEvidence(node);
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
      state.currentRelations = [];
      if (downloadRelationsEl) downloadRelationsEl.disabled = true;
      relationsEl.innerHTML = '<div class="explorer-empty">Visible relations will appear here after you select a term.</div>';
      return;
    }
    const rows = graph.links
      .map((link) => ({
        source: graph.nodeMap.get(link.source)?.label || link.source,
        predicate: String(link.value || link.predicate || ""),
        target: graph.nodeMap.get(link.target)?.label || link.target,
        module: link.module,
        kind: link.edgeFamily,
        path: link.profilePath || "",
        rationale: link.rationale || ""
      }))
      .sort((left, right) => left.predicate.localeCompare(right.predicate) || left.target.localeCompare(right.target));
    state.currentRelations = rows;
    if (downloadRelationsEl) downloadRelationsEl.disabled = rows.length === 0;
    if (!rows.length) {
      relationsEl.innerHTML = '<div class="explorer-empty">No visible relations remain with the current graph filters.</div>';
      return;
    }
    relationsEl.innerHTML = `
      <table class="explorer-relations">
        <thead>
          <tr><th>Source</th><th>Predicate</th><th>Target</th><th>Path</th><th>Module</th></tr>
        </thead>
        <tbody>
          ${rows.map((row) => `
            <tr>
              <td>${escapeHtml(row.source)}</td>
              <td><code>${escapeHtml(row.predicate)}</code></td>
              <td>${escapeHtml(row.target)}</td>
              <td>${row.path ? `<code>${escapeHtml(row.path)}</code>` : "-"}</td>
              <td>${escapeHtml(row.module)}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  }

  function renderGraph(graph) {
    state.currentGraph = graph;
    hideHoverCard();
    countNodesEl.textContent = String(graph.nodes.length);
    countEdgesEl.textContent = String(graph.links.length);
    countExpandedEl.textContent = String(graph.meta.expandedCount || 0);
    if (!graph.center) {
      hideHoverCard();
      graphNoteEl.textContent = "Search for a term or choose a suggested starting point to render the ontology graph.";
      if (cy) cy.elements().remove();
      return;
    }
    const viewLabel = state.viewMode === "taxonomy" ? "taxonomy hierarchy" : state.viewMode === "combined" ? "combined taxonomy and workflow-use neighborhood" : "workflow-use neighborhood";
    graphNoteEl.textContent = `Showing the direct ${viewLabel} for ${graph.center.label}. Click a visible node to recenter and expand the exploration trail.`;
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
    renderBreadcrumb(graph.center);
    renderRelations(graph);
  }

  function applyDeepLink() {
    const params = new URLSearchParams(window.location.search);
    const iri = params.get("iri");
    const requestedView = params.get("view");
    if (["relations", "taxonomy", "combined"].includes(requestedView)) {
      const input = root.querySelector(`[data-explorer-view][value="${requestedView}"]`);
      if (input) input.checked = true;
    }
    if (!iri || !payload) return;
    const match = (payload.nodes || []).find((node) => node.iri === iri);
    if (!match) return;
    state.seedId = match.id;
    selectNode(match.id, { reset: true });
  }

  function syncLayerCount() {
    if (!layerCountEl) return;
    const modules = Array.from(root.querySelectorAll("[data-explorer-module]"));
    const enabled = modules.filter((input) => input.checked).length;
    layerCountEl.textContent = `${enabled} of ${modules.length} enabled`;
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

  root.querySelectorAll("[data-explorer-module], [data-explorer-toggle], [data-explorer-view], [data-explorer-branch]").forEach((input) => {
    input.addEventListener("change", () => {
      syncLayerCount();
      renderAll();
    });
  });
  document.addEventListener("click", (event) => {
    if (layerMenuEl?.open && !layerMenuEl.contains(event.target)) layerMenuEl.open = false;
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && layerMenuEl?.open) {
      layerMenuEl.open = false;
      layerMenuEl.querySelector("summary")?.focus();
    }
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
    if (downloadRelationsEl) {
      downloadRelationsEl.addEventListener("click", () => {
        downloadRelationsAsExcel(state.currentRelations || [], state.currentGraph?.center || null);
      });
    }

    syncLayerCount();
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
.alignment-filters { display: grid; grid-template-columns: repeat(auto-fit, minmax(165px, 1fr)); gap: 0.8rem; margin: 1rem 0; }
.alignment-filters label { display: grid; gap: 0.3rem; color: var(--muted); font-size: 0.84rem; font-weight: 700; }
.alignment-filters input, .alignment-filters select { width: 100%; padding: 0.65rem 0.75rem; border: 1px solid var(--line); border-radius: 10px; background: rgba(255,255,255,0.9); color: var(--ink); }
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
  .alignment-filters { grid-template-columns: 1fr; }
  .acknowledgement { grid-template-columns: 1fr; }
  .hero-head { grid-template-columns: 1fr; }
  .hero-brand { justify-self: start; min-width: 0; width: fit-content; }
  .hero-brand img { width: 126px; }
  h1 { max-width: 13ch; }
  .reference-meta div, .reference-relations div { grid-template-columns: 1fr; gap: 0.2rem; }
}
"""
