from __future__ import annotations

import json
from pathlib import Path

from aimworks_ontology_release.afm_pilot import REQUIRED_LOCAL_TERMS, build_afm_pilot_package
from aimworks_ontology_release.io import load_json_document, merge_document_items


def _write_jsonld(path: Path, payload: list[dict]) -> Path:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def test_afm_pilot_package_generates_outputs(tmp_path: Path):
    payload = [
        {"@id": "https://w3id.org/h2kg/hydrogen-ontology", "@type": ["http://www.w3.org/2002/07/owl#Ontology"]},
        *({"@id": iri, "@type": ["http://www.w3.org/2002/07/owl#Thing"]} for iri in sorted(REQUIRED_LOCAL_TERMS)),
    ]
    source = _write_jsonld(tmp_path / "afm_source.jsonld", payload)
    output_root = tmp_path / "output"
    output_root.mkdir()

    summary = build_afm_pilot_package(source, output_root)

    assert summary["status"] == "generated"
    target_dir = output_root / "examples" / "afm_pilot"
    assert (target_dir / "afm_mapping_matrix.csv").exists()
    assert (target_dir / "afm_example.jsonld").exists()
    assert (target_dir / "afm_validation_note.md").exists()
    assert (target_dir / "afm_manuscript_figure.md").exists()
    assert (target_dir / "afm_manuscript_table.md").exists()

    csv_text = (target_dir / "afm_mapping_matrix.csv").read_text(encoding="utf-8")
    assert "char,MeasurementMethod,AFM,reuse existing term,h2kg:AtomicForceMicroscopyMeasurement" in csv_text
    assert "inst,ScanSpeed,0.488,new ontology term,h2kg:AFMScanSpeed" in csv_text
    assert "inst,NominalRadius,1,new ontology term,h2kg:AFMTipNominalRadius" in csv_text
    assert "anal,Step 1 Target,Average size,reuse existing term,h2kg:MeanParticleSize" in csv_text

    payload = json.loads((target_dir / "afm_example.jsonld").read_text(encoding="utf-8"))
    items = payload["@graph"]

    measurement = next(item for item in items if item["@id"].endswith("afm-measurement-001"))
    assert "https://w3id.org/h2kg/hydrogen-ontology#AtomicForceMicroscopyMeasurement" in measurement["@type"]

    instrument = next(item for item in items if item["@id"].endswith("afm-instrument-001"))
    assert "https://w3id.org/h2kg/hydrogen-ontology#AFMInstrument" in instrument["@type"]

    datapoint = next(item for item in items if item["@id"].endswith("mean-particle-size-datapoint"))
    assert datapoint["https://w3id.org/h2kg/hydrogen-ontology#ofProperty"][0]["@id"] == "https://w3id.org/h2kg/hydrogen-ontology#MeanParticleSize"

    analysis = next(item for item in items if item["@id"].endswith("manual-particle-measurement-step"))
    assert analysis["https://w3id.org/h2kg/hydrogen-ontology#usesInstrument"][0]["@id"] == "https://w3id.org/h2kg/hydrogen-ontology#FijiImageJSoftware"


def test_afm_pilot_package_skips_when_required_terms_are_missing(mini_ontology_file, tmp_path: Path):
    output_root = tmp_path / "output"
    output_root.mkdir()

    summary = build_afm_pilot_package(mini_ontology_file, output_root)

    assert summary["status"] == "skipped_missing_terms"
    assert (output_root / "examples" / "afm_pilot" / "README.md").exists()


def test_current_source_contains_afm_schema_updates():
    source = Path(__file__).resolve().parents[1] / "input" / "current_ontology.jsonld"
    merged = merge_document_items(load_json_document(source))
    by_id = {item["@id"]: item for item in merged if isinstance(item.get("@id"), str)}

    afm = by_id["https://w3id.org/h2kg/hydrogen-ontology#AtomicForceMicroscopyMeasurement"]

    afm_parameters = {
        entry["@id"] for entry in afm["https://w3id.org/h2kg/hydrogen-ontology#hasParameter"]
    }
    assert {
        "https://w3id.org/h2kg/hydrogen-ontology#Temperature",
        "https://w3id.org/h2kg/hydrogen-ontology#RelativeHumidity",
        "https://w3id.org/h2kg/hydrogen-ontology#MicroscopyMeasuredArea",
        "https://w3id.org/h2kg/hydrogen-ontology#AFMScanSpeed",
        "https://w3id.org/h2kg/hydrogen-ontology#AFMTipNominalRadius",
        "https://w3id.org/h2kg/hydrogen-ontology#CantileverSpringConstant",
        "https://w3id.org/h2kg/hydrogen-ontology#CantileverResonanceFrequency",
    }.issubset(afm_parameters)

    afm_outputs = {
        entry["@id"] for entry in afm["https://w3id.org/h2kg/hydrogen-ontology#hasOutputData"]
    }
    assert {
        "https://w3id.org/h2kg/hydrogen-ontology#SurfaceTopographyDataset",
        "https://w3id.org/h2kg/hydrogen-ontology#MicrostructureImageDataset",
    }.issubset(afm_outputs)

    afm_instruments = {
        entry["@id"] for entry in afm["https://w3id.org/h2kg/hydrogen-ontology#usesInstrument"]
    }
    assert "https://w3id.org/h2kg/hydrogen-ontology#AFMInstrument" in afm_instruments

    afm_inputs = {
        entry["@id"] for entry in afm["https://w3id.org/h2kg/hydrogen-ontology#hasInputMaterial"]
    }
    assert {
        "https://w3id.org/h2kg/hydrogen-ontology#MEAAssembly",
        "https://w3id.org/h2kg/hydrogen-ontology#CathodeCatalystLayer",
    }.issubset(afm_inputs)

    afm_properties = {
        entry["@id"] for entry in afm["https://w3id.org/h2kg/hydrogen-ontology#measures"]
    }
    assert "https://w3id.org/h2kg/hydrogen-ontology#MeanParticleSize" in afm_properties

    for iri in [
        "https://w3id.org/h2kg/hydrogen-ontology#AFMScanSpeed",
        "https://w3id.org/h2kg/hydrogen-ontology#AFMTipNominalRadius",
    ]:
        assert iri in by_id

    mean_particle_size = by_id["https://w3id.org/h2kg/hydrogen-ontology#MeanParticleSize"]
    description = mean_particle_size["http://purl.org/dc/terms/description"][0]["@value"].lower()
    assert "laser diffraction" in description
    assert "atomic force microscopy" in description
