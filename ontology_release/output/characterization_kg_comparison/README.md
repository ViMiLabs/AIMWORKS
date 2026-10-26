# H2KG-CHAMEO characterization benchmark

The two scored ABoxes are constructed independently from the same sanitized manifest. They contain no local semantic bridge predicates, and scored SPARQL does not read the neutral source-record layer. CHAMEO receives explicit credit for every applicable relation in its complete pinned EMMO import closure but not for locally invented predicates.

## Frozen inputs

- Workbook manifest: `C3A66E75FABDAF61C60949FFC7B0E08AAD324A1F77D6137BDE60FA20797001E6`
- CHAMEO 1.0.3: `01520fd7bc6f76ec5ff32a051533326a198c499c`; Turtle SHA-256 `2DBC2048B0BCAFBE850A8F7D54521B34F81AB009F7BE4C8EBBA56449D6D0C247`
- EMMO 1.0.3: `b85a0803c47819fc4b53b9c9fd6c61878f714c5b`
- EMMO import closure: 25 modules (12 direct and 13 transitive); lock fingerprint `B12265A4950CDE1E4258572282FFEDAE34E85DDCD03944917EF9EA055FF312FF`

## Frozen application contract

- Ontology-neutral lifecycle requirements: 13
- Assessment modes: native_vocabulary_coverage (1), query_based_retrieval (10), query_retrieval_and_native_pattern_assessment (2)
- Population: 8 source records, 7 method families, 7 unique profiles
- Selection strata: analysis_lineage (1), data_processing (1), measurement_context (1), measurement_settings (2), methodology_description (1), result_provenance (1), result_semantics (2), selected_profile_vocabulary (1), software_traceability (1), specimen_preparation (1), workflow_structure (1)
- H2KG exact requirements: 12/13
- CHAMEO exact requirements: 10/13
- CHAMEO partial requirements: 2/13
- Contract fingerprint: `BF6C5D2F4EA8F504F813464BDC5641F9C0ACC1B3020B42A6C48072A2384924FD`

## Computed conclusion

For the selected characterization profiles, the benchmark supports a scoped complementarity conclusion: CHAMEO provides explicit characterization-methodology structures, while H₂KG provides broader dedicated profile-class coverage together with direct valued-parameter and individually provenance-linked result patterns.

The 12/13 and 10/13 values are requirement-satisfaction rates under this frozen protocol, not general ontology-accuracy or quality scores. The benchmark covers eight source records representing seven unique profiles; governance, maintainability, reasoning performance, usability, and scalability were not measured.

`balanced_requirement_matrix.*` contains the primary evidence, `benchmark_population_audit.*` documents record/profile accounting and value eligibility, `ontology_evidence_audit.*` records the pinned TBox evidence, and `balanced_conclusion_rules.json` records every prespecified rule behind the conclusion. Query outcomes use normalized, deduplicated result-set comparison. The conclusion is emitted only when all five rules pass. The earlier 50-question H2KG application set remains in `native_query_matrix.*` only as a labelled historical asymmetric diagnostic and is excluded from the conclusion.
