from __future__ import annotations

import csv
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from .enrich import enrich_ontology
from .inspect import inspect_ontology
from .io import iter_document_items, load_json_document
from .split import split_ontology
from .utils import (
    OWL_ANNOTATION_PROPERTY,
    OWL_CLASS,
    OWL_DATATYPE_PROPERTY,
    OWL_OBJECT_PROPERTY,
    QUDT_QUANTITY_VALUE,
    RDFS_COMMENT,
    RDFS_LABEL,
    SKOS_DEFINITION,
    default_namespace_policy,
    default_release_profile,
    dump_json,
    ensure_dir,
    try_load_yaml,
    write_text,
)

PLACEHOLDER_PHRASES = (
    "class representing ",
    "object property used to relate two resources",
    "datatype property used to attach literal metadata",
    "is a local h2kg concept preserved",
    "is a local h2kg relation preserved",
)


def validate_release(
    input_path: str | Path,
    output_dir: str | Path,
    config_dir: str | Path | None = None,
) -> dict[str, Any]:
    input_path = Path(input_path)
    output_dir = ensure_dir(Path(output_dir))
    generated_at = datetime.now(timezone.utc).isoformat()
    release_root = _release_root(output_dir)
    config_root = Path(config_dir or input_path.parent.parent / "config")
    profile = try_load_yaml(config_root / "release_profile.yaml", default_release_profile())
    namespace_policy = try_load_yaml(config_root / "namespace_policy.yaml", default_namespace_policy())
    inspection = inspect_ontology(input_path, output_dir, config_root)
    candidate_path = _ensure_release_candidate(input_path, release_root, config_root)
    graph_metrics = _release_graph_metrics(candidate_path, profile["project"]["namespace_uri"], profile["project"]["ontology_iri"])
    duplicate_review = _duplicate_review(input_path)

    errors: list[str] = []
    warnings: list[str] = []
    if graph_metrics["missing_labels"] > 0:
        warnings.append(f"{graph_metrics['missing_labels']} local schema terms are missing rdfs:label in the release candidate.")
    if graph_metrics["missing_definitions"] > 0:
        warnings.append(f"{graph_metrics['missing_definitions']} local schema terms are missing skos:definition or rdfs:comment in the release candidate.")
    if graph_metrics["placeholder_definition_count"] > 0:
        warnings.append(f"{graph_metrics['placeholder_definition_count']} local schema terms still use template-style generated definitions or comments.")
    if not namespace_policy["policy"]["preserve_existing_term_iris"]:
        errors.append("Namespace policy no longer preserves existing term IRIs.")
    if duplicate_review["conflicting_count"] > 0:
        warnings.append(
            f"{duplicate_review['conflicting_count']} duplicated @id values have conflicting schema typing and require source cleanup."
        )
    if graph_metrics["metadata_gap_count"] > 0:
        warnings.append(f"{graph_metrics['metadata_gap_count']} release-header metadata fields are still missing.")

    shacl = _run_shacl(candidate_path, release_root.parent / "shapes")
    mapping_issues = _mapping_issues(release_root / "review" / "mapping_review.csv")
    external = _run_external_assessments(candidate_path, profile.get("external_assessment", {}))

    report = {
        "generated_at": generated_at,
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "shacl": shacl,
        "namespace_strategy": namespace_policy["policy"]["active_strategy"],
        "release_candidate": {
            "path": str(candidate_path),
            "schema_term_count": graph_metrics["schema_term_count"],
            "local_schema_term_count": graph_metrics["local_schema_term_count"],
            "missing_labels": graph_metrics["missing_labels"],
            "missing_definitions": graph_metrics["missing_definitions"],
            "placeholder_definition_count": graph_metrics["placeholder_definition_count"],
            "label_coverage": graph_metrics["label_coverage"],
            "definition_coverage": graph_metrics["definition_coverage"],
            "metadata_gap_count": graph_metrics["metadata_gap_count"],
            "imports_count": graph_metrics["imports_count"],
        },
        "duplicate_review": duplicate_review,
        "mapping_issues": mapping_issues,
        "namespace_violations": 0,
        "external_assessments": external,
    }
    dump_json(output_dir / "validation_report.json", report)
    write_text(output_dir / "validation_report.md", _validation_markdown(report))
    return report


