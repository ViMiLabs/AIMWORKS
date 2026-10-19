from __future__ import annotations

import json
from pathlib import Path

from rdflib import Graph, RDF, URIRef

from aimworks_ontology_release.method_data_profiles import H2KG, QUDT, build_method_data_profiles, validate_method_profile_graph


ROOT = Path(__file__).resolve().parents[1]


def test_method_profiles_generate_and_classify_existing_examples(tmp_path):
    result = build_method_data_profiles(
        ROOT / "input" / "current_ontology.jsonld",
        tmp_path / "output",
        ROOT / "output" / "examples",
    )

    assert result["status"] == "generated"
    assert result["profile_count"] == 9
    coverage = json.loads((tmp_path / "output" / "method_profiles" / "profile_coverage_report.json").read_text(encoding="utf-8"))
    assert len(coverage["profiles"]) == 9
    assert all(row["status"] == "generated" for row in coverage["profiles"])
    assert all(row["shacl_conforms"] for row in coverage["profiles"])
    tem = next(row for row in coverage["profiles"] if row["method_profile"] == "tem")
    assert tem["evidence_status"] == "illustrative_synthetic"
    assert (tmp_path / "output" / "method_profiles" / "tem" / "synthetic_example.ttl").exists()
    assert not (tmp_path / "output" / "method_profiles" / "tem" / "source_grounded_example.ttl").exists()
    neutron = next(row for row in coverage["profiles"] if row["method_profile"] == "neutron_tomography")
    assert neutron["shacl_conforms"] is True
    assert neutron["curation_finding_count"] == 1
    report = json.loads(
        (tmp_path / "output" / "method_profiles" / "neutron_tomography" / "validation_report.json").read_text(encoding="utf-8")
    )
    assert report["curation_findings"] == [
        {
            "code": "reported-unit-awaits-qudt-mapping",
            "field": "NeutronFlux",
            "severity": "curation_required",
            "treatment": (
                "The reported numeric value 2700000 and source unit token n/cm2s "
                "are retained as Metadata; no QuantityValue is asserted until exact "
                "QUDT unit and quantity-kind mappings are approved."
            ),
        }
    ]
    neutron_graph = Graph().parse(
        tmp_path / "output" / "method_profiles" / "neutron_tomography" / "source_grounded_example.ttl",
        format="turtle",
    )
    record = next(
        item
        for item in neutron_graph.subjects(RDF.type, H2KG.Parameter)
        if (next(neutron_graph.objects(item, H2KG.ofProperty), None), RDF.type, H2KG.NeutronFlux) in neutron_graph
    )
    occurrence = next(neutron_graph.objects(record, H2KG.ofProperty))
    assert list(neutron_graph.objects(occurrence, H2KG.hasQuantityValue)) == []
    metadata_text = " ".join(
        str(value)
        for metadata in neutron_graph.objects(record, H2KG.hasMetadata)
        for _, value in neutron_graph.predicate_objects(metadata)
    )
    assert "2700000" in metadata_text
    assert "n/cm2s" in metadata_text
    assert "illustrative_existing_pilot" in (tmp_path / "output" / "method_profiles" / "xps" / "README.md").read_text(encoding="utf-8")


def test_tem_profile_rejects_incompatible_measurement_and_result_chain(tmp_path):
    result = build_method_data_profiles(
        ROOT / "input" / "current_ontology.jsonld",
        tmp_path / "output",
        ROOT / "output" / "examples",
    )
    assert result["status"] == "generated"
    folder = tmp_path / "output" / "method_profiles" / "tem"
    source = folder / "synthetic_example.ttl"
    shapes = folder / "tem_profile_shapes.ttl"
    assert validate_method_profile_graph(shapes, source)["conforms"] is True

    graph = Graph().parse(source, format="turtle")
    measurement = next(graph.subjects(RDF.type, H2KG.TransmissionElectronMicroscopyImaging))
    graph.remove((measurement, RDF.type, H2KG.TransmissionElectronMicroscopyImaging))
    invalid = tmp_path / "invalid-tem.ttl"
    graph.serialize(destination=str(invalid), format="turtle")
    assert validate_method_profile_graph(shapes, invalid)["conforms"] is False

    graph = Graph().parse(source, format="turtle")
    graph.remove((measurement, H2KG.hasOutputData, None))
    graph.serialize(destination=str(invalid), format="turtle")
    assert validate_method_profile_graph(shapes, invalid)["conforms"] is False

    graph = Graph().parse(source, format="turtle")
    result = next(graph.subjects(RDF.type, H2KG.DataPoint))
    property_occurrence = next(graph.objects(result, H2KG.ofProperty))
    assert (property_occurrence, RDF.type, H2KG.PdNanoparticleDiameter) in graph
    graph.remove((property_occurrence, RDF.type, H2KG.PdNanoparticleDiameter))
    graph.add((property_occurrence, RDF.type, URIRef("https://example.org/unsupported-property")))
    graph.serialize(destination=str(invalid), format="turtle")
    assert validate_method_profile_graph(shapes, invalid)["conforms"] is False

    graph = Graph().parse(source, format="turtle")
    result = next(graph.subjects(RDF.type, H2KG.DataPoint))
    property_occurrence = next(graph.objects(result, H2KG.ofProperty))
    quantity_value = next(graph.objects(property_occurrence, H2KG.hasQuantityValue))
    graph.remove((quantity_value, QUDT.unit, None))
    graph.serialize(destination=str(invalid), format="turtle")
    assert validate_method_profile_graph(shapes, invalid)["conforms"] is False


def test_tem_profile_separates_parameter_records_from_properties(tmp_path):
    build_method_data_profiles(
        ROOT / "input" / "current_ontology.jsonld",
        tmp_path / "output",
        ROOT / "output" / "examples",
    )
    graph = Graph().parse(
        tmp_path / "output" / "method_profiles" / "tem" / "synthetic_example.ttl",
        format="turtle",
    )
    measurement = next(graph.subjects(RDF.type, H2KG.TransmissionElectronMicroscopyImaging))
    records = list(graph.objects(measurement, H2KG.hasParameter))
    assert records
    for record in records:
        assert (record, RDF.type, H2KG.Parameter) in graph
        occurrence = next(graph.objects(record, H2KG.ofProperty))
        occurrence_types = set(graph.objects(occurrence, RDF.type))
        assert H2KG.Parameter not in occurrence_types
        assert occurrence_types


def test_sem_profile_allows_explicitly_unreported_result(tmp_path):
    result = build_method_data_profiles(
        ROOT / "input" / "current_ontology.jsonld",
        tmp_path / "output",
        ROOT / "output" / "examples",
    )
    assert result["status"] == "generated"
    report = json.loads((tmp_path / "output" / "method_profiles" / "sem" / "validation_report.json").read_text(encoding="utf-8"))
    assert report["conforms"] is True
    assert any(item["value"] == "not reported" for item in report["scenario"]["results"])
