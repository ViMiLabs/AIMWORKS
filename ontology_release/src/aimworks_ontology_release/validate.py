from __future__ import annotations

import importlib.util
from collections import defaultdict
from pathlib import Path
from typing import Any

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS

from .extract import extract_local_terms
from .inspect import find_ontology_node
from .utils import is_local_iri, write_json, write_text


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


def _local_validation_graph(data_graph: Graph, namespace_policy: dict[str, Any]) -> Graph:
    local_graph = Graph()
    for prefix, namespace in data_graph.namespaces():
        local_graph.bind(prefix, namespace)
    for subject, predicate, obj in data_graph:
        if is_local_iri(subject, namespace_policy):
            local_graph.add((subject, predicate, obj))
    return local_graph


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


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_text(data: Any) -> str:
    if isinstance(data, bytes):
        return data.decode("utf-8")
    return str(data)


def _graph_text_objects(graph: Graph, subject: URIRef, predicate_suffix: str) -> list[str]:
    return [str(obj) for predicate, obj in graph.predicate_objects(subject) if str(predicate).endswith(predicate_suffix)]


def _first_graph_text(graph: Graph, subject: URIRef, predicate_suffix: str) -> str:
    values = _graph_text_objects(graph, subject, predicate_suffix)
    return values[0] if values else ""


