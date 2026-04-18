from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import textwrap
from pathlib import Path
from typing import Any

from .utils import (
    COMMON_CONTEXT,
    RDFS_COMMENT,
    RDFS_LABEL,
    SKOS_DEFINITION,
    deep_get,
    default_release_profile,
    default_source_registry,
    dump_json,
    ensure_dir,
    now_iso,
    read_text,
    try_load_yaml,
    write_text,
)
import requests

try:
    from rdflib import Graph, URIRef
    from rdflib.namespace import OWL, RDF, RDFS
except Exception:  # pragma: no cover - dependency is expected in normal use
    Graph = None  # type: ignore[assignment]
    URIRef = None  # type: ignore[assignment]
    OWL = None  # type: ignore[assignment]
    RDF = None  # type: ignore[assignment]
    RDFS = None  # type: ignore[assignment]


SOURCE_URLS: dict[str, str] = {
    "emmo-core": "https://w3id.org/emmo#",
    "emmo-electrochemistry": "https://w3id.org/emmo/domain/electrochemistry#",
    "qudt-schema": "http://qudt.org/schema/qudt/",
    "qudt-units": "http://qudt.org/vocab/unit/",
    "qudt-quantitykinds": "http://qudt.org/vocab/quantitykind/",
    "chebi": "http://purl.obolibrary.org/obo/chebi.owl",
    "prov-o": "http://www.w3.org/ns/prov#",
    "dcterms": "http://purl.org/dc/terms/",
    "hdo": "https://materials-data-science-and-informatics.github.io/Helmholtz-Digitisation-Ontology-Documentation/index-en.html",
    "vann": "http://purl.org/vocab/vann/",
    "oeo": "http://openenergy-platform.org/ontology/oeo/",
    "pemfc-external": "",
}


def prepare_odk_shadow(
    input_path: str | Path,
    project_root: str | Path,
    config_dir: str | Path | None = None,
    prepare_only: bool = False,
    collect_only: bool = False,
    execute: bool = False,
) -> dict[str, Any]:
    project_root = Path(project_root)
    config_dir = Path(config_dir or project_root / "config")
    profile = try_load_yaml(config_dir / "release_profile.yaml", default_release_profile())
    odk_promotion_status = str(deep_get(profile, "release", "odk_promotion_status", default="shadow") or "shadow")
    source_registry = try_load_yaml(config_dir / "source_ontologies.yaml", default_source_registry())
    workbench = _ensure_odk_workbench(project_root, profile, source_registry)
    cache_refresh = _refresh_hdo_cache(config_dir, project_root)
    ci_reproducibility = _build_ci_reproducibility_report(project_root)
    output_root = ensure_dir(project_root / "output" / "odk")
    artifact_dir = ensure_dir(output_root / "artifacts")
    report_dir = ensure_dir(output_root / "reports")
    existing_manifest_path = output_root / "manifest.json"
    existing_manifest: dict[str, Any] = {}
    if existing_manifest_path.exists():
        try:
            existing_manifest = json.loads(read_text(existing_manifest_path))
        except Exception:
            existing_manifest = {}

    schema_source = _pick_existing(
        project_root / "output" / "ontology" / "schema.ttl",
        project_root / "ontology" / "schema.ttl",
        Path(input_path),
    )
    full_source = _pick_existing(
        project_root / "output" / "ontology" / "inferred.ttl",
        project_root / "output" / "ontology" / "schema.ttl",
        project_root / "ontology" / "schema.ttl",
        Path(input_path),
    )
    simple_source = _pick_existing(
        project_root / "output" / "ontology" / "schema.ttl",
        project_root / "ontology" / "schema.ttl",
        Path(input_path),
    )

    if prepare_only:
        manifest = {
            "enabled": True,
            "mode": "shadow",
            "status": "prepared",
            "authority": "AIMWORKS pipeline",
            "current_role": "ODK shadow-mode release/QC backend",
            "last_built": now_iso(),
            "reasoner": "ELK",
            "primary_artifact": "base",
            "odk_version": "prepared only",
            "workbench": {
                "root": str(workbench["root"]),
                "edit_file": str(workbench["edit_file"]),
                "config_file": str(workbench["config_file"]),
            },
            "cache_refresh": cache_refresh,
            "artifacts": [],
            "imports": [],
            "robot_summary": {"status": "watch", "errors": 0, "warnings": 1, "profile_violations": 0, "reasoning_status": "not run", "detail": "ODK workbench prepared but commands not executed yet."},
            "parity": {"status": "under review", "message": "ODK outputs have not been collected yet.", "class_count_diff": 0, "property_count_diff": 0, "annotation_count_diff": 0, "iri_drift": False},
            "ci_reproducibility": ci_reproducibility,
            "promotion_state": odk_promotion_status,
            "promotion_gates": [],
        }
        dump_json(output_root / "manifest.json", manifest)
        return manifest

    command_results: list[dict[str, Any]] = []
    if execute and not collect_only:
        command_results = _run_odk_commands(project_root, workbench["root"], profile, source_registry)

    actual_outputs = _collect_actual_odk_outputs(project_root, artifact_dir)
    if actual_outputs["artifacts"]:
        persisted_command_results = command_results or existing_manifest.get("command_results", [])
        imports_report = _build_actual_imports_report(config_dir, workbench["root"])
        robot_summary = _build_actual_robot_summary(actual_outputs, persisted_command_results)
        parity = _build_parity_report(schema_source, artifact_dir / "base.ttl", workbench["edit_file"])
        artifacts = actual_outputs["artifacts"]
        if actual_outputs.get("robot_report_source") and Path(actual_outputs["robot_report_source"]).exists():
            shutil.copyfile(Path(actual_outputs["robot_report_source"]), report_dir / "robot_report.tsv")
        else:
            write_text(report_dir / "robot_report.tsv", _robot_report_tsv(robot_summary))
        write_text(report_dir / "robot_report.md", _robot_report_md(robot_summary))
        dump_json(report_dir / "imports_report.json", imports_report)
        dump_json(report_dir / "parity_report.json", parity)
        write_text(report_dir / "parity_report.md", _parity_report_md(parity))
        manifest = {
            "enabled": True,
            "mode": "shadow",
            "status": "enabled",
            "execution_mode": "actual",
            "authority": "AIMWORKS pipeline",
            "current_role": "ODK shadow-mode release/QC backend",
            "last_built": now_iso(),
            "reasoner": "ELK",
            "primary_artifact": "base",
            "odk_version": _extract_odk_version(persisted_command_results) if persisted_command_results else existing_manifest.get("odk_version", "unknown"),
            "workbench": {
                "root": str(workbench["root"]),
                "edit_file": str(workbench["edit_file"]),
                "config_file": str(workbench["config_file"]),
            },
            "cache_refresh": cache_refresh,
            "command_results": persisted_command_results,
            "artifacts": artifacts,
            "imports": imports_report["imports"],
            "robot_summary": robot_summary,
            "parity": parity,
            "ci_reproducibility": ci_reproducibility,
            "promotion_state": odk_promotion_status,
            "promotion_gates": _promotion_gates(imports_report, parity, ci_reproducibility, odk_promotion_status),
        }
        dump_json(output_root / "manifest.json", manifest)
        return manifest

    artifact_specs = [
        {
            "name": "base",
            "title": "Base ontology",
            "description": "Primary ODK machine artefact for downstream ontology reuse without import closure.",
            "source": schema_source,
            "formats": ("owl", "ttl", "json-ld"),
        },
        {
            "name": "full",
            "title": "Full ontology",
            "description": "Companion ODK artefact representing the broader asserted or inferred release surface for validation and distribution.",
            "source": full_source,
            "formats": ("owl",),
        },
        {
            "name": "simple",
            "title": "Simple ontology",
            "description": "Companion ODK artefact optimized as a simplified machine release for tooling that prefers a smaller asserted view.",
            "source": simple_source,
            "formats": ("owl",),
        },
    ]

    artifacts: list[dict[str, Any]] = []
    for spec in artifact_specs:
        artifacts.append(_materialize_artifact(spec, artifact_dir))

    imports_report = _build_imports_report(config_dir)
    robot_summary = _build_robot_summary(artifacts)
    parity = _build_parity_report(schema_source, artifact_dir / "base.ttl", workbench["edit_file"])

    dump_json(report_dir / "imports_report.json", imports_report)
    write_text(report_dir / "robot_report.tsv", _robot_report_tsv(robot_summary))
    write_text(report_dir / "robot_report.md", _robot_report_md(robot_summary))
    dump_json(report_dir / "parity_report.json", parity)
    write_text(report_dir / "parity_report.md", _parity_report_md(parity))

    manifest = {
        "enabled": True,
        "mode": "shadow",
        "status": "enabled",
        "execution_mode": "bridge",
        "authority": "AIMWORKS pipeline",
        "current_role": "ODK shadow-mode release/QC backend",
        "last_built": now_iso(),
        "reasoner": "ELK",
        "primary_artifact": "base",
        "odk_version": "shadow scaffold",
        "workbench": {
            "root": str(workbench["root"]),
            "edit_file": str(workbench["edit_file"]),
            "config_file": str(workbench["config_file"]),
        },
        "cache_refresh": cache_refresh,
        "command_results": command_results,
        "artifacts": artifacts,
        "imports": imports_report["imports"],
        "robot_summary": robot_summary,
        "parity": parity,
        "ci_reproducibility": ci_reproducibility,
        "promotion_state": odk_promotion_status,
        "promotion_gates": _promotion_gates(imports_report, parity, ci_reproducibility, odk_promotion_status),
    }
    dump_json(output_root / "manifest.json", manifest)
    return manifest


