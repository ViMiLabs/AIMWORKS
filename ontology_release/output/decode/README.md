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
- Classified source dependencies: 4276
- H2KG/PROV semantic projection triples: 5631
- Derived property-value DataPoint proxies: 551
- Structural validation: passed

## Mapping states

- `approved_h2kg`: an explicit reviewed mapping to an existing H2KG IRI.
- `reviewed_decode`: a reviewed DECODE anchor pending a future H2KG vocabulary decision.
- `unresolved`: retained without cross-workflow merging.

Raw GraphML files are not redistributed in this package. The normalized JSON, JSON-LD and Turtle projections preserve source node IDs and directed dependencies for review and reuse.

`decode_duplicate_occurrence_audit.csv` documents every repeated source label within a workflow. `decode_semantic_role_conflicts.csv` records any incompatible roles assigned to a shared anchor and causes validation to fail. The semantic overview is a derived visualization only: every aggregate edge records the exact preserved source-dependency IDs it represents.

`decode_edge_registry.csv` classifies every source dependency as `h2kg_direct`, `h2kg_reified`, `prov_derivation`, or `decode_structural_only`. Source dependencies are never relabelled or removed. A semantic projection may reverse direction where required by H2KG, and `DataPoint` proxies are created only for property-valued workflow variables.

`decode_definition_drafts.csv`, `.json`, and `.md` provide domain-aware definition drafts for every distinct DECODE source concept. They are explicitly marked `needs_human_review`; they do not assert H2KG definitions or approve vocabulary additions.
