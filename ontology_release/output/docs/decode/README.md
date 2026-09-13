# DECODE Federated Workflow Layer

This release contains a normalized structural projection of DECODE GraphML workflows. It is a separate data layer aligned to H2KG; it does not change the H2KG ontology TBox or the TBox-only H2KG Explore page.

- Source workflows: 120
- Preserved source occurrences: 2951
- Preserved directed source dependencies: 3986
- Explicitly mapped occurrences: 2951
- Shared reviewed anchors: 522
- Semantic-overview nodes: 695
- Repeated source-concept groups: 293
- Semantic role conflicts: 0
- Structural validation: passed

## Mapping states

- `approved_h2kg`: an explicit reviewed mapping to an existing H2KG IRI.
- `reviewed_decode`: a reviewed DECODE anchor pending a future H2KG vocabulary decision.
- `unresolved`: retained without cross-workflow merging.

Raw GraphML files are not redistributed in this package. The normalized JSON, JSON-LD and Turtle projections preserve source node IDs and directed dependencies for review and reuse.

`decode_duplicate_occurrence_audit.csv` documents every repeated source label within a workflow. `decode_semantic_role_conflicts.csv` records any incompatible roles assigned to a shared anchor and causes validation to fail. The semantic overview is a derived visualization only: every aggregate edge records the exact preserved source-dependency IDs it represents.
