from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any, Iterable

from .io import dump_turtle_items, load_json_document, merge_document_items
from .utils import COMMON_CONTEXT, dump_json, ensure_dir, write_text

H2KG = COMMON_CONTEXT["h2kg"]
PROV = COMMON_CONTEXT["prov"]
DCTERMS = COMMON_CONTEXT["dcterms"]
QUDT = COMMON_CONTEXT["qudt"]
UNIT = COMMON_CONTEXT["unit"]
XSD = COMMON_CONTEXT["xsd"]
XPS_EXAMPLE_NS = "https://w3id.org/h2kg/examples/xps#"

REQUIRED_LOCAL_TERMS = {
    f"{H2KG}Process",
    f"{H2KG}Manufacturing",
    f"{H2KG}Measurement",
    f"{H2KG}Instrument",
    f"{H2KG}Matter",
    f"{H2KG}Parameter",
    f"{H2KG}Data",
    f"{H2KG}DataPoint",
    f"{H2KG}Metadata",
    f"{H2KG}hasMetadata",
    f"{H2KG}hasParameter",
    f"{H2KG}usesInstrument",
    f"{H2KG}hasInputMaterial",
    f"{H2KG}hasOutputMaterial",
    f"{H2KG}hasInputData",
    f"{H2KG}hasOutputData",
    f"{H2KG}hasQuantityValue",
    f"{H2KG}ofProperty",
    f"{H2KG}fromMeasurement",
    f"{H2KG}ExperimentDataset",
    f"{H2KG}XRayPhotoelectronSpectroscopyMeasurement",
    f"{H2KG}XPSInstrument",
    f"{H2KG}XPSDataset",
    f"{H2KG}CatalystPowder",
    f"{H2KG}PtOnCarbonCatalyst",
    f"{H2KG}CatalystInk",
    f"{H2KG}PFSAIonomer",
    f"{H2KG}XPSPassEnergy",
    f"{H2KG}XPSTakeOffAngle",
    f"{H2KG}XPSAnalysisArea",
    f"{H2KG}BindingEnergy",
    f"{H2KG}C1sAtomicPercent",
    f"{H2KG}O1sAtomicPercent",
    f"{H2KG}F1sAtomicPercent",
    f"{H2KG}N1sAtomicPercent",
    f"{H2KG}CarbonToOxygenAtomRatio",
    f"{H2KG}MetalAtomicPercent",
}


def build_xps_pilot_package(
    input_path: str | Path,
    output_root: str | Path,
) -> dict[str, Any]:
    input_path = Path(input_path)
    output_root = Path(output_root)
    target_dir = ensure_dir(output_root / "examples" / "xps_pilot")
    merged = merge_document_items(load_json_document(input_path))
    present = {
        str(item.get("@id"))
        for item in merged
        if isinstance(item.get("@id"), str)
    }
    missing = sorted(REQUIRED_LOCAL_TERMS - present)
    if missing:
        write_text(target_dir / "README.md", _missing_terms_note(missing))
        return {
            "status": "skipped_missing_terms",
            "missing_terms": missing,
            "output_dir": str(target_dir),
            "generated_files": [str(target_dir / "README.md")],
        }

    mapping_rows = _xps_mapping_rows()
    example_items = _xps_example_items()
    generated_files = [
        _write_mapping_matrix(target_dir / "xps_mapping_matrix.csv", mapping_rows),
        _write_mapping_matrix_markdown(target_dir / "xps_mapping_matrix.md", mapping_rows),
        dump_json(
            target_dir / "xps_example.jsonld",
            {"@context": {**COMMON_CONTEXT, "xpscase": XPS_EXAMPLE_NS}, "@graph": example_items},
        ),
        dump_turtle_items(target_dir / "xps_example.ttl", example_items),
        write_text(target_dir / "xps_validation_note.md", _xps_validation_note()),
        write_text(target_dir / "xps_case_summary.md", _xps_case_summary()),
        write_text(target_dir / "xps_follow_on_gaps.md", _xps_follow_on_gaps()),
        write_text(target_dir / "xps_manuscript_figure.md", _xps_manuscript_figure()),
        write_text(target_dir / "xps_manuscript_table.md", _xps_manuscript_table()),
    ]
    write_text(target_dir / "README.md", _xps_readme(generated_files))
    generated_files.append(target_dir / "README.md")
    return {
        "status": "generated",
        "output_dir": str(target_dir),
        "generated_files": [str(path) for path in generated_files],
        "mapping_row_count": len(mapping_rows),
        "example_item_count": len(example_items),
    }