def load_odk_manifest(output_root: str | Path) -> dict[str, Any]:
    manifest_path = Path(output_root) / "odk" / "manifest.json"
    if manifest_path.exists():
        return json.loads(read_text(manifest_path))
    return {
        "enabled": False,
        "mode": "shadow",
        "status": "not-built",
        "authority": "AIMWORKS pipeline",
        "current_role": "ODK shadow-mode release/QC backend",
        "last_built": "",
        "reasoner": "ELK",
        "primary_artifact": "base",
        "odk_version": "not built",
        "artifacts": [],
        "imports": [],
        "robot_summary": {
            "status": "watch",
            "errors": 0,
            "warnings": 1,
            "profile_violations": 0,
            "reasoning_status": "not built",
            "detail": "ODK shadow outputs have not been generated yet.",
        },
        "promotion_state": "shadow",
        "parity": {
            "status": "under review",
            "message": "ODK parity has not been computed yet.",
            "class_count_diff": 0,
            "property_count_diff": 0,
            "annotation_count_diff": 0,
            "iri_drift": False,
        },
        "ci_reproducibility": {
            "status": "watch",
            "message": "CI reproducibility evidence has not been evaluated yet.",
            "workflows_checked": [],
            "required_steps": [],
            "missing_workflows": [],
            "missing_steps": {},
        },
        "promotion_gates": [],
    }


def _ensure_odk_workbench(project_root: Path, profile: dict[str, Any], source_registry: dict[str, Any]) -> dict[str, Path]:
    ontology_root = ensure_dir(project_root / "odk" / "src" / "ontology")
    imports_dir = ensure_dir(ontology_root / "imports")
    ensure_dir(ontology_root / "components")
    run_bat = ontology_root / "run.bat"
    run_sh = ontology_root / "run.sh"
    config_file = ontology_root / "h2kg-odk.yaml"
    edit_file = ontology_root / "h2kg-edit.owl"
    catalog = ontology_root / "catalog-v001.xml"

    write_text(config_file, _odk_yaml(profile, source_registry))
    write_text(run_bat, _run_bat())
    write_text(run_sh, _run_sh())
    write_text(catalog, _catalog_xml())
    write_text(ontology_root / "h2kg.Makefile", _custom_makefile(source_registry))
    _write_merged_edit_file(project_root, edit_file, profile)
    _write_import_term_files(project_root, imports_dir, source_registry)
    return {"root": ontology_root, "config_file": config_file, "edit_file": edit_file}


def _write_merged_edit_file(project_root: Path, target: Path, profile: dict[str, Any]) -> None:
    if Graph is None:
        write_text(target, _minimal_edit_file(profile))
        return
    try:
        graph = Graph()
        ontology_iri = str(profile.get("project", {}).get("ontology_iri", "https://w3id.org/h2kg/hydrogen-ontology"))
        sources = [
            project_root / "output" / "ontology" / "schema.ttl",
            project_root / "output" / "ontology" / "controlled_vocabulary.ttl",
            project_root / "ontology" / "schema.ttl",
            project_root / "ontology" / "controlled_vocabulary.ttl",
        ]
        parsed_any = False
        for seed_source in sources:
            if not seed_source.exists():
                continue
            parsed_any = True
            if seed_source.suffix.lower() in {".ttl", ".turtle"}:
                graph.parse(seed_source, format="turtle")
            elif seed_source.suffix.lower() == ".jsonld":
                graph.parse(seed_source, format="json-ld")
            else:
                graph.parse(seed_source)
        if not parsed_any:
            write_text(target, _minimal_edit_file(profile))
            return
        # ODK manages external imports itself. Keep the merged local seed,
        # but remove asserted import declarations so update_repo does not
        # attempt to resolve upstream ontologies before import modules exist.
        ontology_subject = URIRef(ontology_iri) if URIRef is not None else None
        if ontology_subject is not None and OWL is not None:
            for imported in list(graph.objects(ontology_subject, OWL.imports)):
                graph.remove((ontology_subject, OWL.imports, imported))
        graph.serialize(target, format="xml")
    except Exception:
        write_text(target, _minimal_edit_file(profile))


def _write_import_term_files(project_root: Path, imports_dir: Path, source_registry: dict[str, Any]) -> None:
    ensure_dir(imports_dir)
    enabled_sources = _enabled_odk_sources(source_registry)
    source_index = {str(entry.get("id", "")).strip(): entry for entry in enabled_sources if str(entry.get("id", "")).strip()}
    grouped: dict[str, set[str]] = {source_id: set() for source_id in source_index}
    review_csv = project_root / "output" / "review" / "mapping_review.csv"
    if review_csv.exists():
        with review_csv.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                source_id = str(row.get("source", "") or "").strip()
                target_iri = str(row.get("target_iri", "") or "").strip()
                if not source_id or not target_iri or source_id not in source_index:
                    continue
                if not _target_belongs_to_source(target_iri, source_index[source_id]):
                    continue
                grouped[source_id].add(target_iri)
    for source_id, terms in _collect_source_graph_terms(project_root, source_index).items():
        grouped.setdefault(source_id, set()).update(terms)
    for source_id in source_index:
        target_path = imports_dir / f"{source_id}_terms.txt"
        lines = sorted(grouped[source_id])
        with target_path.open("w", encoding="utf-8", newline="\n") as handle:
            if lines:
                handle.write("\n".join(lines) + "\n")


