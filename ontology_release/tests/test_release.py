from __future__ import annotations

from pathlib import Path

from aimworks_ontology_release.release import run_release


def test_release_runs_end_to_end(mini_ontology_file, tmp_path):
    project_root = tmp_path / "ontology_release"
    for relative in ["config", "output/ontology", "output/reports", "output/review", "output/mappings", "output/examples", "output/docs", "output/w3id"]:
        (project_root / relative).mkdir(parents=True, exist_ok=True)
    summary = run_release(mini_ontology_file, project_root)
    assert summary["mappings"] >= 1
    assert summary["profile_modules"]["core_ontology_iri"] == "https://w3id.org/h2kg/hydrogen-ontology"
    assert (project_root / "output" / "docs" / "index.html").exists()
    assert (project_root / "output" / "docs" / "pages" / "quality-dashboard.html").exists()
    assert (project_root / "output" / "ontology" / "pemfc_schema.ttl").exists()
    assert (project_root / "output" / "ontology" / "pemwe_schema.ttl").exists()
