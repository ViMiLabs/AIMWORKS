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
FIB_SEM_EXAMPLE_NS = "https://w3id.org/h2kg/examples/fib-sem#"

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
    f"{H2KG}Temperature",
    f"{H2KG}RelativeHumidity",
    f"{H2KG}VacuumChamberPressure",
    f"{H2KG}DwellTime",
    f"{H2KG}Magnification",
    f"{H2KG}VoxelSize",
    f"{H2KG}MicroscopyMeasuredArea",
    f"{H2KG}ExposureTime",
    f"{H2KG}PoreSizeDistribution",
    f"{H2KG}AveragePoreSize",
    f"{H2KG}LargePoreFractionAbove150nm",
    f"{H2KG}NanoscalePoreSizeMin",
    f"{H2KG}NanoscalePoreSizeMax",
    f"{H2KG}MesoporeDiameter",
    f"{H2KG}PoreSizeDistributionPeakDiameter",
    f"{H2KG}PoreSizeDistributionDataset",
    f"{H2KG}PoreVolumeFraction",
    f"{H2KG}TotalPorosity",
    f"{H2KG}CatalystLayerPorosity",
    f"{H2KG}FijiImageJSoftware",
    f"{H2KG}SEMImageDataset",
    f"{H2KG}MicrostructureImageDataset",
    f"{H2KG}FIBSEMTomographyMeasurement",
    f"{H2KG}FIBSEMInstrument",
    f"{H2KG}IonBeamCurrent",
    f"{H2KG}IonBeamEnergy",
    f"{H2KG}ElectronCurrent",
    f"{H2KG}ElectronBeamEnergy",
    f"{H2KG}CutThickness",
    f"{H2KG}SliceNumber",
    f"{H2KG}StageTilt",
    f"{H2KG}TotalAcquisitionTime",
    f"{H2KG}Constrictivity",
    f"{H2KG}GeodesicTortuosity",
}


def build_fib_sem_pilot_package(
    input_path: str | Path,
    output_root: str | Path,
) -> dict[str, Any]:
    input_path = Path(input_path)
    output_root = Path(output_root)
    target_dir = ensure_dir(output_root / "examples" / "fib_sem_pilot")
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

    mapping_rows = _fib_sem_mapping_rows()
    example_items = _fib_sem_example_items()
    generated_files = [
        _write_mapping_matrix(target_dir / "fib_sem_mapping_matrix.csv", mapping_rows),
        _write_mapping_matrix_markdown(target_dir / "fib_sem_mapping_matrix.md", mapping_rows),
        dump_json(
            target_dir / "fib_sem_example.jsonld",
            {"@context": {**COMMON_CONTEXT, "fibsem": FIB_SEM_EXAMPLE_NS}, "@graph": example_items},
        ),
        dump_turtle_items(target_dir / "fib_sem_example.ttl", example_items),
        write_text(target_dir / "fib_sem_validation_note.md", _fib_sem_validation_note()),
        write_text(target_dir / "fib_sem_case_summary.md", _fib_sem_case_summary()),
        write_text(target_dir / "fib_sem_follow_on_gaps.md", _fib_sem_follow_on_gaps()),
    ]
    write_text(target_dir / "README.md", _fib_sem_readme(generated_files))
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
        "# FIB-SEM Mapping Matrix",
        "",
        "This matrix accounts for each populated FIB-SEM sheet field and classifies it as `reuse existing term`, `new ontology term`, `instance metadata`, or `not modeled` for the controlled pilot round.",
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


