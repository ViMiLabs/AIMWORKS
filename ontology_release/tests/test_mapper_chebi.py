from __future__ import annotations

from pathlib import Path

from rdflib import Graph, Literal, Namespace, RDF, URIRef

from aimworks_ontology_release.mapper import propose_mappings


H2KG = Namespace("https://w3id.org/h2kg/hydrogen-ontology#")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")


def test_propose_mappings_emits_manual_chebi_alignment_for_water(tmp_path):
    input_path = tmp_path / "current.jsonld"
    output_dir = tmp_path / "output" / "review"
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "source_ontologies.yaml").write_text(
        "\n".join(
            [
                "sources:",
                "  - id: chebi",
                "    title: ChEBI",
                "    enabled: true",
                "    required: false",
                "    kind: api_or_export",
                "  - id: emmo-core",
                "    title: EMMO Core",
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
    graph.add((H2KG.Water, RDF.type, H2KG.Matter))
    graph.add((H2KG.Water, SKOS.prefLabel, Literal("Water")))
    graph.serialize(input_path, format="json-ld")

    rows = propose_mappings(input_path, output_dir, config_dir)

    water_rows = [row for row in rows if row["local_iri"] == str(H2KG.Water)]
    assert water_rows
    chebi_row = next(row for row in water_rows if row["target_iri"] == "http://purl.obolibrary.org/obo/CHEBI_15377")
    assert chebi_row["relation"] == "skos:exactMatch"
    assert chebi_row["source"] == "chebi"
    assert chebi_row["status"] == "manual_override"


def test_propose_mappings_filters_noisy_non_exact_chebi_candidates(tmp_path):
    input_path = tmp_path / "current.jsonld"
    output_dir = tmp_path / "output" / "review"
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "source_ontologies.yaml").write_text(
        "\n".join(
            [
                "sources:",
                "  - id: chebi",
                "    title: ChEBI",
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
    graph.add((H2KG.Methanol, RDF.type, H2KG.Matter))
    graph.add((H2KG.Methanol, SKOS.prefLabel, Literal("Methanol")))
    graph.serialize(input_path, format="json-ld")

    rows = propose_mappings(input_path, output_dir, config_dir)

    assert [row for row in rows if row["source"] == "chebi"] == []


def test_propose_mappings_emits_manual_chebi_alignment_for_potassium_hydroxide(tmp_path):
    input_path = tmp_path / "current.jsonld"
    output_dir = tmp_path / "output" / "review"
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "source_ontologies.yaml").write_text(
        "\n".join(
            [
                "sources:",
                "  - id: chebi",
                "    title: ChEBI",
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
    graph.add((H2KG.PotassiumHydroxide, RDF.type, H2KG.Matter))
    graph.add((H2KG.PotassiumHydroxide, SKOS.prefLabel, Literal("Potassium Hydroxide")))
    graph.serialize(input_path, format="json-ld")

    rows = propose_mappings(input_path, output_dir, config_dir)

    koh_row = next(row for row in rows if row["local_iri"] == str(H2KG.PotassiumHydroxide))
    assert koh_row["relation"] == "skos:exactMatch"
    assert koh_row["target_iri"] == "http://purl.obolibrary.org/obo/CHEBI_32035"
    assert koh_row["status"] == "manual_override"
