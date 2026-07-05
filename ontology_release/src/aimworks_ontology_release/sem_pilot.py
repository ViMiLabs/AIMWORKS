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
SEM_EXAMPLE_NS = "https://w3id.org/h2kg/examples/sem#"

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
    f"{H2KG}AcceleratingVoltage",
    f"{H2KG}Magnification",
    f"{H2KG}WorkingDistance",
    f"{H2KG}Temperature",
    f"{H2KG}RelativeHumidity",
    f"{H2KG}DryingTemperature",
    f"{H2KG}DryingTime",
    f"{H2KG}SputterCoating",
    f"{H2KG}SEMInstrument",
    f"{H2KG}FijiImageJSoftware",
    f"{H2KG}ScanningElectronMicroscopyImaging",
    f"{H2KG}SEMImageDataset",
    f"{H2KG}SEMMicrographDataset",
    f"{H2KG}MicrostructureImageDataset",
    f"{H2KG}CatalystParticleDiameter",
}


def build_sem_pilot_package(
    input_path: str | Path,
    output_root: str | Path,
) -> dict[str, Any]:
    input_path = Path(input_path)
    output_root = Path(output_root)
    target_dir = ensure_dir(output_root / "examples" / "sem_pilot")
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

    mapping_rows = _sem_mapping_rows()
    example_items = _sem_example_items()
    generated_files = [
        _write_mapping_matrix(target_dir / "sem_mapping_matrix.csv", mapping_rows),
        _write_mapping_matrix_markdown(target_dir / "sem_mapping_matrix.md", mapping_rows),
        dump_json(
            target_dir / "sem_pilot_example.jsonld",
            {"@context": {**COMMON_CONTEXT, "sem": SEM_EXAMPLE_NS}, "@graph": example_items},
        ),
        dump_turtle_items(target_dir / "sem_pilot_example.ttl", example_items),
        write_text(target_dir / "sem_validation_note.md", _sem_validation_note()),
        write_text(target_dir / "sem_case_summary.md", _sem_case_summary()),
        write_text(target_dir / "sem_follow_on_gaps.md", _sem_follow_on_gaps()),
    ]
    write_text(target_dir / "README.md", _sem_readme(generated_files))
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
        "# SEM Mapping Matrix",
        "",
        "This matrix accounts for the SEM pilot fields and classifies them as `reuse existing term`, `instance metadata`, or `not modeled` for the current round.",
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


