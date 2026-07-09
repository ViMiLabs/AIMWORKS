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
NEUTRON_TOMO_EXAMPLE_NS = "https://w3id.org/h2kg/examples/neutron-tomo#"

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
    f"{H2KG}MEAAssembly",
    f"{H2KG}Temperature",
    f"{H2KG}RelativeHumidity",
    f"{H2KG}PixelSize",
    f"{H2KG}ExposureTime",
    f"{H2KG}ExperimentDataset",
    f"{H2KG}NeutronTomographyMeasurement",
    f"{H2KG}NeutronTomographyInstrument",
    f"{H2KG}TomographicProjectionDataset",
    f"{H2KG}TomographicReconstructionDataset",
    f"{H2KG}ProjectionNumber",
    f"{H2KG}NeutronFlux",
    f"{H2KG}SpatialResolution",
    f"{H2KG}SampleDetectorDistance",
    f"{H2KG}TortuosityFactor",
    f"{H2KG}AverageWaterDropletArea",
    f"{H2KG}AverageWaterDropletCount",
}


def build_neutron_tomo_pilot_package(
    input_path: str | Path,
    output_root: str | Path,
) -> dict[str, Any]:
    input_path = Path(input_path)
    output_root = Path(output_root)
    target_dir = ensure_dir(output_root / "examples" / "neutron_tomo_pilot")
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

    mapping_rows = _neutron_tomo_mapping_rows()
    example_items = _neutron_tomo_example_items()
    generated_files = [
        _write_mapping_matrix(target_dir / "neutron_tomo_mapping_matrix.csv", mapping_rows),
        _write_mapping_matrix_markdown(target_dir / "neutron_tomo_mapping_matrix.md", mapping_rows),
        dump_json(
            target_dir / "neutron_tomo_example.jsonld",
            {"@context": {**COMMON_CONTEXT, "ntomo": NEUTRON_TOMO_EXAMPLE_NS}, "@graph": example_items},
        ),
        dump_turtle_items(target_dir / "neutron_tomo_example.ttl", example_items),
        write_text(target_dir / "neutron_tomo_validation_note.md", _neutron_tomo_validation_note()),
        write_text(target_dir / "neutron_tomo_case_summary.md", _neutron_tomo_case_summary()),
        write_text(target_dir / "neutron_tomo_follow_on_gaps.md", _neutron_tomo_follow_on_gaps()),
        write_text(target_dir / "neutron_tomo_manuscript_figure.md", _neutron_tomo_manuscript_figure()),
        write_text(target_dir / "neutron_tomo_manuscript_table.md", _neutron_tomo_manuscript_table()),
    ]
    write_text(target_dir / "README.md", _neutron_tomo_readme(generated_files))
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
        "# NeutronTomo Mapping Matrix",
        "",
        "This matrix accounts for each populated `NeutronTomo` sheet field and classifies it as `reuse existing term`, `new ontology term`, `instance metadata`, or `not modeled` for the controlled neutron-tomography round.",
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


