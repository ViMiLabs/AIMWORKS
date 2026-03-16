from __future__ import annotations

from pathlib import Path

from rdflib import Graph, URIRef

from aimworks_ontology_release.io import graph_from_text
from aimworks_ontology_release.release import run_pipeline
from aimworks_ontology_release.unit_enrichment import enrich_units_from_cleaned_dataset
from aimworks_ontology_release.utils import QUDT, read_csv


UNIT_FIXTURE_TTL = """
@prefix h2kg: <https://w3id.org/h2kg/hydrogen-ontology#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<https://w3id.org/h2kg/hydrogen-ontology> a owl:Ontology .
h2kg:hasQuantityValue a owl:ObjectProperty .
h2kg:Property a owl:Class ; rdfs:label "Property"@en .
h2kg:Parameter a owl:Class ; rdfs:label "Parameter"@en .
h2kg:CellResistance a h2kg:Property ; rdfs:label "Cell Resistance"@en .
h2kg:AreaSpecificResistance a h2kg:Property ; rdfs:label "Area Specific Resistance"@en .
"""


def _write_unit_evidence(root: Path, datapoint_rows: list[str], unit_rows: list[str], fill_rows: list[str] | None = None) -> Path:
    evidence_dir = root / "unit-evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    datapoints = "\n".join(
        [
            "datapoint_uid,of_property_iri,has_condition_iris,quantity_kind_iri,unit_key,datapoint_kind,source_file",
            *datapoint_rows,
        ]
    )
    units = "\n".join(
        [
            "unit_key,qudt_unit_iri,ucum_code,unit_label,raw_unit_examples,resolution_method,needs_mapping,tool_name,tool_version,merge_timestamp_utc",
            *unit_rows,
        ]
    )
    (evidence_dir / "datapoints.csv").write_text(datapoints + "\n", encoding="utf-8")
    (evidence_dir / "units.csv").write_text(units + "\n", encoding="utf-8")
    if fill_rows is not None:
        fill = "\n".join(
            [
                "unit_key,unit_label,ucum_code,matched_ucum,qudt_unit_iri,status",
                *fill_rows,
            ]
        )
        (evidence_dir / "qudt_fill_report_iter4.csv").write_text(fill + "\n", encoding="utf-8")
    return evidence_dir


def test_unit_enrichment_adds_qudt_unit(configs, temp_project):
    schema_graph = graph_from_text(UNIT_FIXTURE_TTL, "turtle")
    controlled_graph = Graph()
    for triple in schema_graph.triples((URIRef("https://w3id.org/h2kg/hydrogen-ontology#CellResistance"), None, None)):
        controlled_graph.add(triple)
    for triple in schema_graph.triples((URIRef("https://w3id.org/h2kg/hydrogen-ontology#Property"), None, None)):
        controlled_graph.add(triple)

    evidence_dir = _write_unit_evidence(
        temp_project,
        [
            "dp1,https://w3id.org/h2kg/hydrogen-ontology#CellResistance,,http://qudt.org/vocab/quantitykind/ElectricResistance,u1,measurement,GT_A.xlsx",
            "dp2,https://w3id.org/h2kg/hydrogen-ontology#CellResistance,,http://qudt.org/vocab/quantitykind/ElectricResistance,u1,measurement,GT_B.xlsx",
        ],
        [
            "u1,http://qudt.org/vocab/unit/OHM,Ohm,ohm,ohm,temp_from_raw_string,False,test,1.0,2026-03-16T00:00:00Z",
        ],
    )

    release_profile = dict(configs["release_profile"])
    release_profile["unit_enrichment"] = {"enabled": True, "min_observations": 1, "min_consensus_ratio": 0.8, "create_local_units": True}
    report = enrich_units_from_cleaned_dataset(
        schema_graph,
        controlled_graph,
        release_profile,
        configs["namespace_policy"],
        temp_project,
        evidence_dir=evidence_dir,
    )

    term = URIRef("https://w3id.org/h2kg/hydrogen-ontology#CellResistance")
    qv_nodes = list(controlled_graph.objects(term, URIRef("https://w3id.org/h2kg/hydrogen-ontology#hasQuantityValue")))
    assert qv_nodes
    assert list(controlled_graph.objects(qv_nodes[0], QUDT.unit)) == [URIRef("http://qudt.org/vocab/unit/OHM")]
    assert report["terms_enriched"] == 1


