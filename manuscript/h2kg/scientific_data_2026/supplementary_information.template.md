# Supplementary information

## A domain-specific ontology for interoperable hydrogen electrochemical research workflows

Marjan Kohandani, Mohammad J. Eslamibidgoli, Said Fathallah, Michael H. Eikerling, and Kourosh Malek

This supplement documents the exact H₂KG 2.2.0 release state used in the article. It contains taxonomy and relation metrics, correction outcomes, competency checks, the complete ontology-level TIB benchmark, asserted-alignment counts, and the synthetic transmission electron microscopy profile. It contains no experimental data and no additional characterization-method case studies.

## Supplementary Table S1. Taxonomy content and top-branch distribution

| Metric | Count |
| --- | ---: |
| Active local classes | 2,221 |
| Deprecated compatibility classes | 165 |
| New structural classes | 157 |
| Subclass axioms | 2,221 |
| Object properties | 23 |
| Datatype properties | 1 |
| Annotation properties | 9 |
| Named taxonomy individuals | 0 |
| Agent branch | 4 |
| Characteristic branch | 1,052 |
| Information Entity branch | 109 |
| Matter branch | 692 |
| Process branch | 364 |

The five branch counts sum to 2,221. A branch count reports the number of active classes whose unique intrinsic top branch is the named branch; it is not a ranking of scientific importance.

## Supplementary Table S2. H₂KG object properties and declared domains and ranges

{{OBJECT_PROPERTIES_TABLE}}

Blank domains or ranges indicate intentionally generic relations. Domain and range declarations summarize the canonical H₂KG 2.2 taxonomy. Profile-specific endpoint constraints are expressed separately with SHACL.

## Supplementary Table S3. Version 2.2 correction and role-migration summary

| Correction or migration measure | Result |
| --- | ---: |
| Parent decisions represented | 156 |
| Definition decisions represented | 470 |
| Unique classes covered by correction decisions | 544 |
| Decisions applied | 455 |
| Decisions retained | 6 |
| Replacements | 7 |
| Splits | 1 |
| Source-dependent deprecations | 157 |
| Legacy workflow assertions classified | 4,418 |
| Legacy workflow assertions migrated or explicitly documented | 4,418 (100%) |
| Migrated profile relations | 4,416 |
| Unsupported documented legacy relations | 2 |
| Legacy `hasParameter` assertions classified | 1,163 |
| Parameter-record/property paths | 1,143 |
| Active characteristic classes typed as `Parameter` | 0 |
| Canonical class-to-class workflow assertions | 0 |

The difference between the 1,163 legacy `hasParameter` assertions and 1,143 parameter-record/property paths consists of targets whose intrinsic identities required other treatments, including material input, subprocess, reference-scale, normalization, or explicitly documented unsupported outcomes.

## Supplementary Table S4. Executable competency questions

{{COMPETENCY_TABLE}}

All nine checks passed in the H₂KG 2.2.0 build cited by the article. A passing check confirms the named retrieval or structural expectation; it does not validate experimental results.

## Supplementary Table S5. Automated TIB matching rules

| Outcome | Deterministic release rule | Public bridge treatment |
| --- | --- | --- |
| `exact_iri_reuse` | H₂KG and external concept use the same stable IRI | Reuse the external IRI; no duplicate mapping triple |
| `machine_exact_equivalent` | Active native external class; compatible role, definition, hierarchy, scientific scope, material state, and entity/value granularity; unique canonical target | `skos:exactMatch` only after the stricter assertion gate |
| `h2kg_narrower` | H₂KG definition adds defensible scientific restrictions to the external concept | `skos:broadMatch` only at high confidence |
| `h2kg_broader` | External definition adds defensible restrictions to the H₂KG concept | `skos:narrowMatch` only at high confidence |
| `related_non_equivalent` | Candidate is scientifically related but equivalence or hierarchy direction is unsupported, tied, or role-incompatible | Benchmark evidence only; no assertion |
| `ambiguous_abstained` | Reserved transparency category | Required to be zero in a publishable complete build |
| `unmatched` | Complete native-term search produced no candidate | Benchmark evidence only |