def _write_mapping_matrix(path: Path, rows: list[dict[str, str]]) -> Path:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=["case_element", "example_value", "classification", "h2kg_anchor", "note"],
    )
    writer.writeheader()
    writer.writerows(rows)
    return write_text(path, buffer.getvalue())


def _write_mapping_matrix_markdown(path: Path, rows: list[dict[str, str]]) -> Path:
    lines = [
        "# XPS Case-Element Matrix",
        "",
        "This matrix maps the canonical PEMFC-focused XPS surface-chemistry case to H2KG anchors and classifies each as `reuse existing term`, `normalized existing term`, `metadata only`, or `deferred`.",
        "",
        "| Case element | Example value | Classification | H2KG anchor | Note |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {case_element} | {example_value} | {classification} | {h2kg_anchor} | {note} |".format(
                **{key: value.replace("|", "\\|") for key, value in row.items()}
            )
        )
    lines.append("")
    return write_text(path, "\n".join(lines))


def _xps_mapping_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    def add(case_element: str, example_value: str, classification: str, h2kg_anchor: str, note: str) -> None:
        rows.append(
            {
                "case_element": case_element,
                "example_value": example_value,
                "classification": classification,
                "h2kg_anchor": h2kg_anchor,
                "note": note,
            }
        )

    add(
        "Pt/C catalyst powder context",
        "Carbon-supported Pt catalyst powder",
        "reuse existing term",
        "h2kg:CatalystPowder + h2kg:PtOnCarbonCatalyst",
        "The canonical XPS case stays anchored to PEMFC-relevant Pt/C catalyst matter rather than legacy single-crystal surface inputs.",
    )
    add(
        "PFSA ionomer context",
        "PFSA binder / ionomer phase",
        "reuse existing term",
        "h2kg:PFSAIonomer",
        "Kept as a public material anchor because ionomer-related surface chemistry is a recurring PEMFC XPS use case.",
    )
    add(
        "Catalyst-ink sample conditioning",
        "Prepare dried catalyst-ink film for XPS",
        "normalized existing term",
        "h2kg:Manufacturing + h2kg:CatalystInk",
        "Sample-preparation labels stay conservative as manufacturing/process instances rather than new public XPS workflow classes.",
    )
    add(
        "XPS acquisition",
        "Surface chemical analysis of PEMFC catalyst-related sample",
        "normalized existing term",
        "h2kg:XRayPhotoelectronSpectroscopyMeasurement",
        "The public XPS method node was cleaned to a coherent acquisition neighborhood with one canonical instrument anchor and one reusable parameter family.",
    )
    add(
        "XPS instrument",
        "Laboratory XPS system",
        "normalized existing term",
        "h2kg:XPSInstrument",
        "The direct public method neighborhood now uses only the canonical XPS instrument anchor.",
    )
    add(
        "XPS pass energy",
        "20 eV",
        "normalized existing term",
        "h2kg:XPSPassEnergy",
        "Added as a reusable acquisition parameter for the public XPS neighborhood.",
    )
    add(
        "XPS take-off angle",
        "45 deg",
        "normalized existing term",
        "h2kg:XPSTakeOffAngle",
        "Added as a reusable acquisition parameter for the public XPS neighborhood.",
    )
    add(
        "XPS analysis area",
        "400 um^2",
        "normalized existing term",
        "h2kg:XPSAnalysisArea",
        "Added as a reusable acquisition parameter for the public XPS neighborhood.",
    )
    add(
        "Raw XPS dataset",
        "Survey / high-resolution spectra",
        "normalized existing term",
        "h2kg:XPSDataset",
        "Retained as the canonical public XPS data anchor.",
    )
    add(
        "Acquisition record dataset",
        "Run record / export bundle",
        "reuse existing term",
        "h2kg:ExperimentDataset",
        "Used for generic acquisition-record context without creating a dedicated XPS log class.",
    )
    add(
        "Analysis process",
        "Peak fitting and quantification",
        "reuse existing term",
        "h2kg:Process",
        "Deconvolution and quantification remain conservatively modeled through the generic Process class.",
    )
    add(
        "Binding-energy output",
        "C 1s peak at 284.8 eV",
        "normalized existing term",
        "h2kg:BindingEnergy",
        "Definition broadened to remove legacy Pt(111)-specific wording.",
    )
    add(
        "Carbon atomic percent output",
        "72 at%",
        "reuse existing term",
        "h2kg:C1sAtomicPercent",
        "Core public XPS quantification output retained on the direct method neighborhood.",
    )
    add(
        "Oxygen atomic percent output",
        "15 at%",
        "reuse existing term",
        "h2kg:O1sAtomicPercent",
        "Core public XPS quantification output retained on the direct method neighborhood.",
    )
    add(
        "Fluorine atomic percent output",
        "8 at%",
        "reuse existing term",
        "h2kg:F1sAtomicPercent",
        "Core public XPS quantification output retained on the direct method neighborhood.",
    )
    add(
        "Nitrogen atomic percent output",
        "3 at%",
        "reuse existing term",
        "h2kg:N1sAtomicPercent",
        "Core public XPS quantification output retained on the direct method neighborhood.",
    )
    add(
        "Carbon-to-oxygen atomic ratio",
        "4.8",
        "reuse existing term",
        "h2kg:CarbonToOxygenAtomRatio",
        "Retained as a compact public surface-chemistry comparison output.",
    )
    add(
        "Metal atomic percent output",
        "2 at%",
        "reuse existing term",
        "h2kg:MetalAtomicPercent",
        "Retained as a generic metal-composition output instead of exposing many element-specific or fit-specific public links on the direct method node.",
    )
    add(
        "Source / anode / charge-neutralization details",
        "Al Kα source, neutralizer on, calibration reference",
        "metadata only",
        "h2kg:hasMetadata",
        "Source, analyzer mode, calibration, and charge-control details remain metadata in this round.",
    )
    add(
        "Deconvolution fractions and state-specific ratios",
        "C 1s fractions, Co/N, metallic-metal fractions",
        "deferred",
        "-",
        "These public terms remain in the ontology, but they were intentionally removed from the direct generic XPS method neighborhood to avoid a graph-dump Explore view.",
    )
    return rows


