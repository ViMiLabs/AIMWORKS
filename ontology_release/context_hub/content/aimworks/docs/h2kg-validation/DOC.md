# H2KG Validation

This entry explains what makes the ontology release-ready from a validation perspective.

## Required Ontology Header Metadata

The ontology header should include:

- title
- description or abstract
- creator
- contributor
- created and modified dates
- license
- version IRI
- version information
- preferred namespace prefix and URI

## Required Schema Annotations

Local schema terms should have:

- `rdfs:label`
- `skos:definition` or a well-justified equivalent description
- `rdfs:comment` when helpful
- `rdfs:isDefinedBy` pointing to the ontology

## Structural Checks

Release validation should check:

- RDF serialization sanity
- duplicate resource identifiers
- namespace policy compliance
- split between schema and example/data-like content
- mapping relation sanity
- import references

## SHACL Expectations

Use local SHACL shapes to validate:

- ontology header completeness
- schema annotation completeness
- basic release policy constraints

## Common Failures

- missing labels or definitions on schema terms
- treating quantity-value nodes as schema
- publishing example resources as core ontology classes
- missing version metadata
- using overly strong equivalence mappings without justification
