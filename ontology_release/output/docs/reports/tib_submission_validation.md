# H2KG 2.3.1 TIB Submission Validation

- Pre-release ready: **True**
- Submission ready: **False**
- TIB mandatory warnings/violations: **0**
- TIB recommendation notices: **1**
- Canonical serialization parity: **True**

| Check | Result | Blocking | Evidence |
|---|---|---|---|
| `tib-metadata-shape-lock` | PASS | yes | Pinned TIB metadata shape SHA-256: 1FB6BD869F2E48F7248D87B26BD2D3D5035A5E79C470909E478F4E011A94A6FF. |
| `canonical-serialization-parity` | PASS | yes | Canonical Turtle and JSON-LD graphs are RDF-isomorphic. |
| `tib-mandatory-metadata` | PASS | yes | Official TIB shape results: 0 mandatory warning/violation(s), 1 recommendation notice(s). |
| `count-active-classes` | PASS | yes | Expected 2226; canonical graph contains 2226. |
| `count-deprecated-classes` | PASS | yes | Expected 160; canonical graph contains 160. |
| `count-total-classes` | PASS | yes | Expected 2386; canonical graph contains 2386. |
| `count-object-properties` | PASS | yes | Expected 23; canonical graph contains 23. |
| `count-datatype-properties` | PASS | yes | Expected 1; canonical graph contains 1. |
| `count-annotation-properties` | PASS | yes | Expected 9; canonical graph contains 9. |
| `count-taxonomy-individuals` | PASS | yes | Expected 0; canonical graph contains 0. |
| `single-ontology-header` | PASS | yes | Ontology headers: https://w3id.org/h2kg/hydrogen-ontology. |
| `ontology-title` | PASS | yes | The ontology title is generated from the release profile. |
| `lowercase-prefix` | PASS | yes | Preferred namespace prefix: h2kg. |
| `preferred-namespace` | PASS | yes | Preferred namespace URI: https://w3id.org/h2kg/hydrogen-ontology#. |
| `license` | PASS | yes | License: https://creativecommons.org/licenses/by/4.0/. |
| `created-date` | PASS | yes | Creation date: 2026-03-19. |
| `modified-date` | PASS | yes | Modification date: 2026-11-01. |
| `abstract` | PASS | yes | English abstract length: 330 characters. |
| `issue-tracker` | PASS | yes | Issue tracker: https://github.com/ViMiLabs/AIMWORKS/issues. |
| `documentation` | PASS | yes | Documentation: https://vimilabs.github.io/AIMWORKS/hydrogen-ontology.html. |
| `confirmed-attribution` | PASS | yes | Configured attribution resources: 5; unconfirmed: 0. |
| `attribution-list-complete` | PASS | yes | Contributor order complete: True; configured orders: [1, 2, 3, 4]; missing: none; duplicates: none. |
| `creator-orcid` | PASS | yes | Valid ORCID attribution IRIs: 3; malformed: 0. |
| `affiliation-assignments` | PASS | yes | People without affiliation assignment: none; unknown affiliation identifiers: none. |
| `personal-pid-attribution` | PASS | yes | Named people without an ORCID or documented institutional identifier: none |
| `organization-ror` | PASS | yes | Valid ROR attribution IRIs: 1. |
| `attribution-labels` | PASS | yes | Attribution resources without display labels: 0. |
| `version-metadata` | PASS | yes | Version IRI: https://w3id.org/h2kg/hydrogen-ontology/releases/2.3.1. |
| `prior-version` | PASS | yes | Prior version: https://w3id.org/h2kg/hydrogen-ontology/releases/2.3.0. |
| `foundational-imports-only` | PASS | yes | Declared imports: http://qudt.org/2.1/schema/qudt, https://www.w3.org/ns/prov-o. |
| `explicit-root-classes` | PASS | yes | Declared root classes: 5. |
| `no-local-file-iris` | PASS | yes | Local file IRIs: 0. |
| `canonical-distributions` | PASS | yes | Canonical distributions: https://vimilabs.github.io/AIMWORKS/ontology/h2kg-v2-taxonomy.jsonld, https://vimilabs.github.io/AIMWORKS/ontology/h2kg-v2-taxonomy.ttl. |
| `canonical-resolver-template` | PASS | yes | Stable RDF routes target the taxonomy and the shared core has an explicit secondary route. |
| `immutable-version-route-template` | PASS | yes | The semantic-version route targets immutable Git tags. |
| `citation-cff-version` | PASS | yes | CITATION.cff version: 2.3.1. |
| `citation-cff-title` | PASS | yes | CITATION.cff title: H₂KG Domain Ontology for Hydrogen Electrochemical Systems. |
| `zenodo-version` | PASS | yes | Zenodo version: 2.3.1. |
| `zenodo-title` | PASS | yes | Zenodo title: H₂KG Domain Ontology for Hydrogen Electrochemical Systems. |
| `citation-cff-attribution` | PASS | yes | CITATION.cff attribution records: 5. |
| `zenodo-attribution` | PASS | yes | Zenodo attribution records: 5. |
| `live-documentation` | PASS | no | https://vimilabs.github.io/AIMWORKS/hydrogen-ontology.html returned HTTP 200; final URL https://vimilabs.github.io/AIMWORKS/hydrogen-ontology.html. |
| `live-issue-tracker` | PASS | no | https://github.com/ViMiLabs/AIMWORKS/issues returned HTTP 200; final URL https://github.com/ViMiLabs/AIMWORKS/issues. |
| `live-canonical-turtle` | PASS | no | https://vimilabs.github.io/AIMWORKS/ontology/h2kg-v2-taxonomy.ttl returned HTTP 200; final URL https://vimilabs.github.io/AIMWORKS/ontology/h2kg-v2-taxonomy.ttl. |
| `live-canonical-jsonld` | PASS | no | https://vimilabs.github.io/AIMWORKS/ontology/h2kg-v2-taxonomy.jsonld returned HTTP 200; final URL https://vimilabs.github.io/AIMWORKS/ontology/h2kg-v2-taxonomy.jsonld. |
| `live-version-iri` | FAIL | no | https://w3id.org/h2kg/hydrogen-ontology/releases/2.3.1 returned HTTP 404; final URL https://w3id.org/h2kg/hydrogen-ontology/releases/2.3.1. |
| `live-attribution-pid-1` | PASS | no | https://ror.org/02nv7yv05 was verified through the official ROR registry API (https://api.ror.org/v2/organizations/02nv7yv05, HTTP 200); resolver endpoint HTTP 429. |
| `live-attribution-pid-2` | PASS | no | https://orcid.org/0009-0005-5173-202X returned HTTP 200; final URL https://orcid.org/0009-0005-5173-202X. |
| `live-attribution-pid-3` | PASS | no | https://orcid.org/0000-0002-5057-2993 returned HTTP 200; final URL https://orcid.org/0000-0002-5057-2993. |
| `live-attribution-pid-4` | PASS | no | https://www.fz-juelich.de/profile/malek_k returned HTTP 200; final URL https://www.fz-juelich.de/profile/malek_k. |
| `live-attribution-pid-5` | PASS | no | https://orcid.org/0000-0002-0764-8948 returned HTTP 200; final URL https://orcid.org/0000-0002-0764-8948. |
