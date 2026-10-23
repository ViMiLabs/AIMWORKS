from __future__ import annotations

"""Build a local, source-controlled H2KG--CHAMEO KG comparison.

The CHAMEO graph is constructed independently from the sanitized workbook
manifest.  It is not translated from the H2KG graph.  The two representations
are evaluated with the same questions and manifest-derived expected rows.
"""

import csv
import hashlib
import html
import json
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from pyshacl import validate as shacl_validate
from rdflib import BNode, Dataset, Graph, Literal, Namespace, RDF, RDFS, SKOS, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import DCTERMS, OWL, PROV, SH, XSD
from rdflib.plugins.sparql.algebra import translateQuery
from rdflib.plugins.sparql.parser import parseQuery
from rdflib.plugins.sparql.parserutils import CompValue

from .characterization_kg import (
    CASE_BY_KEY,
    CASE_SPECS,
    EXPECTED_WORKBOOK_SHA256,
    MANIFEST_SCHEMA,
    PROPERTY_FIELDS,
    SOURCE_STATUSES,
    _compare_query_rows,
    _condition_pairs,
    _direct_lookup,
    _field_key,
    _ground_truth_rows,
    _literal_raw,
    _norm_label,
    _paired_direct_units,
    _parse_quantity,
    _query_specs,
    _raw_lexical,
    _semantic_conflict,
    _slug,
    _split_software,
    _with_implicit_quantity_kind,
    _write_csv,
)
from .utils import COMMON_CONTEXT, dump_json, ensure_dir, now_iso, write_text


CHAMEO = Namespace("https://w3id.org/emmo/domain/characterisation-methodology/chameo#")
EMMO = Namespace("https://w3id.org/emmo#")
QUDT = Namespace(COMMON_CONTEXT["qudt"])
UNIT = Namespace(COMMON_CONTEXT["unit"])
QK = Namespace(COMMON_CONTEXT["quantitykind"])
APP = Namespace("https://example.org/aimworks/chameo-characterization/schema#")
CMP = Namespace("https://example.org/aimworks/chameo-characterization/")
CGRAPH = Namespace("https://example.org/aimworks/chameo-characterization/graph/")

BUILD_SCHEMA = "h2kg-chameo-characterization-comparison/v2"
CHAMEO_VERSION = "1.0.3"
CHAMEO_COMMIT = "01520fd7bc6f76ec5ff32a051533326a198c499c"
CHAMEO_SHA256 = "2DBC2048B0BCAFBE850A8F7D54521B34F81AB009F7BE4C8EBBA56449D6D0C247"
EMMO_VERSION = "1.0.3"
EMMO_COMMIT = "b85a0803c47819fc4b53b9c9fd6c61878f714c5b"
H2KG_NAMESPACE = "https://w3id.org/h2kg/hydrogen-ontology#"

EMMO_HAS_INPUT = EMMO.EMMO_36e69413_8c59_4799_946c_10b05d266e22
EMMO_HAS_OUTPUT = EMMO.EMMO_c4bace1d_4db0_4cd3_87e9_18122bae2840
EMMO_HAS_PROPERTY = EMMO.EMMO_e1097637_70d2_4895_973f_2396f04fa204
EMMO_HAS_QUANTITY_VALUE = EMMO.EMMO_88b84515_a0df_47bb_8166_c7c8b893c1d8
EMMO_IS_DESCRIPTION_FOR = EMMO.EMMO_f702bad4_fc77_41f0_a26d_79f6444fd4f3
EMMO_DETERMINATION = EMMO.EMMO_10a5fd39_06aa_4648_9e70_f962a9cb2069
EMMO_HAS_DETERMINED_PROPERTY = EMMO.EMMO_802b7639_9498_4b47_ad45_1a087fe8fb85

DIRECT_IMPORT_PATHS = {
    "https://w3id.org/emmo/1.0.3/disciplines/computerscience": "disciplines/computerscience.ttl",
    "https://w3id.org/emmo/1.0.3/disciplines/isq": "disciplines/isq.ttl",
    "https://w3id.org/emmo/1.0.3/disciplines/manufacturing": "disciplines/manufacturing.ttl",
    "https://w3id.org/emmo/1.0.3/disciplines/math": "disciplines/math.ttl",
    "https://w3id.org/emmo/1.0.3/disciplines/metrology": "disciplines/metrology.ttl",
    "https://w3id.org/emmo/1.0.3/disciplines/models": "disciplines/models.ttl",
    "https://w3id.org/emmo/1.0.3/perspectives/holistic": "perspectives/holistic.ttl",
    "https://w3id.org/emmo/1.0.3/perspectives/persistence": "perspectives/persistence.ttl",
    "https://w3id.org/emmo/1.0.3/perspectives/semiotics": "perspectives/semiotics.ttl",
    "https://w3id.org/emmo/1.0.3/reference/data": "reference/data.ttl",
    "https://w3id.org/emmo/1.0.3/reference/persholistic": "reference/persholistic.ttl",
    "https://w3id.org/emmo/1.0.3/reference/workflow": "reference/workflow.ttl",
}

CASE_TECHNIQUES: dict[str, tuple[str, ...]] = {
    "tem": ("TransmissionElectronMicroscopy",),
    "sem": ("ScanningElectronMicroscopy",),
    "afm": ("AtomicForceMicroscopy",),
    "fib_sem": ("Tomography", "ScanningElectronMicroscopy"),
    "ic_sem": ("ScanningElectronMicroscopy",),
    "neutron_tomography": ("Tomography",),
    # The sheet key says radiography, but its reported MeasurementMethod,
    # publication title, 3D reconstruction, and outputs identify tomography.
    "synchrotron_radiography": ("Tomography",),
    "synchrotron_tomography": ("Tomography",),
}

