from __future__ import annotations

import json
from pathlib import Path

from aimworks_ontology_release.normalize_source import normalize_source_document
from aimworks_ontology_release.release import run_release


def test_release_runs_end_to_end(mini_ontology_file, tmp_path):
    project_root = tmp_path / "ontology_release"
    for relative in ["config", "output/ontology", "output/reports", "output/review", "output/mappings", "output/examples", "output/docs", "output/w3id", "output/odk"]:
        (project_root / relative).mkdir(parents=True, exist_ok=True)
    summary = run_release(mini_ontology_file, project_root, rewrite=True)
    assert summary["mappings"] >= 1
    assert summary["profile_modules"]["core_ontology_iri"] == "https://w3id.org/h2kg/hydrogen-ontology"
    assert (project_root / "output" / "docs" / "index.html").exists()
    assert (project_root / "output" / "docs" / "hydrogen-ontology.html").exists()
    assert (project_root / "output" / "docs" / "pages" / "quality-dashboard.html").exists()
    assert (project_root / "output" / "docs" / "pages" / "core-reference.html").exists()
    assert (project_root / "output" / "docs" / "pages" / "import-guide.html").exists()
    assert (project_root / "output" / "ontology" / "pemfc_schema.ttl").exists()
    assert (project_root / "output" / "ontology" / "pemwe_schema.ttl").exists()
    assert (project_root / "output" / "ontology" / "core_schema.ttl").exists()
    assert (project_root / "output" / "odk" / "manifest.json").exists()
    assert (project_root / "output" / "reports" / "hdo_alignment_report.json").exists()
    assert (project_root / "output" / "w3id" / "h2kg" / ".htaccess").exists()
    htaccess = (project_root / "output" / "w3id" / "h2kg" / ".htaccess").read_text(encoding="utf-8")
    assert "hydrogen-ontology.html" in htaccess
    assert "core_schema.ttl" in htaccess
    assert "pemfc_schema.ttl" in htaccess
    assert (project_root / "output" / "release_bundle" / "odk" / "manifest.json").exists()


def test_normalize_source_repairs_legacy_h2kg_refs(tmp_path):
    source_path = tmp_path / "source.jsonld"
    output_dir = tmp_path / "reports"
    source = {
        "@context": {"h2kg": "https://w3id.org/h2kg/hydrogen-ontology#"},
        "@graph": [
            {
                "@id": "https://w3id.org/h2kg/hydrogen-ontology#SomeMeasurement",
                "@type": ["https://w3id.org/h2kg/hydrogen-ontology#Measurement"],
                "https://w3id.org/h2kg/hydrogen-ontology#hasParameter": [
                    {"@id": "https://w3id.org/h2kg/hydrogen-ontology#Passes"}
                ],
                "https://w3id.org/h2kg/hydrogen-ontology#measures": [
                    {"@id": "https://w3id.org/h2kg/hydrogen-ontology#RotatingDiskVoltammetry"}
                ],
            },
            {
                "@id": "https://w3id.org/h2kg/hydrogen-ontology#NumberOfSprayPasses",
                "@type": ["https://w3id.org/h2kg/hydrogen-ontology#Parameter"],
            },
            {
                "@id": "https://w3id.org/h2kg/hydrogen-ontology#RotatingRingDiskVoltammetry",
                "@type": ["https://w3id.org/h2kg/hydrogen-ontology#Measurement"],
            },
        ],
    }
    source_path.write_text(json.dumps(source, indent=2), encoding="utf-8")

    report = normalize_source_document(source_path, output_dir, write_in_place=False)
    normalized = json.loads((output_dir / source_path.name).read_text(encoding="utf-8"))
    items = normalized["@graph"] if "@graph" in normalized else normalized
    text = json.dumps(items, ensure_ascii=False)

    assert report["repairs"]
    assert "https://w3id.org/h2kg/hydrogen-ontology#Passes" not in text
    assert "https://w3id.org/h2kg/hydrogen-ontology#RotatingDiskVoltammetry" not in text
    assert "https://w3id.org/h2kg/hydrogen-ontology#NumberOfSprayPasses" in text
    assert "https://w3id.org/h2kg/hydrogen-ontology#RotatingRingDiskVoltammetry" in text
    assert any(item.get("@id") == "https://w3id.org/h2kg/hydrogen-ontology#appliesToProfile" for item in items)
