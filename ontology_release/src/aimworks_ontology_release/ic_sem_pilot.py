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
IC_SEM_EXAMPLE_NS = "https://w3id.org/h2kg/examples/ic-sem#"

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
    f"{H2KG}DoctorBladeCoating",
    f"{H2KG}DryingTemperature",
    f"{H2KG}DryingTime",
    f"{H2KG}Temperature",
    f"{H2KG}RelativeHumidity",
    f"{H2KG}VacuumChamberPressure",
    f"{H2KG}DwellTime",
    f"{H2KG}Magnification",
    f"{H2KG}MicroscopyMeasuredArea",
    f"{H2KG}ExposureTime",
    f"{H2KG}IonBeamCurrent",
    f"{H2KG}IonBeamEnergy",
    f"{H2KG}ElectronCurrent",
    f"{H2KG}ElectronBeamEnergy",
    f"{H2KG}CutThickness",
    f"{H2KG}TotalAcquisitionTime",
    f"{H2KG}SEMImageDataset",
    f"{H2KG}SEMMicrographDataset",
    f"{H2KG}MicrostructureImageDataset",
    f"{H2KG}FijiImageJSoftware",
    f"{H2KG}MEAAssembly",
    f"{H2KG}GasDiffusionLayerThickness",
    f"{H2KG}TotalPorosity",
    f"{H2KG}ICSEMImagingMeasurement",
    f"{H2KG}ICSEMInstrument",
    f"{H2KG}MembraneElectrodeAssemblyThickness",
    f"{H2KG}PixelSize",
}


def build_ic_sem_pilot_package(
    input_path: str | Path,
    output_root: str | Path,
) -> dict[str, Any]:
    input_path = Path(input_path)
    output_root = Path(output_root)
    target_dir = ensure_dir(output_root / "examples" / "ic_sem_pilot")
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

    mapping_rows = _ic_sem_mapping_rows()
    example_items = _ic_sem_example_items()
    generated_files = [
        _write_mapping_matrix(target_dir / "ic_sem_mapping_matrix.csv", mapping_rows),
        _write_mapping_matrix_markdown(target_dir / "ic_sem_mapping_matrix.md", mapping_rows),
        dump_json(
            target_dir / "ic_sem_example.jsonld",
            {"@context": {**COMMON_CONTEXT, "icsem": IC_SEM_EXAMPLE_NS}, "@graph": example_items},
        ),
        dump_turtle_items(target_dir / "ic_sem_example.ttl", example_items),
        write_text(target_dir / "ic_sem_validation_note.md", _ic_sem_validation_note()),
        write_text(target_dir / "ic_sem_case_summary.md", _ic_sem_case_summary()),
        write_text(target_dir / "ic_sem_follow_on_gaps.md", _ic_sem_follow_on_gaps()),
        write_text(target_dir / "ic_sem_manuscript_figure.md", _ic_sem_manuscript_figure()),
        write_text(target_dir / "ic_sem_manuscript_table.md", _ic_sem_manuscript_table()),
    ]
    write_text(target_dir / "README.md", _ic_sem_readme(generated_files))
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
        "# IC-SEM Mapping Matrix",
        "",
        "This matrix accounts for each populated IC-SEM sheet field and classifies it as `reuse existing term`, `new ontology term`, `instance metadata`, or `not modeled` for the controlled pilot round.",
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


