from __future__ import annotations

"""Generate executable, H2KG-aligned method data profiles.

Profiles are application constraints and capture templates.  They deliberately do
not add terms to the H2KG TBox: a missing reusable concept is a review finding,
not a reason to weaken either the profile or the ontology.
"""

import csv
import hashlib
import io
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rdflib import Graph, Namespace, RDF, RDFS, SKOS, URIRef
from pyshacl import validate

from .io import load_json_document, merge_document_items
from .utils import COMMON_CONTEXT, dump_json, ensure_dir, write_text


H2KG = Namespace(COMMON_CONTEXT["h2kg"])
PROV = Namespace(COMMON_CONTEXT["prov"])
QUDT = Namespace(COMMON_CONTEXT["qudt"])
SH = Namespace("http://www.w3.org/ns/shacl#")
PROFILE = Namespace("https://w3id.org/h2kg/profiles/")


@dataclass(frozen=True)
class MethodProfile:
    key: str
    title: str
    pilot_dir: str
    example_stem: str
    measurement: str
    instrument: str
    datasets: tuple[str, ...]
    parameters: tuple[str, ...]
    properties: tuple[str, ...]
    metadata_boundary: str
    scenario_note: str
    evidence_status: str = "source_grounded"
    require_result: bool = True


def _iri(local_name: str) -> str:
    return str(H2KG[local_name])


