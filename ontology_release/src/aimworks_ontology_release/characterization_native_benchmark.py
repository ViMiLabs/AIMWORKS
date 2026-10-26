from __future__ import annotations

"""Strict H2KG--CHAMEO characterization benchmark.

The benchmark graph for each ontology contains only assertions made with that
ontology, its declared/reused standards, and ordinary RDF labels.  Local source
records and application bridge predicates are excluded from scored queries.
"""

import csv
import hashlib
import html
import json
import math
import shutil
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

from pyshacl import validate as shacl_validate
from rdflib import Dataset, Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import DCTERMS, OWL, PROV, SH, SKOS, XSD

from .characterization_comparison import (
    APP,
    CHAMEO,
    CHAMEO_COMMIT,
    CHAMEO_SHA256,
    CHAMEO_VERSION,
    CMP,
    EMMO,
    EMMO_COMMIT,
    EMMO_DETERMINATION,
    EMMO_HAS_DETERMINED_PROPERTY,
    EMMO_HAS_INPUT,
    EMMO_HAS_OUTPUT,
    EMMO_HAS_PROPERTY,
    EMMO_HAS_QUANTITY_VALUE,
    EMMO_IS_DESCRIPTION_FOR,
    EMMO_VERSION,
    QUDT,
    _query_complexity,
    _source_lock,
    build_chameo_dataset_from_manifest,
)
from .characterization_kg import (
    CASE_SPECS,
    EXPECTED_WORKBOOK_SHA256,
    GRAPH as HGRAPH,
    H2KG,
    KG,
    _compare_query_rows as _compare_query_row_multisets,
    _ground_truth_rows,
    _query_specs,
    _write_csv,
)
from .utils import dump_json, ensure_dir, now_iso, write_text


SCHEMA_VERSION = "h2kg-chameo-native-characterization-benchmark/v9"
BENCHMARK_ARCHIVE_COMMIT = "5382ff03eb4200416770da2bb4b32317fea69ff6"
H2KG_SEMANTIC_PREFIX = str(HGRAPH["semantic/"])
CHAMEO_GRAPH_PREFIX = "https://example.org/aimworks/chameo-characterization/graph/semantic/"
EMMO_PARAMETER = EMMO.EMMO_d1d436e7_72fc_49cd_863b_7bfb4ba5276a
EMMO_QUANTITY = EMMO.EMMO_0650c031_42b6_4f0a_b62d_d88f071da6bf
EMMO_PROPERTY = EMMO.EMMO_b7bcff25_ffc3_474e_9ab5_01b1664bd4ba
EMMO_REFERENT = EMMO.EMMO_6f5af708_f825_4feb_a0d1_a8d813d3022b

# The primary benchmark contract follows the specimen-to-result lifecycle in
# the source workbook. Requirements are named by scientific function rather
# than by the ontology that happens to implement them well. Each requirement
# is scored once across the complete eight-record population.
BALANCED_REQUIREMENTS: tuple[dict[str, Any], ...] = (
    {
        "id": "b01_measurement_context",
        "question": "Which specimen, instrument, and raw dataset belong to each measurement?",
        "selection_stratum": "measurement_context",
        "assessment_type": "query_based_retrieval",
        "source_basis": "Case identity, specimen field, method family, and raw-data output in the sanitized manifest.",
        "variables": ("caseKey", "measurementLabel", "specimenLabel", "instrumentLabel", "rawDatasetLabel"),
    },
    {
        "id": "b02_measurement_setting_identity",
        "question": "Which named measurement settings are associated with each measurement?",
        "selection_stratum": "measurement_settings",
        "assessment_type": "query_based_retrieval",
        "source_basis": "All characteristic and instrument fields classified as measurement settings in the sanitized manifest.",
        "variables": ("caseKey", "parameterLabel"),
    },
    {
        "id": "b03_valued_measurement_setting",
        "question": "Which measurement-setting record denotes which scientific characteristic, with what parsed numeric value and recognized unit?",
        "selection_stratum": "measurement_settings",
        "assessment_type": "query_retrieval_and_native_pattern_assessment",
        "source_basis": "Reported measurement settings with a distinct scientific characteristic, a parseable numeric value, and a recognized unit in the sanitized manifest.",
        "variables": ("caseKey", "parameterLabel", "propertyLabel", "value", "unit"),
    },
    {
        "id": "b04_preparation_input_output",
        "question": "Which material input and output are connected by each specimen-preparation step?",
        "selection_stratum": "specimen_preparation",
        "assessment_type": "query_based_retrieval",
        "source_basis": "Synthesis and specimen-preparation rows in all eight source records.",
        "variables": ("caseKey", "processLabel", "inputMaterialLabel", "outputMaterialLabel"),
    },
    {
        "id": "b05_processing_input_output",
        "question": "Which input and output datasets are connected by each preprocessing step?",
        "selection_stratum": "data_processing",
        "assessment_type": "query_based_retrieval",
        "source_basis": "Preprocessing rows in all eight source records.",
        "variables": ("caseKey", "processLabel", "inputDataLabel", "outputDataLabel"),
    },
    {
        "id": "b06_software_association",
        "question": "Which software is associated with each preparation, processing, or analysis step?",
        "selection_stratum": "software_traceability",
        "assessment_type": "query_based_retrieval",
        "source_basis": "Software fields in all workflow-table sections.",
        "variables": ("caseKey", "processLabel", "softwareLabel"),
    },
    {
        "id": "b07_analysis_lineage",
        "question": "Which input dataset, analysis step, software, and result form each analysis lineage?",
        "selection_stratum": "analysis_lineage",
        "assessment_type": "query_based_retrieval",
        "source_basis": "Analysis rows and software fields in all eight source records.",
        "variables": ("caseKey", "analysisLabel", "inputDataLabel", "resultLabel", "softwareLabel"),
    },
    {
        "id": "b08_individual_result_property_bearer",
        "question": "Which property and specimen are linked to each individual reported result?",
        "selection_stratum": "result_semantics",
        "assessment_type": "query_based_retrieval",
        "source_basis": "Every analysis target and the case specimen in the sanitized manifest.",
        "variables": ("caseKey", "resultLabel", "propertyLabel", "bearerLabel"),
    },
    {
        "id": "b09_parsed_result_value_and_unit",
        "question": "Which reported result properties have a parsed numeric value and recognized unit?",
        "selection_stratum": "result_semantics",
        "assessment_type": "query_based_retrieval",
        "source_basis": "Analysis outputs with a parseable numeric value and recognized unit in the sanitized manifest; property-unit compatibility is audited separately.",
        "variables": ("caseKey", "propertyLabel", "value", "unit"),
    },
    {
        "id": "b10_result_generation",
        "question": "Which analysis step generated each individual result?",
        "selection_stratum": "result_provenance",
        "assessment_type": "query_based_retrieval",
        "source_basis": "Analysis-step and target pairs in all eight source records.",
        "variables": ("caseKey", "analysisLabel", "resultLabel"),
    },
    {
        "id": "b11_workflow_task_grouping",
        "question": "Which named workflow groups the measurement and processing tasks for each case?",
        "selection_stratum": "workflow_structure",
        "assessment_type": "query_based_retrieval",
        "source_basis": "Each case is one bounded characterization workflow containing one measurement and its distinct source-defined steps.",
        "variables": ("caseKey", "workflowLabel", "taskCount"),
    },
    {
        "id": "b12_technique_occurrence_separation",
        "question": "Which technique description is explicitly distinguished from, and linked to, each measurement occurrence?",
        "selection_stratum": "methodology_description",
        "assessment_type": "query_retrieval_and_native_pattern_assessment",
        "source_basis": "The method-family descriptor and measurement occurrence recorded for every case.",
        "variables": ("caseKey", "techniqueLabel", "measurementLabel"),
    },
    {
        "id": "b13_case_method_specificity",
        "question": "Does each source record resolve to a dedicated native ontology class at the specificity of its selected characterization profile?",
        "selection_stratum": "selected_profile_vocabulary",
        "assessment_type": "native_vocabulary_coverage",
        "source_basis": "The curated characterization-profile identity recorded for each of the eight workbook records.",
        "variables": ("caseKey", "methodLabel"),
    },
)

# These questions inspect the neutral workbook/source-quality layer.  They are
# retained as controls but cannot support a claim about either ontology.
CONTROL_QUERY_IDS = {
    "q7_source_status_summary",
    "q9_conservative_quantity_findings",
    "q10_source_provenance_coverage",
    "q29_tem_source_status",
    "q30_sem_source_status",
    "q31_afm_source_status",
    "q32_fib_sem_source_status",
    "q33_ic_sem_source_status",
    "q34_neutron_tomography_source_status",
    "q35_synchrotron_radiography_source_status",
    "q36_synchrotron_tomography_source_status",
    "q47_qualified_source_fields",
    "q48_qualified_measurement_settings",
}

RESULT_VARIABLES = ("resultLabel", "propertyLabel", "bearerLabel", "value", "unit")
PARAMETER_VARIABLES = ("parameterLabel", "value", "unit")
CASE_BY_CONTEXT_NUMBER = {13 + index: spec.key for index, spec in enumerate(CASE_SPECS)}
CASE_BY_RESULT_NUMBER = {21 + index: spec.key for index, spec in enumerate(CASE_SPECS)}
CASE_BY_PARAMETER_NUMBER = {37 + index: spec.key for index, spec in enumerate(CASE_SPECS)}


def _safe_replace_dir(path: Path) -> None:
    resolved = path.resolve()
    parent = resolved.parent
    if resolved == parent or not str(resolved).startswith(str(parent)):
        raise ValueError(f"Unsafe output path: {resolved}")
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _bind(graph: Graph | Dataset) -> None:
    for prefix, namespace in {
        "h2kg": H2KG,
        "chameo": CHAMEO,
        "emmo": EMMO,
        "qudt": QUDT,
        "prov": PROV,
        "dcterms": DCTERMS,
        "rdf": RDF,
        "rdfs": RDFS,
        "sh": SH,
    }.items():
        graph.bind(prefix, namespace)


def _graph_key(identifier: URIRef, prefix: str) -> str:
    value = str(identifier)
    return value[len(prefix):] if value.startswith(prefix) else ""


def _strict_projection(
    source: Dataset,
    *,
    graph_prefix: str,
    forbidden_vocabulary: str,
    source_instance_prefix: str,
    remove_parameter_characteristics: bool = False,
) -> Dataset:
    """Copy semantic named graphs while excluding local adapter vocabulary."""

    target = Dataset(default_union=False)
    _bind(target)
    for context in source.graphs():
        if not str(context.identifier).startswith(graph_prefix):
            continue
        destination = target.graph(context.identifier)
        local_subjects = {
            subject
            for subject, _, obj in context.triples((None, RDF.type, None))
            if isinstance(obj, URIRef) and str(obj).startswith(forbidden_vocabulary)
        }
        removed_entities: set[URIRef] = set()
        if remove_parameter_characteristics:
            removed_entities.update(
                value
                for triple in context
                for value in (triple[0], triple[2])
                if isinstance(value, URIRef) and "/parameter-characteristic/" in str(value)
            )
            removed_entities.update(
                obj
                for subject in tuple(removed_entities)
                for obj in context.objects(subject, EMMO_HAS_QUANTITY_VALUE)
                if isinstance(obj, URIRef)
            )
        for subject, predicate, obj in context:
            if subject in local_subjects or subject in removed_entities or obj in removed_entities:
                continue
            if isinstance(predicate, URIRef) and str(predicate).startswith(forbidden_vocabulary):
                continue
            if isinstance(obj, URIRef) and str(obj).startswith(forbidden_vocabulary):
                continue
            if isinstance(obj, URIRef) and str(obj).startswith(source_instance_prefix):
                continue
            if predicate == PROV.wasDerivedFrom and isinstance(obj, URIRef):
                continue
            destination.add((subject, predicate, obj))
    return target


def _add_h2kg_workflow_grouping(dataset: Dataset, manifest: dict[str, Any]) -> None:
    """Represent each bounded case with H2KG's generic process/part pattern.

    H2KG does not provide CHAMEO's specialised workflow and task-description
    classes, but its published ``Process`` and ``hasPart`` terms can still
    group the source-defined activities without an application predicate.
    """

    activity_predicates = (
        H2KG.hasMeasurementSubject,
        H2KG.hasInputMaterial,
        H2KG.hasOutputMaterial,
        H2KG.hasInputData,
        H2KG.hasOutputData,
    )
    for case in manifest["cases"]:
        graph = dataset.graph(URIRef(f"{H2KG_SEMANTIC_PREFIX}{case['key']}"))
        activities = {
            subject
            for predicate in activity_predicates
            for subject in graph.subjects(predicate, None)
            if isinstance(subject, URIRef)
        }
        workflow = URIRef(
            f"https://w3id.org/h2kg/examples/characterization/{case['key']}/workflow"
        )
        graph.add((workflow, RDF.type, H2KG.Process))
        graph.add((workflow, RDFS.label, Literal(f"{case['title']} characterization workflow")))
        for activity in sorted(activities, key=str):
            graph.add((workflow, H2KG.hasPart, activity))


def _flatten(dataset: Dataset) -> Graph:
    graph = Graph()
    _bind(graph)
    for context in dataset.graphs():
        for triple in context:
            graph.add(triple)
    return graph


def _serialize_clean(resource: Dataset | Graph, path: Path, format_name: str, **kwargs: Any) -> Path:
    serialized = resource.serialize(format=format_name, **kwargs)
    if isinstance(serialized, bytes):
        serialized = serialized.decode("utf-8")
    return write_text(path, serialized.rstrip() + "\n")


def _serialize_dataset(dataset: Dataset, stem: Path) -> dict[str, Any]:
    _serialize_clean(dataset, stem.with_suffix(".trig"), "trig")
    _serialize_clean(dataset, stem.with_suffix(".nq"), "nquads")
    flat = _flatten(dataset)
    _serialize_clean(flat, stem.with_suffix(".ttl"), "turtle")
    parsed_turtle = Graph().parse(stem.with_suffix(".ttl"), format="turtle")
    _serialize_clean(parsed_turtle, stem.with_suffix(".jsonld"), "json-ld", indent=2)
    parsed_jsonld = Graph().parse(stem.with_suffix(".jsonld"), format="json-ld")
    return {
        "named_graph_count": sum(1 for _ in dataset.graphs()),
        "triple_count": len(flat),
        "semantic_entity_count": len({s for s in flat.subjects() if isinstance(s, URIRef)}),
        "turtle_jsonld_isomorphic": isomorphic(parsed_turtle, parsed_jsonld),
    }


def _number(query_id: str) -> int:
    return int(query_id[1:].split("_", 1)[0])


def _query_family(query_id: str) -> str:
    number = _number(query_id)
    if query_id in CONTROL_QUERY_IDS:
        return "source_quality_control"
    if number == 1:
        return "preparation_traceability"
    if number in {2, 8} or 37 <= number <= 44:
        return "measurement_parameter_identity_and_value"
    if number in {3, 11, 12, 49, 50}:
        return "data_processing_and_provenance"
    if number in {4, 6, 46} or 21 <= number <= 28:
        return "result_property_and_value"
    if number == 5 or 13 <= number <= 20:
        return "measurement_context"
    if number == 45:
        return "occurrence_accounting"
    return "other"


def _variables(query_id: str) -> tuple[str, ...]:
    number = _number(query_id)
    if number == 1:
        return ("resultLabel", "specimenLabel", "preparationLabel", "preparedMaterialLabel")
    if number == 2:
        return ("instrumentLabel", *PARAMETER_VARIABLES)
    if number == 3:
        return ("inputDataLabel", "analysisLabel", "softwareLabel", "resultLabel")
    if number == 4:
        return RESULT_VARIABLES
    if number == 5:
        return ("caseKey", "measurementLabel", "specimenLabel", "instrumentLabel", "rawDatasetLabel")
    if number == 6:
        return ("caseKey", *RESULT_VARIABLES)
    if number == 8:
        return ("caseKey", *PARAMETER_VARIABLES)
    if number == 11:
        return ("caseKey", "processLabel", "softwareLabel")
    if number == 12:
        return ("processLabel", "inputDataLabel", "outputDataLabel")
    if 13 <= number <= 20:
        return ("measurementLabel", "specimenLabel", "instrumentLabel", "rawDatasetLabel")
    if 21 <= number <= 28:
        return RESULT_VARIABLES
    if 37 <= number <= 44:
        return PARAMETER_VARIABLES
    if number == 45:
        return ("caseKey", "measurementCount", "resultCount")
    if number == 46:
        return ("caseKey", "propertyLabel", "value", "unit")
    if number == 49:
        return ("caseKey", "analysisLabel", "inputDataLabel", "resultLabel", "softwareLabel")
    if number == 50:
        return ("caseKey", "processLabel", "inputDataLabel", "outputDataLabel")
    raise KeyError(f"No strict semantic variables for {query_id}")


def _project_expected(query_id: str, manifest: dict[str, Any]) -> list[dict[str, str]]:
    variables = _variables(query_id)
    rows = [
        {variable: _normalize_cell(variable, row.get(variable, "")) for variable in variables}
        for row in _ground_truth_rows(query_id, manifest)
    ]
    return _sort_result_rows(rows, variables)


def _normalize_cell(variable: str, value: Any) -> str:
    """Compare numeric RDF values by value rather than lexical spelling."""

    text = "" if value is None else str(value)
    if variable != "value" or not text:
        return text
    try:
        normalized = format(Decimal(text), "f")
    except (InvalidOperation, ValueError):
        return text
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return "0" if normalized in {"-0", ""} else normalized


def _h_prefixes() -> str:
    return f"""PREFIX h2kg: <{H2KG}>
PREFIX qudt: <{QUDT}>
PREFIX prov: <{PROV}>
PREFIX rdf: <{RDF}>
PREFIX rdfs: <{RDFS}>
"""


def _c_prefixes() -> str:
    return f"""PREFIX chameo: <{CHAMEO}>
PREFIX emmo: <{EMMO}>
PREFIX qudt: <{QUDT}>
PREFIX prov: <{PROV}>
PREFIX rdf: <{RDF}>
PREFIX rdfs: <{RDFS}>
"""


def _h_graph(case_key: str) -> str:
    return f"<{H2KG_SEMANTIC_PREFIX}{case_key}>"


def _c_graph(case_key: str) -> str:
    return f"<{CHAMEO_GRAPH_PREFIX}{case_key}>"


def _h_measurement_query(case_key: str) -> str:
    return _h_prefixes() + f"""
SELECT ?measurementLabel ?specimenLabel ?instrumentLabel ?rawDatasetLabel WHERE {{
  GRAPH {_h_graph(case_key)} {{
    ?measurement a h2kg:Measurement ; rdfs:label ?measurementLabel ;
      h2kg:hasMeasurementSubject ?specimen ; h2kg:usesInstrument ?instrument ; h2kg:hasOutputData ?rawDataset .
    ?specimen rdfs:label ?specimenLabel . ?instrument rdfs:label ?instrumentLabel . ?rawDataset rdfs:label ?rawDatasetLabel .
  }}
}} ORDER BY ?measurementLabel
"""


def _c_measurement_query(case_key: str) -> str:
    return _c_prefixes() + f"""
SELECT ?measurementLabel ?specimenLabel ?instrumentLabel ?rawDatasetLabel WHERE {{
  GRAPH {_c_graph(case_key)} {{
    ?measurement a chameo:CharacterisationMeasurementProcess ; rdfs:label ?measurementLabel ;
      chameo:hasMeasurementSample ?specimen ; chameo:hasCharacterisationMeasurementInstrument ?instrument ;
      chameo:hasCharacterisationOutput ?rawDataset .
    ?rawDataset a chameo:RawData .
    ?specimen rdfs:label ?specimenLabel . ?instrument rdfs:label ?instrumentLabel . ?rawDataset rdfs:label ?rawDatasetLabel .
  }}
}} ORDER BY ?measurementLabel
"""


def _h_parameter_query(case_key: str, include_case: bool = False) -> str:
    case_var = "?caseKey " if include_case else ""
    case_bind = f'BIND("{case_key}" AS ?caseKey)' if include_case else ""
    return _h_prefixes() + f"""
SELECT {case_var}?parameterLabel ?value ?unit WHERE {{
  GRAPH {_h_graph(case_key)} {{
    ?measurement a h2kg:Measurement ; h2kg:hasParameter ?parameter .
    ?parameter rdfs:label ?parameterLabel ; h2kg:ofProperty ?property .
    OPTIONAL {{ ?property h2kg:hasQuantityValue ?qv . ?qv qudt:numericValue ?value ; qudt:unit ?unit . }}
    {case_bind}
  }}
}} ORDER BY ?parameterLabel
"""


def _c_parameter_query(case_key: str, include_case: bool = False) -> str:
    case_var = "?caseKey " if include_case else ""
    case_bind = f'BIND("{case_key}" AS ?caseKey)' if include_case else ""
    return _c_prefixes() + f"""
SELECT {case_var}?parameterLabel ?value ?unit WHERE {{
  GRAPH {_c_graph(case_key)} {{
    ?measurement a chameo:CharacterisationMeasurementProcess ; chameo:hasMeasurementParameter ?parameter .
    ?parameter rdfs:label ?parameterLabel .
    OPTIONAL {{
      ?parameter emmo:EMMO_e1097637_70d2_4895_973f_2396f04fa204 ?property .
      ?property emmo:EMMO_88b84515_a0df_47bb_8166_c7c8b893c1d8 ?qv .
      ?qv qudt:numericValue ?value ; qudt:unit ?unit .
    }}
    {case_bind}
  }}
}} ORDER BY ?parameterLabel
"""


