# AIMWORKS Ontology Release Pipeline

`ontology_release` is the code-first ontology engineering and publication package for H2KG. It keeps H2KG focused as an EMMO-based hydrogen / PEMFC application ontology while adding a compact, BattINFO-inspired release workflow.

The package is intentionally conservative:

- It keeps the current ontology IRI `https://w3id.org/h2kg/hydrogen-ontology`.
- It preserves existing hash-style term IRIs unless configuration explicitly enables namespace migration.
- It separates schema, curated vocabulary-like terms, and example or data-like instances instead of silently rewriting or deleting them.
- It aligns local terms to EMMO, ECHO, QUDT, ChEBI, PROV-O, Dublin Core Terms, and VANN through a config-driven registry.
- It generates additive engineering artifacts and portal pages without breaking the existing release and Pages behavior.

## Quick Start

```bash
cd ontology_release
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pip install -e .
python -m aimworks_ontology_release.cli release-all
```

## Main Commands

```bash
python -m aimworks_ontology_release.cli profiles
python -m aimworks_ontology_release.cli release --profile pemfc
python -m aimworks_ontology_release.cli release --profile pemwe
python -m aimworks_ontology_release.cli docs --profile pemfc
python -m aimworks_ontology_release.cli validate --profile pemwe
python -m aimworks_ontology_release.cli release-all
python -m aimworks_ontology_release.cli docs-all
python -m aimworks_ontology_release.cli run --all-profiles --build-docs --build-release --fair-check
```

The release and docs commands also generate the engineering-facing artifacts described below. There is no separate manual documentation or packaging workflow.

## Engineering Workflow

H2KG now follows a compact asserted / inferred publication pattern inspired by BattINFO while staying scoped to hydrogen electrochemical systems.

Generated engineering outputs include:

- asserted source split:
  - `output/ontology/schema.ttl`
  - `output/ontology/controlled_vocabulary.ttl`
  - `output/examples/examples.ttl`
- merged asserted release:
  - `output/ontology/asserted.ttl`
  - `output/ontology/asserted.jsonld`
  - `output/ontology/asserted.rdf`
- inferred release:
  - `output/ontology/inferred.ttl`
  - `output/ontology/full_inferred.ttl`
  - `output/ontology/full_inferred.rdf`
- generated module views:
  - `output/ontology/modules/top.ttl`
  - `output/ontology/modules/core.ttl`
  - `output/ontology/modules/materials.ttl`
  - `output/ontology/modules/components_devices.ttl`
  - `output/ontology/modules/processes_manufacturing.ttl`
  - `output/ontology/modules/measurements_data.ttl`
  - `output/ontology/modules/mappings.ttl`
  - `output/ontology/modules/examples.ttl`
- local development import support:
  - `output/ontology/catalog-v001.xml`
- generated engineering reports:
  - `output/reports/module_index.json`
  - `output/reports/ontology_stats.json`
  - `output/reports/engineering_workflow.json`
  - `output/reports/emmo_alignment.json`

These module views are generated from the existing release flow to preserve backward compatibility with the current JSON-LD-first profile inputs.

## Input File Update Flow

To publish future ontology versions, replace these files and rerun:

- `input/ONTOLOGY_PEMFC.jsonld`
- `input/ONTOLOGY_PEMWE.jsonld`

No code changes are needed for routine ontology content updates.

## Outputs

The pipeline writes reports, mappings, split ontology serializations, documentation, publication endpoints, w3id assets, engineering reports, review CSV files, and a release bundle under `output/`. Canonical release ontology files are also mirrored to `ontology/`.

## Publication Layout

The public publication tree is generated under `output/publication/`. It includes:

- `index.html` as the Hydrogen Technology profile selector
- `pemfc/` for the PEMFC profile publication site
- `pemwe/` for the PEMWE profile publication site

Each profile subtree contains:

- `hydrogen-ontology.html` as the single-page ontology reference
- `source/ontology.ttl` and `source/ontology.jsonld`
- `source/asserted.ttl`, `source/asserted.jsonld`, and `source/asserted.rdf`
- `source/modules/` for generated engineering module views
- `source/catalog-v001.xml` for local import resolution
- `inferred/ontology.ttl`
- `inferred/full_inferred.ttl`
- `latest/ontology.ttl`, `latest/ontology.jsonld`, `latest/inferred.ttl`, `latest/context.jsonld`
- versioned release directories
- `context/context.jsonld`

The generated portal also includes additive ontology-engineering pages such as:

- `pages/get-started.html`
- `pages/architecture-workflow.html`
- `pages/emmo-alignment.html`
- `pages/module-index.html`
- `pages/metrics.html`
- `pages/developer-guide.html`
- `pages/h2kg-vs-battinfo.html`

## Reference IRIs

- `https://w3id.org/h2kg/hydrogen-ontology`
- `https://w3id.org/h2kg/hydrogen-ontology/source`
- `https://w3id.org/h2kg/hydrogen-ontology/inferred`
- `https://w3id.org/h2kg/hydrogen-ontology/latest`
- `https://w3id.org/h2kg/hydrogen-ontology/context`
- `https://w3id.org/h2kg/hydrogen-ontology/2026.3.0`
- `https://w3id.org/h2kg/hydrogen-ontology/2026.3.0/inferred`

## LLM Annotation Drafting

LLM support is optional and disabled by default. Without an LLM provider the package still produces deterministic heuristic annotation drafts for review.

## CI / Pages

Existing GitHub workflows continue to drive the release:

- `.github/workflows/ontology-release.yml` runs tests and `release-all`
- `.github/workflows/ontology-pages.yml` runs `docs-all` and deploys `output/publication/`
- `.github/workflows/ontology-github-release.yml` runs `release-all`, packages release assets, and publishes them to GitHub Releases for tags such as `v2026.3.0`

No manual post-processing step is required after the ontology build.
