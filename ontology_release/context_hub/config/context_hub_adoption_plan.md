# Context Hub Adoption Plan

## Phase 1: Local Content Stabilization

- keep the content pack local to `ontology_release/context_hub/`
- review every entry for scope correctness
- validate that the content reflects the current H2KG release policy

## Phase 2: Local Build And Retrieval

- install Context Hub CLI in a Node.js environment
- build the local registry from this content pack
- connect a local coding agent or maintainer assistant to the built output
- test retrieval against real H2KG maintenance questions

## Phase 3: Workflow Integration

- add an optional workflow that rebuilds Context Hub content when ontology docs change
- treat the pack as documentation source, not as release-critical infrastructure
- keep ontology release CI independent so a Context Hub issue cannot block ontology publication

## Phase 4: Website Assistant Integration

- connect an AI assistant on the H2KG website only after retrieval quality is stable
- constrain the assistant to this pack plus generated release docs
- do not let the assistant answer from unrelated AIMWORKS material by default
