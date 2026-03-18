# Release Readiness Report

- Release ready: **False**
- Overall readiness score: **95.0 / 100**

## Criteria

- F (Findable): 100 / 100
- A (Accessible): 100 / 100
- I (Interoperable): 100 / 100
- R (Reusable): 80 / 100

## External Transparency Hooks

- OOPS! and FOOPS! are tracked separately from the numeric FAIR score so the base F/A/I/R calculation stays reproducible offline.
- OOPS! ontology pitfall scan: **warning**. OOPS! assessment could not be completed: HTTPSConnectionPool(host='oops.linkeddata.es', port=443): Max retries exceeded with url: /rest (Caused by ProxyError('Unable to connect to proxy', NewConnectionError("HTTPSConnection(host='127.0.0.1', port=9): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it")))
- FOOPS! FAIR assessment: **warning**. FOOPS! assessment could not be completed: HTTPSConnectionPool(host='foops.linkeddata.es', port=443): Max retries exceeded with url: /assessOntologyFile (Caused by ProxyError('Unable to connect to proxy', NewConnectionError("HTTPSConnection(host='127.0.0.1', port=9): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it")))

## External Service Results

- FOOPS! did not return a score in this run.
- OOPS! did not return a pitfall count in this run.

## Required Follow-up

- SHACL validation still reports unresolved constraints.
