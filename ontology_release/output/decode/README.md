# DECODE Federated Workflow Layer

This release contains a normalized structural projection of immutable DECODE GraphML workflows, a sanitized manual-JSON source overlay, and a separately identified derived interface schema. It is a separate data layer aligned to H2KG; it does not change the H2KG ontology TBox or the TBox-only H2KG Explore page.

- Catalogue entries: 137
- Immutable GraphML workflows: 120
- Manual-JSON source workflows: 16
- Derived interface schemas: 1
- Preserved source occurrences: 3134
- Preserved directed source dependencies: 4173
- Explicitly mapped occurrences: 3134
- Shared reviewed anchors: 720
- Semantic-overview nodes: 720
- Repeated source-concept groups: 294
- Semantic role conflicts: 0
- Classified source dependencies: 4463
- H2KG/PROV semantic projection triples: 6018
- Derived property-value DataPoint proxies: 599
- Reviewed workflow dependencies: 623
- Published workflow dependencies: 572
- Structural validation: passed

## Mapping states

- `approved_h2kg`: an explicit reviewed mapping to an existing H2KG IRI.
- `reviewed_decode`: a reviewed DECODE anchor pending a future H2KG vocabulary decision.
- `unresolved`: retained without cross-workflow merging.

Raw GraphML files and the original attached manual JSON are not redistributed in this package. The sanitized overlay excludes personal names and email addresses. Normalized JSON, JSON-LD and Turtle projections preserve source node IDs and directed dependencies for review and reuse.

`decode_manual_reconciliation.json` and `.csv` document duplicate handling, identifier correction, existing-workflow reconciliation, retained GraphML workflows, and the 16 new manual-source workflows. `decode_workflow_dependencies.*` publishes only reciprocal or exact-handoff-grounded method dependencies; unsupported one-sided declarations remain audit-only.

`decode_duplicate_occurrence_audit.csv` documents every repeated source label within a workflow. `decode_semantic_role_conflicts.csv` records any incompatible roles assigned to a shared anchor and causes validation to fail. The semantic overview is a derived visualization only: every aggregate edge records the exact preserved source-dependency IDs it represents.

`decode_edge_registry.csv` classifies every source dependency as `h2kg_direct`, `h2kg_reified`, `prov_derivation`, or `decode_structural_only`. Source dependencies are never relabelled or removed. A semantic projection may reverse direction where required by H2KG, and `DataPoint` proxies are created only for property-valued workflow variables.

`decode_definition_drafts.csv`, `.json`, and `.md` provide domain-aware definition drafts for every distinct DECODE source concept. They are explicitly marked `needs_human_review`; they do not assert H2KG definitions or approve vocabulary additions.

`decode-h2kg-aligned-ontology.ttl` and `.jsonld` contain the complete merged DECODE vocabulary and workflow occurrence graph. Reviewed DECODE anchors are OWL classes under compatible H2KG roles, while source occurrences and reified source edges preserve the original workflow topology. Definitions in this module are marked `expert-draft`. DECODE licensing remains pending governance confirmation, so no open reuse license is asserted for these files.
