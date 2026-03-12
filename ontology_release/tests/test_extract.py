from __future__ import annotations

from aimworks_ontology_release.extract import extract_local_terms


def test_extract_local_terms(sample_graph, configs, classifications):
    terms = extract_local_terms(sample_graph, configs["namespace_policy"], classifications)
    labels = {term.label for term in terms}
    assert "Measurement" in labels
    assert "Instrument" in labels