def _ic_sem_mapping_rows() -> list[dict[str, str]]:
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
        ("ExperimentTitle", "Ion-cut SEM of a doctor bladed MEA", "instance metadata", "h2kg:hasMetadata + dcterms:title", "Stored on the source-record metadata node."),
        ("ExperimentID", "4", "instance metadata", "h2kg:hasMetadata + h2kg:hasIdentifier", "Stored as a literal identifier on the source record."),
        ("Measurement-ID", "Run derived DOI", "instance metadata", "h2kg:hasMetadata + h2kg:hasIdentifier", "Stored on measurement metadata."),
        ("UploadDate", "2021-10-15", "instance metadata", "h2kg:hasMetadata + dcterms:date", "Excel serial normalized to ISO date."),
        ("Institution", "DLR", "instance metadata", "prov:Agent", "Represented as an institutional agent."),
        ("FoundingBody", "Helmholtz Imaging (HI)", "instance metadata", "prov:Agent", "Represented as a funding-body agent."),
        ("Country", "Germany", "instance metadata", "h2kg:hasMetadata", "Retained as contextual metadata."),
        ("Author", "Tobias Morawietz; Andre Colliard", "instance metadata", "prov:Agent", "Represented as author agent instances."),
        ("ORCID", "123-465-7777; 321-321-3211", "instance metadata", "h2kg:hasMetadata", "Stored on author metadata nodes."),
        ("Email", "tobi.mora@dlr.de; andyhuebsch@gmail.mx", "instance metadata", "h2kg:hasMetadata", "Stored on author metadata nodes."),
        ("Published", "1", "instance metadata", "h2kg:hasMetadata", "Retained as publication-status metadata."),
        ("Publication", "Automatic Characterization of Ion-cut SEM of a doctor bladed MEA", "instance metadata", "h2kg:hasMetadata + dcterms:title", "Stored on a publication metadata node."),
        ("DOI", "https://doi.org/10.3390/catal11077778", "instance metadata", "h2kg:hasMetadata + dcterms:identifier", "Stored on a publication metadata node."),
        ("Journal", "Nature", "instance metadata", "h2kg:hasMetadata", "Retained as bibliographic metadata."),
        ("Volume", "89", "instance metadata", "h2kg:hasMetadata", "Retained as bibliographic metadata."),
        ("Issue", "5", "instance metadata", "h2kg:hasMetadata", "Retained as bibliographic metadata."),
        ("Pages", "7778-9998", "instance metadata", "h2kg:hasMetadata", "Retained as bibliographic metadata."),
        ("PublicationDate", "2021-10-18", "instance metadata", "h2kg:hasMetadata + dcterms:issued", "Excel serial normalized to ISO date."),
        ("Topic", "Fuel Cell", "instance metadata", "h2kg:hasMetadata", "Retained as thematic metadata."),
        ("Device", "PEMFC", "instance metadata", "h2kg:hasMetadata", "Retained as application-context metadata."),
        ("Component", "MEA", "instance metadata", "h2kg:hasMetadata", "Retained as component metadata."),
        ("Subcomponent", "Gas diffusion layer", "instance metadata", "h2kg:hasMetadata", "Retained as subcomponent metadata in round 1 instead of promoting a new local node."),
        ("Granularity Level", "Nanostructure", "instance metadata", "h2kg:hasMetadata", "Retained as scale metadata."),
        ("Format", "tiff", "instance metadata", "h2kg:hasMetadata + dcterms:format", "Stored on raw-dataset metadata."),
        ("FileSize", "50 MB", "instance metadata", "h2kg:hasMetadata + dcterms:extent", "Stored on raw-dataset metadata."),
        ("FileName", "ICSEM.zip", "instance metadata", "h2kg:hasMetadata", "Stored on raw-dataset metadata."),
        ("DimensionX", "512", "instance metadata", "h2kg:hasMetadata", "Stored on raw-dataset metadata."),
        ("DimensionY", "512", "instance metadata", "h2kg:hasMetadata", "Stored on raw-dataset metadata."),
        ("DimensionZ", "0", "instance metadata", "h2kg:hasMetadata", "Stored on raw-dataset metadata."),
        ("PixelPerMetric", "20", "instance metadata", "h2kg:hasMetadata", "Stored on raw-dataset metadata."),
        ("Link", "link", "instance metadata", "h2kg:hasMetadata + dcterms:source", "Stored as source/link metadata."),
        ("MaskExist", "yes", "instance metadata", "h2kg:hasMetadata", "Stored on processed-dataset metadata."),
        ("MaskLink", "github-com/ICSEM", "instance metadata", "h2kg:hasMetadata + dcterms:source", "Stored on processed-dataset metadata."),
    ]:
        add("org", field, value, classification, anchor, note)

    for field, value, classification, anchor, note in [
        ("Step 1 Precursor", "HiSPEC 4000", "instance metadata", "h2kg:Matter", "Represented as a material instance with procurement metadata."),
        ("Step 1 AmountPrecursor", "40 wt%", "instance metadata", "h2kg:hasMetadata", "Stored on the catalyst precursor metadata node."),
        ("Step 1 Technique", "Buy", "reuse existing term", "h2kg:Process", "Modeled as a labeled procurement process instance rather than a new TBox term."),
        ("Step 2 Precursor", "Nafion XL membrane", "instance metadata", "h2kg:Matter", "Represented as a material instance with procurement metadata."),
        ("Step 2 AmountPrecursor", "28 um", "instance metadata", "h2kg:hasMetadata", "Stored as membrane-procurement metadata."),
        ("Step 2 Technique", "Buy", "reuse existing term", "h2kg:Process", "Modeled as a labeled procurement process instance."),
        ("Step 3 Precursor", "Nafion ionomer", "instance metadata", "h2kg:Matter", "Represented as a material instance with procurement metadata."),
        ("Step 3 AmountPrecursor", "5 wt.%", "instance metadata", "h2kg:hasMetadata", "Stored as material metadata."),
        ("Step 4 Precursor", "Gas diffusion layer", "instance metadata", "h2kg:Matter", "Represented as a material instance with procurement metadata."),
        ("Step 4 Technique", "Buy", "reuse existing term", "h2kg:Process", "Modeled as a labeled procurement process instance."),
        ("Step 5 Technique", "Dissolved", "reuse existing term", "h2kg:Manufacturing", "Modeled as a labeled manufacturing instance; ratio and viscosity remain metadata."),
        ("Step 5 Condition", "Ratio = 70:30; Viscosity = 80 Pas", "instance metadata", "h2kg:hasMetadata", "Retained as process metadata in round 1."),
        ("Step 6 Technique", "Doctor blade", "reuse existing term", "h2kg:DoctorBladeCoating", "Mapped to the existing DoctorBladeCoating term."),
        ("Step 6 Condition", "Velocity = 1 cm/s; Instrument = MICOS Blading; Thickness = 1 mm", "instance metadata", "h2kg:hasMetadata", "Retained as process metadata in round 1."),
        ("Step 7 Technique", "Dry", "reuse existing term", "h2kg:Manufacturing", "Modeled as a labeled manufacturing instance with drying parameters."),
        ("Step 7 Condition", "Time = 16 h; Temperature = 80 °C", "reuse existing term", "h2kg:DryingTime + h2kg:DryingTemperature", "Modeled through parameter-setting instances linked to the drying step."),
    ]:
        add("syn", field, value, classification, anchor, note)

    for field, value, classification, anchor, note in [
        ("Step 1 Technique", "Cut", "reuse existing term", "h2kg:Manufacturing", "Modeled as a labeled manufacturing instance; sample size stays metadata."),
        ("Step 1 Condition", "Size = 5 mm2", "instance metadata", "h2kg:hasMetadata", "Retained as cut-step metadata."),
        ("Step 2 Technique", "Fix", "reuse existing term", "h2kg:Manufacturing", "Modeled as a labeled manufacturing instance."),
        ("Step 2 Condition", "SampleHolder = Standard CSP", "instance metadata", "h2kg:hasMetadata", "Retained as fixture metadata."),
        ("Step 3 Technique", "Dispersion", "reuse existing term", "h2kg:Process", "Modeled as a labeled process instance."),
        ("Step 3 Precursor", "Carbon coated copper TEM grid", "instance metadata", "h2kg:Matter", "Retained as supporting sample-context material metadata."),
        ("Step 4 Technique", "Dry", "reuse existing term", "h2kg:Manufacturing", "Modeled as a labeled manufacturing instance."),
        ("Step 4 Condition", "Time = 24 h", "reuse existing term", "h2kg:DryingTime", "Modeled through a drying-time setting instance."),
    ]:
        add("sp", field, value, classification, anchor, note)

    for field, value, classification, anchor, note in [
        ("MeasurementMethod", "IC-SEM", "reuse existing term", "h2kg:ICSEMImagingMeasurement", "Mapped to the new public IC-SEM measurement term."),
        ("MeasurementType", "ex-situ", "instance metadata", "h2kg:hasMetadata", "Retained as measurement metadata in round 1."),
        ("Specimen", "highly porous bulk material", "instance metadata", "h2kg:hasMetadata", "Retained as specimen metadata in round 1."),
        ("Temperature", "25 C", "reuse existing term", "h2kg:Temperature", "Modeled as a parameter-setting instance linked to the IC-SEM measurement."),
        ("Humidity", "0 %", "reuse existing term", "h2kg:RelativeHumidity", "Modeled as a parameter-setting instance linked to the IC-SEM measurement."),
        ("Atmosphere", "Vacuum", "instance metadata", "h2kg:hasMetadata", "Retained as measurement metadata in round 1."),
        ("Pressure", "10^-6 atm", "reuse existing term", "h2kg:VacuumChamberPressure", "Modeled as a parameter-setting instance linked to the IC-SEM measurement."),
        ("Calibration", "adjusting lenses and apertures; adjusting the voltage", "instance metadata", "h2kg:hasMetadata", "Retained as acquisition metadata."),
    ]:
        add("char", field, value, classification, anchor, note)

    for field, value, classification, anchor, note in [
        ("Instrument", "FIB-SEM", "new ontology term", "h2kg:ICSEMInstrument", "A distinct public instrument term is introduced so ion-cut SEM is retrievable independently in H2KG Explore."),
        ("FIBEquipment", "Jeol IB-19530CP Cross Section Polisher", "instance metadata", "h2kg:hasMetadata", "Retained on instrument metadata."),
        ("SEMEquipment", "Jeol JSM-7200F SEM", "instance metadata", "h2kg:hasMetadata", "Retained on instrument metadata."),
        ("Optics", "GEMINI", "instance metadata", "h2kg:hasMetadata", "Retained on instrument metadata."),
        ("InjectionSystem", "multi channel gas injection system GIS", "instance metadata", "h2kg:hasMetadata", "Retained on instrument metadata."),
        ("IonBeamType", "Ar", "instance metadata", "h2kg:hasMetadata", "Retained on instrument metadata."),
        ("IonBeamCurrent", "700 pA", "reuse existing term", "h2kg:IonBeamCurrent", "Modeled as a parameter-setting instance linked to the IC-SEM measurement."),
        ("IonBeamEnergy", "6 keV", "reuse existing term", "h2kg:IonBeamEnergy", "Modeled as a parameter-setting instance linked to the IC-SEM measurement."),
        ("PlaneSpacing", "10", "instance metadata", "h2kg:hasMetadata", "Retained as acquisition metadata in round 1."),
        ("MeasuredArea", "20 um2", "reuse existing term", "h2kg:MicroscopyMeasuredArea", "Modeled as a parameter-setting instance linked to the IC-SEM measurement."),
        ("CutThickness", "150 nm", "reuse existing term", "h2kg:CutThickness", "Modeled as a parameter-setting instance linked to the IC-SEM measurement."),
        ("DwellTime", "12 h", "reuse existing term", "h2kg:DwellTime", "Modeled as a parameter-setting instance linked to the IC-SEM measurement."),
        ("Detector", "InLens, SE2", "instance metadata", "h2kg:hasMetadata", "Retained on instrument metadata."),
        ("ElectronCurrent", "250 pA", "reuse existing term", "h2kg:ElectronCurrent", "Modeled as a parameter-setting instance linked to the IC-SEM measurement."),
        ("ElectronBeamEnergy", "1.5 keV", "reuse existing term", "h2kg:ElectronBeamEnergy", "Modeled as a parameter-setting instance linked to the IC-SEM measurement."),
        ("PixelSize", "20 nm", "new ontology term", "h2kg:PixelSize", "A dedicated 2D microscopy pixel-size parameter is introduced instead of reusing voxel size."),
        ("Magnification", "10", "reuse existing term", "h2kg:Magnification", "Modeled as a parameter-setting instance linked to the IC-SEM measurement."),
        ("Brightness", "1", "instance metadata", "h2kg:hasMetadata", "Retained as acquisition metadata in round 1."),
        ("Contrast", "1", "instance metadata", "h2kg:hasMetadata", "Retained as acquisition metadata in round 1."),
        ("ImageAcquisitionTime", "60 s", "reuse existing term", "h2kg:ExposureTime", "Mapped conservatively to the existing exposure-time parameter."),
        ("TotalAcquisitionTime", "12 h", "reuse existing term", "h2kg:TotalAcquisitionTime", "Modeled as a parameter-setting instance linked to the IC-SEM measurement."),
    ]:
        add("inst", field, value, classification, anchor, note)

    for field, value, classification, anchor, note in [
        ("Step 1 Technique", "Thresholding", "reuse existing term", "h2kg:Process", "Modeled as a labeled preprocessing process instance."),
        ("Step 1 Software", "ImageJ; algorithm = Watershed", "reuse existing term", "h2kg:FijiImageJSoftware", "Software is represented through the existing ImageJ software term; algorithm stays metadata."),
        ("Step 2 Technique", "Scale set", "reuse existing term", "h2kg:Process", "Modeled as a labeled preprocessing process instance."),
        ("Step 2 Software", "ImageJ", "reuse existing term", "h2kg:FijiImageJSoftware", "Software is represented through the existing ImageJ software term."),
    ]:
        add("pre", field, value, classification, anchor, note)

    for field, value, classification, anchor, note in [
        ("Step 1 Technique", "Layer thickness measurement", "reuse existing term", "h2kg:Process", "Modeled as a labeled analysis process instance."),
        ("Step 1 Software", "ImageJ", "reuse existing term", "h2kg:FijiImageJSoftware", "Software is represented through the existing ImageJ software term."),
        ("Step 1 Target", "MEA thickness", "new ontology term", "h2kg:MembraneElectrodeAssemblyThickness", "Promoted as a new public H2KG property term."),
        ("Step 1 AmountTarget", "80 nm", "instance metadata", "h2kg:DataPoint + h2kg:hasQuantityValue", "Represented as a measurement-derived datapoint with a quantity value."),
        ("Step 1 Target", "GDL thickness", "reuse existing term", "h2kg:GasDiffusionLayerThickness", "Reused as the existing H2KG thickness anchor requested for this round."),
        ("Step 1 AmountTarget", "160 nm", "instance metadata", "h2kg:DataPoint + h2kg:hasQuantityValue", "Represented as a measurement-derived datapoint with a quantity value."),
        ("Step 2 Technique", "Porosity measurement", "reuse existing term", "h2kg:Process", "Modeled as a labeled analysis process instance."),
        ("Step 2 Software", "ImageJ", "reuse existing term", "h2kg:FijiImageJSoftware", "Software is represented through the existing ImageJ software term."),
        ("Step 2 Target", "Porosity", "reuse existing term", "h2kg:TotalPorosity", "Mapped conservatively to the existing total-porosity property."),
        ("Step 2 AmountTarget", "6 pu", "instance metadata", "h2kg:DataPoint + h2kg:hasQuantityValue", "Represented as a porosity datapoint with metadata noting the raw sheet unit token."),
    ]:
        add("anal", field, value, classification, anchor, note)

    return rows


