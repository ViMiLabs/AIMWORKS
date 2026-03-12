from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader
from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SKOS

from .extract import collect_examples, extract_local_terms
from .inspect import find_ontology_node
from .publication import reference_iri_rows
from .utils import ensure_dir, local_name, write_json, write_text


SITE_CSS = """
:root {
  --accent: #0f766e;
  --accent-soft: #ccfbf1;
  --paper: #f8fafc;
  --ink: #0f172a;
  --muted: #475569;
  --line: #cbd5e1;
  --warm: #fef3c7;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background:
    radial-gradient(circle at top left, rgba(15,118,110,0.16), transparent 35%),
    linear-gradient(180deg, #ecfeff 0%, var(--paper) 32%, #fffdf7 100%);
  color: var(--ink);
  font-family: "Trebuchet MS", "Gill Sans", "Segoe UI", sans-serif;
  line-height: 1.55;
}
code { font-family: "Cascadia Code", "SFMono-Regular", ui-monospace, monospace; font-size: 0.92em; }
.site-shell { max-width: 1220px; margin: 0 auto; padding: 0 1rem 3rem; }
.hero { position: relative; overflow: hidden; padding: 2rem 0 1rem; }
.hero__band { position: absolute; inset: 0 auto auto 0; width: 100%; height: 0.7rem; background: linear-gradient(90deg, var(--accent), #f59e0b); border-radius: 999px; }
.hero__content { padding-top: 1.5rem; }
.eyebrow { text-transform: uppercase; letter-spacing: 0.12em; color: var(--accent); font-size: 0.8rem; font-weight: 700; }
h1, h2, h3 { font-family: Georgia, Cambria, "Times New Roman", serif; line-height: 1.1; }
h1 { font-size: clamp(2.4rem, 5vw, 4rem); margin: 0.2rem 0 0.6rem; max-width: 18ch; }
h2 { margin-top: 0; font-size: 1.8rem; }
.lede { max-width: 62ch; color: var(--muted); font-size: 1.1rem; }
.meta-row { display: flex; gap: 0.8rem; flex-wrap: wrap; color: var(--muted); font-size: 0.92rem; }
.meta-row span { background: rgba(255,255,255,0.7); border: 1px solid var(--line); padding: 0.28rem 0.6rem; border-radius: 999px; }
.nav { display: flex; gap: 0.55rem; flex-wrap: wrap; margin: 1rem 0 1.4rem; }
.nav a { text-decoration: none; color: var(--ink); border: 1px solid var(--line); padding: 0.45rem 0.85rem; border-radius: 999px; background: rgba(255,255,255,0.84); }
.nav a:hover { border-color: var(--accent); color: var(--accent); }
.content { display: grid; gap: 1rem; }
.grid { display: grid; gap: 1rem; }
.grid.two { grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }
.grid.three { grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
.card { background: rgba(255,255,255,0.85); border: 1px solid rgba(203,213,225,0.86); border-radius: 1.25rem; padding: 1.15rem; box-shadow: 0 16px 40px rgba(15,23,42,0.05); }
.score { display: inline-flex; align-items: center; justify-content: center; width: 5rem; height: 5rem; border-radius: 50%; background: linear-gradient(135deg, var(--accent), #f59e0b); color: white; font-size: 1.35rem; font-weight: 700; margin-bottom: 0.75rem; }
.simple-list { margin: 0; padding-left: 1.1rem; }
.chip-row { display: flex; flex-wrap: wrap; gap: 0.5rem; }
.chip-row a { text-decoration: none; color: var(--accent); background: var(--accent-soft); border-radius: 999px; padding: 0.35rem 0.7rem; font-size: 0.88rem; }
.data-table { width: 100%; border-collapse: collapse; font-size: 0.95rem; }
.data-table th, .data-table td { text-align: left; padding: 0.75rem; border-bottom: 1px solid var(--line); vertical-align: top; }
.data-table th { font-size: 0.8rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); }
.filter-input { width: min(320px, 100%); padding: 0.7rem 0.9rem; border: 1px solid var(--line); border-radius: 999px; background: white; }
.section-head { display: flex; justify-content: space-between; gap: 1rem; align-items: end; margin-bottom: 1rem; flex-wrap: wrap; }
.prose p, .prose li { max-width: 72ch; }
.footer { color: var(--muted); font-size: 0.92rem; padding-top: 1rem; }
@media (max-width: 720px) {
  .nav { gap: 0.4rem; }
  .nav a { padding: 0.42rem 0.72rem; }
  .data-table { display: block; overflow-x: auto; }
}
"""

SITE_JS = """
document.querySelectorAll("[data-table-filter]").forEach((input) => {
  const table = document.getElementById(input.dataset.tableFilter);
  if (!table) return;
  input.addEventListener("input", () => {
    const needle = input.value.toLowerCase();
    table.querySelectorAll("tbody tr").forEach((row) => {
      row.style.display = row.textContent.toLowerCase().includes(needle) ? "" : "none";
    });
  });
});
"""


