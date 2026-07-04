from __future__ import annotations

import json
from pathlib import Path

from aimworks_ontology_release.io import load_json_document, merge_document_items
from aimworks_ontology_release.tem_pilot import build_tem_pilot_package


def _write_jsonld(path: Path, payload: list[dict]) -> Path:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def test_tem_pilot_package_generates_outputs(tmp_path: Path):
    source = _write_jsonld(
        tmp_path / "tem_source.jsonld",
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
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#VacuumChamberPressure", "@type": ["https://w3id.org/h2kg/hydrogen-ontology#Parameter"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#Sonication", "@type": ["https://w3id.org/h2kg/hydrogen-ontology#Manufacturing"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#SonicationTime", "@type": ["https://w3id.org/h2kg/hydrogen-ontology#Parameter"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#AcousticFrequency", "@type": ["https://w3id.org/h2kg/hydrogen-ontology#Parameter"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#DryingTime", "@type": ["https://w3id.org/h2kg/hydrogen-ontology#Parameter"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#TEMInstrument", "@type": ["https://w3id.org/h2kg/hydrogen-ontology#Instrument"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#Ultrasonicator", "@type": ["https://w3id.org/h2kg/hydrogen-ontology#Instrument"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#FijiImageJSoftware", "@type": ["https://w3id.org/h2kg/hydrogen-ontology#Instrument"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#TransmissionElectronMicroscopyImaging", "@type": ["https://w3id.org/h2kg/hydrogen-ontology#Measurement"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#MicrostructureImageDataset", "@type": ["https://w3id.org/h2kg/hydrogen-ontology#Data"]},
            {"@id": "https://w3id.org/h2kg/hydrogen-ontology#PdNanoparticleDiameter", "@type": ["https://w3id.org/h2kg/hydrogen-ontology#Property"]},
        ],
    )
    output_root = tmp_path / "output"
    output_root.mkdir()

    summary = build_tem_pilot_package(source, output_root)

    assert summary["status"] == "generated"
    target_dir = output_root / "examples" / "tem_pilot"
    assert (target_dir / "tem_mapping_matrix.csv").exists()
    assert (target_dir / "tem_pilot_example.jsonld").exists()
    assert (target_dir / "tem_validation_note.md").exists()

    csv_text = (target_dir / "tem_mapping_matrix.csv").read_text(encoding="utf-8")
    assert "inst,Magnification,140000,new ontology term,h2kg:Magnification" in csv_text

    payload = json.loads((target_dir / "tem_pilot_example.jsonld").read_text(encoding="utf-8"))
    items = payload["@graph"]
    datapoint = next(item for item in items if item["@id"].endswith("pd-nanoparticle-diameter-datapoint"))
    assert datapoint["https://w3id.org/h2kg/hydrogen-ontology#ofProperty"][0]["@id"] == "https://w3id.org/h2kg/hydrogen-ontology#PdNanoparticleDiameter"
    assert datapoint["http://www.w3.org/ns/prov#wasGeneratedBy"][0]["@id"].endswith("manual-particle-measurement-step")


def test_tem_pilot_package_skips_when_required_terms_are_missing(mini_ontology_file, tmp_path: Path):
    output_root = tmp_path / "output"
    output_root.mkdir()

    summary = build_tem_pilot_package(mini_ontology_file, output_root)

    assert summary["status"] == "skipped_missing_terms"
    assert (output_root / "examples" / "tem_pilot" / "README.md").exists()


def test_current_source_contains_tem_schema_updates():
    source = Path(__file__).resolve().parents[1] / "input" / "current_ontology.jsonld"
    merged = merge_document_items(load_json_document(source))
    by_id = {item["@id"]: item for item in merged if isinstance(item.get("@id"), str)}

    has_output_data = by_id["https://w3id.org/h2kg/hydrogen-ontology#hasOutputData"]
    assert has_output_data["http://www.w3.org/2000/01/rdf-schema#domain"][0]["@id"] == "https://w3id.org/h2kg/hydrogen-ontology#Process"

    has_metadata = by_id["https://w3id.org/h2kg/hydrogen-ontology#hasMetadata"]
    assert has_metadata["http://www.w3.org/2000/01/rdf-schema#range"][0]["@id"] == "https://w3id.org/h2kg/hydrogen-ontology#Metadata"

    assert "https://w3id.org/h2kg/hydrogen-ontology#Magnification" in by_id
    assert "https://w3id.org/h2kg/hydrogen-ontology#WorkingDistance" in by_id

    tem_measurement = by_id["https://w3id.org/h2kg/hydrogen-ontology#TransmissionElectronMicroscopyImaging"]
    tem_parameters = {
        entry["@id"] for entry in tem_measurement["https://w3id.org/h2kg/hydrogen-ontology#hasParameter"]
    }
    assert {
        "https://w3id.org/h2kg/hydrogen-ontology#AcceleratingVoltage",
        "https://w3id.org/h2kg/hydrogen-ontology#Magnification",
        "https://w3id.org/h2kg/hydrogen-ontology#WorkingDistance",
        "https://w3id.org/h2kg/hydrogen-ontology#Temperature",
        "https://w3id.org/h2kg/hydrogen-ontology#RelativeHumidity",
        "https://w3id.org/h2kg/hydrogen-ontology#VacuumChamberPressure",
    }.issubset(tem_parameters)

    accelerating_voltage = by_id["https://w3id.org/h2kg/hydrogen-ontology#AcceleratingVoltage"]
    accelerating_description = accelerating_voltage["http://purl.org/dc/terms/description"][0]["@value"]
    assert "Transmission Electron Microscopy Imaging" in accelerating_description

    magnification = by_id["https://w3id.org/h2kg/hydrogen-ontology#Magnification"]
    magnification_description = magnification["http://purl.org/dc/terms/description"][0]["@value"]
    assert "Transmission Electron Microscopy Imaging" in magnification_description

    working_distance = by_id["https://w3id.org/h2kg/hydrogen-ontology#WorkingDistance"]
    working_distance_description = working_distance["http://purl.org/dc/terms/description"][0]["@value"]
    assert "Transmission Electron Microscopy Imaging" in working_distance_description

    vacuum_pressure = by_id["https://w3id.org/h2kg/hydrogen-ontology#VacuumChamberPressure"]
    vacuum_description = vacuum_pressure["http://purl.org/dc/terms/description"][0]["@value"]
    assert "Transmission Electron Microscopy Imaging" in vacuum_description

    microstructure_dataset = by_id["https://w3id.org/h2kg/hydrogen-ontology#MicrostructureImageDataset"]
    description = microstructure_dataset["http://purl.org/dc/terms/description"][0]["@value"]
    assert "raw or processed microscopy images" in description
