from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS

from .docs import build_docs
from .enrich import enrich_graphs, write_enrichment_outputs
from .fair import compute_fair_scores, write_fair_reports
from .inspect import inspect_graph, write_inspection_reports
from .io import load_graph, save_graph
from .llm_annotator import apply_approved_annotations, draft_annotations, import_approved_rows
from .mapper import align_terms, write_alignment_outputs
from .publication import build_jsonld_context, build_publication_layout
from .split import split_graph, write_split_outputs
from .utils import configured_paths, copy_file, copy_tree, load_configs, write_csv, write_json, write_text
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
    graph.add((ontology_node, DCTERMS.title, Literal("H2KG imports module", lang="en")))
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


def _mirror_release_artifacts(root: Path) -> None:
    ontology_dir = root / "ontology"
    copy_file(root / "output" / "ontology" / "schema.ttl", ontology_dir / "schema.ttl")
    copy_file(root / "output" / "ontology" / "schema.jsonld", ontology_dir / "schema.jsonld")
    copy_file(root / "output" / "ontology" / "controlled_vocabulary.ttl", ontology_dir / "controlled_vocabulary.ttl")
    if (root / "output" / "ontology" / "context.jsonld").exists():
        copy_file(root / "output" / "ontology" / "context.jsonld", ontology_dir / "context.jsonld")
    copy_file(root / "output" / "examples" / "examples.ttl", ontology_dir / "examples.ttl")
    copy_file(root / "output" / "ontology" / "imports.ttl", ontology_dir / "imports.ttl")
    copy_file(root / "output" / "ontology" / "inferred.ttl", ontology_dir / "inferred.ttl")


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
) -> dict[str, Any]:
    root = root or Path(__file__).resolve().parents[2]
    configs = load_configs(root)
    graph = load_graph(_resolve_input(root, input_path))

    inspection_report, classifications = inspect_graph(graph, configs["namespace_policy"], configs["mapping_rules"])
    write_inspection_reports(inspection_report, root)
    _write_classification_review(classifications, root)
    if stage == "inspect":
        return {"inspection_report": inspection_report}

    split_graphs, split_report = split_graph(graph, classifications)
    write_split_outputs(split_graphs, split_report, root)
    if stage == "split":
        return {"inspection_report": inspection_report, "split_report": split_report}

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
        return {"inspection_report": inspection_report, "alignment_report": alignment_report}

    enrichment_report = enrich_graphs(
        split_graphs["schema"],
        split_graphs["controlled_vocabulary"],
        classifications,
        configs["metadata_defaults"],
        configs["release_profile"],
        configs["namespace_policy"],
        root,
    )
    write_enrichment_outputs(split_graphs["schema"], split_graphs["controlled_vocabulary"], enrichment_report, root)
    if stage == "enrich":
        return {"inspection_report": inspection_report, "alignment_report": alignment_report, "metadata_report": enrichment_report}

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
        return {"inspection_report": inspection_report, "alignment_report": alignment_report, "metadata_report": enrichment_report}

    validation_report = validate_release(
        split_graphs["schema"],
        split_graphs["controlled_vocabulary"],
        alignments_graph,
        classifications,
        configs["namespace_policy"],
        root,
    )
    write_validation_outputs(validation_report, root)
    if stage == "validate":
        return {"inspection_report": inspection_report, "validation_report": validation_report}

    imports_graph = _build_imports_graph(configs["namespace_policy"], configs["source_ontologies"])
    inferred_graph = _build_inferred_graph(split_graphs["schema"], alignments_graph)
    context_payload = build_jsonld_context(split_graphs["schema"], split_graphs["controlled_vocabulary"], configs["namespace_policy"])
    save_graph(imports_graph, root / "output" / "ontology" / "imports.ttl", "turtle")
    save_graph(inferred_graph, root / "output" / "ontology" / "inferred.ttl", "turtle")
    write_json(root / "output" / "ontology" / "context.jsonld", context_payload)

    generate_w3id_artifacts(configs["namespace_policy"], configs["release_profile"], root)

    provisional_fair = {"overall": 0, "dimensions": [{"dimension": "Findable", "score": 0}, {"dimension": "Accessible", "score": 0}, {"dimension": "Interoperable", "score": 0}, {"dimension": "Reusable", "score": 0}], "blockers": []}
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
        root,
    )

    fair_scores = compute_fair_scores(root)
    write_fair_reports(fair_scores, root)
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
        root,
    )
    build_publication_layout(root, configs["release_profile"], configs["namespace_policy"], context_payload)
    if stage == "docs":
        return {"inspection_report": inspection_report, "validation_report": validation_report, "fair_scores": fair_scores}
    if stage == "fair":
        return {"fair_scores": fair_scores}

    _build_release_bundle(root, configs["release_profile"])
    if configs["release_profile"]["release"].get("copy_outputs_to_ontology_directory", True):
        _mirror_release_artifacts(root)
    return {"inspection_report": inspection_report, "validation_report": validation_report, "fair_scores": fair_scores}
