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
AFM_EXAMPLE_NS = "https://w3id.org/h2kg/examples/afm#"

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
    f"{H2KG}hasPart",
    f"{H2KG}hasIdentifier",
    f"{H2KG}AtomicForceMicroscopyMeasurement",
    f"{H2KG}AFMInstrument",
    f"{H2KG}AFMScanSpeed",
    f"{H2KG}AFMTipNominalRadius",
    f"{H2KG}SurfaceTopographyDataset",
    f"{H2KG}MicrostructureImageDataset",
    f"{H2KG}MeanParticleSize",
    f"{H2KG}Temperature",
    f"{H2KG}RelativeHumidity",
    f"{H2KG}MicroscopyMeasuredArea",
    f"{H2KG}CantileverSpringConstant",
    f"{H2KG}CantileverResonanceFrequency",
    f"{H2KG}DryingTemperature",
    f"{H2KG}DryingTime",
    f"{H2KG}FijiImageJSoftware",
    f"{H2KG}MEAAssembly",
}


def build_afm_pilot_package(
    input_path: str | Path,
    output_root: str | Path,
) -> dict[str, Any]:
    input_path = Path(input_path)
    output_root = Path(output_root)
    target_dir = ensure_dir(output_root / "examples" / "afm_pilot")
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

    mapping_rows = _afm_mapping_rows()
    example_items = _afm_example_items()
    generated_files = [
        _write_mapping_matrix(target_dir / "afm_mapping_matrix.csv", mapping_rows),
        _write_mapping_matrix_markdown(target_dir / "afm_mapping_matrix.md", mapping_rows),
        dump_json(
            target_dir / "afm_example.jsonld",
            {"@context": {**COMMON_CONTEXT, "afmcase": AFM_EXAMPLE_NS}, "@graph": example_items},
        ),
        dump_turtle_items(target_dir / "afm_example.ttl", example_items),
        write_text(target_dir / "afm_validation_note.md", _afm_validation_note()),
        write_text(target_dir / "afm_case_summary.md", _afm_case_summary()),
        write_text(target_dir / "afm_follow_on_gaps.md", _afm_follow_on_gaps()),
        write_text(target_dir / "afm_manuscript_figure.md", _afm_manuscript_figure()),
        write_text(target_dir / "afm_manuscript_table.md", _afm_manuscript_table()),
    ]
    write_text(target_dir / "README.md", _afm_readme(generated_files))
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
        fieldnames=["section", "field", "example_value", "classification", "h2kg_anchor", "note"],
    )
    writer.writeheader()
    writer.writerows(rows)
    return write_text(path, buffer.getvalue())


def _write_mapping_matrix_markdown(path: Path, rows: list[dict[str, str]]) -> Path:
    lines = [
        "# AFM Mapping Matrix",
        "",
        "This matrix accounts for each populated AFM sheet field and classifies it as `reuse existing term`, `new ontology term`, `instance metadata`, or `not modeled` for the controlled AFM round.",
        "",
        "| Section | Field | Example value | Classification | H2KG anchor | Note |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {section} | {field} | {example_value} | {classification} | {h2kg_anchor} | {note} |".format(
                **{key: value.replace("|", "\\|") for key, value in row.items()}
            )
        )
    lines.append("")
    return write_text(path, "\n".join(lines))


