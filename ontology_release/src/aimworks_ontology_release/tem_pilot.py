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
TEM_EXAMPLE_NS = "https://w3id.org/h2kg/examples/tem#"

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
    f"{H2KG}VacuumChamberPressure",
    f"{H2KG}Sonication",
    f"{H2KG}SonicationTime",
    f"{H2KG}AcousticFrequency",
    f"{H2KG}DryingTime",
    f"{H2KG}TEMInstrument",
    f"{H2KG}FijiImageJSoftware",
    f"{H2KG}TransmissionElectronMicroscopyImaging",
    f"{H2KG}MicrostructureImageDataset",
    f"{H2KG}PdNanoparticleDiameter",
    f"{H2KG}Ultrasonicator",
}


def build_tem_pilot_package(
    input_path: str | Path,
    output_root: str | Path,
) -> dict[str, Any]:
    input_path = Path(input_path)
    output_root = Path(output_root)
    target_dir = ensure_dir(output_root / "examples" / "tem_pilot")
    merged = merge_document_items(load_json_document(input_path))
    present = {
        str(item.get("@id"))
        for item in merged
        if isinstance(item.get("@id"), str)
    }
    missing = sorted(REQUIRED_LOCAL_TERMS - present)
    if missing:
        write_text(
            target_dir / "README.md",
            _missing_terms_note(missing),
        )
        return {
            "status": "skipped_missing_terms",
            "missing_terms": missing,
            "output_dir": str(target_dir),
            "generated_files": [str(target_dir / "README.md")],
        }

    mapping_rows = _tem_mapping_rows()
    example_items = _tem_example_items()
    generated_files = [
        _write_mapping_matrix(target_dir / "tem_mapping_matrix.csv", mapping_rows),
        _write_mapping_matrix_markdown(target_dir / "tem_mapping_matrix.md", mapping_rows),
        dump_json(
            target_dir / "tem_pilot_example.jsonld",
            {"@context": {**COMMON_CONTEXT, "tem": TEM_EXAMPLE_NS}, "@graph": example_items},
        ),
        dump_turtle_items(target_dir / "tem_pilot_example.ttl", example_items),
        write_text(target_dir / "tem_validation_note.md", _tem_validation_note()),
        write_text(target_dir / "tem_case_summary.md", _tem_case_summary()),
        write_text(target_dir / "tem_follow_on_gaps.md", _tem_follow_on_gaps()),
    ]
    write_text(target_dir / "README.md", _tem_readme(generated_files))
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
        "# TEM Mapping Matrix",
        "",
        "This matrix accounts for each populated TEM sheet field and classifies it as `reuse existing term`, `new ontology term`, `instance metadata`, or `not modeled`.",
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