PROFILES: tuple[MethodProfile, ...] = (
    MethodProfile("tem", "Transmission electron microscopy", "tem_pilot", "tem_pilot_example", "TransmissionElectronMicroscopyImaging", "TEMInstrument", ("MicrostructureImageDataset",), ("AcceleratingVoltage", "Magnification", "WorkingDistance", "Temperature", "RelativeHumidity", "VacuumChamberPressure"), ("PdNanoparticleDiameter",), "Detector, grid, specimen descriptors, file details, and publication details remain metadata.", "The pilot contains a reported nanoparticle-diameter result."),
    MethodProfile("sem", "Scanning electron microscopy", "sem_pilot", "sem_pilot_example", "ScanningElectronMicroscopyImaging", "SEMInstrument", ("SEMImageDataset",), ("AcceleratingVoltage", "Magnification", "WorkingDistance", "Temperature", "RelativeHumidity"), ("CatalystParticleDiameter",), "Detector mode, supplier information, image-file details, and publication details remain metadata.", "The pilot deliberately records a particle-diameter target without inventing a numeric result."),
    MethodProfile("fib_sem", "FIB-SEM tomography", "fib_sem_pilot", "fib_sem_example", "FIBSEMTomographyMeasurement", "FIBSEMInstrument", ("SEMImageDataset", "TomographicReconstructionDataset"), ("IonBeamEnergy", "IonBeamCurrent", "ElectronBeamEnergy", "ElectronCurrent", "VoxelSize", "SliceNumber", "CutThickness", "StageTilt", "DwellTime", "ExposureTime", "Magnification", "MicroscopyMeasuredArea", "Temperature", "RelativeHumidity", "VacuumChamberPressure", "TotalAcquisitionTime"), ("TotalPorosity", "GeodesicTortuosity", "Constrictivity"), "Instrument settings not represented by reusable parameters, segmentation choices, and file details remain metadata.", "The pilot captures acquisition, reconstruction, and multiple microstructural outputs."),
    MethodProfile("ic_sem", "Ion-cut scanning electron microscopy", "ic_sem_pilot", "ic_sem_example", "ICSEMImagingMeasurement", "ICSEMInstrument", ("SEMImageDataset", "SEMMicrographDataset"), ("IonBeamEnergy", "IonBeamCurrent", "ElectronBeamEnergy", "ElectronCurrent", "PixelSize", "CutThickness", "DwellTime", "ExposureTime", "Magnification", "MicroscopyMeasuredArea", "Temperature", "RelativeHumidity", "VacuumChamberPressure", "TotalAcquisitionTime"), ("MembraneElectrodeAssemblyThickness", "GasDiffusionLayerThickness", "TotalPorosity"), "Cutting details, detector settings, and study-specific context remain metadata.", "The pilot represents layer-resolved thickness and porosity analysis."),
    MethodProfile("afm", "Atomic force microscopy", "afm_pilot", "afm_example", "AtomicForceMicroscopyMeasurement", "AFMInstrument", ("MicrostructureImageDataset", "SurfaceTopographyDataset"), ("AFMScanSpeed", "AFMTipNominalRadius", "MicroscopyMeasuredArea", "Temperature", "RelativeHumidity", "CantileverSpringConstant", "CantileverResonanceFrequency"), ("MeanParticleSize",), "AFM mode, tip model, sensitivity, resolution, and local file details remain metadata unless reusable across cases.", "The pilot represents an ex-situ topography/image analysis chain."),
    MethodProfile("neutron_tomography", "Neutron tomography", "neutron_tomo_pilot", "neutron_tomo_example", "NeutronTomographyMeasurement", "NeutronTomographyInstrument", ("TomographicProjectionDataset", "TomographicReconstructionDataset", "ExperimentDataset"), ("PixelSize", "ExposureTime", "ProjectionNumber", "NeutronFlux", "SpatialResolution", "SampleDetectorDistance", "Temperature", "RelativeHumidity"), ("TortuosityFactor", "AverageWaterDropletArea", "AverageWaterDropletCount"), "Facility, beamline, detector, holder, and ambiguous source descriptors remain metadata.", "The pilot captures an operando MEA projection-to-reconstruction chain."),
    MethodProfile("synchrotron_xray_tomography", "Synchrotron X-ray tomography", "synchrotron_xray_tomo_pilot", "synchrotron_xray_tomo_example", "XRayComputedTomographyMeasurement", "XRayCTInstrument", ("TomographicProjectionDataset", "TomographicReconstructionDataset", "ExperimentDataset"), ("XRayBeamEnergy", "ExposureTime", "PixelSize", "ProjectionNumber", "SpatialResolution", "SampleDetectorDistance", "Temperature", "RelativeHumidity", "Magnification"), (), "Facility, beamline, detector, sample-holder, and deferred output semantics remain metadata.", "The current pilot intentionally defers source-specific result-property semantics.", require_result=False),
    MethodProfile("xrd", "X-ray diffraction", "xrd_pilot", "xrd_example", "XRayDiffractionMeasurement", "XRayDiffractometer", ("XRDPatternDataset", "ExperimentDataset"), ("XRayWavelength", "XRDStepSize", "XRDTwoThetaStart", "XRDTwoThetaEnd"), ("DiffractionPeakPosition2Theta", "XRDPeakFWHM", "PtCrystalliteSize", "TheoreticalMetalSurfaceArea"), "Sample-holder, scan implementation details, fitting choices, and bibliographic details remain metadata.", "The pilot demonstrates pattern analysis and derived catalyst descriptors."),
    MethodProfile("xps", "X-ray photoelectron spectroscopy", "xps_pilot", "xps_example", "XRayPhotoelectronSpectroscopyMeasurement", "XPSInstrument", ("XPSDataset", "ExperimentDataset"), ("XPSPassEnergy", "XPSTakeOffAngle", "XPSAnalysisArea"), ("BindingEnergy", "C1sAtomicPercent", "O1sAtomicPercent", "F1sAtomicPercent", "N1sAtomicPercent", "CarbonToOxygenAtomRatio", "MetalAtomicPercent"), "Spectral fitting conventions, instrument brand/model, and source-specific preparation details remain metadata.", "The existing pilot is illustrative and is not counted as a source-grounded scenario record.", evidence_status="illustrative_existing_pilot"),
)


