from __future__ import annotations

from aimworks_ontology_release.battinfo_overlap import analyze_battinfo_overlap
from aimworks_ontology_release.release import run_pipeline

LOCAL = "https://w3id.org/h2kg/hydrogen-ontology#"
RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"

BATTINFO_SAMPLE = """
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

<https://w3id.org/emmo#EMMO_frequency> rdf:type owl:Class ;
    <http://www.w3.org/2004/02/skos/core#prefLabel> "Frequency"@en .

<https://w3id.org/emmo/domain/electrochemistry#electrochemistry_limiting_current> rdf:type owl:Class ;
    <http://www.w3.org/2004/02/skos/core#prefLabel> "LimitingCurrent"@en ;
    <http://www.w3.org/2004/02/skos/core#altLabel> "Limiting Current Density"@en .
"""


def _text(value: str) -> dict[str, str]:
    return {"@value": value}


def test_battinfo_overlap_classifies_exact_and_partial_matches(tmp_path) -> None:
    payload = [
        {"@id": f"{LOCAL}Frequency", RDFS_LABEL: [_text("Frequency")]},
        {"@id": f"{LOCAL}LimitingCurrentDensity", RDFS_LABEL: [_text("Limiting Current Density")]},
        {"@id": f"{LOCAL}PEMFCCathodeCatalystLayer", RDFS_LABEL: [_text("PEMFC Cathode Catalyst Layer")]},
    ]

    report = analyze_battinfo_overlap(payload, tmp_path, battinfo_text=BATTINFO_SAMPLE)

    assert report["status"] == "ok"
    assert report["exact_pref_overlap_count"] == 1
    assert report["exact_alt_overlap_count"] == 1
    assert report["reuse_directly_count"] == 1
    assert report["map_only_count"] == 1
    assert report["keep_local_count"] == 1
    assert report["reuse_directly"][0]["h2kg_label"] == "Frequency"
    assert report["map_only"][0]["h2kg_label"] == "Limiting Current Density"
    assert report["keep_local"][0]["h2kg_label"] == "PEMFC Cathode Catalyst Layer"


def test_quality_stage_writes_battinfo_overlap_report(temp_project) -> None:
    (temp_project / "cache" / "sources" / "battinfo-inferred.ttl").write_text(BATTINFO_SAMPLE, encoding="utf-8")

    result = run_pipeline("input/ONTOLOGY_PEMFC.jsonld", root=temp_project, stage="quality")

    assert result["battinfo_overlap_report"]["status"] == "ok"
    assert (temp_project / "output" / "reports" / "battinfo_overlap_report.json").exists()
    assert (temp_project / "output" / "reports" / "battinfo_overlap_report.md").exists()
