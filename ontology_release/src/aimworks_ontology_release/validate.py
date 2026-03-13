from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDFS, SKOS

from .extract import extract_local_terms
from .inspect import find_ontology_node
from .utils import write_json, write_text


def _run_pyshacl(data_graph: Graph, shapes_dir: Path) -> tuple[bool, list[str]]:
    if importlib.util.find_spec("pyshacl") is None:
        return False, ["pySHACL is not installed; SHACL checks were skipped."]
    from pyshacl import validate as pyshacl_validate

    shapes_graph = Graph()
    for shape_file in shapes_dir.glob("*.ttl"):
        shapes_graph.parse(shape_file, format="turtle")
    conforms, _, report_text = pyshacl_validate(data_graph, shacl_graph=shapes_graph, inference="rdfs", serialize_report_graph=True)
    report_value = report_text.decode("utf-8") if isinstance(report_text, bytes) else str(report_text)
    report_lines = report_value.splitlines()[:20]
    return bool(conforms), report_lines


def _optional_check(status: str, details: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {"status": status, "details": details}
    if extra:
        payload.update(extra)
    return payload


def _run_owl_consistency_check(schema_graph: Graph, controlled_vocabulary_graph: Graph, root: Path) -> dict[str, Any]:
    if importlib.util.find_spec("owlready2") is None:
        return _optional_check("skipped", "owlready2 is not installed; OWL consistency loading and reasoner hooks were skipped.")
    try:
        from owlready2 import World

        cache_dir = root / "cache" / "sources"
        cache_dir.mkdir(parents=True, exist_ok=True)
        target = cache_dir / "owl_consistency_check.ttl"
        combined = Graph()
        for graph in (schema_graph, controlled_vocabulary_graph):
            for prefix, namespace in graph.namespaces():
                combined.bind(prefix, namespace)
            for triple in graph:
                combined.add(triple)
        combined.serialize(destination=str(target), format="turtle")
        world = World()
        world.get_ontology(target.resolve().as_uri()).load()
        return _optional_check(
            "loaded",
            "owlready2 loaded the release graph successfully. Full external reasoner execution is left optional because Java-backed reasoners are not mandatory in the core pipeline.",
            {"engine": "owlready2", "reasoner_executed": False},
        )
    except Exception as exc:
        return _optional_check("warning", f"owlready2 was detected but the release graph could not be loaded for optional consistency checks: {exc}")


def _run_emmo_check() -> dict[str, Any]:
    if importlib.util.find_spec("ontopy") or importlib.util.find_spec("EMMOntoPy"):
        return _optional_check(
            "available",
            "EMMOntoPy-compatible tooling is available in the environment. Dedicated EMMO convention checks are prepared but not enforced by default in the core pipeline.",
        )
    return _optional_check("skipped", "EMMOntoPy is not installed; optional EMMO convention checks were skipped.")


def _run_service_hook(name: str, url: str, enabled: bool) -> dict[str, Any]:
    if not enabled:
        return _optional_check("disabled", f"{name} integration is configured but disabled by default for offline-safe local releases.", {"service_url": url})
    if importlib.util.find_spec("requests") is None:
        return _optional_check("skipped", f"requests is not installed; the optional {name} service hook was skipped.", {"service_url": url})
    try:
        import requests

        response = requests.get(url, timeout=5)
        return _optional_check(
            "reachable" if response.ok else "warning",
            f"{name} service responded with HTTP {response.status_code}.",
            {"service_url": url, "http_status": response.status_code},
        )
    except Exception as exc:
        return _optional_check("warning", f"{name} service hook could not be executed: {exc}", {"service_url": url})


def _resolver_check_rows(namespace_policy: dict[str, Any], release_profile: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    ontology_iri = namespace_policy["ontology_iri"].rstrip("/")
    version = str(release_profile["release"]["version"])
    validation_cfg = release_profile.get("validation", {})
    targets = [
        {"label": "Ontology IRI", "iri": ontology_iri, "local_artifact": root / "output" / "docs" / release_profile["publication"]["reference_page"]},
        {"label": "Source", "iri": f"{ontology_iri}/source", "local_artifact": root / "output" / "publication" / "source" / "ontology.ttl"},
        {"label": "Inferred", "iri": f"{ontology_iri}/inferred", "local_artifact": root / "output" / "publication" / "inferred" / "ontology.ttl"},
        {"label": "Latest", "iri": f"{ontology_iri}/latest", "local_artifact": root / "output" / "publication" / "latest" / "ontology.ttl"},
        {"label": "Context", "iri": f"{ontology_iri}/context", "local_artifact": root / "output" / "publication" / "context" / "context.jsonld"},
        {"label": "Versioned release", "iri": f"{ontology_iri}/{version}", "local_artifact": root / "output" / "publication" / version / "ontology.ttl"},
        {"label": "Versioned inferred", "iri": f"{ontology_iri}/{version}/inferred", "local_artifact": root / "output" / "publication" / version / "inferred.ttl"},
    ]
    enable_network = bool(validation_cfg.get("enable_network_checks", False))
    accept_headers = list(validation_cfg.get("resolver_accept_headers", ["text/html", "text/turtle", "application/ld+json"]))
    requests_available = importlib.util.find_spec("requests") is not None
    rows: list[dict[str, Any]] = []
    for target in targets:
        for accept in accept_headers:
            row = {
                "label": target["label"],
                "iri": target["iri"],
                "accept": accept,
                "local_artifact": str(target["local_artifact"].relative_to(root)),
                "local_artifact_exists": target["local_artifact"].exists(),
                "status": "local_ready" if target["local_artifact"].exists() else "missing_local_artifact",
                "http_status": None,
                "details": "Local publication artifact exists." if target["local_artifact"].exists() else "Expected local publication artifact is missing.",
            }
            if enable_network and requests_available:
                try:
                    import requests

                    response = requests.get(target["iri"], headers={"Accept": accept}, timeout=5, allow_redirects=True)
                    row["http_status"] = response.status_code
                    row["status"] = "reachable" if response.ok else "warning"
                    row["details"] = f"Resolver check returned HTTP {response.status_code}."
                except Exception as exc:
                    row["status"] = "warning"
                    row["details"] = f"Resolver check failed: {exc}"
            elif enable_network and not requests_available:
                row["status"] = "skipped"
                row["details"] = "Network resolver checks requested, but requests is not installed."
            else:
                row["details"] += " Network resolver check was not executed because enable_network_checks is false."
            rows.append(row)
    return rows


def validate_release(
    schema_graph: Graph,
    controlled_vocabulary_graph: Graph,
    alignments_graph: Graph,
    classifications: dict[str, Any],
    namespace_policy: dict[str, Any],
    release_profile: dict[str, Any],
    root: Path,
) -> dict[str, Any]:
    data_graph = Graph()
    for graph in (schema_graph, controlled_vocabulary_graph):
        for triple in graph:
            data_graph.add(triple)
    ontology_node = find_ontology_node(schema_graph, namespace_policy)
    terms = extract_local_terms(data_graph, namespace_policy, classifications)
    missing_labels = [term.iri for term in terms if not list(data_graph.objects(URIRef(term.iri), RDFS.label))]
    missing_definitions = [term.iri for term in terms if not list(data_graph.objects(URIRef(term.iri), SKOS.definition)) and not list(data_graph.objects(URIRef(term.iri), RDFS.comment))]
    metadata_missing: list[str] = []
    if ontology_node is not None:
        required = [
            URIRef("http://purl.org/dc/terms/title"),
            URIRef("http://purl.org/dc/terms/description"),
            URIRef("http://purl.org/dc/terms/license"),
            OWL.versionIRI,
            OWL.versionInfo,
        ]
        metadata_missing = [str(predicate) for predicate in required if not list(schema_graph.objects(ontology_node, predicate))]
    else:
        metadata_missing = ["owl:Ontology header"]

    mapping_issues: list[str] = []
    for subject, predicate, _ in alignments_graph:
        if str(predicate) in {str(OWL.equivalentClass), str(RDFS.subClassOf)}:
            record = classifications.get(str(subject))
            if record and record.term_type != "class":
                mapping_issues.append(f"{subject} uses class mapping relation but is typed as {record.term_type}.")
        if str(predicate) in {str(OWL.equivalentProperty), str(RDFS.subPropertyOf)}:
            record = classifications.get(str(subject))
            if record and record.term_type not in {"object_property", "datatype_property", "annotation_property"}:
                mapping_issues.append(f"{subject} uses property mapping relation but is typed as {record.term_type}.")

    namespace_violations = [
        term.iri
        for term in terms
        if not term.iri.startswith(namespace_policy["term_namespace"]) and term.iri != namespace_policy["ontology_iri"]
    ]
    shacl_conforms, shacl_lines = _run_pyshacl(data_graph, root / "shapes")
    owl_consistency = _run_owl_consistency_check(schema_graph, controlled_vocabulary_graph, root)
    emmo_checks = _run_emmo_check()
    validation_cfg = release_profile.get("validation", {})
    oops_checks = _run_service_hook("OOPS!", validation_cfg.get("oops_url", "https://oops.linkeddata.es/rest"), bool(validation_cfg.get("enable_oops", False)))
    foops_checks = _run_service_hook("FOOPS!", validation_cfg.get("foops_url", "https://foops.linkeddata.es/FAIR_validator"), bool(validation_cfg.get("enable_foops", False)))
    resolver_checks = _resolver_check_rows(namespace_policy, release_profile, root)
    report = {
        "syntax_ok": True,
        "metadata_missing": metadata_missing,
        "missing_label_count": len(missing_labels),
        "missing_definition_count": len(missing_definitions),
        "mapping_issues": mapping_issues,
        "namespace_violations": namespace_violations,
        "shacl_conforms": shacl_conforms,
        "shacl_summary": shacl_lines,
        "owl_consistency": owl_consistency,
        "emmo_checks": emmo_checks,
        "oops_checks": oops_checks,
        "foops_checks": foops_checks,
        "resolver_checks": resolver_checks,
        "overall_status": "pass" if not metadata_missing and not missing_labels and not mapping_issues and not namespace_violations and shacl_conforms else "warning",
    }
    return report


def write_validation_outputs(report: dict[str, Any], root: Path) -> None:
    write_json(root / "output" / "reports" / "validation_report.json", report)
    lines = [
        "# Validation Report",
        "",
        f"- RDF syntax sanity: **{'pass' if report['syntax_ok'] else 'fail'}**",
        f"- Overall status: **{report['overall_status']}**",
        f"- Missing metadata predicates: **{len(report['metadata_missing'])}**",
        f"- Missing labels: **{report['missing_label_count']}**",
        f"- Missing definitions/comments: **{report['missing_definition_count']}**",
        f"- Mapping issues: **{len(report['mapping_issues'])}**",
        f"- Namespace violations: **{len(report['namespace_violations'])}**",
        f"- SHACL conforms: **{report['shacl_conforms']}**",
        f"- OWL consistency hook: **{report['owl_consistency']['status']}**",
        f"- EMMO convention hook: **{report['emmo_checks']['status']}**",
        f"- OOPS! hook: **{report['oops_checks']['status']}**",
        f"- FOOPS! hook: **{report['foops_checks']['status']}**",
        "",
        "## Details",
        "",
    ]
    if report["metadata_missing"]:
        lines.extend(f"- Missing metadata: {item}" for item in report["metadata_missing"])
    if report["mapping_issues"]:
        lines.extend(f"- Mapping issue: {item}" for item in report["mapping_issues"])
    if report["namespace_violations"]:
        lines.extend(f"- Namespace violation: {item}" for item in report["namespace_violations"])
    if report["shacl_summary"]:
        lines.append("")
        lines.append("## SHACL Summary")
        lines.append("")
        lines.extend(f"- {item}" for item in report["shacl_summary"])
    lines.extend(
        [
            "",
            "## Optional Hooks",
            "",
            f"- OWL consistency: {report['owl_consistency']['details']}",
            f"- EMMO checks: {report['emmo_checks']['details']}",
            f"- OOPS!: {report['oops_checks']['details']}",
            f"- FOOPS!: {report['foops_checks']['details']}",
            "",
            "## Resolver Checks",
            "",
        ]
    )
    for row in report["resolver_checks"]:
        lines.append(f"- {row['label']} [{row['accept']}]: {row['status']} ({row['details']})")
    write_text(root / "output" / "reports" / "validation_report.md", "\n".join(lines) + "\n")
