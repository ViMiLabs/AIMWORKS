from __future__ import annotations

import csv
import json
from pathlib import Path

from aimworks_ontology_release.io import load_json_document, merge_document_items
from aimworks_ontology_release.xrd_pilot import REQUIRED_LOCAL_TERMS, build_xrd_pilot_package


def _write_jsonld(path: Path, payload: list[dict]) -> Path:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def test_xrd_pilot_package_generates_outputs(tmp_path: Path):
    payload = [
        {"@id": "https://w3id.org/h2kg/hydrogen-ontology", "@type": ["http://www.w3.org/2002/07/owl#Ontology"]},
        *({"@id": iri, "@type": ["http://www.w3.org/2002/07/owl#Thing"]} for iri in sorted(REQUIRED_LOCAL_TERMS)),
    ]
    source = _write_jsonld(tmp_path / "xrd_source.jsonld", payload)
    output_root = tmp_path / "output"
    output_root.mkdir()

    summary = build_xrd_pilot_package(source, output_root)

    assert summary["status"] == "generated"
    target_dir = output_root / "examples" / "xrd_pilot"
    assert (target_dir / "xrd_mapping_matrix.csv").exists()
    assert (target_dir / "xrd_example.jsonld").exists()
    assert (target_dir / "xrd_validation_note.md").exists()
    assert (target_dir / "xrd_manuscript_figure.md").exists()
    assert (target_dir / "xrd_manuscript_table.md").exists()

    csv_rows = list(csv.DictReader((target_dir / "xrd_mapping_matrix.csv").read_text(encoding="utf-8").splitlines()))
    assert any(
        row["case_element"] == "XRD acquisition"
        and row["classification"] == "normalized existing term"
        and row["h2kg_anchor"] == "h2kg:XRayDiffractionMeasurement"
        for row in csv_rows
    )
    assert any(
        row["case_element"] == "Pt crystallite size output"
        and row["classification"] == "reuse existing term"
        and row["h2kg_anchor"] == "h2kg:PtCrystalliteSize"
        for row in csv_rows
    )
    assert any(
        row["case_element"] == "Advanced XRD analysis vocabulary"
        and row["classification"] == "deferred"
        for row in csv_rows
    )

    payload = json.loads((target_dir / "xrd_example.jsonld").read_text(encoding="utf-8"))
    items = payload["@graph"]

    measurement = next(item for item in items if item["@id"].endswith("xrd-measurement-001"))
    assert "https://w3id.org/h2kg/hydrogen-ontology#XRayDiffractionMeasurement" in measurement["@type"]

    instrument = next(item for item in items if item["@id"].endswith("xrd-instrument-001"))
    assert "https://w3id.org/h2kg/hydrogen-ontology#XRayDiffractometer" in instrument["@type"]

    datapoint = next(item for item in items if item["@id"].endswith("pt-crystallite-size-datapoint"))
    assert datapoint["https://w3id.org/h2kg/hydrogen-ontology#ofProperty"][0]["@id"] == "https://w3id.org/h2kg/hydrogen-ontology#PtCrystalliteSize"

    surface_area = next(item for item in items if item["@id"].endswith("theoretical-metal-surface-area-datapoint"))
    assert surface_area["https://w3id.org/h2kg/hydrogen-ontology#ofProperty"][0]["@id"] == "https://w3id.org/h2kg/hydrogen-ontology#TheoreticalMetalSurfaceArea"


def test_xrd_pilot_package_skips_when_required_terms_are_missing(mini_ontology_file, tmp_path: Path):
    output_root = tmp_path / "output"
    output_root.mkdir()

    summary = build_xrd_pilot_package(mini_ontology_file, output_root)

    assert summary["status"] == "skipped_missing_terms"
    assert (output_root / "examples" / "xrd_pilot" / "README.md").exists()


def test_current_source_contains_xrd_schema_updates():
    source = Path(__file__).resolve().parents[1] / "input" / "current_ontology.jsonld"
    merged = merge_document_items(load_json_document(source))
    by_id = {item["@id"]: item for item in merged if isinstance(item.get("@id"), str)}

    measurement = by_id["https://w3id.org/h2kg/hydrogen-ontology#XRayDiffractionMeasurement"]

    parameters = {
        entry["@id"] for entry in measurement["https://w3id.org/h2kg/hydrogen-ontology#hasParameter"]
    }
    assert parameters == {
        "https://w3id.org/h2kg/hydrogen-ontology#XRayWavelength",
        "https://w3id.org/h2kg/hydrogen-ontology#XRDStepSize",
        "https://w3id.org/h2kg/hydrogen-ontology#XRDTwoThetaStart",
        "https://w3id.org/h2kg/hydrogen-ontology#XRDTwoThetaEnd",
    }

    outputs = {
        entry["@id"] for entry in measurement["https://w3id.org/h2kg/hydrogen-ontology#hasOutputData"]
    }
    assert outputs == {
        "https://w3id.org/h2kg/hydrogen-ontology#XRDPatternDataset",
        "https://w3id.org/h2kg/hydrogen-ontology#ExperimentDataset",
    }

    instruments = {
        entry["@id"] for entry in measurement["https://w3id.org/h2kg/hydrogen-ontology#usesInstrument"]
    }
    assert instruments == {
        "https://w3id.org/h2kg/hydrogen-ontology#XRayDiffractometer",
    }

    inputs = {
        entry["@id"] for entry in measurement["https://w3id.org/h2kg/hydrogen-ontology#hasInputMaterial"]
    }
    assert inputs == {
        "https://w3id.org/h2kg/hydrogen-ontology#CatalystPowder",
        "https://w3id.org/h2kg/hydrogen-ontology#PtOnCarbonCatalyst",
    }

    properties = {
        entry["@id"] for entry in measurement["https://w3id.org/h2kg/hydrogen-ontology#measures"]
    }
    assert properties == {
        "https://w3id.org/h2kg/hydrogen-ontology#DiffractionPeakPosition2Theta",
        "https://w3id.org/h2kg/hydrogen-ontology#XRDPeakFWHM",
        "https://w3id.org/h2kg/hydrogen-ontology#PtCrystalliteSize",
        "https://w3id.org/h2kg/hydrogen-ontology#TheoreticalMetalSurfaceArea",
    }

    description = measurement["http://purl.org/dc/terms/description"][0]["@value"].lower()
    assert "pemfc" in description
    assert "catalyst powders" in description

    instrument_description = by_id["https://w3id.org/h2kg/hydrogen-ontology#XRayDiffractometer"]["http://purl.org/dc/terms/description"][0]["@value"].lower()
    assert "diffraction patterns" in instrument_description
    assert "catalyst" in instrument_description

    dataset_description = by_id["https://w3id.org/h2kg/hydrogen-ontology#XRDPatternDataset"]["http://purl.org/dc/terms/description"][0]["@value"].lower()
    assert "diffraction patterns" in dataset_description
    assert "catalyst" in dataset_description
