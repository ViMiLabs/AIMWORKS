# H2KG Properties

This entry explains how to use the main H2KG properties.

## Property Policy

- keep local application relations when they express H2KG-specific modelling choices
- align to external relations conservatively
- never map object properties to datatype properties
- never force literal metadata properties to behave like structural process relations

## Important Properties

### hasInputMaterial

Use when a process consumes or takes a material input.

Subject should be a process-like resource.

Object should be a material-like resource.

### hasOutputMaterial

Use when a process yields a material output.

Do not use this for informational outputs.

### hasInputData

Use when a process consumes data or a data artifact as an input.

Do not use this when the input is physically a material.

### hasOutputData

Use when a process produces data or a data artifact.

This is appropriate for generated measurement results or derived datasets.

### hasParameter

Use to associate a process or measurement with a parameter.

Do not use it for arbitrary descriptive literals.

### hasProperty

Use to associate a measurement with a property being reported or characterized.

### hasQuantityValue

Use to connect a property or similar resource to a quantity-value node.

This should align conservatively with QUDT quantity-value semantics.

### measures

Use when a measurement activity measures a property.

Keep the relation semantically clear: measurement activity to measured property.

### normalizedTo

Use when a value or result is normalized against a named basis.

### usesInstrument

Use when a process or measurement employs an instrument.

### referenceElectrode

Use only when the modelling context genuinely involves a reference electrode concept.

### hasIdentifier

Use for identifier-like literals.

Prefer alignment with DCTERMS identifier semantics.

### hasName

Use for human-readable names where a literal is intended.

Prefer alignment with established metadata vocabularies such as FOAF where suitable.

## Common Misuse

- using `hasOutputMaterial` for data
- using `hasOutputData` for materials
- attaching literal values through object properties
- using `hasParameter` where a dedicated metadata property would be clearer
- confusing the measured property with the quantity-value node