def build_method_data_profiles(
    input_path: str | Path,
    output_root: str | Path,
    pilot_examples_root: str | Path | None = None,
) -> dict[str, Any]:
    """Create the versioned profile package after the method pilot packages."""
    input_path = Path(input_path)
    output_root = Path(output_root)
    target = ensure_dir(output_root / "method_profiles")
    pilot_root = Path(pilot_examples_root) if pilot_examples_root else output_root / "examples"
    source_items = merge_document_items(load_json_document(input_path))
    source_ids = {str(item.get("@id")) for item in source_items if item.get("@id")}
    required = _all_required_terms()
    missing = sorted(required - source_ids)
    if missing:
        write_text(target / "README.md", _missing_note(missing))
        return {"status": "skipped_missing_terms", "missing_terms": missing, "output_dir": str(target)}

    labels = _term_labels(source_items)
    reports: list[dict[str, Any]] = []
    for spec in PROFILES:
        reports.append(_build_one(spec, target, pilot_root, labels))
    coverage = _coverage_rows(reports)
    _write_csv(target / "profile_coverage_report.csv", coverage)
    dump_json(target / "profile_coverage_report.json", {"profile_count": len(PROFILES), "profiles": coverage})
    write_text(target / "profile_coverage_report.md", _coverage_markdown(coverage))
    write_text(target / "supplementary_tables.md", _supplementary_tables(reports))
    write_text(target / "README.md", _root_readme(coverage))
    return {
        "status": "generated",
        "profile_count": len(PROFILES),
        "source_grounded_profile_count": sum(row["evidence_status"] == "source_grounded" for row in coverage),
        "illustrative_profile_count": sum(row["evidence_status"] != "source_grounded" for row in coverage),
        "output_dir": str(target),
        "profiles": reports,
    }


def validate_method_profile_graph(shapes_path: str | Path, data_path: str | Path) -> dict[str, Any]:
    data = Graph().parse(str(data_path), format=_rdf_format(Path(data_path)))
    shapes = Graph().parse(str(shapes_path), format="turtle")
    conforms, _, report = validate(data, shacl_graph=shapes, inference="rdfs", serialize_report_graph=False)
    return {"conforms": bool(conforms), "report": str(report)}


def _build_one(spec: MethodProfile, target: Path, pilot_root: Path, labels: dict[str, dict[str, list[str]]]) -> dict[str, Any]:
    folder = ensure_dir(target / spec.key)
    source_folder = pilot_root / spec.pilot_dir
    source_ttl = source_folder / f"{spec.example_stem}.ttl"
    source_json = source_folder / f"{spec.example_stem}.jsonld"
    if not source_ttl.exists() or not source_json.exists():
        write_text(folder / "README.md", f"# {spec.title} profile\n\nPilot source files were not available at profile build time.\n")
        return {"key": spec.key, "title": spec.title, "status": "skipped_missing_pilot", "evidence_status": spec.evidence_status}
    copied_ttl = folder / "source_grounded_example.ttl"
    copied_json = folder / "source_grounded_example.jsonld"
    shutil.copyfile(source_ttl, copied_ttl)
    shutil.copyfile(source_json, copied_json)
    shapes = folder / f"{spec.key}_profile_shapes.ttl"
    write_text(shapes, _shape_turtle(spec))
    validation = validate_method_profile_graph(shapes, copied_ttl)
    template = folder / f"{spec.key}_capture_template.jsonld"
    dump_json(template, _capture_template(spec))
    fields = _field_rows(spec, labels, copied_ttl)
    _write_csv(folder / f"{spec.key}_field_dictionary.csv", fields)
    _write_field_markdown(folder / f"{spec.key}_field_dictionary.md", fields)
    scenario = _scenario(spec, copied_ttl, labels)
    report = {"profile": spec.key, "title": spec.title, "conforms": validation["conforms"], "evidence_status": spec.evidence_status, "require_result": spec.require_result, "scenario": scenario, "shacl_report": validation["report"]}
    dump_json(folder / "validation_report.json", report)
    write_text(folder / "README.md", _profile_readme(spec, report))
    return {"key": spec.key, "title": spec.title, "status": "generated", "evidence_status": spec.evidence_status, "conforms": validation["conforms"], "field_count": len(fields), "scenario": scenario, "folder": str(folder)}


