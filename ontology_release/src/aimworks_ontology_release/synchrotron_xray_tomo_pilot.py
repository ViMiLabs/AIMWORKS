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
XSD = COMMON_CONTEXT["xsd"]
SXTM_EXAMPLE_NS = "https://w3id.org/h2kg/examples/synchrotron-xray-tomo#"

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
    f"{H2KG}fromMeasurement",
    f"{H2KG}hasIdentifier",
    f"{H2KG}XRayComputedTomographyMeasurement",
    f"{H2KG}XRayCTInstrument",
    f"{H2KG}XRayBeamEnergy",
    f"{H2KG}ExposureTime",
    f"{H2KG}PixelSize",
    f"{H2KG}ProjectionNumber",
    f"{H2KG}SpatialResolution",
    f"{H2KG}SampleDetectorDistance",
    f"{H2KG}Temperature",
    f"{H2KG}RelativeHumidity",
    f"{H2KG}Magnification",
    f"{H2KG}TomographicProjectionDataset",
    f"{H2KG}TomographicReconstructionDataset",
    f"{H2KG}ExperimentDataset",
}


def build_synchrotron_xray_tomo_pilot_package(
    input_path: str | Path,
    output_root: str | Path,
) -> dict[str, Any]:
    input_path = Path(input_path)
    output_root = Path(output_root)
    target_dir = ensure_dir(output_root / "examples" / "synchrotron_xray_tomo_pilot")
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

    mapping_rows = _synchrotron_xray_tomo_mapping_rows()
    example_items = _synchrotron_xray_tomo_example_items()
    generated_files = [
        _write_mapping_matrix(target_dir / "synchrotron_xray_tomo_mapping_matrix.csv", mapping_rows),
        _write_mapping_matrix_markdown(target_dir / "synchrotron_xray_tomo_mapping_matrix.md", mapping_rows),
        dump_json(
            target_dir / "synchrotron_xray_tomo_example.jsonld",
            {"@context": {**COMMON_CONTEXT, "sxrt": SXTM_EXAMPLE_NS}, "@graph": example_items},
        ),
        dump_turtle_items(target_dir / "synchrotron_xray_tomo_example.ttl", example_items),
        write_text(target_dir / "synchrotron_xray_tomo_validation_note.md", _synchrotron_xray_tomo_validation_note()),
        write_text(target_dir / "synchrotron_xray_tomo_case_summary.md", _synchrotron_xray_tomo_case_summary()),
        write_text(target_dir / "synchrotron_xray_tomo_follow_on_gaps.md", _synchrotron_xray_tomo_follow_on_gaps()),
        write_text(target_dir / "synchrotron_xray_tomo_manuscript_figure.md", _synchrotron_xray_tomo_manuscript_figure()),
        write_text(target_dir / "synchrotron_xray_tomo_manuscript_table.md", _synchrotron_xray_tomo_manuscript_table()),
    ]
    write_text(target_dir / "README.md", _synchrotron_xray_tomo_readme(generated_files))
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
        fieldnames=["source_sheet", "section", "field", "example_value", "classification", "h2kg_anchor", "note"],
    )
    writer.writeheader()
    writer.writerows(rows)
    return write_text(path, buffer.getvalue())


def _write_mapping_matrix_markdown(path: Path, rows: list[dict[str, str]]) -> Path:
    lines = [
        "# Synchrotron X-Ray Tomography Mapping Matrix",
        "",
        "This matrix uses `SynchrotronTomo` as the canonical sheet and records `SynchrotronRadio` as a duplicate-structure validation sheet with explicitly listed deviations.",
        "",
        "| Source sheet | Section | Field | Example value | Classification | H2KG anchor | Note |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {source_sheet} | {section} | {field} | {example_value} | {classification} | {h2kg_anchor} | {note} |".format(
                **{key: value.replace("|", "\\|") for key, value in row.items()}
            )
        )
    lines.append("")
    return write_text(path, "\n".join(lines))