def _neutron_tomo_mapping_rows() -> list[dict[str, str]]:
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

    org_rows = [
        ("ExperimentTitle", "Understanding water dynamics in operating fuel cells by operando neutron tomography: investigation of different flow field designs", "instance metadata", "h2kg:hasMetadata + dcterms:title", "Stored on the source-record metadata node."),
        ("ExperimentID", "8", "instance metadata", "h2kg:hasMetadata + h2kg:hasIdentifier", "Stored as a literal identifier on the source record."),
        ("Measurement-ID", "Run derived DOI", "instance metadata", "h2kg:hasMetadata + h2kg:hasIdentifier", "Stored on measurement metadata."),
        ("UploadDate", "2024-02-11", "instance metadata", "h2kg:hasMetadata + dcterms:date", "Excel serial normalized to ISO date."),
        ("MeasurementDate", "", "not modeled", "-", "No measurement date value was populated in the sheet."),
        ("Institution", "HZB", "instance metadata", "prov:Agent", "Represented as an institutional agent."),
        ("FoundingBody", "Helmholtz AI", "instance metadata", "prov:Agent", "Represented as a funding-body agent."),
        ("Country", "Germany", "instance metadata", "h2kg:hasMetadata", "Retained as contextual metadata."),
        ("Author", "Ralf Ziesche; André Colliard Granero", "instance metadata", "prov:Agent", "Represented as author agent instances."),
        ("ORCID", "123-465-7765; 321-321-3211", "instance metadata", "h2kg:hasMetadata", "Stored on author metadata nodes."),
        ("Email", "ralf.ziesche@yahoo.ru; andyhuebsch@gmail.mx", "instance metadata", "h2kg:hasMetadata", "Stored on author metadata nodes."),
        ("Published", "1", "instance metadata", "h2kg:hasMetadata", "Retained as publication-status metadata."),
        ("Publication", "Understanding water dynamics in operating fuel cells by operando neutron tomography: investigation of different flow field designs", "instance metadata", "h2kg:hasMetadata + dcterms:title", "Stored on a publication metadata node."),
        ("DOI", "https://doi.org/10.1088/2515-7655/ad3984", "instance metadata", "h2kg:hasMetadata + dcterms:identifier", "Stored on a publication metadata node."),
        ("Journal", "Materials Today", "instance metadata", "h2kg:hasMetadata", "Retained as bibliographic metadata."),
        ("Volume", "1", "instance metadata", "h2kg:hasMetadata", "Retained as bibliographic metadata."),
        ("Issue", "8", "instance metadata", "h2kg:hasMetadata", "Retained as bibliographic metadata."),
        ("Pages", "23-45", "instance metadata", "h2kg:hasMetadata", "Retained as bibliographic metadata."),
        ("PublicationDate", "2012-11-28", "instance metadata", "h2kg:hasMetadata + dcterms:issued", "Excel serial normalized to ISO date."),
        ("Topic", "Battery", "instance metadata", "h2kg:hasMetadata", "Contradictory to the fuel-cell title and sample chain; retained as source metadata only."),
        ("Device", "Lithium Battery", "instance metadata", "h2kg:hasMetadata", "Contradictory to the fuel-cell title and sample chain; retained as source metadata only."),
        ("Component", "Electrode", "instance metadata", "h2kg:hasMetadata", "Retained as source metadata because the public H2KG case is centered on the MEA assembly context."),
        ("Subcomponent", "-", "not modeled", "-", "The sheet explicitly reports no subcomponent value."),
        ("Granularity Level", "Macrostructure", "instance metadata", "h2kg:hasMetadata", "Retained as granularity metadata."),
        ("Format", "png", "instance metadata", "h2kg:hasMetadata + dcterms:format", "Stored on raw-dataset metadata."),
        ("FileSize", "200", "instance metadata", "h2kg:hasMetadata + dcterms:extent", "Stored with file-size unit in dataset metadata."),
        ("FileSizeUnit", "MB", "instance metadata", "h2kg:hasMetadata + dcterms:extent", "Stored with file size in dataset metadata."),
        ("FileName", "TestNeutronTomography.tif", "instance metadata", "h2kg:hasMetadata", "Stored on raw-dataset metadata."),
        ("DimensionX", "1024", "instance metadata", "h2kg:hasMetadata", "Stored on raw-dataset metadata."),
        ("DimensionY", "1024", "instance metadata", "h2kg:hasMetadata", "Stored on raw-dataset metadata."),
        ("DimensionZ", "1300", "instance metadata", "h2kg:hasMetadata", "Stored on raw-dataset metadata."),
        ("PixelPerMetric", "30", "instance metadata", "h2kg:hasMetadata", "Stored on raw-dataset metadata."),
        ("Link", "link", "instance metadata", "h2kg:hasMetadata + dcterms:source", "Stored as source/link metadata."),
        ("MaskExist", "no", "instance metadata", "h2kg:hasMetadata", "Stored on processed-dataset metadata."),
        ("MaskLink", "link", "instance metadata", "h2kg:hasMetadata + dcterms:source", "Stored on processed-dataset metadata."),
    ]
    for field, value, classification, anchor, note in org_rows:
        add("org", field, value, classification, anchor, note)

    syn_rows = [
        ("Step 1 Precursor", "Gas diffusion electrode", "instance metadata", "h2kg:Matter", "Represented as a supporting material instance in the assembly chain."),
        ("Step 1 AmountPrecursor", "2", "instance metadata", "h2kg:hasMetadata", "Stored as precursor metadata in round 1."),
        ("Step 1 Technique", "Buy", "reuse existing term", "h2kg:Process", "Modeled as a labeled procurement process instance."),
        ("Step 1 Condition", "Manufacturer = HyPlat, South Africa; PtLoading = 0.4 mg/cm2", "instance metadata", "h2kg:hasMetadata", "Retained as procurement metadata on the gas-diffusion-electrode material."),
        ("Step 1 Target", "SInt1", "instance metadata", "h2kg:Matter", "Represents the procured gas-diffusion-electrode material instance."),
        ("Step 2 Precursor", "Membrane", "instance metadata", "h2kg:Matter", "Represented as a membrane material instance."),
        ("Step 2 Technique", "Buy", "reuse existing term", "h2kg:Process", "Modeled as a labeled procurement process instance."),
        ("Step 2 Condition", "Manufacturer = Gore, USA; Type = GORE Select-M8", "instance metadata", "h2kg:hasMetadata", "Retained as membrane procurement metadata."),
        ("Step 2 Target", "SInt2", "instance metadata", "h2kg:Matter", "Represents the procured membrane material instance."),
        ("Step 3 Precursor", "SInt2", "instance metadata", "h2kg:Matter", "Uses the procured membrane instance as input."),
        ("Step 3 Technique", "LaserCut", "reuse existing term", "h2kg:Manufacturing", "Modeled as a labeled manufacturing instance rather than a new public TBox term."),
        ("Step 3 Condition", "-", "instance metadata", "h2kg:hasMetadata", "No explicit laser-cut condition was reported."),
        ("Step 3 Target", "SInt3", "instance metadata", "h2kg:Matter", "Represents the laser-cut membrane intermediate."),
        ("Step 4 Precursor A", "SInt1", "instance metadata", "h2kg:hasInputMaterial", "Connected as one input material to the hot-press step."),
        ("Step 4 Precursor B", "SInt3", "instance metadata", "h2kg:hasInputMaterial", "Connected as one input material to the hot-press step."),
        ("Step 4 Technique", "HotPress", "reuse existing term", "h2kg:Manufacturing", "Modeled as a labeled manufacturing instance rather than promoting a new method term in this round."),
        ("Step 4 Condition", "Temperature = 150 °C; Time = 3 min; Pressure = 400 psi", "instance metadata", "h2kg:hasMetadata", "Retained as hot-press metadata in the example graph."),
        ("Step 4 Target", "MEA", "reuse existing term", "h2kg:MEAAssembly", "Used as the main public sample anchor for the neutron-tomography case."),
    ]
    for field, value, classification, anchor, note in syn_rows:
        add("syn", field, value, classification, anchor, note)

    sp_rows = [
        ("Step 1 Precursor", "MEA", "reuse existing term", "h2kg:MEAAssembly", "Represents the MEA entering sample preparation."),
        ("Step 1 Technique", "Mount", "reuse existing term", "h2kg:Manufacturing", "Modeled as a labeled manufacturing instance."),
        ("Step 1 Condition", "-", "instance metadata", "h2kg:hasMetadata", "No explicit mount condition was reported."),
        ("Step 1 Target", "SPInt1", "instance metadata", "h2kg:Matter", "Represents the mounted-holder intermediate."),
        ("Step 2 Precursor", "Custom-built holder", "instance metadata", "h2kg:Matter", "Retained as a support material instance with holder metadata."),
        ("Step 2 Technique", "Mount", "reuse existing term", "h2kg:Manufacturing", "Modeled as a labeled manufacturing instance."),
        ("Step 2 Condition", "-", "instance metadata", "h2kg:hasMetadata", "No explicit mount condition was reported."),
        ("Step 2 Target", "SPInt1", "instance metadata", "h2kg:Matter", "Same intermediate as the mounted MEA/holder combination."),
        ("Step 3 Precursor A", "SPInt1", "instance metadata", "h2kg:hasInputMaterial", "Connected as one input material to the integration step."),
        ("Step 3 Precursor B", "Slip ring", "instance metadata", "h2kg:hasInputMaterial", "Connected as one input material to the integration step."),
        ("Step 3 AmountPrecursor", "2", "instance metadata", "h2kg:hasMetadata", "Stored as slip-ring metadata in the example graph."),
        ("Step 3 Technique", "Integrate", "reuse existing term", "h2kg:Manufacturing", "Modeled as a labeled integration process instance."),
        ("Step 3 Condition", "-", "instance metadata", "h2kg:hasMetadata", "No explicit integration condition was reported."),
        ("Step 3 Target", "Sample", "instance metadata", "h2kg:Matter", "Represents the final operando neutron-tomography sample context."),
    ]
    for field, value, classification, anchor, note in sp_rows:
        add("sp", field, value, classification, anchor, note)

    char_rows = [
        ("MeasurementMethod", "HR Neutron CT", "new ontology term", "h2kg:NeutronTomographyMeasurement", "Promoted as the public neutron-tomography measurement anchor."),
        ("MeasurementType", "operando", "instance metadata", "h2kg:hasMetadata", "Retained as acquisition metadata in round 1."),
        ("Specimen", "bulk material", "instance metadata", "h2kg:hasMetadata", "Retained as specimen metadata in round 1."),
        ("Characterization environment", "", "not modeled", "-", "No explicit value was populated."),
        ("Temperature", "23", "reuse existing term", "h2kg:Temperature", "Modeled as a parameter-setting instance linked to the neutron measurement."),
        ("TemperatureUnit", "°C", "reuse existing term", "h2kg:Temperature", "Unit captured through the quantity-value pattern on the temperature setting."),
        ("Humidity", "50", "reuse existing term", "h2kg:RelativeHumidity", "Modeled as a parameter-setting instance linked to the neutron measurement."),
        ("HumidityUnit", "%", "reuse existing term", "h2kg:RelativeHumidity", "Unit captured through the quantity-value pattern on the humidity setting."),
        ("Atmosphere", "air", "instance metadata", "h2kg:hasMetadata", "Retained as acquisition metadata in round 1."),
        ("AtmosphereUnit", "-", "instance metadata", "h2kg:hasMetadata", "Retained as acquisition metadata in round 1."),
        ("Pressure", "1", "instance metadata", "h2kg:hasMetadata", "Retained as acquisition metadata in round 1."),
        ("PressureUnit", "atm", "instance metadata", "h2kg:hasMetadata", "Retained as acquisition metadata in round 1."),
        ("Calibration", "adjusting lenses and apertures; adjusting the voltage", "instance metadata", "h2kg:hasMetadata", "Retained as calibration metadata in round 1."),
    ]
    for field, value, classification, anchor, note in char_rows:
        add("char", field, value, classification, anchor, note)

    inst_rows = [
        ("Facility", "Institut Laue–Langevin (ILL)", "instance metadata", "h2kg:hasMetadata", "Retained as instrument/facility metadata in round 1."),
        ("Beamline", "NeXT Beamline", "instance metadata", "h2kg:hasMetadata", "Retained as instrument/facility metadata in round 1."),
        ("BeamType", "Polychromatic cold neutron", "instance metadata", "h2kg:hasMetadata", "Retained as beam metadata in round 1."),
        ("MaximalWavelenght", "44593", "instance metadata", "h2kg:hasMetadata", "Retained as beam metadata because wavelength was not promoted in this round."),
        ("MaximalWavelenghtUnit", "A°", "instance metadata", "h2kg:hasMetadata", "Retained as beam metadata because wavelength was not promoted in this round."),
        ("Detector", "CCD camera (DW436N-BC, Oxford Instruments Andor, UK)", "instance metadata", "h2kg:hasMetadata", "Retained as detector metadata in round 1."),
        ("Lens", "Nikkon photo lens 20 mm", "instance metadata", "h2kg:hasMetadata", "Retained as optical metadata in round 1."),
        ("NeutronFlux", "2.7 x 10^6", "new ontology term", "h2kg:NeutronFlux", "Promoted as a reusable neutron-acquisition parameter."),
        ("NeutronFluxUnit", "n/cm2s", "new ontology term", "h2kg:NeutronFlux", "Retained on the neutron-flux setting metadata because exact QUDT specialization is deferred."),
        ("ExposureTime", "9", "reuse existing term", "h2kg:ExposureTime", "Modeled as a parameter-setting instance linked to the neutron measurement."),
        ("ExposureTimeUnit", "s", "reuse existing term", "h2kg:ExposureTime", "Unit captured through the quantity-value pattern on the exposure-time setting."),
        ("BeamSize", "30", "instance metadata", "h2kg:hasMetadata", "Retained as beam-shape metadata in round 1."),
        ("BeamSizeUnit", "cm2", "instance metadata", "h2kg:hasMetadata", "Retained as beam-shape metadata in round 1."),
        ("L/D value", "500", "instance metadata", "h2kg:hasMetadata", "Retained as collimation metadata in round 1."),
        ("Resolution", "0.5", "instance metadata", "h2kg:hasMetadata", "Retained as metadata because the promoted public anchor is `SpatialResolution`."),
        ("ResolutionUnit", "mm", "instance metadata", "h2kg:hasMetadata", "Retained as metadata because the promoted public anchor is `SpatialResolution`."),
        ("SampleDetectorDistance", "50", "new ontology term", "h2kg:SampleDetectorDistance", "Promoted as a reusable tomography parameter."),
        ("SampleDetectorDistanceUnit", "mm", "new ontology term", "h2kg:SampleDetectorDistance", "Unit captured through the quantity-value pattern on the sample-detector-distance setting."),
        ("Scintillator", "GADOX", "instance metadata", "h2kg:hasMetadata", "Retained as detector metadata in round 1."),
        ("ScintillatorThickness", "10", "instance metadata", "h2kg:hasMetadata", "Retained as detector metadata in round 1."),
        ("ScintillatorThicknessUnit", "um", "instance metadata", "h2kg:hasMetadata", "Retained as detector metadata in round 1."),
        ("Binning", "4", "instance metadata", "h2kg:hasMetadata", "Retained as acquisition metadata in round 1."),
        ("Focus", "20", "instance metadata", "h2kg:hasMetadata", "Retained as optical metadata in round 1."),
        ("FocusUnit", "mm", "instance metadata", "h2kg:hasMetadata", "Retained as optical metadata in round 1."),
        ("SpatialResolution", "300", "new ontology term", "h2kg:SpatialResolution", "Promoted as a reusable tomography parameter."),
        ("SpatialResolutionUnit", "um", "new ontology term", "h2kg:SpatialResolution", "Unit captured through the quantity-value pattern on the spatial-resolution setting."),
        ("PixelSize", "63.6", "reuse existing term", "h2kg:PixelSize", "Modeled as a parameter-setting instance linked to the neutron measurement."),
        ("PixelSizeUnit", "um", "reuse existing term", "h2kg:PixelSize", "Unit captured through the quantity-value pattern on the pixel-size setting."),
        ("FieldOfView", "26", "instance metadata", "h2kg:hasMetadata", "Retained as acquisition metadata in round 1."),
        ("FieldOfViewUnit", "mm2", "instance metadata", "h2kg:hasMetadata", "Retained as acquisition metadata in round 1."),
        ("CollimatorDiameter", "30", "instance metadata", "h2kg:hasMetadata", "Retained as collimator metadata in round 1."),
        ("CollimatorDiameterUnit", "mm", "instance metadata", "h2kg:hasMetadata", "Retained as collimator metadata in round 1."),
        ("PinholeSize", "30", "instance metadata", "h2kg:hasMetadata", "Retained as pinhole metadata in round 1."),
        ("PinholeSizeUnit", "mm", "instance metadata", "h2kg:hasMetadata", "Retained as pinhole metadata in round 1."),
        ("PinholeSampleDistance", "20", "instance metadata", "h2kg:hasMetadata", "Retained as pinhole metadata in round 1."),
        ("PinholeSampleDistanceUnit", "um", "instance metadata", "h2kg:hasMetadata", "Retained as pinhole metadata in round 1."),
        ("ImageFrequency", "40", "instance metadata", "h2kg:hasMetadata", "Retained as frequency metadata in round 1."),
        ("ImageFrequencyUnit", "Hz", "instance metadata", "h2kg:hasMetadata", "Retained as frequency metadata in round 1."),
        ("ProjectionNumber", "1440", "new ontology term", "h2kg:ProjectionNumber", "Promoted as a reusable tomography-acquisition parameter."),
        ("DataAcquisitionRate", "36", "instance metadata", "h2kg:hasMetadata", "Retained as acquisition metadata in round 1."),
        ("DataAcquisitionRateUnit", "s", "instance metadata", "h2kg:hasMetadata", "Retained as acquisition metadata in round 1."),
    ]
    for field, value, classification, anchor, note in inst_rows:
        add("inst", field, value, classification, anchor, note)

    pre_rows = [
        ("Step 1 Precursor", "RawData", "reuse existing term", "h2kg:TomographicProjectionDataset", "Mapped to the raw tomographic-projection dataset anchor."),
        ("Step 1 Technique", "Reconstruct", "reuse existing term", "h2kg:Process", "Modeled as a labeled preprocessing process instance."),
        ("Step 1 Condition", "-", "instance metadata", "h2kg:hasMetadata", "No explicit reconstruction condition was reported."),
        ("Step 1 Software", "Astra Toolbox", "instance metadata", "h2kg:hasMetadata", "Retained as preprocessing metadata in round 1."),
        ("Step 1 Target", "PPInt1", "instance metadata", "h2kg:Data", "Represents the first reconstruction intermediate dataset."),
        ("Step 2 Precursor", "PPInt1", "instance metadata", "h2kg:Data", "Represents the first reconstruction intermediate dataset."),
        ("Step 2 Technique", "DarkFieldCorrect", "reuse existing term", "h2kg:Process", "Modeled as a labeled preprocessing process instance."),
        ("Step 2 Software", "XXXX", "instance metadata", "h2kg:hasMetadata", "Retained as preprocessing metadata in round 1."),
        ("Step 2 Target", "PPInt2", "instance metadata", "h2kg:Data", "Represents the dark-field-corrected intermediate dataset."),
        ("Step 3 Precursor", "PPInt2", "instance metadata", "h2kg:Data", "Represents the dark-field-corrected intermediate dataset."),
        ("Step 3 Technique", "3DReconstruct", "reuse existing term", "h2kg:Process", "Modeled as a labeled preprocessing process instance."),
        ("Step 3 Condition", "Axis = Rotation axis", "instance metadata", "h2kg:hasMetadata", "Retained as preprocessing metadata in round 1."),
        ("Step 3 Software", "Avizo", "instance metadata", "h2kg:hasMetadata", "Retained as preprocessing metadata in round 1."),
        ("Step 3 Target", "PPInt3", "instance metadata", "h2kg:Data", "Represents the reconstructed tomographic intermediate dataset."),
        ("Step 4 Precursor", "PPInt3", "instance metadata", "h2kg:Data", "Represents the reconstructed tomographic intermediate dataset."),
        ("Step 4 Technique", "Threshold", "reuse existing term", "h2kg:Process", "Modeled as a labeled preprocessing process instance."),
        ("Step 4 Software", "XXXX", "instance metadata", "h2kg:hasMetadata", "Retained as preprocessing metadata in round 1."),
        ("Step 4 Target", "Post-processed tomograph", "new ontology term", "h2kg:TomographicReconstructionDataset", "Mapped to the public reconstructed tomograph dataset anchor."),
    ]
    for field, value, classification, anchor, note in pre_rows:
        add("pre", field, value, classification, anchor, note)

    anal_rows = [
        ("Step 1 Precursor", "Post-processed tomograph", "reuse existing term", "h2kg:TomographicReconstructionDataset", "Mapped to the reconstructed tomograph dataset anchor."),
        ("Step 1 Technique", "TortuosityMeasurement", "reuse existing term", "h2kg:Process", "Modeled as a labeled analysis process instance."),
        ("Step 1 Software", "MATLAB TauFactor", "instance metadata", "h2kg:hasMetadata", "Retained as analysis metadata in round 1."),
        ("Step 1 Target", "Tortuosity Factor", "new ontology term", "h2kg:TortuosityFactor", "Promoted as the public derived-property anchor for the TauFactor output."),
        ("Step 1 AmountTarget", "1.5", "new ontology term", "h2kg:TortuosityFactor", "Represented through a datapoint and quantity value in the example graph."),
        ("Step 2 Technique", "DropletAnalysis", "reuse existing term", "h2kg:Process", "Modeled as a labeled analysis process instance."),
        ("Step 2 Software", "LabelAnalysis, Avizo", "instance metadata", "h2kg:hasMetadata", "Retained as analysis metadata in round 1."),
        ("Step 2 Target", "AverageBaryCenter", "instance metadata", "h2kg:Metadata", "Explicitly retained as deferred metadata instead of promoting a weak public property term."),
        ("Step 2 AmountTarget", "5", "instance metadata", "h2kg:Metadata", "Stored on the deferred-barycenter metadata node."),
        ("Step 3 Target", "AverageArea", "new ontology term", "h2kg:AverageWaterDropletArea", "Promoted as a public water-dynamics property term."),
        ("Step 3 AmountTarget", "45 cm2", "new ontology term", "h2kg:AverageWaterDropletArea", "Represented through a datapoint and quantity value in the example graph."),
        ("Step 4 Target", "AverageNumber", "new ontology term", "h2kg:AverageWaterDropletCount", "Promoted as a public water-dynamics property term."),
        ("Step 4 AmountTarget", "45", "new ontology term", "h2kg:AverageWaterDropletCount", "Represented through a datapoint and quantity value in the example graph."),
    ]
    for field, value, classification, anchor, note in anal_rows:
        add("anal", field, value, classification, anchor, note)

    return rows


