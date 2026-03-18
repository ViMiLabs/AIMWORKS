# AIMWORKS

AIMWORKS contains the H2KG ontology engineering and publication workflow for EMMO-aligned hydrogen electrochemical system ontologies.

The ontology release package lives in `ontology_release/` and now publishes:

- profile-based H2KG releases for PEMFC and PEMWE
- asserted and inferred ontology artifacts
- generated engineering modules and import-resolution catalog files
- static ontology portal pages for overview, releases, architecture, EMMO alignment, metrics, and developer guidance
- GitHub Actions automation for release bundling and Pages deployment

Key entry points:

- `ontology_release/README.md`
- `ontology_release/src/aimworks_ontology_release/cli.py`
- `.github/workflows/ontology-release.yml`
- `.github/workflows/ontology-pages.yml`

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
- reproducible release and Pages deployment via CI