def _fib_sem_mapping_rows() -> list[dict[str, str]]:
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
        ("ExperimentTitle", "FIB tomography of NMC111 electrode", "instance metadata", "h2kg:hasMetadata + dcterms:title", "Stored on the source-record metadata node."),
        ("ExperimentID", "7", "instance metadata", "h2kg:hasMetadata + h2kg:hasIdentifier", "Stored as a literal identifier on the source-record metadata node."),
        ("Measurement-ID", "Run derived DOI", "instance metadata", "h2kg:hasMetadata + h2kg:hasIdentifier", "Stored as a literal identifier on the measurement metadata node."),
        ("UploadDate", "2021-12-15", "instance metadata", "h2kg:hasMetadata + dcterms:date", "Stored as a normalized upload-date literal on the source record."),
        ("MeasurementDate", "", "not modeled", "-", "No value was present in the FIB-SEM sheet."),
        ("Institution", "HZB", "instance metadata", "prov:Agent", "Represented as an institutional agent instance."),
        ("FoundingBody", "Helmholtz Imaging (HI)", "instance metadata", "prov:Agent", "Represented as a funding-body agent instance."),
        ("Country", "Germany", "instance metadata", "h2kg:hasMetadata", "Retained as contextual metadata on the source record."),
        ("Author", "Markus Osenberg; Andre Colliard", "instance metadata", "prov:Agent", "Represented as author agent instances linked from the source record and publication metadata."),
        ("ORCID", "123-465-7123; 321-321-3211", "instance metadata", "h2kg:hasMetadata", "Stored on author metadata nodes."),
        ("Email", "mark.osen@hzb.de; andyhuebsch@gmail.mx", "instance metadata", "h2kg:hasMetadata", "Stored on author metadata nodes."),
        ("Published", "TRUE", "instance metadata", "h2kg:hasMetadata", "Retained as publication-status metadata."),
        ("Publication", "FIB tomography of NMC111 electrode", "instance metadata", "h2kg:hasMetadata + dcterms:title", "Stored on a publication metadata node."),
        ("DOI", "https://doi.org/10.3390/1077778", "instance metadata", "h2kg:hasMetadata + dcterms:identifier", "Stored on a publication metadata node."),
        ("Journal", "Nature Communications", "instance metadata", "h2kg:hasMetadata", "Retained as bibliographic metadata."),
        ("Volume", "12", "instance metadata", "h2kg:hasMetadata", "Retained as bibliographic metadata."),
        ("Issue", "4", "instance metadata", "h2kg:hasMetadata", "Retained as bibliographic metadata."),
        ("Pages", "123-321", "instance metadata", "h2kg:hasMetadata", "Retained as bibliographic metadata."),
        ("PublicationDate", "2021-09-17", "instance metadata", "h2kg:hasMetadata + dcterms:issued", "Stored as a normalized issued-date literal on the publication metadata node."),
        ("Topic", "Battery", "instance metadata", "h2kg:hasMetadata", "Retained as thematic metadata."),
        ("Device", "Lithium-ion battery", "instance metadata", "h2kg:hasMetadata", "Retained as application-context metadata."),
        ("Component", "Electrode", "instance metadata", "h2kg:hasMetadata", "Retained as component-context metadata."),
        ("Subcomponent", "-", "not modeled", "-", "The sheet explicitly reports no subcomponent value."),
        ("Granularity Level", "Nanostructure", "instance metadata", "h2kg:hasMetadata", "Retained as scale/granularity metadata."),
        ("Format", "tiff", "instance metadata", "h2kg:hasMetadata + dcterms:format", "Stored on raw-dataset metadata."),
        ("FileSize", "1250", "instance metadata", "h2kg:hasMetadata + dcterms:extent", "Stored with file-size unit in dataset metadata."),
        ("FileSizeUnit", "MB", "instance metadata", "h2kg:hasMetadata + dcterms:extent", "Stored with file size in dataset metadata."),
        ("FileName", "batNMC111.zip", "instance metadata", "h2kg:hasMetadata", "Stored on raw-dataset metadata."),
        ("DimensionX", "1024", "instance metadata", "h2kg:hasMetadata", "Stored on raw-dataset metadata."),
        ("DimensionY", "1024", "instance metadata", "h2kg:hasMetadata", "Stored on raw-dataset metadata."),
        ("DimensionZ", "1000", "instance metadata", "h2kg:hasMetadata", "Stored on raw-dataset metadata."),
        ("PixelPerMetric", "14", "instance metadata", "h2kg:hasMetadata", "Stored on raw-dataset metadata."),
        ("Link", "link", "instance metadata", "h2kg:hasMetadata + dcterms:source", "Stored as source/link metadata."),
        ("MaskExist", "yes", "instance metadata", "h2kg:hasMetadata", "Stored on processed-dataset metadata."),
        ("MaskLink", "github-com/FIB-SEM_NMC", "instance metadata", "h2kg:hasMetadata + dcterms:source", "Stored on processed-dataset metadata."),
    ]
    for field, value, classification, anchor, note in org_fields:
        add("org", field, value, classification, anchor, note)

    syn_fields = [
        ("Step 1 Precursor", "PTMA", "instance metadata", "h2kg:Matter", "Represented as a material instance with procurement metadata."),
        ("Step 1 Technique", "Buy", "reuse existing term", "h2kg:Process", "Modeled as a labeled procurement process instance rather than a new TBox term."),
        ("Step 1 Condition", "Manufacturer = SigmaAldrich; lot number = 205680; CAS-number = 7440-05-3", "instance metadata", "h2kg:hasMetadata", "Stored on the PTMA material metadata node."),
        ("Step 1 Target", "SInt1", "instance metadata", "h2kg:Matter", "Represents the procured PTMA material instance."),
        ("Step 2 Precursor", "SuperP", "instance metadata", "h2kg:Matter", "Represented as a material instance with procurement metadata."),
        ("Step 2 Technique", "Buy", "reuse existing term", "h2kg:Process", "Modeled as a labeled procurement process instance rather than a new TBox term."),
        ("Step 2 Condition", "Manufacturer = SigmaAldrich; lot number = 205680; CAS-number = 7440-05-3", "instance metadata", "h2kg:hasMetadata", "Stored on the SuperP material metadata node."),
        ("Step 2 Target", "SInt2", "instance metadata", "h2kg:Matter", "Represents the procured SuperP material instance."),
        ("Step 3 Precursor", "PVdF", "instance metadata", "h2kg:Matter", "Represented as a material instance with procurement metadata."),
        ("Step 3 Technique", "Buy", "reuse existing term", "h2kg:Process", "Modeled as a labeled procurement process instance rather than a new TBox term."),
        ("Step 3 Condition", "Manufacturer = SigmaAldrich; lot number = 205680; CAS-number = 7440-05-3", "instance metadata", "h2kg:hasMetadata", "Stored on the PVdF material metadata node."),
        ("Step 3 Target", "Nafion ionomer", "instance metadata", "h2kg:hasMetadata", "The source sheet reports a target label inconsistent with the PVdF precursor; the normalized example keeps the raw value as metadata."),
        ("Step 4 Precursor A", "SInt1", "instance metadata", "h2kg:hasInputMaterial", "Connected as one input material to the dissolve step."),
        ("Step 4 Precursor B", "SInt2", "instance metadata", "h2kg:hasInputMaterial", "Connected as one input material to the dissolve step."),
        ("Step 4 Precursor C", "SInt3", "instance metadata", "h2kg:hasMetadata", "The source sheet references SInt3 as an input before it is coherently defined; preserved as source metadata in the pilot note."),
        ("Step 4 Precursor D", "NMP", "instance metadata", "h2kg:Matter", "Represented as an NMP solvent material instance."),
        ("Step 4 AmountPrecursor", "25 mL", "instance metadata", "h2kg:hasMetadata", "Stored as solvent metadata on the NMP input material."),
        ("Step 4 Technique", "Dissolve", "reuse existing term", "h2kg:Manufacturing", "Modeled as a labeled manufacturing process instance rather than a new TBox term."),
        ("Step 4 Condition", "Ratio = 70:20:10; Viscosity = 80 Pas", "instance metadata", "h2kg:hasMetadata", "Retained as slurry-formation metadata in round 1."),
        ("Step 5 Precursor", "SInt4", "instance metadata", "h2kg:hasMetadata", "The source sheet uses an intermediate identifier that is normalized into a coherent slurry output in the example graph."),
        ("Step 5 Additional Input", "Aluminum current collector", "instance metadata", "h2kg:hasInputMaterial", "Connected as an input material to the doctor-blade coating step."),
        ("Step 5 Technique", "Doctor blade", "reuse existing term", "h2kg:Manufacturing", "Modeled as a labeled manufacturing process instance rather than a new TBox term."),
        ("Step 5 Condition", "Velocity = 1 cm/s; Instrument = MICOS Blading; Thickness = 1 mm", "instance metadata", "h2kg:hasMetadata", "Retained as coating metadata in round 1."),
        ("Step 5 Target", "SInt3", "instance metadata", "h2kg:hasMetadata", "The source sheet target identifier is inconsistent with downstream use; the normalized example records the raw identifier as metadata."),
        ("Step 6 Precursor", "SInt5", "instance metadata", "h2kg:hasMetadata", "The source sheet references SInt5 without a coherent prior target; the example graph normalizes it to the wet electrode intermediate."),
        ("Step 6 Technique", "Dry", "reuse existing term", "h2kg:Manufacturing", "Modeled as a labeled manufacturing process instance with explicit drying parameters."),
        ("Step 6 Condition", "Temperature = 80 deg C; Time = 16 h", "instance metadata", "h2kg:hasMetadata", "Retained as drying metadata because no dedicated battery-electrode drying profile is promoted in this round."),
        ("Step 6 Target", "Cathode electrode", "instance metadata", "h2kg:Matter", "Represents the dried electrode material used for FIB-SEM sample preparation."),
    ]
    for field, value, classification, anchor, note in syn_fields:
        add("syn", field, value, classification, anchor, note)

    sp_fields = [
        ("Step 1 Precursor", "Cathode electrode", "instance metadata", "h2kg:Matter", "Uses the prepared electrode material as sample-preparation input."),
        ("Step 1 Technique", "Cut", "reuse existing term", "h2kg:Manufacturing", "Modeled as a labeled manufacturing process instance rather than a new TBox term."),
        ("Step 1 Condition", "Size = 3 mm2", "instance metadata", "h2kg:hasMetadata", "Retained as cut-size metadata."),
        ("Step 1 Target", "SPInt1", "instance metadata", "h2kg:Matter", "Represents the cut electrode coupon."),
        ("Step 2 Precursor A", "SPInt1", "instance metadata", "h2kg:hasInputMaterial", "Connected as one input to the fixing step."),
        ("Step 2 Precursor B", "Aluminum pin stub", "instance metadata", "h2kg:Matter", "Represented as an auxiliary mounting material instance."),
        ("Step 2 AmountPrecursor B", "12.5 mm", "instance metadata", "h2kg:hasMetadata", "Stored as mounting-material metadata."),
        ("Step 2 Precursor C", "Conductive silver", "instance metadata", "h2kg:Matter", "Represented as an auxiliary conductive mounting material instance."),
        ("Step 2 Technique", "Fix", "reuse existing term", "h2kg:Manufacturing", "Modeled as a labeled manufacturing process instance rather than a new TBox term."),
        ("Step 2 Condition", "Time = 8 h", "instance metadata", "h2kg:hasMetadata", "Retained as fixing metadata."),
        ("Step 2 Target", "SPInt2", "instance metadata", "h2kg:Matter", "Represents the mounted sample intermediate."),
        ("Step 3 Precursor A", "SPInt2", "instance metadata", "h2kg:hasInputMaterial", "Connected as one input to the Pt deposition step."),
        ("Step 3 Precursor B", "Pt", "instance metadata", "h2kg:Matter", "Represented as the deposited protective material."),
        ("Step 3 Technique", "Deposit", "reuse existing term", "h2kg:Manufacturing", "Modeled as a labeled manufacturing process instance rather than a new TBox term."),
        ("Step 3 Condition", "Thickness = 0.5 um; Area = 15 um2", "instance metadata", "h2kg:hasMetadata", "Retained as deposition metadata."),
        ("Step 3 Target", "SPInt3", "instance metadata", "h2kg:Matter", "Represents the Pt-protected sample intermediate."),
        ("Step 4 Precursor", "SPInt3", "instance metadata", "h2kg:hasInputMaterial", "Connected as input to the electron-beam polishing step."),
        ("Step 4 Technique", "Electron beam", "reuse existing term", "h2kg:Process", "Modeled as a labeled process instance rather than a new TBox term."),
        ("Step 4 Condition", "Temperature = 50 deg C; Time = 10 min; Current = 250 pA; Energy = 5 keV", "instance metadata", "h2kg:hasMetadata", "Retained as polishing metadata while the reusable current and energy anchors are attached at measurement level."),
        ("Step 4 Target", "SPInt4", "instance metadata", "h2kg:Matter", "Represents the electron-beam-polished sample intermediate."),
        ("Step 5 Precursor", "SPInt4", "instance metadata", "h2kg:hasInputMaterial", "Connected as input to the gallium milling step."),
        ("Step 5 Technique", "Gallium current", "reuse existing term", "h2kg:Process", "Modeled as a labeled process instance rather than a new TBox term."),
        ("Step 5 Condition", "Temperature = 50 deg C; Time = 30 min; Current = 300 pA; Energy = 30 keV", "instance metadata", "h2kg:hasMetadata", "Retained as milling metadata while reusable current and energy anchors are attached at measurement level."),
        ("Step 5 Target", "Sample", "instance metadata", "h2kg:Matter", "Represents the final FIB-SEM sample material instance."),
    ]
    for field, value, classification, anchor, note in sp_fields:
        add("sp", field, value, classification, anchor, note)

    char_fields = [
        ("MeasurementMethod", "FIB-SEM", "reuse existing term", "h2kg:FIBSEMTomographyMeasurement", "Defines the pilot measurement instance type."),
        ("MeasurementType", "ex-situ", "instance metadata", "h2kg:hasMetadata", "Retained as measurement-context metadata in round 1."),
        ("Specimen", "highly porous bulk material", "instance metadata", "h2kg:hasMetadata", "Retained as specimen-context metadata in round 1."),
        ("Characterization environment", "", "not modeled", "-", "No value was present in the FIB-SEM sheet."),
        ("Temperature", "23 C", "reuse existing term", "h2kg:Temperature", "Modeled as a parameter-setting instance linked to the FIB-SEM measurement."),
        ("Humidity", "0 %", "reuse existing term", "h2kg:RelativeHumidity", "Modeled as a parameter-setting instance linked to the FIB-SEM measurement."),
        ("Atmosphere", "Vacuum", "instance metadata", "h2kg:hasMetadata", "Retained as measurement metadata in round 1."),
        ("Pressure", "10^-5 atm", "reuse existing term", "h2kg:VacuumChamberPressure", "Modeled as a parameter-setting instance linked to the FIB-SEM measurement."),
        ("Calibration", "adjusting lenses and apertures; adjusting the voltage", "instance metadata", "h2kg:hasMetadata", "Retained as calibration metadata in round 1."),
    ]
    for field, value, classification, anchor, note in char_fields:
        add("char", field, value, classification, anchor, note)

    inst_fields = [
        ("Instrument", "FIB-SEM", "new ontology term", "h2kg:FIBSEMInstrument", "Introduced as a reusable instrument anchor for focused ion beam SEM tomography."),
        ("FIBEquipment", "ZEISS Crossbeam 340", "instance metadata", "h2kg:hasMetadata", "Stored as instrument metadata."),
        ("SEMEquipment", "-", "not modeled", "-", "The sheet explicitly reports no separate SEM equipment value."),
        ("Optics", "GEMINI", "instance metadata", "h2kg:hasMetadata", "Stored as instrument metadata."),
        ("InjectedElement", "Pt", "instance metadata", "h2kg:hasMetadata", "Stored as instrument metadata."),
        ("InjectionSystem", "multi channel gas injection system GIS", "instance metadata", "h2kg:hasMetadata", "Stored as instrument metadata."),
        ("IonBeamType", "Ga", "instance metadata", "h2kg:hasMetadata", "Stored as instrument metadata."),
        ("IonBeamCurrent", "700 pA", "new ontology term", "h2kg:IonBeamCurrent", "Introduced as a reusable acquisition parameter."),
        ("IonBeamEnergy", "30 keV", "new ontology term", "h2kg:IonBeamEnergy", "Introduced as a reusable acquisition parameter."),
        ("PlaneSpacing", "10", "instance metadata", "h2kg:hasMetadata", "Retained as acquisition metadata in round 1."),
        ("MeasuredArea", "20 um2", "reuse existing term", "h2kg:MicroscopyMeasuredArea", "Mapped conservatively to the existing microscopy measured-area anchor."),
        ("CutThickness", "150 nm", "new ontology term", "h2kg:CutThickness", "Introduced as a reusable acquisition parameter."),
        ("SliceNumber", "1300", "new ontology term", "h2kg:SliceNumber", "Introduced as a reusable acquisition parameter."),
        ("DwellTime", "3 h", "reuse existing term", "h2kg:DwellTime", "Reused as a generic dwell/residence-time acquisition anchor."),
        ("Imaging technique", "", "not modeled", "-", "No value was present in the FIB-SEM sheet."),
        ("Detector", "InLens, SE2", "instance metadata", "h2kg:hasMetadata", "Stored as instrument metadata."),
        ("ElectronCurrent", "250 pA", "new ontology term", "h2kg:ElectronCurrent", "Introduced as a reusable acquisition parameter."),
        ("ElectronBeamEnergy", "1.50 keV", "new ontology term", "h2kg:ElectronBeamEnergy", "Introduced as a reusable acquisition parameter."),
        ("PixelSize", "20 nm", "reuse existing term", "h2kg:VoxelSize", "Mapped conservatively to the existing tomography voxel-size anchor."),
        ("Magnification", "10", "reuse existing term", "h2kg:Magnification", "Reused as an imaging magnification parameter."),
        ("Positioning coordinates", "", "not modeled", "-", "No value was present in the FIB-SEM sheet."),
        ("TiltCompensation", "36", "instance metadata", "h2kg:hasMetadata", "Retained as acquisition metadata in round 1."),
        ("StageTilt", "54", "new ontology term", "h2kg:StageTilt", "Introduced as a reusable acquisition parameter."),
        ("DynamicFocus", "-3", "instance metadata", "h2kg:hasMetadata", "Retained as acquisition metadata in round 1."),
        ("DriftCompensation", "False", "instance metadata", "h2kg:hasMetadata", "Retained as acquisition metadata in round 1."),
        ("Brightness", "1", "instance metadata", "h2kg:hasMetadata", "Retained as acquisition metadata in round 1."),
        ("Contrast", "1", "instance metadata", "h2kg:hasMetadata", "Retained as acquisition metadata in round 1."),
        ("ImageAcquisitionTime", "60 s", "reuse existing term", "h2kg:ExposureTime", "Mapped conservatively to the existing exposure-time anchor."),
        ("TotalAcquisitionTime", "12 h", "new ontology term", "h2kg:TotalAcquisitionTime", "Introduced as a reusable acquisition parameter."),
    ]
    for field, value, classification, anchor, note in inst_fields:
        add("inst", field, value, classification, anchor, note)

    pre_fields = [
        ("Step 1 Precursor", "RawData", "instance metadata", "h2kg:SEMImageDataset", "Mapped to the raw FIB-SEM image-stack dataset."),
        ("Step 1 Technique", "DriftCorrect", "reuse existing term", "h2kg:Process", "Modeled as a labeled preprocessing process instance rather than a new TBox term."),
        ("Step 1 Software", "SIFT", "instance metadata", "h2kg:hasMetadata", "Retained as preprocessing-software metadata in round 1."),
        ("Step 1 Target", "PPInt1", "instance metadata", "h2kg:MicrostructureImageDataset", "Mapped to the drift-corrected image-stack dataset."),
        ("Step 2 Precursor", "PPInt1", "instance metadata", "h2kg:MicrostructureImageDataset", "Uses the drift-corrected dataset as input."),
        ("Step 2 Technique", "3D Reconstruct", "reuse existing term", "h2kg:Process", "Modeled as a labeled preprocessing process instance rather than a new TBox term."),
        ("Step 2 Software", "Astra toolbox", "instance metadata", "h2kg:hasMetadata", "Retained as preprocessing-software metadata in round 1."),
        ("Step 2 Target", "PPInt2", "instance metadata", "h2kg:MicrostructureImageDataset", "Mapped to the reconstructed-volume dataset."),
        ("Step 3 Precursor", "PPInt2", "instance metadata", "h2kg:MicrostructureImageDataset", "Uses the reconstructed-volume dataset as input."),
        ("Step 3 Technique", "Artefact remove", "reuse existing term", "h2kg:Process", "Modeled as a labeled preprocessing process instance rather than a new TBox term."),
        ("Step 3 Software", "In-house 3D Unet", "instance metadata", "h2kg:hasMetadata", "Retained as preprocessing-software metadata in round 1."),
        ("Step 3 Target", "PPInt3", "instance metadata", "h2kg:MicrostructureImageDataset", "Mapped to the artefact-cleaned volume dataset."),
        ("Step 4 Precursor", "PPInt3", "instance metadata", "h2kg:MicrostructureImageDataset", "Uses the artefact-cleaned dataset as input."),
        ("Step 4 Technique", "Clean", "reuse existing term", "h2kg:Process", "Modeled as a labeled preprocessing process instance rather than a new TBox term."),
        ("Step 4 Software", "ImageJ", "reuse existing term", "h2kg:FijiImageJSoftware", "The cleanup process reuses the existing software instrument anchor."),
        ("Step 4 Target", "PPInt4", "instance metadata", "h2kg:MicrostructureImageDataset", "Mapped to the cleaned volume dataset."),
        ("Step 5 Precursor", "PPInt4", "instance metadata", "h2kg:MicrostructureImageDataset", "Uses the cleaned dataset as input."),
        ("Step 5 Technique", "Threshold", "reuse existing term", "h2kg:Process", "Modeled as a labeled preprocessing process instance rather than a new TBox term."),
        ("Step 5 Condition", "Algorithm = Watershed", "instance metadata", "h2kg:hasMetadata", "Retained as thresholding metadata in round 1."),
        ("Step 5 Software", "ImageJ", "reuse existing term", "h2kg:FijiImageJSoftware", "The thresholding process reuses the existing software instrument anchor."),
        ("Step 5 Target", "PPInt5", "instance metadata", "h2kg:MicrostructureImageDataset", "Mapped to the segmented volume dataset."),
        ("Step 6 Precursor", "PPInt5", "instance metadata", "h2kg:MicrostructureImageDataset", "Uses the segmented dataset as input."),
        ("Step 6 Technique", "Visualize", "reuse existing term", "h2kg:Process", "Modeled as a labeled preprocessing process instance rather than a new TBox term."),
        ("Step 6 Software", "Blender3D", "instance metadata", "h2kg:hasMetadata", "Retained as visualization-software metadata in round 1."),
        ("Step 6 Target", "Post-processed image", "instance metadata", "h2kg:MicrostructureImageDataset", "Mapped to the final processed FIB-SEM microstructure image dataset."),
    ]
    for field, value, classification, anchor, note in pre_fields:
        add("pre", field, value, classification, anchor, note)

    anal_fields = [
        ("Step 1 Precursor", "Post-processed image", "instance metadata", "h2kg:MicrostructureImageDataset", "The analysis processes consume the processed FIB-SEM image dataset."),
        ("Step 1 Technique", "Volume fraction calculation", "reuse existing term", "h2kg:Process", "Modeled as a labeled analysis process instance rather than a new TBox term."),
        ("Step 1 Software", "ImageJ", "reuse existing term", "h2kg:FijiImageJSoftware", "The analysis process reuses the existing software instrument anchor."),
        ("Step 1 Target", "Volume fraction", "reuse existing term", "h2kg:PoreVolumeFraction", "Mapped conservatively to the existing legacy anchor; retained as metadata in the example graph because `ofProperty` expects a property-valued target."),
        ("Step 1 AmountTarget", "80 nm", "instance metadata", "h2kg:hasMetadata", "Retained as source metadata because the reported unit is inconsistent with the mapped concept."),
        ("Step 2 Technique", "Surface calculation", "reuse existing term", "h2kg:Process", "Modeled as a labeled analysis process instance rather than a new TBox term."),
        ("Step 2 Software", "ImageJ", "reuse existing term", "h2kg:FijiImageJSoftware", "The analysis process reuses the existing software instrument anchor."),
        ("Step 2 Target", "Porosity", "reuse existing term", "h2kg:TotalPorosity", "Mapped to the existing total-porosity property anchor."),
        ("Step 2 AmountTarget", "10 pu", "instance metadata", "h2kg:DataPoint", "Represented as a result data point with source-value metadata instead of an interpreted quantity value."),
        ("Step 3 Technique", "Direction calculation", "reuse existing term", "h2kg:Process", "Modeled as a labeled analysis process instance rather than a new TBox term."),
        ("Step 3 Software", "ImageJ", "reuse existing term", "h2kg:FijiImageJSoftware", "The analysis process reuses the existing software instrument anchor."),
        ("Step 3 Target", "Direction", "not modeled", "-", "No stable local H2KG term is promoted in this round for the reported direction output."),
        ("Step 3 AmountTarget", "6 deg", "instance metadata", "h2kg:hasMetadata", "Retained as source metadata in the analysis summary dataset."),
        ("Step 4 Technique", "Network relation analysis", "reuse existing term", "h2kg:Process", "Modeled as a labeled analysis process instance rather than a new TBox term."),
        ("Step 4 Software", "-", "not modeled", "-", "The source sheet provides no software value for this analysis step."),
        ("Step 4 Target", "Network relation", "not modeled", "-", "No stable local H2KG term is promoted in this round for the reported network relation output."),
        ("Step 4 AmountTarget", "7 pu", "instance metadata", "h2kg:hasMetadata", "Retained as source metadata in the analysis summary dataset."),
        ("Step 5 Technique", "Constrictivity calculation", "reuse existing term", "h2kg:Process", "Modeled as a labeled analysis process instance rather than a new TBox term."),
        ("Step 5 Condition", "Constrictivity is defined by beta = rmin^2 / rmax^2.", "instance metadata", "h2kg:hasMetadata", "Retained as analysis-definition metadata."),
        ("Step 5 Target", "Constrictivity", "new ontology term", "h2kg:Constrictivity", "Introduced as a reusable FIB-SEM-derived microstructure property."),
        ("Step 5 AmountTarget", "8 pu", "instance metadata", "h2kg:DataPoint", "Represented as a result data point with source-value metadata instead of an interpreted quantity value."),
        ("Step 6 Technique", "Mean geodesic tortuosity calculation", "reuse existing term", "h2kg:Process", "Modeled as a labeled analysis process instance rather than a new TBox term."),
        ("Step 6 Condition", "Quantifying bottleneck effects and shortest transportation paths.", "instance metadata", "h2kg:hasMetadata", "Retained as analysis-definition metadata."),
        ("Step 6 Target", "Mean geodesic torutosity", "new ontology term", "h2kg:GeodesicTortuosity", "Introduced as a reusable FIB-SEM-derived transport property."),
        ("Step 6 AmountTarget", "9 pu", "instance metadata", "h2kg:DataPoint", "Represented as a result data point with source-value metadata instead of an interpreted quantity value."),
    ]
    for field, value, classification, anchor, note in anal_fields:
        add("anal", field, value, classification, anchor, note)

    return rows


