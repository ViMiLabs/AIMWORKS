from __future__ import annotations

import json
from pathlib import Path

from aimworks_ontology_release.io import load_json_document, merge_document_items
from aimworks_ontology_release.neutron_tomo_pilot import (
    REQUIRED_LOCAL_TERMS,
    build_neutron_tomo_pilot_package,
)


def _write_jsonld(path: Path, payload: list[dict]) -> Path:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def test_neutron_tomo_pilot_package_generates_outputs(tmp_path: Path):
    payload = [
        {"@id": "https://w3id.org/h2kg/hydrogen-ontology", "@type": ["http://www.w3.org/2002/07/owl#Ontology"]},
        *({"@id": iri, "@type": ["http://www.w3.org/2002/07/owl#Thing"]} for iri in sorted(REQUIRED_LOCAL_TERMS)),
    ]
    source = _write_jsonld(tmp_path / "neutron_tomo_source.jsonld", payload)
    output_root = tmp_path / "output"
    output_root.mkdir()

    summary = build_neutron_tomo_pilot_package(source, output_root)

    assert summary["status"] == "generated"
    target_dir = output_root / "examples" / "neutron_tomo_pilot"
    assert (target_dir / "neutron_tomo_mapping_matrix.csv").exists()
    assert (target_dir / "neutron_tomo_example.jsonld").exists()
    assert (target_dir / "neutron_tomo_validation_note.md").exists()
    assert (target_dir / "neutron_tomo_manuscript_figure.md").exists()
    assert (target_dir / "neutron_tomo_manuscript_table.md").exists()

    csv_text = (target_dir / "neutron_tomo_mapping_matrix.csv").read_text(encoding="utf-8")
    assert "char,MeasurementMethod,HR Neutron CT,new ontology term,h2kg:NeutronTomographyMeasurement" in csv_text
    assert "inst,ProjectionNumber,1440,new ontology term,h2kg:ProjectionNumber" in csv_text
    assert "anal,Step 3 Target,AverageArea,new ontology term,h2kg:AverageWaterDropletArea" in csv_text
    assert "anal,Step 2 Target,AverageBaryCenter,instance metadata,h2kg:Metadata" in csv_text

    payload = json.loads((target_dir / "neutron_tomo_example.jsonld").read_text(encoding="utf-8"))
    items = payload["@graph"]

    measurement = next(item for item in items if item["@id"].endswith("neutron-measurement-001"))
    assert "https://w3id.org/h2kg/hydrogen-ontology#NeutronTomographyMeasurement" in measurement["@type"]

    instrument = next(item for item in items if item["@id"].endswith("neutron-instrument-001"))
    assert "https://w3id.org/h2kg/hydrogen-ontology#NeutronTomographyInstrument" in instrument["@type"]

    area_datapoint = next(item for item in items if item["@id"].endswith("average-water-droplet-area-datapoint"))
    assert area_datapoint["https://w3id.org/h2kg/hydrogen-ontology#ofProperty"][0]["@id"] == "https://w3id.org/h2kg/hydrogen-ontology#AverageWaterDropletArea"

    analysis = next(item for item in items if item["@id"].endswith("analysis-step"))
    metadata_ids = {
        entry["@id"] for entry in analysis["https://w3id.org/h2kg/hydrogen-ontology#hasMetadata"]
    }
    assert any(identifier.endswith("average-barycenter-metadata") for identifier in metadata_ids)


def test_neutron_tomo_pilot_package_skips_when_required_terms_are_missing(mini_ontology_file, tmp_path: Path):
    output_root = tmp_path / "output"
    output_root.mkdir()

    summary = build_neutron_tomo_pilot_package(mini_ontology_file, output_root)

    assert summary["status"] == "skipped_missing_terms"
    assert (output_root / "examples" / "neutron_tomo_pilot" / "README.md").exists()


def test_current_source_contains_neutron_tomo_schema_updates():
    source = Path(__file__).resolve().parents[1] / "input" / "current_ontology.jsonld"
    merged = merge_document_items(load_json_document(source))
    by_id = {item["@id"]: item for item in merged if isinstance(item.get("@id"), str)}

    measurement = by_id["https://w3id.org/h2kg/hydrogen-ontology#NeutronTomographyMeasurement"]

    parameters = {
        entry["@id"] for entry in measurement["https://w3id.org/h2kg/hydrogen-ontology#hasParameter"]
    }
    assert {
        "https://w3id.org/h2kg/hydrogen-ontology#PixelSize",
        "https://w3id.org/h2kg/hydrogen-ontology#ExposureTime",
        "https://w3id.org/h2kg/hydrogen-ontology#ProjectionNumber",
        "https://w3id.org/h2kg/hydrogen-ontology#NeutronFlux",
        "https://w3id.org/h2kg/hydrogen-ontology#SpatialResolution",
        "https://w3id.org/h2kg/hydrogen-ontology#SampleDetectorDistance",
        "https://w3id.org/h2kg/hydrogen-ontology#Temperature",
        "https://w3id.org/h2kg/hydrogen-ontology#RelativeHumidity",
    }.issubset(parameters)

    outputs = {
        entry["@id"] for entry in measurement["https://w3id.org/h2kg/hydrogen-ontology#hasOutputData"]
    }
    assert {
        "https://w3id.org/h2kg/hydrogen-ontology#TomographicProjectionDataset",
        "https://w3id.org/h2kg/hydrogen-ontology#TomographicReconstructionDataset",
        "https://w3id.org/h2kg/hydrogen-ontology#ExperimentDataset",
    }.issubset(outputs)

    properties = {
        entry["@id"] for entry in measurement["https://w3id.org/h2kg/hydrogen-ontology#measures"]
    }
    assert {
        "https://w3id.org/h2kg/hydrogen-ontology#TortuosityFactor",
        "https://w3id.org/h2kg/hydrogen-ontology#AverageWaterDropletArea",
        "https://w3id.org/h2kg/hydrogen-ontology#AverageWaterDropletCount",
    }.issubset(properties)

    instruments = {
        entry["@id"] for entry in measurement["https://w3id.org/h2kg/hydrogen-ontology#usesInstrument"]
    }
    assert "https://w3id.org/h2kg/hydrogen-ontology#NeutronTomographyInstrument" in instruments

    inputs = {
        entry["@id"] for entry in measurement["https://w3id.org/h2kg/hydrogen-ontology#hasInputMaterial"]
    }
    assert "https://w3id.org/h2kg/hydrogen-ontology#MEAAssembly" in inputs

    for iri in [
        "https://w3id.org/h2kg/hydrogen-ontology#TomographicProjectionDataset",
        "https://w3id.org/h2kg/hydrogen-ontology#TomographicReconstructionDataset",
        "https://w3id.org/h2kg/hydrogen-ontology#ProjectionNumber",
        "https://w3id.org/h2kg/hydrogen-ontology#NeutronFlux",
        "https://w3id.org/h2kg/hydrogen-ontology#SpatialResolution",
        "https://w3id.org/h2kg/hydrogen-ontology#SampleDetectorDistance",
        "https://w3id.org/h2kg/hydrogen-ontology#TortuosityFactor",
        "https://w3id.org/h2kg/hydrogen-ontology#AverageWaterDropletArea",
        "https://w3id.org/h2kg/hydrogen-ontology#AverageWaterDropletCount",
    ]:
        assert iri in by_id

    description = by_id["https://w3id.org/h2kg/hydrogen-ontology#NeutronTomographyMeasurement"]["http://purl.org/dc/terms/description"][0]["@value"].lower()
    assert "neutron tomography" in description
    assert "fuel-cell water dynamics" in description
