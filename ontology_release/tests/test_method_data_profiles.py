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
    assert all(row["shacl_conforms"] for row in coverage["profiles"] if row["method_profile"] != "neutron_tomography")
    neutron = next(row for row in coverage["profiles"] if row["method_profile"] == "neutron_tomography")
    assert neutron["shacl_conforms"] is False
    report = (tmp_path / "output" / "method_profiles" / "neutron_tomography" / "validation_report.json").read_text(encoding="utf-8")
    assert "neutron-flux-setting-qv" in report
    assert "quantityKind" in report
    assert "illustrative_existing_pilot" in (tmp_path / "output" / "method_profiles" / "xps" / "README.md").read_text(encoding="utf-8")


def test_tem_profile_rejects_incompatible_measurement_and_result_chain(tmp_path):
    result = build_method_data_profiles(
        ROOT / "input" / "current_ontology.jsonld",
        tmp_path / "output",
        ROOT / "output" / "examples",
    )
    assert result["status"] == "generated"
    folder = tmp_path / "output" / "method_profiles" / "tem"
    source = folder / "source_grounded_example.ttl"
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
    result = next(graph.subjects(H2KG.ofProperty, H2KG.PdNanoparticleDiameter))
    graph.remove((result, H2KG.ofProperty, H2KG.PdNanoparticleDiameter))
    graph.add((result, H2KG.ofProperty, URIRef("https://example.org/unsupported-property")))
    graph.serialize(destination=str(invalid), format="turtle")
    assert validate_method_profile_graph(shapes, invalid)["conforms"] is False

    graph = Graph().parse(source, format="turtle")
    quantity_value = next(graph.objects(result, H2KG.hasQuantityValue))
    graph.remove((quantity_value, QUDT.unit, None))
    graph.serialize(destination=str(invalid), format="turtle")
    assert validate_method_profile_graph(shapes, invalid)["conforms"] is False


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