Candidate generation used preferred labels, alternate labels, normalized lexical forms, definitions, original ontology identifiers, obsolete/replacement state, direct parents, ancestor paths, and coarse semantic roles. Exact labels alone did not establish equivalence. Retrieval failures blocked publication and were not converted into unmatched outcomes. Percentages use all 2,221 active H₂KG classes as denominator.

## Supplementary Table S6. Ontology-level benchmark for all collection memberships

The frozen TIB snapshot contains 165 collection memberships representing 143 unique ontologies. Ontologies occurring in multiple collections appear once in each applicable collection block. Every outcome cell reports `count (percentage of 2,221 active H₂KG classes)`.

{{ONTOLOGY_BENCHMARK_TABLE}}

## Supplementary Table S7. Asserted TIB-derived bridge mappings by defining ontology

The external bridge contains 245 TIB-derived mapping assertions involving 159 H₂KG classes and 29 defining ontologies. Original ontology IRIs are mapping targets; TIB catalogue URLs are provenance links only. `skos:broadMatch` means that the H₂KG subject is narrower than its target, whereas `skos:narrowMatch` means that the H₂KG subject is broader.

{{ALIGNMENT_COUNTS_TABLE}}

Related benchmark candidates are deliberately absent from this table because they are not asserted as mappings.

## Supplementary Table S8. Synthetic TEM profile field dictionary

{{TEM_FIELD_TABLE}}

All example values are synthetic. The profile defines a record shape, not an experimental protocol, a certified reference dataset, or evidence for a particle-size result.

## Supplementary Table S9. Synthetic TEM validation cases

| Test case | Deliberate change | Expected result | Observed result |
| --- | --- | --- | --- |
| Positive record | Complete synthetic TEM occurrence graph | Conforms | Conforms |
| Wrong measurement type | Remove `TransmissionElectronMicroscopyImaging` type | Fails | Fails |
| Missing measurement output | Remove measurement-to-raw-dataset `hasOutputData` | Fails | Fails |
| Incompatible result property | Replace `PdNanoparticleDiameter` occurrence type with unsupported property | Fails | Fails |
| Incomplete quantity value | Remove QUDT unit from the synthetic `5 nm` quantity value | Fails | Fails |

The result chain uses `DataPoint → ofProperty → property occurrence → hasQuantityValue → qudt:QuantityValue`. The `DataPoint` also points to the TEM measurement with `fromMeasurement` and to the analysis process with `prov:wasGeneratedBy`. Parameter settings use `Measurement → hasParameter → Parameter record → ofProperty → property occurrence`. Thus, a scientific characteristic is not reclassified as a parameter.

## Reproducibility and artifact locations

The release state is identified by Git commit `55e7d86bdde3d41d85411f745b291d8caa3f8d31`. The principal files are:

- `ontology_release/output/ontology/h2kg-v2-complete.ttl` and `.jsonld`: complete recommended distribution.
- `ontology_release/output/ontology/h2kg-v2-taxonomy.ttl` and `.jsonld`: taxonomy-only distribution.
- `ontology_release/output/ontology/h2kg-v2-workflow-profiles.ttl` and `.jsonld`: canonical workflow-use profiles.
- `ontology_release/output/ontology/h2kg-v2-external-bridge.ttl` and `.jsonld`: asserted external mappings.
- `ontology_release/output/benchmarks/tib_collections/`: frozen benchmark reports and workbooks.
- `ontology_release/output/method_profiles/tem/`: synthetic TEM record, SHACL shape, capture template, field dictionary, and validation report.

The ontology resolves from `https://w3id.org/h2kg/hydrogen-ontology`; human-facing release documentation is available at `https://vimilabs.github.io/AIMWORKS/`.
