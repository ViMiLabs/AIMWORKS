from __future__ import annotations

import csv
import json
from pathlib import Path

from aimworks_ontology_release.io import load_json_document, merge_document_items
from aimworks_ontology_release.synchrotron_xray_tomo_pilot import (
    REQUIRED_LOCAL_TERMS,
    build_synchrotron_xray_tomo_pilot_package,
)


def _write_jsonld(path: Path, payload: list[dict]) -> Path:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def test_synchrotron_xray_tomo_pilot_package_generates_outputs(tmp_path: Path):
    payload = [
        {"@id": "https://w3id.org/h2kg/hydrogen-ontology", "@type": ["http://www.w3.org/2002/07/owl#Ontology"]},
        *({"@id": iri, "@type": ["http://www.w3.org/2002/07/owl#Thing"]} for iri in sorted(REQUIRED_LOCAL_TERMS)),
    ]
    source = _write_jsonld(tmp_path / "synchrotron_xray_tomo_source.jsonld", payload)
    output_root = tmp_path / "output"
    output_root.mkdir()

    summary = build_synchrotron_xray_tomo_pilot_package(source, output_root)

    assert summary["status"] == "generated"
    target_dir = output_root / "examples" / "synchrotron_xray_tomo_pilot"
    assert (target_dir / "synchrotron_xray_tomo_mapping_matrix.csv").exists()
    assert (target_dir / "synchrotron_xray_tomo_example.jsonld").exists()
    assert (target_dir / "synchrotron_xray_tomo_validation_note.md").exists()
    assert (target_dir / "synchrotron_xray_tomo_manuscript_figure.md").exists()
    assert (target_dir / "synchrotron_xray_tomo_manuscript_table.md").exists()

    csv_rows = list(csv.DictReader((target_dir / "synchrotron_xray_tomo_mapping_matrix.csv").read_text(encoding="utf-8").splitlines()))
    assert any(
        row["source_sheet"] == "SynchrotronTomo"
        and row["section"] == "char"
        and row["field"] == "MeasurementMethod"
        and row["example_value"] == "Synchrotron X-ray tomography"
        and row["classification"] == "reuse existing term"
        and row["h2kg_anchor"] == "h2kg:XRayComputedTomographyMeasurement"
        for row in csv_rows
    )
    assert any(
        row["source_sheet"] == "SynchrotronTomo"
        and row["section"] == "inst"
        and row["field"] == "NumberOfRadiograms"
        and row["example_value"] == "2000"
        and row["classification"] == "reuse existing term"
        and row["h2kg_anchor"] == "h2kg:ProjectionNumber"
        for row in csv_rows
    )
    assert any(
        row["source_sheet"] == "SynchrotronTomo"
        and row["section"] == "anal"
        and row["field"] == "Step 3"
        and row["example_value"] == "ElectrolyteSaturationMeasurement -> Electrolyte saturation = 47 mol/l"
        and row["classification"] == "instance metadata"
        and row["h2kg_anchor"] == "h2kg:DataPoint + h2kg:Metadata"
        for row in csv_rows
    )
    assert any(
        row["source_sheet"] == "SynchrotronRadio"
        and row["section"] == "org"
        and row["field"] == "Topic"
        and row["example_value"] == "Battery"
        and row["classification"] == "instance metadata"
        and row["h2kg_anchor"] == "h2kg:hasMetadata"
        for row in csv_rows
    )

    payload = json.loads((target_dir / "synchrotron_xray_tomo_example.jsonld").read_text(encoding="utf-8"))
    items = payload["@graph"]

    measurement = next(item for item in items if item["@id"].endswith("xrayct-measurement-001"))
    assert "https://w3id.org/h2kg/hydrogen-ontology#XRayComputedTomographyMeasurement" in measurement["@type"]

    instrument = next(item for item in items if item["@id"].endswith("xrayct-instrument-001"))
    assert "https://w3id.org/h2kg/hydrogen-ontology#XRayCTInstrument" in instrument["@type"]

    reconstructed = next(item for item in items if item["@id"].endswith("reconstructed-tomograph-dataset"))
    assert "https://w3id.org/h2kg/hydrogen-ontology#TomographicReconstructionDataset" in reconstructed["@type"]

    deferred = next(item for item in items if item["@id"].endswith("electrolyte-saturation-datapoint-metadata"))
    assert "Deferred semantic target only: Electrolyte saturation" in deferred["http://www.w3.org/2000/01/rdf-schema#comment"][0]["@value"]