def _tem_mapping_rows() -> list[dict[str, str]]:
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
        ("ExperimentTitle", "Multi-technique characterization of electrodes with different carbons and Pt wt loadings", "instance metadata", "h2kg:hasMetadata + dcterms:title", "Stored on the source-record metadata node."),
        ("ExperimentID", "3", "instance metadata", "h2kg:hasMetadata + h2kg:hasIdentifier", "Stored as a literal identifier on the source-record metadata node."),
        ("Measurement-ID", "Run derived DOI", "instance metadata", "h2kg:hasMetadata + h2kg:hasIdentifier", "Stored as a literal identifier on the measurement metadata node."),
        ("UploadDate", "2024-10-15", "instance metadata", "h2kg:hasMetadata + dcterms:date", "Excel serial normalized to ISO date on the source record."),
        ("MeasurementDate", "", "not modeled", "-", "No value was present in the TEM pilot sheet."),
        ("Institution", "UCONN", "instance metadata", "prov:Agent", "Represented as an agent instance linked from the source record."),
        ("FoundingBody", "GCMAC", "instance metadata", "prov:Agent", "Represented as an agent instance linked from the source record."),
        ("Country", "USA", "instance metadata", "h2kg:hasMetadata", "Retained as contextual metadata on the source record."),
        ("Author", "Mariah Batool; Andre Colliard; Jasna Jankovic", "instance metadata", "prov:Agent", "Represented as author agent instances linked through publication metadata."),
        ("ORCID", "123-465-5478; 321-321-3211; 987-987-4566", "instance metadata", "h2kg:hasMetadata", "Stored on author metadata nodes in the pilot graph."),
        ("Email", "mari.ba@uconn.us; andyhuebsch@gmail.mx; jas.jan@uconn.us", "instance metadata", "h2kg:hasMetadata", "Stored on author metadata nodes in the pilot graph."),
        ("Published", "1", "instance metadata", "h2kg:hasMetadata", "Retained as publication-status metadata."),
        ("Publication", "Automatic Characterization of Energy Materials", "instance metadata", "h2kg:hasMetadata + dcterms:title", "Stored on a publication metadata node."),
        ("DOI", "https://doi.org/10.3390/catal11030655465465", "instance metadata", "h2kg:hasMetadata + dcterms:identifier", "Stored on a publication metadata node."),
        ("Journal", "ACS Nanoscale Au", "instance metadata", "h2kg:hasMetadata", "Retained as bibliographic metadata."),
        ("Volume", "51", "instance metadata", "h2kg:hasMetadata", "Retained as bibliographic metadata."),
        ("Issue", "78", "instance metadata", "h2kg:hasMetadata", "Retained as bibliographic metadata."),
        ("Pages", "82-89", "instance metadata", "h2kg:hasMetadata", "Retained as bibliographic metadata."),
        ("PublicationDate", "2023-11-12", "instance metadata", "h2kg:hasMetadata + dcterms:issued", "Excel serial normalized to ISO date on the publication metadata node."),
        ("Topic", "Catalysis", "instance metadata", "h2kg:hasMetadata", "Retained as thematic metadata."),
        ("Device", "PEMFC", "instance metadata", "h2kg:hasMetadata", "Retained as application-context metadata."),
        ("Component", "Catalyst layer", "instance metadata", "h2kg:hasMetadata", "Retained as component-context metadata."),
        ("Subcomponent", "Catalyst", "instance metadata", "h2kg:hasMetadata", "Retained as subcomponent metadata."),
        ("Granularity Level", "Nanostructure", "instance metadata", "h2kg:hasMetadata", "Retained as scale/granularity metadata."),
        ("Format", "tiff", "instance metadata", "h2kg:hasMetadata + dcterms:format", "Stored on the raw dataset metadata node."),
        ("FileSize", "1", "instance metadata", "h2kg:hasMetadata + dcterms:extent", "Stored with its file-size unit in dataset metadata."),
        ("FileSizeUnit", "MB", "instance metadata", "h2kg:hasMetadata + dcterms:extent", "Stored with file size in dataset metadata."),
        ("FileName", "Pt_wt3.zip", "instance metadata", "h2kg:hasMetadata", "Stored on the raw dataset metadata node."),
        ("DimensionX", "1024", "instance metadata", "h2kg:hasMetadata", "Stored on the raw dataset metadata node."),
        ("DimensionY", "1024", "instance metadata", "h2kg:hasMetadata", "Stored on the raw dataset metadata node."),
        ("DimensionZ", "0", "instance metadata", "h2kg:hasMetadata", "Stored on the raw dataset metadata node."),
        ("PixelPerMetric", "8.1", "instance metadata", "h2kg:hasMetadata", "Stored on the raw dataset metadata node."),
        ("Link", "link", "instance metadata", "h2kg:hasMetadata + dcterms:source", "Stored as source/link metadata."),
        ("MaskExist", "yes", "instance metadata", "h2kg:hasMetadata", "Stored on the processed dataset metadata node."),
        ("MaskLink", "github-com/StarPlatin", "instance metadata", "h2kg:hasMetadata + dcterms:source", "Stored on the processed dataset metadata node."),
    ]
    for field, value, classification, anchor, note in org_fields:
        add("org", field, value, classification, anchor, note)

    syn_fields = [
        ("Step 1 Precursor", "Pd/C", "instance metadata", "h2kg:Matter", "Represented as a material instance with supplier, lot-number, and CAS metadata."),
        ("Step 1 AmountPrecursor", "30 wt%", "instance metadata", "h2kg:hasMetadata", "Retained as procurement metadata on the Pd/C material instance."),
        ("Step 1 Technique", "Buy", "reuse existing term", "h2kg:Process", "Modeled as a labeled process instance rather than a new ontology term."),
        ("Step 1 Condition", "Manufacturer = Tanaka Kikinzoku Kogyo K.K., Japan; Lot number = TEC10E30E; CAS = 7440-05-3", "instance metadata", "h2kg:hasMetadata", "Stored on the Pd/C procurement metadata node."),
        ("Step 1 Target", "Pd/C", "instance metadata", "h2kg:Matter", "The procurement step outputs the Pd/C material instance."),
        ("Step 2 Precursor", "Carbon coated copper TEM grid", "instance metadata", "h2kg:Matter", "Represented as a material instance with procurement metadata."),
        ("Step 2 AmountPrecursor", "3 mm", "instance metadata", "h2kg:hasMetadata", "Stored as dimensional metadata on the TEM-grid material instance."),
        ("Step 2 Technique", "Buy", "reuse existing term", "h2kg:Process", "Modeled as a labeled process instance rather than a new ontology term."),
        ("Step 2 Condition", "Manufacturer = SigmaAldrich; Lot number = 205680; CAS = 7440-05-4", "instance metadata", "h2kg:hasMetadata", "Stored on the TEM-grid procurement metadata node."),
        ("Step 2 Target", "Carbon coated copper TEM grid", "instance metadata", "h2kg:Matter", "The procurement step outputs the TEM-grid material instance."),
    ]
    for field, value, classification, anchor, note in syn_fields:
        add("syn", field, value, classification, anchor, note)

    sp_fields = [
        ("Step 1 Technique", "Mix", "reuse existing term", "h2kg:Manufacturing", "Modeled as a labeled manufacturing instance under the existing process schema."),
        ("Step 1 Inputs", "Pd/C + Liquid mixture", "instance metadata", "h2kg:hasInputMaterial", "Connected as material-input instances to the mix step."),
        ("Step 1 AmountTarget", "5 mL", "instance metadata", "h2kg:hasMetadata", "Retained as intermediate-output metadata for SPInt1."),
        ("Step 2 Technique", "Sonification", "reuse existing term", "h2kg:Sonication", "Mapped to the existing Sonication term with explicit time and frequency settings."),
        ("Step 2 Condition", "Time = 10 min; Frequency = 80 Hz", "reuse existing term", "h2kg:SonicationTime + h2kg:AcousticFrequency", "Modeled through parameter-setting instances linked to the sonication step."),
        ("Step 3 Technique", "Dispersion", "reuse existing term", "h2kg:Manufacturing", "Modeled as a labeled manufacturing instance rather than a new ontology term."),
        ("Step 3 Inputs", "SPInt2 + Carbon coated copper TEM grid", "instance metadata", "h2kg:hasInputMaterial", "Connected as material inputs to the dispersion step."),
        ("Step 4 Technique", "Dry", "reuse existing term", "h2kg:Manufacturing", "Modeled as a labeled manufacturing instance rather than a new ontology term."),
        ("Step 4 Condition", "Time = 24 h", "reuse existing term", "h2kg:DryingTime", "Modeled through a drying-time parameter-setting instance."),
        ("Step 4 Target", "Sample", "instance metadata", "h2kg:Matter", "Represented as the final TEM sample material instance."),
    ]
    for field, value, classification, anchor, note in sp_fields:
        add("sp", field, value, classification, anchor, note)

    char_fields = [
        ("MeasurementMethod", "TEM", "reuse existing term", "h2kg:TransmissionElectronMicroscopyImaging", "Defines the pilot measurement instance type."),
        ("MeasurementType", "ex-situ", "instance metadata", "h2kg:hasMetadata", "Retained as measurement-context metadata in round 1."),
        ("Specimen", "homogeneous powder", "instance metadata", "h2kg:hasMetadata", "Retained as specimen-context metadata in round 1."),
        ("Characterization environment", "", "not modeled", "-", "No value was present in the TEM pilot sheet."),
        ("Temperature", "25 C", "reuse existing term", "h2kg:Temperature", "Modeled as a parameter-setting instance linked to the TEM measurement."),
        ("Humidity", "0 %", "reuse existing term", "h2kg:RelativeHumidity", "Modeled as a parameter-setting instance linked to the TEM measurement."),
        ("Atmosphere", "Vacuum", "instance metadata", "h2kg:hasMetadata", "Retained as measurement metadata in round 1."),
        ("Pressure", "10^-5 atm", "reuse existing term", "h2kg:VacuumChamberPressure", "Modeled as a parameter-setting instance linked to the TEM measurement."),
        ("Calibration", "adjusting lenses and apertures; adjusting the voltage", "instance metadata", "h2kg:hasMetadata", "Retained as calibration metadata in round 1."),
    ]
    for field, value, classification, anchor, note in char_fields:
        add("char", field, value, classification, anchor, note)

    inst_fields = [
        ("Instrument", "Electron Microscope", "reuse existing term", "h2kg:TEMInstrument", "Represented as a TEM instrument instance."),
        ("MicroscopeBrand", "Zeiss Gemini Ultra plus", "instance metadata", "h2kg:hasMetadata", "Stored as instrument metadata."),
        ("AccelerationVoltage", "100 kV", "reuse existing term", "h2kg:AcceleratingVoltage", "Modeled as a parameter-setting instance linked to the TEM measurement."),
        ("Magnification", "140000", "new ontology term", "h2kg:Magnification", "Introduced as a reusable acquisition parameter in the TEM round."),
        ("Cathode", "LaB6", "instance metadata", "h2kg:hasMetadata", "Stored as instrument metadata in round 1."),
        ("WorkingDistance", "8.5 mm", "new ontology term", "h2kg:WorkingDistance", "Introduced as a reusable acquisition parameter in the TEM round."),
        ("Probe", "Electron beam", "instance metadata", "h2kg:hasMetadata", "Stored as instrument metadata in round 1."),
        ("Detector", "CCD Camera", "instance metadata", "h2kg:hasMetadata", "Stored as instrument metadata in round 1."),
        ("ImagingTechnique", "Brightfield", "instance metadata", "h2kg:hasMetadata", "Stored as instrument metadata in round 1."),
        ("Signal", "Transmitted electrons", "instance metadata", "h2kg:hasMetadata", "Stored as instrument metadata in round 1."),
        ("TimeLapse", "30 s", "instance metadata", "h2kg:hasMetadata", "Retained as acquisition metadata in round 1."),
        ("RawData", "electron images", "instance metadata", "h2kg:MicrostructureImageDataset", "Retained as descriptive metadata on the raw image dataset."),
        ("DataAdquisitionRate", "-", "not modeled", "-", "No usable value was present in the TEM pilot sheet."),
    ]
    for field, value, classification, anchor, note in inst_fields:
        add("inst", field, value, classification, anchor, note)

    pre_fields = [
        ("Step 1 Precursor", "RawData", "instance metadata", "h2kg:MicrostructureImageDataset", "Mapped to the raw TEM image dataset instance."),
        ("Step 1 Technique", "Format conversion", "reuse existing term", "h2kg:Process", "Modeled as a labeled process instance rather than a new ontology term."),
        ("Step 1 Condition", "Format = Tiff", "instance metadata", "h2kg:hasMetadata + dcterms:format", "Stored as preprocessing metadata."),
        ("Step 1 Target", "Post-processed image", "instance metadata", "h2kg:MicrostructureImageDataset", "Mapped to the processed TEM image dataset instance."),
    ]
    for field, value, classification, anchor, note in pre_fields:
        add("pre", field, value, classification, anchor, note)

    anal_fields = [
        ("Step 1 Precursor", "Post-processed image", "instance metadata", "h2kg:MicrostructureImageDataset", "The analysis process consumes the processed TEM image dataset."),
        ("Step 1 Technique", "Manual particle measurement", "reuse existing term", "h2kg:Process", "Modeled as a labeled analysis-process instance rather than a new ontology term."),
        ("Step 1 Software", "ImageJ", "reuse existing term", "h2kg:FijiImageJSoftware", "The analysis process reuses the existing software instrument term."),
        ("Step 1 Target", "Average size", "reuse existing term", "h2kg:PdNanoparticleDiameter", "Mapped conservatively to the existing PdNanoparticleDiameter property."),
        ("Step 1 AmountTarget", "5 nm", "instance metadata", "h2kg:DataPoint + h2kg:hasQuantityValue", "Represented as the primary TEM result data point with an explicit quantity value."),
    ]
    for field, value, classification, anchor, note in anal_fields:
        add("anal", field, value, classification, anchor, note)

    return rows