def _neutron_tomo_example_items() -> list[dict[str, Any]]:
    qv = f"{QUDT}QuantityValue"
    qv_num = f"{QUDT}numericValue"
    qv_unit = f"{QUDT}unit"
    qv_kind = f"{QUDT}quantityKind"
    label = f"{COMMON_CONTEXT['rdfs']}label"
    comment = f"{COMMON_CONTEXT['rdfs']}comment"
    title = f"{DCTERMS}title"
    creator = f"{DCTERMS}creator"
    contributor = f"{DCTERMS}contributor"
    issued = f"{DCTERMS}issued"
    date = f"{DCTERMS}date"
    identifier = f"{DCTERMS}identifier"
    source = f"{DCTERMS}source"
    extent = f"{DCTERMS}extent"
    fmt = f"{DCTERMS}format"
    was_generated_by = f"{PROV}wasGeneratedBy"
    was_associated_with = f"{PROV}wasAssociatedWith"

    def iri(local: str) -> str:
        return f"{NEUTRON_TOMO_EXAMPLE_NS}{local}"

    def h(local: str) -> str:
        return f"{H2KG}{local}"

    def lit(value: str, lang: str = "en") -> dict[str, str]:
        return {"@value": value, "@language": lang}

    def ref(value: str) -> dict[str, str]:
        return {"@id": value}

    return [
        {
            "@id": iri("source-record"),
            "@type": [h("Metadata")],
            title: [lit("Understanding water dynamics in operating fuel cells by operando neutron tomography: investigation of different flow field designs")],
            date: [{"@value": "2024-02-11", "@type": f"{XSD}date"}],
            h("hasIdentifier"): [{"@value": "8"}, {"@value": "Run derived DOI"}],
            comment: [
                lit("Source-sheet contradictions retained as metadata only: Topic = Battery; Device = Lithium Battery."),
                lit("Country: Germany; granularity level: Macrostructure; source link: link."),
            ],
            creator: [ref(iri("author-ralf-ziesche")), ref(iri("author-andre-colliard-granero"))],
            contributor: [ref(iri("institution-hzb")), ref(iri("funding-helmholtz-ai"))],
            source: [{"@value": "link"}],
        },
        {
            "@id": iri("publication-record"),
            "@type": [h("Metadata")],
            title: [lit("Understanding water dynamics in operating fuel cells by operando neutron tomography: investigation of different flow field designs")],
            identifier: [{"@value": "https://doi.org/10.1088/2515-7655/ad3984"}],
            issued: [{"@value": "2012-11-28", "@type": f"{XSD}date"}],
            comment: [
                lit("Journal: Materials Today; volume: 1; issue: 8; pages: 23-45."),
                lit("Published flag from source sheet: 1."),
            ],
            creator: [ref(iri("author-ralf-ziesche")), ref(iri("author-andre-colliard-granero"))],
        },
        {
            "@id": iri("author-ralf-ziesche"),
            "@type": [f"{PROV}Agent"],
            label: [lit("Ralf Ziesche")],
            h("hasMetadata"): [ref(iri("author-ralf-ziesche-metadata"))],
        },
        {
            "@id": iri("author-andre-colliard-granero"),
            "@type": [f"{PROV}Agent"],
            label: [lit("André Colliard Granero")],
            h("hasMetadata"): [ref(iri("author-andre-colliard-granero-metadata"))],
        },
        {
            "@id": iri("author-ralf-ziesche-metadata"),
            "@type": [h("Metadata")],
            identifier: [{"@value": "ORCID: 123-465-7765"}, {"@value": "Email: ralf.ziesche@yahoo.ru"}],
        },
        {
            "@id": iri("author-andre-colliard-granero-metadata"),
            "@type": [h("Metadata")],
            identifier: [{"@value": "ORCID: 321-321-3211"}, {"@value": "Email: andyhuebsch@gmail.mx"}],
        },
        {
            "@id": iri("institution-hzb"),
            "@type": [f"{PROV}Agent"],
            label: [lit("HZB")],
        },
        {
            "@id": iri("funding-helmholtz-ai"),
            "@type": [f"{PROV}Agent"],
            label: [lit("Helmholtz AI")],
        },
        {
            "@id": iri("gas-diffusion-electrode"),
            "@type": [h("Matter")],
            label: [lit("Gas diffusion electrode precursor")],
            h("hasMetadata"): [ref(iri("gas-diffusion-electrode-metadata"))],
        },
        {
            "@id": iri("gas-diffusion-electrode-metadata"),
            "@type": [h("Metadata")],
            comment: [
                lit("Amount: 2."),
                lit("Manufacturer: HyPlat, South Africa; Pt loading = 0.4 mg/cm2."),
            ],
        },
        {
            "@id": iri("membrane-precursor"),
            "@type": [h("Matter")],
            label: [lit("Membrane precursor")],
            h("hasMetadata"): [ref(iri("membrane-precursor-metadata"))],
        },
        {
            "@id": iri("membrane-precursor-metadata"),
            "@type": [h("Metadata")],
            comment: [lit("Manufacturer = Gore, USA; type = GORE Select-M8.")],
        },
        {
            "@id": iri("laser-cut-membrane"),
            "@type": [h("Matter")],
            label: [lit("Laser-cut membrane intermediate")],
        },
        {
            "@id": iri("operando-holder"),
            "@type": [h("Matter")],
            label: [lit("Custom-built holder")],
        },
        {
            "@id": iri("slip-ring"),
            "@type": [h("Matter")],
            label: [lit("Slip ring")],
            h("hasMetadata"): [ref(iri("slip-ring-metadata"))],
        },
        {
            "@id": iri("slip-ring-metadata"),
            "@type": [h("Metadata")],
            comment: [lit("Sheet amount: 2.")],
        },
        {
            "@id": iri("mounted-holder-intermediate"),
            "@type": [h("Matter")],
            label: [lit("Mounted MEA/holder intermediate")],
        },
        {
            "@id": iri("operando-neutron-sample"),
            "@type": [h("Matter")],
            label: [lit("Operando neutron tomography sample context")],
            h("hasMetadata"): [ref(iri("operando-neutron-sample-metadata"))],
        },
        {
            "@id": iri("operando-neutron-sample-metadata"),
            "@type": [h("Metadata")],
            comment: [lit("Sheet target label: Sample; holder integration and slip-ring context retained as metadata.")],
        },
        {
            "@id": iri("mea-assembly"),
            "@type": [h("Matter"), h("MEAAssembly")],
            label: [lit("MEA assembly used for operando neutron tomography")],
        },
        {
            "@id": iri("procure-gde"),
            "@type": [h("Process")],
            label: [lit("Procure gas diffusion electrode")],
            h("hasOutputMaterial"): [ref(iri("gas-diffusion-electrode"))],
        },
        {
            "@id": iri("procure-membrane"),
            "@type": [h("Process")],
            label: [lit("Procure membrane")],
            h("hasOutputMaterial"): [ref(iri("membrane-precursor"))],
        },
        {
            "@id": iri("laser-cut-step"),
            "@type": [h("Manufacturing")],
            label: [lit("Laser-cut membrane")],
            h("hasInputMaterial"): [ref(iri("membrane-precursor"))],
            h("hasOutputMaterial"): [ref(iri("laser-cut-membrane"))],
        },
        {
            "@id": iri("hot-press-step"),
            "@type": [h("Manufacturing")],
            label: [lit("Hot-press gas diffusion electrode and laser-cut membrane into MEA assembly")],
            h("hasInputMaterial"): [ref(iri("gas-diffusion-electrode")), ref(iri("laser-cut-membrane"))],
            h("hasOutputMaterial"): [ref(iri("mea-assembly"))],
            h("hasMetadata"): [ref(iri("hot-press-step-metadata"))],
        },
        {
            "@id": iri("hot-press-step-metadata"),
            "@type": [h("Metadata")],
            comment: [lit("Temperature = 150 °C; time = 3 min; pressure = 400 psi.")],
        },
        {
            "@id": iri("mount-step"),
            "@type": [h("Manufacturing")],
            label: [lit("Mount MEA on custom-built holder")],
            h("hasInputMaterial"): [ref(iri("mea-assembly")), ref(iri("operando-holder"))],
            h("hasOutputMaterial"): [ref(iri("mounted-holder-intermediate"))],
        },
        {
            "@id": iri("integrate-step"),
            "@type": [h("Manufacturing")],
            label: [lit("Integrate mounted assembly with slip rings into operando neutron sample")],
            h("hasInputMaterial"): [ref(iri("mounted-holder-intermediate")), ref(iri("slip-ring"))],
            h("hasOutputMaterial"): [ref(iri("operando-neutron-sample"))],
        },
        {
            "@id": iri("neutron-measurement-001"),
            "@type": [h("Measurement"), h("NeutronTomographyMeasurement")],
            label: [lit("Operando neutron tomography pilot measurement")],
            h("hasInputMaterial"): [ref(iri("mea-assembly"))],
            h("usesInstrument"): [ref(iri("neutron-instrument-001"))],
            h("hasOutputData"): [
                ref(iri("raw-projection-dataset")),
                ref(iri("reconstructed-tomograph-dataset")),
                ref(iri("neutron-experiment-dataset")),
            ],
            h("hasParameter"): [
                ref(iri("pixel-size-setting")),
                ref(iri("exposure-time-setting")),
                ref(iri("projection-number-setting")),
                ref(iri("neutron-flux-setting")),
                ref(iri("spatial-resolution-setting")),
                ref(iri("sample-detector-distance-setting")),
                ref(iri("temperature-setting")),
                ref(iri("relative-humidity-setting")),
            ],
            h("hasMetadata"): [
                ref(iri("neutron-acquisition-metadata")),
                ref(iri("source-record")),
                ref(iri("publication-record")),
            ],
            was_associated_with: [ref(iri("author-ralf-ziesche")), ref(iri("author-andre-colliard-granero"))],
            source: [ref(iri("publication-record"))],
        },
        {
            "@id": iri("neutron-instrument-001"),
            "@type": [h("Instrument"), h("NeutronTomographyInstrument")],
            label: [lit("Neutron tomography instrument used in the pilot case")],
            h("hasMetadata"): [ref(iri("neutron-instrument-metadata"))],
        },
        {
            "@id": iri("neutron-instrument-metadata"),
            "@type": [h("Metadata")],
            comment: [
                lit("Facility: Institut Laue–Langevin (ILL); beamline: NeXT Beamline; beam type: polychromatic cold neutron."),
                lit("Detector: CCD camera (DW436N-BC, Oxford Instruments Andor, UK); lens: Nikkon photo lens 20 mm; scintillator: GADOX."),
                lit("Binning = 4; field of view = 26 mm2; collimator diameter = 30 mm; pinhole size = 30 mm; pinhole-sample distance = 20 um; image frequency = 40 Hz."),
            ],
        },
        {
            "@id": iri("raw-projection-dataset"),
            "@type": [h("Data"), h("TomographicProjectionDataset")],
            label: [lit("Raw neutron tomographic projection dataset")],
            h("hasMetadata"): [ref(iri("raw-projection-dataset-metadata"))],
        },
        {
            "@id": iri("raw-projection-dataset-metadata"),
            "@type": [h("Metadata")],
            fmt: [{"@value": "png"}],
            extent: [{"@value": "200 MB"}, {"@value": "1024 x 1024 x 1300 voxels"}],
            comment: [lit("Filename: TestNeutronTomography.tif."), lit("Mask exists: no; mask link: link.")],
        },
        {
            "@id": iri("preprocessing-step"),
            "@type": [h("Process")],
            label: [lit("Reconstruction, dark-field correction, and thresholding")],
            h("hasInputData"): [ref(iri("raw-projection-dataset"))],
            h("hasOutputData"): [ref(iri("reconstructed-tomograph-dataset"))],
            h("hasMetadata"): [ref(iri("preprocessing-step-metadata"))],
        },
        {
            "@id": iri("preprocessing-step-metadata"),
            "@type": [h("Metadata")],
            comment: [
                lit("Worksheet steps retained as labeled process metadata: Reconstruct, DarkFieldCorrect, 3DReconstruct, Threshold."),
                lit("Software metadata: Astra Toolbox; Avizo; unresolved placeholder software values XXXX."),
                lit("3D reconstruction metadata: axis = rotation axis."),
            ],
        },
        {
            "@id": iri("reconstructed-tomograph-dataset"),
            "@type": [h("Data"), h("TomographicReconstructionDataset")],
            label: [lit("Post-processed tomographic reconstruction dataset")],
            h("hasMetadata"): [ref(iri("reconstructed-tomograph-dataset-metadata"))],
        },
        {
            "@id": iri("reconstructed-tomograph-dataset-metadata"),
            "@type": [h("Metadata")],
            comment: [lit("Sheet target label: Post-processed tomograph."), lit("Used as the input dataset for tortuosity and droplet analysis.")],
        },
        {
            "@id": iri("neutron-experiment-dataset"),
            "@type": [h("Data"), h("ExperimentDataset")],
            label: [lit("Neutron-tomography experiment summary dataset")],
            h("hasMetadata"): [ref(iri("neutron-experiment-dataset-metadata"))],
        },
        {
            "@id": iri("neutron-experiment-dataset-metadata"),
            "@type": [h("Metadata")],
            comment: [lit("Aggregates raw projections, reconstructed tomograph, and derived water-dynamics results for the pilot case.")],
        },
        {
            "@id": iri("analysis-step"),
            "@type": [h("Process")],
            label: [lit("Tortuosity and droplet analysis")],
            h("hasInputData"): [ref(iri("reconstructed-tomograph-dataset"))],
            h("hasOutputData"): [ref(iri("neutron-experiment-dataset"))],
            h("hasMetadata"): [ref(iri("analysis-step-metadata")), ref(iri("average-barycenter-metadata"))],
        },
        {
            "@id": iri("analysis-step-metadata"),
            "@type": [h("Metadata")],
            comment: [
                lit("TortuosityMeasurement software: MATLAB TauFactor."),
                lit("DropletAnalysis software: LabelAnalysis, Avizo."),
            ],
        },
        {
            "@id": iri("average-barycenter-metadata"),
            "@type": [h("Metadata")],
            comment: [
                lit("Deferred round-1 field: AverageBaryCenter = 5."),
                lit("The workbook does not provide stable axis/unit semantics, so barycenter remains metadata rather than a public H2KG property term."),
            ],
        },
        {
            "@id": iri("tortuosity-factor-datapoint"),
            "@type": [h("DataPoint")],
            label: [lit("Tortuosity-factor datapoint")],
            h("ofProperty"): [ref(h("TortuosityFactor"))],
            h("fromMeasurement"): [ref(iri("neutron-measurement-001"))],
            h("hasQuantityValue"): [ref(iri("tortuosity-factor-qv"))],
            was_generated_by: [ref(iri("analysis-step"))],
            source: [ref(iri("publication-record"))],
        },
        {
            "@id": iri("tortuosity-factor-qv"),
            "@type": [qv],
            qv_num: [{"@value": "1.5", "@type": f"{XSD}decimal"}],
            qv_kind: [ref("http://qudt.org/vocab/quantitykind/Dimensionless")],
        },
        {
            "@id": iri("average-water-droplet-area-datapoint"),
            "@type": [h("DataPoint")],
            label: [lit("Average water droplet area datapoint")],
            h("ofProperty"): [ref(h("AverageWaterDropletArea"))],
            h("fromMeasurement"): [ref(iri("neutron-measurement-001"))],
            h("hasQuantityValue"): [ref(iri("average-water-droplet-area-qv"))],
            was_generated_by: [ref(iri("analysis-step"))],
            source: [ref(iri("publication-record"))],
        },
        {
            "@id": iri("average-water-droplet-area-qv"),
            "@type": [qv],
            qv_num: [{"@value": "45", "@type": f"{XSD}decimal"}],
            qv_unit: [ref(f"{UNIT}CentiM2")],
            qv_kind: [ref("http://qudt.org/vocab/quantitykind/Area")],
        },
        {
            "@id": iri("average-water-droplet-count-datapoint"),
            "@type": [h("DataPoint")],
            label: [lit("Average water droplet count datapoint")],
            h("ofProperty"): [ref(h("AverageWaterDropletCount"))],
            h("fromMeasurement"): [ref(iri("neutron-measurement-001"))],
            h("hasQuantityValue"): [ref(iri("average-water-droplet-count-qv"))],
            was_generated_by: [ref(iri("analysis-step"))],
            source: [ref(iri("publication-record"))],
        },
        {
            "@id": iri("average-water-droplet-count-qv"),
            "@type": [qv],
            qv_num: [{"@value": "45", "@type": f"{XSD}integer"}],
            qv_kind: [ref("http://qudt.org/vocab/quantitykind/Count")],
        },
        {
            "@id": iri("pixel-size-setting"),
            "@type": [h("Parameter"), h("PixelSize")],
            label: [lit("Neutron tomography pixel-size setting")],
            h("hasQuantityValue"): [ref(iri("pixel-size-setting-qv"))],
        },
        {
            "@id": iri("pixel-size-setting-qv"),
            "@type": [qv],
            qv_num: [{"@value": "63.6", "@type": f"{XSD}decimal"}],
            qv_unit: [ref(f"{UNIT}MicroM")],
            qv_kind: [ref("http://qudt.org/vocab/quantitykind/Length")],
        },
        {
            "@id": iri("exposure-time-setting"),
            "@type": [h("Parameter"), h("ExposureTime")],
            label: [lit("Neutron tomography exposure-time setting")],
            h("hasQuantityValue"): [ref(iri("exposure-time-setting-qv"))],
        },
        {
            "@id": iri("exposure-time-setting-qv"),
            "@type": [qv],
            qv_num: [{"@value": "9", "@type": f"{XSD}decimal"}],
            qv_unit: [ref(f"{UNIT}SEC")],
            qv_kind: [ref("http://qudt.org/vocab/quantitykind/Time")],
        },
        {
            "@id": iri("projection-number-setting"),
            "@type": [h("Parameter"), h("ProjectionNumber")],
            label: [lit("Neutron tomography projection-number setting")],
            h("hasQuantityValue"): [ref(iri("projection-number-setting-qv"))],
        },
        {
            "@id": iri("projection-number-setting-qv"),
            "@type": [qv],
            qv_num: [{"@value": "1440", "@type": f"{XSD}integer"}],
            qv_kind: [ref("http://qudt.org/vocab/quantitykind/Count")],
        },
        {
            "@id": iri("neutron-flux-setting"),
            "@type": [h("Parameter"), h("NeutronFlux")],
            label: [lit("Neutron flux setting")],
            h("hasQuantityValue"): [ref(iri("neutron-flux-setting-qv"))],
            h("hasMetadata"): [ref(iri("neutron-flux-setting-metadata"))],
        },
        {
            "@id": iri("neutron-flux-setting-qv"),
            "@type": [qv],
            qv_num: [{"@value": "2700000", "@type": f"{XSD}decimal"}],
        },
        {
            "@id": iri("neutron-flux-setting-metadata"),
            "@type": [h("Metadata")],
            comment: [lit("Sheet unit retained as metadata in round 1: n/cm2s. Exact QUDT specialization is deferred.")],
        },
        {
            "@id": iri("spatial-resolution-setting"),
            "@type": [h("Parameter"), h("SpatialResolution")],
            label: [lit("Neutron tomography spatial-resolution setting")],
            h("hasQuantityValue"): [ref(iri("spatial-resolution-setting-qv"))],
        },
        {
            "@id": iri("spatial-resolution-setting-qv"),
            "@type": [qv],
            qv_num: [{"@value": "300", "@type": f"{XSD}decimal"}],
            qv_unit: [ref(f"{UNIT}MicroM")],
            qv_kind: [ref("http://qudt.org/vocab/quantitykind/Length")],
        },
        {
            "@id": iri("sample-detector-distance-setting"),
            "@type": [h("Parameter"), h("SampleDetectorDistance")],
            label: [lit("Sample-detector-distance setting")],
            h("hasQuantityValue"): [ref(iri("sample-detector-distance-setting-qv"))],
        },
        {
            "@id": iri("sample-detector-distance-setting-qv"),
            "@type": [qv],
            qv_num: [{"@value": "50", "@type": f"{XSD}decimal"}],
            qv_unit: [ref(f"{UNIT}MilliM")],
            qv_kind: [ref("http://qudt.org/vocab/quantitykind/Length")],
        },
        {
            "@id": iri("temperature-setting"),
            "@type": [h("Parameter"), h("Temperature")],
            label: [lit("Neutron tomography acquisition temperature setting")],
            h("hasQuantityValue"): [ref(iri("temperature-setting-qv"))],
        },
        {
            "@id": iri("temperature-setting-qv"),
            "@type": [qv],
            qv_num: [{"@value": "23", "@type": f"{XSD}decimal"}],
            qv_unit: [ref(f"{UNIT}DEG_C")],
            qv_kind: [ref("http://qudt.org/vocab/quantitykind/ThermodynamicTemperature")],
        },
        {
            "@id": iri("relative-humidity-setting"),
            "@type": [h("Parameter"), h("RelativeHumidity")],
            label: [lit("Neutron tomography acquisition relative-humidity setting")],
            h("hasQuantityValue"): [ref(iri("relative-humidity-setting-qv"))],
        },
        {
            "@id": iri("relative-humidity-setting-qv"),
            "@type": [qv],
            qv_num: [{"@value": "50", "@type": f"{XSD}decimal"}],
            qv_unit: [ref(f"{UNIT}PERCENT")],
            qv_kind: [ref("http://qudt.org/vocab/quantitykind/RelativeHumidity")],
        },
        {
            "@id": iri("neutron-acquisition-metadata"),
            "@type": [h("Metadata")],
            comment: [
                lit("Measurement type: operando; specimen: bulk material."),
                lit("Atmosphere: air; pressure: 1 atm."),
                lit("Calibration note: adjusting lenses and apertures; adjusting the voltage."),
                lit("Additional sheet metadata retained locally: beam size = 30 cm2; L/D value = 500; field of view = 26 mm2; data acquisition rate = 36 s."),
            ],
        },
    ]