def _synchrotron_xray_tomo_mapping_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    def add(sheet: str, section: str, field: str, value: str, classification: str, anchor: str, note: str) -> None:
        rows.append(
            {
                "source_sheet": sheet,
                "section": section,
                "field": field,
                "example_value": value,
                "classification": classification,
                "h2kg_anchor": anchor,
                "note": note,
            }
        )

    canonical = [
        ("org", "ExperimentTitle", "Synchrotron x-ray tomography of dry electrode", "instance metadata", "h2kg:hasMetadata + dcterms:title", "Canonical workbook title retained as source metadata."),
        ("org", "ExperimentID", "2", "instance metadata", "h2kg:hasMetadata + h2kg:hasIdentifier", "Stored as source-record identifier metadata."),
        ("org", "Measurement-ID", "Run derived DOI", "instance metadata", "h2kg:hasMetadata + h2kg:hasIdentifier", "Stored as source-measurement identifier metadata."),
        ("org", "UploadDate", "44845", "instance metadata", "h2kg:hasMetadata", "Excel serial date retained as source metadata in round 1."),
        ("org", "Institution", "HIU", "instance metadata", "prov:Agent", "Represented as institutional provenance metadata."),
        ("org", "FoundingBody", "BASF", "instance metadata", "prov:Agent", "Represented as funding provenance metadata."),
        ("org", "Country", "Germany", "instance metadata", "h2kg:hasMetadata", "Retained as source metadata."),
        ("org", "Author", "Kerstin Koble; Andre Colliard Granero", "instance metadata", "prov:Agent", "Retained as author provenance metadata."),
        ("org", "ORCID", "123-465-4789; 321-321-3211", "instance metadata", "h2kg:hasMetadata", "Stored as author metadata."),
        ("org", "Email", "andyhuebsch@gmail.mx; mustermann@yahoo.ru", "instance metadata", "h2kg:hasMetadata", "Stored as author metadata."),
        ("org", "Published", "1", "instance metadata", "h2kg:hasMetadata", "Retained as source metadata."),
        ("org", "Publication", "Synchrotron x-ray tomography of dry electrode", "instance metadata", "h2kg:hasMetadata + dcterms:title", "Retained as publication metadata."),
        ("org", "DOI", "https://doi.org/10.3390/35654654654", "instance metadata", "h2kg:hasMetadata + dcterms:identifier", "Retained as publication metadata."),
        ("org", "Journal", "Nature", "instance metadata", "h2kg:hasMetadata", "Retained as publication metadata."),
        ("org", "Volume", "41", "instance metadata", "h2kg:hasMetadata", "Retained as publication metadata."),
        ("org", "Issue", "5", "instance metadata", "h2kg:hasMetadata", "Retained as publication metadata."),
        ("org", "Pages", "6456-6541", "instance metadata", "h2kg:hasMetadata", "Retained as publication metadata."),
        ("org", "PublicationDate", "41215", "instance metadata", "h2kg:hasMetadata", "Excel serial date retained as publication metadata in round 1."),
        ("org", "Topic", "VRFB", "instance metadata", "h2kg:hasMetadata", "Out-of-scope study label retained only as source metadata."),
        ("org", "Device", "VRFB", "instance metadata", "h2kg:hasMetadata", "Out-of-scope study label retained only as source metadata."),
        ("org", "Component", "Electrode", "instance metadata", "h2kg:hasMetadata", "Retained as source metadata rather than a public H2KG scope anchor."),
        ("org", "Subcomponent", "Bubble", "instance metadata", "h2kg:hasMetadata", "Retained as source metadata."),
        ("org", "Granularity Level", "Microstructure", "instance metadata", "h2kg:hasMetadata", "Retained as source metadata."),
        ("org", "Format", "tiff", "instance metadata", "h2kg:hasMetadata + dcterms:format", "Stored on raw-dataset metadata."),
        ("org", "FileSize", "541 MB", "instance metadata", "h2kg:hasMetadata + dcterms:extent", "Stored on raw-dataset metadata."),
        ("org", "FileName", "TestTomography.tif", "instance metadata", "h2kg:hasMetadata", "Stored on raw-dataset metadata."),
        ("org", "DimensionX", "1024", "instance metadata", "h2kg:hasMetadata", "Stored on raw-dataset metadata."),
        ("org", "DimensionY", "1024", "instance metadata", "h2kg:hasMetadata", "Stored on raw-dataset metadata."),
        ("org", "DimensionZ", "600", "instance metadata", "h2kg:hasMetadata", "Stored on raw-dataset metadata."),
        ("org", "PixelPerMetric", "8.1", "instance metadata", "h2kg:hasMetadata", "Stored on raw-dataset metadata."),
        ("org", "Link", "link", "instance metadata", "h2kg:hasMetadata + dcterms:source", "Stored as dataset/source metadata."),
        ("org", "MaskExist", "no", "instance metadata", "h2kg:hasMetadata", "Stored on reconstructed-dataset metadata."),
        ("org", "MaskLink", "link", "instance metadata", "h2kg:hasMetadata + dcterms:source", "Stored on reconstructed-dataset metadata."),
        ("syn", "Step 1", "Carbon felt electrode -> Buy -> SInt1", "instance metadata", "h2kg:Matter + h2kg:Process", "Modeled as procurement metadata on a material instance."),
        ("syn", "Step 2", "Unresolved workbook precursor label; 0.1 M -> Buy -> SInt2", "instance metadata", "h2kg:Matter + h2kg:Process", "Source label noise retained as metadata only."),
        ("syn", "Step 3", "Unresolved workbook precursor label; 2 M -> Buy -> SInt3", "instance metadata", "h2kg:Matter + h2kg:Process", "Source label noise retained as metadata only."),
        ("syn", "Step 4", "SInt2 -> Dissolve -> SInt4", "reuse existing term", "h2kg:Process", "Modeled as a labeled process instance."),
        ("syn", "Step 5", "SInt3 -> Dissolve -> SInt5", "reuse existing term", "h2kg:Process", "Modeled as a labeled process instance."),
        ("syn", "Step 6", "SInt4 -> Bubble (Gas = Nitrogen) -> Cell", "reuse existing term", "h2kg:Process", "Modeled as a labeled process instance."),
        ("sp", "Step 1", "Cell -> Heat -> SPInt1", "reuse existing term", "h2kg:Manufacturing", "Modeled as a labeled sample-conditioning step."),
        ("sp", "Step 2", "SPInt1 -> Cool -> SPInt2", "reuse existing term", "h2kg:Manufacturing", "Modeled as a labeled sample-conditioning step."),
        ("sp", "Step 3", "SPInt2 -> Cut -> Sample", "reuse existing term", "h2kg:Manufacturing", "Modeled as a labeled sample-cutting step."),
        ("char", "MeasurementMethod", "Synchrotron X-ray tomography", "reuse existing term", "h2kg:XRayComputedTomographyMeasurement", "Canonical public anchor for the combined round."),
        ("char", "MeasurementType", "ex-situ", "instance metadata", "h2kg:hasMetadata", "Retained as measurement metadata in round 1."),
        ("char", "Specimen", "bulk material", "instance metadata", "h2kg:hasMetadata", "Retained as measurement metadata in round 1."),
        ("char", "Temperature", "23 deg C", "reuse existing term", "h2kg:Temperature", "Modeled as a parameter-setting instance."),
        ("char", "Humidity", "50 %", "reuse existing term", "h2kg:RelativeHumidity", "Modeled as a parameter-setting instance."),
        ("char", "Atmosphere", "air", "instance metadata", "h2kg:hasMetadata", "Retained as measurement metadata in round 1."),
        ("char", "Pressure", "1 atm", "instance metadata", "h2kg:hasMetadata", "Retained as measurement metadata in round 1."),
        ("char", "Calibration", "adjusting lenses and apertures; adjusting the voltage", "instance metadata", "h2kg:hasMetadata", "Retained as calibration metadata."),
        ("inst", "Facility", "Canadian Light Source Inc.", "instance metadata", "h2kg:hasMetadata", "Retained as facility metadata."),
        ("inst", "Beamline", "BMIT-ID 05ID-2", "instance metadata", "h2kg:hasMetadata", "Retained as beamline metadata."),
        ("inst", "SourceMagneticField", "8.5 T", "instance metadata", "h2kg:hasMetadata", "Retained as source metadata."),
        ("inst", "MonochromatorType", "Double layer monochromator", "instance metadata", "h2kg:hasMetadata", "Retained as instrument metadata."),
        ("inst", "EnergyResolution", "10^-2", "instance metadata", "h2kg:hasMetadata", "Retained as instrument metadata."),
        ("inst", "XrayEnergy", "30 keV", "reuse existing term", "h2kg:XRayBeamEnergy", "Modeled as a parameter-setting instance."),
        ("inst", "PixelSize", "13 um", "reuse existing term", "h2kg:PixelSize", "Modeled as a parameter-setting instance."),
        ("inst", "FieldOfView", "26.68 x 8 mm", "instance metadata", "h2kg:hasMetadata", "Retained as detector metadata."),
        ("inst", "Magnification", "10", "reuse existing term", "h2kg:Magnification", "Modeled as a parameter-setting instance."),
        ("inst", "Binning", "None", "instance metadata", "h2kg:hasMetadata", "Retained as detector metadata."),
        ("inst", "ImagingTechnique", "Absorption contrast tomography", "instance metadata", "h2kg:hasMetadata", "Retained as acquisition metadata."),
        ("inst", "MeasuringMode", "Tomography fly scan", "instance metadata", "h2kg:hasMetadata", "Retained as acquisition metadata."),
        ("inst", "NumberOfRadiograms", "2000", "reuse existing term", "h2kg:ProjectionNumber", "Mapped to the reusable tomography projection-count parameter."),
        ("inst", "ExposureTime", "50 ms", "reuse existing term", "h2kg:ExposureTime", "Modeled as a parameter-setting instance."),
        ("inst", "RotationDegree", "180", "instance metadata", "h2kg:hasMetadata", "Retained as acquisition metadata in round 1."),
        ("inst", "NumberOfFlatFields", "210", "instance metadata", "h2kg:hasMetadata", "Retained as acquisition metadata in round 1."),
        ("inst", "NumberOfDarkFields", "10", "instance metadata", "h2kg:hasMetadata", "Retained as acquisition metadata in round 1."),
        ("inst", "SampleHolder", "HIU bone cell", "instance metadata", "h2kg:hasMetadata", "Retained as holder metadata."),
        ("inst", "PositionReferences", "6", "instance metadata", "h2kg:hasMetadata", "Retained as positioning metadata."),
        ("inst", "Scintillator", "YAG", "instance metadata", "h2kg:hasMetadata", "Retained as detector metadata."),
        ("inst", "ScintillatorThickness", "500 um", "instance metadata", "h2kg:hasMetadata", "Retained as detector metadata."),
        ("inst", "Detector", "Orca Flash V2 sCMOS", "instance metadata", "h2kg:hasMetadata", "Retained as detector metadata."),
        ("inst", "DetectorRawPx", "2560 x 2160 px", "instance metadata", "h2kg:hasMetadata", "Retained as detector metadata."),
        ("inst", "SampleElevation", "81 mm", "instance metadata", "h2kg:hasMetadata", "Retained as positioning metadata."),
        ("inst", "DistanceSampleSource", "58 m", "instance metadata", "h2kg:hasMetadata", "Retained as source/beamline metadata."),
        ("inst", "DistanceSampleDetector", "40 cm", "reuse existing term", "h2kg:SampleDetectorDistance", "Mapped to the reusable tomography geometry parameter."),
        ("inst", "SpatialResolution", "1 um", "reuse existing term", "h2kg:SpatialResolution", "Mapped to the reusable tomography resolution parameter."),
        ("inst", "Probe", "High-intensity monochromatic synchrotron radiation", "instance metadata", "h2kg:hasMetadata", "Retained as source metadata."),
        ("inst", "Signal", "Luminescent image; attenuated x-ray signal", "instance metadata", "h2kg:hasMetadata", "Retained as signal metadata."),
        ("inst", "TimeLapse", "1200 s", "instance metadata", "h2kg:hasMetadata", "Retained as acquisition metadata in round 1."),
        ("inst", "DataAdquisitionRate", "1 s", "instance metadata", "h2kg:hasMetadata", "Retained as acquisition metadata in round 1."),
        ("pre", "Step 1", "RawData -> Convert (8-bit) -> PPInt1", "reuse existing term", "h2kg:Process", "Modeled as a labeled preprocessing step."),
        ("pre", "Step 2", "PPInt1 -> DarkFieldCorrect -> PPInt2", "reuse existing term", "h2kg:Process", "Modeled as a labeled preprocessing step."),
        ("pre", "Step 3", "PPInt2 -> FlatFieldCorrect -> PPInt3", "reuse existing term", "h2kg:Process", "Modeled as a labeled preprocessing step."),
        ("pre", "Step 4", "PPInt3 -> BackgroundCorrect -> PPInt4", "reuse existing term", "h2kg:Process", "Modeled as a labeled preprocessing step."),
        ("pre", "Step 5", "PPInt4 -> 3DReconstruct -> PPInt5", "reuse existing term", "h2kg:Process", "Modeled as a labeled preprocessing step."),
        ("pre", "Step 6", "PPInt5 -> ManualSegment -> Post-processed tomograph", "reuse existing term", "h2kg:Process", "Modeled as a labeled preprocessing step."),
        ("anal", "Step 1", "DecayFactorCalculation -> Decay factor = 51 ms", "instance metadata", "h2kg:DataPoint + h2kg:Metadata", "Deferred analysis output represented as a datapoint with metadata only."),
        ("anal", "Step 2", "BeamPathDistanceMeasurement -> Real distance in beam path = 99 cm", "instance metadata", "h2kg:DataPoint + h2kg:Metadata", "Deferred analysis output represented as a datapoint with metadata only."),
        ("anal", "Step 3", "ElectrolyteSaturationMeasurement -> Electrolyte saturation = 47 mol/l", "instance metadata", "h2kg:DataPoint + h2kg:Metadata", "Deferred analysis output represented as a datapoint with metadata only."),
        ("anal", "Step 4", "ElectrodeSegmentRatioCalculation -> carbonfelt/electrolyte/air ratio = 0.12640046296296295", "instance metadata", "h2kg:DataPoint + h2kg:Metadata", "Deferred analysis output represented as a datapoint with metadata only."),
    ]
    for row in canonical:
        add("SynchrotronTomo", *row)

    radio_deviations = [
        ("org", "ExperimentTitle", "Synchrotron x-ray radiography of a dry electrode", "instance metadata", "h2kg:hasMetadata + dcterms:title", "Duplicate-structure validation sheet; only title differs from the canonical sheet."),
        ("org", "ExperimentID", "6", "instance metadata", "h2kg:hasMetadata + h2kg:hasIdentifier", "Duplicate-structure validation sheet; identifier differs from the canonical sheet."),
        ("org", "DOI", "https://doi.org/10.3390/35e45447", "instance metadata", "h2kg:hasMetadata + dcterms:identifier", "Duplicate-structure validation sheet; publication metadata differs."),
        ("org", "Journal", "JACS", "instance metadata", "h2kg:hasMetadata", "Duplicate-structure validation sheet; publication metadata differs."),
        ("org", "Volume", "11", "instance metadata", "h2kg:hasMetadata", "Duplicate-structure validation sheet; publication metadata differs."),
        ("org", "Issue", "12", "instance metadata", "h2kg:hasMetadata", "Duplicate-structure validation sheet; publication metadata differs."),
        ("org", "Pages", "21-22", "instance metadata", "h2kg:hasMetadata", "Duplicate-structure validation sheet; publication metadata differs."),
        ("org", "Topic", "Battery", "instance metadata", "h2kg:hasMetadata", "Duplicate-structure validation sheet; contradictory source label remains metadata only."),
        ("org", "Device", "VRFB", "instance metadata", "h2kg:hasMetadata", "Duplicate-structure validation sheet; out-of-scope source label remains metadata only."),
        ("org", "Granularity Level", "Macrostructure", "instance metadata", "h2kg:hasMetadata", "Duplicate-structure validation sheet; contextual metadata differs."),
        ("org", "FileSize", "600 MB", "instance metadata", "h2kg:hasMetadata + dcterms:extent", "Duplicate-structure validation sheet; dataset metadata differs."),
        ("org", "DimensionZ", "780", "instance metadata", "h2kg:hasMetadata", "Duplicate-structure validation sheet; dataset metadata differs."),
        ("char", "MeasurementMethod", "Synchrotron X-ray tomography", "reuse existing term", "h2kg:XRayComputedTomographyMeasurement", "Duplicate-structure validation confirms the same public method anchor."),
        ("inst", "NumberOfRadiograms", "2000", "reuse existing term", "h2kg:ProjectionNumber", "Duplicate-structure validation confirms the same projection-count parameter mapping."),
        ("pre", "All preprocessing rows", "Same workflow as SynchrotronTomo", "reuse existing term", "h2kg:Process", "Duplicate-structure validation confirms the same preprocessing pattern."),
        ("anal", "All analysis rows", "Same workflow as SynchrotronTomo", "instance metadata", "h2kg:DataPoint + h2kg:Metadata", "Duplicate-structure validation confirms the same deferred-output policy."),
    ]
    for row in radio_deviations:
        add("SynchrotronRadio", *row)

    return rows


