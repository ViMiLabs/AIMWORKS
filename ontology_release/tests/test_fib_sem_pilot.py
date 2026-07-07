from __future__ import annotations

import json
from pathlib import Path

from aimworks_ontology_release.fib_sem_pilot import REQUIRED_LOCAL_TERMS, build_fib_sem_pilot_package
from aimworks_ontology_release.io import load_json_document, merge_document_items


def _write_jsonld(path: Path, payload: list[dict]) -> Path:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def test_fib_sem_pilot_package_generates_outputs(tmp_path: Path):
    payload = [
        {"@id": "https://w3id.org/h2kg/hydrogen-ontology", "@type": ["http://www.w3.org/2002/07/owl#Ontology"]},
        *({"@id": iri, "@type": ["http://www.w3.org/2002/07/owl#Thing"]} for iri in sorted(REQUIRED_LOCAL_TERMS)),
    ]
    source = _write_jsonld(tmp_path / "fib_sem_source.jsonld", payload)
    output_root = tmp_path / "output"
    output_root.mkdir()

    summary = build_fib_sem_pilot_package(source, output_root)

    assert summary["status"] == "generated"
    target_dir = output_root / "examples" / "fib_sem_pilot"
    assert (target_dir / "fib_sem_mapping_matrix.csv").exists()
    assert (target_dir / "fib_sem_example.jsonld").exists()
    assert (target_dir / "fib_sem_validation_note.md").exists()

    csv_text = (target_dir / "fib_sem_mapping_matrix.csv").read_text(encoding="utf-8")
    assert "char,MeasurementMethod,FIB-SEM,reuse existing term,h2kg:FIBSEMTomographyMeasurement" in csv_text
    assert "inst,IonBeamCurrent,700 pA,new ontology term,h2kg:IonBeamCurrent" in csv_text

    payload = json.loads((target_dir / "fib_sem_example.jsonld").read_text(encoding="utf-8"))
    items = payload["@graph"]

    measurement = next(item for item in items if item["@id"].endswith("fib-sem-measurement-001"))
    assert "https://w3id.org/h2kg/hydrogen-ontology#FIBSEMTomographyMeasurement" in measurement["@type"]
    assert measurement["https://w3id.org/h2kg/hydrogen-ontology#usesInstrument"][0]["@id"].endswith("fib-sem-instrument-001")

    datapoint = next(item for item in items if item["@id"].endswith("constrictivity-datapoint"))
    assert datapoint["https://w3id.org/h2kg/hydrogen-ontology#ofProperty"][0]["@id"] == "https://w3id.org/h2kg/hydrogen-ontology#Constrictivity"
    assert datapoint["http://www.w3.org/ns/prov#wasGeneratedBy"][0]["@id"].endswith("constrictivity-step")

    assert any(item["@id"].endswith("volume-fraction-step") for item in items)
    assert not any(
        item.get("https://w3id.org/h2kg/hydrogen-ontology#ofProperty", [{}])[0].get("@id")
        == "https://w3id.org/h2kg/hydrogen-ontology#PoreVolumeFraction"
        for item in items
        if "https://w3id.org/h2kg/hydrogen-ontology#DataPoint" in item.get("@type", [])
    )


def test_fib_sem_pilot_package_skips_when_required_terms_are_missing(mini_ontology_file, tmp_path: Path):
    output_root = tmp_path / "output"
    output_root.mkdir()

    summary = build_fib_sem_pilot_package(mini_ontology_file, output_root)

    assert summary["status"] == "skipped_missing_terms"
    assert (output_root / "examples" / "fib_sem_pilot" / "README.md").exists()


