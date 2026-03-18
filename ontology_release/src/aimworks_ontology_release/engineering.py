from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS

from .extract import extract_local_terms
from .inspect import find_ontology_node
from .io import save_graph
from .utils import (
    as_uri_text,
    is_local_iri,
    local_name,
    namespace_of,
    write_json,
    write_text,
)

_MODULE_SPECS: list[dict[str, str]] = [
    {
        "id": "top",
        "label": "Top / metadata",
        "filename": "top.ttl",
        "purpose": "Ontology header, release metadata, import declarations, and publication-level annotations.",
    },
    {
        "id": "core",
        "label": "Core local terms",
        "filename": "core.ttl",
        "purpose": "Local H2KG backbone terms that anchor the application ontology and do not fit a narrower domain module.",
    },
    {
        "id": "materials",
        "label": "Materials",
        "filename": "materials.ttl",
        "purpose": "Local material, chemical, catalyst, ionomer, and matter-oriented terms retained in the H2KG namespace.",
    },
    {
        "id": "components_devices",
        "label": "Components and devices",
        "filename": "components_devices.ttl",
        "purpose": "Local components, devices, assemblies, and hardware-oriented terms for PEMFC and hydrogen electrochemical systems.",
    },
    {
        "id": "processes_manufacturing",
        "label": "Processes and manufacturing",
        "filename": "processes_manufacturing.ttl",
        "purpose": "Local process, fabrication, coating, printing, and manufacturing terms.",
    },
    {
        "id": "measurements_data",
        "label": "Measurements, properties, and data",
        "filename": "measurements_data.ttl",
        "purpose": "Local measurement, property, parameter, data, metadata, unit, and instrument terms.",
    },
    {
        "id": "mappings",
        "label": "Mappings and alignments",
        "filename": "mappings.ttl",
        "purpose": "Conservative reviewed alignment assertions connecting H2KG local terms to external ontologies.",
    },
    {
        "id": "examples",
        "label": "Examples and individuals",
        "filename": "examples.ttl",
        "purpose": "Separated individuals, example resources, and data-like content kept outside the asserted local TBox release.",
    },
]

_CORE_KEYWORDS = {
    "agent",
    "data",
    "datapoint",
    "entity",
    "metadata",
    "normalizationbasis",
    "parameter",
    "property",
    "process",
    "measurement",
    "unit",
}
_MATERIAL_KEYWORDS = {
    "matter",
    "material",
    "chemical",
    "catalyst",
    "ionomer",
    "solvent",
    "polymer",
    "carbon",
    "platinum",
    "binder",
    "ink",
    "membrane material",
}
_COMPONENT_KEYWORDS = {
    "component",
    "device",
    "electrode",
    "membrane",
    "gasket",
    "bipolarplate",
    "plate",
    "stack",
    "assembly",
    "fuelcell",
    "gasdiffusionlayer",
    "catalystlayer",
    "mea",
}
_PROCESS_KEYWORDS = {
    "manufacturing",
    "process",
    "coating",
    "printing",
    "spray",
    "mixing",
    "drying",
    "deposition",
    "fabrication",
    "sintering",
    "calcination",
    "annealing",
    "treatment",
    "extrusion",
}
_MEASUREMENT_KEYWORDS = {
    "measurement",
    "property",
    "parameter",
    "instrument",
    "data",
    "metadata",
    "unit",
    "referenceelectrode",
    "microscopy",
    "spectroscopy",
    "imaging",
}


def _bind_all_namespaces(target: Graph, *graphs: Graph) -> None:
    for graph in graphs:
        for prefix, namespace in graph.namespaces():
            target.bind(prefix, namespace)


def _merged_graph(*graphs: Graph) -> Graph:
    merged = Graph()
    _bind_all_namespaces(merged, *graphs)
    for graph in graphs:
        for triple in graph:
            merged.add(triple)
    return merged


