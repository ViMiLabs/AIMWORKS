from __future__ import annotations

import json
from pathlib import Path

from aimworks_ontology_release.validate import validate_release
from aimworks_ontology_release.validate import _parse_foops_response, _parse_oops_xml


def _write_jsonld(path: Path, payload: list[dict]) -> Path:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def test_validate_outputs_reports(mini_ontology_file, output_dir):
    report = validate_release(mini_ontology_file, output_dir)
    assert "valid" in report
    assert (output_dir / "validation_report.md").exists()
    assert report["external_assessments"]["oops"]["status"] == "disabled"
    payload = json.loads((output_dir / "validation_report.json").read_text(encoding="utf-8"))
    assert payload["external_assessments"]["foops"]["status"] == "disabled"


def test_parse_oops_xml_extracts_pitfalls():
    xml_text = """<?xml version="1.0" encoding="UTF-8"?>
<oops:OOPSResponse xmlns:oops="http://www.oeg-upm.net/oops">
  <oops:Pitfall>
    <oops:Code>P10</oops:Code>
    <oops:Name>Missing disjointness</oops:Name>
    <oops:Description>The ontology lacks disjoint axioms.</oops:Description>
    <oops:Affects>
      <oops:AffectedElement>https://example.org/ClassA</oops:AffectedElement>
    </oops:Affects>
  </oops:Pitfall>
</oops:OOPSResponse>
"""
    parsed = _parse_oops_xml(xml_text)
    assert parsed["pitfall_count"] == 1
    assert parsed["pitfalls"][0]["code"] == "P10"


def test_parse_foops_response_extracts_scores_and_failed_checks():
    html = """
<html>
  <body>
    <h2>Overall score</h2>
    <div>47.8 / 100</div>
    <div>Findable 60.0 / 100</div>
    <div>Accessible not assessed</div>
    <div>Interoperable 33.3 / 100</div>
    <div>Reusable 50.0 / 100</div>
    <table>
      <tr><td>F1</td><td>failed</td><td>Missing persistent identifier metadata</td></tr>
    </table>
  </body>
</html>
"""
    parsed = _parse_foops_response(html)
    assert parsed["overall_score"] == 47.8
    assert parsed["dimensions"]["findable"] == 60.0
    assert parsed["dimensions"]["accessible"] is None
    assert parsed["failed_checks"][0]["label"] == "F1"


def test_validate_treats_non_conflicting_duplicates_as_merged(tmp_path: Path):
    source = _write_jsonld(
        tmp_path / "dup_ok.jsonld",
        [
            {
                "@id": "https://w3id.org/h2kg/hydrogen-ontology",
                "@type": ["http://www.w3.org/2002/07/owl#Ontology"],
            },
            {
                "@id": "https://w3id.org/h2kg/hydrogen-ontology#TermA",
                "@type": ["http://www.w3.org/2002/07/owl#Class"],
            },
            {
                "@id": "https://w3id.org/h2kg/hydrogen-ontology#TermA",
                "http://www.w3.org/2000/01/rdf-schema#label": [{"@value": "Term A"}],
            },
        ],
    )
    out = tmp_path / "reports"
    out.mkdir()
    report = validate_release(source, out)
    assert report["duplicate_review"]["duplicate_count"] == 1
    assert report["duplicate_review"]["conflicting_count"] == 0
    assert not any("duplicated @id values have conflicting schema typing" in line for line in report["warnings"])


def test_validate_flags_conflicting_duplicate_schema_types(tmp_path: Path):
    source = _write_jsonld(
        tmp_path / "dup_conflict.jsonld",
        [
            {
                "@id": "https://w3id.org/h2kg/hydrogen-ontology",
                "@type": ["http://www.w3.org/2002/07/owl#Ontology"],
            },
            {
                "@id": "https://w3id.org/h2kg/hydrogen-ontology#TermX",
                "@type": ["http://www.w3.org/2002/07/owl#Class"],
            },
            {
                "@id": "https://w3id.org/h2kg/hydrogen-ontology#TermX",
                "@type": ["http://www.w3.org/2002/07/owl#ObjectProperty"],
            },
        ],
    )
    out = tmp_path / "reports"
    out.mkdir()
    report = validate_release(source, out)
    assert report["duplicate_review"]["duplicate_count"] == 1
    assert report["duplicate_review"]["conflicting_count"] == 1
    assert any("duplicated @id values have conflicting schema typing" in line for line in report["warnings"])