def _neutron_tomo_validation_note() -> str:
    return """# NeutronTomo Validation Note

This controlled `NeutronTomo` round adds a small public neutron-tomography neighborhood to H2KG while keeping worksheet-specific facility and preprocessing detail out of the public TBox.

Introduced public ontology terms:

- `h2kg:NeutronTomographyMeasurement`
- `h2kg:NeutronTomographyInstrument`
- `h2kg:TomographicProjectionDataset`
- `h2kg:TomographicReconstructionDataset`
- `h2kg:ProjectionNumber`
- `h2kg:NeutronFlux`
- `h2kg:SpatialResolution`
- `h2kg:SampleDetectorDistance`
- `h2kg:TortuosityFactor`
- `h2kg:AverageWaterDropletArea`
- `h2kg:AverageWaterDropletCount`

Reused public ontology terms:

- `h2kg:MEAAssembly`
- `h2kg:Temperature`
- `h2kg:RelativeHumidity`
- `h2kg:PixelSize`
- `h2kg:ExposureTime`
- `h2kg:ExperimentDataset`
- `h2kg:DataPoint`
- `h2kg:Process`
- `h2kg:Manufacturing`
- `h2kg:Metadata`
- `h2kg:hasMetadata`

What remained instance metadata:

- publication and organizational fields
- facility, beamline, detector, lens, scintillator, and beam descriptors
- operando/specimen/atmosphere/pressure context
- contradictory sheet labels such as `Topic = Battery` and `Device = Lithium Battery`
- preprocessing software and workflow labels
- deferred `AverageBaryCenter` result semantics

What was intentionally deferred:

- a public TBox term for `AverageBaryCenter`
- public TBox terms for worksheet preprocessing labels such as `Reconstruct`, `DarkFieldCorrect`, `3DReconstruct`, and `Threshold`
- public TBox terms for facility-specific hardware details
- exact QUDT specialization of neutron flux beyond the reusable public parameter anchor
"""


