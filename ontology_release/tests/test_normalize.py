from __future__ import annotations

from aimworks_ontology_release.normalize import best_label, looks_like_quantity_value


def test_normalize_helpers():
    item = {
        "@id": "https://w3id.org/h2kg/hydrogen-ontology#GasComposition",
        "http://www.w3.org/2000/01/rdf-schema#label": [{"@value": "Gas composition"}],
    }
    assert best_label(item) == "Gas composition"
    assert looks_like_quantity_value({"@type": ["http://qudt.org/schema/qudt/QuantityValue"]})