def _h_result_query(case_key: str, include_case: bool = False, normalized_only: bool = False) -> str:
    case_var = "?caseKey " if include_case else ""
    case_bind = f'BIND("{case_key}" AS ?caseKey)' if include_case else ""
    quantity = (
        "?property h2kg:hasQuantityValue ?qv . ?qv qudt:numericValue ?value ; qudt:unit ?unit ."
        if normalized_only else
        "OPTIONAL { ?property h2kg:hasQuantityValue ?qv . ?qv qudt:numericValue ?value ; qudt:unit ?unit . }"
    )
    result_var = "" if normalized_only else "?resultLabel "
    bearer_var = "" if normalized_only else "?bearerLabel "
    labels = "" if normalized_only else "?result rdfs:label ?resultLabel . ?bearer rdfs:label ?bearerLabel ."
    return _h_prefixes() + f"""
SELECT {case_var}{result_var}?propertyLabel {bearer_var}?value ?unit WHERE {{
  GRAPH {_h_graph(case_key)} {{
    ?result a h2kg:DataPoint ; h2kg:ofProperty ?property .
    ?property rdfs:label ?propertyLabel ; h2kg:isCharacteristicOf ?bearer .
    {labels} {quantity} {case_bind}
  }}
}} ORDER BY ?propertyLabel
"""


def _c_result_query(case_key: str, include_case: bool = False, normalized_only: bool = False) -> str:
    case_var = "?caseKey " if include_case else ""
    case_bind = f'BIND("{case_key}" AS ?caseKey)' if include_case else ""
    quantity = (
        "?property emmo:EMMO_88b84515_a0df_47bb_8166_c7c8b893c1d8 ?qv . ?qv qudt:numericValue ?value ; qudt:unit ?unit ."
        if normalized_only else
        "OPTIONAL { ?property emmo:EMMO_88b84515_a0df_47bb_8166_c7c8b893c1d8 ?qv . ?qv qudt:numericValue ?value ; qudt:unit ?unit . }"
    )
    result_var = "" if normalized_only else "?resultLabel "
    bearer_var = "" if normalized_only else "?bearerLabel "
    labels = "" if normalized_only else "?result rdfs:label ?resultLabel . ?bearer rdfs:label ?bearerLabel ."
    return _c_prefixes() + f"""
SELECT {case_var}{result_var}?propertyLabel {bearer_var}?value ?unit WHERE {{
  GRAPH {_c_graph(case_key)} {{
    ?analysis a chameo:DataAnalysis, emmo:EMMO_10a5fd39_06aa_4648_9e70_f962a9cb2069 ;
      chameo:hasCharacterisationOutput ?result ;
      emmo:EMMO_802b7639_9498_4b47_ad45_1a087fe8fb85 ?property .
    ?result a chameo:SecondaryData .
    ?property a chameo:CharacterisationProperty ; rdfs:label ?propertyLabel .
    ?bearer chameo:hasCharacterisationProperty ?property .
    {labels} {quantity} {case_bind}
  }}
}} ORDER BY ?propertyLabel
"""


def _all_case_union(builder: Any, *, include_case: bool = True, normalized_only: bool = False) -> str:
    branches: list[str] = []
    for spec in CASE_SPECS:
        query = builder(spec.key, include_case=include_case, normalized_only=normalized_only)
        body = query.split("WHERE {", 1)[1].rsplit("}", 1)[0].strip()
        branches.append("{ " + body + " }")
    # Prefixes and SELECT are supplied by the caller; only UNION bodies are returned.
    return " UNION\n".join(branches)


def _query(ontology: str, query_id: str) -> str:
    number = _number(query_id)
    h = ontology == "h2kg"
    p = _h_prefixes() if h else _c_prefixes()
    graph = _h_graph if h else _c_graph
    measurement_query = _h_measurement_query if h else _c_measurement_query
    parameter_query = _h_parameter_query if h else _c_parameter_query
    result_query = _h_result_query if h else _c_result_query
    semantic_prefix = H2KG_SEMANTIC_PREFIX if h else CHAMEO_GRAPH_PREFIX
    if number == 1:
        if h:
            return p + f"""
SELECT DISTINCT ?resultLabel ?specimenLabel ?preparationLabel ?preparedMaterialLabel WHERE {{ GRAPH {graph('tem')} {{
  ?result a h2kg:DataPoint ; h2kg:fromMeasurement ?measurement ; h2kg:ofProperty ?property ; rdfs:label ?resultLabel .
  ?measurement h2kg:hasMeasurementSubject ?specimen . ?specimen rdfs:label ?specimenLabel . ?property h2kg:isCharacteristicOf ?specimen .
  ?preparation a h2kg:Manufacturing ; rdfs:label ?preparationLabel ; h2kg:hasOutputMaterial ?preparedMaterial .
  ?preparedMaterial rdfs:label ?preparedMaterialLabel .
  ?preparedMaterial (^h2kg:hasInputMaterial/h2kg:hasOutputMaterial)* ?specimen .
}} }} ORDER BY ?preparationLabel ?preparedMaterialLabel
"""
        return p + f"""
SELECT DISTINCT ?resultLabel ?specimenLabel ?preparationLabel ?preparedMaterialLabel WHERE {{ GRAPH {graph('tem')} {{
  ?measurement a chameo:CharacterisationMeasurementProcess ; chameo:hasMeasurementSample ?specimen ; chameo:hasCharacterisationOutput ?rawData .
  ?specimen rdfs:label ?specimenLabel .
  ?analysis a chameo:DataAnalysis ; chameo:hasCharacterisationInput ?analysisInput ; chameo:hasCharacterisationOutput ?result .
  ?result a chameo:SecondaryData ; rdfs:label ?resultLabel .
  ?rawData (^chameo:hasCharacterisationInput/chameo:hasCharacterisationOutput)* ?analysisInput .
  ?preparation a chameo:SamplePreparation ; rdfs:label ?preparationLabel ; emmo:EMMO_c4bace1d_4db0_4cd3_87e9_18122bae2840 ?preparedMaterial .
  ?preparedMaterial rdfs:label ?preparedMaterialLabel .
  ?preparedMaterial (^chameo:hasSampleForPreparation/emmo:EMMO_c4bace1d_4db0_4cd3_87e9_18122bae2840)* ?specimen .
}} }} ORDER BY ?preparationLabel ?preparedMaterialLabel
"""
    if number == 2:
        base = parameter_query("tem")
        instrument_pattern = (
            "?measurement h2kg:usesInstrument ?instrument ." if h else
            "?measurement chameo:hasCharacterisationMeasurementInstrument ?instrument ."
        )
        type_pattern = (
            "?measurement a h2kg:TransmissionElectronMicroscopyImaging ." if h else
            f"?technique a chameo:TransmissionElectronMicroscopy ; <{EMMO_IS_DESCRIPTION_FOR}> ?measurement ."
        )
        parameter_predicate = "h2kg:hasParameter" if h else "chameo:hasMeasurementParameter"
        property_pattern = (
            "?parameter h2kg:ofProperty ?property . OPTIONAL { ?property h2kg:hasQuantityValue ?qv . ?qv qudt:numericValue ?value ; qudt:unit ?unit . }"
            if h else
            "OPTIONAL { ?parameter emmo:EMMO_e1097637_70d2_4895_973f_2396f04fa204 ?property . ?property emmo:EMMO_88b84515_a0df_47bb_8166_c7c8b893c1d8 ?qv . ?qv qudt:numericValue ?value ; qudt:unit ?unit . }"
        )
        return p + f"""
SELECT ?instrumentLabel ?parameterLabel ?value ?unit WHERE {{ GRAPH {graph('tem')} {{
  {type_pattern} {instrument_pattern} ?instrument rdfs:label ?instrumentLabel .
  ?measurement {parameter_predicate} ?parameter . ?parameter rdfs:label ?parameterLabel . {property_pattern}
}} }} ORDER BY ?parameterLabel
"""
    if number == 3:
        if h:
            return p + f"""
SELECT ?inputDataLabel ?analysisLabel ?softwareLabel ?resultLabel WHERE {{ GRAPH {graph('tem')} {{
  ?result a h2kg:DataPoint ; rdfs:label ?resultLabel ; prov:wasGeneratedBy ?analysis .
  ?analysis rdfs:label ?analysisLabel ; h2kg:hasInputData ?inputData . ?inputData rdfs:label ?inputDataLabel .
  OPTIONAL {{ ?analysis h2kg:usesSoftware ?software . ?software rdfs:label ?softwareLabel . }}
}} }} ORDER BY ?resultLabel
"""
        return p + f"""
SELECT ?inputDataLabel ?analysisLabel ?softwareLabel ?resultLabel WHERE {{ GRAPH {graph('tem')} {{
  ?analysis a chameo:DataAnalysis ; rdfs:label ?analysisLabel ; chameo:hasCharacterisationInput ?inputData ; chameo:hasCharacterisationOutput ?result .
  ?result a chameo:SecondaryData ; rdfs:label ?resultLabel . ?inputData rdfs:label ?inputDataLabel .
  OPTIONAL {{ ?analysis chameo:hasCharacterisationSoftware ?software . ?software rdfs:label ?softwareLabel . }}
}} }} ORDER BY ?resultLabel
"""
    if number == 4:
        return result_query("tem")
    if number == 5:
        if h:
            body = """?measurement a h2kg:Measurement ; rdfs:label ?measurementLabel ; h2kg:hasMeasurementSubject ?specimen ; h2kg:usesInstrument ?instrument ; h2kg:hasOutputData ?rawDataset .
?specimen rdfs:label ?specimenLabel . ?instrument rdfs:label ?instrumentLabel . ?rawDataset rdfs:label ?rawDatasetLabel ."""
        else:
            body = """?measurement a chameo:CharacterisationMeasurementProcess ; rdfs:label ?measurementLabel ; chameo:hasMeasurementSample ?specimen ; chameo:hasCharacterisationMeasurementInstrument ?instrument ; chameo:hasCharacterisationOutput ?rawDataset .
?rawDataset a chameo:RawData . ?specimen rdfs:label ?specimenLabel . ?instrument rdfs:label ?instrumentLabel . ?rawDataset rdfs:label ?rawDatasetLabel ."""
        return p + f"""
SELECT ?caseKey ?measurementLabel ?specimenLabel ?instrumentLabel ?rawDatasetLabel WHERE {{
  GRAPH ?semanticGraph {{ {body} }} FILTER(STRSTARTS(STR(?semanticGraph), "{semantic_prefix}"))
  BIND(STRAFTER(STR(?semanticGraph), "{semantic_prefix}") AS ?caseKey)
}} ORDER BY ?caseKey
"""
    if number == 6:
        branches = _all_case_union(result_query, include_case=True)
        return p + f"SELECT ?caseKey ?resultLabel ?propertyLabel ?bearerLabel ?value ?unit WHERE {{ {branches} }} ORDER BY ?caseKey ?propertyLabel"
    if number == 8:
        branches = []
        for spec in CASE_SPECS:
            q = parameter_query(spec.key, include_case=True)
            branches.append("{ " + q.split("WHERE {", 1)[1].rsplit("}", 1)[0].strip() + " }")
        return p + "SELECT ?caseKey ?parameterLabel ?value ?unit WHERE { " + " UNION\n".join(branches) + " } ORDER BY ?caseKey ?parameterLabel"
    if number == 11:
        if h:
            body = "?process h2kg:usesSoftware ?software ; rdfs:label ?processLabel . ?software rdfs:label ?softwareLabel ."
        else:
            body = "?process chameo:hasCharacterisationSoftware ?software ; rdfs:label ?processLabel . ?software rdfs:label ?softwareLabel ."
        return p + f"""
SELECT DISTINCT ?caseKey ?processLabel ?softwareLabel WHERE {{ GRAPH ?semanticGraph {{ {body} }}
  FILTER(STRSTARTS(STR(?semanticGraph), "{semantic_prefix}")) BIND(STRAFTER(STR(?semanticGraph), "{semantic_prefix}") AS ?caseKey)
}} ORDER BY ?caseKey ?processLabel ?softwareLabel
"""
    if number == 12:
        return _processing_query(ontology, "neutron_tomography", include_case=False)
    if 13 <= number <= 20:
        return measurement_query(CASE_BY_CONTEXT_NUMBER[number])
    if 21 <= number <= 28:
        return result_query(CASE_BY_RESULT_NUMBER[number])
    if 37 <= number <= 44:
        return parameter_query(CASE_BY_PARAMETER_NUMBER[number])
    if number == 45:
        measurement_type = "h2kg:Measurement" if h else "chameo:CharacterisationMeasurementProcess"
        result_type = "h2kg:DataPoint" if h else "chameo:SecondaryData"
        return p + f"""
SELECT ?caseKey (COUNT(DISTINCT ?measurement) AS ?measurementCount) (COUNT(DISTINCT ?result) AS ?resultCount) WHERE {{
  GRAPH ?semanticGraph {{ ?measurement a {measurement_type} . OPTIONAL {{ ?result a {result_type} . }} }}
  FILTER(STRSTARTS(STR(?semanticGraph), "{semantic_prefix}")) BIND(STRAFTER(STR(?semanticGraph), "{semantic_prefix}") AS ?caseKey)
}} GROUP BY ?caseKey ORDER BY ?caseKey
"""
    if number == 46:
        branches = _all_case_union(result_query, include_case=True, normalized_only=True)
        return p + f"SELECT ?caseKey ?propertyLabel ?value ?unit WHERE {{ {branches} }} ORDER BY ?caseKey ?propertyLabel"
    if number == 49:
        if h:
            body = """?result a h2kg:DataPoint ; rdfs:label ?resultLabel ; prov:wasGeneratedBy ?analysis .
?analysis rdfs:label ?analysisLabel ; h2kg:hasInputData ?inputData . ?inputData rdfs:label ?inputDataLabel .
OPTIONAL { ?analysis h2kg:usesSoftware ?software . ?software rdfs:label ?softwareLabel . }"""
        else:
            body = """?analysis a chameo:DataAnalysis ; rdfs:label ?analysisLabel ; chameo:hasCharacterisationInput ?inputData ; chameo:hasCharacterisationOutput ?result .
?result a chameo:SecondaryData ; rdfs:label ?resultLabel . ?inputData rdfs:label ?inputDataLabel .
OPTIONAL { ?analysis chameo:hasCharacterisationSoftware ?software . ?software rdfs:label ?softwareLabel . }"""
        return p + f"""
SELECT DISTINCT ?caseKey ?analysisLabel ?inputDataLabel ?resultLabel ?softwareLabel WHERE {{ GRAPH ?semanticGraph {{ {body} }}
  FILTER(STRSTARTS(STR(?semanticGraph), "{semantic_prefix}")) BIND(STRAFTER(STR(?semanticGraph), "{semantic_prefix}") AS ?caseKey)
}} ORDER BY ?caseKey ?analysisLabel ?resultLabel ?inputDataLabel ?softwareLabel
"""
    if number == 50:
        return _processing_query(ontology, None, include_case=True)
    raise KeyError(f"No strict query for {query_id}")


def _processing_query(ontology: str, case_key: str | None, include_case: bool) -> str:
    h = ontology == "h2kg"
    p = _h_prefixes() if h else _c_prefixes()
    graph = f"?semanticGraph" if case_key is None else (_h_graph(case_key) if h else _c_graph(case_key))
    semantic_prefix = H2KG_SEMANTIC_PREFIX if h else CHAMEO_GRAPH_PREFIX
    if h:
        body = """?process a h2kg:DataProcessing ; rdfs:label ?processLabel ; h2kg:hasInputData ?inputData ; h2kg:hasOutputData ?outputData ."""
    else:
        body = """?process a chameo:DataPreparation ; rdfs:label ?processLabel ; chameo:hasCharacterisationInput ?inputData ; chameo:hasCharacterisationOutput ?outputData ."""
    case_var = "?caseKey " if include_case else ""
    graph_filter = ""
    if case_key is None:
        graph_filter = f'FILTER(STRSTARTS(STR(?semanticGraph), "{semantic_prefix}")) BIND(STRAFTER(STR(?semanticGraph), "{semantic_prefix}") AS ?caseKey)'
    return p + f"""
SELECT DISTINCT {case_var}?processLabel ?inputDataLabel ?outputDataLabel WHERE {{ GRAPH {graph} {{
  {body} ?inputData rdfs:label ?inputDataLabel . ?outputData rdfs:label ?outputDataLabel .
}} {graph_filter} }} ORDER BY {case_var}?processLabel ?inputDataLabel ?outputDataLabel
"""


def _execute_query(dataset: Dataset, query: str, variables: Iterable[str]) -> list[dict[str, str]]:
    result = dataset.query(query)
    actual_variables = [str(item) for item in result.vars]
    expected_variables = list(variables)
    if actual_variables != expected_variables:
        raise ValueError(f"Query variable contract mismatch: {actual_variables} != {expected_variables}")
    rows = [
        {name: _normalize_cell(name, row[index]) for index, name in enumerate(actual_variables)}
        for row in result
    ]
    return _sort_result_rows(rows, actual_variables)


def _sort_result_rows(
    rows: list[dict[str, str]],
    variables: Iterable[str],
) -> list[dict[str, str]]:
    """Keep generated evidence stable when an RDF engine returns an unordered set."""

    keys = tuple(variables)
    return sorted(rows, key=lambda row: tuple(str(row.get(key, "")) for key in keys))