def _release_root(output_dir: Path) -> Path:
    return output_dir.parent if output_dir.name == "reports" else output_dir


def _ensure_release_candidate(input_path: Path, release_root: Path, config_root: Path) -> Path:
    ontology_dir = ensure_dir(release_root / "ontology")
    ensure_dir(release_root / "examples")
    ensure_dir(release_root / "review")
    split_ontology(input_path, ontology_dir, config_root)
    enrich_ontology(input_path, ontology_dir, config_root)
    return ontology_dir / "schema.ttl"


def _release_graph_metrics(candidate_path: Path, namespace_uri: str, ontology_iri: str) -> dict[str, Any]:
    try:
        from rdflib import Graph, RDF, RDFS, OWL, URIRef
    except Exception:
        return {
            "schema_term_count": 0,
            "local_schema_term_count": 0,
            "missing_labels": 0,
            "missing_definitions": 0,
            "placeholder_definition_count": 0,
            "label_coverage": 0.0,
            "definition_coverage": 0.0,
            "metadata_gap_count": 0,
            "imports_count": 0,
        }

    graph = Graph()
    graph.parse(candidate_path)
    local_schema_terms: list[Any] = []
    schema_terms: set[Any] = set()
    schema_types = {OWL.Class, RDFS.Class, OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty}
    for schema_type in schema_types:
        schema_terms.update(graph.subjects(RDF.type, schema_type))
    ontology_node = URIRef(ontology_iri)
    label_predicate = RDFS.label
    comment_predicate = RDFS.comment
    definition_predicate = URIRef(SKOS_DEFINITION)
    title_predicate = URIRef("http://purl.org/dc/terms/title")
    description_predicate = URIRef("http://purl.org/dc/terms/description")
    license_predicate = URIRef("http://purl.org/dc/terms/license")
    version_iri_predicate = OWL.versionIRI
    prefix_predicate = URIRef("http://purl.org/vocab/vann/preferredNamespacePrefix")
    namespace_predicate = URIRef("http://purl.org/vocab/vann/preferredNamespaceUri")
    imports_count = len({str(item) for item in graph.objects(ontology_node, OWL.imports)})

    missing_labels = 0
    missing_definitions = 0
    placeholder_definition_count = 0
    for term in schema_terms:
        if not isinstance(term, URIRef):
            continue
        if not str(term).startswith(namespace_uri):
            continue
        local_schema_terms.append(term)
        labels = [str(value) for value in graph.objects(term, label_predicate)]
        definitions = [str(value) for value in graph.objects(term, definition_predicate)]
        comments = [str(value) for value in graph.objects(term, comment_predicate)]
        if not labels:
            missing_labels += 1
        if not definitions and not comments:
            missing_definitions += 1
        combined = " ".join(definitions + comments).lower()
        if combined and any(phrase in combined for phrase in PLACEHOLDER_PHRASES):
            placeholder_definition_count += 1

    metadata_required = [title_predicate, description_predicate, license_predicate, version_iri_predicate, prefix_predicate, namespace_predicate]
    metadata_gap_count = sum(1 for predicate in metadata_required if not any(graph.objects(ontology_node, predicate)))
    local_count = len(local_schema_terms)
    return {
        "schema_term_count": len(schema_terms),
        "local_schema_term_count": local_count,
        "missing_labels": missing_labels,
        "missing_definitions": missing_definitions,
        "placeholder_definition_count": placeholder_definition_count,
        "label_coverage": round((local_count - missing_labels) / local_count, 3) if local_count else 1.0,
        "definition_coverage": round((local_count - missing_definitions) / local_count, 3) if local_count else 1.0,
        "metadata_gap_count": metadata_gap_count,
        "imports_count": imports_count,
    }


