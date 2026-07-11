from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from .io import dump_turtle_items, load_json_document, merge_document_items
from .utils import COMMON_CONTEXT, dump_json, ensure_dir, write_text

H2KG = COMMON_CONTEXT["h2kg"]
PROV = COMMON_CONTEXT["prov"]
DCTERMS = COMMON_CONTEXT["dcterms"]
QUDT = COMMON_CONTEXT["qudt"]
UNIT = COMMON_CONTEXT["unit"]
XSD = COMMON_CONTEXT["xsd"]
XRD_EXAMPLE_NS = "https://w3id.org/h2kg/examples/xrd#"

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
    f"{H2KG}hasIdentifier",
    f"{H2KG}ExperimentDataset",
    f"{H2KG}XRayDiffractionMeasurement",
    f"{H2KG}XRayDiffractometer",
    f"{H2KG}CatalystPowder",
    f"{H2KG}PtOnCarbonCatalyst",
    f"{H2KG}XRDPatternDataset",
    f"{H2KG}XRayWavelength",
    f"{H2KG}XRDStepSize",
    f"{H2KG}XRDTwoThetaStart",
    f"{H2KG}XRDTwoThetaEnd",
    f"{H2KG}DiffractionPeakPosition2Theta",
    f"{H2KG}XRDPeakFWHM",
    f"{H2KG}PtCrystalliteSize",
    f"{H2KG}TheoreticalMetalSurfaceArea",
}


def build_xrd_pilot_package(
    input_path: str | Path,
    output_root: str | Path,
) -> dict[str, Any]:
    input_path = Path(input_path)
    output_root = Path(output_root)
    target_dir = ensure_dir(output_root / "examples" / "xrd_pilot")
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

    mapping_rows = _xrd_mapping_rows()
    example_items = _xrd_example_items()
    generated_files = [
        _write_mapping_matrix(target_dir / "xrd_mapping_matrix.csv", mapping_rows),
        _write_mapping_matrix_markdown(target_dir / "xrd_mapping_matrix.md", mapping_rows),
        dump_json(
            target_dir / "xrd_example.jsonld",
            {"@context": {**COMMON_CONTEXT, "xrdcase": XRD_EXAMPLE_NS}, "@graph": example_items},
        ),
        dump_turtle_items(target_dir / "xrd_example.ttl", example_items),
        write_text(target_dir / "xrd_validation_note.md", _xrd_validation_note()),
        write_text(target_dir / "xrd_case_summary.md", _xrd_case_summary()),
        write_text(target_dir / "xrd_follow_on_gaps.md", _xrd_follow_on_gaps()),
        write_text(target_dir / "xrd_manuscript_figure.md", _xrd_manuscript_figure()),
        write_text(target_dir / "xrd_manuscript_table.md", _xrd_manuscript_table()),
    ]
    write_text(target_dir / "README.md", _xrd_readme(generated_files))
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
        "# XRD Case-Element Matrix",
        "",
        "This matrix maps the canonical PEMFC Pt/C catalyst powder XRD case elements to H2KG anchors and classifies each as `reuse existing term`, `normalized existing term`, `metadata only`, or `deferred`.",
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


