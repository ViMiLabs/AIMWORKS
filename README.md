# AIMWORKS

AIMWORKS contains the H2KG ontology engineering and publication workflow for EMMO-aligned hydrogen electrochemical system ontologies.

The ontology release package lives in `ontology_release/` and now publishes:

- profile-based H2KG releases for PEMFC and PEMWE
- asserted and inferred ontology artifacts
- generated engineering modules and import-resolution catalog files
- static ontology portal pages for overview, releases, architecture, EMMO alignment, metrics, and developer guidance
- GitHub Actions automation for release bundling, Pages deployment, and tagged GitHub Releases

Key entry points:

- `ontology_release/README.md`
- `ontology_release/src/aimworks_ontology_release/cli.py`
- `.github/workflows/ontology-release.yml`
- `.github/workflows/ontology-pages.yml`
- `.github/workflows/ontology-github-release.yml`

## Live Portal

- H2KG profile selector: `https://vimilabs.github.io/AIMWORKS/`
- PEMFC portal: `https://vimilabs.github.io/AIMWORKS/pemfc/`
- PEMWE portal: `https://vimilabs.github.io/AIMWORKS/pemwe/`
- GitHub Releases: `https://github.com/ViMiLabs/AIMWORKS/releases`

## Stable and Machine-Readable Access

Current live publication downloads are exposed through GitHub Pages per profile. The preferred stable ontology IRI pattern remains:

- `https://w3id.org/h2kg/hydrogen-ontology`
- `https://w3id.org/h2kg/hydrogen-ontology/source`
- `https://w3id.org/h2kg/hydrogen-ontology/inferred`
- `https://w3id.org/h2kg/hydrogen-ontology/latest`
- `https://w3id.org/h2kg/hydrogen-ontology/context`

Representative current live downloads:

| Profile | Artifact | URL |
| --- | --- | --- |
| PEMFC | Reference page | `https://vimilabs.github.io/AIMWORKS/pemfc/hydrogen-ontology.html` |
| PEMFC | Merged asserted TTL | `https://vimilabs.github.io/AIMWORKS/pemfc/source/asserted.ttl` |
| PEMFC | Full inferred TTL | `https://vimilabs.github.io/AIMWORKS/pemfc/inferred/full_inferred.ttl` |
| PEMFC | Context JSON-LD | `https://vimilabs.github.io/AIMWORKS/pemfc/context/context.jsonld` |
| PEMWE | Reference page | `https://vimilabs.github.io/AIMWORKS/pemwe/hydrogen-ontology.html` |
| PEMWE | Merged asserted TTL | `https://vimilabs.github.io/AIMWORKS/pemwe/source/asserted.ttl` |
| PEMWE | Full inferred TTL | `https://vimilabs.github.io/AIMWORKS/pemwe/inferred/full_inferred.ttl` |
| PEMWE | Context JSON-LD | `https://vimilabs.github.io/AIMWORKS/pemwe/context/context.jsonld` |

## Local Build

```powershell
cd ontology_release
python -m pip install -r requirements.txt
python -m pip install -e .
python -m aimworks_ontology_release.cli release-all
```

## Main Outputs

After a build, the main outputs are written under `ontology_release/output/`:

- `ontology/` for asserted, inferred, module, context, and catalog artifacts
- `docs/` for the generated HTML portal
- `publication/` for the GitHub Pages-ready publication tree
- `release_bundle/` for the packaged release artifact
- `reports/` for metrics, validation, FAIR, module, and engineering summaries

## Publication Model

H2KG stays a focused EMMO-based hydrogen/PEMFC application ontology. The repository adopts BattINFO-like engineering discipline without expanding H2KG into a broad battery ontology:

- generated asserted vs inferred releases
- generated module views over local H2KG content
- explicit TBox/ABox separation in the public workflow
- static JSON indexes for search and tables
- reproducible release, Pages deployment, and GitHub Release asset publishing via CI
