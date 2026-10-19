from __future__ import annotations

import shutil
from pathlib import Path

from openpyxl import load_workbook

from aimworks_ontology_release.application_evaluation import build_application_evaluation


def test_application_evaluation_is_reproducible_and_does_not_fabricate_review(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "output"
    for relative in (
        "decode/decode_federated_graph.json",
        "decode/decode_concept_registry.json",
        "ontology/taxonomy_registry.json",
        "ontology/external_alignment_registry.json",
        "ontology/h2kg-v2-complete.ttl",
        "benchmarks/tib_collections/ontology_benchmark.csv",
    ):
        source = root / "output" / relative
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    result = build_application_evaluation(
        output,
        root / "input" / "itc_curated_interface.json",
        root / "input" / "tib_collection_candidate_cache.json",
    )
    assert result["status"] == "passed"
    assert result["coverage"]["canonical_source_concepts"] == 573
    assert result["coverage"]["public_h2kg_outcomes"] == 35
    assert result["coverage"]["decode_local_outcomes"] == 538
    assert result["itc_decode_crosswalk"]["itc_field_count"] == 44
    assert result["itc_decode_crosswalk"]["fields_overlapping_source_concept_registry"] == 11
    assert result["itc_decode_crosswalk"]["profile_overlay_only_fields"] == 33
    assert result["itc_decode_crosswalk"]["source_occurrences_covered_by_overlapping_fields"] == 43
    assert result["independent_semantic_audit_status"] == "awaiting_independent_review"
    assert result["independent_judgments_completed"] == 0

    workbook = load_workbook(output / "evaluation" / "independent_semantic_audit_instrument.xlsx")
    assert "ITC 44 fields" in workbook.sheetnames
    assert workbook["ITC 44 fields"].max_row == 45
    status = workbook["Audit status"]
    assert status["A2"].value == "awaiting_independent_review"
