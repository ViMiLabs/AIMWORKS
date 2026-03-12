from __future__ import annotations

from pathlib import Path
from typing import Any

from .utils import write_text


def generate_w3id_artifacts(namespace_policy: dict[str, Any], release_profile: dict[str, Any], root: Path) -> None:
    output_dir = root / "output" / "w3id"
    public_base = namespace_policy["public_html_base"].rstrip("/")
    namespace_mode = namespace_policy["namespace_mode"]
    version = str(release_profile["release"]["version"])
    reference_page = release_profile["publication"]["reference_page"]
    docs_reference = f"{public_base}/{reference_page}"
    source_ttl = f"{public_base}/source/ontology.ttl"
    source_jsonld = f"{public_base}/source/ontology.jsonld"
    inferred_ttl = f"{public_base}/inferred/ontology.ttl"
    latest_ttl = f"{public_base}/latest/ontology.ttl"
    latest_jsonld = f"{public_base}/latest/ontology.jsonld"
    latest_context = f"{public_base}/latest/context.jsonld"
    version_ttl = f"{public_base}/{version}/ontology.ttl"
    version_jsonld = f"{public_base}/{version}/ontology.jsonld"
    version_inferred = f"{public_base}/{version}/inferred.ttl"
    version_context = f"{public_base}/{version}/context.jsonld"
    htaccess = f"""RewriteEngine On
AddType text/turtle .ttl
AddType application/ld+json .jsonld

RewriteCond %{{HTTP_ACCEPT}} text/html [OR]
RewriteCond %{{HTTP_ACCEPT}} application/xhtml\\+xml
RewriteRule ^$ {docs_reference} [R=303,L]

RewriteCond %{{HTTP_ACCEPT}} application/ld\\+json [OR]
RewriteCond %{{QUERY_STRING}} (^|&)format=jsonld(&|$)
RewriteRule ^$ {latest_jsonld} [R=303,L]

RewriteCond %{{HTTP_ACCEPT}} text/turtle [OR]
RewriteCond %{{QUERY_STRING}} (^|&)format=ttl(&|$)
RewriteRule ^$ {latest_ttl} [R=303,L]

RewriteCond %{{HTTP_ACCEPT}} application/ld\\+json [OR]
RewriteCond %{{QUERY_STRING}} (^|&)format=jsonld(&|$)
RewriteRule ^source/?$ {source_jsonld} [R=303,L]

RewriteRule ^source/?$ {source_ttl} [R=303,L]
RewriteRule ^inferred/?$ {inferred_ttl} [R=303,L]

RewriteCond %{{HTTP_ACCEPT}} application/ld\\+json [OR]
RewriteCond %{{QUERY_STRING}} (^|&)format=jsonld(&|$)
RewriteRule ^latest/?$ {latest_jsonld} [R=303,L]

RewriteRule ^latest/?$ {latest_ttl} [R=303,L]
RewriteRule ^latest/inferred/?$ {public_base}/latest/inferred.ttl [R=303,L]
RewriteRule ^context/?$ {latest_context} [R=303,L]

RewriteCond %{{HTTP_ACCEPT}} text/html [OR]
RewriteCond %{{HTTP_ACCEPT}} application/xhtml\\+xml
RewriteRule ^([0-9]{{4}}\\.[0-9]+\\.[0-9]+)/?$ {docs_reference} [R=303,L]

RewriteCond %{{HTTP_ACCEPT}} application/ld\\+json [OR]
RewriteCond %{{QUERY_STRING}} (^|&)format=jsonld(&|$)
RewriteRule ^([0-9]{{4}}\\.[0-9]+\\.[0-9]+)/?$ {public_base}/$1/ontology.jsonld [R=303,L]

RewriteRule ^([0-9]{{4}}\\.[0-9]+\\.[0-9]+)/?$ {public_base}/$1/ontology.ttl [R=303,L]
RewriteRule ^([0-9]{{4}}\\.[0-9]+\\.[0-9]+)/inferred/?$ {public_base}/$1/inferred.ttl [R=303,L]
RewriteRule ^([0-9]{{4}}\\.[0-9]+\\.[0-9]+)/context/?$ {public_base}/$1/context.jsonld [R=303,L]

RewriteRule ^$ {latest_ttl} [R=303,L]
"""
    readme = f"""# w3id Publication Support

Active recipe: **{namespace_mode} namespace**

- Public ontology IRI: `{namespace_policy['ontology_iri']}`
- Preferred namespace URI: `{namespace_policy['preferred_namespace_uri']}`
- HTML reference page target: `{docs_reference}`
- Asserted source target: `{source_ttl}`
- Inferred target: `{inferred_ttl}`
- Latest target: `{latest_ttl}`
- Latest JSON-LD target: `{latest_jsonld}`
- Context target: `{latest_context}`
- Versioned asserted target: `{version_ttl}`
- Versioned inferred target: `{version_inferred}`

This template preserves the current hash-style publication policy by default while exposing ECHO-style source endpoints such as `/source`, `/inferred`, `/latest`, `/context`, and versioned release paths.
"""
    curl_tests = f"""#!/usr/bin/env bash
set -eu

curl -I -H 'Accept: text/html' '{namespace_policy['ontology_iri']}'
curl -I -H 'Accept: text/turtle' '{namespace_policy['ontology_iri']}'
curl -I -H 'Accept: application/ld+json' '{namespace_policy['ontology_iri']}'
curl -I '{namespace_policy['ontology_iri']}/source'
curl -I '{namespace_policy['ontology_iri']}/inferred'
curl -I '{namespace_policy['ontology_iri']}/latest'
curl -I '{namespace_policy['ontology_iri']}/context'
curl -I '{namespace_policy['ontology_iri']}/{version}'
curl -I '{namespace_policy['ontology_iri']}/{version}/inferred'
"""
    notes = f"""# Publishing Notes

1. Keep the ontology IRI stable at `{namespace_policy['ontology_iri']}`.
2. Deploy `output/publication/` as the public static root. The publication layout now includes `source/`, `inferred/`, `latest/`, `context/`, and `{version}/`.
3. Register the generated `.htaccess` rules with the w3id maintainers or mirror them into the existing namespace configuration.
4. Ensure that:
   - `{docs_reference}` resolves to the single-page ontology reference.
   - `{source_ttl}` resolves to the asserted source ontology.
   - `{inferred_ttl}` resolves to the inferred ontology.
   - `{latest_ttl}` resolves to the latest asserted release.
   - `{version_ttl}` resolves to the version-pinned asserted release.
5. If namespace migration is enabled later, also publish the generated migration map and add redirects for legacy hash IRIs.

The current default remains hash-based because the existing ontology already uses stable hash IRIs and preserving them is the safest backward-compatible first release.
"""
    write_text(output_dir / ".htaccess", htaccess)
    write_text(output_dir / "README.md", readme)
    write_text(output_dir / "curl_tests.sh", curl_tests)
    write_text(output_dir / "publishing_notes.md", notes)