def _xrd_mapping_rows() -> list[dict[str, str]]:
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
        "Pt/C catalyst powder sample",
        "Carbon-supported Pt catalyst powder",
        "reuse existing term",
        "h2kg:CatalystPowder + h2kg:PtOnCarbonCatalyst",
        "The canonical XRD sample is a Pt/C catalyst powder instance typed by both public matter anchors.",
    )
    add(
        "Sample conditioning",
        "Dry powder loading / holder preparation",
        "normalized existing term",
        "h2kg:Manufacturing",
        "Kept conservative as a labeled manufacturing step without promoting XRD-specific prep vocabulary.",
    )
    add(
        "XRD acquisition",
        "Powder XRD scan for PEMFC catalyst characterization",
        "normalized existing term",
        "h2kg:XRayDiffractionMeasurement",
        "The public XRD measurement anchor was cleaned to expose a PEMFC-focused direct Explore neighborhood.",
    )
    add(
        "XRD instrument",
        "Laboratory X-ray diffractometer",
        "normalized existing term",
        "h2kg:XRayDiffractometer",
        "The public instrument anchor was generalized to a reusable catalyst/electrode characterization instrument.",
    )
    add(
        "X-ray wavelength",
        "0.15418 nm",
        "reuse existing term",
        "h2kg:XRayWavelength",
        "Captured through the standard quantity-value pattern on a parameter-setting instance.",
    )
    add(
        "XRD step size",
        "0.02 deg",
        "reuse existing term",
        "h2kg:XRDStepSize",
        "Direct public acquisition parameter on the XRD method node.",
    )
    add(
        "XRD 2 theta range start",
        "10 deg",
        "reuse existing term",
        "h2kg:XRDTwoThetaStart",
        "Direct public acquisition parameter on the XRD method node.",
    )
    add(
        "XRD 2 theta range end",
        "90 deg",
        "reuse existing term",
        "h2kg:XRDTwoThetaEnd",
        "Direct public acquisition parameter on the XRD method node.",
    )
    add(
        "Raw diffraction pattern dataset",
        "Diffractogram series",
        "normalized existing term",
        "h2kg:XRDPatternDataset",
        "Retained as the canonical raw XRD output dataset anchor.",
    )
    add(
        "Acquisition record dataset",
        "Scan log / acquisition record",
        "reuse existing term",
        "h2kg:ExperimentDataset",
        "Used for generic acquisition record context without promoting XRD-specific log classes.",
    )
    add(
        "Analysis process",
        "Scherrer-style peak analysis",
        "reuse existing term",
        "h2kg:Process",
        "Analysis remains conservatively modeled through the generic Process class.",
    )
    add(
        "Peak position output",
        "Pt(111) peak position",
        "reuse existing term",
        "h2kg:DiffractionPeakPosition2Theta",
        "Kept as a direct XRD measured-property anchor.",
    )
    add(
        "Peak FWHM output",
        "Pt(111) FWHM",
        "reuse existing term",
        "h2kg:XRDPeakFWHM",
        "Kept as a direct XRD measured-property anchor.",
    )
    add(
        "Pt crystallite size output",
        "Scherrer Pt crystallite size",
        "reuse existing term",
        "h2kg:PtCrystalliteSize",
        "Primary PEMFC catalyst outcome for the canonical XRD case.",
    )
    add(
        "Theoretical metal surface area output",
        "Surface area derived from crystallite size",
        "reuse existing term",
        "h2kg:TheoreticalMetalSurfaceArea",
        "Primary derived Pt/C surface-area outcome for the canonical XRD case.",
    )
    add(
        "Supplier and holder details",
        "Vendor, lot number, holder notes",
        "metadata only",
        "h2kg:hasMetadata",
        "Contextual sample and setup details remain metadata rather than public standalone ontology nodes.",
    )
    add(
        "Peak-selection / Scherrer assumptions",
        "Pt(111); shape factor and density assumptions",
        "metadata only",
        "h2kg:hasMetadata",
        "The pilot records these as analysis metadata rather than promoting a new public analysis vocabulary in this round.",
    )
    add(
        "Advanced XRD analysis vocabulary",
        "Phase identification / Rietveld refinement",
        "deferred",
        "-",
        "Deferred to a later cross-method characterization round after XPS and Raman stabilization.",
    )
    return rows


