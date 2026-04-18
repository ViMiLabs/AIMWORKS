from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .inspect import inspect_ontology
from .utils import deep_get, default_release_profile, dump_json, ensure_dir, try_load_yaml, write_text
from .validate import validate_release


def compute_fair_readiness(
    input_path: str | Path,
    output_dir: str | Path,
    config_dir: str | Path | None = None,
) -> dict[str, Any]:
    input_path = Path(input_path)
    output_dir = ensure_dir(Path(output_dir))
    generated_at = datetime.now(timezone.utc).isoformat()
    release_root = output_dir.parent if output_dir.name == "reports" else output_dir
    config_root = Path(config_dir or input_path.parent.parent / "config")
    profile = try_load_yaml(config_root / "release_profile.yaml", default_release_profile())
    inspection = inspect_ontology(input_path, output_dir, config_root)
    validation = validate_release(input_path, output_dir, config_root)
    release = validation["release_candidate"]
    project = profile["project"]
    publication = _publication_evidence(profile, release_root)

    docs_ready = (release_root / "docs" / "index.html").exists()
    machine_ttl_ready = (release_root / "ontology" / "schema.ttl").exists()
    machine_jsonld_ready = (release_root / "ontology" / "schema.jsonld").exists()
    mappings_ready = (release_root / "mappings" / "alignments.ttl").exists()
    examples_ready = (release_root / "examples" / "examples.ttl").exists()
    w3id_ready = (release_root / "w3id" / ".htaccess").exists()
    release_bundle_ready = (release_root / "release_bundle" / "RELEASE_NOTES.md").exists()
    odk_artifacts_ready = (release_root / "odk" / "artifacts" / "base.owl").exists()
    citation_ready = (release_root.parent / "CITATION.cff").exists()
    zenodo_ready = (release_root.parent / ".zenodo.json").exists()
    docs_url_ready = bool(project.get("docs_url"))
    repository_ready = bool(project.get("repository_url"))

    findable = _bounded_score(
        20 if inspection["ontology_iri"] else 0,
        15 if project.get("version_iri") and project.get("prior_version") else 8 if project.get("version_iri") else 0,
        15 if release["metadata_gap_count"] == 0 else max(0, 15 - 5 * int(release["metadata_gap_count"])),
        10 if citation_ready else 0,
        10 if repository_ready else 0,
        10 if publication["prepared_discovery"] else 0,
        10 if publication["resolver_established"] else 0,
        10 if publication["docs_published"] else 0,
        10 if publication["artifacts_published"] else 0,
    )
    accessible = _bounded_score(
        20 if machine_ttl_ready else 0,
        15 if machine_jsonld_ready else 0,
        15 if docs_ready else 0,
        10 if repository_ready else 0,
        8 if release_bundle_ready else 0,
        5 if odk_artifacts_ready else 0,
        15 if publication["docs_published"] else 0,
        15 if publication["artifacts_published"] else 0,
        12 if publication["resolver_established"] else 0,
    )
    interoperable = _bounded_score(
        20 if validation["release_candidate"]["imports_count"] > 0 else 0,
        18 if mappings_ready else 0,
        18 if validation["namespace_violations"] == 0 else 0,
        10 if validation["shacl"]["conforms"] is True else 0,
        12 if machine_jsonld_ready else 0,
        12 if validation["mapping_issues"] == 0 else 0,
        10 if inspection["counts"]["quantity_value_count"] > 0 else 0,
    )
    definition_coverage = float(release["definition_coverage"])
    reusable_base = _bounded_score(
        18 if release["metadata_gap_count"] == 0 else max(0, 18 - 4 * release["metadata_gap_count"]),
        12 if project.get("license") else 0,
        10 if project.get("version_iri") and project.get("prior_version") else 0,
        10 if examples_ready else 0,
        10 if release_bundle_ready else 0,
        10 if citation_ready else 0,
        8 if zenodo_ready else 0,
        22 if definition_coverage >= 0.95 else 14 if definition_coverage >= 0.8 else 6 if definition_coverage >= 0.6 else 0,
    )
    reusable_penalty = min(25, int(release["placeholder_definition_count"]) * 2) + (10 if validation["shacl"]["conforms"] is False else 0)
    reusable = max(0, reusable_base - reusable_penalty)

    fair_signals = [
        _score_row("F / Findable", findable, "Public-first release score for identifiers, versioning, citation, and publication establishment. Local build assets alone do not yield full credit."),
        _score_row("A / Accessible", accessible, "Public-first release score for machine-readable outputs, documentation, resolver state, and publication establishment. Local files alone do not yield full credit."),
        _score_row("I / Interoperable", interoperable, "Purely internal release-quality score for reuse of imports, mappings, namespace hygiene, and standards-based serializations."),
        _score_row("R / Reusable", reusable, "Purely internal release-quality score for license, provenance, versioning, definitions, examples, and release packaging."),
    ]
    transparency_hooks = [
        _external_row("OOPS! ontology pitfall scan", validation["external_assessments"]["oops"], "External ontology pitfall scan against the release candidate. Service availability is outside the repository."),
        _external_row("FOOPS! FAIR assessment", validation["external_assessments"]["foops"], "External FAIR-oriented ontology assessment against the release candidate. File mode does not assess accessibility."),
    ]
    validation_signals = [
        _status_row("Overall validation status", "good" if validation["valid"] else "action", "pass" if validation["valid"] else "fail", "Combined metadata, namespace, mapping, and SHACL validation checks."),
        _status_row("SHACL conforms", "good" if validation["shacl"]["conforms"] is not False else "action", str(validation["shacl"]["conforms"]), "Local SHACL shape execution when pyshacl is available."),
        _count_row(
            "Duplicate @id conflicts",
            int(validation.get("duplicate_review", {}).get("conflicting_count", 0)),
            "Duplicate source nodes are tolerated only when they merge without schema-type conflicts.",
        ),
        _count_row("Missing labels", release["missing_labels"], "Release-time missing labels on local schema terms."),
        _count_row("Missing definitions", release["missing_definitions"], "Release-time missing definitions or comments on local schema terms."),
        _count_row("Namespace violations", validation["namespace_violations"], "Violations against the active namespace policy."),
        _count_row("Mapping issues", validation["mapping_issues"], "Mappings that remain risky or inconsistent after local checks."),
        _status_row("OWL consistency hook", _optional_hook_status("owlready2"), _optional_hook_value("owlready2"), "Optional OWL reasoner hook. It is non-blocking and only runs when owlready2 is installed."),
        _status_row("EMMO checks", _optional_hook_status("EMMOntoPy"), _optional_hook_value("EMMOntoPy"), "Optional EMMO convention hook. It is non-blocking and only runs when EMMOntoPy is installed."),
        _external_hook_row("OOPS! hook", validation["external_assessments"]["oops"]),
        _external_hook_row("FOOPS! hook", validation["external_assessments"]["foops"]),
    ]
    publication_assets = [
        _asset_row("HTML reference page", _publication_asset_value(docs_ready, publication["docs_published"]), "Generated documentation assets. Public availability is tracked separately from local generation."),
        _asset_row("Machine-readable source", _publication_asset_value(machine_ttl_ready, publication["artifacts_published"]), "Primary Turtle serialization for the release candidate."),
        _asset_row("JSON-LD source", _publication_asset_value(machine_jsonld_ready, publication["artifacts_published"]), "JSON-LD serialization for the release candidate."),
        _asset_row("Alignment mappings", _publication_asset_value(mappings_ready, publication["artifacts_published"]), "Conservative alignment output for review and publication."),
        _asset_row("Examples module", _publication_asset_value(examples_ready, publication["artifacts_published"]), "Separated example and data-like instances."),
        _asset_row("Release bundle", "published" if release_bundle_ready and publication["artifacts_published"] else "prepared" if release_bundle_ready else "not built in docs-only run", "Bundle status depends on whether the current command executed the release-bundle stage."),
        _asset_row("w3id artifacts", "published" if publication["resolver_established"] else "prepared" if w3id_ready else "missing", "Resolver templates may be prepared locally even when public resolver registration is still pending."),
    ]

    result = {
        "generated_at": generated_at,
        "findable": findable,
        "accessible": accessible,
        "interoperable": interoperable,
        "reusable": reusable,
        "summary": (
            "FAIR signals on this page follow a public-first policy: local build artefacts improve readiness, but full findability and accessibility require publicly established publication infrastructure. "
            "External OOPS! and FOOPS! results are reported separately as observability signals so service outages do not masquerade as ontology quality."
        ),
        "publication_evidence": publication,
        "artifacts": [row["label"] for row in publication_assets if row["value"] == "ready"],
        "fair_signals": fair_signals,
        "transparency_hooks": transparency_hooks,
        "validation_signals": validation_signals,
        "publication_assets": publication_assets,
        "foops": validation["external_assessments"]["foops"],
        "oops": validation["external_assessments"]["oops"],
        "release_metrics": release,
        "section_explanations": {
            "fair_signals": "FAIR signals are public-first release indicators. Local artefacts and metadata improve readiness, but full Findable and Accessible credit requires publication to be explicitly established.",
            "transparency_hooks": "External service rows report what third-party assessment services returned, or state clearly when they were unavailable.",
            "validation_signals": "Validation signals summarize local structural, metadata, namespace, mapping, SHACL, and optional non-blocking hook checks on the release candidate.",
            "publication_assets": "Publication asset rows distinguish assets that were prepared locally from those explicitly treated as publicly established.",
        },
    }
    dump_json(output_dir / "fair_readiness_report.json", result)
    write_text(output_dir / "fair_readiness_report.md", _fair_markdown(result))
    write_text(output_dir / "release_readiness_report.md", _release_markdown(result))
    return result


