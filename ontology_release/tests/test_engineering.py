from __future__ import annotations

from aimworks_ontology_release.engineering import _import_graph_svg, _resolve_import_title


def test_resolve_import_title_prefers_specific_emmo_module(configs) -> None:
    source_registry = configs["source_ontologies"]

    assert _resolve_import_title("https://w3id.org/emmo", source_registry) == "EMMO"
    assert _resolve_import_title("https://w3id.org/emmo/domain/manufacturing#", source_registry) == "EMMO Manufacturing"
    assert _resolve_import_title("https://w3id.org/emmo/domain/electrochemistry", source_registry) == "EMMO Electrochemistry"


def test_import_graph_svg_leaves_header_clear() -> None:
    svg = _import_graph_svg(
        [
            {"title": "EMMO", "iri": "https://w3id.org/emmo"},
            {"title": "EMMO PEMFC", "iri": "https://w3id.org/emmo/domain/pemfc"},
            {"title": "EMMO Manufacturing", "iri": "https://w3id.org/emmo/domain/manufacturing#"},
            {"title": "EMMO Electrochemistry", "iri": "https://w3id.org/emmo/domain/electrochemistry"},
            {"title": "CHAMEO", "iri": "https://w3id.org/emmo/domain/characterisation-methodology/chameo#"},
            {"title": "HOLY", "iri": "http://purl.org/holy/ns#"},
        ]
    )

    assert "viewBox='0 0 980 560'" in svg
    assert "y='122.0'" in svg
    assert "Declared ontology imports" in svg
    assert "EMMO Electrochemistry" in svg
