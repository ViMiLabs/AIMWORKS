from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS

from .battinfo_overlap import analyze_battinfo_overlap, write_battinfo_overlap_outputs
from .docs import build_docs
from .engineering import build_engineering_artifacts
from .enrich import enrich_graphs, write_enrichment_outputs
from .fair import compute_fair_scores, write_fair_reports
from .inspect import inspect_graph, write_inspection_reports
from .io import load_graph, save_graph
from .llm_annotator import apply_approved_annotations, draft_annotations, import_approved_rows
from .mapper import align_terms, write_alignment_outputs
from .publication import build_jsonld_context, build_publication_layout
from .quality import clean_jsonld_payload, write_quality_outputs
from .split import split_graph, write_split_outputs
from .unit_enrichment import enrich_units_from_cleaned_dataset
from .utils import configured_paths, copy_file, copy_tree, load_configs, read_json, write_csv, write_json, write_text
from .validate import validate_release, write_validation_outputs
from .w3id import generate_w3id_artifacts


def _resolve_input(root: Path, input_path: str | Path) -> Path:
    path = Path(input_path)
    return path if path.is_absolute() else root / path


def _write_classification_review(classifications: dict[str, Any], root: Path) -> None:
    rows = [record.to_dict() for record in sorted(classifications.values(), key=lambda item: (item.category, item.iri))]
    write_csv(root / "output" / "review" / "classification_review.csv", rows, ["iri", "category", "term_type", "local", "score", "reasons"])


def _build_imports_graph(namespace_policy: dict[str, Any], source_config: dict[str, Any]) -> Graph:
    graph = Graph()
    ontology_node = URIRef(namespace_policy["ontology_iri"] + "/imports")
    graph.add((ontology_node, RDF.type, OWL.Ontology))
    graph.add((ontology_node, DCTERMS.title, Literal("Hydrogen technology imports module", lang="en")))
    for source_id, cfg in source_config.get("sources", {}).items():
        if cfg.get("enabled") and cfg.get("category") == "primary" and source_id not in {"qudt_units", "qudt_quantitykinds", "chebi"}:
            graph.add((ontology_node, OWL.imports, URIRef(cfg["base_iri"])))
    return graph


def _build_inferred_graph(schema_graph: Graph, alignments_graph: Graph) -> Graph:
    graph = Graph()
    for base in (schema_graph, alignments_graph):
        for prefix, namespace in base.namespaces():
            graph.bind(prefix, namespace)
        for triple in base:
            graph.add(triple)

    def closure(predicate: URIRef) -> list[tuple[URIRef, URIRef]]:
        pairs = {(subj, obj) for subj, _, obj in graph.triples((None, predicate, None)) if isinstance(subj, URIRef) and isinstance(obj, URIRef)}
        changed = True
        while changed:
            changed = False
            new_pairs = set(pairs)
            for left_a, left_b in pairs:
                for right_a, right_b in pairs:
                    if left_b == right_a and (left_a, right_b) not in new_pairs:
                        new_pairs.add((left_a, right_b))
                        changed = True
            pairs = new_pairs
        return list(pairs)

    for subject, obj in closure(RDFS.subClassOf):
        graph.add((subject, RDFS.subClassOf, obj))
    for subject, obj in closure(RDFS.subPropertyOf):
        graph.add((subject, RDFS.subPropertyOf, obj))
    return graph


def _source_version_label(cfg: dict[str, Any]) -> str:
    fetch_cfg = cfg.get("fetch", {})
    url = str(fetch_cfg.get("url") or fetch_cfg.get("path") or "")
    match = re.search(r"(\d+\.\d+(?:\.\d+)*)", url)
    if match:
        return match.group(1)
    if "/master/" in url or url.endswith("/master"):
        return "rolling/master"
    if "/main/" in url or url.endswith("/main"):
        return "rolling/main"
    if fetch_cfg.get("kind") == "configurable":
        return "configurable"
    if url:
        return "unversioned"
    return "unspecified"


