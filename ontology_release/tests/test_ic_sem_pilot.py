from __future__ import annotations

import json
from pathlib import Path

from aimworks_ontology_release.ic_sem_pilot import REQUIRED_LOCAL_TERMS, build_ic_sem_pilot_package
from aimworks_ontology_release.io import load_json_document, merge_document_items


def _write_jsonld(path: Path, payload: list[dict]) -> Path:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def test_ic_sem_pilot_package_generates_outputs(tmp_path: Path):
    payload = [
        {"@id": "https://w3id.org/h2kg/hydrogen-ontology", "@type": ["http://www.w3.org/2002/07/owl#Ontology"]},
        *({"@id": iri, "@type": ["http://www.w3.org/2002/07/owl#Thing"]} for iri in sorted(REQUIRED_LOCAL_TERMS)),
    ]
    source = _write_jsonld(tmp_path / "ic_sem_source.jsonld", payload)
    output_root = tmp_path / "output"
    output_root.mkdir()

    summary = build_ic_sem_pilot_package(source, output_root)

    assert summary["status"] == "generated"
    target_dir = output_root / "examples" / "ic_sem_pilot"
    assert (target_dir / "ic_sem_mapping_matrix.csv").exists()
    assert (target_dir / "ic_sem_example.jsonld").exists()
    assert (target_dir / "ic_sem_validation_note.md").exists()
    assert (target_dir / "ic_sem_manuscript_figure.md").exists()
    assert (target_dir / "ic_sem_manuscript_table.md").exists()

    csv_text = (target_dir / "ic_sem_mapping_matrix.csv").read_text(encoding="utf-8")
    assert "char,MeasurementMethod,IC-SEM,reuse existing term,h2kg:ICSEMImagingMeasurement" in csv_text
    assert "inst,PixelSize,20 nm,new ontology term,h2kg:PixelSize" in csv_text
    assert "anal,Step 1 Target,MEA thickness,new ontology term,h2kg:MembraneElectrodeAssemblyThickness" in csv_text

    payload = json.loads((target_dir / "ic_sem_example.jsonld").read_text(encoding="utf-8"))
    items = payload["@graph"]

    measurement = next(item for item in items if item["@id"].endswith("ic-sem-measurement-001"))
    assert "https://w3id.org/h2kg/hydrogen-ontology#ICSEMImagingMeasurement" in measurement["@type"]

    instrument = next(item for item in items if item["@id"].endswith("ic-sem-instrument-001"))
    assert "https://w3id.org/h2kg/hydrogen-ontology#ICSEMInstrument" in instrument["@type"]

    mea_datapoint = next(item for item in items if item["@id"].endswith("mea-thickness-datapoint"))
    assert mea_datapoint["https://w3id.org/h2kg/hydrogen-ontology#ofProperty"][0]["@id"] == "https://w3id.org/h2kg/hydrogen-ontology#MembraneElectrodeAssemblyThickness"

    gdl_datapoint = next(item for item in items if item["@id"].endswith("gdl-thickness-datapoint"))
    assert gdl_datapoint["https://w3id.org/h2kg/hydrogen-ontology#ofProperty"][0]["@id"] == "https://w3id.org/h2kg/hydrogen-ontology#GasDiffusionLayerThickness"

    porosity_datapoint = next(item for item in items if item["@id"].endswith("total-porosity-datapoint"))
    assert porosity_datapoint["https://w3id.org/h2kg/hydrogen-ontology#ofProperty"][0]["@id"] == "https://w3id.org/h2kg/hydrogen-ontology#TotalPorosity"


def test_ic_sem_pilot_package_skips_when_required_terms_are_missing(mini_ontology_file, tmp_path: Path):
    output_root = tmp_path / "output"
    output_root.mkdir()

    summary = build_ic_sem_pilot_package(mini_ontology_file, output_root)

    assert summary["status"] == "skipped_missing_terms"
    assert (output_root / "examples" / "ic_sem_pilot" / "README.md").exists()


def test_current_source_contains_ic_sem_schema_updates():
    source = Path(__file__).resolve().parents[1] / "input" / "current_ontology.jsonld"
    merged = merge_document_items(load_json_document(source))
    by_id = {item["@id"]: item for item in merged if isinstance(item.get("@id"), str)}

    ic_sem = by_id["https://w3id.org/h2kg/hydrogen-ontology#ICSEMImagingMeasurement"]

    ic_sem_parameters = {
        entry["@id"] for entry in ic_sem["https://w3id.org/h2kg/hydrogen-ontology#hasParameter"]
    }
    assert {
        "https://w3id.org/h2kg/hydrogen-ontology#Temperature",
        "https://w3id.org/h2kg/hydrogen-ontology#RelativeHumidity",
        "https://w3id.org/h2kg/hydrogen-ontology#VacuumChamberPressure",
        "https://w3id.org/h2kg/hydrogen-ontology#DwellTime",
        "https://w3id.org/h2kg/hydrogen-ontology#Magnification",
        "https://w3id.org/h2kg/hydrogen-ontology#PixelSize",
        "https://w3id.org/h2kg/hydrogen-ontology#MicroscopyMeasuredArea",
        "https://w3id.org/h2kg/hydrogen-ontology#ExposureTime",
        "https://w3id.org/h2kg/hydrogen-ontology#IonBeamCurrent",
        "https://w3id.org/h2kg/hydrogen-ontology#IonBeamEnergy",
        "https://w3id.org/h2kg/hydrogen-ontology#ElectronCurrent",
        "https://w3id.org/h2kg/hydrogen-ontology#ElectronBeamEnergy",
        "https://w3id.org/h2kg/hydrogen-ontology#CutThickness",
        "https://w3id.org/h2kg/hydrogen-ontology#TotalAcquisitionTime",
    }.issubset(ic_sem_parameters)

    ic_sem_properties = {
        entry["@id"] for entry in ic_sem["https://w3id.org/h2kg/hydrogen-ontology#measures"]
    }
    assert {
        "https://w3id.org/h2kg/hydrogen-ontology#MembraneElectrodeAssemblyThickness",
        "https://w3id.org/h2kg/hydrogen-ontology#GasDiffusionLayerThickness",
        "https://w3id.org/h2kg/hydrogen-ontology#TotalPorosity",
    }.issubset(ic_sem_properties)

    ic_sem_outputs = {
        entry["@id"] for entry in ic_sem["https://w3id.org/h2kg/hydrogen-ontology#hasOutputData"]
    }
    assert {
        "https://w3id.org/h2kg/hydrogen-ontology#SEMImageDataset",
        "https://w3id.org/h2kg/hydrogen-ontology#SEMMicrographDataset",
        "https://w3id.org/h2kg/hydrogen-ontology#MicrostructureImageDataset",
    }.issubset(ic_sem_outputs)

    ic_sem_instruments = {
        entry["@id"] for entry in ic_sem["https://w3id.org/h2kg/hydrogen-ontology#usesInstrument"]
    }
    assert "https://w3id.org/h2kg/hydrogen-ontology#ICSEMInstrument" in ic_sem_instruments

    for iri in [
        "https://w3id.org/h2kg/hydrogen-ontology#ICSEMInstrument",
        "https://w3id.org/h2kg/hydrogen-ontology#MembraneElectrodeAssemblyThickness",
        "https://w3id.org/h2kg/hydrogen-ontology#PixelSize",
    ]:
        assert iri in by_id