def _xps_example_items() -> list[dict[str, Any]]:
    ex = XPS_EXAMPLE_NS

    def iri(local: str) -> str:
        return f"{ex}{local}"

    def lit(value: str, *, datatype: str | None = None, language: str | None = None) -> dict[str, str]:
        payload = {"@value": value}
        if datatype:
            payload["@type"] = datatype
        if language:
            payload["@language"] = language
        return payload

    def ref(target: str) -> dict[str, str]:
        return {"@id": target}

    def qv(
        local: str,
        value: str,
        datatype: str,
        quantity_kinds: str | Iterable[str],
        unit: str | None = None,
    ) -> dict[str, Any]:
        kinds = [quantity_kinds] if isinstance(quantity_kinds, str) else list(quantity_kinds)
        item: dict[str, Any] = {
            "@id": iri(local),
            "@type": [f"{QUDT}QuantityValue"],
            f"{QUDT}numericValue": [lit(value, datatype=datatype)],
            f"{QUDT}quantityKind": [ref(kind) for kind in kinds],
        }
        if unit:
            item[f"{QUDT}unit"] = [ref(unit)]
        return item

    def h(local_name: str) -> str:
        return f"{H2KG}{local_name}"

    items: list[dict[str, Any]] = [
        {
            "@id": iri("source-record"),
            "@type": [h("Metadata")],
            f"{DCTERMS}title": [lit("Illustrative PEMFC-related XPS surface-chemistry case", language="en")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Ontology-native XPS pilot case used to demonstrate the normalized H2KG XPS pattern.", language="en"),
                lit("This package is not derived from a workbook sheet; values are illustrative and remain non-public example instances.", language="en"),
            ],
        },
        {
            "@id": iri("ptc-catalyst-powder"),
            "@type": [h("Matter"), h("CatalystPowder"), h("PtOnCarbonCatalyst")],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Pt/C catalyst powder sample", language="en")],
            h("hasMetadata"): [ref(iri("ptc-catalyst-powder-metadata"))],
        },
        {
            "@id": iri("ptc-catalyst-powder-metadata"),
            "@type": [h("Metadata")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Example only: carbon-supported Pt catalyst powder for PEMFC catalyst-layer formulation.", language="en"),
            ],
        },
        {
            "@id": iri("pfsa-ionomer-material"),
            "@type": [h("Matter"), h("PFSAIonomer")],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("PFSA ionomer material", language="en")],
        },
        {
            "@id": iri("xps-ready-catalyst-ink-film"),
            "@type": [h("Matter"), h("CatalystInk")],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("XPS-ready catalyst-ink film", language="en")],
            h("hasMetadata"): [ref(iri("xps-ready-catalyst-ink-film-metadata"))],
        },
        {
            "@id": iri("xps-ready-catalyst-ink-film-metadata"),
            "@type": [h("Metadata")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Illustrative dried Pt/C + PFSA catalyst-ink film prepared for XPS surface analysis.", language="en"),
            ],
        },
        {
            "@id": iri("sample-conditioning-step"),
            "@type": [h("Manufacturing")],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Prepare XPS-ready catalyst-ink film", language="en")],
            h("hasInputMaterial"): [ref(iri("ptc-catalyst-powder")), ref(iri("pfsa-ionomer-material"))],
            h("hasOutputMaterial"): [ref(iri("xps-ready-catalyst-ink-film"))],
            h("hasMetadata"): [ref(iri("sample-conditioning-step-metadata"))],
        },
        {
            "@id": iri("sample-conditioning-step-metadata"),
            "@type": [h("Metadata")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Film-casting, drying, and mounting details remain metadata in this round.", language="en"),
            ],
        },
        {
            "@id": iri("xps-measurement-001"),
            "@type": [h("Measurement"), h("XRayPhotoelectronSpectroscopyMeasurement")],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("PEMFC catalyst-related XPS acquisition", language="en")],
            h("hasInputMaterial"): [ref(iri("xps-ready-catalyst-ink-film"))],
            h("usesInstrument"): [ref(iri("xps-instrument-001"))],
            h("hasParameter"): [
                ref(iri("xps-pass-energy-setting")),
                ref(iri("xps-take-off-angle-setting")),
                ref(iri("xps-analysis-area-setting")),
            ],
            h("hasOutputData"): [ref(iri("xps-dataset")), ref(iri("xps-acquisition-record"))],
            h("hasMetadata"): [ref(iri("xps-measurement-metadata"))],
        },
        {
            "@id": iri("xps-measurement-metadata"),
            "@type": [h("Metadata")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Example metadata only: Al Kα source, survey/high-resolution scan settings, charge neutralization, and calibration reference.", language="en"),
            ],
        },
        {
            "@id": iri("xps-instrument-001"),
            "@type": [h("Instrument"), h("XPSInstrument")],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("XPS instrument instance", language="en")],
            h("hasMetadata"): [ref(iri("xps-instrument-metadata"))],
        },
        {
            "@id": iri("xps-instrument-metadata"),
            "@type": [h("Metadata")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Example only: laboratory XPS spectrometer model remains metadata.", language="en"),
            ],
        },
        {
            "@id": iri("xps-dataset"),
            "@type": [h("Data"), h("XPSDataset")],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Raw XPS dataset", language="en")],
            h("hasMetadata"): [ref(iri("xps-dataset-metadata"))],
        },
        {
            "@id": iri("xps-dataset-metadata"),
            "@type": [h("Metadata")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Survey and high-resolution spectra plus exported quantification tables remain bundled as XPS dataset content.", language="en"),
            ],
        },
        {
            "@id": iri("xps-acquisition-record"),
            "@type": [h("Data"), h("ExperimentDataset")],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("XPS acquisition record dataset", language="en")],
            h("hasMetadata"): [ref(iri("xps-acquisition-record-metadata"))],
        },
        {
            "@id": iri("xps-acquisition-record-metadata"),
            "@type": [h("Metadata")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Acquisition identifier, export bundle, and operator notes remain metadata.", language="en"),
            ],
        },
        {
            "@id": iri("xps-analysis-step"),
            "@type": [h("Process")],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Peak fitting and quantification", language="en")],
            h("hasInputData"): [ref(iri("xps-dataset")), ref(iri("xps-acquisition-record"))],
            h("hasMetadata"): [ref(iri("xps-analysis-step-metadata"))],
        },
        {
            "@id": iri("xps-analysis-step-metadata"),
            "@type": [h("Metadata")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Peak fitting, background handling, and quantification assumptions remain metadata in this round.", language="en"),
            ],
        },
        {
            "@id": iri("binding-energy-datapoint"),
            "@type": [h("DataPoint")],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Binding energy data point", language="en")],
            h("ofProperty"): [ref(h("BindingEnergy"))],
            h("fromMeasurement"): [ref(iri("xps-measurement-001"))],
            h("hasQuantityValue"): [ref(iri("binding-energy-datapoint-qv"))],
            f"{PROV}wasGeneratedBy": [ref(iri("xps-analysis-step"))],
        },
        {
            "@id": iri("c1s-atomic-percent-datapoint"),
            "@type": [h("DataPoint")],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("C 1s atomic percent data point", language="en")],
            h("ofProperty"): [ref(h("C1sAtomicPercent"))],
            h("fromMeasurement"): [ref(iri("xps-measurement-001"))],
            h("hasQuantityValue"): [ref(iri("c1s-atomic-percent-datapoint-qv"))],
            f"{PROV}wasGeneratedBy": [ref(iri("xps-analysis-step"))],
        },
        {
            "@id": iri("o1s-atomic-percent-datapoint"),
            "@type": [h("DataPoint")],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("O 1s atomic percent data point", language="en")],
            h("ofProperty"): [ref(h("O1sAtomicPercent"))],
            h("fromMeasurement"): [ref(iri("xps-measurement-001"))],
            h("hasQuantityValue"): [ref(iri("o1s-atomic-percent-datapoint-qv"))],
            f"{PROV}wasGeneratedBy": [ref(iri("xps-analysis-step"))],
        },
        {
            "@id": iri("f1s-atomic-percent-datapoint"),
            "@type": [h("DataPoint")],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("F 1s atomic percent data point", language="en")],
            h("ofProperty"): [ref(h("F1sAtomicPercent"))],
            h("fromMeasurement"): [ref(iri("xps-measurement-001"))],
            h("hasQuantityValue"): [ref(iri("f1s-atomic-percent-datapoint-qv"))],
            f"{PROV}wasGeneratedBy": [ref(iri("xps-analysis-step"))],
        },
        {
            "@id": iri("n1s-atomic-percent-datapoint"),
            "@type": [h("DataPoint")],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("N 1s atomic percent data point", language="en")],
            h("ofProperty"): [ref(h("N1sAtomicPercent"))],
            h("fromMeasurement"): [ref(iri("xps-measurement-001"))],
            h("hasQuantityValue"): [ref(iri("n1s-atomic-percent-datapoint-qv"))],
            f"{PROV}wasGeneratedBy": [ref(iri("xps-analysis-step"))],
        },
        {
            "@id": iri("carbon-to-oxygen-ratio-datapoint"),
            "@type": [h("DataPoint")],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Carbon-to-oxygen atom ratio data point", language="en")],
            h("ofProperty"): [ref(h("CarbonToOxygenAtomRatio"))],
            h("fromMeasurement"): [ref(iri("xps-measurement-001"))],
            h("hasQuantityValue"): [ref(iri("carbon-to-oxygen-ratio-datapoint-qv"))],
            f"{PROV}wasGeneratedBy": [ref(iri("xps-analysis-step"))],
        },
        {
            "@id": iri("metal-atomic-percent-datapoint"),
            "@type": [h("DataPoint")],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Metal atomic percent data point", language="en")],
            h("ofProperty"): [ref(h("MetalAtomicPercent"))],
            h("fromMeasurement"): [ref(iri("xps-measurement-001"))],
            h("hasQuantityValue"): [ref(iri("metal-atomic-percent-datapoint-qv"))],
            f"{PROV}wasGeneratedBy": [ref(iri("xps-analysis-step"))],
        },
        {
            "@id": iri("xps-pass-energy-setting"),
            "@type": [h("Parameter"), h("XPSPassEnergy")],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("XPS pass energy setting", language="en")],
            h("hasQuantityValue"): [ref(iri("xps-pass-energy-setting-qv"))],
        },
        {
            "@id": iri("xps-take-off-angle-setting"),
            "@type": [h("Parameter"), h("XPSTakeOffAngle")],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("XPS take-off angle setting", language="en")],
            h("hasQuantityValue"): [ref(iri("xps-take-off-angle-setting-qv"))],
        },
        {
            "@id": iri("xps-analysis-area-setting"),
            "@type": [h("Parameter"), h("XPSAnalysisArea")],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("XPS analysis area setting", language="en")],
            h("hasQuantityValue"): [ref(iri("xps-analysis-area-setting-qv"))],
        },
        qv(
            "xps-pass-energy-setting-qv",
            "20",
            f"{XSD}decimal",
            "http://qudt.org/vocab/quantitykind/Energy",
            f"{UNIT}EV",
        ),
        qv(
            "xps-take-off-angle-setting-qv",
            "45",
            f"{XSD}decimal",
            "http://qudt.org/vocab/quantitykind/PlaneAngle",
            f"{UNIT}DEG",
        ),
        qv(
            "xps-analysis-area-setting-qv",
            "400",
            f"{XSD}decimal",
            "http://qudt.org/vocab/quantitykind/Area",
            f"{UNIT}MicroM2",
        ),
        qv(
            "binding-energy-datapoint-qv",
            "284.8",
            f"{XSD}decimal",
            "http://qudt.org/vocab/quantitykind/Energy",
            f"{UNIT}EV",
        ),
        qv(
            "c1s-atomic-percent-datapoint-qv",
            "72",
            f"{XSD}decimal",
            [
                "http://qudt.org/vocab/quantitykind/AtomPercent",
                "http://qudt.org/vocab/quantitykind/AtomicPercent",
                "http://qudt.org/vocab/quantitykind/Dimensionless",
            ],
            f"{UNIT}PERCENT",
        ),
        qv(
            "o1s-atomic-percent-datapoint-qv",
            "15",
            f"{XSD}decimal",
            [
                "http://qudt.org/vocab/quantitykind/AtomPercent",
                "http://qudt.org/vocab/quantitykind/AtomicPercent",
                "http://qudt.org/vocab/quantitykind/Dimensionless",
            ],
            f"{UNIT}PERCENT",
        ),
        qv(
            "f1s-atomic-percent-datapoint-qv",
            "8",
            f"{XSD}decimal",
            [
                "http://qudt.org/vocab/quantitykind/AtomPercent",
                "http://qudt.org/vocab/quantitykind/AtomicPercent",
                "http://qudt.org/vocab/quantitykind/Dimensionless",
            ],
            f"{UNIT}PERCENT",
        ),
        qv(
            "n1s-atomic-percent-datapoint-qv",
            "3",
            f"{XSD}decimal",
            [
                "http://qudt.org/vocab/quantitykind/AtomPercent",
                "http://qudt.org/vocab/quantitykind/AtomicPercent",
                "http://qudt.org/vocab/quantitykind/Dimensionless",
            ],
            f"{UNIT}PERCENT",
        ),
        qv(
            "carbon-to-oxygen-ratio-datapoint-qv",
            "4.8",
            f"{XSD}decimal",
            [
                "http://qudt.org/vocab/quantitykind/Ratio",
                "http://qudt.org/vocab/quantitykind/Dimensionless",
            ],
        ),
        qv(
            "metal-atomic-percent-datapoint-qv",
            "2",
            f"{XSD}decimal",
            [
                "http://qudt.org/vocab/quantitykind/AtomPercent",
                "http://qudt.org/vocab/quantitykind/AtomicPercent",
                "http://qudt.org/vocab/quantitykind/Dimensionless",
            ],
            f"{UNIT}PERCENT",
        ),
    ]
    return items


