# Alignment Report

## Summary

- Proposed mappings: 139
- Strong equivalence candidates: 3
- Subclass or subproperty anchors: 9
- SKOS soft matches: 127

## Representative Mappings

- `Agent` -> `rdfs:subClassOf` -> `http://www.w3.org/ns/prov#Agent` (0.99)
- `Aggregate Aspect Ratio` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00006044` (0.651)
- `Aggregate Aspect Ratio` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00006028` (0.564)
- `Aggregate Aspect Ratio` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00007033` (0.56)
- `Annealing Duration` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00000025` (0.552)
- `Component Molar Ratio` -> `skos:closeMatch` -> `http://purl.obolibrary.org/obo/IAO_0000030` (0.553)
- `Concentration Exponent` -> `skos:closeMatch` -> `http://purl.obolibrary.org/obo/BFO_0000004` (0.636)
- `Crack Aspect Ratio` -> `skos:closeMatch` -> `http://purl.obolibrary.org/obo/IAO_0000104` (0.556)
- `Data` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00000009` (0.747)
- `Data` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00000116` (0.747)
- `Data` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00000107` (0.695)
- `Data` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00001037` (0.695)
- `Data` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00001039` (0.695)
- `Data Point` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00002013` (0.712)
- `Data Point` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00007008` (0.689)
- `Data Point` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00000108` (0.651)
- `Data Point` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00001069` (0.64)
- `Data Point` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00000007` (0.636)
- `Designed Porosity` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00000108` (0.571)
- `Drying Duration` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00000025` (0.615)
- `Drying Duration` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00006025` (0.588)
- `Drying Duration` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00005003` (0.552)
- `Dye Concentration` -> `skos:closeMatch` -> `http://purl.obolibrary.org/obo/IAO_0000030` (0.558)
- `ECSA Basis` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00006037` (0.556)
- `Electrode Substrate` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00000121` (0.571)

## Policy Notes

- Generic process, material, measurement, and property concepts are anchored conservatively to EMMO and ECHO.
- Units and quantity-value semantics reuse QUDT when possible.
- Metadata and provenance terms prefer DCTERMS, FOAF, and PROV-O.
- HDO is the preferred shadow-mode alignment source for data, metadata, identifier, digital-object, schema, validation, and information-profile concepts.
- Local PEMFC catalyst-layer terms remain in the `h2kg` namespace for v1 unless a later migration policy is explicitly enabled.