def _collect_source_graph_terms(project_root: Path, source_index: dict[str, dict[str, Any]]) -> dict[str, set[str]]:
    if Graph is None or URIRef is None or not source_index:
        return {}
    input_candidates = (
        project_root / "input" / "current_ontology.jsonld",
        project_root / "output" / "ontology" / "inferred.ttl",
        project_root / "output" / "ontology" / "schema.ttl",
    )
    source_path = next((path for path in input_candidates if path.exists()), None)
    if source_path is None:
        return {}
    graph = Graph()
    try:
        if source_path.suffix.lower() == ".jsonld":
            graph.parse(source_path, format="json-ld")
        elif source_path.suffix.lower() in {".ttl", ".turtle"}:
            graph.parse(source_path, format="turtle")
        else:
            graph.parse(source_path)
    except Exception:
        return {}
    grouped: dict[str, set[str]] = {source_id: set() for source_id in source_index}
    for triple in graph:
        for node in triple:
            if not isinstance(node, URIRef):
                continue
            source_id = _best_matching_source_id(str(node), source_index)
            if source_id:
                grouped[source_id].add(str(node))
    return grouped


def _best_matching_source_id(target_iri: str, source_index: dict[str, dict[str, Any]]) -> str:
    best_source_id = ""
    best_length = -1
    for source_id, source_entry in source_index.items():
        for prefix in _source_prefixes(source_entry):
            if target_iri.startswith(prefix) and len(prefix) > best_length:
                best_source_id = source_id
                best_length = len(prefix)
    return best_source_id


def _target_belongs_to_source(target_iri: str, source_entry: dict[str, Any]) -> bool:
    prefixes = _source_prefixes(source_entry)
    return any(target_iri.startswith(prefix) for prefix in prefixes)


def _source_prefixes(source_entry: dict[str, Any]) -> tuple[str, ...]:
    source_id = str(source_entry.get("id", "") or "").strip()
    candidates = [
        str(source_entry.get("source_iri", "") or "").strip(),
        str(source_entry.get("remote_url", "") or "").strip(),
        str(SOURCE_URLS.get(source_id, "") or "").strip(),
    ]
    normalized: list[str] = []
    for candidate in candidates:
        if not candidate:
            continue
        normalized.append(candidate)
        if "#" not in candidate and not candidate.endswith(("/", "#")):
            normalized.append(candidate + "#")
            normalized.append(candidate + "/")
    if source_id == "hdo":
        normalized.extend(
            [
                "https://purls.helmholtz-metadaten.de/hob/",
                "https://purls.helmholtz-metadaten.de/hob/hdo.owl#",
            ]
        )
    if source_id == "chebi":
        normalized.extend(
            [
                "http://purl.obolibrary.org/obo/CHEBI_",
                "https://purl.obolibrary.org/obo/CHEBI_",
            ]
        )
    return tuple(dict.fromkeys(prefix for prefix in normalized if prefix))


def _materialize_artifact(spec: dict[str, Any], artifact_dir: Path) -> dict[str, Any]:
    source = Path(spec["source"])
    entry = {
        "name": spec["name"],
        "title": spec["title"],
        "description": spec["description"],
        "generated_at": now_iso(),
        "status": "good" if source.exists() else "watch",
        "formats": [],
    }
    for fmt in spec["formats"]:
        output_path = artifact_dir / f"{spec['name']}{_extension_for_format(fmt)}"
        if source.exists():
            _write_artifact_variant(source, output_path, fmt)
            size_bytes = output_path.stat().st_size if output_path.exists() else 0
            entry["formats"].append(
                {
                    "format": fmt,
                    "path": str(output_path),
                    "filename": output_path.name,
                    "size_bytes": size_bytes,
                }
            )
        else:
            entry["formats"].append(
                {
                    "format": fmt,
                    "path": str(output_path),
                    "filename": output_path.name,
                    "size_bytes": 0,
                }
            )
    entry["size_bytes"] = sum(item["size_bytes"] for item in entry["formats"])
    return entry


def _write_artifact_variant(source: Path, output_path: Path, fmt: str) -> None:
    ensure_dir(output_path.parent)
    if fmt == "ttl" and source.suffix.lower() in {".ttl", ".turtle"}:
        shutil.copyfile(source, output_path)
        return
    if Graph is None:
        shutil.copyfile(source, output_path)
        return
    graph = Graph()
    if source.suffix.lower() in {".ttl", ".turtle"}:
        graph.parse(source, format="turtle")
    elif source.suffix.lower() == ".jsonld":
        graph.parse(source, format="json-ld")
    elif source.suffix.lower() == ".owl":
        graph.parse(source)
    else:
        graph.parse(source)
    serialize_format = "json-ld" if fmt == "json-ld" else "xml" if fmt == "owl" else fmt
    graph.serialize(output_path, format=serialize_format)


def _build_imports_report(config_dir: Path) -> dict[str, Any]:
    registry = try_load_yaml(config_dir / "source_ontologies.yaml", default_source_registry())
    imports: list[dict[str, Any]] = []
    required_failed = 0
    enabled_count = 0
    for source in registry.get("sources", []):
        if not isinstance(source, dict):
            continue
        source_id = str(source.get("id", "")).strip()
        enabled = bool(source.get("enabled", False))
        required = bool(source.get("required", False))
        status = "configured" if enabled else "optional-disabled"
        if enabled:
            enabled_count += 1
        if required and not enabled:
            required_failed += 1
            status = "required-disabled"
        imports.append(
            {
                "id": source_id,
                "title": source.get("title", source_id),
                "required": required,
                "enabled": enabled,
                "status": status,
                "source_iri": SOURCE_URLS.get(source_id, ""),
                "local_cache": f"ontology_release/odk/src/ontology/imports/{source_id}.owl",
                "product_id": source_id,
                "included_in_release": enabled,
                "last_refresh_status": "configured (shadow mode)" if enabled else "not included",
                "semantic_role": "data/metadata/digital-object/process-management anchor" if source_id == "hdo" else "",
            }
        )
    return {
        "summary": {
            "enabled": enabled_count,
            "required_failed": required_failed,
            "optional_disabled": sum(1 for item in imports if item["status"] == "optional-disabled"),
        },
        "imports": imports,
    }


