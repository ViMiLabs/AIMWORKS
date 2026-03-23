from __future__ import annotations

from pathlib import Path
from typing import Any

from .utils import default_namespace_policy, default_release_profile, ensure_dir, try_load_yaml, write_text


def generate_w3id_artifacts(
    output_dir: str | Path,
    config_dir: str | Path | None = None,
) -> dict[str, Any]:
    output_dir = ensure_dir(Path(output_dir))
    config_root = Path(config_dir or Path(output_dir).parent.parent / "config")
    policy = try_load_yaml(config_root / "namespace_policy.yaml", default_namespace_policy())["policy"]
    profile = try_load_yaml(config_root / "release_profile.yaml", default_release_profile())["project"]
    strategy = policy["active_strategy"]
    html_base = policy["publication_base_html"].rstrip("/") + "/"
    rdf_base = policy["publication_base_rdf"].rstrip("/") + "/"
    htaccess = f"""Options +FollowSymLinks
RewriteEngine On

RewriteCond %{{HTTP_ACCEPT}} text/html [OR]
RewriteCond %{{HTTP_ACCEPT}} application/xhtml\\+xml
RewriteRule ^$ {html_base}index.html [R=302,L]

RewriteCond %{{HTTP_ACCEPT}} text/turtle
RewriteRule ^$ {rdf_base}schema.ttl [R=302,L]

RewriteCond %{{HTTP_ACCEPT}} application/ld\\+json
RewriteRule ^$ {rdf_base}schema.jsonld [R=302,L]

RewriteRule ^$ {html_base}index.html [R=302,L]
"""
    write_text(output_dir / ".htaccess", htaccess)
    write_text(output_dir / "README.md", _w3id_readme(strategy, profile))
    write_text(output_dir / "publishing_notes.md", _publishing_notes(strategy, profile))
    write_text(output_dir / "curl_tests.sh", _curl_tests(profile))
    return {"strategy": strategy, "html_base": html_base, "rdf_base": rdf_base}


def _w3id_readme(strategy: str, profile: dict[str, Any]) -> str:
    return f"""# w3id Redirect Template

Active recipe: `{strategy}`.

This release preserves the current ontology IRI and hash-style term IRIs by default:

- Ontology IRI: `{profile['ontology_iri']}`
- Namespace URI: `{profile['namespace_uri']}`
- Version IRI: `{profile['version_iri']}`

Use `.htaccess` as the starting point for w3id registration. It prefers HTML for browsers and serves Turtle or JSON-LD for RDF-aware clients.
"""


def _publishing_notes(strategy: str, profile: dict[str, Any]) -> str:
    return f"""# Publishing Notes

1. Register or update the w3id entry for `{profile['ontology_iri']}`.
2. Point HTML requests to the GitHub Pages documentation site.
3. Point RDF requests to the raw ontology artifacts in the repository.
4. Keep the active namespace strategy as `{strategy}` until a reviewed migration plan exists.
5. If a future slash namespace is adopted, generate alias maps and redirects before switching publication policy.
"""


def _curl_tests(profile: dict[str, Any]) -> str:
    iri = profile["ontology_iri"]
    return f"""#!/usr/bin/env sh
set -eu

curl -I -H "Accept: text/html" {iri}
curl -I -H "Accept: text/turtle" {iri}
curl -I -H "Accept: application/ld+json" {iri}
"""
