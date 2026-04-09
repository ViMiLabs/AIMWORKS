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
- Release candidate path: `ontology_release\output\ontology\schema.ttl`

## Release Candidate Checks

- Local schema terms: 34
- Missing labels: 0
- Missing definitions: 0
- Placeholder-style generated definitions: 34
- Definition coverage: 1.0
- Imports declared in release schema: 9
- Mapping issues detected: 0
- Duplicate @id groups in source: 11
- Duplicate @id conflicts in source: 0

## OOPS! Pitfall Scan

- Status: unavailable
- Service: https://oops.linkeddata.es/rest
- Message: OOPS! service unavailable: HTTPSConnectionPool(host='oops.linkeddata.es', port=443): Max retries exceeded with url: /rest (Caused by NewConnectionError("HTTPSConnection(host='oops.linkeddata.es', port=443): Failed to establish a new connection: [WinError 10013] An attempt was made to access a socket in a way forbidden by its access permissions"))
- Pitfall count: not assessed

- No pitfalls listed.

## FOOPS! FAIR Assessment

- Status: unavailable
- Service: https://foops.linkeddata.es/FAIR_validator.html
- Mode: file
- Message: FOOPS! service unavailable: HTTPSConnectionPool(host='foops.linkeddata.es', port=443): Max retries exceeded with url: /assessOntologyFile (Caused by NewConnectionError("HTTPSConnection(host='foops.linkeddata.es', port=443): Failed to establish a new connection: [WinError 10013] An attempt was made to access a socket in a way forbidden by its access permissions"))
- Overall score: not assessed
- Findable: not assessed
- Accessible: not assessed
- Interoperable: not assessed
- Reusable: not assessed

## FOOPS! Failed Checks

- No failed-check detail extracted.

## Errors

- None

## Warnings

- 34 local schema terms still use template-style generated definitions or comments.
