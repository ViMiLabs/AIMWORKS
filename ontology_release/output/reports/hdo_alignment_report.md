# HDO Alignment Report

## Summary

- Reviewed against HDO: 10
- Aligned to HDO: 130
- Reused directly from HDO: 130
- Kept local after HDO review: 3
- Overlap with PROV-O / DCTERMS / EMMO anchors: 1

## HDO-Aligned Terms

- `Aggregate Aspect Ratio` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00006044`
- `Aggregate Aspect Ratio` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00006028`
- `Aggregate Aspect Ratio` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00007033`
- `Annealing Duration` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00000025`
- `Component Molar Ratio` -> `skos:closeMatch` -> `http://purl.obolibrary.org/obo/IAO_0000030`
- `Concentration Exponent` -> `skos:closeMatch` -> `http://purl.obolibrary.org/obo/BFO_0000004`
- `Crack Aspect Ratio` -> `skos:closeMatch` -> `http://purl.obolibrary.org/obo/IAO_0000104`
- `Data` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00000009`
- `Data` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00000116`
- `Data` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00000107`
- `Data` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00001037`
- `Data` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00001039`
- `Data Point` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00002013`
- `Data Point` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00007008`
- `Data Point` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00000108`
- `Data Point` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00001069`
- `Data Point` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00000007`
- `Designed Porosity` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00000108`
- `Drying Duration` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00000025`
- `Drying Duration` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00006025`
- `Drying Duration` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00005003`
- `Dye Concentration` -> `skos:closeMatch` -> `http://purl.obolibrary.org/obo/IAO_0000030`
- `ECSA Basis` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00006037`
- `Electrode Substrate` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00000121`
- `Electrode Substrate` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00006031`

## Terms Kept Local

- `hasIdentifier`: Candidate for future direct HDO reuse; currently kept local until the HDO cache and parity review are accepted.
- `Radius Of Gyration`: Remains local because the current H2KG term carries profile-specific semantics beyond the generic HDO anchor.
- `Carbon Black Aggregate Anisotropy Ratio`: Remains local because the current H2KG term carries profile-specific semantics beyond the generic HDO anchor.

## Cross-Standard Overlap Notes

- `hasIdentifier` also aligns with `dcterms` via `rdfs:subPropertyOf`

## Guidance

- HDO role: Primary alignment source for Helmholtz-community data, metadata, identifier, digital-object, information-profile, schema, validation, and provenance-record concepts.
- Cache note: Direct HDO term reuse becomes stronger when a real HDO cache file is available at cache/sources/hdo.ttl.
