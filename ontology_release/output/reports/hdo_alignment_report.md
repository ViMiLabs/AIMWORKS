# HDO Alignment Report

## Summary

- Assessed against HDO: 141
- Aligned to HDO: 8
- Reused directly from HDO: 8
- Kept local after HDO comparison: 135
- Overlap with PROV-O / DCTERMS / EMMO anchors: 2

## HDO-Aligned Terms

- `Agent` -> `rdfs:subClassOf` -> `http://www.w3.org/ns/prov#Agent`
- `FTIR Dataset` -> `rdfs:subClassOf` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00002013`
- `Metadata` -> `rdfs:subClassOf` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00000029`
- `Metadata` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00001036`
- `Microstructure Image Dataset` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00000005`
- `PEMFCCFD Simulation` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00001069`
- `hasMetadata` -> `owl:equivalentProperty` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00006069`
- `hasMetadata` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00006070`

## Terms Kept Local

- `hasOutputData`: Candidate for future direct HDO reuse; currently kept local until the HDO cache and parity review are accepted.
- `hasInputData`: Candidate for future direct HDO reuse; currently kept local until the HDO cache and parity review are accepted.
- `Through-Plane Gas Transport Measurement`: Remains local because the current H2KG term carries profile-specific semantics beyond the generic HDO anchor.
- `ofProperty`: Remains local because the current H2KG term carries profile-specific semantics beyond the generic HDO anchor.
- `fromMeasurement`: Remains local because the current H2KG term carries profile-specific semantics beyond the generic HDO anchor.
- `hasIdentifier`: Candidate for future direct HDO reuse; currently kept local until the HDO cache and parity review are accepted.
- `Square Wave Voltammetry`: Remains local because the current H2KG term carries profile-specific semantics beyond the generic HDO anchor.
- `atCurrentDensity`: Remains local because the current H2KG term carries profile-specific semantics beyond the generic HDO anchor.
- `Electrochemical Impedance Spectroscopy Potentiostatic`: Remains local because the current H2KG term carries profile-specific semantics beyond the generic HDO anchor.
- `Rotating Ring Disk Voltammetry`: Remains local because the current H2KG term carries profile-specific semantics beyond the generic HDO anchor.
- `Process`: Remains local because the current H2KG term carries profile-specific semantics beyond the generic HDO anchor.
- `Electrochemical Impedance Spectroscopy Galvanostatic`: Remains local because the current H2KG term carries profile-specific semantics beyond the generic HDO anchor.
- `Cyclic Voltammetry`: Remains local because the current H2KG term carries profile-specific semantics beyond the generic HDO anchor.
- `Experiment Dataset`: Candidate for future direct HDO reuse; currently kept local until the HDO cache and parity review are accepted.
- `ECSA by Double-Layer Capacitance`: Remains local because the current H2KG term carries profile-specific semantics beyond the generic HDO anchor.
- `hasQuantityValue`: Remains local because the current H2KG term carries profile-specific semantics beyond the generic HDO anchor.
- `Data`: Candidate for future direct HDO reuse; currently kept local until the HDO cache and parity review are accepted.
- `Data Point`: Kept local pending a more precise HDO term-level match while retaining H2KG experimental granularity.
- `Linear Sweep Voltammetry`: Remains local because the current H2KG term carries profile-specific semantics beyond the generic HDO anchor.
- `Cathodic Stripping Voltammetry`: Remains local because the current H2KG term carries profile-specific semantics beyond the generic HDO anchor.
- `ECSA Dataset`: Candidate for future direct HDO reuse; currently kept local until the HDO cache and parity review are accepted.
- `Impedance Dataset`: Candidate for future direct HDO reuse; currently kept local until the HDO cache and parity review are accepted.
- `Limiting Current Dataset`: Candidate for future direct HDO reuse; currently kept local until the HDO cache and parity review are accepted.
- `Polarization Curve Dataset`: Candidate for future direct HDO reuse; currently kept local until the HDO cache and parity review are accepted.
- `Ionomer Dispersion Property Dataset`: Candidate for future direct HDO reuse; currently kept local until the HDO cache and parity review are accepted.

## Cross-Standard Overlap Notes

- `Process` also aligns with `emmo-core` via `owl:equivalentClass`
- `hasIdentifier` also aligns with `dcterms` via `rdfs:subPropertyOf`

## Guidance

- HDO role: Primary alignment source for Helmholtz-community data, metadata, identifier, digital-object, information-profile, schema, validation, and provenance-record concepts.
- Cache note: Direct HDO term reuse becomes stronger when a real HDO cache file is available at cache/sources/hdo.ttl.