def _duplicate_review(input_path: Path) -> dict[str, Any]:
    schema_types = {OWL_CLASS, OWL_OBJECT_PROPERTY, OWL_DATATYPE_PROPERTY, OWL_ANNOTATION_PROPERTY}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in iter_document_items(load_json_document(input_path)):
        identifier = item.get("@id")
        if isinstance(identifier, str):
            grouped.setdefault(identifier, []).append(item)

    duplicate_groups = {identifier: entries for identifier, entries in grouped.items() if len(entries) > 1}
    duplicate_ids = sorted(duplicate_groups.keys())
    conflict_rows: list[dict[str, Any]] = []
    for identifier, entries in duplicate_groups.items():
        types: set[str] = set()
        for entry in entries:
            raw_types = entry.get("@type", [])
            values = raw_types if isinstance(raw_types, list) else [raw_types]
            for value in values:
                if isinstance(value, str):
                    types.add(value)
        schema_type_hits = [value for value in types if value in schema_types]
        if len(schema_type_hits) > 1:
            conflict_rows.append(
                {
                    "iri": identifier,
                    "types": sorted(types),
                    "entry_count": len(entries),
                }
            )

    conflicting_ids = [row["iri"] for row in conflict_rows]
    merged_without_conflict = [identifier for identifier in duplicate_ids if identifier not in conflicting_ids]
    return {
        "status": "conflict" if conflicting_ids else ("merged" if duplicate_ids else "none"),
        "duplicate_count": len(duplicate_ids),
        "conflicting_count": len(conflicting_ids),
        "merged_without_conflict_count": len(merged_without_conflict),
        "duplicate_ids": duplicate_ids[:100],
        "conflicting_ids": conflicting_ids[:100],
        "conflicts": conflict_rows[:20],
    }


def _run_shacl(candidate_path: Path, shapes_dir: Path) -> dict[str, Any]:
    shacl = {"executed": False, "conforms": None, "details": "pyshacl not installed in the current environment."}
    shape_files = [path for path in [shapes_dir / "release_shapes.ttl", shapes_dir / "metadata_shapes.ttl", shapes_dir / "annotation_shapes.ttl"] if path.exists()]
    if not shape_files:
        shacl["details"] = "No local SHACL shapes were found."
        return shacl
    try:
        from pyshacl import validate  # type: ignore
        from rdflib import Graph
    except Exception:
        return shacl

    data_graph = Graph()
    data_graph.parse(candidate_path)
    shapes_graph = Graph()
    for shape_path in shape_files:
        shapes_graph.parse(shape_path)
    try:
        conforms, _, results_text = validate(data_graph, shacl_graph=shapes_graph, inference="rdfs", serialize_report_graph=False)
        return {"executed": True, "conforms": bool(conforms), "details": str(results_text).strip()[:800] or "SHACL validation completed."}
    except Exception as exc:
        return {"executed": True, "conforms": False, "details": f"pyshacl execution failed: {exc}"}


def _mapping_issues(mapping_review_path: Path) -> int:
    if not mapping_review_path.exists():
        return 0
    issues = 0
    with mapping_review_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            local_kind = (row.get("local_kind") or "").strip().lower()
            relation = (row.get("relation") or "").strip().lower()
            target_kind = (row.get("target_kind") or "").strip().lower()
            target_label = ((row.get("target_label") or "") + " " + (row.get("rationale") or "")).lower()
            if local_kind in {"class", "controlled_vocabulary_term"} and target_kind == "object_property":
                issues += 1
            elif local_kind in {"object_property", "datatype_property"} and target_kind == "class":
                issues += 1
            elif not relation:
                issues += 1
            elif "obsolete" in target_label or "deprecated" in target_label:
                issues += 1
    return issues


def _run_external_assessments(candidate_path: Path, settings: dict[str, Any]) -> dict[str, Any]:
    enabled = bool(settings.get("enabled", False))
    if not enabled:
        disabled = {
            "status": "disabled",
            "service": "",
            "message": "External ontology quality services are disabled in the active release profile.",
        }
        return {"oops": dict(disabled), "foops": dict(disabled)}
    return {
        "oops": _run_oops_assessment(candidate_path, settings),
        "foops": _run_foops_assessment(candidate_path, settings),
    }