def _all_required_terms() -> set[str]:
    common = {"Measurement", "Instrument", "Matter", "Data", "DataPoint", "Process", "Metadata", "hasInputMaterial", "usesInstrument", "hasOutputData", "hasInputData", "hasParameter", "hasMetadata", "fromMeasurement", "ofProperty", "hasQuantityValue"}
    terms = {_iri(term) for term in common}
    for spec in PROFILES:
        terms.add(_iri(spec.measurement)); terms.add(_iri(spec.instrument))
        terms.update(_iri(item) for item in spec.datasets + spec.parameters + spec.properties)
    return terms


def _term_labels(items: list[dict[str, Any]]) -> dict[str, dict[str, list[str]]]:
    result: dict[str, dict[str, list[str]]] = {}
    for item in items:
        iri = str(item.get("@id", ""))
        if not iri:
            continue
        result[iri] = {
            "label": _values(item.get(str(SKOS.prefLabel))) + _values(item.get(str(RDFS.label))),
            "alt": _values(item.get(str(SKOS.altLabel))),
        }
    return result


def _values(value: Any) -> list[str]:
    if not isinstance(value, list): value = [value]
    output: list[str] = []
    for item in value:
        if isinstance(item, dict) and "@value" in item: output.append(str(item["@value"]))
        elif isinstance(item, str): output.append(item)
    return output


def _shape_turtle(spec: MethodProfile) -> str:
    property_values = " ".join(f"h2kg:{item}" for item in spec.properties) or "h2kg:Property"
    result_rule = "." if not spec.require_result else """
  sh:property [
    sh:path [ sh:inversePath h2kg:fromMeasurement ] ; sh:minCount 1 ; sh:class h2kg:DataPoint
  ] ."""
    return f'''@prefix h2kg: <{H2KG}> .
@prefix prov: <{PROV}> .
@prefix qudt: <{QUDT}> .
@prefix quantitykind: <http://qudt.org/vocab/quantitykind/> .
@prefix sh: <{SH}> .

<{PROFILE}{spec.key}/MeasurementShape> a sh:NodeShape ;
  sh:targetClass h2kg:{spec.measurement} ;
  sh:class h2kg:Measurement ;
  sh:property [ sh:path h2kg:hasInputMaterial ; sh:minCount 1 ; sh:class h2kg:Matter ] ;
  sh:property [ sh:path h2kg:usesInstrument ; sh:minCount 1 ; sh:class h2kg:Instrument ] ;
  sh:property [ sh:path h2kg:hasOutputData ; sh:minCount 1 ; sh:class h2kg:Data ] ;{result_rule}

<{PROFILE}{spec.key}/DataPointShape> a sh:NodeShape ;
  sh:targetSubjectsOf h2kg:fromMeasurement ;
  sh:property [ sh:path h2kg:fromMeasurement ; sh:node [ sh:class h2kg:{spec.measurement} ] ] ;
  sh:property [ sh:path h2kg:ofProperty ; sh:in ( {property_values} ) ] ;
  sh:property [ sh:path prov:wasGeneratedBy ; sh:minCount 1 ; sh:class h2kg:Process ] ;
  sh:or (
    [ sh:property [ sh:path h2kg:hasQuantityValue ; sh:minCount 1 ] ]
    [ sh:property [ sh:path h2kg:hasMetadata ; sh:minCount 1 ] ]
  ) .

<{PROFILE}{spec.key}/QuantityValueShape> a sh:NodeShape ;
  sh:targetObjectsOf h2kg:hasQuantityValue ;
  sh:class qudt:QuantityValue ;
  sh:property [ sh:path qudt:numericValue ; sh:minCount 1 ] ;
  sh:or (
    [ sh:property [ sh:path qudt:unit ; sh:minCount 1 ] ; sh:property [ sh:path qudt:quantityKind ; sh:minCount 1 ] ]
    [ sh:property [ sh:path qudt:quantityKind ; sh:hasValue quantitykind:Count ] ]
    [ sh:property [ sh:path qudt:quantityKind ; sh:hasValue quantitykind:Dimensionless ] ]
  ) .
'''