def _compare_deduplicated_rows(
    expected: list[dict[str, Any]],
    observed: list[dict[str, Any]],
    variables: Iterable[str],
) -> dict[str, Any]:
    """Compare exact normalized row sets and report the actual benchmark policy."""

    keys = tuple(variables)

    def unique(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
        signatures = {
            tuple(_normalize_cell(key, row.get(key, "")) for key in keys)
            for row in rows
        }
        return [dict(zip(keys, values)) for values in sorted(signatures)]

    comparison = _compare_query_row_multisets(
        unique(expected),
        unique(observed),
        list(keys),
    )
    comparison["comparison_method"] = (
        "exact equality of deduplicated result sets after numeric lexical normalization, against expectations "
        "independently derived from the sanitized workbook manifest"
    )
    return comparison


def _f1(precision: float, recall: float) -> float:
    return round(2 * precision * recall / (precision + recall), 2) if precision + recall else 0.0


def _contract_diagnostic(
    contract_id: str,
    evidence: dict[str, dict[str, list[dict[str, str]]]],
    query_id: str,
    variables: tuple[str, ...],
    *,
    require_value_and_unit: bool = False,
) -> dict[str, Any]:
    def project(rows: list[dict[str, str]]) -> list[dict[str, str]]:
        selected = rows
        if require_value_and_unit:
            selected = [row for row in rows if row.get("value") and row.get("unit")]
        return [{key: row.get(key, "") for key in variables} for row in selected]

    expected = project(evidence[query_id]["expected"])
    result: dict[str, Any] = {
        "contract_id": contract_id,
        "source_query_id": query_id,
        "variables": list(variables),
        "expected_rows": len(expected),
    }
    for ontology in ("h2kg", "chameo"):
        comparison = _compare_deduplicated_rows(expected, project(evidence[query_id][ontology]), variables)
        result[ontology] = {
            "status": comparison["status"],
            "matched_rows": comparison["matched_row_count"],
            "missing_rows": comparison["missing_expected_row_count"],
            "unexpected_rows": comparison["unexpected_row_count"],
            "precision_percent": comparison["row_precision_percent"],
            "recall_percent": comparison["row_recall_percent"],
        }
    return result


def _run_benchmark_queries(
    h2kg: Dataset,
    chameo: Dataset,
    manifest: dict[str, Any],
    target: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    specs = {item["id"]: item for item in _query_specs()}
    matrix: list[dict[str, Any]] = []
    evidence: dict[str, dict[str, list[dict[str, str]]]] = {}
    for query_id, spec in specs.items():
        expected_full = _ground_truth_rows(query_id, manifest)
        if query_id in CONTROL_QUERY_IDS:
            matrix.append({
                "query_id": query_id,
                "plain_language_question": spec["question"],
                "query_family": _query_family(query_id),
                "assessment_scope": "unscored_source_or_quality_control",
                "expected_rows": len(expected_full),
                "h2kg_status": "not_scored",
                "chameo_status": "not_scored",
                "reason": "The answer depends on the neutral source/quality layer rather than ontology semantics.",
            })
            continue
        variables = _variables(query_id)
        expected = _project_expected(query_id, manifest)
        query_rows: dict[str, Any] = {}
        for ontology, dataset in (("h2kg", h2kg), ("chameo", chameo)):
            query = _query(ontology, query_id).strip()
            query_dir = ensure_dir(target / "queries" / ontology)
            result_dir = ensure_dir(target / "query_results" / ontology)
            write_text(query_dir / f"{query_id}.rq", query + "\n")
            observed = _execute_query(dataset, query, variables)
            comparison = _compare_deduplicated_rows(expected, observed, variables)
            comparison["row_f1_percent"] = _f1(
                comparison["row_precision_percent"], comparison["row_recall_percent"]
            )
            _write_csv(result_dir / f"{query_id}.csv", observed, list(variables))
            dump_json(result_dir / f"{query_id}.json", {"variables": variables, "rows": observed})
            dump_json(result_dir / f"{query_id}_comparison.json", comparison)
            query_rows[ontology] = {
                "observed": observed,
                "comparison": comparison,
                "complexity": _query_complexity(query),
            }
        ground_truth_dir = ensure_dir(target / "query_ground_truth")
        _write_csv(ground_truth_dir / f"{query_id}_expected.csv", expected, list(variables))
        dump_json(ground_truth_dir / f"{query_id}_expected.json", {
            "variables": variables,
            "rows": expected,
            "derivation": "Projected directly from the sanitized workbook manifest before graph querying.",
        })
        h_validation = query_rows["h2kg"]["comparison"]
        c_validation = query_rows["chameo"]["comparison"]
        evidence[query_id] = {
            "expected": expected,
            "h2kg": query_rows["h2kg"]["observed"],
            "chameo": query_rows["chameo"]["observed"],
        }
        h_complexity = query_rows["h2kg"]["complexity"]
        c_complexity = query_rows["chameo"]["complexity"]
        matrix.append({
            "query_id": query_id,
            "plain_language_question": spec["question"],
            "query_family": _query_family(query_id),
            "assessment_scope": "strict_ontology_semantics",
            "variables": ";".join(variables),
            "expected_rows": len(expected),
            "h2kg_status": h_validation["status"],
            "h2kg_matched": h_validation["matched_row_count"],
            "h2kg_missing": h_validation["missing_expected_row_count"],
            "h2kg_unexpected": h_validation["unexpected_row_count"],
            "h2kg_precision_percent": h_validation["row_precision_percent"],
            "h2kg_recall_percent": h_validation["row_recall_percent"],
            "h2kg_f1_percent": h_validation["row_f1_percent"],
            "chameo_status": c_validation["status"],
            "chameo_matched": c_validation["matched_row_count"],
            "chameo_missing": c_validation["missing_expected_row_count"],
            "chameo_unexpected": c_validation["unexpected_row_count"],
            "chameo_precision_percent": c_validation["row_precision_percent"],
            "chameo_recall_percent": c_validation["row_recall_percent"],
            "chameo_f1_percent": c_validation["row_f1_percent"],
            **{f"h2kg_{key}": value for key, value in h_complexity.items()},
            **{f"chameo_{key}": value for key, value in c_complexity.items()},
            "answer_parity": Counter(tuple(row[v] for v in variables) for row in query_rows["h2kg"]["observed"])
            == Counter(tuple(row[v] for v in variables) for row in query_rows["chameo"]["observed"]),
        })
    scored = [row for row in matrix if row["assessment_scope"] == "strict_ontology_semantics"]
    summary: dict[str, Any] = {
        "question_count": len(matrix),
        "scored_query_count": len(scored),
        "unscored_control_count": len(matrix) - len(scored),
        "expected_row_count": sum(int(row["expected_rows"]) for row in scored),
    }
    for ontology in ("h2kg", "chameo"):
        expected_count = summary["expected_row_count"]
        matched = sum(int(row[f"{ontology}_matched"]) for row in scored)
        observed = sum(int(row[f"{ontology}_matched"]) + int(row[f"{ontology}_unexpected"]) for row in scored)
        precision = 100.0 * matched / observed if observed else 0.0
        recall = 100.0 * matched / expected_count if expected_count else 100.0
        summary[ontology] = {
            "queries_passed": sum(row[f"{ontology}_status"] == "pass" for row in scored),
            "queries_partial_or_failed": sum(row[f"{ontology}_status"] != "pass" for row in scored),
            "matched_rows": matched,
            "observed_rows": observed,
            "micro_precision_percent": round(precision, 2),
            "micro_recall_percent": round(recall, 2),
            "micro_f1_percent": _f1(precision, recall),
        }
    summary["by_query_family"] = {}
    for family in sorted({row["query_family"] for row in scored}):
        subset = [row for row in scored if row["query_family"] == family]
        family_summary: dict[str, Any] = {
            "query_count": len(subset),
            "expected_rows": sum(int(row["expected_rows"]) for row in subset),
        }
        for ontology in ("h2kg", "chameo"):
            matched = sum(int(row[f"{ontology}_matched"]) for row in subset)
            observed = sum(
                int(row[f"{ontology}_matched"]) + int(row[f"{ontology}_unexpected"])
                for row in subset
            )
            expected = family_summary["expected_rows"]
            precision = 100.0 * matched / observed if observed else 0.0
            recall = 100.0 * matched / expected if expected else 100.0
            family_summary[ontology] = {
                "queries_passed": sum(row[f"{ontology}_status"] == "pass" for row in subset),
                "matched_rows": matched,
                "observed_rows": observed,
                "precision_percent": round(precision, 2),
                "recall_percent": round(recall, 2),
            }
        summary["by_query_family"][family] = family_summary
    summary["semantic_contract_diagnostics"] = [
        _contract_diagnostic(
            "measurement_context",
            evidence,
            "q5_all_measurement_contexts",
            ("caseKey", "measurementLabel", "specimenLabel", "instrumentLabel", "rawDatasetLabel"),
        ),
        _contract_diagnostic(
            "measurement_parameter_identity",
            evidence,
            "q8_all_measurement_parameters",
            ("caseKey", "parameterLabel"),
        ),
        _contract_diagnostic(
            "normalized_measurement_parameter_value",
            evidence,
            "q8_all_measurement_parameters",
            ("caseKey", "parameterLabel", "value", "unit"),
            require_value_and_unit=True,
        ),
        _contract_diagnostic(
            "result_property_bearer_association",
            evidence,
            "q6_all_result_records",
            ("caseKey", "resultLabel", "propertyLabel", "bearerLabel"),
        ),
        _contract_diagnostic(
            "normalized_result_value",
            evidence,
            "q46_normalized_result_quantities",
            ("caseKey", "propertyLabel", "value", "unit"),
            require_value_and_unit=True,
        ),
    ]
    return matrix, summary


def _strict_chameo_shapes() -> Graph:
    graph = Graph()
    _bind(graph)
    graph.parse(data=f"""
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix chameo: <{CHAMEO}> .
@prefix emmo: <{EMMO}> .

[] a sh:NodeShape ; sh:targetClass chameo:CharacterisationMeasurementProcess ;
  sh:property [ sh:path chameo:hasMeasurementSample ; sh:minCount 1 ; sh:class chameo:Sample ] ;
  sh:property [ sh:path chameo:hasCharacterisationMeasurementInstrument ; sh:minCount 1 ; sh:class chameo:CharacterisationMeasurementInstrument ] ;
  sh:property [ sh:path chameo:hasCharacterisationOutput ; sh:minCount 1 ; sh:class chameo:CharacterisationData ] .

[] a sh:NodeShape ; sh:targetClass chameo:DataAnalysis ;
  sh:property [ sh:path chameo:hasCharacterisationInput ; sh:minCount 1 ; sh:class chameo:CharacterisationData ] ;
  sh:property [ sh:path chameo:hasCharacterisationOutput ; sh:minCount 1 ; sh:class chameo:CharacterisationData ] ;
  sh:property [ sh:path emmo:EMMO_802b7639_9498_4b47_ad45_1a087fe8fb85 ; sh:minCount 1 ; sh:class chameo:CharacterisationProperty ] .
""", format="turtle")
    return graph


def _validate_strict_chameo(flat: Graph, target: Path) -> dict[str, Any]:
    shapes = _strict_chameo_shapes()
    _serialize_clean(shapes, target / "strict_chameo_shapes.ttl", "turtle")
    conforms, report_graph, report_text = shacl_validate(flat, shacl_graph=shapes, inference="rdfs")
    _serialize_clean(report_graph, target / "strict_chameo_shacl_report.ttl", "turtle")
    write_text(target / "strict_chameo_shacl_report.txt", str(report_text))
    scenarios = (
        ("measurement_subject", CHAMEO.hasMeasurementSample, CHAMEO.CharacterisationMeasurementProcess),
        ("measurement_instrument", CHAMEO.hasCharacterisationMeasurementInstrument, CHAMEO.CharacterisationMeasurementProcess),
        ("measurement_output", CHAMEO.hasCharacterisationOutput, CHAMEO.CharacterisationMeasurementProcess),
        ("analysis_input", CHAMEO.hasCharacterisationInput, CHAMEO.DataAnalysis),
        ("analysis_determined_property", EMMO_HAS_DETERMINED_PROPERTY, CHAMEO.DataAnalysis),
    )
    negative: list[dict[str, Any]] = []
    for name, predicate, subject_type in scenarios:
        graph = Graph()
        for triple in flat:
            graph.add(triple)
        subjects = sorted({
            subject
            for subject, _, _ in graph.triples((None, predicate, None))
            if (subject, RDF.type, subject_type) in graph
        }, key=str)
        removed = list(graph.triples((subjects[0], predicate, None))) if subjects else []
        for triple in removed:
            graph.remove(triple)
        negative_conforms, _, _ = shacl_validate(graph, shacl_graph=shapes, inference="rdfs")
        negative.append({
            "requirement": name,
            "removed_triples": [[str(value) for value in triple] for triple in removed],
            "conforms": bool(negative_conforms),
        })
    return {"conforms": bool(conforms), "negative_tests": negative}


def _capability_matrix() -> list[dict[str, str]]:
    return [
        {"capability": "Explicit workflow and task grouping", "h2kg": "generic_direct_native", "chameo": "specialized_direct_native", "h2kg_evidence": f"{H2KG.Process};{H2KG.hasPart}", "chameo_evidence": f"{CHAMEO.CharacterisationWorkflow};{CHAMEO.hasCharacterisationTask};{CHAMEO.CharacterisationTask}"},
        {"capability": "Measurement subject", "h2kg": "direct_native", "chameo": "direct_native", "h2kg_evidence": str(H2KG.hasMeasurementSubject), "chameo_evidence": str(CHAMEO.hasMeasurementSample)},
        {"capability": "Instrument used", "h2kg": "direct_native", "chameo": "direct_native", "h2kg_evidence": str(H2KG.usesInstrument), "chameo_evidence": str(CHAMEO.hasCharacterisationMeasurementInstrument)},
        {"capability": "Technique descriptor and occurrence", "h2kg": "occurrence_class_without_separate_descriptor", "chameo": "direct_via_declared_import", "h2kg_evidence": str(H2KG.Measurement), "chameo_evidence": f"{CHAMEO.CharacterisationTechnique};{EMMO_IS_DESCRIPTION_FOR};{CHAMEO.CharacterisationMeasurementProcess}"},
        {"capability": "Measurement parameter identity", "h2kg": "direct_native", "chameo": "direct_native", "h2kg_evidence": str(H2KG.hasParameter), "chameo_evidence": str(CHAMEO.hasMeasurementParameter)},
        {"capability": "Parameter-to-characteristic/value", "h2kg": "direct_native_plus_shared_value", "chameo": "native_pattern_not_identified_under_mapping_rules", "h2kg_evidence": f"{H2KG.ofProperty};{H2KG.hasQuantityValue}", "chameo_evidence": "Under the benchmark's permitted native encoding, no declared ancestry-compatible relation was identified from MeasurementParameter to a distinct Property or Quantity. This does not establish that all alternative CHAMEO/EMMO encodings are prohibited."},
        {"capability": "Raw and processed datasets", "h2kg": "direct_native", "chameo": "direct_native", "h2kg_evidence": f"{H2KG.hasInputData};{H2KG.hasOutputData}", "chameo_evidence": f"{CHAMEO.hasCharacterisationInput};{CHAMEO.hasCharacterisationOutput}"},
        {"capability": "Data processing and analysis", "h2kg": "direct_native", "chameo": "direct_native", "h2kg_evidence": f"{H2KG.DataProcessing};{H2KG.Process}", "chameo_evidence": f"{CHAMEO.DataPreparation};{CHAMEO.DataAnalysis}"},
        {"capability": "Software used", "h2kg": "direct_native", "chameo": "direct_native", "h2kg_evidence": str(H2KG.usesSoftware), "chameo_evidence": str(CHAMEO.hasCharacterisationSoftware)},
        {"capability": "Sample-to-property bearer", "h2kg": "direct_native", "chameo": "direct_native", "h2kg_evidence": str(H2KG.isCharacteristicOf), "chameo_evidence": str(CHAMEO.hasCharacterisationProperty)},
        {"capability": "Result-to-property association", "h2kg": "direct_native_result_level", "chameo": "declared_import_application_pattern", "h2kg_evidence": str(H2KG.ofProperty), "chameo_evidence": f"The source analysis is typed as {CHAMEO.DataAnalysis} and {EMMO_DETERMINATION}; {CHAMEO.hasCharacterisationOutput} identifies result data and {EMMO_HAS_DETERMINED_PROPERTY} identifies the determined property. CHAMEO does not entail that additional EMMO type from DataAnalysis, and the process-level pattern is ambiguous when one analysis has multiple results and properties."},
        {"capability": "Result generation provenance", "h2kg": "direct_shared_standard", "chameo": "direct_shared_standard", "h2kg_evidence": str(PROV.wasGeneratedBy), "chameo_evidence": str(PROV.wasGeneratedBy)},
        {"capability": "Normalized value and unit", "h2kg": "direct_native_plus_shared_standard", "chameo": "direct_import_plus_shared_standard_for_property", "h2kg_evidence": f"{H2KG.hasQuantityValue};{QUDT.unit}", "chameo_evidence": f"{EMMO_HAS_QUANTITY_VALUE};{QUDT.unit}"},
        {"capability": "Missingness and source-cell status", "h2kg": "source_layer_only", "chameo": "source_layer_only", "h2kg_evidence": "Not counted in strict ontology benchmark", "chameo_evidence": "Not counted in strict ontology benchmark"},
    ]


def _method_specificity_matrix() -> list[dict[str, str]]:
    techniques = {
        "tem": (str(CHAMEO.TransmissionElectronMicroscopy), "specific_native"),
        "sem": (str(CHAMEO.ScanningElectronMicroscopy), "specific_native"),
        "afm": (str(CHAMEO.AtomicForceMicroscopy), "specific_native"),
        "fib_sem": (
            f"{CHAMEO.Tomography};{CHAMEO.ScanningElectronMicroscopy}",
            "composite_broader_native",
        ),
        "ic_sem": (str(CHAMEO.ScanningElectronMicroscopy), "broader_native"),
        "neutron_tomography": (str(CHAMEO.Tomography), "broader_native"),
        "synchrotron_radiography": (str(CHAMEO.Tomography), "broader_native"),
        "synchrotron_tomography": (str(CHAMEO.Tomography), "broader_native"),
    }
    return [
        {
            "case": spec.key,
            "method": spec.title,
            "mapping_basis": (
                "The sheet key says radiography, but the curated MeasurementMethod and 3D reconstruction chain identify tomography."
                if spec.key == "synchrotron_radiography"
                else "Source method label and workflow evidence."
            ),
            "h2kg_term": str(H2KG[spec.measurement_class]),
            "h2kg_specificity": "specific_native",
            "chameo_term": techniques[spec.key][0],
            "chameo_specificity": techniques[spec.key][1],
        }
        for spec in CASE_SPECS
    ]


def _uri_ancestors(graph: Graph, start: URIRef) -> set[URIRef]:
    pending = [start]
    ancestors: set[URIRef] = set()
    while pending:
        current = pending.pop(0)
        if current in ancestors:
            continue
        ancestors.add(current)
        pending.extend(
            parent for parent in graph.objects(current, RDFS.subClassOf)
            if isinstance(parent, URIRef)
        )
    return ancestors


def _term_label(graph: Graph, term: URIRef) -> str:
    return str(next(
        iter(graph.objects(term, SKOS.prefLabel)),
        next(iter(graph.objects(term, RDFS.label)), ""),
    ))


def _ontology_evidence_audit(
    source_tbox: Graph,
    strict_h2kg: Dataset,
    strict_chameo: Dataset,
    source_lock: dict[str, Any],
) -> dict[str, Any]:
    parameter_ancestors = _uri_ancestors(source_tbox, CHAMEO.MeasurementParameter)
    data_analysis_ancestors = _uri_ancestors(source_tbox, CHAMEO.DataAnalysis)
    has_property_domains = {
        value for value in source_tbox.objects(EMMO_HAS_PROPERTY, RDFS.domain)
        if isinstance(value, URIRef)
    }
    has_quantity_domains = {
        value for value in source_tbox.objects(EMMO_HAS_QUANTITY_VALUE, RDFS.domain)
        if isinstance(value, URIRef)
    }

    applicable_property_relations: list[dict[str, str]] = []
    for relation in sorted(set(source_tbox.subjects(RDF.type, OWL.ObjectProperty)), key=str):
        if not isinstance(relation, URIRef):
            continue
        domains = {
            value for value in source_tbox.objects(relation, RDFS.domain)
            if isinstance(value, URIRef)
        }
        ranges = {
            value for value in source_tbox.objects(relation, RDFS.range)
            if isinstance(value, URIRef)
        }
        if not domains.intersection(parameter_ancestors):
            continue
        if any(EMMO_PROPERTY in _uri_ancestors(source_tbox, value) for value in ranges):
            applicable_property_relations.append({
                "iri": str(relation),
                "label": _term_label(source_tbox, relation),
            })

    applicable_value_relations: list[dict[str, str]] = []
    for relation_type in (OWL.ObjectProperty, OWL.DatatypeProperty):
        for relation in sorted(set(source_tbox.subjects(RDF.type, relation_type)), key=str):
            if not isinstance(relation, URIRef):
                continue
            domains = {
                value for value in source_tbox.objects(relation, RDFS.domain)
                if isinstance(value, URIRef)
            }
            label = _term_label(source_tbox, relation)
            if domains.intersection(parameter_ancestors) and "value" in label.casefold():
                applicable_value_relations.append({"iri": str(relation), "label": label})

    h2kg_flat = _flatten(strict_h2kg)
    chameo_flat = _flatten(strict_chameo)
    method_rows = _method_specificity_matrix()
    return {
        "schema_version": "h2kg-chameo-ontology-evidence-audit/v1",
        "source_lock_fingerprint": source_lock["lock_fingerprint"],
        "complete_import_closure": source_lock["complete_import_closure"],
        "direct_import_count": source_lock["direct_import_count"],
        "transitive_import_count": source_lock["transitive_import_count"],
        "resolved_import_count": source_lock["resolved_import_count"],
        "tbox_triple_count": len(source_tbox),
        "measurement_parameter": {
            "class_iri": str(CHAMEO.MeasurementParameter),
            "ancestor_path": [
                {"iri": str(term), "label": _term_label(source_tbox, term)}
                for term in sorted(parameter_ancestors, key=str)
            ],
            "is_emmo_mathematical_parameter": EMMO_PARAMETER in parameter_ancestors,
            "is_emmo_quantity": EMMO_QUANTITY in parameter_ancestors,
            "is_emmo_referent": EMMO_REFERENT in parameter_ancestors,
            "emmo_has_property_domain": sorted(map(str, has_property_domains)),
            "emmo_has_property_domain_applicable": bool(has_property_domains.intersection(parameter_ancestors)),
            "emmo_has_quantity_value_domain": sorted(map(str, has_quantity_domains)),
            "emmo_has_quantity_value_domain_applicable": bool(has_quantity_domains.intersection(parameter_ancestors)),
            "declared_applicable_property_relations": applicable_property_relations,
            "declared_applicable_value_relations": applicable_value_relations,
            "finding": "Within the benchmark's inspected native pattern and mapping rules, the pinned CHAMEO/EMMO closure supplies parameter identity but no declared ancestry-compatible relation from MeasurementParameter to a distinct valued scientific characteristic. This is not a general impossibility finding.",
        },
        "result_semantics": {
            "data_analysis_is_declared_emmo_determination": EMMO_DETERMINATION in data_analysis_ancestors,
            "chameo_has_sample_property_relation": (
                CHAMEO.hasCharacterisationProperty, RDF.type, OWL.ObjectProperty
            ) in source_tbox,
            "emmo_has_determined_property_relation": (
                EMMO_HAS_DETERMINED_PROPERTY, RDF.type, OWL.ObjectProperty
            ) in source_tbox,
            "finding": "CHAMEO supplies sample-to-property semantics. The scored result association uses an explicit EMMO Determination application pattern; CHAMEO DataAnalysis does not entail that type and the process-level pattern is ambiguous for multi-result analyses.",
        },
        "workflow_and_technique": {
            "chameo_workflow_class_present": (CHAMEO.CharacterisationWorkflow, RDF.type, OWL.Class) in source_tbox,
            "chameo_task_relation_present": (CHAMEO.hasCharacterisationTask, RDF.type, OWL.ObjectProperty) in source_tbox,
            "chameo_technique_class_present": (CHAMEO.CharacterisationTechnique, RDF.type, OWL.Class) in source_tbox,
            "emmo_description_relation_present": (EMMO_IS_DESCRIPTION_FOR, RDF.type, OWL.ObjectProperty) in source_tbox,
        },
        "scored_abox_assertions": {
            "h2kg_measurement_to_parameter": len(set(h2kg_flat.triples((None, H2KG.hasParameter, None)))),
            "h2kg_parameter_to_property": len(set(h2kg_flat.triples((None, H2KG.ofProperty, None)))),
            "h2kg_property_to_quantity_value": len(set(h2kg_flat.triples((None, H2KG.hasQuantityValue, None)))),
            "chameo_measurement_to_parameter": len(set(chameo_flat.triples((None, CHAMEO.hasMeasurementParameter, None)))),
            "chameo_parameter_to_distinct_property": len(applicable_property_relations),
            "h2kg_workflow_parts": len(set(h2kg_flat.triples((None, H2KG.hasPart, None)))),
            "chameo_workflow_tasks": len(set(chameo_flat.triples((None, CHAMEO.hasCharacterisationTask, None)))),
            "chameo_technique_to_occurrence": len(set(chameo_flat.triples((None, EMMO_IS_DESCRIPTION_FOR, None)))),
        },
        "method_specificity": [
            {
                **row,
                "chameo_terms_present": all(
                    (URIRef(iri), RDF.type, OWL.Class) in source_tbox
                    for iri in row["chameo_term"].split(";")
                ),
            }
            for row in method_rows
        ],
    }


def _mapping_policy_constraints() -> list[dict[str, str]]:
    return [
        {
            "requirement": "Measurement parameter identity",
            "h2kg": "no additional semantic relation",
            "chameo": "no additional semantic relation",
            "evidence": f"{H2KG.hasParameter};{CHAMEO.hasMeasurementParameter}",
        },
        {
            "requirement": "Measurement parameter characteristic, value, and unit",
            "h2kg": "supported by H2KG relation plus shared QUDT",
            "chameo": "not supported by the permitted native encoding",
            "evidence": "Under the frozen mapping rules, no declared ancestry-compatible relation was identified from CHAMEO MeasurementParameter to a distinct Property or Quantity. This is a bounded policy finding, not an impossibility proof.",
        },
        {
            "requirement": "Analysis-level determined property",
            "h2kg": "available through result-level ofProperty",
            "chameo": "no new predicate; explicit application typing and assertion from the declared EMMO import",
            "evidence": f"{EMMO_DETERMINATION};{EMMO_HAS_DETERMINED_PROPERTY}. CHAMEO DataAnalysis is not formally a subclass of EMMO Determination in the pinned graph.",
        },
        {
            "requirement": "Unambiguous result-data to property association",
            "h2kg": "supported by a direct result-level relation",
            "chameo": "the tested process-level encoding is ambiguous for one multi-result analysis",
            "evidence": "The tested process-level EMMO encoding yields two additional result/property combinations for the IC-SEM multi-output analysis; this does not characterize every permissible CHAMEO encoding.",
        },
        {
            "requirement": "Source-cell status and missingness",
            "h2kg": "neutral source layer required",
            "chameo": "neutral source layer required",
            "evidence": "Excluded from ontology-specific scoring for both graphs.",
        },
    ]


def _query_complexity_rows(matrix: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = ("triple_patterns", "joins", "optional_blocks", "property_paths", "lines")
    return [
        {
            "query_id": row["query_id"],
            "query_family": row["query_family"],
            **{f"h2kg_{key}": row.get(f"h2kg_{key}", "") for key in keys},
            **{f"chameo_{key}": row.get(f"chameo_{key}", "") for key in keys},
        }
        for row in matrix
        if row["assessment_scope"] == "strict_ontology_semantics"
    ]


def _write_case_graphs(dataset: Dataset, root: Path, graph_prefix: str) -> None:
    target = ensure_dir(root)
    for spec in CASE_SPECS:
        graph = Graph()
        _bind(graph)
        context = dataset.graph(URIRef(f"{graph_prefix}{spec.key}"))
        for triple in context:
            graph.add(triple)
        _serialize_clean(graph, target / f"{spec.key}.ttl", "turtle")


_EVIDENCE_PREDICATE_LABELS = {
    str(RDF.type): "type",
    str(H2KG.hasMeasurementSubject): "has measurement subject",
    str(H2KG.usesInstrument): "uses instrument",
    str(H2KG.hasOutputData): "has output data",
    str(H2KG.hasInputData): "has input data",
    str(H2KG.hasInputMaterial): "has input material",
    str(H2KG.hasOutputMaterial): "has output material",
    str(H2KG.hasParameter): "has parameter",
    str(H2KG.ofProperty): "of property",
    str(H2KG.hasQuantityValue): "has quantity value",
    str(H2KG.isCharacteristicOf): "is characteristic of",
    str(H2KG.usesSoftware): "uses software",
    str(H2KG.hasPart): "has part",
    str(H2KG.fromMeasurement): "from measurement",
    str(PROV.wasGeneratedBy): "was generated by",
    str(QUDT.numericValue): "numeric value",
    str(QUDT.unit): "unit",
    str(CHAMEO.hasMeasurementSample): "has measurement sample",
    str(CHAMEO.hasCharacterisationMeasurementInstrument): "uses instrument",
    str(CHAMEO.hasCharacterisationOutput): "has characterization output",
    str(CHAMEO.hasCharacterisationInput): "has characterization input",
    str(CHAMEO.hasMeasurementParameter): "has measurement parameter",
    str(CHAMEO.hasSampleForPreparation): "has sample for preparation",
    str(CHAMEO.hasCharacterisationSoftware): "uses characterization software",
    str(CHAMEO.hasCharacterisationProperty): "has characterization property",
    str(CHAMEO.hasCharacterisationTask): "has characterization task",
    str(EMMO_HAS_OUTPUT): "has output",
    str(EMMO_HAS_DETERMINED_PROPERTY): "has determined property",
    str(EMMO_HAS_QUANTITY_VALUE): "has quantity value",
    str(EMMO_IS_DESCRIPTION_FOR): "is description for",
}


def _evidence_term_id(term: Any) -> str:
    if isinstance(term, Literal):
        return f"literal:{term.n3()}"
    return str(term)


def _evidence_local_name(value: Any) -> str:
    text = str(value)
    if "#" in text:
        return text.rsplit("#", 1)[-1]
    return text.rstrip("/").rsplit("/", 1)[-1]


def _evidence_label(graph: Graph, term: Any) -> str:
    if isinstance(term, Literal):
        return str(term)
    label = next(iter(graph.objects(term, RDFS.label)), None)
    if label is not None:
        return str(label)
    local = _evidence_local_name(term)
    return local.replace("_", " ") if local else str(term)


def _evidence_role(graph: Graph, term: Any) -> str:
    if isinstance(term, Literal):
        return "literal"
    text = " ".join(
        _evidence_local_name(class_iri).casefold()
        for class_iri in graph.objects(term, RDF.type)
        if isinstance(class_iri, URIRef)
    )
    iri = str(term).casefold()
    if "workflow" in text or "/workflow" in iri:
        return "workflow"
    if "technique" in text or "technique-description" in iri:
        return "technique"
    if "instrument" in text or "/instrument/" in iri:
        return "instrument"
    if "parameter" in text or "/parameter/" in iri:
        return "parameter"
    if "measurement" in text or "/measurement/" in iri:
        return "measurement"
    if "software" in text or "/software/" in iri:
        return "software"
    if "property" in text or "characteristic" in text or "/property-occurrence/" in iri:
        return "property"
    if "quantity" in text or "quantity-value" in iri:
        return "quantity"
    if any(token in text for token in ("process", "preparation", "analysis", "task")):
        return "process"
    if "data" in text or "/data" in iri or "/result/" in iri:
        return "data"
    if any(token in text for token in ("matter", "material", "sample", "specimen")):
        return "matter"
    if str(term).startswith("http://qudt.org/vocab/unit/"):
        return "unit"
    return "other"


def _evidence_type_label(graph: Graph, term: Any) -> str:
    if isinstance(term, Literal):
        return "Literal"
    types = sorted({
        _evidence_local_name(class_iri).replace("_", " ")
        for class_iri in graph.objects(term, RDF.type)
        if isinstance(class_iri, URIRef)
    }, key=str.casefold)
    return types[0] if types else _evidence_role(graph, term).title()


def _semantic_edges(graph: Graph) -> list[tuple[Any, URIRef, Any]]:
    return sorted(
        (
            (subject, predicate, obj)
            for subject, predicate, obj in graph
            if predicate not in {RDF.type, RDFS.label}
        ),
        key=lambda triple: tuple(map(str, triple)),
    )


def _shortest_evidence_path(
    adjacency: dict[Any, list[tuple[Any, tuple[Any, URIRef, Any]]]],
    start: Any,
    goal: Any,
    max_depth: int = 5,
) -> list[tuple[Any, URIRef, Any]]:
    if start == goal:
        return []
    queue: list[tuple[Any, list[tuple[Any, URIRef, Any]]]] = [(start, [])]
    visited = {start}
    while queue:
        node, path = queue.pop(0)
        if len(path) >= max_depth:
            continue
        for neighbour, triple in adjacency.get(node, []):
            if neighbour in visited:
                continue
            next_path = [*path, triple]
            if neighbour == goal:
                return next_path
            visited.add(neighbour)
            queue.append((neighbour, next_path))
    return []


def _row_seed_terms(graph: Graph, row: dict[str, Any]) -> list[Any]:
    labels: dict[str, list[URIRef]] = {}
    for subject, label in graph.subject_objects(RDFS.label):
        if isinstance(subject, URIRef):
            labels.setdefault(str(label).strip().casefold(), []).append(subject)
    terms: list[Any] = []
    ignored = {"casekey", "taskcount"}
    for key, raw in row.items():
        if key.casefold() in ignored or raw in (None, ""):
            continue
        value = str(raw).strip()
        if value.startswith(("http://", "https://")):
            candidate = URIRef(value)
            if any(graph.triples((candidate, None, None))) or any(graph.triples((None, None, candidate))):
                terms.append(candidate)
            continue
        terms.extend(labels.get(value.casefold(), []))
        if key.casefold() == "value":
            terms.extend(
                literal
                for literal in set(graph.objects(None, QUDT.numericValue))
                if str(literal) == value
            )
    return list(dict.fromkeys(terms))


def _coverage_evidence_graph(ontology: str, row: dict[str, Any]) -> dict[str, Any]:
    item = next(
        entry for entry in _method_specificity_matrix()
        if entry["case"] == row.get("caseKey")
    )
    term_value = item[f"{ontology}_term"]
    specificity = item[f"{ontology}_specificity"]
    method_id = f"source-method:{item['case']}"
    nodes = [{
        "id": method_id,
        "label": item["method"],
        "type": "Source method identity",
        "role": "technique",
        "iri": "",
    }]
    edges: list[dict[str, str]] = []
    for index, iri in enumerate(term_value.split(";"), start=1):
        target = iri.strip()
        node_id = target or f"class:{index}"
        nodes.append({
            "id": node_id,
            "label": _evidence_local_name(target).replace("_", " "),
            "type": "Native ontology class",
            "role": "class",
            "iri": target,
        })
        edges.append({
            "id": f"coverage:{index}",
            "source": method_id,
            "target": node_id,
            "label": specificity.replace("_", " "),
            "predicate": "native class coverage audit",
        })
    return {
        "kind": "ontology_class_coverage_audit",
        "message": item["mapping_basis"],
        "nodes": nodes,
        "edges": edges,
        "truncated": False,
    }


def _row_evidence_graph(
    dataset: Dataset,
    ontology: str,
    requirement_id: str,
    row: dict[str, Any],
    status: str,
) -> dict[str, Any]:
    if requirement_id == "b13_case_method_specificity":
        return _coverage_evidence_graph(ontology, row)
    graph_prefix = H2KG_SEMANTIC_PREFIX if ontology == "h2kg" else CHAMEO_GRAPH_PREFIX
    case_key = str(row.get("caseKey") or "")
    graph = dataset.graph(URIRef(f"{graph_prefix}{case_key}"))
    semantic_edges = _semantic_edges(graph)
    adjacency: dict[Any, list[tuple[Any, tuple[Any, URIRef, Any]]]] = {}
    for triple in semantic_edges:
        subject, _, obj = triple
        adjacency.setdefault(subject, []).append((obj, triple))
        adjacency.setdefault(obj, []).append((subject, triple))
    seeds = _row_seed_terms(graph, row)
    selected: set[tuple[Any, URIRef, Any]] = set()
    connected_seeds: set[Any] = set()
    for index, start in enumerate(seeds):
        for goal in seeds[index + 1:]:
            path = _shortest_evidence_path(adjacency, start, goal)
            if path:
                selected.update(path)
                connected_seeds.update((start, goal))
    for seed in seeds:
        if seed in connected_seeds and selected:
            continue
        incident = [triple for _, triple in adjacency.get(seed, [])]
        selected.update(incident[:12])
    if requirement_id in {"b02_measurement_setting_identity", "b03_valued_measurement_setting"}:
        parent_predicate = H2KG.hasParameter if ontology == "h2kg" else CHAMEO.hasMeasurementParameter
        selected.update(
            triple
            for triple in semantic_edges
            if triple[1] == parent_predicate and triple[2] in seeds
        )
    elif requirement_id == "b11_workflow_task_grouping":
        part_predicate = H2KG.hasPart if ontology == "h2kg" else CHAMEO.hasCharacterisationTask
        selected.update(
            triple
            for triple in semantic_edges
            if triple[1] == part_predicate and triple[0] in seeds
        )
    if requirement_id in {"b03_valued_measurement_setting", "b09_parsed_result_value_and_unit"}:
        selected_terms = {
            term
            for subject, _, obj in selected
            for term in (subject, obj)
        }
        selected.update(
            triple
            for triple in semantic_edges
            if triple[1] == QUDT.numericValue and triple[0] in selected_terms
        )
    if not selected and seeds:
        for seed in seeds:
            selected.update(triple for _, triple in adjacency.get(seed, [])[:6])
    ordered_edges = sorted(selected, key=lambda triple: tuple(map(str, triple)))
    truncated = len(ordered_edges) > 24
    ordered_edges = ordered_edges[:24]
    terms: set[Any] = set(seeds)
    for subject, _, obj in ordered_edges:
        terms.update((subject, obj))
    nodes = [
        {
            "id": _evidence_term_id(term),
            "label": _evidence_label(graph, term),
            "type": _evidence_type_label(graph, term),
            "role": _evidence_role(graph, term),
            "iri": "" if isinstance(term, Literal) else str(term),
        }
        for term in sorted(terms, key=lambda value: (_evidence_role(graph, value), _evidence_label(graph, value), str(value)))
    ]
    edges = [
        {
            "id": f"edge:{index}",
            "source": _evidence_term_id(subject),
            "target": _evidence_term_id(obj),
            "label": _EVIDENCE_PREDICATE_LABELS.get(str(predicate), _evidence_local_name(predicate).replace("_", " ")),
            "predicate": str(predicate),
        }
        for index, (subject, predicate, obj) in enumerate(ordered_edges, start=1)
    ]
    gap = status == "not_supported_under_benchmark_mapping_rules"
    message = (
        "The native graph contains only the disconnected or partial evidence shown; the relation required to return this expected row is absent."
        if gap else
        "Only RDF resources and predicates participating in the selected answer are shown."
    )
    return {
        "kind": "gap_evidence" if gap else "rdf_answer_evidence",
        "message": message,
        "nodes": nodes,
        "edges": edges,
        "truncated": truncated,
    }


def _row_signature(row: dict[str, Any], variables: Iterable[str]) -> str:
    return json.dumps(
        [str(row.get(variable, "")) for variable in variables],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _write_comparison_workbench(
    target: Path,
    report: dict[str, Any],
    manifest: dict[str, Any],
    h2kg: Dataset,
    chameo: Dataset,
) -> None:
    matrix = {row["requirement_id"]: row for row in report["balanced_requirement_matrix"]}
    requirements: list[dict[str, Any]] = []
    evidence_root = ensure_dir(target / "web_evidence")
    for requirement in BALANCED_REQUIREMENTS:
        requirement_id = requirement["id"]
        variables = tuple(requirement["variables"])
        expected = _balanced_expected(requirement_id, manifest)
        item: dict[str, Any] = {
            "id": requirement_id,
            "question": requirement["question"],
            "selection_stratum": requirement["selection_stratum"],
            "assessment_type": requirement["assessment_type"],
            "source_basis": requirement["source_basis"],
            "variables": list(variables),
            "expected_rows": expected,
            "ontologies": {},
        }
        for ontology, dataset in (("h2kg", h2kg), ("chameo", chameo)):
            query, tier, rationale = _balanced_query(ontology, requirement_id)
            result_path = target / "balanced_results" / ontology / f"{requirement_id}.json"
            result = json.loads(result_path.read_text(encoding="utf-8"))
            observed = result["rows"]
            status = matrix[requirement_id][f"{ontology}_status"]
            unique_rows: dict[str, dict[str, Any]] = {}
            for row in [*observed, *expected]:
                unique_rows.setdefault(_row_signature(row, variables), row)
            entries = [
                {
                    "signature": signature,
                    "row": row,
                    "graph": _row_evidence_graph(
                        dataset,
                        ontology,
                        requirement_id,
                        row,
                        status,
                    ),
                }
                for signature, row in unique_rows.items()
            ]
            evidence_dir = ensure_dir(evidence_root / ontology)
            dump_json(evidence_dir / f"{requirement_id}.json", {
                "schema_version": "h2kg-chameo-query-evidence/v1",
                "requirement_id": requirement_id,
                "ontology": ontology,
                "entries": entries,
            })
            item["ontologies"][ontology] = {
                "status": status,
                "assessment_mode": matrix[requirement_id][f"{ontology}_assessment_mode"],
                "query_executed": matrix[requirement_id][f"{ontology}_query_executed"],
                "representation_tier": tier,
                "rationale": rationale,
                "query": (query or f"# No SPARQL query emitted.\n# {rationale}").strip(),
                "rows": observed,
                "comparison": result["comparison"],
                "evidence_path": f"web_evidence/{ontology}/{requirement_id}.json",
            }
        requirements.append(item)
    dump_json(target / "comparison_query_workbench.json", {
        "schema_version": "h2kg-chameo-query-workbench/v2",
        "generated_at": report["generated_at"],
        "source_sha256": report["source_sha256"],
        "default_requirement": "b03_valued_measurement_setting",
        "default_ontology": "h2kg",
        "summary": report["balanced_benchmark"],
        "conclusion": report["balanced_conclusion"],
        "requirements": requirements,
    })


def _benchmark_contract(manifest: dict[str, Any]) -> dict[str, Any]:
    specs = {item["id"]: item for item in _query_specs()}
    rows = [
        {
            "query_id": query_id,
            "plain_language_question": specs[query_id]["question"],
            "query_family": _query_family(query_id),
            "variables": list(_variables(query_id)) if query_id not in CONTROL_QUERY_IDS else [],
            "assessment_scope": (
                "unscored_source_or_quality_control"
                if query_id in CONTROL_QUERY_IDS
                else "strict_ontology_semantics"
            ),
        }
        for query_id in specs
    ]
    canonical = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return {
        "schema_version": "h2kg-chameo-benchmark-contract/v1",
        "source_manifest_sha256": manifest["source"]["sha256"],
        "question_count": len(rows),
        "contract_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest().upper(),
        "design_provenance": "The 50 questions predate the CHAMEO encoding and were inherited from the H2KG characterization application. They are source-grounded but not blinded, independently authored, or neutral with respect to H2KG's design.",
        "interpretation": "Historical asymmetric transfer diagnostic retained for reproducibility and excluded from the fair thirteen-requirement benchmark and its conclusion.",
        "questions": rows,
    }


def _deduplicate_rows(rows: Iterable[dict[str, Any]], variables: Iterable[str]) -> list[dict[str, str]]:
    names = tuple(variables)
    unique = {
        tuple(_normalize_cell(name, row.get(name, "")) for name in names)
        for row in rows
    }
    return [dict(zip(names, values)) for values in sorted(unique)]


def _label_key(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _expected_preparation_rows(manifest: dict[str, Any]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for case in manifest["cases"]:
        specimen_record = next(
            (
                record
                for record in case["direct_fields"]
                if _label_key(record.get("field")) == "specimen"
            ),
            None,
        )
        specimen_label = str(
            (specimen_record or {}).get("raw_value") or "Characterization specimen"
        ).strip()
        stage_targets: dict[tuple[str, str, str], set[str]] = {}
        for row in case["table_rows"]:
            values = row["values"]
            stage = (
                row["section"],
                str(values.get("Step") or "").strip(),
                str(values.get("Technique") or "").strip(),
            )
            stage_targets.setdefault(stage, set()).add(_label_key(values.get("Target")))
        groups: dict[tuple[Any, ...], dict[str, Any]] = {}
        for row in case["table_rows"]:
            if row["section"] not in {"syn", "sp"}:
                continue
            values = row["values"]
            stage = (
                row["section"],
                str(values.get("Step") or "").strip(),
                str(values.get("Technique") or "").strip(),
            )
            can_group = bool(stage[1] and stage[2]) and len(stage_targets[stage]) == 1
            key: tuple[Any, ...] = stage if can_group else (*stage, row["row"])
            group = groups.setdefault(key, {
                "label": str(values.get("Technique") or f"{row['section']} step {values.get('Step', row['row'])}"),
                "inputs": set(),
                "outputs": set(),
            })
            if values.get("Precursor"):
                group["inputs"].add(str(values["Precursor"]).strip())
            if values.get("Target"):
                output_label = (
                    specimen_label
                    if _label_key(values["Target"]) == "sample"
                    else str(values["Target"]).strip()
                )
                group["outputs"].add(output_label)
        for group in groups.values():
            for input_label in sorted(group["inputs"]):
                for output_label in sorted(group["outputs"]):
                    result.append({
                        "caseKey": case["key"],
                        "processLabel": group["label"],
                        "inputMaterialLabel": input_label,
                        "outputMaterialLabel": output_label,
                    })
    return _deduplicate_rows(
        result,
        ("caseKey", "processLabel", "inputMaterialLabel", "outputMaterialLabel"),
    )


def _expected_workflow_rows(manifest: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for case in manifest["cases"]:
        stage_targets: dict[tuple[str, str, str], set[str]] = {}
        for row in case["table_rows"]:
            values = row["values"]
            stage = (
                row["section"],
                str(values.get("Step") or "").strip(),
                str(values.get("Technique") or "").strip(),
            )
            stage_targets.setdefault(stage, set()).add(_label_key(values.get("Target")))
        process_keys: set[tuple[Any, ...]] = set()
        for row in case["table_rows"]:
            values = row["values"]
            stage = (
                row["section"],
                str(values.get("Step") or "").strip(),
                str(values.get("Technique") or "").strip(),
            )
            can_group = bool(stage[1] and stage[2]) and (
                row["section"] == "anal" or len(stage_targets[stage]) == 1
            )
            process_keys.add(stage if can_group else (*stage, row["row"]))
        rows.append({
            "caseKey": case["key"],
            "workflowLabel": f"{case['title']} characterization workflow",
            "taskCount": str(1 + len(process_keys)),
        })
    return rows


def _balanced_expected(requirement_id: str, manifest: dict[str, Any]) -> list[dict[str, str]]:
    requirement = next(item for item in BALANCED_REQUIREMENTS if item["id"] == requirement_id)
    variables = requirement["variables"]
    if requirement_id == "b01_measurement_context":
        rows = _ground_truth_rows("q5_all_measurement_contexts", manifest)
    elif requirement_id in {"b02_measurement_setting_identity", "b03_valued_measurement_setting"}:
        rows = _ground_truth_rows("q8_all_measurement_parameters", manifest)
        if requirement_id == "b03_valued_measurement_setting":
            rows = [
                {**row, "propertyLabel": row["parameterLabel"].removesuffix(" parameter record")}
                for row in rows
                if row.get("value") and row.get("unit")
            ]
    elif requirement_id == "b04_preparation_input_output":
        rows = _expected_preparation_rows(manifest)
    elif requirement_id == "b05_processing_input_output":
        rows = _ground_truth_rows("q50_preprocessing_transformations", manifest)
    elif requirement_id == "b06_software_association":
        rows = _ground_truth_rows("q11_software_provenance", manifest)
    elif requirement_id in {"b07_analysis_lineage", "b10_result_generation"}:
        rows = _ground_truth_rows("q49_analysis_provenance_across_cases", manifest)
    elif requirement_id == "b08_individual_result_property_bearer":
        rows = _ground_truth_rows("q6_all_result_records", manifest)
    elif requirement_id == "b09_parsed_result_value_and_unit":
        rows = _ground_truth_rows("q46_normalized_result_quantities", manifest)
    elif requirement_id == "b11_workflow_task_grouping":
        rows = _expected_workflow_rows(manifest)
    elif requirement_id == "b12_technique_occurrence_separation":
        rows = [
            {
                "caseKey": case["key"],
                "techniqueLabel": case["title"],
                "measurementLabel": f"{case['title']} measurement",
            }
            for case in manifest["cases"]
        ]
    elif requirement_id == "b13_case_method_specificity":
        rows = [
            {"caseKey": case["key"], "methodLabel": case["title"]}
            for case in manifest["cases"]
        ]
    else:
        raise KeyError(f"Unknown balanced benchmark requirement: {requirement_id}")
    return _deduplicate_rows(rows, variables)


def _benchmark_population_audit(manifest: dict[str, Any]) -> dict[str, Any]:
    """Describe the scored records, unique profiles, and value eligibility."""

    cases: list[dict[str, Any]] = manifest["cases"]
    profile_groups: dict[str, list[str]] = {}
    case_rows: list[dict[str, Any]] = []
    specificity = {row["case"]: row for row in _method_specificity_matrix()}

    for case in cases:
        profile_payload = {
            "acquisition_and_instrument": sorted(
                (
                    {
                        "section": record["section"],
                        "field": record["field"],
                        "raw_value": record.get("raw_value"),
                        "status": record["status"],
                    }
                    for record in case["direct_fields"]
                    if record["section"] in {"char", "inst"}
                ),
                key=lambda item: (item["section"], item["field"]),
            ),
            "workflow_rows": [
                {"section": row["section"], "values": row["values"]}
                for row in case["table_rows"]
            ],
        }
        profile_text = json.dumps(
            profile_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        profile_id = hashlib.sha256(profile_text.encode("utf-8")).hexdigest()[:16]
        profile_groups.setdefault(profile_id, []).append(case["key"])
        method_record = next(
            (
                record
                for record in case["direct_fields"]
                if _label_key(record.get("field")) == "measurementmethod"
            ),
            None,
        )
        source_method = str((method_record or {}).get("raw_value") or "").strip()
        label_conflict = (
            case["key"] == "synchrotron_radiography"
            and "tomography" in source_method.casefold()
        )
        case_rows.append({
            "case_key": case["key"],
            "sheet": case["sheet"],
            "record_title": case["title"],
            "method_family": case["family"],
            "source_measurement_method": source_method,
            "profile_id": profile_id,
            "profile_label_conflict": label_conflict,
            "h2kg_dedicated_class": specificity[case["key"]]["h2kg_specificity"] == "specific_native",
            "chameo_dedicated_class": specificity[case["key"]]["chameo_specificity"] == "specific_native",
        })

    setting_identity_rows = _balanced_expected("b02_measurement_setting_identity", manifest)
    valued_setting_rows = _balanced_expected("b03_valued_measurement_setting", manifest)
    valued_setting_keys = {
        (row["caseKey"], row["parameterLabel"])
        for row in valued_setting_rows
    }
    all_setting_rows = _ground_truth_rows("q8_all_measurement_parameters", manifest)
    setting_groups: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in all_setting_rows:
        setting_groups.setdefault((row["caseKey"], row["parameterLabel"]), []).append(row)
    setting_exclusions: list[dict[str, str]] = []
    for key, rows in sorted(setting_groups.items()):
        if key in valued_setting_keys:
            continue
        row = rows[0]
        status = row.get("statusLabel", "")
        reason = (
            status
            if status and status != "reported"
            else "reported_without_parseable_numeric_recognized_unit_pair"
        )
        setting_exclusions.append({
            "case_key": key[0],
            "setting": key[1],
            "source_status": status,
            "raw_value": row.get("rawValue", ""),
            "exclusion_reason": reason,
        })

    result_rows = _balanced_expected("b08_individual_result_property_bearer", manifest)
    parsed_result_rows = _balanced_expected("b09_parsed_result_value_and_unit", manifest)
    parsed_result_keys = {
        (row["caseKey"], row["propertyLabel"])
        for row in parsed_result_rows
    }
    all_result_rows = _ground_truth_rows("q6_all_result_records", manifest)
    result_exclusions = [
        {
            "case_key": row["caseKey"],
            "property": row["propertyLabel"],
            "raw_value": row.get("rawValue", ""),
            "exclusion_reason": "no_parseable_numeric_recognized_unit_pair",
        }
        for row in all_result_rows
        if (row["caseKey"], row["propertyLabel"]) not in parsed_result_keys
    ]
    quantity_compatibility = []
    for row in parsed_result_rows:
        saturation_concentration_conflict = (
            _label_key(row["propertyLabel"]) == "electrolyte saturation"
            and str(row["unit"]).endswith("MOL-PER-L")
        )
        quantity_compatibility.append({
            "case_key": row["caseKey"],
            "property": row["propertyLabel"],
            "value": row["value"],
            "unit": row["unit"],
            "compatibility_status": (
                "semantic_conflict"
                if saturation_concentration_conflict
                else "no_detected_property_unit_conflict"
            ),
            "verification_status": "not_independently_verified",
            "rationale": (
                "The source label denotes saturation, ordinarily a dimensionless fraction, "
                "whereas mol/L denotes amount-of-substance concentration. The source value "
                "remains queryable but is not treated as a scientifically compatible quantity."
                if saturation_concentration_conflict
                else "The explicit property/unit rule found no dimensional conflict; this does not verify the reported value scientifically."
            ),
        })
    compatibility_counts = dict(sorted(Counter(
        row["compatibility_status"] for row in quantity_compatibility
    ).items()))

    profile_rows = []
    for profile_id, keys in sorted(profile_groups.items()):
        members = [specificity[key] for key in keys]
        profile_rows.append({
            "profile_id": profile_id,
            "case_keys": keys,
            "record_count": len(keys),
            "h2kg_dedicated_class": all(row["h2kg_specificity"] == "specific_native" for row in members),
            "chameo_dedicated_class": all(row["chameo_specificity"] == "specific_native" for row in members),
        })

    return {
        "record_count": len(cases),
        "method_family_count": len({case["family"] for case in cases}),
        "unique_profile_count": len(profile_groups),
        "profile_identity_basis": "Exact equality of acquisition/instrument fields and workflow-table values after removing source coordinates and record identifiers.",
        "cases": case_rows,
        "profiles": profile_rows,
        "dedicated_class_coverage": {
            "record_level": {
                "h2kg": sum(row["h2kg_dedicated_class"] for row in case_rows),
                "chameo": sum(row["chameo_dedicated_class"] for row in case_rows),
                "denominator": len(case_rows),
            },
            "unique_profile_level": {
                "h2kg": sum(row["h2kg_dedicated_class"] for row in profile_rows),
                "chameo": sum(row["chameo_dedicated_class"] for row in profile_rows),
                "denominator": len(profile_rows),
            },
        },
        "measurement_settings": {
            "distinct_identities": len(setting_identity_rows),
            "parsed_recognized_unit_rows": len(valued_setting_rows),
            "excluded_from_parsed_unit_assessment": len(setting_exclusions),
            "exclusion_reason_counts": dict(sorted(Counter(
                row["exclusion_reason"] for row in setting_exclusions
            ).items())),
            "exclusions": setting_exclusions,
        },
        "reported_results": {
            "distinct_records": len(result_rows),
            "parsed_recognized_unit_rows": len(parsed_result_rows),
            "excluded_from_parsed_unit_assessment": len(result_exclusions),
            "exclusions": result_exclusions,
            "property_unit_compatibility_counts": compatibility_counts,
            "property_unit_compatibility": quantity_compatibility,
            "compatibility_scope": (
                "Rule-based property/unit compatibility screening is separate from numeric parsing and unit recognition; "
                "it is not independent verification of the reported measurements."
            ),
        },
    }


def _balanced_contract(manifest: dict[str, Any]) -> dict[str, Any]:
    requirements = [
        {**item, "variables": list(item["variables"])}
        for item in BALANCED_REQUIREMENTS
    ]
    conclusion_rules = [
        {
            "id": "r1_chameo_broad_methodology",
            "criterion": "CHAMEO is exact for measurement context, setting identity, preparation, processing, software, analysis lineage, result generation, workflow/task grouping, and technique/occurrence separation.",
        },
        {
            "id": "r2_chameo_unique_methodology_patterns",
            "criterion": "CHAMEO supplies specialised workflow/task and technique-description patterns; H2KG can group activities generically but lacks a separate technique-description pattern.",
        },
        {
            "id": "r3_h2kg_valued_settings",
            "criterion": "H2KG is exact, while no declared ancestry-compatible path from a CHAMEO measurement-parameter record to a distinct valued scientific characteristic was identified under the benchmark's permitted native-encoding rules.",
        },
        {
            "id": "r4_h2kg_individual_results",
            "criterion": "H2KG is exact for individual result/property/bearer associations and parsed numeric values with recognized units, while CHAMEO is not exact for the individual association contract.",
        },
        {
            "id": "r5_h2kg_method_specificity",
            "criterion": "H2KG has greater native class coverage at the predefined profile granularity than CHAMEO for the selected source records.",
        },
    ]
    canonical = json.dumps(
        {"requirements": requirements, "conclusion_rules": conclusion_rules},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    strata = Counter(item["selection_stratum"] for item in requirements)
    return {
        "schema_version": "h2kg-chameo-fair-characterization-contract/v5",
        "source_manifest_sha256": manifest["source"]["sha256"],
        "requirement_count": len(requirements),
        "selection_strata": dict(sorted(strata.items())),
        "contract_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest().upper(),
        "selection_protocol": [
            "Enumerate the specimen-to-result information lifecycle present in the sanitized workbook.",
            "Score each scientific relation or value pattern once over the full eight-record population; do not repeat it as global and per-record questions.",
            "Derive every requirement from information present in the application lifecycle and label it by scientific function, never by ontology origin.",
            "Include selected-profile native vocabulary coverage as an explicit scored requirement rather than an unscored post hoc argument.",
            "Generate expected rows from the manifest before executing ontology-specific SPARQL or native-pattern assessment.",
            "Compare deduplicated result sets after normalizing numeric lexical forms only; preserve all other selected values exactly.",
            "Treat numeric parsing and recognized-unit mapping separately from rule-based property/unit compatibility screening.",
            "Disallow local semantic bridge predicates and report shared standards and declared imports separately.",
            "Credit generic native patterns as successful while reporting their semantic specificity separately from specialised native patterns.",
        ],
        "inference_scope": "The resulting requirement-satisfaction decisions apply only to these thirteen frozen retrieval, native-pattern, and vocabulary-coverage assessments over eight source records representing seven unique profiles.",
        "conclusion_rules": conclusion_rules,
        "requirements": requirements,
    }


def _balanced_query(ontology: str, requirement_id: str) -> tuple[str | None, str, str]:
    h2kg = ontology == "h2kg"
    prefixes = _h_prefixes() if h2kg else _c_prefixes()
    graph_prefix = H2KG_SEMANTIC_PREFIX if h2kg else CHAMEO_GRAPH_PREFIX
    if requirement_id == "b01_measurement_context":
        return _query(ontology, "q5_all_measurement_contexts"), "direct_native", "Direct subject, instrument, and output-data relations."
    if requirement_id == "b02_measurement_setting_identity":
        body = (
            "?measurement a h2kg:Measurement ; h2kg:hasParameter ?parameter . ?parameter rdfs:label ?parameterLabel ."
            if h2kg else
            "?measurement a chameo:CharacterisationMeasurementProcess ; chameo:hasMeasurementParameter ?parameter . ?parameter rdfs:label ?parameterLabel ."
        )
        query = prefixes + f"""
SELECT DISTINCT ?caseKey ?parameterLabel WHERE {{
  GRAPH ?semanticGraph {{ {body} }}
  FILTER(STRSTARTS(STR(?semanticGraph), "{graph_prefix}"))
  BIND(STRAFTER(STR(?semanticGraph), "{graph_prefix}") AS ?caseKey)
}} ORDER BY ?caseKey ?parameterLabel
"""
        return query, "direct_native", "Direct measurement-to-parameter relation."
    if requirement_id == "b03_valued_measurement_setting":
        if not h2kg:
            return None, "native_pattern_not_identified_under_mapping_rules", "Under the benchmark's permitted native encoding, no declared ancestry-compatible relation was identified from CHAMEO MeasurementParameter to a distinct valued scientific characteristic. This bounded finding does not establish that every possible CHAMEO/EMMO representation is prohibited."
        query = prefixes + f"""
SELECT DISTINCT ?caseKey ?parameterLabel ?propertyLabel ?value ?unit WHERE {{
  GRAPH ?semanticGraph {{
    ?measurement a h2kg:Measurement ; h2kg:hasParameter ?parameter .
    ?parameter rdfs:label ?parameterLabel ; h2kg:ofProperty ?property .
    ?property rdfs:label ?propertyLabel ; h2kg:hasQuantityValue ?quantity .
    ?quantity qudt:numericValue ?value ; qudt:unit ?unit .
  }}
  FILTER(STRSTARTS(STR(?semanticGraph), "{graph_prefix}"))
  BIND(STRAFTER(STR(?semanticGraph), "{graph_prefix}") AS ?caseKey)
}} ORDER BY ?caseKey ?parameterLabel
"""
        return query, "direct_native_plus_shared_standard", "H2KG binds a parameter record to a property occurrence; QUDT supplies value and unit terms."
    if requirement_id == "b04_preparation_input_output":
        body = (
            "?process a h2kg:Manufacturing ; rdfs:label ?processLabel ; h2kg:hasInputMaterial ?input ; h2kg:hasOutputMaterial ?output ."
            if h2kg else
            f"?process a chameo:SamplePreparation ; rdfs:label ?processLabel ; chameo:hasSampleForPreparation ?input ; <{EMMO_HAS_OUTPUT}> ?output ."
        )
        query = prefixes + f"""
SELECT DISTINCT ?caseKey ?processLabel ?inputMaterialLabel ?outputMaterialLabel WHERE {{
  GRAPH ?semanticGraph {{
    {body}
    ?input rdfs:label ?inputMaterialLabel . ?output rdfs:label ?outputMaterialLabel .
  }}
  FILTER(STRSTARTS(STR(?semanticGraph), "{graph_prefix}"))
  BIND(STRAFTER(STR(?semanticGraph), "{graph_prefix}") AS ?caseKey)
}} ORDER BY ?caseKey ?processLabel ?inputMaterialLabel ?outputMaterialLabel
"""
        tier = "direct_native" if h2kg else "direct_native_plus_declared_import"
        return query, tier, "Native preparation semantics; CHAMEO uses its declared EMMO output relation."
    if requirement_id == "b05_processing_input_output":
        return _query(ontology, "q50_preprocessing_transformations"), "direct_native", "Direct processing input and output relations."
    if requirement_id == "b06_software_association":
        return _query(ontology, "q11_software_provenance"), "direct_native", "Direct process-to-software relation."
    if requirement_id == "b07_analysis_lineage":
        return _query(ontology, "q49_analysis_provenance_across_cases"), "direct_native", "Direct analysis input, output, and software relations."
    if requirement_id == "b08_individual_result_property_bearer":
        if h2kg:
            body = """?result a h2kg:DataPoint ; rdfs:label ?resultLabel ; h2kg:ofProperty ?property .
?property rdfs:label ?propertyLabel ; h2kg:isCharacteristicOf ?bearer . ?bearer rdfs:label ?bearerLabel ."""
            tier = "direct_native"
            rationale = "Each result record directly identifies one property occurrence and its bearer."
        else:
            body = """?analysis a chameo:DataAnalysis, emmo:EMMO_10a5fd39_06aa_4648_9e70_f962a9cb2069 ;
  chameo:hasCharacterisationOutput ?result ; emmo:EMMO_802b7639_9498_4b47_ad45_1a087fe8fb85 ?property .
?result a chameo:SecondaryData ; rdfs:label ?resultLabel .
?property a chameo:CharacterisationProperty ; rdfs:label ?propertyLabel .
?bearer chameo:hasCharacterisationProperty ?property ; rdfs:label ?bearerLabel ."""
            tier = "declared_import_process_level_pattern"
            rationale = "The imported process-level determination pattern can become ambiguous when one analysis has several outputs and properties."
        query = prefixes + f"""
SELECT DISTINCT ?caseKey ?resultLabel ?propertyLabel ?bearerLabel WHERE {{
  GRAPH ?semanticGraph {{ {body} }}
  FILTER(STRSTARTS(STR(?semanticGraph), "{graph_prefix}"))
  BIND(STRAFTER(STR(?semanticGraph), "{graph_prefix}") AS ?caseKey)
}} ORDER BY ?caseKey ?resultLabel ?propertyLabel
"""
        return query, tier, rationale
    if requirement_id == "b09_parsed_result_value_and_unit":
        return _query(ontology, "q46_normalized_result_quantities"), (
            "direct_native_plus_shared_standard" if h2kg else "declared_import_plus_shared_standard"
        ), "The ontology-specific result/property path is combined with shared QUDT value and unit terms."
    if requirement_id == "b10_result_generation":
        result_type = "h2kg:DataPoint" if h2kg else "chameo:SecondaryData"
        query = prefixes + f"""
SELECT DISTINCT ?caseKey ?analysisLabel ?resultLabel WHERE {{
  GRAPH ?semanticGraph {{
    ?result a {result_type} ; rdfs:label ?resultLabel ; prov:wasGeneratedBy ?analysis .
    ?analysis rdfs:label ?analysisLabel .
  }}
  FILTER(STRSTARTS(STR(?semanticGraph), "{graph_prefix}"))
  BIND(STRAFTER(STR(?semanticGraph), "{graph_prefix}") AS ?caseKey)
}} ORDER BY ?caseKey ?analysisLabel ?resultLabel
"""
        return query, "shared_standard", "Both graphs use the same PROV-O generation relation."
    if requirement_id == "b11_workflow_task_grouping":
        if h2kg:
            query = prefixes + f"""
SELECT ?caseKey ?workflowLabel (COUNT(DISTINCT ?task) AS ?taskCount) WHERE {{
  GRAPH ?semanticGraph {{
    ?workflow a h2kg:Process ; rdfs:label ?workflowLabel ; h2kg:hasPart ?task .
  }}
  FILTER(STRSTARTS(STR(?semanticGraph), "{graph_prefix}"))
  BIND(STRAFTER(STR(?semanticGraph), "{graph_prefix}") AS ?caseKey)
}} GROUP BY ?caseKey ?workflowLabel ORDER BY ?caseKey
"""
            return query, "generic_direct_native", "H2KG's generic Process/hasPart pattern groups the source-defined activities."
        query = prefixes + f"""
SELECT ?caseKey ?workflowLabel (COUNT(DISTINCT ?task) AS ?taskCount) WHERE {{
  GRAPH ?semanticGraph {{
    ?workflow a chameo:CharacterisationWorkflow ; rdfs:label ?workflowLabel ; chameo:hasCharacterisationTask ?task .
  }}
  FILTER(STRSTARTS(STR(?semanticGraph), "{graph_prefix}"))
  BIND(STRAFTER(STR(?semanticGraph), "{graph_prefix}") AS ?caseKey)
}} GROUP BY ?caseKey ?workflowLabel ORDER BY ?caseKey
"""
        return query, "direct_native", "CHAMEO explicitly groups CharacterisationTask descriptions in a CharacterisationWorkflow."
    if requirement_id == "b12_technique_occurrence_separation":
        if h2kg:
            return None, "native_pattern_not_identified_under_mapping_rules", "Under the benchmark's permitted native encoding, H2KG identifies the method by typing the measurement occurrence; no separate technique-description resource and linking relation was identified in the pinned core. This is not a general impossibility claim."
        query = prefixes + f"""
SELECT DISTINCT ?caseKey ?techniqueLabel ?measurementLabel WHERE {{
  GRAPH ?semanticGraph {{
    ?technique a ?techniqueType ; rdfs:label ?techniqueLabel ; <{EMMO_IS_DESCRIPTION_FOR}> ?measurement .
    ?measurement a chameo:CharacterisationMeasurementProcess ; rdfs:label ?measurementLabel .
    FILTER(?techniqueType != chameo:CharacterisationTask)
  }}
  FILTER(STRSTARTS(STR(?semanticGraph), "{graph_prefix}"))
  BIND(STRAFTER(STR(?semanticGraph), "{graph_prefix}") AS ?caseKey)
}} ORDER BY ?caseKey
"""
        return query, "direct_native_plus_declared_import", "CHAMEO supplies the technique descriptor and its declared EMMO import supplies the description-to-occurrence relation."
    if requirement_id == "b13_case_method_specificity":
        return None, "native_class_coverage_audit", "Evaluated against the ontology class inventory and source method identity rather than an ABox query."
    raise KeyError(f"Unknown balanced benchmark requirement: {requirement_id}")


def _run_balanced_benchmark(
    h2kg: Dataset,
    chameo: Dataset,
    manifest: dict[str, Any],
    target: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    matrix: list[dict[str, Any]] = []
    for requirement in BALANCED_REQUIREMENTS:
        requirement_id = requirement["id"]
        variables = tuple(requirement["variables"])
        expected = _balanced_expected(requirement_id, manifest)
        expected_dir = ensure_dir(target / "balanced_ground_truth")
        _write_csv(expected_dir / f"{requirement_id}.csv", expected, list(variables))
        dump_json(expected_dir / f"{requirement_id}.json", {
            "variables": list(variables),
            "rows": expected,
            "source_basis": requirement["source_basis"],
        })
        row: dict[str, Any] = {
            "requirement_id": requirement_id,
            "plain_language_question": requirement["question"],
            "selection_stratum": requirement["selection_stratum"],
            "assessment_type": requirement["assessment_type"],
            "expected_rows": len(expected),
            "variables": ";".join(variables),
        }
        for ontology, dataset in (("h2kg", h2kg), ("chameo", chameo)):
            query, tier, rationale = _balanced_query(ontology, requirement_id)
            query_dir = ensure_dir(target / "balanced_queries" / ontology)
            result_dir = ensure_dir(target / "balanced_results" / ontology)
            coverage_audit = requirement_id == "b13_case_method_specificity"
            if coverage_audit:
                ontology_assessment_mode = "native_vocabulary_coverage"
                query_executed = False
                specificity_key = f"{ontology}_specificity"
                observed = [
                    {"caseKey": item["case"], "methodLabel": item["method"]}
                    for item in _method_specificity_matrix()
                    if item[specificity_key] == "specific_native"
                ]
                write_text(
                    query_dir / f"{requirement_id}.rq",
                    "# Native-class coverage audit; see method_specificity_matrix.csv.\n",
                )
                complexity = {key: 0 for key in ("triple_patterns", "joins", "optional_blocks", "property_paths", "lines")}
            elif query is None:
                ontology_assessment_mode = "native_pattern_assessment"
                query_executed = False
                observed: list[dict[str, str]] = []
                write_text(
                    query_dir / f"{requirement_id}.rq",
                    f"# No query emitted: {rationale}\n",
                )
                complexity = {key: 0 for key in ("triple_patterns", "joins", "optional_blocks", "property_paths", "lines")}
            else:
                ontology_assessment_mode = "sparql_query"
                query_executed = True
                query = query.strip()
                write_text(query_dir / f"{requirement_id}.rq", query + "\n")
                observed = _deduplicate_rows(_execute_query(dataset, query, variables), variables)
                complexity = _query_complexity(query)
            comparison = _compare_deduplicated_rows(expected, observed, variables)
            status = (
                "exact"
                if comparison["exact_match"] else
                ("not_supported_under_benchmark_mapping_rules" if query is None and not coverage_audit else
                 ("partial" if comparison["matched_row_count"] else "no_match"))
            )
            _write_csv(result_dir / f"{requirement_id}.csv", observed, list(variables))
            dump_json(result_dir / f"{requirement_id}.json", {
                "variables": list(variables),
                "rows": observed,
                "comparison": comparison,
                "assessment_mode": ontology_assessment_mode,
                "query_executed": query_executed,
                "representation_tier": tier,
                "rationale": rationale,
            })
            row.update({
                f"{ontology}_status": status,
                f"{ontology}_assessment_mode": ontology_assessment_mode,
                f"{ontology}_query_executed": query_executed,
                f"{ontology}_representation_tier": tier,
                f"{ontology}_matched": comparison["matched_row_count"],
                f"{ontology}_missing": comparison["missing_expected_row_count"],
                f"{ontology}_unexpected": comparison["unexpected_row_count"],
                f"{ontology}_precision_percent": comparison["row_precision_percent"],
                f"{ontology}_recall_percent": comparison["row_recall_percent"],
                f"{ontology}_rationale": rationale,
                **{f"{ontology}_{key}": value for key, value in complexity.items()},
            })
        matrix.append(row)

    summary: dict[str, Any] = {
        "requirement_count": len(matrix),
        "selection_strata": dict(sorted(Counter(row["selection_stratum"] for row in matrix).items())),
        "assessment_type_counts": dict(sorted(Counter(row["assessment_type"] for row in matrix).items())),
        "aggregation_policy": "Each requirement is counted once. Numeric lexical forms are normalized and rows are deduplicated before set comparison; row counts are reported per requirement and are not pooled into a weighted quality score.",
    }
    for ontology in ("h2kg", "chameo"):
        summary[ontology] = {
            "exact_requirements": sum(row[f"{ontology}_status"] == "exact" for row in matrix),
            "partial_requirements": sum(row[f"{ontology}_status"] == "partial" for row in matrix),
            "native_pattern_not_supported_requirements": sum(
                row[f"{ontology}_status"] == "not_supported_under_benchmark_mapping_rules"
                for row in matrix
            ),
            "no_match_requirements": sum(row[f"{ontology}_status"] == "no_match" for row in matrix),
        }

    index = {row["requirement_id"]: row for row in matrix}
    h_specific = index["b13_case_method_specificity"]["h2kg_matched"]
    c_specific = index["b13_case_method_specificity"]["chameo_matched"]
    chameo_methodology_ids = {
        "b01_measurement_context", "b02_measurement_setting_identity",
        "b04_preparation_input_output", "b05_processing_input_output",
        "b06_software_association", "b07_analysis_lineage",
        "b09_parsed_result_value_and_unit", "b10_result_generation", "b11_workflow_task_grouping",
        "b12_technique_occurrence_separation",
    }
    rules = {
        "chameo_broad_characterization_methodology": all(
            index[item]["chameo_status"] == "exact" for item in chameo_methodology_ids
        ),
        "chameo_specialized_methodology_patterns": (
            index["b11_workflow_task_grouping"]["chameo_status"] == "exact"
            and index["b11_workflow_task_grouping"]["chameo_representation_tier"] == "direct_native"
            and index["b11_workflow_task_grouping"]["h2kg_status"] == "exact"
            and index["b11_workflow_task_grouping"]["h2kg_representation_tier"] == "generic_direct_native"
            and index["b12_technique_occurrence_separation"]["chameo_status"] == "exact"
            and index["b12_technique_occurrence_separation"]["h2kg_status"] == "not_supported_under_benchmark_mapping_rules"
        ),
        "h2kg_direct_valued_parameter_pattern": (
            index["b03_valued_measurement_setting"]["h2kg_status"] == "exact"
            and index["b03_valued_measurement_setting"]["chameo_status"] == "not_supported_under_benchmark_mapping_rules"
        ),
        "h2kg_individual_result_pattern": (
            index["b08_individual_result_property_bearer"]["h2kg_status"] == "exact"
            and index["b08_individual_result_property_bearer"]["chameo_status"] != "exact"
            and index["b09_parsed_result_value_and_unit"]["h2kg_status"] == "exact"
        ),
        "h2kg_greater_case_method_specificity": (
            index["b13_case_method_specificity"]["h2kg_status"] == "exact"
            and index["b13_case_method_specificity"]["chameo_status"] == "partial"
            and h_specific > c_specific
        ),
        "h2kg_specific_method_count": h_specific,
        "chameo_specific_method_count": c_specific,
    }
    rules["complementarity_conclusion_supported"] = all(
        rules[key] is True
        for key in (
            "chameo_broad_characterization_methodology",
            "chameo_specialized_methodology_patterns",
            "h2kg_direct_valued_parameter_pattern",
            "h2kg_individual_result_pattern",
            "h2kg_greater_case_method_specificity",
        )
    )
    conclusion = {
        "rules": rules,
        "supported": bool(rules["complementarity_conclusion_supported"]),
        "statement": (
            "For the selected characterization profiles, the benchmark supports a scoped complementarity conclusion: CHAMEO provides explicit characterization-methodology structures, while H₂KG provides greater native class coverage at the predefined profile granularity together with direct valued-parameter and individually provenance-linked result patterns."
            if rules["complementarity_conclusion_supported"] else
            "The frozen benchmark evidence did not satisfy every rule required for the proposed complementarity conclusion."
        ),
        "scope": "The 12/13 and 10/13 values are requirement-satisfaction rates under this frozen protocol, not general ontology-accuracy or quality scores. The benchmark covers eight source records representing seven unique profiles; governance, maintainability, reasoning performance, usability, and scalability were not measured.",
    }
    return matrix, summary, conclusion


def _html_report(report: dict[str, Any], matrix: list[dict[str, Any]]) -> str:
    summary = report["query_benchmark"]
    families = "".join(
        "<tr>"
        f"<td>{html.escape(name.replace('_', ' '))}</td>"
        f"<td>{values['query_count']}</td>"
        f"<td>{values['h2kg']['queries_passed']}/{values['query_count']}</td>"
        f"<td>{values['chameo']['queries_passed']}/{values['query_count']}</td>"
        f"<td>{values['chameo']['precision_percent']:.2f}%</td>"
        f"<td>{values['chameo']['recall_percent']:.2f}%</td>"
        "</tr>"
        for name, values in summary["by_query_family"].items()
    )
    diagnostics = "".join(
        "<tr>"
        f"<td>{html.escape(row['contract_id'].replace('_', ' '))}</td>"
        f"<td>{row['expected_rows']}</td>"
        f"<td>{row['h2kg']['matched_rows']} matched; {row['h2kg']['unexpected_rows']} additional</td>"
        f"<td>{row['chameo']['matched_rows']} matched; {row['chameo']['unexpected_rows']} additional</td>"
        "</tr>"
        for row in summary["semantic_contract_diagnostics"]
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>H2KG-CHAMEO characterization use-case comparison</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;max-width:1180px;margin:0 auto;padding:38px;color:#19313a;background:#f4f7f6}}h1,h2{{color:#123f46}}.card{{background:#fff;border:1px solid #cfdbd8;border-radius:14px;padding:22px;margin:18px 0;box-shadow:0 8px 24px #17343a12}}.metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}}.metric{{background:#e7f2ef;border-radius:10px;padding:16px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;border-bottom:1px solid #d8e1df;text-align:left;vertical-align:top}}th{{background:#174b53;color:#fff}}code{{background:#eef2f1;padding:2px 5px}}a{{color:#086a75}}</style></head>
<body><h1>H2KG-CHAMEO characterization use-case comparison</h1>
<p>Both application graphs were constructed independently from the same sanitized workbook manifest. Neither ontology was modified, no graph was translated from the other, and no local semantic bridge was allowed in scored graphs.</p>
<div class="metrics"><div class="metric"><strong>Cases</strong><br>8</div><div class="metric"><strong>Semantic contracts</strong><br>{summary['scored_query_count']}</div><div class="metric"><strong>H2KG exact contracts</strong><br>{summary['h2kg']['queries_passed']}/{summary['scored_query_count']}</div><div class="metric"><strong>CHAMEO exact contracts</strong><br>{summary['chameo']['queries_passed']}/{summary['scored_query_count']}</div></div>
<div class="card"><h2>Evaluation boundary</h2><p>The questions were inherited from the existing H2KG characterization application and predate the CHAMEO encoding. They therefore form an asymmetric use-case transfer test, not a neutral or general ontology ranking. The 13 source-quality questions are controls and are not credited to either ontology. QUDT and PROV-O are shared infrastructure, and CHAMEO receives explicit credit for declared EMMO-import patterns.</p></div>
<div class="card"><h2>Results by question family</h2><table><thead><tr><th>Family</th><th>Queries</th><th>H2KG exact</th><th>CHAMEO exact</th><th>CHAMEO precision</th><th>CHAMEO recall</th></tr></thead><tbody>{families}</tbody></table></div>
<div class="card"><h2>Non-duplicated semantic diagnostics</h2><table><thead><tr><th>Contract</th><th>Expected</th><th>H2KG</th><th>CHAMEO</th></tr></thead><tbody>{diagnostics}</tbody></table></div>
<div class="card"><h2>Interpretation</h2><p>This historical transfer diagnostic is excluded from the primary conclusion. For the selected records, CHAMEO supplies broad characterization workflow semantics, while H2KG supplies dedicated profile classes and direct valued-parameter and result-property paths. The tested EMMO process-level determination encoding is credited as an imported application assertion, including the two additional associations it produces for one multi-output analysis.</p></div>
<div class="card"><h2>Downloads</h2><p><a href="benchmark_contract.json">Benchmark contract</a> · <a href="native_query_matrix.csv">Query matrix</a> · <a href="native_capability_matrix.csv">Capability matrix</a> · <a href="mapping_policy_constraints.csv">Mapping-policy constraints</a> · <a href="native_benchmark_report.json">Complete report</a></p></div>
</body></html>"""


def _markdown_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> str:
    lines = [
        "| " + " | ".join(label for _, label in columns) + " |",
        "|" + "|".join("---" for _ in columns) + "|",
    ]
    for row in rows:
        values = [str(row.get(key, "")).replace("|", "\\|").replace("\n", " ") for key, _ in columns]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines) + "\n"


def _write_local_manuscript_legacy(local: Path, report: dict[str, Any], matrix: list[dict[str, Any]]) -> None:
    _safe_replace_dir(local)
    summary = report["query_benchmark"]
    methods = f"""## Ontology-independent characterization benchmark

The same sanitized workbook manifest (SHA-256 `{report['source_sha256']}`) was mapped independently to H₂KG and CHAMEO {CHAMEO_VERSION}. The CHAMEO graph used CHAMEO and its declared EMMO {EMMO_VERSION} imports; the H₂KG graph used H₂KG and its documented standards. No local semantic class or property was admitted to either scored graph. Ground-truth rows were generated directly from the manifest before SPARQL evaluation. Of 50 explicit questions, {summary['scored_query_count']} tested ontology semantics and {summary['unscored_control_count']} source-fidelity or quality-status functions and were therefore retained as unscored controls. Ontology-specific SPARQL was permitted, but every scored query used the same variables; numeric lexical forms were normalized, duplicate rows were removed over all selected variables, and the resulting sets were compared.

This historical question set used its recorded row comparison. Native, declared-import, shared-standard, and mapping-policy evidence was reported separately. Consequently, an absent permitted native relation produced a missing result rather than being repaired with an application bridge. Graph size and query complexity were descriptive only and were not combined into a ranking.
"""
    results = f"""## Results of the strict semantic comparison

H₂KG reproduced {summary['h2kg']['matched_rows']} of {summary['expected_row_count']} expected semantic rows and passed {summary['h2kg']['queries_passed']} of {summary['scored_query_count']} complete query contracts. CHAMEO reproduced {summary['chameo']['matched_rows']} rows and passed {summary['chameo']['queries_passed']} complete contracts. CHAMEO directly represented measurement subjects, instruments, technique descriptions, parameters, datasets, processing activities, software, and sample properties. Under the frozen mapping rules, no native assertion was identified that connected a measurement-parameter record to its valued characteristic. That bounded absence was not repaired in the benchmark graph and is not an impossibility claim.

For the measured characterization knowledge-graph scope, the findings indicate complementary capabilities. CHAMEO supplies a broad characterization-methodology model and explicit technique descriptions. H₂KG supplies dedicated classes for more of the selected profiles and direct parameter–property and result–property paths. Source-cell status and missingness were outside both strict semantic graphs and therefore cannot be presented as an advantage of either ontology.
"""
    limitations = """## Interpretation limits

This is a bounded representational diagnostic over eight source records. It does not establish scientific correctness, general search performance, execution capability, scalability, or automatic FAIRness. The ground truth is independent of graph querying but derives from the same workbook manifest as both ABoxes. Ontology-specific SPARQL measures whether the tested encodings expose the requested paths; it is not a test of one query formulation being universally optimal. Mapping-policy findings should not be interpreted as defects in CHAMEO's intended scope or as prohibitions on alternative encodings.
"""
    write_text(local / "methods_subsection.md", methods)
    write_text(local / "results_subsection.md", results)
    write_text(local / "limitations.md", limitations)
    write_text(
        local / "manuscript_ready_benchmark_section.md",
        methods + "\n" + results + "\n" + limitations,
    )
    representative_ids = {
        "q1_tem_specimen_preparation", "q2_tem_instrument_settings", "q3_tem_dataset_analysis",
        "q4_tem_result_value", "q5_all_measurement_contexts", "q6_all_result_records",
        "q8_all_measurement_parameters", "q11_software_provenance",
        "q46_normalized_result_quantities", "q49_analysis_provenance_across_cases",
    }
    representative = [row for row in matrix if row["query_id"] in representative_ids]
    columns = [
        ("query_id", "ID"), ("plain_language_question", "Question"), ("expected_rows", "Expected"),
        ("h2kg_recall_percent", "H₂KG recall"), ("chameo_recall_percent", "CHAMEO recall"),
    ]
    write_text(local / "representative_10_query_table.md", _markdown_table(representative, columns))
    write_text(local / "supplementary_50_query_table.md", _markdown_table(matrix, [
        ("query_id", "ID"), ("assessment_scope", "Scope"), ("plain_language_question", "Question"),
        ("expected_rows", "Expected"), ("h2kg_status", "H₂KG"), ("chameo_status", "CHAMEO"),
        ("h2kg_recall_percent", "H₂KG recall"), ("chameo_recall_percent", "CHAMEO recall"),
    ]))
    write_text(local / "README.md", "# Local manuscript material\n\nThese files describe the strict, extension-free benchmark. They are local-only and must not be committed.\n")


def _write_report_files_legacy(target: Path, report: dict[str, Any], matrix: list[dict[str, Any]]) -> None:
    dump_json(target / "native_benchmark_report.json", report)
    dump_json(target / "benchmark_contract.json", report["benchmark_contract"])
    dump_json(target / "native_query_matrix.json", {"schema_version": SCHEMA_VERSION, "queries": matrix})
    _write_csv(target / "native_query_matrix.csv", matrix)
    write_text(target / "native_query_matrix.md", _markdown_table(matrix, [
        ("query_id", "ID"), ("assessment_scope", "Scope"), ("plain_language_question", "Question"),
        ("expected_rows", "Expected"), ("h2kg_status", "H₂KG"), ("chameo_status", "CHAMEO"),
        ("h2kg_recall_percent", "H₂KG recall"), ("chameo_recall_percent", "CHAMEO recall"),
    ]))
    capabilities = report["capability_matrix"]
    dump_json(target / "native_capability_matrix.json", {"capabilities": capabilities})
    _write_csv(target / "native_capability_matrix.csv", capabilities)
    write_text(target / "native_capability_matrix.md", _markdown_table(capabilities, [
        ("capability", "Capability"), ("h2kg", "H₂KG"), ("chameo", "CHAMEO"),
        ("h2kg_evidence", "H₂KG evidence"), ("chameo_evidence", "CHAMEO evidence"),
    ]))
    specificity = report["method_specificity"]
    dump_json(target / "method_specificity_matrix.json", {"methods": specificity})
    _write_csv(target / "method_specificity_matrix.csv", specificity)
    family_rows = [
        {
            "query_family": family,
            "query_count": values["query_count"],
            "expected_rows": values["expected_rows"],
            **{
                f"{ontology}_{key}": value
                for ontology in ("h2kg", "chameo")
                for key, value in values[ontology].items()
            },
        }
        for family, values in report["query_benchmark"]["by_query_family"].items()
    ]
    _write_csv(target / "query_family_summary.csv", family_rows)
    dump_json(target / "query_family_summary.json", {"families": family_rows})
    diagnostic_rows = []
    for row in report["query_benchmark"]["semantic_contract_diagnostics"]:
        diagnostic_rows.append({
            "contract_id": row["contract_id"],
            "source_query_id": row["source_query_id"],
            "variables": ";".join(row["variables"]),
            "expected_rows": row["expected_rows"],
            **{
                f"{ontology}_{key}": value
                for ontology in ("h2kg", "chameo")
                for key, value in row[ontology].items()
            },
        })
    _write_csv(target / "semantic_contract_diagnostics.csv", diagnostic_rows)
    dump_json(target / "semantic_contract_diagnostics.json", {"contracts": diagnostic_rows})
    complexity = _query_complexity_rows(matrix)
    _write_csv(target / "query_complexity_report.csv", complexity)
    dump_json(target / "query_complexity_report.json", {
        "method": "RDFLib SPARQL algebra counts; descriptive only and not an ontology-quality score.",
        "queries": complexity,
    })
    constraints = report["mapping_policy_constraints"]
    _write_csv(target / "mapping_policy_constraints.csv", constraints)
    dump_json(target / "mapping_policy_constraints.json", {"requirements": constraints})
    write_text(target / "comparison_report.html", _html_report(report, matrix))
    q = report["query_benchmark"]
    readme = f"""# Strict H2KG--CHAMEO characterization benchmark

This package supersedes the earlier adapter-assisted 50/50 comparison. Scored graphs contain no local semantic bridge predicates and scored SPARQL never reads the neutral source-record layer. CHAMEO receives credit for its declared EMMO imports, but not for application predicates.

## Frozen inputs

- Workbook manifest: `{report['source_sha256']}`
- CHAMEO {CHAMEO_VERSION}: `{CHAMEO_COMMIT}`; Turtle SHA-256 `{CHAMEO_SHA256}`
- EMMO {EMMO_VERSION}: `{EMMO_COMMIT}`

## Evaluation boundary

- Explicit questions: {q['question_count']}
- Strict ontology-semantic queries: {q['scored_query_count']}
- Unscored source/quality controls: {q['unscored_control_count']}
- H₂KG complete query contracts: {q['h2kg']['queries_passed']}/{q['scored_query_count']}
- CHAMEO complete query contracts: {q['chameo']['queries_passed']}/{q['scored_query_count']}

`native_capability_matrix.*` documents the exact terms and missing relations. `semantic_contract_diagnostics.*` separates identity coverage from value linkage and exposes multi-result ambiguity. `native_query_matrix.*` contains the historical transfer questions. Scientific validity, runtime performance, and FAIRness were not measured.
"""
    write_text(target / "README.md", readme)


def _diagnostic_index(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        row["contract_id"]: row
        for row in report["query_benchmark"]["semantic_contract_diagnostics"]
    }


def _write_local_manuscript(
    local: Path,
    report: dict[str, Any],
    legacy_matrix: list[dict[str, Any]],
    balanced_matrix: list[dict[str, Any]],
) -> None:
    _safe_replace_dir(local)
    summary = report["balanced_benchmark"]
    conclusion = report["balanced_conclusion"]
    rows = {row["requirement_id"]: row for row in balanced_matrix}
    parameter_values = rows["b03_valued_measurement_setting"]
    result_links = rows["b08_individual_result_property_bearer"]
    result_values = rows["b09_parsed_result_value_and_unit"]
    workflow = rows["b11_workflow_task_grouping"]
    technique = rows["b12_technique_occurrence_separation"]
    specificity = report["balanced_conclusion"]["rules"]
    population = report["benchmark_population_audit"]
    compatibility = population["reported_results"]["property_unit_compatibility_counts"]
    h2kg_exact_percent = 100 * summary["h2kg"]["exact_requirements"] / summary["requirement_count"]
    chameo_exact_percent = 100 * summary["chameo"]["exact_requirements"] / summary["requirement_count"]

    methods = f"""## H₂KG–CHAMEO characterization benchmark

Two application knowledge graphs were constructed independently from the same sanitized workbook manifest (SHA-256 `{report['source_sha256']}`). The H₂KG graph used the published H₂KG vocabulary and its documented standards. The CHAMEO graph used CHAMEO {CHAMEO_VERSION} at commit `{CHAMEO_COMMIT}`, all {report['source_lock']['resolved_import_count']} modules in its transitive EMMO {EMMO_VERSION} import closure at commit `{EMMO_COMMIT}`, and shared QUDT and PROV-O terms where applicable. Neither ontology was modified, neither graph was translated from the other, and no local class or relation was admitted to either scored semantic graph. A relation absent from a permitted native encoding was left absent rather than repaired with an application bridge; this policy bounds the comparison but does not prove that every alternative encoding is impossible.

The manifest comprised {population['record_count']} source records from {population['method_family_count']} method families: TEM, SEM, AFM, FIB-SEM, IC-SEM, neutron tomography, and two synchrotron X-ray records. The two synchrotron sheets had identical acquisition/instrument fields and workflow-table values. Moreover, the sheet titled “Synchrotron X-ray radiography” reported “Synchrotron X-ray tomography” as its measurement method. They were retained as separate source records for fidelity but counted as one profile, giving {population['unique_profile_count']} unique profiles for profile-level reporting.

The frozen contract contained {summary['requirement_count']} requirements spanning the characterization lifecycle. Ten were evaluated by ontology-specific SPARQL retrieval, two combined SPARQL retrieval for one graph with native-pattern assessment for the other, and one assessed native vocabulary coverage. Expected rows were generated from the manifest before graph interrogation. Numeric lexical forms were normalized, rows were deduplicated over all selected variables, and the resulting sets were compared; labels, IRIs, and other selected values remained exact. Numeric parsing and recognized-unit mapping were evaluated separately from rule-based scientific property/unit compatibility. Thus, the reported percentages are requirement-satisfaction rates under this protocol, not general accuracy scores.

Five explicit decision criteria governed the scoped complementarity interpretation: (1) CHAMEO had to satisfy the common characterization-methodology requirements; (2) its dedicated workflow/task and technique-description patterns had to be demonstrated; (3) H₂KG had to support the valued-setting path while no corresponding path was identified in the CHAMEO encoding permitted by the protocol; (4) H₂KG had to preserve individual result–property–bearer identity where the tested CHAMEO process-level encoding was not exact; and (5) H₂KG had to provide greater native class coverage at the predefined profile granularity. The executable graph, mappings, ontology-specific queries, expected rows, observed rows, assessment modes, and population audit are archived at immutable commit `{BENCHMARK_ARCHIVE_COMMIT}`.
"""

    results = f"""## Comparative benchmark results

H₂KG satisfied {summary['h2kg']['exact_requirements']} of {summary['requirement_count']} requirements ({h2kg_exact_percent:.1f}%); CHAMEO satisfied {summary['chameo']['exact_requirements']} ({chameo_exact_percent:.1f}%), partially satisfied {summary['chameo']['partial_requirements']}, and did not support one requirement under the benchmark’s permitted native encoding. Both graphs returned the expected measurement contexts, setting identities, preparation and processing transformations, software associations, analysis lineage, parsed result values with recognized units, result-generation provenance, and workflow grouping. H₂KG grouped activities with the generic `Process / hasPart` pattern, whereas CHAMEO provided the dedicated `CharacterisationWorkflow / hasCharacterisationTask` pattern. CHAMEO also explicitly distinguished a technique description from its measurement occurrence for all {technique['expected_rows']} records; no corresponding separate-description pattern was identified in the pinned H₂KG core under the same mapping policy.

Of {population['measurement_settings']['distinct_identities']} distinct setting identities, {parameter_values['expected_rows']} had a parseable numeric value and recognized unit and entered the valued-setting assessment. The other {population['measurement_settings']['excluded_from_parsed_unit_assessment']} were retained but excluded because they were not applicable, unconfirmed, not specified, or lacked a complete parseable numeric/recognized-unit pair. H₂KG returned all {parameter_values['expected_rows']} through `hasParameter / ofProperty / hasQuantityValue`. CHAMEO returned all setting identities, but no declared ancestry-compatible link from `MeasurementParameter` to a separate valued scientific characteristic was identified under the permitted native encoding. No CHAMEO query was therefore executed for this requirement, and the outcome must not be interpreted as a general impossibility claim.

For results, H₂KG linked all {result_links['expected_rows']} individual result records directly to one property occurrence and bearer. The tested CHAMEO process-level encoding returned all expected associations but also produced {result_links['chameo_unexpected']} additional associations for one IC-SEM analysis. That analysis generated separate GDL-thickness and MEA-thickness result identities. Joining both process outputs to both process-level determined properties produced the two expected identity pairs plus the crossed pairs “GDL thickness result–MEA thickness” and “MEA thickness result–GDL thickness.” H₂KG’s result-level `ofProperty` links retained one property per result. The underlying IC-SEM measurements were not independently verified, so no numerical thickness values are used in this worked example. This finding concerns the tested process-level CHAMEO encoding, not every permissible CHAMEO representation. Of {result_links['expected_rows']} result records, {result_values['expected_rows']} contained a parseable numeric value and recognized unit; the remaining {population['reported_results']['excluded_from_parsed_unit_assessment']} were retained outside that assessment. A separate compatibility screen found {compatibility.get('no_detected_property_unit_conflict', 0)} rows with no detected property/unit conflict and {compatibility.get('semantic_conflict', 0)} conflicts. Both conflicts were the duplicated synchrotron source value labelled “electrolyte saturation” with unit mol/L; the value remains queryable as source evidence but is not treated as a scientifically compatible saturation quantity.

Native class coverage at the predefined profile granularity was {specificity['h2kg_specific_method_count']}/{population['record_count']} records and {population['dedicated_class_coverage']['unique_profile_level']['h2kg']}/{population['unique_profile_count']} unique profiles for H₂KG, compared with {specificity['chameo_specific_method_count']}/{population['record_count']} records and {population['dedicated_class_coverage']['unique_profile_level']['chameo']}/{population['unique_profile_count']} profiles for CHAMEO. This does not establish hydrogen-domain specificity or inability to model the remaining profiles compositionally. All five explicit decision criteria were met. Within this bounded scope, **{conclusion['statement']}**
"""

    limitations = f"""## Scope of inference

{conclusion['scope']} Expected answers and both ABoxes derive from the same curated manifest, so the benchmark tests representation and deterministic retrieval rather than scientific truth or experimental repeatability. It combines query-based retrieval, native-pattern assessment, and vocabulary coverage and must not be read as a single homogeneous performance test. Workflow execution and automatic FAIRness were also outside scope. Numeric parsing and unit recognition do not establish scientific property/unit compatibility or verify a measurement. The working distance in the TEM record remains explicitly unconfirmed and is excluded from parsed-value evaluation. The workbook-supplied TEM instrument model, publication metadata, 5 nm value, and IC-SEM measurements were not independently verified and must be described as illustrative source content rather than validated experimental evidence. Independent replication should freeze the contract before mapping and include additional, independently sourced characterization profiles.
"""

    write_text(local / "methods_subsection.md", methods)
    write_text(local / "results_subsection.md", results)
    write_text(local / "limitations.md", limitations)
    write_text(
        local / "manuscript_ready_benchmark_section.md",
        methods
        + "\n"
        + results
        + "\n"
        + limitations
        + "\n## Suggested figure caption\n\n"
        + "Controlled comparison of independently constructed H₂KG- and CHAMEO-backed characterization graphs. "
        + "The benchmark separates query-based retrieval, native-pattern assessment, and native vocabulary coverage "
        + "across eight source records representing seven unique profiles. The IC-SEM example shows the two expected "
        + "thickness-result associations and the two additional crossed associations produced by the tested CHAMEO "
        + "process-level encoding; H₂KG retains one result-level `ofProperty` association for each DataPoint. "
        + "The comparison applies only to the frozen source manifest, mapping rules, and tested encodings.\n",
    )
    manuscript_table: list[dict[str, Any]] = []
    for source_row in balanced_matrix:
        table_row = dict(source_row)
        for ontology in ("h2kg", "chameo"):
            mode = source_row[f"{ontology}_assessment_mode"]
            if source_row[f"{ontology}_query_executed"]:
                evidence_summary = (
                    f"SPARQL: {source_row[f'{ontology}_matched']}/{source_row['expected_rows']} expected rows; "
                    f"{source_row[f'{ontology}_unexpected']} additional"
                )
            elif mode == "native_vocabulary_coverage":
                evidence_summary = (
                    f"Class-inventory coverage: {source_row[f'{ontology}_matched']}/"
                    f"{source_row['expected_rows']} records"
                )
            else:
                evidence_summary = "Native-pattern assessment; no SPARQL query executed"
            table_row[f"{ontology}_evidence_summary"] = evidence_summary
        manuscript_table.append(table_row)
    write_text(local / "fair_13_requirement_table.md", _markdown_table(manuscript_table, [
        ("requirement_id", "ID"),
        ("selection_stratum", "Selection stratum"),
        ("assessment_type", "Assessment type"),
        ("plain_language_question", "Plain-language question"),
        ("expected_rows", "Expected"),
        ("h2kg_status", "H2KG"),
        ("h2kg_evidence_summary", "H2KG evidence"),
        ("chameo_status", "CHAMEO"),
        ("chameo_evidence_summary", "CHAMEO evidence"),
    ]))
    write_text(local / "historical_50_question_transfer_test.md", _markdown_table(legacy_matrix, [
        ("query_id", "ID"),
        ("assessment_scope", "Scope"),
        ("plain_language_question", "Plain-language question"),
        ("expected_rows", "Expected"),
        ("h2kg_status", "H2KG"),
        ("chameo_status", "CHAMEO"),
        ("chameo_missing", "CHAMEO missing"),
        ("chameo_unexpected", "CHAMEO additional"),
    ]))
    write_text(local / "comparison_figure_specification.md", """# Figure specification

Use three panels. Panel A shows one sanitized manifest branching into independently constructed H2KG and CHAMEO ABoxes, with three evaluation modes above them: SPARQL retrieval, native-pattern assessment, and native vocabulary coverage. State `8 source records / 7 method families / 7 unique profiles` and mark the two identical synchrotron records as one profile. Panel B contrasts supported native patterns: CHAMEO's dedicated workflow/task and technique-description structures, and H2KG's parameter-record/property/value and result/property/bearer structures. Panel C shows the IC-SEM worked example. Draw one analysis with separate GDL-thickness-result and MEA-thickness-result identities. For the tested CHAMEO process-level encoding, show the two expected and two additional crossed identity associations in distinct styles. For H2KG, show one `ofProperty` edge per DataPoint. Do not annotate numerical thickness values; add `workbook measurements not independently verified`. Caption every comparison as applying to the tested encoding and frozen mapping rules, not all possible ontology uses.
""")
    write_text(local / "manuscript_integration_edits.md", f"""# Manuscript integration edits

## Abstract replacement sentences

Two independently constructed H₂KG- and CHAMEO-backed graphs were assessed against 13 frozen characterization requirements using SPARQL retrieval, native-pattern assessment, and native vocabulary coverage. H₂KG satisfied 12/13 and CHAMEO 10/13 requirements under this protocol, supporting a scoped complementarity finding: CHAMEO provided explicit methodology-description structures, whereas H₂KG directly represented valued settings and result-level property ownership for the selected profiles.

## Conclusion replacement paragraph

The comparison does not rank either ontology globally. Across eight source records representing seven unique characterization profiles, CHAMEO supplied dedicated workflow/task and technique-description patterns, while H₂KG provided greater native class coverage at the predefined profile granularity and direct paths from parameter records to valued characteristics and from individual results to properties and bearers. The IC-SEM example demonstrates the practical consequence without relying on unverified numerical measurements: the tested process-level CHAMEO encoding returned two crossed thickness-result identity associations, whereas H₂KG retained the GDL and MEA thickness result identities separately. These findings are limited to the frozen mapping rules, source manifest, and requirements evaluated here.

## TEM corrections

- Write `working distance: unconfirmed`; do not present a numeric working distance.
- Describe `5 nm` as a workbook-supplied illustrative value pending independent source verification.
- Do not claim that the listed TEM instrument model or publication metadata has been independently verified. State this limitation in Table 2 and the text.
- Replace the malformed QUDT sentence with: `Parseable source numbers with recognized units were represented using QUDT; scientific property/unit compatibility was screened separately, and unresolved, qualified, or conflicting values were retained with an explicit status.`

## Editorial corrections

- Change `nonoelectrical` to `nanoelectrical` in AFM Table 3.
- Replace `including H2KG draws on` with `H₂KG draws on` or rewrite the complete sentence.
- Remove doubled punctuation and resolve every `Figure X` and `Table X` placeholder after figure synchronization.

## Reproducibility links

- Interactive benchmark: https://vimilabs.github.io/AIMWORKS/pages/characterization-benchmark.html
- Immutable package: https://github.com/ViMiLabs/AIMWORKS/tree/{BENCHMARK_ARCHIVE_COMMIT}/ontology_release/output/characterization_kg_comparison
- Contract: `benchmark_contract.json`
- Manifest: `characterization_source_manifest.json`
- H2KG mappings: `h2kg_source_semantic_mapping_registry.csv`
- CHAMEO mappings: `chameo_native_mapping_registry.csv`
- Queries and results: `balanced_queries/` and `balanced_results/`
""")
    write_text(local / "review_comment_resolution.md", """# Benchmark review-comment resolution

| Reviewer concern | Resolution |
|---|---|
| `Extension required` overstates the evidence | Replaced with `not supported under the benchmark's permitted native encoding`; the text explicitly rejects a general impossibility interpretation. |
| Mixed evaluation methods were not disclosed | Every requirement now records `query_based_retrieval`, `query_retrieval_and_native_pattern_assessment`, or `native_vocabulary_coverage`. |
| `Row multiset` contradicted implementation | Corrected to deduplicated result-set comparison after numeric lexical normalization; duplicate handling is documented. |
| Percentages could be read as accuracy | Recast as requirement-satisfaction rates under the frozen protocol. |
| Specificity claim exceeded the evidence | Replaced with native vocabulary coverage for the selected profiles; compositional representation is distinguished from dedicated class availability. |
| Eight cases were insufficiently described | Reported as eight source records, seven method families, and seven unique profiles; the radiography/tomography conflict and duplicate synchrotron profile are explicit. |
| Reproducibility package was weakly connected | Added immutable commit and direct artifact links plus a population/eligibility audit. |
| 107/131 settings and 13/24 results were unexplained | Added eligibility criteria and exclusion counts; excluded values remain represented in the source layer. |
| TEM scientific qualification was incomplete | Working distance is explicitly unconfirmed; instrument/publication metadata and 5 nm are identified as workbook-supplied illustrative content pending independent verification. |
| Quantity normalization implied scientific compatibility | Reframed as numeric parsing and recognized-unit mapping; added a separate property/unit compatibility audit that flags the two duplicated `electrolyte saturation = 47 mol/L` records as semantic conflicts. |
| IC-SEM ambiguity was overgeneralized | Reworded as two additional identity associations produced by the tested CHAMEO process-level encoding; removed the unverified thickness numbers from the text and figure specification. |
| Abstract/conclusion and copy-editing remained stale | Added exact replacement text and a checklist for typo, QUDT sentence, punctuation, placeholders, and figure synchronization. |
""")
    write_text(local / "README.md", """# Local manuscript material

These files describe the bounded H₂KG–CHAMEO characterization benchmark and are intentionally excluded from Git.

- `manuscript_ready_benchmark_section.md`: complete Methods, Results, and limitations text.
- `fair_13_requirement_table.md`: full requirement table with assessment modes.
- `comparison_figure_specification.md`: revised figure design, including the IC-SEM worked example.
- `manuscript_integration_edits.md`: abstract, conclusion, TEM, and copy-edit replacements.
- `review_comment_resolution.md`: point-by-point response to the latest review.
""")


def _render_comparison_html(report: dict[str, Any]) -> str:
    summary = report["balanced_benchmark"]
    conclusion = report["balanced_conclusion"]
    diagnostics = "".join(
        "<tr>"
        f"<td>{html.escape(row['requirement_id'])}</td>"
        f"<td>{html.escape(row['plain_language_question'])}</td>"
        f"<td>{row['expected_rows']}</td>"
        f"<td>{html.escape(row['h2kg_status'])}</td>"
        f"<td>{html.escape(row['chameo_status'])}</td>"
        "</tr>"
        for row in report["balanced_requirement_matrix"]
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>H2KG-CHAMEO characterization benchmark</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;max-width:1180px;margin:0 auto;padding:38px;color:#19313a;background:#f4f7f6}}h1,h2{{color:#123f46}}.card{{background:#fff;border:1px solid #cfdbd8;border-radius:14px;padding:22px;margin:18px 0;box-shadow:0 8px 24px #17343a12}}.metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}}.metric{{background:#e7f2ef;border-radius:10px;padding:16px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;border-bottom:1px solid #d8e1df;text-align:left;vertical-align:top}}th{{background:#174b53;color:#fff}}a{{color:#086a75}}</style></head>
<body><h1>H2KG-CHAMEO characterization benchmark</h1>
<p>Both ABoxes were constructed independently from one sanitized workbook manifest. Neither ontology was modified, neither graph was translated from the other, and no local bridge relation was admitted to a scored graph. CHAMEO was evaluated with its complete pinned EMMO transitive import closure.</p>
<div class="metrics"><div class="metric"><strong>Cases</strong><br>8</div><div class="metric"><strong>Frozen requirements</strong><br>{summary['requirement_count']}</div><div class="metric"><strong>H2KG exact requirements</strong><br>{summary['h2kg']['exact_requirements']}/{summary['requirement_count']}</div><div class="metric"><strong>CHAMEO exact requirements</strong><br>{summary['chameo']['exact_requirements']}/{summary['requirement_count']}</div></div>
<div class="card"><h2>Controlled comparison protocol</h2><p>All thirteen requirements were derived from the same characterization-record lifecycle and named by scientific function rather than ontology origin. Both ABoxes were generated independently from the same frozen manifest. Each requirement was scored once over the full case population; native, generic, declared-import, and shared-standard support are distinguished explicitly. The contract and five decision rules were hashed before query execution, and the conclusion was emitted only because all five rules passed.</p></div>
<div class="card"><h2>Requirement results</h2><table><thead><tr><th>ID</th><th>Plain-language requirement</th><th>Expected</th><th>H2KG</th><th>CHAMEO</th></tr></thead><tbody>{diagnostics}</tbody></table></div>
<div class="card"><h2>Conclusion</h2><p><strong>{html.escape(conclusion['statement'])}</strong></p><p>{html.escape(conclusion['scope'])}</p></div>
<div class="card"><h2>Downloads</h2><p><a href="benchmark_contract.json">Frozen benchmark contract</a> | <a href="balanced_requirement_matrix.csv">Requirement result matrix</a> | <a href="balanced_conclusion_rules.json">Conclusion rules</a> | <a href="ontology_evidence_audit.json">Ontology evidence audit</a> | <a href="native_capability_matrix.csv">Capability matrix</a> | <a href="native_benchmark_report.json">Complete report</a></p></div>
</body></html>"""


def _write_report_files(
    target: Path,
    report: dict[str, Any],
    matrix: list[dict[str, Any]],
    balanced_matrix: list[dict[str, Any]],
) -> None:
    dump_json(target / "native_benchmark_report.json", report)
    dump_json(target / "benchmark_contract.json", report["benchmark_contract"])
    dump_json(
        target / "legacy_h2kg_application_contract.json",
        report["legacy_h2kg_application_contract"],
    )
    dump_json(target / "balanced_requirement_matrix.json", {
        "schema_version": report["benchmark_contract"]["schema_version"],
        "requirements": balanced_matrix,
    })
    _write_csv(target / "balanced_requirement_matrix.csv", balanced_matrix)
    write_text(target / "balanced_requirement_matrix.md", _markdown_table(balanced_matrix, [
        ("requirement_id", "ID"),
        ("selection_stratum", "Selection stratum"),
        ("assessment_type", "Assessment type"),
        ("plain_language_question", "Requirement"),
        ("expected_rows", "Expected"),
        ("h2kg_status", "H2KG"),
        ("chameo_status", "CHAMEO"),
        ("h2kg_representation_tier", "H2KG basis"),
        ("chameo_representation_tier", "CHAMEO basis"),
    ]))
    population = report["benchmark_population_audit"]
    dump_json(target / "benchmark_population_audit.json", population)
    _write_csv(target / "benchmark_case_inventory.csv", population["cases"])
    _write_csv(target / "benchmark_unique_profiles.csv", population["profiles"])
    _write_csv(
        target / "measurement_setting_parsing_exclusions.csv",
        population["measurement_settings"]["exclusions"],
    )
    _write_csv(
        target / "result_parsing_exclusions.csv",
        population["reported_results"]["exclusions"],
    )
    _write_csv(
        target / "result_property_unit_compatibility.csv",
        population["reported_results"]["property_unit_compatibility"],
    )
    write_text(
        target / "benchmark_population_audit.md",
        "# Benchmark population audit\n\n"
        f"- Source records: {population['record_count']}\n"
        f"- Method families: {population['method_family_count']}\n"
        f"- Unique characterization profiles: {population['unique_profile_count']}\n"
        f"- Distinct measurement-setting identities: {population['measurement_settings']['distinct_identities']}\n"
        f"- Settings with a parseable number and recognized unit: {population['measurement_settings']['parsed_recognized_unit_rows']}\n"
        f"- Reported result records: {population['reported_results']['distinct_records']}\n"
        f"- Results with a parseable number and recognized unit: {population['reported_results']['parsed_recognized_unit_rows']}\n"
        f"- Result property/unit conflicts: {population['reported_results']['property_unit_compatibility_counts'].get('semantic_conflict', 0)}\n\n"
        "Numeric parsing and unit recognition do not establish scientific compatibility. "
        "The separate compatibility audit flags both duplicated `electrolyte saturation = 47 mol/L` records because saturation is ordinarily dimensionless whereas mol/L denotes concentration. "
        "The raw values remain queryable and are not treated as validated saturation quantities.\n\n"
        "The two synchrotron sheets contain identical acquisition/instrument fields and workflow-table values. "
        "The sheet titled radiography reports `Synchrotron X-ray tomography` as its measurement method; both records are therefore one unique tomography profile for profile-level reporting.\n",
    )
    dump_json(target / "balanced_conclusion_rules.json", report["balanced_conclusion"])
    evidence = report["ontology_evidence_audit"]
    dump_json(target / "ontology_evidence_audit.json", evidence)
    evidence_rows = [
        {
            "claim": "Complete CHAMEO/EMMO import closure loaded",
            "observed": f"{evidence['resolved_import_count']} modules ({evidence['direct_import_count']} direct; {evidence['transitive_import_count']} transitive)",
            "supports": str(evidence["complete_import_closure"]),
        },
        {
            "claim": "MeasurementParameter is an EMMO mathematical Parameter",
            "observed": str(evidence["measurement_parameter"]["is_emmo_mathematical_parameter"]),
            "supports": "Parameter identity is native to CHAMEO/EMMO.",
        },
        {
            "claim": "MeasurementParameter is an EMMO Quantity",
            "observed": str(evidence["measurement_parameter"]["is_emmo_quantity"]),
            "supports": "No quantity-value path through the declared class ancestry was identified under the benchmark's native-pattern audit.",
        },
        {
            "claim": "EMMO hasProperty domain applies to MeasurementParameter ancestry",
            "observed": str(evidence["measurement_parameter"]["emmo_has_property_domain_applicable"]),
            "supports": "The generic hasProperty relation is not counted as a native parameter-to-characteristic path.",
        },
        {
            "claim": "Declared ancestry-compatible parameter-to-Property relations",
            "observed": str(len(evidence["measurement_parameter"]["declared_applicable_property_relations"])),
            "supports": evidence["measurement_parameter"]["finding"],
        },
        {
            "claim": "CHAMEO DataAnalysis entails EMMO Determination",
            "observed": str(evidence["result_semantics"]["data_analysis_is_declared_emmo_determination"]),
            "supports": "The determination pattern is reported as an explicit declared-import application pattern, not a CHAMEO entailment.",
        },
        {
            "claim": "CHAMEO specialized workflow/task pattern present",
            "observed": str(evidence["workflow_and_technique"]["chameo_workflow_class_present"] and evidence["workflow_and_technique"]["chameo_task_relation_present"]),
            "supports": "CHAMEO receives direct-native credit for workflow grouping.",
        },
        {
            "claim": "CHAMEO technique-description pattern present",
            "observed": str(evidence["workflow_and_technique"]["chameo_technique_class_present"] and evidence["workflow_and_technique"]["emmo_description_relation_present"]),
            "supports": "CHAMEO receives exact credit for separating technique descriptions from occurrences.",
        },
    ]
    _write_csv(target / "ontology_evidence_audit.csv", evidence_rows)
    write_text(target / "ontology_evidence_audit.md", _markdown_table(evidence_rows, [
        ("claim", "Audited claim"),
        ("observed", "Observed evidence"),
        ("supports", "Benchmark interpretation"),
    ]))
    dump_json(target / "native_query_matrix.json", {"schema_version": SCHEMA_VERSION, "queries": matrix})
    _write_csv(target / "native_query_matrix.csv", matrix)
    write_text(target / "native_query_matrix.md", _markdown_table(matrix, [
        ("query_id", "ID"),
        ("assessment_scope", "Scope"),
        ("plain_language_question", "Question"),
        ("expected_rows", "Expected"),
        ("h2kg_status", "H2KG"),
        ("chameo_status", "CHAMEO"),
        ("chameo_missing", "CHAMEO missing"),
        ("chameo_unexpected", "CHAMEO additional"),
    ]))

    capabilities = report["capability_matrix"]
    dump_json(target / "native_capability_matrix.json", {"capabilities": capabilities})
    _write_csv(target / "native_capability_matrix.csv", capabilities)
    write_text(target / "native_capability_matrix.md", _markdown_table(capabilities, [
        ("capability", "Capability"),
        ("h2kg", "H2KG"),
        ("chameo", "CHAMEO"),
        ("h2kg_evidence", "H2KG evidence"),
        ("chameo_evidence", "CHAMEO evidence"),
    ]))
    coverage_rows = [
        {"ontology": ontology, "outcome": outcome, "capability_count": count}
        for ontology, outcomes in report["capability_coverage"].items()
        for outcome, count in outcomes.items()
    ]
    _write_csv(target / "capability_coverage_summary.csv", coverage_rows)
    dump_json(target / "capability_coverage_summary.json", {"rows": coverage_rows})

    specificity = report["method_specificity"]
    dump_json(target / "method_specificity_matrix.json", {"methods": specificity})
    _write_csv(target / "method_specificity_matrix.csv", specificity)

    family_rows = [
        {
            "query_family": family,
            "query_count": values["query_count"],
            "expected_rows": values["expected_rows"],
            **{
                f"{ontology}_{key}": value
                for ontology in ("h2kg", "chameo")
                for key, value in values[ontology].items()
            },
        }
        for family, values in report["query_benchmark"]["by_query_family"].items()
    ]
    _write_csv(target / "query_family_summary.csv", family_rows)
    dump_json(target / "query_family_summary.json", {"families": family_rows})

    diagnostic_rows = []
    for row in report["query_benchmark"]["semantic_contract_diagnostics"]:
        diagnostic_rows.append({
            "contract_id": row["contract_id"],
            "source_query_id": row["source_query_id"],
            "variables": ";".join(row["variables"]),
            "expected_rows": row["expected_rows"],
            **{
                f"{ontology}_{key}": value
                for ontology in ("h2kg", "chameo")
                for key, value in row[ontology].items()
            },
        })
    _write_csv(target / "semantic_contract_diagnostics.csv", diagnostic_rows)
    dump_json(target / "semantic_contract_diagnostics.json", {"contracts": diagnostic_rows})

    complexity = _query_complexity_rows(matrix)
    _write_csv(target / "query_complexity_report.csv", complexity)
    dump_json(target / "query_complexity_report.json", {
        "method": "RDFLib SPARQL algebra counts; descriptive only and not an ontology-quality score.",
        "queries": complexity,
    })
    constraints = report["mapping_policy_constraints"]
    _write_csv(target / "mapping_policy_constraints.csv", constraints)
    dump_json(target / "mapping_policy_constraints.json", {"requirements": constraints})
    write_text(target / "comparison_report.html", _render_comparison_html(report))

    summary = report["balanced_benchmark"]
    conclusion = report["balanced_conclusion"]
    readme = f"""# H2KG-CHAMEO characterization benchmark

The two scored ABoxes are constructed independently from the same sanitized manifest. They contain no local semantic bridge predicates, and scored SPARQL does not read the neutral source-record layer. CHAMEO receives explicit credit for every applicable relation in its complete pinned EMMO import closure but not for locally invented predicates.

## Frozen inputs

- Workbook manifest: `{report['source_sha256']}`
- CHAMEO {CHAMEO_VERSION}: `{CHAMEO_COMMIT}`; Turtle SHA-256 `{CHAMEO_SHA256}`
- EMMO {EMMO_VERSION}: `{EMMO_COMMIT}`
- EMMO import closure: {report['source_lock']['resolved_import_count']} modules ({report['source_lock']['direct_import_count']} direct and {report['source_lock']['transitive_import_count']} transitive); lock fingerprint `{report['source_lock']['lock_fingerprint']}`

## Frozen application contract

- Ontology-neutral lifecycle requirements: {summary['requirement_count']}
- Assessment modes: {', '.join(f'{key} ({value})' for key, value in summary['assessment_type_counts'].items())}
- Population: {report['benchmark_population_audit']['record_count']} source records, {report['benchmark_population_audit']['method_family_count']} method families, {report['benchmark_population_audit']['unique_profile_count']} unique profiles
- Selection strata: {', '.join(f'{key} ({value})' for key, value in summary['selection_strata'].items())}
- H2KG exact requirements: {summary['h2kg']['exact_requirements']}/{summary['requirement_count']}
- CHAMEO exact requirements: {summary['chameo']['exact_requirements']}/{summary['requirement_count']}
- CHAMEO partial requirements: {summary['chameo']['partial_requirements']}/{summary['requirement_count']}
- Contract fingerprint: `{report['benchmark_contract']['contract_sha256']}`

## Computed conclusion

{conclusion['statement']}

{conclusion['scope']}

`balanced_requirement_matrix.*` contains the primary evidence, `benchmark_population_audit.*` documents record/profile accounting, parsing eligibility, and property/unit compatibility, `ontology_evidence_audit.*` records the pinned TBox evidence, and `balanced_conclusion_rules.json` records every explicit decision rule behind the conclusion. Query outcomes use deduplicated result-set comparison after numeric lexical normalization. The conclusion is emitted only when all five rules pass. The earlier 50-question H2KG application set remains in `native_query_matrix.*` only as a labelled historical asymmetric diagnostic and is excluded from the conclusion.
"""
    write_text(target / "README.md", readme)


def build_native_characterization_benchmark(
    manifest_path: str | Path,
    h2kg_output_dir: str | Path,
    chameo_source_dir: str | Path,
    emmo_source_dir: str | Path,
    output_dir: str | Path,
    local_manuscript_dir: str | Path,
) -> dict[str, Any]:
    """Build extension-free semantic graphs and benchmark their capabilities."""

    manifest_path = Path(manifest_path)
    h2kg_output = Path(h2kg_output_dir)
    target = Path(output_dir)
    local = Path(local_manuscript_dir)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("source", {}).get("sha256") != EXPECTED_WORKBOOK_SHA256:
        raise ValueError("The strict benchmark requires the approved workbook-manifest fingerprint.")
    if len(manifest.get("cases", [])) != 8 or int(manifest.get("eligible_field_count", 0)) != 1635:
        raise ValueError("The strict benchmark requires eight cases and 1,635 eligible fields.")

    _safe_replace_dir(target)
    source_lock, source_tbox = _source_lock(Path(chameo_source_dir), Path(emmo_source_dir))
    chameo_source, _, chameo_mapping_rows = build_chameo_dataset_from_manifest(
        manifest,
        include_application_bridges=False,
    )
    if len(chameo_mapping_rows) != int(manifest["eligible_field_count"]):
        raise ValueError("Strict CHAMEO mapping ledger does not cover every eligible source field.")
    for row in chameo_mapping_rows:
        if row["mapping_outcome"] == "measurement_parameter_identity_only":
            row["strict_assertion_status"] = "identity_asserted_value_link_not_asserted"
        elif row["representation_tier"] == "source_only":
            row["strict_assertion_status"] = "source_evidence_only_excluded_from_scoring"
        else:
            row["strict_assertion_status"] = "asserted_without_local_bridge"
    h2kg_source = Dataset(default_union=False).parse(
        h2kg_output / "characterization_knowledge_graph.trig", format="trig"
    )
    strict_chameo = _strict_projection(
        chameo_source,
        graph_prefix=CHAMEO_GRAPH_PREFIX,
        forbidden_vocabulary=str(APP),
        source_instance_prefix=f"{CMP}source/",
    )
    strict_h2kg = _strict_projection(
        h2kg_source,
        graph_prefix=H2KG_SEMANTIC_PREFIX,
        forbidden_vocabulary=str(KG),
        source_instance_prefix="https://w3id.org/h2kg/examples/characterization/source/",
    )
    _add_h2kg_workflow_grouping(strict_h2kg, manifest)

    shutil.copyfile(manifest_path, target / "characterization_source_manifest.json")
    dump_json(target / "chameo_source_lock.json", source_lock)
    _write_csv(target / "chameo_source_lock.csv", source_lock["files"])
    dump_json(target / "chameo_native_mapping_registry.json", {
        "schema_version": SCHEMA_VERSION,
        "source_sha256": manifest["source"]["sha256"],
        "mappings": chameo_mapping_rows,
    })
    _write_csv(target / "chameo_native_mapping_registry.csv", chameo_mapping_rows)
    h2kg_mapping_rows: list[dict[str, Any]] = []
    for suffix in ("json", "csv"):
        source_registry = h2kg_output / f"source_semantic_mapping_registry.{suffix}"
        if source_registry.exists():
            shutil.copyfile(source_registry, target / f"h2kg_source_semantic_mapping_registry.{suffix}")
            if suffix == "json":
                h2kg_mapping_rows = json.loads(source_registry.read_text(encoding="utf-8"))["mappings"]
    if len({row["record_id"] for row in h2kg_mapping_rows}) != int(manifest["eligible_field_count"]):
        raise ValueError("H2KG mapping ledger does not cover every eligible source field.")
    graph_stats = {
        "h2kg": _serialize_dataset(strict_h2kg, target / "strict_h2kg_semantic_graph"),
        "chameo": _serialize_dataset(strict_chameo, target / "strict_chameo_semantic_graph"),
    }
    if not graph_stats["h2kg"]["turtle_jsonld_isomorphic"] or not graph_stats["chameo"]["turtle_jsonld_isomorphic"]:
        raise ValueError("Strict Turtle and JSON-LD serializations are not RDF-isomorphic.")
    _write_case_graphs(strict_h2kg, target / "cases" / "h2kg", H2KG_SEMANTIC_PREFIX)
    _write_case_graphs(strict_chameo, target / "cases" / "chameo", CHAMEO_GRAPH_PREFIX)

    forbidden = {
        "h2kg": (str(KG), str(APP), str(CHAMEO)),
        "chameo": (str(APP), str(KG), str(H2KG)),
    }
    for name, dataset in (("h2kg", strict_h2kg), ("chameo", strict_chameo)):
        leaked = sorted({
            str(value)
            for graph in dataset.graphs()
            for triple in graph
            for value in triple
            if isinstance(value, URIRef)
            and any(str(value).startswith(namespace) for namespace in forbidden[name])
        })
        if leaked:
            raise ValueError(f"Foreign or local semantic vocabulary leaked into strict {name} graph: {leaked[:3]}")

    # Freeze and hash the balanced contract before executing either ontology's
    # queries.  The older H2KG-originated question set is retained only as a
    # separately labelled transfer-test diagnostic.
    balanced_contract = _balanced_contract(manifest)
    balanced_matrix, balanced_summary, balanced_conclusion = _run_balanced_benchmark(
        strict_h2kg,
        strict_chameo,
        manifest,
        target,
    )
    ontology_evidence = _ontology_evidence_audit(
        source_tbox,
        strict_h2kg,
        strict_chameo,
        source_lock,
    )
    matrix, query_summary = _run_benchmark_queries(strict_h2kg, strict_chameo, manifest, target)
    chameo_validation = _validate_strict_chameo(_flatten(strict_chameo), target)
    if not chameo_validation["conforms"] or any(item["conforms"] for item in chameo_validation["negative_tests"]):
        raise ValueError("Strict CHAMEO structural validation failed its declared contract.")

    legacy_contract = _benchmark_contract(manifest)
    capabilities = _capability_matrix()
    population_audit = _benchmark_population_audit(manifest)
    capability_coverage = {
        ontology: dict(sorted(Counter(row[ontology] for row in capabilities).items()))
        for ontology in ("h2kg", "chameo")
    }
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_iso(),
        "source_sha256": manifest["source"]["sha256"],
        "case_count": 8,
        "eligible_field_count": 1635,
        "benchmark_population_audit": population_audit,
        "benchmark_contract": balanced_contract,
        "balanced_benchmark": balanced_summary,
        "balanced_requirement_matrix": balanced_matrix,
        "balanced_conclusion": balanced_conclusion,
        "legacy_h2kg_application_contract": legacy_contract,
        "legacy_transfer_test": query_summary,
        "benchmark_policy": {
            "comparison_type": "balanced_ontology_neutral_characterization_record_benchmark",
            "abox_construction": "independent_direct_mapping_from_the_same_sanitized_manifest",
            "cross_graph_translation": False,
            "ontology_tbox_modification": False,
            "local_semantic_extensions_allowed": False,
            "source_layer_allowed_in_scored_queries": False,
            "ground_truth_source": "sanitized workbook manifest",
            "ontology_specific_sparql": True,
            "same_variables_and_expected_rows": True,
            "declared_imports_allowed_and_reported_separately": True,
            "shared_standards_not_credited_as_ontology_specific": True,
            "requirement_selection": "Thirteen requirements derived from the source characterization lifecycle and named by scientific function; every requirement is scored once over all eight source records, representing seven unique profiles, and none is selected by ontology origin.",
            "comparison_method": "Deduplicated result-set equality after numeric lexical normalization for query-based requirements; explicit native-pattern assessment for unsupported-query cases; native vocabulary coverage for the selected profiles.",
            "quantity_interpretation": "Numeric parsing and recognized-unit mapping are distinct from rule-based scientific property/unit compatibility screening.",
            "conclusion_rule": "The complementarity statement is emitted only when every explicit machine-checkable decision rule passes.",
            "legacy_question_set_status": "Retained as a historical asymmetric transfer-test diagnostic and excluded from the primary conclusion.",
        },
        "source_lock": {key: value for key, value in source_lock.items() if key != "files"},
        "graph_statistics": graph_stats,
        "mapping_coverage": {
            "eligible_source_fields": int(manifest["eligible_field_count"]),
            "h2kg_mapping_assertions": len(h2kg_mapping_rows),
            "h2kg_unique_source_fields": len({row["record_id"] for row in h2kg_mapping_rows}),
            "h2kg_additional_assertions_for_multimapped_fields": (
                len(h2kg_mapping_rows) - len({row["record_id"] for row in h2kg_mapping_rows})
            ),
            "chameo_mapping_rows": len(chameo_mapping_rows),
            "chameo_strict_assertion_status_counts": dict(sorted(Counter(
                row["strict_assertion_status"] for row in chameo_mapping_rows
            ).items())),
            "chameo_primary_tier_counts": dict(sorted(Counter(
                row["representation_tier"] for row in chameo_mapping_rows
            ).items())),
        },
        "query_benchmark": query_summary,
        "capability_matrix": capabilities,
        "capability_coverage": capability_coverage,
        "ontology_evidence_audit": ontology_evidence,
        "method_specificity": _method_specificity_matrix(),
        "mapping_policy_constraints": _mapping_policy_constraints(),
        "shacl": {
            "chameo": chameo_validation,
            "comparison_limit": "Both graphs are tested against the same source-derived requirements. The complete CHAMEO/EMMO transitive import closure is available to CHAMEO. Under the benchmark's permitted native encoding, no ancestry-compatible parameter-record-to-valued-characteristic path was identified; this is not a proof that every alternative CHAMEO/EMMO encoding is impossible. The analysis-to-property constraint uses an explicit imported EMMO application pattern and is not described as a CHAMEO entailment.",
        },
        "excluded_preliminary_method": {
            "publication_status": "not_a_benchmark",
            "reason": "An earlier adapter-assisted run used a neutral source layer and local bridge relations. Its scores are excluded rather than reported as ontology capability.",
        },
        "interpretation": {
            "complementarity": balanced_conclusion["statement"],
            "conclusion_supported": balanced_conclusion["supported"],
            "limits": balanced_conclusion["scope"],
        },
    }
    _write_comparison_workbench(
        target,
        report,
        manifest,
        strict_h2kg,
        strict_chameo,
    )
    _write_report_files(target, report, matrix, balanced_matrix)
    _write_local_manuscript(local, report, matrix, balanced_matrix)
    return report
