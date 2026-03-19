from __future__ import annotations

from collections import Counter
from html import escape
from pathlib import Path
from typing import Any

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS

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
_MODULE_SHORT_LABELS = {
    "top": "Top",
    "core": "Core",
    "materials": "Materials",
    "components_devices": "Components",
    "processes_manufacturing": "Processes",
    "measurements_data": "Measurements",
    "mappings": "Mappings",
    "examples": "Examples",
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


def _wrap_svg_lines(text: str, max_chars: int = 24, max_lines: int = 2) -> list[str]:
    words = str(text or "").split()
    if not words:
        return [""]
    lines: list[str] = []
    remaining = words[:]
    while remaining and len(lines) < max_lines:
        current = remaining.pop(0)
        while remaining and len(f"{current} {remaining[0]}") <= max_chars:
            current = f"{current} {remaining.pop(0)}"
        lines.append(current)
    if remaining:
        overflow = " ".join([lines[-1], *remaining]).strip()
        if len(overflow) > max_chars:
            overflow = overflow[: max_chars - 3].rstrip() + "..."
        lines[-1] = overflow
    return lines


def _svg_text_block(
    x: float,
    y: float,
    lines: list[str],
    *,
    font_size: int,
    fill: str,
    anchor: str = "middle",
    weight: str = "400",
    line_height: int = 15,
) -> str:
    tspans = []
    for index, line in enumerate(lines):
        dy = "0" if index == 0 else str(line_height)
        tspans.append(f"<tspan x='{x}' dy='{dy}'>{escape(line)}</tspan>")
    return (
        f"<text x='{x}' y='{y}' text-anchor='{anchor}' font-size='{font_size}' "
        f"font-family='Trebuchet MS' font-weight='{weight}' fill='{fill}'>"
        + "".join(tspans)
        + "</text>"
    )


def _compact_iri_label(value: str, max_chars: int = 34) -> str:
    compact = str(value).replace("https://", "").replace("http://", "").rstrip("/#")
    if len(compact) <= max_chars:
        return compact
    parts = compact.split("/")
    if len(parts) >= 2:
        reduced = f"{parts[0]}/.../{parts[-1]}"
        if len(reduced) <= max_chars:
            return reduced
    return compact[: max_chars - 3].rstrip() + "..."


def _resolve_import_title(import_iri: str, source_registry: dict[str, Any]) -> str:
    normalized = str(import_iri).rstrip("/#")
    for cfg in source_registry.get("sources", {}).values():
        base_iri = str(cfg.get("base_iri") or "").rstrip("/#")
        if not base_iri:
            continue
        if normalized == base_iri or normalized.startswith(base_iri) or base_iri.startswith(normalized):
            return str(cfg.get("title") or base_iri)
    explicit_titles = {
        "https://w3id.org/emmo": "EMMO",
        "https://w3id.org/emmo/domain/pemfc": "EMMO PEMFC",
        "https://w3id.org/emmo/domain/manufacturing": "EMMO Manufacturing",
        "https://w3id.org/emmo/domain/coating": "EMMO Coating",
        "https://w3id.org/emmo/domain/equivalent-circuit-model": "Equivalent Circuit Model",
        "https://w3id.org/emmo/domain/characterisation-methodology/chameo": "CHAMEO",
        "https://w3id.org/emmo/domain/microscopy": "EMMO Microscopy",
        "https://w3id.org/emmo/domain/electrochemistry": "EMMO Electrochemistry",
        "http://purl.org/holy/ns": "HOLY",
        "http://www.w3.org/ns/prov": "PROV-O",
    }
    if normalized in explicit_titles:
        return explicit_titles[normalized]
    tail = normalized.split("/")[-1].split("#")[-1]
    return tail.replace("-", " ").replace("_", " ").title() if tail else normalized


def _module_dependency_svg(modules: list[dict[str, Any]], edges: list[dict[str, Any]]) -> str:
    positions = {
        "top": (350, 60),
        "core": (120, 176),
        "materials": (350, 176),
        "components_devices": (580, 176),
        "processes_manufacturing": (120, 344),
        "measurements_data": (350, 344),
        "mappings": (580, 344),
        "examples": (350, 476),
    }
    card_width = 220
    card_height = 86
    half_width = card_width / 2
    half_height = card_height / 2
    top_edges = edges[:10]
    max_edge_count = max((edge["count"] for edge in top_edges), default=1)
    module_lookup = {row["id"]: row for row in modules}

    node_svg: list[str] = []
    for row in modules:
        x, y = positions.get(row["id"], (350, 476))
        label_lines = _wrap_svg_lines(row["label"], max_chars=24, max_lines=2)
        label_y = y - 12 if len(label_lines) == 1 else y - 18
        subtitle_y = y + 24 if len(label_lines) == 1 else y + 30
        node_svg.append(
            f"<rect x='{x - half_width}' y='{y - half_height}' width='{card_width}' height='{card_height}' rx='22' fill='#ffffff' stroke='#cbd5e1'></rect>"
            + _svg_text_block(x, label_y, label_lines, font_size=13, fill="#0f172a", weight="600")
            + _svg_text_block(x, subtitle_y, [f"{row['term_count']} local terms"], font_size=11, fill="#64748b")
        )

    edge_svg: list[str] = []
    legend_svg: list[str] = [
        "<rect x='706' y='42' width='250' height='470' rx='24' fill='#ffffff' stroke='#dbe4ec'></rect>",
        "<text x='730' y='76' font-size='15' font-family='Trebuchet MS' font-weight='600' fill='#0f172a'>Strongest cross-module flows</text>",
        "<text x='730' y='98' font-size='12' font-family='Trebuchet MS' fill='#64748b'>Top 10 local reference paths in the asserted engineering modules.</text>",
    ]
    for index, edge in enumerate(top_edges):
        sx, sy = positions.get(edge["source"], (0, 0))
        tx, ty = positions.get(edge["target"], (0, 0))
        if ty > sy:
            start_x, start_y = sx, sy + half_height
            end_x, end_y = tx, ty - half_height
            control_y = (sy + ty) / 2
            path = (
                f"M {start_x:.1f} {start_y:.1f} "
                f"C {start_x:.1f} {control_y:.1f}, {end_x:.1f} {control_y:.1f}, {end_x:.1f} {end_y:.1f}"
            )
        elif ty < sy:
            start_x, start_y = sx, sy - half_height
            end_x, end_y = tx, ty + half_height
            control_y = (sy + ty) / 2
            path = (
                f"M {start_x:.1f} {start_y:.1f} "
                f"C {start_x:.1f} {control_y:.1f}, {end_x:.1f} {control_y:.1f}, {end_x:.1f} {end_y:.1f}"
            )
        else:
            direction = 1 if tx > sx else -1
            start_x, start_y = sx + direction * half_width, sy
            end_x, end_y = tx - direction * half_width, ty
            lift = sy - 68 if sy < 260 else sy + 68
            path = (
                f"M {start_x:.1f} {start_y:.1f} "
                f"C {start_x + direction * 70:.1f} {lift:.1f}, {end_x - direction * 70:.1f} {lift:.1f}, {end_x:.1f} {end_y:.1f}"
            )
        stroke_width = 2.0 + (4.5 * edge["count"] / max_edge_count)
        edge_svg.append(
            f"<path d='{path}' fill='none' stroke='#0f766e' stroke-width='{stroke_width:.2f}' opacity='0.34' stroke-linecap='round'></path>"
        )
        legend_y = 136 + index * 34
        source_label = _MODULE_SHORT_LABELS.get(edge["source"], module_lookup.get(edge["source"], {}).get("label", edge["source"]))
        target_label = _MODULE_SHORT_LABELS.get(edge["target"], module_lookup.get(edge["target"], {}).get("label", edge["target"]))
        pill_width = 34 if edge["count"] < 100 else 42 if edge["count"] < 1000 else 52
        legend_svg.append(
            f"<rect x='730' y='{legend_y - 14}' width='{pill_width}' height='22' rx='11' fill='#e6fffb' stroke='#99f6e4'></rect>"
            f"<text x='{730 + pill_width / 2:.1f}' y='{legend_y + 1}' text-anchor='middle' font-size='11' font-family='Trebuchet MS' font-weight='600' fill='#0f766e'>{edge['count']}</text>"
            + _svg_text_block(782, legend_y - 2, [f"{source_label} -> {target_label}"], font_size=12, fill="#0f172a", anchor="start")
        )
    return (
        "<svg viewBox='0 0 980 560' width='100%' role='img' aria-label='Module dependency graph'>"
        "<rect width='980' height='560' rx='24' fill='#f8fafc'></rect>"
        "<text x='36' y='44' font-size='15' font-family='Trebuchet MS' font-weight='600' fill='#0f172a'>Module layout</text>"
        "<text x='36' y='66' font-size='12' font-family='Trebuchet MS' fill='#64748b'>Generated asserted engineering modules arranged by release layer and domain role.</text>"
        "<line x1='36' y1='108' x2='644' y2='108' stroke='#dbe4ec' stroke-width='1'></line>"
        "<line x1='36' y1='266' x2='644' y2='266' stroke='#dbe4ec' stroke-width='1'></line>"
        "<text x='36' y='101' font-size='11' font-family='Trebuchet MS' fill='#94a3b8'>Release frame</text>"
        "<text x='36' y='259' font-size='11' font-family='Trebuchet MS' fill='#94a3b8'>Domain modules</text>"
        "<text x='36' y='442' font-size='11' font-family='Trebuchet MS' fill='#94a3b8'>Example layer</text>"
        + "".join(edge_svg)
        + "".join(node_svg)
        + "".join(legend_svg)
        + "<text x='36' y='536' font-size='12' font-family='Trebuchet MS' fill='#475569'>Cross-module local references are shown as the ten strongest flows to keep the diagram readable.</text>"
        + "</svg>"
    )


def _import_graph_svg(import_rows: list[dict[str, str]]) -> str:
    width = 980
    height = 458
    center_x = width / 2
    center_y = 220
    hub_width = 250
    hub_height = 94
    card_width = 240
    card_height = 64
    cards: list[str] = [
        f"<rect x='{center_x - hub_width / 2:.1f}' y='{center_y - hub_height / 2:.1f}' width='{hub_width}' height='{hub_height}' rx='24' fill='#ecfeff' stroke='#94a3b8'></rect>"
        + _svg_text_block(center_x, center_y - 8, ["H2KG asserted release"], font_size=15, fill="#0f172a", weight="600")
        + _svg_text_block(center_x, center_y + 20, ["Profile header imports and release dependencies"], font_size=11, fill="#475569")
    ]
    left_rows = import_rows[: (len(import_rows) + 1) // 2]
    right_rows = import_rows[(len(import_rows) + 1) // 2 :]
    left_positions = [(170, 72 + index * 82) for index in range(len(left_rows))]
    right_positions = [(810, 72 + index * 82) for index in range(len(right_rows))]
    edges: list[str] = []
    for row, (x, y) in zip(left_rows, left_positions):
        title_lines = _wrap_svg_lines(row["title"], max_chars=24, max_lines=2)
        subtitle = _compact_iri_label(row["iri"])
        cards.append(
            f"<rect x='{x - card_width / 2:.1f}' y='{y - card_height / 2:.1f}' width='{card_width}' height='{card_height}' rx='18' fill='#ffffff' stroke='#cbd5e1'></rect>"
            + _svg_text_block(x, y - 8 if len(title_lines) == 1 else y - 14, title_lines, font_size=12, fill="#0f172a", weight="600")
            + _svg_text_block(x, y + 18, [subtitle], font_size=10, fill="#64748b")
        )
        start_x = x + card_width / 2
        end_x = center_x - hub_width / 2
        edges.append(
            f"<path d='M {start_x:.1f} {y:.1f} C {start_x + 70:.1f} {y:.1f}, {end_x - 70:.1f} {center_y:.1f}, {end_x:.1f} {center_y:.1f}' fill='none' stroke='#0f766e' stroke-width='2.5' opacity='0.45' stroke-linecap='round'></path>"
        )
    for row, (x, y) in zip(right_rows, right_positions):
        title_lines = _wrap_svg_lines(row["title"], max_chars=24, max_lines=2)
        subtitle = _compact_iri_label(row["iri"])
        cards.append(
            f"<rect x='{x - card_width / 2:.1f}' y='{y - card_height / 2:.1f}' width='{card_width}' height='{card_height}' rx='18' fill='#ffffff' stroke='#cbd5e1'></rect>"
            + _svg_text_block(x, y - 8 if len(title_lines) == 1 else y - 14, title_lines, font_size=12, fill="#0f172a", weight="600")
            + _svg_text_block(x, y + 18, [subtitle], font_size=10, fill="#64748b")
        )
        start_x = x - card_width / 2
        end_x = center_x + hub_width / 2
        edges.append(
            f"<path d='M {start_x:.1f} {y:.1f} C {start_x - 70:.1f} {y:.1f}, {end_x + 70:.1f} {center_y:.1f}, {end_x:.1f} {center_y:.1f}' fill='none' stroke='#0f766e' stroke-width='2.5' opacity='0.45' stroke-linecap='round'></path>"
        )
    return (
        "<svg viewBox='0 0 980 458' width='100%' role='img' aria-label='Import graph overview'>"
        "<rect width='980' height='458' rx='24' fill='#f8fafc'></rect>"
        "<text x='36' y='44' font-size='15' font-family='Trebuchet MS' font-weight='600' fill='#0f172a'>Declared ontology imports</text>"
        "<text x='36' y='66' font-size='12' font-family='Trebuchet MS' fill='#64748b'>Actual owl:imports declared in the active profile header, shown as release-time dependencies around the local H2KG core.</text>"
        + "".join(edges)
        + "".join(cards)
        + f"<text x='36' y='430' font-size='12' font-family='Trebuchet MS' fill='#475569'>{len(import_rows)} ontology imports are declared in the current profile header.</text>"
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


def _alignment_family(target_iri: str) -> str:
    namespace = namespace_of(target_iri)
    if "w3id.org/battinfo" in target_iri:
        return "battinfo"
    if "w3id.org/emmo" in namespace:
        return "emmo"
    if "qudt.org" in namespace:
        return "qudt"
    if "purl.obolibrary.org/obo/CHEBI" in target_iri:
        return "chebi"
    if "w3.org/ns/prov" in namespace:
        return "prov"
    if "purl.org/dc/terms" in namespace:
        return "dcterms"
    if "purl.org/holy" in namespace:
        return "holy"
    return "other"


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
    import_visual_rows = sorted(
        [{"title": _resolve_import_title(item, source_registry), "iri": item} for item in imports],
        key=lambda row: (row["title"].lower(), row["iri"]),
    )
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
    schema_source_counts: Counter[str] = Counter()
    schema_relation_counts: Counter[str] = Counter()
    vocabulary_source_counts: Counter[str] = Counter()
    vocabulary_relation_counts: Counter[str] = Counter()
    for subject, predicate, obj in alignments_graph:
        if not isinstance(obj, URIRef):
            continue
        family = _alignment_family(str(obj))
        if predicate in {OWL.equivalentClass, OWL.equivalentProperty, RDFS.subClassOf, RDFS.subPropertyOf}:
            schema_source_counts[family] += 1
            schema_relation_counts[local_name(predicate)] += 1
        elif predicate in {SKOS.exactMatch, SKOS.closeMatch}:
            vocabulary_source_counts[family] += 1
            vocabulary_relation_counts[local_name(predicate)] += 1
    emmo_alignment_payload = {
        "imports": imports,
        "import_rows": emmo_import_rows,
        "schema_source_counts": dict(schema_source_counts),
        "schema_relation_counts": dict(schema_relation_counts),
        "vocabulary_source_counts": dict(vocabulary_source_counts),
        "vocabulary_relation_counts": dict(vocabulary_relation_counts),
        "source_counts": dict(schema_source_counts),
        "relation_counts": dict(schema_relation_counts),
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
    write_text(reports_output / "import_graph.svg", _import_graph_svg(import_visual_rows))

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