def _afm_mapping_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    def add(section: str, field: str, example_value: str, classification: str, h2kg_anchor: str, note: str) -> None:
        rows.append(
            {
                "section": section,
                "field": field,
                "example_value": example_value,
                "classification": classification,
                "h2kg_anchor": h2kg_anchor,
                "note": note,
            }
        )

    for field, value, classification, anchor, note in [
        ("ExperimentTitle", "Quantitative in Situ Analysis of Ionomer Structure in Fuel Cell catalytic layer", "instance metadata", "h2kg:hasMetadata + dcterms:title", "Stored on the AFM source-record metadata node."),
        ("ExperimentID", "5", "instance metadata", "h2kg:hasMetadata + h2kg:hasIdentifier", "Stored as a literal identifier on the source record."),
        ("Measurement-ID", "Run derived DOI", "instance metadata", "h2kg:hasMetadata + h2kg:hasIdentifier", "Stored on AFM measurement metadata."),
        ("UploadDate", "2023-10-11", "instance metadata", "h2kg:hasMetadata + dcterms:date", "Excel serial normalized to ISO date."),
        ("Institution", "DLR", "instance metadata", "prov:Agent", "Represented as an institutional agent."),
        ("FoundingBody", "HIP", "instance metadata", "prov:Agent", "Represented as a funding-body agent."),
        ("Country", "Germany", "instance metadata", "h2kg:hasMetadata", "Retained as contextual metadata."),
        ("Author", "Tobias Morawitz; Andre Colliard Granero", "instance metadata", "prov:Agent", "Represented as author agent instances."),
        ("ORCID", "123-465-7777; 321-321-3211", "instance metadata", "h2kg:hasMetadata", "Stored on author metadata nodes."),
        ("Email", "tobi.mora@dlr.de; andyhuebsch@gmail.mx", "instance metadata", "h2kg:hasMetadata", "Stored on author metadata nodes."),
        ("Published", "1", "instance metadata", "h2kg:hasMetadata", "Retained as publication-status metadata."),
        ("Publication", "Quantitative in Situ Analysis of Ionomer Structure in Fuel Cell catalytic layer", "instance metadata", "h2kg:hasMetadata + dcterms:title", "Stored on a publication metadata node."),
        ("DOI", "https://doi.org/10.3390/afm38383", "instance metadata", "h2kg:hasMetadata + dcterms:identifier", "Stored on a publication metadata node."),
        ("Journal", "PCCP", "instance metadata", "h2kg:hasMetadata", "Retained as bibliographic metadata."),
        ("Volume", "8", "instance metadata", "h2kg:hasMetadata", "Retained as bibliographic metadata."),
        ("Issue", "78", "instance metadata", "h2kg:hasMetadata", "Retained as bibliographic metadata."),
        ("Pages", "789-987", "instance metadata", "h2kg:hasMetadata", "Retained as bibliographic metadata."),
        ("PublicationDate", "2012-11-28", "instance metadata", "h2kg:hasMetadata + dcterms:issued", "Excel serial normalized to ISO date."),
        ("Topic", "Fuel cell", "instance metadata", "h2kg:hasMetadata", "Retained as topical metadata."),
        ("Device", "PEMFC", "instance metadata", "h2kg:hasMetadata", "Retained as application-context metadata."),
        ("Component", "MEA", "instance metadata", "h2kg:MEAAssembly", "Used as MEA application context metadata."),
        ("Subcomponent", "Catalyst layer", "instance metadata", "h2kg:hasMetadata", "Retained as subcomponent metadata."),
        ("Granularity Level", "Microstructure", "instance metadata", "h2kg:hasMetadata", "Retained as scale metadata."),
        ("Format", "tiff", "instance metadata", "h2kg:hasMetadata + dcterms:format", "Stored on raw-dataset metadata."),
        ("FileSize", "258", "instance metadata", "h2kg:hasMetadata + dcterms:extent", "Stored with file-size unit in raw-dataset metadata."),
        ("FileSizeUnit", "MB", "instance metadata", "h2kg:hasMetadata + dcterms:extent", "Stored with file size in raw-dataset metadata."),
        ("FileName", "afm_rawdata.tif", "instance metadata", "h2kg:hasMetadata", "Stored on raw-dataset metadata."),
        ("DimensionX", "256", "instance metadata", "h2kg:hasMetadata", "Stored on raw-dataset metadata."),
        ("DimensionY", "256", "instance metadata", "h2kg:hasMetadata", "Stored on raw-dataset metadata."),
        ("DimensionZ", "0", "instance metadata", "h2kg:hasMetadata", "Stored on raw-dataset metadata."),
        ("PixelPerMetric", "8.1", "instance metadata", "h2kg:hasMetadata", "Stored on raw-dataset metadata."),
        ("Link", "link", "instance metadata", "h2kg:hasMetadata + dcterms:source", "Stored as source/link metadata."),
        ("MaskExist", "yes", "instance metadata", "h2kg:hasMetadata", "Stored on processed-dataset metadata."),
        ("MaskLink", "link", "instance metadata", "h2kg:hasMetadata + dcterms:source", "Stored on processed-dataset metadata."),
    ]:
        add("org", field, value, classification, anchor, note)

    for field, value, classification, anchor, note in [
        ("Step 1 Precursor", "Pd/C", "instance metadata", "h2kg:Matter", "Represented as a material instance with supplier, lot-number, and CAS metadata."),
        ("Step 1 AmountPrecursor", "5 wt%", "instance metadata", "h2kg:hasMetadata", "Stored as precursor material metadata."),
        ("Step 1 Technique", "Buy", "reuse existing term", "h2kg:Process", "Modeled as a labeled procurement process instance rather than a new TBox term."),
        ("Step 1 Condition", "Manufacturer = SigmaAldrich; Loot number = 205680; CAS-number = 7440-05-3", "instance metadata", "h2kg:hasMetadata", "Stored as procurement metadata on the Pd/C precursor."),
        ("Step 1 Target", "SInt1", "instance metadata", "h2kg:Matter", "Represents the procured catalyst material instance."),
        ("Step 2 Precursor", "SInt1", "instance metadata", "h2kg:Matter", "Uses the procured catalyst material as input."),
        ("Step 2 Technique", "Sieve", "reuse existing term", "h2kg:Manufacturing", "Modeled as a labeled manufacturing instance."),
        ("Step 2 Condition", "sieve size = 75 um", "instance metadata", "h2kg:hasMetadata", "Retained as sieving metadata in round 1."),
        ("Step 2 Target", "SInt2", "instance metadata", "h2kg:Matter", "Represents the sieved catalyst material."),
        ("Step 3 Precursor", "SInt2", "instance metadata", "h2kg:Matter", "Uses the sieved catalyst material as input."),
        ("Step 3 Technique", "Dry", "reuse existing term", "h2kg:Manufacturing", "Modeled as a labeled manufacturing instance with drying parameters."),
        ("Step 3 Condition", "Temperature = 100 deg C; Time = 10 h", "reuse existing term", "h2kg:DryingTemperature + h2kg:DryingTime", "Modeled through parameter-setting instances linked to the drying step."),
        ("Step 3 Target", "MEA", "instance metadata", "h2kg:MEAAssembly", "Represents the MEA-oriented material context used for AFM sample preparation."),
    ]:
        add("syn", field, value, classification, anchor, note)

    for field, value, classification, anchor, note in [
        ("Step 1 Precursor", "MEA", "instance metadata", "h2kg:MEAAssembly", "Represents the MEA sample entering AFM preparation."),
        ("Step 1 Technique", "Cut", "reuse existing term", "h2kg:Manufacturing", "Modeled as a labeled manufacturing instance rather than a new TBox term."),
        ("Step 1 Condition", "Size = 25 cm2", "instance metadata", "h2kg:hasMetadata", "Retained as cut-step metadata."),
        ("Step 1 Target", "SPInt1", "instance metadata", "h2kg:Matter", "Represents the cut MEA sample."),
        ("Step 2 Precursor", "SPInt1; Terosion Teromix PU6700", "instance metadata", "h2kg:Matter", "Cut sample and embedding resin are retained as material metadata."),
        ("Step 2 Technique", "Embedded", "reuse existing term", "h2kg:Manufacturing", "Modeled as a labeled manufacturing instance."),
        ("Step 2 Condition", "-", "instance metadata", "h2kg:hasMetadata", "No explicit embedding condition was reported."),
        ("Step 2 Target", "SPInt2", "instance metadata", "h2kg:Matter", "Represents the embedded sample."),
        ("Step 3 Precursor", "SPInt2", "instance metadata", "h2kg:Matter", "Uses the embedded sample as input."),
        ("Step 3 Technique", "Curated", "reuse existing term", "h2kg:Manufacturing", "Modeled conservatively as a labeled curing process instance."),
        ("Step 3 Condition", "Temperature = 25 deg C; Time = 24 h", "instance metadata", "h2kg:hasMetadata", "Retained as curing metadata in round 1."),
        ("Step 3 Target", "SPInt3", "instance metadata", "h2kg:Matter", "Represents the cured embedded sample."),
        ("Step 4 Precursor", "SPInt3", "instance metadata", "h2kg:Matter", "Uses the cured sample as input."),
        ("Step 4 Technique", "Microtome cut", "reuse existing term", "h2kg:Manufacturing", "Modeled as a labeled sectioning process instance."),
        ("Step 4 Condition", "Microtome = Leitz; Thickness = 2 mm", "instance metadata", "h2kg:hasMetadata", "Retained as sectioning metadata in round 1."),
        ("Step 4 Target", "SPInt4", "instance metadata", "h2kg:Matter", "Represents the sectioned AFM sample intermediate."),
        ("Step 5 Precursor", "SPInt4; Double sided adhesive tape; AFM sample disc", "instance metadata", "h2kg:Matter", "Sample, adhesive tape, and sample disc remain material instances with metadata."),
        ("Step 5 Technique", "Fix", "reuse existing term", "h2kg:Manufacturing", "Modeled as a labeled mounting process instance."),
        ("Step 5 Condition", "Disc size = 12 mm; Disc brand = Plano", "instance metadata", "h2kg:hasMetadata", "Retained as mounting metadata in round 1."),
        ("Step 5 Target", "Sample", "instance metadata", "h2kg:Matter", "Represents the final AFM sample material instance."),
    ]:
        add("sp", field, value, classification, anchor, note)

    for field, value, classification, anchor, note in [
        ("MeasurementMethod", "AFM", "reuse existing term", "h2kg:AtomicForceMicroscopyMeasurement", "Reuses the public AFM measurement anchor."),
        ("MeasurementType", "ex-situ", "instance metadata", "h2kg:hasMetadata", "Retained as measurement metadata in round 1."),
        ("Specimen", "homogeneous powder", "instance metadata", "h2kg:hasMetadata", "Retained as specimen metadata in round 1."),
        ("Temperature", "23", "reuse existing term", "h2kg:Temperature", "Modeled as a parameter-setting instance linked to the AFM measurement."),
        ("TemperatureUnit", "C", "reuse existing term", "h2kg:Temperature", "Unit captured through the quantity-value pattern on the temperature setting."),
        ("Humidity", "80", "reuse existing term", "h2kg:RelativeHumidity", "Modeled as a parameter-setting instance linked to the AFM measurement."),
        ("HumidityUnit", "%", "reuse existing term", "h2kg:RelativeHumidity", "Unit captured through the quantity-value pattern on the humidity setting."),
        ("Atmosphere", "air", "instance metadata", "h2kg:hasMetadata", "Retained as measurement metadata in round 1."),
        ("AtmosphereUnit", "-", "instance metadata", "h2kg:hasMetadata", "Retained as atmosphere metadata in round 1."),
        ("Pressure", "1", "instance metadata", "h2kg:hasMetadata", "Retained as measurement metadata in round 1."),
        ("PressureUnit", "atm", "instance metadata", "h2kg:hasMetadata", "Retained as measurement metadata in round 1."),
        ("Calibration", "adjusting lenses and apertures; adjusting the voltage", "instance metadata", "h2kg:hasMetadata", "Retained as acquisition metadata."),
    ]:
        add("char", field, value, classification, anchor, note)

    for field, value, classification, anchor, note in [
        ("Instrument", "Bruker multimode 8 AFM", "reuse existing term", "h2kg:AFMInstrument", "Represented as an AFM instrument instance."),
        ("Mode", "Conductive tapping", "instance metadata", "h2kg:hasMetadata", "Retained as instrument metadata in round 1."),
        ("Tip", "DLC SHR150, Nanosensors", "instance metadata", "h2kg:hasMetadata", "Retained as tip metadata in round 1."),
        ("NominalRadius", "1", "new ontology term", "h2kg:AFMTipNominalRadius", "Promoted as a reusable AFM acquisition parameter."),
        ("NominalRadiusUnit", "nm", "new ontology term", "h2kg:AFMTipNominalRadius", "Unit captured through the quantity-value pattern on the tip-radius setting."),
        ("Look-inAmplifier", "PF-TUNA module, Bruker", "instance metadata", "h2kg:hasMetadata", "Retained as supporting electronics metadata in round 1."),
        ("Sensitivity", "1", "instance metadata", "h2kg:hasMetadata", "Retained as metadata in round 1."),
        ("SensitivityUnit", "fA", "instance metadata", "h2kg:hasMetadata", "Retained as metadata in round 1."),
        ("MeasuringSize", "1", "reuse existing term", "h2kg:MicroscopyMeasuredArea", "Reused as the public AFM measured-area parameter."),
        ("MeasuringSizeUnit", "um2", "reuse existing term", "h2kg:MicroscopyMeasuredArea", "Unit captured through the quantity-value pattern on the measured-area setting."),
        ("ScanSpeed", "0.488", "new ontology term", "h2kg:AFMScanSpeed", "Promoted as a reusable AFM acquisition parameter."),
        ("ScanSpeedUnit", "Hz", "new ontology term", "h2kg:AFMScanSpeed", "Unit captured through the quantity-value pattern on the AFM scan-speed setting."),
        ("Resolution", "0.5", "instance metadata", "h2kg:hasMetadata", "Retained as metadata in round 1."),
        ("ResolutionUnit", "mm", "instance metadata", "h2kg:hasMetadata", "Retained as metadata in round 1."),
        ("Raw data", "electron images", "instance metadata", "h2kg:MicrostructureImageDataset", "Retained as descriptive dataset metadata exactly as reported in the worksheet."),
        ("DataAdquisitionRate", "1024", "instance metadata", "h2kg:hasMetadata", "Retained as metadata in round 1."),
        ("DataAdquisitionRateUnit", "px", "instance metadata", "h2kg:hasMetadata", "Retained as metadata in round 1."),
    ]:
        add("inst", field, value, classification, anchor, note)

    for field, value, classification, anchor, note in [
        ("Step 1 Precursor", "RawData", "instance metadata", "h2kg:MicrostructureImageDataset", "Mapped to the raw AFM image dataset instance."),
        ("Step 1 AmountPrecursor", "-", "instance metadata", "h2kg:hasMetadata", "No precursor amount value was reported."),
        ("Step 1 Technique", "Contrast adjustment", "reuse existing term", "h2kg:Process", "Modeled as a labeled preprocessing process instance."),
        ("Step 1 Condition", "Contrast factor = 1", "instance metadata", "h2kg:hasMetadata", "Stored as preprocessing metadata."),
        ("Step 1 Software", "-", "instance metadata", "h2kg:hasMetadata", "No preprocessing software was explicitly reported for this step."),
        ("Step 1 Target", "PPInt1", "instance metadata", "h2kg:MicrostructureImageDataset", "Represents the contrast-adjusted intermediate dataset."),
        ("Step 2 Precursor", "PPInt1", "instance metadata", "h2kg:MicrostructureImageDataset", "Uses the contrast-adjusted intermediate dataset as input."),
        ("Step 2 AmountPrecursor", "-", "instance metadata", "h2kg:hasMetadata", "No precursor amount value was reported."),
        ("Step 2 Technique", "Brightness adjustment", "reuse existing term", "h2kg:Process", "Modeled as a labeled preprocessing process instance."),
        ("Step 2 Condition", "Brightness factor = 1", "instance metadata", "h2kg:hasMetadata", "Stored as preprocessing metadata."),
        ("Step 2 Software", "-", "instance metadata", "h2kg:hasMetadata", "No preprocessing software was explicitly reported for this step."),
        ("Step 2 Target", "Post-processed image", "instance metadata", "h2kg:SurfaceTopographyDataset", "Mapped to the final processed AFM topography/image dataset."),
    ]:
        add("pre", field, value, classification, anchor, note)

    for field, value, classification, anchor, note in [
        ("Step 1 Precursor", "Post-processed image", "instance metadata", "h2kg:SurfaceTopographyDataset", "The analysis process consumes the processed AFM dataset."),
        ("Step 1 Technique", "Manual particle measurement", "reuse existing term", "h2kg:Process", "Modeled as a labeled analysis-process instance rather than a new TBox term."),
        ("Step 1 Condition", "-", "instance metadata", "h2kg:hasMetadata", "No extra analysis condition was reported."),
        ("Step 1 Software", "ImageJ", "reuse existing term", "h2kg:FijiImageJSoftware", "Reuses the existing software instrument term."),
        ("Step 1 Target", "Average size", "reuse existing term", "h2kg:MeanParticleSize", "Mapped to the broadened reusable MeanParticleSize property."),
        ("Step 1 AmountTarget", "110 um", "reuse existing term", "h2kg:DataPoint + h2kg:MeanParticleSize", "Represented as a datapoint with a quantity value for MeanParticleSize."),
    ]:
        add("anal", field, value, classification, anchor, note)

    return rows


