from __future__ import annotations

from pathlib import Path
from typing import Any

from .classify import classify_resources
from .io import load_json_document, merge_document_items
from .mapper import propose_mappings
from .normalize import best_description, best_label
from .utils import (
    default_release_profile,
    dump_json,
    ensure_dir,
    html_paragraphs,
    short_text,
    try_load_yaml,
    write_text,
)


def build_docs(
    input_path: str | Path,
    output_dir: str | Path,
    config_dir: str | Path | None = None,
    fair_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    output_dir = ensure_dir(Path(output_dir))
    ensure_dir(output_dir / "pages")
    ensure_dir(output_dir / "assets")
    write_text(output_dir / ".nojekyll", "")
    profile = try_load_yaml(Path(config_dir or Path(input_path).parent.parent / "config") / "release_profile.yaml", default_release_profile())
    project = profile["project"]
    items = {item["@id"]: item for item in merge_document_items(load_json_document(input_path)) if isinstance(item.get("@id"), str)}
    classes, properties, examples = _term_views(input_path, output_dir.parent / "review", config_dir, items)
    mappings = propose_mappings(input_path, output_dir.parent / "review", config_dir)
    summary = {
        "schema_count": len(classes) + len(properties),
        "vocabulary_count": sum(1 for item in examples if "basis" in item["label"].lower() or "type" in item["label"].lower()),
        "example_count": len(examples),
        "mapping_count": len(mappings),
    }
    release = _release_snapshot_for_docs(output_dir, fair_snapshot)
    pages = {
        output_dir / "index.html": _page_template(project, "Home", _home_body(project, summary, ["EMMO core", "EMMO electrochemistry", "QUDT", "PROV-O", "DCTERMS"])),
        output_dir / "pages" / "user-guide.html": _page_template(project, "User Guide", _user_guide_body()),
        output_dir / "pages" / "ontology-overview.html": _page_template(project, "Ontology Overview", _overview_body(project, summary)),
        output_dir / "pages" / "class-index.html": _page_template(project, "Class Index", _class_body(classes)),
        output_dir / "pages" / "property-index.html": _page_template(project, "Property Index", _property_body(properties)),
        output_dir / "pages" / "alignment.html": _page_template(project, "Alignment", _alignment_body(mappings)),
        output_dir / "pages" / "examples.html": _page_template(project, "Examples", _examples_body(examples)),
        output_dir / "pages" / "quality-dashboard.html": _page_template(project, "Quality Dashboard", _quality_body(release)),
        output_dir / "pages" / "release.html": _page_template(project, "Release", _release_body(release)),
    }
    for path, content in pages.items():
        write_text(path, content)
    write_text(output_dir / "assets" / "style.css", _style_css())
    dump_json(output_dir / "search-index.json", {"classes": classes, "properties": properties, "examples": examples, "mappings": mappings})
    return summary


def _term_views(input_path: str | Path, review_dir: Path, config_dir: str | Path | None, items: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
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
        if classification.kind == "class":
            classes.append(view)
        elif classification.kind in {"object_property", "datatype_property"}:
            properties.append(view)
        elif classification.kind in {"controlled_vocabulary_term", "example_individual", "ephemeral_generated_instance", "quantity_value_data_node"} and len(examples) < 60:
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


def _page_template(project: dict[str, Any], page_title: str, body: str) -> str:
    if page_title == "Home":
        nav_base = "pages/"
        css_base = "assets/style.css"
        home_link = "index.html"
    else:
        nav_base = ""
        css_base = "../assets/style.css"
        home_link = "../index.html"
    nav = f"""
    <nav class="nav">
      <a href="{home_link}">Home</a>
      <a href="{nav_base}user-guide.html">User Guide</a>
      <a href="{nav_base}ontology-overview.html">Overview</a>
      <a href="{nav_base}class-index.html">Classes</a>
      <a href="{nav_base}property-index.html">Properties</a>
      <a href="{nav_base}alignment.html">Alignments</a>
      <a href="{nav_base}examples.html">Examples</a>
      <a href="{nav_base}quality-dashboard.html">Quality</a>
      <a href="{nav_base}release.html">Release</a>
    </nav>
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{page_title} | {project['title']}</title>
  <link rel="stylesheet" href="{css_base}">
</head>
<body>
  <header class="hero">
    <div class="wrap">
      <p class="eyebrow">{project['short_title']}</p>
      <h1>{page_title}</h1>
      <p class="subtitle">{project.get('subtitle', '')}</p>
      {nav}
    </div>
  </header>
  <main class="wrap content">
    {body}
  </main>
  <footer class="footer">
    <div class="wrap">
      <p>{project['title']} | Version {project['version']} | {project['namespace_uri']}</p>
    </div>
  </footer>
</body>
</html>
"""


def _home_body(project: dict[str, Any], summary: dict[str, Any], imports: list[str]) -> str:
    import_list = "".join(f"<li>{item}</li>" for item in imports)
    return f"""
    <section class="grid">
      <article class="card">
        <h2>Scope</h2>
        <p>{project['description']}</p>
      </article>
      <article class="card">
        <h2>Release Snapshot</h2>
        <ul class="stats">
          <li><strong>{summary['schema_count']}</strong> schema terms</li>
          <li><strong>{summary['vocabulary_count']}</strong> curated vocabulary terms</li>
          <li><strong>{summary['example_count']}</strong> example or data-like resources</li>
          <li><strong>{summary['mapping_count']}</strong> mapping proposals</li>
        </ul>
      </article>
      <article class="card">
        <h2>Imports and Alignments</h2>
        <ul>{import_list}</ul>
      </article>
      <article class="card">
        <h2>Publication</h2>
        <p>Stable ontology IRI: <code>{project['ontology_iri']}</code></p>
        <p>Version IRI: <code>{project['version_iri']}</code></p>
        <p>License: <a href="{project['license']}">{project['license']}</a></p>
      </article>
    </section>
    """


def _user_guide_body() -> str:
    return """
    <section class="prose">
      <p>The H2KG PEMFC Catalyst Layer Application Ontology is published conservatively. The recommended maintenance workflow is inspect, split, review mappings, enrich metadata, validate, build docs, then publish.</p>
      <p>Maintain local PEMFC-specific terms under the <code>h2kg</code> namespace unless a future migration policy is approved and redirect artifacts are prepared.</p>
      <p>Use QUDT for quantity kinds and units, ChEBI for chemicals when resolvable, and PROV-O plus DCTERMS for release metadata and provenance.</p>
    </section>
    """


def _overview_body(project: dict[str, Any], summary: dict[str, Any]) -> str:
    paragraphs = [
        f"{project['title']} is an EMMO-aligned application ontology rather than a broad hydrogen-economy ontology.",
        "Its primary scope is PEMFC cathode catalyst-layer experiments, materials, processes, measurements, and provenance.",
        f"The current release snapshot contains {summary['schema_count']} schema terms and preserves the original h2kg identifiers by default.",
    ]
    return f'<section class="prose">{html_paragraphs(paragraphs)}</section>'


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


def _alignment_body(mappings: list[dict[str, Any]]) -> str:
    cards = "".join(
        f"<article class='term-card'><h2>{item['local_label']}</h2><p class='iri'>{item['local_iri']}</p><p><strong>{item['relation']}</strong> {item['target_iri']}</p><p>{item['rationale']}</p></article>"
        for item in mappings[:60]
    )
    return f"<section class='list-grid'>{cards}</section>"


def _examples_body(examples: list[dict[str, Any]]) -> str:
    cards = "".join(
        f"<article class='term-card'><h2>{item['label']}</h2><p class='iri'>{item['iri']}</p><p>{item['description']}</p></article>"
        for item in examples[:60]
    )
    return f"<section class='list-grid'>{cards}</section>"


def _release_body(release: dict[str, Any]) -> str:
    artifacts = "".join(f"<li>{item}</li>" for item in release.get("artifacts", []))
    return f"""
    <section class="grid">
      <article class="card">
        <h2>Release Readiness</h2>
        <p>{release.get('summary', 'No release summary available.')}</p>
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
        <h2>Artifacts</h2>
        <ul>{artifacts}</ul>
      </article>
    </section>
    """


def _release_snapshot_for_docs(output_dir: Path, fair_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    release = dict(fair_snapshot or {"findable": 0, "accessible": 0, "interoperable": 0, "reusable": 0, "summary": "Release summary unavailable.", "artifacts": [], "fair_signals": [], "transparency_hooks": [], "validation_signals": [], "publication_assets": [], "section_explanations": {}})
    publication_assets = [dict(item) for item in release.get("publication_assets", [])]
    for asset in publication_assets:
        if asset.get("label") == "HTML reference page":
            asset["value"] = "ready"
            asset["status"] = "good"
        elif asset.get("label") == "Release bundle" and (output_dir.parent / "release_bundle" / "RELEASE_NOTES.md").exists():
            asset["value"] = "ready"
            asset["status"] = "good"
    release["publication_assets"] = publication_assets
    return release


def _quality_body(release: dict[str, Any]) -> str:
    explanations = release.get("section_explanations", {})
    return f"""
    <section class="prose">
      <p>{release.get('summary', 'No quality summary available.')}</p>
    </section>
    <section class="stack">
      <article class="card">
        <h2>FAIR Signals</h2>
        <p class="muted">{explanations.get('fair_signals', 'Internal FAIR signals estimate release readiness from locally built ontology artifacts.')}</p>
        {_render_rows(release.get('fair_signals', []))}
      </article>
      <article class="card">
        <h2>Transparency Hooks</h2>
        <p class="muted">{explanations.get('transparency_hooks', 'External assessment hooks report what third-party services returned, or state clearly when they were unavailable.')}</p>
        {_render_rows(release.get('transparency_hooks', []))}
      </article>
      <article class="card">
        <h2>FOOPS! Assessment</h2>
        <p class="muted">FOOPS! is an external FAIR-oriented ontology validator. In file mode it does not run accessibility checks, so the Accessible dimension may appear as not assessed.</p>
        {_foops_details(release.get('foops', {}))}
      </article>
      <article class="card">
        <h2>OOPS! Pitfalls</h2>
        <p class="muted">OOPS! is an external ontology pitfall scanner. Service errors are shown as availability problems rather than as zero pitfalls.</p>
        {_oops_details(release.get('oops', {}))}
      </article>
      <article class="card">
        <h2>Validation Signals</h2>
        <p class="muted">{explanations.get('validation_signals', 'Validation signals summarize local structural and metadata checks against the release candidate ontology.')}</p>
        {_render_rows(release.get('validation_signals', []))}
      </article>
      <article class="card">
        <h2>Publication Assets</h2>
        <p class="muted">{explanations.get('publication_assets', 'Publication asset rows show whether files were generated in the current run rather than assuming they exist.')}</p>
        {_render_rows(release.get('publication_assets', []))}
      </article>
    </section>
    """


def _render_rows(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p>No data available.</p>"
    items = "".join(
        f"<li><strong>{item.get('label', 'Metric')}</strong> <span class='badge {item.get('status', 'watch')}'>{item.get('status', 'watch').upper()}</span> <span class='value'>{item.get('value', '')}</span><br><span class='muted'>{item.get('detail', '')}</span></li>"
        for item in rows
    )
    return f"<ul class='metric-list'>{items}</ul>"


def _foops_details(assessment: dict[str, Any]) -> str:
    dimensions = assessment.get("dimensions", {})
    rows = [
        {"label": "Status", "status": "good" if assessment.get("status") == "assessed" else "watch", "value": assessment.get("status", "unknown"), "detail": assessment.get("message", "")},
        {"label": "Overall score", "status": "good" if (assessment.get("overall_score") or 0) >= 70 else "watch" if assessment.get("overall_score") is not None else "watch", "value": f"{assessment.get('overall_score')} / 100" if assessment.get("overall_score") is not None else "not assessed", "detail": "Returned directly by the FOOPS! service."},
        {"label": "F / Findable", "status": "good" if dimensions.get("findable") is not None and dimensions.get("findable") >= 70 else "action" if dimensions.get("findable") is not None else "watch", "value": f"{dimensions.get('findable')} / 100" if dimensions.get("findable") is not None else "not assessed", "detail": "Returned directly by the FOOPS! service."},
        {"label": "A / Accessible", "status": "good" if dimensions.get("accessible") is not None and dimensions.get("accessible") >= 70 else "watch", "value": f"{dimensions.get('accessible')} / 100" if dimensions.get("accessible") is not None else "not assessed", "detail": "In file mode this dimension is commonly not assessed by FOOPS!."},
        {"label": "I / Interoperable", "status": "good" if dimensions.get("interoperable") is not None and dimensions.get("interoperable") >= 70 else "action" if dimensions.get("interoperable") is not None else "watch", "value": f"{dimensions.get('interoperable')} / 100" if dimensions.get("interoperable") is not None else "not assessed", "detail": "Returned directly by the FOOPS! service."},
        {"label": "R / Reusable", "status": "good" if dimensions.get("reusable") is not None and dimensions.get("reusable") >= 70 else "action" if dimensions.get("reusable") is not None else "watch", "value": f"{dimensions.get('reusable')} / 100" if dimensions.get("reusable") is not None else "not assessed", "detail": "Returned directly by the FOOPS! service."},
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
        {"label": "Status", "status": "good" if assessment.get("status") == "assessed" else "watch", "value": assessment.get("status", "unknown"), "detail": assessment.get("message", "")},
        {"label": "Pitfall count", "status": "good" if assessment.get("status") == "assessed" and assessment.get("pitfall_count", 0) == 0 else "watch" if assessment.get("status") == "assessed" else "watch", "value": str(assessment.get("pitfall_count", "not assessed")) if assessment.get("status") == "assessed" else "not assessed", "detail": "Returned directly by the OOPS! service when the scan succeeds."},
    ]
    for item in assessment.get("pitfalls", [])[:8]:
        code = item.get("code") or "Pitfall"
        name = item.get("name", "Unnamed pitfall")
        detail = item.get("description", "")
        rows.append({"label": code, "status": "action", "value": name, "detail": detail})
    return _render_rows(rows)


def _style_css() -> str:
    return """
:root {
  --bg: #f6f1e8;
  --panel: #fffaf3;
  --ink: #152025;
  --accent: #0f6d7a;
  --line: #d6c6ae;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: var(--ink);
  background:
    radial-gradient(circle at top left, rgba(200,106,43,0.12), transparent 30%),
    linear-gradient(180deg, #fffaf3 0%, #f6f1e8 100%);
}
.wrap { width: min(1120px, calc(100% - 2rem)); margin: 0 auto; }
.hero {
  padding: 3rem 0 2rem;
  border-bottom: 1px solid var(--line);
  background: linear-gradient(135deg, rgba(15,109,122,0.12), rgba(200,106,43,0.08));
}
.eyebrow { text-transform: uppercase; letter-spacing: 0.18em; font-size: 0.75rem; color: var(--accent); }
.subtitle { max-width: 60rem; font-size: 1.1rem; }
.nav { display: flex; flex-wrap: wrap; gap: 0.85rem; margin-top: 1rem; }
.nav a { color: var(--ink); text-decoration: none; padding: 0.45rem 0.8rem; border: 1px solid var(--line); border-radius: 999px; background: rgba(255,255,255,0.55); }
.content { padding: 2rem 0 4rem; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; }
.stack { display: grid; gap: 1rem; }
.card, .term-card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 1rem 1.1rem;
  box-shadow: 0 10px 30px rgba(0,0,0,0.05);
}
.list-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem; }
.prose { max-width: 70rem; line-height: 1.65; }
.stats { list-style: none; padding: 0; margin: 0; }
.stats li { padding: 0.25rem 0; }
.metric-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 0.8rem; }
.metric-list li { padding: 0.85rem 0; border-top: 1px solid rgba(21,32,37,0.08); }
.metric-list li:first-child { border-top: 0; padding-top: 0; }
.badge { display: inline-block; margin-left: 0.4rem; padding: 0.1rem 0.45rem; border-radius: 999px; font-size: 0.72rem; letter-spacing: 0.06em; }
.badge.good { background: rgba(44,138,72,0.12); color: #22663a; }
.badge.watch { background: rgba(198,130,36,0.14); color: #8b5f0a; }
.badge.action { background: rgba(176,51,51,0.12); color: #8a2323; }
.value { font-weight: 700; margin-left: 0.4rem; }
.muted { color: rgba(21,32,37,0.74); }
.iri { font-size: 0.86rem; color: var(--accent); word-break: break-word; }
code { background: rgba(15,109,122,0.08); padding: 0.1rem 0.35rem; border-radius: 4px; }
.footer { border-top: 1px solid var(--line); padding: 1.5rem 0 2rem; }
"""
