from __future__ import annotations

from aimworks_ontology_release.extract import extract_local_term_profiles


def test_extract_profiles(mini_ontology_file, output_dir):
    profiles = extract_local_term_profiles(mini_ontology_file, output_dir)
    iris = {entry["iri"] for entry in profiles}
    assert "https://w3id.org/h2kg/hydrogen-ontology#Process" in iris