def _synchrotron_xray_tomo_example_items() -> list[dict[str, Any]]:
    label = f"{COMMON_CONTEXT['rdfs']}label"
    comment = f"{COMMON_CONTEXT['rdfs']}comment"
    title = f"{DCTERMS}title"
    identifier = f"{DCTERMS}identifier"
    source = f"{DCTERMS}source"
    extent = f"{DCTERMS}extent"
    fmt = f"{DCTERMS}format"
    date = f"{DCTERMS}date"
    issued = f"{DCTERMS}issued"
    creator = f"{DCTERMS}creator"
    was_generated_by = f"{PROV}wasGeneratedBy"

    def iri(local: str) -> str:
        return f"{SXTM_EXAMPLE_NS}{local}"

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
            title: [lit("Synchrotron x-ray tomography of dry electrode")],
            identifier: [{"@value": "ExperimentID: 2"}, {"@value": "Measurement-ID: Run derived DOI"}],
            date: [{"@value": "44845"}],
            comment: [
                lit("Canonical source sheet: SynchrotronTomo."),
                lit("SynchrotronRadio was validated as a duplicate-structure sheet with metadata-only deviations."),
                lit("Out-of-scope labels retained only as source metadata: Topic = VRFB; Device = VRFB."),
            ],
        },
        {
            "@id": iri("publication-record"),
            "@type": [h("Metadata")],
            title: [lit("Synchrotron x-ray tomography of dry electrode")],
            identifier: [{"@value": "https://doi.org/10.3390/35654654654"}],
            issued: [{"@value": "41215"}],
            comment: [lit("Journal: Nature; volume: 41; issue: 5; pages: 6456-6541.")],
        },
        {
            "@id": iri("carbon-felt-electrode"),
            "@type": [h("Matter")],
            label: [lit("Carbon felt electrode precursor")],
            h("hasMetadata"): [ref(iri("carbon-felt-electrode-metadata"))],
        },
        {
            "@id": iri("carbon-felt-electrode-metadata"),
            "@type": [h("Metadata")],
            comment: [lit("Workbook context retained as metadata only: Manufacturer = SGL Carbon; Type = Sigracell GFA 6 EA.")],
        },
        {
            "@id": iri("conditioned-sample"),
            "@type": [h("Matter")],
            label: [lit("Conditioned tomography sample")],
            h("hasMetadata"): [ref(iri("conditioned-sample-metadata"))],
        },
        {
            "@id": iri("conditioned-sample-metadata"),
            "@type": [h("Metadata")],
            comment: [
                lit("Workbook context retained as metadata only: dry-electrode / VRFB study context."),
                lit("Sample geometry from sheet: XYZ = 7.4, 0.8, 0.6 cm."),
            ],
        },
        {
            "@id": iri("sample-conditioning-step"),
            "@type": [h("Manufacturing")],
            label: [lit("Sample conditioning and cutting")],
            h("hasInputMaterial"): [ref(iri("carbon-felt-electrode"))],
            h("hasOutputMaterial"): [ref(iri("conditioned-sample"))],
            h("hasMetadata"): [ref(iri("sample-conditioning-step-metadata"))],
        },
        {
            "@id": iri("sample-conditioning-step-metadata"),
            "@type": [h("Metadata")],
            comment: [
                lit("Worksheet steps represented conservatively as labeled process content: Buy, Dissolve, Bubble, Heat, Cool, Cut."),
                lit("Representative condition values: Heat temperature = 400 deg C; time = 25 h; Cool temperature = 25 deg C."),
            ],
        },
        {
            "@id": iri("xrayct-measurement-001"),
            "@type": [h("Measurement"), h("XRayComputedTomographyMeasurement")],
            label: [lit("Synchrotron x-ray tomography pilot measurement")],
            h("usesInstrument"): [ref(iri("xrayct-instrument-001"))],
            h("hasInputMaterial"): [ref(iri("conditioned-sample"))],
            h("hasParameter"): [
                ref(iri("xray-beam-energy-setting")),
                ref(iri("exposure-time-setting")),
                ref(iri("pixel-size-setting")),
                ref(iri("projection-number-setting")),
                ref(iri("spatial-resolution-setting")),
                ref(iri("sample-detector-distance-setting")),
                ref(iri("temperature-setting")),
                ref(iri("relative-humidity-setting")),
                ref(iri("magnification-setting")),
            ],
            h("hasOutputData"): [ref(iri("raw-projection-dataset")), ref(iri("experiment-dataset"))],
            h("hasMetadata"): [ref(iri("xrayct-measurement-metadata")), ref(iri("publication-record")), ref(iri("source-record"))],
        },
        {
            "@id": iri("xrayct-measurement-metadata"),
            "@type": [h("Metadata")],
            comment: [
                lit("MeasurementType = ex-situ; Specimen = bulk material; Atmosphere = air; Pressure = 1 atm."),
                lit("Calibration note from workbook: adjusting lenses and apertures; adjusting the voltage."),
            ],
        },
        {
            "@id": iri("xrayct-instrument-001"),
            "@type": [h("Instrument"), h("XRayCTInstrument")],
            label: [lit("Synchrotron x-ray CT instrument configuration")],
            h("hasMetadata"): [ref(iri("xrayct-instrument-metadata"))],
        },
        {
            "@id": iri("xrayct-instrument-metadata"),
            "@type": [h("Metadata")],
            comment: [
                lit("Facility = Canadian Light Source Inc.; Beamline = BMIT-ID 05ID-2."),
                lit("Monochromator = double layer monochromator; Detector = Orca Flash V2 sCMOS; Scintillator = YAG."),
                lit("Additional instrument metadata retained only as metadata: field of view, detector raw pixels, sample elevation, source-sample distance, probe, signal, time lapse, acquisition rate."),
            ],
        },
        {
            "@id": iri("raw-projection-dataset"),
            "@type": [h("Data"), h("TomographicProjectionDataset")],
            label: [lit("Raw synchrotron tomographic projection dataset")],
            h("hasMetadata"): [ref(iri("raw-projection-dataset-metadata"))],
        },
        {
            "@id": iri("raw-projection-dataset-metadata"),
            "@type": [h("Metadata")],
            fmt: [{"@value": "tiff"}],
            extent: [{"@value": "541 MB"}],
            source: [{"@value": "link"}],
            comment: [
                lit("Filename = TestTomography.tif."),
                lit("Dimensions = 1024 x 1024 x 600; PixelPerMetric = 8.1."),
            ],
        },
        {
            "@id": iri("experiment-dataset"),
            "@type": [h("Data"), h("ExperimentDataset")],
            label: [lit("Synchrotron x-ray tomography experiment dataset record")],
            h("hasMetadata"): [ref(iri("experiment-dataset-metadata"))],
        },
        {
            "@id": iri("experiment-dataset-metadata"),
            "@type": [h("Metadata")],
            comment: [lit("Source sheet bundle for the combined SynchrotronTomo / SynchrotronRadio controlled integration round.")],
        },
        {
            "@id": iri("preprocessing-step"),
            "@type": [h("Process")],
            label: [lit("Correction, reconstruction, and segmentation")],
            h("hasInputData"): [ref(iri("raw-projection-dataset"))],
            h("hasOutputData"): [ref(iri("reconstructed-tomograph-dataset"))],
            h("hasMetadata"): [ref(iri("preprocessing-step-metadata"))],
        },
        {
            "@id": iri("preprocessing-step-metadata"),
            "@type": [h("Metadata")],
            comment: [
                lit("Worksheet preprocessing labels retained as process metadata: Convert, DarkFieldCorrect, FlatFieldCorrect, BackgroundCorrect, 3DReconstruct, ManualSegment."),
                lit("Workbook software notes retained as metadata: XXXX; Avizo."),
            ],
        },
        {
            "@id": iri("reconstructed-tomograph-dataset"),
            "@type": [h("Data"), h("TomographicReconstructionDataset")],
            label: [lit("Reconstructed synchrotron tomograph dataset")],
            h("hasMetadata"): [ref(iri("reconstructed-tomograph-dataset-metadata"))],
        },
        {
            "@id": iri("reconstructed-tomograph-dataset-metadata"),
            "@type": [h("Metadata")],
            comment: [
                lit("Mask exists = no; mask link = link."),
                lit("Segmentation semantics retained as metadata only: carbon felt, electrolyte, and air."),
            ],
        },
        {
            "@id": iri("analysis-step"),
            "@type": [h("Process")],
            label: [lit("Tomography analysis of deferred outputs")],
            h("hasInputData"): [ref(iri("reconstructed-tomograph-dataset"))],
            h("hasMetadata"): [ref(iri("analysis-step-metadata"))],
        },
        {
            "@id": iri("analysis-step-metadata"),
            "@type": [h("Metadata")],
            comment: [
                lit("Worksheet analysis labels retained as process metadata: DecayFactorCalculation, BeamPathDistanceMeasurement, ElectrolyteSaturationMeasurement, ElectrodeSegmentRatioCalculation."),
                lit("Workbook software notes retained as metadata: ImageJ."),
            ],
        },
        {
            "@id": iri("decay-factor-datapoint"),
            "@type": [h("DataPoint")],
            label: [lit("Deferred decay-factor datapoint")],
            h("fromMeasurement"): [ref(iri("xrayct-measurement-001"))],
            h("hasMetadata"): [ref(iri("decay-factor-datapoint-metadata"))],
            was_generated_by: [ref(iri("analysis-step"))],
        },
        {
            "@id": iri("decay-factor-datapoint-metadata"),
            "@type": [h("Metadata")],
            comment: [lit("Deferred semantic target only: Decay factor; reported workbook value = 51 ms.")],
        },
        {
            "@id": iri("beam-path-distance-datapoint"),
            "@type": [h("DataPoint")],
            label: [lit("Deferred beam-path-distance datapoint")],
            h("fromMeasurement"): [ref(iri("xrayct-measurement-001"))],
            h("hasMetadata"): [ref(iri("beam-path-distance-datapoint-metadata"))],
            was_generated_by: [ref(iri("analysis-step"))],
        },
        {
            "@id": iri("beam-path-distance-datapoint-metadata"),
            "@type": [h("Metadata")],
            comment: [lit("Deferred semantic target only: Real distance in beam path; reported workbook value = 99 cm.")],
        },
        {
            "@id": iri("electrolyte-saturation-datapoint"),
            "@type": [h("DataPoint")],
            label: [lit("Deferred electrolyte-saturation datapoint")],
            h("fromMeasurement"): [ref(iri("xrayct-measurement-001"))],
            h("hasMetadata"): [ref(iri("electrolyte-saturation-datapoint-metadata"))],
            was_generated_by: [ref(iri("analysis-step"))],
        },
        {
            "@id": iri("electrolyte-saturation-datapoint-metadata"),
            "@type": [h("Metadata")],
            comment: [lit("Deferred semantic target only: Electrolyte saturation; reported workbook value = 47 mol/l.")],
        },
        {
            "@id": iri("phase-ratio-datapoint"),
            "@type": [h("DataPoint")],
            label: [lit("Deferred carbonfelt/electrolyte/air-ratio datapoint")],
            h("fromMeasurement"): [ref(iri("xrayct-measurement-001"))],
            h("hasMetadata"): [ref(iri("phase-ratio-datapoint-metadata"))],
            was_generated_by: [ref(iri("analysis-step"))],
        },
        {
            "@id": iri("phase-ratio-datapoint-metadata"),
            "@type": [h("Metadata")],
            comment: [lit("Deferred semantic target only: carbonfelt/electrolyte/air ratio; reported workbook value = 0.12640046296296295.")],
        },
        {
            "@id": iri("xray-beam-energy-setting"),
            "@type": [h("Parameter"), h("XRayBeamEnergy")],
            label: [lit("Synchrotron x-ray beam-energy setting")],
            h("hasMetadata"): [ref(iri("xray-beam-energy-setting-metadata"))],
        },
        {
            "@id": iri("xray-beam-energy-setting-metadata"),
            "@type": [h("Metadata")],
            comment: [lit("Reported workbook value = 30 keV.")],
        },
        {
            "@id": iri("exposure-time-setting"),
            "@type": [h("Parameter"), h("ExposureTime")],
            label: [lit("Projection exposure-time setting")],
            h("hasMetadata"): [ref(iri("exposure-time-setting-metadata"))],
        },
        {
            "@id": iri("exposure-time-setting-metadata"),
            "@type": [h("Metadata")],
            comment: [lit("Reported workbook value = 50 ms.")],
        },
        {
            "@id": iri("pixel-size-setting"),
            "@type": [h("Parameter"), h("PixelSize")],
            label: [lit("Projection pixel-size setting")],
            h("hasMetadata"): [ref(iri("pixel-size-setting-metadata"))],
        },
        {
            "@id": iri("pixel-size-setting-metadata"),
            "@type": [h("Metadata")],
            comment: [lit("Reported workbook value = 13 um.")],
        },
        {
            "@id": iri("projection-number-setting"),
            "@type": [h("Parameter"), h("ProjectionNumber")],
            label: [lit("Projection-number setting")],
            h("hasMetadata"): [ref(iri("projection-number-setting-metadata"))],
        },
        {
            "@id": iri("projection-number-setting-metadata"),
            "@type": [h("Metadata")],
            comment: [lit("Reported workbook value = 2000.")],
        },
        {
            "@id": iri("spatial-resolution-setting"),
            "@type": [h("Parameter"), h("SpatialResolution")],
            label: [lit("Spatial-resolution setting")],
            h("hasMetadata"): [ref(iri("spatial-resolution-setting-metadata"))],
        },
        {
            "@id": iri("spatial-resolution-setting-metadata"),
            "@type": [h("Metadata")],
            comment: [lit("Reported workbook value = 1 um.")],
        },
        {
            "@id": iri("sample-detector-distance-setting"),
            "@type": [h("Parameter"), h("SampleDetectorDistance")],
            label: [lit("Sample-detector-distance setting")],
            h("hasMetadata"): [ref(iri("sample-detector-distance-setting-metadata"))],
        },
        {
            "@id": iri("sample-detector-distance-setting-metadata"),
            "@type": [h("Metadata")],
            comment: [lit("Reported workbook value = 40 cm.")],
        },
        {
            "@id": iri("temperature-setting"),
            "@type": [h("Parameter"), h("Temperature")],
            label: [lit("Sample temperature setting")],
            h("hasMetadata"): [ref(iri("temperature-setting-metadata"))],
        },
        {
            "@id": iri("temperature-setting-metadata"),
            "@type": [h("Metadata")],
            comment: [lit("Reported workbook value = 23 deg C.")],
        },
        {
            "@id": iri("relative-humidity-setting"),
            "@type": [h("Parameter"), h("RelativeHumidity")],
            label: [lit("Relative-humidity setting")],
            h("hasMetadata"): [ref(iri("relative-humidity-setting-metadata"))],
        },
        {
            "@id": iri("relative-humidity-setting-metadata"),
            "@type": [h("Metadata")],
            comment: [lit("Reported workbook value = 50 %.")],
        },
        {
            "@id": iri("magnification-setting"),
            "@type": [h("Parameter"), h("Magnification")],
            label: [lit("Tomography magnification setting")],
            h("hasMetadata"): [ref(iri("magnification-setting-metadata"))],
        },
        {
            "@id": iri("magnification-setting-metadata"),
            "@type": [h("Metadata")],
            comment: [lit("Reported workbook value = 10.")],
        },
    ]


