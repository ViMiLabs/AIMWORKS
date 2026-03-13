from __future__ import annotations

from aimworks_ontology_release.enrich import enrich_graphs
from aimworks_ontology_release.mapper import align_terms
from aimworks_ontology_release.split import split_graph
from aimworks_ontology_release.validate import _foops_dimension_rows, validate_release


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
    report = validate_release(
        graphs["schema"],
        graphs["controlled_vocabulary"],
        alignments,
        classifications,
        configs["namespace_policy"],
        configs["release_profile"],
        package_root,
    )
    assert report["syntax_ok"] is True
    assert report["overall_status"] in {"pass", "warning"}
    assert "owl_consistency" in report
    assert "resolver_checks" in report


def test_foops_dimension_rows_aggregate() -> None:
    rows = _foops_dimension_rows(
        [
            {"category_id": "Findable", "principle_id": "F1", "total_passed_tests": 1, "total_tests_run": 1, "status": "ok"},
            {"category_id": "Findable", "principle_id": "F2", "total_passed_tests": 2, "total_tests_run": 4, "status": "error"},
            {"category_id": "Interoperable", "principle_id": "I1", "total_passed_tests": 3, "total_tests_run": 3, "status": "ok"},
        ]
    )
    indexed = {row["dimension"]: row for row in rows}
    assert indexed["Findable"]["score"] == 60.0
    assert indexed["Accessible"]["score"] is None
    assert indexed["Interoperable"]["score"] == 100.0