def _capture_template(spec: MethodProfile) -> dict[str, Any]:
    namespace = f"https://w3id.org/h2kg/profiles/examples/{spec.key}/"
    graph: list[dict[str, Any]] = [
        {"@id": f"{namespace}measurement", "@type": ["h2kg:Measurement", f"h2kg:{spec.measurement}"], "h2kg:hasInputMaterial": [{"@id": f"{namespace}sample"}], "h2kg:usesInstrument": [{"@id": f"{namespace}instrument"}], "h2kg:hasOutputData": [{"@id": f"{namespace}raw-data"}], "h2kg:hasMetadata": [{"@id": f"{namespace}measurement-metadata"}]},
        {"@id": f"{namespace}sample", "@type": ["h2kg:Matter"]},
        {"@id": f"{namespace}instrument", "@type": ["h2kg:Instrument", f"h2kg:{spec.instrument}"]},
        {"@id": f"{namespace}raw-data", "@type": ["h2kg:Data", f"h2kg:{spec.datasets[0]}"]},
        {"@id": f"{namespace}measurement-metadata", "@type": ["h2kg:Metadata"], "rdfs:comment": "Record source evidence, file details, and method-specific context here."},
    ]
    for index, param in enumerate(spec.parameters, start=1):
        graph.append({"@id": f"{namespace}parameter-{index}", "@type": ["h2kg:Parameter", f"h2kg:{param}"], "rdfs:comment": "Conditional: add a quantity value only when reported."})
        graph[0].setdefault("h2kg:hasParameter", []).append({"@id": f"{namespace}parameter-{index}"})
    if spec.require_result:
        graph.extend([
            {"@id": f"{namespace}analysis", "@type": ["h2kg:Process"]},
            {"@id": f"{namespace}result", "@type": ["h2kg:DataPoint"], "h2kg:fromMeasurement": [{"@id": f"{namespace}measurement"}], "h2kg:ofProperty": [{"@id": f"h2kg:{spec.properties[0]}"}], "prov:wasGeneratedBy": [{"@id": f"{namespace}analysis"}], "h2kg:hasMetadata": [{"@id": f"{namespace}result-metadata"}]},
            {"@id": f"{namespace}result-metadata", "@type": ["h2kg:Metadata"], "rdfs:comment": "Use this explicit statement when no numeric value was reported; otherwise add h2kg:hasQuantityValue with QUDT numericValue, unit, and quantity kind."},
        ])
    return {"@context": {**COMMON_CONTEXT, "rdfs": str(RDFS)}, "@graph": graph}


