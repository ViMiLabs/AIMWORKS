from __future__ import annotations

from aimworks_ontology_release.io import dump_jsonld_items, dump_turtle_items, load_json_document, merge_document_items


def test_load_and_dump_io(mini_ontology_file, output_dir):
    document = load_json_document(mini_ontology_file)
    merged = merge_document_items(document)
    assert len(merged) >= 6
    dump_jsonld_items(output_dir / "test.jsonld", merged)
    dump_turtle_items(output_dir / "test.ttl", merged[:3])
    assert (output_dir / "test.jsonld").exists()
    assert (output_dir / "test.ttl").read_text(encoding="utf-8").startswith("@prefix")
