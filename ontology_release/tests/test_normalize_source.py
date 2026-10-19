from __future__ import annotations

import json
from pathlib import Path

from aimworks_ontology_release.normalize_source import normalize_source_document


def test_normalize_source_merges_duplicates_and_repairs_dynamic_hydrogen_electrode(tmp_path: Path):
    source = tmp_path / "source.jsonld"
    source.write_text(
        json.dumps(
            [
                {
                    "@id": "https://w3id.org/h2kg/hydrogen-ontology",
                    "@type": ["http://www.w3.org/2002/07/owl#Ontology"],
                },
                {
                    "@id": "https://w3id.org/h2kg/hydrogen-ontology#hasParameter",
                    "@type": ["http://www.w3.org/2002/07/owl#ObjectProperty"],
                    "http://www.w3.org/2000/01/rdf-schema#domain": [{"@id": "https://example.org/Thing"}],
                },
                {
                    "@id": "https://w3id.org/h2kg/hydrogen-ontology#hasParameter",
                    "@type": ["http://www.w3.org/2002/07/owl#ObjectProperty"],
                    "http://www.w3.org/2000/01/rdf-schema#label": [{"@value": "hasParameter"}],
                },
                {
                    "@id": "https://w3id.org/h2kg/hydrogen-ontology#DynamicHydrogenElectrode",
                    "@type": ["https://w3id.org/emmo/domain/electrochemistry#electrochemistry_7729c34e_1ae9_403d_b933_1765885e7f29"],
                    "http://www.w3.org/2004/02/skos/core#prefLabel": [{"@value": "Dynamic Hydrogen Electrode"}],
                },
            ],
            indent=2,
        ),
        encoding="utf-8",
    )

    report = normalize_source_document(source, tmp_path, write_in_place=True)
    assert report["duplicate_group_count"] == 1
    assert "https://w3id.org/h2kg/hydrogen-ontology#hasParameter" in report["duplicate_ids"]

    payload = json.loads(source.read_text(encoding="utf-8"))
    ids = [item["@id"] for item in payload]
    assert ids.count("https://w3id.org/h2kg/hydrogen-ontology#hasParameter") == 1

    dhe = next(item for item in payload if item["@id"] == "https://w3id.org/h2kg/hydrogen-ontology#DynamicHydrogenElectrode")
    assert "https://w3id.org/h2kg/hydrogen-ontology#Instrument" in dhe["@type"]
    assert dhe["http://purl.org/dc/terms/description"][0]["@value"].startswith("An instrument corresponding to a dynamic hydrogen electrode")


def test_normalize_source_can_emit_report_without_copying_document(tmp_path: Path):
    source = tmp_path / "source.jsonld"
    original = [{"@id": "https://example.org/Term", "@type": ["http://www.w3.org/2002/07/owl#Class"]}]
    source.write_text(json.dumps(original), encoding="utf-8")
    reports = tmp_path / "reports"

    report = normalize_source_document(
        source,
        reports,
        write_in_place=False,
        emit_normalized_document=False,
    )

    assert report["normalized_document_written"] is False
    assert json.loads(source.read_text(encoding="utf-8")) == original
    assert (reports / "source_normalization_report.json").exists()
    assert not (reports / source.name).exists()