def _synchrotron_xray_tomo_validation_note() -> str:
    return """# Synchrotron X-Ray Tomography Validation Note

This controlled round does not introduce a new public synchrotron-branded measurement node. Instead, it normalizes the existing public CT neighborhood around `h2kg:XRayComputedTomographyMeasurement`.

Public ontology changes in this round:

- no new public TBox terms added
- normalized `h2kg:XRayComputedTomographyMeasurement`
- normalized `h2kg:XRayCTInstrument`
- broadened `h2kg:TomographicProjectionDataset`
- broadened `h2kg:TomographicReconstructionDataset`
- broadened `h2kg:PixelSize` so it can support tomography-detector usage as well as microscopy usage

What remained metadata or example-instance content:

- VRFB and dry-electrode study context
- beamline, detector, scintillator, and holder details
- acquisition descriptors such as fly-scan mode, flat fields, dark fields, and time-lapse settings
- worksheet preprocessing labels such as `Convert`, `DarkFieldCorrect`, `FlatFieldCorrect`, `BackgroundCorrect`, `3DReconstruct`, and `ManualSegment`
- worksheet analysis labels such as `DecayFactorCalculation`, `BeamPathDistanceMeasurement`, `ElectrolyteSaturationMeasurement`, and `ElectrodeSegmentRatioCalculation`

What was intentionally deferred:

- no new public property term for decay factor
- no new public property term for beam-path distance
- no new public property term for electrolyte saturation
- no new public property term for the carbonfelt/electrolyte/air ratio
- no separate public `SynchrotronXRayTomographyMeasurement` node
- no separate public `SynchrotronRadiographyMeasurement` node
"""


