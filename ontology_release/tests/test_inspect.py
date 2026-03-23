from __future__ import annotations

from aimworks_ontology_release.inspect import inspect_ontology


def test_inspect_generates_reports(mini_ontology_file, output_dir):
    report = inspect_ontology(mini_ontology_file, output_dir)
    assert report["counts"]["class_count"] >= 2
    assert (output_dir / "inspection_report.md").exists()
    assert (output_dir / "inspection_report.json").exists()
