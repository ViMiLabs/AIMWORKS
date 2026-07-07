# Validation Report

- Overall valid: true
- Namespace strategy: `preserve_hash_namespace`
- SHACL executed: true
- SHACL details: Validation Report
Conforms: True
- Release candidate path: `..\output\ontology\schema.ttl`

## Release Candidate Checks

- Local schema terms: 33
- Missing labels: 0
- Missing definitions: 0
- Placeholder-style generated definitions: 0
- Definition coverage: 1.0
- Imports declared in release schema: 9
- Mapping issues detected: 0
- Duplicate @id groups in source: 0
- Duplicate @id conflicts in source: 0

## OOPS! Pitfall Scan

- Status: unavailable
- Service: https://oops.linkeddata.es/rest
- Message: OOPS! something went wrong. There was an unexpected error.
- Pitfall count: not assessed

- No pitfalls listed.

## FOOPS! FAIR Assessment

- Status: assessed
- Service: https://foops.linkeddata.es/FAIR_validator.html
- Mode: file
- Message: FOOPS! assessment completed in file mode. Accessible checks may remain unassessed.
- Overall score: 75.0
- Findable: 60.0
- Accessible: None
- Interoperable: 100.0
- Reusable: 91.5

## FOOPS! Failed Checks

- F1: the ontology URI does not follow any of the schemes followed by known registers of persistent URIs. We checked w3id, purl, DOI, W3C, perma.cc, linked.data.gov.au, data.europa.eu and dbpedia.org
- F2: The following metadata was not found: version iri
- R1: The following metadata was not found: citation
- R1: The following metadata was not found: doi, logo, status, source, issued. Warning: The following OPTIONAL detailed metadata could not be found: backwards compatibility. Please consider adding them if appropriate.
- R1.2: The following provenance information was not found: issued
- F1: Version IRI  not defined. Version info found (1.0.0).

## Errors

- None

## Warnings

- None