def _write_import_catalog(source_config: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_id, cfg in source_config.get("sources", {}).items():
        fetch_cfg = cfg.get("fetch", {})
        rows.append(
            {
                "source_id": source_id,
                "title": cfg.get("title", source_id),
                "category": cfg.get("category", ""),
                "enabled": bool(cfg.get("enabled", False)),
                "optional": bool(cfg.get("optional", False)),
                "priority": cfg.get("priority", ""),
                "base_iri": cfg.get("base_iri", ""),
                "fetch_kind": fetch_cfg.get("kind", ""),
                "fetch_location": fetch_cfg.get("url") or fetch_cfg.get("path") or "",
                "version_label": _source_version_label(cfg),
                "allow_remote": bool(fetch_cfg.get("allow_remote", False)),
            }
        )
    write_json(root / "output" / "reports" / "import_catalog.json", rows)
    lines = ["# Import Catalog", "", "Configured source ontologies and release-time reuse targets.", ""]
    for row in rows:
        lines.extend(
            [
                f"## {row['title']}",
                "",
                f"- Source ID: `{row['source_id']}`",
                f"- Category: `{row['category']}`",
                f"- Enabled: `{row['enabled']}`",
                f"- Optional: `{row['optional']}`",
                f"- Version label: `{row['version_label']}`",
                f"- Base IRI: `{row['base_iri']}`",
                f"- Fetch kind: `{row['fetch_kind']}`",
                f"- Fetch location: `{row['fetch_location']}`",
                "",
            ]
        )
    write_text(root / "output" / "reports" / "import_catalog.md", "\n".join(lines) + "\n")
    return rows


def _write_changelog_report(
    release_profile: dict[str, Any],
    split_report: dict[str, Any],
    enrichment_report: dict[str, Any],
    mapping_review: list[dict[str, Any]],
    validation_report: dict[str, Any],
    fair_scores: dict[str, Any],
    root: Path,
) -> dict[str, Any]:
    version = str(release_profile["release"]["version"])
    release_date = str(release_profile["release"]["release_date"])
    project_title = str(release_profile["project"]["title"])
    mapped_rows = sum(1 for row in mapping_review if row.get("target_iri"))
    entry = {
        "version": version,
        "date": release_date,
        "summary": f"Public-ready {project_title} release baseline.",
        "changes": [
            f"Separated {split_report['schema_subject_count']} schema subjects, {split_report['controlled_vocabulary_subject_count']} controlled vocabulary subjects, and {split_report['example_subject_count']} example or data-like subjects.",
            f"Generated or normalized {enrichment_report['generated_annotations']} annotations and metadata updates for version {version}.",
            f"Published {mapped_rows} mapped review rows across the alignment outputs.",
            f"Validation status is {validation_report['overall_status']} with SHACL conforms set to {validation_report['shacl_conforms']}.",
            f"Overall FAIR readiness score is {fair_scores['overall']} / 100.",
        ],
        "notes": [
            "No prior published ontology version was registered in the current release profile, so this release acts as the initial curated public baseline.",
            "Placeholder definitions and unmapped local vocabulary terms remain explicit editorial follow-up items rather than being hidden.",
        ],
    }
    payload = {"entries": [entry]}
    write_json(root / "output" / "reports" / "changelog_report.json", payload)
    lines = [
        "# Changelog",
        "",
        f"## {entry['version']} ({entry['date']})",
        "",
        entry["summary"],
        "",
        "### Changes",
        "",
    ]
    lines.extend(f"- {item}" for item in entry["changes"])
    lines.extend(["", "### Notes", ""])
    lines.extend(f"- {item}" for item in entry["notes"])
    write_text(root / "output" / "reports" / "changelog_report.md", "\n".join(lines) + "\n")
    return payload


def _mirror_release_artifacts(root: Path) -> None:
    ontology_dir = root / "ontology"
    copy_file(root / "output" / "ontology" / "schema.ttl", ontology_dir / "schema.ttl")
    copy_file(root / "output" / "ontology" / "schema.jsonld", ontology_dir / "schema.jsonld")
    if (root / "output" / "ontology" / "asserted.ttl").exists():
        copy_file(root / "output" / "ontology" / "asserted.ttl", ontology_dir / "asserted.ttl")
    if (root / "output" / "ontology" / "asserted.jsonld").exists():
        copy_file(root / "output" / "ontology" / "asserted.jsonld", ontology_dir / "asserted.jsonld")
    if (root / "output" / "ontology" / "asserted.rdf").exists():
        copy_file(root / "output" / "ontology" / "asserted.rdf", ontology_dir / "asserted.rdf")
    copy_file(root / "output" / "ontology" / "controlled_vocabulary.ttl", ontology_dir / "controlled_vocabulary.ttl")
    if (root / "output" / "ontology" / "context.jsonld").exists():
        copy_file(root / "output" / "ontology" / "context.jsonld", ontology_dir / "context.jsonld")
    if (root / "output" / "ontology" / "catalog-v001.xml").exists():
        copy_file(root / "output" / "ontology" / "catalog-v001.xml", ontology_dir / "catalog-v001.xml")
    if (root / "output" / "ontology" / "modules").exists():
        copy_tree(root / "output" / "ontology" / "modules", ontology_dir / "modules")
    copy_file(root / "output" / "examples" / "examples.ttl", ontology_dir / "examples.ttl")
    copy_file(root / "output" / "ontology" / "imports.ttl", ontology_dir / "imports.ttl")
    copy_file(root / "output" / "ontology" / "inferred.ttl", ontology_dir / "inferred.ttl")
    if (root / "output" / "ontology" / "full_inferred.ttl").exists():
        copy_file(root / "output" / "ontology" / "full_inferred.ttl", ontology_dir / "full_inferred.ttl")
    if (root / "output" / "ontology" / "full_inferred.rdf").exists():
        copy_file(root / "output" / "ontology" / "full_inferred.rdf", ontology_dir / "full_inferred.rdf")


def _build_release_bundle(root: Path, release_profile: dict[str, Any]) -> None:
    bundle_root = root / "output" / "release_bundle"
    bundle_root.mkdir(parents=True, exist_ok=True)
    copy_tree(root / "output" / "ontology", bundle_root / "ontology")
    copy_tree(root / "output" / "examples", bundle_root / "examples")
    copy_tree(root / "output" / "mappings", bundle_root / "mappings")
    copy_tree(root / "output" / "reports", bundle_root / "reports")
    copy_tree(root / "output" / "docs", bundle_root / "docs")
    copy_tree(root / "output" / "publication", bundle_root / "publication")
    copy_tree(root / "output" / "w3id", bundle_root / "w3id")
    copy_file(root / "CITATION.cff", bundle_root / "CITATION.cff")
    copy_file(root / ".zenodo.json", bundle_root / ".zenodo.json")
    copy_file(root / ".nojekyll", bundle_root / ".nojekyll")
    release_notes = f"""# Release Notes

- Title: {release_profile['project']['title']}
- Version: {release_profile['release']['version']}
- Release date: {release_profile['release']['release_date']}
- Scope: FAIR release preparation, metadata enrichment, conservative alignment, validation, static documentation, and w3id publication support.
"""
    write_text(bundle_root / "RELEASE_NOTES.md", release_notes)
    manifest = {
        "title": release_profile["project"]["title"],
        "version": release_profile["release"]["version"],
        "files": [str(path.relative_to(bundle_root)) for path in sorted(bundle_root.rglob("*")) if path.is_file()],
    }
    write_json(bundle_root / "manifest.json", manifest)


def run_pipeline(
    input_path: str | Path,
    root: Path | None = None,
    stage: str = "release",
    draft_llm: bool = False,
    llm_config_path: Path | None = None,
    review_file: Path | None = None,
    apply_approved_file: Path | None = None,
    unit_evidence_dir: str | Path | None = None,
) -> dict[str, Any]:
    root = root or Path(__file__).resolve().parents[2]
    configs = load_configs(root)
    resolved_input = _resolve_input(root, input_path)
    quality_report = {
        "source": str(resolved_input),
        "status": "skipped",
        "duplicate_term_pairs_detected": 0,
        "auto_merged_terms": 0,
        "manual_review_pairs": 0,
        "helper_nodes_merged": 0,
        "reference_rewrites": 0,
        "alt_labels_removed": 0,
        "alt_label_removal_reasons": {},
        "removed_alt_label_examples": [],
        "review_pairs": [],
        "auto_merge_examples": [],
        "suspicious_remaining_alt_labels": [],
        "changed": False,
    }
    battinfo_overlap_report = {"status": "skipped"}
    if resolved_input.suffix.lower() in {".json", ".jsonld"}:
        cleaned_payload, quality_report = clean_jsonld_payload(read_json(resolved_input), source_name=str(resolved_input))
        write_quality_outputs(quality_report, root)
        battinfo_overlap_report = analyze_battinfo_overlap(cleaned_payload, root, source_config=configs["source_ontologies"])
        write_battinfo_overlap_outputs(battinfo_overlap_report, root)
        jsonld_text = json.dumps(cleaned_payload, ensure_ascii=False)
        graph = Graph()
        graph.parse(data=jsonld_text, format="json-ld")
        if stage == "quality":
            return {"quality_report": quality_report, "battinfo_overlap_report": battinfo_overlap_report}
    else:
        graph = load_graph(resolved_input)
        write_quality_outputs(quality_report, root)
        write_battinfo_overlap_outputs(battinfo_overlap_report, root)
        if stage == "quality":
            return {"quality_report": quality_report, "battinfo_overlap_report": battinfo_overlap_report}

    inspection_report, classifications = inspect_graph(graph, configs["namespace_policy"], configs["mapping_rules"])
    write_inspection_reports(inspection_report, root)
    _write_classification_review(classifications, root)
    if stage == "inspect":
        return {"inspection_report": inspection_report, "battinfo_overlap_report": battinfo_overlap_report}

    split_graphs, split_report = split_graph(graph, classifications)
    write_split_outputs(split_graphs, split_report, root)
    if stage == "split":
        return {"inspection_report": inspection_report, "split_report": split_report, "battinfo_overlap_report": battinfo_overlap_report}

    alignments_graph, mapping_review, alignment_report = align_terms(
        split_graphs["schema"],
        split_graphs["controlled_vocabulary"],
        classifications,
        configs["source_ontologies"],
        configs["namespace_policy"],
        configs["mapping_rules"],
        root,
    )
    write_alignment_outputs(alignments_graph, mapping_review, alignment_report, root)
    if stage == "map":
        return {"inspection_report": inspection_report, "alignment_report": alignment_report, "battinfo_overlap_report": battinfo_overlap_report}

    enrichment_report = enrich_graphs(
        split_graphs["schema"],
        split_graphs["controlled_vocabulary"],
        classifications,
        configs["metadata_defaults"],
        configs["release_profile"],
        configs["namespace_policy"],
        root,
    )
    unit_report = enrich_units_from_cleaned_dataset(
        split_graphs["schema"],
        split_graphs["controlled_vocabulary"],
        configs["release_profile"],
        configs["namespace_policy"],
        root,
        evidence_dir=unit_evidence_dir,
    )
    write_enrichment_outputs(split_graphs["schema"], split_graphs["controlled_vocabulary"], enrichment_report, root)
    if stage == "enrich":
        return {
            "inspection_report": inspection_report,
            "alignment_report": alignment_report,
            "metadata_report": enrichment_report,
            "unit_enrichment_report": unit_report,
            "battinfo_overlap_report": battinfo_overlap_report,
        }
    if stage == "units":
        return {
            "inspection_report": inspection_report,
            "alignment_report": alignment_report,
            "metadata_report": enrichment_report,
            "unit_enrichment_report": unit_report,
            "battinfo_overlap_report": battinfo_overlap_report,
        }

    if review_file and stage == "annotate":
        approved_rows = import_approved_rows(review_file, root)
    else:
        draft_annotations(
            split_graphs["schema"],
            split_graphs["controlled_vocabulary"],
            classifications,
            configs["namespace_policy"],
            root,
            llm_config_path=llm_config_path,
            draft_llm=draft_llm,
        )
        approved_rows = []
    if apply_approved_file:
        approved_rows = import_approved_rows(apply_approved_file, root)
        apply_approved_annotations(split_graphs["schema"], split_graphs["controlled_vocabulary"], approved_rows)
        write_enrichment_outputs(split_graphs["schema"], split_graphs["controlled_vocabulary"], enrichment_report, root)
    if stage == "annotate":
        return {
            "inspection_report": inspection_report,
            "alignment_report": alignment_report,
            "metadata_report": enrichment_report,
            "unit_enrichment_report": unit_report,
            "battinfo_overlap_report": battinfo_overlap_report,
        }

    validation_report = validate_release(
        split_graphs["schema"],
        split_graphs["controlled_vocabulary"],
        alignments_graph,
        classifications,
        configs["namespace_policy"],
        configs["release_profile"],
        root,
    )
    write_validation_outputs(validation_report, root)
    if stage == "validate":
        return {
            "inspection_report": inspection_report,
            "validation_report": validation_report,
            "unit_enrichment_report": unit_report,
            "battinfo_overlap_report": battinfo_overlap_report,
        }

    imports_graph = _build_imports_graph(configs["namespace_policy"], configs["source_ontologies"])
    inferred_graph = _build_inferred_graph(split_graphs["schema"], alignments_graph)
    context_payload = build_jsonld_context(split_graphs["schema"], split_graphs["controlled_vocabulary"], configs["namespace_policy"])
    save_graph(imports_graph, root / "output" / "ontology" / "imports.ttl", "turtle")
    save_graph(inferred_graph, root / "output" / "ontology" / "inferred.ttl", "turtle")
    write_json(root / "output" / "ontology" / "context.jsonld", context_payload)
    build_engineering_artifacts(
        split_graphs["schema"],
        split_graphs["controlled_vocabulary"],
        split_graphs["examples"],
        alignments_graph,
        inferred_graph,
        classifications,
        configs["release_profile"],
        configs["namespace_policy"],
        configs["source_ontologies"],
        root,
    )

    generate_w3id_artifacts(configs["namespace_policy"], configs["release_profile"], root)
    _write_import_catalog(configs["source_ontologies"], root)

    provisional_fair = {
        "overall": 0,
        "dimensions": [
            {"acronym": "F", "dimension": "Findable", "score": 0},
            {"acronym": "A", "dimension": "Accessible", "score": 0},
            {"acronym": "I", "dimension": "Interoperable", "score": 0},
            {"acronym": "R", "dimension": "Reusable", "score": 0},
        ],
        "blockers": [],
        "transparency_checks": [],
    }
    build_docs(
        split_graphs["schema"],
        split_graphs["controlled_vocabulary"],
        split_graphs["examples"],
        mapping_review,
        inspection_report,
        validation_report,
        provisional_fair,
        classifications,
        configs["release_profile"],
        configs["namespace_policy"],
        configs["source_ontologies"],
        configs["namespace_policy_raw"],
        root,
    )

    fair_scores = compute_fair_scores(root)
    write_fair_reports(fair_scores, root)
    _write_changelog_report(configs["release_profile"], split_report, enrichment_report, mapping_review, validation_report, fair_scores, root)
    build_docs(
        split_graphs["schema"],
        split_graphs["controlled_vocabulary"],
        split_graphs["examples"],
        mapping_review,
        inspection_report,
        validation_report,
        fair_scores,
        classifications,
        configs["release_profile"],
        configs["namespace_policy"],
        configs["source_ontologies"],
        configs["namespace_policy_raw"],
        root,
    )
    build_publication_layout(root, configs["release_profile"], configs["namespace_policy"], context_payload)
    if stage == "docs":
        return {
            "inspection_report": inspection_report,
            "validation_report": validation_report,
            "fair_scores": fair_scores,
            "unit_enrichment_report": unit_report,
            "battinfo_overlap_report": battinfo_overlap_report,
        }
    if stage == "fair":
        return {"fair_scores": fair_scores, "unit_enrichment_report": unit_report, "battinfo_overlap_report": battinfo_overlap_report}

    _build_release_bundle(root, configs["release_profile"])
    if configs["release_profile"]["release"].get("copy_outputs_to_ontology_directory", True):
        _mirror_release_artifacts(root)
    return {
        "inspection_report": inspection_report,
        "validation_report": validation_report,
        "fair_scores": fair_scores,
        "unit_enrichment_report": unit_report,
        "battinfo_overlap_report": battinfo_overlap_report,
    }
