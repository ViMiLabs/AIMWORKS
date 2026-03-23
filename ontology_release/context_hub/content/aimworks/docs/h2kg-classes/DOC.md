# H2KG Classes

This entry explains how to use the main H2KG classes and when they should remain local.

## Core Class Policy

- Preserve H2KG domain classes that capture PEMFC catalyst-layer-specific distinctions.
- Align generic scientific classes conservatively to EMMO or ECHO.
- Prefer `rdfs:subClassOf` over `owl:equivalentClass` unless the match is very strong.

## Important Classes

### Agent

Use for a responsible actor in an experimental or release context.

Keep local but anchor to PROV-O `Agent`.

Do not treat it as a general replacement for all organization or person ontologies.

### Process

Use for a local process concept in H2KG.

Anchor conservatively to an EMMO process concept.

Do not delete it automatically; keep it as the application-level class.

### Manufacturing

Use for catalyst-layer preparation or related manufacturing activities.

Treat as a local specialization of process.

### Measurement

Use for an experimental measurement activity in the PEMFC catalyst-layer domain.

Anchor it to EMMO Electrochemistry or ECHO using subclassing unless a stronger reviewed equivalence is justified.

### Instrument

Use for a device or apparatus involved in an experimental process or measurement.

Keep local if the application-level distinction matters.

### Matter

Use for local material entities relevant to catalyst-layer experiments.

Consider EMMO material alignment, but keep the local class if it organizes domain content well.

### Parameter

Use for controlled or reported experimental parameters.

Do not collapse it into raw data nodes.

### Property

Use for properties that are measured, estimated, or otherwise associated with materials or processes.

Prefer local organization with external semantic anchors rather than removing it.

### Data

Use for local data concepts that need to remain visible in the application ontology.

Treat as a local information or data specialization rather than broad external equivalence by default.

### DataPoint

Use sparingly and keep separate from the schema release if the nodes are example or data-like.

### Metadata

Use only where the local ontology genuinely needs a metadata concept.

Avoid mixing ontology release metadata with domain-instance metadata unless the distinction is explicit.

### NormalizationBasis

Use for stable named bases against which values are normalized.

This often belongs in the controlled vocabulary module rather than the core schema module.

## Class Review Rule

When reviewing a class, always ask:

1. Is this a schema concept or an example/data node?
2. Does this distinction matter specifically for PEMFC catalyst-layer modelling?
3. Should it remain local but aligned, or can it be reused directly from an external ontology?