def _tem_example_items() -> list[dict[str, Any]]:
    ex = TEM_EXAMPLE_NS

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
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("TEM pilot source record", language="en")],
            f"{DCTERMS}title": [lit("Multi-technique characterization of electrodes with different carbons and Pt wt loadings", language="en")],
            f"{DCTERMS}date": [lit("2024-10-15", datatype=f"{XSD}date")],
            f"{H2KG}hasIdentifier": [lit("3"), lit("Run derived DOI")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Topic: Catalysis; device: PEMFC; component: Catalyst layer; subcomponent: Catalyst; granularity: Nanostructure.", language="en"),
                lit("Country: USA; source link: link; pixel-per-metric: 8.1.", language="en"),
            ],
            f"{DCTERMS}creator": [ref(iri("author-mariah-batool")), ref(iri("author-andre-colliard")), ref(iri("author-jasna-jankovic"))],
            f"{DCTERMS}contributor": [ref(iri("institution-uconn")), ref(iri("funding-gcmac"))],
            f"{DCTERMS}source": [lit("link")],
        },
        {
            "@id": iri("publication-record"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("TEM pilot publication metadata", language="en")],
            f"{DCTERMS}title": [lit("Automatic Characterization of Energy Materials", language="en")],
            f"{DCTERMS}identifier": [lit("https://doi.org/10.3390/catal11030655465465")],
            f"{DCTERMS}issued": [lit("2023-11-12", datatype=f"{XSD}date")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Journal: ACS Nanoscale Au; volume: 51; issue: 78; pages: 82-89.", language="en"),
                lit("Published flag from source sheet: 1.", language="en"),
            ],
            f"{DCTERMS}creator": [ref(iri("author-mariah-batool")), ref(iri("author-andre-colliard")), ref(iri("author-jasna-jankovic"))],
        },
        {
            "@id": iri("author-mariah-batool"),
            "@type": [f"{PROV}Agent"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Mariah Batool", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("author-mariah-batool-metadata"))],
        },
        {
            "@id": iri("author-andre-colliard"),
            "@type": [f"{PROV}Agent"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Andre Colliard", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("author-andre-colliard-metadata"))],
        },
        {
            "@id": iri("author-jasna-jankovic"),
            "@type": [f"{PROV}Agent"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Jasna Jankovic", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("author-jasna-jankovic-metadata"))],
        },
        {
            "@id": iri("author-mariah-batool-metadata"),
            "@type": [f"{H2KG}Metadata"],
            f"{DCTERMS}identifier": [lit("ORCID: 123-465-5478"), lit("Email: mari.ba@uconn.us")],
        },
        {
            "@id": iri("author-andre-colliard-metadata"),
            "@type": [f"{H2KG}Metadata"],
            f"{DCTERMS}identifier": [lit("ORCID: 321-321-3211"), lit("Email: andyhuebsch@gmail.mx")],
        },
        {
            "@id": iri("author-jasna-jankovic-metadata"),
            "@type": [f"{H2KG}Metadata"],
            f"{DCTERMS}identifier": [lit("ORCID: 987-987-4566"), lit("Email: jas.jan@uconn.us")],
        },
        {
            "@id": iri("institution-uconn"),
            "@type": [f"{PROV}Agent"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("UCONN", language="en")],
        },
        {
            "@id": iri("funding-gcmac"),
            "@type": [f"{PROV}Agent"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("GCMAC", language="en")],
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
                lit("Sheet value: Pd/C; amount: 30 wt%.", language="en"),
                lit("Manufacturer: Tanaka Kikinzoku Kogyo K.K., Japan; lot number: TEC10E30E; CAS: 7440-05-3.", language="en"),
            ],
        },
        {
            "@id": iri("tem-grid"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Carbon coated copper TEM grid", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("tem-grid-metadata"))],
        },
        {
            "@id": iri("tem-grid-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Amount: 3 mm.", language="en"),
                lit("Manufacturer: SigmaAldrich; lot number: 205680; CAS: 7440-05-4.", language="en"),
            ],
        },
        {
            "@id": iri("liquid-mixture"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Liquid mixture", language="en")],
        },
        {
            "@id": iri("spint1"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("SPInt1 mixture intermediate", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("spint1-metadata"))],
        },
        {
            "@id": iri("spint1-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Target amount from sheet: 5 mL.", language="en")],
        },
        {
            "@id": iri("spint2"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("SPInt2 sonicated dispersion intermediate", language="en")],
        },
        {
            "@id": iri("spint3"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("SPInt3 deposited dispersion intermediate", language="en")],
        },
        {
            "@id": iri("tem-sample"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("TEM pilot powder sample", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("tem-sample-metadata"))],
        },
        {
            "@id": iri("tem-sample-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Specimen metadata from sheet: homogeneous powder.", language="en")],
        },
        {
            "@id": iri("procure-pdc"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Procure Pd/C precursor", language="en")],
            f"{H2KG}hasOutputMaterial": [ref(iri("pdc-material"))],
        },
        {
            "@id": iri("procure-tem-grid"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Procure carbon coated copper TEM grid", language="en")],
            f"{H2KG}hasOutputMaterial": [ref(iri("tem-grid"))],
        },
        {
            "@id": iri("mix-step"),
            "@type": [f"{H2KG}Manufacturing"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Mix Pd/C with liquid mixture", language="en")],
            f"{H2KG}hasInputMaterial": [ref(iri("pdc-material")), ref(iri("liquid-mixture"))],
            f"{H2KG}hasOutputMaterial": [ref(iri("spint1"))],
        },
        {
            "@id": iri("sonication-step"),
            "@type": [f"{H2KG}Manufacturing", f"{H2KG}Sonication"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Sonication of SPInt1", language="en")],
            f"{H2KG}hasInputMaterial": [ref(iri("spint1"))],
            f"{H2KG}hasOutputMaterial": [ref(iri("spint2"))],
            f"{H2KG}hasParameter": [ref(iri("sonication-time-setting")), ref(iri("acoustic-frequency-setting"))],
            f"{H2KG}usesInstrument": [ref(f"{H2KG}Ultrasonicator")],
        },
        {
            "@id": iri("dispersion-step"),
            "@type": [f"{H2KG}Manufacturing"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Dispersion onto carbon coated copper TEM grid", language="en")],
            f"{H2KG}hasInputMaterial": [ref(iri("spint2")), ref(iri("tem-grid"))],
            f"{H2KG}hasOutputMaterial": [ref(iri("spint3"))],
        },
        {
            "@id": iri("dry-step"),
            "@type": [f"{H2KG}Manufacturing"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Dry dispersed TEM sample", language="en")],
            f"{H2KG}hasInputMaterial": [ref(iri("spint3"))],
            f"{H2KG}hasOutputMaterial": [ref(iri("tem-sample"))],
            f"{H2KG}hasParameter": [ref(iri("drying-time-setting"))],
        },
        {
            "@id": iri("tem-measurement-001"),
            "@type": [f"{H2KG}Measurement", f"{H2KG}TransmissionElectronMicroscopyImaging"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("TEM pilot measurement", language="en")],
            f"{H2KG}hasInputMaterial": [ref(iri("tem-sample"))],
            f"{H2KG}usesInstrument": [ref(iri("tem-instrument-001"))],
            f"{H2KG}hasOutputData": [ref(iri("tem-raw-image-dataset"))],
            f"{H2KG}hasParameter": [
                ref(iri("accelerating-voltage-setting")),
                ref(iri("magnification-setting")),
                ref(iri("working-distance-setting")),
                ref(iri("temperature-setting")),
                ref(iri("relative-humidity-setting")),
                ref(iri("vacuum-pressure-setting")),
            ],
            f"{H2KG}hasMetadata": [
                ref(iri("tem-acquisition-metadata")),
                ref(iri("source-record")),
                ref(iri("publication-record")),
            ],
            f"{PROV}wasAssociatedWith": [ref(iri("author-mariah-batool")), ref(iri("author-andre-colliard")), ref(iri("author-jasna-jankovic"))],
            f"{DCTERMS}source": [ref(iri("publication-record"))],
        },
        {
            "@id": iri("tem-instrument-001"),
            "@type": [f"{H2KG}Instrument", f"{H2KG}TEMInstrument"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("TEM instrument used in the pilot case", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("tem-instrument-metadata"))],
        },
        {
            "@id": iri("tem-instrument-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Microscope brand: Zeiss Gemini Ultra plus; cathode: LaB6; probe: Electron beam.", language="en"),
                lit("Detector: CCD Camera; imaging technique: Brightfield; signal: Transmitted electrons; time lapse: 30 s.", language="en"),
            ],
        },
        {
            "@id": iri("tem-raw-image-dataset"),
            "@type": [f"{H2KG}Data", f"{H2KG}MicrostructureImageDataset"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("TEM raw image dataset", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("tem-raw-image-metadata"))],
        },
        {
            "@id": iri("tem-raw-image-metadata"),
            "@type": [f"{H2KG}Metadata"],
            f"{DCTERMS}format": [lit("tiff")],
            f"{DCTERMS}extent": [lit("1 MB"), lit("1024 x 1024 x 0 pixels")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Filename: Pt_wt3.zip.", language="en"),
                lit("Raw-data description from sheet: electron images.", language="en"),
            ],
        },
        {
            "@id": iri("format-conversion-step"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Format conversion", language="en")],
            f"{H2KG}hasInputData": [ref(iri("tem-raw-image-dataset"))],
            f"{H2KG}hasOutputData": [ref(iri("tem-processed-image-dataset"))],
            f"{H2KG}hasMetadata": [ref(iri("format-conversion-metadata"))],
        },
        {
            "@id": iri("format-conversion-metadata"),
            "@type": [f"{H2KG}Metadata"],
            f"{DCTERMS}format": [lit("tiff")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Preprocessing note from sheet: raw data converted to post-processed TIFF image.", language="en")],
        },
        {
            "@id": iri("tem-processed-image-dataset"),
            "@type": [f"{H2KG}Data", f"{H2KG}MicrostructureImageDataset"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("TEM processed image dataset", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("tem-processed-image-metadata"))],
        },
        {
            "@id": iri("tem-processed-image-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Mask present: yes.", language="en"),
                lit("Mask link: github-com/StarPlatin.", language="en"),
            ],
        },
        {
            "@id": iri("manual-particle-measurement-step"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Manual particle measurement", language="en")],
            f"{H2KG}hasInputData": [ref(iri("tem-processed-image-dataset"))],
            f"{H2KG}hasOutputData": [ref(iri("tem-analysis-summary-dataset"))],
            f"{H2KG}usesInstrument": [ref(f"{H2KG}FijiImageJSoftware")],
        },
        {
            "@id": iri("tem-analysis-summary-dataset"),
            "@type": [f"{H2KG}Data"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("TEM manual particle measurement summary dataset", language="en")],
            f"{H2KG}hasPart": [ref(iri("pd-nanoparticle-diameter-datapoint"))],
        },
        {
            "@id": iri("pd-nanoparticle-diameter-datapoint"),
            "@type": [f"{H2KG}DataPoint"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("TEM-derived Pd nanoparticle diameter datapoint", language="en")],
            f"{H2KG}ofProperty": [ref(f"{H2KG}PdNanoparticleDiameter")],
            f"{H2KG}fromMeasurement": [ref(iri("tem-measurement-001"))],
            f"{H2KG}hasQuantityValue": [ref(iri("pd-nanoparticle-diameter-qv"))],
            f"{PROV}wasGeneratedBy": [ref(iri("manual-particle-measurement-step"))],
            f"{DCTERMS}source": [ref(iri("publication-record"))],
        },
        qv("pd-nanoparticle-diameter-qv", "5", f"{XSD}decimal", f"{UNIT}NanoM", "http://qudt.org/vocab/quantitykind/Length"),
        {
            "@id": iri("accelerating-voltage-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}AcceleratingVoltage"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("TEM accelerating voltage setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("accelerating-voltage-setting-qv"))],
        },
        qv("accelerating-voltage-setting-qv", "100", f"{XSD}decimal", f"{UNIT}KiloV", "http://qudt.org/vocab/quantitykind/ElectricPotential"),
        {
            "@id": iri("magnification-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}Magnification"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("TEM magnification setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("magnification-setting-qv"))],
        },
        qv("magnification-setting-qv", "140000", f"{XSD}integer", f"{UNIT}UNITLESS", "http://qudt.org/vocab/quantitykind/Dimensionless"),
        {
            "@id": iri("working-distance-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}WorkingDistance"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("TEM working-distance setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("working-distance-setting-qv"))],
        },
        qv("working-distance-setting-qv", "8.5", f"{XSD}decimal", f"{UNIT}MilliM", "http://qudt.org/vocab/quantitykind/Length"),
        {
            "@id": iri("temperature-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}Temperature"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("TEM acquisition temperature setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("temperature-setting-qv"))],
        },
        qv("temperature-setting-qv", "25", f"{XSD}decimal", f"{UNIT}DEG_C", "http://qudt.org/vocab/quantitykind/ThermodynamicTemperature"),
        {
            "@id": iri("relative-humidity-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}RelativeHumidity"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("TEM acquisition relative-humidity setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("relative-humidity-setting-qv"))],
        },
        qv("relative-humidity-setting-qv", "0", f"{XSD}decimal", f"{UNIT}PERCENT", "http://qudt.org/vocab/quantitykind/RelativeHumidity"),
        {
            "@id": iri("vacuum-pressure-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}VacuumChamberPressure"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("TEM vacuum-chamber pressure setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("vacuum-pressure-setting-qv"))],
        },
        qv("vacuum-pressure-setting-qv", "1.0e-5", f"{XSD}double", f"{UNIT}ATM", "http://qudt.org/vocab/quantitykind/Pressure"),
        {
            "@id": iri("sonication-time-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}SonicationTime"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Sonication time setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("sonication-time-setting-qv"))],
        },
        qv("sonication-time-setting-qv", "10", f"{XSD}decimal", f"{UNIT}MIN", "http://qudt.org/vocab/quantitykind/Time"),
        {
            "@id": iri("acoustic-frequency-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}AcousticFrequency"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Acoustic-frequency setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("acoustic-frequency-setting-qv"))],
        },
        qv("acoustic-frequency-setting-qv", "80", f"{XSD}decimal", f"{UNIT}HZ", "http://qudt.org/vocab/quantitykind/Frequency"),
        {
            "@id": iri("drying-time-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}DryingTime"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Drying-time setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("drying-time-setting-qv"))],
        },
        qv("drying-time-setting-qv", "24", f"{XSD}decimal", f"{UNIT}HR", "http://qudt.org/vocab/quantitykind/Time"),
        {
            "@id": iri("tem-acquisition-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Measurement type: ex-situ; specimen: homogeneous powder; atmosphere: vacuum.", language="en"),
                lit("Calibration notes: adjusting lenses and apertures; adjusting the voltage.", language="en"),
            ],
        },
    ]
    return items


def _tem_validation_note() -> str:
    return """# TEM Validation Note

## Ontology changes introduced in the TEM round

- Added `h2kg:hasMetadata` as a generic metadata-attachment relation with range `h2kg:Metadata`.
- Generalized the domain of `h2kg:hasOutputData` from `h2kg:Measurement` to `h2kg:Process` so preprocessing and analysis steps can emit data cleanly.
- Added `h2kg:Magnification` as a reusable acquisition parameter.
- Added `h2kg:WorkingDistance` as a reusable acquisition parameter.
- Normalized the definition of `h2kg:MicrostructureImageDataset` so it remains generic and reusable beyond one source paper.

## What remained instance metadata in round 1

- Organizational, bibliographic, file, and access details from the `org` section.
- `MeasurementType`, `Specimen`, `Atmosphere`, and `Calibration` from the `char` section.
- `MicroscopeBrand`, `Cathode`, `Probe`, `Detector`, `ImagingTechnique`, `Signal`, `TimeLapse`, `RawData`, and `DataAdquisitionRate` from the `inst` section.
- Procurement metadata such as supplier, lot number, and CAS number.

## What was intentionally deferred

- No new TBox terms were introduced for `Buy`, `Mix`, `Dispersion`, `Dry`, or `Manual particle measurement`; these remain labeled process instances.
- No dedicated metadata sub-vocabulary was introduced for every catalog field in this first round.
- `MeasurementType`, imaging mode, detector, and signal remain metadata until they are reviewed across additional imaging methods.
- The pilot uses `PdNanoparticleDiameter` as the primary scientific output and does not broaden the result to a generic particle-size term.

## Modeling note

The TEM pilot follows the current H2KG release style by combining the reusable base schema (`Process`, `Measurement`, `Data`, `Metadata`, `DataPoint`) with local controlled-vocabulary anchors such as `TransmissionElectronMicroscopyImaging`, `TEMInstrument`, `MicrostructureImageDataset`, and `PdNanoparticleDiameter`.
"""


def _tem_case_summary() -> str:
    return """# TEM Case Summary

The TEM pilot demonstrates that H2KG can capture one imaging workflow end to end without uncontrolled ontology growth. Procurement and sample-preparation steps are represented as process instances that consume and produce material instances, while the TEM acquisition itself is represented as a `TransmissionElectronMicroscopyImaging` measurement linked to a `TEMInstrument`, explicit acquisition-parameter settings, and a raw `MicrostructureImageDataset`.

A preprocessing step converts the raw image data into a processed image dataset, and an analysis step uses `FijiImageJSoftware` to derive the final scientific result. The reported average particle size is represented as a `DataPoint` for `PdNanoparticleDiameter`, linked back to the TEM measurement through `fromMeasurement`, to the analysis process through `prov:wasGeneratedBy`, and to a local QUDT quantity-value node carrying the numeric value `5 nm`.

This pilot keeps publication, file, author, and organizational information as attached metadata rather than promoting dozens of one-off ontology terms. It therefore shows a conservative H2KG extension pattern that is rich enough for provenance and querying, but disciplined enough to remain compatible with the existing release model.
"""


def _tem_follow_on_gaps() -> str:
    return """# Follow-on Gaps After TEM

- Introduce a reusable pattern for explicit acquisition-setting instances across imaging methods if SEM, AFM, FIB-SEM, and tomography rounds show the same need.
- Review whether `MeasurementType`, imaging mode, detector, probe, and signal descriptors recur strongly enough to justify promotion from metadata to reusable H2KG terms.
- Consider a small imaging-metadata profile that groups common file, calibration, resolution, and mask fields without overloading the base ontology.
- Review whether procurement and deposition-style preparation steps should remain labeled instances or be promoted selectively after multiple methods are compared.
- Decide in a later cross-method round whether XRD, XPS, and Raman should be added as ontology-native characterization extensions even though they are not present as sheets in the current catalog workbook.
"""


def _tem_readme(generated_files: list[Path]) -> str:
    files = "\n".join(f"- `{path.name}`" for path in generated_files)
    return f"""# TEM Pilot Package

Generated TEM companion artifacts for the first imaging-method integration round.

## Files

{files}

The pilot is intentionally conservative: only minimal reusable schema changes were introduced, while catalog-specific details remain attached as metadata or labeled process instances.
"""


def _missing_terms_note(missing: list[str]) -> str:
    lines = "\n".join(f"- `{term}`" for term in missing)
    return f"""# TEM Pilot Package

TEM pilot artifacts were not generated because required H2KG terms were missing from the input ontology source.

## Missing terms

{lines}
"""
