from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import yaml
from pyshacl import validate as shacl_validate
from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import DCTERMS, OWL, SKOS, XSD

from .utils import ensure_dir, write_text


H2KG_ONTOLOGY = URIRef("https://w3id.org/h2kg/hydrogen-ontology")
H2KG = Namespace("https://w3id.org/h2kg/hydrogen-ontology#")
SH = Namespace("http://www.w3.org/ns/shacl#")
VANN = Namespace("http://purl.org/vocab/vann/")
DOAP = Namespace("http://usefulinc.com/ns/doap#")
PREMIS = Namespace("http://www.loc.gov/premis/rdf/v3/")
IAO_ROOT = URIRef("http://purl.obolibrary.org/obo/IAO_0000700")
ORCID_PATTERN = re.compile(r"^https://orcid\.org/\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")
ROR_PATTERN = re.compile(r"^https://ror\.org/[0-9a-hj-km-np-tv-z]{9}$")


def write_release_citation_metadata(
    project_root: str | Path,
    config_dir: str | Path,
) -> dict[str, str]:
    """Generate citation and repository metadata from the release profile."""

    project_root = Path(project_root)
    config_dir = Path(config_dir)
    profile_document = yaml.safe_load((config_dir / "release_profile.yaml").read_text(encoding="utf-8")) or {}
    profile = dict(profile_document.get("project", {}))
    creator_rows = list(profile.get("creators", []))
    contributor_rows = list(profile.get("contributors", []))
    attribution = [*creator_rows, *contributor_rows]
    affiliation_registry = dict(profile.get("affiliations", {}))

    cff_authors: list[dict[str, str]] = []
    zenodo_creators: list[dict[str, str]] = []
    zenodo_contributors: list[dict[str, str]] = []
    for row in attribution:
        iri = str(row.get("iri", ""))
        label = str(row.get("label", "")).strip()
        kind = str(row.get("kind", "")).strip()
        if not iri or not label or kind not in {"person", "organization"}:
            raise ValueError(f"Incomplete release attribution entry: {row!r}")
        if kind == "person":
            given = str(row.get("given_names", "")).strip()
            family = str(row.get("family_names", "")).strip()
            affiliation_ids = [str(value) for value in row.get("affiliation_ids", [])]
            unknown_affiliations = [value for value in affiliation_ids if value not in affiliation_registry]
            if unknown_affiliations:
                raise ValueError(
                    f"Unknown affiliation identifiers for {label}: {', '.join(unknown_affiliations)}"
                )
            affiliation = "; ".join(
                str(affiliation_registry[value].get("label", "")).strip()
                for value in affiliation_ids
                if str(affiliation_registry[value].get("label", "")).strip()
            )
            if not affiliation:
                affiliation = str(row.get("affiliation", "")).strip()
            if not given or not family:
                raise ValueError(f"Person attribution lacks structured names: {label}")
            cff_row = {"family-names": family, "given-names": given}
            if affiliation:
                cff_row["affiliation"] = affiliation
            zenodo_row = {
                "name": f"{family}, {given}",
                "affiliation": affiliation,
            }
            if ORCID_PATTERN.fullmatch(iri):
                cff_row["orcid"] = iri
                zenodo_row["orcid"] = iri.removeprefix("https://orcid.org/")
            else:
                cff_row["website"] = iri
            cff_authors.append(cff_row)
            normalized_zenodo_row = {key: value for key, value in zenodo_row.items() if value}
        else:
            cff_authors.append({"name": label, "website": iri})
            normalized_zenodo_row = {"name": label}
        if row in contributor_rows:
            zenodo_contributors.append({**normalized_zenodo_row, "type": "Researcher"})
        else:
            zenodo_creators.append(normalized_zenodo_row)

    license_url = str(profile.get("license", ""))
    license_identifier = "CC-BY-4.0" if license_url.rstrip("/") == "https://creativecommons.org/licenses/by/4.0" else license_url
    title = str(profile.get("title", ""))
    version = str(profile.get("version", ""))
    modified = str(profile.get("modified", ""))
    abstract = str(profile.get("abstract", ""))
    cff = {
        "cff-version": "1.2.0",
        "title": title,
        "message": "If you use H2KG, please cite the ontology release using the metadata below.",
        "type": "dataset",
        "authors": cff_authors,
        "repository-code": str(profile.get("repository_url", "")),
        "url": str(profile.get("ontology_iri", "")),
        "license": license_identifier,
        "version": version,
        "date-released": modified,
        "abstract": abstract,
    }
    zenodo = {
        "title": title,
        "description": abstract,
        "creators": zenodo_creators,
        "contributors": zenodo_contributors,
        "license": license_identifier.casefold(),
        "upload_type": "dataset",
        "version": version,
        "access_right": "open",
    }
    cff_path = project_root / "CITATION.cff"
    zenodo_path = project_root / ".zenodo.json"
    write_text(
        cff_path,
        yaml.safe_dump(cff, sort_keys=False, allow_unicode=True, width=1000),
    )
    write_text(zenodo_path, json.dumps(zenodo, indent=2, ensure_ascii=False) + "\n")
    return {"citation_cff": str(cff_path), "zenodo": str(zenodo_path)}


