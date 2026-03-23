# Validation Report

- Overall valid: true
- Namespace strategy: `preserve_hash_namespace`
- SHACL executed: true
- SHACL details: Validation Report
Conforms: False
Results (1):
Constraint Violation in MinCountConstraintComponent (http://www.w3.org/ns/shacl#MinCountConstraintComponent):
	Severity: sh:Violation
	Source Shape: [ sh:minCount Literal("1", datatype=xsd:integer) ; sh:path skos:definition ]
	Focus Node: electrochemistry:electrochemistry_7729c34e_1ae9_403d_b933_1765885e7f29
	Result Path: skos:definition
	Message: Less than 1 values on electrochemistry:electrochemistry_7729c34e_1ae9_403d_b933_1765885e7f29->skos:definition
- Release candidate path: `output\ontology\schema.ttl`

## Release Candidate Checks

- Local schema terms: 34
- Missing labels: 0
- Missing definitions: 0
- Placeholder-style generated definitions: 34
- Definition coverage: 1.0
- Imports declared in release schema: 9
- Mapping issues detected: 0

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
- Overall score: 46.7
- Findable: 60.0
- Accessible: None
- Interoperable: 33.3
- Reusable: 44.4

## FOOPS! Failed Checks

- F1: Unexpected error while running the test: null
- F2: The following metadata was not found: version iri
- R1: The following metadata was not found: version info, citation
- R1: The following metadata was not found: doi, logo, status, source, issued. Warning: The following OPTIONAL detailed metadata could not be found: previous version, backwards compatibility. Please consider adding them if appropriate.
- R1.2: The following provenance information was not found: issued
- I2: The ontology does not reuse vocabularies for common metadata
- I2: The ontology does not import/extend other vocabularies.
- R1: No ontology terms found
- R1: No ontology terms found
- F1: Version IRI  not defined. Version information not found.  Please consider adding it to describe the version number of the ontology.

## Errors

- None

## Warnings

- 34 local schema terms still use template-style generated definitions or comments.
- Duplicate JSON-LD node identifiers were found and should be reviewed.
