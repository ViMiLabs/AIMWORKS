from __future__ import annotations

from aimworks_ontology_release.classify import classify_resources


def test_classify_detects_schema_and_examples(mini_ontology_file, output_dir):
    classifications = classify_resources(mini_ontology_file, output_dir)
    by_kind = {entry.iri: entry.kind for entry in classifications}
    assert by_kind["https://w3id.org/h2kg/hydrogen-ontology#Process"] == "class"
    assert by_kind["https://w3id.org/h2kg/hydrogen-ontology#ExampleMeasurementQV"] == "quantity_value_data_node"
