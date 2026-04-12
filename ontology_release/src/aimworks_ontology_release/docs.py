from __future__ import annotations

import os
import shutil
from html import escape
from pathlib import Path
from typing import Any

from .classify import classify_resources
from .hdo import load_hdo_alignment_report
from .io import load_json_document, merge_document_items
from .mapper import propose_mappings
from .normalize import best_description, best_label
from .odk import load_odk_manifest
from .utils import (
    default_release_profile,
    dump_json,
    ensure_dir,
    html_paragraphs,
    load_json,
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
    ensure_dir(output_dir / "pemfc")
    ensure_dir(output_dir / "pemwe")
    write_text(output_dir / ".nojekyll", "")
    profile = try_load_yaml(Path(config_dir or Path(input_path).parent.parent / "config") / "release_profile.yaml", default_release_profile())
    project = profile["project"]
    items = {item["@id"]: item for item in merge_document_items(load_json_document(input_path)) if isinstance(item.get("@id"), str)}
    classes, properties, examples = _term_views(input_path, output_dir.parent / "review", config_dir, items)
    mappings = propose_mappings(input_path, output_dir.parent / "review", config_dir)
    mapping_summary = _load_alignment_summary(output_dir.parent / "reports")
    summary = {
        "schema_count": len(classes) + len(properties),
        "vocabulary_count": sum(1 for item in examples if "basis" in item["label"].lower() or "type" in item["label"].lower()),
        "example_count": len(examples),
        "mapping_count": len(mappings),
    }
    release = _release_snapshot_for_docs(output_dir, fair_snapshot)
    odk = load_odk_manifest(output_dir.parent)
    hdo = load_hdo_alignment_report(output_dir.parent / "reports")

    page_specs: list[tuple[Path, str, str]] = [
        (output_dir / "pages" / "user-guide.html", "User Guide", _user_guide_body()),
        (output_dir / "pages" / "ontology-overview.html", "Ontology Overview", _overview_body(project, summary, odk, hdo)),
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
        (output_dir / "pemfc" / "hydrogen-ontology.html", "PEMFC Reference", _reference_body(project, "pemfc", odk, hdo, output_dir / "pemfc" / "hydrogen-ontology.html", output_dir)),
        (output_dir / "pemwe" / "index.html", "PEMWE Profile", _profile_home_body(project, "pemwe", odk, hdo, output_dir / "pemwe" / "index.html", output_dir)),
        (output_dir / "pemwe" / "hydrogen-ontology.html", "PEMWE Reference", _reference_body(project, "pemwe", odk, hdo, output_dir / "pemwe" / "hydrogen-ontology.html", output_dir)),
    ]
    for path, title, body in page_specs:
        write_text(path, _page_template(project, title, body, path, output_dir))

    write_text(output_dir / "index.html", _legacy_profile_home())
    _copy_site_assets(output_dir, project)
    write_text(output_dir / "assets" / "style.css", _style_css())
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


def _page_template(project: dict[str, Any], page_title: str, body: str, page_path: Path, docs_root: Path) -> str:
    home_link = _relative_href(page_path, docs_root / "index.html")
    css_href = _relative_href(page_path, docs_root / "assets" / "style.css")
    asset_base = _relative_href(page_path, docs_root / "assets")
    hero_brand = _hero_brand(project, asset_base)
    nav = f"""
    <nav class="nav">
      <a href="{home_link}">Home</a>
      <a href="{_relative_href(page_path, docs_root / 'pages' / 'user-guide.html')}">User Guide</a>
      <a href="{_relative_href(page_path, docs_root / 'pages' / 'ontology-overview.html')}">Overview</a>
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
        </div>
      </article>
      <article class="card">
        <h2>PEMWE Profile</h2>
        <p>Profile documentation for proton exchange membrane water electrolysis experiments, materials, processes, measurements, and data assets.</p>
        <p><strong>Ontology IRI:</strong> <code>https://w3id.org/h2kg/pemwe/hydrogen-ontology</code></p>
        <div class="links">
          <a href="./pemwe/index.html">Open profile home</a>
          <a class="ghost" href="./pemwe/hydrogen-ontology.html">Open reference</a>
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


def _release_body(release: dict[str, Any], odk: dict[str, Any], hdo: dict[str, Any], page_path: Path, docs_root: Path) -> str:
    artifacts = "".join(f"<li>{escape(str(item))}</li>" for item in release.get("artifacts", []))
    odk_base = _relative_href(page_path, docs_root.parent / "odk")
    odk_artifacts = _odk_artifact_cards(odk, odk_base)
    gates = _render_rows(odk.get("promotion_gates", []))
    parity = odk.get("parity", {})
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
        <ul>{artifacts}</ul>
      </article>
    </section>
    <section class="stack">
      <article class="card">
        <h2>ODK Release Artefacts</h2>
        <p class="muted">ODK remains in shadow mode. These machine artefacts are generated in parallel for comparison, QC, and downstream tooling.</p>
        {odk_artifacts}
      </article>
      <article class="card">
        <h2>Shadow Mode Status</h2>
        <ul class="stats">
          <li><strong>Current authority:</strong> {escape(str(odk.get('authority', 'AIMWORKS pipeline')))}</li>
          <li><strong>ODK status:</strong> {escape(str(odk.get('mode', 'shadow')))}</li>
          <li><strong>Reasoner:</strong> {escape(str(odk.get('reasoner', 'ELK')))}</li>
          <li><strong>ODK version:</strong> {escape(str(odk.get('odk_version', 'shadow scaffold')))}</li>
          <li><strong>Parity:</strong> {escape(str(parity.get('status', 'under review')))}</li>
        </ul>
        <p>{escape(str(parity.get('message', 'ODK parity has not yet been reviewed.')))}</p>
        {gates}
      </article>
      <article class="card">
        <h2>ODK and HDO Integration</h2>
        <ul class="stats">
          <li><strong>HDO import status:</strong> {_hdo_import_status(odk)}</li>
          <li><strong>Last refresh:</strong> {_hdo_import_refresh(odk)}</li>
          <li><strong>Included in current shadow build:</strong> {_hdo_import_included(odk)}</li>
          <li><strong>HDO-reviewed local terms:</strong> {hdo.get('summary', {}).get('reviewed_against_hdo', 0)}</li>
          <li><strong>Aligned to HDO:</strong> {hdo.get('summary', {}).get('aligned_to_hdo', 0)}</li>
        </ul>
        <p>HDO is the primary shadow-mode alignment source for data, metadata, digital-object, information-profile, identifier, schema, and validation concepts in H2KG.</p>
        <p class="muted">{escape(str(hdo.get('cache_note', '')))}</p>
      </article>
    </section>
    """


def _quality_body(release: dict[str, Any], odk: dict[str, Any], hdo: dict[str, Any]) -> str:
    explanations = release.get("section_explanations", {})
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
            "status": "watch" if hdo.get("summary", {}).get("stayed_local", 0) > 0 else "good",
            "value": str(hdo.get("summary", {}).get("stayed_local", 0)),
            "detail": "Reviewed terms intentionally kept local until direct HDO reuse is accepted or a more precise HDO target is loaded.",
        },
    ]
    return f"""
    <section class="prose">
      <p>{escape(str(release.get('summary', 'No quality summary available.')))}</p>
    </section>
    <section class="stack">
      <article class="card">
        <h2>FAIR Signals</h2>
        <p class="muted">{escape(str(explanations.get('fair_signals', 'Internal FAIR signals estimate release readiness from locally built ontology artifacts.')))}</p>
        {_render_rows(release.get('fair_signals', []))}
      </article>
      <article class="card">
        <h2>Transparency Hooks</h2>
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
        <p class="muted">{escape(str(explanations.get('validation_signals', 'Validation signals summarize local structural and metadata checks against the release candidate ontology.')))}</p>
        {_render_rows(release.get('validation_signals', []))}
      </article>
      <article class="card">
        <h2>Publication Assets</h2>
        <p class="muted">{escape(str(explanations.get('publication_assets', 'Publication asset rows show whether files were generated in the current run rather than assuming they exist.')))}</p>
        {_render_rows(release.get('publication_assets', []))}
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


def _release_snapshot_for_docs(output_dir: Path, fair_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    release = dict(
        fair_snapshot
        or {
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
            asset["value"] = "ready"
            asset["status"] = "good"
        elif asset.get("label") == "Release bundle" and (output_dir.parent / "release_bundle" / "RELEASE_NOTES.md").exists():
            asset["value"] = "ready"
            asset["status"] = "good"
    release["publication_assets"] = publication_assets
    return release


def _render_rows(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p>No data available.</p>"
    items = "".join(
        f"<li><strong>{escape(str(item.get('label', 'Metric')))}</strong> <span class='badge {escape(str(item.get('status', 'watch')))}'>{escape(str(item.get('status', 'watch')).upper())}</span> <span class='value'>{escape(str(item.get('value', '')))}</span><br><span class='muted'>{escape(str(item.get('detail', '')))}</span></li>"
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
  width: 152px;
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
  .hero-brand img { width: 118px; }
  h1 { max-width: 13ch; }
}
"""
