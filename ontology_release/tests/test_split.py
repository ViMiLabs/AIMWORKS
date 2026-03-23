from __future__ import annotations

from aimworks_ontology_release.split import split_ontology


def test_split_writes_modules(mini_ontology_file, output_dir):
    (output_dir / "ontology").mkdir()
    (output_dir / "review").mkdir()
    (output_dir / "examples").mkdir()
    (output_dir / "reports").mkdir()
    summary = split_ontology(mini_ontology_file, output_dir / "ontology")
    assert summary["schema_count"] >= 3
    assert (output_dir / "ontology" / "schema.ttl").exists()
    assert (output_dir / "examples" / "examples.ttl").exists()
