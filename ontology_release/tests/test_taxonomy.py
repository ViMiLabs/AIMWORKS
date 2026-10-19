from __future__ import annotations

import json
from pathlib import Path

import yaml
from rdflib import Graph, RDF, RDFS, URIRef
from rdflib.namespace import DCTERMS, OWL, PROV, SKOS

from aimworks_ontology_release.taxonomy import _build_external_bridge, build_taxonomy_release
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
    assert result["active_local_classes"] == 2221
    assert result["deprecated_compatibility_classes"] == 165
    assert result["new_structural_classes"] == 157
    assert result["publication_ready"] is True

    graph = Graph().parse(result["taxonomy_ttl"], format="turtle")
    ontology_iri = URIRef("https://w3id.org/h2kg/hydrogen-ontology")
    assert str(graph.value(ontology_iri, DCTERMS.title)) == (
        "H₂KG Domain Ontology for Hydrogen Electrochemical Systems"
    )
    assert (_iri("Matter"), RDF.type, OWL.Class) in graph
    assert (_iri("Parameter"), RDFS.subClassOf, _iri("ParameterRecord")) in graph
    assert (_iri("Instrument"), RDFS.subClassOf, _iri("Device")) in graph
    assert (_iri("MEAAssembly"), RDFS.subClassOf, _iri("MembraneElectrodeAssembly")) in graph
    assert (_iri("FuelCellTestStation"), RDFS.subClassOf, _iri("ElectrochemicalTestInstrument")) in graph
    assert (_iri("FijiImageJSoftware"), RDFS.subClassOf, _iri("ImageAnalysisSoftware")) in graph
    assert (_iri("CatalystLayerThickness"), RDFS.subClassOf, _iri("LayerThickness")) in graph
    assert str(graph.value(_iri("CatalystLayerThickness"), SKOS.definition)).startswith(
        "A thickness characteristic representing"
    )
    assert str(graph.value(_iri("AFMScanSpeed"), SKOS.definition)).startswith(
        "A scan-rate characteristic"
    )
    assert str(graph.value(_iri("IonomerCatalystDispersionParameter"), SKOS.definition)).startswith(
        "A dimensionless dispersion characteristic"
    )
    assert (_iri("DynamicHydrogenElectrode"), RDFS.subClassOf, _iri("ReferenceElectrode")) in graph
    assert (_iri("SCE"), RDFS.subClassOf, _iri("ReferenceElectrode")) in graph
    assert (_iri("SHE"), RDFS.subClassOf, _iri("ReferenceElectrode")) in graph
    assert (_iri("GlassyCarbonDiskElectrode"), RDFS.subClassOf, _iri("ElectrodeComponent")) in graph
    assert (_iri("AbsorptionPeakWavelength"), RDFS.subClassOf, _iri("SpectroscopicCharacteristic")) in graph
    assert (_iri("BindingEnergy"), RDFS.subClassOf, _iri("SpectroscopicCharacteristic")) in graph
    atomic_layer_deposition = _iri("AtomicLayerDeposition")
    assert (atomic_layer_deposition, RDFS.subClassOf, _iri("CoatingOrDepositionProcess")) in graph
    assert str(graph.value(atomic_layer_deposition, SKOS.definition)).startswith(
        "A coating or deposition process that forms a material layer"
    )
    assert str(graph.value(atomic_layer_deposition, DCTERMS.description)).startswith(
        "A coating or deposition process that forms a material layer"
    )
    assert "Pt/NbB2 catalyst workflow" in str(graph.value(atomic_layer_deposition, SKOS.scopeNote))

    acid_base_titration = _iri("AcidBaseTitrationMeasurement")
    assert (acid_base_titration, RDFS.subClassOf, _iri("CompositionMeasurement")) in graph
    assert str(graph.value(acid_base_titration, SKOS.prefLabel)) == "Acid-base titration"
    assert str(graph.value(acid_base_titration, DCTERMS.description)).startswith(
        "A composition measurement in which an acidic or basic titrant"
    )
    assert "phosphoric-acid doping level" in str(graph.value(acid_base_titration, SKOS.scopeNote))

    assert (_iri("hasOutputData"), OWL.inverseOf, PROV.wasGeneratedBy) not in graph
    assert (_iri("hasOutputData"), RDFS.subPropertyOf, PROV.generated) in graph
    assert (_iri("fromMeasurement"), RDFS.subPropertyOf, PROV.wasDerivedFrom) not in graph
    assert (_iri("usesSoftware"), RDF.type, OWL.ObjectProperty) in graph
    assert (_iri("ofProperty"), RDFS.domain, _iri("InformationEntity")) in graph
    assert (_iri("ofProperty"), RDFS.range, _iri("Property")) in graph
    assert (_iri("hasQuantityValue"), RDFS.domain, _iri("Property")) in graph
    assert "Parameter or DataPoint" in str(graph.value(_iri("ofProperty"), DCTERMS.description))
    assert "Parameter record" in str(graph.value(_iri("hasParameter"), DCTERMS.description))
    assert "property occurrence" in str(graph.value(_iri("hasQuantityValue"), DCTERMS.description))
    assert not any(graph.triples((_iri("hasProperty"), None, None)))
    assert not any(graph.triples((None, _iri("hasProperty"), None)))
    assert (_iri("isCharacteristicOf"), RDF.type, OWL.ObjectProperty) in graph
    assert (_iri("isCharacteristicOf"), RDFS.domain, _iri("Characteristic")) in graph
    assert (_iri("isCharacteristicOf"), RDFS.range, RDFS.Resource) in graph

    validation = json.loads(Path(result["validation"]).read_text(encoding="utf-8"))
    assert validation["competency_checks"]["all_passed"] is True
    assert validation["counts"]["competency_checks_passed"] == 9
    assert validation["asserted_foundational_imports"] == [
        "http://qudt.org/2.1/schema/qudt",
        "https://www.w3.org/ns/prov-o",
    ]
    assert validation["governance"] == {
        "approval_status": "approved",
        "external_reasoner_status": "passed",
        "technical_validation": "passed",
    }
    assert validation["publication_status"] == "approved"
    assert not validation["warnings"]
    assert validation["file_uris"] == []
    assert validation["compatibility_file_uris"] == []

    compatibility = Graph().parse(result["compatibility_ttl"], format="turtle")
    assert (_iri("hasProperty"), OWL.deprecated, None) in compatibility
    assert "compatibility predicate" in str(compatibility.value(_iri("hasProperty"), SKOS.scopeNote)).lower()
    assert not any(
        isinstance(term, URIRef) and str(term).startswith("file:")
        for triple in compatibility
        for term in triple
    )
    migration_registry = Path(
        result["semantic_profiles"]["relation_migration_registry"]
    ).read_text(encoding="utf-8")
    usage_registry = Path(
        result["semantic_profiles"]["workflow_usage_registry"]
    ).read_text(encoding="utf-8")
    assert "file:///" not in migration_registry
    assert "file:///" not in usage_registry
    assert "https://w3id.org/h2kg/hydrogen-ontology/legacy-source/" in migration_registry

    characteristic_definitions = [
        str(graph.value(_iri(term["local_name"]), SKOS.definition) or "")
        for term in json.loads(Path(result["registry"]).read_text(encoding="utf-8"))["terms"]
        if term["top_branch"] == "Characteristic"
    ]
    assert not any(definition.startswith("A parameter ") for definition in characteristic_definitions)
    assert not any(definition.startswith("Parameter describing") for definition in characteristic_definitions)

    assert (_iri("Solution"), RDFS.subClassOf, _iri("Mixture")) in graph
    assert (_iri("MetalOxideMaterial"), RDFS.subClassOf, _iri("OxideMaterial")) in graph
    assert (_iri("SilicaBasedMaterial"), RDFS.subClassOf, _iri("OxideMaterial")) in graph
    assert (_iri("BallMilling"), RDFS.subClassOf, _iri("MillingProcess")) in graph
    assert (_iri("UVCuringProcess"), RDFS.subClassOf, _iri("PhotochemicalCuringProcess")) in graph
    assert (
        _iri("AnodeStoichiometricRatio"),
        RDFS.subClassOf,
        _iri("ElectrochemicalOperatingCharacteristic"),
    ) in graph
    assert (_iri("EISPerturbationAmplitude"), RDFS.subClassOf, _iri("ACAmplitude")) in graph

    assert (_iri("DepositionRate"), OWL.deprecated, None) in graph
    assert (
        _iri("DepositionRate"),
        DCTERMS.isReplacedBy,
        _iri("VolumetricInkDepositionRate"),
    ) in graph
    assert (_iri("PolydispersityIndex"), OWL.deprecated, None) in graph
    assert not any(graph.objects(_iri("PolydispersityIndex"), DCTERMS.isReplacedBy))
    assert (_iri("XRayPhotoelectronSpectrometer"), DCTERMS.isReplacedBy, _iri("XPSInstrument")) in graph

    registry = json.loads(Path(result["registry"]).read_text(encoding="utf-8"))
    assert registry["version"] == "2.2.0"
    assert registry["correction_decision_counts"] == {
        "parent": 156,
        "definition": 470,
        "total": 626,
    }
    correction_report = json.loads(
        Path(result["correction_report"]["json"]).read_text(encoding="utf-8")
    )
    assert correction_report["decision_counts"]["total"] == 626
    assert correction_report["decision_counts"]["parent"] == 156
    assert correction_report["decision_counts"]["definition"] == 470
    assert correction_report["decision_counts"]["unique_classes"] == 544
    assert correction_report["source_dependent_classes_assessed"] == 153
    assert correction_report["source_ambiguous_classes_deprecated"] == 152
    assert correction_report["source_dependent_classes_resolved"] == 1
    assert len(correction_report["decisions"]) == 626
    assert all(
        term["definition_status"] in {"source", "curated", "structural"}
        for term in registry["terms"]
        if term["disposition"] == "active_local_class"
    )


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