def _neutron_tomo_case_summary() -> str:
    return """# NeutronTomo Case Summary

H2KG captures the neutron-tomography case as an operando fuel-cell characterization pattern centered on `h2kg:NeutronTomographyMeasurement`. The public TBox connects the measurement to `h2kg:MEAAssembly`, `h2kg:NeutronTomographyInstrument`, a projection-data output (`h2kg:TomographicProjectionDataset`), a reconstructed tomograph output (`h2kg:TomographicReconstructionDataset`), and the main acquisition parameters `h2kg:PixelSize`, `h2kg:ExposureTime`, `h2kg:ProjectionNumber`, `h2kg:NeutronFlux`, `h2kg:SpatialResolution`, `h2kg:SampleDetectorDistance`, `h2kg:Temperature`, and `h2kg:RelativeHumidity`.

The example graph then shows how worksheet-grounded preprocessing and analysis steps are represented conservatively as labeled `h2kg:Process` instances rather than promoted public classes. Derived scientific outcomes are expressed as datapoints for `h2kg:TortuosityFactor`, `h2kg:AverageWaterDropletArea`, and `h2kg:AverageWaterDropletCount`, with source provenance and deferred ambiguous worksheet content preserved through `h2kg:Metadata`.
"""


def _neutron_tomo_follow_on_gaps() -> str:
    return """# NeutronTomo Follow-On Gaps

- Decide whether reconstruction labels shared with synchrotron tomography should be promoted into reusable public analysis-process terms after the synchrotron rounds.
- Revisit the exact public semantics of `NeutronFlux` and align it to a more specific external quantity-kind anchor if that becomes stable across neutron methods.
- Decide whether `AverageBaryCenter` should become a reusable property after additional neutron or synchrotron cases establish stable axis and unit semantics.
- Evaluate whether `FieldOfView`, `BeamSize`, and `ImageFrequency` recur strongly enough across tomography methods to justify promotion from metadata to public parameter terms.
- Revisit whether `TomographicReconstructionDataset` should also be linked to other future tomography methods for a cross-method public Explore neighborhood.
"""