def _synchrotron_xray_tomo_case_summary() -> str:
    return """# Synchrotron X-Ray Tomography Case Summary

H2KG captures the remaining workbook tomography family by reusing the existing public CT anchor `h2kg:XRayComputedTomographyMeasurement` and cleaning it into a coherent generic tomography neighborhood. The public TBox connects the measurement to `h2kg:XRayCTInstrument`, `h2kg:TomographicProjectionDataset`, `h2kg:TomographicReconstructionDataset`, `h2kg:ExperimentDataset`, and the main acquisition parameters `h2kg:XRayBeamEnergy`, `h2kg:ExposureTime`, `h2kg:PixelSize`, `h2kg:ProjectionNumber`, `h2kg:SpatialResolution`, `h2kg:SampleDetectorDistance`, `h2kg:Temperature`, `h2kg:RelativeHumidity`, and `h2kg:Magnification`.

The canonical example uses `SynchrotronTomo` as the source sheet while treating `SynchrotronRadio` as a duplicate-structure validation sheet. Out-of-scope study context such as VRFB and dry-electrode labels remains metadata only. Preprocessing and analysis steps are represented conservatively as labeled `h2kg:Process` instances, and the reported analysis outputs are retained as `h2kg:DataPoint` instances with metadata-attached semantic notes rather than promoted public property terms.
"""