def _xps_validation_note() -> str:
    return """# XPS Validation Note

This controlled XPS round reuses the existing H2KG XPS public vocabulary rather than adding a second XPS method node.

Implemented normalization:

- `h2kg:XRayPhotoelectronSpectroscopyMeasurement` remains the canonical public XPS method node.
- The direct public XPS neighborhood was cleaned to a PEMFC-focused generic pattern:
  - `usesInstrument -> h2kg:XPSInstrument`
  - `hasInputMaterial -> h2kg:CatalystPowder`, `h2kg:PtOnCarbonCatalyst`, `h2kg:CatalystInk`, `h2kg:PFSAIonomer`
  - `hasOutputData -> h2kg:XPSDataset`, `h2kg:ExperimentDataset`
  - `hasParameter -> h2kg:XPSPassEnergy`, `h2kg:XPSTakeOffAngle`, `h2kg:XPSAnalysisArea`
  - `measures -> h2kg:BindingEnergy`, `h2kg:C1sAtomicPercent`, `h2kg:O1sAtomicPercent`, `h2kg:F1sAtomicPercent`, `h2kg:N1sAtomicPercent`, `h2kg:CarbonToOxygenAtomRatio`, `h2kg:MetalAtomicPercent`
- `h2kg:BindingEnergy`, `h2kg:XPSInstrument`, and `h2kg:XPSDataset` definitions were broadened to reusable PEMFC-oriented XPS wording.
- `h2kg:XRayPhotoelectronSpectrometer` remains in the ontology as a legacy synonym anchor but is no longer used as a direct public instrument link from the measurement node.

Intentionally deferred:

- direct public exposure of many fit-specific, state-specific, or study-specific XPS outputs on the generic XPS method node
- public promotion of survey/high-resolution mode vocabulary, charge-neutralization settings, or calibration-reference terms
- any public ABox example nodes in Explore
"""


