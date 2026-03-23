# Mapping Rules

Use these mapping rules when reviewing alignments:

- never map class to property
- never map datatype property to object property
- prefer subclassing when the local term is narrower or more application-specific
- prefer SKOS mapping when the relationship is useful but not ontologically strict
- only use equivalence when labels, semantics, and intended usage are strongly aligned

Preferred external reuse:

- EMMO or ECHO for process, material, property, and measurement anchors
- QUDT for units, quantity kinds, and quantity-value structure
- ChEBI for chemicals
- PROV-O and DCTERMS for provenance and metadata
