# AIMWORKS

AIMWORKS contains the H2KG ontology release preparation pipeline and supporting release automation assets.

The ontology release package is located in `ontology_release/`.

Key entry points:

- `ontology_release/README.md`
- `ontology_release/src/aimworks_ontology_release/cli.py`
- `.github/workflows/ontology-release.yml`
- `.github/workflows/ontology-pages.yml`

To build the ontology release locally:

```powershell
cd ontology_release
python -m aimworks_ontology_release.cli release --input input/current_ontology.jsonld
```