def test_unit_enrichment_creates_local_reviewed_unit(configs, temp_project):
    schema_graph = graph_from_text(UNIT_FIXTURE_TTL, "turtle")
    controlled_graph = Graph()
    for triple in schema_graph.triples((URIRef("https://w3id.org/h2kg/hydrogen-ontology#AreaSpecificResistance"), None, None)):
        controlled_graph.add(triple)
    for triple in schema_graph.triples((URIRef("https://w3id.org/h2kg/hydrogen-ontology#Property"), None, None)):
        controlled_graph.add(triple)

    evidence_dir = _write_unit_evidence(
        temp_project,
        [
            "dp1,https://w3id.org/h2kg/hydrogen-ontology#AreaSpecificResistance,,http://qudt.org/vocab/quantitykind/AreaSpecificResistance,u2,measurement,GT_A.xlsx",
            "dp2,https://w3id.org/h2kg/hydrogen-ontology#AreaSpecificResistance,,http://qudt.org/vocab/quantitykind/AreaSpecificResistance,u2,measurement,GT_B.xlsx",
        ],
        [
            "u2,,Ohm.cm2,ohm cm2,ohm cm2,temp_from_raw_string,False,test,1.0,2026-03-16T00:00:00Z",
        ],
    )

    release_profile = dict(configs["release_profile"])
    release_profile["unit_enrichment"] = {"enabled": True, "min_observations": 1, "min_consensus_ratio": 0.8, "create_local_units": True}
    report = enrich_units_from_cleaned_dataset(
        schema_graph,
        controlled_graph,
        release_profile,
        configs["namespace_policy"],
        temp_project,
        evidence_dir=evidence_dir,
    )

    term = URIRef("https://w3id.org/h2kg/hydrogen-ontology#AreaSpecificResistance")
    qv_nodes = list(controlled_graph.objects(term, URIRef("https://w3id.org/h2kg/hydrogen-ontology#hasQuantityValue")))
    assert qv_nodes
    unit_nodes = list(controlled_graph.objects(qv_nodes[0], QUDT.unit))
    assert unit_nodes
    assert str(unit_nodes[0]).startswith("https://w3id.org/h2kg/hydrogen-ontology#_Unit_")
    assert list(controlled_graph.objects(unit_nodes[0], URIRef("http://qudt.org/schema/qudt/ucumCode")))
    assert report["local_units_created"] == 1


def test_pipeline_units_stage_writes_reports(configs, temp_project):
    custom_ttl = temp_project / "input" / "sample_units.ttl"
    custom_ttl.write_text(UNIT_FIXTURE_TTL, encoding="utf-8")
    evidence_dir = _write_unit_evidence(
        temp_project,
        [
            "dp1,https://w3id.org/h2kg/hydrogen-ontology#CellResistance,,http://qudt.org/vocab/quantitykind/ElectricResistance,u1,measurement,GT_A.xlsx",
        ],
        [
            "u1,http://qudt.org/vocab/unit/OHM,Ohm,ohm,ohm,temp_from_raw_string,False,test,1.0,2026-03-16T00:00:00Z",
        ],
    )

    result = run_pipeline(custom_ttl, root=temp_project, stage="units", unit_evidence_dir=evidence_dir)

    assert result["unit_enrichment_report"]["applied"] is True
    assert (temp_project / "output" / "reports" / "unit_enrichment_report.json").exists()
    assert (temp_project / "output" / "review" / "unit_evidence_review.csv").exists()
    review_rows = read_csv(temp_project / "output" / "review" / "unit_evidence_review.csv")
    assert any(row["decision"] == "assert_qudt_unit" for row in review_rows)
