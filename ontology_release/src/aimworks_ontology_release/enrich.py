from __future__ import annotations

from pathlib import Path
from typing import Any

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SKOS

from .classify import ResourceClassification
from .inspect import find_ontology_node
from .io import save_graph
from .normalize import coerce_version, humanize_identifier
from .utils import VANN, is_local_iri, local_name, make_literal, today_iso, write_json, write_text

FOAF = Namespace("http://xmlns.com/foaf/0.1/")


def _ensure_literal(graph: Graph, subject: URIRef, predicate: URIRef, value: str, lang: str = "en") -> bool:
    if list(graph.objects(subject, predicate)):
        return False
    graph.add((subject, predicate, Literal(value, lang=lang)))
    return True


def _ensure_object(graph: Graph, subject: URIRef, predicate: URIRef, value: str) -> bool:
    if list(graph.objects(subject, predicate)):
        return False
    graph.add((subject, predicate, URIRef(value)))
    return True


def enrich_graphs(
    schema_graph: Graph,
    controlled_vocabulary_graph: Graph,
    classifications: dict[str, ResourceClassification],
    metadata_defaults: dict[str, Any],
    release_profile: dict[str, Any],
    namespace_policy: dict[str, Any],
    root: Path,
) -> dict[str, Any]:
    ontology_defaults = metadata_defaults.get("ontology", {})
    annotation_defaults = metadata_defaults.get("annotations", {})
    language = annotation_defaults.get("language", "en")
    version = coerce_version(release_profile.get("release", {}).get("version"))
    version_iri = namespace_policy.get("version_iri_template", "{version}").format(version=version)
    ontology_node = find_ontology_node(schema_graph, namespace_policy) or URIRef(namespace_policy["ontology_iri"])
    schema_graph.add((ontology_node, RDF.type, OWL.Ontology))

    added: list[str] = []
    creators = ontology_defaults.get("creator", [])
    contributors = ontology_defaults.get("contributor", [])
    title = ontology_defaults.get("title", release_profile.get("project", {}).get("title", "Ontology"))
    description = ontology_defaults.get("description", "")
    abstract = ontology_defaults.get("abstract", "")

    if _ensure_literal(schema_graph, ontology_node, DCTERMS.title, title, language):
        added.append("dcterms:title")
    if _ensure_literal(schema_graph, ontology_node, DCTERMS.description, description, language):
        added.append("dcterms:description")
    if abstract and _ensure_literal(schema_graph, ontology_node, DCTERMS.abstract, abstract, language):
        added.append("dcterms:abstract")
    for creator in creators:
        if (ontology_node, DCTERMS.creator, Literal(creator, lang=language)) not in schema_graph:
            schema_graph.add((ontology_node, DCTERMS.creator, Literal(creator, lang=language)))
            added.append("dcterms:creator")
    for contributor in contributors:
        if (ontology_node, DCTERMS.contributor, Literal(contributor, lang=language)) not in schema_graph:
            schema_graph.add((ontology_node, DCTERMS.contributor, Literal(contributor, lang=language)))
            added.append("dcterms:contributor")
    if _ensure_literal(schema_graph, ontology_node, DCTERMS.created, release_profile.get("release", {}).get("release_date", today_iso()), None):
        added.append("dcterms:created")
    if list(schema_graph.objects(ontology_node, DCTERMS.modified)):
        schema_graph.set((ontology_node, DCTERMS.modified, Literal(today_iso())))
    else:
        schema_graph.add((ontology_node, DCTERMS.modified, Literal(today_iso())))
    added.append("dcterms:modified")
    if _ensure_object(schema_graph, ontology_node, DCTERMS.license, ontology_defaults.get("license", release_profile.get("release", {}).get("ontology_license", ""))):
        added.append("dcterms:license")
    if _ensure_object(schema_graph, ontology_node, DCTERMS.source, ontology_defaults.get("source", namespace_policy["ontology_iri"])):
        added.append("dcterms:source")
    if _ensure_object(schema_graph, ontology_node, OWL.versionIRI, version_iri):
        added.append("owl:versionIRI")
    if _ensure_literal(schema_graph, ontology_node, OWL.versionInfo, version, None):
        added.append("owl:versionInfo")
    if _ensure_literal(schema_graph, ontology_node, VANN.preferredNamespacePrefix, namespace_policy["preferred_namespace_prefix"], None):
        added.append("vann:preferredNamespacePrefix")
    if _ensure_object(schema_graph, ontology_node, VANN.preferredNamespaceUri, namespace_policy["preferred_namespace_uri"]):
        added.append("vann:preferredNamespaceUri")
    logo = ontology_defaults.get("logo")
    if logo and _ensure_object(schema_graph, ontology_node, FOAF.logo, logo):
        added.append("foaf:logo")

    term_templates = annotation_defaults.get("default_definition_templates", {})
    generated_annotations = 0
    for graph in (schema_graph, controlled_vocabulary_graph):
        for subject in sorted(set(graph.subjects()), key=str):
            if not isinstance(subject, URIRef) or not is_local_iri(subject, namespace_policy):
                continue
            record = classifications.get(str(subject))
            if not record or record.category == "ontology_header":
                continue
            rdfs_label = next((str(obj) for obj in graph.objects(subject, RDFS.label)), "")
            pref_label = next((str(obj) for obj in graph.objects(subject, SKOS.prefLabel)), "")
            label = rdfs_label or pref_label
            if not rdfs_label:
                label = label or humanize_identifier(local_name(subject))
                graph.add((subject, RDFS.label, Literal(label, lang=language)))
                generated_annotations += 1
            elif not label:
                label = humanize_identifier(local_name(subject))
            if annotation_defaults.get("add_is_defined_by", True) and not list(graph.objects(subject, RDFS.isDefinedBy)):
                graph.add((subject, RDFS.isDefinedBy, ontology_node))
                generated_annotations += 1
            has_definition = list(graph.objects(subject, SKOS.definition))
            has_comment = list(graph.objects(subject, RDFS.comment))
            if not has_definition:
                template = term_templates.get(record.category) or term_templates.get(record.term_type) or "A local ontology term representing {label}."
                graph.add((subject, SKOS.definition, Literal(template.format(label=label), lang=language)))
                generated_annotations += 1
            if not has_comment:
                template = term_templates.get(record.category) or term_templates.get(record.term_type) or "A local ontology term representing {label}."
                graph.add((subject, RDFS.comment, Literal(template.format(label=label), lang=language)))
                generated_annotations += 1

    report = {
        "version": version,
        "version_iri": version_iri,
        "added_metadata": added,
        "generated_annotations": generated_annotations,
        "ontology_iri": str(ontology_node),
    }
    return report


def write_enrichment_outputs(schema_graph: Graph, controlled_vocabulary_graph: Graph, report: dict[str, Any], root: Path) -> None:
    save_graph(schema_graph, root / "output" / "ontology" / "schema.ttl", "turtle")
    save_graph(schema_graph, root / "output" / "ontology" / "schema.jsonld", "json-ld")
    save_graph(controlled_vocabulary_graph, root / "output" / "ontology" / "controlled_vocabulary.ttl", "turtle")
    write_json(root / "output" / "reports" / "metadata_report.json", report)
    lines = [
        "# Metadata Report",
        "",
        f"- Version: `{report['version']}`",
        f"- Version IRI: `{report['version_iri']}`",
        f"- Added or normalized metadata items: **{len(report['added_metadata'])}**",
        f"- Generated annotations: **{report['generated_annotations']}**",
        "",
        "## Added Metadata",
        "",
    ]
    if report["added_metadata"]:
        lines.extend(f"- {item}" for item in report["added_metadata"])
    else:
        lines.append("- Existing metadata already covered the required fields.")
    write_text(root / "output" / "reports" / "metadata_report.md", "\n".join(lines) + "\n")
