from __future__ import annotations

import csv
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml
from rdflib import BNode, Graph, Literal, Namespace, URIRef

PROV = Namespace("http://www.w3.org/ns/prov#")
VANN = Namespace("http://purl.org/vocab/vann/")
QUDT = Namespace("http://qudt.org/schema/qudt/")
QK = Namespace("http://qudt.org/vocab/quantitykind/")
UNIT = Namespace("http://qudt.org/vocab/unit/")


def package_root() -> Path:
    return Path(__file__).resolve().parents[2]


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> Path:
    ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8")
    return path


def write_json(path: Path, payload: Any) -> Path:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> Path:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> Path:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
    return path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def as_uri_text(node: URIRef | BNode | Literal | None) -> str:
    if node is None:
        return ""
    return str(node)


def local_name(node: URIRef | BNode | str | None) -> str:
    if node is None:
        return ""
    value = str(node)
    if value.startswith("_:"):
        return value
    if "#" in value:
        return value.rsplit("#", 1)[-1]
    value = value.rstrip("/")
    return value.rsplit("/", 1)[-1]


def namespace_of(uri: str) -> str:
    if "#" in uri:
        return uri.rsplit("#", 1)[0] + "#"
    if "/" in uri:
        return uri.rsplit("/", 1)[0] + "/"
    return uri


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def make_literal(text: str, lang: str = "en") -> Literal:
    return Literal(normalize_space(text), lang=lang)


def is_uri(node: Any) -> bool:
    return isinstance(node, URIRef)


def is_bnode(node: Any) -> bool:
    return isinstance(node, BNode)


def is_local_iri(node: URIRef | BNode | Literal, namespace_policy: dict[str, Any]) -> bool:
    if not isinstance(node, URIRef):
        return False
    ontology_iri = namespace_policy.get("ontology_iri", "")
    term_namespace = namespace_policy.get("term_namespace", "")
    return str(node).startswith(term_namespace) or str(node) == ontology_iri


def configured_paths(root: Path | None = None) -> dict[str, Path]:
    base = root or package_root()
    return {
        "root": base,
        "config": base / "config",
        "input": base / "input",
        "output": base / "output",
        "reports": base / "output" / "reports",
        "review": base / "output" / "review",
        "mappings": base / "output" / "mappings",
        "ontology_output": base / "output" / "ontology",
        "examples_output": base / "output" / "examples",
        "docs_output": base / "output" / "docs",
        "release_bundle": base / "output" / "release_bundle",
        "w3id_output": base / "output" / "w3id",
        "ontology_dir": base / "ontology",
        "templates": base / "templates",
        "shapes": base / "shapes",
        "cache": base / "cache",
    }


def load_configs(root: Path | None = None) -> dict[str, Any]:
    paths = configured_paths(root)
    config_dir = paths["config"]
    namespace_data = load_yaml(config_dir / "namespace_policy.yaml")
    active_profile = namespace_data["profiles"][namespace_data["active_profile"]]
    return {
        "source_ontologies": load_yaml(config_dir / "source_ontologies.yaml"),
        "release_profile": load_yaml(config_dir / "release_profile.yaml"),
        "metadata_defaults": load_yaml(config_dir / "metadata_defaults.yaml"),
        "mapping_rules": load_yaml(config_dir / "mapping_rules.yaml"),
        "namespace_policy": active_profile,
        "namespace_policy_raw": namespace_data,
    }


def copy_file(src: Path, dst: Path) -> Path:
    ensure_dir(dst.parent)
    shutil.copy2(src, dst)
    return dst


def copy_tree(src: Path, dst: Path) -> Path:
    ensure_dir(dst.parent)
    shutil.copytree(src, dst, dirs_exist_ok=True)
    return dst


def gather_bnode_closure(graph: Graph, seeds: Iterable[URIRef | BNode]) -> set[URIRef | BNode]:
    pending = list(seeds)
    seen: set[URIRef | BNode] = set(pending)
    while pending:
        node = pending.pop()
        for _, _, obj in graph.triples((node, None, None)):
            if isinstance(obj, BNode) and obj not in seen:
                seen.add(obj)
                pending.append(obj)
        for subj, _, _ in graph.triples((None, None, node)):
            if isinstance(subj, BNode) and subj not in seen:
                seen.add(subj)
                pending.append(subj)
    return seen