def _graph_text(graph: Graph, subject: URIRef, predicates: list[URIRef]) -> str:
    for predicate in predicates:
        for obj in graph.objects(subject, predicate):
            return str(obj)
    return ""


def _mapping_lookup(review_rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    lookup: dict[str, list[str]] = {}
    for row in review_rows:
        if not row.get("target_iri"):
            continue
        lookup.setdefault(row["local_iri"], []).append(f"{row['relation']} -> {row['target_label']}")
    return lookup


def _term_row(term: Any, mapping_lookup: dict[str, list[str]]) -> dict[str, str]:
    return {
        "label": term.label,
        "iri": term.iri,
        "definition": term.definition or term.comment or "No definition recorded.",
        "superclasses": ", ".join(term.superclasses) or "None",
        "mappings": ", ".join(mapping_lookup.get(term.iri, [])) or "None",
        "kind": term.term_type,
        "domain": ", ".join(term.domains) or "None",
        "range": ", ".join(term.ranges) or "None",
        "anchor": local_name(term.iri),
    }


def build_docs(
    schema_graph: Graph,
    controlled_vocabulary_graph: Graph,
    examples_graph: Graph,
    review_rows: list[dict[str, Any]],
    inspection_report: dict[str, Any],
    validation_report: dict[str, Any],
    fair_scores: dict[str, Any],
    classifications: dict[str, Any],
    release_profile: dict[str, Any],
    namespace_policy: dict[str, Any],
    root: Path,
) -> None:
    output_dir = root / "output" / "docs"
    pages_dir = ensure_dir(output_dir / "pages")
    assets_dir = ensure_dir(output_dir / "assets")
    data_dir = ensure_dir(output_dir / "data")

    env = Environment(loader=FileSystemLoader(str(root / "templates" / "site")))
    site = {
        "title": release_profile["project"]["title"],
        "subtitle": release_profile["project"]["subtitle"],
        "tagline": release_profile["documentation"]["site_tagline"],
        "version": release_profile["release"]["version"],
        "license_label": release_profile["release"]["ontology_license"],
        "prefix": namespace_policy["preferred_namespace_prefix"],
    }
    write_text(assets_dir / "site.css", SITE_CSS)
    write_text(assets_dir / "site.js", SITE_JS)
    write_text(output_dir / ".nojekyll", "")

    mapping_lookup = _mapping_lookup(review_rows)
    schema_terms = extract_local_terms(schema_graph, namespace_policy, classifications)
    vocabulary_terms = extract_local_terms(controlled_vocabulary_graph, namespace_policy, classifications)
    classes = [_term_row(term, mapping_lookup) for term in schema_terms if term.term_type == "class"]
    properties = [_term_row(term, mapping_lookup) for term in schema_terms if term.term_type != "class"]
    vocabulary_rows = [_term_row(term, mapping_lookup) for term in vocabulary_terms]
    classes.sort(key=lambda item: item["label"].lower())
    properties.sort(key=lambda item: item["label"].lower())
    vocabulary_rows.sort(key=lambda item: item["label"].lower())

    ontology_node = find_ontology_node(schema_graph, namespace_policy) or URIRef(namespace_policy["ontology_iri"])
    creators = [str(obj) for obj in schema_graph.objects(ontology_node, DCTERMS.creator)]
    contributors = [str(obj) for obj in schema_graph.objects(ontology_node, DCTERMS.contributor)]
    imports = [str(obj) for obj in schema_graph.objects(ontology_node, OWL.imports)]
    namespace_rows = []
    prefix_lookup = {str(namespace): prefix for prefix, namespace in schema_graph.namespaces()}
    for row in inspection_report["namespace_rows"][:18]:
        namespace_rows.append({"prefix": prefix_lookup.get(row["namespace"], ""), "namespace": row["namespace"], "count": row["count"]})

    overview = {
        "description": _graph_text(schema_graph, ontology_node, [DCTERMS.description, DCTERMS.abstract]),
        "ontology_iri": namespace_policy["ontology_iri"],
        "namespace_mode": namespace_policy["namespace_mode"],
        "schema_term_count": inspection_report["schema_term_count"],
        "vocabulary_count": inspection_report["category_counts"].get("controlled_vocabulary_term", 0),
        "example_count": inspection_report["category_counts"].get("example_individual", 0) + inspection_report["category_counts"].get("quantity_value_data_node", 0),
    }
    cards = [
        {"title": "Alignment Stack", "body": "Primary alignment targets are EMMO, ECHO, QUDT, ChEBI, PROV-O, Dublin Core Terms, and VANN."},
        {"title": "IRI Policy", "body": "The default publication profile preserves the existing hash namespace for backward compatibility and safer first release publishing."},
        {"title": "Release Assets", "body": "The bundle includes machine-readable RDF, static HTML documentation, versioned publication endpoints, validation reports, FAIR reports, and w3id redirect templates."},
    ]
    endpoint_rows = reference_iri_rows(namespace_policy, release_profile)
    metadata_rows = [
        {"label": "Title", "value": _graph_text(schema_graph, ontology_node, [DCTERMS.title])},
        {"label": "Ontology IRI", "value": namespace_policy["ontology_iri"]},
        {"label": "Version", "value": str(release_profile["release"]["version"])},
        {"label": "Namespace mode", "value": namespace_policy["namespace_mode"]},
        {"label": "License", "value": release_profile["release"]["ontology_license"]},
        {"label": "Creators", "value": ", ".join(creators) or "Not recorded"},
        {"label": "Contributors", "value": ", ".join(contributors) or "Not recorded"},
    ]

    index_template = env.get_template("index.html")
    write_text(
        output_dir / "index.html",
        index_template.render(
            page_title="Overview",
            site=site,
            base_path=".",
            overview=overview,
            release_score=fair_scores["overall"],
            readiness_summary="Release readiness combines metadata quality, validation, documentation, mappings, and publication support.",
            blockers=fair_scores["blockers"][:8] or ["No blocking issues detected."],
            cards=cards,
            namespace_rows=namespace_rows,
        ),
    )

    class_template = env.get_template("class_index.html")
    write_text(pages_dir / "class-index.html", class_template.render(page_title="Class Index", site=site, base_path="..", classes=classes))

    property_template = env.get_template("property_index.html")
    write_text(pages_dir / "property-index.html", property_template.render(page_title="Property Index", site=site, base_path="..", properties=properties))

    reference_template = env.get_template("reference.html")
    example_rows = collect_examples(examples_graph, classifications, limit=int(release_profile["release"]["docs_example_preview_limit"]))
    write_text(
        output_dir / release_profile["publication"]["reference_page"],
        reference_template.render(
            page_title="Ontology Reference",
            site=site,
            base_path=".",
            endpoint_rows=endpoint_rows,
            metadata_rows=metadata_rows,
            imports=imports,
            namespace_rows=namespace_rows,
            class_rows=classes,
            property_rows=properties,
            vocabulary_rows=vocabulary_rows,
            example_rows=example_rows,
        ),
    )

    examples_template = env.get_template("examples.html")
    write_text(pages_dir / "examples.html", examples_template.render(page_title="Examples", site=site, base_path="..", examples=example_rows))

    alignment_template = env.get_template("alignment.html")
    write_text(pages_dir / "alignment.html", alignment_template.render(page_title="Alignment", site=site, base_path="..", mappings=review_rows[:200]))

    release_template = env.get_template("release.html")
    release_files = [str(path.relative_to(root / "output")) for path in sorted((root / "output").rglob("*")) if path.is_file()]
    write_text(
        pages_dir / "release.html",
        release_template.render(
            page_title="Release",
            site=site,
            base_path="..",
            release_files=release_files[:120],
            fair_rows=fair_scores["dimensions"],
            validation_lines=[
                f"Overall status: {validation_report['overall_status']}",
                f"SHACL conforms: {validation_report['shacl_conforms']}",
                f"Missing labels: {validation_report['missing_label_count']}",
                f"Missing definitions: {validation_report['missing_definition_count']}",
            ],
        ),
    )

    page_template = env.get_template("page.html")
    user_guide_html = """
<p>Run the pipeline from the <code>ontology_release</code> directory. The default release command performs inspection, split, alignment, enrichment, validation, documentation generation, w3id artifact generation, FAIR scoring, and release bundling.</p>
<pre><code>python -m aimworks_ontology_release.cli release --input input/current_ontology.jsonld</code></pre>
<p>For stepwise review:</p>
<ul>
  <li><code>inspect</code> writes ontology diagnostics and blockers.</li>
  <li><code>split</code> separates schema, vocabulary-like resources, and example/data-like content.</li>
  <li><code>map</code> generates conservative alignment proposals and a CSV review sheet.</li>
  <li><code>annotate</code> creates reviewable annotation drafts, with optional LLM support.</li>
  <li><code>validate</code> runs metadata, namespace, mapping, and SHACL checks.</li>
</ul>
"""
    write_text(pages_dir / "user-guide.html", page_template.render(page_title="User Guide", site=site, base_path="..", heading="User Guide", content_html=user_guide_html))

    overview_html = "<ul>"
    overview_html += f"<li>Ontology IRI: <code>{namespace_policy['ontology_iri']}</code></li>"
    overview_html += f"<li>Version: <code>{release_profile['release']['version']}</code></li>"
    overview_html += f"<li>Creators: {', '.join(creators) or 'Not recorded'}</li>"
    overview_html += f"<li>Imports: {', '.join(imports) or 'None declared in schema module'}</li>"
    overview_html += f"<li>License: <code>{release_profile['release']['ontology_license']}</code></li>"
    overview_html += f"<li>Namespace URI: <code>{namespace_policy['preferred_namespace_uri']}</code></li>"
    overview_html += "</ul>"
    write_text(
        pages_dir / "ontology-overview.html",
        page_template.render(page_title="Ontology Overview", site=site, base_path="..", heading="Ontology Overview", content_html=overview_html),
    )

    write_json(data_dir / "classes.json", classes)
    write_json(data_dir / "properties.json", properties)
    write_json(data_dir / "mappings.json", review_rows)
    write_json(data_dir / "reference_iris.json", endpoint_rows)
