# Repository Guide

## Purpose

This document describes how the AIMWORKS repository is organized and how the H2KG release pipeline works at the code level. It is intended for developers, ontology maintainers, and anyone updating the PEMFC or PEMWE profile inputs.

## Repository Model

The repository has a simple top-level split:

- `input/` contains the ontology source payloads used for publication.
- `ontology_release/` contains the Python package, configuration, templates, SHACL shapes, tests, and generated outputs.

The repository is not a general web application. The GitHub Pages site is generated from ontology data by the release package.

## Source Of Truth

Primary source files:

- `input/ONTOLOGY_PEMFC.jsonld`
- `input/ONTOLOGY_PEMWE.jsonld`
- `ontology_release/src/aimworks_ontology_release/`
- `ontology_release/config/`
- `ontology_release/templates/`
- `ontology_release/shapes/`

Generated files:

- `ontology_release/output/`
- `ontology_release/ontology/`

Anything under `output/` or `ontology/` can be regenerated and should not be treated as the editing surface for long-term maintenance.

## Package Structure

The main implementation lives in `ontology_release/src/aimworks_ontology_release/`.

Important modules:

| Module | Responsibility |
| --- | --- |
| `cli.py` | Typer-based command-line interface |
| `profiles.py` | Per-profile runtime setup and multi-profile orchestration |
| `release.py` | End-to-end build pipeline and artifact assembly |
| `inspect.py` | Graph inspection and ontology header discovery |
| `classify.py` | Term categorization and type-level classification |
| `split.py` | Separation into schema, controlled vocabulary, and examples |
| `mapper.py` | Alignment generation and mapping review output |
| `candidates.py`, `scorer.py` | Candidate retrieval and scoring for mappings |
| `enrich.py` | Metadata enrichment |
| `unit_enrichment.py` | Unit and quantity-kind enrichment from curated evidence |
| `quality.py` | JSON-LD cleanup, duplicate consolidation, alt-label filtering |
| `battinfo_overlap.py` | Secondary overlap analysis against BattINFO |
| `validate.py` | Validation logic, SHACL, resolver checks, OOPS!/FOOPS! integration hooks |
| `engineering.py` | Engineering summaries, module reports, alignment coverage data |
| `docs.py` | Static documentation generation and page data assembly |
| `publication.py` | Publication tree and JSON-LD context generation |
| `w3id.py` | Redirect-support assets for stable publication |

## Pipeline Stages

The CLI stages are thin wrappers over `run_pipeline()` in `release.py`.

| Stage | Main operations | Primary outputs |
| --- | --- | --- |
| `quality` | JSON-LD cleanup and BattINFO overlap analysis | `output/reports/term_quality_report.*`, BattINFO overlap reports |
| `inspect` | Parse, inspect, classify | `output/reports/inspection_report.*`, review CSV |
| `split` | Split into schema, vocabulary, examples | `output/ontology/`, `output/examples/`, split reports |
| `map` | Align local terms to configured sources | `output/mappings/alignments.ttl`, mapping review CSV/JSON |
| `enrich` / `units` | Add metadata and curated unit enrichment | metadata and unit enrichment reports |
| `annotate` | Draft and optionally apply annotation proposals | review CSV / JSONL artifacts |
| `validate` | Run local checks, SHACL, FAIR/OOPS!/FOOPS! hooks, resolver checks | validation reports |
| `docs` | Build docs, engineering reports, publication tree | `output/docs/`, `output/publication/` |
| `fair` | Compute FAIR reports after docs are built | FAIR reports |
| `release` | Full end-to-end release, including bundle assembly | `output/release_bundle/`, mirrored ontology artifacts |

## Profile System

Profiles are declared in `ontology_release/config/ontology_profiles.yaml`.

Current profiles:

- `pemfc`
- `pemwe`

For each profile, `profiles.py`:

1. Creates an isolated workspace under `output/profiles/<profile>/workspace`.
2. Copies configs, templates, shapes, and base metadata into that workspace.
3. Copies the selected profile input into `workspace/input/current_ontology.jsonld`.
4. Applies profile-specific config overrides.
5. Runs the pipeline in that workspace.
6. Copies the generated results back to `output/profiles/<profile>/`.
7. Reassembles combined `output/publication/` and `output/release_bundle/` trees.