REPRESENTATION_TIERS = {
    "native_specific",
    "native_generic",
    "declared_import",
    "shared_standard",
    "application_extension",
    "source_only",
}

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _git_commit(path: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _bind(graph: Graph | Dataset) -> None:
    for prefix, namespace in {
        "chameo": CHAMEO,
        "emmo": EMMO,
        "app": APP,
        "cmp": CMP,
        "qudt": QUDT,
        "unit": UNIT,
        "quantitykind": QK,
        "prov": PROV,
        "dcterms": DCTERMS,
        "skos": SKOS,
        "sh": SH,
    }.items():
        graph.bind(prefix, namespace)


def _iri(case_key: str, kind: str, label: Any, suffix: str = "") -> URIRef:
    seed = f"{case_key}|{kind}|{label}|{suffix}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:10]
    return URIRef(f"{CMP}{case_key}/{kind}/{_slug(label)}-{digest}")


def _case_iri(case_key: str) -> URIRef:
    return URIRef(f"{CMP}case/{case_key}")


def _source_record_iri(record_id: str) -> URIRef:
    return URIRef(f"{CMP}source/{record_id}")


def _graph_iri(layer: str, case_key: str | None = None) -> URIRef:
    return URIRef(f"{CGRAPH}{layer}" + (f"/{case_key}" if case_key else ""))


def _safe_replace_dir(path: Path, allowed_parent: Path) -> None:
    resolved = path.resolve()
    parent = allowed_parent.resolve()
    if resolved == parent or parent not in resolved.parents:
        raise ValueError(f"Refusing to replace output outside {parent}: {resolved}")
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _source_lock(chameo_root: Path, emmo_root: Path) -> tuple[dict[str, Any], Graph]:
    chameo_path = chameo_root / "chameo.ttl"
    if not chameo_path.exists():
        raise FileNotFoundError(f"Pinned CHAMEO source is missing: {chameo_path}")
    chameo_commit = _git_commit(chameo_root)
    emmo_commit = _git_commit(emmo_root)
    if chameo_commit != CHAMEO_COMMIT:
        raise ValueError(f"CHAMEO commit mismatch: {chameo_commit}")
    if emmo_commit != EMMO_COMMIT:
        raise ValueError(f"EMMO commit mismatch: {emmo_commit}")
    chameo_hash = _sha256(chameo_path)
    if chameo_hash != CHAMEO_SHA256:
        raise ValueError(f"CHAMEO SHA-256 mismatch: {chameo_hash}")

    chameo_graph = Graph().parse(chameo_path, format="turtle")
    ontology = URIRef("https://w3id.org/emmo/domain/characterisation-methodology/chameo")
    version = str(next(chameo_graph.objects(ontology, OWL.versionInfo), ""))
    if version != CHAMEO_VERSION:
        raise ValueError(f"CHAMEO version mismatch: {version}")
    imports = {str(value) for value in chameo_graph.objects(ontology, OWL.imports)}
    if imports != set(DIRECT_IMPORT_PATHS):
        raise ValueError("CHAMEO direct-import closure differs from the pinned 1.0.3 contract.")

    files: list[dict[str, Any]] = [{
        "kind": "ontology",
        "ontology_iri": str(ontology),
        "version_iri": "https://w3id.org/emmo/domain/characterisation-methodology/1.0.3/chameo",
        "import_depth": 0,
        "version": CHAMEO_VERSION,
        "git_commit": chameo_commit,
        "relative_path": "chameo.ttl",
        "sha256": chameo_hash,
        "license": "https://creativecommons.org/licenses/by/4.0/legalcode",
    }]
    import_graph = Graph()
    pending = [(import_iri, 1) for import_iri in sorted(imports)]
    resolved_imports: set[str] = set()
    while pending:
        import_iri, depth = pending.pop(0)
        if import_iri in resolved_imports:
            continue
        resolved_imports.add(import_iri)
        version_prefix = f"https://w3id.org/emmo/{EMMO_VERSION}/"
        if not import_iri.startswith(version_prefix):
            raise ValueError(f"Unversioned or foreign EMMO import in pinned closure: {import_iri}")
        relative = f"{import_iri.removeprefix(version_prefix)}.ttl"
        path = emmo_root / relative
        if not path.exists():
            raise FileNotFoundError(f"Declared EMMO import-closure member is missing: {path}")
        parsed = Graph().parse(path, format="turtle")
        ontology_nodes = list(parsed.subjects(RDF.type, OWL.Ontology))
        matching_nodes = [
            node for node in ontology_nodes
            if str(node) == import_iri or import_iri in {str(value) for value in parsed.objects(node, OWL.versionIRI)}
        ]
        if len(matching_nodes) != 1:
            raise ValueError(f"Import IRI does not identify exactly one ontology in {path}: {import_iri}")
        imported_ontology = matching_nodes[0]
        nested_imports = sorted(str(value) for value in parsed.objects(imported_ontology, OWL.imports))
        pending.extend((value, depth + 1) for value in nested_imports if value not in resolved_imports)
        for triple in parsed:
            import_graph.add(triple)
        files.append({
            "kind": "direct_import" if depth == 1 else "transitive_import",
            "ontology_iri": str(imported_ontology),
            "version_iri": import_iri,
            "import_depth": depth,
            "version": EMMO_VERSION,
            "git_commit": emmo_commit,
            "relative_path": relative.replace("\\", "/"),
            "sha256": _sha256(path),
            "license": "https://creativecommons.org/licenses/by/4.0/legalcode",
        })
    lock_fingerprint = hashlib.sha256(
        "\n".join(f"{item['ontology_iri']}|{item['sha256']}" for item in files).encode("utf-8")
    ).hexdigest().upper()
    return {
        "schema_version": "chameo-emmo-source-lock/v2",
        "generated_at": now_iso(),
        "network_required_for_build": False,
        "chameo_version": CHAMEO_VERSION,
        "chameo_commit": chameo_commit,
        "emmo_version": EMMO_VERSION,
        "emmo_commit": emmo_commit,
        "direct_import_count": len(DIRECT_IMPORT_PATHS),
        "transitive_import_count": len(resolved_imports) - len(DIRECT_IMPORT_PATHS),
        "resolved_import_count": len(resolved_imports),
        "complete_import_closure": True,
        "lock_fingerprint": lock_fingerprint,
        "files": files,
    }, chameo_graph + import_graph


def _add_local_schema(graph: Graph) -> None:
    classes = (
        (APP.SourceField, "Source field"),
        (APP.ValidationFinding, "Validation finding"),
        (APP.WorkbookSnapshot, "Workbook snapshot"),
        (APP.CharacterizationCase, "Characterization case"),
    )
    for subject, label in classes:
        graph.add((subject, RDF.type, OWL.Class))
        graph.add((subject, RDFS.label, Literal(label)))
        graph.add((subject, APP.representationTier, Literal("application_extension")))
    properties = (
        (APP.sourceSheet, "source sheet"),
        (APP.sourceSection, "source section"),
        (APP.sourceCell, "source cell"),
        (APP.fieldName, "field name"),
        (APP.valueStatus, "value status"),
        (APP.mappedEntity, "mapped entity"),
        (APP.case, "case"),
        (APP.findingCode, "finding code"),
        (APP.severity, "severity"),
        (APP.mappingRationale, "mapping rationale"),
        (APP.sourceUnit, "source unit"),
        (APP.valueQualifier, "value qualifier"),
        (APP.describesCharacteristic, "describes characteristic"),
        (APP.reportsProperty, "reports property"),
        (APP.isResultOfMeasurement, "is result of measurement"),
        (APP.representationTier, "representation tier"),
    )
    for subject, label in properties:
        graph.add((subject, RDF.type, OWL.AnnotationProperty if subject not in {
            APP.describesCharacteristic, APP.reportsProperty, APP.isResultOfMeasurement, APP.case, APP.mappedEntity
        } else OWL.ObjectProperty))
        graph.add((subject, RDFS.label, Literal(label)))
    for status in (*SOURCE_STATUSES, "unit_unresolved"):
        iri = APP[status]
        graph.add((iri, RDF.type, SKOS.Concept))
        graph.add((iri, SKOS.prefLabel, Literal(status.replace("_", " "))))


def _add_source_records(
    graph: Graph,
    case: dict[str, Any],
    workbook: URIRef,
) -> dict[str, URIRef]:
    records: dict[str, URIRef] = {}
    for record in case["source_records"]:
        subject = _source_record_iri(record["record_id"])
        records[record["record_id"]] = subject
        graph.add((subject, RDF.type, APP.SourceField))
        graph.add((subject, DCTERMS.identifier, Literal(record["record_id"])))
        graph.add((subject, RDFS.label, Literal(f"{record['field']} ({record['cell']})")))
        graph.add((subject, APP.sourceSheet, Literal(record["sheet"])))
        graph.add((subject, APP.sourceSection, Literal(record["section"])))
        graph.add((subject, APP.sourceCell, Literal(record["cell"])))
        graph.add((subject, APP.fieldName, Literal(record["field"])))
        graph.add((subject, APP.valueStatus, APP[str(record["status"])]))
        graph.add((subject, PROV.wasDerivedFrom, workbook))
        if record.get("raw_value") is not None:
            graph.add((subject, RDF.value, _literal_raw(record["raw_value"])))
        if record.get("conflict"):
            graph.add((subject, DCTERMS.description, Literal(record["conflict"])))
    return records


def _link_source(graph: Graph, entity: URIRef, source: URIRef) -> None:
    graph.add((entity, PROV.wasDerivedFrom, source))
    graph.add((source, APP.mappedEntity, entity))


def _entity(
    graph: Graph,
    cache: dict[tuple[str, str], URIRef],
    case_key: str,
    label: Any,
    kind: str,
    specific_type: URIRef | None = None,
) -> URIRef:
    normalized = _norm_label(label) or "unspecified"
    key = (kind, normalized)
    if key in cache:
        return cache[key]
    subject = _iri(case_key, kind, normalized)
    cache[key] = subject
    generic = CHAMEO.Sample if kind == "sample" else CHAMEO.CharacterisationData
    graph.add((subject, RDF.type, generic))
    if specific_type:
        graph.add((subject, RDF.type, specific_type))
    graph.add((subject, RDFS.label, Literal(str(label or "Unspecified source entity").strip())))
    graph.add((subject, APP.case, _case_iri(case_key)))
    return subject


def _dataset_type(label: Any, *, raw: bool = False) -> URIRef:
    if raw or _norm_label(label) in {"rawdata", "raw data"} or _norm_label(label).startswith("raw "):
        return CHAMEO.RawData
    return CHAMEO.PrimaryData


def _add_quantity(
    graph: Graph,
    bearer: URIRef,
    quantity: dict[str, Any] | None,
    case_key: str,
    seed: str,
) -> URIRef | None:
    if not quantity or quantity.get("unit") is None or quantity.get("quantity_kind") is None:
        return None
    qv = _iri(case_key, "quantity-value", seed)
    graph.add((qv, RDF.type, QUDT.QuantityValue))
    graph.add((qv, QUDT.numericValue, Literal(quantity["numeric"], datatype=XSD.decimal)))
    graph.add((qv, QUDT.unit, quantity["unit"]))
    graph.add((qv, QUDT.quantityKind, quantity["quantity_kind"]))
    unit_label = str(quantity.get("source_unit") or str(quantity["unit"]).rsplit("/", 1)[-1])
    graph.add((qv, RDFS.label, Literal(f"{quantity['numeric']} {unit_label}".strip())))
    if quantity.get("qualifier"):
        graph.add((qv, APP.valueQualifier, Literal(quantity["qualifier"])))
    graph.add((bearer, EMMO_HAS_QUANTITY_VALUE, qv))
    return qv


def _add_parameter(
    graph: Graph,
    owner: URIRef,
    case_key: str,
    label: str,
    raw: Any,
    status: str,
    source: URIRef,
    unit: Any = None,
    suffix: str = "",
    *,
    include_application_bridges: bool = True,
) -> dict[str, Any]:
    parameter = _iri(case_key, "measurement-parameter", label, suffix)
    graph.add((owner, CHAMEO.hasMeasurementParameter, parameter))
    graph.add((parameter, RDF.type, CHAMEO.MeasurementParameter))
    graph.add((parameter, RDFS.label, Literal(f"{label} parameter record")))
    _link_source(graph, parameter, source)
    characteristic = None
    qv = None
    parsed = _with_implicit_quantity_kind(_parse_quantity(raw, unit), label)
    if include_application_bridges:
        characteristic = _iri(case_key, "parameter-characteristic", label, suffix)
        graph.add((parameter, APP.describesCharacteristic, characteristic))
        graph.add((parameter, APP.valueStatus, APP[status]))
        graph.add((characteristic, RDF.type, CHAMEO.CharacterisationProperty))
        graph.add((characteristic, RDFS.label, Literal(label)))
        graph.add((owner, EMMO_HAS_PROPERTY, characteristic))
        _link_source(graph, characteristic, source)
        qv = _add_quantity(
            graph,
            characteristic,
            parsed if status == "reported" else None,
            case_key,
            f"{label}|{suffix}",
        )
    return {
        "parameter": parameter,
        "characteristic": characteristic,
        "quantity": qv,
        "unit_status": (
            "not_asserted_without_native_link"
            if not include_application_bridges
            else ("mapped" if qv else ("not_numeric" if parsed is None else "unit_unresolved"))
        ),
    }


def _add_finding(
    graph: Graph,
    case_key: str,
    code: str,
    message: str,
    source: URIRef | None,
    entity: URIRef | None,
    severity: str = "warning",
) -> URIRef:
    finding = _iri(case_key, "finding", code, str(source or entity or message))
    graph.add((finding, RDF.type, APP.ValidationFinding))
    graph.add((finding, APP.findingCode, Literal(code)))
    graph.add((finding, APP.severity, Literal(severity)))
    graph.add((finding, DCTERMS.description, Literal(message)))
    graph.add((finding, APP.case, _case_iri(case_key)))
    if source:
        graph.add((finding, PROV.wasDerivedFrom, source))
    if entity:
        graph.add((finding, DCTERMS.subject, entity))
    return finding


def _mapping_row(
    record: dict[str, Any],
    entity: URIRef,
    outcome: str,
    category: str,
    tier: str,
    native_iri: URIRef | None = None,
    rationale: str = "",
    supporting_tiers: Iterable[str] = (),
) -> dict[str, Any]:
    if tier not in REPRESENTATION_TIERS:
        raise ValueError(f"Unknown representation tier: {tier}")
    supporting = sorted(set(supporting_tiers))
    if any(item not in REPRESENTATION_TIERS for item in supporting):
        raise ValueError(f"Unknown supporting representation tier: {supporting}")
    return {
        **record,
        "linked_entity": str(entity),
        "mapping_outcome": outcome,
        "semantic_category": category,
        "representation_tier": tier,
        "supporting_tiers": ";".join(supporting),
        "native_ontology_iri": str(native_iri or ""),
        "mapping_rationale": rationale,
    }


def _task_descriptor(graph: Graph, workflow: URIRef, process: URIRef, case_key: str, label: str, suffix: str) -> URIRef:
    task = _iri(case_key, "task-description", label, suffix)
    graph.add((task, RDF.type, CHAMEO.CharacterisationTask))
    graph.add((task, RDFS.label, Literal(f"{label} task")))
    graph.add((workflow, CHAMEO.hasCharacterisationTask, task))
    graph.add((task, EMMO_IS_DESCRIPTION_FOR, process))
    return task


def _build_case(
    dataset: Dataset,
    case: dict[str, Any],
    workbook: URIRef,
    *,
    include_application_bridges: bool = True,
) -> dict[str, Any]:
    spec = CASE_BY_KEY[case["key"]]
    source_graph = dataset.graph(_graph_iri("source", spec.key))
    semantic_graph = dataset.graph(_graph_iri("semantic", spec.key))
    validation_graph = dataset.graph(_graph_iri("validation", spec.key))
    for graph in (source_graph, semantic_graph, validation_graph):
        _bind(graph)
    record_iris = _add_source_records(source_graph, case, workbook)
    mapping_by_record: dict[str, dict[str, Any]] = {}
    case_iri = _case_iri(spec.key)
    semantic_graph.add((case_iri, RDF.type, APP.CharacterizationCase))
    semantic_graph.add((case_iri, RDFS.label, Literal(spec.title)))
    semantic_graph.add((case_iri, DCTERMS.identifier, Literal(spec.key)))

    workflow = _iri(spec.key, "workflow", spec.title)
    measurement = _iri(spec.key, "measurement", spec.title)
    instrument = _iri(spec.key, "instrument", spec.title)
    technique = _iri(spec.key, "technique-description", spec.title)
    semantic_graph.add((workflow, RDF.type, CHAMEO.CharacterisationWorkflow))
    semantic_graph.add((workflow, RDFS.label, Literal(f"{spec.title} characterization workflow")))
    semantic_graph.add((workflow, APP.case, case_iri))
    semantic_graph.add((measurement, RDF.type, CHAMEO.CharacterisationMeasurementProcess))
    semantic_graph.add((measurement, RDFS.label, Literal(f"{spec.title} measurement")))
    semantic_graph.add((measurement, APP.case, case_iri))
    semantic_graph.add((instrument, RDF.type, CHAMEO.CharacterisationMeasurementInstrument))
    semantic_graph.add((instrument, RDFS.label, Literal(f"{spec.title} instrument")))
    semantic_graph.add((instrument, APP.case, case_iri))
    semantic_graph.add((measurement, CHAMEO.hasCharacterisationMeasurementInstrument, instrument))
    for technique_class in CASE_TECHNIQUES[spec.key]:
        semantic_graph.add((technique, RDF.type, CHAMEO[technique_class]))
    semantic_graph.add((technique, RDFS.label, Literal(spec.title)))
    semantic_graph.add((technique, EMMO_IS_DESCRIPTION_FOR, measurement))
    _task_descriptor(semantic_graph, workflow, measurement, spec.key, f"{spec.title} measurement", "measurement")

    entities: dict[tuple[str, str], URIRef] = {}
    raw_dataset = _entity(semantic_graph, entities, spec.key, "RawData", "data", CHAMEO.RawData)
    semantic_graph.add((measurement, CHAMEO.hasCharacterisationOutput, raw_dataset))
    direct_lookup = _direct_lookup(case)
    units = _paired_direct_units(case)
    specimen_record = next((row for row in case["direct_fields"] if _field_key(row["field"]) == "specimen"), None)
    specimen_label = specimen_record.get("raw_value") if specimen_record else "Characterization specimen"
    specimen = _entity(semantic_graph, entities, spec.key, "Sample", "sample", CHAMEO.PreparedSample)
    semantic_graph.set((specimen, RDFS.label, Literal(str(specimen_label or "Characterization specimen"))))
    semantic_graph.add((measurement, CHAMEO.hasMeasurementSample, specimen))
    if specimen_record:
        source = record_iris[specimen_record["record_id"]]
        _link_source(semantic_graph, specimen, source)
        mapping_by_record[specimen_record["record_id"]] = _mapping_row(
            specimen_record,
            specimen,
            "sample_occurrence",
            "specimen",
            "native_generic",
            CHAMEO.Sample,
            "The source specimen is represented as a CHAMEO Sample occurrence.",
            ("shared_standard",),
        )

    dataset_metadata_fields = {
        "filename", "format", "filesize", "filesizeunit", "dimensionx", "dimensiony",
        "dimensionz", "pixelpermetric", "link", "maskexist", "masklink",
    }
    for record in case["direct_fields"]:
        source = record_iris[record["record_id"]]
        key = _field_key(record["field"])
        if record["section"] in {"char", "inst"} and key in PROPERTY_FIELDS and not key.endswith("unit"):
            result = _add_parameter(
                semantic_graph,
                measurement,
                spec.key,
                record["field"],
                record.get("raw_value"),
                record["status"],
                source,
                units.get(key),
                record["record_id"],
                include_application_bridges=include_application_bridges,
            )
            mapping_by_record[record["record_id"]] = _mapping_row(
                record,
                result["parameter"],
                "measurement_parameter" if include_application_bridges else "measurement_parameter_identity_only",
                "settings",
                "native_generic",
                CHAMEO.MeasurementParameter,
                (
                    "CHAMEO supplies the parameter record; an application relation identifies its characteristic and QUDT normalizes defensible values."
                    if include_application_bridges
                    else "CHAMEO supplies the parameter identity, but the strict graph does not assert a characteristic or value because the pinned closure has no defensible linking relation."
                ),
                (
                    ("application_extension", "declared_import", "shared_standard")
                    if include_application_bridges
                    else ("application_extension",)
                ),
            )
            if result["unit_status"] == "unit_unresolved" and record["status"] == "reported":
                _add_finding(
                    validation_graph,
                    spec.key,
                    "unit_unresolved",
                    f"{record['field']} retains its source unit without an invented normalization.",
                    source,
                    result["characteristic"],
                )
            continue

        target = measurement
        category = "measurement"
        native = CHAMEO.CharacterisationMeasurementProcess
        tier = "source_only"
        outcome = "measurement_metadata"
        if record["section"] == "inst":
            target = instrument
            category = "instrument"
            native = CHAMEO.CharacterisationMeasurementInstrument
            outcome = "instrument_metadata"
        elif record["section"] == "org" and key in dataset_metadata_fields:
            target = raw_dataset
            category = "datasets"
            native = CHAMEO.RawData
            outcome = "dataset_metadata"
        if key == "specimen":
            target = specimen
            category = "specimen"
            native = CHAMEO.Sample
            tier = "native_generic"
            outcome = "sample_occurrence"
        _link_source(semantic_graph, target, source)
        mapping_by_record.setdefault(
            record["record_id"],
            _mapping_row(
                record,
                target,
                outcome,
                category,
                tier,
                native if tier != "source_only" else None,
                "The field is retained as source metadata unless CHAMEO provides an explicit occurrence class.",
                ("shared_standard",),
            ),
        )

    analysis_rows: list[tuple[dict[str, Any], URIRef, URIRef]] = []
    stage_targets: dict[tuple[str, str, str], set[str]] = {}
    for candidate in case["table_rows"]:
        values = candidate["values"]
        stage = (candidate["section"], str(values.get("Step") or "").strip(), str(values.get("Technique") or "").strip())
        stage_targets.setdefault(stage, set()).add(_norm_label(values.get("Target")))

    for row in case["table_rows"]:
        section = row["section"]
        values = row["values"]
        process_label = values.get("Technique") or f"{section} step {values.get('Step', row['row'])}"
        stage = (section, str(values.get("Step") or "").strip(), str(values.get("Technique") or "").strip())
        can_group = bool(stage[1] and stage[2]) and (section == "anal" or len(stage_targets[stage]) == 1)
        suffix = "|".join(stage) if can_group else f"{'|'.join(stage)}|row:{row['row']}"
        process = _iri(spec.key, f"{section}-process", process_label, suffix)
        process_type = CHAMEO.SamplePreparation if section in {"syn", "sp"} else (
            CHAMEO.DataPreparation if section == "pre" else CHAMEO.DataAnalysis
        )
        semantic_graph.add((process, RDF.type, process_type))
        semantic_graph.add((process, RDFS.label, Literal(str(process_label))))
        semantic_graph.add((process, APP.case, case_iri))
        _task_descriptor(semantic_graph, workflow, process, spec.key, str(process_label), suffix)
        precursor = values.get("Precursor")
        target_label = values.get("Target")
        if section in {"syn", "sp"}:
            if precursor:
                input_entity = _entity(semantic_graph, entities, spec.key, precursor, "sample")
                semantic_graph.add((process, CHAMEO.hasSampleForPreparation, input_entity))
            if target_label:
                output_entity = specimen if _norm_label(target_label) == "sample" else _entity(
                    semantic_graph, entities, spec.key, target_label, "sample", CHAMEO.PreparedSample
                )
                semantic_graph.add((process, EMMO_HAS_OUTPUT, output_entity))
        else:
            input_entity = raw_dataset if _norm_label(precursor) in {"rawdata", "raw data"} else _entity(
                semantic_graph, entities, spec.key, precursor or "unspecified input data", "data", _dataset_type(precursor)
            )
            semantic_graph.add((process, CHAMEO.hasCharacterisationInput, input_entity))
            if section == "pre" and target_label:
                output_entity = _entity(semantic_graph, entities, spec.key, target_label, "data", _dataset_type(target_label))
                semantic_graph.add((process, CHAMEO.hasCharacterisationOutput, output_entity))
            elif section == "anal":
                analysis_rows.append((row, process, input_entity))

        for field, raw in values.items():
            record_id = row["record_ids"].get(field)
            if not record_id:
                continue
            record = next(item for item in case["source_records"] if item["record_id"] == record_id)
            source = record_iris[record_id]
            _link_source(semantic_graph, process, source)
            category = "preparation" if section in {"syn", "sp"} else ("processing" if section == "pre" else "results")
            tier = "native_specific" if field == "Software" and _split_software(raw) else "native_generic"
            native = CHAMEO.CharacterisationSoftware if tier == "native_specific" else process_type
            mapping_by_record[record_id] = _mapping_row(
                record,
                process,
                "process_field",
                category,
                tier,
                native,
                "The source row is represented with a CHAMEO procedure or data-analysis occurrence.",
                ("shared_standard",),
            )

        condition_id = row["record_ids"].get("Condition")
        if condition_id:
            condition_source = record_iris[condition_id]
            for index, (name, value) in enumerate(_condition_pairs(values.get("Condition")), start=1):
                parsed = _parse_quantity(value)
                if parsed is not None:
                    _add_parameter(
                        semantic_graph,
                        process,
                        spec.key,
                        name,
                        value,
                        "reported",
                        condition_source,
                        parsed.get("source_unit"),
                        f"row-{row['row']}-{index}",
                        include_application_bridges=include_application_bridges,
                    )
        software_id = row["record_ids"].get("Software")
        if software_id:
            software_source = record_iris[software_id]
            for software_label in _split_software(values.get("Software")):
                software = _iri(spec.key, "software", software_label)
                semantic_graph.add((software, RDF.type, CHAMEO.CharacterisationSoftware))
                semantic_graph.add((software, RDFS.label, Literal(software_label)))
                semantic_graph.add((process, CHAMEO.hasCharacterisationSoftware, software))
                _link_source(semantic_graph, software, software_source)

    result_count = 0
    for row, process, input_data in analysis_rows:
        values = row["values"]
        target_label = str(values.get("Target") or "Unspecified result")
        amount = values.get("AmountTarget")
        result = _iri(spec.key, "result-data", target_label, str(row["row"]))
        prop = _iri(spec.key, "characterisation-property", target_label, str(row["row"]))
        semantic_graph.add((result, RDF.type, CHAMEO.CharacterisationData))
        semantic_graph.add((result, RDF.type, CHAMEO.SecondaryData))
        semantic_graph.add((result, RDFS.label, Literal(f"{target_label} result")))
        semantic_graph.add((result, PROV.wasGeneratedBy, process))
        if include_application_bridges:
            semantic_graph.add((result, APP.isResultOfMeasurement, measurement))
            semantic_graph.add((result, APP.reportsProperty, prop))
        semantic_graph.add((result, APP.case, case_iri))
        semantic_graph.add((process, CHAMEO.hasCharacterisationInput, input_data))
        semantic_graph.add((process, CHAMEO.hasCharacterisationOutput, result))
        # CHAMEO defines DataAnalysis as determining a characterisation property.
        # Its declared EMMO metrology import supplies the process-level relation.
        semantic_graph.add((process, RDF.type, EMMO_DETERMINATION))
        semantic_graph.add((process, EMMO_HAS_DETERMINED_PROPERTY, prop))
        semantic_graph.add((prop, RDF.type, CHAMEO.CharacterisationProperty))
        semantic_graph.add((prop, RDFS.label, Literal(target_label)))
        semantic_graph.add((prop, APP.case, case_iri))
        semantic_graph.add((specimen, CHAMEO.hasCharacterisationProperty, prop))
        target_record = next(item for item in case["source_records"] if item["record_id"] == row["record_ids"]["Target"])
        amount_record = next(item for item in case["source_records"] if item["record_id"] == row["record_ids"]["AmountTarget"])
        target_source = record_iris[target_record["record_id"]]
        amount_source = record_iris[amount_record["record_id"]]
        _link_source(semantic_graph, result, target_source)
        _link_source(semantic_graph, prop, target_source)
        _link_source(semantic_graph, prop, amount_source)
        parsed = _with_implicit_quantity_kind(_parse_quantity(amount), target_label)
        conflict = _semantic_conflict(spec.key, target_label, amount)
        qv = None
        if not conflict and parsed and parsed.get("unit") and parsed.get("quantity_kind"):
            qv = _add_quantity(semantic_graph, prop, parsed, spec.key, f"result|{row['row']}|{target_label}")
        elif conflict:
            _add_finding(
                validation_graph,
                spec.key,
                conflict,
                f"{target_label}: {amount!s} remains source evidence without an unsupported normalized quantity.",
                amount_source,
                prop,
            )
        elif amount not in (None, ""):
            _add_finding(
                validation_graph,
                spec.key,
                "quantity-incomplete",
                f"{target_label}: the reported value lacks a defensible complete value/unit interpretation.",
                amount_source,
                prop,
            )
        mapping_by_record[target_record["record_id"]] = _mapping_row(
            target_record,
            prop,
            "characterisation_property",
            "results",
            "native_generic",
            CHAMEO.CharacterisationProperty,
            (
                "CHAMEO links the sample to a generic characterisation property; a local result-to-property link preserves result provenance."
                if include_application_bridges
                else "CHAMEO links the sample to a generic characterisation property. The strict graph uses an explicitly asserted EMMO Determination pattern at process level and does not add a result-to-property predicate."
            ),
            (
                ("application_extension", "shared_standard")
                if include_application_bridges
                else ("declared_import", "shared_standard")
            ),
        )
        mapping_by_record[amount_record["record_id"]] = _mapping_row(
            amount_record,
            prop,
            "reported_value" if qv else "conservative_source_value",
            "values_units",
            "shared_standard" if qv else "source_only",
            QUDT.QuantityValue if qv else None,
            "Defensible values use the shared QUDT projection; incomplete values remain source evidence.",
            ("declared_import",) if qv else (),
        )
        result_count += 1

    for record in case["source_records"]:
        if record["status"] != "reported":
            _add_finding(
                validation_graph,
                spec.key,
                f"source_{record['status']}",
                f"{record['field']} is recorded as {record['status'].replace('_', ' ')} at {record['cell']}.",
                record_iris[record["record_id"]],
                None,
                "information" if record["status"] in {"not_applicable", "not_specified"} else "warning",
            )
        if record["record_id"] not in mapping_by_record:
            source = record_iris[record["record_id"]]
            _link_source(semantic_graph, case_iri, source)
            mapping_by_record[record["record_id"]] = _mapping_row(
                record,
                case_iri,
                "source_only",
                "missingness" if record["status"] != "reported" else "provenance",
                "source_only",
                None,
                "The field is retained with source-cell provenance and explicit status without an unsupported semantic assertion.",
                ("shared_standard",),
            )

    return {
        "key": spec.key,
        "title": spec.title,
        "measurement": str(measurement),
        "instrument": str(instrument),
        "specimen": str(specimen),
        "raw_dataset": str(raw_dataset),
        "source_record_count": len(record_iris),
        "mapped_record_count": len(mapping_by_record),
        "result_count": result_count,
        "source_status_counts": {
            status: sum(1 for record in case["source_records"] if record["status"] == status)
            for status in SOURCE_STATUSES
        },
        "mapping_rows": [mapping_by_record[key] for key in sorted(mapping_by_record)],
        "source_graph": str(_graph_iri("source", spec.key)),
        "semantic_graph": str(_graph_iri("semantic", spec.key)),
        "validation_graph": str(_graph_iri("validation", spec.key)),
    }


def _shape_graph() -> Graph:
    graph = Graph()
    _bind(graph)
    graph.parse(
        data=f"""
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix chameo: <{CHAMEO}> .
@prefix app: <{APP}> .
@prefix qudt: <{QUDT}> .
@prefix prov: <{PROV}> .

app:MeasurementShape a sh:NodeShape ;
  sh:targetClass chameo:CharacterisationMeasurementProcess ;
  sh:property [ sh:path chameo:hasMeasurementSample ; sh:minCount 1 ; sh:class chameo:Sample ] ;
  sh:property [ sh:path chameo:hasCharacterisationMeasurementInstrument ; sh:minCount 1 ; sh:class chameo:CharacterisationMeasurementInstrument ] ;
  sh:property [ sh:path chameo:hasCharacterisationOutput ; sh:minCount 1 ; sh:class chameo:CharacterisationData ] .

app:ParameterShape a sh:NodeShape ;
  sh:targetClass chameo:MeasurementParameter ;
  sh:property [ sh:path app:describesCharacteristic ; sh:minCount 1 ; sh:maxCount 1 ; sh:class chameo:CharacterisationProperty ] .

app:ResultShape a sh:NodeShape ;
  sh:targetSubjectsOf app:reportsProperty ;
  sh:property [ sh:path app:reportsProperty ; sh:minCount 1 ; sh:maxCount 1 ; sh:class chameo:CharacterisationProperty ] ;
  sh:property [ sh:path app:isResultOfMeasurement ; sh:minCount 1 ; sh:maxCount 1 ; sh:class chameo:CharacterisationMeasurementProcess ] ;
  sh:property [ sh:path prov:wasGeneratedBy ; sh:minCount 1 ; sh:class chameo:DataAnalysis ] .

app:QuantityValueShape a sh:NodeShape ;
  sh:targetClass qudt:QuantityValue ;
  sh:property [ sh:path qudt:numericValue ; sh:minCount 1 ; sh:maxCount 1 ] ;
  sh:property [ sh:path qudt:unit ; sh:minCount 1 ; sh:maxCount 1 ] .
""",
        format="turtle",
    )
    return graph


def _flatten(dataset: Dataset) -> Graph:
    graph = Graph()
    _bind(graph)
    for context in dataset.graphs():
        for triple in context:
            graph.add(triple)
    return graph


def _referenced_tbox_subset(flat: Graph, source_tbox: Graph) -> Graph:
    subset = Graph()
    _bind(subset)
    prefixes = (str(CHAMEO), str(EMMO))
    frontier: set[URIRef | BNode] = {
        value
        for triple in flat
        for value in triple
        if isinstance(value, URIRef) and str(value).startswith(prefixes)
    }
    visited: set[URIRef | BNode] = set()
    depth = 0
    while frontier and depth < 4:
        next_frontier: set[URIRef | BNode] = set()
        for subject in frontier:
            if subject in visited:
                continue
            visited.add(subject)
            for triple in source_tbox.triples((subject, None, None)):
                subset.add(triple)
                obj = triple[2]
                if isinstance(obj, BNode):
                    next_frontier.add(obj)
                elif isinstance(obj, URIRef) and str(obj).startswith(prefixes) and triple[1] in {
                    RDFS.subClassOf, RDFS.subPropertyOf, RDFS.domain, RDFS.range, OWL.equivalentClass,
                }:
                    next_frontier.add(obj)
        frontier = next_frontier
        depth += 1
    return subset


def _prefixes() -> str:
    return f"""PREFIX chameo: <{CHAMEO}>
PREFIX emmo: <{EMMO}>
PREFIX app: <{APP}>
PREFIX cmp: <{CMP}>
PREFIX qudt: <{QUDT}>
PREFIX prov: <{PROV}>
PREFIX rdf: <{RDF}>
PREFIX rdfs: <{RDFS}>
PREFIX dcterms: <{DCTERMS}>
"""


def _sgraph(case_key: str) -> str:
    return f"<{_graph_iri('semantic', case_key)}>"


def _srcgraph(case_key: str) -> str:
    return f"<{_graph_iri('source', case_key)}>"


def _case_key_for_query(query_number: int, start: int) -> str:
    return CASE_SPECS[query_number - start].key


def _query_text(query_id: str) -> str:
    number = int(query_id[1:].split("_", 1)[0])
    p = _prefixes()
    semantic_prefix = str(_graph_iri("semantic")) + "/"
    source_prefix = str(_graph_iri("source")) + "/"
    if number == 1:
        return p + f"""
SELECT DISTINCT ?resultLabel ?specimenLabel ?preparationLabel ?preparedMaterialLabel
WHERE {{
  GRAPH {_sgraph('tem')} {{
    ?result a chameo:SecondaryData ; app:isResultOfMeasurement ?measurement ; rdfs:label ?resultLabel ; app:reportsProperty ?property .
    ?measurement chameo:hasMeasurementSample ?specimen .
    ?specimen rdfs:label ?specimenLabel ; chameo:hasCharacterisationProperty ?property .
    ?preparation a chameo:SamplePreparation ; app:case <{_case_iri('tem')}> ; rdfs:label ?preparationLabel ; emmo:EMMO_c4bace1d_4db0_4cd3_87e9_18122bae2840 ?preparedMaterial .
    ?preparedMaterial rdfs:label ?preparedMaterialLabel .
    ?preparedMaterial (^chameo:hasSampleForPreparation/emmo:EMMO_c4bace1d_4db0_4cd3_87e9_18122bae2840)* ?specimen .
  }}
}}
ORDER BY ?preparationLabel ?preparedMaterialLabel
"""
    if number == 2:
        return p + f"""
SELECT ?instrumentLabel ?parameterLabel ?statusLabel ?sourceCell ?rawValue ?value ?unit
WHERE {{
  GRAPH {_sgraph('tem')} {{
    ?technique a chameo:TransmissionElectronMicroscopy ; emmo:EMMO_f702bad4_fc77_41f0_a26d_79f6444fd4f3 ?measurement .
    ?measurement a chameo:CharacterisationMeasurementProcess ; chameo:hasCharacterisationMeasurementInstrument ?instrument ; chameo:hasMeasurementParameter ?parameter .
    ?instrument rdfs:label ?instrumentLabel .
    ?parameter rdfs:label ?parameterLabel ; app:valueStatus ?status ; app:describesCharacteristic ?property ; prov:wasDerivedFrom ?source .
    OPTIONAL {{ ?property emmo:EMMO_88b84515_a0df_47bb_8166_c7c8b893c1d8 ?qv . ?qv qudt:numericValue ?value ; qudt:unit ?unit . }}
    BIND(REPLACE(STR(?status), "^.*[#/]", "") AS ?statusLabel)
  }}
  GRAPH {_srcgraph('tem')} {{ ?source app:sourceCell ?sourceCell . OPTIONAL {{ ?source rdf:value ?rawValue . }} }}
}}
ORDER BY ?parameterLabel
"""
    if number == 3:
        return p + f"""
SELECT ?inputDataLabel ?analysisLabel ?softwareLabel ?resultLabel
WHERE {{
  GRAPH {_sgraph('tem')} {{
    ?result a chameo:SecondaryData ; rdfs:label ?resultLabel ; prov:wasGeneratedBy ?analysis .
    ?analysis a chameo:DataAnalysis ; rdfs:label ?analysisLabel ; chameo:hasCharacterisationInput ?inputData .
    ?inputData rdfs:label ?inputDataLabel .
    OPTIONAL {{ ?analysis chameo:hasCharacterisationSoftware ?software . ?software rdfs:label ?softwareLabel . }}
  }}
}}
ORDER BY ?resultLabel
"""
    if number == 4:
        return _result_query("tem", include_case=False)
    if number == 5:
        return p + f"""
SELECT ?caseKey ?measurementLabel ?specimenLabel ?instrumentLabel ?rawDatasetLabel
WHERE {{
  GRAPH ?semanticGraph {{
    ?case a app:CharacterizationCase ; dcterms:identifier ?caseKey .
    ?measurement a chameo:CharacterisationMeasurementProcess ; app:case ?case ; rdfs:label ?measurementLabel ;
      chameo:hasMeasurementSample ?specimen ; chameo:hasCharacterisationMeasurementInstrument ?instrument ; chameo:hasCharacterisationOutput ?rawDataset .
    ?rawDataset a chameo:RawData .
    ?specimen rdfs:label ?specimenLabel . ?instrument rdfs:label ?instrumentLabel . ?rawDataset rdfs:label ?rawDatasetLabel .
  }}
  FILTER(STRSTARTS(STR(?semanticGraph), "{semantic_prefix}"))
}}
ORDER BY ?caseKey
"""
    if number == 6:
        return _all_results_query()
    if number == 7:
        return p + f"""
SELECT ?caseKey ?statusLabel (COUNT(?source) AS ?fieldCount)
WHERE {{
  GRAPH ?sourceGraph {{ ?source a app:SourceField ; app:valueStatus ?status . }}
  FILTER(STRSTARTS(STR(?sourceGraph), "{source_prefix}"))
  BIND(STRAFTER(STR(?sourceGraph), "{source_prefix}") AS ?caseKey)
  BIND(REPLACE(STR(?status), "^.*[#/]", "") AS ?statusLabel)
}}
GROUP BY ?caseKey ?statusLabel
ORDER BY ?caseKey ?statusLabel
"""
    if number == 8:
        return _all_parameters_query()
    if number == 9:
        return p + f"""
SELECT ?caseKey ?propertyLabel ?code ?sourceCell ?rawValue
WHERE {{
  GRAPH ?validationGraph {{ ?finding a app:ValidationFinding ; app:case ?case ; app:findingCode ?code ; dcterms:subject ?property ; prov:wasDerivedFrom ?source . }}
  GRAPH ?semanticGraph {{ ?case dcterms:identifier ?caseKey . ?property rdfs:label ?propertyLabel . }}
  GRAPH ?sourceGraph {{ ?source app:sourceCell ?sourceCell . OPTIONAL {{ ?source rdf:value ?rawValue . }} }}
  FILTER(?code IN ("label_unit_conflict", "incomplete_semantics", "unresolved_metric", "unit_unresolved", "ordered_ratio_basis_unspecified", "quantity-incomplete"))
}}
ORDER BY ?caseKey ?propertyLabel ?sourceCell
"""
    if number == 10:
        return p + f"""
SELECT ?caseKey (COUNT(DISTINCT ?source) AS ?sourceFieldCount) (COUNT(DISTINCT ?mappedSource) AS ?mappedFieldCount)
WHERE {{
  GRAPH ?sourceGraph {{ ?source a app:SourceField . }}
  FILTER(STRSTARTS(STR(?sourceGraph), "{source_prefix}"))
  BIND(STRAFTER(STR(?sourceGraph), "{source_prefix}") AS ?caseKey)
  OPTIONAL {{ GRAPH ?semanticGraph {{ ?source app:mappedEntity ?entity . }} BIND(?source AS ?mappedSource) }}
}}
GROUP BY ?caseKey
ORDER BY ?caseKey
"""
    if number == 11:
        return p + f"""
SELECT DISTINCT ?caseKey ?processLabel ?softwareLabel
WHERE {{
  GRAPH ?semanticGraph {{
    ?case a app:CharacterizationCase ; dcterms:identifier ?caseKey .
    ?process app:case ?case ; rdfs:label ?processLabel ; chameo:hasCharacterisationSoftware ?software .
    ?software rdfs:label ?softwareLabel .
  }}
  FILTER(STRSTARTS(STR(?semanticGraph), "{semantic_prefix}"))
}}
ORDER BY ?caseKey ?processLabel ?softwareLabel
"""
    if number == 12:
        return _processing_query("neutron_tomography", include_case=False)
    if 13 <= number <= 20:
        return _measurement_query(_case_key_for_query(number, 13))
    if 21 <= number <= 28:
        return _result_query(_case_key_for_query(number, 21), include_case=False)
    if 29 <= number <= 36:
        key = _case_key_for_query(number, 29)
        return p + f"""
SELECT ?statusLabel (COUNT(?source) AS ?fieldCount)
WHERE {{ GRAPH {_srcgraph(key)} {{ ?source a app:SourceField ; app:valueStatus ?status . }}
  BIND(REPLACE(STR(?status), "^.*[#/]", "") AS ?statusLabel) }}
GROUP BY ?statusLabel
ORDER BY ?statusLabel
"""
    if 37 <= number <= 44:
        return _parameter_query(_case_key_for_query(number, 37), include_case=False)
    if number == 45:
        return p + f"""
SELECT ?caseKey (COUNT(DISTINCT ?measurement) AS ?measurementCount) (COUNT(DISTINCT ?result) AS ?resultCount)
WHERE {{
  GRAPH ?semanticGraph {{
    ?case a app:CharacterizationCase ; dcterms:identifier ?caseKey .
    ?measurement a chameo:CharacterisationMeasurementProcess ; app:case ?case .
    OPTIONAL {{ ?result a chameo:SecondaryData ; app:reportsProperty ?property ; app:case ?case . }}
  }}
  FILTER(STRSTARTS(STR(?semanticGraph), "{semantic_prefix}"))
}}
GROUP BY ?caseKey
ORDER BY ?caseKey
"""
    if number == 46:
        return p + f"""
SELECT ?caseKey ?propertyLabel ?sourceCell ?rawValue ?value ?unit
WHERE {{
  GRAPH ?semanticGraph {{
    ?case a app:CharacterizationCase ; dcterms:identifier ?caseKey .
    ?result a chameo:SecondaryData ; app:reportsProperty ?property ; app:case ?case .
    ?property rdfs:label ?propertyLabel ; prov:wasDerivedFrom ?source ; emmo:EMMO_88b84515_a0df_47bb_8166_c7c8b893c1d8 ?qv .
    ?qv qudt:numericValue ?value ; qudt:unit ?unit .
  }}
  GRAPH ?sourceGraph {{ ?source app:fieldName "AmountTarget" ; app:sourceCell ?sourceCell . OPTIONAL {{ ?source rdf:value ?rawValue . }} }}
  FILTER(STRSTARTS(STR(?semanticGraph), "{semantic_prefix}"))
  FILTER(STRSTARTS(STR(?sourceGraph), "{source_prefix}"))
}}
ORDER BY ?caseKey ?propertyLabel
"""
    if number == 47:
        return p + f"""
SELECT ?caseKey ?fieldName ?sourceCell ?statusLabel ?rawValue
WHERE {{
  GRAPH ?sourceGraph {{ ?source a app:SourceField ; app:fieldName ?fieldName ; app:sourceCell ?sourceCell ; app:valueStatus ?status . OPTIONAL {{ ?source rdf:value ?rawValue . }} }}
  FILTER(STRSTARTS(STR(?sourceGraph), "{source_prefix}"))
  FILTER(?status != app:reported)
  BIND(STRAFTER(STR(?sourceGraph), "{source_prefix}") AS ?caseKey)
  BIND(REPLACE(STR(?status), "^.*[#/]", "") AS ?statusLabel)
}}
ORDER BY ?caseKey ?sourceCell
"""
    if number == 48:
        return p + f"""
SELECT ?caseKey ?parameterLabel ?statusLabel ?sourceCell ?rawValue
WHERE {{
  GRAPH ?semanticGraph {{
    ?case a app:CharacterizationCase ; dcterms:identifier ?caseKey .
    ?measurement a chameo:CharacterisationMeasurementProcess ; app:case ?case ; chameo:hasMeasurementParameter ?parameter .
    ?parameter rdfs:label ?parameterLabel ; app:valueStatus ?status ; prov:wasDerivedFrom ?source .
    FILTER(?status != app:reported)
    BIND(REPLACE(STR(?status), "^.*[#/]", "") AS ?statusLabel)
  }}
  GRAPH ?sourceGraph {{ ?source app:sourceCell ?sourceCell . OPTIONAL {{ ?source rdf:value ?rawValue . }} }}
  FILTER(STRSTARTS(STR(?semanticGraph), "{semantic_prefix}"))
  FILTER(STRSTARTS(STR(?sourceGraph), "{source_prefix}"))
}}
ORDER BY ?caseKey ?parameterLabel ?sourceCell
"""
    if number == 49:
        return p + f"""
SELECT DISTINCT ?caseKey ?analysisLabel ?inputDataLabel ?resultLabel ?softwareLabel
WHERE {{
  GRAPH ?semanticGraph {{
    ?case a app:CharacterizationCase ; dcterms:identifier ?caseKey .
    ?result a chameo:SecondaryData ; rdfs:label ?resultLabel ; app:case ?case ; prov:wasGeneratedBy ?analysis .
    ?analysis a chameo:DataAnalysis ; rdfs:label ?analysisLabel ; chameo:hasCharacterisationInput ?inputData .
    ?inputData rdfs:label ?inputDataLabel .
    OPTIONAL {{ ?analysis chameo:hasCharacterisationSoftware ?software . ?software rdfs:label ?softwareLabel . }}
  }}
  FILTER(STRSTARTS(STR(?semanticGraph), "{semantic_prefix}"))
}}
ORDER BY ?caseKey ?analysisLabel ?resultLabel ?inputDataLabel ?softwareLabel
"""
    if number == 50:
        return _processing_query(None, include_case=True)
    raise ValueError(f"No CHAMEO query template for {query_id}")


def _measurement_query(case_key: str) -> str:
    return _prefixes() + f"""
SELECT ?measurementLabel ?specimenLabel ?instrumentLabel ?rawDatasetLabel
WHERE {{
  GRAPH {_sgraph(case_key)} {{
    ?measurement a chameo:CharacterisationMeasurementProcess ; rdfs:label ?measurementLabel ;
      chameo:hasMeasurementSample ?specimen ; chameo:hasCharacterisationMeasurementInstrument ?instrument ; chameo:hasCharacterisationOutput ?rawDataset .
    ?rawDataset a chameo:RawData .
    ?specimen rdfs:label ?specimenLabel . ?instrument rdfs:label ?instrumentLabel . ?rawDataset rdfs:label ?rawDatasetLabel .
  }}
}}
ORDER BY ?measurementLabel
"""


def _result_query(case_key: str, *, include_case: bool) -> str:
    case_var = "?caseKey " if include_case else ""
    case_pattern = "?case dcterms:identifier ?caseKey ." if include_case else ""
    return _prefixes() + f"""
SELECT {case_var}?resultLabel ?propertyLabel ?bearerLabel ?sourceCell ?rawValue ?value ?unit
WHERE {{
  GRAPH {_sgraph(case_key)} {{
    {case_pattern}
    ?result a chameo:SecondaryData ; rdfs:label ?resultLabel ; app:reportsProperty ?property .
    ?bearer chameo:hasCharacterisationProperty ?property ; rdfs:label ?bearerLabel .
    ?property rdfs:label ?propertyLabel ; prov:wasDerivedFrom ?source .
    OPTIONAL {{ ?property emmo:EMMO_88b84515_a0df_47bb_8166_c7c8b893c1d8 ?qv . ?qv qudt:numericValue ?value ; qudt:unit ?unit . }}
  }}
  GRAPH {_srcgraph(case_key)} {{ ?source app:fieldName "AmountTarget" ; app:sourceCell ?sourceCell . OPTIONAL {{ ?source rdf:value ?rawValue . }} }}
}}
ORDER BY ?resultLabel
"""


def _all_results_query() -> str:
    semantic_prefix = str(_graph_iri("semantic")) + "/"
    source_prefix = str(_graph_iri("source")) + "/"
    return _prefixes() + f"""
SELECT ?caseKey ?resultLabel ?propertyLabel ?bearerLabel ?sourceCell ?rawValue ?value ?unit
WHERE {{
  GRAPH ?semanticGraph {{
    ?case a app:CharacterizationCase ; dcterms:identifier ?caseKey .
    ?result a chameo:SecondaryData ; rdfs:label ?resultLabel ; app:reportsProperty ?property ; app:case ?case .
    ?bearer chameo:hasCharacterisationProperty ?property ; rdfs:label ?bearerLabel .
    ?property rdfs:label ?propertyLabel ; prov:wasDerivedFrom ?source .
    OPTIONAL {{ ?property emmo:EMMO_88b84515_a0df_47bb_8166_c7c8b893c1d8 ?qv . ?qv qudt:numericValue ?value ; qudt:unit ?unit . }}
  }}
  GRAPH ?sourceGraph {{ ?source app:fieldName "AmountTarget" ; app:sourceCell ?sourceCell . OPTIONAL {{ ?source rdf:value ?rawValue . }} }}
  FILTER(STRSTARTS(STR(?semanticGraph), "{semantic_prefix}"))
  FILTER(STRSTARTS(STR(?sourceGraph), "{source_prefix}"))
}}
ORDER BY ?caseKey ?resultLabel
"""


def _parameter_query(case_key: str, *, include_case: bool) -> str:
    case_var = "?caseKey " if include_case else ""
    case_pattern = "?case dcterms:identifier ?caseKey . ?measurement app:case ?case ." if include_case else ""
    return _prefixes() + f"""
SELECT {case_var}?parameterLabel ?statusLabel ?sourceCell ?rawValue ?value ?unit
WHERE {{
  GRAPH {_sgraph(case_key)} {{
    {case_pattern}
    ?measurement a chameo:CharacterisationMeasurementProcess ; chameo:hasMeasurementParameter ?parameter .
    ?parameter rdfs:label ?parameterLabel ; app:valueStatus ?status ; app:describesCharacteristic ?property ; prov:wasDerivedFrom ?source .
    OPTIONAL {{ ?property emmo:EMMO_88b84515_a0df_47bb_8166_c7c8b893c1d8 ?qv . ?qv qudt:numericValue ?value ; qudt:unit ?unit . }}
    BIND(REPLACE(STR(?status), "^.*[#/]", "") AS ?statusLabel)
  }}
  GRAPH {_srcgraph(case_key)} {{ ?source app:sourceCell ?sourceCell . OPTIONAL {{ ?source rdf:value ?rawValue . }} }}
}}
ORDER BY ?parameterLabel ?sourceCell
"""


def _all_parameters_query() -> str:
    semantic_prefix = str(_graph_iri("semantic")) + "/"
    source_prefix = str(_graph_iri("source")) + "/"
    return _prefixes() + f"""
SELECT ?caseKey ?parameterLabel ?statusLabel ?sourceCell ?rawValue ?value ?unit
WHERE {{
  GRAPH ?semanticGraph {{
    ?case a app:CharacterizationCase ; dcterms:identifier ?caseKey .
    ?measurement a chameo:CharacterisationMeasurementProcess ; app:case ?case ; chameo:hasMeasurementParameter ?parameter .
    ?parameter rdfs:label ?parameterLabel ; app:valueStatus ?status ; app:describesCharacteristic ?property ; prov:wasDerivedFrom ?source .
    OPTIONAL {{ ?property emmo:EMMO_88b84515_a0df_47bb_8166_c7c8b893c1d8 ?qv . ?qv qudt:numericValue ?value ; qudt:unit ?unit . }}
    BIND(REPLACE(STR(?status), "^.*[#/]", "") AS ?statusLabel)
  }}
  GRAPH ?sourceGraph {{ ?source app:sourceCell ?sourceCell . OPTIONAL {{ ?source rdf:value ?rawValue . }} }}
  FILTER(STRSTARTS(STR(?semanticGraph), "{semantic_prefix}"))
  FILTER(STRSTARTS(STR(?sourceGraph), "{source_prefix}"))
}}
ORDER BY ?caseKey ?parameterLabel ?sourceCell
"""


def _processing_query(case_key: str | None, *, include_case: bool) -> str:
    graph = "?semanticGraph" if case_key is None else _sgraph(case_key)
    case_var = "?caseKey " if include_case else ""
    case_pattern = "?case a app:CharacterizationCase ; dcterms:identifier ?caseKey . ?process app:case ?case ." if include_case else ""
    graph_filter = (
        f'FILTER(STRSTARTS(STR(?semanticGraph), "{str(_graph_iri("semantic"))}/"))'
        if case_key is None else ""
    )
    return _prefixes() + f"""
SELECT DISTINCT {case_var}?processLabel ?inputDataLabel ?outputDataLabel
WHERE {{
  GRAPH {graph} {{
    {case_pattern}
    ?process a chameo:DataPreparation ; rdfs:label ?processLabel ; chameo:hasCharacterisationInput ?inputData ; chameo:hasCharacterisationOutput ?outputData .
    ?inputData rdfs:label ?inputDataLabel . ?outputData rdfs:label ?outputDataLabel .
  }}
  {graph_filter}
}}
ORDER BY {case_var}?processLabel ?inputDataLabel ?outputDataLabel
"""


def _query_sensitivity(query_id: str) -> str:
    number = int(query_id[1:].split("_", 1)[0])
    if number in {7, 10, *range(29, 37), 47}:
        return "shared_infrastructure"
    if number == 9:
        return "mixed_semantic_quality"
    return "ontology_sensitive"


def _f1(precision: float, recall: float) -> float:
    return round(2 * precision * recall / (precision + recall), 2) if precision + recall else 0.0


def _query_complexity(query: str) -> dict[str, int]:
    counts = {"triple_patterns": 0, "joins": 0, "optional_blocks": 0, "property_paths": 0}
    try:
        algebra = translateQuery(parseQuery(query)).algebra

        def walk(value: Any) -> None:
            if isinstance(value, CompValue):
                if value.name == "BGP":
                    triples = value.get("triples", [])
                    counts["triple_patterns"] += len(triples)
                    counts["property_paths"] += sum(1 for triple in triples if not isinstance(triple[1], URIRef))
                elif value.name == "Join":
                    counts["joins"] += 1
                elif value.name == "LeftJoin":
                    counts["optional_blocks"] += 1
                for item in value.values():
                    walk(item)
            elif isinstance(value, (list, tuple)):
                for item in value:
                    walk(item)

        walk(algebra)
    except Exception:
        counts["optional_blocks"] = query.upper().count("OPTIONAL")
        counts["property_paths"] = query.count("*")
    counts["lines"] = len([line for line in query.splitlines() if line.strip()])
    return counts


def _run_queries(dataset: Dataset, target: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    query_dir = ensure_dir(target / "queries" / "chameo")
    result_dir = ensure_dir(target / "query_results" / "chameo")
    expected_dir = ensure_dir(target / "query_ground_truth")
    summaries: list[dict[str, Any]] = []
    specs = _query_specs()
    for spec in specs:
        query = _query_text(spec["id"]).strip()
        write_text(query_dir / f"{spec['id']}.rq", query + "\n")
        result = dataset.query(query)
        variables = [str(item) for item in result.vars]
        observed = [
            {variable: "" if row[index] is None else str(row[index]) for index, variable in enumerate(variables)}
            for row in result
        ]
        expected = [
            {variable: str(row.get(variable, "")) for variable in variables}
            for row in _ground_truth_rows(spec["id"], manifest)
        ]
        comparison = _compare_query_rows(expected, observed, variables)
        comparison["row_f1_percent"] = _f1(
            comparison["row_precision_percent"], comparison["row_recall_percent"]
        )
        _write_csv(result_dir / f"{spec['id']}.csv", observed, variables)
        dump_json(result_dir / f"{spec['id']}.json", {"variables": variables, "rows": observed})
        _write_csv(expected_dir / f"{spec['id']}_expected.csv", expected, variables)
        dump_json(expected_dir / f"{spec['id']}_expected.json", {"variables": variables, "rows": expected})
        dump_json(expected_dir / f"{spec['id']}_comparison.json", comparison)
        summaries.append({
            **{key: spec[key] for key in ("id", "category", "question", "title", "purpose", "ground_truth_basis")},
            "sensitivity": _query_sensitivity(spec["id"]),
            "query": query,
            "variables": variables,
            "rows": observed,
            "expected_rows": expected,
            "validation": comparison,
            "complexity": _query_complexity(query),
        })
    return summaries


def _validate_graph(flat: Graph, shapes: Graph, target: Path) -> dict[str, Any]:
    conforms, report_graph, report_text = shacl_validate(flat, shacl_graph=shapes, inference="rdfs")
    report_graph.serialize(target / "chameo_shacl_validation_report.ttl", format="turtle")
    write_text(target / "chameo_shacl_validation_report.txt", str(report_text))
    scenarios = (
        ("missing_measurement_subject", CHAMEO.hasMeasurementSample, CHAMEO.CharacterisationMeasurementProcess),
        ("missing_parameter_property", APP.describesCharacteristic, CHAMEO.MeasurementParameter),
        ("missing_result_provenance", PROV.wasGeneratedBy, CHAMEO.SecondaryData),
        ("missing_quantity_unit", QUDT.unit, QUDT.QuantityValue),
    )
    negatives: list[dict[str, Any]] = []
    for name, predicate, subject_type in scenarios:
        negative = Graph()
        for triple in flat:
            negative.add(triple)
        candidates = sorted(negative.triples((None, predicate, None)), key=lambda row: tuple(map(str, row)))
        removed = next((row for row in candidates if (row[0], RDF.type, subject_type) in negative), None)
        if removed:
            negative.remove(removed)
        negative_conforms, _, negative_report = shacl_validate(negative, shacl_graph=shapes, inference="rdfs")
        negatives.append({
            "scenario": name,
            "removed_triple": [str(item) for item in removed] if removed else [],
            "conforms": bool(negative_conforms),
            "expected": False,
            "report": str(negative_report),
        })
    return {"conforms": bool(conforms), "report": str(report_text), "negative_tests": negatives}


def _markdown_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> str:
    lines = [
        "| " + " | ".join(label for _, label in columns) + " |",
        "|" + "|".join("---" for _ in columns) + "|",
    ]
    for row in rows:
        values = [str(row.get(key, "")).replace("|", "\\|").replace("\n", " ") for key, _ in columns]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines) + "\n"


def _comparison_matrix(
    chameo_queries: list[dict[str, Any]],
    h2kg_workbench: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    h2kg = {item["id"]: item for item in h2kg_workbench["queries"]}
    rows: list[dict[str, Any]] = []
    for item in chameo_queries:
        baseline = h2kg[item["id"]]
        h_validation = baseline["validation"]
        c_validation = item["validation"]
        h_precision = float(h_validation["row_precision_percent"])
        h_recall = float(h_validation["row_recall_percent"])
        row = {
            "query_id": item["id"],
            "plain_language_question": item["question"],
            "sensitivity": item["sensitivity"],
            "expected_rows": c_validation["expected_row_count"],
            "h2kg_status": h_validation["status"],
            "h2kg_observed": h_validation["observed_row_count"],
            "h2kg_matched": h_validation["matched_row_count"],
            "h2kg_missing": h_validation["missing_expected_row_count"],
            "h2kg_unexpected": h_validation["unexpected_row_count"],
            "h2kg_precision_percent": h_precision,
            "h2kg_recall_percent": h_recall,
            "h2kg_f1_percent": _f1(h_precision, h_recall),
            "chameo_status": c_validation["status"],
            "chameo_observed": c_validation["observed_row_count"],
            "chameo_matched": c_validation["matched_row_count"],
            "chameo_missing": c_validation["missing_expected_row_count"],
            "chameo_unexpected": c_validation["unexpected_row_count"],
            "chameo_precision_percent": c_validation["row_precision_percent"],
            "chameo_recall_percent": c_validation["row_recall_percent"],
            "chameo_f1_percent": c_validation["row_f1_percent"],
            "answer_parity": Counter(
                tuple(str(row.get(variable, "")) for variable in item["variables"])
                for row in baseline["rows"]
            ) == Counter(
                tuple(str(row.get(variable, "")) for variable in item["variables"])
                for row in item["rows"]
            ),
        }
        rows.append(row)
    summary: dict[str, Any] = {
        "query_count": len(rows),
        "expected_row_count": sum(row["expected_rows"] for row in rows),
        "h2kg_passed": sum(row["h2kg_status"] == "pass" for row in rows),
        "chameo_passed": sum(row["chameo_status"] == "pass" for row in rows),
        "answer_parity_count": sum(bool(row["answer_parity"]) for row in rows),
        "by_sensitivity": {},
    }
    for sensitivity in sorted({row["sensitivity"] for row in rows}):
        subset = [row for row in rows if row["sensitivity"] == sensitivity]
        summary["by_sensitivity"][sensitivity] = {
            "query_count": len(subset),
            "h2kg_passed": sum(row["h2kg_status"] == "pass" for row in subset),
            "chameo_passed": sum(row["chameo_status"] == "pass" for row in subset),
            "answer_parity_count": sum(bool(row["answer_parity"]) for row in subset),
        }
    return rows, summary


def _graph_stats(dataset: Dataset, case_summaries: list[dict[str, Any]], mapping_rows: list[dict[str, Any]]) -> dict[str, Any]:
    source_triples = sum(len(dataset.graph(URIRef(case["source_graph"]))) for case in case_summaries)
    semantic_graphs = [dataset.graph(URIRef(case["semantic_graph"])) for case in case_summaries]
    semantic_triples = sum(len(graph) for graph in semantic_graphs)
    validation_triples = sum(len(dataset.graph(URIRef(case["validation_graph"]))) for case in case_summaries)
    semantic_entities = {
        subject for graph in semantic_graphs for subject in graph.subjects() if isinstance(subject, URIRef)
    }
    return {
        "source_triples": source_triples,
        "semantic_triples": semantic_triples,
        "validation_triples": validation_triples,
        "abox_triples": source_triples + semantic_triples + validation_triples,
        "semantic_entity_count": len(semantic_entities),
        "mapping_rule_count": len({row["mapping_outcome"] for row in mapping_rows}),
    }


def _h2kg_stats(h2kg_output: Path) -> dict[str, Any]:
    report = json.loads((h2kg_output / "validation_report.json").read_text(encoding="utf-8"))
    dataset = Dataset(default_union=False).parse(h2kg_output / "characterization_knowledge_graph.trig", format="trig")
    prefixes = (
        "https://w3id.org/h2kg/examples/characterization/graph/source/",
        "https://w3id.org/h2kg/examples/characterization/graph/semantic/",
        "https://w3id.org/h2kg/examples/characterization/graph/validation/",
    )
    counts = {"source_triples": 0, "semantic_triples": 0, "validation_triples": 0}
    semantic_entities: set[URIRef] = set()
    for context in dataset.graphs():
        iri = str(context.identifier)
        if iri.startswith(prefixes[0]):
            counts["source_triples"] += len(context)
        elif iri.startswith(prefixes[1]):
            counts["semantic_triples"] += len(context)
            semantic_entities.update(subject for subject in context.subjects() if isinstance(subject, URIRef))
        elif iri.startswith(prefixes[2]):
            counts["validation_triples"] += len(context)
    mappings = json.loads((h2kg_output / "source_semantic_mapping_registry.json").read_text(encoding="utf-8"))["mappings"]
    return {
        **counts,
        "abox_triples": sum(counts.values()),
        "semantic_entity_count": len(semantic_entities),
        "mapping_rule_count": len({row.get("mapping_outcome", "") for row in mappings}),
        "rdf_triple_count": report["rdf_triple_count"],
        "named_graph_count": report["named_graph_count"],
        "shacl_conforms": report["shacl_conforms"],
    }


def _coverage_report(mapping_rows: list[dict[str, Any]]) -> dict[str, Any]:
    tier_counts = Counter(row["representation_tier"] for row in mapping_rows)
    participation_counts: Counter[str] = Counter()
    category_counts: dict[str, Counter[str]] = {}
    for row in mapping_rows:
        category_counts.setdefault(row["semantic_category"], Counter())[row["representation_tier"]] += 1
        participation_counts[row["representation_tier"]] += 1
        participation_counts.update(
            item for item in str(row.get("supporting_tiers", "")).split(";") if item
        )
    return {
        "field_mapping_count": len(mapping_rows),
        "primary_tier_counts": dict(sorted(tier_counts.items())),
        "field_tier_participation_counts": dict(sorted(participation_counts.items())),
        "category_tier_counts": {
            category: dict(sorted(counts.items())) for category, counts in sorted(category_counts.items())
        },
        "domain_extension_classes": 0,
        "domain_gap_object_properties": 3,
        "domain_gap_relations": [
            str(APP.describesCharacteristic), str(APP.reportsProperty), str(APP.isResultOfMeasurement)
        ],
        "support_schema_classes": 4,
        "support_schema_properties": 13,
        "chameo_tbox_modified": False,
        "h2kg_tbox_modified": False,
    }


def _representation_patterns() -> list[dict[str, Any]]:
    return [
        {
            "semantic_category": "workflow",
            "pattern": "workflow has task description; task describes occurrence",
            "primary_tier": "native_generic",
            "native_terms": f"{CHAMEO.CharacterisationWorkflow};{CHAMEO.CharacterisationTask};{CHAMEO.hasCharacterisationTask}",
            "supporting_terms": str(EMMO_IS_DESCRIPTION_FOR),
            "supporting_tier": "declared_import",
            "application_extension": "",
        },
        {
            "semantic_category": "measurement",
            "pattern": "technique description identifies a measurement-process occurrence",
            "primary_tier": "native_specific",
            "native_terms": f"{CHAMEO.CharacterisationTechnique};{CHAMEO.CharacterisationMeasurementProcess}",
            "supporting_terms": str(EMMO_IS_DESCRIPTION_FOR),
            "supporting_tier": "declared_import",
            "application_extension": "",
        },
        {
            "semantic_category": "specimen",
            "pattern": "measurement has sample",
            "primary_tier": "native_generic",
            "native_terms": f"{CHAMEO.Sample};{CHAMEO.hasMeasurementSample}",
            "supporting_terms": "",
            "supporting_tier": "",
            "application_extension": "",
        },
        {
            "semantic_category": "instrument",
            "pattern": "measurement has characterisation instrument",
            "primary_tier": "native_generic",
            "native_terms": f"{CHAMEO.CharacterisationMeasurementInstrument};{CHAMEO.hasCharacterisationMeasurementInstrument}",
            "supporting_terms": "",
            "supporting_tier": "",
            "application_extension": "",
        },
        {
            "semantic_category": "settings",
            "pattern": "procedure has measurement parameter; parameter describes characteristic",
            "primary_tier": "native_generic",
            "native_terms": f"{CHAMEO.MeasurementParameter};{CHAMEO.hasMeasurementParameter}",
            "supporting_terms": str(EMMO_HAS_PROPERTY),
            "supporting_tier": "declared_import",
            "application_extension": str(APP.describesCharacteristic),
        },
        {
            "semantic_category": "preparation",
            "pattern": "sample preparation consumes and outputs sample occurrences",
            "primary_tier": "native_generic",
            "native_terms": f"{CHAMEO.SamplePreparation};{CHAMEO.hasSampleForPreparation}",
            "supporting_terms": str(EMMO_HAS_OUTPUT),
            "supporting_tier": "declared_import",
            "application_extension": "",
        },
        {
            "semantic_category": "datasets",
            "pattern": "procedure consumes and outputs characterisation data",
            "primary_tier": "native_generic",
            "native_terms": f"{CHAMEO.CharacterisationData};{CHAMEO.RawData};{CHAMEO.PrimaryData};{CHAMEO.hasCharacterisationInput};{CHAMEO.hasCharacterisationOutput}",
            "supporting_terms": "",
            "supporting_tier": "",
            "application_extension": "",
        },
        {
            "semantic_category": "processing",
            "pattern": "data preparation or analysis consumes and outputs characterisation data",
            "primary_tier": "native_specific",
            "native_terms": f"{CHAMEO.DataPreparation};{CHAMEO.DataAnalysis}",
            "supporting_terms": "",
            "supporting_tier": "",
            "application_extension": "",
        },
        {
            "semantic_category": "software",
            "pattern": "process uses characterisation software",
            "primary_tier": "native_specific",
            "native_terms": f"{CHAMEO.CharacterisationSoftware};{CHAMEO.hasCharacterisationSoftware}",
            "supporting_terms": "",
            "supporting_tier": "",
            "application_extension": "",
        },
        {
            "semantic_category": "results",
            "pattern": "secondary result data reports a sample characterisation property",
            "primary_tier": "native_generic",
            "native_terms": f"{CHAMEO.SecondaryData};{CHAMEO.CharacterisationProperty};{CHAMEO.hasCharacterisationProperty}",
            "supporting_terms": str(PROV.wasGeneratedBy),
            "supporting_tier": "shared_standard",
            "application_extension": f"{APP.reportsProperty};{APP.isResultOfMeasurement}",
        },
        {
            "semantic_category": "values_units",
            "pattern": "property has normalized QUDT quantity value",
            "primary_tier": "shared_standard",
            "native_terms": "",
            "supporting_terms": f"{EMMO_HAS_QUANTITY_VALUE};{QUDT.QuantityValue};{QUDT.numericValue};{QUDT.unit}",
            "supporting_tier": "declared_import;shared_standard",
            "application_extension": "",
        },
        {
            "semantic_category": "provenance_missingness",
            "pattern": "source field retains cell, raw lexical value, explicit status, and derivation",
            "primary_tier": "source_only",
            "native_terms": "",
            "supporting_terms": str(PROV.wasDerivedFrom),
            "supporting_tier": "shared_standard",
            "application_extension": f"{APP.SourceField};{APP.sourceCell};{APP.valueStatus}",
        },
    ]


def _query_complexity_report(chameo_queries: list[dict[str, Any]], h2kg_workbench: dict[str, Any]) -> dict[str, Any]:
    rows = []
    h2kg = {item["id"]: item for item in h2kg_workbench["queries"]}
    for item in chameo_queries:
        h_metrics = _query_complexity(h2kg[item["id"]]["query"])
        c_metrics = item["complexity"]
        rows.append({
            "query_id": item["id"],
            "sensitivity": item["sensitivity"],
            **{f"h2kg_{key}": value for key, value in h_metrics.items()},
            **{f"chameo_{key}": value for key, value in c_metrics.items()},
        })
    return {
        "method": "RDFLib SPARQL algebra counts for BGP triples, joins, left joins, and path predicates; line counts are non-empty query lines.",
        "interpretation_limit": "Syntactic complexity is descriptive and is not an ontology-quality score.",
        "queries": rows,
    }


def _write_reports(
    target: Path,
    report: dict[str, Any],
    matrix: list[dict[str, Any]],
    mapping_rows: list[dict[str, Any]],
    source_lock: dict[str, Any],
    complexity: dict[str, Any],
) -> None:
    dump_json(target / "comparison_report.json", report)
    dump_json(target / "chameo_source_lock.json", source_lock)
    _write_csv(target / "chameo_source_lock.csv", source_lock["files"])
    dump_json(target / "source_semantic_mapping_registry.json", {"schema_version": BUILD_SCHEMA, "mappings": mapping_rows})
    _write_csv(target / "source_semantic_mapping_registry.csv", mapping_rows)
    dump_json(target / "query_comparison_matrix.json", {"schema_version": BUILD_SCHEMA, "queries": matrix})
    _write_csv(target / "query_comparison_matrix.csv", matrix)
    write_text(target / "query_comparison_matrix.md", _markdown_table(matrix, [
        ("query_id", "Query"), ("plain_language_question", "Plain-language question"),
        ("sensitivity", "Evidence layer"), ("expected_rows", "Expected"),
        ("h2kg_status", "H2KG"), ("chameo_status", "CHAMEO"), ("answer_parity", "Same answers"),
    ]))
    dump_json(target / "query_complexity_report.json", complexity)
    _write_csv(target / "query_complexity_report.csv", complexity["queries"])
    dump_json(target / "representation_coverage_report.json", report["representation_coverage"])
    coverage_rows = []
    for category, counts in report["representation_coverage"]["category_tier_counts"].items():
        coverage_rows.append({"semantic_category": category, **{tier: counts.get(tier, 0) for tier in sorted(REPRESENTATION_TIERS)}})
    _write_csv(target / "representation_coverage_report.csv", coverage_rows)
    patterns = report["representation_patterns"]
    dump_json(target / "representation_pattern_registry.json", {"schema_version": BUILD_SCHEMA, "patterns": patterns})
    _write_csv(target / "representation_pattern_registry.csv", patterns)


def _html_report(report: dict[str, Any], matrix: list[dict[str, Any]]) -> str:
    summary = report["query_comparison"]
    coverage = report["representation_coverage"]["primary_tier_counts"]
    representative = [row for row in matrix if row["query_id"] in {
        "q1_tem_specimen_preparation", "q2_tem_instrument_settings", "q3_tem_dataset_analysis",
        "q4_tem_result_value", "q5_all_measurement_contexts", "q6_all_result_records",
        "q9_conservative_quantity_findings", "q46_normalized_result_quantities",
        "q47_qualified_source_fields", "q50_preprocessing_transformations",
    }]
    rows = "".join(
        f"<tr><td>{html.escape(row['query_id'])}</td><td>{html.escape(row['plain_language_question'])}</td>"
        f"<td>{html.escape(row['sensitivity'])}</td><td>{html.escape(row['h2kg_status'])}</td>"
        f"<td>{html.escape(row['chameo_status'])}</td><td>{'yes' if row['answer_parity'] else 'no'}</td></tr>"
        for row in representative
    )
    tiers = "".join(f"<li><strong>{html.escape(key)}</strong>: {value:,} source fields</li>" for key, value in coverage.items())
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>H₂KG--CHAMEO characterization KG comparison</title>
<style>body{{font-family:Arial,sans-serif;max-width:1180px;margin:0 auto;padding:36px;color:#172735;background:#f4f7f6}}h1,h2{{color:#123b43}}.card{{background:white;border:1px solid #ccd9d7;border-radius:12px;padding:20px;margin:18px 0;box-shadow:0 6px 18px #17343a12}}.metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}}.metric{{background:#eaf3f1;padding:14px;border-radius:8px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:9px;border-bottom:1px solid #d7e0de;text-align:left;vertical-align:top}}th{{background:#123b43;color:white}}code{{background:#eef1f0;padding:2px 5px}}a{{color:#0b6471}}</style></head>
<body><h1>H₂KG--CHAMEO characterization knowledge-graph comparison</h1>
<p>This historical transfer diagnostic applies 50 H2KG-application questions to independently constructed H2KG and CHAMEO graphs. The separate frozen 13-requirement benchmark, rather than this asymmetric diagnostic, determines the comparative conclusion.</p>
<div class="metrics"><div class="metric"><strong>Cases</strong><br>{report['case_count']}</div><div class="metric"><strong>Source fields</strong><br>{report['eligible_field_count']:,}</div><div class="metric"><strong>H₂KG queries passed</strong><br>{summary['h2kg_passed']}/50</div><div class="metric"><strong>CHAMEO queries passed</strong><br>{summary['chameo_passed']}/50</div></div>
<div class="card"><h2>Frozen ontology sources</h2><p>CHAMEO {CHAMEO_VERSION}, commit <code>{CHAMEO_COMMIT}</code>; EMMO {EMMO_VERSION}, commit <code>{EMMO_COMMIT}</code>. The build used original ontology IRIs and a frozen local import closure.</p></div>
<div class="card"><h2>Representative competency questions</h2><table><thead><tr><th>ID</th><th>Question</th><th>Evidence layer</th><th>H2KG</th><th>CHAMEO</th><th>Same answers</th></tr></thead><tbody>{rows}</tbody></table></div>
<div class="card"><h2>CHAMEO representation tiers</h2><ul>{tiers}</ul><p>Three local domain-gap relations are declared explicitly; no local CHAMEO domain class was created.</p></div>
<div class="card"><h2>Downloads</h2><p><a href="query_comparison_matrix.csv">Query matrix</a> · <a href="representation_coverage_report.csv">Coverage</a> · <a href="comparison_report.json">Complete report</a> · <a href="README.md">Reproducibility notes</a></p></div>
<div class="card"><h2>Interpretation boundary</h2><p>Passing a competency question means that the encoded graph reproduced manifest-derived expectations. It does not establish scientific correctness, independent retrieval accuracy, workflow execution, scalability, or automatic FAIRness.</p></div></body></html>"""


def _readme(report: dict[str, Any]) -> str:
    return f"""# H2KG--CHAMEO characterization KG comparison

This local package compares two independently built RDF representations of the same sanitized characterization workbook manifest. CHAMEO is pinned to version {CHAMEO_VERSION} at commit `{CHAMEO_COMMIT}` and EMMO to version {EMMO_VERSION} at commit `{EMMO_COMMIT}`. CHAMEO is licensed under CC BY 4.0; see `chameo_source_lock.json` for source IRIs, versions, commits, and file fingerprints.

## Reproduce

Run from `ontology_release` after installing the project environment:

```powershell
python -m aimworks_ontology_release.cli characterization-compare-chameo
```

The build is offline once the pinned source repositories exist under `cache/sources/chameo` and `cache/sources/emmo-1.0.3`. It verifies every commit, ontology version, the complete transitive import closure, and every source fingerprint before generating results.

## Interpretation

- Source coverage: {report['represented_field_count']:,}/{report['eligible_field_count']:,} eligible fields.
- Questions: {report['query_comparison']['query_count']} using one manifest-derived answer contract.
- CHAMEO TBox changes: none.
- H2KG TBox changes: none.
- Local CHAMEO domain classes: none.
- Explicit domain-gap relations: three.

The source layer, shared QUDT projection, and PROV/DCTERMS provenance are reported separately from CHAMEO-native and EMMO-imported semantics. Query success is a bounded competency result, not an ontology-quality ranking.
"""


def _manuscript_materials(local: Path, report: dict[str, Any], matrix: list[dict[str, Any]]) -> None:
    _safe_replace_dir(local, local.parent)
    q = report["query_comparison"]
    coverage = report["representation_coverage"]
    methods = f"""## Comparative knowledge-graph construction and evaluation

Two RDF knowledge graphs were constructed independently from the same sanitized workbook manifest (SHA-256 `{report['source_sha256']}`). The first used H₂KG 2.3.0; the second used CHAMEO {CHAMEO_VERSION} (`{CHAMEO_COMMIT}`) and its declared EMMO {EMMO_VERSION} imports (`{EMMO_COMMIT}`). The CHAMEO graph was generated directly from the manifest rather than translated from the H₂KG graph. Both representations retained all {report['eligible_field_count']:,} eligible fields from eight cases, including raw lexical values, source cells, missingness states, normalized quantities where defensible, and provenance.

Fifty prespecified questions used the same plain-language formulation, variables, source population, and expected answer rows. Ontology-specific SPARQL expressed each ontology's native model. Expected rows were generated independently from the sanitized manifest and compared with RDFLib results as exact row multisets. Questions were stratified as ontology-sensitive, shared-infrastructure, or mixed semantic-quality questions so that source bookkeeping alone was not counted as domain-ontology capability. Equivalent ontology-specific SHACL shapes tested the valid graphs and four negative mutations: missing measurement subject, parameter-characteristic link, result provenance, and quantity unit.

CHAMEO-native, EMMO-imported, shared-standard, application-extension, and source-only assertions were counted separately. QUDT normalization and PROV-O/DCTERMS provenance were treated as shared infrastructure. CHAMEO required no new domain class; three neutral application relations represented parameter-to-characteristic, result-to-property, and result-to-measurement links. Syntactic query and graph-size metrics were reported descriptively and were not combined into an overall score.
"""
    results = f"""## Comparative competency results

Both graphs represented {report['represented_field_count']:,} of {report['eligible_field_count']:,} eligible source fields across eight characterization cases. The H₂KG query set passed {q['h2kg_passed']} of {q['query_count']} questions and the CHAMEO query set passed {q['chameo_passed']} of {q['query_count']}; exact answer parity was observed for {q['answer_parity_count']} questions. These results show whether each implemented representation reproduced the same curated source expectations under the prespecified questions. They do not measure corpus-wide search performance or scientific correctness.

CHAMEO supplied native generic patterns for samples, measurements, instruments, parameters, characterisation data, processing, software, and sample properties, and method-specific technique classes where available. EMMO imports supplied description-to-occurrence, output, property, and quantity-value relations. Of the {coverage['field_mapping_count']:,} source-field mappings, the primary representation tiers were: {', '.join(f'{key} {value:,}' for key, value in coverage['primary_tier_counts'].items())}. No CHAMEO or H₂KG class/property IRI was changed.

The comparison exposes modeling differences rather than a winner. H₂KG directly represents result data points and the parameter-record/property pattern used by the hydrogen workflow profiles. CHAMEO provides a broader native characterization workflow vocabulary and explicit technique descriptions but required three local bridging relations for the common answer contract. Shared source, provenance, and quantity layers accounted for a subset of the successful questions and are reported separately.
"""
    limitations = """## Interpretation and limitations

The expected answers are deterministic derivatives of the same curated manifest used to construct the graphs; they are implementation ground truth, not independent experimental measurements. The test therefore assesses source preservation, structural conformance, and answer reproducibility for 50 bounded questions. It does not estimate general precision or recall, validate the scientific content of the workbook, execute workflows, compare reasoner performance, or prove FAIRness. Generic CHAMEO representations indicate that a fact can be encoded without adding a domain class; they do not imply the same hydrogen-domain specificity as an H2KG term. Conversely, H2KG's additional specificity is not by itself evidence of superior ontology quality. Future work should use independently authored questions, blinded relevance judgments, additional laboratories, and runtime/scalability experiments.
"""
    write_text(local / "methods_subsection.md", methods)
    write_text(local / "results_subsection.md", results)
    write_text(local / "limitations.md", limitations)
    representative_ids = {
        "q1_tem_specimen_preparation", "q2_tem_instrument_settings", "q3_tem_dataset_analysis",
        "q4_tem_result_value", "q5_all_measurement_contexts", "q6_all_result_records",
        "q9_conservative_quantity_findings", "q46_normalized_result_quantities",
        "q47_qualified_source_fields", "q50_preprocessing_transformations",
    }
    representative = [row for row in matrix if row["query_id"] in representative_ids]
    columns = [
        ("query_id", "Query"), ("plain_language_question", "Plain-language question"),
        ("sensitivity", "Evidence layer"), ("expected_rows", "Expected rows"),
        ("h2kg_status", "H2KG"), ("chameo_status", "CHAMEO"), ("answer_parity", "Answer parity"),
    ]
    write_text(local / "representative_10_query_table.md", _markdown_table(representative, columns))
    write_text(local / "supplementary_50_query_table.md", _markdown_table(matrix, columns))
    write_text(local / "comparison_figure_specification.md", """# Figure specification

Create a two-column figure beginning with one sanitized workbook manifest and splitting into independently constructed H2KG and CHAMEO RDF datasets. Show a shared bottom evaluation layer containing the 50 plain-language question contracts, manifest-derived expected rows, RDFLib/SPARQL comparison, and ontology-specific SHACL validation. In the CHAMEO column, distinguish native CHAMEO, declared EMMO imports, shared QUDT/PROV/DCTERMS, and three application-extension relations. Do not draw a winner, ranking arrow, or aggregate score.
""")
    write_text(local / "comparison_figure.svg", _figure_svg(report))
    write_text(local / "README.md", "The files in this directory are local manuscript drafting material and are intentionally excluded from Git.\n")


def _figure_svg(report: dict[str, Any]) -> str:
    q = report["query_comparison"]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="780" viewBox="0 0 1400 780">
<style>.t{{font:700 30px Arial;fill:#16303b}}.h{{font:700 24px Arial;fill:#16303b}}.b{{font:18px Arial;fill:#344b55}}.n{{fill:#eef6f4;stroke:#247f76;stroke-width:3}}.h2{{fill:#eaf1f8;stroke:#3d76a8;stroke-width:3}}.c{{fill:#f2edf8;stroke:#8057a6;stroke-width:3}}.s{{fill:#fff4df;stroke:#b47a19;stroke-width:3}}.a{{stroke:#526b75;stroke-width:3;fill:none;marker-end:url(#m)}}</style>
<defs><marker id="m" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#526b75"/></marker></defs>
<text class="t" x="700" y="48" text-anchor="middle">One source manifest, two independently constructed ontology-backed graphs</text>
<rect class="n" x="475" y="80" rx="16" width="450" height="90"/><text class="h" x="700" y="118" text-anchor="middle">Sanitized workbook manifest</text><text class="b" x="700" y="148" text-anchor="middle">8 cases · {report['eligible_field_count']:,} eligible fields · explicit source status</text>
<path class="a" d="M620 170 L380 240"/><path class="a" d="M780 170 L1020 240"/>
<rect class="h2" x="90" y="240" rx="18" width="520" height="230"/><text class="h" x="350" y="280" text-anchor="middle">H₂KG-backed graph</text><text class="b" x="130" y="320">Hydrogen-domain workflow anchors</text><text class="b" x="130" y="355">Parameter record → property occurrence</text><text class="b" x="130" y="390">DataPoint → property, measurement, analysis</text><text class="b" x="130" y="425">QUDT + PROV-O + DCTERMS</text>
<rect class="c" x="790" y="240" rx="18" width="520" height="230"/><text class="h" x="1050" y="280" text-anchor="middle">CHAMEO-backed graph</text><text class="b" x="830" y="320">Native characterization procedures and data</text><text class="b" x="830" y="355">Declared EMMO import semantics</text><text class="b" x="830" y="390">QUDT + PROV-O + DCTERMS shared layer</text><text class="b" x="830" y="425">3 explicit application bridge relations</text>
<path class="a" d="M350 470 L540 560"/><path class="a" d="M1050 470 L860 560"/>
<rect class="s" x="280" y="560" rx="18" width="840" height="150"/><text class="h" x="700" y="600" text-anchor="middle">Common competency evaluation</text><text class="b" x="700" y="638" text-anchor="middle">50 identical plain-language questions and answer contracts</text><text class="b" x="700" y="670" text-anchor="middle">Ontology-specific SPARQL · exact row-multiset comparison · ontology-specific SHACL</text><text class="b" x="700" y="700" text-anchor="middle">H₂KG {q['h2kg_passed']}/50 passed · CHAMEO {q['chameo_passed']}/50 passed · no overall score</text>
<text class="b" x="700" y="755" text-anchor="middle">Competency demonstration only: not scientific validation, search-performance evaluation, or workflow execution</text></svg>"""


def build_chameo_dataset_from_manifest(
    manifest: dict[str, Any],
    *,
    include_application_bridges: bool,
) -> tuple[Dataset, list[dict[str, Any]], list[dict[str, Any]]]:
    """Construct a CHAMEO ABox directly from the neutral workbook manifest.

    The strict benchmark calls this with application bridges disabled.  That
    mode still permits assertions from CHAMEO, its declared EMMO imports, and
    shared standards, but it does not create relations to repair ontology gaps.
    """

    dataset = Dataset(default_union=False)
    _bind(dataset)
    schema = dataset.graph(_graph_iri("schema"))
    _bind(schema)
    _add_local_schema(schema)
    workbook = URIRef(f"{CMP}source/workbook-{manifest['source']['sha256'].lower()[:16]}")
    schema.add((workbook, RDF.type, APP.WorkbookSnapshot))
    schema.add((workbook, DCTERMS.title, Literal(manifest["source"]["title"])))
    schema.add((workbook, DCTERMS.identifier, Literal(manifest["source"]["sha256"])))
    schema.add((workbook, DCTERMS.description, Literal(manifest["source"]["redistribution"])))
    case_summaries = [
        _build_case(
            dataset,
            case,
            workbook,
            include_application_bridges=include_application_bridges,
        )
        for case in manifest["cases"]
    ]
    mapping_rows = [row for case in case_summaries for row in case.pop("mapping_rows")]
    return dataset, case_summaries, mapping_rows


def build_characterization_comparison(
    manifest_path: str | Path,
    h2kg_output_dir: str | Path,
    chameo_source_dir: str | Path,
    emmo_source_dir: str | Path,
    output_dir: str | Path,
    local_manuscript_dir: str | Path,
) -> dict[str, Any]:
    """Build the local CHAMEO graph and H2KG--CHAMEO comparison package."""

    manifest_path = Path(manifest_path)
    h2kg_output = Path(h2kg_output_dir)
    chameo_root = Path(chameo_source_dir)
    emmo_root = Path(emmo_source_dir)
    target = Path(output_dir)
    local = Path(local_manuscript_dir)
    _safe_replace_dir(target, target.parent)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise ValueError(f"Unsupported characterization manifest: {manifest.get('schema_version')}")
    if manifest.get("source", {}).get("sha256") != EXPECTED_WORKBOOK_SHA256:
        raise ValueError("The comparison requires the approved corrected-workbook fingerprint.")
    if len(manifest.get("cases", [])) != 8 or int(manifest.get("eligible_field_count", 0)) != 1635:
        raise ValueError("The comparison contract requires eight cases and 1,635 eligible source fields.")
    h2kg_workbench_path = h2kg_output / "characterization_query_workbench.json"
    h2kg_workbench = json.loads(h2kg_workbench_path.read_text(encoding="utf-8"))
    if len(h2kg_workbench.get("queries", [])) != 50:
        raise ValueError("The H2KG baseline must contain exactly 50 competency questions.")
    if h2kg_workbench.get("source_sha256") != manifest["source"]["sha256"]:
        raise ValueError("H2KG workbench and comparison manifest use different workbook fingerprints.")

    source_lock, source_tbox = _source_lock(chameo_root, emmo_root)
    shutil.copyfile(manifest_path, target / "characterization_source_manifest.json")
    dataset, case_summaries, mapping_rows = build_chameo_dataset_from_manifest(
        manifest,
        include_application_bridges=True,
    )
    if len(mapping_rows) != int(manifest["eligible_field_count"]):
        raise ValueError(f"Mapping coverage mismatch: {len(mapping_rows)} records")

    shapes = _shape_graph()
    shapes_context = dataset.graph(_graph_iri("shapes"))
    for triple in shapes:
        shapes_context.add(triple)
    before_tbox = _flatten(dataset)
    tbox_subset = _referenced_tbox_subset(before_tbox, source_tbox)
    tbox_context = dataset.graph(_graph_iri("referenced-tbox"))
    for triple in tbox_subset:
        tbox_context.add(triple)

    dataset.serialize(target / "chameo_characterization_knowledge_graph.trig", format="trig")
    dataset.serialize(target / "chameo_characterization_knowledge_graph.nq", format="nquads")
    flat = _flatten(dataset)
    flat.serialize(target / "chameo_characterization_knowledge_graph.ttl", format="turtle")
    canonical = Graph().parse(target / "chameo_characterization_knowledge_graph.ttl", format="turtle")
    canonical.serialize(target / "chameo_characterization_knowledge_graph.jsonld", format="json-ld", indent=2, use_native_types=False)
    shapes.serialize(target / "chameo_characterization_shapes.ttl", format="turtle")
    tbox_subset.serialize(target / "referenced_chameo_emmo_subset.ttl", format="turtle")
    cases_dir = ensure_dir(target / "cases")
    for summary in case_summaries:
        graph = Graph()
        _bind(graph)
        for graph_iri in (summary["source_graph"], summary["semantic_graph"], summary["validation_graph"]):
            for triple in dataset.graph(URIRef(graph_iri)):
                graph.add(triple)
        graph.serialize(cases_dir / f"{summary['key']}.ttl", format="turtle")

    validation = _validate_graph(flat, shapes, target)
    if not validation["conforms"] or any(item["conforms"] for item in validation["negative_tests"]):
        raise ValueError("CHAMEO SHACL validation contract failed.")
    parsed_turtle = Graph().parse(target / "chameo_characterization_knowledge_graph.ttl", format="turtle")
    parsed_jsonld = Graph().parse(target / "chameo_characterization_knowledge_graph.jsonld", format="json-ld")
    parity = isomorphic(parsed_turtle, parsed_jsonld)
    if not parity:
        raise ValueError("CHAMEO Turtle and JSON-LD exports are not RDF-isomorphic.")
    forbidden_iris = sorted({
        str(value) for triple in flat for value in triple
        if isinstance(value, URIRef) and str(value).startswith(H2KG_NAMESPACE)
    })
    if forbidden_iris:
        raise ValueError(f"H2KG ontology IRIs leaked into the CHAMEO graph: {forbidden_iris[:3]}")
    represented = set(flat.subjects(RDF.type, APP.SourceField))
    if len(represented) != int(manifest["eligible_field_count"]):
        raise ValueError("Not every eligible workbook field is represented in the CHAMEO graph.")

    chameo_queries = _run_queries(dataset, target, manifest)
    matrix, query_summary = _comparison_matrix(chameo_queries, h2kg_workbench)
    comparison_workbench = {
        "schema_version": BUILD_SCHEMA,
        "generated_at": now_iso(),
        "source_sha256": manifest["source"]["sha256"],
        "questions_reused_from": str(h2kg_workbench_path),
        "validation_summary": query_summary,
        "queries": chameo_queries,
    }
    dump_json(target / "chameo_query_workbench.json", comparison_workbench)
    complexity = _query_complexity_report(chameo_queries, h2kg_workbench)
    coverage = _coverage_report(mapping_rows)
    graph_stats = _graph_stats(dataset, case_summaries, mapping_rows)
    h2kg_stats = _h2kg_stats(h2kg_output)
    report = {
        "schema_version": BUILD_SCHEMA,
        "generated_at": now_iso(),
        "source_sha256": manifest["source"]["sha256"],
        "case_count": 8,
        "method_family_count": manifest["method_family_count"],
        "eligible_field_count": int(manifest["eligible_field_count"]),
        "represented_field_count": len(represented),
        "source_coverage_percent": 100.0,
        "excluded_personal_field_count": manifest["excluded_field_count"],
        "source_status_counts": {
            status: sum(case["source_status_counts"][status] for case in case_summaries)
            for status in SOURCE_STATUSES
        },
        "source_lock": {key: value for key, value in source_lock.items() if key != "files"},
        "chameo_graph": {
            **graph_stats,
            "rdf_triple_count": len(flat),
            "named_graph_count": sum(1 for _ in dataset.graphs()),
            "referenced_tbox_triples": len(tbox_subset),
            "turtle_jsonld_isomorphic": parity,
            "h2kg_ontology_iri_count": 0,
            "shacl_conforms": validation["conforms"],
            "negative_tests": validation["negative_tests"],
        },
        "h2kg_graph": h2kg_stats,
        "representation_coverage": coverage,
        "representation_patterns": _representation_patterns(),
        "query_comparison": query_summary,
        "cases": case_summaries,
        "interpretation": {
            "claim_boundary": "Bounded source-conformance and competency comparison; not scientific validation, general retrieval performance, workflow execution, scalability, or automatic FAIRness.",
            "shared_infrastructure": "QUDT, PROV-O, DCTERMS, and the neutral source-fidelity layer are not credited as native CHAMEO capability.",
        },
    }
    _write_reports(target, report, matrix, mapping_rows, source_lock, complexity)
    write_text(target / "comparison_report.html", _html_report(report, matrix))
    write_text(target / "README.md", _readme(report))
    _manuscript_materials(local, report, matrix)
    return report