def _bucket_from_text(text: str) -> str:
    compact = "".join(ch.lower() for ch in text if ch.isalnum())
    if compact in _CORE_KEYWORDS:
        return "core"
    if any(keyword.replace(" ", "") in compact for keyword in _COMPONENT_KEYWORDS):
        return "components_devices"
    if any(keyword.replace(" ", "") in compact for keyword in _MATERIAL_KEYWORDS):
        return "materials"
    if any(keyword.replace(" ", "") in compact for keyword in _PROCESS_KEYWORDS):
        return "processes_manufacturing"
    if any(keyword.replace(" ", "") in compact for keyword in _MEASUREMENT_KEYWORDS):
        return "measurements_data"
    return ""


def _module_for_term(term: Any) -> str:
    class_label = str(getattr(term, "class_label", "") or "").lower()
    if class_label in {"matter", "material"}:
        return "materials"
    if class_label in {"manufacturing", "process"}:
        return "processes_manufacturing"
    if class_label in {"measurement", "property", "parameter", "data", "metadata", "instrument", "unit", "normalization basis", "reference electrode"}:
        return "measurements_data"
    if class_label in {"component", "device"}:
        return "components_devices"

    for candidate in (
        getattr(term, "label", ""),
        getattr(term, "local_name", ""),
        class_label,
        " ".join(getattr(term, "types", [])),
        " ".join(getattr(term, "superclasses", [])),
    ):
        module_id = _bucket_from_text(str(candidate))
        if module_id:
            return module_id
    return "core"