def _sem_mapping_rows() -> list[dict[str, str]]:
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

    org_fields = [
        ("ExperimentTitle", "Elucidating the Influence of the d-Band Center on the Synthesis of Isobutanol", "instance metadata", "h2kg:hasMetadata + dcterms:title", "Stored on the SEM source-record metadata node."),
        ("ExperimentID", "1", "instance metadata", "h2kg:hasMetadata + h2kg:hasIdentifier", "Stored as a literal identifier on the source record."),
        ("Measurement-ID", "Run derived DOI", "instance metadata", "h2kg:hasMetadata + h2kg:hasIdentifier", "Stored on measurement metadata."),
        ("UploadDate", "2022-10-11", "instance metadata", "h2kg:hasMetadata + dcterms:date", "Excel serial normalized to ISO date."),
        ("MeasurementDate", "", "not modeled", "-", "No value was present."),
        ("Institution", "FZJ IEK-14", "instance metadata", "prov:Agent", "Represented as an institutional agent."),
        ("FoundingBody", "HIP", "instance metadata", "prov:Agent", "Represented as a funding-body agent."),
        ("Country", "Germany", "instance metadata", "h2kg:hasMetadata", "Retained as contextual metadata."),
        ("Author", "Joachim Pasel", "instance metadata", "prov:Agent", "Represented as an author agent instance."),
        ("ORCID", "123-465-4789", "instance metadata", "h2kg:hasMetadata", "Stored on author metadata."),
        ("Email", "andyhuebsch@gmail.mx", "instance metadata", "h2kg:hasMetadata", "Stored on author metadata."),
        ("Published", "1", "instance metadata", "h2kg:hasMetadata", "Retained as publication-status metadata."),
        ("Publication", "Interseting study about myself", "instance metadata", "h2kg:hasMetadata + dcterms:title", "Stored on a publication metadata node."),
        ("DOI", "https://doi.org/10.3390/catal11030406", "instance metadata", "h2kg:hasMetadata + dcterms:identifier", "Stored as publication metadata."),
        ("Journal", "RSC Nanoscale", "instance metadata", "h2kg:hasMetadata", "Retained as bibliographic metadata."),
        ("Volume", "1", "instance metadata", "h2kg:hasMetadata", "Retained as bibliographic metadata."),
        ("Issue", "25", "instance metadata", "h2kg:hasMetadata", "Retained as bibliographic metadata."),
        ("Pages", "456-654", "instance metadata", "h2kg:hasMetadata", "Retained as bibliographic metadata."),
        ("PublicationDate", "2012-11-12", "instance metadata", "h2kg:hasMetadata + dcterms:issued", "Excel serial normalized to ISO date."),
        ("Topic", "Catalysis", "instance metadata", "h2kg:hasMetadata", "Retained as topical metadata."),
        ("Device", "-", "not modeled", "-", "No device value was supplied."),
        ("Component", "-", "not modeled", "-", "No component value was supplied."),
        ("Subcomponent", "Catalyst", "instance metadata", "h2kg:hasMetadata", "Retained as subcomponent metadata."),
        ("Granularity Level", "Nanostructure", "instance metadata", "h2kg:hasMetadata", "Retained as scale metadata."),
        ("Format", "tiff", "instance metadata", "h2kg:hasMetadata + dcterms:format", "Stored on dataset metadata."),
        ("FileSize", "1", "instance metadata", "h2kg:hasMetadata + dcterms:extent", "Stored with file-size unit in dataset metadata."),
        ("FileSizeUnit", "MB", "instance metadata", "h2kg:hasMetadata + dcterms:extent", "Stored with file size in dataset metadata."),
        ("FileName", "Test.tif", "instance metadata", "h2kg:hasMetadata", "Stored on raw dataset metadata."),
        ("DimensionX", "1024", "instance metadata", "h2kg:hasMetadata", "Stored on raw dataset metadata."),
        ("DimensionY", "1024", "instance metadata", "h2kg:hasMetadata", "Stored on raw dataset metadata."),
        ("DimensionZ", "600", "instance metadata", "h2kg:hasMetadata", "Stored on raw dataset metadata."),
        ("PixelPerMetric", "8.1", "instance metadata", "h2kg:hasMetadata", "Stored on raw dataset metadata."),
        ("Link", "link", "instance metadata", "h2kg:hasMetadata + dcterms:source", "Stored as source/link metadata."),
        ("MaskExist", "yes", "instance metadata", "h2kg:hasMetadata", "Stored on processed-dataset metadata."),
        ("MaskLink", "link", "instance metadata", "h2kg:hasMetadata + dcterms:source", "Stored on processed-dataset metadata."),
    ]
    for field, value, classification, anchor, note in org_fields:
        add("org", field, value, classification, anchor, note)

    syn_fields = [
        ("Step 1 Precursor", "Pd/C", "instance metadata", "h2kg:Matter", "Represented as a material instance with supplier, lot-number, and CAS metadata."),
        ("Step 1 AmountPrecursor", "5 wt%", "instance metadata", "h2kg:hasMetadata", "Stored as material metadata on the Pd/C precursor."),
        ("Step 1 Technique", "Buy", "reuse existing term", "h2kg:Process", "Modeled as a labeled process instance rather than a new TBox term."),
        ("Step 1 Condition", "Manufacturer = SigmaAldrich; Loot number = 205680; CAS-number = 7440-05-3", "instance metadata", "h2kg:hasMetadata", "Stored as procurement metadata on the Pd/C precursor."),
        ("Step 1 Target", "SInt1", "instance metadata", "h2kg:Matter", "Represented as the procured Pd/C material instance."),
        ("Step 2 Precursor", "SInt1", "instance metadata", "h2kg:Matter", "Uses the procured Pd/C material instance as input."),
        ("Step 2 Technique", "Sieve", "reuse existing term", "h2kg:Manufacturing", "Modeled as a labeled manufacturing instance rather than a new TBox term."),
        ("Step 2 Condition", "sieve size = 75 um", "instance metadata", "h2kg:hasMetadata", "Retained as sieving metadata in round 1."),
        ("Step 2 Target", "SInt2", "instance metadata", "h2kg:Matter", "Represents the sieved catalyst material."),
        ("Step 3 Precursor", "SInt2", "instance metadata", "h2kg:Matter", "Uses the sieved catalyst material as input."),
        ("Step 3 Technique", "Dry", "reuse existing term", "h2kg:Manufacturing", "Modeled as a labeled manufacturing instance with drying parameters."),
        ("Step 3 Condition", "Temperature = 100 °C / Time = 10 h", "reuse existing term", "h2kg:DryingTemperature + h2kg:DryingTime", "Modeled through parameter-setting instances linked to the drying step."),
        ("Step 3 Target", "MEA", "instance metadata", "h2kg:Matter", "Represents the dried catalyst material used for SEM sample preparation."),
    ]
    for field, value, classification, anchor, note in syn_fields:
        add("syn", field, value, classification, anchor, note)

    sp_fields = [
        ("Step 1 Inputs", "MEA + Sampleholder (Plano GmbH) + Tape (Plano GmbH)", "instance metadata", "h2kg:hasInputMaterial", "Connected as material-input instances to the mounting step."),
        ("Step 1 Technique", "Fix", "reuse existing term", "h2kg:Manufacturing", "Modeled as a labeled manufacturing instance rather than a new TBox term."),
        ("Step 1 Target", "SPInt1", "instance metadata", "h2kg:Matter", "Represents the mounted SEM intermediate sample."),
        ("Step 2 Inputs", "SPInt1 + Au", "instance metadata", "h2kg:hasInputMaterial", "Connected as material-input instances to the conductive-coating step."),
        ("Step 2 Technique", "Deposition", "reuse existing term", "h2kg:SputterCoating", "Mapped conservatively to the existing SputterCoating term."),
        ("Step 2 Target", "Sample", "instance metadata", "h2kg:Matter", "Represents the final SEM sample material instance."),
    ]
    for field, value, classification, anchor, note in sp_fields:
        add("sp", field, value, classification, anchor, note)

    char_fields = [
        ("MeasurementMethod", "SEM", "reuse existing term", "h2kg:ScanningElectronMicroscopyImaging", "Defines the pilot measurement instance type."),
        ("MeasurementType", "ex-situ", "instance metadata", "h2kg:hasMetadata", "Retained as measurement-context metadata in round 1."),
        ("Specimen", "homogeneous powder", "instance metadata", "h2kg:hasMetadata", "Retained as specimen-context metadata in round 1."),
        ("Characterization environment", "", "not modeled", "-", "No value was present."),
        ("Temperature", "23 C", "reuse existing term", "h2kg:Temperature", "Modeled as a parameter-setting instance linked to the SEM measurement."),
        ("Humidity", "50 %", "reuse existing term", "h2kg:RelativeHumidity", "Modeled as a parameter-setting instance linked to the SEM measurement."),
        ("Atmosphere", "air", "instance metadata", "h2kg:hasMetadata", "Retained as measurement metadata."),
        ("Pressure", "1 atm", "instance metadata", "h2kg:hasMetadata", "Stored as measurement metadata because a generic pressure term is not promoted in this round."),
        ("Calibration", "adjusting lenses and apertures / adjusting the voltage", "instance metadata", "h2kg:hasMetadata", "Retained as calibration metadata."),
    ]
    for field, value, classification, anchor, note in char_fields:
        add("char", field, value, classification, anchor, note)

    inst_fields = [
        ("Instrument", "Electron Microscope", "reuse existing term", "h2kg:SEMInstrument", "Represented as a SEM instrument instance."),
        ("MicroscopeBrand", "Zeiss Gemini Ultra plus", "instance metadata", "h2kg:hasMetadata", "Stored as instrument metadata."),
        ("AccelerationVoltage", "20 kV", "reuse existing term", "h2kg:AcceleratingVoltage", "Modeled as a parameter-setting instance linked to the SEM measurement."),
        ("Magnification", "250", "reuse existing term", "h2kg:Magnification", "Modeled as a parameter-setting instance linked to the SEM measurement."),
        ("Cathode", "LaB6", "instance metadata", "h2kg:hasMetadata", "Stored as instrument metadata."),
        ("WorkingDistance", "8.5 mm", "reuse existing term", "h2kg:WorkingDistance", "Modeled as a parameter-setting instance linked to the SEM measurement."),
        ("Probe", "Electron beam", "instance metadata", "h2kg:hasMetadata", "Stored as instrument metadata."),
        ("Detector", "InLens", "instance metadata", "h2kg:hasMetadata", "Stored as instrument metadata."),
        ("ImagingTechnique", "Brightfield", "instance metadata", "h2kg:hasMetadata", "Stored as instrument metadata in round 1."),
        ("Signal", "Secondary electrons", "instance metadata", "h2kg:hasMetadata", "Stored as instrument metadata in round 1."),
        ("TimeLapse", "30 s", "instance metadata", "h2kg:hasMetadata", "Retained as acquisition metadata in round 1."),
        ("RawData", "electron images", "instance metadata", "h2kg:SEMImageDataset", "Retained as descriptive metadata on the raw SEM dataset."),
        ("DataAdquisitionRate", "-", "not modeled", "-", "No usable value was present."),
    ]
    for field, value, classification, anchor, note in inst_fields:
        add("inst", field, value, classification, anchor, note)

    pre_fields = [
        ("Step 1 Precursor", "RawData", "instance metadata", "h2kg:SEMImageDataset", "Mapped to the raw SEM image dataset instance."),
        ("Step 1 Technique", "Contrast adjustment", "reuse existing term", "h2kg:Process", "Modeled as a labeled process instance rather than a new TBox term."),
        ("Step 1 Condition", "Contrast factor = 1", "instance metadata", "h2kg:hasMetadata", "Stored as preprocessing metadata."),
        ("Step 1 Target", "PPInt1", "instance metadata", "h2kg:SEMImageDataset", "Mapped to the contrast-adjusted SEM image dataset instance."),
        ("Step 2 Precursor", "PPInt1", "instance metadata", "h2kg:SEMImageDataset", "Uses the contrast-adjusted SEM image dataset as input."),
        ("Step 2 Technique", "Brightness adjustment", "reuse existing term", "h2kg:Process", "Modeled as a labeled process instance rather than a new TBox term."),
        ("Step 2 Condition", "Brightness factor = 1", "instance metadata", "h2kg:hasMetadata", "Stored as preprocessing metadata."),
        ("Step 2 Target", "Post-processed image", "instance metadata", "h2kg:SEMMicrographDataset", "Mapped to the final processed SEM image dataset."),
    ]
    for field, value, classification, anchor, note in pre_fields:
        add("pre", field, value, classification, anchor, note)

    anal_fields = [
        ("Step 1 Precursor", "Post-processed image", "instance metadata", "h2kg:SEMMicrographDataset", "The analysis process consumes the processed SEM image dataset."),
        ("Step 1 Technique", "Manual particle measurement", "reuse existing term", "h2kg:Process", "Modeled as a labeled analysis-process instance rather than a new TBox term."),
        ("Step 1 Software", "ImageJ", "reuse existing term", "h2kg:FijiImageJSoftware", "The analysis process reuses the existing software instrument term."),
        ("Step 1 Target", "Average size", "reuse existing term", "h2kg:CatalystParticleDiameter", "Mapped conservatively to the existing CatalystParticleDiameter property."),
        ("Step 1 AmountTarget", "", "not modeled", "h2kg:DataPoint", "A semantic result data point is created, but the worksheet does not provide a numeric value."),
    ]
    for field, value, classification, anchor, note in anal_fields:
        add("anal", field, value, classification, anchor, note)

    return rows


