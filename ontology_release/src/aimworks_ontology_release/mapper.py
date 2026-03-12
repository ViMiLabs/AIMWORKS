from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SKOS

from .candidates import generate_candidates
from .extract import LocalTerm, extract_local_terms
from .index import build_source_index
from .scorer import ScoredCandidate, score_candidate
from .sources import load_source_records
from .utils import PROV, VANN, write_csv, write_text


RELATION_URIS = {
    "owl:equivalentClass": OWL.equivalentClass,
    "owl:equivalentProperty": OWL.equivalentProperty,
    "rdfs:subClassOf": RDFS.subClassOf,
    "rdfs:subPropertyOf": RDFS.subPropertyOf,
    "skos:exactMatch": SKOS.exactMatch,
    "skos:closeMatch": SKOS.closeMatch,
}


def _union_graphs(*graphs: Graph) -> Graph:
    merged = Graph()
    for graph in graphs:
        for prefix, namespace in graph.namespaces():
            merged.bind(prefix, namespace)
        for triple in graph:
            merged.add(triple)
    return merged


def _pick_best(term: LocalTerm, candidate_records: list[Any], rules: dict[str, Any]) -> ScoredCandidate | None:
    scored = [score_candidate(term, record, rules) for record in candidate_records]
    if not scored:
        return None
    scored.sort(key=lambda item: (-item.score, -item.lexical_score, item.record.label))
    best = scored[0]
    if best.score < float(rules.get("thresholds", {}).get("weak_match", 62)):
        return None
    return best


def align_terms(
    schema_graph: Graph,
    controlled_vocabulary_graph: Graph,
    classifications: dict[str, Any],
    source_config: dict[str, Any],
    namespace_policy: dict[str, Any],
    mapping_rules: dict[str, Any],
    root: Path,
) -> tuple[Graph, list[dict[str, Any]], dict[str, Any]]:
    combined = _union_graphs(schema_graph, controlled_vocabulary_graph)
    terms = extract_local_terms(combined, namespace_policy, classifications)
    records, source_notes = load_source_records(source_config, root)
    source_index = build_source_index(records)

    alignments = Graph()
    for prefix, namespace in combined.namespaces():
        alignments.bind(prefix, namespace)
    alignments.bind("skos", SKOS)
    alignments.bind("dcterms", DCTERMS)
    alignments.bind("prov", PROV)
    alignments.bind("vann", VANN)

    alignment_ontology = URIRef(namespace_policy["ontology_iri"] + "/alignments")
    alignments.add((alignment_ontology, RDF.type, OWL.Ontology))
    alignments.add((alignment_ontology, DCTERMS.title, Literal("H2KG alignment module", lang="en")))

    review_rows: list[dict[str, Any]] = []
    relation_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    limit = int(mapping_rules.get("mapping_candidate_limit", 5))

    for term in terms:
        candidate_records = generate_candidates(term, source_index, mapping_rules, limit=limit)
        best = _pick_best(term, candidate_records, mapping_rules)
        if best is None:
            review_rows.append(
                {
                    "local_iri": term.iri,
                    "local_label": term.label,
                    "local_type": term.term_type,
                    "target_iri": "",
                    "target_label": "",
                    "source_id": "",
                    "score": "",
                    "relation": "",
                    "rationale": "No candidate exceeded the weak-match threshold.",
                    "apply_default": "no",
                }
            )
            continue

        relation = RELATION_URIS[best.relation]
        alignments.add((URIRef(term.iri), relation, URIRef(best.record.iri)))
        review_rows.append(
            {
                "local_iri": term.iri,
                "local_label": term.label,
                "local_type": term.term_type,
                "target_iri": best.record.iri,
                "target_label": best.record.label,
                "source_id": best.record.source_id,
                "score": best.score,
                "relation": best.relation,
                "rationale": best.rationale,
                "apply_default": "yes",
            }
        )
        relation_counts[best.relation] += 1
        source_counts[best.record.source_id] += 1

    report = {
        "local_term_count": len(terms),
        "proposed_mappings": sum(1 for row in review_rows if row["target_iri"]),
        "relation_counts": dict(relation_counts),
        "source_counts": dict(source_counts),
        "source_notes": source_notes,
    }
    return alignments, review_rows, report


def write_alignment_outputs(alignments: Graph, review_rows: list[dict[str, Any]], report: dict[str, Any], root: Path) -> None:
    from .io import save_graph

    save_graph(alignments, root / "output" / "mappings" / "alignments.ttl", "turtle")
    fieldnames = ["local_iri", "local_label", "local_type", "target_iri", "target_label", "source_id", "score", "relation", "rationale", "apply_default"]
    write_csv(root / "output" / "review" / "mapping_review.csv", review_rows, fieldnames)

    lines = [
        "# Alignment Report",
        "",
        f"- Local schema or vocabulary terms reviewed: **{report['local_term_count']}**",
        f"- Proposed mappings: **{report['proposed_mappings']}**",
        "",
        "## Mapping Relations",
        "",
    ]
    if report["relation_counts"]:
        lines.extend(f"- {relation}: {count}" for relation, count in sorted(report["relation_counts"].items()))
    else:
        lines.append("- No mappings were proposed.")
    lines.extend(["", "## Sources Used", ""])
    if report["source_counts"]:
        lines.extend(f"- {source}: {count}" for source, count in sorted(report["source_counts"].items()))
    else:
        lines.append("- No sources selected.")
    lines.extend(["", "## Source Notes", ""])
    if report["source_notes"]:
        lines.extend(f"- {note}" for note in report["source_notes"])
    else:
        lines.append("- Built-in seed registries were sufficient for this run.")
    write_text(root / "output" / "reports" / "alignment_report.md", "\n".join(lines) + "\n")