def _local_term_counts(graph: Graph, namespace_policy: dict[str, Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for subject in set(graph.subjects()):
        if not isinstance(subject, URIRef):
            continue
        if not is_local_iri(subject, namespace_policy):
            continue
        for rdf_type in graph.objects(subject, RDF.type):
            if rdf_type == OWL.Class or rdf_type == RDFS.Class:
                counts["classes"] += 1
            elif rdf_type == OWL.ObjectProperty:
                counts["object_properties"] += 1
            elif rdf_type == OWL.DatatypeProperty:
                counts["datatype_properties"] += 1
            elif rdf_type == OWL.AnnotationProperty:
                counts["annotation_properties"] += 1
            elif rdf_type == OWL.NamedIndividual:
                counts["individuals"] += 1
    return dict(counts)


def _module_dependency_graph(
    combined_graph: Graph,
    assignments: dict[str, str],
    namespace_policy: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    edge_counts: Counter[tuple[str, str]] = Counter()
    imported_domains: dict[str, set[str]] = {spec["id"]: set() for spec in _MODULE_SPECS}
    for subject, predicate, obj in combined_graph:
        if not isinstance(subject, URIRef):
            continue
        source_module = assignments.get(str(subject))
        if not source_module:
            continue
        if isinstance(obj, URIRef) and is_local_iri(obj, namespace_policy):
            target_module = assignments.get(str(obj))
            if target_module and target_module != source_module:
                edge_counts[(source_module, target_module)] += 1
        for node in (predicate, obj):
            if isinstance(node, URIRef) and not is_local_iri(node, namespace_policy):
                imported_domains[source_module].add(namespace_of(str(node)))
    edges = [
        {"source": source, "target": target, "count": count}
        for (source, target), count in sorted(edge_counts.items(), key=lambda item: (-item[1], item[0][0], item[0][1]))
    ]
    imported_rows = {module_id: sorted(values) for module_id, values in imported_domains.items()}
    return edges, imported_rows


def _module_dependency_svg(modules: list[dict[str, Any]], edges: list[dict[str, Any]]) -> str:
    positions = {
        "top": (380, 36),
        "core": (180, 118),
        "materials": (380, 118),
        "components_devices": (580, 118),
        "processes_manufacturing": (180, 214),
        "measurements_data": (380, 214),
        "mappings": (580, 214),
        "examples": (380, 304),
    }
    node_svg: list[str] = []
    for row in modules:
        x, y = positions.get(row["id"], (380, 304))
        node_svg.append(
            f"<rect x='{x - 92}' y='{y}' width='184' height='44' rx='16' fill='#ffffff' stroke='#cbd5e1'></rect>"
            f"<text x='{x}' y='{y + 20}' text-anchor='middle' font-size='13' font-family='Trebuchet MS' fill='#0f172a'>{row['label']}</text>"
            f"<text x='{x}' y='{y + 34}' text-anchor='middle' font-size='11' font-family='Trebuchet MS' fill='#64748b'>{row['term_count']} local terms</text>"
        )
    edge_svg: list[str] = []
    for edge in edges[:18]:
        sx, sy = positions.get(edge["source"], (0, 0))
        tx, ty = positions.get(edge["target"], (0, 0))
        edge_svg.append(
            f"<line x1='{sx}' y1='{sy + 44}' x2='{tx}' y2='{ty}' stroke='#0f766e' stroke-width='2' opacity='0.65'></line>"
            f"<text x='{(sx + tx) / 2:.1f}' y='{(sy + ty) / 2:.1f}' text-anchor='middle' font-size='10' font-family='Trebuchet MS' fill='#0f766e'>{edge['count']}</text>"
        )
    return (
        "<svg viewBox='0 0 760 372' width='100%' role='img' aria-label='Module dependency graph'>"
        "<rect width='760' height='372' rx='24' fill='#f8fafc'></rect>"
        + "".join(edge_svg)
        + "".join(node_svg)
        + "<text x='24' y='352' font-size='12' font-family='Trebuchet MS' fill='#475569'>Cross-module local references in the generated asserted engineering modules.</text>"
        + "</svg>"
    )


def _import_graph_svg(import_rows: list[dict[str, str]]) -> str:
    anchors = [
        (140, 92, "H2KG asserted"),
        (380, 48, "EMMO / PEMFC"),
        (620, 92, "Electrochemistry"),
        (620, 192, "Manufacturing / Coating"),
        (380, 244, "CHAMEO / Microscopy / ECM"),
        (140, 244, "HOLY / bridges"),
    ]
    cards = []
    for x, y, label in anchors:
        cards.append(
            f"<rect x='{x - 88}' y='{y - 18}' width='176' height='40' rx='16' fill='#ffffff' stroke='#cbd5e1'></rect>"
            f"<text x='{x}' y='{y + 6}' text-anchor='middle' font-size='12' font-family='Trebuchet MS' fill='#0f172a'>{label}</text>"
        )
    lines = [
        "<line x1='228' y1='92' x2='292' y2='62' stroke='#0f766e' stroke-width='2.5'></line>",
        "<line x1='228' y1='92' x2='532' y2='92' stroke='#0f766e' stroke-width='2.5'></line>",
        "<line x1='228' y1='244' x2='292' y2='230' stroke='#0f766e' stroke-width='2.5'></line>",
        "<line x1='380' y1='70' x2='620' y2='170' stroke='#0f766e' stroke-width='2.5'></line>",
        "<line x1='380' y1='226' x2='620' y2='114' stroke='#0f766e' stroke-width='2.5'></line>",
    ]
    return (
        "<svg viewBox='0 0 760 300' width='100%' role='img' aria-label='Import graph overview'>"
        "<rect width='760' height='300' rx='24' fill='#f8fafc'></rect>"
        + "".join(lines)
        + "".join(cards)
        + f"<text x='24' y='278' font-size='12' font-family='Trebuchet MS' fill='#475569'>{len(import_rows)} configured imported ontologies contribute to the release stack.</text>"
        + "</svg>"
    )


def _catalog_xml(namespace_policy: dict[str, Any], release_profile: dict[str, Any], module_rows: list[dict[str, Any]]) -> str:
    ontology_iri = str(namespace_policy["ontology_iri"]).rstrip("/")
    version = str(release_profile["release"]["version"])
    entries = [
        (ontology_iri, "asserted.ttl"),
        (f"{ontology_iri}/source", "schema.ttl"),
        (f"{ontology_iri}/inferred", "inferred.ttl"),
        (f"{ontology_iri}/context", "context.jsonld"),
        (f"{ontology_iri}/latest", "asserted.ttl"),
        (f"{ontology_iri}/{version}", "asserted.ttl"),
    ]
    module_entries = [
        (f"{ontology_iri}/source/modules/{row['filename']}", f"modules/{row['filename']}")
        for row in module_rows
        if row["id"] not in {"mappings", "examples"}
    ]
    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<catalog prefer="public" xmlns="urn:oasis:names:tc:entity:xmlns:xml:catalog">',
    ]
    for iri, target in entries + module_entries:
        xml_lines.append(f'  <uri name="{iri}" uri="{target}"/>')
    xml_lines.append("</catalog>")
    return "\n".join(xml_lines) + "\n"


def _workflow_rows(release_profile: dict[str, Any]) -> list[dict[str, Any]]:
    version = str(release_profile["release"]["version"])
    return [
        {
            "step": 1,
            "label": "Inspect and classify",
            "detail": "Read the mixed ontology source, detect local resources, and classify TBox-like, controlled vocabulary, and ABox-like content.",
            "artifacts": ["reports/inspection_report.json", "review/classification_review.csv"],
        },
        {
            "step": 2,
            "label": "Separate asserted modules",
            "detail": "Split schema, controlled vocabulary, and examples into release-friendly asserted modules without destructive rewriting.",
            "artifacts": ["ontology/schema.ttl", "ontology/controlled_vocabulary.ttl", "examples/examples.ttl"],
        },
        {
            "step": 3,
            "label": "Align and enrich",
            "detail": "Generate conservative mappings, metadata enrichment, unit enrichment, and local-vs-imported engineering summaries.",
            "artifacts": ["mappings/alignments.ttl", "reports/metadata_report.json", "reports/unit_enrichment_report.json"],
        },
        {
            "step": 4,
            "label": "Validate and reason",
            "detail": "Run validation, generate inferred outputs, and build machine-readable asserted and inferred releases.",
            "artifacts": ["ontology/inferred.ttl", "ontology/asserted.ttl", "ontology/asserted.rdf"],
        },
        {
            "step": 5,
            "label": "Publish and deploy",
            "detail": f"Generate HTML docs, search indexes, metrics, w3id assets, and versioned release files for release {version}.",
            "artifacts": ["publication/source/asserted.ttl", "publication/source/modules/", "w3id/.htaccess"],
        },
    ]


def build_engineering_artifacts(
    schema_graph: Graph,
    controlled_vocabulary_graph: Graph,
    examples_graph: Graph,
    alignments_graph: Graph,
    inferred_graph: Graph,
    classifications: dict[str, Any],
    release_profile: dict[str, Any],
    namespace_policy: dict[str, Any],
    source_registry: dict[str, Any],
    root: Path,
) -> dict[str, Any]:
    ontology_output = root / "output" / "ontology"
    reports_output = root / "output" / "reports"
    modules_output = ontology_output / "modules"

    combined_asserted = _merged_graph(schema_graph, controlled_vocabulary_graph, alignments_graph)
    full_inferred = _merged_graph(combined_asserted, inferred_graph)
    _bind_all_namespaces(combined_asserted, examples_graph)
    _bind_all_namespaces(full_inferred, examples_graph)

    ontology_node = find_ontology_node(combined_asserted, namespace_policy)
    local_terms = extract_local_terms(_merged_graph(schema_graph, controlled_vocabulary_graph), namespace_policy, classifications)

    assignment_rows: list[dict[str, Any]] = []
    assignments: dict[str, str] = {}
    for term in local_terms:
        module_id = _module_for_term(term)
        assignments[term.iri] = module_id
        assignment_rows.append(
            {
                "iri": term.iri,
                "label": term.label,
                "module_id": module_id,
                "class_label": getattr(term, "class_label", ""),
                "term_type": term.term_type,
                "category": term.category,
            }
        )

    module_graphs: dict[str, Graph] = {spec["id"]: Graph() for spec in _MODULE_SPECS}
    for graph in module_graphs.values():
        _bind_all_namespaces(graph, schema_graph, controlled_vocabulary_graph, alignments_graph, examples_graph)

    if ontology_node is not None:
        for triple in combined_asserted.triples((ontology_node, None, None)):
            module_graphs["top"].add(triple)
    for triple in alignments_graph:
        module_graphs["mappings"].add(triple)
    for triple in examples_graph:
        module_graphs["examples"].add(triple)

    for term in local_terms:
        module_id = assignments[term.iri]
        subject = URIRef(term.iri)
        for triple in combined_asserted.triples((subject, None, None)):
            module_graphs[module_id].add(triple)

    dependency_edges, imported_domains = _module_dependency_graph(combined_asserted, assignments, namespace_policy)

    module_rows: list[dict[str, Any]] = []
    for spec in _MODULE_SPECS:
        module_graph = module_graphs[spec["id"]]
        filename = spec["filename"]
        save_graph(module_graph, modules_output / filename, "turtle")
        owned_terms = [row for row in assignment_rows if row["module_id"] == spec["id"]]
        counts = Counter(row["term_type"] for row in owned_terms)
        dependency_rows = [edge["target"] for edge in dependency_edges if edge["source"] == spec["id"]]
        module_rows.append(
            {
                "id": spec["id"],
                "label": spec["label"],
                "purpose": spec["purpose"],
                "filename": filename,
                "path": f"modules/{filename}",
                "term_count": len(owned_terms),
                "triple_count": len(module_graph),
                "class_count": counts.get("class", 0),
                "object_property_count": counts.get("object property", 0),
                "datatype_property_count": counts.get("datatype property", 0),
                "controlled_term_count": sum(1 for row in owned_terms if row["category"] == "controlled_vocabulary_term"),
                "dependencies": dependency_rows,
                "imported_domains": imported_domains.get(spec["id"], []),
            }
        )

    save_graph(combined_asserted, ontology_output / "asserted.ttl", "turtle")
    save_graph(combined_asserted, ontology_output / "asserted.jsonld", "json-ld")
    save_graph(combined_asserted, ontology_output / "asserted.rdf", "xml")
    save_graph(full_inferred, ontology_output / "full_inferred.ttl", "turtle")
    save_graph(full_inferred, ontology_output / "full_inferred.rdf", "xml")

    imports = [as_uri_text(obj) for obj in combined_asserted.objects(ontology_node, OWL.imports)] if ontology_node else []
    local_counts = _local_term_counts(combined_asserted, namespace_policy)
    imported_term_count = sum(
        1
        for subject in set(combined_asserted.subjects())
        if isinstance(subject, URIRef) and not is_local_iri(subject, namespace_policy)
    )
    stats_payload = {
        "profile_label": release_profile.get("documentation", {}).get("profile_label", ""),
        "ontology_iri": namespace_policy["ontology_iri"],
        "local_term_count": len(local_terms),
        "imported_term_count": imported_term_count,
        "class_count": local_counts.get("classes", 0),
        "object_property_count": local_counts.get("object_properties", 0),
        "datatype_property_count": local_counts.get("datatype_properties", 0),
        "annotation_property_count": local_counts.get("annotation_properties", 0),
        "individual_count": local_counts.get("individuals", 0),
        "imported_ontology_count": len(imports),
        "asserted_triple_count": len(combined_asserted),
        "inferred_triple_count": len(full_inferred),
        "module_count": len(module_rows),
        "modules": [
            {"id": row["id"], "label": row["label"], "term_count": row["term_count"], "triple_count": row["triple_count"]}
            for row in module_rows
        ],
    }

    emmo_import_rows = []
    for source_id, cfg in source_registry.get("sources", {}).items():
        base_iri = str(cfg.get("base_iri", ""))
        if "w3id.org/emmo" in base_iri or source_id == "holy":
            emmo_import_rows.append(
                {
                    "source_id": source_id,
                    "title": cfg.get("title", source_id),
                    "base_iri": base_iri,
                    "enabled": bool(cfg.get("enabled", False)),
                    "category": cfg.get("category", ""),
                    "rationale": cfg.get("description", cfg.get("title", source_id)),
                }
            )
    source_counts: Counter[str] = Counter()
    relation_counts: Counter[str] = Counter()
    for subject, predicate, obj in alignments_graph:
        if predicate not in {OWL.equivalentClass, OWL.equivalentProperty, RDFS.subClassOf, RDFS.subPropertyOf}:
            continue
        if not isinstance(obj, URIRef):
            continue
        namespace = namespace_of(str(obj))
        if "w3id.org/emmo" in namespace:
            source_counts["emmo"] += 1
        elif "qudt.org" in namespace:
            source_counts["qudt"] += 1
        elif "purl.obolibrary.org/obo/CHEBI" in str(obj):
            source_counts["chebi"] += 1
        elif "w3.org/ns/prov" in namespace:
            source_counts["prov"] += 1
        elif "purl.org/dc/terms" in namespace:
            source_counts["dcterms"] += 1
        elif "purl.org/holy" in namespace:
            source_counts["holy"] += 1
        else:
            source_counts["other"] += 1
        relation_counts[local_name(predicate)] += 1
    emmo_alignment_payload = {
        "imports": imports,
        "import_rows": emmo_import_rows,
        "source_counts": dict(source_counts),
        "relation_counts": dict(relation_counts),
        "kept_local_terms": sum(1 for row in assignment_rows if row["module_id"] != "examples"),
        "alignment_triple_count": len(alignments_graph),
    }

    workflow_rows = _workflow_rows(release_profile)
    write_json(reports_output / "module_index.json", module_rows)
    write_json(reports_output / "ontology_stats.json", stats_payload)
    write_json(reports_output / "engineering_workflow.json", workflow_rows)
    write_json(reports_output / "emmo_alignment.json", emmo_alignment_payload)
    write_json(reports_output / "module_term_assignments.json", assignment_rows)
    write_text(ontology_output / "catalog-v001.xml", _catalog_xml(namespace_policy, release_profile, module_rows))
    write_text(reports_output / "module_dependency_graph.svg", _module_dependency_svg(module_rows, dependency_edges))
    write_text(reports_output / "import_graph.svg", _import_graph_svg(emmo_import_rows))

    module_md_lines = [
        "# Module Index",
        "",
        "Generated BattINFO-inspired engineering modules for the asserted H2KG release.",
        "",
    ]
    for row in module_rows:
        module_md_lines.extend(
            [
                f"## {row['label']}",
                "",
                f"- File: `modules/{row['filename']}`",
                f"- Purpose: {row['purpose']}",
                f"- Local terms: `{row['term_count']}`",
                f"- Triples: `{row['triple_count']}`",
                f"- Dependencies: {', '.join(row['dependencies']) or 'None'}",
                "",
            ]
        )
    write_text(reports_output / "module_index.md", "\n".join(module_md_lines) + "\n")

    stats_md = "\n".join(
        [
            "# Ontology Stats",
            "",
            f"- Local terms: `{stats_payload['local_term_count']}`",
            f"- Imported terms: `{stats_payload['imported_term_count']}`",
            f"- Classes: `{stats_payload['class_count']}`",
            f"- Object properties: `{stats_payload['object_property_count']}`",
            f"- Datatype properties: `{stats_payload['datatype_property_count']}`",
            f"- Annotation properties: `{stats_payload['annotation_property_count']}`",
            f"- Individuals: `{stats_payload['individual_count']}`",
            f"- Imported ontologies: `{stats_payload['imported_ontology_count']}`",
            f"- Asserted triples: `{stats_payload['asserted_triple_count']}`",
            f"- Full inferred triples: `{stats_payload['inferred_triple_count']}`",
            "",
        ]
    )
    write_text(reports_output / "ontology_stats.md", stats_md)
    return {
        "module_rows": module_rows,
        "stats": stats_payload,
        "workflow_rows": workflow_rows,
        "alignment": emmo_alignment_payload,
    }
