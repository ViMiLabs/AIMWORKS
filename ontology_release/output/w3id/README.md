# w3id Redirect Template

Active recipe: `preserve_hash_namespace`.

This release preserves the current ontology IRI and hash-style term IRIs by default:

- Ontology IRI: `https://w3id.org/h2kg/hydrogen-ontology`
- Namespace URI: `https://w3id.org/h2kg/hydrogen-ontology#`
- Version IRI: `https://w3id.org/h2kg/hydrogen-ontology/releases/1.0.0`

Use `.htaccess` as the starting point for w3id registration. It prefers HTML for browsers and serves Turtle or JSON-LD for RDF-aware clients.
