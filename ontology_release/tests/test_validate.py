from __future__ import annotations

import json

from aimworks_ontology_release.validate import validate_release
from aimworks_ontology_release.validate import _parse_foops_response, _parse_oops_xml


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
