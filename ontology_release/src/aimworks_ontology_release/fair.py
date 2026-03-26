from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from .inspect import inspect_ontology
from .utils import default_release_profile, dump_json, ensure_dir, try_load_yaml, write_text
from .validate import validate_release


def compute_fair_readiness(
    input_path: str | Path,
    output_dir: str | Path,
    config_dir: str | Path | None = None,
) -> dict[str, Any]:
    input_path = Path(input_path)
    output_dir = ensure_dir(Path(output_dir))
    release_root = output_dir.parent if output_dir.name == "reports" else output_dir
    config_root = Path(config_dir or input_path.parent.parent / "config")
    profile = try_load_yaml(config_root / "release_profile.yaml", default_release_profile())
    inspection = inspect_ontology(input_path, output_dir, config_root)
    validation = validate_release(input_path, output_dir, config_root)
    release = validation["release_candidate"]
    project = profile["project"]

    docs_ready = (release_root / "docs" / "index.html").exists()
    machine_ttl_ready = (release_root / "ontology" / "schema.ttl").exists()
    machine_jsonld_ready = (release_root / "ontology" / "schema.jsonld").exists()
    mappings_ready = (release_root / "mappings" / "alignments.ttl").exists()
    examples_ready = (release_root / "examples" / "examples.ttl").exists()
    w3id_ready = (release_root / "w3id" / ".htaccess").exists()
    release_bundle_ready = (release_root / "release_bundle" / "RELEASE_NOTES.md").exists()
    citation_ready = (release_root.parent / "CITATION.cff").exists()
    zenodo_ready = (release_root.parent / ".zenodo.json").exists()
    docs_url_ready = bool(project.get("docs_url"))
    repository_ready = bool(project.get("repository_url"))

    findable = _bounded_score(
        16 if inspection["ontology_iri"] else 0,
        10 if project.get("version_iri") else 0,
        10 if release["metadata_gap_count"] == 0 else 0,
        10 if docs_url_ready else 0,
        10 if machine_ttl_ready and machine_jsonld_ready else 5 if machine_ttl_ready or machine_jsonld_ready else 0,
        8 if validation["release_candidate"]["imports_count"] > 0 else 0,
        8 if citation_ready else 0,
        6 if zenodo_ready else 0,
        8 if w3id_ready else 0,
    )
    accessible = _bounded_score(
        20 if machine_ttl_ready else 0,
        15 if machine_jsonld_ready else 0,
        12 if docs_ready else 0,
        12 if w3id_ready else 0,
        10 if repository_ready else 0,
        8 if docs_url_ready else 0,
        8 if release_bundle_ready else 0,
        15 if validation["external_assessments"]["foops"].get("dimensions", {}).get("accessible") is not None else 0,
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
        _score_row("F / Findable", findable, "Internal score for identifiers, versioning, citation, namespace, and findable publication metadata."),
        _score_row("A / Accessible", accessible, "Internal score for machine-readable outputs, docs presence, resolver artifacts, and public access hooks."),
        _score_row("I / Interoperable", interoperable, "Internal score for reuse of imports, mappings, namespace hygiene, and standards-based serializations."),
        _score_row("R / Reusable", reusable, "Internal score for license, provenance, versioning, definitions, examples, and release packaging."),
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
        _status_row("OWL consistency hook", _optional_hook_status("owlready2"), _optional_hook_value("owlready2"), "Optional OWL reasoner hook. It is skipped when owlready2 is not installed."),
        _status_row("EMMO checks", _optional_hook_status("EMMOntoPy"), _optional_hook_value("EMMOntoPy"), "Optional EMMO convention hook. It is skipped when EMMOntoPy is not installed."),
        _external_hook_row("OOPS! hook", validation["external_assessments"]["oops"]),
        _external_hook_row("FOOPS! hook", validation["external_assessments"]["foops"]),
    ]
    publication_assets = [
        _asset_row("HTML reference page", "ready" if docs_ready else "pending", "Generated public documentation page."),
        _asset_row("Machine-readable source", "ready" if machine_ttl_ready else "missing", "Primary Turtle serialization for the release candidate."),
        _asset_row("JSON-LD source", "ready" if machine_jsonld_ready else "missing", "JSON-LD serialization for the release candidate."),
        _asset_row("Alignment mappings", "ready" if mappings_ready else "missing", "Conservative alignment output for review and publication."),
        _asset_row("Examples module", "ready" if examples_ready else "missing", "Separated example and data-like instances."),
        _asset_row("Release bundle", "ready" if release_bundle_ready else "not built in docs-only run", "Bundle status depends on whether the current command executed the release-bundle stage."),
        _asset_row("w3id artifacts", "ready" if w3id_ready else "missing", "Redirect templates and publication notes for stable public identifiers."),
    ]

    result = {
        "findable": findable,
        "accessible": accessible,
        "interoperable": interoperable,
        "reusable": reusable,
        "summary": (
            "Internal FAIR signals are local release-readiness indicators. "
            "External OOPS! and FOOPS! results are reported separately so service outages do not masquerade as ontology quality."
        ),
        "artifacts": [row["label"] for row in publication_assets if row["value"] == "ready"],
        "fair_signals": fair_signals,
        "transparency_hooks": transparency_hooks,
        "validation_signals": validation_signals,
        "publication_assets": publication_assets,
        "foops": validation["external_assessments"]["foops"],
        "oops": validation["external_assessments"]["oops"],
        "release_metrics": release,
        "section_explanations": {
            "fair_signals": "Internal FAIR signals estimate release readiness from the built ontology package itself. They are conservative but not equivalent to live post-publication FAIR audits.",
            "transparency_hooks": "External transparency hooks call public assessment services. Their availability depends on external infrastructure and network access.",
            "validation_signals": "Validation signals summarize local structural, metadata, namespace, mapping, and optional SHACL checks on the release candidate.",
            "publication_assets": "Publication asset rows show whether the files required for public release were actually built in the current run.",
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
        return {"label": label, "status": "watch", "value": "disabled", "detail": assessment.get("message", detail)}
    return {"label": label, "status": "watch", "value": "service unavailable", "detail": assessment.get("message", detail)}


def _external_hook_row(label: str, assessment: dict[str, Any]) -> dict[str, str]:
    status = assessment.get("status", "unknown")
    if status == "assessed":
        value = "assessed"
        detail = assessment.get("message", "")
        return {"label": label, "status": "good", "value": value, "detail": detail}
    if status == "disabled":
        return {"label": label, "status": "watch", "value": "disabled", "detail": assessment.get("message", "")}
    return {"label": label, "status": "watch", "value": "service unavailable", "detail": assessment.get("message", "")}


def _asset_row(label: str, value: str, detail: str) -> dict[str, str]:
    status = "good" if value == "ready" else "watch" if "docs-only" in value or value == "pending" else "action"
    return {"label": label, "status": status, "value": value, "detail": detail}


def _optional_hook_status(module_name: str) -> str:
    return "good" if importlib.util.find_spec(module_name) else "watch"


def _optional_hook_value(module_name: str) -> str:
    return "available" if importlib.util.find_spec(module_name) else f"skipped ({module_name} not installed)"


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
