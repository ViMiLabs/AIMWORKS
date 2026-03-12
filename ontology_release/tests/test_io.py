from __future__ import annotations

from aimworks_ontology_release.io import load_graph, save_graph


def test_read_write_rdf(tmp_path, sample_graph):
    target = tmp_path / "graph.ttl"
    save_graph(sample_graph, target, "turtle")
    reloaded = load_graph(target, "turtle")
    assert len(reloaded) == len(sample_graph)
