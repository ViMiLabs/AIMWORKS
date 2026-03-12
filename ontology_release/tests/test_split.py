from __future__ import annotations

from rdflib import URIRef

from aimworks_ontology_release.split import split_graph


def test_split_separates_schema_vocab_examples(sample_graph, classifications):
    graphs, report = split_graph(sample_graph, classifications)
    assert report["schema_subject_count"] >= 5
    assert (URIRef("https://w3id.org/h2kg/hydrogen-ontology#Measurement"), None, None) in graphs["schema"]
    assert (URIRef("https://w3id.org/h2kg/hydrogen-ontology#PtMass"), None, None) in graphs["controlled_vocabulary"]
    assert (URIRef("https://w3id.org/h2kg/hydrogen-ontology#Measurement1"), None, None) in graphs["examples"]