def _xps_case_summary() -> str:
    return """# XPS Case Summary

The XPS round demonstrates how H2KG captures a PEMFC-relevant surface-chemistry characterization case without introducing a second XPS method node. A Pt/C catalyst-powder and PFSA-ionomer context feeds a conservative sample-conditioning step that yields an XPS-ready catalyst-ink film. That sample is analyzed by `h2kg:XRayPhotoelectronSpectroscopyMeasurement` using an `h2kg:XPSInstrument`, producing an `h2kg:XPSDataset` and a generic `h2kg:ExperimentDataset` acquisition record. A downstream generic `h2kg:Process` instance represents peak fitting and quantification, from which `h2kg:DataPoint` instances are linked to `h2kg:BindingEnergy`, `h2kg:C1sAtomicPercent`, `h2kg:O1sAtomicPercent`, `h2kg:F1sAtomicPercent`, `h2kg:N1sAtomicPercent`, `h2kg:CarbonToOxygenAtomRatio`, and `h2kg:MetalAtomicPercent`.

This keeps the public ontology Explore surface disciplined: users find reusable TBox anchors for XPS acquisition, datasets, parameters, and core surface-chemistry outputs, while source/anode details, calibration notes, and fit-specific deconvolution assumptions remain metadata on example instances.
"""


