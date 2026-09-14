from __future__ import annotations

import json
from pathlib import Path

from aimworks_ontology_release.decode_workflows import apply_decode_alias_curation, build_decode_workflow_release, ingest_decode_graphml_directory


def _graphml(nodes: list[tuple[str, str]], edges: list[tuple[str, str]]) -> str:
    node_xml = "\n".join(f'<node id="{node_id}"><data key="d4">{description}</data></node>' for node_id, description in nodes)
    edge_xml = "\n".join(f'<edge id="e{index}" source="{source}" target="{target}"/>' for index, (source, target) in enumerate(edges))
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <key attr.name="description" attr.type="string" for="node" id="d4"/>
  <graph id="G" edgedefault="directed">{node_xml}{edge_xml}</graph>
</graphml>'''


def test_decode_release_preserves_source_topology_and_uses_explicit_anchors(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "prep.graphml").write_text(
        _graphml(
            [("n0", "Catalyst ink\ninternal key: Catalyst ink: material"), ("n1", "CCM\ninternal key: CCM: component")],
            [("n0", "n1")],
        ),
        encoding="utf-8",
    )
    (source_dir / "fib.graphml").write_text(
        _graphml(
            [("n0", "CCM\ninternal key: CCM: component"), ("n1", "FIB method")],
            [("n0", "n1")],
        ),
        encoding="utf-8",
    )
    (source_dir / "unreviewed.graphml").write_text(
        _graphml([("n0", "CCM\ninternal key: CCM: material")], []), encoding="utf-8"
    )
    snapshot = tmp_path / "decode.json"
    ingest = ingest_decode_graphml_directory(source_dir, snapshot)
    assert ingest["workflow_count"] == 3
    assert ingest["node_count"] == 5
    assert ingest["edge_count"] == 2
    config = tmp_path / "mappings.yaml"
    config.write_text(
        '''mappings:
  - source_label: CCM
    native_category: component
    state: approved_h2kg
    anchor_iri: https://w3id.org/h2kg/hydrogen-ontology#CatalystCoatedMembrane
    anchor_label: Catalyst Coated Membrane
    evidence: reviewed fixture decision
