from __future__ import annotations

import argparse
import json
from pathlib import Path

from .characterization_kg import (
    build_characterization_kg,
    ingest_characterization_workbook,
    write_characterization_manuscript_materials,
)
from .docs import build_docs
from .decode_workflows import apply_decode_alias_curation, build_decode_workflow_release, ingest_decode_graphml_directory
from .decode_manual_overlay import ingest_decode_manual_json
from .decode_ontology import build_decode_ontology_from_release
from .curate_definitions import curate_source_definitions
from .enrich import enrich_ontology
from .fair import compute_fair_readiness
from .inspect import inspect_ontology
from .independent_review import build_independent_review_package, import_independent_reviews
from .itc_pilot import build_itc_pilot_package, integrate_itc_terms
from .llm_annotator import draft_annotations
from .mapper import propose_mappings
from .normalize_source import normalize_source_document
from .odk import prepare_odk_shadow
from .profile_modules import build_profile_modules
from .prefix_repair import repair_doc_prefixes
from .release import run_release
from .split import split_ontology
from .taxonomy import build_taxonomy_release
from .tib_benchmark import build_tib_benchmark_package
from .tib_collections import apply_harmonization_registry, build_collection_benchmark
from .validate import validate_release


def main() -> None:
    parser = argparse.ArgumentParser(description="AIMWORKS ontology release pipeline")
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parents[2]), help="Path to ontology_release root")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ["inspect", "split", "map", "enrich", "profiles", "taxonomy", "docs", "validate", "fair", "release", "odk", "tib-benchmark", "decode-build", "decode-apply-aliases", "itc-integrate", "itc-build", "characterization-build"]:
        sub = subparsers.add_parser(command)
        sub.add_argument("--input", required=True)
        if command == "odk":
            sub.add_argument("--prepare-only", action="store_true")
            sub.add_argument("--collect-only", action="store_true")
            sub.add_argument("--execute", action="store_true")
        if command == "tib-benchmark":
            sub.add_argument("--snapshot", default="input/tib_terminology_snapshot.json")
            sub.add_argument("--refresh", action="store_true", help="Query TIB and replace the dated catalogue snapshot and candidate cache.")
        if command in {"decode-build", "decode-apply-aliases"}:
            sub.add_argument("--snapshot", default="input/decode_workflows_source.json")
            sub.add_argument("--mapping-config", default="config/decode_workflow_mappings.yaml")
        if command == "decode-build":
            sub.add_argument("--manual-overlay", default="input/decode_manual_workflow_overlay.json")
        if command in {"itc-integrate", "itc-build"}:
            sub.add_argument("--review", default="input/itc_curated_interface.json")
        if command == "itc-integrate":
            sub.add_argument("--write-in-place", action="store_true")
        if command == "characterization-build":
            sub.add_argument("--manifest", default="input/characterization_workbook_manifest.json")
            sub.add_argument("--taxonomy-registry", default="output/ontology/taxonomy_registry.json")
            sub.add_argument("--taxonomy-ttl", default="output/ontology/h2kg-v2-taxonomy.ttl")
    characterization_ingest = subparsers.add_parser("characterization-ingest")
    characterization_ingest.add_argument("--workbook", required=True)
    characterization_ingest.add_argument("--manifest", default="input/characterization_workbook_manifest.json")
    characterization_ingest.add_argument("--allow-fingerprint-change", action="store_true")
    characterization_manuscript = subparsers.add_parser("characterization-manuscript")
    characterization_manuscript.add_argument("--kg-output", default="output/characterization_kg")
    characterization_manuscript.add_argument("--local-output", required=True)
    decode_ingest = subparsers.add_parser("decode-ingest")
    decode_ingest.add_argument("--source-dir", required=True)
    decode_ingest.add_argument("--snapshot", default="input/decode_workflows_source.json")
    decode_manual = subparsers.add_parser("decode-ingest-manual")
    decode_manual.add_argument("--source", required=True)
    decode_manual.add_argument("--snapshot", default="input/decode_workflows_source.json")
    decode_manual.add_argument("--overlay", default="input/decode_manual_workflow_overlay.json")
    decode_ontology = subparsers.add_parser("decode-ontology")
    decode_ontology.add_argument("--decode-dir", default="output/decode")
    decode_ontology.add_argument("--config", default="config/decode_ontology.yaml")
    annotate = subparsers.add_parser("annotate")
    annotate.add_argument("--input", required=True)
    annotate.add_argument("--draft-llm", action="store_true")
    curate = subparsers.add_parser("curate-definitions")
    curate.add_argument("--input", required=True)
    curate.add_argument("--write-in-place", action="store_true")
    normalize_source = subparsers.add_parser("normalize-source")
    normalize_source.add_argument("--input", required=True)
    normalize_source.add_argument("--write-in-place", action="store_true")
    run = subparsers.add_parser("run")
    run.add_argument("--input", required=True)
    run.add_argument("--rewrite", action="store_true")
    run.add_argument("--split", action="store_true")
    run.add_argument("--build-docs", action="store_true")
    run.add_argument("--build-release", action="store_true")
    run.add_argument("--fair-check", action="store_true")
    run.add_argument("--draft-llm", action="store_true")
    repair = subparsers.add_parser("repair-doc-prefixes")
    repair.add_argument("--docs-root", required=True)
    tib_collections = subparsers.add_parser("tib-collection-benchmark")
    tib_collections.add_argument("--taxonomy-registry", default="output/ontology/taxonomy_registry.json")
    tib_collections.add_argument("--snapshot", default="input/tib_collection_snapshot.json")
    tib_collections.add_argument("--candidate-cache", default="input/tib_collection_candidate_cache.json")
    tib_collections.add_argument("--existing-mappings", default="output/ontology/external_alignment_registry.json")
    tib_collections.add_argument("--harmonization-registry", default="config/tib_auto_harmonization.json")
    tib_collections.add_argument("--correction-registry", default="config/tib_h2kg_corrections.json")
    tib_collections.add_argument("--collections", default="NFDI4CAT,NFDI4ENERGY,NFDI4ING")
    tib_collections.add_argument("--refresh", action="store_true")
    tib_collections.add_argument(
        "--retry-failures",
        action="store_true",
        help="Retry only failed candidate queries against the frozen catalogue snapshot.",
    )
    tib_harmonize = subparsers.add_parser("tib-harmonize")
    tib_harmonize.add_argument(
        "--benchmark-registry",
        default="output/benchmarks/tib_collections/automatic_harmonization_registry.json",
    )
    tib_harmonize.add_argument("--output-registry", default="config/tib_auto_harmonization.json")
    review_package = subparsers.add_parser("evaluation-review-package")
    review_package.add_argument("--output-root", default="output")
    review_package.add_argument("--itc-registry", default="input/itc_curated_interface.json")
    review_package.add_argument("--package-dir", required=True)
    review_package.add_argument("--baseline-commit", default="")
    review_import = subparsers.add_parser("evaluation-import-review")
    review_import.add_argument("--manifest", required=True)
    review_import.add_argument("--reviewer-one", required=True)
    review_import.add_argument("--reviewer-two", required=True)
    review_import.add_argument("--adjudication")
    review_import.add_argument("--public-output", default="output/evaluation")
    review_import.add_argument("--private-output", required=True)
    args = parser.parse_args()
    project_root = Path(args.project_root)
    input_path = Path(getattr(args, "input", project_root))
    if hasattr(args, "input") and not input_path.is_absolute():
        input_path = project_root / input_path
    config_dir = project_root / "config"
    output = project_root / "output"
    if args.command == "characterization-ingest":
        manifest = Path(args.manifest)
        if not manifest.is_absolute():
            manifest = project_root / manifest
        result = ingest_characterization_workbook(
            args.workbook,
            manifest,
            enforce_fingerprint=not args.allow_fingerprint_change,
        )
    elif args.command == "characterization-manuscript":
        kg_output = Path(args.kg_output)
        local_output = Path(args.local_output)
        if not kg_output.is_absolute():
            kg_output = project_root / kg_output
        if not local_output.is_absolute():
            local_output = project_root / local_output
        result = write_characterization_manuscript_materials(kg_output, local_output)
    elif args.command == "evaluation-review-package":
        output_root = Path(args.output_root)
        itc_registry = Path(args.itc_registry)
        package_dir = Path(args.package_dir)
        if not output_root.is_absolute():
            output_root = project_root / output_root
        if not itc_registry.is_absolute():
            itc_registry = project_root / itc_registry
        if not package_dir.is_absolute():
            package_dir = project_root / package_dir
        result = build_independent_review_package(
            output_root,
            itc_registry,
            package_dir,
            baseline_commit=args.baseline_commit,
        )
    elif args.command == "evaluation-import-review":
        manifest = Path(args.manifest)
        reviewer_one = Path(args.reviewer_one)
        reviewer_two = Path(args.reviewer_two)
        public_output = Path(args.public_output)
        private_output = Path(args.private_output)
        adjudication = Path(args.adjudication) if args.adjudication else None
        for path_name, path_value in (
            ("manifest", manifest),
            ("reviewer_one", reviewer_one),
            ("reviewer_two", reviewer_two),
            ("public_output", public_output),
            ("private_output", private_output),
        ):
            if not path_value.is_absolute():
                resolved = project_root / path_value
                if path_name == "manifest":
                    manifest = resolved
                elif path_name == "reviewer_one":
                    reviewer_one = resolved
                elif path_name == "reviewer_two":
                    reviewer_two = resolved
                elif path_name == "public_output":
                    public_output = resolved
                else:
                    private_output = resolved
        if adjudication is not None and not adjudication.is_absolute():
            adjudication = project_root / adjudication
        result = import_independent_reviews(
            manifest,
            reviewer_one,
            reviewer_two,
            public_output,
            private_output,
            adjudication,
        )
    elif args.command == "tib-collection-benchmark":
        taxonomy_registry = Path(args.taxonomy_registry)
        snapshot = Path(args.snapshot)
        candidate_cache = Path(args.candidate_cache)
        existing_mappings = Path(args.existing_mappings)
        harmonization_registry = Path(args.harmonization_registry)
        correction_registry = Path(args.correction_registry)
        if not taxonomy_registry.is_absolute():
            taxonomy_registry = project_root / taxonomy_registry
        if not snapshot.is_absolute():
            snapshot = project_root / snapshot
        if not candidate_cache.is_absolute():
            candidate_cache = project_root / candidate_cache
        if not existing_mappings.is_absolute():
            existing_mappings = project_root / existing_mappings
        if not harmonization_registry.is_absolute():
            harmonization_registry = project_root / harmonization_registry
        if not correction_registry.is_absolute():
            correction_registry = project_root / correction_registry
        result = build_collection_benchmark(
            taxonomy_registry,
            output,
            snapshot,
            candidate_cache,
            collections=[value.strip() for value in args.collections.split(",") if value.strip()],
            refresh=args.refresh,
            retry_failures=args.retry_failures,
            existing_mapping_path=existing_mappings,
            existing_harmonization_path=harmonization_registry,
            correction_registry_path=correction_registry,
        )
    elif args.command == "tib-harmonize":
        benchmark_registry = Path(args.benchmark_registry)
        output_registry = Path(args.output_registry)
        if not benchmark_registry.is_absolute():
            benchmark_registry = project_root / benchmark_registry
        if not output_registry.is_absolute():
            output_registry = project_root / output_registry
        result = apply_harmonization_registry(benchmark_registry, output_registry)
    elif args.command == "repair-doc-prefixes":
        docs_root = Path(args.docs_root)
        if not docs_root.is_absolute():
            docs_root = project_root / docs_root
        result = repair_doc_prefixes(docs_root)
    elif args.command == "inspect":
        result = inspect_ontology(input_path, output / "reports", config_dir)
    elif args.command == "split":
        result = split_ontology(input_path, output / "ontology", config_dir)
    elif args.command == "map":
        result = propose_mappings(input_path, output / "review", config_dir)
    elif args.command == "enrich":
        result = enrich_ontology(input_path, output / "ontology", config_dir)
    elif args.command == "profiles":
        result = build_profile_modules(input_path, output / "ontology", config_dir)
    elif args.command == "taxonomy":
        result = build_taxonomy_release(input_path, output, config_dir)
    elif args.command == "annotate":
        result = draft_annotations(input_path, output / "review", args.draft_llm, config_dir / "llm_agent.example.yaml")
    elif args.command == "curate-definitions":
        result = curate_source_definitions(input_path, output / "reports", config_dir, write_in_place=args.write_in_place)
    elif args.command == "normalize-source":
        result = normalize_source_document(input_path, output / "reports", write_in_place=args.write_in_place)
    elif args.command == "docs":
        fair_snapshot = compute_fair_readiness(input_path, output / "reports", config_dir)
        result = build_docs(input_path, output / "docs", config_dir, fair_snapshot)
    elif args.command == "validate":
        result = validate_release(input_path, output / "reports", config_dir)
    elif args.command == "fair":
        result = compute_fair_readiness(input_path, output / "reports", config_dir)
    elif args.command == "odk":
        result = prepare_odk_shadow(
            input_path,
            project_root,
            config_dir,
            prepare_only=getattr(args, "prepare_only", False),
            collect_only=getattr(args, "collect_only", False),
            execute=getattr(args, "execute", False),
        )
    elif args.command == "tib-benchmark":
        snapshot = Path(args.snapshot)
        if not snapshot.is_absolute():
            snapshot = project_root / snapshot
        result = build_tib_benchmark_package(input_path, output, snapshot, refresh=args.refresh)
    elif args.command == "decode-ingest":
        snapshot = Path(args.snapshot)
        if not snapshot.is_absolute():
            snapshot = project_root / snapshot
        result = ingest_decode_graphml_directory(args.source_dir, snapshot)
    elif args.command == "decode-ingest-manual":
        snapshot = Path(args.snapshot)
        overlay = Path(args.overlay)
        if not snapshot.is_absolute():
            snapshot = project_root / snapshot
        if not overlay.is_absolute():
            overlay = project_root / overlay
        result = ingest_decode_manual_json(args.source, overlay, snapshot)
    elif args.command == "decode-ontology":
        decode_dir = Path(args.decode_dir)
        ontology_config = Path(args.config)
        if not decode_dir.is_absolute():
            decode_dir = project_root / decode_dir
        if not ontology_config.is_absolute():
            ontology_config = project_root / ontology_config
        result = build_decode_ontology_from_release(decode_dir, ontology_config)
    elif args.command == "decode-build":
        snapshot = Path(args.snapshot)
        mapping_config = Path(args.mapping_config)
        if not snapshot.is_absolute():
            snapshot = project_root / snapshot
        if not mapping_config.is_absolute():
            mapping_config = project_root / mapping_config
        manual_overlay = Path(args.manual_overlay)
        if not manual_overlay.is_absolute():
            manual_overlay = project_root / manual_overlay
        result = build_decode_workflow_release(
            snapshot,
            output,
            mapping_config,
            input_path,
            include_multiscale_interface=True,
            manual_overlay_path=manual_overlay,
        )
    elif args.command == "decode-apply-aliases":
        mapping_config = Path(args.mapping_config)
        if not mapping_config.is_absolute():
            mapping_config = project_root / mapping_config
        result = apply_decode_alias_curation(input_path, mapping_config)
    elif args.command in {"itc-integrate", "itc-build"}:
        review_path = Path(args.review)
        if not review_path.is_absolute():
            review_path = project_root / review_path
        if args.command == "itc-integrate":
            result = integrate_itc_terms(input_path, review_path, write_in_place=args.write_in_place)
        else:
            result = build_itc_pilot_package(input_path, output, review_path)
    elif args.command == "characterization-build":
        manifest = Path(args.manifest)
        taxonomy_registry = Path(args.taxonomy_registry)
        taxonomy_ttl = Path(args.taxonomy_ttl)
        if not manifest.is_absolute():
            manifest = project_root / manifest
        if not taxonomy_registry.is_absolute():
            taxonomy_registry = project_root / taxonomy_registry
        if not taxonomy_ttl.is_absolute():
            taxonomy_ttl = project_root / taxonomy_ttl
        result = build_characterization_kg(
            manifest,
            input_path,
            output,
            taxonomy_registry_path=taxonomy_registry,
            taxonomy_ttl_path=taxonomy_ttl,
        )
    else:
        result = run_release(
            input_path,
            project_root,
            draft_llm=getattr(args, "draft_llm", False),
            rewrite=getattr(args, "rewrite", False),
        )
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
