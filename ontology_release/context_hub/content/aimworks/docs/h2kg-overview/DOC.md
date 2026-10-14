# H2KG Overview

H2KG is a domain-expert-reviewed ontology for hydrogen electrochemical systems, FAIR workflow representation, and external semantic alignment. It reuses selected concepts from HDO, EMMO, QUDT, ChEBI, PROV-O, and DCTERMS while preserving its hydrogen-domain scope.

## In Scope

- PEMFC cathode catalyst-layer experiments
- catalyst-layer materials and formulations
- manufacturing and preparation steps
- electrochemical and transport measurements
- parameters, properties, and quantity values
- provenance and release metadata

## Out Of Scope

- a broad hydrogen economy ontology
- a general PEMWE ontology
- a replacement for core EMMO
- a generic energy ontology
- a repository for all experimental data as if it were schema

## Positioning

H2KG should be positioned as the H2KG PEMFC Catalyst Layer Application Ontology.

It should remain under the `h2kg` namespace by default.

## External Semantic Anchors

- EMMO core for general scientific and process semantics
- EMMO Electrochemistry or ECHO for electrochemical measurement context
- QUDT for units and quantity kinds
- ChEBI for chemical entities when resolvable and appropriate
- PROV-O and Dublin Core Terms for provenance and ontology metadata

## Default Local Policy

Keep PEMFC catalyst-layer-specific concepts local in the `h2kg` namespace unless there is a reviewed reason to migrate or replace them.

Do not delete local terms automatically simply because an external term exists.

## Release Principle

The first release should be conservative:

- preserve existing ontology IRI
- preserve existing hash-style term IRIs
- improve metadata and annotations
- separate schema from example or data-like content
- add mappings without silently breaking compatibility