def test_external_bridge_accepts_reviewed_equivalent_property(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    config_dir.mkdir()
    input_dir.mkdir()
    (input_dir / "tib_terminology_snapshot.json").write_text(
        json.dumps(
            {
                "retrieved_at": "2026-09-03T15:52:03+00:00",
                "ontologies": [
                    {
                        "ontology_id": "prov",
                        "title": "The PROV Ontology",
                        "version": "Recommendation version 2013-04-30",
                        "loaded": "2026-08-31T15:53:55.597322875",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (config_dir / "mapping_rules.yaml").write_text(
        "\n".join(
            [
                "manual_overrides:",
                "  generatedBy:",
                "    relation: owl:equivalentProperty",
                "    target: http://www.w3.org/ns/prov#wasGeneratedBy",
                "    local_kind: object_property",
                "    target_label: was generated by",
                "    target_kind: object_property",
                "    source: prov-o",
                "    rationale: Strictly equivalent reviewed generation relation.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    review_dir = output_dir / "review"
    review_dir.mkdir(parents=True)
    (review_dir / "mapping_review.csv").write_text(
        "\n".join(
            [
                "local_iri,local_label,local_kind,relation,target_iri,target_label,target_kind,source,score,status,rationale",
                "https://w3id.org/h2kg/hydrogen-ontology#AutomaticRelation,Automatic relation,object_property,owl:equivalentProperty,http://www.w3.org/ns/prov#used,used,object_property,prov-o,1.0,accepted,Automatic lexical candidate awaiting review.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = _build_external_bridge(
        output_dir,
        config_dir,
        {"version": "2.0.0", "version_iri": "https://w3id.org/h2kg/hydrogen-ontology/releases/2.0.0"},
        {
            "format": "h2kg-tib-auto-harmonization/v2",
            "snapshot_sha256": "TEST-SNAPSHOT-SHA256",
            "mappings": [
                {
                    "local_iri": str(_iri("ExactLocal")),
                    "local_label": "Exact local",
                    "relation": "skos:exactMatch",
                    "target_iri": "https://example.org/ontology/ExactExternal",
                    "target_label": "Exact external",
                    "tib_ontology_id": "prov",
                    "tib_ontology_version": "Recommendation version 2013-04-30",
                    "status": "machine_safe",
                    "confidence": "high",
                    "outcome": "machine_exact_equivalent",
                    "rule_id": "TEST-EXACT",
                    "decision_basis": "Strict test equivalence evidence.",
                },
                {
                    "local_iri": str(_iri("NarrowerLocal")),
                    "local_label": "Narrower local",
                    "relation": "skos:broadMatch",
                    "target_iri": "https://example.org/ontology/BroaderExternal",
                    "target_label": "Broader external",
                    "tib_ontology_id": "prov",
                    "tib_ontology_version": "Recommendation version 2013-04-30",
                    "status": "machine_safe",
                    "confidence": "high",
                    "outcome": "h2kg_narrower",
                    "rule_id": "TEST-BROAD",
                    "decision_basis": "Strict test broader-target evidence.",
                },
                {
                    "local_iri": str(_iri("BroaderLocal")),
                    "local_label": "Broader local",
                    "relation": "skos:narrowMatch",
                    "target_iri": "https://example.org/ontology/NarrowerExternal",
                    "target_label": "Narrower external",
                    "tib_ontology_id": "prov",
                    "tib_ontology_version": "Recommendation version 2013-04-30",
                    "status": "machine_safe",
                    "confidence": "high",
                    "outcome": "h2kg_broader",
                    "rule_id": "TEST-NARROW",
                    "decision_basis": "Strict test narrower-target evidence.",
                },
                {
                    "local_iri": str(_iri("generatedBy")),
                    "local_label": "generated by",
                    "relation": "skos:exactMatch",
                    "target_iri": str(PROV.wasGeneratedBy),
                    "target_label": "was generated by",
                    "tib_ontology_id": "prov",
                    "tib_ontology_version": "Recommendation version 2013-04-30",
                    "status": "machine_safe",
                    "confidence": "high",
                    "outcome": "machine_exact_equivalent",
                    "rule_id": "TEST-SUPPRESSED",
                    "decision_basis": "Must be suppressed by reviewed pair precedence.",
                },
            ],
        },
    )

    assert result["mapping_count"] == 4
    assert result["tib_benchmark_asserted_mapping_count"] == 3
    assert result["foundational_mapping_count"] == 1
    assert result["evidence_only_mapping_count"] == 1
    assert result["invalid_mapping_count"] == 0
    assert result["serializations_isomorphic"] is True
    assert result["automatic_logical_axiom_count"] == 0
    assert result["external_import_count"] == 0
    graph = Graph().parse(result["turtle"], format="turtle")
    assert (_iri("generatedBy"), OWL.equivalentProperty, PROV.wasGeneratedBy) in graph
    assert (_iri("generatedBy"), SKOS.exactMatch, PROV.wasGeneratedBy) not in graph
    assert (_iri("AutomaticRelation"), OWL.equivalentProperty, PROV.used) not in graph
    assert (_iri("ExactLocal"), SKOS.exactMatch, URIRef("https://example.org/ontology/ExactExternal")) in graph
    assert (_iri("NarrowerLocal"), SKOS.broadMatch, URIRef("https://example.org/ontology/BroaderExternal")) in graph
    assert (_iri("BroaderLocal"), SKOS.narrowMatch, URIRef("https://example.org/ontology/NarrowerExternal")) in graph
    jsonld_graph = Graph().parse(result["jsonld"], format="json-ld")
    assert set(graph) == set(jsonld_graph)
    assert Path(result["immutable_turtle"]).exists()
    assert Path(result["immutable_jsonld"]).exists()
    assert Path(result["sssom"]).exists()
    assert Path(result["changelog"]).exists()
    registry = json.loads((output_dir / "ontology" / "external_alignment_registry.json").read_text(encoding="utf-8"))
    assert registry["evidence_only_mappings"][0]["decision_status"] == "evidence-only"
    categories = {row["alignment_category"] for row in registry["mappings"]}
    assert categories == {"foundational_alignment", "tib_benchmark_alignment"}
