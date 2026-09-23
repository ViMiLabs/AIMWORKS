from __future__ import annotations

import json

from aimworks_ontology_release.docs import build_docs


def test_decode_explorer_is_separate_from_tbox_explorer(mini_ontology_file, output_dir) -> None:
    (output_dir / "review").mkdir()
    (output_dir / "reports").mkdir()
    decode_dir = output_dir / "decode"
    decode_dir.mkdir()
    payload = {
        "counts": {"workflow_count": 1, "source_node_count": 2, "source_edge_count": 1, "anchor_count": 1},
        "workflows": [{"id": "fixture", "title": "Fixture", "source_filename": "fixture.graphml", "source_sha256": "x", "method_family": "other", "mapping_status": "mapped", "source_node_count": 2, "source_edge_count": 1, "mapped_anchor_count": 1, "cross_workflow_connection_count": 0}],
        "nodes": [], "anchors": [], "source_edges": [], "anchor_edges": [], "semantic_edges": [], "anchor_index": {},
    }
    (decode_dir / "decode_federated_graph.json").write_text(json.dumps(payload), encoding="utf-8")
    build_docs(mini_ontology_file, output_dir / "docs")
    page = (output_dir / "docs" / "pages" / "decode-workflows.html").read_text(encoding="utf-8")
    explorer = (output_dir / "docs" / "data" / "explorer.json").read_text(encoding="utf-8")
    assert "Federated DECODE workflow graph" in page
    assert "decode_workflows.json" in page
    assert "decode-h2kg-aligned-ontology.ttl" in page
    assert "decode-h2kg-aligned-ontology.jsonld" in page
    assert "License is pending" not in page
    assert "license is pending governance confirmation" in page
    assert (output_dir / "docs" / "assets" / "decode-workflows.js").exists()
    assert (output_dir / "docs" / "assets" / "decode-workflows.css").exists()
    assert (output_dir / "docs" / "data" / "decode_workflows.json").exists()
    assert "decode/workflow/" not in explorer
    script = (output_dir / "docs" / "assets" / "decode-workflows.js").read_text(encoding="utf-8")
    assert "shownWorkflows" in script
    assert "rankedConnectedWorkflows" in script
    assert "Add full workflow" in script
    assert "showHover" in script
    assert "Semantic overview" in page
    assert "Preserved source occurrences" in page
    assert "Projection outcome" in page
    assert "semantic_overview" in script
    assert "decode_duplicate_occurrence_audit.csv" in script
    assert 'value="source" type="radio" checked' in page
    assert "viewMode = 'source'" in script
    assert "function semanticRoleKey" in script
    assert "function updateLegend" in script
    assert 'role = "measurement"' in script
    assert 'node[kind = "occurrence"][role = "parameter"]' in script
    assert 'node[kind = "occurrence"][role = "data"]' in script
    assert "Semantic role (node fill)" in script
    assert "Mixed role" in script
    assert "decode-semantic-filter" in script
    assert "dependencyToggle = $('#decode-show-dependencies')" in script
    assert "[sourceToggle, anchorToggle, semanticToggle, dependencyToggle, semanticFilter]" in script
    assert "edgeDecisionHtml" in script
    assert "decode_edge_registry.csv" in script
