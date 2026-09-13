from __future__ import annotations

import json
from pathlib import Path

from aimworks_ontology_release.decode_multiscale_interface import build_decode_multiscale_model_interface


def test_pdf_derived_multiscale_interface_is_complete_and_value_free(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    result = build_decode_multiscale_model_interface(
        root / "input" / "decode_multiscale_model_interface.json",
        root / "input" / "decode_workflows_source.json",
        tmp_path / "output",
    )

    assert result["status"] == "generated"
    validation = result["validation"]
    assert validation["value_free_schema"] is True
    assert validation["source_pdf_redistributed"] is False
    assert validation["occurrence_count"] == 290
    assert validation["unique_identifier_count"] == 170
    assert len(validation["handoffs"]["itc_to_ctp"]) == 7
    assert len(validation["handoffs"]["ctp_to_ptp"]) == 14
    assert validation["from_measurement_assertions"] == 0

    package = Path(result["output_dir"])
    assert (package / "iet_multiscale_model_interface.graphml").exists()
    assert (package / "iet_multiscale_model_interface.jsonld").exists()
    assert (package / "iet_multiscale_model_interface.ttl").exists()
    assert (package / "iet_multiscale_model_interface_shapes.ttl").exists()

    jsonld = json.loads((package / "iet_multiscale_model_interface.jsonld").read_text(encoding="utf-8"))
    serialized = json.dumps(jsonld)
    assert "hasParameter" in serialized
    assert "hasInputData" in serialized
    assert "hasOutputData" in serialized
    assert "fromMeasurement" not in serialized
