from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .docs import build_docs
from .enrich import enrich_ontology
from .fair import compute_fair_readiness
from .hdo import load_hdo_alignment_report
from .inspect import inspect_ontology
from .llm_annotator import draft_annotations
from .mapper import propose_mappings
from .odk import load_odk_manifest, prepare_odk_shadow
from .profile_modules import build_profile_modules
from .split import split_ontology
from .utils import ensure_dir, write_text
from .validate import validate_release
from .w3id import generate_w3id_artifacts


def run_release(
    input_path: str | Path,
    project_root: str | Path,
    draft_llm: bool = False,
) -> dict[str, Any]:
    project_root = Path(project_root)
    output_root = ensure_dir(project_root / "output")
    reports_dir = ensure_dir(output_root / "reports")
    review_dir = ensure_dir(output_root / "review")
    ontology_dir = ensure_dir(output_root / "ontology")
    ensure_dir(output_root / "mappings")
    ensure_dir(output_root / "examples")
    ensure_dir(output_root / "docs")
    ensure_dir(output_root / "w3id")
    ensure_dir(output_root / "odk")
    inspection = inspect_ontology(input_path, reports_dir, project_root / "config")
    split_summary = split_ontology(input_path, ontology_dir, project_root / "config")
    mappings = propose_mappings(input_path, review_dir, project_root / "config")
    hdo = load_hdo_alignment_report(reports_dir)
    enrich_ontology(input_path, ontology_dir, project_root / "config")
    profile_modules = build_profile_modules(input_path, ontology_dir, project_root / "config")
    drafts = draft_annotations(input_path, review_dir, draft_llm, project_root / "config" / "llm_agent.example.yaml")
    validation = validate_release(input_path, reports_dir, project_root / "config")
    # Preserve an already-executed actual ODK manifest so the website and
    # release bundle continue to show the real ODK command history, version,
    # and QC state. Fall back to collect-only when the actual manifest has not
    # been produced yet.
    existing_odk = load_odk_manifest(output_root)
    if existing_odk.get("execution_mode") == "actual" and existing_odk.get("command_results"):
        odk = existing_odk
    else:
        odk = prepare_odk_shadow(
            input_path,
            project_root,
            project_root / "config",
            collect_only=True,
        )
    w3id = generate_w3id_artifacts(output_root / "w3id", project_root / "config")
    build_docs(input_path, output_root / "docs", project_root / "config", None)
    fair = compute_fair_readiness(input_path, reports_dir, project_root / "config")
    docs = build_docs(input_path, output_root / "docs", project_root / "config", fair)
    bundle = build_release_bundle(project_root)
    summary = {
        "inspection": inspection["counts"],
        "split": split_summary,
        "mappings": len(mappings),
        "hdo": hdo,
        "profile_modules": profile_modules,
        "annotation_drafts": len(drafts),
        "validation": validation,
        "fair": fair,
        "odk": odk,
        "docs": docs,
        "w3id": w3id,
        "bundle": str(bundle),
    }
    write_text(project_root / "output" / "release_bundle" / "release_summary.json", json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


def build_release_bundle(project_root: str | Path) -> Path:
    project_root = Path(project_root)
    bundle_dir = ensure_dir(project_root / "output" / "release_bundle")
    for folder in ["ontology", "mappings", "reports", "review", "examples", "docs", "w3id", "odk"]:
        source = project_root / "output" / folder
        target = bundle_dir / folder
        if target.exists():
            shutil.rmtree(target)
        if source.exists():
            shutil.copytree(source, target)
    write_text(bundle_dir / "RELEASE_NOTES.md", _release_notes())
    return bundle_dir


def _release_notes() -> str:
    return """# Release Notes Template

- Release title: H2KG Application Ontology for Hydrogen Electrochemical Systems
- Namespace policy: preserve existing h2kg hash IRIs
- Major release focus: metadata enrichment, schema/example separation, alignment review, static documentation, and FAIR readiness
"""
