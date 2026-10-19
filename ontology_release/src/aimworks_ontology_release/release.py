from __future__ import annotations

import json
import hashlib
import shutil
import zipfile
from pathlib import Path
from typing import Any

from .docs import build_docs
from .decode_workflows import build_decode_workflow_release
from .enrich import enrich_ontology
from .fair import compute_fair_readiness
from .afm_pilot import build_afm_pilot_package
from .application_evaluation import build_application_evaluation
from .fib_sem_pilot import build_fib_sem_pilot_package
from .hdo import load_hdo_alignment_report
from .ic_sem_pilot import build_ic_sem_pilot_package
from .inspect import inspect_ontology
from .itc_pilot import build_itc_pilot_package
from .llm_annotator import draft_annotations
from .mapper import propose_mappings
from .neutron_tomo_pilot import build_neutron_tomo_pilot_package
from .method_data_profiles import build_method_data_profiles
from .normalize_source import normalize_source_document
from .odk import load_odk_manifest, prepare_odk_shadow
from .profile_modules import build_profile_modules
from .sem_pilot import build_sem_pilot_package
from .semantic_instances import normalize_generated_example_instances
from .split import split_ontology
from .synchrotron_xray_tomo_pilot import build_synchrotron_xray_tomo_pilot_package
from .taxonomy import build_taxonomy_release
from .tem_pilot import build_tem_pilot_package
from .tib_benchmark import build_tib_benchmark_package
from .tib_collections import build_collection_benchmark
from .xps_pilot import build_xps_pilot_package
from .xrd_pilot import build_xrd_pilot_package
from .utils import ensure_dir, write_text
from .validate import validate_release
from .w3id import generate_w3id_artifacts