def _fib_sem_example_items() -> list[dict[str, Any]]:
    ex = FIB_SEM_EXAMPLE_NS

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
        quantity_kind: str,
        unit: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "@id": iri(local),
            "@type": [f"{QUDT}QuantityValue"],
            f"{QUDT}numericValue": [lit(value, datatype=datatype)],
            f"{QUDT}quantityKind": [ref(quantity_kind)],
        }
        if unit:
            payload[f"{QUDT}unit"] = [ref(unit)]
        return payload

    items: list[dict[str, Any]] = [
        {
            "@id": iri("source-record"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("FIB-SEM pilot source record", language="en")],
            f"{DCTERMS}title": [lit("FIB tomography of NMC111 electrode", language="en")],
            f"{DCTERMS}date": [lit("2021-12-15", datatype=f"{XSD}date")],
            f"{H2KG}hasIdentifier": [lit("7"), lit("Run derived DOI")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Topic: Battery; device: Lithium-ion battery; component: Electrode; granularity: Nanostructure.", language="en"),
                lit("Country: Germany; source link: link; pixel-per-metric: 14.", language="en"),
            ],
            f"{DCTERMS}creator": [ref(iri("author-markus-osenberg")), ref(iri("author-andre-colliard"))],
            f"{DCTERMS}contributor": [ref(iri("institution-hzb")), ref(iri("funding-hi"))],
            f"{DCTERMS}source": [lit("link")],
        },
        {
            "@id": iri("publication-record"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("FIB-SEM pilot publication metadata", language="en")],
            f"{DCTERMS}title": [lit("FIB tomography of NMC111 electrode", language="en")],
            f"{DCTERMS}identifier": [lit("https://doi.org/10.3390/1077778")],
            f"{DCTERMS}issued": [lit("2021-09-17", datatype=f"{XSD}date")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Journal: Nature Communications; volume: 12; issue: 4; pages: 123-321.", language="en"),
                lit("Published flag from source sheet: TRUE.", language="en"),
            ],
            f"{DCTERMS}creator": [ref(iri("author-markus-osenberg")), ref(iri("author-andre-colliard"))],
        },
        {
            "@id": iri("author-markus-osenberg"),
            "@type": [f"{PROV}Agent"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Markus Osenberg", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("author-markus-osenberg-metadata"))],
        },
        {
            "@id": iri("author-andre-colliard"),
            "@type": [f"{PROV}Agent"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Andre Colliard", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("author-andre-colliard-metadata"))],
        },
        {
            "@id": iri("author-markus-osenberg-metadata"),
            "@type": [f"{H2KG}Metadata"],
            f"{DCTERMS}identifier": [lit("ORCID: 123-465-7123"), lit("Email: mark.osen@hzb.de")],
        },
        {
            "@id": iri("author-andre-colliard-metadata"),
            "@type": [f"{H2KG}Metadata"],
            f"{DCTERMS}identifier": [lit("ORCID: 321-321-3211"), lit("Email: andyhuebsch@gmail.mx")],
        },
        {
            "@id": iri("institution-hzb"),
            "@type": [f"{PROV}Agent"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("HZB", language="en")],
        },
        {
            "@id": iri("funding-hi"),
            "@type": [f"{PROV}Agent"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Helmholtz Imaging (HI)", language="en")],
        },
        {
            "@id": iri("ptma-material"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("PTMA precursor", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("ptma-material-metadata"))],
        },
        {
            "@id": iri("ptma-material-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Manufacturer: SigmaAldrich; lot number: 205680; CAS-number: 7440-05-3.", language="en")],
        },
        {
            "@id": iri("superp-material"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("SuperP precursor", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("superp-material-metadata"))],
        },
        {
            "@id": iri("superp-material-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Manufacturer: SigmaAldrich; lot number: 205680; CAS-number: 7440-05-3.", language="en")],
        },
        {
            "@id": iri("pvdf-material"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("PVdF binder precursor", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("pvdf-material-metadata"))],
        },
        {
            "@id": iri("pvdf-material-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Manufacturer: SigmaAldrich; lot number: 205680; CAS-number: 7440-05-3.", language="en"),
                lit("Raw sheet target label after procurement: Nafion ionomer.", language="en"),
            ],
        },
        {
            "@id": iri("nmp-solvent"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("NMP solvent", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("nmp-solvent-metadata"))],
        },
        {
            "@id": iri("nmp-solvent-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Input amount from sheet: 25 mL.", language="en")],
        },
        {
            "@id": iri("aluminum-current-collector"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Aluminum current collector", language="en")],
        },
        {
            "@id": iri("slurry-intermediate"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Electrode slurry intermediate", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("slurry-intermediate-metadata"))],
        },
        {
            "@id": iri("slurry-intermediate-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Raw source references SInt3 and SInt4 inconsistently across dissolve and doctor-blade rows.", language="en"),
                lit("Normalized example treats them as one coherent slurry intermediate.", language="en"),
            ],
        },
        {
            "@id": iri("wet-coated-electrode"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Wet doctor-bladed electrode intermediate", language="en")],
        },
        {
            "@id": iri("cathode-electrode"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Cathode electrode", language="en")],
        },
        {
            "@id": iri("electrode-coupon"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Cut cathode electrode coupon", language="en")],
        },
        {
            "@id": iri("aluminum-pin-stub"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Aluminum pin stub", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("aluminum-pin-stub-metadata"))],
        },
        {
            "@id": iri("aluminum-pin-stub-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Source amount: 12.5 mm.", language="en")],
        },
        {
            "@id": iri("conductive-silver"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Conductive silver", language="en")],
        },
        {
            "@id": iri("mounted-sample"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Mounted FIB-SEM sample intermediate", language="en")],
        },
        {
            "@id": iri("pt-protective-material"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Pt protective coating material", language="en")],
        },
        {
            "@id": iri("pt-protected-sample"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Pt-protected sample intermediate", language="en")],
        },
        {
            "@id": iri("electron-beam-polished-sample"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Electron-beam-polished sample intermediate", language="en")],
        },
        {
            "@id": iri("fib-sem-sample"),
            "@type": [f"{H2KG}Matter"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("FIB-SEM pilot sample", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("fib-sem-sample-metadata"))],
        },
        {
            "@id": iri("fib-sem-sample-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Specimen metadata from sheet: highly porous bulk material.", language="en"),
                lit("Normalized preparation chain reconciles source identifiers SInt3, SInt4, and SInt5 into one coherent sample path.", language="en"),
            ],
        },
        {
            "@id": iri("procure-ptma"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Procure PTMA precursor", language="en")],
            f"{H2KG}hasOutputMaterial": [ref(iri("ptma-material"))],
        },
        {
            "@id": iri("procure-superp"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Procure SuperP precursor", language="en")],
            f"{H2KG}hasOutputMaterial": [ref(iri("superp-material"))],
        },
        {
            "@id": iri("procure-pvdf"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Procure PVdF binder precursor", language="en")],
            f"{H2KG}hasOutputMaterial": [ref(iri("pvdf-material"))],
        },
        {
            "@id": iri("dissolve-step"),
            "@type": [f"{H2KG}Manufacturing"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Dissolve PTMA, SuperP, PVdF, and NMP", language="en")],
            f"{H2KG}hasInputMaterial": [ref(iri("ptma-material")), ref(iri("superp-material")), ref(iri("pvdf-material")), ref(iri("nmp-solvent"))],
            f"{H2KG}hasOutputMaterial": [ref(iri("slurry-intermediate"))],
            f"{H2KG}hasMetadata": [ref(iri("dissolve-step-metadata"))],
        },
        {
            "@id": iri("dissolve-step-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Ratio = 70:20:10; viscosity = 80 Pas.", language="en")],
        },
        {
            "@id": iri("doctor-blade-step"),
            "@type": [f"{H2KG}Manufacturing"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Doctor blade coat slurry on aluminum current collector", language="en")],
            f"{H2KG}hasInputMaterial": [ref(iri("slurry-intermediate")), ref(iri("aluminum-current-collector"))],
            f"{H2KG}hasOutputMaterial": [ref(iri("wet-coated-electrode"))],
            f"{H2KG}hasMetadata": [ref(iri("doctor-blade-step-metadata"))],
        },
        {
            "@id": iri("doctor-blade-step-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Velocity = 1 cm/s; instrument = MICOS Blading; thickness = 1 mm.", language="en"),
                lit("Raw source target identifier reported as SInt3.", language="en"),
            ],
        },
        {
            "@id": iri("dry-electrode-step"),
            "@type": [f"{H2KG}Manufacturing"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Dry doctor-bladed electrode", language="en")],
            f"{H2KG}hasInputMaterial": [ref(iri("wet-coated-electrode"))],
            f"{H2KG}hasOutputMaterial": [ref(iri("cathode-electrode"))],
            f"{H2KG}hasMetadata": [ref(iri("dry-electrode-step-metadata"))],
        },
        {
            "@id": iri("dry-electrode-step-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Temperature = 80 deg C; time = 16 h.", language="en"),
                lit("Raw source precursor identifier before drying reported as SInt5.", language="en"),
            ],
        },
        {
            "@id": iri("cut-step"),
            "@type": [f"{H2KG}Manufacturing"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Cut cathode electrode coupon", language="en")],
            f"{H2KG}hasInputMaterial": [ref(iri("cathode-electrode"))],
            f"{H2KG}hasOutputMaterial": [ref(iri("electrode-coupon"))],
            f"{H2KG}hasMetadata": [ref(iri("cut-step-metadata"))],
        },
        {
            "@id": iri("cut-step-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Size = 3 mm2.", language="en")],
        },
        {
            "@id": iri("fix-step"),
            "@type": [f"{H2KG}Manufacturing"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Fix electrode coupon on pin stub with conductive silver", language="en")],
            f"{H2KG}hasInputMaterial": [ref(iri("electrode-coupon")), ref(iri("aluminum-pin-stub")), ref(iri("conductive-silver"))],
            f"{H2KG}hasOutputMaterial": [ref(iri("mounted-sample"))],
            f"{H2KG}hasMetadata": [ref(iri("fix-step-metadata"))],
        },
        {
            "@id": iri("fix-step-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Time = 8 h.", language="en")],
        },
        {
            "@id": iri("deposit-step"),
            "@type": [f"{H2KG}Manufacturing"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Deposit Pt protective layer", language="en")],
            f"{H2KG}hasInputMaterial": [ref(iri("mounted-sample")), ref(iri("pt-protective-material"))],
            f"{H2KG}hasOutputMaterial": [ref(iri("pt-protected-sample"))],
            f"{H2KG}hasMetadata": [ref(iri("deposit-step-metadata"))],
        },
        {
            "@id": iri("deposit-step-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Thickness = 0.5 um; area = 15 um2.", language="en")],
        },
        {
            "@id": iri("electron-beam-step"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Electron beam polishing", language="en")],
            f"{H2KG}hasInputMaterial": [ref(iri("pt-protected-sample"))],
            f"{H2KG}hasOutputMaterial": [ref(iri("electron-beam-polished-sample"))],
            f"{H2KG}hasMetadata": [ref(iri("electron-beam-step-metadata"))],
        },
        {
            "@id": iri("electron-beam-step-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Temperature = 50 deg C; time = 10 min; current = 250 pA; energy = 5 keV.", language="en")],
        },
        {
            "@id": iri("gallium-current-step"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Gallium current milling", language="en")],
            f"{H2KG}hasInputMaterial": [ref(iri("electron-beam-polished-sample"))],
            f"{H2KG}hasOutputMaterial": [ref(iri("fib-sem-sample"))],
            f"{H2KG}hasMetadata": [ref(iri("gallium-current-step-metadata"))],
        },
        {
            "@id": iri("gallium-current-step-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Temperature = 50 deg C; time = 30 min; current = 300 pA; energy = 30 keV.", language="en")],
        },
        {
            "@id": iri("fib-sem-measurement-001"),
            "@type": [f"{H2KG}Measurement", f"{H2KG}FIBSEMTomographyMeasurement"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("FIB-SEM pilot tomography measurement", language="en")],
            f"{H2KG}hasInputMaterial": [ref(iri("fib-sem-sample"))],
            f"{H2KG}usesInstrument": [ref(iri("fib-sem-instrument-001"))],
            f"{H2KG}hasOutputData": [ref(iri("fib-sem-raw-image-dataset"))],
            f"{H2KG}hasParameter": [
                ref(iri("temperature-setting")),
                ref(iri("relative-humidity-setting")),
                ref(iri("vacuum-pressure-setting")),
                ref(iri("ion-beam-current-setting")),
                ref(iri("ion-beam-energy-setting")),
                ref(iri("electron-current-setting")),
                ref(iri("electron-beam-energy-setting")),
                ref(iri("measured-area-setting")),
                ref(iri("cut-thickness-setting")),
                ref(iri("slice-number-setting")),
                ref(iri("dwell-time-setting")),
                ref(iri("magnification-setting")),
                ref(iri("stage-tilt-setting")),
                ref(iri("exposure-time-setting")),
                ref(iri("total-acquisition-time-setting")),
                ref(iri("voxel-size-setting")),
            ],
            f"{H2KG}hasMetadata": [
                ref(iri("fib-sem-acquisition-metadata")),
                ref(iri("source-record")),
                ref(iri("publication-record")),
            ],
            f"{PROV}wasAssociatedWith": [ref(iri("author-markus-osenberg")), ref(iri("author-andre-colliard"))],
            f"{DCTERMS}source": [ref(iri("publication-record"))],
        },
        {
            "@id": iri("fib-sem-instrument-001"),
            "@type": [f"{H2KG}Instrument", f"{H2KG}FIBSEMInstrument"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("FIB-SEM instrument used in the pilot case", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("fib-sem-instrument-metadata"))],
        },
        {
            "@id": iri("fib-sem-instrument-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("FIB equipment: ZEISS Crossbeam 340; optics: GEMINI; injected element: Pt.", language="en"),
                lit("Injection system: multi channel gas injection system GIS; ion beam type: Ga; detector: InLens, SE2.", language="en"),
                lit("Plane spacing = 10; tilt compensation = 36; dynamic focus = -3; drift compensation = False; brightness = 1; contrast = 1.", language="en"),
            ],
        },
        {
            "@id": iri("fib-sem-raw-image-dataset"),
            "@type": [f"{H2KG}Data", f"{H2KG}SEMImageDataset"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("FIB-SEM raw image stack dataset", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("fib-sem-raw-image-metadata"))],
        },
        {
            "@id": iri("fib-sem-raw-image-metadata"),
            "@type": [f"{H2KG}Metadata"],
            f"{DCTERMS}format": [lit("tiff")],
            f"{DCTERMS}extent": [lit("1250 MB"), lit("1024 x 1024 x 1000 pixels")],
            f"{DCTERMS}source": [lit("link")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Filename: batNMC111.zip.", language="en"),
                lit("PixelPerMetric: 14.", language="en"),
            ],
        },
        {
            "@id": iri("drift-correction-step"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("DriftCorrect", language="en")],
            f"{H2KG}hasInputData": [ref(iri("fib-sem-raw-image-dataset"))],
            f"{H2KG}hasOutputData": [ref(iri("drift-corrected-image-dataset"))],
            f"{H2KG}hasMetadata": [ref(iri("drift-correction-metadata"))],
        },
        {
            "@id": iri("drift-correction-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Software = SIFT.", language="en")],
        },
        {
            "@id": iri("drift-corrected-image-dataset"),
            "@type": [f"{H2KG}Data", f"{H2KG}MicrostructureImageDataset"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("FIB-SEM drift-corrected image stack", language="en")],
        },
        {
            "@id": iri("reconstruct-step"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("3D Reconstruct", language="en")],
            f"{H2KG}hasInputData": [ref(iri("drift-corrected-image-dataset"))],
            f"{H2KG}hasOutputData": [ref(iri("reconstructed-volume-dataset"))],
            f"{H2KG}hasMetadata": [ref(iri("reconstruct-step-metadata"))],
        },
        {
            "@id": iri("reconstruct-step-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Software = Astra toolbox.", language="en")],
        },
        {
            "@id": iri("reconstructed-volume-dataset"),
            "@type": [f"{H2KG}Data", f"{H2KG}MicrostructureImageDataset"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("FIB-SEM reconstructed volume dataset", language="en")],
        },
        {
            "@id": iri("artefact-remove-step"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Artefact remove", language="en")],
            f"{H2KG}hasInputData": [ref(iri("reconstructed-volume-dataset"))],
            f"{H2KG}hasOutputData": [ref(iri("artefact-cleaned-volume-dataset"))],
            f"{H2KG}hasMetadata": [ref(iri("artefact-remove-step-metadata"))],
        },
        {
            "@id": iri("artefact-remove-step-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Software = In-house 3D Unet.", language="en")],
        },
        {
            "@id": iri("artefact-cleaned-volume-dataset"),
            "@type": [f"{H2KG}Data", f"{H2KG}MicrostructureImageDataset"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("FIB-SEM artefact-cleaned volume dataset", language="en")],
        },
        {
            "@id": iri("clean-step"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Clean", language="en")],
            f"{H2KG}hasInputData": [ref(iri("artefact-cleaned-volume-dataset"))],
            f"{H2KG}hasOutputData": [ref(iri("cleaned-volume-dataset"))],
            f"{H2KG}usesInstrument": [ref(f"{H2KG}FijiImageJSoftware")],
        },
        {
            "@id": iri("cleaned-volume-dataset"),
            "@type": [f"{H2KG}Data", f"{H2KG}MicrostructureImageDataset"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("FIB-SEM cleaned volume dataset", language="en")],
        },
        {
            "@id": iri("threshold-step"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Threshold", language="en")],
            f"{H2KG}hasInputData": [ref(iri("cleaned-volume-dataset"))],
            f"{H2KG}hasOutputData": [ref(iri("segmented-volume-dataset"))],
            f"{H2KG}usesInstrument": [ref(f"{H2KG}FijiImageJSoftware")],
            f"{H2KG}hasMetadata": [ref(iri("threshold-step-metadata"))],
        },
        {
            "@id": iri("threshold-step-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Algorithm = Watershed.", language="en")],
        },
        {
            "@id": iri("segmented-volume-dataset"),
            "@type": [f"{H2KG}Data", f"{H2KG}MicrostructureImageDataset"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("FIB-SEM segmented volume dataset", language="en")],
        },
        {
            "@id": iri("visualize-step"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Visualize", language="en")],
            f"{H2KG}hasInputData": [ref(iri("segmented-volume-dataset"))],
            f"{H2KG}hasOutputData": [ref(iri("postprocessed-image-dataset"))],
            f"{H2KG}hasMetadata": [ref(iri("visualize-step-metadata"))],
        },
        {
            "@id": iri("visualize-step-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Software = Blender3D.", language="en")],
        },
        {
            "@id": iri("postprocessed-image-dataset"),
            "@type": [f"{H2KG}Data", f"{H2KG}MicrostructureImageDataset"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("FIB-SEM post-processed image dataset", language="en")],
            f"{H2KG}hasMetadata": [ref(iri("postprocessed-image-metadata"))],
        },
        {
            "@id": iri("postprocessed-image-metadata"),
            "@type": [f"{H2KG}Metadata"],
            f"{DCTERMS}source": [lit("github-com/FIB-SEM_NMC")],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Mask present: yes.", language="en")],
        },
        {
            "@id": iri("volume-fraction-step"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Volume fraction calculation", language="en")],
            f"{H2KG}hasInputData": [ref(iri("postprocessed-image-dataset"))],
            f"{H2KG}hasOutputData": [ref(iri("fib-sem-analysis-summary-dataset"))],
            f"{H2KG}usesInstrument": [ref(f"{H2KG}FijiImageJSoftware")],
            f"{H2KG}hasMetadata": [ref(iri("volume-fraction-step-metadata"))],
        },
        {
            "@id": iri("volume-fraction-step-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Mapped to legacy anchor h2kg:PoreVolumeFraction.", language="en"),
                lit("Raw source amount target retained as metadata: 80 nm.", language="en"),
            ],
        },
        {
            "@id": iri("surface-calculation-step"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Surface calculation", language="en")],
            f"{H2KG}hasInputData": [ref(iri("postprocessed-image-dataset"))],
            f"{H2KG}hasOutputData": [ref(iri("fib-sem-analysis-summary-dataset"))],
            f"{H2KG}usesInstrument": [ref(f"{H2KG}FijiImageJSoftware")],
        },
        {
            "@id": iri("direction-calculation-step"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Direction calculation", language="en")],
            f"{H2KG}hasInputData": [ref(iri("postprocessed-image-dataset"))],
            f"{H2KG}hasOutputData": [ref(iri("fib-sem-analysis-summary-dataset"))],
            f"{H2KG}usesInstrument": [ref(f"{H2KG}FijiImageJSoftware")],
            f"{H2KG}hasMetadata": [ref(iri("direction-calculation-metadata"))],
        },
        {
            "@id": iri("direction-calculation-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Deferred output retained as metadata: Direction = 6 deg.", language="en")],
        },
        {
            "@id": iri("network-relation-analysis-step"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Network relation analysis", language="en")],
            f"{H2KG}hasInputData": [ref(iri("postprocessed-image-dataset"))],
            f"{H2KG}hasOutputData": [ref(iri("fib-sem-analysis-summary-dataset"))],
            f"{H2KG}hasMetadata": [ref(iri("network-relation-analysis-metadata"))],
        },
        {
            "@id": iri("network-relation-analysis-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Deferred output retained as metadata: Network relation = 7 pu.", language="en")],
        },
        {
            "@id": iri("constrictivity-step"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Constrictivity calculation", language="en")],
            f"{H2KG}hasInputData": [ref(iri("postprocessed-image-dataset"))],
            f"{H2KG}hasOutputData": [ref(iri("fib-sem-analysis-summary-dataset"))],
            f"{H2KG}hasMetadata": [ref(iri("constrictivity-step-metadata"))],
        },
        {
            "@id": iri("constrictivity-step-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Description = Constrictivity is defined by beta = rmin^2 / rmax^2.", language="en"),
                lit("Raw source amount target retained as metadata: 8 pu.", language="en"),
            ],
        },
        {
            "@id": iri("geodesic-tortuosity-step"),
            "@type": [f"{H2KG}Process"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("Mean geodesic tortuosity calculation", language="en")],
            f"{H2KG}hasInputData": [ref(iri("postprocessed-image-dataset"))],
            f"{H2KG}hasOutputData": [ref(iri("fib-sem-analysis-summary-dataset"))],
            f"{H2KG}hasMetadata": [ref(iri("geodesic-tortuosity-step-metadata"))],
        },
        {
            "@id": iri("geodesic-tortuosity-step-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Description = Quantifying bottleneck effects and shortest transportation paths, respectively.", language="en"),
                lit("Raw source amount target retained as metadata: 9 pu.", language="en"),
            ],
        },
        {
            "@id": iri("fib-sem-analysis-summary-dataset"),
            "@type": [f"{H2KG}Data", f"{H2KG}PoreSizeDistributionDataset"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("FIB-SEM derived pore-analysis summary dataset", language="en")],
            f"{H2KG}hasPart": [
                ref(iri("total-porosity-datapoint")),
                ref(iri("constrictivity-datapoint")),
                ref(iri("geodesic-tortuosity-datapoint")),
            ],
            f"{H2KG}hasMetadata": [ref(iri("fib-sem-analysis-summary-metadata"))],
        },
        {
            "@id": iri("fib-sem-analysis-summary-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Volume fraction output mapped to legacy anchor h2kg:PoreVolumeFraction and retained as metadata because the current anchor is parameter-valued.", language="en"),
                lit("Direction and network relation outputs remain metadata-only in this pilot round.", language="en"),
            ],
        },
        {
            "@id": iri("total-porosity-datapoint"),
            "@type": [f"{H2KG}DataPoint"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("FIB-SEM derived total porosity datapoint", language="en")],
            f"{H2KG}ofProperty": [ref(f"{H2KG}TotalPorosity")],
            f"{H2KG}fromMeasurement": [ref(iri("fib-sem-measurement-001"))],
            f"{PROV}wasGeneratedBy": [ref(iri("surface-calculation-step"))],
            f"{H2KG}hasMetadata": [ref(iri("total-porosity-datapoint-metadata"))],
            f"{DCTERMS}source": [ref(iri("publication-record"))],
        },
        {
            "@id": iri("total-porosity-datapoint-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Worksheet amount target retained as source metadata: 10 pu.", language="en")],
        },
        {
            "@id": iri("constrictivity-datapoint"),
            "@type": [f"{H2KG}DataPoint"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("FIB-SEM derived constrictivity datapoint", language="en")],
            f"{H2KG}ofProperty": [ref(f"{H2KG}Constrictivity")],
            f"{H2KG}fromMeasurement": [ref(iri("fib-sem-measurement-001"))],
            f"{PROV}wasGeneratedBy": [ref(iri("constrictivity-step"))],
            f"{H2KG}hasMetadata": [ref(iri("constrictivity-datapoint-metadata"))],
            f"{DCTERMS}source": [ref(iri("publication-record"))],
        },
        {
            "@id": iri("constrictivity-datapoint-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Worksheet amount target retained as source metadata: 8 pu.", language="en")],
        },
        {
            "@id": iri("geodesic-tortuosity-datapoint"),
            "@type": [f"{H2KG}DataPoint"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("FIB-SEM derived geodesic tortuosity datapoint", language="en")],
            f"{H2KG}ofProperty": [ref(f"{H2KG}GeodesicTortuosity")],
            f"{H2KG}fromMeasurement": [ref(iri("fib-sem-measurement-001"))],
            f"{PROV}wasGeneratedBy": [ref(iri("geodesic-tortuosity-step"))],
            f"{H2KG}hasMetadata": [ref(iri("geodesic-tortuosity-datapoint-metadata"))],
            f"{DCTERMS}source": [ref(iri("publication-record"))],
        },
        {
            "@id": iri("geodesic-tortuosity-datapoint-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [lit("Worksheet amount target retained as source metadata: 9 pu.", language="en")],
        },
        {
            "@id": iri("temperature-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}Temperature"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("FIB-SEM acquisition temperature setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("temperature-setting-qv"))],
        },
        qv("temperature-setting-qv", "23", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/ThermodynamicTemperature", f"{UNIT}DEG_C"),
        {
            "@id": iri("relative-humidity-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}RelativeHumidity"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("FIB-SEM acquisition relative-humidity setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("relative-humidity-setting-qv"))],
        },
        qv("relative-humidity-setting-qv", "0", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/RelativeHumidity", f"{UNIT}PERCENT"),
        {
            "@id": iri("vacuum-pressure-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}VacuumChamberPressure"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("FIB-SEM vacuum pressure setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("vacuum-pressure-setting-qv"))],
        },
        qv("vacuum-pressure-setting-qv", "1.0e-5", f"{XSD}double", "http://qudt.org/vocab/quantitykind/Pressure", f"{UNIT}ATM"),
        {
            "@id": iri("ion-beam-current-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}IonBeamCurrent"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("FIB ion-beam current setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("ion-beam-current-setting-qv"))],
        },
        qv("ion-beam-current-setting-qv", "700", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/ElectricCurrent", f"{UNIT}PicoA"),
        {
            "@id": iri("ion-beam-energy-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}IonBeamEnergy"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("FIB ion-beam energy setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("ion-beam-energy-setting-qv"))],
        },
        qv("ion-beam-energy-setting-qv", "30", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/Energy", f"{UNIT}KiloEV"),
        {
            "@id": iri("electron-current-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}ElectronCurrent"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("SEM electron-current setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("electron-current-setting-qv"))],
        },
        qv("electron-current-setting-qv", "250", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/ElectricCurrent", f"{UNIT}PicoA"),
        {
            "@id": iri("electron-beam-energy-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}ElectronBeamEnergy"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("SEM electron-beam energy setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("electron-beam-energy-setting-qv"))],
        },
        qv("electron-beam-energy-setting-qv", "1.5", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/Energy", f"{UNIT}KiloEV"),
        {
            "@id": iri("measured-area-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}MicroscopyMeasuredArea"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("FIB-SEM measured-area setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("measured-area-setting-qv"))],
        },
        qv("measured-area-setting-qv", "20", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/Area", f"{UNIT}MicroM2"),
        {
            "@id": iri("cut-thickness-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}CutThickness"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("FIB-SEM cut-thickness setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("cut-thickness-setting-qv"))],
        },
        qv("cut-thickness-setting-qv", "150", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/Length", f"{UNIT}NanoM"),
        {
            "@id": iri("slice-number-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}SliceNumber"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("FIB-SEM slice-number setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("slice-number-setting-qv"))],
        },
        qv("slice-number-setting-qv", "1300", f"{XSD}integer", "http://qudt.org/vocab/quantitykind/Count"),
        {
            "@id": iri("dwell-time-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}DwellTime"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("FIB-SEM dwell-time setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("dwell-time-setting-qv"))],
        },
        qv("dwell-time-setting-qv", "3", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/Time", f"{UNIT}HR"),
        {
            "@id": iri("magnification-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}Magnification"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("FIB-SEM magnification setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("magnification-setting-qv"))],
        },
        qv("magnification-setting-qv", "10", f"{XSD}integer", "http://qudt.org/vocab/quantitykind/Dimensionless", f"{UNIT}UNITLESS"),
        {
            "@id": iri("stage-tilt-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}StageTilt"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("FIB-SEM stage-tilt setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("stage-tilt-setting-qv"))],
        },
        qv("stage-tilt-setting-qv", "54", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/PlaneAngle", f"{UNIT}DEG"),
        {
            "@id": iri("exposure-time-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}ExposureTime"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("FIB-SEM image-acquisition time setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("exposure-time-setting-qv"))],
        },
        qv("exposure-time-setting-qv", "60", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/Time", f"{UNIT}SEC"),
        {
            "@id": iri("total-acquisition-time-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}TotalAcquisitionTime"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("FIB-SEM total-acquisition-time setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("total-acquisition-time-setting-qv"))],
        },
        qv("total-acquisition-time-setting-qv", "12", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/Time", f"{UNIT}HR"),
        {
            "@id": iri("voxel-size-setting"),
            "@type": [f"{H2KG}Parameter", f"{H2KG}VoxelSize"],
            "http://www.w3.org/2000/01/rdf-schema#label": [lit("FIB-SEM voxel-size setting", language="en")],
            f"{H2KG}hasQuantityValue": [ref(iri("voxel-size-setting-qv"))],
        },
        qv("voxel-size-setting-qv", "20", f"{XSD}decimal", "http://qudt.org/vocab/quantitykind/Length", f"{UNIT}NanoM"),
        {
            "@id": iri("fib-sem-acquisition-metadata"),
            "@type": [f"{H2KG}Metadata"],
            "http://www.w3.org/2000/01/rdf-schema#comment": [
                lit("Measurement type: ex-situ; specimen: highly porous bulk material; atmosphere: vacuum.", language="en"),
                lit("Calibration notes: adjusting lenses and apertures; adjusting the voltage.", language="en"),
            ],
        },
    ]
    return items


def _fib_sem_validation_note() -> str:
    return """# FIB-SEM Validation Note

## Ontology changes introduced in the FIB-SEM round

- Added `h2kg:FIBSEMInstrument` as a reusable instrument anchor for focused ion beam scanning electron microscopy.
- Added reusable FIB-SEM acquisition parameters: `h2kg:IonBeamCurrent`, `h2kg:IonBeamEnergy`, `h2kg:ElectronCurrent`, `h2kg:ElectronBeamEnergy`, `h2kg:CutThickness`, `h2kg:SliceNumber`, `h2kg:StageTilt`, and `h2kg:TotalAcquisitionTime`.
- Added reusable derived-property anchors `h2kg:Constrictivity` and `h2kg:GeodesicTortuosity`.
- Strengthened `h2kg:FIBSEMTomographyMeasurement` so the Explore/Search page can expose a coherent FIB-SEM neighborhood directly from the ontology, including explicit parameter, instrument, property, and dataset links.
- Generalized reused descriptions where needed so `DwellTime`, `PoreVolumeFraction`, `TotalPorosity`, `SEMImageDataset`, and `PoreSizeDistributionDataset` no longer read as method-incompatible when reused in the FIB-SEM context.

## What remained instance metadata in round 1

- Organizational, bibliographic, file, and access details from the `org` section.
- `MeasurementType`, `Specimen`, `Atmosphere`, and `Calibration` from the `char` section.
- Instrument descriptors such as `FIBEquipment`, `Optics`, `InjectedElement`, `InjectionSystem`, `IonBeamType`, `Detector`, `TiltCompensation`, `DynamicFocus`, `DriftCompensation`, `Brightness`, and `Contrast`.
- Sheet-specific process labels such as `Dissolve`, `Doctor blade`, `Cut`, `Fix`, `Deposit`, `Electron beam`, `Gallium current`, `DriftCorrect`, `3D Reconstruct`, `Artefact remove`, `Clean`, `Threshold`, `Visualize`, and the named analysis techniques.

## What was intentionally deferred

- No new TBox terms were introduced for `Direction` or `Network relation`; those outputs remain metadata-only in this pilot round.
- `PoreVolumeFraction` is a legacy local anchor currently typed as a parameter, so the example graph keeps the source result as mapped metadata instead of forcing it into a strict `DataPoint -> ofProperty` pattern that expects a property-valued target.
- Software names such as `SIFT`, `Astra toolbox`, `In-house 3D Unet`, and `Blender3D` remain metadata in this round. Only `ImageJ` reuses the existing `h2kg:FijiImageJSoftware` anchor.

## Source-sheet normalization note

The FIB-SEM sheet contains internal identifier inconsistencies across `SInt3`, `SInt4`, and `SInt5`, and one procurement target label that reports `Nafion ionomer` for a `PVdF` precursor row. The normalized example graph records those raw values as metadata but resolves them into one coherent material and process chain so the ontology demonstration remains readable and queryable.
"""


def _fib_sem_case_summary() -> str:
    return """# FIB-SEM Case Summary

The FIB-SEM pilot demonstrates how H2KG can capture a tomography-oriented imaging workflow from electrode preparation through dual-beam acquisition, 3D preprocessing, and derived porous-microstructure analysis without uncontrolled ontology growth. The acquisition itself is represented as a `FIBSEMTomographyMeasurement` linked to a `FIBSEMInstrument`, explicit acquisition-parameter settings such as ion-beam current, ion-beam energy, electron-beam energy, cut thickness, slice number, stage tilt, voxel size, and total acquisition time, and a raw `SEMImageDataset`.

The preprocessing chain transforms the raw slice stack through drift correction, reconstruction, artefact removal, cleanup, thresholding, and visualization into a final `MicrostructureImageDataset`. Downstream analysis then derives formal H2KG result nodes for `TotalPorosity`, `Constrictivity`, and `GeodesicTortuosity`, while legacy or not-yet-promoted outputs such as `PoreVolumeFraction`, `Direction`, and `Network relation` remain attached as structured metadata rather than being forced into semantically incorrect TBox patterns.

This pilot is also deliberately honest about the source sheet itself. Where the sheet uses inconsistent intermediate identifiers or method labels, the example graph normalizes them into a coherent workflow while preserving the raw source wording as metadata. That makes the ontology representation faithful to the source without importing spreadsheet inconsistency into the released H2KG vocabulary.
"""


def _fib_sem_follow_on_gaps() -> str:
    return """# Follow-on Gaps After FIB-SEM

- Review whether `PoreVolumeFraction` should be promoted from a legacy parameter-style anchor into a property-style anchor so future image-analysis datapoints can use it cleanly with `ofProperty`.
- Review whether directionality and network-connectivity outputs recur strongly enough across imaging methods to justify promotion from metadata into reusable H2KG terms.
- Compare FIB-SEM with synchrotron tomography and neutron tomography to decide whether a small shared 3D imaging-acquisition profile should be introduced.
- Review whether microscope configuration fields such as detector mode, drift compensation, dynamic focus, and tilt compensation should remain metadata or become reusable TBox anchors after cross-method comparison.
- Continue the controlled integration sequence with the remaining workbook-backed imaging methods before promoting broader imaging abstractions.
"""


def _fib_sem_readme(generated_files: list[Path]) -> str:
    files = "\n".join(f"- `{path.name}`" for path in generated_files)
    return f"""# FIB-SEM Pilot Package

Generated FIB-SEM companion artifacts for the controlled FIB-SEM imaging-method integration round.

## Files

{files}

The pilot keeps H2KG disciplined: the released ontology grows only where repeated FIB-SEM concepts clearly justify reusable TBox anchors, while source-specific values and spreadsheet inconsistencies remain attached as metadata or labeled process instances.
"""


def _missing_terms_note(missing: list[str]) -> str:
    lines = "\n".join(f"- `{term}`" for term in missing)
    return f"""# FIB-SEM Pilot Package

FIB-SEM pilot artifacts were not generated because required H2KG terms were missing from the input ontology source.

## Missing terms

{lines}
"""