def test_synchrotron_xray_tomo_pilot_package_skips_when_required_terms_are_missing(mini_ontology_file, tmp_path: Path):
    output_root = tmp_path / "output"
    output_root.mkdir()

    summary = build_synchrotron_xray_tomo_pilot_package(mini_ontology_file, output_root)

    assert summary["status"] == "skipped_missing_terms"
    assert (output_root / "examples" / "synchrotron_xray_tomo_pilot" / "README.md").exists()


def test_current_source_contains_synchrotron_xray_tomo_schema_updates():
    source = Path(__file__).resolve().parents[1] / "input" / "current_ontology.jsonld"
    merged = merge_document_items(load_json_document(source))
    by_id = {item["@id"]: item for item in merged if isinstance(item.get("@id"), str)}

    measurement = by_id["https://w3id.org/h2kg/hydrogen-ontology#XRayComputedTomographyMeasurement"]

    parameters = {
        entry["@id"] for entry in measurement["https://w3id.org/h2kg/hydrogen-ontology#hasParameter"]
    }
    assert parameters == {
        "https://w3id.org/h2kg/hydrogen-ontology#XRayBeamEnergy",
        "https://w3id.org/h2kg/hydrogen-ontology#ExposureTime",
        "https://w3id.org/h2kg/hydrogen-ontology#PixelSize",
        "https://w3id.org/h2kg/hydrogen-ontology#ProjectionNumber",
        "https://w3id.org/h2kg/hydrogen-ontology#SpatialResolution",
        "https://w3id.org/h2kg/hydrogen-ontology#SampleDetectorDistance",
        "https://w3id.org/h2kg/hydrogen-ontology#Temperature",
        "https://w3id.org/h2kg/hydrogen-ontology#RelativeHumidity",
        "https://w3id.org/h2kg/hydrogen-ontology#Magnification",
    }

    outputs = {
        entry["@id"] for entry in measurement["https://w3id.org/h2kg/hydrogen-ontology#hasOutputData"]
    }
    assert outputs == {
        "https://w3id.org/h2kg/hydrogen-ontology#TomographicProjectionDataset",
        "https://w3id.org/h2kg/hydrogen-ontology#TomographicReconstructionDataset",
        "https://w3id.org/h2kg/hydrogen-ontology#ExperimentDataset",
    }

    instruments = {
        entry["@id"] for entry in measurement["https://w3id.org/h2kg/hydrogen-ontology#usesInstrument"]
    }
    assert instruments == {
        "https://w3id.org/h2kg/hydrogen-ontology#XRayCTInstrument",
    }

    assert "https://w3id.org/h2kg/hydrogen-ontology#hasInputMaterial" not in measurement
    assert "https://w3id.org/h2kg/hydrogen-ontology#measures" not in measurement

    description = measurement["http://purl.org/dc/terms/description"][0]["@value"].lower()
    assert "tomographic projections" in description
    assert "reconstructed volumes" in description

    instrument_description = by_id["https://w3id.org/h2kg/hydrogen-ontology#XRayCTInstrument"]["http://purl.org/dc/terms/description"][0]["@value"].lower()
    assert "synchrotron" in instrument_description
    assert "tomographic" in instrument_description

    projection_description = by_id["https://w3id.org/h2kg/hydrogen-ontology#TomographicProjectionDataset"]["http://purl.org/dc/terms/description"][0]["@value"].lower()
    assert "synchrotron x-ray tomography" in projection_description
    assert "neutron tomography" in projection_description

    reconstruction_description = by_id["https://w3id.org/h2kg/hydrogen-ontology#TomographicReconstructionDataset"]["http://purl.org/dc/terms/description"][0]["@value"].lower()
    assert "x-ray computed tomography" in reconstruction_description
    assert "neutron tomography" in reconstruction_description
