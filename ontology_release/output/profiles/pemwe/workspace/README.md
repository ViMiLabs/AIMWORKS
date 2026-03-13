# AIMWORKS Ontology Release Pipeline

`ontology_release` is a self-contained release-preparation package for Hydrogen Technology ontology profiles. It currently supports both PEMFC and PEMWE application ontologies and publishes them through a shared switchable documentation site.

The package is intentionally conservative:

- It keeps the current ontology IRI `https://w3id.org/h2kg/hydrogen-ontology`.
- It preserves existing hash-style term IRIs unless configuration explicitly enables namespace migration.
- It separates schema, curated vocabulary-like terms, and example or data-like instances instead of silently rewriting or deleting them.
- It aligns local terms to EMMO, ECHO, QUDT, ChEBI, PROV-O, Dublin Core Terms, and VANN through a config-driven registry.

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

## Input File Update Flow

To publish future ontology versions, replace these files and rerun:

- `input/ONTOLOGY_PEMFC.jsonld`
- `input/ONTOLOGY_PEMWE.jsonld`

No code changes are needed for routine ontology content updates.

## Outputs

The pipeline writes reports, mappings, split ontology serializations, documentation, publication endpoints, w3id assets, review CSV files, and a release bundle under `output/`. Canonical release ontology files are also mirrored to `ontology/`.

## Publication Layout

The ECHO-style public publication tree is generated under `output/publication/`. It includes:

- `index.html` as the Hydrogen Technology profile selector
- `pemfc/` for the PEMFC profile publication site
- `pemwe/` for the PEMWE profile publication site

Each profile subtree contains:

- `hydrogen-ontology.html` as the single-page ontology reference
- `source/ontology.ttl` and `source/ontology.jsonld`
- `inferred/ontology.ttl`
- `latest/ontology.ttl`, `latest/ontology.jsonld`, `latest/inferred.ttl`, `latest/context.jsonld`
- versioned release directories
- `context/context.jsonld`

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