def run_release(
    input_path: str | Path,
    project_root: str | Path,
    draft_llm: bool = False,
    rewrite: bool = False,
) -> dict[str, Any]:
    project_root = Path(project_root)
    output_root = project_root / "output"
    prior_alignment_registry_path = output_root / "ontology" / "external_alignment_registry.json"
    prior_alignment_registry_text = (
        prior_alignment_registry_path.read_text(encoding="utf-8")
        if prior_alignment_registry_path.exists()
        else ""
    )
    # Public outputs are generated deterministically. Removing old generated
    # directories prevents superseded status labels and filenames from leaking
    # into a later release bundle. ODK is preserved because it may contain an
    # independently executed reasoner/QC manifest.
    for folder in (
        "mappings", "reports", "examples", "method_profiles",
        "benchmarks", "decode", "evaluation", "w3id", "release_bundle",
    ):
        path = output_root / folder
        if path.exists():
            shutil.rmtree(path)
    _reset_directory_except(output_root / "ontology", {"releases"})
    _reset_docs_output(output_root / "docs")
    output_root = ensure_dir(output_root)
    reports_dir = ensure_dir(output_root / "reports")
    review_dir = ensure_dir(output_root / "review")
    ontology_dir = ensure_dir(output_root / "ontology")
    ensure_dir(output_root / "mappings")
    ensure_dir(output_root / "examples")
    ensure_dir(output_root / "docs")
    ensure_dir(output_root / "w3id")
    ensure_dir(output_root / "odk")
    if rewrite:
        normalize_source_document(input_path, reports_dir, write_in_place=True)
    else:
        normalize_source_document(
            input_path,
            reports_dir,
            write_in_place=False,
            emit_normalized_document=False,
        )
    inspection = inspect_ontology(input_path, reports_dir, project_root / "config")
    split_summary = split_ontology(input_path, ontology_dir, project_root / "config")
    mappings = propose_mappings(input_path, review_dir, project_root / "config")
    taxonomy_config = project_root / "config" / "taxonomy.yaml"
    taxonomy = (
        build_taxonomy_release(input_path, output_root, project_root / "config")
        if taxonomy_config.exists()
        else {"status": "skipped_missing_config", "config": str(taxonomy_config)}
    )
    hdo = load_hdo_alignment_report(reports_dir)
    enrich_ontology(input_path, ontology_dir, project_root / "config")
    profile_modules = build_profile_modules(input_path, ontology_dir, project_root / "config")
    drafts = draft_annotations(input_path, review_dir, draft_llm, project_root / "config" / "llm_agent.example.yaml")
    validation = validate_release(input_path, reports_dir, project_root / "config")
    tem_pilot = build_tem_pilot_package(input_path, output_root)
    sem_pilot = build_sem_pilot_package(input_path, output_root)
    fib_sem_pilot = build_fib_sem_pilot_package(input_path, output_root)
    ic_sem_pilot = build_ic_sem_pilot_package(input_path, output_root)
    afm_pilot = build_afm_pilot_package(input_path, output_root)
    neutron_tomo_pilot = build_neutron_tomo_pilot_package(input_path, output_root)
    synchrotron_xray_tomo_pilot = build_synchrotron_xray_tomo_pilot_package(input_path, output_root)
    xrd_pilot = build_xrd_pilot_package(input_path, output_root)
    xps_pilot = build_xps_pilot_package(input_path, output_root)
    semantic_instances = normalize_generated_example_instances(
        output_root,
        output_root / "ontology" / "taxonomy_registry.json",
    )
    itc_pilot = build_itc_pilot_package(
        input_path,
        output_root,
        project_root / "input" / "itc_curated_interface.json",
    )
    method_data_profiles = build_method_data_profiles(input_path, output_root)
    decode_workflows = build_decode_workflow_release(
        project_root / "input" / "decode_workflows_source.json",
        output_root,
        project_root / "config" / "decode_workflow_mappings.yaml",
        input_path,
        include_multiscale_interface=True,
        manual_overlay_path=project_root / "input" / "decode_manual_workflow_overlay.json",
    )
    tib_benchmark = build_tib_benchmark_package(
        input_path,
        output_root,
        project_root / "input" / "tib_terminology_snapshot.json",
    )
    tib_collection_benchmark = build_collection_benchmark(
        output_root / "ontology" / "taxonomy_registry.json",
        output_root,
        project_root / "input" / "tib_collection_snapshot.json",
        project_root / "input" / "tib_collection_candidate_cache.json",
        existing_mapping_path=output_root / "ontology" / "external_alignment_registry.json",
        existing_harmonization_path=project_root / "config" / "tib_auto_harmonization.json",
        correction_registry_path=project_root / "config" / "tib_h2kg_corrections.json",
    )
    # Rebuild the taxonomy publication surfaces with the harmonization registry
    # generated from this same frozen-snapshot run.  This prevents the bridge
    # from lagging one release behind the benchmark that justifies it.
    generated_harmonization = (
        output_root / "benchmarks" / "tib_collections" / "automatic_harmonization_registry.json"
    )
    if taxonomy_config.exists() and generated_harmonization.exists():
        if prior_alignment_registry_text:
            write_text(prior_alignment_registry_path, prior_alignment_registry_text)
        taxonomy = build_taxonomy_release(
            input_path,
            output_root,
            project_root / "config",
            auto_harmonization_override=json.loads(generated_harmonization.read_text(encoding="utf-8")),
        )
    application_evaluation = build_application_evaluation(
        output_root,
        project_root / "input" / "itc_curated_interface.json",
        project_root / "input" / "tib_collection_candidate_cache.json",
    )
    # Preserve an already-executed actual ODK manifest so the website and
    # release bundle continue to show the real ODK command history, version,
    # and QC state. Fall back to collect-only when the actual manifest has not
    # been produced yet.
    existing_odk = load_odk_manifest(output_root)
    taxonomy_path = output_root / "ontology" / "h2kg-v2-taxonomy.ttl"
    taxonomy_sha256 = _sha256_file(taxonomy_path) if taxonomy_path.exists() else ""
    preserve_actual_odk = (
        existing_odk.get("execution_mode") == "actual"
        and existing_odk.get("command_results")
        and existing_odk.get("taxonomy_sha256") == taxonomy_sha256
        and _odk_public_artifacts_are_clean(output_root / "odk" / "artifacts")
    )
    if preserve_actual_odk:
        odk = existing_odk
    else:
        odk = prepare_odk_shadow(
            input_path,
            project_root,
            project_root / "config",
            collect_only=True,
            prefer_actual_outputs=False,
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
        "taxonomy": taxonomy,
        "hdo": hdo,
        "profile_modules": profile_modules,
        "annotation_drafts": len(drafts),
        "validation": validation,
        "tem_pilot": tem_pilot,
        "sem_pilot": sem_pilot,
        "fib_sem_pilot": fib_sem_pilot,
        "ic_sem_pilot": ic_sem_pilot,
        "afm_pilot": afm_pilot,
        "neutron_tomo_pilot": neutron_tomo_pilot,
        "synchrotron_xray_tomo_pilot": synchrotron_xray_tomo_pilot,
        "xrd_pilot": xrd_pilot,
        "xps_pilot": xps_pilot,
        "semantic_instances": semantic_instances,
        "itc_pilot": itc_pilot,
        "method_data_profiles": method_data_profiles,
        "decode_workflows": decode_workflows,
        "tib_benchmark": tib_benchmark,
        "tib_collection_benchmark": tib_collection_benchmark,
        "application_evaluation": application_evaluation,
        "fair": fair,
        "odk": odk,
        "docs": docs,
        "w3id": w3id,
        "bundle": str(bundle),
    }
    write_text(project_root / "output" / "release_bundle" / "release_summary.json", json.dumps(summary, indent=2, ensure_ascii=False))
    _validate_public_release_content(project_root / "output" / "release_bundle")
    return summary


