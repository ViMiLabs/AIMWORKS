from __future__ import annotations

from pathlib import Path
from typing import Any

from .utils import default_namespace_policy, default_release_profile, ensure_dir, try_load_yaml, write_text


def generate_w3id_artifacts(
    output_dir: str | Path,
    config_dir: str | Path | None = None,
) -> dict[str, Any]:
    output_dir = ensure_dir(Path(output_dir))
    w3id_root = ensure_dir(output_dir / "h2kg")
    config_root = Path(config_dir or output_dir.parent.parent / "config")
    policy = try_load_yaml(config_root / "namespace_policy.yaml", default_namespace_policy())["policy"]
    profile = try_load_yaml(config_root / "release_profile.yaml", default_release_profile())["project"]
    strategy = policy["active_strategy"]
    html_base = policy["publication_base_html"].rstrip("/") + "/"
    rdf_base = policy["publication_base_rdf"].rstrip("/") + "/"

    html_targets = {
        "root": f"{html_base}index.html",
        "core": f"{html_base}hydrogen-ontology.html",
        "pemfc": f"{html_base}pemfc/hydrogen-ontology.html",
        "pemwe": f"{html_base}pemwe/hydrogen-ontology.html",
    }
    rdf_targets = {
        "core_ttl": f"{rdf_base}core_schema.ttl",
        "core_jsonld": f"{rdf_base}core_schema.jsonld",
        "pemfc_ttl": f"{rdf_base}pemfc_schema.ttl",
        "pemfc_jsonld": f"{rdf_base}pemfc_schema.jsonld",
        "pemwe_ttl": f"{rdf_base}pemwe_schema.ttl",
        "pemwe_jsonld": f"{rdf_base}pemwe_schema.jsonld",
    }

    htaccess = _htaccess(html_targets, rdf_targets)
    readme = _w3id_readme(strategy, profile, html_targets, rdf_targets)

    # Root-level helper files remain useful for FAIR checks and local review,
    # while the nested h2kg directory mirrors the actual structure expected by
    # a future PR to perma-id/w3id.org.
    write_text(output_dir / ".htaccess", htaccess)
    write_text(output_dir / "README.md", _root_readme())
    write_text(output_dir / "publishing_notes.md", _publishing_notes(strategy, profile, html_targets, rdf_targets))
    write_text(output_dir / "curl_tests.sh", _curl_tests())

    write_text(w3id_root / ".htaccess", htaccess)
    write_text(w3id_root / "README.md", readme)

    return {
        "strategy": strategy,
        "html_base": html_base,
        "rdf_base": rdf_base,
        "w3id_directory": "h2kg",
        "html_targets": html_targets,
        "rdf_targets": rdf_targets,
    }


def _htaccess(html_targets: dict[str, str], rdf_targets: dict[str, str]) -> str:
    return f"""Options +FollowSymLinks
RewriteEngine On

# Project home under /h2kg/
RewriteRule ^$ {html_targets['root']} [R=302,L]

# Core H2KG namespace document
RewriteCond %{{HTTP_ACCEPT}} text/turtle [OR]
RewriteCond %{{HTTP_ACCEPT}} application/x-turtle
RewriteRule ^hydrogen-ontology$ {rdf_targets['core_ttl']} [R=302,L]

RewriteCond %{{HTTP_ACCEPT}} application/ld\\+json [OR]
RewriteCond %{{HTTP_ACCEPT}} application/json
RewriteRule ^hydrogen-ontology$ {rdf_targets['core_jsonld']} [R=302,L]

RewriteCond %{{HTTP_ACCEPT}} text/html [OR]
RewriteCond %{{HTTP_ACCEPT}} application/xhtml\\+xml
RewriteRule ^hydrogen-ontology$ {html_targets['core']} [R=302,L]

RewriteRule ^hydrogen-ontology$ {html_targets['core']} [R=302,L]

# PEMFC profile namespace document
RewriteCond %{{HTTP_ACCEPT}} text/turtle [OR]
RewriteCond %{{HTTP_ACCEPT}} application/x-turtle
RewriteRule ^pemfc/hydrogen-ontology$ {rdf_targets['pemfc_ttl']} [R=302,L]

RewriteCond %{{HTTP_ACCEPT}} application/ld\\+json [OR]
RewriteCond %{{HTTP_ACCEPT}} application/json
RewriteRule ^pemfc/hydrogen-ontology$ {rdf_targets['pemfc_jsonld']} [R=302,L]

RewriteCond %{{HTTP_ACCEPT}} text/html [OR]
RewriteCond %{{HTTP_ACCEPT}} application/xhtml\\+xml
RewriteRule ^pemfc/hydrogen-ontology$ {html_targets['pemfc']} [R=302,L]

RewriteRule ^pemfc/hydrogen-ontology$ {html_targets['pemfc']} [R=302,L]

# PEMWE profile namespace document
RewriteCond %{{HTTP_ACCEPT}} text/turtle [OR]
RewriteCond %{{HTTP_ACCEPT}} application/x-turtle
RewriteRule ^pemwe/hydrogen-ontology$ {rdf_targets['pemwe_ttl']} [R=302,L]

RewriteCond %{{HTTP_ACCEPT}} application/ld\\+json [OR]
RewriteCond %{{HTTP_ACCEPT}} application/json
RewriteRule ^pemwe/hydrogen-ontology$ {rdf_targets['pemwe_jsonld']} [R=302,L]

RewriteCond %{{HTTP_ACCEPT}} text/html [OR]
RewriteCond %{{HTTP_ACCEPT}} application/xhtml\\+xml
RewriteRule ^pemwe/hydrogen-ontology$ {html_targets['pemwe']} [R=302,L]

RewriteRule ^pemwe/hydrogen-ontology$ {html_targets['pemwe']} [R=302,L]
"""


