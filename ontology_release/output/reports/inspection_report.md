# Inspection Report

Generated on 2026-04-09.

## Ontology Summary

- Ontology IRI: `https://w3id.org/h2kg/hydrogen-ontology`
- Raw JSON-LD nodes: 3300
- Merged node count: 3289
- Local `h2kg` nodes: 2164
- Explicit classes: 14
- Explicit object properties: 27
- Explicit datatype properties: 2
- QUDT quantity value nodes: 1119

## Schema Annotation Coverage

- Schema terms inspected: 43
- With labels: 23
- With comments: 0
- With definitions: 0

## Imported Ontologies

- `http://purl.org/holy/ns#`
- `https://w3id.org/emmo`
- `https://w3id.org/emmo/domain/characterisation-methodology/chameo#`
- `https://w3id.org/emmo/domain/coating#`
- `https://w3id.org/emmo/domain/electrochemistry`
- `https://w3id.org/emmo/domain/equivalent-circuit-model#`
- `https://w3id.org/emmo/domain/manufacturing#`
- `https://w3id.org/emmo/domain/microscopy#`
- `https://w3id.org/emmo/domain/pemfc`

## Namespace Usage

- `https://w3id.org/h2kg/hydrogen-ontology#`: 4118
- `http://www.w3.org/2004/02/skos/core#`: 3822
- `http://www.w3.org/2000/01/rdf-schema#`: 2067
- `http://purl.org/dc/terms/`: 2003
- `http://qudt.org/schema/qudt/`: 1485
- `http://www.w3.org/2002/07/owl#`: 7
- `http://www.w3.org/ns/prov#`: 6
- `http://xmlns.com/foaf/0.1/`: 1
- `http://www.w3.org/ns/dcat#`: 1

## Likely Release Blockers

- 20 schema terms are missing rdfs:label annotations.
- 43 schema terms are missing skos:definition annotations.
- 11 duplicated @id values detected in the source JSON-LD.
- The ontology contains many QUDT quantity-value nodes that should remain in an example or data module.

## Likely FAIR Blockers

- Version IRI and preferred namespace metadata are not consistently declared in the source ontology header.
- Schema annotation coverage is incomplete for labels, comments, and definitions.
- The source graph mixes schema and data-like resources, which reduces release clarity.