def _synchrotron_xray_tomo_follow_on_gaps() -> str:
    return """# Synchrotron X-Ray Tomography Follow-on Gaps

- Decide later whether H2KG should gain a broader non-hydrogen characterization layer for workbook cases outside PEMFC/PEMWE scope.
- Revisit whether `SynchrotronRadiography` ever needs its own public method node if a future workbook case is genuinely 2D radiography rather than tomography.
- Evaluate future promotion of repeated tomography-analysis outputs such as saturation descriptors, phase-segment ratios, or path-length descriptors if they recur across multiple H2-relevant tomography studies.
- Evaluate whether `FieldOfView`, `RotationDegree`, `NumberOfFlatFields`, and `NumberOfDarkFields` should become reusable public tomography parameters.
- Revisit whether facility and beamline metadata should stay free-text metadata or move into a structured external instrumentation vocabulary.
"""


def _synchrotron_xray_tomo_manuscript_figure() -> str:
    return """# Synchrotron X-Ray Tomography Manuscript Figure Guidance

Use a combined ontology-workflow figure with **TBox-only standalone nodes** and worksheet-derived values shown only as annotations or metadata callouts.

Recommended backbone:

`Matter -> Manufacturing -> X Ray Computed Tomography Measurement -> Tomographic Projection Dataset -> Process (correction / reconstruction / segmentation) -> Tomographic Reconstruction Dataset -> Process (analysis) -> DataPoint`

Supporting families:

- Above acquisition:
  - `X Ray Beam Energy`
  - `Exposure Time`
  - `Pixel Size`
  - `Projection Number`
  - `Spatial Resolution`
  - `Sample Detector Distance`
  - `Temperature`
  - `Relative Humidity`
  - `Magnification`
- Below acquisition:
  - `X Ray CT Instrument`
- Metadata callouts:
  - facility / beamline / detector / scintillator details
  - sample-holder and positioning details
  - raw file and dataset details
  - deferred output semantics for decay factor, beam-path distance, electrolyte saturation, and phase ratio

Important rule:

- Every standalone node in the figure must be retrievable from the public H2KG TBox and therefore visible in Explore after regeneration.
- Workbook values such as `Canadian Light Source`, `Orca Flash V2 sCMOS`, `YAG`, DOI, or VRFB labels remain annotations or metadata-callout text, not standalone ontology nodes.
"""


