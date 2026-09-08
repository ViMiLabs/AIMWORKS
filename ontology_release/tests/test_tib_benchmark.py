from __future__ import annotations

import csv
import json
from pathlib import Path

from aimworks_ontology_release.tib_benchmark import (
    REVIEW_COLUMNS,
    build_tib_benchmark_package,
    normalized_label,
)

H2KG = "https://w3id.org/h2kg/hydrogen-ontology#"


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class FakeSession:
    def get(self, url: str, params: dict, timeout: int):
        if url.endswith("/ontologies"):
            return FakeResponse({"_embedded": {"ontologies": [{"ontologyId": "chmo", "numberOfTerms": 2, "config": {"title": "CHMO"}}]}})
        query = params["q"].lower()
        hits = {
            "scanning electron microscopy imaging": [{"iri": "urn:chmo:sem", "label": "scanning electron microscopy", "ontology": "chmo", "type": "class"}],
            "ionomer to carbon ratio": [{"iri": "urn:chmo:ratio", "label": "carbon ratio", "ontology": "chmo", "type": "class"}],
        }.get(query, [])
        return FakeResponse({"response": {"docs": hits}})


def _source(path: Path) -> Path:
    payload = [
        {"@id": f"{H2KG}ScanningElectronMicroscopyImaging", "@type": [f"{H2KG}Measurement"], "http://www.w3.org/2000/01/rdf-schema#label": [{"@value": "Scanning Electron Microscopy Imaging"}]},
        {"@id": f"{H2KG}IonomerToCarbonRatio", "@type": [f"{H2KG}Parameter"], "http://www.w3.org/2000/01/rdf-schema#label": [{"@value": "Ionomer To Carbon Ratio"}]},
        {"@id": f"{H2KG}hasMetadata", "@type": ["http://www.w3.org/2002/07/owl#ObjectProperty"], "http://www.w3.org/2000/01/rdf-schema#label": [{"@value": "has metadata"}]},
    ]
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_normalized_label_expands_acronyms_and_can_remove_role_words() -> None:
    assert normalized_label("SEM Imaging") == "scanning electron microscopy imaging"
    assert normalized_label("Scanning Electron Microscopy Imaging", remove_role_words=True) == "scanning electron microscopy"


def test_build_tib_benchmark_creates_reviewable_artifacts(tmp_path: Path) -> None:
    source = _source(tmp_path / "source.jsonld")
    snapshot = tmp_path / "tib_snapshot.json"
    summary = build_tib_benchmark_package(source, tmp_path / "output", snapshot, refresh=True, session=FakeSession())
    target = tmp_path / "output" / "benchmarks" / "tib_terminology"

    assert summary["h2kg_local_terms_assessed"] == 3
    assert (target / "candidate_mappings.json").exists()
    assert (target / "reviewed_mapping_matrix.csv").exists()
    assert (target / "unmatched_h2kg_terms.csv").exists()
    assert (target / "manuscript_reporting.md").exists()

    rows = list(csv.DictReader((target / "reviewed_mapping_matrix.csv").read_text(encoding="utf-8").splitlines()))
    sem = next(row for row in rows if row["h2kg_label"] == "Scanning Electron Microscopy Imaging")
    assert sem["match_strength"] == "normalized_equivalent_label"
    assert sem["review_decision"] == "pending_manual_review"
    assert "Ionomer To Carbon Ratio" in (target / "unmatched_h2kg_terms.csv").read_text(encoding="utf-8")


def test_existing_manual_decisions_are_preserved(tmp_path: Path) -> None:
    source = _source(tmp_path / "source.jsonld")
    snapshot = tmp_path / "tib_snapshot.json"
    target = tmp_path / "output" / "benchmarks" / "tib_terminology"
    build_tib_benchmark_package(source, tmp_path / "output", snapshot, refresh=True, session=FakeSession())
    review_path = target / "reviewed_mapping_matrix.csv"
    rows = list(csv.DictReader(review_path.read_text(encoding="utf-8").splitlines()))
    rows[0]["review_decision"] = "accept"
    rows[0]["reviewer"] = "Reviewer"
    with review_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_COLUMNS)
        writer.writeheader(); writer.writerows(rows)
    summary = build_tib_benchmark_package(source, tmp_path / "output", snapshot, refresh=False)
    assert summary["accepted_terms"] == 1