def _build_actual_imports_report(config_dir: Path, workbench_root: Path) -> dict[str, Any]:
    report = _build_imports_report(config_dir)
    imports_dir = workbench_root / "imports"
    required_failed = 0
    for item in report["imports"]:
        source_id = str(item["id"])
        candidates = [
            imports_dir / f"{source_id}_import.owl",
            imports_dir / f"{source_id}.owl",
            imports_dir / f"{source_id}.ttl",
        ]
        import_file = next((path for path in candidates if path.exists()), None)
        terms_file = imports_dir / f"{source_id}_terms.txt"
        if import_file:
            item["local_cache"] = str(import_file)
            item["included_in_release"] = True
            term_count = 0
            if terms_file.exists():
                term_count = sum(1 for line in terms_file.read_text(encoding="utf-8").splitlines() if line.strip())
            if term_count == 0 and not item["required"]:
                item["status"] = "optional-unused-after-refresh"
                item["included_in_release"] = False
                item["last_refresh_status"] = f"no selected terms at {import_file.stat().st_mtime}"
                continue
            if _is_placeholder_import_artifact(import_file, terms_file):
                item["status"] = "placeholder-after-refresh"
                item["last_refresh_status"] = f"placeholder refresh output at {import_file.stat().st_mtime}"
                if item["required"]:
                    required_failed += 1
            else:
                item["last_refresh_status"] = f"actual refresh at {import_file.stat().st_mtime}"
                item["status"] = "configured"
        elif item["required"]:
            item["status"] = "required-missing-after-refresh"
            required_failed += 1
    report["summary"]["required_failed"] = required_failed
    return report


def _is_placeholder_import_artifact(import_file: Path, terms_file: Path) -> bool:
    if not import_file.exists():
        return True
    term_count = 0
    if terms_file.exists():
        term_count = sum(1 for line in terms_file.read_text(encoding="utf-8").splitlines() if line.strip())
    if term_count == 0:
        return True
    size_bytes = import_file.stat().st_size
    if size_bytes > 2048:
        return False
    text = read_text(import_file)
    semantic_markers = (
        "AnnotationProperty",
        "ObjectProperty",
        "DatatypeProperty",
        "owl:Class",
        "Class(",
        "NamedIndividual",
        "rdf:Description",
    )
    ontology_iri = f"http://purl.obolibrary.org/obo/h2kg/imports/{import_file.stem}"
    if any(marker in text for marker in semantic_markers):
        ontology_mentions = text.count(ontology_iri)
        ontology_decls = text.count("Ontology(") + text.count("<owl:Ontology")
        return ontology_mentions < max(1, ontology_decls)
    return True


def _build_robot_summary(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    missing_formats = sum(1 for artifact in artifacts for fmt in artifact["formats"] if fmt["size_bytes"] == 0)
    warnings = 1 if missing_formats else 1
    status = "watch"
    detail = "ODK shadow scaffold generated machine artefacts. Run the nested ODK workbench to replace this bridge report with ROBOT output."
    if not missing_formats:
        detail = "Shadow artefacts were generated successfully. ROBOT profile and reasoner checks still need an explicit ODK run."
    return {
        "status": status,
        "errors": 0,
        "warnings": warnings,
        "profile_violations": 0,
        "reasoning_status": "pending nested ODK execution",
        "detail": detail,
    }


def _build_actual_robot_summary(actual_outputs: dict[str, Any], command_results: list[dict[str, Any]]) -> dict[str, Any]:
    success = all(item.get("returncode", 1) == 0 for item in command_results) if command_results else True
    warnings = 0 if success else 1
    errors = 0 if success else 1
    return {
        "status": "good" if success else "action",
        "errors": errors,
        "warnings": warnings,
        "profile_violations": 0,
        "reasoning_status": "completed" if success else "failed",
        "detail": "ROBOT/ODK commands completed and actual ODK artefacts were collected." if success else "ODK command execution did not complete successfully.",
    }


def _build_parity_report(current_source: Path, base_artifact: Path, edit_source: Path | None = None) -> dict[str, Any]:
    if Graph is None or not current_source.exists() or not base_artifact.exists():
        return {
            "status": "under review",
            "message": "Parity could not be computed because one of the required RDF sources is missing.",
            "class_count_diff": 0,
            "property_count_diff": 0,
            "annotation_count_diff": 0,
            "iri_drift": False,
            "comparison_target": "unavailable",
            "artifact_incomplete": False,
        }

    current_graph = _parse_graph(current_source)
    base_graph = _parse_graph(base_artifact)

    current_local = _local_resource_sets(current_graph)
    current_subjects = set(current_local["all"])
    base_local_all = _local_resource_sets(base_graph)
    base_local = _resource_sets_for_subjects(base_graph, current_subjects)
    annotation_predicates = {URIRef(RDFS_LABEL), URIRef(RDFS_COMMENT), URIRef(SKOS_DEFINITION)}
    current_annotations = _annotation_count(current_graph, annotation_predicates, current_subjects)
    base_annotations = _annotation_count(base_graph, annotation_predicates, current_subjects)
    comparison_target = "base_artifact"
    artifact_incomplete = False
    missing_in_artifact = sorted(current_local["all"] - base_local["all"])

    effective_local = base_local
    effective_annotations = base_annotations
    if missing_in_artifact and edit_source and edit_source.exists():
        edit_graph = _parse_graph(edit_source)
        edit_local = _resource_sets_for_subjects(edit_graph, current_subjects)
        if current_local["all"].issubset(edit_local["all"]):
            effective_local = edit_local
            effective_annotations = _annotation_count(edit_graph, annotation_predicates, current_subjects)
            comparison_target = "edit_file_fallback"
            artifact_incomplete = True

    iri_drift = current_local["all"] != effective_local["all"]
    class_diff = len(effective_local["classes"]) - len(current_local["classes"])
    property_diff = len(effective_local["properties"]) - len(current_local["properties"])
    annotation_diff = effective_annotations - current_annotations
    aligned = not any([class_diff, property_diff, annotation_diff, iri_drift])
    return {
        "status": "aligned" if aligned else "minor differences under review",
        "message": "ODK base artefact currently matches the curated schema and vocabulary baseline closely enough for shadow-mode review."
        if aligned
        else "ODK base artefact differs slightly from the current curated release and remains in shadow-mode comparison."
        if comparison_target == "base_artifact"
        else "The collected ODK base artefact is structurally incomplete for schema parity, so parity was computed against h2kg-edit.owl while the artefact gap remains flagged for follow-up.",
        "class_count_diff": class_diff,
        "property_count_diff": property_diff,
        "annotation_count_diff": annotation_diff,
        "iri_drift": iri_drift,
        "comparison_target": comparison_target,
        "artifact_incomplete": artifact_incomplete,
        "actual_artifact_local_term_count": len(base_local_all["all"]),
        "actual_artifact_missing_local_count": len(missing_in_artifact),
        "actual_artifact_missing_local_sample": missing_in_artifact[:10],
    }


def _parse_graph(path: Path) -> Graph:
    graph = Graph()
    suffix = path.suffix.lower()
    fmt = "turtle" if suffix in {".ttl", ".turtle"} else "xml" if suffix in {".owl", ".rdf", ".xml"} else None
    graph.parse(path, format=fmt)
    return graph


def _local_resource_sets(graph: Graph) -> dict[str, set[str]]:
    local_classes: set[str] = set()
    local_properties: set[str] = set()
    local_all: set[str] = set()
    for subject, _, obj in graph.triples((None, RDF.type, None)):
        subject_text = str(subject)
        if not _is_local_subject(subject_text):
            continue
        local_all.add(subject_text)
        if obj in {OWL.Class, RDFS.Class}:
            local_classes.add(subject_text)
        if obj in {OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty}:
            local_properties.add(subject_text)
    return {"classes": local_classes, "properties": local_properties, "all": local_all}


def _resource_sets_for_subjects(graph: Graph, subjects: set[str]) -> dict[str, set[str]]:
    local_classes: set[str] = set()
    local_properties: set[str] = set()
    local_all: set[str] = set()
    for subject, _, obj in graph.triples((None, RDF.type, None)):
        subject_text = str(subject)
        if subject_text not in subjects:
            continue
        local_all.add(subject_text)
        if obj in {OWL.Class, RDFS.Class}:
            local_classes.add(subject_text)
        if obj in {OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty}:
            local_properties.add(subject_text)
    return {"classes": local_classes, "properties": local_properties, "all": local_all}


def _annotation_count(graph: Graph, predicates: set[URIRef], subjects: set[str]) -> int:
    return sum(1 for s, p, _ in graph if str(s) in subjects and p in predicates)


def _is_local_subject(iri: str) -> bool:
    return any(iri.startswith(base) for key, base in COMMON_CONTEXT.items() if key.startswith("h2kg"))


def _robot_report_tsv(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "check\tseverity\tmessage",
            f"shadow-mode\t{summary['status']}\t{summary['detail']}",
            f"reasoning\twatch\t{summary['reasoning_status']}",
        ]
    )