def _field_rows(spec: MethodProfile, labels: dict[str, dict[str, list[str]]], example_path: Path) -> list[dict[str, str]]:
    observed = _observed_units(example_path)
    rows: list[dict[str, str]] = []
    entries = [("measurement", spec.measurement, "one required", "workflow occurrence", "Method identity; source citation or record identifier."), ("input material/sample context", "Matter", "at least one required", "IRI or linked material record", "Sample, composition, and preparation details may remain metadata."), ("instrument", spec.instrument, "at least one required", "linked instrument occurrence", "Brand/model belongs in metadata."), ("raw dataset", spec.datasets[0], "at least one required", "linked data occurrence", "File, detector, and local storage details belong in metadata.")]
    entries.extend(("conditional parameter", item, "conditional when reported or method-defining", "quantity value when numeric", "Use a QUDT QuantityValue with numeric value, unit, and quantity kind when a value is asserted.") for item in spec.parameters)
    entries.extend(("derived result", item, "at least one required" if spec.require_result else "deferred in current profile", "DataPoint; numeric or explicitly unreported", "Link through fromMeasurement, ofProperty, and a producing Process.") for item in spec.properties)
    entries.append(("contextual metadata", "Metadata", "optional", "metadata node", spec.metadata_boundary))
    for role, local, cardinality, form, boundary in entries:
        iri = _iri(local)
        term = labels.get(iri, {})
        unit = observed.get(iri, "QUDT unit and quantity kind required when a numeric value is asserted.")
        rows.append({"method_profile": spec.key, "h2kg_iri": iri, "preferred_label": "; ".join(term.get("label", [])[:1]) or local, "alternative_labels": "; ".join(term.get("alt", [])), "semantic_role": role, "expected_value_form": form, "cardinality_or_condition": cardinality, "qudt_guidance": unit, "source_evidence_field": "source record identifier, page/section, or dataset pointer", "metadata_boundary": boundary})
    return rows


def _observed_units(path: Path) -> dict[str, str]:
    graph = Graph().parse(str(path), format="turtle")
    output: dict[str, str] = {}
    for param in graph.subjects(RDF.type, H2KG.Parameter):
        types = [str(value) for value in graph.objects(param, RDF.type) if value != H2KG.Parameter]
        qvs = list(graph.objects(param, H2KG.hasQuantityValue))
        if not qvs: continue
        values: list[str] = []
        for qv in qvs:
            unit = next(graph.objects(qv, QUDT.unit), None); kind = next(graph.objects(qv, QUDT.quantityKind), None)
            values.append(f"Observed: unit {unit or 'not supplied'}; quantity kind {kind or 'not supplied'}.")
        for term in types: output[term] = " ".join(values)
    return output


def _scenario(spec: MethodProfile, path: Path, labels: dict[str, dict[str, list[str]]]) -> dict[str, Any]:
    if not spec.require_result:
        return {
            "note": spec.scenario_note,
            "evidence_status": spec.evidence_status,
            "results": [{"property": "Deferred tomography outputs", "value": "not promoted in current source-grounded profile", "status": "deferred"}],
        }
    graph = Graph().parse(str(path), format="turtle")
    measurement = H2KG[spec.measurement]
    values: list[dict[str, str]] = []
    for point in graph.subjects(H2KG.fromMeasurement, None):
        producing_measurements = list(graph.objects(point, H2KG.fromMeasurement))
        if not any(measurement in set(graph.objects(item, RDF.type)) for item in producing_measurements):
            continue
        prop = next(graph.objects(point, H2KG.ofProperty), None)
        prop_label = labels.get(str(prop), {}).get("label", [str(prop).split("#")[-1]])[0]
        qv = next(graph.objects(point, H2KG.hasQuantityValue), None)
        if qv:
            number = next(graph.objects(qv, QUDT.numericValue), None); unit = next(graph.objects(qv, QUDT.unit), None)
            values.append({"property": prop_label, "value": f"{number} {str(unit).split('/')[-1] if unit else ''}".strip(), "status": "reported"})
        else:
            values.append({"property": prop_label, "value": "not reported", "status": "explicitly unreported or metadata-only"})
    return {"note": spec.scenario_note, "evidence_status": spec.evidence_status, "results": values}


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> Path:
    if not rows: return write_text(path, "")
    stream = io.StringIO(newline=""); writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n"); writer.writeheader(); writer.writerows(rows)
    ensure_dir(path.parent)
    path.write_bytes(stream.getvalue().encode("utf-8"))
    return path


