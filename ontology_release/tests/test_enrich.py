from __future__ import annotations

from rdflib import URIRef
from rdflib.namespace import OWL, RDFS, SKOS

from aimworks_ontology_release.enrich import enrich_graphs
from aimworks_ontology_release.split import split_graph


def test_enrichment_adds_metadata_and_annotations(sample_graph, classifications, configs, package_root):
    graphs, _ = split_graph(sample_graph, classifications)
    report = enrich_graphs(
        graphs["schema"],
        graphs["controlled_vocabulary"],
        classifications,
        configs["metadata_defaults"],
        configs["release_profile"],
        configs["namespace_policy"],
        package_root,
    )
    ontology = URIRef(configs["namespace_policy"]["ontology_iri"])
    assert list(graphs["schema"].objects(ontology, OWL.versionIRI))
    measurement = URIRef("https://w3id.org/h2kg/hydrogen-ontology#Measurement")
    assert list(graphs["schema"].objects(measurement, RDFS.label))
    assert list(graphs["schema"].objects(measurement, SKOS.definition))
    assert report["generated_annotations"] >= 1
