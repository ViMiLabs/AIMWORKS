from __future__ import annotations

import json
import shutil
from pathlib import Path

from rdflib import Graph, RDF, URIRef

from aimworks_ontology_release.decode_multiscale_interface import build_decode_multiscale_model_interface
from aimworks_ontology_release.itc_pilot import (
    H2KG,
    apply_itc_mapping_overrides,
    build_decode_itc_overlay,
    build_itc_pilot_package,
    integrate_itc_terms,
    validate_interface_registry,
)


def test_itc_expert_registry_and_h2kg_profile(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    review_path = root / "input" / "itc_curated_interface.json"
    review = json.loads(review_path.read_text(encoding="utf-8"))
    validation = validate_interface_registry(review)
    assert validation["input_count"] == 24
    assert validation["output_count"] == 20
    assert validation["unique_identifier_count"] == 44
    assert validation["new_term_count"] == 40
    assert validation["reused_term_count"] == 4
    assert validation["source_metadata_complete"] is True
    assert validation["misleading_identifiers_without_evidence"] == []
    assert validation["normalized_fields_without_basis_iri"] == []

    ontology = tmp_path / "current_ontology.jsonld"
    shutil.copy2(root / "input" / "current_ontology.jsonld", ontology)
    integration = integrate_itc_terms(ontology, review_path, write_in_place=True)
    assert integration["managed_resource_count"] == 116

    package = build_itc_pilot_package(ontology, tmp_path / "output", review_path)
    assert package["status"] == "passed"
    assert package["validation"]["equivalent_rdf_statements"] is True
    graph = Graph().parse(Path(package["output_dir"]) / "itc_h2kg_profile.ttl", format="turtle")
    model = URIRef(H2KG + "InkToCompositionModel")
    assert (model, URIRef(H2KG + "hasInputData"), None) not in graph
    assert (model, URIRef(H2KG + "hasOutputData"), None) not in graph
    assert (model, URIRef(H2KG + "hasParameter"), None) not in graph
    assert (URIRef(H2KG + "IonomerToCarbonRatio"), RDF.type, URIRef(H2KG + "Property")) in graph
    assert (URIRef(H2KG + "IonomerToCarbonRatio"), RDF.type, URIRef(H2KG + "Parameter")) not in graph
    shapes = Graph().parse(Path(package["output_dir"]) / "itc_h2kg_profile_shapes.ttl", format="turtle")
    assert (
        URIRef(H2KG + "InkToCompositionModelProfileShape"),
        URIRef("http://www.w3.org/ns/shacl#targetClass"),
        model,
    ) in shapes
    assert (URIRef(H2KG + "PlatinumParticleRadius"), URIRef("http://www.w3.org/2004/02/skos/core#notation"), None) in graph
    serialized = (Path(package["output_dir"]) / "itc_h2kg_profile.jsonld").read_text(encoding="utf-8")
    assert "catalyst active particle diameter" not in serialized.lower()
    assert "mean pore radius inside the ionomer" not in serialized.lower()

    pattern = Graph().parse(Path(package["output_dir"]) / "itc_semantic_pattern.ttl", format="turtle")
    pattern_base = "https://w3id.org/h2kg/profiles/itc/example/"
    pore_occurrence = URIRef(pattern_base + "total-pore-volume-occurrence")
    catalyst = URIRef(pattern_base + "pt-on-carbon-bearer-template")
    carbon_basis = URIRef(pattern_base + "carbon-mass-normalization-basis")
    assert (pore_occurrence, URIRef(H2KG + "isCharacteristicOf"), catalyst) in pattern
    assert (pore_occurrence, URIRef(H2KG + "normalizedTo"), carbon_basis) in pattern
    assert (carbon_basis, RDF.type, URIRef(H2KG + "CarbonMass")) in pattern
    tension = URIRef(pattern_base + "surface-tension-occurrence")
    water = URIRef(pattern_base + "water-bearer-at-353-k-template")
    assert (tension, URIRef(H2KG + "isCharacteristicOf"), water) in pattern

    mapping_csv = (Path(package["output_dir"]) / "itc_mapping_matrix.csv").read_text(encoding="utf-8")
    assert "source_registry_version" in mapping_csv
    assert "misleading_identifier_retained_for_traceability" in mapping_csv
    assert "CarbonMass" in mapping_csv


def test_itc_corrections_propagate_without_changing_source_topology(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    review = json.loads((root / "input" / "itc_curated_interface.json").read_text(encoding="utf-8"))
    snapshot = json.loads((root / "input" / "decode_workflows_source.json").read_text(encoding="utf-8"))
    source = next(workflow for workflow in snapshot["workflows"] if workflow["id"] == "iet-ink-to-composition-model")
    source_pairs = [(edge["source"], edge["target"]) for edge in source["edges"]]
    mapped = apply_itc_mapping_overrides(snapshot, review)
    mapped_source = next(workflow for workflow in mapped["workflows"] if workflow["id"] == "iet-ink-to-composition-model")
    assert len(mapped_source["nodes"]) == 41
    assert len(mapped_source["edges"]) == 59
    assert source_pairs == [(edge["source"], edge["target"]) for edge in mapped_source["edges"]]
    radius = next(node for node in mapped_source["nodes"] if node["source_id"] == "n6")
    assert radius["label"] == "Catalyst active particle diameter"
    assert radius["mapping_override"]["anchor_iri"] == H2KG + "PlatinumParticleRadius"
    non_itc = next(
        workflow for workflow in mapped["workflows"]
        if workflow["id"] == "image-tem-data-parameter-extraction-3d"
    )
    non_itc_diameter = next(
        node for node in non_itc["nodes"]
        if node["label"] == "Catalyst active particle diameter"
    )
    assert "mapping_override" not in non_itc_diameter
    assert non_itc_diameter["prevent_anchor_canonicalization"] is True
    overlay = build_decode_itc_overlay(review)
    assert overlay["badge"] == "Curated ITC profile"
    parameter_records = [node for node in overlay["nodes"] if node["semantic_role"] == "Parameter"]
    parameter_edges = [edge for edge in overlay["edges"] if edge["predicate"] == H2KG + "hasParameter"]
    property_edges = [edge for edge in overlay["edges"] if edge["predicate"] == H2KG + "ofProperty"]
    assert len(parameter_records) == 16
    assert len(parameter_edges) == 16
    assert len(property_edges) >= 16

    interface = build_decode_multiscale_model_interface(
        root / "input" / "decode_multiscale_model_interface.json",
        root / "input" / "decode_workflows_source.json",
        tmp_path / "output",
        root / "input" / "itc_curated_interface.json",
    )
    curated = interface["validation"]["curated_itc_profile"]
    assert curated["stage_occurrence_count"] == 68
    assert curated["shared_identifier_count"] == 12
    nodes = {node["source_id"]: node for node in interface["nodes"]}
    assert nodes["IO_MAT_CatalystActiveParticleDiameter"]["label"] == "Platinum particle radius"
    assert nodes["IO_CMP_CCLFractionHydrophilicPores"]["label"] == "CCL accessible primary-pore volume fraction"
    assert nodes["IO_MAT_CatalystPoreSizeDistribution_sigmaR2"]["label"] == "CCL secondary-pore logarithmic radius deviation"
