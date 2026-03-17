# Validation Report

- RDF syntax sanity: **pass**
- Overall status: **warning**
- Missing metadata predicates: **0**
- Missing labels: **0**
- Missing definitions/comments: **0**
- Mapping issues: **0**
- Namespace violations: **0**
- SHACL conforms: **False**
- OWL consistency hook: **skipped**
- EMMO convention hook: **skipped**
- OOPS! hook: **warning**
- FOOPS! hook: **warning**

## Details


## SHACL Summary

- Validation Report
- Conforms: False
- Results (1):
- Constraint Violation in OrConstraintComponent (http://www.w3.org/ns/shacl#OrConstraintComponent):
- 	Severity: sh:Violation
- 	Source Shape: [ rdf:type sh:NodeShape ; sh:or ( [ sh:property [ sh:minCount Literal("1", datatype=xsd:integer) ; sh:path rdfs:comment ] ] [ sh:property [ sh:minCount Literal("1", datatype=xsd:integer) ; sh:path skos:definition ] ] ) ; sh:property [ sh:minCount Literal("1", datatype=xsd:integer) ; sh:path rdfs:label ] ; sh:targetClass owl:Class ]
- 	Focus Node: <https://w3id.org/emmo/domain/electrochemistry#electrochemistry_7729c34e_1ae9_403d_b933_1765885e7f29>
- 	Value Node: <https://w3id.org/emmo/domain/electrochemistry#electrochemistry_7729c34e_1ae9_403d_b933_1765885e7f29>
- 	Message: Node <https://w3id.org/emmo/domain/electrochemistry#electrochemistry_7729c34e_1ae9_403d_b933_1765885e7f29> must conform to one or more shapes in [ sh:property [ sh:minCount Literal("1", datatype=xsd:integer) ; sh:path rdfs:comment ] ] , [ sh:property [ sh:minCount Literal("1", datatype=xsd:integer) ; sh:path skos:definition ] ]

## External Service Assessments

- OOPS!: OOPS! assessment could not be completed: HTTPSConnectionPool(host='oops.linkeddata.es', port=443): Max retries exceeded with url: /rest (Caused by ProxyError('Unable to connect to proxy', NewConnectionError("HTTPSConnection(host='127.0.0.1', port=9): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it")))
- OOPS! link: https://oops.linkeddata.es/
- FOOPS!: FOOPS! assessment could not be completed: HTTPSConnectionPool(host='foops.linkeddata.es', port=443): Max retries exceeded with url: /assessOntologyFile (Caused by ProxyError('Unable to connect to proxy', NewConnectionError("HTTPSConnection(host='127.0.0.1', port=9): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it")))
- FOOPS! link: https://foops.linkeddata.es/FAIR_validator.html

- FOOPS! test catalogue: https://w3id.org/foops/catalogue

## Optional Hooks

- OWL consistency: owlready2 is not installed; OWL consistency loading and reasoner hooks were skipped.
- EMMO checks: EMMOntoPy is not installed; optional EMMO convention checks were skipped.

## Resolver Checks

- Ontology IRI [text/html]: local_ready (Local publication artifact exists. Network resolver check was not executed because enable_network_checks is false.)
- Ontology IRI [text/turtle]: local_ready (Local publication artifact exists. Network resolver check was not executed because enable_network_checks is false.)
- Ontology IRI [application/ld+json]: local_ready (Local publication artifact exists. Network resolver check was not executed because enable_network_checks is false.)
- Source [text/html]: local_ready (Local publication artifact exists. Network resolver check was not executed because enable_network_checks is false.)
- Source [text/turtle]: local_ready (Local publication artifact exists. Network resolver check was not executed because enable_network_checks is false.)
- Source [application/ld+json]: local_ready (Local publication artifact exists. Network resolver check was not executed because enable_network_checks is false.)
- Inferred [text/html]: local_ready (Local publication artifact exists. Network resolver check was not executed because enable_network_checks is false.)
- Inferred [text/turtle]: local_ready (Local publication artifact exists. Network resolver check was not executed because enable_network_checks is false.)
- Inferred [application/ld+json]: local_ready (Local publication artifact exists. Network resolver check was not executed because enable_network_checks is false.)
- Latest [text/html]: local_ready (Local publication artifact exists. Network resolver check was not executed because enable_network_checks is false.)
- Latest [text/turtle]: local_ready (Local publication artifact exists. Network resolver check was not executed because enable_network_checks is false.)
- Latest [application/ld+json]: local_ready (Local publication artifact exists. Network resolver check was not executed because enable_network_checks is false.)
- Context [text/html]: local_ready (Local publication artifact exists. Network resolver check was not executed because enable_network_checks is false.)
- Context [text/turtle]: local_ready (Local publication artifact exists. Network resolver check was not executed because enable_network_checks is false.)
- Context [application/ld+json]: local_ready (Local publication artifact exists. Network resolver check was not executed because enable_network_checks is false.)
- Versioned release [text/html]: local_ready (Local publication artifact exists. Network resolver check was not executed because enable_network_checks is false.)
- Versioned release [text/turtle]: local_ready (Local publication artifact exists. Network resolver check was not executed because enable_network_checks is false.)
- Versioned release [application/ld+json]: local_ready (Local publication artifact exists. Network resolver check was not executed because enable_network_checks is false.)
- Versioned inferred [text/html]: local_ready (Local publication artifact exists. Network resolver check was not executed because enable_network_checks is false.)
- Versioned inferred [text/turtle]: local_ready (Local publication artifact exists. Network resolver check was not executed because enable_network_checks is false.)
- Versioned inferred [application/ld+json]: local_ready (Local publication artifact exists. Network resolver check was not executed because enable_network_checks is false.)
