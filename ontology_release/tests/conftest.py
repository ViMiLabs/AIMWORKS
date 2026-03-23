from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture()
def mini_ontology_file(tmp_path: Path) -> Path:
    payload = [
        {
            "@id": "https://w3id.org/h2kg/hydrogen-ontology",
            "@type": ["http://www.w3.org/2002/07/owl#Ontology"],
            "http://purl.org/dc/terms/title": [{"@value": "Mini H2KG"}],
            "http://purl.org/dc/terms/description": [{"@value": "Mini ontology for tests."}],
        },
        {
            "@id": "https://w3id.org/h2kg/hydrogen-ontology#Process",
            "@type": ["http://www.w3.org/2002/07/owl#Class"],
        },
        {
            "@id": "https://w3id.org/h2kg/hydrogen-ontology#Measurement",
            "@type": ["http://www.w3.org/2002/07/owl#Class"],
            "http://www.w3.org/2000/01/rdf-schema#subClassOf": [{"@id": "https://w3id.org/h2kg/hydrogen-ontology#Process"}],
        },
        {
            "@id": "https://w3id.org/h2kg/hydrogen-ontology#hasParameter",
            "@type": ["http://www.w3.org/2002/07/owl#ObjectProperty"],
            "http://www.w3.org/2000/01/rdf-schema#domain": [{"@id": "https://w3id.org/h2kg/hydrogen-ontology#Process"}],
            "http://www.w3.org/2000/01/rdf-schema#range": [{"@id": "https://w3id.org/h2kg/hydrogen-ontology#Parameter"}],
        },
        {
            "@id": "https://w3id.org/h2kg/hydrogen-ontology#Parameter",
            "@type": ["http://www.w3.org/2002/07/owl#Class"],
        },
        {
            "@id": "https://w3id.org/h2kg/hydrogen-ontology#ECSABasis",
            "http://www.w3.org/2000/01/rdf-schema#label": [{"@value": "ECSA basis"}],
        },
        {
            "@id": "https://w3id.org/h2kg/hydrogen-ontology#ExampleMeasurement",
            "@type": ["https://w3id.org/h2kg/hydrogen-ontology#Measurement"],
            "https://w3id.org/h2kg/hydrogen-ontology#hasQuantityValue": [{"@id": "https://w3id.org/h2kg/hydrogen-ontology#ExampleMeasurementQV"}],
        },
        {
            "@id": "https://w3id.org/h2kg/hydrogen-ontology#ExampleMeasurementQV",
            "@type": ["http://qudt.org/schema/qudt/QuantityValue"],
            "http://qudt.org/schema/qudt/numericValue": [{"@value": "1.23", "@type": "http://www.w3.org/2001/XMLSchema#decimal"}],
        },
    ]
    path = tmp_path / "mini.jsonld"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


@pytest.fixture()
def output_dir(tmp_path: Path) -> Path:
    path = tmp_path / "output"
    path.mkdir()
    return path