def _run_oops_assessment(candidate_path: Path, settings: dict[str, Any]) -> dict[str, Any]:
    if not settings.get("oops_enabled", False):
        return {
            "status": "disabled",
            "service": settings.get("oops_service", ""),
            "message": "OOPS! assessment is disabled in the active release profile.",
        }
    service = settings.get("oops_service", "https://oops.linkeddata.es/rest")
    timeout = int(settings.get("timeout_seconds", 45))
    retries = int(settings.get("retries", 3))
    backoff = float(settings.get("backoff_seconds", 2))
    use_env_proxies = bool(settings.get("use_env_proxies", False))
    try:
        ontology_content = _serialize_candidate(candidate_path, "pretty-xml")
        request_body = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<OOPSRequest>"
            "<OntologyUrl></OntologyUrl>"
            f"<OntologyContent><![CDATA[{ontology_content}]]></OntologyContent>"
            "<Pitfalls></Pitfalls>"
            "<OutputFormat>XML</OutputFormat>"
            "</OOPSRequest>"
        )
        response_text = _external_post(
            service,
            data=request_body.encode("utf-8"),
            headers={"Content-Type": "application/xml; charset=utf-8"},
            timeout=timeout,
            retries=retries,
            backoff_seconds=backoff,
            use_env_proxies=use_env_proxies,
        )
        if "unexpected error" in response_text.lower():
            return {
                "status": "unavailable",
                "service": service,
                "message": _short_message(response_text),
            }
        parsed = _parse_oops_xml(response_text)
        parsed.update({"status": "assessed", "service": service, "message": "OOPS! assessment completed against the release candidate ontology."})
        return parsed
    except Exception as exc:
        return {
            "status": "unavailable",
            "service": service,
            "message": f"OOPS! service unavailable: {exc}",
        }


def _run_foops_assessment(candidate_path: Path, settings: dict[str, Any]) -> dict[str, Any]:
    if not settings.get("foops_enabled", False):
        return {
            "status": "disabled",
            "service": settings.get("foops_service", ""),
            "message": "FOOPS! assessment is disabled in the active release profile.",
        }
    service = settings.get("foops_service", "https://foops.linkeddata.es/FAIR_validator.html")
    file_service = settings.get("foops_file_service", "https://foops.linkeddata.es/assessOntologyFile")
    uri_service = settings.get("foops_uri_service", "https://foops.linkeddata.es/assessOntology")
    timeout = int(settings.get("timeout_seconds", 45))
    retries = int(settings.get("retries", 3))
    backoff = float(settings.get("backoff_seconds", 2))
    use_env_proxies = bool(settings.get("use_env_proxies", False))
    mode = str(settings.get("foops_mode", "file")).strip().lower()
    public_uri = str(settings.get("public_uri", "")).strip()
    try:
        if mode == "uri" and public_uri:
            response_text = _external_post(
                uri_service,
                data=json.dumps({"ontologyUri": public_uri}),
                timeout=timeout,
                retries=retries,
                backoff_seconds=backoff,
                use_env_proxies=use_env_proxies,
                headers={"Content-Type": "application/json; charset=utf-8"},
            )
        else:
            candidate_bytes = _serialize_candidate(candidate_path, "pretty-xml").encode("utf-8")
            response_text = _external_post(
                file_service,
                data={},
                files={"file": (candidate_path.with_suffix(".rdf").name, candidate_bytes, "application/rdf+xml")},
                timeout=max(timeout, 180),
                retries=retries,
                backoff_seconds=backoff,
                use_env_proxies=use_env_proxies,
                headers={"Referer": service},
            )
            mode = "file"
        parsed = _parse_foops_payload(response_text)
        parsed.update(
            {
                "status": "assessed" if parsed.get("overall_score") is not None else "unavailable",
                "service": service,
                "mode": mode,
                "message": parsed.get("message")
                or (
                    "FOOPS! assessment completed in URI mode."
                    if mode == "uri"
                    else "FOOPS! assessment completed in file mode. Accessible checks may remain unassessed."
                ),
            }
        )
        if parsed["status"] != "assessed":
            parsed["message"] = parsed.get("message") or "FOOPS! response did not expose machine-readable scores."
        return parsed
    except Exception as exc:
        return {
            "status": "unavailable",
            "service": service,
            "mode": mode,
            "message": f"FOOPS! service unavailable: {exc}",
        }


