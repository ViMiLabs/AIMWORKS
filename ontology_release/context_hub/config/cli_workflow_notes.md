# Context Hub CLI Workflow Notes

Use these as the expected operational steps when adopting Context Hub for H2KG.

## Installation

Install the Context Hub CLI in a Node.js-capable environment.

## Expected Operations

The upstream project describes a workflow based on:

- installing the CLI
- building a local content source
- searching entries
- retrieving a specific entry
- optionally annotating retrieved material

## H2KG Workflow

Recommended operator sequence:

1. install Context Hub CLI
2. build a local H2KG source from `ontology_release/context_hub/content/`
3. register or reference that built source in your local agent configuration
4. test retrieval with H2KG scope, class, property, alignment, validation, and release questions
5. only then connect it to a maintainer assistant or website assistant

## Stability Rule

Do not make ontology release CI depend on Context Hub being installed.

The ontology release pipeline and the Context Hub content pack should remain loosely coupled:

- ontology release pipeline is the publication path
- Context Hub pack is the retrieval and guidance layer