def _bounded_score(*parts: int) -> int:
    return max(0, min(100, sum(parts)))


def _score_row(label: str, score: int, detail: str) -> dict[str, str]:
    if score >= 85:
        status = "good"
    elif score >= 65:
        status = "watch"
    else:
        status = "action"
    return {"label": label, "status": status, "value": f"{score} / 100", "detail": detail}


def _status_row(label: str, status: str, value: str, detail: str) -> dict[str, str]:
    return {"label": label, "status": status, "value": value, "detail": detail}


def _count_row(label: str, count: int, detail: str) -> dict[str, str]:
    status = "good" if count == 0 else "watch" if count <= 5 else "action"
    return {"label": label, "status": status, "value": str(count), "detail": detail}


def _external_row(label: str, assessment: dict[str, Any], detail: str) -> dict[str, str]:
    status = assessment.get("status", "unknown")
    if status == "assessed":
        if "overall_score" in assessment and assessment.get("overall_score") is not None:
            value = f"{assessment['overall_score']} / 100"
        else:
            value = f"{assessment.get('pitfall_count', 0)} findings"
        row_status = "good" if label.startswith("OOPS!") and assessment.get("pitfall_count", 1) == 0 else "watch"
        if label.startswith("FOOPS!") and assessment.get("overall_score", 0) >= 70:
            row_status = "good"
        elif label.startswith("FOOPS!") and assessment.get("overall_score", 0) < 50:
            row_status = "action"
        return {"label": label, "status": row_status, "value": value, "detail": detail}
    if status == "disabled":
        return {"label": label, "status": "optional", "value": "not enabled", "detail": assessment.get("message", detail)}
    return {"label": label, "status": "unavailable", "value": "external service unreachable", "detail": assessment.get("message", detail)}


