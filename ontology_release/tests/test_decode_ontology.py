from __future__ import annotations

import json
import re
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SKOS

from aimworks_ontology_release.decode_workflows import build_decode_workflow_release


DECODE = "https://w3id.org/h2kg/decode/ontology#"
H2KG_ONTOLOGY = URIRef("https://w3id.org/h2kg/hydrogen-ontology")
ONTOLOGY_IRI = URIRef("https://w3id.org/h2kg/decode/ontology")


def test_decode_ontology_preserves_release_and_serializes_equivalently(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    result = build_decode_workflow_release(
        root / "input" / "decode_workflows_source.json",
        tmp_path / "output",
        root / "config" / "decode_workflow_mappings.yaml",
        root / "input" / "current_ontology.jsonld",
        include_multiscale_interface=True,
        manual_overlay_path=root / "input" / "decode_manual_workflow_overlay.json",
    )
    decode_dir = tmp_path / "output" / "decode"
    ttl_path = decode_dir / "decode-h2kg-aligned-ontology.ttl"
    jsonld_path = decode_dir / "decode-h2kg-aligned-ontology.jsonld"
    assert ttl_path.exists()
    assert jsonld_path.exists()

    turtle = Graph().parse(ttl_path, format="turtle")
    jsonld = Graph().parse(jsonld_path, format="json-ld")
    assert set(turtle) == set(jsonld)
    assert (ONTOLOGY_IRI, RDF.type, OWL.Ontology) in turtle
    assert (ONTOLOGY_IRI, OWL.imports, H2KG_ONTOLOGY) in turtle
    assert not any(turtle.objects(ONTOLOGY_IRI, DCTERMS.license))
    assert any(turtle.objects(ONTOLOGY_IRI, DCTERMS.rights))

    workflow_type = URIRef(DECODE + "WorkflowDefinition")
    occurrence_type = URIRef(DECODE + "SourceOccurrence")
    source_edge_type = URIRef(DECODE + "SourceEdge")
    dependency_type = URIRef(DECODE + "WorkflowDependency")
    assert len(set(turtle.subjects(RDF.type, workflow_type))) == 137
    assert len(set(turtle.subjects(RDF.type, occurrence_type))) == 3307
    assert len(set(turtle.subjects(RDF.type, source_edge_type))) == 4463
    assert len(set(turtle.subjects(RDF.type, dependency_type))) == 623

    validation = json.loads(
        (decode_dir / "decode_ontology_validation_report.json").read_text(encoding="utf-8")
    )
    assert validation["status"] == "passed"
    assert validation["equivalent_serializations"] is True
    assert validation["published_workflow_dependency_count"] == 572
    assert validation["audit_only_workflow_dependency_count"] == 51
    assert validation["definition_candidate_source_record_count"] == 522
    assert validation["definition_candidate_unique_label_count"] == 522
    assert validation["missing_definition_iris"] == []
    assert validation["placeholder_definition_iris"] == []
    assert result["decode_ontology"]["status"] == "generated"


def test_decode_ontology_definitions_roles_and_aliases_are_reviewable(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    build_decode_workflow_release(
        root / "input" / "decode_workflows_source.json",
        tmp_path / "output",
        root / "config" / "decode_workflow_mappings.yaml",
        root / "input" / "current_ontology.jsonld",
        include_multiscale_interface=True,
        manual_overlay_path=root / "input" / "decode_manual_workflow_overlay.json",
    )
    decode_dir = tmp_path / "output" / "decode"
    graph_data = json.loads((decode_dir / "decode_federated_graph.json").read_text(encoding="utf-8"))
    registry = json.loads(
        (decode_dir / "decode_ontology_definition_registry.json").read_text(encoding="utf-8")
    )
    candidates = json.loads(
        (root / "config" / "decode_definition_candidates.json").read_text(encoding="utf-8-sig")
    )
    ontology = Graph().parse(decode_dir / "decode-h2kg-aligned-ontology.ttl", format="turtle")

    assert graph_data["deprecated_anchor_aliases"]
    assert candidates["source_record_count"] == 522
    assert candidates["source_sha256"] == registry["definition_seed_sha256"]
    assert registry["counts"]["classes_with_supplied_candidate"] > 0
    assert registry["counts"]["candidate_role_conflict_count"] > 0
    labels = {row["preferred_label"]: row for row in registry["definitions"]}
    for required in (
        "Adsorbate conformation on electrode (nanostructured)",
        "Cell H2 outlet pressure",
        "Degradation rate of cell voltage",
        "PTL bulk resistance",
        "StarDist-TEM nanoparticle segmentation",
    ):
        assert required in labels
        assert len(labels[required]["definition"].split()) >= 10
    assert all(row["definition_status"] == "expert-draft" for row in registry["definitions"])
    assert all("concept denoted" not in row["definition"].casefold() for row in registry["definitions"])

    roles = {
        (node["label"], node["semantic_role"])
        for node in graph_data["nodes"]
    }
    assert ("Catalyst active particle diameter", "Property") in roles
    assert ("CCL structural parameters", "Data") in roles
    assert ("Single cell test bench: polarization, EIS", "Measurement") in roles
    assert ("Ultrasonic spray deposition for catalytic layers", "Manufacturing") in roles

    deprecated = list(ontology.subjects(OWL.deprecated, None))
    assert deprecated
    assert all(any(ontology.objects(iri, DCTERMS.isReplacedBy)) for iri in deprecated)
    active_decode_classes = {
        URIRef(anchor["id"])
        for anchor in graph_data["anchors"]
        if anchor.get("state") == "reviewed_decode"
    }
    assert all(any(ontology.objects(iri, RDFS.subClassOf)) for iri in active_decode_classes)
    assert all(any(ontology.objects(iri, SKOS.definition)) for iri in active_decode_classes)

    serialized = (decode_dir / "decode-h2kg-aligned-ontology.ttl").read_text(encoding="utf-8")
    assert not re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", serialized, flags=re.I)
