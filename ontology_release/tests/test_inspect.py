from __future__ import annotations

from aimworks_ontology_release.inspect import inspect_graph


def test_inspection_reports_missing_version(sample_graph, configs):
    report, _ = inspect_graph(sample_graph, configs["namespace_policy"], configs["mapping_rules"])
    assert report["ontology_iri"] == "https://w3id.org/h2kg/hydrogen-ontology"
    assert "http://www.w3.org/2002/07/owl#versionIRI" in report["metadata_missing"]
    assert report["category_counts"]["class"] >= 3
