from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from aimworks_ontology_release.classify import classify_resources
from aimworks_ontology_release.io import graph_from_text
from aimworks_ontology_release.utils import load_configs


SAMPLE_TTL = """
@prefix h2kg: <https://w3id.org/h2kg/hydrogen-ontology#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix qudt: <http://qudt.org/schema/qudt/> .
@prefix unit: <http://qudt.org/vocab/unit/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<https://w3id.org/h2kg/hydrogen-ontology> a owl:Ontology ;
  dcterms:title "Sample H2KG Ontology"@en ;
  dcterms:description "Sample release fixture."@en ;
  dcterms:license <https://creativecommons.org/licenses/by/4.0/> .

h2kg:Measurement a owl:Class .
h2kg:Instrument a owl:Class ; rdfs:label "Instrument"@en .
h2kg:NormalizationBasis a owl:Class ; rdfs:label "Normalization Basis"@en .
h2kg:hasQuantityValue a owl:ObjectProperty .
h2kg:usesInstrument a owl:ObjectProperty ; rdfs:domain h2kg:Measurement ; rdfs:range h2kg:Instrument .

h2kg:PtMass a h2kg:NormalizationBasis ; rdfs:label "Pt Mass"@en .
h2kg:InstrumentA a h2kg:Instrument ; rdfs:label "Potentiostat"@en .
h2kg:Measurement1 a h2kg:Measurement ; h2kg:usesInstrument h2kg:InstrumentA ; h2kg:hasQuantityValue h2kg:QV1 .
h2kg:QV1 a qudt:QuantityValue ; qudt:numericValue "1.0"^^xsd:decimal ; qudt:unit unit:OHM .
"""


@pytest.fixture()
def package_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture()
def sample_graph():
    return graph_from_text(SAMPLE_TTL, "turtle")


@pytest.fixture()
def temp_project(tmp_path: Path, package_root: Path) -> Path:
    for dirname in ["config", "templates", "shapes"]:
        shutil.copytree(package_root / dirname, tmp_path / dirname)
    for filename in ["CITATION.cff", ".zenodo.json", ".nojekyll", "README.md"]:
        shutil.copy2(package_root / filename, tmp_path / filename)
    (tmp_path / "input").mkdir(exist_ok=True)
    (tmp_path / "output").mkdir(exist_ok=True)
    (tmp_path / "ontology").mkdir(exist_ok=True)
    (tmp_path / "cache" / "sources").mkdir(parents=True, exist_ok=True)
    (tmp_path / "input" / "sample.ttl").write_text(SAMPLE_TTL, encoding="utf-8")
    return tmp_path


@pytest.fixture()
def configs(package_root: Path):
    return load_configs(package_root)


@pytest.fixture()
def classifications(sample_graph, configs):
    return classify_resources(sample_graph, configs["namespace_policy"], configs["mapping_rules"])
