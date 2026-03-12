from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import requests
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDFS, SKOS

from .classify import ResourceClassification
from .extract import extract_local_terms
from .normalize import humanize_identifier
from .utils import load_yaml, read_csv, write_csv, write_jsonl


def _heuristic_draft(term: Any) -> dict[str, str]:
    label = term.label or humanize_identifier(term.local_name)
    definition = term.definition or f"A local ontology {term.term_type.replace('_', ' ')} representing {label}."
    comment = term.comment or f"Draft editorial description for {label}."
    return {"label": label, "definition": definition, "comment": comment}


def _cache_key(term: Any, model: str) -> str:
    return hashlib.sha256(f"{term.iri}|{term.label}|{model}".encode("utf-8")).hexdigest()


def _call_openai_compatible(term: Any, config: dict[str, Any], cache_dir: Path) -> dict[str, str]:
    cache_file = cache_dir / f"{_cache_key(term, config['model'])}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))
    prompt = (
        "Return JSON with keys label, definition, comment. "
        f"Ontology term: {term.iri}. Label: {term.label}. Type: {term.term_type}. "
        f"Definition: {term.definition}. Comment: {term.comment}."
    )
    payload = {
        "model": config["model"],
        "temperature": config.get("temperature", 0.2),
        "messages": [
            {"role": "system", "content": config.get("system_prompt", "Draft ontology annotations.")},
            {"role": "user", "content": prompt},
        ],
    }
    headers = {
        "Authorization": f"Bearer {__import__('os').environ.get(config.get('api_key_env', 'OPENAI_API_KEY'), '')}",
        "Content-Type": "application/json",
    }
    response = requests.post(
        config["api_base"].rstrip("/") + "/chat/completions",
        headers=headers,
        json=payload,
        timeout=int(config.get("request_timeout_seconds", 60)),
    )
    response.raise_for_status()
    data = response.json()
    text = data["choices"][0]["message"]["content"]
    parsed = json.loads(text)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
    return parsed


def draft_annotations(
    schema_graph: Graph,
    controlled_vocabulary_graph: Graph,
    classifications: dict[str, ResourceClassification],
    namespace_policy: dict[str, Any],
    root: Path,
    llm_config_path: Path | None = None,
    draft_llm: bool = False,
) -> list[dict[str, Any]]:
    combined = Graph()
    for graph in (schema_graph, controlled_vocabulary_graph):
        for triple in graph:
            combined.add(triple)
    terms = extract_local_terms(combined, namespace_policy, classifications)
    config = load_yaml(llm_config_path) if llm_config_path and llm_config_path.exists() else {}
    cache_dir = root / config.get("cache_directory", "cache/llm")
    rows: list[dict[str, Any]] = []
    for term in terms:
        if draft_llm and config.get("enabled"):
            try:
                draft = _call_openai_compatible(term, config, cache_dir)
                source = "llm"
            except Exception:
                draft = _heuristic_draft(term)
                source = "heuristic-fallback"
        else:
            draft = _heuristic_draft(term)
            source = "heuristic"
        rows.append(
            {
                "subject_iri": term.iri,
                "term_type": term.term_type,
                "draft_label": draft["label"],
                "draft_definition": draft["definition"],
                "draft_comment": draft["comment"],
                "draft_source": source,
                "approved": "no",
                "overwrite_existing": "no",
            }
        )
    fieldnames = ["subject_iri", "term_type", "draft_label", "draft_definition", "draft_comment", "draft_source", "approved", "overwrite_existing"]
    write_csv(root / "output" / "review" / "annotation_drafts.csv", rows, fieldnames)
    write_jsonl(root / "output" / "review" / "annotation_drafts.jsonl", rows)
    return rows


def import_approved_rows(review_file: Path, root: Path) -> list[dict[str, str]]:
    rows = [row for row in read_csv(review_file) if row.get("approved", "").lower() in {"yes", "true", "1"}]
    fieldnames = ["subject_iri", "term_type", "draft_label", "draft_definition", "draft_comment", "draft_source", "approved", "overwrite_existing"]
    write_csv(root / "output" / "review" / "annotation_approved.csv", rows, fieldnames)
    return rows


def apply_approved_annotations(
    schema_graph: Graph,
    controlled_vocabulary_graph: Graph,
    approved_rows: list[dict[str, str]],
) -> int:
    applied = 0
    graph_map = {**{str(subject): schema_graph for subject in schema_graph.subjects()}, **{str(subject): controlled_vocabulary_graph for subject in controlled_vocabulary_graph.subjects()}}
    for row in approved_rows:
        subject = URIRef(row["subject_iri"])
        graph = graph_map.get(str(subject), schema_graph)
        overwrite = row.get("overwrite_existing", "").lower() in {"yes", "true", "1"}
        if overwrite or not list(graph.objects(subject, RDFS.label)):
            graph.set((subject, RDFS.label, Literal(row["draft_label"], lang="en")))
        if overwrite or not list(graph.objects(subject, SKOS.definition)):
            graph.set((subject, SKOS.definition, Literal(row["draft_definition"], lang="en")))
        if overwrite or not list(graph.objects(subject, RDFS.comment)):
            graph.set((subject, RDFS.comment, Literal(row["draft_comment"], lang="en")))
        applied += 1
    return applied
