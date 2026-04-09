from __future__ import annotations

from aimworks_ontology_release.mapper import propose_mappings


def test_mapper_creates_review_files(mini_ontology_file, output_dir):
    (output_dir / "review").mkdir()
    (output_dir / "reports").mkdir()
    (output_dir / "mappings").mkdir()
    rows = propose_mappings(mini_ontology_file, output_dir / "review")
    assert any(row["local_label"] == "Measurement" for row in rows)
    assert (output_dir / "review" / "mapping_review.csv").exists()
    assert (output_dir / "reports" / "hdo_alignment_report.json").exists()