def _root_readme() -> str:
    return """# Local w3id Review Output

This directory contains locally generated materials for a future `perma-id/w3id.org`
pull request.

The actual submission structure should use the nested `h2kg/` directory:

- `h2kg/.htaccess`
- `h2kg/README.md`

The root-level files are kept as local helpers and for FAIR readiness checks.
"""


def _w3id_readme(strategy: str, profile: dict[str, Any], html_targets: dict[str, str], rdf_targets: dict[str, str]) -> str:
    return f"""# H2KG w3id Redirect Configuration

Project: `{profile['title']}`

This directory is intended for a future pull request to `perma-id/w3id.org` to
register the `https://w3id.org/h2kg/` namespace.

## Namespace policy

- Active strategy: `{strategy}`
- Main ontology IRI: `{profile['ontology_iri']}`
- Main namespace URI: `{profile['namespace_uri']}`
- Existing term IRIs are preserved

## Redirect targets

### Shared H2KG namespace

- Browser / HTML: `{html_targets['core']}`
- Turtle: `{rdf_targets['core_ttl']}`
- JSON-LD: `{rdf_targets['core_jsonld']}`

### PEMFC profile namespace

- Browser / HTML: `{html_targets['pemfc']}`
- Turtle: `{rdf_targets['pemfc_ttl']}`
- JSON-LD: `{rdf_targets['pemfc_jsonld']}`

### PEMWE profile namespace

- Browser / HTML: `{html_targets['pemwe']}`
- Turtle: `{rdf_targets['pemwe_ttl']}`
- JSON-LD: `{rdf_targets['pemwe_jsonld']}`

## Contact and maintenance

- Repository: `{profile['repository_url']}`
- Docs base: `{profile['docs_url']}`
- Maintainers: AIMWORKS / ViMiLabs

## Notes

Hash IRIs such as `https://w3id.org/h2kg/hydrogen-ontology#FixedBedReactor`
resolve through the namespace document `https://w3id.org/h2kg/hydrogen-ontology`.
The target HTML page therefore needs exact term-fragment anchors, which the
current documentation build provides.
"""


def _publishing_notes(
    strategy: str,
    profile: dict[str, Any],
    html_targets: dict[str, str],
    rdf_targets: dict[str, str],
) -> str:
    return f"""# Publishing Notes

1. Fork `perma-id/w3id.org`.
2. Create the directory `h2kg/`.
3. Copy `h2kg/.htaccess` and `h2kg/README.md` from this output.
4. Open a PR describing the namespace and the long-term maintenance contact.

## Resolver targets

- Shared H2KG HTML target: `{html_targets['core']}`
- Shared H2KG Turtle target: `{rdf_targets['core_ttl']}`
- Shared H2KG JSON-LD target: `{rdf_targets['core_jsonld']}`
- PEMFC HTML target: `{html_targets['pemfc']}`
- PEMWE HTML target: `{html_targets['pemwe']}`

## Policy reminders

- Preserve existing hash IRIs under `{profile['namespace_uri']}`.
- Do not switch to slash-term IRIs during the w3id registration step.
- Keep the active namespace strategy as `{strategy}` until a reviewed migration plan exists.
"""


def _curl_tests() -> str:
    return """#!/usr/bin/env sh
set -eu

curl -I -H "Accept: text/html" https://w3id.org/h2kg/hydrogen-ontology
curl -I -H "Accept: text/turtle" https://w3id.org/h2kg/hydrogen-ontology
curl -I -H "Accept: application/ld+json" https://w3id.org/h2kg/hydrogen-ontology

curl -I -H "Accept: text/html" https://w3id.org/h2kg/pemfc/hydrogen-ontology
curl -I -H "Accept: text/turtle" https://w3id.org/h2kg/pemfc/hydrogen-ontology

curl -I -H "Accept: text/html" https://w3id.org/h2kg/pemwe/hydrogen-ontology
curl -I -H "Accept: text/turtle" https://w3id.org/h2kg/pemwe/hydrogen-ontology
"""
