# Repository Integration Notes

The workflow files in `repo_root_integration/github_workflows/` are mirrored into the repository root under `.github/workflows/`.

- `ontology-release.yml` runs tests and builds the release bundle.
- `ontology-pages.yml` generates the static publication tree and deploys `ontology_release/output/publication/` with GitHub Pages.

The workflows assume the ontology source file is present at `ontology_release/input/current_ontology.jsonld`.