def _afm_example_items() -> list[dict[str, Any]]:
    ex = AFM_EXAMPLE_NS

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

    items: list[dict[str, Any]] = [
        {
            "@id": iri("source-record"),
            "@type": [f"{H2KG}Metadata"],
            f"{DCTERMS}title": [lit("Quantitative in Situ Analysis of Ionomer Structure in Fuel Cell catalytic layer", language="en")],
            f"{DCTERMS}date": [lit("2023-10-11", datatype=f"{XSD}date")],
            f"{H2KG}hasIdentifier": [lit("5"), lit("Run derived DOI")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Topic: Fuel cell; device: PEMFC; component: MEA; subcomponent: Catalyst layer.", language="en"),
                lit("Granularity level: Microstructure.", language="en"),
            ],
        },
        {
            "@id": iri("publication-record"),
            "@type": [f"{H2KG}Metadata"],
            f"{DCTERMS}title": [lit("Quantitative in Situ Analysis of Ionomer Structure in Fuel Cell catalytic layer", language="en")],
            f"{DCTERMS}identifier": [lit("https://doi.org/10.3390/afm38383")],
            f"{DCTERMS}issued": [lit("2012-11-28", datatype=f"{XSD}date")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Journal: PCCP; volume: 8; issue: 78; pages: 789-987.", language="en"),
                lit("Publication-status flag from worksheet: 1.", language="en"),
            ],
        },
        {
            "@id": iri("institution-dlr"),
            "@type": [f"{PROV}Agent"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("DLR", language="en")],
        },
        {
            "@id": iri("funding-hip"),
            "@type": [f"{PROV}Agent"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("HIP", language="en")],
        },
        {
            "@id": iri("author-tobias-morawitz"),
            "@type": [f"{PROV}Agent"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Tobias Morawitz", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("author-tobias-morawitz-metadata"))],
        },
        {
            "@id": iri("author-tobias-morawitz-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("ORCID: 123-465-7777.", language="en"),
                lit("Email: tobi.mora@dlr.de.", language="en"),
            ],
        },
        {
            "@id": iri("author-andre-colliard-granero"),
            "@type": [f"{PROV}Agent"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Andre Colliard Granero", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("author-andre-colliard-granero-metadata"))],
        },
        {
            "@id": iri("author-andre-colliard-granero-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("ORCID: 321-321-3211.", language="en"),
                lit("Email: andyhuebsch@gmail.mx.", language="en"),
            ],
        },
        {
            "@id": iri("pdc-material"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Pd/C precursor material", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("pdc-material-metadata"))],
        },
        {
            "@id": iri("pdc-material-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Pd/C amount metadata: 5 wt%.", language="en"),
                lit("Manufacturer: SigmaAldrich; lot number: 205680; CAS number: 7440-05-3.", language="en"),
            ],
        },
        {
            "@id": iri("sieved-pdc-material"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Sieved Pd/C material", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("sieved-pdc-material-metadata"))],
        },
        {
            "@id": iri("sieved-pdc-material-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Sieve size: 75 um.", language="en")],
        },
        {
            "@id": iri("mea-assembly-material"),
            "@type": [f"{H2KG}Matter", f"{H2KG}MEAAssembly"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("MEA sample material for AFM preparation", language="en")],
        },
        {
            "@id": iri("cut-mea-sample"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Cut MEA sample", language="en")],
        },
        {
            "@id": iri("embedding-resin"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Embedding resin (Terosion Teromix PU6700)", language="en")],
        },
        {
            "@id": iri("embedded-sample"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Embedded AFM sample", language="en")],
        },
        {
            "@id": iri("cured-embedded-sample"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Cured embedded AFM sample", language="en")],
        },
        {
            "@id": iri("microtomed-sample"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Microtomed AFM sample", language="en")],
        },
        {
            "@id": iri("adhesive-tape"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Double sided adhesive tape", language="en")],
        },
        {
            "@id": iri("afm-sample-disc"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("AFM sample disc", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("afm-sample-disc-metadata"))],
        },
        {
            "@id": iri("afm-sample-disc-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Disc size: 12 mm; disc brand: Plano.", language="en")],
        },
        {
            "@id": iri("afm-sample"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("AFM pilot sample", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("afm-sample-metadata"))],
        },
        {
            "@id": iri("afm-sample-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Specimen metadata from sheet: homogeneous powder.", language="en"),
                lit("Sample context assembled through cutting, embedding, curing, microtome sectioning, and mounting on an AFM sample disc.", language="en"),
            ],
        },
        {
            "@id": iri("procure-pdc-step"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Procure Pd/C precursor", language="en")],
            f"{H2KG}hasOutputMaterial": [ref(iri("pdc-material"))],
        },
        {
            "@id": iri("sieving-step"),
            "@type": [f"{H2KG}Manufacturing"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Sieve Pd/C precursor", language="en")],
            f"{H2KG}hasInputMaterial": [ref(iri("pdc-material"))],
            f"{H2KG}hasOutputMaterial": [ref(iri("sieved-pdc-material"))],
        },
        {
            "@id": iri("drying-step"),
            "@type": [f"{H2KG}Manufacturing"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Dry catalyst material for AFM preparation", language="en")],
            f"{H2KG}hasInputMaterial": [ref(iri("sieved-pdc-material"))],
            f"{H2KG}hasOutputMaterial": [ref(iri("mea-assembly-material"))],
            f"{H2KG}hasParameter": [ref(iri("drying-temperature-setting")), ref(iri("drying-time-setting"))],
        },
        {
            "@id": iri("cut-step"),
            "@type": [f"{H2KG}Manufacturing"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Cut MEA sample", language="en")],
            f"{H2KG}hasInputMaterial": [ref(iri("mea-assembly-material"))],
            f"{H2KG}hasOutputMaterial": [ref(iri("cut-mea-sample"))],
            f"{H2KG}hasMetadata": [ref(iri("cut-step-metadata"))],
        },
        {
            "@id": iri("cut-step-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Cut size: 25 cm2.", language="en")],
        },
        {
            "@id": iri("embedding-step"),
            "@type": [f"{H2KG}Manufacturing"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Embed cut MEA sample", language="en")],
            f"{H2KG}hasInputMaterial": [ref(iri("cut-mea-sample")), ref(iri("embedding-resin"))],
            f"{H2KG}hasOutputMaterial": [ref(iri("embedded-sample"))],
        },
        {
            "@id": iri("curing-step"),
            "@type": [f"{H2KG}Manufacturing"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Cure embedded sample", language="en")],
            f"{H2KG}hasInputMaterial": [ref(iri("embedded-sample"))],
            f"{H2KG}hasOutputMaterial": [ref(iri("cured-embedded-sample"))],
            f"{H2KG}hasMetadata": [ref(iri("curing-step-metadata"))],
        },
        {
            "@id": iri("curing-step-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Curing metadata: temperature 25 deg C; time 24 h.", language="en")],
        },
        {
            "@id": iri("microtome-step"),
            "@type": [f"{H2KG}Manufacturing"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Microtome section the cured sample", language="en")],
            f"{H2KG}hasInputMaterial": [ref(iri("cured-embedded-sample"))],
            f"{H2KG}hasOutputMaterial": [ref(iri("microtomed-sample"))],
            f"{H2KG}hasMetadata": [ref(iri("microtome-step-metadata"))],
        },
        {
            "@id": iri("microtome-step-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Microtome: Leitz; thickness: 2 mm.", language="en")],
        },
        {
            "@id": iri("mounting-step"),
            "@type": [f"{H2KG}Manufacturing"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Fix sample on AFM sample disc", language="en")],
            f"{H2KG}hasInputMaterial": [ref(iri("microtomed-sample")), ref(iri("adhesive-tape")), ref(iri("afm-sample-disc"))],
            f"{H2KG}hasOutputMaterial": [ref(iri("afm-sample"))],
        },
        {
            "@id": iri("afm-measurement-001"),
            "@type": [f"{H2KG}Measurement", f"{H2KG}AtomicForceMicroscopyMeasurement"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("AFM pilot measurement", language="en")],
            f"{H2KG}hasInputMaterial": [ref(iri("afm-sample"))],
            f"{H2KG}usesInstrument": [ref(iri("afm-instrument-001"))],
            f"{H2KG}hasOutputData": [ref(iri("afm-raw-image-dataset"))],
            f"{H2KG}hasParameter": [
                ref(iri("temperature-setting")),
                ref(iri("relative-humidity-setting")),
                ref(iri("measured-area-setting")),
                ref(iri("afm-scan-speed-setting")),
                ref(iri("afm-tip-radius-setting")),
            ],
            f"{H2KG}hasMetadata": [
                ref(iri("afm-acquisition-metadata")),
                ref(iri("source-record")),
                ref(iri("publication-record")),
            ],
            f"{PROV}wasAssociatedWith": [
                ref(iri("author-tobias-morawitz")),
                ref(iri("author-andre-colliard-granero")),
                ref(iri("institution-dlr")),
                ref(iri("funding-hip")),
            ],
            f"{DCTERMS}source": [ref(iri("publication-record"))],
        },
        {
            "@id": iri("afm-instrument-001"),
            "@type": [f"{H2KG}Instrument", f"{H2KG}AFMInstrument"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("AFM instrument used in the pilot case", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("afm-instrument-metadata"))],
        },
        {
            "@id": iri("afm-instrument-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Instrument worksheet label: Bruker multimode 8 AFM; mode: Conductive tapping.", language="en"),
                lit("Tip metadata: DLC SHR150, Nanosensors; lock-in amplifier: PF-TUNA module, Bruker.", language="en"),
                lit("Sensitivity: 1 fA; resolution: 0.5 mm; data acquisition rate: 1024 px.", language="en"),
            ],
        },
        {
            "@id": iri("afm-raw-image-dataset"),
            "@type": [f"{H2KG}Data", f"{H2KG}MicrostructureImageDataset"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("AFM raw image dataset", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("afm-raw-image-metadata"))],
        },
        {
            "@id": iri("afm-raw-image-metadata"),
            "@type": [f"{H2KG}Metadata"],
            f"{DCTERMS}format": [lit("tiff")],
            f"{DCTERMS}extent": [lit("258 MB"), lit("256 x 256 x 0 pixels")],
            f"{DCTERMS}source": [lit("link")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Filename: afm_rawdata.tif.", language="en"),
                lit("PixelPerMetric: 8.1.", language="en"),
                lit("Worksheet raw-data descriptor: electron images.", language="en"),
            ],
        },
        {
            "@id": iri("contrast-adjustment-step"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Contrast adjustment", language="en")],
            f"{H2KG}hasInputData": [ref(iri("afm-raw-image-dataset"))],
            f"{H2KG}hasOutputData": [ref(iri("afm-contrast-adjusted-dataset"))],
            f"{H2KG}hasMetadata": [ref(iri("contrast-adjustment-metadata"))],
        },
        {
            "@id": iri("contrast-adjustment-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Contrast factor: 1.", language="en")],
        },
        {
            "@id": iri("afm-contrast-adjusted-dataset"),
            "@type": [f"{H2KG}Data", f"{H2KG}MicrostructureImageDataset"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("AFM contrast-adjusted image dataset", language="en")],
        },
        {
            "@id": iri("brightness-adjustment-step"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Brightness adjustment", language="en")],
            f"{H2KG}hasInputData": [ref(iri("afm-contrast-adjusted-dataset"))],
            f"{H2KG}hasOutputData": [ref(iri("afm-processed-topography-dataset"))],
            f"{H2KG}hasMetadata": [ref(iri("brightness-adjustment-metadata"))],
        },
        {
            "@id": iri("brightness-adjustment-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Brightness factor: 1.", language="en")],
        },
        {
            "@id": iri("afm-processed-topography-dataset"),
            "@type": [f"{H2KG}Data", f"{H2KG}SurfaceTopographyDataset", f"{H2KG}MicrostructureImageDataset"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("AFM processed topography dataset", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("afm-processed-topography-metadata"))],
        },
        {
            "@id": iri("afm-processed-topography-metadata"),
            "@type": [f"{H2KG}Metadata"],
            f"{DCTERMS}source": [lit("link")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Mask present: yes.", language="en"),
                lit("Mask link: link.", language="en"),
                lit("Target label from worksheet: Post-processed image.", language="en"),
            ],
        },
        {
            "@id": iri("manual-particle-measurement-step"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Manual particle measurement", language="en")],
            f"{H2KG}hasInputData": [ref(iri("afm-processed-topography-dataset"))],
            f"{H2KG}hasOutputData": [ref(iri("afm-analysis-summary-dataset"))],
            f"{H2KG}usesInstrument": [ref(f"{H2KG}FijiImageJSoftware")],
        },
        {
            "@id": iri("afm-analysis-summary-dataset"),
            "@type": [f"{H2KG}Data"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("AFM analysis summary dataset", language="en")],
            f"{H2KG}hasPart": [ref(iri("mean-particle-size-datapoint"))],
        },
        {
            "@id": iri("mean-particle-size-datapoint"),
            "@type": [f"{H2KG}DataPoint"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("AFM-derived mean particle size datapoint", language="en")],
            f"{H2KG}ofProperty": [ref(f"{H2KG}MeanParticleSize")],
            f"{H2KG}fromMeasurement": [ref(iri("afm-measurement-001"))],
            f"{H2KG}hasQuantityValue": [ref(iri("mean-particle-size-datapoint-qv"))],
            f"{PROV}wasGeneratedBy": [ref(iri("manual-particle-measurement-step"))],
            f"{H2KG}hasMetadata": [ref(iri("mean-particle-size-datapoint-metadata"))],
            f"{DCTERMS}source": [ref(iri("publication-record"))],
        },
        {
            "@id": iri("mean-particle-size-datapoint-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Worksheet target label: Average size.", language="en")],
        },
        {
            "@id": iri("drying-temperature-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}DryingTemperature"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Drying temperature setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("drying-temperature-setting-qv"))],
        },
        {
            "@id": iri("drying-time-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}DryingTime"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Drying time setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("drying-time-setting-qv"))],
        },
        {
            "@id": iri("temperature-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}Temperature"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("AFM acquisition temperature setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("temperature-setting-qv"))],
        },
        {
            "@id": iri("relative-humidity-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}RelativeHumidity"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("AFM acquisition relative-humidity setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("relative-humidity-setting-qv"))],
        },
        {
            "@id": iri("measured-area-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}MicroscopyMeasuredArea"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("AFM measured-area setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("measured-area-setting-qv"))],
        },
        {
            "@id": iri("afm-scan-speed-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}AFMScanSpeed"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("AFM scan-speed setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("afm-scan-speed-setting-qv"))],
        },
        {
            "@id": iri("afm-tip-radius-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}AFMTipNominalRadius"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("AFM tip nominal-radius setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("afm-tip-radius-setting-qv"))],
        },
        qv("drying-temperature-setting-qv", "100", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/ThermodynamicTemperature", f"{UNIT}DEG_C"),
        qv("drying-time-setting-qv", "10", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/Time", f"{UNIT}HR"),
        qv("temperature-setting-qv", "23", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/ThermodynamicTemperature", f"{UNIT}DEG_C"),
        qv("relative-humidity-setting-qv", "80", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/RelativeHumidity", f"{UNIT}PERCENT"),
        qv("measured-area-setting-qv", "1", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/Area", f"{UNIT}MicroM2"),
        qv("afm-scan-speed-setting-qv", "0.488", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/Frequency", f"{UNIT}HZ"),
        qv("afm-tip-radius-setting-qv", "1", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/Length", f"{UNIT}NanoM"),
        qv("mean-particle-size-datapoint-qv", "110", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/Length", f"{UNIT}MicroM"),
        {
            "@id": iri("afm-acquisition-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Measurement type: ex-situ; specimen: homogeneous powder; atmosphere: air.", language="en"),
                lit("Pressure metadata: 1 atm; calibration notes: adjusting lenses and apertures / adjusting the voltage.", language="en"),
            ],
        },
    ]
    return items


def _afm_validation_note() -> str:
    return """# AFM Validation Note

## Ontology changes introduced in the AFM round

- Reused and broadened the existing public AFM vocabulary rather than introducing a parallel AFM measurement node.
- `h2kg:AtomicForceMicroscopyMeasurement` now supports a wider AFM neighborhood for ex-situ catalyst-layer and MEA microstructure/topography characterization while preserving the prior in-situ AFM use.
- `h2kg:AFMInstrument` was kept as the public AFM instrument anchor and generalized textually for broader AFM usage.
- New public AFM parameters introduced in this round:
  - `h2kg:AFMScanSpeed`
  - `h2kg:AFMTipNominalRadius`
- `h2kg:MeanParticleSize` was broadened so it can support both legacy particle-sizing contexts and AFM-derived size results.

## What remained instance metadata in round 1

- Organizational, bibliographic, file, and access details from the `org` section.
- `MeasurementType`, `Specimen`, `Atmosphere`, `Pressure`, and `Calibration` from the `char` section.
- AFM mode, tip model, lock-in amplifier, sensitivity, resolution, and data-acquisition-rate fields from the `inst` section.
- Supplier, lot-number, CAS, mounting-disc, resin, and sectioning details from the preparation sections.

## What was intentionally deferred

- No public TBox terms were introduced for `Buy`, `Sieve`, `Dry`, `Cut`, `Embedded`, `Curated`, `Microtome cut`, `Fix`, `Contrast adjustment`, `Brightness adjustment`, or `Manual particle measurement`; these remain labeled process instances.
- No dedicated AFM metadata sub-vocabulary was introduced for mode, tip, amplifier, sensitivity, or calibration fields in this first AFM round.
- The worksheet value `Raw data = electron images` is preserved only as metadata because it is a sheet descriptor rather than a reusable ontology node.
"""


def _afm_case_summary() -> str:
    return """# AFM Case Summary

The AFM pilot demonstrates how H2KG can represent an atomic-force-microscopy workflow for PEMFC catalyst-layer and MEA-related characterization without duplicating the public AFM measurement vocabulary. The acquisition is represented as an `AtomicForceMicroscopyMeasurement` linked to an `AFMInstrument`, explicit acquisition-parameter settings such as temperature, relative humidity, measured area, AFM scan speed, and AFM tip nominal radius, and a raw `MicrostructureImageDataset`.

Two preprocessing steps, contrast adjustment and brightness adjustment, transform the raw AFM dataset into a processed dataset typed as both `SurfaceTopographyDataset` and `MicrostructureImageDataset`. An analysis step uses `FijiImageJSoftware` to derive the scientific result as a `DataPoint` for `MeanParticleSize`, linked back to the AFM measurement through `fromMeasurement` and to the analysis process through `prov:wasGeneratedBy`.

The pilot remains conservative about ontology growth: worksheet-specific operational labels stay at instance level, while the public AFM node exposed in Explore is strengthened through reusable TBox links to instrument, parameters, datasets, and the measured-property anchor.
"""


def _afm_follow_on_gaps() -> str:
    return """# AFM Follow-On Gaps

- Revisit whether AFM mode families, tip families, and AFM-sensitivity descriptors recur strongly enough across later AFM-like methods to justify promotion from metadata to reusable H2KG terms.
- Compare AFM with TEM, SEM, FIB-SEM, and IC-SEM to decide whether a shared imaging-acquisition metadata profile should be introduced.
- Revisit whether embedding, sectioning, and sample-mounting preparation steps should remain labeled process instances or become reusable preparation vocabulary terms after cross-method comparison.
- Review whether `CantileverSpringConstant` and `CantileverResonanceFrequency` need example-level value patterns in a later AFM round even when the current worksheet does not report values for them.
"""


def _afm_manuscript_figure() -> str:
    return """# AFM Manuscript Figure Guidance

Use a combined ontology-workflow figure with **TBox-only standalone nodes** and worksheet-derived values shown only as annotations or metadata callouts.

Recommended backbone:

`Matter -> Manufacturing -> Atomic Force Microscopy Measurement -> Microstructure Image Dataset -> Process (contrast / brightness adjustment) -> Surface Topography Dataset -> Process (analysis) -> DataPoint -> Mean Particle Size`

Supporting families:

- Above acquisition:
  - `Temperature`
  - `Relative Humidity`
  - `Microscopy Measured Area`
  - `AFM Scan Speed`
  - `AFM Tip Nominal Radius`
  - `Cantilever Spring Constant`
  - `Cantilever Resonance Frequency`
- Below acquisition:
  - `AFM Instrument`
- Below analysis:
  - `Fiji ImageJ Software`
- Metadata callouts:
  - sample context
  - AFM mode/tip metadata
  - raw/processed dataset metadata
  - publication/provenance metadata

Important rule:

- Every standalone node in the figure must be retrievable from the public H2KG TBox and therefore visible in Explore after regeneration.
- Worksheet values such as `Bruker multimode 8 AFM`, `Conductive tapping`, `DLC SHR150`, `PF-TUNA module`, DOI, and file dimensions remain annotations or metadata-callout text, not standalone ontology nodes.
"""


def _afm_manuscript_table() -> str:
    return """# AFM Manuscript Companion Table

| AFM case element | H2KG ontology anchor | Example case value | Figure treatment |
| --- | --- | --- | --- |
| Sample context | `h2kg:Matter` / `h2kg:MEAAssembly` | PEMFC MEA / catalyst-layer context | standalone ontology node |
| Drying route | `h2kg:Manufacturing` + `h2kg:DryingTemperature` + `h2kg:DryingTime` | 100 deg C; 10 h | ontology node + parameter callout |
| Mounting/sectioning route | `h2kg:Manufacturing` | cut, embed, cure, microtome, fix | standalone ontology node with annotation |
| AFM acquisition | `h2kg:AtomicForceMicroscopyMeasurement` | AFM | standalone ontology node |
| AFM instrument | `h2kg:AFMInstrument` | Bruker multimode 8 AFM | standalone ontology node with metadata callout |
| AFM acquisition area | `h2kg:MicroscopyMeasuredArea` | 1 um2 | parameter callout |
| AFM scan speed | `h2kg:AFMScanSpeed` | 0.488 Hz | parameter callout |
| AFM tip radius | `h2kg:AFMTipNominalRadius` | 1 nm | parameter callout |
| AFM environment | `h2kg:Temperature`, `h2kg:RelativeHumidity` | 23 deg C; 80 % | parameter callout |
| Raw image data | `h2kg:MicrostructureImageDataset` | afm_rawdata.tif | standalone ontology node |
| Preprocessing | `h2kg:Process` | contrast adjustment; brightness adjustment | standalone ontology node with annotation |
| Processed topography/image data | `h2kg:SurfaceTopographyDataset`, `h2kg:MicrostructureImageDataset` | post-processed image | standalone ontology node |
| Analysis | `h2kg:Process` | manual particle measurement | standalone ontology node with annotation |
| Analysis software | `h2kg:FijiImageJSoftware` | ImageJ | supporting ontology node |
| Final result | `h2kg:MeanParticleSize` | 110 um | final property node via datapoint |
| Provenance | `h2kg:Metadata` + `h2kg:hasMetadata` | DOI, authors, file details | metadata callout |
"""


def _afm_readme(generated_files: list[Path]) -> str:
    files = "\n".join(f"- `{path.name}`" for path in generated_files)
    return f"""# AFM Pilot Package

Generated AFM companion artifacts for the controlled AFM imaging-method integration round.

## Files

{files}

This pilot keeps the ontology disciplined: the public AFM vocabulary was generalized where Explore needed real TBox links, while worksheet-specific details remain attached as metadata or labeled process instances.
"""


def _missing_terms_note(missing: list[str]) -> str:
    bullets = "\n".join(f"- `{term}`" for term in missing)
    return f"""# AFM Pilot Package

The AFM pilot package was not generated because the current ontology source is missing required local terms.

Missing terms:

{bullets}
"""