def build_tib_submission_package(
    taxonomy_ttl: str | Path,
    taxonomy_jsonld: str | Path,
    output_root: str | Path,
    config_dir: str | Path,
    *,
    check_live_urls: bool = False,
    require_live_urls: bool = False,
) -> dict[str, Any]:
    """Validate and document the canonical H2KG artifact for TIB ingestion."""

    taxonomy_ttl = Path(taxonomy_ttl)
    taxonomy_jsonld = Path(taxonomy_jsonld)
    output_root = Path(output_root)
    config_dir = Path(config_dir)
    reports_dir = ensure_dir(output_root / "reports")

    profile_document = yaml.safe_load((config_dir / "release_profile.yaml").read_text(encoding="utf-8")) or {}
    profile = dict(profile_document.get("project", {}))
    expected = {key: int(value) for key, value in profile.get("expected_counts", {}).items()}
    shape_path = config_dir / "tib" / "OntoMetadataShape4TS.ttl"
    lock_path = config_dir / "tib" / "metadata_shape_lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))

    checks: list[dict[str, Any]] = []

    def record(identifier: str, passed: bool, detail: str, *, blocking: bool = True) -> None:
        checks.append(
            {
                "id": identifier,
                "passed": bool(passed),
                "blocking": bool(blocking),
                "detail": detail,
            }
        )

    shape_sha256 = _sha256(shape_path)
    record(
        "tib-metadata-shape-lock",
        shape_sha256 == str(lock.get("sha256", "")).upper(),
        f"Pinned TIB metadata shape SHA-256: {shape_sha256}.",
    )

    ttl_graph = Graph().parse(taxonomy_ttl, format="turtle")
    jsonld_graph = Graph().parse(taxonomy_jsonld, format="json-ld")
    serialization_parity = isomorphic(ttl_graph, jsonld_graph)
    record(
        "canonical-serialization-parity",
        serialization_parity,
        "Canonical Turtle and JSON-LD graphs are RDF-isomorphic.",
    )

    shape_graph = Graph().parse(shape_path, format="turtle")
    _, shacl_report_graph, shacl_report_text = shacl_validate(
        data_graph=ttl_graph,
        shacl_graph=shape_graph,
        inference="none",
        abort_on_first=False,
        allow_infos=True,
        allow_warnings=True,
    )
    shape_results = _shape_results(shacl_report_graph)
    mandatory_results = [
        row for row in shape_results if row["severity"] in {str(SH.Warning), str(SH.Violation)}
    ]
    info_results = [row for row in shape_results if row["severity"] == str(SH.Info)]
    record(
        "tib-mandatory-metadata",
        not mandatory_results,
        f"Official TIB shape results: {len(mandatory_results)} mandatory warning/violation(s), {len(info_results)} recommendation notice(s).",
    )

    counts = _ontology_counts(ttl_graph)
    for key, expected_value in expected.items():
        actual = int(counts.get(key, -1))
        record(
            f"count-{key.replace('_', '-')}",
            actual == expected_value,
            f"Expected {expected_value}; canonical graph contains {actual}.",
        )

    ontology_nodes = set(ttl_graph.subjects(RDF.type, OWL.Ontology))
    record(
        "single-ontology-header",
        ontology_nodes == {H2KG_ONTOLOGY},
        f"Ontology headers: {', '.join(sorted(map(str, ontology_nodes))) or 'none'}.",
    )
    record(
        "ontology-title",
        _literal_value(ttl_graph, DCTERMS.title) == str(profile.get("title", "")),
        "The ontology title is generated from the release profile.",
    )
    record(
        "lowercase-prefix",
        bool(re.fullmatch(r"[a-z][a-z0-9]*", str(profile.get("namespace_prefix", ""))))
        and _literal_value(ttl_graph, VANN.preferredNamespacePrefix) == str(profile.get("namespace_prefix")),
        f"Preferred namespace prefix: {profile.get('namespace_prefix', '')}.",
    )
    record(
        "preferred-namespace",
        URIRef(str(profile.get("namespace_uri"))) in set(ttl_graph.objects(H2KG_ONTOLOGY, VANN.preferredNamespaceUri)),
        f"Preferred namespace URI: {profile.get('namespace_uri', '')}.",
    )
    record(
        "license",
        URIRef(str(profile.get("license"))) in set(ttl_graph.objects(H2KG_ONTOLOGY, DCTERMS.license)),
        f"License: {profile.get('license', '')}.",
    )
    record(
        "created-date",
        _typed_date_matches(ttl_graph, DCTERMS.created, str(profile.get("created", ""))),
        f"Creation date: {profile.get('created', '')}.",
    )
    record(
        "modified-date",
        _typed_date_matches(ttl_graph, DCTERMS.modified, str(profile.get("modified", ""))),
        f"Modification date: {profile.get('modified', '')}.",
    )
    abstract = ttl_graph.value(H2KG_ONTOLOGY, DCTERMS.abstract)
    record(
        "abstract",
        isinstance(abstract, Literal)
        and abstract.language == "en"
        and 0 < len(str(abstract).strip()) <= 500,
        f"English abstract length: {len(str(abstract or ''))} characters.",
    )
    record(
        "issue-tracker",
        URIRef(str(profile.get("issue_tracker_url"))) in set(ttl_graph.objects(H2KG_ONTOLOGY, DOAP["bug-database"])),
        f"Issue tracker: {profile.get('issue_tracker_url', '')}.",
    )
    record(
        "documentation",
        URIRef(str(profile.get("documentation_url"))) in set(ttl_graph.objects(H2KG_ONTOLOGY, PREMIS.documentation)),
        f"Documentation: {profile.get('documentation_url', '')}.",
    )

    configured_people = [
        *profile.get("creators", []),
        *profile.get("contributors", []),
    ]
    attribution_iris = {
        str(value)
        for predicate in (DCTERMS.creator, DCTERMS.contributor)
        for value in ttl_graph.objects(H2KG_ONTOLOGY, predicate)
        if isinstance(value, URIRef)
    }
    unconfirmed = [str(row.get("iri", "")) for row in configured_people if not row.get("confirmed")]
    malformed_orcids = [
        str(row.get("iri", ""))
        for row in configured_people
        if str(row.get("iri", "")).startswith("https://orcid.org/")
        and not ORCID_PATTERN.fullmatch(str(row.get("iri", "")))
    ]
    orcids = [iri for iri in attribution_iris if iri.startswith("https://orcid.org/")]
    rors = [iri for iri in attribution_iris if iri.startswith("https://ror.org/")]
    record(
        "confirmed-attribution",
        not unconfirmed and all(str(row.get("iri", "")) in attribution_iris for row in configured_people),
        f"Configured attribution resources: {len(configured_people)}; unconfirmed: {len(unconfirmed)}.",
    )
    contributor_orders = sorted(
        int(row["contribution_order"])
        for row in profile.get("contributors", [])
        if str(row.get("contribution_order", "")).isdigit()
    )
    expected_orders = list(range(1, max(contributor_orders, default=0) + 1))
    missing_orders = sorted(set(expected_orders) - set(contributor_orders))
    duplicate_orders = sorted(
        order for order in set(contributor_orders) if contributor_orders.count(order) > 1
    )
    attribution_complete = bool(profile.get("attribution_complete"))
    record(
        "attribution-list-complete",
        attribution_complete
        and bool(contributor_orders)
        and not missing_orders
        and not duplicate_orders,
        "Contributor order complete: "
        f"{attribution_complete}; configured orders: {contributor_orders}; "
        f"missing: {missing_orders or 'none'}; duplicates: {duplicate_orders or 'none'}.",
    )
    record(
        "creator-orcid",
        bool(orcids) and not malformed_orcids,
        f"Valid ORCID attribution IRIs: {len(orcids)}; malformed: {len(malformed_orcids)}.",
    )
    personal_rows = [row for row in configured_people if str(row.get("kind", "")) == "person"]
    affiliation_registry = dict(profile.get("affiliations", {}))
    people_without_affiliation = [
        str(row.get("label", row.get("iri", "")))
        for row in personal_rows
        if not row.get("affiliation_ids")
    ]
    unknown_affiliation_ids = sorted(
        {
            str(identifier)
            for row in personal_rows
            for identifier in row.get("affiliation_ids", [])
            if str(identifier) not in affiliation_registry
        }
    )
    record(
        "affiliation-assignments",
        not people_without_affiliation and not unknown_affiliation_ids,
        f"People without affiliation assignment: {people_without_affiliation or 'none'}; "
        f"unknown affiliation identifiers: {unknown_affiliation_ids or 'none'}.",
    )
    personal_without_pid = []
    for row in personal_rows:
        iri = str(row.get("iri", ""))
        has_orcid = bool(ORCID_PATTERN.fullmatch(iri))
        has_documented_institutional_identifier = (
            str(row.get("orcid_status", "")) == "unavailable"
            and str(row.get("identifier_type", "")) == "institutional_profile"
            and iri.startswith("https://www.fz-juelich.de/profile/")
            and bool(row.get("confirmed"))
        )
        if not (has_orcid or has_documented_institutional_identifier):
            personal_without_pid.append(str(row.get("label", iri)))
    record(
        "personal-pid-attribution",
        not personal_without_pid,
        "Named people without an ORCID or documented institutional identifier: "
        + (", ".join(personal_without_pid) if personal_without_pid else "none"),
    )
    record(
        "organization-ror",
        bool(rors) and all(ROR_PATTERN.fullmatch(iri) for iri in rors),
        f"Valid ROR attribution IRIs: {len(rors)}.",
    )
    missing_labels = [iri for iri in attribution_iris if ttl_graph.value(URIRef(iri), RDFS.label) is None]
    record(
        "attribution-labels",
        not missing_labels,
        f"Attribution resources without display labels: {len(missing_labels)}.",
    )

    version_iri = str(profile.get("version_iri", ""))
    record(
        "version-metadata",
        ttl_graph.value(H2KG_ONTOLOGY, OWL.versionIRI) == URIRef(version_iri)
        and ttl_graph.value(H2KG_ONTOLOGY, OWL.versionInfo) == Literal(str(profile.get("version", ""))),
        f"Version IRI: {version_iri}.",
    )
    record(
        "prior-version",
        ttl_graph.value(H2KG_ONTOLOGY, OWL.priorVersion) == URIRef(str(profile.get("prior_version", ""))),
        f"Prior version: {profile.get('prior_version', '')}.",
    )

    imports = {str(value).rstrip("#") for value in ttl_graph.objects(H2KG_ONTOLOGY, OWL.imports)}
    expected_imports = {str(value).rstrip("#") for value in profile.get("imports", [])}
    record(
        "foundational-imports-only",
        imports == expected_imports,
        f"Declared imports: {', '.join(sorted(imports)) or 'none'}.",
    )
    roots = {str(value) for value in ttl_graph.objects(H2KG_ONTOLOGY, IAO_ROOT)}
    expected_roots = {str(H2KG[str(value)]) for value in profile.get("root_classes", [])}
    record(
        "explicit-root-classes",
        roots == expected_roots,
        f"Declared root classes: {len(roots)}.",
    )

    local_file_iris = sorted(
        {
            str(value)
            for triple in ttl_graph
            for value in triple
            if isinstance(value, URIRef) and str(value).startswith("file:")
        }
    )
    record(
        "no-local-file-iris",
        not local_file_iris,
        f"Local file IRIs: {len(local_file_iris)}.",
    )

    distributions = {str(value) for value in ttl_graph.objects(H2KG_ONTOLOGY, URIRef("http://www.w3.org/ns/dcat#distribution"))}
    expected_distributions = {str(value) for value in profile.get("distributions", {}).values()}
    record(
        "canonical-distributions",
        distributions == expected_distributions,
        f"Canonical distributions: {', '.join(sorted(distributions)) or 'none'}.",
    )

    w3id_path = output_root / "w3id" / "h2kg" / ".htaccess"
    w3id_text = w3id_path.read_text(encoding="utf-8") if w3id_path.exists() else ""
    record(
        "canonical-resolver-template",
        "RewriteRule ^hydrogen-ontology$" in w3id_text
        and "h2kg-v2-taxonomy.ttl" in w3id_text
        and "RewriteRule ^hydrogen-ontology/core$" in w3id_text
        and "core_schema.ttl" in w3id_text,
        "Stable RDF routes target the taxonomy and the shared core has an explicit secondary route.",
    )
    record(
        "immutable-version-route-template",
        "AIMWORKS/v$1/ontology_release/output/ontology/h2kg-v2-taxonomy.ttl" in w3id_text,
        "The semantic-version route targets immutable Git tags.",
    )

    citation = _citation_checks(output_root.parent, profile)
    for row in citation:
        record(row["id"], row["passed"], row["detail"])

    live_checks: list[dict[str, Any]] = []
    if check_live_urls:
        live_checks = _live_url_checks(profile)
        for row in live_checks:
            record(row["id"], row["passed"], row["detail"], blocking=require_live_urls)

    blocking_failures = [row for row in checks if row["blocking"] and not row["passed"]]
    pre_release_ready = not blocking_failures
    submission_ready = pre_release_ready and bool(live_checks) and all(row["passed"] for row in live_checks)
    generated_at = datetime.now(timezone.utc).isoformat()
    report = {
        "schema_version": "h2kg-tib-submission-validation/v1",
        "generated_at": generated_at,
        "ontology_iri": str(H2KG_ONTOLOGY),
        "version": str(profile.get("version", "")),
        "version_iri": version_iri,
        "canonical_turtle": str(taxonomy_ttl),
        "canonical_jsonld": str(taxonomy_jsonld),
        "tib_shape": {
            **lock,
            "local_path": str(shape_path),
            "actual_sha256": shape_sha256,
            "mandatory_result_count": len(mandatory_results),
            "recommendation_result_count": len(info_results),
            "results": shape_results,
            "report_text": str(shacl_report_text),
        },
        "counts": counts,
        "serialization_parity": serialization_parity,
        "checks": checks,
        "blocking_failure_count": len(blocking_failures),
        "pre_release_ready": pre_release_ready,
        "live_url_checks_executed": check_live_urls,
        "submission_ready": submission_ready,
    }
    report_json = reports_dir / "tib_submission_validation.json"
    report_md = reports_dir / "tib_submission_validation.md"
    write_text(report_json, json.dumps(report, indent=2, ensure_ascii=False))
    write_text(report_md, _validation_markdown(report))

    manifest = {
        "schema_version": "h2kg-tib-submission-manifest/v1",
        "generated_at": generated_at,
        "submission_status": "ready" if submission_ready else "pre_release_ready" if pre_release_ready else "blocked",
        "pre_release_ready": pre_release_ready,
        "live_url_checks_executed": check_live_urls,
        "submission_ready": submission_ready,
        "blocking_checks": [
            {"id": row["id"], "detail": row["detail"]}
            for row in blocking_failures
        ],
        "ontology_title": str(profile.get("title", "")),
        "ontology_iri": str(H2KG_ONTOLOGY),
        "version": str(profile.get("version", "")),
        "version_iri": version_iri,
        "preferred_prefix": str(profile.get("namespace_prefix", "")),
        "preferred_namespace": str(profile.get("namespace_uri", "")),
        "canonical_turtle_url": str(profile.get("distributions", {}).get("turtle", "")),
        "canonical_jsonld_url": str(profile.get("distributions", {}).get("jsonld", "")),
        "license": str(profile.get("license", "")),
        "created": str(profile.get("created", "")),
        "modified": str(profile.get("modified", "")),
        "abstract": str(profile.get("abstract", "")),
        "documentation_url": str(profile.get("documentation_url", "")),
        "issue_tracker_url": str(profile.get("issue_tracker_url", "")),
        "attribution": [
            {
                "role": role,
                **{
                    key: row[key]
                    for key in (
                        "label",
                        "iri",
                        "kind",
                        "contribution_order",
                        "affiliation_ids",
                        "identifier_type",
                        "orcid_status",
                    )
                    if key in row
                },
            }
            for role, rows in (
                ("creator", profile.get("creators", [])),
                ("contributor", profile.get("contributors", [])),
            )
            for row in rows
        ],
        "affiliations": profile.get("affiliations", {}),
        "counts": counts,
        "collections": {
            "primary": "NFDI4Cat",
            "additional": ["NFDI4Ing", "NFDI4Energy"],
        },
        "declared_imports": sorted(imports),
        "expected_ingestion_checks": [
            "One ontology record with the configured title and prefix.",
            "Five explicit hierarchy roots.",
            f"{expected.get('total_classes', 0)} class records, including {expected.get('deprecated_classes', 0)} deprecated classes.",
            f"{expected.get('object_properties', 0)} object, {expected.get('datatype_properties', 0)} datatype, and {expected.get('annotation_properties', 0)} annotation properties.",
            "Deprecated terms remain resolvable and are marked deprecated.",
            "QUDT and PROV-O imports are separated from native H2KG records.",
            "Downloads, search, hierarchy navigation, and API retrieval are operational.",
        ],
        "validation_report": report_json.name,
    }
    manifest_json = reports_dir / "tib_submission_manifest.json"
    manifest_md = reports_dir / "tib_submission_manifest.md"
    write_text(manifest_json, json.dumps(manifest, indent=2, ensure_ascii=False))
    write_text(manifest_md, _manifest_markdown(manifest))

    if not pre_release_ready:
        raise ValueError(
            "TIB submission preflight failed: "
            + "; ".join(f"{row['id']}: {row['detail']}" for row in blocking_failures[:10])
        )
    return {
        "pre_release_ready": pre_release_ready,
        "submission_ready": submission_ready,
        "validation_json": str(report_json),
        "validation_markdown": str(report_md),
        "manifest_json": str(manifest_json),
        "manifest_markdown": str(manifest_md),
        "counts": counts,
        "mandatory_warning_count": len(mandatory_results),
        "recommendation_count": len(info_results),
    }


