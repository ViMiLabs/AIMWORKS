from __future__ import annotations

from aimworks_ontology_release.utils import dump_json, write_text


def test_generated_text_writers_do_not_duplicate_carriage_returns(tmp_path):
    csv_path = write_text(tmp_path / "records.csv", "a,b  \r\n1,2\r\n   \r\n")
    json_path = dump_json(tmp_path / "record.json", {"label": "test"})

    assert b"\r\r\n" not in csv_path.read_bytes()
    assert csv_path.read_bytes() == b"a,b\r\n1,2\r\n\r\n"
    assert b"\r\n" not in json_path.read_bytes()