def _synchrotron_xray_tomo_manuscript_table() -> str:
    return """# Synchrotron X-Ray Tomography Manuscript Table Guidance

Recommended columns:

- Scientific case element
- H2KG ontology anchor
- Example workbook value
- Figure treatment

Recommended rows:

| Scientific case element | H2KG ontology anchor | Example workbook value | Figure treatment |
| --- | --- | --- | --- |
| Sample/material context | `h2kg:Matter` | Carbon felt electrode; dry-electrode sample | standalone ontology node with metadata callout |
| Sample conditioning | `h2kg:Manufacturing` | Heat, cool, cut | standalone ontology node with example annotation |
| CT acquisition | `h2kg:XRayComputedTomographyMeasurement` | Synchrotron X-ray tomography | standalone ontology node |
| CT instrument | `h2kg:XRayCTInstrument` | BMIT-ID / detector / scintillator stack | standalone ontology node with metadata callout |
| X-ray beam energy | `h2kg:XRayBeamEnergy` | 30 keV | parameter callout |
| Exposure time | `h2kg:ExposureTime` | 50 ms | parameter callout |
| Pixel size | `h2kg:PixelSize` | 13 um | parameter callout |
| Projection number | `h2kg:ProjectionNumber` | 2000 | parameter callout |
| Spatial resolution | `h2kg:SpatialResolution` | 1 um | parameter callout |
| Sample-detector distance | `h2kg:SampleDetectorDistance` | 40 cm | parameter callout |
| Temperature | `h2kg:Temperature` | 23 deg C | parameter callout |
| Relative humidity | `h2kg:RelativeHumidity` | 50 % | parameter callout |
| Magnification | `h2kg:Magnification` | 10 | parameter callout |
| Raw data | `h2kg:TomographicProjectionDataset` | TestTomography.tif | standalone ontology node |
| Preprocessing | `h2kg:Process` | Convert, dark-field correction, flat-field correction, 3D reconstruction, segmentation | standalone ontology node with annotation |
| Reconstructed data | `h2kg:TomographicReconstructionDataset` | Post-processed tomograph | standalone ontology node |
| Analysis | `h2kg:Process` | Decay-factor, beam-path, saturation, and phase-ratio analysis | standalone ontology node with annotation |
| Deferred outputs | `h2kg:DataPoint` | 51 ms; 99 cm; 47 mol/l; 0.12640046296296295 | standalone ontology node with metadata callout |
"""


