from __future__ import annotations

import argparse
import json
from pathlib import Path

from .docs import build_docs
from .enrich import enrich_ontology
from .fair import compute_fair_readiness
from .inspect import inspect_ontology
from .llm_annotator import draft_annotations
from .mapper import propose_mappings
from .profile_modules import build_profile_modules
from .prefix_repair import repair_doc_prefixes
from .release import run_release
from .split import split_ontology
from .validate import validate_release


def main() -> None:
    parser = argparse.ArgumentParser(description="AIMWORKS ontology release pipeline")
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parents[2]), help="Path to ontology_release root")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ["inspect", "split", "map", "enrich", "profiles", "docs", "validate", "fair", "release"]:
        sub = subparsers.add_parser(command)
        sub.add_argument("--input", required=True)
    annotate = subparsers.add_parser("annotate")
    annotate.add_argument("--input", required=True)
    annotate.add_argument("--draft-llm", action="store_true")
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
    args = parser.parse_args()
    project_root = Path(args.project_root)
    input_path = Path(getattr(args, "input", project_root))
    if hasattr(args, "input") and not input_path.is_absolute():
        input_path = project_root / input_path
    config_dir = project_root / "config"
    output = project_root / "output"
    if args.command == "repair-doc-prefixes":
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
    elif args.command == "annotate":
        result = draft_annotations(input_path, output / "review", args.draft_llm, config_dir / "llm_agent.example.yaml")
    elif args.command == "docs":
        fair_snapshot = compute_fair_readiness(input_path, output / "reports", config_dir)
        result = build_docs(input_path, output / "docs", config_dir, fair_snapshot)
    elif args.command == "validate":
        result = validate_release(input_path, output / "reports", config_dir)
    elif args.command == "fair":
        result = compute_fair_readiness(input_path, output / "reports", config_dir)
    else:
        result = run_release(input_path, project_root, draft_llm=getattr(args, "draft_llm", False))
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
