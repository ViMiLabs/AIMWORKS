# H2KG Ontology Model

H2KG contains several different kinds of resources that should not all be published in the same way.

## Main Layers

### Ontology Header

This is the release metadata layer for the ontology itself. It should include:

- title
- description or abstract
- creator and contributor metadata
- license
- version IRI and version information
- preferred namespace metadata

### Schema Or TBox

This is the core ontology structure:

- classes
- object properties
- datatype properties
- annotation properties
- subclass and subproperty structure

This is the authoritative release module.

### Controlled Vocabulary

These are curated named terms that act as stable domain reference values and should not be confused with general instance data.

Typical examples include:

- normalization bases
- named design or reference categories
- stable reference terms used repeatedly across experiments

### Example Or Data-Like Content

These are not core schema and should be split from the main ontology release:

- measurement instances
- quantity-value nodes
- generated identifiers
- example resources used to illustrate patterns
- data-centric nodes from extraction pipelines

## Release Separation Rule

Publish these as separate outputs:

- schema ontology
- controlled vocabulary module
- examples module

Do not present quantity-value nodes or generated resources as if they were core schema.

## Why The Split Matters

Without separation, the ontology looks larger and more schema-rich than it really is, and FAIR release quality suffers because example data is mixed with the TBox.

## H2KG-Specific Interpretation

The current ontology is best understood as a relatively small application schema over a much larger set of experimental and quantity-value resources.

That means the release pipeline should treat the small explicit schema as the primary ontology and treat most operational resources as example or data-like content.