def _write_field_markdown(path: Path, rows: list[dict[str, str]]) -> None:
    lines = ["# Field Dictionary", "", "| Semantic role | H2KG term | Cardinality / condition | QUDT guidance |", "| --- | --- | --- | --- |"]
    for row in rows: lines.append(f"| {row['semantic_role']} | `{row['preferred_label']}` | {row['cardinality_or_condition']} | {row['qudt_guidance']} |")
    write_text(path, "\n".join(lines) + "\n")


def _coverage_rows(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"method_profile": report["key"], "title": report["title"], "status": report["status"], "evidence_status": report["evidence_status"], "shacl_conforms": report.get("conforms", False), "field_count": report.get("field_count", 0), "result_requirement": "required" if next(item for item in PROFILES if item.key == report["key"]).require_result else "deferred"} for report in reports]


def _coverage_markdown(rows: list[dict[str, Any]]) -> str:
    lines = ["# H2KG Method-Profile Coverage", "", "| Profile | Evidence status | SHACL conforms | Result treatment |", "| --- | --- | --- | --- |"]
    for row in rows: lines.append(f"| {row['title']} | {row['evidence_status']} | {row['shacl_conforms']} | {row['result_requirement']} |")
    return "\n".join(lines) + "\n"


def _supplementary_tables(reports: list[dict[str, Any]]) -> str:
    lines = ["# Supplementary Tables S1-S9: H2KG Method Data Profiles", "", "Each profile consists of a SHACL constraint file, value-free JSON-LD capture template, field dictionary, copied pilot record, and validation report. `source_grounded` means the example originates from the integrated pilot material. The XPS profile is structurally validated but its existing pilot is illustrative.", ""]
    for index, report in enumerate(reports, start=1):
        spec = next(item for item in PROFILES if item.key == report["key"])
        lines.extend([f"## Table S{index}. {spec.title}", "", "| Element | H2KG anchor(s) | Rule |", "| --- | --- | --- |", f"| Measurement | `h2kg:{spec.measurement}` | One typed measurement occurrence. |", f"| Instrument | `h2kg:{spec.instrument}` | At least one linked instrument. |", f"| Dataset chain | `{', '.join('h2kg:' + item for item in spec.datasets)}` | At least one raw output dataset. |", f"| Conditional parameters | `{', '.join('h2kg:' + item for item in spec.parameters)}` | Capture only when reported or method-defining; numeric values require QUDT quantity values. |", f"| Results | `{', '.join('h2kg:' + item for item in spec.properties) or 'Deferred'}` | {'At least one DataPoint or explicit missing-value metadata.' if spec.require_result else 'Output property semantics deferred in this profile.'} |", f"| Evidence boundary | Metadata | {spec.metadata_boundary} |", ""])
    return "\n".join(lines)


def _profile_readme(spec: MethodProfile, report: dict[str, Any]) -> str:
    return f"# {spec.title} H2KG Method Data Profile\n\nThis profile is an H2KG-aligned capture and validation artifact, not a second ontology. SHACL conformance for the included pilot record: `{report['conforms']}`. Evidence status: `{spec.evidence_status}`.\n\n{spec.scenario_note}\n"


def _root_readme(rows: list[dict[str, Any]]) -> str:
    source_grounded = sum(row["evidence_status"] == "source_grounded" for row in rows)
    return f"# H2KG Method Data Profiles\n\nThis versioned package contains {len(rows)} H2KG-aligned method profiles. {source_grounded} profiles use source-grounded pilot records; the XPS profile retains an explicitly illustrative existing pilot. Profiles define capture templates and SHACL constraints without changing the H2KG TBox.\n"


def _missing_note(missing: list[str]) -> str:
    return "# H2KG Method Data Profiles\n\nProfile generation was skipped because the source ontology lacks these required public terms:\n\n" + "\n".join(f"- `{term}`" for term in missing) + "\n"


def _rdf_format(path: Path) -> str:
    return "json-ld" if path.suffix.lower() in {".json", ".jsonld"} else "turtle"