def _xps_follow_on_gaps() -> str:
    return """# XPS Follow-on Gaps

- Decide whether survey/high-resolution acquisition mode terms should be promoted after Raman normalization clarifies the cross-method acquisition-parameter policy.
- Revisit whether reusable XPS analysis vocabulary such as `PeakFitting` or `ChemicalStateDeconvolution` should be promoted after more than one surface-spectroscopy round depends on them.
- Decide whether some currently retained but demoted XPS outputs should move into narrower subpatterns rather than staying disconnected from the generic XPS method node.
- Use the next ontology-native round to normalize the remaining immediate extension queue: `Raman`.
"""


def _xps_manuscript_figure() -> str:
    return """# XPS Manuscript Figure Guidance

Use a combined ontology-workflow figure with **TBox-only standalone nodes** and ontology-property edge labels only.

Recommended backbone:

`Matter -> Manufacturing -> X Ray Photoelectron Spectroscopy Measurement -> XPS Dataset -> Process (analysis) -> DataPoint -> {Binding Energy, C 1 s Atomic Percent, O 1 s Atomic Percent, F 1 s Atomic Percent, N 1 s Atomic Percent, Carbon To Oxygen Atom Ratio, Metal Atomic Percent}`

Supporting ontology families:

- sample-side matter anchors:
  - `h2kg:CatalystPowder`
  - `h2kg:PtOnCarbonCatalyst`
  - `h2kg:CatalystInk`
  - `h2kg:PFSAIonomer`
- above acquisition:
  - `h2kg:XPSPassEnergy`
  - `h2kg:XPSTakeOffAngle`
  - `h2kg:XPSAnalysisArea`
- below acquisition:
  - `h2kg:XPSInstrument`
- metadata callouts:
  - source / anode details
  - charge-neutralization and calibration notes
  - file / acquisition-record metadata
  - fit-specific deconvolution notes

Important figure rule:

- do not draw deconvolution fractions or state-specific ratios as standalone nodes in this generic XPS figure
- use labels such as `survey + high-resolution spectra` or `peak fitting and quantification` only as annotations or subtitles
- do not make numeric example values public ontology nodes
"""