def build_release_bundle(project_root: str | Path) -> Path:
    project_root = Path(project_root)
    bundle_dir = project_root / "output" / "release_bundle"
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    ensure_dir(bundle_dir)
    for folder in ["ontology", "mappings", "reports", "examples", "method_profiles", "benchmarks", "decode", "evaluation", "docs", "w3id", "odk"]:
        source = project_root / "output" / folder
        target = bundle_dir / folder
        if target.exists():
            shutil.rmtree(target)
        if source.exists():
            shutil.copytree(source, target)
    write_text(bundle_dir / "RELEASE_NOTES.md", _release_notes())
    _validate_public_release_content(bundle_dir)
    return bundle_dir


def _reset_docs_output(docs_dir: Path) -> None:
    """Clear copied dynamic datasets while retaining stable documentation."""

    if not docs_dir.exists():
        return
    for name in ("benchmarks", "decode"):
        child = docs_dir / name
        if child.exists():
            shutil.rmtree(child)


def _reset_directory_except(path: Path, retained_names: set[str]) -> None:
    """Reset generated content without deleting immutable release directories."""

    if not path.exists():
        return
    for child in path.iterdir():
        if child.name in retained_names:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def _validate_public_release_content(bundle_dir: Path) -> None:
    """Reject reviewer-origin labels while allowing legitimate scientific AI terminology."""

    prohibited = (
        "ai-reviewed",
        "expert-reviewed",
        "expert-draft",
        "domain-expert-reviewed",
        "needs-expert-review",
        "needs_human_review",
        "reviewed_decode",
        "reviewer_decision",
    )
    text_suffixes = {
        ".css", ".csv", ".html", ".ipynb", ".js", ".json", ".jsonld",
        ".md", ".nt", ".owl", ".rdf", ".rq", ".sh", ".tsv", ".ttl",
        ".txt", ".xml", ".yaml", ".yml",
    }
    office_suffixes = {".docx", ".pptx", ".xlsx"}
    prohibited_public_filenames = (
        "decode_definition_drafts",
        "decode_definition_candidates",
        "decode_promotion_candidates",
        "decode_anchor_candidates",
        "itc_expert_review",
    )
    violations: list[str] = []
    for path in sorted(bundle_dir.rglob("*")):
        if not path.is_file():
            continue
        relative_path = path.relative_to(bundle_dir).as_posix()
        if any(value in path.name.casefold() for value in prohibited_public_filenames):
            violations.append(f"{relative_path}: prohibited public filename")
        suffix = path.suffix.casefold()
        if suffix in text_suffixes:
            content = path.read_text(encoding="utf-8", errors="replace").casefold()
        elif suffix in office_suffixes:
            content = _office_package_text(path).casefold()
        else:
            continue
        for phrase in prohibited:
            if phrase in content:
                violations.append(f"{relative_path}: {phrase}")
    if violations:
        raise ValueError(
            "Public release contains prohibited reviewer-origin language: "
            + "; ".join(violations[:20])
        )


def _office_package_text(path: Path) -> str:
    """Read textual XML from an Office Open XML package for release linting."""

    chunks: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                if name.casefold().endswith((".xml", ".rels")):
                    chunks.append(archive.read(name).decode("utf-8", errors="replace"))
    except zipfile.BadZipFile as exc:
        raise ValueError(f"Invalid Office release artifact: {path}") from exc
    return "\n".join(chunks)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _odk_public_artifacts_are_clean(artifact_dir: Path) -> bool:
    if not artifact_dir.exists():
        return False
    prohibited = (
        "ai-reviewed",
        "expert-reviewed",
        "expert-draft",
        "domain-expert-reviewed",
        "needs-expert-review",
        "needs_human_review",
        "reviewed_decode",
        "reviewer_decision",
    )
    checked = False
    for path in artifact_dir.iterdir():
        if not path.is_file() or path.suffix.casefold() not in {".json", ".jsonld", ".owl", ".rdf", ".ttl"}:
            continue
        checked = True
        content = path.read_text(encoding="utf-8", errors="replace").casefold()
        if any(phrase in content for phrase in prohibited):
            return False
    return checked


def _release_notes() -> str:
    return """# H₂KG 2.2.0 Release Notes

- Release title: H₂KG Domain Ontology for Hydrogen Electrochemical Systems
- Namespace policy: existing H2KG hash IRIs are preserved
- Semantic correction: scientific characteristics retain intrinsic Property identity while Parameter and DataPoint records express contextual workflow roles
- Workflow profiles: class-level workflow assertions are migrated to value-free SHACL profiles with complete provenance
- Compatibility: legacy assertions remain available only in the versioned compatibility artifact
- External alignment: conservative SKOS mappings are published separately from the H2KG taxonomy
"""