def _shape_results(report_graph: Graph) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for result in report_graph.subjects(RDF.type, SH.ValidationResult):
        rows.append(
            {
                "severity": str(report_graph.value(result, SH.resultSeverity) or ""),
                "focus_node": str(report_graph.value(result, SH.focusNode) or ""),
                "path": str(report_graph.value(result, SH.resultPath) or ""),
                "name": str(report_graph.value(result, SH.sourceShape) or ""),
                "message": str(report_graph.value(result, SH.resultMessage) or "").strip(),
            }
        )
    return sorted(rows, key=lambda row: (row["severity"], row["path"], row["message"]))


def _ontology_counts(graph: Graph) -> dict[str, int]:
    classes = {
        subject
        for subject in graph.subjects(RDF.type, OWL.Class)
        if isinstance(subject, URIRef) and str(subject).startswith(str(H2KG))
    }
    deprecated = {
        subject
        for subject in classes
        if any(_literal_true(value) for value in graph.objects(subject, OWL.deprecated))
    }
    named_individuals = {
        subject
        for subject in graph.subjects(RDF.type, OWL.NamedIndividual)
        if isinstance(subject, URIRef) and str(subject).startswith(str(H2KG))
    }
    return {
        "active_classes": len(classes - deprecated),
        "deprecated_classes": len(deprecated),
        "total_classes": len(classes),
        "object_properties": len(
            {
                subject
                for subject in graph.subjects(RDF.type, OWL.ObjectProperty)
                if isinstance(subject, URIRef) and str(subject).startswith(str(H2KG))
            }
        ),
        "datatype_properties": len(
            {
                subject
                for subject in graph.subjects(RDF.type, OWL.DatatypeProperty)
                if isinstance(subject, URIRef) and str(subject).startswith(str(H2KG))
            }
        ),
        "annotation_properties": len(
            {
                subject
                for subject in graph.subjects(RDF.type, OWL.AnnotationProperty)
                if isinstance(subject, URIRef) and str(subject).startswith(str(H2KG))
            }
        ),
        "taxonomy_individuals": len(named_individuals),
    }


