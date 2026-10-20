# DECODE Federated Workflow Layer

This release contains a normalized structural projection of immutable DECODE GraphML workflows, a sanitized manual-JSON source overlay, and a separately identified derived interface schema. It is a separate data layer aligned to H2KG; it does not change the H2KG ontology TBox or the TBox-only H2KG Explore page.

- Catalogue entries: 137
- Immutable GraphML workflows: 120
- Manual-JSON source workflows: 16
- Derived interface schemas: 1
- Preserved source occurrences: 3307
- Preserved directed source dependencies: 4463
- Explicitly mapped occurrences: 3134
- Shared semantic anchors: 714
- Semantic-overview nodes: 714
- Repeated source-concept groups: 294
- Semantic role conflicts: 0
- Classified source dependencies: 4463
- H2KG/PROV semantic projection triples: 6646
- Derived property-value DataPoint proxies: 713
- Derived contextual Parameter-record proxies: 84
- Declared workflow dependencies: 623
- Published workflow dependencies: 572
- Structural validation: passed

## Mapping states

- `approved_h2kg`: an explicit mapping to an existing H2KG IRI.
- `decode_local`: a stable DECODE-local anchor that is not part of H2KG.
- `unresolved`: retained without cross-workflow merging.

Raw GraphML files and the original attached manual JSON are not redistributed in this package. The sanitized overlay excludes personal names and email addresses. Normalized JSON, JSON-LD and Turtle projections preserve source node IDs and directed dependencies for inspection and reuse.

`decode_manual_reconciliation.json` and `.csv` document duplicate handling, identifier correction, existing-workflow reconciliation, retained GraphML workflows, and the 16 new manual-source workflows. `decode_workflow_dependencies.*` publishes only reciprocal or exact-handoff-grounded method dependencies; unsupported one-sided declarations remain audit-only.

`decode_duplicate_occurrence_audit.csv` documents every repeated source label within a workflow. `decode_semantic_role_conflicts.csv` records any incompatible roles assigned to a shared anchor and causes validation to fail. The semantic overview is a derived visualization only: every aggregate edge records the exact preserved source-dependency IDs it represents.

`decode_edge_registry.csv` classifies every source dependency as `h2kg_direct`, `h2kg_reified`, `prov_derivation`, or `decode_structural_only`. Source dependencies are never relabelled or removed. A semantic projection may reverse direction where required by H2KG. Property-valued inputs use contextual `Parameter`-record proxies linked to preserved property occurrences through `ofProperty`; calculated values use `DataPoint` proxies with the same intrinsic-property pattern.

`decode_definition_registry.csv`, `.json`, and `.md` provide domain-aware DECODE-local definitions for every distinct source concept. Entries marked `not_in_h2kg` remain outside the public H2KG taxonomy.

`decode-h2kg-aligned-ontology.ttl` and `.jsonld` contain the complete merged DECODE vocabulary and workflow occurrence graph. DECODE-local anchors are OWL classes under compatible H2KG roles, while source occurrences and reified source edges preserve the original workflow topology. DECODE-local terms remain separate from H2KG. DECODE licensing remains pending governance confirmation, so no open reuse license is asserted for these files.
