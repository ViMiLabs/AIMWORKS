from __future__ import annotations

import shutil
from pathlib import Path

from openpyxl import load_workbook

from aimworks_ontology_release.application_evaluation import build_application_evaluation


def test_application_evaluation_is_reproducible_and_traceable(tmp_path: Path) -> None:
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
        root / "config" / "comparator_evaluation.json",
    )
    assert result["status"] == "passed"
    assert result["coverage"]["canonical_source_concepts"] == 573
    assert result["coverage"]["public_h2kg_outcomes"] == 35
    assert result["coverage"]["decode_local_outcomes"] == 538
    assert result["itc_decode_crosswalk"]["itc_field_count"] == 44
    assert result["itc_decode_crosswalk"]["fields_overlapping_source_concept_registry"] == 11
    assert result["itc_decode_crosswalk"]["profile_overlay_only_fields"] == 33
    assert result["itc_decode_crosswalk"]["source_occurrences_covered_by_overlapping_fields"] == 43
    assert result["independent_semantic_audit_status"] == "complete"
    assert result["independent_judgments_completed"] == result["semantic_assessment"]["assessment_count"]
    assert result["semantic_assessment"]["unresolved_count"] == 0
    strata = {
        row["review_stratum"]: row["item_count"]
        for row in result["semantic_assessment"]["strata"]
    }
    assert strata["itc_field"] == 44
    assert strata["decode_concept"] == 573
    assert strata["decode_edge"] == 4463
    assert strata["h2kg_taxonomy_sample"] == 150
    assert result["retrieval"]["rq1_semantic_result_count"] == 26
    assert result["retrieval"]["rq1_semantic_workflow_count"] == 14
    assert result["retrieval"]["rq1_exact_label_result_count"] == 19
    assert result["retrieval"]["rq1_exact_label_workflow_count"] == 11
    assert result["retrieval"]["independent_precision_recall_claimed"] is False
    assert result["comparator_evaluation"]["resource_count"] == 4
    assert result["comparator_evaluation"]["task_count"] == 5
    assert result["comparator_evaluation"]["assessment_count"] == 20
    assert result["comparator_evaluation"]["aggregate_score_reported"] is False

    workbook = load_workbook(output / "evaluation" / "semantic_assessment_registry.xlsx")
    assert "ITC fields" in workbook.sheetnames
    assert workbook["ITC fields"].max_row == 45
    assert workbook["DECODE concepts"].max_row == 574
    assert workbook["DECODE edges"].max_row == 4464
    comparator = load_workbook(output / "evaluation" / "focused_comparator_matrix.xlsx")
    assert "Comparator matrix" in comparator.sheetnames
