# Alignment Report

## Summary

- Proposed mappings: 9
- Strong equivalence candidates: 2
- Subclass or subproperty anchors: 4
- SKOS soft matches: 3

## Representative Mappings

- `Agent` -> `rdfs:subClassOf` -> `http://www.w3.org/ns/prov#Agent` (0.99)
- `Electrode Substrate` -> `skos:closeMatch` -> `https://w3id.org/emmo/domain/electrochemistry#electrochemistry_7729c34e_1ae9_403d_b933_1765885e7f29` (0.565)
- `Matter` -> `skos:closeMatch` -> `https://w3id.org/emmo#EMMO_material` (0.714)
- `Measurement` -> `rdfs:subClassOf` -> `https://w3id.org/emmo/domain/electrochemistry#electrochemistry_7729c34e_1ae9_403d_b933_1765885e7f29` (0.99)
- `Process` -> `owl:equivalentClass` -> `https://w3id.org/emmo#EMMO_process` (1.0)
- `Property` -> `owl:equivalentClass` -> `https://w3id.org/emmo#EMMO_property` (1.0)
- `hasIdentifier` -> `rdfs:subPropertyOf` -> `http://purl.org/dc/terms/identifier` (0.87)
- `hasName` -> `skos:closeMatch` -> `http://xmlns.com/foaf/0.1/name` (0.727)
- `hasQuantityValue` -> `rdfs:subPropertyOf` -> `http://qudt.org/schema/qudt/quantityValue` (0.99)

## Policy Notes

- Generic process, material, measurement, and property concepts are anchored conservatively to EMMO and ECHO.
- Units and quantity-value semantics reuse QUDT when possible.
- Metadata and provenance terms prefer DCTERMS, FOAF, and PROV-O.
- Local PEMFC catalyst-layer terms remain in the `h2kg` namespace for v1 unless a later migration policy is explicitly enabled.
