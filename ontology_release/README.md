# AIMWORKS Ontology Release Pipeline

`ontology_release` is a self-contained release-preparation package for the H2KG PEMFC Catalyst Layer Application Ontology. It upgrades the existing `h2kg` ontology into a FAIR-oriented, release-ready bundle while preserving current IRIs by default.

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
python -m aimworks_ontology_release.cli release --input input/current_ontology.jsonld
```

## Main Commands

```bash
python -m aimworks_ontology_release.cli inspect --input input/current_ontology.jsonld
python -m aimworks_ontology_release.cli split --input input/current_ontology.jsonld
python -m aimworks_ontology_release.cli map --input input/current_ontology.jsonld
python -m aimworks_ontology_release.cli enrich --input input/current_ontology.jsonld
python -m aimworks_ontology_release.cli annotate --input input/current_ontology.jsonld
python -m aimworks_ontology_release.cli docs --input input/current_ontology.jsonld
python -m aimworks_ontology_release.cli validate --input input/current_ontology.jsonld
python -m aimworks_ontology_release.cli fair --input input/current_ontology.jsonld
python -m aimworks_ontology_release.cli release --input input/current_ontology.jsonld
python -m aimworks_ontology_release.cli run --input input/current_ontology.jsonld --build-docs --build-release --fair-check
```

## Outputs

The pipeline writes reports, mappings, split ontology serializations, documentation, publication endpoints, w3id assets, review CSV files, and a release bundle under `output/`. Canonical release ontology files are also mirrored to `ontology/`.

## Publication Layout

The ECHO-style public publication tree is generated under `output/publication/`. It includes:

- `hydrogen-ontology.html` as the single-page ontology reference
- `source/ontology.ttl` and `source/ontology.jsonld`
- `inferred/ontology.ttl`
- `latest/ontology.ttl`, `latest/ontology.jsonld`, `latest/inferred.ttl`, `latest/context.jsonld`
- `2026.3.0/ontology.ttl`, `2026.3.0/ontology.jsonld`, `2026.3.0/inferred.ttl`, `2026.3.0/context.jsonld`
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
