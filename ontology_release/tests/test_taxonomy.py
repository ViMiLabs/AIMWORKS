from __future__ import annotations

import json
from pathlib import Path

import yaml
from rdflib import Graph, RDF, RDFS, URIRef
from rdflib.namespace import DCTERMS, OWL, PROV

from aimworks_ontology_release.taxonomy import build_taxonomy_release
from aimworks_ontology_release.utils import default_mapping_rules, try_load_yaml


ROOT = Path(__file__).resolve().parents[1]
H2KG = "https://w3id.org/h2kg/hydrogen-ontology#"


def _iri(local_name: str) -> URIRef:
    return URIRef(H2KG + local_name)


def test_full_taxonomy_is_complete_and_preserves_stable_anchors(tmp_path: Path) -> None:
    result = build_taxonomy_release(
        ROOT / "input" / "current_ontology.jsonld",
        tmp_path / "output",
        ROOT / "config",
    )

    assert result["conforms"] is True
    assert result["active_local_classes"] == 2360
    assert result["deprecated_compatibility_classes"] == 6
    assert result["new_structural_classes"] == 131
    assert result["publication_ready"] is False

    graph = Graph().parse(result["taxonomy_ttl"], format="turtle")
    assert (_iri("Matter"), RDF.type, OWL.Class) in graph
    assert (_iri("Parameter"), RDFS.subClassOf, _iri("ParameterRecord")) in graph
    assert (_iri("Instrument"), RDFS.subClassOf, _iri("Device")) in graph
    assert (_iri("MEAAssembly"), RDFS.subClassOf, _iri("MembraneElectrodeAssembly")) in graph
    assert (_iri("FuelCellTestStation"), RDFS.subClassOf, _iri("ElectrochemicalTestInstrument")) in graph
    assert (_iri("FijiImageJSoftware"), RDFS.subClassOf, _iri("ImageAnalysisSoftware")) in graph
    assert (_iri("CatalystLayerThickness"), RDFS.subClassOf, _iri("LayerThickness")) in graph
    assert (_iri("DynamicHydrogenElectrode"), RDFS.subClassOf, _iri("ReferenceElectrode")) in graph
    assert (_iri("SCE"), RDFS.subClassOf, _iri("ReferenceElectrode")) in graph
    assert (_iri("SHE"), RDFS.subClassOf, _iri("ReferenceElectrode")) in graph
    assert (_iri("GlassyCarbonDiskElectrode"), RDFS.subClassOf, _iri("ElectrodeComponent")) in graph
    assert (_iri("AbsorptionPeakWavelength"), RDFS.subClassOf, _iri("SpectroscopicCharacteristic")) in graph
    assert (_iri("BindingEnergy"), RDFS.subClassOf, _iri("SpectroscopicCharacteristic")) in graph

    assert (_iri("hasOutputData"), OWL.inverseOf, PROV.wasGeneratedBy) not in graph
    assert (_iri("hasOutputData"), RDFS.subPropertyOf, PROV.generated) in graph
    assert (_iri("fromMeasurement"), RDFS.subPropertyOf, PROV.wasDerivedFrom) not in graph
    assert (_iri("usesSoftware"), RDF.type, OWL.ObjectProperty) in graph
    assert (_iri("hasProperty"), OWL.deprecated, None) in graph
    assert (_iri("hasProperty"), DCTERMS.isReplacedBy, _iri("measures")) in graph

    validation = json.loads(Path(result["validation"]).read_text(encoding="utf-8"))
    assert validation["competency_checks"]["all_passed"] is True
    assert validation["counts"]["competency_checks_passed"] == 9
    assert validation["asserted_foundational_imports"] == [
        "http://qudt.org/2.1/schema/qudt",
        "https://www.w3.org/ns/prov-o",
    ]
    assert validation["governance"] == {
        "domain_reviewer_status": "pending",
        "external_reasoner_status": "pending",
        "technical_validation": "passed",
    }


def test_profile_fields_and_duplicate_iris_are_not_active_classes(tmp_path: Path) -> None:
    result = build_taxonomy_release(
        ROOT / "input" / "current_ontology.jsonld",
        tmp_path / "output",
        ROOT / "config",
    )
    graph = Graph().parse(result["taxonomy_ttl"], format="turtle")

    field = _iri("ITCCarbonDensityInputField")
    assert (field, RDF.type, OWL.Class) not in graph

    duplicate = _iri("CatalystLayerThickness_2")
    canonical = _iri("CatalystLayerThickness")
    assert (duplicate, OWL.deprecated, None) in graph
    assert (duplicate, DCTERMS.isReplacedBy, canonical) in graph

    resource_registry = json.loads(Path(result["resource_registry"]).read_text(encoding="utf-8"))
    by_iri = {row["iri"]: row for row in resource_registry["resources"]}
    assert by_iri[str(field)]["disposition"] == "profile_or_workflow_field"
    assert all(row["disposition"] for row in by_iri.values())

    validation = json.loads(Path(result["validation"]).read_text(encoding="utf-8"))
    assert validation["counts"]["source_local_resources"] == validation["counts"]["source_resources_with_disposition"]
    assert validation["subclass_cycles"] == []
    assert validation["orphan_class_iris"] == []
    assert validation["file_uris"] == []


def test_taxonomy_serializations_are_equivalent(tmp_path: Path) -> None:
    result = build_taxonomy_release(
        ROOT / "input" / "current_ontology.jsonld",
        tmp_path / "output",
        ROOT / "config",
    )
    turtle = Graph().parse(result["taxonomy_ttl"], format="turtle")
    jsonld = Graph().parse(result["taxonomy_jsonld"], format="json-ld")
    assert set(turtle) == set(jsonld)


def test_external_alignment_targets_the_specific_electrochemical_branch() -> None:
    config_path = ROOT / "config" / "mapping_rules.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    overrides = config["manual_overrides"]
    assert "Measurement" not in overrides
    assert overrides["ElectrochemicalMeasurement"]["relation"] == "rdfs:subClassOf"
    assert overrides["ElectrochemicalMeasurement"]["target"].endswith(
        "electrochemistry_7729c34e_1ae9_403d_b933_1765885e7f29"
    )
    runtime_config = try_load_yaml(config_path, default_mapping_rules())
    assert "Measurement" not in runtime_config["manual_overrides"]
    assert "ElectrochemicalMeasurement" in runtime_config["manual_overrides"]
