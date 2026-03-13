from __future__ import annotations

from pathlib import Path
import shutil
import uuid

from aimworks_ontology_release.io import load_graph, save_graph


def test_read_write_rdf(sample_graph):
    temp_root = Path(__file__).resolve().parents[1] / "pytest-cache-files-fixtures"
    temp_root.mkdir(parents=True, exist_ok=True)
    tmpdir = temp_root / f"testio-{uuid.uuid4().hex[:12]}"
    tmpdir.mkdir(parents=True, exist_ok=False)
    try:
        target = tmpdir / "graph.ttl"
        save_graph(sample_graph, target, "turtle")
        reloaded = load_graph(target, "turtle")
        assert len(reloaded) == len(sample_graph)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