def _parse_foops_payload(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except Exception:
        return _parse_foops_response(text)
    if not isinstance(payload, dict):
        return _parse_foops_response(text)
    return _parse_foops_json(payload)


def _submit_foops_file_mode(
    service: str,
    page_html: str,
    candidate_path: Path,
    timeout: int,
    retries: int,
    backoff_seconds: float,
    use_env_proxies: bool,
) -> str:
    parser = _FoopsFormParser()
    parser.feed(page_html)
    form = parser.pick_form(mode="file")
    if not form or not form.file_field:
        raise RuntimeError("FOOPS! file-upload form could not be discovered from the validator page.")
    data = form.data(mode="file")
    with candidate_path.open("rb") as handle:
        files = {form.file_field: (candidate_path.name, handle.read(), "text/turtle")}
    post_url = urljoin(service, form.action or "")
    return _external_post(
        post_url,
        data=data,
        files=files,
        timeout=timeout,
        retries=retries,
        backoff_seconds=backoff_seconds,
        use_env_proxies=use_env_proxies,
        headers={"Referer": service},
    )


def _submit_foops_uri_mode(
    service: str,
    page_html: str,
    public_uri: str,
    timeout: int,
    retries: int,
    backoff_seconds: float,
    use_env_proxies: bool,
) -> str:
    parser = _FoopsFormParser()
    parser.feed(page_html)
    form = parser.pick_form(mode="uri")
    if not form or not form.uri_field:
        raise RuntimeError("FOOPS! URI form could not be discovered from the validator page.")
    data = form.data(mode="uri")
    data[form.uri_field] = public_uri
    post_url = urljoin(service, form.action or "")
    return _external_post(
        post_url,
        data=data,
        timeout=timeout,
        retries=retries,
        backoff_seconds=backoff_seconds,
        use_env_proxies=use_env_proxies,
        headers={"Referer": service},
    )


def _external_get(url: str, timeout: int, retries: int, backoff_seconds: float, use_env_proxies: bool) -> str:
    try:
        import requests
    except Exception as exc:
        raise RuntimeError(f"requests is not installed: {exc}") from exc

    last_error: Exception | None = None
    for attempt in range(retries):
        session = requests.Session()
        session.trust_env = use_env_proxies
        try:
            response = session.get(url, timeout=timeout, headers={"User-Agent": "aimworks-ontology-release/1.0"})
            response.raise_for_status()
            return response.text
        except Exception as exc:
            last_error = exc
            if attempt < retries - 1:
                time.sleep(backoff_seconds)
        finally:
            session.close()
    raise RuntimeError(str(last_error) if last_error else "External GET failed.")


def _external_post(
    url: str,
    *,
    data: Any,
    timeout: int,
    retries: int,
    backoff_seconds: float,
    use_env_proxies: bool,
    headers: dict[str, str] | None = None,
    files: dict[str, Any] | None = None,
) -> str:
    try:
        import requests
    except Exception as exc:
        raise RuntimeError(f"requests is not installed: {exc}") from exc

    last_error: Exception | None = None
    for attempt in range(retries):
        session = requests.Session()
        session.trust_env = use_env_proxies
        try:
            response = session.post(url, data=data, files=files, timeout=timeout, headers={"User-Agent": "aimworks-ontology-release/1.0", **(headers or {})})
            response.raise_for_status()
            return response.text
        except Exception as exc:
            last_error = exc
            if attempt < retries - 1:
                time.sleep(backoff_seconds)
        finally:
            session.close()
    raise RuntimeError(str(last_error) if last_error else "External POST failed.")


def _serialize_candidate(candidate_path: Path, serialization: str) -> str:
    from rdflib import Graph

    graph = Graph()
    graph.parse(candidate_path)
    return graph.serialize(format=serialization)


def _parse_oops_xml(text: str) -> dict[str, Any]:
    root = ET.fromstring(text)
    pitfalls: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    suggestions: list[dict[str, Any]] = []
    for element in root.iter():
        tag = _xml_local_name(element.tag).lower()
        if tag == "pitfall":
            pitfalls.append(
                {
                    "code": _first_child_text(element, {"Code", "hasCode"}),
                    "name": _first_child_text(element, {"Name", "hasName"}),
                    "description": _first_child_text(element, {"Description", "hasDescription"}),
                    "affected_elements": _all_child_text(element, {"AffectedElement", "hasAffectedElement"})[:10],
                }
            )
        elif tag == "warning":
            warnings.append(
                {
                    "name": _first_child_text(element, {"Name", "hasName"}),
                    "affected_elements": _all_child_text(element, {"AffectedElement", "hasAffectedElement"})[:10],
                }
            )
        elif tag == "suggestion":
            suggestions.append(
                {
                    "name": _first_child_text(element, {"Name", "hasName"}),
                    "description": _first_child_text(element, {"Description", "hasDescription"}),
                    "affected_elements": _all_child_text(element, {"AffectedElement", "hasAffectedElement"})[:10],
                }
            )
    return {
        "pitfall_count": len(pitfalls),
        "warning_count": len(warnings),
        "suggestion_count": len(suggestions),
        "pitfalls": pitfalls[:12],
        "warnings": warnings[:12],
        "suggestions": suggestions[:12],
    }


def _xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].rsplit(":", 1)[-1]


