from __future__ import annotations

import json
from pathlib import Path

import pytest
from rdflib import Graph, URIRef
from rdflib.compare import isomorphic

from aimworks_ontology_release.characterization_comparison import (
    APP,
    CHAMEO,
    EMMO_HAS_DETERMINED_PROPERTY,
    QUDT,
)
from aimworks_ontology_release.characterization_kg import H2KG, KG
from aimworks_ontology_release.characterization_native_benchmark import (
    CHAMEO_COMMIT,
    CONTROL_QUERY_IDS,
    build_native_characterization_benchmark,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def native_build(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path, dict]:
    chameo = ROOT / "cache" / "sources" / "chameo"
    emmo = ROOT / "cache" / "sources" / "emmo-1.0.3"
    if not (chameo / "chameo.ttl").exists() or not (emmo / "reference" / "workflow.ttl").exists():
        pytest.skip("Pinned CHAMEO/EMMO source cache is not installed")
    root = tmp_path_factory.mktemp("characterization-native-benchmark")
    output = root / "benchmark"
    local = root / "local"
    report = build_native_characterization_benchmark(
        ROOT / "input" / "characterization_workbook_manifest.json",
        ROOT / "output" / "characterization_kg",
        chameo,
        emmo,
        output,
        local,
    )
    return output, local, report


def test_strict_graphs_exclude_adapter_vocabularies(native_build) -> None:
    output, _, report = native_build
    forbidden_by_graph = {
        "h2kg": (str(KG), str(APP), str(CHAMEO)),
        "chameo": (str(APP), str(KG), str(H2KG)),
    }
    for name, forbidden_namespaces in forbidden_by_graph.items():
        graph = Graph().parse(output / f"strict_{name}_semantic_graph.ttl", format="turtle")
        assert not {
            str(value)
            for triple in graph
            for value in triple
            if isinstance(value, URIRef)
            and any(str(value).startswith(namespace) for namespace in forbidden_namespaces)
        }
        jsonld = Graph().parse(output / f"strict_{name}_semantic_graph.jsonld", format="json-ld")
        assert isomorphic(graph, jsonld)
        assert report["graph_statistics"][name]["turtle_jsonld_isomorphic"] is True


def test_source_controls_are_not_scored_as_ontology_capability(native_build) -> None:
    output, _, report = native_build
    summary = report["query_benchmark"]
    assert summary["question_count"] == 50
    assert summary["scored_query_count"] == 37
    assert summary["unscored_control_count"] == len(CONTROL_QUERY_IDS) == 13
    matrix = json.loads((output / "native_query_matrix.json").read_text(encoding="utf-8"))["queries"]
    controls = {row["query_id"] for row in matrix if row["assessment_scope"] != "strict_ontology_semantics"}
    assert controls == CONTROL_QUERY_IDS
    assert all(row["h2kg_status"] == row["chameo_status"] == "not_scored" for row in matrix if row["query_id"] in controls)


def test_benchmark_does_not_force_answer_parity(native_build) -> None:
    _, _, report = native_build
    summary = report["query_benchmark"]
    assert summary["h2kg"]["queries_passed"] <= summary["scored_query_count"]
    assert summary["chameo"]["queries_passed"] <= summary["scored_query_count"]
    assert summary["h2kg"]["matched_rows"] >= summary["chameo"]["matched_rows"]
    assert report["excluded_preliminary_method"]["publication_status"] == "not_a_benchmark"
    assert report["benchmark_policy"]["cross_graph_translation"] is False
    assert report["benchmark_policy"]["ontology_tbox_modification"] is False
    assert report["benchmark_policy"]["comparison_type"] == "balanced_ontology_neutral_characterization_record_benchmark"


def test_balanced_contract_drives_the_conclusion(native_build) -> None:
    output, _, report = native_build
    contract = report["benchmark_contract"]
    summary = report["balanced_benchmark"]
    conclusion = report["balanced_conclusion"]
    assert contract["requirement_count"] == 13
    assert contract["selection_strata"] == {
        "analysis_lineage": 1,
        "data_processing": 1,
        "measurement_context": 1,
        "measurement_settings": 2,
        "methodology_description": 1,
        "result_provenance": 1,
        "result_semantics": 2,
        "selected_profile_vocabulary": 1,
        "software_traceability": 1,
        "specimen_preparation": 1,
        "workflow_structure": 1,
    }
    assert all(
        "h2kg" not in stratum.casefold() and "chameo" not in stratum.casefold()
        for stratum in contract["selection_strata"]
    )
    assert summary["requirement_count"] == 13
    assert summary["assessment_type_counts"] == {
        "native_vocabulary_coverage": 1,
        "query_based_retrieval": 10,
        "query_retrieval_and_native_pattern_assessment": 2,
    }
    assert conclusion["supported"] is True
    assert all(
        value is True
        for key, value in conclusion["rules"].items()
        if key not in {"h2kg_specific_method_count", "chameo_specific_method_count"}
    )
    matrix = {
        row["requirement_id"]: row
        for row in report["balanced_requirement_matrix"]
    }
    assert matrix["b03_valued_measurement_setting"]["h2kg_status"] == "exact"
    assert matrix["b03_valued_measurement_setting"]["chameo_status"] == "not_supported_under_benchmark_mapping_rules"
    assert matrix["b03_valued_measurement_setting"]["assessment_type"] == "query_retrieval_and_native_pattern_assessment"
    assert matrix["b03_valued_measurement_setting"]["h2kg_query_executed"] is True
    assert matrix["b03_valued_measurement_setting"]["chameo_query_executed"] is False
    assert matrix["b03_valued_measurement_setting"]["chameo_assessment_mode"] == "native_pattern_assessment"
    assert matrix["b11_workflow_task_grouping"]["chameo_status"] == "exact"
    assert matrix["b11_workflow_task_grouping"]["h2kg_status"] == "exact"
    assert matrix["b11_workflow_task_grouping"]["h2kg_representation_tier"] == "generic_direct_native"
    assert matrix["b11_workflow_task_grouping"]["chameo_representation_tier"] == "direct_native"
    assert matrix["b12_technique_occurrence_separation"]["chameo_status"] == "exact"
    assert matrix["b12_technique_occurrence_separation"]["h2kg_status"] == "not_supported_under_benchmark_mapping_rules"
    assert matrix["b12_technique_occurrence_separation"]["h2kg_query_executed"] is False
    assert matrix["b12_technique_occurrence_separation"]["chameo_query_executed"] is True
    assert matrix["b13_case_method_specificity"]["h2kg_status"] == "exact"
    assert matrix["b13_case_method_specificity"]["chameo_status"] == "partial"
    assert matrix["b13_case_method_specificity"]["h2kg_assessment_mode"] == "native_vocabulary_coverage"
    assert matrix["b13_case_method_specificity"]["chameo_assessment_mode"] == "native_vocabulary_coverage"
    assert matrix["b13_case_method_specificity"]["h2kg_matched"] == 8
    assert matrix["b13_case_method_specificity"]["chameo_matched"] == 3
    assert (output / "balanced_requirement_matrix.csv").exists()
    assert (output / "balanced_conclusion_rules.json").exists()


def test_native_capability_gaps_are_reported_not_inserted(native_build) -> None:
    output, _, report = native_build
    capabilities = {row["capability"]: row for row in report["capability_matrix"]}
    assert capabilities["Parameter-to-characteristic/value"]["chameo"] == "native_pattern_not_identified_under_mapping_rules"
    assert capabilities["Result-to-property association"]["chameo"] == "declared_import_application_pattern"
    chameo = Graph().parse(output / "strict_chameo_semantic_graph.ttl", format="turtle")
    assert not set(chameo.triples((None, APP.describesCharacteristic, None)))
    assert not set(chameo.triples((None, APP.reportsProperty, None)))
    assert not set(chameo.triples((None, APP.isResultOfMeasurement, None)))
    assert set(chameo.triples((None, EMMO_HAS_DETERMINED_PROPERTY, None)))


def test_nonduplicated_semantic_diagnostics_expose_complementarity(native_build) -> None:
    _, _, report = native_build
    diagnostics = {
        row["contract_id"]: row
        for row in report["query_benchmark"]["semantic_contract_diagnostics"]
    }
    assert diagnostics["measurement_context"]["h2kg"]["status"] == "pass"
    assert diagnostics["measurement_context"]["chameo"]["status"] == "pass"
    assert diagnostics["measurement_parameter_identity"]["chameo"]["matched_rows"] > 0
    assert diagnostics["normalized_measurement_parameter_value"]["h2kg"]["status"] == "pass"
    assert diagnostics["normalized_measurement_parameter_value"]["chameo"]["matched_rows"] == 0
    assert diagnostics["result_property_bearer_association"]["chameo"]["unexpected_rows"] > 0


def test_pinned_sources_validation_and_local_material(native_build) -> None:
    output, local, report = native_build
    assert report["source_lock"]["chameo_commit"] == CHAMEO_COMMIT
    assert report["source_lock"]["direct_import_count"] == 12
    assert report["source_lock"]["transitive_import_count"] == 13
    assert report["source_lock"]["resolved_import_count"] == 25
    assert report["source_lock"]["complete_import_closure"] is True
    assert report["shacl"]["chameo"]["conforms"] is True
    assert all(item["conforms"] is False for item in report["shacl"]["chameo"]["negative_tests"])
    assert report["mapping_coverage"]["eligible_source_fields"] == 1635
    assert report["mapping_coverage"]["h2kg_unique_source_fields"] == 1635
    assert report["mapping_coverage"]["h2kg_mapping_assertions"] == 1659
    assert report["mapping_coverage"]["h2kg_additional_assertions_for_multimapped_fields"] == 24
    assert report["mapping_coverage"]["chameo_mapping_rows"] == 1635
    assert (output / "native_capability_matrix.md").exists()
    assert (output / "chameo_native_mapping_registry.csv").exists()
    assert (output / "h2kg_source_semantic_mapping_registry.csv").exists()
    assert (output / "method_specificity_matrix.csv").exists()
    assert (output / "benchmark_contract.json").exists()
    assert (output / "ontology_evidence_audit.json").exists()
    assert (output / "ontology_evidence_audit.md").exists()
    assert (output / "mapping_policy_constraints.csv").exists()
    assert (output / "benchmark_population_audit.json").exists()
    population = report["benchmark_population_audit"]
    assert population["record_count"] == 8
    assert population["method_family_count"] == 7
    assert population["unique_profile_count"] == 7
    assert population["measurement_settings"]["distinct_identities"] == 131
    assert population["measurement_settings"]["normalized_value_rows"] == 107
    assert population["reported_results"]["distinct_records"] == 24
    assert population["reported_results"]["normalized_value_rows"] == 13
    assert (output / "comparison_report.html").exists()
    assert (output / "cases" / "h2kg" / "tem.ttl").exists()
    assert (output / "cases" / "chameo" / "tem.ttl").exists()
    assert (local / "methods_subsection.md").exists()
    assert (local / "results_subsection.md").exists()
    assert (local / "manuscript_ready_benchmark_section.md").exists()
    requirement_table = (local / "fair_13_requirement_table.md").read_text(encoding="utf-8")
    assert "Native-pattern assessment; no SPARQL query executed" in requirement_table
    manuscript = (local / "methods_subsection.md").read_text(encoding="utf-8")
    assert "13 requirements" in manuscript.lower()
    assert "constructed independently" in manuscript.lower()
    assert "no local class or relation was admitted" in manuscript
    assert "not an overall ontology ranking" not in manuscript.lower()


def test_complete_import_closure_supports_parameter_gap_finding(native_build) -> None:
    output, _, report = native_build
    audit = report["ontology_evidence_audit"]
    parameter = audit["measurement_parameter"]
    assert audit["complete_import_closure"] is True
    assert audit["resolved_import_count"] == 25
    assert parameter["is_emmo_mathematical_parameter"] is True
    assert parameter["is_emmo_quantity"] is False
    assert parameter["is_emmo_referent"] is False
    assert parameter["emmo_has_property_domain_applicable"] is False
    assert parameter["emmo_has_quantity_value_domain_applicable"] is False
    assert parameter["declared_applicable_property_relations"] == []
    assert parameter["declared_applicable_value_relations"] == []
    assert audit["result_semantics"]["data_analysis_is_declared_emmo_determination"] is False
    assert all(item["chameo_terms_present"] for item in audit["method_specificity"])
    report_text = (output / "comparison_report.html").read_text(encoding="utf-8").casefold()
    assert "not an overall ontology ranking" not in report_text


def test_web_workbench_exposes_plain_questions_results_and_rdf_evidence(native_build) -> None:
    output, _, report = native_build
    package_path = output / "comparison_query_workbench.json"
    assert package_path.exists()
    package = json.loads(package_path.read_text(encoding="utf-8"))
    assert package["default_requirement"] == "b03_valued_measurement_setting"
    assert package["summary"] == report["balanced_benchmark"]
    assert len(package["requirements"]) == 13
    assert all(item["question"] and item["source_basis"] for item in package["requirements"])
    assert all(set(item["ontologies"]) == {"h2kg", "chameo"} for item in package["requirements"])

    context = next(item for item in package["requirements"] if item["id"] == "b01_measurement_context")
    assert context["ontologies"]["h2kg"]["rows"]
    assert context["ontologies"]["chameo"]["rows"]
    h2kg_evidence = json.loads(
        (output / context["ontologies"]["h2kg"]["evidence_path"]).read_text(encoding="utf-8")
    )
    chameo_evidence = json.loads(
        (output / context["ontologies"]["chameo"]["evidence_path"]).read_text(encoding="utf-8")
    )
    assert h2kg_evidence["entries"] and chameo_evidence["entries"]
    assert h2kg_evidence["entries"][0]["graph"]["edges"]
    assert chameo_evidence["entries"][0]["graph"]["edges"]

    valued = next(item for item in package["requirements"] if item["id"] == "b03_valued_measurement_setting")
    assert valued["ontologies"]["h2kg"]["status"] == "exact"
    assert valued["assessment_type"] == "query_retrieval_and_native_pattern_assessment"
    assert valued["ontologies"]["chameo"]["status"] == "not_supported_under_benchmark_mapping_rules"
    assert valued["ontologies"]["h2kg"]["query_executed"] is True
    assert valued["ontologies"]["chameo"]["query_executed"] is False
    assert valued["ontologies"]["chameo"]["assessment_mode"] == "native_pattern_assessment"
    valued_evidence = json.loads(
        (output / valued["ontologies"]["h2kg"]["evidence_path"]).read_text(encoding="utf-8")
    )
    predicates = {
        edge["predicate"]
        for edge in valued_evidence["entries"][0]["graph"]["edges"]
    }
    assert {
        str(H2KG.hasParameter),
        str(H2KG.ofProperty),
        str(H2KG.hasQuantityValue),
        str(QUDT.numericValue),
        str(QUDT.unit),
    }.issubset(predicates)
    gap = json.loads(
        (output / valued["ontologies"]["chameo"]["evidence_path"]).read_text(encoding="utf-8")
    )
    assert gap["entries"][0]["graph"]["kind"] == "gap_evidence"
