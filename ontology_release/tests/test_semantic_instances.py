from __future__ import annotations

import json

from rdflib import Graph, RDF, URIRef

from aimworks_ontology_release.semantic_instances import normalize_example_pair
from aimworks_ontology_release.utils import COMMON_CONTEXT


H2KG = "https://w3id.org/h2kg/hydrogen-ontology#"


def test_example_normalization_separates_workflow_records_and_property_occurrences(tmp_path):
    parameter = URIRef("https://example.org/temperature-parameter")
    result = URIRef("https://example.org/temperature-result")
    temperature = URIRef(H2KG + "Temperature")
    quantity_value = URIRef("https://example.org/temperature-value")
    document = {
        "@context": COMMON_CONTEXT,
        "@graph": [
            {
                "@id": str(parameter),
                "@type": [H2KG + "Parameter", str(temperature)],
                H2KG + "hasQuantityValue": [{"@id": str(quantity_value)}],
            },
            {
                "@id": str(result),
                "@type": [H2KG + "DataPoint"],
                H2KG + "ofProperty": [{"@id": str(temperature)}],
                H2KG + "hasQuantityValue": [{"@id": str(quantity_value)}],
            },
            {"@id": str(quantity_value), "@type": ["http://qudt.org/schema/qudt/QuantityValue"]},
        ],
    }
    jsonld_path = tmp_path / "example.jsonld"
    ttl_path = tmp_path / "example.ttl"
    jsonld_path.write_text(json.dumps(document), encoding="utf-8")
    Graph().parse(data=json.dumps(document), format="json-ld").serialize(ttl_path, format="turtle")

    report = normalize_example_pair(jsonld_path, ttl_path, {str(temperature)})

    assert report["conforms"] is True
    assert report["parameter_record_count"] == 1
    assert report["result_record_count"] == 1
    graph = Graph().parse(ttl_path, format="turtle")
    assert (parameter, RDF.type, URIRef(H2KG + "Parameter")) in graph
    assert (parameter, RDF.type, temperature) not in graph
    parameter_occurrence = next(graph.objects(parameter, URIRef(H2KG + "ofProperty")))
    result_occurrence = next(graph.objects(result, URIRef(H2KG + "ofProperty")))
    assert (parameter_occurrence, RDF.type, temperature) in graph
    assert (result_occurrence, RDF.type, temperature) in graph
    assert (parameter_occurrence, URIRef(H2KG + "hasQuantityValue"), quantity_value) in graph
    assert (result_occurrence, URIRef(H2KG + "hasQuantityValue"), quantity_value) in graph