def _sem_example_items() -> list[dict[str, Any]]:
    ex = SEM_EXAMPLE_NS

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

    def qv(local: str, value: str, datatype: str, unit: str, quantity_kind: str) -> dict[str, Any]:
        return {
            "@id": iri(local),
            "@type": [f"{QUDT}QuantityValue"],
            f"{QUDT}numericValue": [lit(value, datatype=datatype)],
            f"{QUDT}unit": [ref(unit)],
            f"{QUDT}quantityKind": [ref(quantity_kind)],
        }

    items: list[dict[str, Any]] = [
        {
            "@id": iri("source-record"),
            "@type": [f"{H2KG}Metadata"],
            f"{DCTERMS}title": [lit("Elucidating the Influence of the d-Band Center on the Synthesis of Isobutanol", language="en")],
            f"{DCTERMS}date": [lit("2022-10-11", datatype=f"{XSD}date")],
            f"{H2KG}hasIdentifier": [lit("1"), lit("Run derived DOI")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Topic: Catalysis; subcomponent: Catalyst; granularity level: Nanostructure.", language="en"),
                lit("Country: Germany; publication status: 1.", language="en"),
            ],
        },
        {
            "@id": iri("publication-record"),
            "@type": [f"{H2KG}Metadata"],
            f"{DCTERMS}title": [lit("Interseting study about myself", language="en")],
            f"{DCTERMS}identifier": [lit("https://doi.org/10.3390/catal11030406")],
            f"{DCTERMS}issued": [lit("2012-11-12", datatype=f"{XSD}date")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Journal: RSC Nanoscale; volume 1; issue 25; pages 456-654.", language="en"),
            ],
        },
        {
            "@id": iri("institution-fzj-iek14"),
            "@type": [f"{PROV}Agent"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("FZJ IEK-14", language="en")],
        },
        {
            "@id": iri("funding-hip"),
            "@type": [f"{PROV}Agent"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("HIP", language="en")],
        },
        {
            "@id": iri("author-joachim-pasel"),
            "@type": [f"{PROV}Agent"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Joachim Pasel", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("author-joachim-pasel-metadata"))],
        },
        {
            "@id": iri("author-joachim-pasel-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("ORCID: 123-465-4789.", language="en"),
                lit("Email: andyhuebsch@gmail.mx.", language="en"),
            ],
        },
        {
            "@id": iri("pdc-material"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Pd/C precursor", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("pdc-material-metadata"))],
        },
        {
            "@id": iri("pdc-material-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Amount: 5 wt%.", language="en"),
                lit("Manufacturer: SigmaAldrich; lot number: 205680; CAS-number: 7440-05-3.", language="en"),
            ],
        },
        {
            "@id": iri("sieved-pdc-material"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Sieved Pd/C catalyst material", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("sieved-pdc-material-metadata"))],
        },
        {
            "@id": iri("sieved-pdc-material-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Sieve size: 75 um.", language="en")],
        },
        {
            "@id": iri("dried-catalyst-material"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Dried catalyst material for SEM sample preparation", language="en")],
        },
        {
            "@id": iri("sample-holder"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Sample holder (Plano GmbH)", language="en")],
        },
        {
            "@id": iri("mounting-tape"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Tape (Plano GmbH)", language="en")],
        },
        {
            "@id": iri("gold-coating-material"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Au coating material", language="en")],
        },
        {
            "@id": iri("mounted-sem-intermediate"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Mounted SEM sample intermediate", language="en")],
        },
        {
            "@id": iri("sem-sample"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("SEM pilot sample", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("sem-sample-metadata"))],
        },
        {
            "@id": iri("sem-sample-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Specimen metadata from sheet: homogeneous powder.", language="en"),
                lit("Sample context assembled through fixing and Au deposition steps.", language="en"),
            ],
        },
        {
            "@id": iri("procure-pdc"),
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
            f"{H2KG}hasMetadata": [ref(iri("sieving-step-metadata"))],
        },
        {
            "@id": iri("sieving-step-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Technique label from source: Sieve; sieve size = 75 um.", language="en")],
        },
        {
            "@id": iri("drying-step"),
            "@type": [f"{H2KG}Manufacturing"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Dry catalyst material", language="en")],
            f"{H2KG}hasInputMaterial": [ref(iri("sieved-pdc-material"))],
            f"{H2KG}hasOutputMaterial": [ref(iri("dried-catalyst-material"))],
            f"{H2KG}hasParameter": [ref(iri("drying-temperature-setting")), ref(iri("drying-time-setting"))],
        },
        {
            "@id": iri("mounting-step"),
            "@type": [f"{H2KG}Manufacturing"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Fix sample on holder and tape", language="en")],
            f"{H2KG}hasInputMaterial": [ref(iri("dried-catalyst-material")), ref(iri("sample-holder")), ref(iri("mounting-tape"))],
            f"{H2KG}hasOutputMaterial": [ref(iri("mounted-sem-intermediate"))],
        },
        {
            "@id": iri("gold-deposition-step"),
            "@type": [f"{H2KG}Manufacturing", f"{H2KG}SputterCoating"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Au conductive coating deposition", language="en")],
            f"{H2KG}hasInputMaterial": [ref(iri("mounted-sem-intermediate")), ref(iri("gold-coating-material"))],
            f"{H2KG}hasOutputMaterial": [ref(iri("sem-sample"))],
        },
        {
            "@id": iri("sem-measurement-001"),
            "@type": [f"{H2KG}Measurement", f"{H2KG}ScanningElectronMicroscopyImaging"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("SEM pilot measurement", language="en")],
            f"{H2KG}hasInputMaterial": [ref(iri("sem-sample"))],
            f"{H2KG}usesInstrument": [ref(iri("sem-instrument-001"))],
            f"{H2KG}hasOutputData": [ref(iri("sem-raw-image-dataset"))],
            f"{H2KG}hasParameter": [
                ref(iri("accelerating-voltage-setting")),
                ref(iri("magnification-setting")),
                ref(iri("working-distance-setting")),
                ref(iri("temperature-setting")),
                ref(iri("relative-humidity-setting")),
            ],
            f"{H2KG}hasMetadata": [
                ref(iri("sem-acquisition-metadata")),
                ref(iri("source-record")),
                ref(iri("publication-record")),
            ],
            f"{PROV}wasAssociatedWith": [
                ref(iri("author-joachim-pasel")),
                ref(iri("institution-fzj-iek14")),
                ref(iri("funding-hip")),
            ],
            f"{DCTERMS}source": [ref(iri("publication-record"))],
        },
        {
            "@id": iri("sem-instrument-001"),
            "@type": [f"{H2KG}Instrument", f"{H2KG}SEMInstrument"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("SEM instrument used in the pilot case", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("sem-instrument-metadata"))],
        },
        {
            "@id": iri("sem-instrument-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Microscope brand: Zeiss Gemini Ultra plus; cathode: LaB6; probe: Electron beam.", language="en"),
                lit("Detector: InLens; imaging technique: Brightfield; signal: Secondary electrons; time lapse: 30 s.", language="en"),
                lit("Raw-data descriptor from sheet: electron images.", language="en"),
            ],
        },
        {
            "@id": iri("sem-raw-image-dataset"),
            "@type": [f"{H2KG}Data", f"{H2KG}SEMImageDataset"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("SEM raw image dataset", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("sem-raw-image-metadata"))],
        },
        {
            "@id": iri("sem-raw-image-metadata"),
            "@type": [f"{H2KG}Metadata"],
            f"{DCTERMS}format": [lit("tiff")],
            f"{DCTERMS}extent": [lit("1 MB"), lit("1024 x 1024 x 600 pixels")],
            f"{DCTERMS}source": [lit("link")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Filename: Test.tif.", language="en"),
                lit("PixelPerMetric: 8.1.", language="en"),
            ],
        },
        {
            "@id": iri("contrast-adjustment-step"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Contrast adjustment", language="en")],
            f"{H2KG}hasInputData": [ref(iri("sem-raw-image-dataset"))],
            f"{H2KG}hasOutputData": [ref(iri("sem-contrast-adjusted-dataset"))],
            f"{H2KG}hasMetadata": [ref(iri("contrast-adjustment-metadata"))],
        },
        {
            "@id": iri("contrast-adjustment-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Contrast factor: 1.", language="en")],
        },
        {
            "@id": iri("sem-contrast-adjusted-dataset"),
            "@type": [f"{H2KG}Data", f"{H2KG}SEMImageDataset"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("SEM contrast-adjusted image dataset", language="en")],
        },
        {
            "@id": iri("brightness-adjustment-step"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Brightness adjustment", language="en")],
            f"{H2KG}hasInputData": [ref(iri("sem-contrast-adjusted-dataset"))],
            f"{H2KG}hasOutputData": [ref(iri("sem-processed-image-dataset"))],
            f"{H2KG}hasMetadata": [ref(iri("brightness-adjustment-metadata"))],
        },
        {
            "@id": iri("brightness-adjustment-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Brightness factor: 1.", language="en")],
        },
        {
            "@id": iri("sem-processed-image-dataset"),
            "@type": [f"{H2KG}Data", f"{H2KG}SEMMicrographDataset", f"{H2KG}MicrostructureImageDataset"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("SEM processed micrograph dataset", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("sem-processed-image-metadata"))],
        },
        {
            "@id": iri("sem-processed-image-metadata"),
            "@type": [f"{H2KG}Metadata"],
            f"{DCTERMS}source": [lit("link")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Mask present: yes.", language="en"),
                lit("Mask link: link.", language="en"),
            ],
        },
        {
            "@id": iri("manual-particle-measurement-step"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Manual particle measurement", language="en")],
            f"{H2KG}hasInputData": [ref(iri("sem-processed-image-dataset"))],
            f"{H2KG}hasOutputData": [ref(iri("sem-analysis-summary-dataset"))],
            f"{H2KG}usesInstrument": [ref(f"{H2KG}FijiImageJSoftware")],
        },
        {
            "@id": iri("sem-analysis-summary-dataset"),
            "@type": [f"{H2KG}Data"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("SEM manual particle measurement summary dataset", language="en")],
            f"{H2KG}hasPart": [ref(iri("catalyst-particle-diameter-datapoint"))],
        },
        {
            "@id": iri("catalyst-particle-diameter-datapoint"),
            "@type": [f"{H2KG}DataPoint"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("SEM-derived catalyst particle diameter datapoint", language="en")],
            f"{H2KG}ofProperty": [ref(f"{H2KG}CatalystParticleDiameter")],
            f"{H2KG}fromMeasurement": [ref(iri("sem-measurement-001"))],
            f"{PROV}wasGeneratedBy": [ref(iri("manual-particle-measurement-step"))],
            f"{H2KG}hasMetadata": [ref(iri("catalyst-particle-diameter-datapoint-metadata"))],
            f"{DCTERMS}source": [ref(iri("publication-record"))],
        },
        {
            "@id": iri("catalyst-particle-diameter-datapoint-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Worksheet target label: Average size.", language="en"),
                lit("No numeric amount target value was provided in the SEM source sheet.", language="en"),
            ],
        },
        {
            "@id": iri("accelerating-voltage-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}AcceleratingVoltage"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("SEM accelerating-voltage setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("accelerating-voltage-setting-qv"))],
        },
        qv("accelerating-voltage-setting-qv", "20", f"{XSD}decimal", f"{UNIT}KiloV", "http://qudt.org/vocab/quantitykind/ElectricPotential"),
        {
            "@id": iri("magnification-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}Magnification"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("SEM magnification setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("magnification-setting-qv"))],
        },
        qv("magnification-setting-qv", "250", f"{XSD}integer", f"{UNIT}UNITLESS", "http://qudt.org/vocab/quantitykind/Dimensionless"),
        {
            "@id": iri("working-distance-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}WorkingDistance"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("SEM working-distance setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("working-distance-setting-qv"))],
        },
        qv("working-distance-setting-qv", "8.5", f"{XSD}decimal", f"{UNIT}MilliM", "http://qudt.org/vocab/quantitykind/Length"),
        {
            "@id": iri("temperature-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}Temperature"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("SEM acquisition temperature setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("temperature-setting-qv"))],
        },
        qv("temperature-setting-qv", "23", f"{XSD}decimal", f"{UNIT}DEG_C", "http://qudt.org/vocab/quantitykind/ThermodynamicTemperature"),
        {
            "@id": iri("relative-humidity-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}RelativeHumidity"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("SEM acquisition relative-humidity setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("relative-humidity-setting-qv"))],
        },
        qv("relative-humidity-setting-qv", "50", f"{XSD}decimal", f"{UNIT}PERCENT", "http://qudt.org/vocab/quantitykind/RelativeHumidity"),
        {
            "@id": iri("drying-temperature-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}DryingTemperature"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Drying temperature setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("drying-temperature-setting-qv"))],
        },
        qv("drying-temperature-setting-qv", "100", f"{XSD}decimal", f"{UNIT}DEG_C", "http://qudt.org/vocab/quantitykind/ThermodynamicTemperature"),
        {
            "@id": iri("drying-time-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}DryingTime"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Drying time setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("drying-time-setting-qv"))],
        },
        qv("drying-time-setting-qv", "10", f"{XSD}decimal", f"{UNIT}HR", "http://qudt.org/vocab/quantitykind/Time"),
        {
            "@id": iri("sem-acquisition-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Measurement type: ex-situ; specimen: homogeneous powder; atmosphere: air.", language="en"),
                lit("Pressure metadata: 1 atm; calibration notes: adjusting lenses and apertures / adjusting the voltage.", language="en"),
            ],
        },
    ]
    return items


def _sem_validation_note() -> str:
    return """# SEM Validation Note

## Ontology changes introduced in the SEM round

- No new SEM-specific TBox classes or parameters were introduced in this round.
- Existing SEM-related vocabulary entries were strengthened so the Explore/Search page can expose a coherent SEM neighborhood directly from the ontology.
- `ScanningElectronMicroscopyImaging`, `SEM Imaging`, and `SEM Imaging Measurement` were updated to point explicitly to shared SEM acquisition parameters and SEM output datasets.
- `Magnification`, `WorkingDistance`, `SEM Image Dataset`, and `SEM Micrograph Dataset` were generalized textually so they now describe SEM usage explicitly instead of remaining TEM-biased or too narrow.

## What remained instance metadata in round 1

- Organizational, bibliographic, file, and access details from the `org` section.
- `MeasurementType`, `Specimen`, `Atmosphere`, `Pressure`, and `Calibration` from the `char` section.
- `MicroscopeBrand`, `Cathode`, `Probe`, `Detector`, `ImagingTechnique`, `Signal`, `TimeLapse`, and raw-data descriptors from the `inst` section.
- Supplier, lot-number, CAS, and mounting details from the preparation sections.

## What was intentionally deferred

- No new TBox terms were introduced for `Buy`, `Sieve`, `Fix`, `Contrast adjustment`, `Brightness adjustment`, or `Manual particle measurement`; these remain labeled process instances.
- No dedicated metadata sub-vocabulary was introduced for detector, imaging mode, signal, or calibration fields in this first SEM round.
- The SEM pilot creates a `CatalystParticleDiameter` result data point, but the source sheet does not report a numeric result value, so no quantity value is attached.
"""


def _sem_case_summary() -> str:
    return """# SEM Case Summary

The SEM pilot demonstrates how H2KG can represent an imaging workflow from sample preparation through acquisition, image preprocessing, and derived analysis without introducing unnecessary ontology growth. The acquisition itself is represented as a `ScanningElectronMicroscopyImaging` measurement linked to a `SEMInstrument`, explicit acquisition-parameter settings such as accelerating voltage, magnification, working distance, temperature, and relative humidity, and a raw `SEMImageDataset`.

Two preprocessing steps, contrast adjustment and brightness adjustment, transform the raw dataset into a processed SEM micrograph dataset. An analysis step uses `FijiImageJSoftware` to derive the intended scientific output as a `DataPoint` for `CatalystParticleDiameter`, linked back to the measurement through `fromMeasurement` and to the analysis process through `prov:wasGeneratedBy`.

The source sheet does not provide a numeric average-size value. H2KG therefore captures the semantic result node and its provenance cleanly while preserving the absence of a reported quantity value rather than inventing one. This is important for later cross-method integration, because it keeps the ontology faithful to what was actually reported while still making the intended analytical target queryable.
"""


def _sem_follow_on_gaps() -> str:
    return """# Follow-on Gaps After SEM

- Review whether detector, signal, imaging mode, and calibration descriptors recur strongly enough across imaging methods to justify promotion from metadata to reusable H2KG terms.
- Compare SEM and TEM together to decide whether a small shared imaging-acquisition metadata profile should be introduced.
- Review whether sample-mounting and conductive-coating preparation steps should remain labeled process instances or become reusable vocabulary terms after cross-method comparison.
- Add subsequent rounds for AFM, FIB-SEM, synchrotron tomography/radiography, neutron tomography, and other characterization methods before promoting broader imaging abstractions.
"""


def _sem_readme(generated_files: list[Path]) -> str:
    files = "\n".join(f"- `{path.name}`" for path in generated_files)
    return f"""# SEM Pilot Package

Generated SEM companion artifacts for the controlled SEM imaging-method integration round.

## Files

{files}

The pilot keeps the ontology disciplined: SEM-specific vocabulary was strengthened where the explorer needed real TBox links, while worksheet-specific details remain attached as metadata or labeled process instances.
"""


def _missing_terms_note(missing: list[str]) -> str:
    lines = "\n".join(f"- `{term}`" for term in missing)
    return f"""# SEM Pilot Package

SEM pilot artifacts were not generated because required H2KG terms were missing from the input ontology source.

## Missing terms

{lines}
"""