def _first_child_text(element: ET.Element, names: set[str]) -> str:
    for child in element.iter():
        if child is element:
            continue
        if _xml_local_name(child.tag) in names:
            text = (child.text or "").strip()
            if text:
                return text
    return ""


def _all_child_text(element: ET.Element, names: set[str]) -> list[str]:
    values: list[str] = []
    for child in element.iter():
        if child is element:
            continue
        if _xml_local_name(child.tag) in names:
            text = (child.text or "").strip()
            if text and text not in values:
                values.append(text)
    return values


def _parse_foops_response(text: str) -> dict[str, Any]:
    plain_text = _collapse_whitespace(_strip_html(text))
    overall_score = _extract_score(plain_text, "Overall score")
    dimensions = {
        "findable": _extract_dimension_score(plain_text, "Findable"),
        "accessible": _extract_dimension_score(plain_text, "Accessible"),
        "interoperable": _extract_dimension_score(plain_text, "Interoperable"),
        "reusable": _extract_dimension_score(plain_text, "Reusable"),
    }
    failed_checks = _extract_foops_failed_checks(text, plain_text)
    if overall_score is None and all(value is None for value in dimensions.values()):
        return {
            "overall_score": None,
            "dimensions": dimensions,
            "failed_checks": failed_checks,
            "message": _short_message(plain_text or text),
        }
    if dimensions["accessible"] is None and "does not run accessibility tests" in plain_text.lower():
        failed_checks = failed_checks[:]
    return {
        "overall_score": overall_score,
        "dimensions": dimensions,
        "failed_checks": failed_checks[:10],
        "message": "",
    }


def _parse_foops_json(payload: dict[str, Any]) -> dict[str, Any]:
    raw_score = payload.get("overall_score")
    overall_score = None
    if isinstance(raw_score, (int, float)):
        overall_score = round(float(raw_score) * 100, 1) if float(raw_score) <= 1 else round(float(raw_score), 1)
    checks = payload.get("checks", [])
    category_totals: dict[str, list[int]] = {}
    failed_checks: list[dict[str, str]] = []
    for check in checks if isinstance(checks, list) else []:
        if not isinstance(check, dict):
            continue
        category = str(check.get("category_id", "")).strip().lower()
        passed = int(check.get("total_passed_tests", 0) or 0)
        total = int(check.get("total_tests_run", 0) or 0)
        bucket = category_totals.setdefault(category, [0, 0])
        bucket[0] += passed
        bucket[1] += total
        if str(check.get("status", "")).lower() != "ok":
            label = str(check.get("principle_id") or check.get("abbreviation") or check.get("id") or "check")
            detail = str(check.get("explanation") or check.get("title") or "")
            failed_checks.append({"label": label, "detail": detail})
    dimensions = {
        "findable": _foops_category_score(category_totals.get("findable")),
        "accessible": _foops_category_score(category_totals.get("accessible")),
        "interoperable": _foops_category_score(category_totals.get("interoperable")),
        "reusable": _foops_category_score(category_totals.get("reusable")),
    }
    return {
        "overall_score": overall_score,
        "dimensions": dimensions,
        "failed_checks": failed_checks[:10],
        "message": "",
        "ontology_title": payload.get("ontology_title", ""),
        "ontology_uri": payload.get("ontology_URI", ""),
    }