def _foops_dimension_rows(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    aggregates: dict[str, dict[str, Any]] = defaultdict(lambda: {"passed": 0, "total": 0, "checks": 0, "principles": set()})
    for row in checks:
        category = str(row.get("category_id") or "").strip() or "Unknown"
        passed = _safe_int(row.get("total_passed_tests"), 1 if row.get("status") == "ok" else 0)
        total = _safe_int(row.get("total_tests_run"), 1)
        bucket = aggregates[category]
        bucket["passed"] += max(passed, 0)
        bucket["total"] += max(total, 0)
        bucket["checks"] += 1
        principle = str(row.get("principle_id") or "").strip()
        if principle:
            bucket["principles"].add(principle)
    ordered = [("F", "Findable"), ("A", "Accessible"), ("I", "Interoperable"), ("R", "Reusable")]
    rows: list[dict[str, Any]] = []
    for acronym, dimension in ordered:
        bucket = aggregates.get(dimension)
        if not bucket or bucket["total"] == 0:
            rows.append(
                {
                    "acronym": acronym,
                    "dimension": dimension,
                    "score": None,
                    "passed": 0,
                    "total": 0,
                    "status": "not_assessed",
                    "principles": [],
                }
            )
            continue
        rows.append(
            {
                "acronym": acronym,
                "dimension": dimension,
                "score": round((bucket["passed"] / bucket["total"]) * 100, 1),
                "passed": bucket["passed"],
                "total": bucket["total"],
                "status": "assessed",
                "principles": sorted(bucket["principles"]),
            }
        )
    return rows


def _run_foops_assessment(schema_graph: Graph, release_profile: dict[str, Any], validation_cfg: dict[str, Any]) -> dict[str, Any]:
    homepage_url = validation_cfg.get("foops_url", "https://foops.linkeddata.es/FAIR_validator.html")
    catalogue_url = validation_cfg.get("foops_catalogue_url", "https://w3id.org/foops/catalogue")
    if not validation_cfg.get("enable_foops", False):
        return _optional_check("disabled", "FOOPS! integration is configured but disabled.", {"service_url": homepage_url, "catalogue_url": catalogue_url})
    if importlib.util.find_spec("requests") is None:
        return _optional_check("skipped", "requests is not installed; the FOOPS! assessment was skipped.", {"service_url": homepage_url, "catalogue_url": catalogue_url})

    import requests

    mode = str(validation_cfg.get("foops_mode", "file")).strip().lower() or "file"
    timeout_seconds = _safe_int(validation_cfg.get("foops_timeout_seconds"), 180)
    assess_uri_url = validation_cfg.get("foops_assess_uri_url", "https://foops.linkeddata.es/assessOntology")
    assess_file_url = validation_cfg.get("foops_assess_file_url", "https://foops.linkeddata.es/assessOntologyFile")
    resources_cfg = release_profile.get("documentation", {}).get("resources", {})
    target_uri = str(validation_cfg.get("foops_target_uri") or resources_cfg.get("ontology_homepage_iri") or "").strip()
    request_target = assess_file_url

    try:
        if mode == "uri":
            if not target_uri:
                return _optional_check(
                    "skipped",
                    "FOOPS! URI mode was requested, but no public ontology URI was configured.",
                    {"service_url": homepage_url, "catalogue_url": catalogue_url, "mode": mode},
                )
            request_target = assess_uri_url
            response = requests.post(request_target, json={"ontologyUri": target_uri}, timeout=timeout_seconds)
        else:
            turtle_payload = _as_text(schema_graph.serialize(format="turtle")).encode("utf-8")
            response = requests.post(
                request_target,
                files={"file": ("ontology.ttl", turtle_payload, "text/turtle")},
                timeout=timeout_seconds,
            )
        response.raise_for_status()
        payload = response.json()
        checks = payload.get("checks", [])
        dimension_rows = _foops_dimension_rows(checks if isinstance(checks, list) else [])
        failed_checks = [
            {
                "abbreviation": str(row.get("abbreviation") or ""),
                "category": str(row.get("category_id") or ""),
                "title": str(row.get("title") or ""),
                "status": str(row.get("status") or ""),
                "explanation": str(row.get("explanation") or ""),
            }
            for row in checks
            if str(row.get("status") or "").lower() != "ok"
        ][:12]
        overall_score = round(_safe_float(payload.get("overall_score")) * 100, 1)
        unassessed_dimensions = [row["dimension"] for row in dimension_rows if row["score"] is None]
        details = f"FOOPS! assessment completed in {mode} mode with an overall score of {overall_score} / 100."
        if unassessed_dimensions:
            details += f" The following dimensions were not assessed in this mode: {', '.join(unassessed_dimensions)}."
        return _optional_check(
            "assessed",
            details,
            {
                "service_url": homepage_url,
                "service_endpoint": request_target,
                "catalogue_url": catalogue_url,
                "mode": mode,
                "ontology_uri": payload.get("ontology_URI", target_uri),
                "ontology_title": payload.get("ontology_title", ""),
                "ontology_license": payload.get("ontology_license", ""),
                "resource_found": payload.get("resource_found", ""),
                "overall_score": overall_score,
                "dimension_scores": dimension_rows,
                "check_count": len(checks) if isinstance(checks, list) else 0,
                "failed_checks": failed_checks,
            },
        )
    except Exception as exc:
        return _optional_check(
            "warning",
            f"FOOPS! assessment could not be completed: {exc}",
            {
                "service_url": homepage_url,
                "service_endpoint": request_target,
                "catalogue_url": catalogue_url,
                "mode": mode,
            },
        )


def _run_oops_assessment(schema_graph: Graph, validation_cfg: dict[str, Any]) -> dict[str, Any]:
    homepage_url = validation_cfg.get("oops_homepage_url", "https://oops.linkeddata.es/")
    service_url = validation_cfg.get("oops_url", "https://oops.linkeddata.es/rest")
    if not validation_cfg.get("enable_oops", False):
        return _optional_check("disabled", "OOPS! integration is configured but disabled.", {"service_url": homepage_url, "service_endpoint": service_url})
    if importlib.util.find_spec("requests") is None:
        return _optional_check("skipped", "requests is not installed; the OOPS! assessment was skipped.", {"service_url": homepage_url, "service_endpoint": service_url})

    import requests

    try:
        rdf_xml = _as_text(schema_graph.serialize(format="xml")).replace("]]>", "]]]]><![CDATA[>")
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<OOPSRequest>"
            "<OntologyUrl></OntologyUrl>"
            f"<OntologyContent><![CDATA[{rdf_xml}]]></OntologyContent>"
            "<Pitfalls>10</Pitfalls>"
            "<OutputFormat>RDF/XML</OutputFormat>"
            "</OOPSRequest>"
        )
        response = requests.post(
            service_url,
            data=body.encode("utf-8"),
            headers={"Content-Type": "text/xml; charset=UTF-8"},
            timeout=_safe_int(validation_cfg.get("oops_timeout_seconds"), 180),
        )
        response.raise_for_status()
        graph = Graph()
        graph.parse(data=_as_text(response.text), format="xml")
        pitfall_nodes = {subject for subject, obj in graph.subject_objects(RDF.type) if str(obj).endswith("#pitfall")}
        if not pitfall_nodes:
            pitfall_nodes = {subject for subject, predicate, _ in graph if str(predicate).endswith("hasCode")}
        pitfalls: list[dict[str, Any]] = []
        severity_counts: dict[str, int] = defaultdict(int)
        for node in pitfall_nodes:
            code = _first_graph_text(graph, node, "hasCode")
            name = _first_graph_text(graph, node, "hasName")
            importance = _first_graph_text(graph, node, "hasImportanceLevel") or "Unspecified"
            affected = _safe_int(_first_graph_text(graph, node, "hasNumberAffectedElements"))
            description = _first_graph_text(graph, node, "hasDescription")
            severity_counts[importance] += 1
            pitfalls.append(
                {
                    "code": code,
                    "name": name,
                    "importance": importance,
                    "affected_elements": affected,
                    "description": description,
                }
            )
        pitfalls.sort(key=lambda row: (row["code"], row["name"]))
        message_nodes = [subject for subject in graph.subjects() if _graph_text_objects(graph, subject, "hasMessage") or _graph_text_objects(graph, subject, "hasTitle")]
        messages: list[str] = []
        for node in message_nodes:
            title = _first_graph_text(graph, node, "hasTitle")
            detail_lines = _graph_text_objects(graph, node, "hasMessage")
            if title:
                messages.append(title)
            messages.extend(detail_lines)
        details = f"OOPS! assessed the ontology and reported {len(pitfalls)} pitfalls."
        if messages and len(pitfalls) == 0:
            details = " ".join(messages[:2])
        return _optional_check(
            "assessed" if pitfalls or not messages else "warning",
            details,
            {
                "service_url": homepage_url,
                "service_endpoint": service_url,
                "pitfall_count": len(pitfalls),
                "pitfalls": pitfalls[:20],
                "severity_counts": dict(sorted(severity_counts.items())),
                "messages": messages[:6],
            },
        )
    except Exception as exc:
        return _optional_check(
            "warning",
            f"OOPS! assessment could not be completed: {exc}",
            {"service_url": homepage_url, "service_endpoint": service_url},
        )


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
    shacl_conforms, shacl_lines = _run_pyshacl(_local_validation_graph(data_graph, namespace_policy), root / "shapes")
    owl_consistency = _run_owl_consistency_check(schema_graph, controlled_vocabulary_graph, root)
    emmo_checks = _run_emmo_check()
    validation_cfg = release_profile.get("validation", {})
    oops_checks = _run_oops_assessment(schema_graph, validation_cfg)
    foops_checks = _run_foops_assessment(schema_graph, release_profile, validation_cfg)
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
    foops_checks = report["foops_checks"]
    oops_checks = report["oops_checks"]
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
            "## External Service Assessments",
            "",
            f"- OOPS!: {oops_checks['details']}",
            f"- OOPS! link: {oops_checks.get('service_url', '')}",
            f"- FOOPS!: {foops_checks['details']}",
            f"- FOOPS! link: {foops_checks.get('service_url', '')}",
            "",
        ]
    )
    if "pitfall_count" in oops_checks:
        lines.append(f"- OOPS! pitfall count: **{oops_checks['pitfall_count']}**")
        for importance, count in sorted(oops_checks.get("severity_counts", {}).items()):
            lines.append(f"- OOPS! {importance}: {count}")
    if "overall_score" in foops_checks:
        lines.append(f"- FOOPS! overall score: **{foops_checks['overall_score']} / 100**")
        for row in foops_checks.get("dimension_scores", []):
            score = "not assessed" if row.get("score") is None else f"{row['score']} / 100"
            lines.append(f"- FOOPS! {row['acronym']} ({row['dimension']}): {score}")
    if foops_checks.get("catalogue_url"):
        lines.append(f"- FOOPS! test catalogue: {foops_checks['catalogue_url']}")
    lines.extend(
        [
            "",
            "## Optional Hooks",
            "",
            f"- OWL consistency: {report['owl_consistency']['details']}",
            f"- EMMO checks: {report['emmo_checks']['details']}",
            "",
            "## Resolver Checks",
            "",
        ]
    )
    for row in report["resolver_checks"]:
        lines.append(f"- {row['label']} [{row['accept']}]: {row['status']} ({row['details']})")
    write_text(root / "output" / "reports" / "validation_report.md", "\n".join(lines) + "\n")
