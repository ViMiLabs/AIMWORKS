from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml
from rdflib import Graph
from rdflib.namespace import DCTERMS

from aimworks_ontology_release.taxonomy import H2KG_ONTOLOGY, build_taxonomy_release
from aimworks_ontology_release.tib_submission import (
    _resolve_public_url,
    build_tib_submission_package,
    write_release_citation_metadata,
)
from aimworks_ontology_release.w3id import generate_w3id_artifacts


ROOT = Path(__file__).resolve().parents[1]


def _prepared_output(
    tmp_path: Path,
    *,
    confirm_attribution: bool = False,
    missing_personal_orcid: bool = False,
    incomplete_contributor_order: bool = False,
) -> tuple[dict, Path, Path]:
    config_dir = tmp_path / "config"
    shutil.copytree(ROOT / "config", config_dir)
    if confirm_attribution or incomplete_contributor_order:
        profile_path = config_dir / "release_profile.yaml"
        document = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
        project = document["project"]
        if confirm_attribution:
            project["attribution_complete"] = True
            for order, contributor in enumerate(project["contributors"], start=1):
                contributor["contribution_order"] = order
        if missing_personal_orcid:
            project["contributors"][0]["iri"] = "https://www.fz-juelich.de/profile/kohandani_m"
        if incomplete_contributor_order:
            project["attribution_complete"] = False
            project["contributors"] = [
                row for row in project["contributors"] if row.get("contribution_order") != 3
            ]
        profile_path.write_text(
            yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=1000),
            encoding="utf-8",
        )
    output_root = tmp_path / "output"
    result = build_taxonomy_release(
        ROOT / "input" / "current_ontology.jsonld",
        output_root,
        config_dir,
    )
    generate_w3id_artifacts(output_root / "w3id", config_dir)
    write_release_citation_metadata(tmp_path, config_dir)
    return result, output_root, config_dir


def test_tib_submission_blocks_missing_personal_pid(tmp_path: Path) -> None:
    taxonomy, output_root, config_dir = _prepared_output(
        tmp_path,
        confirm_attribution=True,
        missing_personal_orcid=True,
    )
    with pytest.raises(ValueError, match="personal-pid-attribution"):
        build_tib_submission_package(
            taxonomy["taxonomy_ttl"],
            taxonomy["taxonomy_jsonld"],
            output_root,
            config_dir,
        )

    report_data = json.loads((output_root / "reports" / "tib_submission_validation.json").read_text(encoding="utf-8"))
    assert report_data["pre_release_ready"] is False
    assert report_data["counts"]["active_classes"] == 2226


def test_tib_submission_blocks_incomplete_contributor_order(tmp_path: Path) -> None:
    taxonomy, output_root, config_dir = _prepared_output(
        tmp_path,
        incomplete_contributor_order=True,
    )
    with pytest.raises(ValueError, match="attribution-list-complete"):
        build_tib_submission_package(
            taxonomy["taxonomy_ttl"],
            taxonomy["taxonomy_jsonld"],
            output_root,
            config_dir,
        )

    report_data = json.loads((output_root / "reports" / "tib_submission_validation.json").read_text(encoding="utf-8"))
    completeness = next(row for row in report_data["checks"] if row["id"] == "attribution-list-complete")
    assert completeness["passed"] is False
    assert "missing: [3]" in completeness["detail"]


def test_tib_submission_preflight_uses_full_taxonomy_and_official_shape(
    tmp_path: Path,
) -> None:
    taxonomy, output_root, config_dir = _prepared_output(tmp_path, confirm_attribution=True)
    report = build_tib_submission_package(
        taxonomy["taxonomy_ttl"], taxonomy["taxonomy_jsonld"], output_root, config_dir
    )

    assert report["pre_release_ready"] is True
    assert report["mandatory_warning_count"] == 0
    citation = yaml.safe_load((tmp_path / "CITATION.cff").read_text(encoding="utf-8"))
    people = {
        f"{row.get('given-names', '')} {row.get('family-names', '')}".strip(): row
        for row in citation["authors"]
        if row.get("given-names")
    }
    assert "RWTH Aachen University" in people["Marjan Kohandani"]["affiliation"]
    assert "CASA" in people["Mohammad J. Eslamibidgoli"]["affiliation"]
    assert people["Kourosh Malek"]["website"] == "https://www.fz-juelich.de/profile/malek_k"
    assert "RWTH Aachen University" in people["Michael Eikerling"]["affiliation"]
    assert report["counts"] == {
        "active_classes": 2226,
        "deprecated_classes": 160,
        "total_classes": 2386,
        "object_properties": 23,
        "datatype_properties": 1,
        "annotation_properties": 9,
        "taxonomy_individuals": 0,
    }
    manifest = json.loads(Path(report["manifest_json"]).read_text(encoding="utf-8"))
    assert manifest["collections"]["primary"] == "NFDI4Cat"
    assert manifest["canonical_turtle_url"].endswith("h2kg-v2-taxonomy.ttl")
    assert manifest["submission_status"] == "pre_release_ready"
    attribution = {row["label"]: row for row in manifest["attribution"]}
    assert attribution["Marjan Kohandani"]["affiliation_ids"] == ["a", "b", "c"]
    assert attribution["Mohammad J. Eslamibidgoli"]["affiliation_ids"] == ["a", "b"]
    assert attribution["Kourosh Malek"]["orcid_status"] == "unavailable"
    assert attribution["Kourosh Malek"]["identifier_type"] == "institutional_profile"
    assert attribution["Michael Eikerling"]["affiliation_ids"] == ["a", "b", "c"]


def test_tib_submission_fails_when_mandatory_abstract_is_missing(tmp_path: Path) -> None:
    taxonomy, output_root, config_dir = _prepared_output(tmp_path, confirm_attribution=True)
    graph = Graph().parse(taxonomy["taxonomy_ttl"], format="turtle")
    graph.remove((H2KG_ONTOLOGY, DCTERMS.abstract, None))
    graph.serialize(destination=taxonomy["taxonomy_ttl"], format="turtle")
    graph.serialize(destination=taxonomy["taxonomy_jsonld"], format="json-ld", indent=2)

    with pytest.raises(ValueError, match="tib-mandatory-metadata|abstract"):
        build_tib_submission_package(
            taxonomy["taxonomy_ttl"],
            taxonomy["taxonomy_jsonld"],
            output_root,
            config_dir,
        )


def test_ror_pid_uses_official_registry_fallback_when_resolver_is_rate_limited(monkeypatch) -> None:
    class Response:
        def __init__(self, status_code: int, url: str) -> None:
            self.status_code = status_code
            self.url = url

        def close(self) -> None:
            return None

    responses = iter(
        [
            Response(429, "https://ror.org/02nv7yv05"),
            Response(200, "https://api.ror.org/v2/organizations/02nv7yv05"),
        ]
    )
    monkeypatch.setattr(
        "aimworks_ontology_release.tib_submission.requests.get",
        lambda *args, **kwargs: next(responses),
    )

    passed, detail = _resolve_public_url("live-attribution-pid-1", "https://ror.org/02nv7yv05")

    assert passed is True
    assert "official ROR registry API" in detail
