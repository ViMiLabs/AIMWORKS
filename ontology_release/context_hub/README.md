# H2KG Context Hub Pack

This folder contains an AI-facing documentation pack for the H2KG PEMFC Catalyst Layer Application Ontology.

It is intended for:

- ontology maintainers
- coding agents
- release automation agents
- future H2KG website assistants or chat/help tools

It is not the public website. The public, human-facing documentation remains the generated site in:

- `ontology_release/output/docs/`

This pack is the curated source of truth for agent retrieval. It is deliberately shorter, more policy-focused, and more operational than the public docs site.

## Purpose

The pack exists so an agent can answer questions such as:

- What is in scope for H2KG?
- Which terms should remain local in the `h2kg` namespace?
- When should EMMO, ECHO, QUDT, ChEBI, PROV-O, or DCTERMS be reused?
- How should core classes and properties be used?
- What makes a term release-ready?
- What is the maintainer release workflow?

## Structure

- `config/`: local installation and build templates for Context Hub use in this repository
- `content/aimworks/docs/`: the actual H2KG content entries, following the author/docs/entry pattern

## Editorial Rules

- Keep entries concise and scoped to a single operational question.
- Prefer explicit policy over long narrative.
- State what H2KG is not as clearly as what it is.
- Distinguish schema, vocabulary, and examples.
- State when to keep terms local and when to reuse external ontologies.
- Update this pack whenever ontology modelling policy or release policy changes.

## Recommended Usage

1. Install Context Hub separately from the ontology release pipeline.
2. Build a local registry from this folder.
3. Point your agent tooling at the built local pack.
4. Use the public docs for humans and this pack for AI retrieval.
5. Keep both aligned during release preparation.