def _xrd_example_items() -> list[dict[str, Any]]:
    ex = XRD_EXAMPLE_NS

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

    def qv(local: str, value: str, datatype: str, quantity_kind: str, unit: str) -> dict[str, Any]:
        return {
            "@id": iri(local),
            "@type": [f"{QUDT}QuantityValue"],
            f"{QUDT}numericValue": [lit(value, datatype=datatype)],
            f"{QUDT}quantityKind": [ref(quantity_kind)],
            f"{QUDT}unit": [ref(unit)],
        }

    def h(local_name: str) -> str:
        return f"{H2KG}{local_name}"

    items: list[dict[str, Any]] = [
        {
            "@id": iri("source-record"),
            "@type": [h("Metadata")],
            f"{DCTERMS}title": [lit("Illustrative PEMFC Pt/C catalyst powder XRD case", language="en")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Ontology-native XRD pilot case used to demonstrate the normalized H2KG XRD pattern.", language="en"),
                lit("This package is not derived from a workbook sheet; values are illustrative and remain non-public example instances.", language="en"),
            ],
        },
        {
            "@id": iri("pdc-catalyst-powder"),
            "@type": [h("Matter"), h("CatalystPowder"), h("PtOnCarbonCatalyst")],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Pt/C catalyst powder sample", language="en")],
            h("hasMetadata"): [ref(iri("pdc-catalyst-powder-metadata"))],
        },
        {
            "@id": iri("pdc-catalyst-powder-metadata"),
            "@type": [h("Metadata")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Example only: commercial carbon-supported Pt catalyst powder.", language="en"),
                lit("Supplier, lot, and Pt wt.% stay as metadata in the pilot.", language="en"),
            ],
        },
        {
            "@id": iri("conditioned-pdc-catalyst-powder"),
            "@type": [h("Matter"), h("CatalystPowder"), h("PtOnCarbonCatalyst")],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Conditioned Pt/C catalyst powder for XRD", language="en")],
            h("hasMetadata"): [ref(iri("conditioned-pdc-catalyst-powder-metadata"))],
        },
        {
            "@id": iri("conditioned-pdc-catalyst-powder-metadata"),
            "@type": [h("Metadata")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Example conditioning note: dry powder loaded on an XRD sample holder.", language="en"),
            ],
        },
        {
            "@id": iri("sample-conditioning-step"),
            "@type": [h("Manufacturing")],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Prepare Pt/C powder for XRD acquisition", language="en")],
            h("hasInputMaterial"): [ref(iri("pdc-catalyst-powder"))],
            h("hasOutputMaterial"): [ref(iri("conditioned-pdc-catalyst-powder"))],
        },
        {
            "@id": iri("xrd-measurement-001"),
            "@type": [h("Measurement"), h("XRayDiffractionMeasurement")],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Pt/C catalyst powder XRD acquisition", language="en")],
            h("hasInputMaterial"): [ref(iri("conditioned-pdc-catalyst-powder"))],
            h("usesInstrument"): [ref(iri("xrd-instrument-001"))],
            h("hasParameter"): [
                ref(iri("xray-wavelength-setting")),
                ref(iri("xrd-step-size-setting")),
                ref(iri("xrd-two-theta-start-setting")),
                ref(iri("xrd-two-theta-end-setting")),
            ],
            h("hasOutputData"): [ref(iri("xrd-pattern-dataset")), ref(iri("xrd-acquisition-record"))],
            h("hasMetadata"): [ref(iri("xrd-measurement-metadata"))],
        },
        {
            "@id": iri("xrd-measurement-metadata"),
            "@type": [h("Metadata")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Illustrative powder XRD scan for PEMFC catalyst characterization.", language="en"),
            ],
        },
        {
            "@id": iri("xrd-instrument-001"),
            "@type": [h("Instrument"), h("XRayDiffractometer")],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("XRD instrument instance", language="en")],
            h("hasMetadata"): [ref(iri("xrd-instrument-metadata"))],
        },
        {
            "@id": iri("xrd-instrument-metadata"),
            "@type": [h("Metadata")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Example only: laboratory diffractometer model and holder details remain metadata.", language="en"),
            ],
        },
        {
            "@id": iri("xrd-pattern-dataset"),
            "@type": [h("Data"), h("XRDPatternDataset")],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Raw XRD pattern dataset", language="en")],
            h("hasMetadata"): [ref(iri("xrd-pattern-dataset-metadata"))],
        },
        {
            "@id": iri("xrd-pattern-dataset-metadata"),
            "@type": [h("Metadata")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Example only: diffraction pattern exported as a raw diffractogram file.", language="en"),
            ],
        },
        {
            "@id": iri("xrd-acquisition-record"),
            "@type": [h("Data"), h("ExperimentDataset")],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("XRD acquisition record dataset", language="en")],
            h("hasMetadata"): [ref(iri("xrd-acquisition-record-metadata"))],
        },
        {
            "@id": iri("xrd-acquisition-record-metadata"),
            "@type": [h("Metadata")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Scan notes, run identifier, and acquisition-log details remain metadata.", language="en"),
            ],
        },
        {
            "@id": iri("peak-analysis-step"),
            "@type": [h("Process")],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Scherrer-style peak analysis", language="en")],
            h("hasInputData"): [ref(iri("xrd-pattern-dataset")), ref(iri("xrd-acquisition-record"))],
            h("hasMetadata"): [ref(iri("peak-analysis-step-metadata"))],
        },
        {
            "@id": iri("peak-analysis-step-metadata"),
            "@type": [h("Metadata")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Illustrative analysis note: Pt(111) peak used for peak-position, FWHM, and Scherrer-derived size calculations.", language="en"),
                lit("Shape-factor and density assumptions remain analysis metadata in this round.", language="en"),
            ],
        },
        {
            "@id": iri("diffraction-peak-position-datapoint"),
            "@type": [h("DataPoint")],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Diffraction peak position data point", language="en")],
            h("ofProperty"): [ref(h("DiffractionPeakPosition2Theta"))],
            h("fromMeasurement"): [ref(iri("xrd-measurement-001"))],
            h("hasQuantityValue"): [ref(iri("diffraction-peak-position-datapoint-qv"))],
            f"{PROV}wasGeneratedBy": [ref(iri("peak-analysis-step"))],
        },
        {
            "@id": iri("xrd-peak-fwhm-datapoint"),
            "@type": [h("DataPoint")],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("XRD peak FWHM data point", language="en")],
            h("ofProperty"): [ref(h("XRDPeakFWHM"))],
            h("fromMeasurement"): [ref(iri("xrd-measurement-001"))],
            h("hasQuantityValue"): [ref(iri("xrd-peak-fwhm-datapoint-qv"))],
            f"{PROV}wasGeneratedBy": [ref(iri("peak-analysis-step"))],
        },
        {
            "@id": iri("pt-crystallite-size-datapoint"),
            "@type": [h("DataPoint")],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Pt crystallite size data point", language="en")],
            h("ofProperty"): [ref(h("PtCrystalliteSize"))],
            h("fromMeasurement"): [ref(iri("xrd-measurement-001"))],
            h("hasQuantityValue"): [ref(iri("pt-crystallite-size-datapoint-qv"))],
            f"{PROV}wasGeneratedBy": [ref(iri("peak-analysis-step"))],
        },
        {
            "@id": iri("theoretical-metal-surface-area-datapoint"),
            "@type": [h("DataPoint")],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Theoretical metal surface area data point", language="en")],
            h("ofProperty"): [ref(h("TheoreticalMetalSurfaceArea"))],
            h("fromMeasurement"): [ref(iri("xrd-measurement-001"))],
            h("hasQuantityValue"): [ref(iri("theoretical-metal-surface-area-datapoint-qv"))],
            f"{PROV}wasGeneratedBy": [ref(iri("peak-analysis-step"))],
        },
        {
            "@id": iri("xray-wavelength-setting"),
            "@type": [h("Parameter"), h("XRayWavelength")],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("X-ray wavelength setting", language="en")],
            h("hasQuantityValue"): [ref(iri("xray-wavelength-setting-qv"))],
        },
        {
            "@id": iri("xrd-step-size-setting"),
            "@type": [h("Parameter"), h("XRDStepSize")],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("XRD step size setting", language="en")],
            h("hasQuantityValue"): [ref(iri("xrd-step-size-setting-qv"))],
        },
        {
            "@id": iri("xrd-two-theta-start-setting"),
            "@type": [h("Parameter"), h("XRDTwoThetaStart")],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("XRD two theta start setting", language="en")],
            h("hasQuantityValue"): [ref(iri("xrd-two-theta-start-setting-qv"))],
        },
        {
            "@id": iri("xrd-two-theta-end-setting"),
            "@type": [h("Parameter"), h("XRDTwoThetaEnd")],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("XRD two theta end setting", language="en")],
            h("hasQuantityValue"): [ref(iri("xrd-two-theta-end-setting-qv"))],
        },
        qv(
            "xray-wavelength-setting-qv",
            "0.15418",
            f"{XSD}decimal",
            "http://qudt.org/vocab/quantitykind/Wavelength",
            f"{UNIT}NanoM",
        ),
        qv(
            "xrd-step-size-setting-qv",
            "0.02",
            f"{XSD}decimal",
            "http://qudt.org/vocab/quantitykind/PlaneAngle",
            f"{UNIT}DEG",
        ),
        qv(
            "xrd-two-theta-start-setting-qv",
            "10",
            f"{XSD}decimal",
            "http://qudt.org/vocab/quantitykind/PlaneAngle",
            f"{UNIT}DEG",
        ),
        qv(
            "xrd-two-theta-end-setting-qv",
            "90",
            f"{XSD}decimal",
            "http://qudt.org/vocab/quantitykind/PlaneAngle",
            f"{UNIT}DEG",
        ),
        qv(
            "diffraction-peak-position-datapoint-qv",
            "39.8",
            f"{XSD}decimal",
            "http://qudt.org/vocab/quantitykind/PlaneAngle",
            f"{UNIT}DEG",
        ),
        qv(
            "xrd-peak-fwhm-datapoint-qv",
            "0.9",
            f"{XSD}decimal",
            "http://qudt.org/vocab/quantitykind/PlaneAngle",
            f"{UNIT}DEG",
        ),
        qv(
            "pt-crystallite-size-datapoint-qv",
            "3.1",
            f"{XSD}decimal",
            "http://qudt.org/vocab/quantitykind/Length",
            f"{UNIT}NanoM",
        ),
        qv(
            "theoretical-metal-surface-area-datapoint-qv",
            "100",
            f"{XSD}decimal",
            "http://qudt.org/vocab/quantitykind/AreaPerMass",
            "http://qudt.org/vocab/unit/M2-PER-GM",
        ),
    ]
    return items