def _synchrotron_xray_tomo_readme(generated_files: list[Path]) -> str:
    lines = [
        "# Synchrotron X-Ray Tomography Pilot Package",
        "",
        "This package contains the controlled combined `SynchrotronTomo` / `SynchrotronRadio` integration outputs for H2KG.",
        "",
        "Generated files:",
        "",
    ]
    for path in generated_files:
        lines.append(f"- `{path.name}`")
    lines.extend(
        [
            "",
            "Highlights:",
            "",
            "- Public measurement anchor reused and normalized: `h2kg:XRayComputedTomographyMeasurement`",
            "- Public instrument anchor reused and normalized: `h2kg:XRayCTInstrument`",
            "- Public dataset anchors reused and generalized: `h2kg:TomographicProjectionDataset`, `h2kg:TomographicReconstructionDataset`",
            "- No new public derived-property terms added in this round",
            "- `SynchrotronRadio` handled as duplicate-structure validation rather than a separate public method node",
        ]
    )
    return "\n".join(lines) + "\n"


def _missing_terms_note(missing: list[str]) -> str:
    bullets = "\n".join(f"- `{term}`" for term in missing)
    return (
        "# Synchrotron X-Ray Tomography Pilot Package\n\n"
        "Generation skipped because the current ontology source is missing required local terms.\n\n"
        f"{bullets}\n"
    )