def _robot_report_md(summary: dict[str, Any]) -> str:
    return textwrap.dedent(
        f"""\
        # ODK / ROBOT Shadow Report

        - Status: {summary['status']}
        - Errors: {summary['errors']}
        - Warnings: {summary['warnings']}
        - Profile violations: {summary['profile_violations']}
        - Reasoning status: {summary['reasoning_status']}

        {summary['detail']}
        """
    )


def _parity_report_md(parity: dict[str, Any]) -> str:
    return textwrap.dedent(
        f"""\
        # ODK Parity Report

        - Status: {parity['status']}
        - Message: {parity['message']}
        - Class count difference: {parity['class_count_diff']}
        - Property count difference: {parity['property_count_diff']}
        - Annotation count difference: {parity['annotation_count_diff']}
        - IRI drift detected: {'yes' if parity['iri_drift'] else 'no'}
        """
    )


def _run_odk_commands(project_root: Path, workbench_root: Path, profile: dict[str, Any], source_registry: dict[str, Any]) -> list[dict[str, Any]]:
    command_specs = [
        ("update_repo", _command_for_platform(workbench_root, ["update_repo"])),
        ("odkversion", _command_for_platform(workbench_root, ["make", "odkversion"])),
        ("refresh-imports", _command_for_platform(workbench_root, ["make", "refresh-imports"])),
        ("test", _command_for_platform(workbench_root, ["make", "test"])),
        ("prepare_release", _command_for_platform(workbench_root, ["make", "prepare_release"])),
    ]
    results: list[dict[str, Any]] = []
    for label, command in command_specs:
        completed = subprocess.run(command, cwd=workbench_root, capture_output=True, text=True, check=False)
        results.append(
            {
                "label": label,
                "command": command,
                "returncode": completed.returncode,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
            }
        )
        if label == "update_repo" and completed.returncode == 0:
            _ensure_odk_workbench(project_root, profile, source_registry)
        if completed.returncode != 0:
            break
    return results


def _command_for_platform(workbench_root: Path, args: list[str]) -> list[str]:
    if os.name == "nt":
        return ["cmd", "/c", "run.bat", *args]
    return ["sh", "./run.sh", *args]


def _collect_actual_odk_outputs(project_root: Path, artifact_dir: Path) -> dict[str, Any]:
    odk_root = project_root / "odk"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    mapping = {
        "base": {
            "owl": [odk_root / "h2kg-base.owl", odk_root / "h2kg.owl"],
            "ttl": [odk_root / "h2kg-base.ttl", odk_root / "h2kg.ttl"],
            "json-ld": [odk_root / "h2kg-base.json", odk_root / "h2kg.json"],
            "title": "Base ontology",
            "description": "Actual ODK base artefact generated from the nested workbench.",
        },
        "full": {
            "owl": [odk_root / "h2kg-full.owl"],
            "title": "Full ontology",
            "description": "Actual ODK full artefact with import closure or broader release surface.",
        },
        "simple": {
            "owl": [odk_root / "h2kg-simple.owl"],
            "title": "Simple ontology",
            "description": "Actual ODK simple artefact for tooling that prefers a smaller release view.",
        },
    }
    artifacts: list[dict[str, Any]] = []
    for name, spec in mapping.items():
        formats: list[dict[str, Any]] = []
        for fmt, candidates in spec.items():
            if fmt in {"title", "description"}:
                continue
            candidate_list = candidates if isinstance(candidates, list) else [candidates]
            source = next((path for path in candidate_list if path.exists()), None)
            if not source:
                continue
            output_path = artifact_dir / f"{name}{_extension_for_format(fmt)}"
            shutil.copyfile(source, output_path)
            formats.append({"format": fmt, "path": str(output_path), "filename": output_path.name, "size_bytes": output_path.stat().st_size})
        if formats:
            artifacts.append(
                {
                    "name": name,
                    "title": spec["title"],
                    "description": spec["description"],
                    "generated_at": now_iso(),
                    "status": "good",
                    "formats": formats,
                    "size_bytes": sum(item["size_bytes"] for item in formats),
                }
            )
    report_candidates = list((odk_root / "src" / "ontology").rglob("*.tsv")) + list(odk_root.rglob("*.tsv"))
    robot_report_source = next((path for path in report_candidates if "report" in path.name.lower() or "qc" in path.name.lower()), None)
    return {"artifacts": artifacts, "robot_report_source": str(robot_report_source) if robot_report_source else ""}


def _extract_odk_version(command_results: list[dict[str, Any]]) -> str:
    for item in command_results:
        if item.get("label") == "odkversion":
            text = f"{item.get('stdout', '')}\n{item.get('stderr', '')}".strip()
            if not text:
                return "unknown"
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            for marker in ("ODK Image", "ODK Makefile", "ROBOT version"):
                for line in lines:
                    if marker in line:
                        return line
            return lines[-1]
    return "unknown"


def _refresh_hdo_cache(config_dir: Path, project_root: Path) -> dict[str, Any]:
    registry = try_load_yaml(config_dir / "source_ontologies.yaml", default_source_registry())
    hdo = next((entry for entry in registry.get("sources", []) if isinstance(entry, dict) and entry.get("id") == "hdo"), None)
    if not hdo:
        return {"status": "missing-config", "path": "", "detail": "HDO source registry entry not found."}
    local_cache = Path(str(hdo.get("local_cache", "cache/sources/hdo.owl")))
    if not local_cache.is_absolute():
        local_cache = project_root / local_cache
    ensure_dir(local_cache.parent)
    if local_cache.exists():
        return {"status": "cached", "path": str(local_cache), "detail": "Existing HDO cache file retained."}
    remote_url = str(hdo.get("remote_url", "")).strip()
    if not remote_url:
        return {"status": "missing-remote", "path": str(local_cache), "detail": "HDO remote URL is not configured."}
    try:
        response = requests.get(remote_url, timeout=45)
        response.raise_for_status()
        local_cache.write_bytes(response.content)
        return {"status": "downloaded", "path": str(local_cache), "detail": "Fetched HDO cache from the configured remote URL."}
    except Exception as exc:
        return {"status": "unavailable", "path": str(local_cache), "detail": f"Could not refresh HDO cache: {exc}"}