def _xrd_validation_note() -> str:
    return """# XRD Validation Note

This controlled XRD round reuses the existing H2KG XRD public vocabulary rather than adding a second XRD method node.

Implemented normalization:

- `h2kg:XRayDiffractionMeasurement` remains the canonical public XRD method node.
- The direct public XRD neighborhood was cleaned to the PEMFC Pt/C catalyst powder pattern only:
  - `usesInstrument -> h2kg:XRayDiffractometer`
  - `hasInputMaterial -> h2kg:CatalystPowder`, `h2kg:PtOnCarbonCatalyst`
  - `hasOutputData -> h2kg:XRDPatternDataset`, `h2kg:ExperimentDataset`
  - `hasParameter -> h2kg:XRayWavelength`, `h2kg:XRDStepSize`, `h2kg:XRDTwoThetaStart`, `h2kg:XRDTwoThetaEnd`
  - `measures -> h2kg:DiffractionPeakPosition2Theta`, `h2kg:XRDPeakFWHM`, `h2kg:PtCrystalliteSize`, `h2kg:TheoreticalMetalSurfaceArea`
- `h2kg:XRayDiffractometer` and `h2kg:XRDPatternDataset` definitions were broadened to reusable catalyst/electrode characterization wording.

Intentionally deferred:

- public promotion of XRD-specific analysis classes such as Scherrer analysis, phase identification, or Rietveld refinement
- broader non-PEMFC XRD cleanup outside the direct public measurement neighborhood
- any public ABox example nodes in Explore
"""


