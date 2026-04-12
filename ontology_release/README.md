# AIMWORKS Ontology Release Pipeline

`ontology_release/` is a self-contained release-preparation package for the H2KG Application Ontology for Hydrogen Electrochemical Systems. It treats the existing `h2kg` ontology as a conservative, EMMO-aligned application ontology spanning PEMFC and PEMWE experiments, measurements, materials, processes, data, provenance, and related FAIR release assets.

The package is designed to:

- inspect the current ontology and identify release blockers
- separate schema, curated vocabulary, and example or data-like content
- enrich metadata without breaking stable term IRIs
- propose conservative alignments to EMMO, ECHO, QUDT, ChEBI, PROV-O, and DCTERMS
- generate review artifacts for mappings and optional LLM-assisted annotations
- validate the ontology locally with SHACL and policy checks
- generate a polished static documentation site
- prepare w3id publication artifacts, GitHub Pages assets, and release bundles
- generate profile ontology modules for `pemfc` and `pemwe` without breaking shared `h2kg` term IRIs

## Scope

This pipeline is intentionally conservative:

- the ontology IRI remains `https://w3id.org/h2kg/hydrogen-ontology` by default
- hash-style term IRIs are preserved by default for backward compatibility
- local H2KG terms remain in the `h2kg` namespace unless an explicit migration policy is enabled
- the pipeline does not silently delete terms or rewrite unrelated repository content

## Quick Start

Create an environment with Python 3.11+ and install dependencies:

```bash
pip install -r requirements.txt
```

Run the end-to-end release preparation flow:

```bash
python -m aimworks_ontology_release.cli run --input input/current_ontology.jsonld --rewrite --split --build-docs --build-release --fair-check
```

Build profile-specific ontology modules directly:

```bash
python -m aimworks_ontology_release.cli profiles --input input/current_ontology.jsonld
```

This writes:

- `output/ontology/core_schema.ttl` and `.jsonld`
- `output/ontology/pemfc_schema.ttl` and `.jsonld`
- `output/ontology/pemwe_schema.ttl` and `.jsonld`
- `output/reports/profile_module_report.md` and `.json`

## Detailed Coding Plan

1. Inspect the current ontology.
   - parse the source ontology into raw JSON-LD and RDF views
   - identify ontology header metadata, namespace usage, duplicate nodes, imports, schema coverage, and likely FAIR blockers
   - emit machine-readable and markdown inspection reports

2. Classify resources conservatively.
   - distinguish ontology header, schema classes, object properties, datatype properties, annotation properties, controlled vocabulary terms, example individuals, quantity-value nodes, and ephemeral data-like instances
   - keep the heuristics config-driven and reviewable

3. Split the ontology into release modules.
   - write `schema.ttl` and `schema.jsonld` for the TBox-centric release module
   - write `controlled_vocabulary.ttl` for curated domain vocabulary
   - write `examples.ttl` for example and data-like content
   - produce a split report that explains why resources landed in each module

4. Build an external source index and propose mappings.
   - load configured source ontologies or cached exports if available
   - reuse existing QUDT, PROV-O, DCTERMS, and W3C terms when already present
   - score lexical and contextual candidates conservatively
   - emit review CSVs and RDF mapping graphs without deleting local terms

5. Enrich ontology metadata and local schema annotations.
   - preserve valid existing metadata
   - add missing labels, comments, definitions, versioning, `rdfs:isDefinedBy`, and namespace metadata
   - normalize language tags and release metadata

6. Support optional LLM-assisted annotation drafting.
   - keep it off by default
   - cache prompts and responses locally
   - produce CSV and JSONL drafts that require explicit human approval before application

7. Validate release readiness.
   - run syntax, metadata, mapping-sanity, import, namespace, annotation, and SHACL checks
   - optionally use `pyshacl` and any installed ontology QA tools

8. Generate docs, FAIR reports, and publication assets.
   - build a static HTML site suitable for GitHub Pages
   - write FAIR and release-readiness reports
   - generate w3id redirect templates and release bundle contents

9. Automate repository publication.
   - provide GitHub workflow templates for release validation and GitHub Pages deployment
   - keep ontology-specific logic in this folder and only mirror the minimal workflows to repository root