def _xps_manuscript_table() -> str:
    return """# XPS Manuscript Table Guidance

Prepare one companion table with columns:

- scientific case element
- H2KG ontology anchor
- example value
- figure treatment

Recommended rows:

- Pt/C catalyst powder context
- PFSA ionomer context
- catalyst-ink sample conditioning
- XPS acquisition
- XPS instrument
- XPS pass energy
- XPS take-off angle
- XPS analysis area
- raw XPS dataset
- acquisition record dataset
- analysis process
- binding energy
- C 1 s atomic percent
- O 1 s atomic percent
- F 1 s atomic percent
- N 1 s atomic percent
- carbon-to-oxygen atom ratio
- metal atomic percent
- source / calibration metadata
- fit-specific deconvolution outputs

Recommended figure-treatment values:

- standalone ontology node
- ontology edge label
- example annotation
- metadata callout
- deferred
"""


def _xps_readme(generated_files: list[Path]) -> str:
    lines = [
        "# XPS Pilot Package",
        "",
        "Generated XPS companion artifacts for the controlled PEMFC-focused normalization round.",
        "",
        "## Files",
        "",
    ]
    lines.extend(f"- `{path.name}`" for path in generated_files)
    lines.extend(
        [
            "",
            "Highlights:",
            "",
            "- Public measurement anchor reused and normalized: `h2kg:XRayPhotoelectronSpectroscopyMeasurement`",
            "- Canonical public instrument anchor: `h2kg:XPSInstrument`",
            "- Public dataset anchor retained: `h2kg:XPSDataset`",
            "- New reusable acquisition parameters: `h2kg:XPSPassEnergy`, `h2kg:XPSTakeOffAngle`, `h2kg:XPSAnalysisArea`",
            "- Canonical scientific case: PEMFC-relevant Pt/C catalyst and ionomer surface chemistry",
            "- No new public XPS method node added in this round",
        ]
    )
    return "\n".join(lines) + "\n"


def _missing_terms_note(missing: list[str]) -> str:
    bullets = "\n".join(f"- `{iri}`" for iri in missing)
    return (
        "# XPS Pilot Package\n\n"
        "The XPS pilot package was not generated because the current source ontology does not yet contain all required local terms.\n\n"
        "Missing terms:\n"
        f"{bullets}\n"
    )