def _xrd_case_summary() -> str:
    return """# XRD Case Summary

The XRD round demonstrates how H2KG captures a PEMFC-relevant Pt/C catalyst powder characterization case without introducing a second XRD method node. A catalyst-powder sample enters a conservative sample-conditioning step, is analyzed by `h2kg:XRayDiffractionMeasurement` using an `h2kg:XRayDiffractometer`, and yields an `h2kg:XRDPatternDataset` plus a generic `h2kg:ExperimentDataset` acquisition record. A downstream generic `h2kg:Process` instance represents peak analysis, from which `h2kg:DataPoint` instances are linked to `h2kg:DiffractionPeakPosition2Theta`, `h2kg:XRDPeakFWHM`, `h2kg:PtCrystalliteSize`, and `h2kg:TheoreticalMetalSurfaceArea`.

This keeps the public ontology Explore surface disciplined: users find reusable TBox anchors for XRD acquisition, datasets, parameters, and core Pt/C-derived outputs, while supplier details, holder details, and Scherrer-analysis assumptions remain metadata on example instances.
"""


def _xrd_follow_on_gaps() -> str:
    return """# XRD Follow-on Gaps

- Decide whether a reusable `ScherrerAnalysis` process term should be promoted after XPS and Raman rounds establish the broader characterization-analysis pattern.
- Revisit whether legacy non-PEMFC XRD measured-property links should be split into narrower XRD subpatterns instead of remaining on the generic property inventory.
- Decide whether phase-identification outputs merit public promotion once a stable PEMFC-relevant multi-phase XRD case is available.
- Use the next ontology-native rounds to normalize sibling characterization families in order: `XPS`, then `Raman`.
"""


