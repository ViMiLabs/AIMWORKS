from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .docs import build_docs
from .decode_workflows import build_decode_workflow_release
from .enrich import enrich_ontology
from .fair import compute_fair_readiness
from .afm_pilot import build_afm_pilot_package
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
    output_root = ensure_dir(project_root / "output")
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
    inspection = inspect_ontology(input_path, reports_dir, project_root / "config")
    split_summary = split_ontology(input_path, ontology_dir, project_root / "config")
    mappings = propose_mappings(input_path, review_dir, project_root / "config")
    taxonomy_config = project_root / "config" / "taxonomy.yaml"
    prior_alignment_registry_path = output_root / "ontology" / "external_alignment_registry.json"
    prior_alignment_registry_text = (
        prior_alignment_registry_path.read_text(encoding="utf-8")
        if prior_alignment_registry_path.exists()
        else ""
    )
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
        project_root / "input" / "itc_expert_review.json",
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
    for folder in ["ontology", "mappings", "reports", "review", "examples", "method_profiles", "benchmarks", "decode", "docs", "w3id", "odk"]:
        source = project_root / "output" / folder
        target = bundle_dir / folder
        if target.exists():
            shutil.rmtree(target)
        if source.exists():
            shutil.copytree(source, target)
    write_text(bundle_dir / "RELEASE_NOTES.md", _release_notes())
    return bundle_dir


def _release_notes() -> str:
    return """# H2KG 2.1.0 Release Notes

- Release title: H2KG Domain-Specific Ontology for Hydrogen Electrochemical Systems
- Namespace policy: existing H2KG hash IRIs are preserved
- Semantic correction: scientific characteristics retain intrinsic Property identity while Parameter and DataPoint records express contextual workflow roles
- Workflow profiles: class-level workflow assertions are migrated to value-free SHACL profiles with complete provenance
- Compatibility: legacy assertions remain available only in the versioned compatibility artifact
- External alignment: conservative SKOS mappings are published separately from the H2KG taxonomy
"""
