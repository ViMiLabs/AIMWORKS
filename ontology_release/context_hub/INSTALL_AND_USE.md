# Install And Use Context Hub For H2KG

This file documents the intended adoption path for using Context Hub with AIMWORKS.

## Goal

Use Context Hub as the AI-facing retrieval layer for H2KG ontology documentation while keeping the generated static site as the public documentation surface.

## Installation Plan

1. Install the Context Hub CLI in a Node.js environment.
2. Build a local H2KG content registry from `ontology_release/context_hub/content/`.
3. Configure your coding agent or local tooling to use that built H2KG source.
4. Validate retrieval with typical maintainer questions before exposing it to end users.

## H2KG Usage Model

- Public website:
  - human-facing
  - polished
  - browseable class/property pages
  - FAIR and release reports

- Context Hub pack:
  - AI-facing
  - concise
  - retrieval-oriented
  - focused on modelling policy, alignments, release decisions, and common mistakes

## Validation Questions

Before relying on this pack, test whether an agent can answer these correctly from the local source:

- Is H2KG a broad hydrogen economy ontology?
- Should `Measurement` be deleted and replaced with an external class?
- When should QUDT be reused?
- What belongs in the schema module versus the examples module?
- Why are current `h2kg` hash IRIs preserved by default?
- What must be present before a release is published?

## Maintenance Rules

- When class/property policy changes, update the relevant Context Hub entry first.
- When release policy changes, update `h2kg-release-process` and `h2kg-iri-policy`.
- When mappings are reviewed, update `h2kg-alignments`.
- When validation rules change, update `h2kg-validation`.

## Non-Goals

- This pack does not replace the ontology release pipeline.
- This pack does not replace GitHub Pages docs.
- This pack does not publish RDF or HTML by itself.
- This pack should not become a raw dump of the ontology file.
