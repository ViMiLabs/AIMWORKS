from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VISUALS_JS = ROOT / "output" / "docs" / "pemfc" / "assets" / "visuals.js"
VISUALS_HTML = ROOT / "output" / "docs" / "pemfc" / "pages" / "visualizations.html"


def test_visual_explorer_defaults_to_full_neighbor_rendering() -> None:
    content = VISUALS_JS.read_text(encoding="utf-8")

    assert "showExternalNeighbors: true" in content
    assert "Showing all connected nodes and visible relations around" in content
    assert "function radialPositions(graph)" in content
    assert "direct links" in content
    assert "MAX_VISIBLE_NODES" not in content
    assert "MAX_NEW_NEIGHBORS_PER_SOURCE" not in content


def test_visualization_page_enables_external_terms_by_default() -> None:
    content = VISUALS_HTML.read_text(encoding="utf-8")

    assert 'data-visual-toggle="showExternalNeighbors" checked' in content
    assert "full directly connected neighborhood" in content
