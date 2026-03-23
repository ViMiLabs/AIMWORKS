# GitHub Pages Integration

The authoritative workflow sources live in `ontology_release/repo_root_integration/github_workflows/`.

Mirror these files to repository root as:

- `.github/workflows/ontology-release.yml`
- `.github/workflows/ontology-pages.yml`

They are intentionally minimal. All ontology-specific logic remains inside `ontology_release/`, and the workflows only:

1. install Python dependencies
2. run tests
3. build the ontology release outputs
4. upload artifacts or deploy `output/docs/` to GitHub Pages
