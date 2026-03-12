from __future__ import annotations

from pathlib import Path
from typing import Any

from rdflib import Graph

from .utils import copy_file, copy_tree, ensure_dir, write_json, write_text


def build_jsonld_context(schema_graph: Graph, controlled_vocabulary_graph: Graph, namespace_policy: dict[str, Any]) -> dict[str, Any]:
    context: dict[str, Any] = {
        "@version": 1.1,
        "@vocab": namespace_policy["preferred_namespace_uri"],
        "id": "@id",
        "type": "@type",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "comment": "http://www.w3.org/2000/01/rdf-schema#comment",
        "definition": "http://www.w3.org/2004/02/skos/core#definition",
        "title": "http://purl.org/dc/terms/title",
        "description": "http://purl.org/dc/terms/description",
        "creator": "http://purl.org/dc/terms/creator",
        "contributor": "http://purl.org/dc/terms/contributor",
        "license": {"@id": "http://purl.org/dc/terms/license", "@type": "@id"},
        "versionIRI": {"@id": "http://www.w3.org/2002/07/owl#versionIRI", "@type": "@id"},
    }
    prefix_map: dict[str, str] = {}
    for graph in (schema_graph, controlled_vocabulary_graph):
        for prefix, namespace in graph.namespaces():
            if prefix:
                prefix_map[prefix] = str(namespace)
    prefix_map.setdefault(namespace_policy["preferred_namespace_prefix"], namespace_policy["preferred_namespace_uri"])
    context.update(dict(sorted(prefix_map.items())))
    return {"@context": context}


def reference_iri_rows(namespace_policy: dict[str, Any], release_profile: dict[str, Any]) -> list[dict[str, str]]:
    ontology_iri = namespace_policy["ontology_iri"].rstrip("/")
    version = str(release_profile["release"]["version"])
    return [
        {"label": "Ontology IRI", "iri": ontology_iri, "purpose": "Canonical ontology IRI with HTML/RDF content negotiation."},
        {"label": "Asserted Source", "iri": f"{ontology_iri}/source", "purpose": "Latest asserted source ontology serialization."},
        {"label": "Inferred Source", "iri": f"{ontology_iri}/inferred", "purpose": "Latest inferred ontology serialization."},
        {"label": "Latest Release", "iri": f"{ontology_iri}/latest", "purpose": "Stable alias for the latest asserted release."},
        {"label": "JSON-LD Context", "iri": f"{ontology_iri}/context", "purpose": "Stable JSON-LD context endpoint."},
        {"label": "Versioned Release", "iri": f"{ontology_iri}/{version}", "purpose": "Version-pinned asserted release."},
        {"label": "Versioned Inferred", "iri": f"{ontology_iri}/{version}/inferred", "purpose": "Version-pinned inferred release."},
    ]


def build_publication_layout(
    root: Path,
    release_profile: dict[str, Any],
    namespace_policy: dict[str, Any],
    context_payload: dict[str, Any],
) -> None:
    publication_dir = root / "output" / "publication"
    docs_dir = root / "output" / "docs"
    ontology_dir = root / "output" / "ontology"
    examples_dir = root / "output" / "examples"
    mappings_dir = root / "output" / "mappings"
    reports_dir = root / "output" / "reports"

    ensure_dir(publication_dir)
    copy_tree(docs_dir, publication_dir)
    reference_page = release_profile["publication"]["reference_page"]
    if (publication_dir / "index.html").exists():
        copy_file(publication_dir / "index.html", publication_dir / "overview.html")
    redirect_html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="0; url={reference_page}">
  <title>H2KG PEMFC Catalyst Layer Application Ontology</title>
</head>
<body>
  <p>Redirecting to <a href="{reference_page}">{reference_page}</a>.</p>
</body>
</html>
"""
    write_text(publication_dir / "index.html", redirect_html)

    source_dir = ensure_dir(publication_dir / "source")
    inferred_dir = ensure_dir(publication_dir / "inferred")
    context_dir = ensure_dir(publication_dir / "context")
    latest_dir = ensure_dir(publication_dir / "latest")
    version_dir = ensure_dir(publication_dir / str(release_profile["release"]["version"]))

    source_filename = release_profile["publication"]["source_filename"]
    source_jsonld_filename = release_profile["publication"]["source_jsonld_filename"]
    inferred_filename = release_profile["publication"]["inferred_filename"]
    context_filename = release_profile["publication"]["context_filename"]

    copy_file(ontology_dir / "schema.ttl", source_dir / source_filename)
    copy_file(ontology_dir / "schema.jsonld", source_dir / source_jsonld_filename)
    copy_file(ontology_dir / "controlled_vocabulary.ttl", source_dir / "controlled_vocabulary.ttl")
    copy_file(ontology_dir / "imports.ttl", source_dir / "imports.ttl")
    copy_file(examples_dir / "examples.ttl", source_dir / "examples.ttl")
    copy_file(mappings_dir / "alignments.ttl", source_dir / "alignments.ttl")

    copy_file(ontology_dir / "inferred.ttl", inferred_dir / inferred_filename)
    write_json(context_dir / context_filename, context_payload)

    copy_file(ontology_dir / "schema.ttl", latest_dir / source_filename)
    copy_file(ontology_dir / "schema.jsonld", latest_dir / source_jsonld_filename)
    copy_file(ontology_dir / "inferred.ttl", latest_dir / "inferred.ttl")
    write_json(latest_dir / context_filename, context_payload)
    copy_file(ontology_dir / "controlled_vocabulary.ttl", latest_dir / "controlled_vocabulary.ttl")
    copy_file(mappings_dir / "alignments.ttl", latest_dir / "alignments.ttl")

    copy_file(ontology_dir / "schema.ttl", version_dir / source_filename)
    copy_file(ontology_dir / "schema.jsonld", version_dir / source_jsonld_filename)
    copy_file(ontology_dir / "inferred.ttl", version_dir / "inferred.ttl")
    write_json(version_dir / context_filename, context_payload)
    copy_file(ontology_dir / "controlled_vocabulary.ttl", version_dir / "controlled_vocabulary.ttl")
    copy_file(examples_dir / "examples.ttl", version_dir / "examples.ttl")
    copy_file(mappings_dir / "alignments.ttl", version_dir / "alignments.ttl")

    copy_tree(reports_dir, publication_dir / "reports")
    copy_tree(mappings_dir, publication_dir / "mappings")
    copy_tree(examples_dir, publication_dir / "examples")

    reference_rows = reference_iri_rows(namespace_policy, release_profile)
    write_json(publication_dir / "reference_iris.json", reference_rows)
    readme_lines = [
        "# Publication Layout",
        "",
        "This directory is intended to be deployed directly as the public static publication root.",
        "",
        "## Reference IRIs",
        "",
    ]
    readme_lines.extend(f"- `{row['label']}`: `{row['iri']}` - {row['purpose']}" for row in reference_rows)
    write_text(publication_dir / "README.md", "\n".join(readme_lines) + "\n")
