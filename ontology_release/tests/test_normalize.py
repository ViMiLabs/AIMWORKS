from __future__ import annotations

from aimworks_ontology_release.normalize import coerce_version, humanize_identifier, normalize_label


def test_normalization_helpers():
    assert humanize_identifier("hasQuantityValue") == "Has Quantity Value"
    assert normalize_label(" Pt Mass  ") == "pt mass"
    assert coerce_version("2026.3.0") == "2026.3.0"