def _neutron_tomo_manuscript_figure() -> str:
    return """# NeutronTomo Manuscript Figure Guidance

Use a combined ontology-workflow figure with **TBox-only standalone nodes** and worksheet-derived values shown only as annotations or metadata callouts.

Recommended backbone:

`Matter -> Manufacturing -> Neutron Tomography Measurement -> Tomographic Projection Dataset -> Process (reconstruction / preprocessing) -> Tomographic Reconstruction Dataset -> Process (analysis) -> DataPoint -> {Tortuosity Factor, Average Water Droplet Area, Average Water Droplet Count}`

Supporting families:

- Above acquisition:
  - `Pixel Size`
  - `Exposure Time`
  - `Projection Number`
  - `Neutron Flux`
  - `Spatial Resolution`
  - `Sample Detector Distance`
  - `Temperature`
  - `Relative Humidity`
- Below acquisition:
  - `Neutron Tomography Instrument`
- Metadata callouts:
  - MEA assembly and holder context
  - beamline, detector, and scintillator details
  - raw and reconstructed dataset details
  - publication/provenance details
  - deferred `AverageBaryCenter` note

Important rule:

- Every standalone node in the figure must be retrievable from the public H2KG TBox and therefore visible in Explore after regeneration.
- Worksheet values such as `NeXT Beamline`, `GADOX`, `Astra Toolbox`, `Avizo`, DOI, file dimensions, and contradictory battery/device labels remain annotations or metadata-callout text, not standalone ontology nodes.
"""


