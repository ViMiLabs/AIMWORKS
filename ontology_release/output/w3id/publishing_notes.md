# Resolver and Publishing Notes

The H2KG namespace is already established. This generated configuration adds a
reusable semantic-version route while preserving every existing ontology and
term IRI. Activating the updated route requires updating the existing H2KG
resolver configuration, not registering a new namespace.
This route update does not require a new W3ID registration.

## Resolver targets

- Shared H2KG HTML target: `https://vimilabs.github.io/AIMWORKS/hydrogen-ontology.html`
- Shared H2KG Turtle target: `https://raw.githubusercontent.com/ViMiLabs/AIMWORKS/main/ontology_release/output/ontology/core_schema.ttl`
- Shared H2KG JSON-LD target: `https://raw.githubusercontent.com/ViMiLabs/AIMWORKS/main/ontology_release/output/ontology/core_schema.jsonld`
- PEMFC HTML target: `https://vimilabs.github.io/AIMWORKS/pemfc/hydrogen-ontology.html`
- PEMWE HTML target: `https://vimilabs.github.io/AIMWORKS/pemwe/hydrogen-ontology.html`
- H2KG v2 taxonomy target: `https://raw.githubusercontent.com/ViMiLabs/AIMWORKS/main/ontology_release/output/ontology/h2kg-v2-taxonomy.ttl`
- Immutable version target pattern: `https://raw.githubusercontent.com/ViMiLabs/AIMWORKS/vX.Y.Z/ontology_release/output/ontology/`

## Policy reminders

- Preserve existing hash IRIs under `https://w3id.org/h2kg/hydrogen-ontology#`.
- Do not switch to slash-term IRIs during release publication.
- Keep the active namespace strategy as `preserve_hash_namespace` until a reviewed migration plan exists.
- Publish external bridge artifacts through GitHub Pages and retain original
  external ontology IRIs as mapping targets.
