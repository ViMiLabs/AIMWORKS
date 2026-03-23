# H2KG IRI Policy

This entry explains how stable identifiers are handled for H2KG.

## Current Default

The ontology IRI remains:

- `https://w3id.org/h2kg/hydrogen-ontology`

The default namespace remains:

- `https://w3id.org/h2kg/hydrogen-ontology#`

## Backward Compatibility Rule

Preserve the current ontology IRI and current term IRIs by default.

Do not silently break existing identifiers.

## Hash Namespace Default

The current release should preserve the existing hash-style namespace because:

- the explicit schema is still relatively small
- the current ontology already uses these IRIs
- preserving them is safer for first public release preparation

## Future Migration Rule

The release tooling may support a future slash namespace, but migration must be explicit and reviewed.

If migration is enabled, maintainers must generate:

- alias or migration maps
- redirect templates
- publication notes
- clear release communication

## Versioning Rule

Every release should declare:

- a stable ontology IRI
- a version IRI
- version information
- prior version metadata where relevant

## Publication Rule

w3id redirect artifacts must distinguish:

- HTML documentation requests
- RDF requests for Turtle or JSON-LD

The active publication recipe should be documented in release outputs.
