from __future__ import annotations

from aimworks_ontology_release.mapper import align_terms
from aimworks_ontology_release.split import split_graph


def test_alignment_proposes_mappings(sample_graph, classifications, configs, package_root):
    graphs, _ = split_graph(sample_graph, classifications)
    _, review_rows, report = align_terms(
        graphs["schema"],
        graphs["controlled_vocabulary"],
        classifications,
        configs["source_ontologies"],
        configs["namespace_policy"],
        configs["mapping_rules"],
        package_root,
    )
    assert report["local_term_count"] >= 4
    assert any(row["target_iri"] for row in review_rows)
