from __future__ import annotations

from aimworks_ontology_release.quality import clean_jsonld_payload
from aimworks_ontology_release.release import run_pipeline


LOCAL = "https://w3id.org/h2kg/hydrogen-ontology#"
PARAMETER = f"{LOCAL}Parameter"
PROPERTY = f"{LOCAL}Property"
HAS_QV = f"{LOCAL}hasQuantityValue"
USES_TERM = f"{LOCAL}usesTerm"


def _text(value: str) -> dict[str, str]:
    return {"@value": value}


def _ref(iri: str) -> dict[str, str]:
    return {"@id": iri}


def test_quality_cleanup_merges_safe_suffix_duplicates() -> None:
    payload = [
        {ID: f"{LOCAL}AcceleratingVoltage", TYPE: [PARAMETER], RDFS_LABEL: [_text("Accelerating Voltage")], SKOS_ALTLABEL: [_text("300 kV"), _text("tube voltage")], HAS_QV: [_ref(f"{LOCAL}_AcceleratingVoltage_QV")]},
        {ID: f"{LOCAL}AcceleratingVoltage_2", TYPE: [PARAMETER], RDFS_LABEL: [_text("Accelerating Voltage")], SKOS_ALTLABEL: [_text("10 kV"), _text("SEM operating voltage")], HAS_QV: [_ref(f"{LOCAL}_AcceleratingVoltage_QV_2")]},
        {ID: f"{LOCAL}_AcceleratingVoltage_QV", f"{LOCAL}hasQuantityKind": [_ref("http://qudt.org/vocab/quantitykind/ElectricPotential")]},
        {ID: f"{LOCAL}_AcceleratingVoltage_QV_2", f"{LOCAL}hasQuantityKind": [_ref("http://qudt.org/vocab/quantitykind/ElectricPotential")]},
        {ID: f"{LOCAL}MeasurementExample", USES_TERM: [_ref(f"{LOCAL}AcceleratingVoltage_2")]},
    ]

    cleaned, report = clean_jsonld_payload(payload, source_name="fixture")
    cleaned_by_id = {row[ID]: row for row in cleaned}

    assert report["auto_merged_terms"] == 1
    assert report["manual_review_pairs"] == 0
    assert f"{LOCAL}AcceleratingVoltage_2" not in cleaned_by_id
    assert f"{LOCAL}_AcceleratingVoltage_QV_2" not in cleaned_by_id
    assert cleaned_by_id[f"{LOCAL}MeasurementExample"][USES_TERM] == [_ref(f"{LOCAL}AcceleratingVoltage")]

    alt_labels = {item["@value"] for item in cleaned_by_id[f"{LOCAL}AcceleratingVoltage"][SKOS_ALTLABEL]}
    assert "tube voltage" in alt_labels
    assert "SEM operating voltage" in alt_labels
    assert "300 kV" not in alt_labels
    assert "10 kV" not in alt_labels


def test_quality_cleanup_keeps_type_mismatch_for_review() -> None:
    payload = [
        {ID: f"{LOCAL}CatalystLayerThickness", TYPE: [PARAMETER], RDFS_LABEL: [_text("Catalyst Layer Thickness")]},
        {ID: f"{LOCAL}CatalystLayerThickness_2", TYPE: [PROPERTY], RDFS_LABEL: [_text("Catalyst Layer Thickness")]},
    ]

    cleaned, report = clean_jsonld_payload(payload, source_name="fixture")
    cleaned_ids = {row[ID] for row in cleaned}

    assert report["auto_merged_terms"] == 0
    assert report["manual_review_pairs"] == 1
    assert f"{LOCAL}CatalystLayerThickness" in cleaned_ids
    assert f"{LOCAL}CatalystLayerThickness_2" in cleaned_ids


def test_quality_stage_writes_report_for_jsonld_input(temp_project):
    result = run_pipeline("input/ONTOLOGY_PEMFC.jsonld", root=temp_project, stage="quality")
    assert "quality_report" in result
    assert (temp_project / "output" / "reports" / "term_quality_report.json").exists()
    assert (temp_project / "output" / "reports" / "term_quality_report.md").exists()


ID = "@id"
TYPE = "@type"
RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"
SKOS_ALTLABEL = "http://www.w3.org/2004/02/skos/core#altLabel"
