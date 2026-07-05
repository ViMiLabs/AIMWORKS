from __future__ import annotations

import json
from pathlib import Path

from aimworks_ontology_release.io import load_json_document, merge_document_items
from aimworks_ontology_release.sem_pilot import build_sem_pilot_package


def _write_jsonld(path: Path, payload: list[dict]) -> Path:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def test_sem_pilot_package_generates_outputs(tmp_path: Path):
    source = _write_jsonld(
        tmp_path / "sem_source.jsonld",
        [
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology", "@type": ["http://www.w3.org/2002/07/owl#Ontology"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#Process", "@type": ["http://www.w3.org/2002/07/owl#Class"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#Manufacturing", "@type": ["http://www.w3.org/2002/07/owl#Class"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#Measurement", "@type": ["http://www.w3.org/2002/07/owl#Class"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#Instrument", "@type": ["http://www.w3.org/2002/07/owl#Class"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#Matter", "@type": ["http://www.w3.org/2002/07/owl#Class"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#Parameter", "@type": ["http://www.w3.org/2002/07/owl#Class"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#Data", "@type": ["http://www.w3.org/2002/07/owl#Class"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#DataPoint", "@type": ["http://www.w3.org/2002/07/owl#Class"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#Metadata", "@type": ["http://www.w3.org/2002/07/owl#Class"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#hasMetadata", "@type": ["http://www.w3.org/2002/07/owl#ObjectProperty"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#hasParameter", "@type": ["http://www.w3.org/2002/07/owl#ObjectProperty"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#usesInstrument", "@type": ["http://www.w3.org/2002/07/owl#ObjectProperty"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#hasInputMaterial", "@type": ["http://www.w3.org/2002/07/owl#ObjectProperty"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#hasOutputMaterial", "@type": ["http://www.w3.org/2002/07/owl#ObjectProperty"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#hasInputData", "@type": ["http://www.w3.org/2002/07/owl#ObjectProperty"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#hasOutputData", "@type": ["http://www.w3.org/2002/07/owl#ObjectProperty"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#hasQuantityValue", "@type": ["http://www.w3.org/2002/07/owl#ObjectProperty"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#ofProperty", "@type": ["http://www.w3.org/2002/07/owl#ObjectProperty"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#fromMeasurement", "@type": ["http://www.w3.org/2002/07/owl#ObjectProperty"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#hasPart", "@type": ["http://www.w3.org/2002/07/owl#ObjectProperty"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#hasIdentifier", "@type": ["http://www.w3.org/2002/07/owl#DatatypeProperty"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#AcceleratingVoltage", "@type": ["https://w3id.org/h2kg/hydrogen-ontology#Parameter"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#Magnification", "@type": ["https://w3id.org/h2kg/hydrogen-ontology#Parameter"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#WorkingDistance", "@type": ["https://w3id.org/h2kg/hydrogen-ontology#Parameter"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#Temperature", "@type": ["https://w3id.org/h2kg/hydrogen-ontology#Parameter"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#RelativeHumidity", "@type": ["https://w3id.org/h2kg/hydrogen-ontology#Parameter"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#DryingTemperature", "@type": ["https://w3id.org/h2kg/hydrogen-ontology#Parameter"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#DryingTime", "@type": ["https://w3id.org/h2kg/hydrogen-ontology#Parameter"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#SputterCoating", "@type": ["https://w3id.org/h2kg/hydrogen-ontology#Manufacturing"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#SEMInstrument", "@type": ["https://w3id.org/h2kg/hydrogen-ontology#Instrument"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#FijiImageJSoftware", "@type": ["https://w3id.org/h2kg/hydrogen-ontology#Instrument"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#ScanningElectronMicroscopyImaging", "@type": ["https://w3id.org/h2kg/hydrogen-ontology#Measurement"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#SEMImageDataset", "@type": ["https://w3id.org/h2kg/hydrogen-ontology#Data"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#SEMMicrographDataset", "@type": ["https://w3id.org/h2kg/hydrogen-ontology#Data"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#MicrostructureImageDataset", "@type": ["https://w3id.org/h2kg/hydrogen-ontology#Data"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#CatalystParticleDiameter", "@type": ["https://w3id.org/h2kg/hydrogen-ontology#Property"]},
        ],
    )
    output_root = tmp_path / "output"
    output_root.mkdir()

    summary = build_sem_pilot_package(source, output_root)

    assert summary["status"] == "generated"
    target_dir = output_root / "examples" / "sem_pilot"
    assert (target_dir / "sem_mapping_matrix.csv").exists()
    assert (target_dir / "sem_pilot_example.jsonld").exists()
    assert (target_dir / "sem_validation_note.md").exists()

    csv_text = (target_dir / "sem_mapping_matrix.csv").read_text(encoding="utf-8")
    assert "inst,Magnification,250,reuse existing term,h2kg:Magnification" in csv_text

    payload = json.loads((target_dir / "sem_pilot_example.jsonld").read_text(encoding="utf-8"))
    items = payload["@graph"]
    datapoint = next(item for item in items if item["@id"].endswith("catalyst-particle-diameter-datapoint"))
    assert datapoint["https://w3id.org/h2kg/hydrogen-ontology#ofProperty"][0]["@id"] == "https://w3id.org/h2kg/hydrogen-ontology#CatalystParticleDiameter"
    assert "https://w3id.org/h2kg/hydrogen-ontology#hasQuantityValue" not in datapoint
    assert datapoint["http://www.w3.org/ns/prov#wasGeneratedBy"][0]["@id"].endswith("manual-particle-measurement-step")