def _ic_sem_example_items() -> list[dict[str, Any]]:
    ex = IC_SEM_EXAMPLE_NS

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
            f"{DCTERMS}title": [lit("Ion-cut SEM of a doctor bladed MEA", language="en")],
            f"{DCTERMS}date": [lit("2021-10-15", datatype=f"{XSD}date")],
            f"{H2KG}hasIdentifier": [lit("4"), lit("Run derived DOI")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Topic: Fuel Cell; device: PEMFC; component: MEA; subcomponent: Gas diffusion layer.", language="en"),
                lit("Granularity level: Nanostructure; country: Germany; source link: link.", language="en"),
            ],
            f"{DCTERMS}creator": [ref(iri("author-tobias-morawietz")), ref(iri("author-andre-colliard"))],
            f"{DCTERMS}contributor": [ref(iri("institution-dlr")), ref(iri("funding-hi"))],
            f"{DCTERMS}source": [lit("link")],
        },
        {
            "@id": iri("publication-record"),
            "@type": [f"{H2KG}Metadata"],
            f"{DCTERMS}title": [lit("Automatic Characterization of Ion-cut SEM of a doctor bladed MEA", language="en")],
            f"{DCTERMS}identifier": [lit("https://doi.org/10.3390/catal11077778")],
            f"{DCTERMS}issued": [lit("2021-10-18", datatype=f"{XSD}date")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Journal: Nature; volume: 89; issue: 5; pages: 7778-9998.", language="en"),
                lit("Published flag from source sheet: 1.", language="en"),
            ],
            f"{DCTERMS}creator": [ref(iri("author-tobias-morawietz")), ref(iri("author-andre-colliard"))],
        },
        {
            "@id": iri("author-tobias-morawietz"),
            "@type": [f"{PROV}Agent"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Tobias Morawietz", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("author-tobias-morawietz-metadata"))],
        },
        {
            "@id": iri("author-andre-colliard"),
            "@type": [f"{PROV}Agent"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Andre Colliard", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("author-andre-colliard-metadata"))],
        },
        {
            "@id": iri("author-tobias-morawietz-metadata"),
            "@type": [f"{H2KG}Metadata"],
            f"{DCTERMS}identifier": [lit("ORCID: 123-465-7777"), lit("Email: tobi.mora@dlr.de")],
        },
        {
            "@id": iri("author-andre-colliard-metadata"),
            "@type": [f"{H2KG}Metadata"],
            f"{DCTERMS}identifier": [lit("ORCID: 321-321-3211"), lit("Email: andyhuebsch@gmail.mx")],
        },
        {
            "@id": iri("institution-dlr"),
            "@type": [f"{PROV}Agent"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("DLR", language="en")],
        },
        {
            "@id": iri("funding-hi"),
            "@type": [f"{PROV}Agent"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Helmholtz Imaging (HI)", language="en")],
        },
        {
            "@id": iri("hispec-4000-material"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("HiSPEC 4000 catalyst precursor", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("hispec-4000-material-metadata"))],
        },
        {
            "@id": iri("hispec-4000-material-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Amount: 40 wt%.", language="en"),
                lit("Manufacturer: Johnson Matthey; lot number: 205680; CAS-number: 7440-05-3.", language="en"),
            ],
        },
        {
            "@id": iri("nafion-xl-membrane"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Nafion XL membrane precursor", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("nafion-xl-membrane-metadata"))],
        },
        {
            "@id": iri("nafion-xl-membrane-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Amount: 28 um.", language="en"),
                lit("Manufacturer: DuPont; lot number: 205680; CAS-number: 7440-05-3.", language="en"),
            ],
        },
        {
            "@id": iri("nafion-ionomer-material"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Nafion ionomer precursor", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("nafion-ionomer-material-metadata"))],
        },
        {
            "@id": iri("nafion-ionomer-material-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Amount: 5 wt.%.", language="en"),
                lit("Manufacturer: DuPont; lot number: 205680; CAS-number: 7440-05-3.", language="en"),
            ],
        },
        {
            "@id": iri("gdl-support-material"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Gas diffusion layer support precursor", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("gdl-support-material-metadata"))],
        },
        {
            "@id": iri("gdl-support-material-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Manufacturer: SGL Carbon; ID: 25BC Sigracet.", language="en"),
            ],
        },
        {
            "@id": iri("dissolved-intermediate"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Dissolved catalyst-membrane intermediate", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("dissolved-intermediate-metadata"))],
        },
        {
            "@id": iri("dissolved-intermediate-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Ratio = 70:30; viscosity = 80 Pas.", language="en"),
            ],
        },
        {
            "@id": iri("aluminum-current-collector"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Aluminum current collector", language="en")],
        },
        {
            "@id": iri("wet-doctor-bladed-mea"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Wet doctor-bladed MEA intermediate", language="en")],
        },
        {
            "@id": iri("doctor-bladed-mea"),
            "@type": [f"{H2KG}Matter", f"{H2KG}MEAAssembly"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Doctor-bladed MEA sample", language="en")],
        },
        {
            "@id": iri("mea-coupon"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Cut MEA coupon", language="en")],
        },
        {
            "@id": iri("si-wafer"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Si-wafer support", language="en")],
        },
        {
            "@id": iri("mounted-coupon"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Mounted IC-SEM intermediate", language="en")],
        },
        {
            "@id": iri("carbon-coated-copper-grid"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Carbon coated copper grid", language="en")],
        },
        {
            "@id": iri("dispersed-coupon"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Dispersed IC-SEM intermediate", language="en")],
        },
        {
            "@id": iri("ic-sem-sample"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("IC-SEM pilot sample", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("ic-sem-sample-metadata"))],
        },
        {
            "@id": iri("ic-sem-sample-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Specimen metadata from sheet: highly porous bulk material.", language="en"),
                lit("Local source context emphasizes an MEA sample with gas-diffusion-layer-focused interpretation.", language="en"),
            ],
        },
        {
            "@id": iri("procure-hispec-4000"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Procure HiSPEC 4000 precursor", language="en")],
            f"{H2KG}hasOutputMaterial": [ref(iri("hispec-4000-material"))],
        },
        {
            "@id": iri("procure-nafion-xl-membrane"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Procure Nafion XL membrane", language="en")],
            f"{H2KG}hasOutputMaterial": [ref(iri("nafion-xl-membrane"))],
        },
        {
            "@id": iri("procure-nafion-ionomer"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Procure Nafion ionomer", language="en")],
            f"{H2KG}hasOutputMaterial": [ref(iri("nafion-ionomer-material"))],
        },
        {
            "@id": iri("procure-gdl-support"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Procure gas diffusion layer support", language="en")],
            f"{H2KG}hasOutputMaterial": [ref(iri("gdl-support-material"))],
        },
        {
            "@id": iri("dissolve-step"),
            "@type": [f"{H2KG}Manufacturing"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Dissolve catalyst, membrane, and ionomer precursor mixture", language="en")],
            f"{H2KG}hasInputMaterial": [ref(iri("hispec-4000-material")), ref(iri("nafion-xl-membrane")), ref(iri("nafion-ionomer-material"))],
            f"{H2KG}hasOutputMaterial": [ref(iri("dissolved-intermediate"))],
            f"{H2KG}hasMetadata": [ref(iri("dissolve-step-metadata"))],
        },
        {
            "@id": iri("dissolve-step-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Worksheet technique label: Dissolved.", language="en")],
        },
        {
            "@id": iri("doctor-blade-coating-step"),
            "@type": [f"{H2KG}Manufacturing", f"{H2KG}DoctorBladeCoating"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Doctor blade coat dissolved intermediate on aluminum current collector", language="en")],
            f"{H2KG}hasInputMaterial": [ref(iri("dissolved-intermediate")), ref(iri("aluminum-current-collector"))],
            f"{H2KG}hasOutputMaterial": [ref(iri("wet-doctor-bladed-mea"))],
            f"{H2KG}hasMetadata": [ref(iri("doctor-blade-coating-metadata"))],
        },
        {
            "@id": iri("doctor-blade-coating-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Velocity = 1 cm/s; instrument = MICOS Blading; thickness = 1 mm.", language="en"),
            ],
        },
        {
            "@id": iri("dry-doctor-bladed-mea-step"),
            "@type": [f"{H2KG}Manufacturing"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Dry doctor-bladed MEA", language="en")],
            f"{H2KG}hasInputMaterial": [ref(iri("wet-doctor-bladed-mea"))],
            f"{H2KG}hasOutputMaterial": [ref(iri("doctor-bladed-mea"))],
            f"{H2KG}hasParameter": [ref(iri("drying-temperature-setting")), ref(iri("drying-time-setting"))],
        },
        {
            "@id": iri("cut-mea-step"),
            "@type": [f"{H2KG}Manufacturing"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Cut MEA coupon", language="en")],
            f"{H2KG}hasInputMaterial": [ref(iri("doctor-bladed-mea"))],
            f"{H2KG}hasOutputMaterial": [ref(iri("mea-coupon"))],
            f"{H2KG}hasMetadata": [ref(iri("cut-mea-metadata"))],
        },
        {
            "@id": iri("cut-mea-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Size = 5 mm2.", language="en")],
        },
        {
            "@id": iri("fix-step"),
            "@type": [f"{H2KG}Manufacturing"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Fix MEA coupon on Si-wafer support", language="en")],
            f"{H2KG}hasInputMaterial": [ref(iri("mea-coupon")), ref(iri("si-wafer"))],
            f"{H2KG}hasOutputMaterial": [ref(iri("mounted-coupon"))],
            f"{H2KG}hasMetadata": [ref(iri("fix-step-metadata"))],
        },
        {
            "@id": iri("fix-step-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("SampleHolder = Standard CSP.", language="en")],
        },
        {
            "@id": iri("dispersion-step"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Disperse mounted coupon with carbon coated copper grid", language="en")],
            f"{H2KG}hasInputMaterial": [ref(iri("mounted-coupon")), ref(iri("carbon-coated-copper-grid"))],
            f"{H2KG}hasOutputMaterial": [ref(iri("dispersed-coupon"))],
        },
        {
            "@id": iri("dry-sample-step"),
            "@type": [f"{H2KG}Manufacturing"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Dry dispersed IC-SEM sample", language="en")],
            f"{H2KG}hasInputMaterial": [ref(iri("dispersed-coupon"))],
            f"{H2KG}hasOutputMaterial": [ref(iri("ic-sem-sample"))],
            f"{H2KG}hasParameter": [ref(iri("sample-drying-time-setting"))],
        },
        {
            "@id": iri("ic-sem-measurement-001"),
            "@type": [f"{H2KG}Measurement", f"{H2KG}ICSEMImagingMeasurement"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("IC-SEM pilot measurement", language="en")],
            f"{H2KG}hasInputMaterial": [ref(iri("doctor-bladed-mea"))],
            f"{H2KG}usesInstrument": [ref(iri("ic-sem-instrument-001"))],
            f"{H2KG}hasOutputData": [ref(iri("ic-sem-raw-image-dataset"))],
            f"{H2KG}hasParameter": [
                ref(iri("temperature-setting")),
                ref(iri("relative-humidity-setting")),
                ref(iri("vacuum-pressure-setting")),
                ref(iri("dwell-time-setting")),
                ref(iri("magnification-setting")),
                ref(iri("pixel-size-setting")),
                ref(iri("measured-area-setting")),
                ref(iri("exposure-time-setting")),
                ref(iri("ion-beam-current-setting")),
                ref(iri("ion-beam-energy-setting")),
                ref(iri("electron-current-setting")),
                ref(iri("electron-beam-energy-setting")),
                ref(iri("cut-thickness-setting")),
                ref(iri("total-acquisition-time-setting")),
            ],
            f"{H2KG}hasMetadata": [ref(iri("ic-sem-acquisition-metadata")), ref(iri("source-record")), ref(iri("publication-record"))],
            f"{PROV}wasAssociatedWith": [ref(iri("author-tobias-morawietz")), ref(iri("author-andre-colliard")), ref(iri("institution-dlr")), ref(iri("funding-hi"))],
            f"{DCTERMS}source": [ref(iri("publication-record"))],
        },
        {
            "@id": iri("ic-sem-instrument-001"),
            "@type": [f"{H2KG}Instrument", f"{H2KG}ICSEMInstrument"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("IC-SEM instrument used in the pilot case", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("ic-sem-instrument-metadata"))],
        },
        {
            "@id": iri("ic-sem-instrument-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Instrument stack: FIB-SEM; FIB equipment: Jeol IB-19530CP Cross Section Polisher; SEM equipment: Jeol JSM-7200F SEM.", language="en"),
                lit("Optics: GEMINI; injection system: multi channel gas injection system GIS; ion beam type: Ar.", language="en"),
                lit("Detector: InLens, SE2; brightness: 1; contrast: 1.", language="en"),
            ],
        },
        {
            "@id": iri("ic-sem-acquisition-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Measurement type: ex-situ.", language="en"),
                lit("Specimen: highly porous bulk material; atmosphere: vacuum.", language="en"),
                lit("Calibration: adjusting lenses and apertures; adjusting the voltage.", language="en"),
                lit("Plane spacing reported in sheet: 10.", language="en"),
            ],
        },
        {
            "@id": iri("ic-sem-raw-image-dataset"),
            "@type": [f"{H2KG}Data", f"{H2KG}SEMImageDataset"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("IC-SEM raw image dataset", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("ic-sem-raw-image-metadata"))],
        },
        {
            "@id": iri("ic-sem-raw-image-metadata"),
            "@type": [f"{H2KG}Metadata"],
            f"{DCTERMS}format": [lit("tiff")],
            f"{DCTERMS}extent": [lit("50 MB"), lit("512 x 512 x 0 pixels")],
            f"{DCTERMS}source": [lit("link")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Filename: ICSEM.zip.", language="en"),
                lit("PixelPerMetric: 20.", language="en"),
            ],
        },
        {
            "@id": iri("thresholding-step"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Thresholding with Watershed", language="en")],
            f"{H2KG}hasInputData": [ref(iri("ic-sem-raw-image-dataset"))],
            f"{H2KG}hasOutputData": [ref(iri("ic-sem-thresholded-dataset"))],
            f"{H2KG}usesInstrument": [ref(f"{H2KG}FijiImageJSoftware")],
            f"{H2KG}hasMetadata": [ref(iri("thresholding-step-metadata"))],
        },
        {
            "@id": iri("thresholding-step-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Software = ImageJ; algorithm = Watershed.", language="en")],
        },
        {
            "@id": iri("ic-sem-thresholded-dataset"),
            "@type": [f"{H2KG}Data", f"{H2KG}SEMImageDataset"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("IC-SEM thresholded image dataset", language="en")],
        },
        {
            "@id": iri("scale-set-step"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Scale set preprocessing", language="en")],
            f"{H2KG}hasInputData": [ref(iri("ic-sem-thresholded-dataset"))],
            f"{H2KG}hasOutputData": [ref(iri("ic-sem-processed-image-dataset"))],
            f"{H2KG}usesInstrument": [ref(f"{H2KG}FijiImageJSoftware")],
        },
        {
            "@id": iri("ic-sem-processed-image-dataset"),
            "@type": [f"{H2KG}Data", f"{H2KG}SEMMicrographDataset", f"{H2KG}MicrostructureImageDataset"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("IC-SEM processed micrograph dataset", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("ic-sem-processed-image-metadata"))],
        },
        {
            "@id": iri("ic-sem-processed-image-metadata"),
            "@type": [f"{H2KG}Metadata"],
            f"{DCTERMS}source": [lit("github-com/ICSEM")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Mask present: yes.", language="en"),
                lit("Processed target label: Post-processed image.", language="en"),
            ],
        },
        {
            "@id": iri("layer-thickness-analysis-step"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Layer thickness analysis", language="en")],
            f"{H2KG}hasInputData": [ref(iri("ic-sem-processed-image-dataset"))],
            f"{H2KG}hasOutputData": [ref(iri("ic-sem-analysis-summary-dataset"))],
            f"{H2KG}usesInstrument": [ref(f"{H2KG}FijiImageJSoftware")],
        },
        {
            "@id": iri("porosity-analysis-step"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Porosity analysis", language="en")],
            f"{H2KG}hasInputData": [ref(iri("ic-sem-processed-image-dataset"))],
            f"{H2KG}hasOutputData": [ref(iri("ic-sem-analysis-summary-dataset"))],
            f"{H2KG}usesInstrument": [ref(f"{H2KG}FijiImageJSoftware")],
        },
        {
            "@id": iri("ic-sem-analysis-summary-dataset"),
            "@type": [f"{H2KG}Data"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("IC-SEM analysis summary dataset", language="en")],
            f"{H2KG}hasPart": [
                ref(iri("mea-thickness-datapoint")),
                ref(iri("gdl-thickness-datapoint")),
                ref(iri("total-porosity-datapoint")),
            ],
        },
        {
            "@id": iri("mea-thickness-datapoint"),
            "@type": [f"{H2KG}DataPoint"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("IC-SEM-derived MEA thickness datapoint", language="en")],
            f"{H2KG}ofProperty": [ref(f"{H2KG}MembraneElectrodeAssemblyThickness")],
            f"{H2KG}fromMeasurement": [ref(iri("ic-sem-measurement-001"))],
            f"{H2KG}hasQuantityValue": [ref(iri("mea-thickness-datapoint-qv"))],
            f"{PROV}wasGeneratedBy": [ref(iri("layer-thickness-analysis-step"))],
        },
        {
            "@id": iri("gdl-thickness-datapoint"),
            "@type": [f"{H2KG}DataPoint"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("IC-SEM-derived gas diffusion layer thickness datapoint", language="en")],
            f"{H2KG}ofProperty": [ref(f"{H2KG}GasDiffusionLayerThickness")],
            f"{H2KG}fromMeasurement": [ref(iri("ic-sem-measurement-001"))],
            f"{H2KG}hasQuantityValue": [ref(iri("gdl-thickness-datapoint-qv"))],
            f"{PROV}wasGeneratedBy": [ref(iri("layer-thickness-analysis-step"))],
        },
        {
            "@id": iri("total-porosity-datapoint"),
            "@type": [f"{H2KG}DataPoint"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("IC-SEM-derived total porosity datapoint", language="en")],
            f"{H2KG}ofProperty": [ref(f"{H2KG}TotalPorosity")],
            f"{H2KG}fromMeasurement": [ref(iri("ic-sem-measurement-001"))],
            f"{H2KG}hasQuantityValue": [ref(iri("total-porosity-datapoint-qv"))],
            f"{PROV}wasGeneratedBy": [ref(iri("porosity-analysis-step"))],
            f"{H2KG}hasMetadata": [ref(iri("total-porosity-datapoint-metadata"))],
        },
        {
            "@id": iri("total-porosity-datapoint-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Raw worksheet amount target reported as 6 pu; normalized here as a percent-style porosity datapoint.", language="en")],
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
            "@id": iri("sample-drying-time-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}DryingTime"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Sample drying time setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("sample-drying-time-setting-qv"))],
        },
        {
            "@id": iri("temperature-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}Temperature"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("IC-SEM temperature setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("temperature-setting-qv"))],
        },
        {
            "@id": iri("relative-humidity-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}RelativeHumidity"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("IC-SEM relative humidity setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("relative-humidity-setting-qv"))],
        },
        {
            "@id": iri("vacuum-pressure-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}VacuumChamberPressure"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("IC-SEM vacuum-chamber pressure setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("vacuum-pressure-setting-qv"))],
        },
        {
            "@id": iri("dwell-time-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}DwellTime"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("IC-SEM dwell-time setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("dwell-time-setting-qv"))],
        },
        {
            "@id": iri("magnification-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}Magnification"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("IC-SEM magnification setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("magnification-setting-qv"))],
        },
        {
            "@id": iri("pixel-size-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}PixelSize"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("IC-SEM pixel-size setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("pixel-size-setting-qv"))],
        },
        {
            "@id": iri("measured-area-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}MicroscopyMeasuredArea"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("IC-SEM measured-area setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("measured-area-setting-qv"))],
        },
        {
            "@id": iri("exposure-time-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}ExposureTime"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("IC-SEM exposure-time setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("exposure-time-setting-qv"))],
        },
        {
            "@id": iri("ion-beam-current-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}IonBeamCurrent"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("IC-SEM ion-beam current setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("ion-beam-current-setting-qv"))],
        },
        {
            "@id": iri("ion-beam-energy-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}IonBeamEnergy"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("IC-SEM ion-beam energy setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("ion-beam-energy-setting-qv"))],
        },
        {
            "@id": iri("electron-current-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}ElectronCurrent"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("IC-SEM electron current setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("electron-current-setting-qv"))],
        },
        {
            "@id": iri("electron-beam-energy-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}ElectronBeamEnergy"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("IC-SEM electron-beam energy setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("electron-beam-energy-setting-qv"))],
        },
        {
            "@id": iri("cut-thickness-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}CutThickness"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("IC-SEM cut-thickness setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("cut-thickness-setting-qv"))],
        },
        {
            "@id": iri("total-acquisition-time-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}TotalAcquisitionTime"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("IC-SEM total acquisition time setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("total-acquisition-time-setting-qv"))],
        },
        qv("drying-temperature-setting-qv", "80", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/ThermodynamicTemperature", f"{UNIT}DEG_C"),
        qv("drying-time-setting-qv", "16", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/Time", f"{UNIT}HR"),
        qv("sample-drying-time-setting-qv", "24", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/Time", f"{UNIT}HR"),
        qv("temperature-setting-qv", "25", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/ThermodynamicTemperature", f"{UNIT}DEG_C"),
        qv("relative-humidity-setting-qv", "0", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/RelativeHumidity", f"{UNIT}PERCENT"),
        qv("vacuum-pressure-setting-qv", "1.0e-6", f"{XSD}double", "http://qudt.org/vocab/quantitykind/Pressure", f"{UNIT}ATM"),
        qv("dwell-time-setting-qv", "12", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/Time", f"{UNIT}HR"),
        qv("magnification-setting-qv", "10", f"{XSD}integer", "http://qudt.org/vocab/quantitykind/Dimensionless", f"{UNIT}UNITLESS"),
        qv("pixel-size-setting-qv", "20", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/Length", f"{UNIT}NanoM"),
        qv("measured-area-setting-qv", "20", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/Area", f"{UNIT}MicroM2"),
        qv("exposure-time-setting-qv", "60", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/Time", f"{UNIT}SEC"),
        qv("ion-beam-current-setting-qv", "700", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/ElectricCurrent", f"{UNIT}PicoA"),
        qv("ion-beam-energy-setting-qv", "6", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/ElectricPotential", f"{UNIT}KiloV"),
        qv("electron-current-setting-qv", "250", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/ElectricCurrent", f"{UNIT}PicoA"),
        qv("electron-beam-energy-setting-qv", "1.5", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/ElectricPotential", f"{UNIT}KiloV"),
        qv("cut-thickness-setting-qv", "150", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/Length", f"{UNIT}NanoM"),
        qv("total-acquisition-time-setting-qv", "12", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/Time", f"{UNIT}HR"),
        qv("mea-thickness-datapoint-qv", "80", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/Length", f"{UNIT}NanoM"),
        qv("gdl-thickness-datapoint-qv", "160", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/Length", f"{UNIT}NanoM"),
        qv("total-porosity-datapoint-qv", "6", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/PorosityPercent", f"{UNIT}PERCENT"),
    ]
    return items


def _ic_sem_validation_note() -> str:
    return """# IC-SEM Validation Note

- New public ontology terms introduced in this round:
  - `h2kg:ICSEMImagingMeasurement`
  - `h2kg:ICSEMInstrument`
  - `h2kg:MembraneElectrodeAssemblyThickness`
  - `h2kg:PixelSize`
- Existing terms deliberately reused:
  - `h2kg:GasDiffusionLayerThickness`
  - `h2kg:TotalPorosity`
  - `h2kg:Magnification`
  - `h2kg:Temperature`
  - `h2kg:RelativeHumidity`
  - `h2kg:VacuumChamberPressure`
  - `h2kg:DwellTime`
  - `h2kg:MicroscopyMeasuredArea`
  - `h2kg:ExposureTime`
  - `h2kg:IonBeamCurrent`
  - `h2kg:IonBeamEnergy`
  - `h2kg:ElectronCurrent`
  - `h2kg:ElectronBeamEnergy`
  - `h2kg:CutThickness`
  - `h2kg:TotalAcquisitionTime`
  - `h2kg:SEMImageDataset`
  - `h2kg:SEMMicrographDataset`
  - `h2kg:MicrostructureImageDataset`
- Worksheet-specific steps such as `Cut`, `Fix`, `Dispersion`, `Thresholding`, `Scale set`, and `Layer thickness measurement` remain labeled process instances rather than public TBox terms.
- Instrument details, detector names, publication metadata, filenames, and dimensional metadata remain attached through `h2kg:hasMetadata`.
"""


def _ic_sem_case_summary() -> str:
    return """# IC-SEM Case Summary

This pilot shows how H2KG captures an ion-cut scanning electron microscopy characterization route for a PEMFC membrane-electrode-assembly context without promoting worksheet-specific operational labels into the public TBox. The public ontology layer centers on `h2kg:ICSEMImagingMeasurement`, `h2kg:ICSEMInstrument`, `h2kg:PixelSize`, and `h2kg:MembraneElectrodeAssemblyThickness`, while reusing the established SEM/FIB-style acquisition parameters and data-dataset terms.

The example graph follows an end-to-end chain from material and doctor-blade preparation through IC-SEM acquisition, image preprocessing, ImageJ-supported analysis, and measurement-derived datapoints. The final semantic outputs are an MEA-thickness datapoint, a gas-diffusion-layer-thickness datapoint, and a total-porosity datapoint, all linked back to the same IC-SEM measurement context and accompanied by publication, acquisition, and file metadata.
"""


def _ic_sem_follow_on_gaps() -> str:
    return """# IC-SEM Follow-On Gaps

- Consider whether `plane spacing` deserves promotion as a reusable microscopy parameter after more cross-sectional imaging rounds.
- Revisit whether `Gas Diffusion Layer` should become a local H2KG node rather than remaining an imported or metadata-level anchor in imaging cases.
- Revisit whether detector families, brightness/contrast controls, and imaging-mode descriptors recur strongly enough to justify public ontology terms.
- Revisit whether thickness-analysis process families should stay generic `h2kg:Process` instances or be promoted after multiple microscopy rounds.
"""


def _ic_sem_manuscript_figure() -> str:
    return """# IC-SEM Manuscript Figure Guidance

Use a combined ontology-workflow figure with **TBox-only standalone nodes** and worksheet-derived values shown only as annotations or metadata callouts.

Recommended backbone:

`Matter -> Manufacturing -> IC-SEM Imaging Measurement -> SEM Image Dataset -> Process (thresholding / scale set) -> SEM Micrograph Dataset -> Process (analysis) -> DataPoint -> {Membrane Electrode Assembly Thickness, Gas Diffusion Layer Thickness, Total Porosity}`

Supporting families:

- Above acquisition:
  - `Temperature`
  - `Relative Humidity`
  - `Vacuum Chamber Pressure`
  - `Dwell Time`
  - `Magnification`
  - `Pixel Size`
  - `Microscopy Measured Area`
  - `Exposure Time`
  - `Ion Beam Current`
  - `Ion Beam Energy`
  - `Electron Current`
  - `Electron Beam Energy`
  - `Cut Thickness`
  - `Total Acquisition Time`
- Below acquisition:
  - `IC-SEM Instrument`
- Below preprocessing and analysis:
  - `Fiji ImageJ Software`
- Metadata callouts:
  - sample context
  - acquisition context
  - instrument metadata
  - raw/processed dataset metadata
  - publication/provenance metadata
"""


def _ic_sem_manuscript_table() -> str:
    return """# IC-SEM Manuscript Companion Table

| IC-SEM case element | H2KG ontology anchor | Example case value | Figure treatment |
| --- | --- | --- | --- |
| Sample context | `h2kg:Matter` | doctor-bladed MEA sample | standalone ontology node |
| Coating route | `h2kg:DoctorBladeCoating` | doctor blade | standalone ontology node |
| Drying controls | `h2kg:DryingTemperature`, `h2kg:DryingTime` | 80 °C; 16 h | parameter callout |
| Measurement route | `h2kg:ICSEMImagingMeasurement` | IC-SEM | standalone ontology node |
| Instrument | `h2kg:ICSEMInstrument` | Jeol cross-section polisher + SEM stack | standalone ontology node with metadata callout |
| Acquisition geometry | `h2kg:CutThickness`, `h2kg:MicroscopyMeasuredArea`, `h2kg:PixelSize` | 150 nm; 20 um2; 20 nm | parameter callout |
| Beam settings | `h2kg:IonBeamCurrent`, `h2kg:IonBeamEnergy`, `h2kg:ElectronCurrent`, `h2kg:ElectronBeamEnergy` | 700 pA; 6 keV; 250 pA; 1.5 keV | parameter callout |
| Acquisition timing | `h2kg:DwellTime`, `h2kg:ExposureTime`, `h2kg:TotalAcquisitionTime` | 12 h; 60 s; 12 h | parameter callout |
| Environment | `h2kg:Temperature`, `h2kg:RelativeHumidity`, `h2kg:VacuumChamberPressure` | 25 °C; 0 %; 10^-6 atm | parameter callout |
| Raw data | `h2kg:SEMImageDataset` | ICSEM.zip | standalone ontology node |
| Preprocessing | `h2kg:Process` | thresholding; scale set | standalone ontology node with annotation |
| Processed data | `h2kg:SEMMicrographDataset`, `h2kg:MicrostructureImageDataset` | post-processed image | standalone ontology node |
| Analysis | `h2kg:Process` | layer-thickness analysis; porosity analysis | standalone ontology node with annotation |
| Thickness result | `h2kg:MembraneElectrodeAssemblyThickness` | 80 nm | final property node via datapoint |
| GDL result | `h2kg:GasDiffusionLayerThickness` | 160 nm | final property node via datapoint |
| Porosity result | `h2kg:TotalPorosity` | 6 pu | final property node via datapoint |
| Software | `h2kg:FijiImageJSoftware` | ImageJ | supporting ontology node |
| Provenance | `h2kg:Metadata` + `h2kg:hasMetadata` | DOI, authors, file details | metadata callout |
"""


def _ic_sem_readme(generated_files: list[Path]) -> str:
    file_list = "\n".join(f"- `{path.name}`" for path in generated_files)
    return f"""# IC-SEM Pilot Package

This package demonstrates the controlled H2KG integration of the IC-SEM worksheet as a reusable ontology-guided case.

Generated files:

{file_list}

Key public ontology additions for this round:

- `h2kg:ICSEMImagingMeasurement`
- `h2kg:ICSEMInstrument`
- `h2kg:MembraneElectrodeAssemblyThickness`
- `h2kg:PixelSize`

The example graph keeps worksheet-specific operational labels at instance level while the public Explore-ready vocabulary remains TBox-only.
"""


def _missing_terms_note(missing: list[str]) -> str:
    bullets = "\n".join(f"- `{term}`" for term in missing)
    return f"""# IC-SEM Pilot Package

The IC-SEM pilot package was not generated because the current ontology source is missing required local terms.

Missing terms:

{bullets}
"""
