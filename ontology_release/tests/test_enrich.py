from __future__ import annotations

from aimworks_ontology_release.enrich import enrich_ontology


def test_enrich_adds_schema_outputs(mini_ontology_file, output_dir):
    (output_dir / "ontology").mkdir()
    (output_dir / "review").mkdir()
    (output_dir / "reports").mkdir()
    enriched = enrich_ontology(mini_ontology_file, output_dir / "ontology")
    assert any(item["@id"].endswith("#Process") for item in enriched if "@id" in item)
    assert (output_dir / "ontology" / "schema.jsonld").exists()
