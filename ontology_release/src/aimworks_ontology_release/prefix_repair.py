from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .utils import canonical_qname, ensure_dir, read_text, write_text


_NAMESPACE_ROW_RE = re.compile(
    r"(<tr>\s*<td><code>)([^<]+)(</code></td>\s*<td>(?:<a [^>]+>)?<code>)([^<]+)(</code>)",
    re.MULTILINE,
)


def repair_doc_prefixes(docs_root: str | Path) -> dict[str, Any]:
    docs_root = Path(docs_root)
    changed_files: list[str] = []

    graph_path = docs_root / "data" / "graph_explorer.json"
    if graph_path.exists() and _repair_graph_json(graph_path):
        changed_files.append(str(graph_path))

    visuals_path = docs_root / "assets" / "visuals.js"
    if visuals_path.exists() and _repair_visuals_js(visuals_path):
        changed_files.append(str(visuals_path))

    reference_path = docs_root / "hydrogen-ontology.html"
    if reference_path.exists() and _repair_reference_html(reference_path):
        changed_files.append(str(reference_path))

    return {
        "docs_root": str(docs_root),
        "changed_files": changed_files,
        "changed_count": len(changed_files),
    }


def _repair_graph_json(path: Path) -> bool:
    data = json.loads(read_text(path))
    changed = False

    for node in data.get("nodes", []):
        iri = str(node.get("iri", ""))
        original_qname = str(node.get("qname", ""))
        new_qname = canonical_qname(iri, original_qname)
        if new_qname and new_qname != original_qname:
            node["qname"] = new_qname
            search_text = str(node.get("search_text", ""))
            if original_qname:
                node["search_text"] = search_text.replace(original_qname, new_qname)
            changed = True

    for link in data.get("links", []):
        predicate = str(link.get("predicate", ""))
        original_value = str(link.get("value", ""))
        new_value = canonical_qname(predicate, original_value)
        if new_value and new_value != original_value:
            link["value"] = new_value
            changed = True

    if changed:
        ensure_dir(path.parent)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return changed


def _repair_visuals_js(path: Path) -> bool:
    content = read_text(path)
    updated = content

    if "const CANONICAL_PREFIXES = [" not in updated:
        marker = '  const MAX_HISTORY = 40;\n'
        insert = """  const MAX_HISTORY = 40;\n\n  const CANONICAL_PREFIXES = [\n    [\"https://w3id.org/h2kg/hydrogen-ontology#\", \"h2kg\"],\n    [\"http://purl.org/holy/ns#\", \"holy\"],\n    [\"https://w3id.org/emmo/domain/electrochemistry#\", \"electrochemistry\"],\n    [\"https://w3id.org/emmo/domain/pemfc#\", \"pemfc\"],\n    [\"https://w3id.org/emmo#\", \"emmo\"],\n    [\"http://qudt.org/schema/qudt/\", \"qudt\"],\n    [\"http://qudt.org/vocab/unit/\", \"unit\"],\n    [\"http://qudt.org/vocab/quantitykind/\", \"quantitykind\"],\n    [\"http://purl.obolibrary.org/obo/CHEBI_\", \"chebi\"],\n    [\"http://openenergy-platform.org/ontology/oeo/\", \"oeo\"],\n  ];\n"""
        updated = updated.replace(marker, insert, 1)

    if "function canonicalQnameFromIri(" not in updated:
        marker = "  function levenshtein(left, right) {\n"
        insert = """  function canonicalQnameFromIri(iri, fallback = \"\") {\n    const value = String(iri || \"\");\n    for (const [base, prefix] of CANONICAL_PREFIXES.slice().sort((left, right) => right[0].length - left[0].length)) {\n      if (value.startsWith(base)) {\n        const local = value.slice(base.length);\n        return local ? `${prefix}:${local}` : `${prefix}:`;\n      }\n    }\n    return /^ns\\d+:/.test(String(fallback || \"\")) ? (fallback || value) : (fallback || value);\n  }\n\n  function nodeQname(node) {\n    return canonicalQnameFromIri(node.iri, node.qname || \"\");\n  }\n\n  function linkLabel(link) {\n    return canonicalQnameFromIri(link.predicate, link.value || \"\");\n  }\n\n"""
        updated = updated.replace(marker, insert + marker, 1)

    updated = updated.replace('"font-family": "Aptos, Gill Sans, Trebuchet MS, sans-serif",', '"font-family": "system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif",')
    updated = updated.replace("    const qname = normalize(node.qname);", "    const qname = normalize(nodeQname(node));")
    updated = updated.replace("          qname: node.qname,", "          qname: nodeQname(node),")
    updated = updated.replace('        label: showEdgeLabels ? link.value : "",', '        label: showEdgeLabels ? linkLabel(link) : "",')
    updated = updated.replace("${escapeHtml(node.localName || node.qname || node.iri)}", "${escapeHtml(node.localName || nodeQname(node) || node.iri)}")
    updated = updated.replace("${escapeHtml(node.localName || node.qname)}", "${escapeHtml(node.localName || nodeQname(node))}")
    updated = updated.replace("      predicate: link.value,", "      predicate: linkLabel(link),")

    if updated != content:
        write_text(path, updated)
        return True
    return False


def _repair_reference_html(path: Path) -> bool:
    content = read_text(path)

    def replace_row(match: re.Match[str]) -> str:
        prefix = match.group(2)
        namespace_uri = match.group(4)
        canonical = canonical_qname(namespace_uri, prefix)
        canonical_prefix = canonical[:-1] if canonical.endswith(":") else prefix
        return f"{match.group(1)}{canonical_prefix}{match.group(3)}{namespace_uri}{match.group(5)}"

    updated = _NAMESPACE_ROW_RE.sub(replace_row, content)
    if updated != content:
        write_text(path, updated)
        return True
    return False