This means the profile inputs in `input/` are the main authoring surface; the workspace copies are transient build products.

## Configuration

Important configuration files:

| File | Role |
| --- | --- |
| `config/release_profile.yaml` | Release metadata, publication options, validation settings |
| `config/ontology_profiles.yaml` | Profile list, profile labels, input paths, profile-specific overrides |
| `config/namespace_policy.yaml` | Ontology IRI, local namespace handling, active profile |
| `config/source_ontologies.yaml` | Mapping and import source registry |
| `config/mapping_rules.yaml` | Classification and mapping behavior |
| `config/metadata_defaults.yaml` | Default metadata applied during enrichment |
| `config/curated_units/pemfc_curated_units.csv` | Profile-specific curated units evidence |

## Validation Model

Validation is intentionally mixed:

- internal structural checks for metadata, mappings, and namespaces
- SHACL checks from `shapes/`
- optional external checks through OOPS! and FOOPS!
- optional resolver checks for publication IRIs

One important implementation detail: local editorial SHACL checks are scoped to local H2KG subjects in `validate.py`. Imported external ontology stubs are not used to fail local completeness rules. This avoids false-positive warnings caused by thin imported references that are not authored by H2KG.

## Documentation And Publication

The docs site is generated from templates in `ontology_release/templates/site/` and data assembled in `docs.py`.

Generated documentation includes:

- reference pages
- profile landing pages
- explorer pages
- quality and alignment dashboards
- release pages
- import and architecture pages

`build_publication_layout()` in `publication.py` assembles the GitHub Pages-ready tree in `output/publication/`.

## Testing

The repository currently has 14 pytest files under `ontology_release/tests/`.

The tests cover:

- profiles
- release orchestration
- docs generation
- mapping
- validation
- quality cleanup
- unit enrichment
- graph loading and extraction

Run the full suite from `ontology_release/`:

```bash
python -m pytest
```

## CI Workflows

### Ontology Release

`.github/workflows/ontology-release.yml`

- installs dependencies
- runs tests
- runs `python -m aimworks_ontology_release.cli release-all`
- uploads release bundle and publication site artifacts

### Ontology Pages

`.github/workflows/ontology-pages.yml`

- installs dependencies
- runs `python -m aimworks_ontology_release.cli docs-all`
- deploys `ontology_release/output/publication` to GitHub Pages

### Ontology GitHub Release

`.github/workflows/ontology-github-release.yml`

- runs tests
- builds `release-all`
- packages ZIP assets
- publishes versioned GitHub Releases for tags such as `v2026.3.0`

## Common Maintenance Tasks

### Update ontology content only

1. Edit `input/ONTOLOGY_PEMFC.jsonld` or `input/ONTOLOGY_PEMWE.jsonld`.
2. Run `python -m aimworks_ontology_release.cli release --profile <profile>`.
3. Review generated reports and docs.

### Update the docs UI

1. Edit templates in `ontology_release/templates/site/`.
2. Rebuild docs with `python -m aimworks_ontology_release.cli docs --profile <profile>`.

### Update pipeline behavior

1. Edit code in `ontology_release/src/aimworks_ontology_release/`.
2. Update or add tests under `ontology_release/tests/`.
3. Run `python -m pytest`.
4. Rebuild the affected profile or all profiles.

## Operational Notes

- The pipeline automatically cleans JSON-LD inputs before graph parsing. Duplicate `_2` style terms and noisy value-like `skos:altLabel` content are handled in this quality layer.
- BattINFO is used as a comparison and overlap-analysis source, not as a primary imported ontology in the release model.
- The public docs are generated artifacts. If the published Pages content looks stale, the issue is usually in the build workflow or generated outputs, not in the HTML under `output/` alone.
- Profile-specific runtime workspaces are disposable build directories.

## Suggested Reading Order

For a new maintainer:

1. `README.md`
2. `ontology_release/README.md`
3. `ontology_release/config/ontology_profiles.yaml`
4. `ontology_release/src/aimworks_ontology_release/cli.py`
5. `ontology_release/src/aimworks_ontology_release/release.py`
6. `ontology_release/src/aimworks_ontology_release/profiles.py`

That path gives the clearest view of how the repository is intended to be operated.
