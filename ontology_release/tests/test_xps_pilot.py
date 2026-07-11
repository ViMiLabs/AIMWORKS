from __future__ import annotations

import csv
import json
from pathlib import Path

from aimworks_ontology_release.io import load_json_document, merge_document_items
from aimworks_ontology_release.xps_pilot import REQUIRED_LOCAL_TERMS, build_xps_pilot_package


def _write_jsonld(path: Path, payload: list[dict]) -> Path:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def test_xps_pilot_package_generates_outputs(tmp_path: Path):
    payload = [
        {"@id": "https://w3id.org/h2kg/hydrogen-ontology", "@type": ["http://www.w3.org/2002/07/owl#Ontology"]},
        *({"@id": iri, "@type": ["http://www.w3.org/2002/07/owl#Thing"]} for iri in sorted(REQUIRED_LOCAL_TERMS)),
    ]
    source = _write_jsonld(tmp_path / "xps_source.jsonld", payload)
    output_root = tmp_path / "output"
    output_root.mkdir()

    summary = build_xps_pilot_package(source, output_root)

    assert summary["status"] == "generated"
    target_dir = output_root / "examples" / "xps_pilot"
    assert (target_dir / "xps_mapping_matrix.csv").exists()
    assert (target_dir / "xps_example.jsonld").exists()
    assert (target_dir / "xps_validation_note.md").exists()
    assert (target_dir / "xps_manuscript_figure.md").exists()
    assert (target_dir / "xps_manuscript_table.md").exists()

    csv_rows = list(csv.DictReader((target_dir / "xps_mapping_matrix.csv").read_text(encoding="utf-8").splitlines()))
    assert any(
        row["case_element"] == "XPS acquisition"
        and row["classification"] == "normalized existing term"
        and row["h2kg_anchor"] == "h2kg:XRayPhotoelectronSpectroscopyMeasurement"
        for row in csv_rows
    )
    assert any(
        row["case_element"] == "XPS pass energy"
        and row["classification"] == "normalized existing term"
        and row["h2kg_anchor"] == "h2kg:XPSPassEnergy"
        for row in csv_rows
    )
    assert any(
        row["case_element"] == "Deconvolution fractions and state-specific ratios"
        and row["classification"] == "deferred"
        for row in csv_rows
    )

    payload = json.loads((target_dir / "xps_example.jsonld").read_text(encoding="utf-8"))
    items = payload["@graph"]

    measurement = next(item for item in items if item["@id"].endswith("xps-measurement-001"))
    assert "https://w3id.org/h2kg/hydrogen-ontology#XRayPhotoelectronSpectroscopyMeasurement" in measurement["@type"]

    instrument = next(item for item in items if item["@id"].endswith("xps-instrument-001"))
    assert "https://w3id.org/h2kg/hydrogen-ontology#XPSInstrument" in instrument["@type"]

    datapoint = next(item for item in items if item["@id"].endswith("binding-energy-datapoint"))
    assert datapoint["https://w3id.org/h2kg/hydrogen-ontology#ofProperty"][0]["@id"] == "https://w3id.org/h2kg/hydrogen-ontology#BindingEnergy"

    metal = next(item for item in items if item["@id"].endswith("metal-atomic-percent-datapoint"))
    assert metal["https://w3id.org/h2kg/hydrogen-ontology#ofProperty"][0]["@id"] == "https://w3id.org/h2kg/hydrogen-ontology#MetalAtomicPercent"


def test_xps_pilot_package_skips_when_required_terms_are_missing(mini_ontology_file, tmp_path: Path):
    output_root = tmp_path / "output"
    output_root.mkdir()

    summary = build_xps_pilot_package(mini_ontology_file, output_root)

    assert summary["status"] == "skipped_missing_terms"
    assert (output_root / "examples" / "xps_pilot" / "README.md").exists()


def test_current_source_contains_xps_schema_updates():
    source = Path(__file__).resolve().parents[1] / "input" / "current_ontology.jsonld"
    merged = merge_document_items(load_json_document(source))
    by_id = {item["@id"]: item for item in merged if isinstance(item.get("@id"), str)}

    measurement = by_id["https://w3id.org/h2kg/hydrogen-ontology#XRayPhotoelectronSpectroscopyMeasurement"]

    parameters = {
        entry["@id"] for entry in measurement["https://w3id.org/h2kg/hydrogen-ontology#hasParameter"]
    }
    assert parameters == {
        "https://w3id.org/h2kg/hydrogen-ontology#XPSPassEnergy",
        "https://w3id.org/h2kg/hydrogen-ontology#XPSTakeOffAngle",
        "https://w3id.org/h2kg/hydrogen-ontology#XPSAnalysisArea",
    }

    outputs = {
        entry["@id"] for entry in measurement["https://w3id.org/h2kg/hydrogen-ontology#hasOutputData"]
    }
    assert outputs == {
        "https://w3id.org/h2kg/hydrogen-ontology#XPSDataset",
        "https://w3id.org/h2kg/hydrogen-ontology#ExperimentDataset",
    }

    instruments = {
        entry["@id"] for entry in measurement["https://w3id.org/h2kg/hydrogen-ontology#usesInstrument"]
    }
    assert instruments == {
        "https://w3id.org/h2kg/hydrogen-ontology#XPSInstrument",
    }

    inputs = {
        entry["@id"] for entry in measurement["https://w3id.org/h2kg/hydrogen-ontology#hasInputMaterial"]
    }
    assert inputs == {
        "https://w3id.org/h2kg/hydrogen-ontology#CatalystPowder",
        "https://w3id.org/h2kg/hydrogen-ontology#PtOnCarbonCatalyst",
        "https://w3id.org/h2kg/hydrogen-ontology#CatalystInk",
        "https://w3id.org/h2kg/hydrogen-ontology#PFSAIonomer",
    }

    properties = {
        entry["@id"] for entry in measurement["https://w3id.org/h2kg/hydrogen-ontology#measures"]
    }
    assert properties == {
        "https://w3id.org/h2kg/hydrogen-ontology#BindingEnergy",
        "https://w3id.org/h2kg/hydrogen-ontology#C1sAtomicPercent",
        "https://w3id.org/h2kg/hydrogen-ontology#O1sAtomicPercent",
        "https://w3id.org/h2kg/hydrogen-ontology#F1sAtomicPercent",
        "https://w3id.org/h2kg/hydrogen-ontology#N1sAtomicPercent",
        "https://w3id.org/h2kg/hydrogen-ontology#CarbonToOxygenAtomRatio",
        "https://w3id.org/h2kg/hydrogen-ontology#MetalAtomicPercent",
    }

    description = measurement["http://purl.org/dc/terms/description"][0]["@value"].lower()
    assert "pemfc" in description
    assert "xps spectra" in description

    instrument = by_id["https://w3id.org/h2kg/hydrogen-ontology#XPSInstrument"]
    instrument_description = instrument["http://purl.org/dc/terms/description"][0]["@value"].lower()
    assert "photoelectron spectroscopy" in instrument_description
    assert "surface-chemistry" in instrument_description

    dataset_description = by_id["https://w3id.org/h2kg/hydrogen-ontology#XPSDataset"]["http://purl.org/dc/terms/description"][0]["@value"].lower()
    assert "xps spectra" in dataset_description
    assert "pemfc" in dataset_description

    binding_description = by_id["https://w3id.org/h2kg/hydrogen-ontology#BindingEnergy"]["http://purl.org/dc/terms/description"][0]["@value"].lower()
    assert "pt(111)" not in binding_description
    assert "surface-chemistry" in binding_description