def _promotion_gates(imports_report: dict[str, Any], parity: dict[str, Any], ci_reproducibility: dict[str, Any], promotion_state: str = "shadow") -> list[dict[str, Any]]:
    technically_ready = (
        imports_report["summary"]["required_failed"] == 0
        and parity["status"] == "aligned"
        and not parity["iri_drift"]
        and not parity.get("artifact_incomplete", False)
        and ci_reproducibility.get("status") == "good"
    )
    return [
        {
            "label": "Import stability",
            "status": "good" if imports_report["summary"]["required_failed"] == 0 else "watch",
            "value": "configured" if imports_report["summary"]["required_failed"] == 0 else "follow-up",
            "detail": "Required imports are configured and surfaced through the nested ODK workbench.",
        },
        {
            "label": "Parity accepted",
            "status": "good" if parity["status"] == "aligned" else "watch",
            "value": parity["status"],
            "detail": parity["message"],
        },
        {
            "label": "Collected base artefact completeness",
            "status": "good" if not parity.get("artifact_incomplete", False) else "action",
            "value": "complete" if not parity.get("artifact_incomplete", False) else "incomplete",
            "detail": "The collected ODK base artefact contains the expected local schema terms."
            if not parity.get("artifact_incomplete", False)
            else "The collected ODK base artefact is missing local schema terms; shadow-mode parity is currently being computed against h2kg-edit.owl until the ODK export path is corrected.",
        },
        {
            "label": "Reproducible CI build",
            "status": ci_reproducibility.get("status", "watch"),
            "value": ci_reproducibility.get("status", "watch"),
            "detail": ci_reproducibility.get("message", "Promote only after CI reproduces ODK base/full/simple outputs consistently."),
        },
        {
            "label": "No IRI drift",
            "status": "good" if not parity["iri_drift"] else "action",
            "value": "none" if not parity["iri_drift"] else "detected",
            "detail": "No local H2KG IRI drift was detected between the curated release and the parity comparison target."
            if not parity["iri_drift"]
            else "IRI drift is currently detected between the curated release and the parity comparison target; keep ODK in shadow mode until parity is reviewed.",
        },
        {
            "label": "Promotion readiness",
            "status": "good" if promotion_state == "promoted" and technically_ready else "watch",
            "value": promotion_state,
            "detail": "Shadow mode remains the active governance state. Technical parity can be good while explicit promotion is still pending."
            if promotion_state != "promoted"
            else "ODK promotion has been explicitly approved and the current technical gates are satisfied."
            if technically_ready
            else "Promotion was requested, but one or more technical shadow-mode gates are still not satisfied.",
        },
    ]


def _build_ci_reproducibility_report(project_root: Path) -> dict[str, Any]:
    workflow_dir = project_root.resolve().parent / ".github" / "workflows"
    required_workflows = ("ontology-release.yml", "ontology-pages.yml")
    required_snippets = (
        "python -m aimworks_ontology_release.cli --project-root . odk --input input/current_ontology.jsonld --prepare-only",
        "docker run --rm -e ROBOT_JAVA_ARGS=-Xmx6G -v \"$PWD:/work\" -w /work/odk/src/ontology obolibrary/odkfull update_repo",
        "bash odk/src/ontology/run.sh make odkversion",
        "bash odk/src/ontology/run.sh make refresh-imports",
        "bash odk/src/ontology/run.sh make test",
        "bash odk/src/ontology/run.sh make prepare_release",
        "python -m aimworks_ontology_release.cli --project-root . odk --input input/current_ontology.jsonld --collect-only",
    )
    missing_workflows: list[str] = []
    missing_steps: dict[str, list[str]] = {}
    checked: list[str] = []

    for workflow_name in required_workflows:
        workflow_path = workflow_dir / workflow_name
        if not workflow_path.exists():
            missing_workflows.append(workflow_name)
            continue
        checked.append(str(workflow_path))
        content = read_text(workflow_path)
        missing = [snippet for snippet in required_snippets if snippet not in content]
        if missing:
            missing_steps[workflow_name] = missing

    if missing_workflows:
        return {
            "status": "action",
            "message": "Required GitHub Actions workflow files are missing, so CI reproducibility cannot yet be confirmed.",
            "workflows_checked": checked,
            "required_steps": list(required_snippets),
            "missing_workflows": missing_workflows,
            "missing_steps": missing_steps,
        }
    if missing_steps:
        return {
            "status": "watch",
            "message": "CI workflows exist, but one or more required ODK release steps are missing from the configured GitHub Actions sequence.",
            "workflows_checked": checked,
            "required_steps": list(required_snippets),
            "missing_workflows": [],
            "missing_steps": missing_steps,
        }
    return {
        "status": "good",
        "message": "GitHub Actions workflows include the full ODK prepare, build, collect, and release sequence needed to reproduce the shadow build in CI.",
        "workflows_checked": checked,
        "required_steps": list(required_snippets),
        "missing_workflows": [],
        "missing_steps": {},
    }


def _enabled_odk_sources(source_registry: dict[str, Any]) -> list[dict[str, Any]]:
    enabled: list[dict[str, Any]] = []
    for entry in source_registry.get("sources", []):
        if not isinstance(entry, dict):
            continue
        if not entry.get("enabled", True):
            continue
        enabled.append(entry)
    return enabled


def _effective_remote_url(entry: dict[str, Any]) -> str:
    source_id = str(entry.get("id", "")).strip()
    source_kind = str(entry.get("kind", "")).strip()
    remote_url = str(entry.get("remote_url", "") or "").strip()
    if remote_url:
        return remote_url
    if source_kind == "api_or_export":
        return ""
    return str(SOURCE_URLS.get(source_id, "")).strip()


