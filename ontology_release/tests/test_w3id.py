from __future__ import annotations

from pathlib import Path

from aimworks_ontology_release.w3id import generate_w3id_artifacts


def test_w3id_keeps_established_routes_without_a_new_bridge_route(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    result = generate_w3id_artifacts(output_root / "w3id", config_dir)

    htaccess = (output_root / "w3id" / "h2kg" / ".htaccess").read_text(encoding="utf-8")
    readme = (output_root / "w3id" / "h2kg" / "README.md").read_text(encoding="utf-8")
    curls = (output_root / "w3id" / "curl_tests.sh").read_text(encoding="utf-8")
    publishing_notes = (output_root / "w3id" / "publishing_notes.md").read_text(encoding="utf-8")
    assert "hydrogen-ontology/bridge/tib" not in htaccess
    assert "h2kg-v2-external-bridge" not in htaccess
    assert "established `https://w3id.org/h2kg/` namespace" in readme
    assert "future pull request" not in readme.casefold()
    assert "does not require a new W3ID registration" in publishing_notes
    assert "Accept: text/turtle" in curls
    assert "hydrogen-ontology/bridge/tib" not in curls
    assert "external_bridge_ttl" not in result["rdf_targets"]
