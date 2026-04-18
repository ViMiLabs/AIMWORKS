# HDO Alignment Report

## Summary

- Reviewed against HDO: 96
- Aligned to HDO: 0
- Reused directly from HDO: 0
- Kept local after HDO review: 96
- Overlap with PROV-O / DCTERMS / EMMO anchors: 3

## HDO-Aligned Terms

- No direct HDO-aligned terms were generated in this run.

## Terms Kept Local

- `hasOutputData`: Candidate for future direct HDO reuse; currently kept local until the HDO cache and parity review are accepted.
- `hasInputData`: Candidate for future direct HDO reuse; currently kept local until the HDO cache and parity review are accepted.
- `Oxygen Gain/Loss Measurement`: Remains local because the current H2KG term carries profile-specific semantics beyond the generic HDO anchor.
- `O2–N2 Switching Measurement`: Remains local because the current H2KG term carries profile-specific semantics beyond the generic HDO anchor.
- `Through-Plane Gas Transport Measurement`: Remains local because the current H2KG term carries profile-specific semantics beyond the generic HDO anchor.
- `Current-Interrupt HFR Measurement`: Remains local because the current H2KG term carries profile-specific semantics beyond the generic HDO anchor.
- `ofProperty`: Remains local because the current H2KG term carries profile-specific semantics beyond the generic HDO anchor.
- `fromMeasurement`: Remains local because the current H2KG term carries profile-specific semantics beyond the generic HDO anchor.
- `MEA Polarization`: Remains local because the current H2KG term carries profile-specific semantics beyond the generic HDO anchor.
- `hasIdentifier`: Candidate for future direct HDO reuse; currently kept local until the HDO cache and parity review are accepted.
- `Square Wave Voltammetry`: Remains local because the current H2KG term carries profile-specific semantics beyond the generic HDO anchor.
- `Agent`: Remains local because the current H2KG term carries profile-specific semantics beyond the generic HDO anchor.
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
- `Metadata`: Candidate for future direct HDO reuse; currently kept local until the HDO cache and parity review are accepted.

## Cross-Standard Overlap Notes

- `Agent` also aligns with `prov-o` via `rdfs:subClassOf`
- `Process` also aligns with `emmo-core` via `owl:equivalentClass`
- `hasIdentifier` also aligns with `dcterms` via `rdfs:subPropertyOf`

## Guidance

- HDO role: Primary alignment source for Helmholtz-community data, metadata, identifier, digital-object, information-profile, schema, validation, and provenance-record concepts.
- Cache note: Direct HDO term reuse becomes stronger when a real HDO cache file is available at cache/sources/hdo.ttl.
