# Publishing Notes

1. Fork `perma-id/w3id.org`.
2. Create the directory `h2kg/`.
3. Copy `h2kg/.htaccess` and `h2kg/README.md` from this output.
4. Open a PR describing the namespace and the long-term maintenance contact.

## Resolver targets

- Shared H2KG HTML target: `https://vimilabs.github.io/AIMWORKS/hydrogen-ontology.html`
- Shared H2KG Turtle target: `https://raw.githubusercontent.com/ViMiLabs/AIMWORKS/main/ontology_release/output/ontology/core_schema.ttl`
- Shared H2KG JSON-LD target: `https://raw.githubusercontent.com/ViMiLabs/AIMWORKS/main/ontology_release/output/ontology/core_schema.jsonld`
- PEMFC HTML target: `https://vimilabs.github.io/AIMWORKS/pemfc/hydrogen-ontology.html`
- PEMWE HTML target: `https://vimilabs.github.io/AIMWORKS/pemwe/hydrogen-ontology.html`

## Policy reminders

- Preserve existing hash IRIs under `https://w3id.org/h2kg/hydrogen-ontology#`.
- Do not switch to slash-term IRIs during the w3id registration step.
- Keep the active namespace strategy as `preserve_hash_namespace` until a reviewed migration plan exists.
