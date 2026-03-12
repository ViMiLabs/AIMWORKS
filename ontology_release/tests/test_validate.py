from __future__ import annotations

from aimworks_ontology_release.enrich import enrich_graphs
from aimworks_ontology_release.mapper import align_terms
from aimworks_ontology_release.split import split_graph
from aimworks_ontology_release.validate import validate_release


def test_validation_runs(sample_graph, classifications, configs, package_root):
    graphs, _ = split_graph(sample_graph, classifications)
    alignments, _, _ = align_terms(
        graphs["schema"],
        graphs["controlled_vocabulary"],
        classifications,
        configs["source_ontologies"],
        configs["namespace_policy"],
        configs["mapping_rules"],
        package_root,
    )
    enrich_graphs(
        graphs["schema"],
        graphs["controlled_vocabulary"],
        classifications,
        configs["metadata_defaults"],
        configs["release_profile"],
        configs["namespace_policy"],
        package_root,
    )
    report = validate_release(graphs["schema"], graphs["controlled_vocabulary"], alignments, classifications, configs["namespace_policy"], package_root)
    assert report["syntax_ok"] is True
    assert report["overall_status"] in {"pass", "warning"}
