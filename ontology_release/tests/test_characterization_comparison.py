from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from rdflib import Graph, Namespace, RDF, URIRef
from rdflib.compare import isomorphic

from aimworks_ontology_release.characterization_comparison import (
    APP,
    CHAMEO,
    CHAMEO_COMMIT,
    CHAMEO_SHA256,
    EMMO_COMMIT,
    EMMO_IS_DESCRIPTION_FOR,
    H2KG_NAMESPACE,
    REPRESENTATION_TIERS,
    build_characterization_comparison,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def comparison_build(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path, dict]:
    chameo = ROOT / "cache" / "sources" / "chameo"
    emmo = ROOT / "cache" / "sources" / "emmo-1.0.3"
    if not (chameo / "chameo.ttl").exists() or not (emmo / "reference" / "workflow.ttl").exists():
        pytest.skip("Pinned CHAMEO/EMMO source cache is not installed")
    root = tmp_path_factory.mktemp("characterization-comparison")
    output = root / "comparison"
    local = root / "local-manuscript"
    report = build_characterization_comparison(
        ROOT / "input" / "characterization_workbook_manifest.json",
        ROOT / "output" / "characterization_kg",
        chameo,
        emmo,
        output,
        local,
    )
    return output, local, report


def test_comparison_preserves_source_and_frozen_ontologies(comparison_build) -> None:
    output, _, report = comparison_build
    assert report["case_count"] == 8
    assert report["method_family_count"] == 7
    assert report["eligible_field_count"] == report["represented_field_count"] == 1635
    assert report["source_coverage_percent"] == 100.0
    assert report["source_lock"]["chameo_commit"] == CHAMEO_COMMIT
    assert report["source_lock"]["emmo_commit"] == EMMO_COMMIT
    lock = json.loads((output / "chameo_source_lock.json").read_text(encoding="utf-8"))
    assert lock["files"][0]["sha256"] == CHAMEO_SHA256
    assert lock["direct_import_count"] == 12
    assert lock["transitive_import_count"] == 13
    assert lock["resolved_import_count"] == 25
    assert lock["complete_import_closure"] is True
    assert len(lock["files"]) == 26
    assert report["chameo_graph"]["h2kg_ontology_iri_count"] == 0


def test_chameo_graph_is_independent_and_serialization_isomorphic(comparison_build) -> None:
    output, _, report = comparison_build
    turtle = Graph().parse(output / "chameo_characterization_knowledge_graph.ttl", format="turtle")
    jsonld = Graph().parse(output / "chameo_characterization_knowledge_graph.jsonld", format="json-ld")
    assert isomorphic(turtle, jsonld)
    assert report["chameo_graph"]["turtle_jsonld_isomorphic"] is True
    assert not {
        str(value)
        for triple in turtle
        for value in triple
        if isinstance(value, URIRef) and str(value).startswith(H2KG_NAMESPACE)
    }
    tem_technique = next(turtle.subjects(RDF.type, CHAMEO.TransmissionElectronMicroscopy))
    measurement = next(turtle.objects(tem_technique, EMMO_IS_DESCRIPTION_FOR))
    assert tem_technique != measurement
    assert (measurement, RDF.type, CHAMEO.CharacterisationMeasurementProcess) in turtle


def test_all_queries_use_one_ground_truth_contract(comparison_build) -> None:
    output, _, report = comparison_build
    summary = report["query_comparison"]
    assert summary == {
        "query_count": 50,
        "expected_row_count": 952,
        "h2kg_passed": 50,
        "chameo_passed": 50,
        "answer_parity_count": 50,
        "by_sensitivity": {
            "mixed_semantic_quality": {
                "query_count": 1,
                "h2kg_passed": 1,
                "chameo_passed": 1,
                "answer_parity_count": 1,
            },
            "ontology_sensitive": {
                "query_count": 38,
                "h2kg_passed": 38,
                "chameo_passed": 38,
                "answer_parity_count": 38,
            },
            "shared_infrastructure": {
                "query_count": 11,
                "h2kg_passed": 11,
                "chameo_passed": 11,
                "answer_parity_count": 11,
            },
        },
    }
    matrix = json.loads((output / "query_comparison_matrix.json").read_text(encoding="utf-8"))["queries"]
    assert len(matrix) == 50
    assert all(row["answer_parity"] for row in matrix)
    assert all(row["h2kg_status"] == row["chameo_status"] == "pass" for row in matrix)
    assert len(list((output / "queries" / "chameo").glob("q*.rq"))) == 50
    assert len(list((output / "query_ground_truth").glob("q*_comparison.json"))) == 50


def test_representation_tiers_and_extensions_are_explicit(comparison_build) -> None:
    output, _, report = comparison_build
    mappings = json.loads((output / "source_semantic_mapping_registry.json").read_text(encoding="utf-8"))["mappings"]
    assert len(mappings) == 1635
    assert {row["representation_tier"] for row in mappings} <= REPRESENTATION_TIERS
    participation = report["representation_coverage"]["field_tier_participation_counts"]
    assert participation["native_generic"] > 0
    assert participation["native_specific"] > 0
    assert participation["declared_import"] > 0
    assert participation["shared_standard"] > 0
    assert participation["application_extension"] > 0
    assert participation["source_only"] > 0
    assert report["representation_coverage"]["domain_extension_classes"] == 0
    assert report["representation_coverage"]["domain_gap_object_properties"] == 3
    patterns = json.loads((output / "representation_pattern_registry.json").read_text(encoding="utf-8"))["patterns"]
    assert len(patterns) == 12


def test_shacl_controls_and_local_manuscript_outputs(comparison_build) -> None:
    output, local, report = comparison_build
    assert report["chameo_graph"]["shacl_conforms"] is True
    assert {item["scenario"] for item in report["chameo_graph"]["negative_tests"]} == {
        "missing_measurement_subject",
        "missing_parameter_property",
        "missing_result_provenance",
        "missing_quantity_unit",
    }
    assert all(item["conforms"] is False for item in report["chameo_graph"]["negative_tests"])
    assert (output / "comparison_report.html").exists()
    assert (local / "methods_subsection.md").exists()
    assert (local / "results_subsection.md").exists()
    assert (local / "representative_10_query_table.md").exists()
    assert (local / "supplementary_50_query_table.md").exists()
    representative = (local / "representative_10_query_table.md").read_text(encoding="utf-8")
    assert len([line for line in representative.splitlines() if line.startswith("| q")]) == 10
    supplement = (local / "supplementary_50_query_table.md").read_text(encoding="utf-8")
    assert len([line for line in supplement.splitlines() if line.startswith("| q")]) == 50


def test_outputs_do_not_expose_personal_values(comparison_build) -> None:
    output, local, _ = comparison_build
    checked = [
        output / "comparison_report.json",
        output / "comparison_report.html",
        output / "source_semantic_mapping_registry.json",
        local / "methods_subsection.md",
        local / "results_subsection.md",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in checked)
    assert not re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", text, flags=re.IGNORECASE)
