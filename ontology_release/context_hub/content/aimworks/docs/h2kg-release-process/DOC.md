# H2KG Release Process

This entry is the maintainer runbook for preparing an H2KG release.

## Step 1: Inspect

Run the ontology inspection step and review:

- ontology header status
- schema counts
- annotation coverage
- namespace usage
- FAIR blockers

## Step 2: Classify And Split

Separate resources into:

- schema
- controlled vocabulary
- examples or data-like content

Do not silently discard anything.

## Step 3: Review Alignments

Inspect mapping candidates and confirm:

- kind compatibility
- conservative relation choice
- rationale for each retained local term

## Step 4: Enrich Metadata

Add or normalize:

- ontology release metadata
- labels
- comments
- definitions
- `rdfs:isDefinedBy`

## Step 5: Optional Annotation Drafting

If using LLM-assisted drafts:

- keep drafting off by default
- generate drafts into review files
- require explicit approval before applying

## Step 6: Validate

Run syntax, policy, namespace, mapping, and SHACL checks.

## Step 7: Build Docs

Generate the static documentation site and review:

- overview pages
- class index
- property index
- alignment page
- examples page
- release page

## Step 8: Generate Publication Artifacts

Build:

- release bundle
- GitHub Pages content
- w3id redirect templates
- citation metadata

## Step 9: Publish

Publish documentation, preserve stable IRIs, and only then update public release references.
