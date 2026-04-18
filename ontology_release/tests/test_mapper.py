from __future__ import annotations

from pathlib import Path

from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef

from aimworks_ontology_release.mapper import propose_mappings


H2KG = Namespace("https://w3id.org/h2kg/hydrogen-ontology#")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
OWL = Namespace("http://www.w3.org/2002/07/owl#")


def test_mapper_creates_review_and_exploratory_files(mini_ontology_file, output_dir):
    (output_dir / "review").mkdir()
    (output_dir / "reports").mkdir()
    (output_dir / "mappings").mkdir()

    rows = propose_mappings(mini_ontology_file, output_dir / "review")

    assert any(row["local_label"] == "Measurement" for row in rows)
    assert (output_dir / "review" / "mapping_review.csv").exists()
    assert (output_dir / "review" / "mapping_exploratory.csv").exists()
    assert (output_dir / "reports" / "alignment_summary.json").exists()
    assert (output_dir / "reports" / "hdo_alignment_report.json").exists()


def test_mapper_rejects_hdo_object_property_and_obsolete_targets_for_domain_terms(tmp_path):
    input_path = tmp_path / "current.jsonld"
    output_dir = tmp_path / "output" / "review"
    config_dir = tmp_path / "config"
    cache_dir = tmp_path / "cache" / "sources"
    config_dir.mkdir(parents=True)
    cache_dir.mkdir(parents=True)
    (config_dir / "source_ontologies.yaml").write_text(
        "\n".join(
            [
                "sources:",
                "  - id: hdo",
                "    title: HDO",
                "    enabled: true",
                "    required: true",
                "    kind: ontology",
                "    local_cache: cache/sources/hdo.owl",
            ]
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    hdo_graph = Graph()
    acts_upon = URIRef("https://purls.helmholtz-metadaten.de/hob/HDO_00006040")
    obsolete_data = URIRef("https://purls.helmholtz-metadaten.de/hob/HDO_00007008")
    structured_data = URIRef("https://purls.helmholtz-metadaten.de/hob/HDO_00000005")
    hdo_graph.add((acts_upon, RDF.type, OWL.ObjectProperty))
    hdo_graph.add((acts_upon, RDFS.label, Literal("acts upon")))
    hdo_graph.add((obsolete_data, RDF.type, OWL.Class))
    hdo_graph.add((obsolete_data, RDFS.label, Literal("obsolete data")))
    hdo_graph.add((structured_data, RDF.type, OWL.Class))
    hdo_graph.add((structured_data, RDFS.label, Literal("structured data")))
    hdo_graph.serialize(cache_dir / "hdo.owl", format="pretty-xml")

    graph = Graph()
    graph.add((H2KG.Acetone, RDF.type, H2KG.Matter))
    graph.add((H2KG.Acetone, SKOS.prefLabel, Literal("Acetone")))
    graph.add((H2KG.AcidUptakeDataset, RDF.type, H2KG.Data))
    graph.add((H2KG.AcidUptakeDataset, SKOS.prefLabel, Literal("Acid Uptake Dataset")))
    graph.add((H2KG.AcidUptakeDataset, URIRef("http://purl.org/dc/terms/description"), Literal("A dataset containing acid uptake data.")))
    graph.serialize(input_path, format="json-ld")

    rows = propose_mappings(input_path, output_dir, config_dir)
    exploratory = (output_dir / "mapping_exploratory.csv").read_text(encoding="utf-8")

    assert not any(row["local_label"] == "Acetone" and row["target_kind"] == "object_property" for row in rows)
    assert not any("obsolete" in row["target_label"].lower() for row in rows)
    assert "rejected_kind_mismatch" in exploratory


def test_mapper_rejects_deprecated_targets(tmp_path):
    input_path = tmp_path / "current.jsonld"
    output_dir = tmp_path / "output" / "review"
    config_dir = tmp_path / "config"
    cache_dir = tmp_path / "cache" / "sources"
    config_dir.mkdir(parents=True)
    cache_dir.mkdir(parents=True)
    (config_dir / "source_ontologies.yaml").write_text(
        "\n".join(
            [
                "sources:",
                "  - id: hdo",
                "    title: HDO",
                "    enabled: true",
                "    required: true",
                "    kind: ontology",
                "    local_cache: cache/sources/hdo.owl",
            ]
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    hdo_graph = Graph()
    obsolete_data = URIRef("https://purls.helmholtz-metadaten.de/hob/HDO_00007008")
    hdo_graph.add((obsolete_data, RDF.type, OWL.Class))
    hdo_graph.add((obsolete_data, RDFS.label, Literal("obsolete data")))
    hdo_graph.serialize(cache_dir / "hdo.owl", format="pretty-xml")

    graph = Graph()
    graph.add((H2KG.ObsoleteData, RDF.type, H2KG.Data))
    graph.add((H2KG.ObsoleteData, SKOS.prefLabel, Literal("obsolete data")))
    graph.serialize(input_path, format="json-ld")

    rows = propose_mappings(input_path, output_dir, config_dir)
    exploratory = (output_dir / "mapping_exploratory.csv").read_text(encoding="utf-8")

    assert rows == []
    assert "rejected_deprecated_target" in exploratory


def test_mapper_rejects_qudt_scaffold_for_property_concepts(tmp_path):
    input_path = tmp_path / "current.jsonld"
    output_dir = tmp_path / "output" / "review"
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "source_ontologies.yaml").write_text(
        "\n".join(
            [
                "sources:",
                "  - id: qudt-schema",
                "    title: QUDT Schema",
                "    enabled: true",
                "    required: true",
                "    kind: ontology",
            ]
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    graph = Graph()
    graph.add((H2KG.AcidValue, RDF.type, H2KG.Property))
    graph.add((H2KG.AcidValue, SKOS.prefLabel, Literal("Acid Value")))
    graph.serialize(input_path, format="json-ld")

    rows = propose_mappings(input_path, output_dir, config_dir)
    exploratory = (output_dir / "mapping_exploratory.csv").read_text(encoding="utf-8")

    assert not any(row["source"] == "qudt-schema" for row in rows)
    assert "rejected_qudt_scaffold" in exploratory


def test_mapper_blocks_generic_electrochemical_measurement_for_non_electrochemical_measurements(tmp_path):
    input_path = tmp_path / "current.jsonld"
    output_dir = tmp_path / "output" / "review"
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "source_ontologies.yaml").write_text(
        "\n".join(
            [
                "sources:",
                "  - id: emmo-electrochemistry",
                "    title: EMMO Electrochemistry",
                "    enabled: true",
                "    required: true",
                "    kind: ontology",
            ]
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    graph = Graph()
    graph.add((H2KG.ContactAngleMeasurement, RDF.type, H2KG.Measurement))
    graph.add((H2KG.ContactAngleMeasurement, SKOS.prefLabel, Literal("Contact Angle Measurement")))
    graph.serialize(input_path, format="json-ld")

    rows = propose_mappings(input_path, output_dir, config_dir)
    exploratory = (output_dir / "mapping_exploratory.csv").read_text(encoding="utf-8")

    assert not any(row["target_iri"] == "https://w3id.org/emmo/domain/electrochemistry#electrochemistry_7729c34e_1ae9_403d_b933_1765885e7f29" for row in rows)
    assert "rejected_generic_electrochemical_measurement" in exploratory


def test_mapper_does_not_align_chemical_entities_to_agent_roles(tmp_path):
    input_path = tmp_path / "current.jsonld"
    output_dir = tmp_path / "output" / "review"
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "source_ontologies.yaml").write_text(
        "\n".join(
            [
                "sources:",
                "  - id: prov-o",
                "    title: PROV-O",
                "    enabled: true",
                "    required: true",
                "    kind: ontology",
                "  - id: hdo",
                "    title: HDO",
                "    enabled: true",
                "    required: false",
                "    kind: api_or_export",
            ]
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    graph = Graph()
    graph.add((H2KG.Argon, RDF.type, H2KG.Matter))
    graph.add((H2KG.Argon, SKOS.prefLabel, Literal("Argon")))
    graph.serialize(input_path, format="json-ld")

    rows = propose_mappings(input_path, output_dir, config_dir)
    exploratory = (output_dir / "mapping_exploratory.csv").read_text(encoding="utf-8")

    assert not any(row["target_label"] == "Agent" for row in rows)
    assert "rejected_metadata_scope" in exploratory


def test_mapper_preserves_manual_quantity_value_bridge(tmp_path):
    input_path = tmp_path / "current.jsonld"
    output_dir = tmp_path / "output" / "review"
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "source_ontologies.yaml").write_text(
        "\n".join(
            [
                "sources:",
                "  - id: qudt-schema",
                "    title: QUDT Schema",
                "    enabled: true",
                "    required: true",
                "    kind: ontology",
            ]
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    graph = Graph()
    graph.add((H2KG.hasQuantityValue, RDF.type, OWL.ObjectProperty))
    graph.add((H2KG.hasQuantityValue, RDFS.label, Literal("hasQuantityValue")))
    graph.serialize(input_path, format="json-ld")

    rows = propose_mappings(input_path, output_dir, config_dir)

    row = next(row for row in rows if row["local_iri"] == str(H2KG.hasQuantityValue))
    assert row["relation"] == "rdfs:subPropertyOf"
    assert row["target_iri"] == "http://qudt.org/schema/qudt/quantityValue"
    assert row["status"] == "manual_override"