semantic_projections: []
''',
        encoding="utf-8",
    )
    result = build_decode_workflow_release(snapshot, tmp_path / "output", config)
    assert result["status"] == "generated"
    assert result["validation_status"] == "passed"
    graph = json.loads((tmp_path / "output" / "decode" / "decode_federated_graph.json").read_text(encoding="utf-8"))
    assert graph["counts"]["source_node_count"] == 5
    assert graph["counts"]["source_edge_count"] == 2
    assert {edge["source"] for edge in graph["source_edges"]} == {"prep::n0", "fib::n0"}
    anchor = graph["anchors"][0]
    assert anchor["id"].endswith("#CatalystCoatedMembrane")
    assert set(anchor["occurrence_ids"]) == {"prep::n1", "fib::n0"}
    assert graph["anchor_index"][anchor["id"]] == anchor["occurrence_ids"]
    unresolved = next(node for node in graph["nodes"] if node["id"] == "unreviewed::n0")
    assert unresolved["mapping_state"] == "unresolved"
    assert unresolved["visual_category"] == "material"
    ccm_occurrence = next(node for node in graph["nodes"] if node["id"] == "prep::n1")
    assert ccm_occurrence["visual_category"] == "component"
    assert not graph["semantic_edges"]
    candidates = (tmp_path / "output" / "decode" / "decode_anchor_candidates.csv").read_text(encoding="utf-8")
    assert "recommended_state" in candidates
    assert (tmp_path / "output" / "decode" / "workflows" / "prep.jsonld").exists()
    assert (tmp_path / "output" / "decode" / "workflows" / "prep.ttl").exists()


def test_reviewed_semantic_projections_must_trace_a_source_dependency(tmp_path: Path) -> None:
    snapshot = tmp_path / "decode.json"
    snapshot.write_text(
        json.dumps(
            {
                "workflows": [
                    {
                        "id": "workflow", "iri": "https://example.org/workflow", "title": "Workflow", "source_filename": "workflow.graphml", "source_sha256": "workflow", "method_family": "other",
                        "nodes": [
                            {"id": "workflow::n0", "source_id": "n0", "iri": "https://example.org/workflow/n0", "label": "Material", "native_category": "material", "description": "", "shape": "ellipse"},
                            {"id": "workflow::n1", "source_id": "n1", "iri": "https://example.org/workflow/n1", "label": "Measurement", "native_category": "method", "description": "", "shape": "rectangle"},
                        ],
                        "edges": [{"id": "workflow::e0", "source_id": "n0", "target_id": "n1", "source": "workflow::n0", "target": "workflow::n1", "description": ""}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    config = tmp_path / "mappings.yaml"
    config.write_text(
        """mappings: []
semantic_projections:
  - workflow_id: workflow
    source_node_id: n0
    target_node_id: n1
    predicate: https://w3id.org/h2kg/hydrogen-ontology#hasInputMaterial
""",
        encoding="utf-8",
    )
    build_decode_workflow_release(snapshot, tmp_path / "output", config)
    graph = json.loads((tmp_path / "output" / "decode" / "decode_federated_graph.json").read_text(encoding="utf-8"))
    assert graph["semantic_edges"][0]["source_dependency_id"] == "workflow::e0"
    validation = json.loads((tmp_path / "output" / "decode" / "decode_validation_report.json").read_text(encoding="utf-8"))
    assert validation["untraceable_semantic_edge_ids"] == []


def test_decode_registry_resolves_unmapped_concepts_to_reviewed_anchors(tmp_path: Path) -> None:
    snapshot = tmp_path / "decode.json"
    snapshot.write_text(
        json.dumps(
            {
                "workflows": [
                    {
                        "id": "one", "iri": "https://example.org/one", "title": "One", "source_filename": "one.graphml", "source_sha256": "one", "method_family": "other",
                        "nodes": [{"id": "one::n0", "source_id": "n0", "iri": "https://example.org/one/n0", "label": "Custom electrolyte", "native_category": "material", "description": "", "shape": "ellipse"}], "edges": [],
                    },
                    {
                        "id": "two", "iri": "https://example.org/two", "title": "Two", "source_filename": "two.graphml", "source_sha256": "two", "method_family": "other",
                        "nodes": [{"id": "two::n0", "source_id": "n0", "iri": "https://example.org/two/n0", "label": "Custom electrolyte", "native_category": "material", "description": "", "shape": "ellipse"}], "edges": [],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    config = tmp_path / "mappings.yaml"
    config.write_text(
        """default_alignment:
  enabled: true
  role_by_visual_category:
    material: https://w3id.org/h2kg/hydrogen-ontology#Matter
mappings: []
semantic_projections: []
""",
        encoding="utf-8",
    )
    build_decode_workflow_release(snapshot, tmp_path / "output", config)
    graph = json.loads((tmp_path / "output" / "decode" / "decode_federated_graph.json").read_text(encoding="utf-8"))
    assert {node["decision"] for node in graph["nodes"]} == {"reviewed_decode_anchor"}
    assert graph["nodes"][0]["canonical_role_iri"].endswith("#Matter")
    registry = json.loads((tmp_path / "output" / "decode" / "decode_concept_registry.json").read_text(encoding="utf-8"))
    assert registry["counts"]["concept_count"] == 1
    assert registry["concepts"][0]["occurrence_count"] == 2


def test_decode_alias_curation_updates_only_explicit_target(tmp_path: Path) -> None:
    target = "https://w3id.org/h2kg/hydrogen-ontology#ElectrochemicallyActiveSurfaceArea"
    ontology = tmp_path / "ontology.jsonld"
    ontology.write_text(
        json.dumps([{"@id": target, "http://www.w3.org/2004/02/skos/core#altLabel": [{"@value": "existing"}]}]),
        encoding="utf-8",
    )
    config = tmp_path / "mappings.yaml"
    config.write_text(f"alias_curation:\n  - target_iri: {target}\n    aliases: [ECSA]\n", encoding="utf-8")
    result = apply_decode_alias_curation(ontology, config)
    assert result["count"] == 1
    content = json.loads(ontology.read_text(encoding="utf-8"))
    aliases = content[0]["http://www.w3.org/2004/02/skos/core#altLabel"]
    assert {item["@value"] for item in aliases} == {"existing", "ECSA"}


def test_semantic_overview_collapses_gde_occurrences_without_changing_source_graph(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    build_decode_workflow_release(
        root / "input" / "decode_workflows_source.json",
        tmp_path / "output",
        root / "config" / "decode_workflow_mappings.yaml",
        root / "input" / "current_ontology.jsonld",
    )
    graph = json.loads((tmp_path / "output" / "decode" / "decode_federated_graph.json").read_text(encoding="utf-8"))
    overview = graph["semantic_overview"]
    assert graph["counts"]["source_node_count"] == 2951
    assert graph["counts"]["source_edge_count"] == 3986
    assert graph["counts"]["duplicate_occurrence_group_count"] == 293
    assert graph["counts"]["workflows_with_duplicate_occurrences"] == 84
    assert graph["counts"]["semantic_role_conflict_count"] == 0
    assert graph["semantic_role_conflicts"] == []

    gde = next(
        row
        for row in graph["duplicate_occurrence_audit"]
        if row["workflow_id"] == "gde-cell-for-electrochemical-studies"
        and row["source_label"] == "GDE cell for electrochemical studies"
    )
    assert gde["occurrence_count"] == 3
    assert {value.rsplit("::", 1)[-1] for value in gde["occurrence_ids"]} == {"n10", "n11", "n12"}
    assert gde["collapse_eligible"] is True
    assert gde["context_classification"] == "distinct_branch_context"

    semantic_node = next(node for node in overview["nodes"] if node["id"] == gde["anchor_ids"][0])
    assert set(gde["occurrence_ids"]).issubset(set(semantic_node["occurrence_ids"]))
    overview_edge_ids = [
        edge_id
        for edge in overview["source_edges"]
        if all(
            pair["workflow_id"] != "iet-multiscale-model-interface"
            for pair in edge.get("occurrence_pairs", [])
        )
        for edge_id in edge["source_dependency_ids"]
    ]
    assert len(overview_edge_ids) == 3986
    assert len(set(overview_edge_ids)) == 3986


def test_role_curation_overrides_graphml_visual_categories(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    build_decode_workflow_release(
        root / "input" / "decode_workflows_source.json",
        tmp_path / "output",
        root / "config" / "decode_workflow_mappings.yaml",
        root / "input" / "current_ontology.jsonld",
    )
    registry = json.loads((tmp_path / "output" / "decode" / "decode_concept_registry.json").read_text(encoding="utf-8"))
    concepts = {concept["source_label"]: concept for concept in registry["concepts"]}

    assert concepts["LRE pH distribution"]["semantic_role"] == "Data"
    assert concepts["LRE pH distribution"]["role_assignment"] == "lre_ph_distribution_is_data"
    assert concepts["CLSM temperature"]["semantic_role"] == "Parameter"
    assert concepts["CLSM temperature"]["role_assignment"] == "clsm_temperature_is_parameter"
    assert concepts["Cell EIS"]["semantic_role"] == "Data"
    assert concepts["Cell Tafel slope"]["semantic_role"] == "Property"


def test_all_decode_edges_receive_traceable_semantic_classification(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    build_decode_workflow_release(
        root / "input" / "decode_workflows_source.json",
        tmp_path / "output",
        root / "config" / "decode_workflow_mappings.yaml",
        root / "input" / "current_ontology.jsonld",
        include_multiscale_interface=True,
    )
    graph = json.loads((tmp_path / "output" / "decode" / "decode_federated_graph.json").read_text(encoding="utf-8"))
    validation = json.loads((tmp_path / "output" / "decode" / "decode_validation_report.json").read_text(encoding="utf-8"))
    registry = graph["edge_registry"]

    assert len(graph["source_edges"]) == 4276
    assert len(registry) == 4276
    assert {row["source_dependency_id"] for row in registry} == {edge["id"] for edge in graph["source_edges"]}
    assert {row["projection_outcome"] for row in registry} <= {
        "h2kg_direct", "h2kg_reified", "prov_derivation", "decode_structural_only"
    }
    assert validation["status"] == "passed"
    assert validation["missing_edge_classifications"] == []
    assert validation["duplicated_edge_classifications"] == []

    fib_input = next(edge for edge in graph["semantic_edges"] if edge["source_dependency_id"] == "fib-sem-on-cl-material::e0")
    assert fib_input["predicate"].endswith("#hasInputMaterial")
    assert fib_input["source"] == "fib-sem-on-cl-material::n3"
    assert fib_input["target"] == "fib-sem-on-cl-material::n0"

    inert = next(node for node in graph["nodes"] if node["label"] == "Inert substrate")
    assert inert["semantic_role"] == "Matter"

    fib_turtle = (tmp_path / "output" / "decode" / "workflows" / "fib-sem-on-cl-material.ttl").read_text(encoding="utf-8")
    assert "#hasInputMaterial" in fib_turtle
    assert "#Measurement>" in fib_turtle
    assert "decode:SemanticProjection" in fib_turtle
    concepts = json.loads((tmp_path / "output" / "decode" / "decode_concept_registry.json").read_text(encoding="utf-8"))
    assert all(concept["role_assignment"] != "visual_category_fallback" for concept in concepts["concepts"])


def test_semantic_role_conflicts_are_audited_and_fail_validation(tmp_path: Path) -> None:
    snapshot = tmp_path / "decode.json"
    snapshot.write_text(
        json.dumps(
            {
                "workflows": [
                    {
                        "id": "fixture", "iri": "https://example.org/fixture", "title": "Fixture", "source_filename": "fixture.graphml", "source_sha256": "fixture", "method_family": "other",
                        "nodes": [
                            {"id": "fixture::n0", "source_id": "n0", "iri": "https://example.org/fixture/n0", "label": "Shared material", "native_category": "material", "description": "", "shape": "ellipse"},
                            {"id": "fixture::n1", "source_id": "n1", "iri": "https://example.org/fixture/n1", "label": "Shared method", "native_category": "", "description": "", "shape": "hexagon"},
                        ],
                        "edges": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    config = tmp_path / "mappings.yaml"
    config.write_text(
        """mappings:
  - source_label: Shared material
    state: reviewed_decode
    anchor_iri: https://w3id.org/h2kg/decode/workflow/anchor/conflict
    anchor_label: Deliberate conflict fixture
    canonical_role_iri: https://w3id.org/h2kg/hydrogen-ontology#Matter
    semantic_role: Matter
  - source_label: Shared method
    state: reviewed_decode
    anchor_iri: https://w3id.org/h2kg/decode/workflow/anchor/conflict
    anchor_label: Deliberate conflict fixture
    canonical_role_iri: https://w3id.org/h2kg/hydrogen-ontology#Measurement
    semantic_role: Measurement
semantic_projections: []
""",
        encoding="utf-8",
    )
    result = build_decode_workflow_release(snapshot, tmp_path / "output", config)
    graph = json.loads((tmp_path / "output" / "decode" / "decode_federated_graph.json").read_text(encoding="utf-8"))
    assert result["validation_status"] == "failed"
    assert graph["counts"]["semantic_role_conflict_count"] == 1
    node = graph["semantic_overview"]["nodes"][0]
    assert node["role_conflict"] is True
    assert node["semantic_role"] == "Mixed role"
    assert set(node["conflicting_canonical_role_iris"]) == {
        "https://w3id.org/h2kg/hydrogen-ontology#Matter",
        "https://w3id.org/h2kg/hydrogen-ontology#Measurement",
    }
    assert (tmp_path / "output" / "decode" / "decode_semantic_role_conflicts.csv").exists()