def _neutron_tomo_manuscript_table() -> str:
    return """# NeutronTomo Manuscript Companion Table

| NeutronTomo case element | H2KG ontology anchor | Example case value | Figure treatment |
| --- | --- | --- | --- |
| Sample context | `h2kg:Matter` / `h2kg:MEAAssembly` | operando MEA assembly | standalone ontology node |
| Assembly route | `h2kg:Manufacturing` | buy, laser cut, hot press, mount, integrate | standalone ontology node with annotation |
| Neutron acquisition | `h2kg:NeutronTomographyMeasurement` | HR neutron CT | standalone ontology node |
| Neutron instrument | `h2kg:NeutronTomographyInstrument` | ILL NeXT beamline setup | standalone ontology node with metadata callout |
| Pixel size | `h2kg:PixelSize` | 63.6 um | parameter callout |
| Exposure time | `h2kg:ExposureTime` | 9 s | parameter callout |
| Projection number | `h2kg:ProjectionNumber` | 1440 | parameter callout |
| Neutron flux | `h2kg:NeutronFlux` | 2.7 x 10^6 n/cm2s | parameter callout |
| Spatial resolution | `h2kg:SpatialResolution` | 300 um | parameter callout |
| Sample-detector distance | `h2kg:SampleDetectorDistance` | 50 mm | parameter callout |
| Acquisition environment | `h2kg:Temperature`, `h2kg:RelativeHumidity` | 23 °C; 50 % | parameter callout |
| Raw tomography data | `h2kg:TomographicProjectionDataset` | TestNeutronTomography.tif | standalone ontology node |
| Preprocessing | `h2kg:Process` | reconstruct, dark-field correction, 3D reconstruction, threshold | standalone ontology node with annotation |
| Reconstructed tomograph | `h2kg:TomographicReconstructionDataset` | post-processed tomograph | standalone ontology node |
| Analysis | `h2kg:Process` | tortuosity analysis; droplet analysis | standalone ontology node with annotation |
| Derived tortuosity result | `h2kg:TortuosityFactor` | 1.5 | final property node via datapoint |
| Derived droplet-area result | `h2kg:AverageWaterDropletArea` | 45 cm2 | final property node via datapoint |
| Derived droplet-count result | `h2kg:AverageWaterDropletCount` | 45 | final property node via datapoint |
| Deferred ambiguous result | `h2kg:Metadata` | AverageBaryCenter = 5 | metadata callout |
| Provenance | `h2kg:Metadata` + `h2kg:hasMetadata` | DOI, authors, facility, file details | metadata callout |
"""


def _neutron_tomo_readme(generated_files: list[Path]) -> str:
    file_list = "\n".join(f"- `{path.name}`" for path in generated_files)
    return f"""# NeutronTomo Pilot Package

This package contains the controlled `NeutronTomo` integration outputs for H2KG.

Generated files:

{file_list}

Highlights:

- Public measurement anchor: `h2kg:NeutronTomographyMeasurement`
- Public instrument anchor: `h2kg:NeutronTomographyInstrument`
- Public dataset anchors: `h2kg:TomographicProjectionDataset`, `h2kg:TomographicReconstructionDataset`
- Public derived-result anchors: `h2kg:TortuosityFactor`, `h2kg:AverageWaterDropletArea`, `h2kg:AverageWaterDropletCount`
- Deferred ambiguous worksheet result: `AverageBaryCenter` retained as metadata only
"""


def _missing_terms_note(missing: list[str]) -> str:
    lines = ["# NeutronTomo Pilot Package", "", "The pilot package was not generated because the current source ontology is missing the required terms:", ""]
    lines.extend(f"- `{term}`" for term in missing)
    lines.append("")
    return "\n".join(lines)