def _literal_true(value: Any) -> bool:
    if isinstance(value, Literal):
        converted = value.toPython()
        return converted is True or str(converted).casefold() == "true"
    return str(value).casefold() == "true"


def _literal_value(graph: Graph, predicate: URIRef) -> str:
    return str(graph.value(H2KG_ONTOLOGY, predicate) or "")


def _typed_date_matches(graph: Graph, predicate: URIRef, expected: str) -> bool:
    value = graph.value(H2KG_ONTOLOGY, predicate)
    return isinstance(value, Literal) and value.datatype == XSD.date and str(value) == expected


def _citation_checks(project_root: Path, profile: dict[str, Any]) -> list[dict[str, Any]]:
    cff = yaml.safe_load((project_root / "CITATION.cff").read_text(encoding="utf-8")) or {}
    zenodo = json.loads((project_root / ".zenodo.json").read_text(encoding="utf-8"))
    version = str(profile.get("version", ""))
    title = str(profile.get("title", ""))
    expected_names = sorted(
        str(row.get("label", ""))
        for row in [*profile.get("creators", []), *profile.get("contributors", [])]
    )
    cff_names = sorted(
        str(row.get("name") or " ".join(filter(None, [row.get("given-names"), row.get("family-names")]))).strip()
        for row in cff.get("authors", [])
    )
    zenodo_names = sorted(
        _display_name_from_zenodo(str(row.get("name", "")))
        for row in [*zenodo.get("creators", []), *zenodo.get("contributors", [])]
    )
    return [
        {
            "id": "citation-cff-version",
            "passed": str(cff.get("version", "")) == version,
            "detail": f"CITATION.cff version: {cff.get('version', '')}.",
        },
        {
            "id": "citation-cff-title",
            "passed": str(cff.get("title", "")) == title,
            "detail": f"CITATION.cff title: {cff.get('title', '')}.",
        },
        {
            "id": "zenodo-version",
            "passed": str(zenodo.get("version", "")) == version,
            "detail": f"Zenodo version: {zenodo.get('version', '')}.",
        },
        {
            "id": "zenodo-title",
            "passed": str(zenodo.get("title", "")) == title,
            "detail": f"Zenodo title: {zenodo.get('title', '')}.",
        },
        {
            "id": "citation-cff-attribution",
            "passed": cff_names == expected_names,
            "detail": f"CITATION.cff attribution records: {len(cff_names)}.",
        },
        {
            "id": "zenodo-attribution",
            "passed": zenodo_names == expected_names,
            "detail": f"Zenodo attribution records: {len(zenodo_names)}.",
        },
    ]