def _custom_makefile(source_registry: dict[str, Any]) -> str:
    lines = [
        "## Customize Makefile settings for h2kg",
        "##",
        "## This file is generated by the AIMWORKS ontology release pipeline.",
        "## It overrides ODK mirror/import rules for non-OBO sources used by H2KG.",
        "## It also preserves the canonical H2KG w3id namespace in ODK base releases.",
        "",
    ]
    enabled_sources = _enabled_odk_sources(source_registry)
    for entry in enabled_sources:
        source_id = str(entry.get("id", "")).strip()
        if not source_id:
            continue
        var_name = source_id.upper().replace("-", "_")
        local_cache = str(entry.get("local_cache", "") or "").strip()
        remote_url = _effective_remote_url(entry)
        required = bool(entry.get("required", False))
        cache_path = f"../../../{local_cache}" if local_cache else ""
        strip_imports_in_mirror = source_id in {"qudt-units", "qudt-quantitykinds"}
        cache_mirror_command = f"$(ROBOT) convert -i $({var_name}_CACHE) -o $(TMPDIR)/$@.owl;"
        remote_convert_command = f"$(ROBOT) convert -i $(TMPDIR)/{source_id}-download.owl -o $(TMPDIR)/$@.owl"
        if strip_imports_in_mirror:
            cache_mirror_command = (
                f"$(ROBOT) convert -i $({var_name}_CACHE) -o $(TMPDIR)/$@.raw.owl; "
                f"$(ROBOT) remove --input $(TMPDIR)/$@.raw.owl --select imports --trim false --output $(TMPDIR)/$@.owl; "
                f"rm -f $(TMPDIR)/$@.raw.owl;"
            )
            remote_convert_command = (
                f"$(ROBOT) convert -i $(TMPDIR)/{source_id}-download.owl -o $(TMPDIR)/$@.raw.owl && "
                f"$(ROBOT) remove --input $(TMPDIR)/$@.raw.owl --select imports --trim false --output $(TMPDIR)/$@.owl && "
                f"rm -f $(TMPDIR)/$@.raw.owl"
            )
        if source_id in {"dcterms", "vann", "chebi"}:
            declaration_tag = "owl:AnnotationProperty" if source_id in {"dcterms", "vann"} else "owl:Class"
            import_rule_lines = [
                f"$(IMPORTDIR)/{source_id}_import.owl: $(MIRRORDIR)/{source_id}.owl $(IMPORTDIR)/{source_id}_terms.txt $(IMPORTSEED) | all_robot_plugins",
                f"\t@if [ ! -s $(IMPORTDIR)/{source_id}_terms.txt ]; then \\",
                f"\t\techo \"No configured terms for {source_id}; writing placeholder import module.\"; \\",
                f"\t\tprintf '%s\\n' 'Prefix(:=<http://purl.obolibrary.org/obo/h2kg/imports/{source_id}_import.owl>)' 'Prefix(owl:=<http://www.w3.org/2002/07/owl#>)' '' 'Ontology(<http://purl.obolibrary.org/obo/h2kg/imports/{source_id}_import.owl>)' > $(IMPORTDIR)/{source_id}_import.ofn; \\",
                f"\t\t$(ROBOT) convert -i $(IMPORTDIR)/{source_id}_import.ofn -o $(IMPORTDIR)/{source_id}_import.owl; \\",
                f"\t\trm -f $(IMPORTDIR)/{source_id}_import.ofn; \\",
                f"\telse \\",
                f"\t\tprintf '%s\\n' '<?xml version=\"1.0\"?>' '<rdf:RDF xmlns:rdf=\"http://www.w3.org/1999/02/22-rdf-syntax-ns#\" xmlns:owl=\"http://www.w3.org/2002/07/owl#\">' '<owl:Ontology rdf:about=\"http://purl.obolibrary.org/obo/h2kg/imports/{source_id}_import.owl\"/>' > $(IMPORTDIR)/{source_id}_import.owl; \\",
                f"\t\twhile IFS= read -r term; do \\",
                f"\t\t\tterm=$$(printf '%s' \"$$term\" | tr -d '\\r'); \\",
                f"\t\t\tif [ -n \"$$term\" ]; then printf '%s\\n' \"<{declaration_tag} rdf:about=\\\"$$term\\\"/>\" >> $(IMPORTDIR)/{source_id}_import.owl; fi; \\",
                f"\t\tdone < $(IMPORTDIR)/{source_id}_terms.txt; \\",
                f"\t\tprintf '%s\\n' '</rdf:RDF>' >> $(IMPORTDIR)/{source_id}_import.owl; \\",
                f"\tfi",
                "",
            ]
        else:
            import_rule_lines = [
                f"$(IMPORTDIR)/{source_id}_import.owl: $(MIRRORDIR)/{source_id}.owl $(IMPORTDIR)/{source_id}_terms.txt $(IMPORTSEED) | all_robot_plugins",
                f"\t@if [ ! -s $(IMPORTDIR)/{source_id}_terms.txt ]; then \\",
                f"\t\techo \"No configured terms for {source_id}; writing placeholder import module.\"; \\",
                f"\t\tprintf '%s\\n' 'Prefix(:=<http://purl.obolibrary.org/obo/h2kg/imports/{source_id}_import.owl>)' 'Prefix(owl:=<http://www.w3.org/2002/07/owl#>)' '' 'Ontology(<http://purl.obolibrary.org/obo/h2kg/imports/{source_id}_import.owl>)' > $(IMPORTDIR)/{source_id}_import.ofn; \\",
                f"\t\t$(ROBOT) convert -i $(IMPORTDIR)/{source_id}_import.ofn -o $(IMPORTDIR)/{source_id}_import.owl; \\",
                f"\t\trm -f $(IMPORTDIR)/{source_id}_import.ofn; \\",
                f"\telse \\",
                f"\t\t$(ROBOT) annotate --input $< --remove-annotations \\",
                f"\t\t\t odk:normalize --add-source true \\",
                f"\t\t\t extract --term-file $(IMPORTDIR)/{source_id}_terms.txt $(T_IMPORTSEED) \\",
                f"\t\t\t         --force true --copy-ontology-annotations false \\",
                f"\t\t\t         --individuals include \\",
                f"\t\t\t         --method BOT \\",
                f"\t\t\t remove $(foreach p, $(ANNOTATION_PROPERTIES), --term $(p)) \\",
                f"\t\t\t        --term-file $(IMPORTDIR)/{source_id}_terms.txt $(T_IMPORTSEED) \\",
                f"\t\t\t        --select complement --select annotation-properties \\",
                f"\t\t\t annotate --ontology-iri http://purl.obolibrary.org/obo/h2kg/imports/{source_id}_import.owl \\",
                f"\t\t\t odk:normalize --base-iri http://purl.obolibrary.org/obo \\",
                f"\t\t\t               --subset-decls true --synonym-decls true \\",
                f"\t\t\t repair --merge-axiom-annotations true \\",
                f"\t\t\t $(ANNOTATE_CONVERT_FILE); \\",
                f"\tfi",
                "",
            ]
        lines.extend(
            [
                f"{var_name}_CACHE := {cache_path}",
                f"{var_name}_URL := {remote_url}",
                f"{var_name}_REQUIRED := {'true' if required else 'false'}",
                "",
                f".PHONY: mirror-{source_id}",
                f".PRECIOUS: $(MIRRORDIR)/{source_id}.owl",
                f"mirror-{source_id}: | $(TMPDIR)",
                f"\t@if [ ! -s $(IMPORTDIR)/{source_id}_terms.txt ] && [ \"$({var_name}_REQUIRED)\" != \"true\" ]; then \\",
                f"\t\techo \"No configured terms for optional source {source_id}; writing placeholder import mirror.\"; \\",
                f"\t\tprintf '%s\\n' 'Prefix(:=<http://purl.obolibrary.org/obo/h2kg/imports/{source_id}_import.owl>)' 'Prefix(owl:=<http://www.w3.org/2002/07/owl#>)' '' 'Ontology(<http://purl.obolibrary.org/obo/h2kg/imports/{source_id}_import.owl>)' > $(TMPDIR)/$@.ofn; \\",
                f"\t\t$(ROBOT) convert -i $(TMPDIR)/$@.ofn -o $(TMPDIR)/$@.owl; \\",
                f"\telif [ -f $({var_name}_CACHE) ]; then \\",
                f"\t\techo \"Using local cache for {source_id}: $({var_name}_CACHE)\"; \\",
                f"\t\t{cache_mirror_command} \\",
                f"\telif [ -n \"$({var_name}_URL)\" ]; then \\",
                f"\t\techo \"Downloading {source_id} from $({var_name}_URL)\"; \\",
                f"\t\tif curl -L \"$({var_name}_URL)\" -H \"Accept: application/rdf+xml, application/owl+xml;q=0.95, text/turtle;q=0.9, text/plain;q=0.8, text/xml;q=0.8\" --create-dirs -o $(TMPDIR)/{source_id}-download.owl --retry 4 --max-time 200 && {remote_convert_command}; then \\",
                f"\t\t\ttrue; \\",
                f"\t\telse \\",
                f"\t\t\techo \"Remote fetch failed for {source_id}; writing placeholder mirror for shadow-mode continuity.\"; \\",
                f"\t\t\tprintf '%s\\n' 'Prefix(:=<http://purl.obolibrary.org/obo/h2kg/imports/{source_id}_import.owl>)' 'Prefix(owl:=<http://www.w3.org/2002/07/owl#>)' '' 'Ontology(<http://purl.obolibrary.org/obo/h2kg/imports/{source_id}_import.owl>)' > $(TMPDIR)/$@.ofn; \\",
                f"\t\t\t$(ROBOT) convert -i $(TMPDIR)/$@.ofn -o $(TMPDIR)/$@.owl; \\",
                f"\t\tfi; \\",
                f"\telif [ \"$({var_name}_REQUIRED)\" = \"true\" ]; then \\",
                f"\t\techo \"Missing required cache or remote URL for {source_id}; writing placeholder mirror.\"; \\",
                f"\t\tprintf '%s\\n' 'Prefix(:=<http://purl.obolibrary.org/obo/h2kg/imports/{source_id}_import.owl>)' 'Prefix(owl:=<http://www.w3.org/2002/07/owl#>)' '' 'Ontology(<http://purl.obolibrary.org/obo/h2kg/imports/{source_id}_import.owl>)' > $(TMPDIR)/$@.ofn; \\",
                f"\t\t$(ROBOT) convert -i $(TMPDIR)/$@.ofn -o $(TMPDIR)/$@.owl; \\",
                f"\telse \\",
                f"\t\techo \"Skipping optional source {source_id}; writing placeholder import mirror.\"; \\",
                f"\t\tprintf '%s\\n' 'Prefix(:=<http://purl.obolibrary.org/obo/h2kg/imports/{source_id}_import.owl>)' 'Prefix(owl:=<http://www.w3.org/2002/07/owl#>)' '' 'Ontology(<http://purl.obolibrary.org/obo/h2kg/imports/{source_id}_import.owl>)' > $(TMPDIR)/$@.ofn; \\",
                f"\t\t$(ROBOT) convert -i $(TMPDIR)/$@.ofn -o $(TMPDIR)/$@.owl; \\",
                f"\tfi",
                "",
                *import_rule_lines,
            ]
        )
    lines.extend(
        [
            "H2KG_LOCAL_BASE_IRI := https://w3id.org/h2kg/hydrogen-ontology",
            "",
            "# Override the generated ODK base release rule so ROBOT keeps local H2KG axioms",
            "# in the canonical w3id namespace when pruning external axioms.",
            "$(ONT)-base.owl: $(EDIT_PREPROCESSED) $(OTHER_SRC) $(IMPORT_FILES)",
            "\t$(ROBOT_RELEASE_IMPORT_MODE) \\",
            "\treason --reasoner $(REASONER) --equivalent-classes-allowed asserted-only --exclude-tautologies structural --annotate-inferred-axioms false \\",
            "\trelax $(RELAX_OPTIONS) \\",
            "\treduce -r $(REASONER) $(REDUCE_OPTIONS) \\",
            "\tremove --base-iri $(URIBASE)/H2KG --base-iri $(H2KG_LOCAL_BASE_IRI) --base-iri $(H2KG_LOCAL_BASE_IRI)# --axioms external --preserve-structure false --trim false \\",
            "\t$(SHARED_ROBOT_COMMANDS) \\",
            "\tannotate --link-annotation http://purl.org/dc/elements/1.1/type http://purl.obolibrary.org/obo/IAO_8000001 \\",
            "\t\t--ontology-iri $(ONTBASE)/$@ $(ANNOTATE_ONTOLOGY_VERSION) \\",
            "\t\t--output $@.tmp.owl && mv $@.tmp.owl $@",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def _odk_yaml(profile: dict[str, Any], source_registry: dict[str, Any]) -> str:
    project = profile.get("project", {})
    lines = [
        "id: h2kg",
        f'title: "{project.get("title", "H2KG - Ontology for Hydrogen Electrochemical Systems")}"',
        "github_org: ViMiLabs",
        "repo: AIMWORKS",
        "git_main_branch: main",
        "edit_format: owl",
        "primary_release: base",
        "release_artefacts:",
        "  - base",
        "  - full",
        "  - simple",
        "export_formats:",
        "  - owl",
        "  - ttl",
        "  - json",
        "reasoner: ELK",
        "release_use_reasoner: true",
        "workflows: []",
        "ci: []",
        "import_group:",
        "  products:",
    ]
    for entry in _enabled_odk_sources(source_registry):
        source_id = str(entry.get("id", "")).strip()
        if source_id:
            lines.append(f"    - id: {source_id}")
            lines.append("      module_type: external")
    return "\n".join(lines) + "\n"


def _run_bat() -> str:
    return textwrap.dedent(
        """\
        @echo off
        setlocal
        if "%~1"=="" (
          echo Usage: run.bat make ^<target^>
          exit /b 1
        )
        set "SCRIPT_DIR=%~dp0"
        for %%I in ("%SCRIPT_DIR%..\\..\\..") do set "PIPELINE_ROOT=%%~fI"
        docker run --rm -e ROBOT_JAVA_ARGS=-Xmx6G -v "%PIPELINE_ROOT%:/work" -w /work/odk/src/ontology obolibrary/odkfull %*
        """
    )


def _run_sh() -> str:
    return textwrap.dedent(
        """\
        #!/usr/bin/env bash
        set -eu
        if [ "$#" -eq 0 ]; then
          echo "Usage: ./run.sh make <target>"
          exit 1
        fi
        SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
        PIPELINE_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
        exec docker run --rm -e ROBOT_JAVA_ARGS=-Xmx6G -v "$PIPELINE_ROOT:/work" -w /work/odk/src/ontology obolibrary/odkfull "$@"
        """
    )


def _catalog_xml() -> str:
    return textwrap.dedent(
        """\
        <?xml version="1.0" encoding="UTF-8" standalone="no"?>
        <catalog prefer="public" xmlns="urn:oasis:names:tc:entity:xmlns:xml:catalog">
          <rewriteURI uriStartString="https://w3id.org/h2kg/hydrogen-ontology" rewritePrefix="./"/>
        </catalog>
        """
    )


def _minimal_edit_file(profile: dict[str, Any]) -> str:
    project = profile.get("project", {})
    ontology_iri = project.get("ontology_iri", "https://w3id.org/h2kg/hydrogen-ontology")
    title = project.get("title", "H2KG - Ontology for Hydrogen Electrochemical Systems")
    return textwrap.dedent(
        f"""\
        <?xml version="1.0"?>
        <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
                 xmlns:owl="http://www.w3.org/2002/07/owl#"
                 xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
                 xmlns:dcterms="http://purl.org/dc/terms/">
          <owl:Ontology rdf:about="{ontology_iri}">
            <dcterms:title>{title}</dcterms:title>
            <rdfs:comment>Seed edit file for the nested H2KG ODK shadow workbench.</rdfs:comment>
          </owl:Ontology>
        </rdf:RDF>
        """
    )


def _pick_existing(*paths: Path) -> Path:
    for path in paths:
        if path.exists():
            return path
    return paths[0]


def _extension_for_format(fmt: str) -> str:
    return {
        "owl": ".owl",
        "ttl": ".ttl",
        "json-ld": ".json",
    }.get(fmt, f".{fmt}")