def _external_hook_row(label: str, assessment: dict[str, Any]) -> dict[str, str]:
    status = assessment.get("status", "unknown")
    if status == "assessed":
        value = "assessed"
        detail = assessment.get("message", "")
        return {"label": label, "status": "good", "value": value, "detail": detail}
    if status == "disabled":
        return {"label": label, "status": "optional", "value": "not enabled", "detail": assessment.get("message", "")}
    return {"label": label, "status": "unavailable", "value": "external service unreachable", "detail": assessment.get("message", "")}


def _asset_row(label: str, value: str, detail: str) -> dict[str, str]:
    status = "good" if value == "published" else "watch" if value in {"prepared", "ready", "pending"} or "docs-only" in value else "action"
    return {"label": label, "status": status, "value": value, "detail": detail}


def _publication_asset_value(local_ready: bool, published: bool) -> str:
    if published:
        return "published"
    if local_ready:
        return "prepared"
    return "missing"


def _publication_evidence(profile: dict[str, Any], release_root: Path) -> dict[str, Any]:
    project = profile.get("project", {})
    publication_status = str(deep_get(project, "publication_status", default="local-build") or "local-build")
    resolver_status = str(deep_get(project, "resolver_status", default="prepared") or "prepared")
    docs_status = str(deep_get(project, "docs_publication_status", default="prepared") or "prepared")
    artifact_status = str(deep_get(project, "artifact_publication_status", default="prepared") or "prepared")

    docs_ready = (release_root / "docs" / "index.html").exists()
    machine_ready = (release_root / "ontology" / "schema.ttl").exists() and (release_root / "ontology" / "schema.jsonld").exists()
    w3id_ready = (release_root / "w3id" / ".htaccess").exists()
    docs_url_ready = bool(project.get("docs_url"))

    canonical_published = publication_status == "published"
    return {
        "publication_status": publication_status,
        "resolver_status": resolver_status,
        "docs_publication_status": docs_status,
        "artifact_publication_status": artifact_status,
        "prepared_discovery": bool(docs_url_ready or machine_ready or w3id_ready),
        "resolver_established": resolver_status == "established",
        "docs_published": docs_status == "published" and canonical_published,
        "artifacts_published": artifact_status == "published" and canonical_published,
        "public_establishment_pending": not canonical_published or resolver_status != "established",
    }


def _optional_hook_status(module_name: str) -> str:
    return "good" if importlib.util.find_spec(module_name) else "optional"


def _optional_hook_value(module_name: str) -> str:
    return "available" if importlib.util.find_spec(module_name) else f"not enabled in current environment ({module_name} not installed)"


def _fair_markdown(result: dict[str, Any]) -> str:
    rows = "\n".join(f"- {row['label']}: {row['value']} ({row['status']})" for row in result["fair_signals"])
    hooks = "\n".join(f"- {row['label']}: {row['value']} ({row['status']})" for row in result["transparency_hooks"])
    return f"""# FAIR Readiness Report

## Internal FAIR Signals

{rows}

## Transparency Hooks

{hooks}

## Summary

{result['summary']}
"""


def _release_markdown(result: dict[str, Any]) -> str:
    assets = "\n".join(f"- {row['label']}: {row['value']}" for row in result["publication_assets"])
    return f"""# Release Readiness Report

{result['summary']}

## Publication Assets

{assets}
"""