def _display_name_from_zenodo(value: str) -> str:
    if "," not in value:
        return value.strip()
    family, given = value.split(",", 1)
    return f"{given.strip()} {family.strip()}".strip()


def _live_url_checks(profile: dict[str, Any]) -> list[dict[str, Any]]:
    targets = {
        "live-documentation": str(profile.get("documentation_url", "")),
        "live-issue-tracker": str(profile.get("issue_tracker_url", "")),
        "live-canonical-turtle": str(profile.get("distributions", {}).get("turtle", "")),
        "live-canonical-jsonld": str(profile.get("distributions", {}).get("jsonld", "")),
        "live-version-iri": str(profile.get("version_iri", "")),
    }
    for index, row in enumerate([*profile.get("creators", []), *profile.get("contributors", [])], start=1):
        targets[f"live-attribution-pid-{index}"] = str(row.get("iri", ""))
    rows: list[dict[str, Any]] = []
    for identifier, url in targets.items():
        passed, detail = _resolve_public_url(identifier, url)
        rows.append({"id": identifier, "passed": passed, "detail": detail})
    return rows


def _resolve_public_url(identifier: str, url: str) -> tuple[bool, str]:
    if not url:
        return False, f"No URL configured for {identifier}."
    headers = {
        "User-Agent": "H2KG-TIB-release-validation/2.3.1 (+https://github.com/ViMiLabs/AIMWORKS)"
    }
    status: int | None = None
    detail = ""
    try:
        response = requests.get(
            url,
            timeout=20,
            allow_redirects=True,
            stream=True,
            headers=headers,
        )
        status = response.status_code
        passed = 200 <= response.status_code < 400
        detail = f"{url} returned HTTP {response.status_code}; final URL {response.url}."
        response.close()
        if passed:
            return True, detail
    except requests.RequestException as exc:
        detail = f"{url} could not be resolved: {exc}"

    # The public ROR resolver rate-limits automated clients. The official API
    # provides an authoritative registry check without weakening PID validation.
    if ROR_PATTERN.fullmatch(url):
        ror_id = url.rstrip("/").rsplit("/", 1)[-1]
        registry_url = f"https://api.ror.org/v2/organizations/{ror_id}"
        try:
            response = requests.get(
                registry_url,
                timeout=20,
                allow_redirects=True,
                stream=True,
                headers=headers,
            )
            registry_status = response.status_code
            response.close()
            if 200 <= registry_status < 400:
                resolver_status = f"HTTP {status}" if status is not None else "unavailable"
                return (
                    True,
                    f"{url} was verified through the official ROR registry API "
                    f"({registry_url}, HTTP {registry_status}); resolver endpoint {resolver_status}.",
                )
            detail += f" Official ROR registry API returned HTTP {registry_status}."
        except requests.RequestException as exc:
            detail += f" Official ROR registry API could not be resolved: {exc}"
    return False, detail