def _foops_category_score(bucket: list[int] | None) -> float | None:
    if not bucket or bucket[1] == 0:
        return None
    return round(bucket[0] / bucket[1] * 100, 1)


def _extract_score(text: str, label: str) -> float | None:
    pattern = re.compile(rf"{re.escape(label)}[^0-9]{{0,160}}([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
    match = pattern.search(text)
    return float(match.group(1)) if match else None


def _extract_dimension_score(text: str, label: str) -> float | None:
    direct_match = re.search(rf"{re.escape(label)}\s+([0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
    if direct_match:
        return float(direct_match.group(1))
    not_assessed_match = re.search(rf"{re.escape(label)}\s+(?:/ 100\s+)?(not assessed|not run|not available)", text, re.IGNORECASE)
    if not_assessed_match:
        return None
    segment_pattern = re.compile(rf"{re.escape(label)}([^FAIR]{{0,40}})", re.IGNORECASE)
    match = segment_pattern.search(text)
    if not match:
        return None
    score_match = re.search(r"([0-9]+(?:\.[0-9]+)?)", match.group(1))
    return float(score_match.group(1)) if score_match else None


def _extract_foops_failed_checks(html: str, plain_text: str) -> list[dict[str, str]]:
    failed_checks: list[dict[str, str]] = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, flags=re.IGNORECASE | re.DOTALL):
        row_text = _collapse_whitespace(_strip_html(row))
        if not row_text:
            continue
        if re.search(r"\b(fail|failed|warning|not passed|not assessed)\b", row_text, re.IGNORECASE):
            code_match = re.search(r"\b([FAIR]\d+(?:\.\d+)*)\b", row_text)
            label = code_match.group(1) if code_match else row_text.split(" ", 1)[0]
            failed_checks.append({"label": label, "detail": row_text})
    if failed_checks:
        return failed_checks

    for line in re.split(r"(?<=[.;])\s+", plain_text):
        if re.search(r"\b(fail|failed|warning|not assessed)\b", line, re.IGNORECASE):
            code_match = re.search(r"\b([FAIR]\d+(?:\.\d+)*)\b", line)
            if code_match:
                failed_checks.append({"label": code_match.group(1), "detail": line.strip()})
    return failed_checks


def _short_message(text: str, limit: int = 240) -> str:
    compact = _collapse_whitespace(_strip_html(text))
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text)


def _collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


class _FoopsForm:
    def __init__(self, action: str, method: str, controls: list[dict[str, str]]) -> None:
        self.action = action
        self.method = method
        self.controls = controls

    @property
    def file_field(self) -> str:
        for control in self.controls:
            if control.get("type") == "file":
                return control.get("name", "")
        return ""

    @property
    def uri_field(self) -> str:
        for control in self.controls:
            control_type = control.get("type", "")
            token = f"{control.get('name', '')} {control.get('id', '')}".lower()
            if control_type in {"url", "text"} and ("uri" in token or "ontology" in token):
                return control.get("name", "")
        return ""

    def data(self, mode: str) -> dict[str, str]:
        payload: dict[str, str] = {}
        for control in self.controls:
            control_type = control.get("type", "text")
            name = control.get("name", "")
            if not name or control_type in {"file", "submit", "button"}:
                continue
            if control_type in {"hidden", "text", "url"}:
                payload[name] = control.get("value", "")
            token = f"{name} {control.get('id', '')} {control.get('value', '')}".lower()
            if mode == "file" and control_type in {"radio", "hidden", "text"} and "file" in token and ("mode" in token or "input" in token or "type" in token):
                payload[name] = control.get("value", "file")
            if mode == "uri" and control_type in {"radio", "hidden", "text"} and "uri" in token and ("mode" in token or "input" in token or "type" in token):
                payload[name] = control.get("value", "uri")
        return payload


