from __future__ import annotations

import json
from pathlib import Path

from aimworks_ontology_release.decode_workflows import build_decode_workflow_release, ingest_decode_graphml_directory


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
    assert not graph["semantic_edges"]
    assert (tmp_path / "output" / "decode" / "workflows" / "prep.jsonld").exists()
    assert (tmp_path / "output" / "decode" / "workflows" / "prep.ttl").exists()