def test_current_source_contains_fib_sem_schema_updates():
    source = Path(__file__).resolve().parents[1] / "input" / "current_ontology.jsonld"
    merged = merge_document_items(load_json_document(source))
    by_id = {item["@id"]: item for item in merged if isinstance(item.get("@id"), str)}

    fib_sem = by_id["https://w3id.org/h2kg/hydrogen-ontology#FIBSEMTomographyMeasurement"]

    fib_sem_parameters = {
        entry["@id"] for entry in fib_sem["https://w3id.org/h2kg/hydrogen-ontology#hasParameter"]
    }
    assert {
        "https://w3id.org/h2kg/hydrogen-ontology#Temperature",
        "https://w3id.org/h2kg/hydrogen-ontology#RelativeHumidity",
        "https://w3id.org/h2kg/hydrogen-ontology#VacuumChamberPressure",
        "https://w3id.org/h2kg/hydrogen-ontology#DwellTime",
        "https://w3id.org/h2kg/hydrogen-ontology#Magnification",
        "https://w3id.org/h2kg/hydrogen-ontology#VoxelSize",
        "https://w3id.org/h2kg/hydrogen-ontology#MicroscopyMeasuredArea",
        "https://w3id.org/h2kg/hydrogen-ontology#ExposureTime",
        "https://w3id.org/h2kg/hydrogen-ontology#IonBeamCurrent",
        "https://w3id.org/h2kg/hydrogen-ontology#IonBeamEnergy",
        "https://w3id.org/h2kg/hydrogen-ontology#ElectronCurrent",
        "https://w3id.org/h2kg/hydrogen-ontology#ElectronBeamEnergy",
        "https://w3id.org/h2kg/hydrogen-ontology#CutThickness",
        "https://w3id.org/h2kg/hydrogen-ontology#SliceNumber",
        "https://w3id.org/h2kg/hydrogen-ontology#StageTilt",
        "https://w3id.org/h2kg/hydrogen-ontology#TotalAcquisitionTime",
    }.issubset(fib_sem_parameters)

    fib_sem_properties = {
        entry["@id"] for entry in fib_sem["https://w3id.org/h2kg/hydrogen-ontology#measures"]
    }
    assert {
        "https://w3id.org/h2kg/hydrogen-ontology#PoreVolumeFraction",
        "https://w3id.org/h2kg/hydrogen-ontology#TotalPorosity",
        "https://w3id.org/h2kg/hydrogen-ontology#Constrictivity",
        "https://w3id.org/h2kg/hydrogen-ontology#GeodesicTortuosity",
    }.issubset(fib_sem_properties)

    fib_sem_outputs = {
        entry["@id"] for entry in fib_sem["https://w3id.org/h2kg/hydrogen-ontology#hasOutputData"]
    }
    assert {
        "https://w3id.org/h2kg/hydrogen-ontology#SEMImageDataset",
        "https://w3id.org/h2kg/hydrogen-ontology#MicrostructureImageDataset",
        "https://w3id.org/h2kg/hydrogen-ontology#PoreSizeDistributionDataset",
    }.issubset(fib_sem_outputs)

    fib_sem_instruments = {
        entry["@id"] for entry in fib_sem["https://w3id.org/h2kg/hydrogen-ontology#usesInstrument"]
    }
    assert "https://w3id.org/h2kg/hydrogen-ontology#FIBSEMInstrument" in fib_sem_instruments

    for iri in [
        "https://w3id.org/h2kg/hydrogen-ontology#FIBSEMInstrument",
        "https://w3id.org/h2kg/hydrogen-ontology#IonBeamCurrent",
        "https://w3id.org/h2kg/hydrogen-ontology#IonBeamEnergy",
        "https://w3id.org/h2kg/hydrogen-ontology#ElectronCurrent",
        "https://w3id.org/h2kg/hydrogen-ontology#ElectronBeamEnergy",
        "https://w3id.org/h2kg/hydrogen-ontology#CutThickness",
        "https://w3id.org/h2kg/hydrogen-ontology#SliceNumber",
        "https://w3id.org/h2kg/hydrogen-ontology#StageTilt",
        "https://w3id.org/h2kg/hydrogen-ontology#TotalAcquisitionTime",
        "https://w3id.org/h2kg/hydrogen-ontology#Constrictivity",
        "https://w3id.org/h2kg/hydrogen-ontology#GeodesicTortuosity",
    ]:
        assert iri in by_id

    pore_volume_fraction = by_id["https://w3id.org/h2kg/hydrogen-ontology#PoreVolumeFraction"]
    assert "https://w3id.org/h2kg/hydrogen-ontology#Parameter" in pore_volume_fraction["@type"]
