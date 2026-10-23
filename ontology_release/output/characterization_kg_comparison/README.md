# Fair H2KG-CHAMEO characterization benchmark

The two scored ABoxes are constructed independently from the same sanitized manifest. They contain no local semantic bridge predicates, and scored SPARQL does not read the neutral source-record layer. CHAMEO receives explicit credit for every applicable relation in its complete pinned EMMO import closure but not for locally invented predicates.

## Frozen inputs

- Workbook manifest: `C3A66E75FABDAF61C60949FFC7B0E08AAD324A1F77D6137BDE60FA20797001E6`
- CHAMEO 1.0.3: `01520fd7bc6f76ec5ff32a051533326a198c499c`; Turtle SHA-256 `2DBC2048B0BCAFBE850A8F7D54521B34F81AB009F7BE4C8EBBA56449D6D0C247`
- EMMO 1.0.3: `b85a0803c47819fc4b53b9c9fd6c61878f714c5b`
- EMMO import closure: 25 modules (12 direct and 13 transitive); lock fingerprint `B12265A4950CDE1E4258572282FFEDAE34E85DDCD03944917EF9EA055FF312FF`

## Frozen application contract

- Ontology-neutral lifecycle requirements: 13
- Selection strata: analysis_lineage (1), data_processing (1), domain_terminology (1), measurement_context (1), measurement_settings (2), methodology_description (1), result_provenance (1), result_semantics (2), software_traceability (1), specimen_preparation (1), workflow_structure (1)
- H2KG exact requirements: 12/13
- CHAMEO exact requirements: 10/13
- CHAMEO partial requirements: 2/13
- Contract fingerprint: `F731088A30DE6148B526814F40C6E7E0718379FFBB1DB1A68237C0CA21237FEA`

## Computed conclusion

The benchmark supports the conclusion that CHAMEO provides broad characterization methodology, while H₂KG complements it with hydrogen-domain specificity and direct valued-parameter and individually provenance-linked result patterns.

This is a conclusive result for the frozen thirteen-requirement characterization knowledge-graph benchmark over the eight workbook-derived cases. Governance, maintainability, reasoning performance, usability, and scalability were not measured.

`balanced_requirement_matrix.*` contains the primary evidence, `ontology_evidence_audit.*` records the pinned TBox evidence, and `balanced_conclusion_rules.json` records every prespecified rule behind the conclusion. The conclusion is emitted only when all five rules pass. The earlier 50-question H2KG application set remains in `native_query_matrix.*` only as a labelled historical asymmetric diagnostic and is excluded from the conclusion.