class _FoopsFormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.forms: list[_FoopsForm] = []
        self._current_action = ""
        self._current_method = "post"
        self._current_controls: list[dict[str, str]] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value or "" for key, value in attrs}
        if tag == "form":
            self._current_action = attr_map.get("action", "")
            self._current_method = attr_map.get("method", "post").lower()
            self._current_controls = []
        elif tag == "input" and self._current_controls is not None:
            self._current_controls.append(
                {
                    "name": attr_map.get("name", ""),
                    "id": attr_map.get("id", ""),
                    "type": attr_map.get("type", "text").lower(),
                    "value": attr_map.get("value", ""),
                }
            )

    def handle_endtag(self, tag: str) -> None:
        if tag == "form" and self._current_controls is not None:
            self.forms.append(_FoopsForm(self._current_action, self._current_method, self._current_controls))
            self._current_controls = None

    def pick_form(self, mode: str) -> _FoopsForm | None:
        if mode == "file":
            for form in self.forms:
                if form.file_field:
                    return form
        if mode == "uri":
            for form in self.forms:
                if form.uri_field:
                    return form
        return self.forms[0] if self.forms else None


def _validation_markdown(report: dict[str, Any]) -> str:
    errors = "\n".join(f"- {line}" for line in report["errors"]) or "- None"
    warnings = "\n".join(f"- {line}" for line in report["warnings"]) or "- None"
    release = report["release_candidate"]
    duplicate_review = report.get("duplicate_review", {})
    oops = report["external_assessments"]["oops"]
    foops = report["external_assessments"]["foops"]
    foops_checks = "\n".join(f"- {item['label']}: {item['detail']}" for item in foops.get("failed_checks", [])) or "- No failed-check detail extracted."
    oops_pitfalls = "\n".join(f"- {item.get('code') or 'pitfall'}: {item.get('name', 'Unnamed pitfall')}" for item in oops.get("pitfalls", [])) or "- No pitfalls listed."
    return f"""# Validation Report

- Overall valid: {str(report['valid']).lower()}
- Namespace strategy: `{report['namespace_strategy']}`
- SHACL executed: {str(report['shacl']['executed']).lower()}
- SHACL details: {report['shacl']['details']}
- Release candidate path: `{release['path']}`

## Release Candidate Checks

- Local schema terms: {release['local_schema_term_count']}
- Missing labels: {release['missing_labels']}
- Missing definitions: {release['missing_definitions']}
- Placeholder-style generated definitions: {release['placeholder_definition_count']}
- Definition coverage: {release['definition_coverage']}
- Imports declared in release schema: {release['imports_count']}
- Mapping issues detected: {report['mapping_issues']}
- Duplicate @id groups in source: {duplicate_review.get('duplicate_count', 0)}
- Duplicate @id conflicts in source: {duplicate_review.get('conflicting_count', 0)}

## OOPS! Pitfall Scan

- Status: {oops.get('status', 'unknown')}
- Service: {oops.get('service', '')}
- Message: {oops.get('message', '')}
- Pitfall count: {oops.get('pitfall_count', 'not assessed')}

{oops_pitfalls}

## FOOPS! FAIR Assessment

- Status: {foops.get('status', 'unknown')}
- Service: {foops.get('service', '')}
- Mode: {foops.get('mode', 'n/a')}
- Message: {foops.get('message', '')}
- Overall score: {foops.get('overall_score', 'not assessed')}
- Findable: {foops.get('dimensions', {}).get('findable', 'not assessed')}
- Accessible: {foops.get('dimensions', {}).get('accessible', 'not assessed')}
- Interoperable: {foops.get('dimensions', {}).get('interoperable', 'not assessed')}
- Reusable: {foops.get('dimensions', {}).get('reusable', 'not assessed')}

## FOOPS! Failed Checks

{foops_checks}

## Errors

{errors}

## Warnings

{warnings}
"""