def _xrd_manuscript_figure() -> str:
    return """# XRD Manuscript Figure Guidance

Use a combined ontology-workflow figure with **TBox-only standalone nodes** and ontology-property edge labels only.

Recommended backbone:

`Matter -> Manufacturing -> X Ray Diffraction Measurement -> XRD Pattern Dataset -> Process (analysis) -> DataPoint -> {Pt Crystallite Size, Theoretical Metal Surface Area}`

Supporting ontology families:

- sample node:
  - `h2kg:CatalystPowder`
  - `h2kg:PtOnCarbonCatalyst`
- above acquisition:
  - `h2kg:XRayWavelength`
  - `h2kg:XRDStepSize`
  - `h2kg:XRDTwoThetaStart`
  - `h2kg:XRDTwoThetaEnd`
- below acquisition:
  - `h2kg:XRayDiffractometer`
- analysis-side measured outputs:
  - `h2kg:DiffractionPeakPosition2Theta`
  - `h2kg:XRDPeakFWHM`
  - `h2kg:PtCrystalliteSize`
  - `h2kg:TheoreticalMetalSurfaceArea`
- metadata callouts:
  - supplier / lot / Pt wt.% context
  - holder / run-record context
  - Scherrer-assumption note

Important figure rule:

- do not draw worksheet-style procedural labels as standalone nodes
- use annotations such as `powder loading`, `Pt(111) peak`, or `Scherrer-style analysis` only inside callouts or subtitles
- do not make example datapoint values public ontology nodes
"""


def _xrd_manuscript_table() -> str:
    return """# XRD Manuscript Table Guidance

Prepare one companion table with columns:

- scientific case element
- H2KG ontology anchor
- example value
- figure treatment

Recommended rows:

- Pt/C catalyst powder sample
- sample-conditioning step
- XRD acquisition
- XRD instrument
- X-ray wavelength
- XRD step size
- XRD 2 theta start
- XRD 2 theta end
- raw XRD pattern dataset
- acquisition record dataset
- analysis process
- diffraction peak position
- XRD peak FWHM
- Pt crystallite size
- theoretical metal surface area
- supplier / holder metadata
- Scherrer-assumption metadata

Recommended figure-treatment values:

- standalone ontology node
- ontology edge label
- example annotation
- metadata callout
- deferred
"""


def _xrd_readme(generated_files: list[Path]) -> str:
    lines = [
        "# XRD Pilot Package",
        "",
        "Generated XRD companion artifacts for the controlled PEMFC-focused normalization round.",
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
            "- Public measurement anchor reused and normalized: `h2kg:XRayDiffractionMeasurement`",
            "- Public instrument anchor reused and normalized: `h2kg:XRayDiffractometer`",
            "- Public dataset anchors used directly: `h2kg:XRDPatternDataset`, `h2kg:ExperimentDataset`",
            "- Canonical scientific case: Pt/C catalyst powder characterization",
            "- Primary XRD outputs: `h2kg:PtCrystalliteSize`, `h2kg:TheoreticalMetalSurfaceArea`",
            "- No new public XRD method node added in this round",
        ]
    )
    return "\n".join(lines) + "\n"


def _missing_terms_note(missing: list[str]) -> str:
    bullets = "\n".join(f"- `{iri}`" for iri in missing)
    return (
        "# XRD Pilot Package\n\n"
        "The XRD pilot package was not generated because the current source ontology does not yet contain all required local terms.\n\n"
        "Missing terms:\n"
        f"{bullets}\n"
    )
