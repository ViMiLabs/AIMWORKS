from __future__ import annotations

import json
from pathlib import Path

import pytest
from rdflib import Graph, Literal, RDF, RDFS
from rdflib.compare import isomorphic

from aimworks_ontology_release.characterization_docs import (
    characterization_body,
    characterization_css,
    characterization_js,
)
from aimworks_ontology_release.characterization_kg import (
    CASE,
    EXPECTED_WORKBOOK_SHA256,
    GRAPH,
    H2KG,
    KG,
    QUDT,
    build_characterization_kg,
    write_characterization_manuscript_materials,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def characterization_build(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict]:
    root = tmp_path_factory.mktemp("characterization")
    report = build_characterization_kg(
        ROOT / "input" / "characterization_workbook_manifest.json",
        ROOT / "input" / "current_ontology.jsonld",
        root,
        taxonomy_registry_path=ROOT / "output" / "ontology" / "taxonomy_registry.json",
        taxonomy_ttl_path=ROOT / "output" / "ontology" / "h2kg-v2-taxonomy.ttl",
    )
    return root / "characterization_kg", report


def test_manifest_is_sanitized_complete_and_fingerprinted() -> None:
    manifest = json.loads((ROOT / "input" / "characterization_workbook_manifest.json").read_text(encoding="utf-8"))
    assert manifest["source"]["sha256"] == EXPECTED_WORKBOOK_SHA256
    assert manifest["case_count"] == 8
    assert manifest["method_family_count"] == 7
    assert {item["key"] for item in manifest["cases"]} == {
        "tem", "sem", "afm", "fib_sem", "ic_sem", "neutron_tomography",
        "synchrotron_radiography", "synchrotron_tomography",
    }
    assert manifest["eligible_field_count"] == 1635
    assert manifest["excluded_field_count"] == 40
    assert {item["field"] for item in manifest["excluded_fields"]} == {
        "Author", "Email", "ORCID", "Institution", "FoundingBody"
    }
    source_records = [record for case in manifest["cases"] for record in case["source_records"]]
    assert len(source_records) == 1635
    assert not any(record["field"] in {"Author", "Email", "ORCID", "Institution", "FoundingBody"} for record in source_records)
    assert not any("@" in str(record.get("raw_value", "")) for record in source_records)


def test_build_preserves_every_eligible_field_and_serialization_parity(characterization_build) -> None:
    target, report = characterization_build
    assert report["ontology_version"] == "2.3.0"
    assert report["ontology_modified"] is False
    assert report["case_count"] == 8
    assert report["represented_field_count"] == report["eligible_field_count"] == 1635
    assert report["source_coverage_percent"] == 100.0
    assert sum(report["source_status_counts"].values()) == 1635
    assert report["source_status_counts"]["missing"] > 0
    assert report["source_status_counts"]["semantic_conflict"] == 1
    assert report["shacl_conforms"] is True
    assert {item["scenario"] for item in report["negative_tests"]} == {
        "missing_measurement_subject",
        "missing_parameter_property",
        "missing_result_provenance",
        "missing_quantity_unit",
    }
    assert all(item["conforms"] is False for item in report["negative_tests"])
    assert report["turtle_jsonld_isomorphic"] is True
    turtle = Graph().parse(target / "characterization_knowledge_graph.ttl", format="turtle")
    jsonld = Graph().parse(target / "characterization_knowledge_graph.jsonld", format="json-ld")
    assert isomorphic(turtle, jsonld)
    assert len(set(turtle.subjects(RDF.type, KG.SourceField))) == 1635
    assert len(list((target / "cases").glob("*.ttl"))) == 8


def test_tem_queryable_chain_and_missing_states(characterization_build) -> None:
    target, _ = characterization_build
    graph = Graph().parse(target / "cases" / "tem.ttl", format="turtle")
    measurement = next(graph.subjects(RDF.type, H2KG.TransmissionElectronMicroscopyImaging))
    specimen = next(graph.objects(measurement, H2KG.hasMeasurementSubject))
    instrument = next(graph.objects(measurement, H2KG.usesInstrument))
    assert (specimen, RDF.type, H2KG.Matter) in graph
    assert (instrument, RDF.type, H2KG.TEMInstrument) in graph
    result = next(graph.subjects(RDF.type, H2KG.DataPoint))
    prop = next(graph.objects(result, H2KG.ofProperty))
    assert (prop, RDF.type, H2KG.MeanParticleSize) in graph
    assert (prop, H2KG.isCharacteristicOf, specimen) in graph
    qv = next(graph.objects(prop, H2KG.hasQuantityValue))
    assert str(next(graph.objects(qv, QUDT.numericValue))) in {"5", "5.0"}
    assert str(next(graph.objects(qv, QUDT.unit))).endswith("NanoM")
    assert str(next(graph.objects(qv, RDFS.label))) == "5 nm"
    mix_steps = {
        subject
        for subject in graph.subjects(RDFS.label, Literal("Mix"))
        if (subject, RDF.type, H2KG.Manufacturing) in graph
    }
    assert len(mix_steps) == 1
    mix_step = next(iter(mix_steps))
    assert len(set(graph.objects(mix_step, H2KG.hasInputMaterial))) == 2
    assert (mix_step, RDF.type, H2KG.MixingOrDispersionProcess) in graph
    sonication = next(graph.subjects(RDFS.label, Literal("Sonification")))
    assert (sonication, RDF.type, H2KG.Sonication) in graph
    working_distance_records = [
        item
        for item in graph.subjects(RDF.type, H2KG.Parameter)
        if "WorkingDistance" in str(next(graph.objects(item, RDFS.label), ""))
    ]
    assert working_distance_records
    assert any(str(next(graph.objects(item, KG.valueStatus))).endswith("unconfirmed") for item in working_distance_records)


def test_parameter_records_do_not_reclassify_properties(characterization_build) -> None:
    target, _ = characterization_build
    graph = Graph().parse(target / "characterization_knowledge_graph.ttl", format="turtle")
    records = set(graph.subjects(RDF.type, H2KG.Parameter))
    assert records
    for record in records:
        occurrences = list(graph.objects(record, H2KG.ofProperty))
        assert len(occurrences) == 1
        assert (occurrences[0], RDF.type, H2KG.Parameter) not in graph
        assert len(list(graph.objects(occurrences[0], H2KG.isCharacteristicOf))) == 1
    afm = Graph().parse(target / "cases" / "afm.ttl", format="turtle")
    scan_rate_occurrences = set(afm.subjects(RDF.type, H2KG.FrequencyCharacteristic))
    assert scan_rate_occurrences
    assert not list(afm.subjects(RDF.type, H2KG.AFMScanSpeed))


def test_conservative_source_conflicts_are_findings_not_quantities(characterization_build) -> None:
    target, _ = characterization_build
    fib = Graph().parse(target / "cases" / "fib_sem.ttl", format="turtle")
    volume_prop = next(
        subject
        for subject in fib.subjects(RDF.type, H2KG.CompositionCharacteristic)
        if str(next(fib.objects(subject, RDFS.label), "")).casefold() == "volume fraction"
    )
    assert not list(fib.objects(volume_prop, H2KG.hasQuantityValue))
    findings = {str(value) for finding in fib.subjects(RDF.type, KG.ValidationFinding) for value in fib.objects(finding, KG.findingCode)}
    assert "label_unit_conflict" in findings
    assert "unit_unresolved" in findings
    neutron = Graph().parse(target / "cases" / "neutron_tomography.ttl", format="turtle")
    barycenter = next(
        subject
        for subject in neutron.subjects(RDF.type, H2KG.GeometricCharacteristic)
        if str(next(neutron.objects(subject, RDFS.label), "")) == "AverageBaryCenter"
    )
    assert not list(neutron.objects(barycenter, H2KG.hasQuantityValue))
    synchrotron = Graph().parse(target / "cases" / "synchrotron_tomography.ttl", format="turtle")
    ratio = next(
        subject
        for subject in synchrotron.subjects(RDF.type, H2KG.CompositionCharacteristic)
        if str(next(synchrotron.objects(subject, RDFS.label), "")).casefold().endswith("ratio")
    )
    assert not list(synchrotron.objects(ratio, H2KG.hasQuantityValue))


def test_queries_and_browser_package_are_deterministic(characterization_build) -> None:
    target, report = characterization_build
    counts = {item["id"]: item["row_count"] for item in report["queries"]}
    assert len(counts) == 50
    assert {key: counts[key] for key in [
        "q1_tem_specimen_preparation",
        "q2_tem_instrument_settings",
        "q3_tem_dataset_analysis",
        "q4_tem_result_value",
        "q5_all_measurement_contexts",
        "q6_all_result_records",
        "q7_source_status_summary",
        "q8_all_measurement_parameters",
        "q9_conservative_quantity_findings",
        "q10_source_provenance_coverage",
        "q11_software_provenance",
        "q12_neutron_processing_chain",
    ]} == {
        "q1_tem_specimen_preparation": 6,
        "q2_tem_instrument_settings": 8,
        "q3_tem_dataset_analysis": 1,
        "q4_tem_result_value": 1,
        "q5_all_measurement_contexts": 8,
        "q6_all_result_records": 24,
        "q7_source_status_summary": 37,
        "q8_all_measurement_parameters": 134,
        "q9_conservative_quantity_findings": 27,
        "q10_source_provenance_coverage": 8,
        "q11_software_provenance": 31,
        "q12_neutron_processing_chain": 4,
    }
    assert all(item["category"] and item["question"] for item in report["queries"])
    assert report["query_validation"] == {
        "query_count": 50,
        "passed_query_count": 50,
        "failed_query_count": 0,
        "expected_row_count": 952,
        "observed_row_count": 952,
        "matched_row_count": 952,
        "method": "SPARQL result rows compared exactly with manifest-derived ground truth",
    }
    workbench = json.loads((target / "characterization_query_workbench.json").read_text(encoding="utf-8"))
    assert workbench["default_query"] == "q1_tem_specimen_preparation"
    assert len(workbench["cases"]) == 8
    assert len(workbench["queries"]) == 50
    assert "nodes" not in workbench and "links" not in workbench
    assert all(item["query"].startswith("PREFIX h2kg:") for item in workbench["queries"])
    assert all(item["category"] and item["question"] for item in workbench["queries"])
    assert all(item["validation"]["exact_match"] for item in workbench["queries"])
    assert not (target / "characterization_web_graph.json").exists()
    assert len(list((target / "query_ground_truth").glob("q*_expected.csv"))) == 50
    assert len(list((target / "query_ground_truth").glob("q*_comparison.json"))) == 50
    assert (target / "query_ground_truth" / "query_ground_truth_validation.csv").exists()
    assert (target / "run_demo.py").exists()
    assert (target / "characterization_kg_demo.ipynb").exists()


def test_characterization_page_is_dependency_free_and_downloadable(characterization_build, tmp_path: Path) -> None:
    target, report = characterization_build
    page = characterization_body(report, tmp_path / "pages" / "characterization-knowledge-graph.html", tmp_path)
    assert "Validated SPARQL competency workbench" in page
    assert "Ground-truth validation" in page
    assert "Observed RDFLib result" in page
    assert "Workbook-derived ground truth" in page
    assert "50 release-tested questions" in page
    assert "Scientific question" in page
    assert "characterization_knowledge_graph.trig" in page
    assert "query_ground_truth_validation.csv" in page
    assert "cdn.jsdelivr" not in page
    assert "kg-graph" not in page
    assert "#kg-graph" not in characterization_css()
    script = characterization_js()
    assert "default_query" in (target / "characterization_query_workbench.json").read_text(encoding="utf-8")
    assert "fetch(root.dataset.package)" in script
    assert "missing_expected_rows" in script
    assert "item.question" in script
    assert "queryQuestion" in script
    assert "data.nodes" not in script and "data.links" not in script


def test_local_manuscript_materials_are_generated_outside_release(characterization_build, tmp_path: Path) -> None:
    target, _ = characterization_build
    local = tmp_path / "local_manuscript"
    result = write_characterization_manuscript_materials(target, local)
    assert result["status"] == "generated"
    assert (local / "methods_subsection.md").exists()
    assert (local / "results_subsection.md").exists()
    assert (local / "manuscript_section_kg_construction_and_query_evaluation.md").exists()
    assert (local / "representative_query_table.md").exists()
    assert (local / "query_table.md").exists()
    assert (local / "workflow_to_kg_figure.svg").exists()
    assert "Fifty questions were prespecified" in (local / "methods_subsection.md").read_text(encoding="utf-8")
    manuscript_section = (local / "manuscript_section_kg_construction_and_query_evaluation.md").read_text(encoding="utf-8")
    assert "Fifty questions" in manuscript_section
    assert "H₂KG provided the common semantic paths" in manuscript_section
    assert "Representative ontology-backed competency queries" in manuscript_section
    assert "not independent experimental measurements" in manuscript_section
    representative_table = (local / "representative_query_table.md").read_text(encoding="utf-8")
    assert "Plain-language question" in representative_table
    assert len([
        line for line in representative_table.splitlines()
        if line.startswith("| Q") and not line.startswith("| Query")
    ]) == 10
    query_table = (local / "query_table.md").read_text(encoding="utf-8")
    assert "Plain-language question" in query_table
    assert query_table.count("\n|") == 51