def test_sem_pilot_package_skips_when_required_terms_are_missing(mini_ontology_file, tmp_path: Path):
    output_root = tmp_path / "output"
    output_root.mkdir()

    summary = build_sem_pilot_package(mini_ontology_file, output_root)

    assert summary["status"] == "skipped_missing_terms"
    assert (output_root / "examples" / "sem_pilot" / "README.md").exists()


def test_current_source_contains_sem_schema_updates():
    source = Path(__file__).resolve().parents[1] / "input" / "current_ontology.jsonld"
    merged = merge_document_items(load_json_document(source))
    by_id = {item["@id"]: item for item in merged if isinstance(item.get("@id"), str)}

    sem_general = by_id["https://w3id.org/h2kg/hydrogen-ontology#ScanningElectronMicroscopyImaging"]
    sem_general_parameters = {
        entry["@id"] for entry in sem_general["https://w3id.org/h2kg/hydrogen-ontology#hasParameter"]
    }
    assert {
        "https://w3id.org/h2kg/hydrogen-ontology#AcceleratingVoltage",
        "https://w3id.org/h2kg/hydrogen-ontology#Magnification",
        "https://w3id.org/h2kg/hydrogen-ontology#WorkingDistance",
        "https://w3id.org/h2kg/hydrogen-ontology#Temperature",
        "https://w3id.org/h2kg/hydrogen-ontology#RelativeHumidity",
    }.issubset(sem_general_parameters)
    sem_general_outputs = {
        entry["@id"] for entry in sem_general["https://w3id.org/h2kg/hydrogen-ontology#hasOutputData"]
    }
    assert {
        "https://w3id.org/h2kg/hydrogen-ontology#SEMImageDataset",
        "https://w3id.org/h2kg/hydrogen-ontology#SEMMicrographDataset",
        "https://w3id.org/h2kg/hydrogen-ontology#MicrostructureImageDataset",
    }.issubset(sem_general_outputs)

    sem_measurement = by_id["https://w3id.org/h2kg/hydrogen-ontology#SEMImagingMeasurement"]
    sem_measurement_parameters = {
        entry["@id"] for entry in sem_measurement["https://w3id.org/h2kg/hydrogen-ontology#hasParameter"]
    }
    assert "https://w3id.org/h2kg/hydrogen-ontology#Magnification" in sem_measurement_parameters
    assert "https://w3id.org/h2kg/hydrogen-ontology#WorkingDistance" in sem_measurement_parameters
    sem_measurement_properties = {
        entry["@id"] for entry in sem_measurement["https://w3id.org/h2kg/hydrogen-ontology#measures"]
    }
    assert "https://w3id.org/h2kg/hydrogen-ontology#CatalystParticleDiameter" in sem_measurement_properties

    sem_imaging = by_id["https://w3id.org/h2kg/hydrogen-ontology#SEMImaging"]
    sem_imaging_parameters = {
        entry["@id"] for entry in sem_imaging["https://w3id.org/h2kg/hydrogen-ontology#hasParameter"]
    }
    assert "https://w3id.org/h2kg/hydrogen-ontology#Magnification" in sem_imaging_parameters
    assert "https://w3id.org/h2kg/hydrogen-ontology#WorkingDistance" in sem_imaging_parameters

    magnification = by_id["https://w3id.org/h2kg/hydrogen-ontology#Magnification"]
    magnification_description = magnification["http://purl.org/dc/terms/description"][0]["@value"]
    assert "Scanning Electron Microscopy Imaging" in magnification_description

    working_distance = by_id["https://w3id.org/h2kg/hydrogen-ontology#WorkingDistance"]
    working_distance_description = working_distance["http://purl.org/dc/terms/description"][0]["@value"]
    assert "Scanning Electron Microscopy Imaging" in working_distance_description

    sem_dataset = by_id["https://w3id.org/h2kg/hydrogen-ontology#SEMImageDataset"]
    sem_dataset_description = sem_dataset["http://purl.org/dc/terms/description"][0]["@value"]
    assert "Scanning Electron Microscopy Imaging" in sem_dataset_description

    sem_micrograph = by_id["https://w3id.org/h2kg/hydrogen-ontology#SEMMicrographDataset"]
    sem_micrograph_description = sem_micrograph["http://purl.org/dc/terms/description"][0]["@value"]
    assert "Scanning Electron Microscopy Imaging" in sem_micrograph_description