def _validation_markdown(report: dict[str, Any]) -> str:
    rows = "\n".join(
        f"| `{row['id']}` | {'PASS' if row['passed'] else 'FAIL'} | {'yes' if row['blocking'] else 'no'} | {row['detail'].replace('|', '/')} |"
        for row in report["checks"]
    )
    return f"""# H2KG {report['version']} TIB Submission Validation

- Pre-release ready: **{report['pre_release_ready']}**
- Submission ready: **{report['submission_ready']}**
- TIB mandatory warnings/violations: **{report['tib_shape']['mandatory_result_count']}**
- TIB recommendation notices: **{report['tib_shape']['recommendation_result_count']}**
- Canonical serialization parity: **{report['serialization_parity']}**

| Check | Result | Blocking | Evidence |
|---|---|---|---|
{rows}
"""


def _manifest_markdown(manifest: dict[str, Any]) -> str:
    counts = manifest["counts"]
    checks = "\n".join(f"- {value}" for value in manifest["expected_ingestion_checks"])
    blockers = manifest.get("blocking_checks", [])
    blocker_text = "\n".join(
        f"- `{row['id']}`: {row['detail']}"
        for row in blockers
    ) or "- None."
    attribution_text = "\n".join(
        f"- **{row['role'].title()}:** [{row['label']}]({row['iri']})"
        + (
            f"; affiliations {', '.join(map(str, row.get('affiliation_ids', [])))}"
            if row.get("affiliation_ids")
            else ""
        )
        + (
            "; ORCID unavailable, verified institutional profile used"
            if row.get("orcid_status") == "unavailable"
            else ""
        )
        for row in manifest.get("attribution", [])
    ) or "- See canonical ontology metadata."
    affiliation_text = "\n".join(
        f"- `{identifier}`: {record.get('label', '')}"
        for identifier, record in manifest.get("affiliations", {}).items()
    ) or "- None recorded."
    return f"""# H2KG {manifest['version']} TIB Submission Manifest

- Status: **{manifest['submission_status']}**
- Ontology IRI: `{manifest['ontology_iri']}`
- Version IRI: `{manifest['version_iri']}`
- Prefix: `{manifest['preferred_prefix']}`
- Canonical Turtle: {manifest['canonical_turtle_url']}
- Canonical JSON-LD: {manifest['canonical_jsonld_url']}
- Classes: {counts['active_classes']} active + {counts['deprecated_classes']} deprecated = {counts['total_classes']} total
- Properties: {counts['object_properties']} object, {counts['datatype_properties']} datatype, {counts['annotation_properties']} annotation
- Requested collections: NFDI4Cat (primary), NFDI4Ing and NFDI4Energy (additional)

## Attribution

{attribution_text}

### Affiliations

{affiliation_text}

## Publication blockers

{blocker_text}

## Expected ingestion checks

{checks}
"""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()
