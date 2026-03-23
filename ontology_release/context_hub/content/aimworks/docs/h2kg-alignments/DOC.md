# H2KG Alignments

This entry explains the alignment policy for H2KG.

## Primary Alignment Stack

1. EMMO core
2. EMMO Electrochemistry or ECHO
3. QUDT
4. ChEBI
5. PROV-O and Dublin Core Terms

Optional sources may be used, but they must not block the release workflow.

## Alignment Rules

- keep local PEMFC catalyst-layer-specific terms in the `h2kg` namespace
- align generic scientific concepts to EMMO or ECHO
- align units and quantity kinds to QUDT
- align chemicals to ChEBI where identifiers are resolvable and relevant
- align provenance and release metadata to PROV-O and DCTERMS
- use OEO only as a fallback for broad energy terms

## Mapping Relation Policy

Prefer this order of confidence:

- `rdfs:subClassOf`
- `rdfs:subPropertyOf`
- `skos:exactMatch`
- `skos:closeMatch`
- `owl:equivalentClass` or `owl:equivalentProperty` only when very strong

## Conservative Defaults

Do not auto-delete local terms.

Do not assume a broad external term fully replaces a local application ontology term.

Do not map across incompatible kinds.

## H2KG Examples

- `Measurement` should usually stay local and be anchored by subclassing to an electrochemical measurement concept.
- `hasQuantityValue` should usually stay local while aligning as a subproperty to a QUDT quantity-value relation.
- `Agent` should stay local while being anchored to PROV-O `Agent`.

## Review Expectation

Every proposed mapping should have a rationale that explains:

- why the external target was chosen
- why the relation type is appropriate
- why the local term is preserved or not preserved
