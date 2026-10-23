from __future__ import annotations

"""Build workbook-backed H2KG characterization knowledge graphs.

The workbook is an external source and is never redistributed.  A sanitized
manifest is the versioned release input; every eligible workbook value remains
traceable to its source cell and raw lexical form.
"""

import csv
import hashlib
import io
import json
import re
import shutil
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

from pyshacl import validate as shacl_validate
from rdflib import Dataset, Graph, Literal, Namespace, RDF, RDFS, SKOS, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import DCTERMS, OWL, PROV, SH, XSD

from .utils import COMMON_CONTEXT, dump_json, ensure_dir, now_iso, write_text


H2KG = Namespace(COMMON_CONTEXT["h2kg"])
QUDT = Namespace(COMMON_CONTEXT["qudt"])
UNIT = Namespace(COMMON_CONTEXT["unit"])
QK = Namespace(COMMON_CONTEXT["quantitykind"])
KG = Namespace("https://w3id.org/h2kg/examples/characterization/schema#")
CASE = Namespace("https://w3id.org/h2kg/examples/characterization/")
GRAPH = Namespace("https://w3id.org/h2kg/examples/characterization/graph/")

MANIFEST_SCHEMA = "h2kg-characterization-workbook/v1"
BUILD_SCHEMA = "h2kg-characterization-kg/v1"
EXPECTED_WORKBOOK_SHA256 = "C3A66E75FABDAF61C60949FFC7B0E08AAD324A1F77D6137BDE60FA20797001E6"

DIRECT_SECTIONS = {"org", "char", "inst"}
TABLE_SECTIONS = {"syn", "sp", "pre", "anal"}
SOURCE_STATUSES = (
    "reported",
    "missing",
    "not_applicable",
    "not_specified",
    "unconfirmed",
    "formula_unresolved",
    "semantic_conflict",
)
EXCLUDED_FIELDS = {
    "author": "personal identity",
    "email": "personal contact",
    "orcid": "personal identifier",
    "institution": "author institution",
    "foundingbody": "author or funder organization field",
}


@dataclass(frozen=True)
class CaseSpec:
    key: str
    sheet: str
    title: str
    family: str
    measurement_class: str
    instrument_class: str
    raw_dataset_class: str
    processed_dataset_class: str


CASE_SPECS: tuple[CaseSpec, ...] = (
    CaseSpec("tem", "TEM", "Transmission electron microscopy", "TEM", "TransmissionElectronMicroscopyImaging", "TEMInstrument", "MicrostructureImageDataset", "MicrostructureImageDataset"),
    CaseSpec("sem", "SEM", "Scanning electron microscopy", "SEM", "ScanningElectronMicroscopyImaging", "SEMInstrument", "SEMImageDataset", "SEMMicrographDataset"),
    CaseSpec("afm", "AFM", "Atomic force microscopy", "AFM", "AtomicForceMicroscopyMeasurement", "AFMInstrument", "MicrostructureImageDataset", "SurfaceTopographyDataset"),
    CaseSpec("fib_sem", "FIB-SEM", "FIB-SEM tomography", "FIB-SEM", "FIBSEMTomographyMeasurement", "FIBSEMInstrument", "SEMImageDataset", "TomographicReconstructionDataset"),
    CaseSpec("ic_sem", "IC-SEM", "Ion-cut scanning electron microscopy", "IC-SEM", "ICSEMImagingMeasurement", "ICSEMInstrument", "SEMImageDataset", "SEMMicrographDataset"),
    CaseSpec("neutron_tomography", "NeutronTomo", "Neutron tomography", "Neutron tomography", "NeutronTomographyMeasurement", "NeutronTomographyInstrument", "TomographicProjectionDataset", "TomographicReconstructionDataset"),
    CaseSpec("synchrotron_radiography", "SynchrotronRadio", "Synchrotron X-ray radiography", "Synchrotron X-ray", "XRayComputedTomographyMeasurement", "XRayCTInstrument", "TomographicProjectionDataset", "TomographicReconstructionDataset"),
    CaseSpec("synchrotron_tomography", "SynchrotronTomo", "Synchrotron X-ray tomography", "Synchrotron X-ray", "XRayComputedTomographyMeasurement", "XRayCTInstrument", "TomographicProjectionDataset", "TomographicReconstructionDataset"),
)

CASE_BY_SHEET = {item.sheet: item for item in CASE_SPECS}
CASE_BY_KEY = {item.key: item for item in CASE_SPECS}


PROPERTY_FIELDS: dict[str, str] = {
    "temperature": "Temperature",
    "humidity": "RelativeHumidity",
    "pressure": "PressureCharacteristic",
    "accelerationvoltage": "AcceleratingVoltage",
    "acceleratingvoltage": "AcceleratingVoltage",
    "magnification": "Magnification",
    "workingdistance": "WorkingDistance",
    "nominalradius": "AFMTipNominalRadius",
    "measuringsize": "MicroscopyMeasuredArea",
    "measuredareaum2": "MicroscopyMeasuredArea",
    "scanspeed": "FrequencyCharacteristic",
    "ionbeamcurrent": "IonBeamCurrent",
    "ionbeamenergy": "IonBeamEnergy",
    "electroncurrent": "ElectronCurrent",
    "electronbeamenergy": "ElectronBeamEnergy",
    "pixelsize": "PixelSize",
    "cutthickness": "CutThickness",
    "slicenumber": "SliceNumber",
    "dwelltime": "DwellTime",
    "stagetilt": "StageTilt",
    "imageacquisitiontime": "ExposureTime",
    "totalacquisitiontime": "TotalAcquisitionTime",
    "exposuretime": "ExposureTime",
    "projectionnumber": "ProjectionNumber",
    "numberofradiograms": "ProjectionNumber",
    "neutronflux": "NeutronFlux",
    "spatialresolution": "SpatialResolution",
    "sampledetectordistance": "SampleDetectorDistance",
    "distancesampledetector": "SampleDetectorDistance",
    "xrayenergy": "XRayBeamEnergy",
    "sourcemagneticfield": "MagneticFieldCharacteristic",
    "imagesfrequency": "FrequencyCharacteristic",
    "imagefrequency": "FrequencyCharacteristic",
    "fieldofview": "GeometricCharacteristic",
    "fieldofviewx": "GeometricCharacteristic",
    "fieldofviewy": "GeometricCharacteristic",
    "beamsize": "GeometricCharacteristic",
    "resolution": "SpatialResolution",
    "scintillatorthickness": "GeometricCharacteristic",
    "collimatordiameter": "GeometricCharacteristic",
    "pinholesize": "GeometricCharacteristic",
    "pinholesampledistance": "GeometricCharacteristic",
    "focus": "GeometricCharacteristic",
    "sampleelevation": "GeometricCharacteristic",
    "distancesamplesource": "GeometricCharacteristic",
    "rotationdegree": "QuantitativeCharacteristic",
    "numberofflatfields": "CountCharacteristic",
    "numberofdarkfields": "CountCharacteristic",
    "positionreferences": "CountCharacteristic",
    "binning": "CountCharacteristic",
    "timelapse": "TemporalCharacteristic",
    "dataadquisitionrate": "QuantitativeCharacteristic",
    "dataacquisitionrate": "QuantitativeCharacteristic",
    "maximalwavelenght": "GeometricCharacteristic",
    "energyresolution": "QuantitativeCharacteristic",
    "planespacing": "GeometricCharacteristic",
    "tiltcompensation": "QuantitativeCharacteristic",
    "dynamicfocus": "QuantitativeCharacteristic",
    "brightness": "QuantitativeCharacteristic",
    "contrast": "QuantitativeCharacteristic",
}

RESULT_PROPERTIES: dict[tuple[str, str], tuple[str, str]] = {
    ("tem", "average size"): ("MeanParticleSize", "exact existing H2KG size characteristic"),
    ("afm", "average size"): ("MeanParticleSize", "exact existing H2KG size characteristic"),
    ("sem", "support needle length"): ("GeometricCharacteristic", "source-specific geometric output"),
    ("fib_sem", "volume fraction"): ("CompositionCharacteristic", "source-specific fraction; source label/unit conflict retained"),
    ("fib_sem", "porosity"): ("TotalPorosity", "existing H2KG porosity characteristic"),
    ("fib_sem", "direction"): ("GeometricCharacteristic", "generic geometric output because the source axis is unspecified"),
    ("fib_sem", "network relation"): ("Property", "generic property because the source relation metric is unspecified"),
    ("fib_sem", "constrictivity"): ("Constrictivity", "existing H2KG transport characteristic"),
    ("fib_sem", "mean geodesic torutosity"): ("GeodesicTortuosity", "existing H2KG geodesic-tortuosity characteristic"),
    ("ic_sem", "mea thickness"): ("MembraneElectrodeAssemblyThickness", "existing H2KG layer-thickness characteristic"),
    ("ic_sem", "gdl thickness"): ("GasDiffusionLayerThickness", "existing H2KG layer-thickness characteristic"),
    ("ic_sem", "porosity"): ("TotalPorosity", "existing H2KG porosity characteristic"),
    ("neutron_tomography", "tortuosity factor"): ("TortuosityFactor", "existing H2KG tortuosity characteristic"),
    ("neutron_tomography", "averagebarycenter"): ("GeometricCharacteristic", "generic geometric output because axis and unit are absent"),
    ("neutron_tomography", "averagearea"): ("AverageWaterDropletArea", "existing H2KG water-droplet area characteristic"),
    ("neutron_tomography", "averagenumber"): ("AverageWaterDropletCount", "existing H2KG water-droplet count characteristic"),
    ("synchrotron_radiography", "decay factor"): ("TemporalCharacteristic", "source-specific temporal output"),
    ("synchrotron_radiography", "real distance in beam path"): ("GeometricCharacteristic", "source-specific beam-path distance"),
    ("synchrotron_radiography", "electrolyte saturation"): ("CompositionCharacteristic", "source label retained without equating saturation to concentration"),
    ("synchrotron_radiography", "carbonfelt electrolyte air ratio"): ("CompositionCharacteristic", "source-specific ordered phase ratio"),
    ("synchrotron_tomography", "decay factor"): ("TemporalCharacteristic", "source-specific temporal output"),
    ("synchrotron_tomography", "real distance in beam path"): ("GeometricCharacteristic", "source-specific beam-path distance"),
    ("synchrotron_tomography", "electrolyte saturation"): ("CompositionCharacteristic", "source label retained without equating saturation to concentration"),
    ("synchrotron_tomography", "carbonfelt electrolyte air ratio"): ("CompositionCharacteristic", "source-specific ordered phase ratio"),
}

PROCESS_CLASSES: dict[str, str] = {
    "buy": "ProcurementProcess",
    "mix": "MixingOrDispersionProcess",
    "sonification": "Sonication",
    "dispersion": "DispersionProcess",
    "dissolve": "FormulationProcess",
    "dissolved": "FormulationProcess",
    "doctor blade": "DoctorBladeCoating",
    "coat": "CoatingOrDepositionProcess",
    "coating": "CoatingOrDepositionProcess",
    "deposit": "CoatingOrDepositionProcess",
    "deposition": "CoatingOrDepositionProcess",
    "au coating": "SputterCoating",
    "sputter coating": "SputterCoating",
    "dry": "ThermalTreatmentProcess",
    "hotpress": "HotPressing",
    "hot press": "HotPressing",
    "laser cutting": "MachiningProcess",
    "cut": "MachiningProcess",
    "ball milling": "BallMilling",
    "gallium current milling": "MillingProcess",
}


UNIT_MAP: dict[str, tuple[URIRef, URIRef]] = {
    "c": (UNIT.DEG_C, QK.ThermodynamicTemperature),
    "°c": (UNIT.DEG_C, QK.ThermodynamicTemperature),
    "%": (UNIT.PERCENT, QK.DimensionlessRatio),
    "atm": (UNIT.ATM, QK.Pressure),
    "kv": (UNIT.KiloV, QK.ElectricPotential),
    "v": (UNIT.V, QK.ElectricPotential),
    "mm": (UNIT.MilliM, QK.Length),
    "cm": (UNIT.CentiM, QK.Length),
    "m": (UNIT.M, QK.Length),
    "um": (UNIT.MicroM, QK.Length),
    "µm": (UNIT.MicroM, QK.Length),
    "nm": (UNIT.NanoM, QK.Length),
    "mm2": (UNIT.MilliM2, QK.Area),
    "cm2": (UNIT.CentiM2, QK.Area),
    "um2": (UNIT.MicroM2, QK.Area),
    "µm2": (UNIT.MicroM2, QK.Area),
    "s": (UNIT.SEC, QK.Time),
    "ms": (UNIT.MilliSEC, QK.Time),
    "min": (UNIT.MIN, QK.Time),
    "h": (UNIT.HR, QK.Time),
    "hr": (UNIT.HR, QK.Time),
    "hz": (UNIT.HZ, QK.Frequency),
    "pa": (UNIT.PicoA, QK.ElectricCurrent),
    "fa": (UNIT.FemtoA, QK.ElectricCurrent),
    "kev": (UNIT.KiloEV, QK.Energy),
    "t": (UNIT.T, QK.MagneticFluxDensity),
    "°": (UNIT.DEG, QK.Angle),
    "deg": (UNIT.DEG, QK.Angle),
    "mol/l": (URIRef("http://qudt.org/vocab/unit/MOL-PER-L"), QK.AmountOfSubstanceConcentration),
    "mol l-1": (URIRef("http://qudt.org/vocab/unit/MOL-PER-L"), QK.AmountOfSubstanceConcentration),
    "psi": (UNIT.PSI, QK.Pressure),
    "cm/s": (URIRef("http://qudt.org/vocab/unit/CentiM-PER-SEC"), QK.Velocity),
    "pas": (URIRef("http://qudt.org/vocab/unit/PA-SEC"), QK.DynamicViscosity),
    "ml": (UNIT.MilliL, QK.Volume),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _field_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _norm_label(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def _slug(value: Any) -> str:
    token = re.sub(r"[^a-z0-9]+", "-", str(value or "").casefold()).strip("-")
    return token[:80] or "item"


def _status(value: Any) -> str:
    if value is None or (isinstance(value, str) and not value.strip()):
        return "missing"
    text = str(value).strip().casefold()
    if text in {"-", "not specified", "none"}:
        return "not_specified"
    if text == "not applicable":
        return "not_applicable"
    if "to be confirmed" in text or text == "xxxx" or text == "link":
        return "unconfirmed"
    if isinstance(value, str) and value.startswith("="):
        return "formula_unresolved"
    return "reported"


def _record_id(case_key: str, section: str, row: int, column: str, field: str) -> str:
    seed = f"{case_key}|{section}|{row}|{column}|{field}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def ingest_characterization_workbook(
    workbook_path: str | Path,
    manifest_path: str | Path,
    *,
    enforce_fingerprint: bool = True,
) -> dict[str, Any]:
    """Sanitize the corrected workbook into a deterministic public manifest."""

    from openpyxl import load_workbook
    from openpyxl.utils import get_column_letter

    workbook_path = Path(workbook_path)
    manifest_path = Path(manifest_path)
    fingerprint = _sha256(workbook_path)
    if enforce_fingerprint and fingerprint != EXPECTED_WORKBOOK_SHA256:
        raise ValueError(
            f"Unexpected characterization workbook fingerprint {fingerprint}; "
            f"expected {EXPECTED_WORKBOOK_SHA256}."
        )
    workbook = load_workbook(workbook_path, data_only=False, read_only=True)
    missing_sheets = sorted(set(CASE_BY_SHEET) - set(workbook.sheetnames))
    extra_sheets = sorted(set(workbook.sheetnames) - set(CASE_BY_SHEET))
    if missing_sheets or extra_sheets:
        raise ValueError(f"Workbook sheet mismatch: missing={missing_sheets}, extra={extra_sheets}")

    cases: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    for spec in CASE_SPECS:
        sheet = workbook[spec.sheet]
        direct_fields: list[dict[str, Any]] = []
        table_rows: list[dict[str, Any]] = []
        source_records: list[dict[str, Any]] = []
        current_section = ""
        headers: dict[str, list[tuple[int, str]]] = {}
        for row_index, row in enumerate(sheet.iter_rows(values_only=True), start=1):
            section_value = str(row[0] or "").strip()
            if section_value:
                current_section = section_value
            if current_section in DIRECT_SECTIONS:
                field = str(row[1] or "").strip()
                if not field:
                    continue
                field_key = _field_key(field)
                if field_key in EXCLUDED_FIELDS:
                    exclusions.append(
                        {
                            "case": spec.key,
                            "sheet": spec.sheet,
                            "section": current_section,
                            "row": row_index,
                            "field": field,
                            "reason": EXCLUDED_FIELDS[field_key],
                        }
                    )
                    continue
                raw = _json_value(row[2])
                record = {
                    "record_id": _record_id(spec.key, current_section, row_index, "C", field),
                    "case": spec.key,
                    "sheet": spec.sheet,
                    "section": current_section,
                    "row": row_index,
                    "column": "C",
                    "cell": f"{spec.sheet}!C{row_index}",
                    "field": field,
                    "raw_value": raw,
                    "status": _status(raw),
                }
                direct_fields.append(record)
                source_records.append(record)
                continue
            if current_section not in TABLE_SECTIONS:
                continue
            if str(row[1] or "").strip() == "Step":
                headers[current_section] = [
                    (column_index, str(row[column_index - 1] or "").strip())
                    for column_index in range(2, min(len(row), 9) + 1)
                    if str(row[column_index - 1] or "").strip()
                ]
                continue
            if not any(value not in (None, "") for value in row[1:9]):
                continue
            section_headers = headers.get(current_section)
            if not section_headers:
                raise ValueError(f"Missing {current_section} header before {spec.sheet} row {row_index}")
            values: dict[str, Any] = {}
            record_ids: dict[str, str] = {}
            for column_index, field in section_headers:
                raw = _json_value(row[column_index - 1])
                column = get_column_letter(column_index)
                record = {
                    "record_id": _record_id(spec.key, current_section, row_index, column, field),
                    "case": spec.key,
                    "sheet": spec.sheet,
                    "section": current_section,
                    "row": row_index,
                    "column": column,
                    "cell": f"{spec.sheet}!{column}{row_index}",
                    "field": field,
                    "raw_value": raw,
                    "status": _status(raw),
                }
                if (
                    spec.key == "fib_sem"
                    and current_section == "anal"
                    and field == "AmountTarget"
                    and _norm_label(row[7]) == "volume fraction"
                    and re.search(r"\bnm\b", str(raw or ""), flags=re.IGNORECASE)
                ):
                    record["status"] = "semantic_conflict"
                    record["conflict"] = "A length unit is incompatible with the reported volume-fraction label."
                values[field] = raw
                record_ids[field] = record["record_id"]
                source_records.append(record)
            table_rows.append(
                {
                    "section": current_section,
                    "row": row_index,
                    "values": values,
                    "record_ids": record_ids,
                }
            )
        cases.append(
            {
                "key": spec.key,
                "sheet": spec.sheet,
                "title": spec.title,
                "family": spec.family,
                "measurement_class": spec.measurement_class,
                "instrument_class": spec.instrument_class,
                "raw_dataset_class": spec.raw_dataset_class,
                "processed_dataset_class": spec.processed_dataset_class,
                "direct_fields": direct_fields,
                "table_rows": table_rows,
                "source_records": source_records,
                "eligible_field_count": len(source_records),
            }
        )
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "source": {
            "title": "Corrected imaging-characterization workbook",
            "source_filename": workbook_path.name,
            "sha256": fingerprint,
            "redistribution": "The source workbook is not redistributed; this manifest contains sanitized scientific fields only.",
        },
        "case_count": len(cases),
        "method_family_count": len({case["family"] for case in cases}),
        "eligible_field_count": sum(case["eligible_field_count"] for case in cases),
        "excluded_field_count": len(exclusions),
        "excluded_fields": exclusions,
        "cases": cases,
    }
    dump_json(manifest_path, manifest)
    return {
        "status": "generated",
        "manifest": str(manifest_path),
        "source_sha256": fingerprint,
        "case_count": len(cases),
        "eligible_field_count": manifest["eligible_field_count"],
        "excluded_field_count": len(exclusions),
    }


def _bind(graph: Graph | Dataset) -> None:
    for prefix, namespace in {
        "h2kg": H2KG,
        "kg": KG,
        "case": CASE,
        "qudt": QUDT,
        "unit": UNIT,
        "quantitykind": QK,
        "prov": PROV,
        "dcterms": DCTERMS,
        "skos": SKOS,
        "sh": SH,
    }.items():
        graph.bind(prefix, namespace)


def _case_iri(case_key: str, kind: str, label: Any, suffix: str = "") -> URIRef:
    seed = f"{case_key}|{kind}|{label}|{suffix}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:10]
    return URIRef(f"{CASE}{case_key}/{kind}/{_slug(label)}-{digest}")


def _literal_raw(value: Any) -> Literal:
    if isinstance(value, bool):
        return Literal(value)
    if isinstance(value, int):
        return Literal(value)
    if isinstance(value, float):
        return Literal(value)
    return Literal("" if value is None else str(value))


def _decimal(value: str) -> Decimal | None:
    text = value.strip().replace(",", "")
    text = re.sub(r"^[~≈]", "", text).strip()
    match = re.fullmatch(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))(?:\s*[x×]\s*10\^([+-]?\d+))?", text, flags=re.IGNORECASE)
    if not match:
        exponent = re.fullmatch(r"10\^([+-]?\d+)", text)
        if exponent:
            return Decimal(10) ** int(exponent.group(1))
        return None
    try:
        base = Decimal(match.group(1))
        return base * (Decimal(10) ** int(match.group(2))) if match.group(2) else base
    except InvalidOperation:
        return None


def _unit_token(value: Any) -> str:
    text = str(value or "").strip().replace("μ", "µ")
    text = re.sub(r"\s+", "", text)
    return text.casefold()


def _parse_quantity(raw: Any, explicit_unit: Any = None) -> dict[str, Any] | None:
    if raw is None or isinstance(raw, bool):
        return None
    raw_text = str(raw).strip().replace("μ", "µ")
    if not raw_text or ":" in raw_text and re.fullmatch(r"\d+(?::\d+)+", raw_text):
        return None
    qualifier = ""
    if re.match(r"(?i)^up\s+to", raw_text):
        qualifier = "upper_bound"
        raw_text = re.sub(r"(?i)^up\s+to\s*", "", raw_text).strip()
    raw_text = raw_text.lstrip("~≈ ")
    number_text = raw_text
    unit_text = str(explicit_unit or "").strip()
    if not unit_text:
        match = re.match(r"^([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:\s*[x×]\s*10\^[+-]?\d+)?|10\^[+-]?\d+)\s*(.*)$", raw_text, flags=re.IGNORECASE)
        if not match:
            return None
        number_text, unit_text = match.group(1), match.group(2)
    number = _decimal(number_text)
    if number is None:
        return None
    token = _unit_token(unit_text)
    mapping = UNIT_MAP.get(token)
    if not mapping:
        if not token:
            return {"numeric": number, "unit": None, "quantity_kind": None, "qualifier": qualifier}
        return {"numeric": number, "unit": None, "quantity_kind": None, "source_unit": unit_text, "qualifier": qualifier}
    return {"numeric": number, "unit": mapping[0], "quantity_kind": mapping[1], "source_unit": unit_text, "qualifier": qualifier}


def _active_terms(taxonomy_registry_path: Path | None) -> dict[str, dict[str, Any]]:
    if taxonomy_registry_path is None or not taxonomy_registry_path.exists():
        return {}
    payload = json.loads(taxonomy_registry_path.read_text(encoding="utf-8"))
    return {
        str(term["local_name"]): term
        for term in payload.get("terms", [])
        if term.get("disposition") == "active_local_class"
    }


def _safe_class(local_name: str, active_terms: dict[str, dict[str, Any]], fallback: str) -> URIRef:
    if not active_terms or local_name in active_terms:
        return H2KG[local_name]
    return H2KG[fallback]


def _direct_lookup(case: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    values: dict[str, list[dict[str, Any]]] = {}
    for record in case["direct_fields"]:
        values.setdefault(_field_key(record["field"]), []).append(record)
    return values


def _paired_direct_units(case: dict[str, Any]) -> dict[str, Any]:
    lookup = _direct_lookup(case)
    result: dict[str, Any] = {}
    for key, records in lookup.items():
        if key.endswith("unit"):
            result[key[:-4]] = records[0].get("raw_value")
        elif len(records) > 1:
            first, second = records[0].get("raw_value"), records[1].get("raw_value")
            if _decimal(str(first or "")) is not None and _decimal(str(second or "")) is None:
                result[key] = second
    return result


def _source_record_iri(record_id: str) -> URIRef:
    return URIRef(f"{CASE}source/{record_id}")


def _add_source_records(
    graph: Graph,
    case: dict[str, Any],
    workbook: URIRef,
) -> dict[str, URIRef]:
    record_iris: dict[str, URIRef] = {}
    for record in case["source_records"]:
        subject = _source_record_iri(record["record_id"])
        record_iris[record["record_id"]] = subject
        graph.add((subject, RDF.type, KG.SourceField))
        graph.add((subject, RDF.type, H2KG.Metadata))
        graph.add((subject, DCTERMS.identifier, Literal(record["record_id"])))
        graph.add((subject, RDFS.label, Literal(f"{record['field']} ({record['cell']})")))
        graph.add((subject, KG.sourceSheet, Literal(record["sheet"])))
        graph.add((subject, KG.sourceSection, Literal(record["section"])))
        graph.add((subject, KG.sourceCell, Literal(record["cell"])))
        graph.add((subject, KG.fieldName, Literal(record["field"])))
        graph.add((subject, KG.valueStatus, KG[str(record["status"])]))
        graph.add((subject, PROV.wasDerivedFrom, workbook))
        if record.get("raw_value") is not None:
            graph.add((subject, RDF.value, _literal_raw(record["raw_value"])))
        if record.get("conflict"):
            graph.add((subject, DCTERMS.description, Literal(record["conflict"])))
    return record_iris


def _add_local_schema(graph: Graph) -> None:
    for cls, label in (
        (KG.SourceField, "Source field"),
        (KG.ValidationFinding, "Validation finding"),
        (KG.WorkbookSnapshot, "Workbook snapshot"),
        (KG.CharacterizationCase, "Characterization case"),
    ):
        graph.add((cls, RDF.type, OWL.Class))
        graph.add((cls, RDFS.label, Literal(label)))
    for prop, label in (
        (KG.sourceSheet, "source sheet"),
        (KG.sourceSection, "source section"),
        (KG.sourceCell, "source cell"),
        (KG.fieldName, "field name"),
        (KG.valueStatus, "value status"),
        (KG.mappedEntity, "mapped entity"),
        (KG.case, "case"),
        (KG.findingCode, "finding code"),
        (KG.severity, "severity"),
        (KG.mappingRationale, "mapping rationale"),
        (KG.sourceUnit, "source unit"),
        (KG.valueQualifier, "value qualifier"),
    ):
        graph.add((prop, RDF.type, OWL.AnnotationProperty))
        graph.add((prop, RDFS.label, Literal(label)))
    for status in (
        "reported", "missing", "not_applicable", "not_specified", "unconfirmed",
        "formula_unresolved", "semantic_conflict", "unit_unresolved",
    ):
        iri = KG[status]
        graph.add((iri, RDF.type, SKOS.Concept))
        graph.add((iri, SKOS.prefLabel, Literal(status.replace("_", " "))))


def _add_quantity(
    graph: Graph,
    bearer: URIRef,
    quantity: dict[str, Any] | None,
    case_key: str,
    seed: str,
) -> URIRef | None:
    if not quantity or quantity.get("unit") is None or quantity.get("quantity_kind") is None:
        return None
    qv = _case_iri(case_key, "quantity-value", seed)
    graph.add((qv, RDF.type, QUDT.QuantityValue))
    graph.add((qv, QUDT.numericValue, Literal(quantity["numeric"], datatype=XSD.decimal)))
    graph.add((qv, QUDT.unit, quantity["unit"]))
    graph.add((qv, QUDT.quantityKind, quantity["quantity_kind"]))
    unit_label = str(quantity.get("source_unit") or str(quantity["unit"]).rsplit("/", 1)[-1])
    graph.add((qv, RDFS.label, Literal(f"{quantity['numeric']} {unit_label}".strip())))
    if quantity.get("qualifier"):
        graph.add((qv, KG.valueQualifier, Literal(quantity["qualifier"])))
    graph.add((bearer, H2KG.hasQuantityValue, qv))
    return qv


def _add_metadata_link(graph: Graph, entity: URIRef, source_record: URIRef) -> None:
    graph.add((entity, H2KG.hasMetadata, source_record))
    graph.add((entity, PROV.wasDerivedFrom, source_record))
    graph.add((source_record, KG.mappedEntity, entity))


def _entity_for_label(
    graph: Graph,
    cache: dict[tuple[str, str], URIRef],
    case_key: str,
    label: Any,
    kind: str,
    specific_type: URIRef | None = None,
) -> URIRef:
    normalized = _norm_label(label) or "unspecified"
    key = (kind, normalized)
    if key in cache:
        return cache[key]
    entity = _case_iri(case_key, kind, normalized)
    cache[key] = entity
    generic_type = H2KG.Matter if kind == "matter" else H2KG.Data
    graph.add((entity, RDF.type, generic_type))
    if specific_type is not None:
        graph.add((entity, RDF.type, specific_type))
    graph.add((entity, RDFS.label, Literal(str(label or "Unspecified source entity").strip())))
    graph.add((entity, KG.case, CASE[case_key]))
    return entity


def _parameter_property_class(field: str, unit: Any, active_terms: dict[str, dict[str, Any]]) -> URIRef:
    key = _field_key(field)
    local_name = PROPERTY_FIELDS.get(key)
    if local_name:
        return _safe_class(local_name, active_terms, "QuantitativeCharacteristic")
    token = _unit_token(unit)
    if token in {"mm", "cm", "m", "um", "µm", "nm", "mm2", "cm2", "um2", "µm2"}:
        return H2KG.GeometricCharacteristic
    if token in {"s", "ms", "min", "h", "hr"}:
        return H2KG.TemporalCharacteristic
    if token == "hz":
        return H2KG.FrequencyCharacteristic
    if token == "t":
        return _safe_class("MagneticFieldCharacteristic", active_terms, "QuantitativeCharacteristic")
    return H2KG.QuantitativeCharacteristic


def _add_parameter(
    graph: Graph,
    owner: URIRef,
    case_key: str,
    label: str,
    raw: Any,
    status: str,
    source_record: URIRef,
    active_terms: dict[str, dict[str, Any]],
    unit: Any = None,
    suffix: str = "",
) -> dict[str, Any]:
    record = _case_iri(case_key, "parameter-record", label, suffix)
    prop = _case_iri(case_key, "property-occurrence", label, suffix)
    prop_class = _parameter_property_class(label, unit, active_terms)
    graph.add((owner, H2KG.hasParameter, record))
    graph.add((record, RDF.type, H2KG.Parameter))
    graph.add((record, RDFS.label, Literal(f"{label} parameter record")))
    graph.add((record, H2KG.ofProperty, prop))
    graph.add((record, KG.valueStatus, KG[status]))
    graph.add((prop, RDF.type, prop_class))
    graph.add((prop, RDFS.label, Literal(label)))
    graph.add((prop, H2KG.isCharacteristicOf, owner))
    _add_metadata_link(graph, record, source_record)
    _add_metadata_link(graph, prop, source_record)
    parsed = _with_implicit_quantity_kind(_parse_quantity(raw, unit), label)
    qv = _add_quantity(graph, prop, parsed if status == "reported" else None, case_key, f"{label}|{suffix}")
    return {
        "parameter_record": str(record),
        "property_occurrence": str(prop),
        "property_class": str(prop_class),
        "quantity_value": str(qv or ""),
        "mapping_outcome": "parameter_record",
        "unit_status": "mapped" if qv else ("not_numeric" if parsed is None else "unit_unresolved"),
    }


def _with_implicit_quantity_kind(quantity: dict[str, Any] | None, label: str) -> dict[str, Any] | None:
    """Complete only scientifically unambiguous count/dimensionless quantities."""

    if quantity is None or quantity.get("unit") is not None:
        return quantity
    key = _field_key(label)
    count_fields = {
        "projectionnumber", "numberofradiograms", "numberofflatfields", "numberofdarkfields",
        "positionreferences", "slicenumber", "averagenumber",
    }
    dimensionless_fields = {
        "magnification", "binning", "brightness", "contrast", "tiltcompensation",
        "dynamicfocus", "ldvalue", "tortuosityfactor",
    }
    if key in count_fields:
        return {**quantity, "unit": UNIT.UNITLESS, "quantity_kind": QK.Count}
    if key in dimensionless_fields:
        return {**quantity, "unit": UNIT.UNITLESS, "quantity_kind": QK.Dimensionless}
    return quantity


def _condition_pairs(raw: Any) -> list[tuple[str, str]]:
    text = str(raw or "").strip()
    if not text or text == "-":
        return []
    pairs: list[tuple[str, str]] = []
    for part in re.split(r"[|\n]+", text):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            key, value = part.split("=", 1)
            pairs.append((key.strip(), value.strip()))
            continue
        match = re.match(r"^([A-Za-z][A-Za-z /_-]*?)\s+([+-]?(?:\d|\.\d).*)$", part)
        if match:
            pairs.append((match.group(1).strip(), match.group(2).strip()))
    return pairs


def _split_software(raw: Any) -> list[str]:
    text = str(raw or "").strip()
    if not text or text == "-" or "xxxx" in text.casefold():
        return []
    text = re.sub(r"(?i)^software\s*=\s*", "", text)
    text = text.split("|", 1)[0]
    return [item.strip() for item in re.split(r"[,;]", text) if item.strip()]


def _dataset_type(label: Any, spec: CaseSpec) -> URIRef:
    normalized = _norm_label(label)
    if normalized in {"rawdata", "raw data"} or normalized.startswith("raw "):
        return H2KG[spec.raw_dataset_class]
    if "tomograph" in normalized or "reconstruct" in normalized:
        return H2KG.TomographicReconstructionDataset
    if "image" in normalized:
        return H2KG[spec.processed_dataset_class]
    return H2KG.Dataset


def _semantic_conflict(case_key: str, target: str, amount: Any) -> str:
    if case_key == "fib_sem" and _norm_label(target) == "volume fraction" and re.search(r"\bnm\b", str(amount or ""), flags=re.IGNORECASE):
        return "label_unit_conflict"
    if _norm_label(target) in {"averagebarycenter", "direction"}:
        return "incomplete_semantics"
    if _norm_label(target) in {"network relation"}:
        return "unresolved_metric"
    if re.search(r"\bpu\b", str(amount or ""), flags=re.IGNORECASE):
        return "unit_unresolved"
    if re.fullmatch(r"\d+(?::\d+)+", str(amount or "").strip()):
        return "ordered_ratio_basis_unspecified"
    return ""


def _add_finding(
    graph: Graph,
    case_key: str,
    code: str,
    message: str,
    source_record: URIRef | None,
    entity: URIRef | None,
    severity: str = "warning",
) -> URIRef:
    finding = _case_iri(case_key, "finding", code, str(source_record or entity or message))
    graph.add((finding, RDF.type, KG.ValidationFinding))
    graph.add((finding, KG.findingCode, Literal(code)))
    graph.add((finding, KG.severity, Literal(severity)))
    graph.add((finding, DCTERMS.description, Literal(message)))
    graph.add((finding, KG.case, CASE[case_key]))
    if source_record:
        graph.add((finding, PROV.wasDerivedFrom, source_record))
    if entity:
        graph.add((finding, DCTERMS.subject, entity))
    return finding


def _build_case(
    dataset: Dataset,
    case: dict[str, Any],
    active_terms: dict[str, dict[str, Any]],
    workbook: URIRef,
) -> dict[str, Any]:
    spec = CASE_BY_KEY[case["key"]]
    source_graph = dataset.graph(GRAPH[f"source/{spec.key}"])
    semantic_graph = dataset.graph(GRAPH[f"semantic/{spec.key}"])
    validation_graph = dataset.graph(GRAPH[f"validation/{spec.key}"])
    for graph in (source_graph, semantic_graph, validation_graph):
        _bind(graph)
    record_iris = _add_source_records(source_graph, case, workbook)
    case_iri = CASE[spec.key]
    semantic_graph.add((case_iri, RDF.type, KG.CharacterizationCase))
    semantic_graph.add((case_iri, RDFS.label, Literal(spec.title)))
    semantic_graph.add((case_iri, DCTERMS.identifier, Literal(spec.key)))

    measurement = _case_iri(spec.key, "measurement", spec.title)
    instrument = _case_iri(spec.key, "instrument", spec.title)
    semantic_graph.add((measurement, RDF.type, H2KG.Measurement))
    semantic_graph.add((measurement, RDF.type, H2KG[spec.measurement_class]))
    semantic_graph.add((measurement, RDFS.label, Literal(f"{spec.title} measurement")))
    semantic_graph.add((measurement, KG.case, case_iri))
    semantic_graph.add((instrument, RDF.type, H2KG.Instrument))
    semantic_graph.add((instrument, RDF.type, H2KG[spec.instrument_class]))
    semantic_graph.add((instrument, RDFS.label, Literal(f"{spec.title} instrument")))
    semantic_graph.add((instrument, KG.case, case_iri))
    semantic_graph.add((measurement, H2KG.usesInstrument, instrument))

    entity_cache: dict[tuple[str, str], URIRef] = {}
    raw_dataset = _entity_for_label(semantic_graph, entity_cache, spec.key, "RawData", "data", H2KG[spec.raw_dataset_class])
    semantic_graph.add((measurement, H2KG.hasOutputData, raw_dataset))
    mapping_rows: list[dict[str, Any]] = []
    mapped_records: set[str] = set()
    direct_lookup = _direct_lookup(case)
    units = _paired_direct_units(case)

    specimen_record = next((record for record in case["direct_fields"] if _field_key(record["field"]) == "specimen"), None)
    specimen_label = specimen_record.get("raw_value") if specimen_record else "characterization specimen"
    specimen = _entity_for_label(semantic_graph, entity_cache, spec.key, "Sample", "matter", H2KG.Specimen)
    semantic_graph.set((specimen, RDFS.label, Literal(str(specimen_label or "Characterization specimen"))))
    semantic_graph.add((measurement, H2KG.hasMeasurementSubject, specimen))
    if specimen_record:
        source = record_iris[specimen_record["record_id"]]
        _add_metadata_link(semantic_graph, specimen, source)
        mapped_records.add(specimen_record["record_id"])

    for record in case["direct_fields"]:
        source = record_iris[record["record_id"]]
        key = _field_key(record["field"])
        target = measurement
        outcome = "measurement_metadata"
        if record["section"] == "inst":
            target = instrument
            outcome = "instrument_metadata"
        elif record["section"] == "org" and key in {
            "filename", "format", "filesize", "filesizeunit", "dimensionx", "dimensiony",
            "dimensionz", "pixelpermetric", "link", "maskexist", "masklink",
        }:
            target = raw_dataset
            outcome = "dataset_metadata"
        if record["section"] in {"char", "inst"} and key in PROPERTY_FIELDS and not key.endswith("unit"):
            unit = units.get(key)
            mapping = _add_parameter(
                semantic_graph,
                measurement,
                spec.key,
                record["field"],
                record.get("raw_value"),
                record["status"],
                source,
                active_terms,
                unit,
                record["record_id"],
            )
            outcome = mapping["mapping_outcome"]
            mapping_rows.append({**record, **mapping, "linked_entity": mapping["property_occurrence"]})
            mapped_records.add(record["record_id"])
            if mapping["unit_status"] == "unit_unresolved" and record["status"] == "reported":
                _add_finding(
                    validation_graph,
                    spec.key,
                    "unit_unresolved",
                    f"{record['field']} retains the source unit without inventing a QUDT mapping.",
                    source,
                    URIRef(mapping["property_occurrence"]),
                )
            continue
        _add_metadata_link(semantic_graph, target, source)
        mapped_records.add(record["record_id"])
        mapping_rows.append({**record, "mapping_outcome": outcome, "linked_entity": str(target)})

    last_material = specimen
    analysis_rows: list[tuple[dict[str, Any], URIRef, URIRef]] = []
    stage_targets: dict[tuple[str, str, str], set[str]] = {}
    for candidate in case["table_rows"]:
        candidate_values = candidate["values"]
        stage = (
            candidate["section"],
            str(candidate_values.get("Step") or "").strip(),
            str(candidate_values.get("Technique") or "").strip(),
        )
        stage_targets.setdefault(stage, set()).add(_norm_label(candidate_values.get("Target")))
    for row in case["table_rows"]:
        section = row["section"]
        values = row["values"]
        process_label = values.get("Technique") or f"{section} step {values.get('Step', row['row'])}"
        stage = (
            section,
            str(values.get("Step") or "").strip(),
            str(values.get("Technique") or "").strip(),
        )
        # Repeated rows with the same step and target encode multiple inputs to
        # one process. Analysis rows may encode several outputs of one step.
        # Distinct synthesis targets remain separate process occurrences.
        can_group = bool(stage[1] and stage[2]) and (
            section == "anal" or len(stage_targets[stage]) == 1
        )
        process_suffix = "|".join(stage) if can_group else f"{'|'.join(stage)}|row:{row['row']}"
        process = _case_iri(spec.key, f"{section}-process", process_label, process_suffix)
        semantic_graph.add((process, RDF.type, H2KG.Process))
        if section in {"syn", "sp"}:
            semantic_graph.add((process, RDF.type, H2KG.Manufacturing))
        process_class = PROCESS_CLASSES.get(_norm_label(process_label))
        if process_class:
            semantic_graph.add((process, RDF.type, _safe_class(process_class, active_terms, "Process")))
        elif section == "pre":
            semantic_graph.add((process, RDF.type, _safe_class("DataProcessing", active_terms, "Process")))
        elif section == "anal":
            semantic_graph.add((process, RDF.type, _safe_class("Analysis", active_terms, "Process")))
        semantic_graph.add((process, RDFS.label, Literal(str(process_label))))
        semantic_graph.add((process, KG.case, case_iri))
        precursor = values.get("Precursor")
        target_label = values.get("Target")
        if section in {"syn", "sp"}:
            if precursor:
                input_entity = _entity_for_label(semantic_graph, entity_cache, spec.key, precursor, "matter")
                semantic_graph.add((process, H2KG.hasInputMaterial, input_entity))
            if target_label:
                output_entity = specimen if _norm_label(target_label) == "sample" else _entity_for_label(semantic_graph, entity_cache, spec.key, target_label, "matter")
                semantic_graph.add((process, H2KG.hasOutputMaterial, output_entity))
                last_material = output_entity
        else:
            input_entity = raw_dataset if _norm_label(precursor) in {"rawdata", "raw data"} else _entity_for_label(semantic_graph, entity_cache, spec.key, precursor or "unspecified input data", "data", _dataset_type(precursor, spec))
            semantic_graph.add((process, H2KG.hasInputData, input_entity))
            if section == "pre" and target_label:
                output_entity = _entity_for_label(semantic_graph, entity_cache, spec.key, target_label, "data", _dataset_type(target_label, spec))
                semantic_graph.add((process, H2KG.hasOutputData, output_entity))
            elif section == "anal":
                analysis_rows.append((row, process, input_entity))

        for field, raw in values.items():
            record_id = row["record_ids"].get(field)
            if not record_id:
                continue
            source = record_iris[record_id]
            _add_metadata_link(semantic_graph, process, source)
            mapped_records.add(record_id)
            mapping_rows.append({
                "record_id": record_id,
                "case": spec.key,
                "sheet": spec.sheet,
                "section": section,
                "row": row["row"],
                "column": next((r["column"] for r in case["source_records"] if r["record_id"] == record_id), ""),
                "cell": next((r["cell"] for r in case["source_records"] if r["record_id"] == record_id), ""),
                "field": field,
                "raw_value": raw,
                "status": next((r["status"] for r in case["source_records"] if r["record_id"] == record_id), ""),
                "mapping_outcome": "process_field",
                "linked_entity": str(process),
            })
        condition_record_id = row["record_ids"].get("Condition")
        if condition_record_id:
            condition_source = record_iris[condition_record_id]
            for index, (name, value) in enumerate(_condition_pairs(values.get("Condition")), start=1):
                parsed = _parse_quantity(value)
                # Textual provenance such as manufacturer, gas, software, or
                # algorithm names remains metadata on the process.  Only a
                # defensibly parsed quantity becomes a parameter record.
                if parsed is None:
                    continue
                unit = parsed.get("source_unit") if parsed else None
                _add_parameter(
                    semantic_graph,
                    process,
                    spec.key,
                    name,
                    value,
                    "reported",
                    condition_source,
                    active_terms,
                    unit,
                    f"row-{row['row']}-{index}",
                )
        software_record_id = row["record_ids"].get("Software")
        if software_record_id:
            software_source = record_iris[software_record_id]
            for software_label in _split_software(values.get("Software")):
                software = _case_iri(spec.key, "software", software_label)
                semantic_graph.add((software, RDF.type, H2KG.SoftwareArtifact))
                semantic_graph.add((software, RDFS.label, Literal(software_label)))
                semantic_graph.add((process, H2KG.usesSoftware, software))
                _add_metadata_link(semantic_graph, software, software_source)

    if last_material != specimen:
        # Preserve source topology while ensuring the direct measurement subject is the final sample node.
        semantic_graph.add((measurement, H2KG.hasMeasurementSubject, specimen))

    result_count = 0
    for row, process, input_data in analysis_rows:
        values = row["values"]
        target_label = str(values.get("Target") or "Unspecified result")
        amount = values.get("AmountTarget")
        normalized_target = _norm_label(target_label)
        local_name, rationale = RESULT_PROPERTIES.get(
            (spec.key, normalized_target),
            ("Property", "source-specific output represented by the generic H2KG property anchor"),
        )
        prop_class = _safe_class(local_name, active_terms, "Property")
        data_point = _case_iri(spec.key, "data-point", target_label, str(row["row"]))
        prop = _case_iri(spec.key, "result-property", target_label, str(row["row"]))
        semantic_graph.add((data_point, RDF.type, H2KG.Data))
        semantic_graph.add((data_point, RDF.type, H2KG.DataPoint))
        semantic_graph.add((data_point, RDFS.label, Literal(f"{target_label} result")))
        semantic_graph.add((data_point, H2KG.fromMeasurement, measurement))
        semantic_graph.add((data_point, PROV.wasGeneratedBy, process))
        semantic_graph.add((data_point, H2KG.ofProperty, prop))
        semantic_graph.add((data_point, KG.case, case_iri))
        semantic_graph.add((process, H2KG.hasInputData, input_data))
        semantic_graph.add((process, H2KG.hasOutputData, data_point))
        semantic_graph.add((prop, RDF.type, prop_class))
        semantic_graph.add((prop, RDFS.label, Literal(target_label)))
        semantic_graph.add((prop, KG.mappingRationale, Literal(rationale)))
        semantic_graph.add((prop, H2KG.isCharacteristicOf, specimen))
        semantic_graph.add((prop, KG.case, case_iri))
        target_record = record_iris[row["record_ids"]["Target"]]
        amount_record = record_iris[row["record_ids"]["AmountTarget"]]
        _add_metadata_link(semantic_graph, data_point, target_record)
        _add_metadata_link(semantic_graph, prop, target_record)
        _add_metadata_link(semantic_graph, prop, amount_record)
        parsed = _with_implicit_quantity_kind(_parse_quantity(amount), target_label)
        conflict = _semantic_conflict(spec.key, target_label, amount)
        if not conflict and parsed and parsed.get("unit") and parsed.get("quantity_kind"):
            _add_quantity(semantic_graph, prop, parsed, spec.key, f"result|{row['row']}|{target_label}")
        elif conflict:
            _add_finding(
                validation_graph,
                spec.key,
                conflict,
                f"{target_label}: {amount!s} is retained as source evidence without an unsupported normalized quantity assertion.",
                amount_record,
                prop,
            )
        elif amount not in (None, ""):
            _add_finding(
                validation_graph,
                spec.key,
                "quantity-incomplete",
                f"{target_label}: the reported value is retained, but an exact value/unit interpretation is unavailable.",
                amount_record,
                prop,
            )
        mapping_rows.append({
            **next(record for record in case["source_records"] if record["record_id"] == row["record_ids"]["Target"]),
            "mapping_outcome": "result_property",
            "linked_entity": str(prop),
            "property_class": str(prop_class),
            "mapping_rationale": rationale,
        })
        result_count += 1

    # Make omissions and conservative statuses explicit validation findings.
    for record in case["source_records"]:
        if record["status"] in {"missing", "not_applicable", "not_specified", "unconfirmed", "formula_unresolved", "semantic_conflict"}:
            _add_finding(
                validation_graph,
                spec.key,
                f"source_{record['status']}",
                f"{record['field']} is recorded as {record['status'].replace('_', ' ')} at {record['cell']}.",
                record_iris[record["record_id"]],
                None,
                "information" if record["status"] in {"not_applicable", "not_specified"} else "warning",
            )

    for record in case["source_records"]:
        if record["record_id"] not in mapped_records:
            source = record_iris[record["record_id"]]
            _add_metadata_link(semantic_graph, case_iri, source)
            mapping_rows.append({**record, "mapping_outcome": "source_only", "linked_entity": str(case_iri)})
            mapped_records.add(record["record_id"])

    return {
        "key": spec.key,
        "title": spec.title,
        "measurement": str(measurement),
        "instrument": str(instrument),
        "specimen": str(specimen),
        "raw_dataset": str(raw_dataset),
        "source_record_count": len(record_iris),
        "mapped_record_count": len(mapped_records),
        "source_status_counts": {
            status: sum(1 for record in case["source_records"] if record["status"] == status)
            for status in SOURCE_STATUSES
        },
        "result_count": result_count,
        "mapping_rows": mapping_rows,
        "source_graph": str(GRAPH[f"source/{spec.key}"]),
        "semantic_graph": str(GRAPH[f"semantic/{spec.key}"]),
        "validation_graph": str(GRAPH[f"validation/{spec.key}"]),
    }


def _shape_graph() -> Graph:
    shapes = Graph()
    _bind(shapes)
    shapes.parse(data=f"""
@prefix h2kg: <{H2KG}> .
@prefix kg: <{KG}> .
@prefix prov: <{PROV}> .
@prefix qudt: <{QUDT}> .
@prefix sh: <{SH}> .
@prefix xsd: <{XSD}> .

kg:MeasurementShape a sh:NodeShape ;
  sh:targetClass h2kg:Measurement ;
  sh:property [ sh:path h2kg:hasMeasurementSubject ; sh:minCount 1 ; sh:class h2kg:Matter ] ;
  sh:property [ sh:path h2kg:usesInstrument ; sh:minCount 1 ; sh:class h2kg:Instrument ] ;
  sh:property [ sh:path h2kg:hasParameter ; sh:class h2kg:Parameter ] ;
  sh:property [ sh:path h2kg:hasOutputData ; sh:minCount 1 ; sh:class h2kg:Data ] .

kg:ProcessShape a sh:NodeShape ;
  sh:targetClass h2kg:Process ;
  sh:property [ sh:path h2kg:hasParameter ; sh:class h2kg:Parameter ] ;
  sh:property [ sh:path h2kg:hasInputMaterial ; sh:class h2kg:Matter ] ;
  sh:property [ sh:path h2kg:hasOutputMaterial ; sh:class h2kg:Matter ] ;
  sh:property [ sh:path h2kg:hasInputData ; sh:class h2kg:Data ] ;
  sh:property [ sh:path h2kg:hasOutputData ; sh:class h2kg:Data ] ;
  sh:property [ sh:path h2kg:usesInstrument ; sh:class h2kg:Instrument ] ;
  sh:property [ sh:path h2kg:usesSoftware ; sh:class h2kg:SoftwareArtifact ] .

kg:ParameterShape a sh:NodeShape ;
  sh:targetClass h2kg:Parameter ;
  sh:property [ sh:path h2kg:ofProperty ; sh:minCount 1 ; sh:maxCount 1 ; sh:class h2kg:Property ] .

kg:DataPointShape a sh:NodeShape ;
  sh:targetClass h2kg:DataPoint ;
  sh:property [ sh:path h2kg:fromMeasurement ; sh:minCount 1 ; sh:maxCount 1 ; sh:class h2kg:Measurement ] ;
  sh:property [ sh:path prov:wasGeneratedBy ; sh:minCount 1 ; sh:class h2kg:Process ] ;
  sh:property [ sh:path h2kg:ofProperty ; sh:minCount 1 ; sh:maxCount 1 ; sh:class h2kg:Property ] .

kg:PropertyShape a sh:NodeShape ;
  sh:targetClass h2kg:Property ;
  sh:property [ sh:path h2kg:isCharacteristicOf ; sh:minCount 1 ; sh:maxCount 1 ] ;
  sh:property [ sh:path h2kg:hasQuantityValue ; sh:class qudt:QuantityValue ] .

kg:QuantityValueShape a sh:NodeShape ;
  sh:targetClass qudt:QuantityValue ;
  sh:property [ sh:path qudt:numericValue ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:decimal ] ;
  sh:property [ sh:path qudt:unit ; sh:minCount 1 ; sh:maxCount 1 ; sh:nodeKind sh:IRI ] ;
  sh:property [ sh:path qudt:quantityKind ; sh:minCount 1 ; sh:maxCount 1 ; sh:nodeKind sh:IRI ] .

kg:SourceFieldShape a sh:NodeShape ;
  sh:targetClass kg:SourceField ;
  sh:property [ sh:path kg:sourceCell ; sh:minCount 1 ; sh:maxCount 1 ] ;
  sh:property [ sh:path kg:fieldName ; sh:minCount 1 ; sh:maxCount 1 ] ;
  sh:property [ sh:path kg:valueStatus ; sh:minCount 1 ; sh:maxCount 1 ] ;
  sh:property [ sh:path prov:wasDerivedFrom ; sh:minCount 1 ; sh:maxCount 1 ] .
""", format="turtle")
    return shapes


def _flatten(dataset: Dataset) -> Graph:
    flat = Graph()
    _bind(flat)
    for graph in dataset.graphs():
        for triple in graph:
            flat.add(triple)
    return flat


def _referenced_taxonomy_subset(flat: Graph, taxonomy_path: Path | None) -> Graph:
    subset = Graph()
    _bind(subset)
    if taxonomy_path is None or not taxonomy_path.exists():
        return subset
    taxonomy = Graph().parse(taxonomy_path, format="turtle")
    seeds = {
        node
        for _, predicate, node in flat
        if isinstance(node, URIRef) and (predicate == RDF.type or str(node).startswith(str(H2KG)))
    }
    seeds.update(predicate for _, predicate, _ in flat if str(predicate).startswith(str(H2KG)))
    queue = list(seeds)
    seen: set[URIRef] = set()
    while queue:
        subject = queue.pop()
        if subject in seen:
            continue
        seen.add(subject)
        for triple in taxonomy.triples((subject, None, None)):
            subset.add(triple)
            if triple[1] == RDFS.subClassOf and isinstance(triple[2], URIRef):
                queue.append(triple[2])
    return subset


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        fieldnames = sorted({key for row in rows for key in row})
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    write_text(path, buffer.getvalue())


def _query_specs() -> list[dict[str, str]]:
    prefixes = f"""PREFIX h2kg: <{H2KG}>
PREFIX kg: <{KG}>
PREFIX case: <{CASE}>
PREFIX qudt: <{QUDT}>
PREFIX prov: <{PROV}>
PREFIX rdf: <{RDF}>
PREFIX rdfs: <{RDFS}>
PREFIX dcterms: <{DCTERMS}>
"""
    specs = [
        {
            "id": "q1_tem_specimen_preparation",
            "title": "TEM specimen, preparation, and reported result",
            "purpose": "Traverse the material chain from the TEM result and specimen to each preparation process that produced an upstream material.",
            "ground_truth_basis": "TEM synthesis and specimen-preparation rows, final specimen field, and analysis target in the sanitized workbook manifest.",
            "query": prefixes + f"""
SELECT DISTINCT ?resultLabel ?specimenLabel ?preparationLabel ?preparedMaterialLabel
WHERE {{
  GRAPH <{GRAPH['semantic/tem']}> {{
    ?result a h2kg:DataPoint ; h2kg:fromMeasurement ?measurement ; rdfs:label ?resultLabel ; h2kg:ofProperty ?property .
    ?measurement h2kg:hasMeasurementSubject ?specimen .
    ?specimen rdfs:label ?specimenLabel .
    ?property h2kg:isCharacteristicOf ?specimen .
    ?preparation a h2kg:Manufacturing ; kg:case case:tem ; rdfs:label ?preparationLabel ; h2kg:hasOutputMaterial ?preparedMaterial .
    ?preparedMaterial rdfs:label ?preparedMaterialLabel .
    ?preparedMaterial (^h2kg:hasInputMaterial/h2kg:hasOutputMaterial)* ?specimen .
  }}
}}
ORDER BY ?preparationLabel ?preparedMaterialLabel
""",
        },
        {
            "id": "q2_tem_instrument_settings",
            "title": "TEM instrument and acquisition settings",
            "purpose": "Retrieve parameter records, values, units, and explicit missing or unconfirmed states.",
            "ground_truth_basis": "TEM characterization and instrument fields, including raw values, source cells, and declared units.",
            "query": prefixes + f"""
SELECT ?instrumentLabel ?parameterLabel ?statusLabel ?sourceCell ?rawValue ?value ?unit
WHERE {{
  GRAPH <{GRAPH['semantic/tem']}> {{
    ?measurement a h2kg:TransmissionElectronMicroscopyImaging ; h2kg:usesInstrument ?instrument ; h2kg:hasParameter ?parameter .
    ?instrument rdfs:label ?instrumentLabel .
    ?parameter rdfs:label ?parameterLabel ; kg:valueStatus ?status ; h2kg:ofProperty ?property ; h2kg:hasMetadata ?source .
    OPTIONAL {{ ?property h2kg:hasQuantityValue ?qv . ?qv qudt:numericValue ?value ; qudt:unit ?unit . }}
    BIND(REPLACE(STR(?status), "^.*[#/]", "") AS ?statusLabel)
  }}
  GRAPH <{GRAPH['source/tem']}> {{
    ?source kg:sourceCell ?sourceCell .
    OPTIONAL {{ ?source rdf:value ?rawValue . }}
  }}
}}
ORDER BY ?parameterLabel
""",
        },
        {
            "id": "q3_tem_dataset_analysis",
            "title": "TEM data and analysis provenance",
            "purpose": "Retrieve the dataset, software, and analysis process that produced each TEM result.",
            "ground_truth_basis": "TEM analysis rows: precursor dataset, technique, software, and target output.",
            "query": prefixes + f"""
SELECT ?inputDataLabel ?analysisLabel ?softwareLabel ?resultLabel
WHERE {{
  GRAPH <{GRAPH['semantic/tem']}> {{
    ?result a h2kg:DataPoint ; rdfs:label ?resultLabel ; prov:wasGeneratedBy ?analysis .
    ?analysis rdfs:label ?analysisLabel ; h2kg:hasInputData ?inputData .
    ?inputData rdfs:label ?inputDataLabel .
    OPTIONAL {{ ?analysis h2kg:usesSoftware ?software . ?software rdfs:label ?softwareLabel . }}
  }}
}}
ORDER BY ?resultLabel
""",
        },
        {
            "id": "q4_tem_result_value",
            "title": "TEM result, value, unit, and bearer",
            "purpose": "Retrieve the reported TEM result with its workbook lexical value, normalized QUDT value, property, and specimen bearer.",
            "ground_truth_basis": "TEM analysis target and amount fields plus the final specimen field.",
            "query": prefixes + f"""
SELECT ?resultLabel ?propertyLabel ?bearerLabel ?sourceCell ?rawValue ?value ?unit
WHERE {{
  GRAPH <{GRAPH['semantic/tem']}> {{
    ?result a h2kg:DataPoint ; rdfs:label ?resultLabel ; h2kg:ofProperty ?property .
    ?property rdfs:label ?propertyLabel ; h2kg:isCharacteristicOf ?bearer ; h2kg:hasMetadata ?source .
    ?bearer rdfs:label ?bearerLabel .
    OPTIONAL {{ ?property h2kg:hasQuantityValue ?qv . ?qv qudt:numericValue ?value ; qudt:unit ?unit . }}
  }}
  GRAPH <{GRAPH['source/tem']}> {{
    ?source kg:fieldName "AmountTarget" ; kg:sourceCell ?sourceCell .
    OPTIONAL {{ ?source rdf:value ?rawValue . }}
  }}
}}
ORDER BY ?resultLabel
""",
        },
        {
            "id": "q5_all_measurement_contexts",
            "title": "Measurement subjects, instruments, and raw datasets",
            "purpose": "Retrieve the core measurement context for every workbook-backed case.",
            "ground_truth_basis": "The eight case definitions, final specimen fields, and method-specific measurement and instrument assignments.",
            "query": prefixes + """
SELECT ?caseKey ?measurementLabel ?specimenLabel ?instrumentLabel ?rawDatasetLabel
WHERE {
  GRAPH ?semanticGraph {
    ?case a kg:CharacterizationCase ; dcterms:identifier ?caseKey .
    ?measurement a h2kg:Measurement ; kg:case ?case ; rdfs:label ?measurementLabel ;
      h2kg:hasMeasurementSubject ?specimen ; h2kg:usesInstrument ?instrument ; h2kg:hasOutputData ?rawDataset .
    ?specimen rdfs:label ?specimenLabel .
    ?instrument rdfs:label ?instrumentLabel .
    ?rawDataset rdfs:label ?rawDatasetLabel .
  }
  FILTER(STRSTARTS(STR(?semanticGraph), "https://w3id.org/h2kg/examples/characterization/graph/semantic/"))
}
ORDER BY ?caseKey
""",
        },
        {
            "id": "q6_all_result_records",
            "title": "Result properties, values, units, and bearers",
            "purpose": "Retrieve every analysis output across all eight cases while retaining raw workbook values beside defensible QUDT normalization.",
            "ground_truth_basis": "All 24 workbook analysis rows, their AmountTarget cells, and each case's final specimen field.",
            "query": prefixes + """
SELECT ?caseKey ?resultLabel ?propertyLabel ?bearerLabel ?sourceCell ?rawValue ?value ?unit
WHERE {
  GRAPH ?semanticGraph {
    ?case a kg:CharacterizationCase ; dcterms:identifier ?caseKey .
    ?result a h2kg:DataPoint ; rdfs:label ?resultLabel ; h2kg:ofProperty ?property ; kg:case ?case .
    ?property rdfs:label ?propertyLabel ; h2kg:isCharacteristicOf ?bearer ; h2kg:hasMetadata ?source .
    ?bearer rdfs:label ?bearerLabel .
    OPTIONAL { ?property h2kg:hasQuantityValue ?qv . ?qv qudt:numericValue ?value ; qudt:unit ?unit . }
  }
  GRAPH ?sourceGraph {
    ?source kg:fieldName "AmountTarget" ; kg:sourceCell ?sourceCell .
    OPTIONAL { ?source rdf:value ?rawValue . }
  }
  FILTER(STRSTARTS(STR(?semanticGraph), "https://w3id.org/h2kg/examples/characterization/graph/semantic/"))
  FILTER(STRSTARTS(STR(?sourceGraph), "https://w3id.org/h2kg/examples/characterization/graph/source/"))
}
ORDER BY ?caseKey ?resultLabel
""",
        },
        {
            "id": "q7_source_status_summary",
            "title": "Workbook field-status summary",
            "purpose": "Count reported, missing, inapplicable, unspecified, unconfirmed, unresolved-formula, and conflicting fields by case.",
            "ground_truth_basis": "The explicit status assigned to every eligible field in the sanitized workbook manifest.",
            "query": prefixes + """
SELECT ?caseKey ?statusLabel (COUNT(?source) AS ?fieldCount)
WHERE {
  GRAPH ?sourceGraph { ?source a kg:SourceField ; kg:valueStatus ?status . }
  FILTER(STRSTARTS(STR(?sourceGraph), "https://w3id.org/h2kg/examples/characterization/graph/source/"))
  BIND(STRAFTER(STR(?sourceGraph), "https://w3id.org/h2kg/examples/characterization/graph/source/") AS ?caseKey)
  BIND(REPLACE(STR(?status), "^.*[#/]", "") AS ?statusLabel)
}
GROUP BY ?caseKey ?statusLabel
ORDER BY ?caseKey ?statusLabel
""",
        },
        {
            "id": "q8_all_measurement_parameters",
            "title": "Measurement settings with source and QUDT values",
            "purpose": "Retrieve all direct measurement-setting records across the eight cases with source cells, raw values, statuses, and normalized quantities where justified.",
            "ground_truth_basis": "Characterization and instrument fields recognized as scientific settings, together with their declared units.",
            "query": prefixes + """
SELECT ?caseKey ?parameterLabel ?statusLabel ?sourceCell ?rawValue ?value ?unit
WHERE {
  GRAPH ?semanticGraph {
    ?case a kg:CharacterizationCase ; dcterms:identifier ?caseKey .
    ?measurement a h2kg:Measurement ; kg:case ?case ; h2kg:hasParameter ?parameter .
    ?parameter rdfs:label ?parameterLabel ; kg:valueStatus ?status ; h2kg:ofProperty ?property ; h2kg:hasMetadata ?source .
    OPTIONAL { ?property h2kg:hasQuantityValue ?qv . ?qv qudt:numericValue ?value ; qudt:unit ?unit . }
    BIND(REPLACE(STR(?status), "^.*[#/]", "") AS ?statusLabel)
  }
  GRAPH ?sourceGraph {
    ?source kg:sourceCell ?sourceCell .
    OPTIONAL { ?source rdf:value ?rawValue . }
  }
  FILTER(STRSTARTS(STR(?semanticGraph), "https://w3id.org/h2kg/examples/characterization/graph/semantic/"))
  FILTER(STRSTARTS(STR(?sourceGraph), "https://w3id.org/h2kg/examples/characterization/graph/source/"))
}
ORDER BY ?caseKey ?parameterLabel ?sourceCell
""",
        },
        {
            "id": "q9_conservative_quantity_findings",
            "title": "Conflicting or semantically incomplete result quantities",
            "purpose": "Retrieve result values deliberately retained as source evidence without unsupported QUDT assertions.",
            "ground_truth_basis": "Analysis outputs whose label, unit, metric, axis, or ratio basis is insufficient for defensible normalization.",
            "query": prefixes + """
SELECT ?caseKey ?propertyLabel ?code ?sourceCell ?rawValue
WHERE {
  GRAPH ?validationGraph {
    ?finding a kg:ValidationFinding ; kg:case ?case ; kg:findingCode ?code ;
      dcterms:subject ?property ; prov:wasDerivedFrom ?source .
  }
  GRAPH ?semanticGraph {
    ?case dcterms:identifier ?caseKey .
    ?property rdfs:label ?propertyLabel .
  }
  GRAPH ?sourceGraph {
    ?source kg:sourceCell ?sourceCell .
    OPTIONAL { ?source rdf:value ?rawValue . }
  }
  FILTER(?code IN ("label_unit_conflict", "incomplete_semantics", "unresolved_metric", "unit_unresolved", "ordered_ratio_basis_unspecified", "quantity-incomplete"))
}
ORDER BY ?caseKey ?propertyLabel ?sourceCell
""",
        },
        {
            "id": "q10_source_provenance_coverage",
            "title": "Source-to-semantic provenance coverage",
            "purpose": "Verify that every eligible workbook source field is represented and linked to at least one semantic entity.",
            "ground_truth_basis": "Per-case eligible-field totals in the sanitized workbook manifest.",
            "query": prefixes + """
SELECT ?caseKey (COUNT(DISTINCT ?source) AS ?sourceFieldCount) (COUNT(DISTINCT ?mappedSource) AS ?mappedFieldCount)
WHERE {
  GRAPH ?sourceGraph { ?source a kg:SourceField . }
  FILTER(STRSTARTS(STR(?sourceGraph), "https://w3id.org/h2kg/examples/characterization/graph/source/"))
  BIND(STRAFTER(STR(?sourceGraph), "https://w3id.org/h2kg/examples/characterization/graph/source/") AS ?caseKey)
  OPTIONAL {
    GRAPH ?semanticGraph { ?source kg:mappedEntity ?entity . }
    BIND(?source AS ?mappedSource)
  }
}
GROUP BY ?caseKey
ORDER BY ?caseKey
""",
        },
        {
            "id": "q11_software_provenance",
            "title": "Software used in processing and analysis",
            "purpose": "Retrieve source-reported software linked to processing and analysis activities across all cases.",
            "ground_truth_basis": "Non-empty Software cells in preprocessing and analysis rows, parsed without inventing software names.",
            "query": prefixes + """
SELECT DISTINCT ?caseKey ?processLabel ?softwareLabel
WHERE {
  GRAPH ?semanticGraph {
    ?case a kg:CharacterizationCase ; dcterms:identifier ?caseKey .
    ?process a h2kg:Process ; kg:case ?case ; rdfs:label ?processLabel ; h2kg:usesSoftware ?software .
    ?software rdfs:label ?softwareLabel .
  }
  FILTER(STRSTARTS(STR(?semanticGraph), "https://w3id.org/h2kg/examples/characterization/graph/semantic/"))
}
ORDER BY ?caseKey ?processLabel ?softwareLabel
""",
        },
        {
            "id": "q12_neutron_processing_chain",
            "title": "Neutron-tomography preprocessing chain",
            "purpose": "Retrieve the ordered source-described data transformations from raw projections to the processed tomograph.",
            "ground_truth_basis": "The four neutron-tomography preprocessing rows and their precursor, technique, and target fields.",
            "query": prefixes + f"""
SELECT ?processLabel ?inputDataLabel ?outputDataLabel
WHERE {{
  GRAPH <{GRAPH['semantic/neutron_tomography']}> {{
    ?process a h2kg:DataProcessing ; rdfs:label ?processLabel ;
      h2kg:hasInputData ?inputData ; h2kg:hasOutputData ?outputData .
    ?inputData rdfs:label ?inputDataLabel .
    ?outputData rdfs:label ?outputDataLabel .
  }}
}}
ORDER BY ?processLabel ?inputDataLabel ?outputDataLabel
""",
        },
    ]

    core_metadata = {
        "q1_tem_specimen_preparation": (
            "TEM traceability",
            "Which specimen-preparation steps produced the TEM specimen associated with the reported particle-size result?",
        ),
        "q2_tem_instrument_settings": (
            "TEM acquisition",
            "Which TEM instrument and acquisition settings were recorded, including values that were unconfirmed or not applicable?",
        ),
        "q3_tem_dataset_analysis": (
            "TEM provenance",
            "Which image dataset, analysis process, and software produced the reported TEM result?",
        ),
        "q4_tem_result_value": (
            "TEM result",
            "What TEM property was reported, for which specimen, and with what source value and normalized unit?",
        ),
        "q5_all_measurement_contexts": (
            "Cross-case measurement context",
            "What specimen, instrument, and raw dataset are linked to each characterization measurement?",
        ),
        "q6_all_result_records": (
            "Cross-case results",
            "Which properties were reported across all cases, and what values, units, and specimen bearers were recorded?",
        ),
        "q7_source_status_summary": (
            "Source completeness",
            "How many workbook fields in each case were reported, missing, not applicable, unspecified, unconfirmed, unresolved, or conflicting?",
        ),
        "q8_all_measurement_parameters": (
            "Cross-case acquisition settings",
            "Which measurement settings were recorded across all cases, and which have normalized QUDT values and units?",
        ),
        "q9_conservative_quantity_findings": (
            "Semantic quality findings",
            "Which reported quantities were deliberately not normalized because their units, labels, axes, or meanings were incomplete or conflicting?",
        ),
        "q10_source_provenance_coverage": (
            "Source provenance",
            "Does every eligible workbook field have a traceable semantic representation in each case graph?",
        ),
        "q11_software_provenance": (
            "Software provenance",
            "Which software packages were linked to processing and analysis activities in each case?",
        ),
        "q12_neutron_processing_chain": (
            "Neutron-tomography processing",
            "Which ordered preprocessing transformations connect the neutron-tomography raw projections to processed data?",
        ),
    }
    for spec in specs:
        spec["category"], spec["question"] = core_metadata[spec["id"]]

    case_specs = list(CASE_SPECS)
    for offset, case_spec in enumerate(case_specs, start=13):
        semantic_graph = GRAPH[f"semantic/{case_spec.key}"]
        specs.append({
            "id": f"q{offset}_{case_spec.key}_measurement_context",
            "category": "Method-specific measurement context",
            "title": f"{case_spec.title} measurement context",
            "question": f"What specimen, instrument, and raw dataset define the {case_spec.title} measurement?",
            "purpose": "Retrieve the core subject, instrument, and raw-data context for one method-specific case.",
            "ground_truth_basis": f"The {case_spec.sheet} final-specimen field and its measurement, instrument, and raw-dataset assignments.",
            "query": prefixes + f"""
SELECT ?measurementLabel ?specimenLabel ?instrumentLabel ?rawDatasetLabel
WHERE {{
  GRAPH <{semantic_graph}> {{
    ?measurement a h2kg:Measurement ; rdfs:label ?measurementLabel ;
      h2kg:hasMeasurementSubject ?specimen ; h2kg:usesInstrument ?instrument ; h2kg:hasOutputData ?rawDataset .
    ?specimen rdfs:label ?specimenLabel .
    ?instrument rdfs:label ?instrumentLabel .
    ?rawDataset rdfs:label ?rawDatasetLabel .
  }}
}}
ORDER BY ?measurementLabel
""",
        })

    for offset, case_spec in enumerate(case_specs, start=21):
        semantic_graph = GRAPH[f"semantic/{case_spec.key}"]
        source_graph = GRAPH[f"source/{case_spec.key}"]
        specs.append({
            "id": f"q{offset}_{case_spec.key}_results",
            "category": "Method-specific results",
            "title": f"{case_spec.title} result records",
            "question": f"Which results were reported for {case_spec.title}, and what values, units, and specimen bearers were recorded?",
            "purpose": "Retrieve every result for one case with its property, bearer, raw source value, and defensible normalized quantity.",
            "ground_truth_basis": f"All analysis target and AmountTarget fields in the {case_spec.sheet} case plus its final-specimen field.",
            "query": prefixes + f"""
SELECT ?resultLabel ?propertyLabel ?bearerLabel ?sourceCell ?rawValue ?value ?unit
WHERE {{
  GRAPH <{semantic_graph}> {{
    ?result a h2kg:DataPoint ; rdfs:label ?resultLabel ; h2kg:ofProperty ?property .
    ?property rdfs:label ?propertyLabel ; h2kg:isCharacteristicOf ?bearer ; h2kg:hasMetadata ?source .
    ?bearer rdfs:label ?bearerLabel .
    OPTIONAL {{ ?property h2kg:hasQuantityValue ?qv . ?qv qudt:numericValue ?value ; qudt:unit ?unit . }}
  }}
  GRAPH <{source_graph}> {{
    ?source kg:fieldName "AmountTarget" ; kg:sourceCell ?sourceCell .
    OPTIONAL {{ ?source rdf:value ?rawValue . }}
  }}
}}
ORDER BY ?resultLabel
""",
        })

    for offset, case_spec in enumerate(case_specs, start=29):
        source_graph = GRAPH[f"source/{case_spec.key}"]
        specs.append({
            "id": f"q{offset}_{case_spec.key}_source_status",
            "category": "Method-specific source completeness",
            "title": f"{case_spec.title} source-status summary",
            "question": f"How many {case_spec.title} source fields were reported, missing, not applicable, unspecified, unconfirmed, unresolved, or conflicting?",
            "purpose": "Summarize every explicit source-value status for one workbook case.",
            "ground_truth_basis": f"The status assigned to every eligible field in the sanitized {case_spec.sheet} manifest record.",
            "query": prefixes + f"""
SELECT ?statusLabel (COUNT(?source) AS ?fieldCount)
WHERE {{
  GRAPH <{source_graph}> {{ ?source a kg:SourceField ; kg:valueStatus ?status . }}
  BIND(REPLACE(STR(?status), "^.*[#/]", "") AS ?statusLabel)
}}
GROUP BY ?statusLabel
ORDER BY ?statusLabel
""",
        })

    for offset, case_spec in enumerate(case_specs, start=37):
        semantic_graph = GRAPH[f"semantic/{case_spec.key}"]
        source_graph = GRAPH[f"source/{case_spec.key}"]
        specs.append({
            "id": f"q{offset}_{case_spec.key}_measurement_settings",
            "category": "Method-specific acquisition settings",
            "title": f"{case_spec.title} measurement settings",
            "question": f"Which acquisition settings were recorded for {case_spec.title}, and which have normalized values and units?",
            "purpose": "Retrieve all direct measurement-setting records for one case, including qualified source states.",
            "ground_truth_basis": f"Characterization and instrument fields recognized as settings in the {case_spec.sheet} manifest record.",
            "query": prefixes + f"""
SELECT ?parameterLabel ?statusLabel ?sourceCell ?rawValue ?value ?unit
WHERE {{
  GRAPH <{semantic_graph}> {{
    ?measurement a h2kg:Measurement ; h2kg:hasParameter ?parameter .
    ?parameter rdfs:label ?parameterLabel ; kg:valueStatus ?status ; h2kg:ofProperty ?property ; h2kg:hasMetadata ?source .
    OPTIONAL {{ ?property h2kg:hasQuantityValue ?qv . ?qv qudt:numericValue ?value ; qudt:unit ?unit . }}
    BIND(REPLACE(STR(?status), "^.*[#/]", "") AS ?statusLabel)
  }}
  GRAPH <{source_graph}> {{
    ?source kg:sourceCell ?sourceCell .
    OPTIONAL {{ ?source rdf:value ?rawValue . }}
  }}
}}
ORDER BY ?parameterLabel ?sourceCell
""",
        })

    specs.extend([
        {
            "id": "q45_case_measurement_result_counts",
            "category": "Cross-case integrity",
            "title": "Measurement and result counts by case",
            "question": "How many measurement occurrences and result records are represented for each characterization case?",
            "purpose": "Count distinct measurements and DataPoint results per case without conflating the two occurrence types.",
            "ground_truth_basis": "One modeled measurement per case and the number of workbook analysis-output rows in each sanitized case record.",
            "query": prefixes + """
SELECT ?caseKey (COUNT(DISTINCT ?measurement) AS ?measurementCount) (COUNT(DISTINCT ?result) AS ?resultCount)
WHERE {
  GRAPH ?semanticGraph {
    ?case a kg:CharacterizationCase ; dcterms:identifier ?caseKey .
    ?measurement a h2kg:Measurement ; kg:case ?case .
    OPTIONAL { ?result a h2kg:DataPoint ; kg:case ?case . }
  }
  FILTER(STRSTARTS(STR(?semanticGraph), "https://w3id.org/h2kg/examples/characterization/graph/semantic/"))
}
GROUP BY ?caseKey
ORDER BY ?caseKey
""",
        },
        {
            "id": "q46_normalized_result_quantities",
            "category": "Cross-case quantity validation",
            "title": "Normalized result quantities",
            "question": "Which reported scientific results have both a defensible numeric value and an explicit QUDT unit?",
            "purpose": "Return only result properties for which the graph asserts a complete normalized quantity-value pattern.",
            "ground_truth_basis": "Analysis outputs whose AmountTarget values parse to compatible numeric values, units, and quantity kinds without a semantic conflict.",
            "query": prefixes + """
SELECT ?caseKey ?propertyLabel ?sourceCell ?rawValue ?value ?unit
WHERE {
  GRAPH ?semanticGraph {
    ?case a kg:CharacterizationCase ; dcterms:identifier ?caseKey .
    ?result a h2kg:DataPoint ; h2kg:ofProperty ?property ; kg:case ?case .
    ?property rdfs:label ?propertyLabel ; h2kg:hasMetadata ?source ; h2kg:hasQuantityValue ?qv .
    ?qv qudt:numericValue ?value ; qudt:unit ?unit .
  }
  GRAPH ?sourceGraph {
    ?source kg:fieldName "AmountTarget" ; kg:sourceCell ?sourceCell .
    OPTIONAL { ?source rdf:value ?rawValue . }
  }
  FILTER(STRSTARTS(STR(?semanticGraph), "https://w3id.org/h2kg/examples/characterization/graph/semantic/"))
  FILTER(STRSTARTS(STR(?sourceGraph), "https://w3id.org/h2kg/examples/characterization/graph/source/"))
}
ORDER BY ?caseKey ?propertyLabel
""",
        },
        {
            "id": "q47_qualified_source_fields",
            "category": "Cross-case source completeness",
            "title": "Qualified and missing source fields",
            "question": "Which workbook fields are not simply reported values, and why are they marked missing, inapplicable, unspecified, unconfirmed, unresolved, or conflicting?",
            "purpose": "Retrieve every source field whose explicit status is not reported, preserving its cell and raw lexical value.",
            "ground_truth_basis": "All sanitized source records with a status other than reported.",
            "query": prefixes + """
SELECT ?caseKey ?fieldName ?sourceCell ?statusLabel ?rawValue
WHERE {
  GRAPH ?sourceGraph {
    ?source a kg:SourceField ; kg:fieldName ?fieldName ; kg:sourceCell ?sourceCell ; kg:valueStatus ?status .
    OPTIONAL { ?source rdf:value ?rawValue . }
  }
  FILTER(STRSTARTS(STR(?sourceGraph), "https://w3id.org/h2kg/examples/characterization/graph/source/"))
  FILTER(?status != kg:reported)
  BIND(STRAFTER(STR(?sourceGraph), "https://w3id.org/h2kg/examples/characterization/graph/source/") AS ?caseKey)
  BIND(REPLACE(STR(?status), "^.*[#/]", "") AS ?statusLabel)
}
ORDER BY ?caseKey ?sourceCell
""",
        },
        {
            "id": "q48_qualified_measurement_settings",
            "category": "Cross-case acquisition settings",
            "title": "Qualified measurement-setting records",
            "question": "Which acquisition settings are missing, not applicable, unspecified, unconfirmed, unresolved, or conflicting rather than fully reported?",
            "purpose": "Retrieve measurement-setting records with a non-reported source status.",
            "ground_truth_basis": "Recognized characterization and instrument settings whose sanitized source status is not reported.",
            "query": prefixes + """
SELECT ?caseKey ?parameterLabel ?statusLabel ?sourceCell ?rawValue
WHERE {
  GRAPH ?semanticGraph {
    ?case a kg:CharacterizationCase ; dcterms:identifier ?caseKey .
    ?measurement a h2kg:Measurement ; kg:case ?case ; h2kg:hasParameter ?parameter .
    ?parameter rdfs:label ?parameterLabel ; kg:valueStatus ?status ; h2kg:hasMetadata ?source .
    FILTER(?status != kg:reported)
    BIND(REPLACE(STR(?status), "^.*[#/]", "") AS ?statusLabel)
  }
  GRAPH ?sourceGraph {
    ?source kg:sourceCell ?sourceCell .
    OPTIONAL { ?source rdf:value ?rawValue . }
  }
  FILTER(STRSTARTS(STR(?semanticGraph), "https://w3id.org/h2kg/examples/characterization/graph/semantic/"))
  FILTER(STRSTARTS(STR(?sourceGraph), "https://w3id.org/h2kg/examples/characterization/graph/source/"))
}
ORDER BY ?caseKey ?parameterLabel ?sourceCell
""",
        },
        {
            "id": "q49_analysis_provenance_across_cases",
            "category": "Cross-case analysis provenance",
            "title": "Analysis provenance across all cases",
            "question": "Which input datasets, analysis processes, and software are linked to each reported result across all cases?",
            "purpose": "Traverse each DataPoint to its generating analysis process, input data, and source-reported software.",
            "ground_truth_basis": "All analysis rows grouped by their source step and technique, including their precursor, target, and software fields.",
            "query": prefixes + """
SELECT DISTINCT ?caseKey ?analysisLabel ?inputDataLabel ?resultLabel ?softwareLabel
WHERE {
  GRAPH ?semanticGraph {
    ?case a kg:CharacterizationCase ; dcterms:identifier ?caseKey .
    ?result a h2kg:DataPoint ; rdfs:label ?resultLabel ; kg:case ?case ; prov:wasGeneratedBy ?analysis .
    ?analysis a h2kg:Process ; rdfs:label ?analysisLabel ; h2kg:hasInputData ?inputData .
    ?inputData rdfs:label ?inputDataLabel .
    OPTIONAL { ?analysis h2kg:usesSoftware ?software . ?software rdfs:label ?softwareLabel . }
  }
  FILTER(STRSTARTS(STR(?semanticGraph), "https://w3id.org/h2kg/examples/characterization/graph/semantic/"))
}
ORDER BY ?caseKey ?analysisLabel ?resultLabel ?inputDataLabel ?softwareLabel
""",
        },
        {
            "id": "q50_preprocessing_transformations",
            "category": "Cross-case processing provenance",
            "title": "Preprocessing transformations across all cases",
            "question": "Which preprocessing activities transformed which input datasets into which output datasets across the eight cases?",
            "purpose": "Retrieve source-described input-to-process-to-output transformations for all preprocessing stages.",
            "ground_truth_basis": "All preprocessing rows grouped by their source step and technique, with precursor and target fields retained.",
            "query": prefixes + """
SELECT DISTINCT ?caseKey ?processLabel ?inputDataLabel ?outputDataLabel
WHERE {
  GRAPH ?semanticGraph {
    ?case a kg:CharacterizationCase ; dcterms:identifier ?caseKey .
    ?process a h2kg:DataProcessing ; kg:case ?case ; rdfs:label ?processLabel ;
      h2kg:hasInputData ?inputData ; h2kg:hasOutputData ?outputData .
    ?inputData rdfs:label ?inputDataLabel .
    ?outputData rdfs:label ?outputDataLabel .
  }
  FILTER(STRSTARTS(STR(?semanticGraph), "https://w3id.org/h2kg/examples/characterization/graph/semantic/"))
}
ORDER BY ?caseKey ?processLabel ?inputDataLabel ?outputDataLabel
""",
        },
    ])
    if len(specs) != 50:
        raise AssertionError(f"Expected 50 characterization competency queries, found {len(specs)}")
    return specs


def _manifest_case(manifest: dict[str, Any], case_key: str) -> dict[str, Any]:
    return next(case for case in manifest["cases"] if case["key"] == case_key)


def _record_map(case: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {record["record_id"]: record for record in case["source_records"]}


def _direct_record(case: dict[str, Any], field_key: str) -> dict[str, Any] | None:
    return next((record for record in case["direct_fields"] if _field_key(record["field"]) == field_key), None)


def _raw_lexical(value: Any) -> str:
    return "" if value is None else str(_literal_raw(value))


def _quantity_columns(raw: Any, label: str, unit: Any = None, *, asserted: bool = True) -> tuple[str, str]:
    quantity = _with_implicit_quantity_kind(_parse_quantity(raw, unit), label)
    if not asserted or not quantity or quantity.get("unit") is None or quantity.get("quantity_kind") is None:
        return "", ""
    return str(Literal(quantity["numeric"], datatype=XSD.decimal)), str(quantity["unit"])


def _expected_result_rows(case: dict[str, Any]) -> list[dict[str, str]]:
    records = _record_map(case)
    specimen_record = _direct_record(case, "specimen")
    specimen_label = str((specimen_record or {}).get("raw_value") or "Characterization specimen")
    rows: list[dict[str, str]] = []
    for row in case["table_rows"]:
        if row["section"] != "anal":
            continue
        target = str(row["values"].get("Target") or "Unspecified result")
        amount = row["values"].get("AmountTarget")
        amount_record = records[row["record_ids"]["AmountTarget"]]
        conflict = _semantic_conflict(case["key"], target, amount)
        value, unit = _quantity_columns(amount, target, asserted=not conflict)
        rows.append({
            "caseKey": case["key"],
            "resultLabel": f"{target} result",
            "propertyLabel": target,
            "bearerLabel": specimen_label,
            "sourceCell": amount_record["cell"],
            "rawValue": _raw_lexical(amount_record.get("raw_value")),
            "value": value,
            "unit": unit,
        })
    return rows


def _expected_parameter_rows(case: dict[str, Any]) -> list[dict[str, str]]:
    units = _paired_direct_units(case)
    rows: list[dict[str, str]] = []
    for record in case["direct_fields"]:
        key = _field_key(record["field"])
        if record["section"] not in {"char", "inst"} or key not in PROPERTY_FIELDS or key.endswith("unit"):
            continue
        value, unit = _quantity_columns(
            record.get("raw_value"),
            record["field"],
            units.get(key),
            asserted=record["status"] == "reported",
        )
        rows.append({
            "caseKey": case["key"],
            "instrumentLabel": f"{case['title']} instrument",
            "parameterLabel": f"{record['field']} parameter record",
            "statusLabel": record["status"],
            "sourceCell": record["cell"],
            "rawValue": _raw_lexical(record.get("raw_value")),
            "value": value,
            "unit": unit,
        })
    return rows


def _expected_measurement_context(case: dict[str, Any]) -> dict[str, str]:
    specimen_record = _direct_record(case, "specimen")
    return {
        "caseKey": case["key"],
        "measurementLabel": f"{case['title']} measurement",
        "specimenLabel": str((specimen_record or {}).get("raw_value") or "Characterization specimen"),
        "instrumentLabel": f"{case['title']} instrument",
        "rawDatasetLabel": "RawData",
    }


def _expected_status_rows(case: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"caseKey": case["key"], "statusLabel": status, "fieldCount": str(count)}
        for status, count in sorted(Counter(record["status"] for record in case["source_records"]).items())
    ]


def _source_data_label(value: Any) -> str:
    return "RawData" if _norm_label(value) in {"rawdata", "raw data"} else str(value or "unspecified input data")


def _expected_analysis_provenance_rows(case: dict[str, Any]) -> list[dict[str, str]]:
    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in case["table_rows"]:
        if row["section"] != "anal":
            continue
        values = row["values"]
        stage = ("anal", str(values.get("Step") or "").strip(), str(values.get("Technique") or "").strip())
        key: tuple[Any, ...] = stage if stage[1] and stage[2] else (*stage, row["row"])
        item = grouped.setdefault(key, {
            "label": str(values.get("Technique") or f"anal step {values.get('Step', row['row'])}"),
            "inputs": set(),
            "results": set(),
            "software": set(),
        })
        item["inputs"].add(_source_data_label(values.get("Precursor")))
        item["results"].add(f"{values.get('Target') or 'Unspecified result'} result")
        item["software"].update(_split_software(values.get("Software")))
    rows: list[dict[str, str]] = []
    for item in grouped.values():
        software_values = sorted(item["software"]) or [""]
        for input_label in sorted(item["inputs"]):
            for result_label in sorted(item["results"]):
                for software_label in software_values:
                    rows.append({
                        "caseKey": case["key"],
                        "analysisLabel": item["label"],
                        "inputDataLabel": input_label,
                        "resultLabel": result_label,
                        "softwareLabel": software_label,
                    })
    return rows


def _expected_preprocessing_rows(case: dict[str, Any]) -> list[dict[str, str]]:
    stage_targets: dict[tuple[str, str, str], set[str]] = {}
    for candidate in case["table_rows"]:
        values = candidate["values"]
        stage = (
            candidate["section"],
            str(values.get("Step") or "").strip(),
            str(values.get("Technique") or "").strip(),
        )
        stage_targets.setdefault(stage, set()).add(_norm_label(values.get("Target")))
    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in case["table_rows"]:
        if row["section"] != "pre":
            continue
        values = row["values"]
        stage = ("pre", str(values.get("Step") or "").strip(), str(values.get("Technique") or "").strip())
        can_group = bool(stage[1] and stage[2]) and len(stage_targets[stage]) == 1
        key: tuple[Any, ...] = stage if can_group else (*stage, row["row"])
        item = grouped.setdefault(key, {
            "label": str(values.get("Technique") or f"pre step {values.get('Step', row['row'])}"),
            "inputs": set(),
            "outputs": set(),
        })
        item["inputs"].add(_source_data_label(values.get("Precursor")))
        item["outputs"].add(str(values.get("Target") or "Unspecified source entity"))
    rows: list[dict[str, str]] = []
    for item in grouped.values():
        for input_label in sorted(item["inputs"]):
            for output_label in sorted(item["outputs"]):
                rows.append({
                    "caseKey": case["key"],
                    "processLabel": item["label"],
                    "inputDataLabel": input_label,
                    "outputDataLabel": output_label,
                })
    return rows


def _case_for_number(query_number: int, start: int) -> str:
    return CASE_SPECS[query_number - start].key


def _expected_tem_preparation_rows(manifest: dict[str, Any]) -> list[dict[str, str]]:
    case = _manifest_case(manifest, "tem")
    specimen_record = _direct_record(case, "specimen")
    specimen_label = str((specimen_record or {}).get("raw_value") or "Characterization specimen")
    stage_targets: dict[tuple[str, str, str], set[str]] = {}
    for row in case["table_rows"]:
        values = row["values"]
        stage = (row["section"], str(values.get("Step") or "").strip(), str(values.get("Technique") or "").strip())
        stage_targets.setdefault(stage, set()).add(_norm_label(values.get("Target")))
    processes: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in case["table_rows"]:
        if row["section"] not in {"syn", "sp"}:
            continue
        values = row["values"]
        stage = (row["section"], str(values.get("Step") or "").strip(), str(values.get("Technique") or "").strip())
        can_group = bool(stage[1] and stage[2]) and len(stage_targets[stage]) == 1
        key: tuple[Any, ...] = stage if can_group else (*stage, row["row"])
        target = values.get("Target")
        output_key = "__specimen__" if _norm_label(target) == "sample" else _norm_label(target)
        item = processes.setdefault(key, {
            "label": str(values.get("Technique") or f"{row['section']} step {values.get('Step', row['row'])}"),
            "inputs": set(),
            "output": output_key,
            "output_label": specimen_label if output_key == "__specimen__" else str(target or "Unspecified source entity"),
        })
        if values.get("Precursor"):
            item["inputs"].add(_norm_label(values["Precursor"]))
    reachable = {"__specimen__"}
    selected: set[tuple[Any, ...]] = set()
    changed = True
    while changed:
        changed = False
        for key, process in processes.items():
            if process["output"] in reachable and key not in selected:
                selected.add(key)
                reachable.update(process["inputs"])
                changed = True
    result_rows = _expected_result_rows(case)
    rows: list[dict[str, str]] = []
    for result in result_rows:
        for key in selected:
            process = processes[key]
            rows.append({
                "resultLabel": result["resultLabel"],
                "specimenLabel": specimen_label,
                "preparationLabel": process["label"],
                "preparedMaterialLabel": process["output_label"],
            })
    return rows


def _ground_truth_rows(query_id: str, manifest: dict[str, Any]) -> list[dict[str, str]]:
    cases = manifest["cases"]
    query_number = int(re.match(r"q(\d+)_", query_id).group(1))
    if 13 <= query_number <= 20:
        case = _manifest_case(manifest, _case_for_number(query_number, 13))
        return [{key: value for key, value in _expected_measurement_context(case).items() if key != "caseKey"}]
    if 21 <= query_number <= 28:
        case = _manifest_case(manifest, _case_for_number(query_number, 21))
        return [
            {key: value for key, value in row.items() if key != "caseKey"}
            for row in _expected_result_rows(case)
        ]
    if 29 <= query_number <= 36:
        case = _manifest_case(manifest, _case_for_number(query_number, 29))
        return [
            {key: value for key, value in row.items() if key != "caseKey"}
            for row in _expected_status_rows(case)
        ]
    if 37 <= query_number <= 44:
        case = _manifest_case(manifest, _case_for_number(query_number, 37))
        return [
            {key: value for key, value in row.items() if key not in {"caseKey", "instrumentLabel"}}
            for row in _expected_parameter_rows(case)
        ]
    if query_id == "q1_tem_specimen_preparation":
        return _expected_tem_preparation_rows(manifest)
    if query_id == "q2_tem_instrument_settings":
        return [
            {key: value for key, value in row.items() if key != "caseKey"}
            for row in _expected_parameter_rows(_manifest_case(manifest, "tem"))
        ]
    if query_id == "q3_tem_dataset_analysis":
        case = _manifest_case(manifest, "tem")
        rows: list[dict[str, str]] = []
        for item in case["table_rows"]:
            if item["section"] != "anal":
                continue
            software = _split_software(item["values"].get("Software")) or [""]
            for software_label in software:
                rows.append({
                    "inputDataLabel": str(item["values"].get("Precursor") or "unspecified input data"),
                    "analysisLabel": str(item["values"].get("Technique") or f"anal step {item['values'].get('Step', item['row'])}"),
                    "softwareLabel": software_label,
                    "resultLabel": f"{item['values'].get('Target') or 'Unspecified result'} result",
                })
        return rows
    if query_id == "q4_tem_result_value":
        return [
            {key: value for key, value in row.items() if key != "caseKey"}
            for row in _expected_result_rows(_manifest_case(manifest, "tem"))
        ]
    if query_id == "q5_all_measurement_contexts":
        return [_expected_measurement_context(case) for case in cases]
    if query_id == "q6_all_result_records":
        return [row for case in cases for row in _expected_result_rows(case)]
    if query_id == "q7_source_status_summary":
        return [row for case in cases for row in _expected_status_rows(case)]
    if query_id == "q8_all_measurement_parameters":
        return [
            {key: value for key, value in row.items() if key != "instrumentLabel"}
            for case in cases
            for row in _expected_parameter_rows(case)
        ]
    if query_id == "q9_conservative_quantity_findings":
        rows = []
        for case in cases:
            units = _paired_direct_units(case)
            for record in case["direct_fields"]:
                key = _field_key(record["field"])
                if record["section"] not in {"char", "inst"} or key not in PROPERTY_FIELDS or key.endswith("unit"):
                    continue
                quantity = _with_implicit_quantity_kind(_parse_quantity(record.get("raw_value"), units.get(key)), record["field"])
                if record["status"] == "reported" and quantity and (quantity.get("unit") is None or quantity.get("quantity_kind") is None):
                    rows.append({"caseKey": case["key"], "propertyLabel": record["field"], "code": "unit_unresolved", "sourceCell": record["cell"], "rawValue": _raw_lexical(record.get("raw_value"))})
            records = _record_map(case)
            for item in case["table_rows"]:
                if item["section"] != "anal":
                    continue
                target = str(item["values"].get("Target") or "Unspecified result")
                amount = item["values"].get("AmountTarget")
                source = records[item["record_ids"]["AmountTarget"]]
                conflict = _semantic_conflict(case["key"], target, amount)
                quantity = _with_implicit_quantity_kind(_parse_quantity(amount), target)
                code = conflict or ("quantity-incomplete" if amount not in (None, "") and (not quantity or quantity.get("unit") is None or quantity.get("quantity_kind") is None) else "")
                if code:
                    rows.append({"caseKey": case["key"], "propertyLabel": target, "code": code, "sourceCell": source["cell"], "rawValue": _raw_lexical(source.get("raw_value"))})
        return rows
    if query_id == "q10_source_provenance_coverage":
        return [{"caseKey": case["key"], "sourceFieldCount": str(len(case["source_records"])), "mappedFieldCount": str(len(case["source_records"]))} for case in cases]
    if query_id == "q11_software_provenance":
        distinct = {
            (case["key"], str(row["values"].get("Technique") or f"{row['section']} step {row['values'].get('Step', row['row'])}"), software)
            for case in cases
            for row in case["table_rows"]
            for software in _split_software(row["values"].get("Software"))
        }
        return [{"caseKey": case_key, "processLabel": process, "softwareLabel": software} for case_key, process, software in sorted(distinct)]
    if query_id == "q12_neutron_processing_chain":
        case = _manifest_case(manifest, "neutron_tomography")
        return [
            {
                "processLabel": str(row["values"].get("Technique") or f"pre step {row['values'].get('Step', row['row'])}"),
                "inputDataLabel": "RawData" if _norm_label(row["values"].get("Precursor")) in {"rawdata", "raw data"} else str(row["values"].get("Precursor") or "unspecified input data"),
                "outputDataLabel": str(row["values"].get("Target") or "Unspecified source entity"),
            }
            for row in case["table_rows"]
            if row["section"] == "pre"
        ]
    if query_id == "q45_case_measurement_result_counts":
        return [
            {
                "caseKey": case["key"],
                "measurementCount": "1",
                "resultCount": str(sum(row["section"] == "anal" for row in case["table_rows"])),
            }
            for case in cases
        ]
    if query_id == "q46_normalized_result_quantities":
        return [
            {
                "caseKey": row["caseKey"],
                "propertyLabel": row["propertyLabel"],
                "sourceCell": row["sourceCell"],
                "rawValue": row["rawValue"],
                "value": row["value"],
                "unit": row["unit"],
            }
            for case in cases
            for row in _expected_result_rows(case)
            if row["value"] and row["unit"]
        ]
    if query_id == "q47_qualified_source_fields":
        return [
            {
                "caseKey": case["key"],
                "fieldName": record["field"],
                "sourceCell": record["cell"],
                "statusLabel": record["status"],
                "rawValue": _raw_lexical(record.get("raw_value")),
            }
            for case in cases
            for record in case["source_records"]
            if record["status"] != "reported"
        ]
    if query_id == "q48_qualified_measurement_settings":
        return [
            {
                "caseKey": row["caseKey"],
                "parameterLabel": row["parameterLabel"],
                "statusLabel": row["statusLabel"],
                "sourceCell": row["sourceCell"],
                "rawValue": row["rawValue"],
            }
            for case in cases
            for row in _expected_parameter_rows(case)
            if row["statusLabel"] != "reported"
        ]
    if query_id == "q49_analysis_provenance_across_cases":
        return [row for case in cases for row in _expected_analysis_provenance_rows(case)]
    if query_id == "q50_preprocessing_transformations":
        return [row for case in cases for row in _expected_preprocessing_rows(case)]
    raise KeyError(f"No ground-truth builder for {query_id}")


def _counter_rows(counter: Counter[tuple[str, ...]], variables: list[str]) -> list[dict[str, Any]]:
    return [
        {**dict(zip(variables, values)), "occurrences": count}
        for values, count in sorted(counter.items())
    ]


def _compare_query_rows(expected: list[dict[str, str]], observed: list[dict[str, str]], variables: list[str]) -> dict[str, Any]:
    expected_counter = Counter(tuple(str(row.get(variable, "")) for variable in variables) for row in expected)
    observed_counter = Counter(tuple(str(row.get(variable, "")) for variable in variables) for row in observed)
    missing = expected_counter - observed_counter
    unexpected = observed_counter - expected_counter
    matched = sum((expected_counter & observed_counter).values())
    expected_count = sum(expected_counter.values())
    observed_count = sum(observed_counter.values())
    precision = 100.0 if observed_count == 0 and expected_count == 0 else (100.0 * matched / observed_count if observed_count else 0.0)
    recall = 100.0 if expected_count == 0 else 100.0 * matched / expected_count
    return {
        "status": "pass" if not missing and not unexpected else "fail",
        "exact_match": not missing and not unexpected,
        "expected_row_count": expected_count,
        "observed_row_count": observed_count,
        "matched_row_count": matched,
        "missing_expected_row_count": sum(missing.values()),
        "unexpected_row_count": sum(unexpected.values()),
        "row_precision_percent": round(precision, 2),
        "row_recall_percent": round(recall, 2),
        "missing_expected_rows": _counter_rows(missing, variables),
        "unexpected_rows": _counter_rows(unexpected, variables),
        "comparison_method": "exact row-multiset equality against expectations independently derived from the sanitized workbook manifest",
    }


def _query_workbench_payload(case_summaries: list[dict[str, Any]], queries: list[dict[str, Any]], source_sha256: str) -> dict[str, Any]:
    validations = [item["validation"] for item in queries]
    return {
        "schema_version": "h2kg-characterization-query-workbench/v3",
        "default_query": "q1_tem_specimen_preparation",
        "source_sha256": source_sha256,
        "cases": [
            {key: case[key] for key in ("key", "title", "source_record_count", "result_count")}
            for case in case_summaries
        ],
        "validation_summary": {
            "query_count": len(queries),
            "passed_query_count": sum(item["exact_match"] for item in validations),
            "failed_query_count": sum(not item["exact_match"] for item in validations),
            "expected_row_count": sum(item["expected_row_count"] for item in validations),
            "observed_row_count": sum(item["observed_row_count"] for item in validations),
            "matched_row_count": sum(item["matched_row_count"] for item in validations),
            "method": "SPARQL result rows compared exactly with manifest-derived ground truth",
        },
        "queries": queries,
    }


def _run_queries(dataset: Dataset, output_dir: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    query_dir = ensure_dir(output_dir / "queries")
    result_dir = ensure_dir(output_dir / "query_results")
    ground_truth_dir = ensure_dir(output_dir / "query_ground_truth")
    summaries: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    for spec in _query_specs():
        query_path = write_text(query_dir / f"{spec['id']}.rq", spec["query"].strip() + "\n")
        observed_rows: list[dict[str, str]] = []
        result = dataset.query(spec["query"])
        variables = [str(item) for item in result.vars]
        for binding in result:
            observed_rows.append({variables[index]: "" if value is None else str(value) for index, value in enumerate(binding)})
        expected_rows = [{variable: str(row.get(variable, "")) for variable in variables} for row in _ground_truth_rows(spec["id"], manifest)]
        validation = _compare_query_rows(expected_rows, observed_rows, variables)
        _write_csv(result_dir / f"{spec['id']}.csv", observed_rows, variables)
        dump_json(result_dir / f"{spec['id']}.json", {"variables": variables, "rows": observed_rows})
        _write_csv(ground_truth_dir / f"{spec['id']}_expected.csv", expected_rows, variables)
        dump_json(ground_truth_dir / f"{spec['id']}_expected.json", {
            "variables": variables,
            "plain_language_question": spec["question"],
            "basis": spec["ground_truth_basis"],
            "rows": expected_rows,
        })
        dump_json(ground_truth_dir / f"{spec['id']}_comparison.json", {"query_id": spec["id"], **validation})
        validation_rows.append({
            "query_id": spec["id"],
            "category": spec["category"],
            "plain_language_question": spec["question"],
            "title": spec["title"],
            **{key: value for key, value in validation.items() if not isinstance(value, list)},
        })
        summaries.append({
            "id": spec["id"],
            "category": spec["category"],
            "question": spec["question"],
            "title": spec["title"],
            "purpose": spec["purpose"],
            "ground_truth_basis": spec["ground_truth_basis"],
            "query": spec["query"].strip(),
            "query_file": f"queries/{query_path.name}",
            "result_csv": f"query_results/{spec['id']}.csv",
            "result_json": f"query_results/{spec['id']}.json",
            "expected_csv": f"query_ground_truth/{spec['id']}_expected.csv",
            "expected_json": f"query_ground_truth/{spec['id']}_expected.json",
            "comparison_json": f"query_ground_truth/{spec['id']}_comparison.json",
            "row_count": len(observed_rows),
            "variables": variables,
            "rows": observed_rows,
            "expected_rows": expected_rows,
            "validation": validation,
        })
    _write_csv(ground_truth_dir / "query_ground_truth_validation.csv", validation_rows)
    dump_json(ground_truth_dir / "query_ground_truth_validation.json", {"schema_version": "h2kg-characterization-query-validation/v2", "queries": validation_rows})
    return summaries


def _validate_graph(flat: Graph, shapes: Graph, output_dir: Path) -> dict[str, Any]:
    conforms, report_graph, report_text = shacl_validate(
        flat,
        shacl_graph=shapes,
        inference="rdfs",
        serialize_report_graph=False,
    )
    report_graph.serialize(output_dir / "shacl_validation_report.ttl", format="turtle")
    write_text(output_dir / "shacl_validation_report.txt", str(report_text))
    negatives: list[dict[str, Any]] = []
    scenarios = (
        ("missing_measurement_subject", H2KG.hasMeasurementSubject, H2KG.Measurement),
        ("missing_parameter_property", H2KG.ofProperty, H2KG.Parameter),
        ("missing_result_provenance", PROV.wasGeneratedBy, H2KG.DataPoint),
        ("missing_quantity_unit", QUDT.unit, QUDT.QuantityValue),
    )
    for name, predicate, subject_type in scenarios:
        negative = Graph()
        for triple in flat:
            negative.add(triple)
        candidates = sorted(
            negative.triples((None, predicate, None)),
            key=lambda triple: tuple(str(item) for item in triple),
        )
        removed = next(
            (triple for triple in candidates if (triple[0], RDF.type, subject_type) in negative),
            None,
        )
        if removed:
            negative.remove(removed)
        negative_conforms, _, negative_report = shacl_validate(
            negative,
            shacl_graph=shapes,
            inference="rdfs",
            serialize_report_graph=False,
        )
        negatives.append({"scenario": name, "removed_triple": [str(item) for item in removed] if removed else [], "conforms": bool(negative_conforms), "expected": False, "report": str(negative_report)})
    return {"conforms": bool(conforms), "report": str(report_text), "negative_tests": negatives}


def _write_demo_files(output_dir: Path) -> None:
    write_text(output_dir / "run_demo.py", _demo_script())
    dump_json(output_dir / "characterization_kg_demo.ipynb", _demo_notebook())


def _demo_script() -> str:
    return '''from __future__ import annotations

import argparse
import json
from pathlib import Path

from pyshacl import validate
from rdflib import Dataset, Graph


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the H2KG characterization knowledge-graph demonstration")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent))
    parser.add_argument("--query", default="q1_tem_specimen_preparation")
    args = parser.parse_args()
    root = Path(args.root)
    dataset = Dataset()
    dataset.parse(root / "characterization_knowledge_graph.trig", format="trig")
    query = (root / "queries" / f"{args.query}.rq").read_text(encoding="utf-8")
    result = dataset.query(query)
    observed = [dict(zip([str(v) for v in result.vars], [str(x) if x is not None else "" for x in row])) for row in result]
    print(json.dumps(observed, indent=2))
    comparison_path = root / "query_ground_truth" / f"{args.query}_comparison.json"
    expected_path = root / "query_ground_truth" / f"{args.query}_expected.json"
    if comparison_path.exists() and expected_path.exists():
        comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
        expected = json.loads(expected_path.read_text(encoding="utf-8"))["rows"]
        print(f"Ground-truth status: {comparison['status']} ({comparison['matched_row_count']}/{comparison['expected_row_count']} rows matched)")
        if not comparison["exact_match"]:
            print(json.dumps({"expected": expected, "comparison": comparison}, indent=2))
    flat = Graph().parse(root / "characterization_knowledge_graph.ttl", format="turtle")
    shapes = Graph().parse(root / "characterization_shapes.ttl", format="turtle")
    conforms, _, report = validate(flat, shacl_graph=shapes, inference="rdfs")
    print(f"SHACL conforms: {conforms}")
    if not conforms:
        print(report)


if __name__ == "__main__":
    main()
'''


def _demo_notebook() -> dict[str, Any]:
    return {
        "cells": [
            {"cell_type": "markdown", "metadata": {}, "source": ["# H₂KG-backed characterization knowledge graph\n", "Load the named RDF graphs, execute the published SPARQL competency queries, compare the results with manifest-derived ground truth, and validate the flattened graph with pySHACL.\n"]},
            {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": ["from pathlib import Path\n", "from rdflib import Dataset, Graph\n", "from pyshacl import validate\n", "ROOT = Path('.')\n", "dataset = Dataset()\n", "dataset.parse(ROOT / 'characterization_knowledge_graph.trig', format='trig')\n", "len(dataset)\n"]},
            {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": ["query = (ROOT / 'queries' / 'q1_tem_specimen_preparation.rq').read_text(encoding='utf-8')\n", "list(dataset.query(query))\n"]},
            {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": ["import json\n", "comparison = json.loads((ROOT / 'query_ground_truth' / 'q1_tem_specimen_preparation_comparison.json').read_text(encoding='utf-8'))\n", "comparison\n"]},
            {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": ["data = Graph().parse(ROOT / 'characterization_knowledge_graph.ttl', format='turtle')\n", "shapes = Graph().parse(ROOT / 'characterization_shapes.ttl', format='turtle')\n", "validate(data, shacl_graph=shapes, inference='rdfs')[0]\n"]},
        ],
        "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "language_info": {"name": "python", "version": "3.11"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def build_characterization_kg(
    manifest_path: str | Path,
    ontology_path: str | Path,
    output_root: str | Path,
    *,
    taxonomy_registry_path: str | Path | None = None,
    taxonomy_ttl_path: str | Path | None = None,
) -> dict[str, Any]:
    """Generate the named-graph dataset and all reproducibility artifacts."""

    manifest_path = Path(manifest_path)
    ontology_path = Path(ontology_path)
    output_root = Path(output_root)
    target = output_root / "characterization_kg"
    if target.exists():
        shutil.rmtree(target)
    ensure_dir(target)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise ValueError(f"Unsupported characterization manifest: {manifest.get('schema_version')}")
    if manifest.get("source", {}).get("sha256") != EXPECTED_WORKBOOK_SHA256:
        raise ValueError("Characterization manifest is not derived from the approved corrected workbook fingerprint.")
    if len(manifest.get("cases", [])) != 8:
        raise ValueError("Characterization manifest must contain exactly eight case graphs.")
    shutil.copyfile(manifest_path, target / "characterization_source_manifest.json")

    registry_path = Path(taxonomy_registry_path) if taxonomy_registry_path else output_root / "ontology" / "taxonomy_registry.json"
    taxonomy_path = Path(taxonomy_ttl_path) if taxonomy_ttl_path else output_root / "ontology" / "h2kg-v2-taxonomy.ttl"
    active_terms = _active_terms(registry_path)
    dataset = Dataset(default_union=False)
    _bind(dataset)
    schema_graph = dataset.graph(GRAPH.schema)
    _bind(schema_graph)
    _add_local_schema(schema_graph)
    workbook = URIRef(f"{CASE}source/workbook-{manifest['source']['sha256'].lower()[:16]}")
    schema_graph.add((workbook, RDF.type, KG.WorkbookSnapshot))
    schema_graph.add((workbook, DCTERMS.title, Literal(manifest["source"]["title"])))
    schema_graph.add((workbook, DCTERMS.identifier, Literal(manifest["source"]["sha256"])))
    schema_graph.add((workbook, DCTERMS.description, Literal(manifest["source"]["redistribution"])))

    case_summaries = [_build_case(dataset, case, active_terms, workbook) for case in manifest["cases"]]
    shapes = _shape_graph()
    shapes_graph = dataset.graph(GRAPH.shapes)
    for triple in shapes:
        shapes_graph.add(triple)
    flat_before_taxonomy = _flatten(dataset)
    taxonomy_subset = _referenced_taxonomy_subset(flat_before_taxonomy, taxonomy_path if taxonomy_path.exists() else None)
    taxonomy_graph = dataset.graph(GRAPH.taxonomy)
    for triple in taxonomy_subset:
        taxonomy_graph.add(triple)

    dataset.serialize(target / "characterization_knowledge_graph.trig", format="trig")
    dataset.serialize(target / "characterization_knowledge_graph.nq", format="nquads")
    flat = _flatten(dataset)
    flat.serialize(target / "characterization_knowledge_graph.ttl", format="turtle")
    canonical_flat = Graph().parse(target / "characterization_knowledge_graph.ttl", format="turtle")
    canonical_flat.serialize(
        target / "characterization_knowledge_graph.jsonld",
        format="json-ld",
        indent=2,
        use_native_types=False,
    )
    shapes.serialize(target / "characterization_shapes.ttl", format="turtle")
    taxonomy_subset.serialize(target / "referenced_h2kg_taxonomy_subset.ttl", format="turtle")

    case_dir = ensure_dir(target / "cases")
    for summary in case_summaries:
        case_graph = Graph()
        _bind(case_graph)
        for graph_iri in (summary["source_graph"], summary["semantic_graph"], summary["validation_graph"]):
            for triple in dataset.graph(URIRef(graph_iri)):
                case_graph.add(triple)
        case_graph.serialize(case_dir / f"{summary['key']}.ttl", format="turtle")

    all_mapping_rows = [row for summary in case_summaries for row in summary.pop("mapping_rows")]
    _write_csv(target / "source_semantic_mapping_registry.csv", all_mapping_rows)
    dump_json(target / "source_semantic_mapping_registry.json", {"schema_version": BUILD_SCHEMA, "mappings": all_mapping_rows})
    unit_rows = _unit_registry_rows(flat, all_mapping_rows)
    _write_csv(target / "unit_registry.csv", unit_rows)
    dump_json(target / "unit_registry.json", {"units": unit_rows})

    validation = _validate_graph(flat, shapes, target)
    if not validation["conforms"]:
        raise ValueError("Generated characterization knowledge graph does not conform to its SHACL profile.")
    if any(item["conforms"] for item in validation["negative_tests"]):
        raise ValueError("A required negative SHACL test unexpectedly conformed.")

    query_summaries = _run_queries(dataset, target, manifest)
    _validate_expected_queries(query_summaries)
    query_payload = _query_workbench_payload(case_summaries, query_summaries, manifest["source"]["sha256"])
    dump_json(target / "characterization_query_workbench.json", query_payload)
    _write_demo_files(target)
    _write_profile_package(target, case_summaries, shapes)
    workflow_usage = _characterization_workflow_usage(manifest, active_terms)
    dump_json(
        target / "characterization_workflow_usage_registry.json",
        {
            "schema_version": "h2kg-characterization-workflow-usage/v1",
            "ontology_version": "2.3.0",
            "usage_count": len(workflow_usage),
            "usage_edges": workflow_usage,
        },
    )
    _write_csv(target / "characterization_workflow_usage_registry.csv", workflow_usage)

    parsed_turtle = Graph().parse(target / "characterization_knowledge_graph.ttl", format="turtle")
    parsed_jsonld = Graph().parse(target / "characterization_knowledge_graph.jsonld", format="json-ld")
    parity = isomorphic(parsed_turtle, parsed_jsonld)
    if not parity:
        raise ValueError("Flattened Turtle and JSON-LD characterization graphs are not RDF-isomorphic.")
    represented = {str(record) for record in flat.subjects(RDF.type, KG.SourceField)}
    eligible = int(manifest["eligible_field_count"])
    coverage = len(represented) / eligible if eligible else 1.0
    if len(represented) != eligible:
        raise ValueError(f"Workbook field coverage mismatch: {len(represented)} represented of {eligible} eligible fields.")

    findings = list(flat.subjects(RDF.type, KG.ValidationFinding))
    report = {
        "schema_version": BUILD_SCHEMA,
        "generated_at": now_iso(),
        "ontology_version": "2.3.0",
        "ontology_modified": False,
        "source_manifest": manifest_path.name,
        "source_sha256": manifest["source"]["sha256"],
        "case_count": len(case_summaries),
        "method_family_count": manifest["method_family_count"],
        "eligible_field_count": eligible,
        "represented_field_count": len(represented),
        "source_coverage_percent": round(coverage * 100, 2),
        "source_status_counts": {
            status: sum(case["source_status_counts"][status] for case in case_summaries)
            for status in SOURCE_STATUSES
        },
        "excluded_personal_field_count": manifest["excluded_field_count"],
        "rdf_triple_count": len(flat),
        "named_graph_count": sum(1 for _ in dataset.graphs()),
        "validation_finding_count": len(findings),
        "workflow_usage_count": len(workflow_usage),
        "shacl_conforms": validation["conforms"],
        "negative_tests": validation["negative_tests"],
        "turtle_jsonld_isomorphic": parity,
        "query_validation": query_payload["validation_summary"],
        "queries": [
            {key: value for key, value in item.items() if key not in {"rows", "expected_rows"}}
            for item in query_summaries
        ],
        "cases": case_summaries,
    }
    dump_json(target / "validation_report.json", report)
    _write_csv(target / "source_coverage_report.csv", [
        {
            "case": case["key"],
            "title": case["title"],
            "eligible_fields": case["source_record_count"],
            "represented_fields": case["mapped_record_count"],
            "coverage_percent": round(100 * case["mapped_record_count"] / case["source_record_count"], 2) if case["source_record_count"] else 100,
            "results": case["result_count"],
            **{
                f"status_{status}": case["source_status_counts"][status]
                for status in SOURCE_STATUSES
            },
        }
        for case in case_summaries
    ])
    write_text(target / "README.md", _readme(report))
    return report


def _unit_registry_rows(flat: Graph, mappings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for qv in sorted(set(flat.subjects(RDF.type, QUDT.QuantityValue)), key=str):
        rows.append({
            "quantity_value": str(qv),
            "numeric_value": str(next(flat.objects(qv, QUDT.numericValue), "")),
            "unit_iri": str(next(flat.objects(qv, QUDT.unit), "")),
            "quantity_kind_iri": str(next(flat.objects(qv, QUDT.quantityKind), "")),
            "status": "exact_qudt_mapping",
        })
    unresolved = [row for row in mappings if row.get("unit_status") == "unit_unresolved"]
    for row in unresolved:
        rows.append({
            "quantity_value": "",
            "numeric_value": str(row.get("raw_value", "")),
            "unit_iri": "",
            "quantity_kind_iri": "",
            "status": "source_unit_retained_no_qudt_assertion",
            "source_cell": row.get("cell", ""),
        })
    return rows


def _validate_expected_queries(queries: list[dict[str, Any]]) -> None:
    by_id = {item["id"]: item for item in queries}
    failed = [item["id"] for item in queries if not item["validation"]["exact_match"]]
    if failed:
        raise ValueError(f"SPARQL ground-truth validation failed for: {', '.join(failed)}")
    q2 = by_id["q2_tem_instrument_settings"]["rows"]
    if not any("WorkingDistance" in row.get("parameterLabel", "") and row.get("statusLabel") == "unconfirmed" for row in q2):
        raise ValueError("TEM query did not retain the unconfirmed working-distance state.")
    q4 = by_id["q4_tem_result_value"]["rows"]
    if not any(row.get("resultLabel") == "Average size result" and row.get("value") == "5" and row.get("unit", "").endswith("NanoM") for row in q4):
        raise ValueError("TEM 5 nm result is missing from the deterministic result query.")
    q9 = by_id["q9_conservative_quantity_findings"]["rows"]
    required = {"label_unit_conflict", "unit_unresolved", "ordered_ratio_basis_unspecified"}
    observed = {row.get("code", "") for row in q9}
    if not required.issubset(observed):
        raise ValueError(f"Required conservative findings are missing: {sorted(required - observed)}")


def _write_profile_package(target: Path, cases: list[dict[str, Any]], shapes: Graph) -> None:
    profile_dir = ensure_dir(target / "profiles")
    shapes.serialize(profile_dir / "characterization_profile_shapes.ttl", format="turtle")
    for case in cases:
        dump_json(profile_dir / f"{case['key']}_profile.json", {
            "profile": case["key"],
            "title": case["title"],
            "measurement": case["measurement"],
            "required_pattern": ["measurement subject", "instrument", "raw output dataset", "parameter records where reported", "result provenance where reported"],
            "source_record_count": case["source_record_count"],
            "result_count": case["result_count"],
            "shapes": "characterization_profile_shapes.ttl",
        })


def _characterization_workflow_usage(
    manifest: dict[str, Any],
    active_terms: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Expose corrected contextual usage in H2KG Explore without TBox axioms."""

    rows: dict[tuple[str, str, str], dict[str, Any]] = {}
    labels = {name: term.get("label", name) for name, term in active_terms.items()}

    def add(case: dict[str, Any], target_local: str, relation: str, path: str, outcome: str, rationale: str) -> None:
        source_local = case["measurement_class"]
        target_local = target_local if target_local in active_terms or not active_terms else "Property"
        key = (source_local, target_local, relation)
        if key in rows:
            return
        token = hashlib.sha256("|".join(key).encode("utf-8")).hexdigest()[:16]
        rows[key] = {
            "migration_id": f"characterization-{token}",
            "source_iri": str(H2KG[source_local]),
            "canonical_source_iri": str(H2KG[source_local]),
            "source_label": labels.get(source_local, source_local),
            "source_intrinsic_role": "Measurement",
            "target_iri": str(H2KG[target_local]),
            "canonical_target_iri": str(H2KG[target_local]),
            "target_label": labels.get(target_local, target_local),
            "target_intrinsic_role": "Characteristic" if relation in {"uses as parameter", "measures property"} else ("Instrument" if relation == "uses instrument" else "Data"),
            "migration_outcome": outcome,
            "display_relation": relation,
            "path_iris": [str(H2KG[item]) for item in path.split(" / ") if not item.startswith("inverse(")],
            "path_label": path,
            "status": "migrated-profile",
            "rationale": rationale,
            "source_profile": f"characterization:{case['key']}",
        }

    for case in manifest["cases"]:
        add(case, case["instrument_class"], "uses instrument", "usesInstrument", "direct_profile_relation", "Workbook-backed profile requires the method-specific instrument type.")
        add(case, case["raw_dataset_class"], "has output data", "hasOutputData", "direct_profile_relation", "Workbook-backed profile requires the reported raw-data output type.")
        unit_lookup = _paired_direct_units(case)
        for record in case["direct_fields"]:
            key = _field_key(record["field"])
            if record["section"] not in {"char", "inst"} or key not in PROPERTY_FIELDS or key.endswith("unit"):
                continue
            target = _parameter_property_class(record["field"], unit_lookup.get(key), active_terms)
            add(case, str(target).rsplit("#", 1)[-1], "uses as parameter", "hasParameter / ofProperty", "parameter_record_profile", "The setting is represented through a Parameter record whose ofProperty target retains its intrinsic characteristic identity.")
        for row in case["table_rows"]:
            if row["section"] != "anal":
                continue
            target_label = _norm_label(row["values"].get("Target"))
            target_local = RESULT_PROPERTIES.get((case["key"], target_label), ("Property", ""))[0]
            add(case, target_local, "measures property", "inverse(fromMeasurement) / ofProperty", "result_property_profile", "A DataPoint from the measurement refers to an occurrence of this intrinsic property type.")
    return sorted(rows.values(), key=lambda item: (item["source_label"].casefold(), item["display_relation"], item["target_label"].casefold()))


def _readme(report: dict[str, Any]) -> str:
    return f"""# H₂KG-backed characterization knowledge graph

This package is generated from the sanitized, fingerprinted corrected workbook manifest. The source workbook is not redistributed.

## Scope

- {report['case_count']} case graphs across {report['method_family_count']} method families
- {report['represented_field_count']} of {report['eligible_field_count']} eligible workbook fields represented ({report['source_coverage_percent']:.2f}%)
- TEM is the principal bounded competency demonstration
- XRD and XPS are outside this workbook-backed package

## Modeling policy

The package uses H₂KG 2.3.0 classes and properties without changing the ontology taxonomy. Parameter records are distinct from intrinsic scientific properties. Missing, unconfirmed, inapplicable, unresolved-unit, and semantically conflicting source values remain explicit provenance records and are not silently normalized.

## Query validation

All {report['query_validation']['query_count']} SPARQL competency queries are evaluated by exact row-multiset comparison with expectations independently derived from the sanitized manifest. The current build matched {report['query_validation']['matched_row_count']} of {report['query_validation']['expected_row_count']} expected rows, with {report['query_validation']['failed_query_count']} failed queries. Query-specific expected rows and comparison reports are in `query_ground_truth/`.

## Run

```bash
python run_demo.py --query q1_tem_specimen_preparation
```

The notebook and query files provide the equivalent RDFLib and SPARQL workflow. `validation_report.json` records query-ground-truth results, SHACL conformance, negative tests, RDF serialization parity, and source coverage.
"""


def write_characterization_manuscript_materials(
    kg_output_dir: str | Path,
    local_output_dir: str | Path,
) -> dict[str, Any]:
    """Write manuscript-ready text locally; callers must keep it outside Git."""

    kg_output_dir = Path(kg_output_dir)
    local_output_dir = Path(local_output_dir)
    ensure_dir(local_output_dir)
    report = json.loads((kg_output_dir / "validation_report.json").read_text(encoding="utf-8"))
    write_text(local_output_dir / "methods_subsection.md", _methods_text(report))
    write_text(local_output_dir / "results_subsection.md", _results_text(report))
    write_text(
        local_output_dir / "manuscript_section_kg_construction_and_query_evaluation.md",
        _manuscript_section(report),
    )
    write_text(local_output_dir / "representative_query_table.md", _representative_query_table(report))
    write_text(local_output_dir / "query_table.md", _query_table(report))
    write_text(local_output_dir / "figure_specification.md", _figure_specification())
    write_text(local_output_dir / "workflow_to_kg_figure.svg", _figure_svg())
    return {"status": "generated", "output_dir": str(local_output_dir), "files": sorted(path.name for path in local_output_dir.iterdir())}


def _methods_text(report: dict[str, Any]) -> str:
    return f"""## Knowledge-graph construction and query evaluation

A bounded characterization knowledge graph was constructed from a corrected workbook containing eight cases from seven method families. The workbook was transformed into a sanitized manifest identified by SHA-256 `{report['source_sha256']}`; personal names, email addresses, and author-institution fields were excluded. An RDFLib `Dataset` separated source-fidelity statements, H₂KG semantic assertions, validation findings, and the referenced taxonomy subset into named graphs. Specimens, preparation activities, measurements, instruments, parameter records, datasets, analyses, results, scientific properties, quantity values, and provenance were represented using H₂KG 2.3.0 together with PROV-O, DCTERMS, and QUDT. Every eligible workbook field retained its sheet and cell reference, raw lexical value, parsed value where defensible, and an explicit status for reported, missing, not applicable, not specified, unconfirmed, unresolved-formula, or semantically conflicting content.

H₂KG provided the common semantic paths that made heterogeneous workbook records searchable as one graph. Method-specific records were typed with shared classes for matter, manufacturing, measurement, instrument, data, process, DataPoint, and property. Relations such as `hasMeasurementSubject`, `usesInstrument`, `hasInputData`, and `hasOutputData` connected workflow stages consistently across methods. Acquisition settings were modeled as parameter records linked through `ofProperty` to scientific property occurrences, preventing a property such as temperature from being reclassified as a parameter merely because it was used as a setting. Result records linked a DataPoint to its measured property, specimen bearer, generating analysis, and measurement provenance; QUDT represented defensible values and units. Source-field resources and `prov:wasDerivedFrom` links retained the workbook evidence behind each semantic assertion. This ontology-driven structure did not infer new scientific facts. It supplied stable types and query paths through which differently named source records could be retrieved, compared, and checked without discarding missing or conflicting content.

The evaluation combined source coverage, RDF serialization parity, SHACL validation, negative controls, and SPARQL competency questions. Fifty questions were prespecified in plain language and paired one-to-one with executable SPARQL. They covered TEM traceability, method-specific measurement context, reported results, source-status accounting, acquisition settings, normalized quantities, qualified or missing values, analysis provenance, and preprocessing transformations. Expected result rows were generated independently from the sanitized manifest rather than copied from SPARQL output. RDFLib results were compared with these expectations using exact row-multiset equality, so missing rows, unexpected rows, or duplicate-count differences caused a query to fail. pySHACL tested the valid graph and four deliberately invalid graphs with a missing measurement subject, parameter-property link, result provenance link, or quantity unit. These tests evaluate conformance to the encoded source and profile requirements. They do not establish scientific correctness, ontology completeness, workflow execution, general search performance, or automatic FAIRness.
"""


def _results_text(report: dict[str, Any]) -> str:
    return f"""## Query and validation results

The dataset represented all {report['represented_field_count']:,} eligible workbook fields across eight cases ({report['source_coverage_percent']:.2f}% source coverage) as {report['rdf_triple_count']:,} RDF statements in {report['named_graph_count']} named graphs. Turtle and JSON-LD serializations were RDF-isomorphic. The valid graph conformed to the SHACL profile, whereas all four negative controls failed for the intended missing relation. TEM provided the principal traceability example: the queries recovered the six-step specimen-preparation chain, eight acquisition-setting records including qualified source states, image-analysis provenance, and the workbook-reported 5 nm mean-particle-size result with its specimen bearer and QUDT unit.

All {report['query_validation']['query_count']} prespecified SPARQL questions passed exact comparison with their manifest-derived expectations. In total, {report['query_validation']['matched_row_count']:,} of {report['query_validation']['expected_row_count']:,} expected rows were recovered, with no missing or unexpected rows. The cross-case questions retrieved measurement contexts and results for every case, accounted for each source-value status, exposed normalized and withheld quantities, and traced analysis and preprocessing provenance. Conservative handling remained observable: the FIB-SEM entry `Volume fraction = 80 nm` was retained as a label-unit conflict, and unresolved `pu` tokens were preserved without assigning an unsupported QUDT unit. The agreement demonstrates that the graph and queries reproduce the curated source manifest under the stated competency questions. It is not an independently remeasured ground truth and does not quantify general retrieval accuracy or scientific validity.

Ten representative questions are summarized in the accompanying table. They show how the shared ontology paths support both case-specific traversal and cross-method retrieval. The complete set of 50 questions, SPARQL text, expected rows, observed rows, and exact comparison reports is provided in the supplementary query package.
"""


def _manuscript_section(report: dict[str, Any]) -> str:
    return (
        _methods_text(report)
        + "\n"
        + _results_text(report)
        + "\n"
        + _representative_query_table(report)
        + "\n"
        + """## Interpretation and limitations

The evaluation uses complementary checks that answer different questions. Complete source-field representation tests whether eligible workbook content was retained. RDF isomorphism tests whether the Turtle and JSON-LD exports express the same graph. SHACL and its negative controls test explicit structural requirements. The SPARQL comparison tests whether prespecified scientific questions recover exactly the records expected from the same curated source manifest. Together, these checks provide reproducible evidence for source-conformant construction, constraint checking, and queryability of this bounded graph.

The manifest-derived expectations are a reproducible reference for implementation testing, but they are not independent experimental measurements. Consequently, the 50 successful questions must not be interpreted as corpus-wide precision or recall, scientific verification of the workbook, or proof that H₂KG covers every characterization use case. Future evaluation should include blinded questions from independent laboratories, independently adjudicated relevance judgments, alternative data models, larger graphs, and runtime or scalability measurements. The present demonstration instead establishes a transparent baseline in which each answer can be traced to source cells and rerun with RDFLib, SPARQL, and pySHACL.
"""
    )


def _representative_query_table(report: dict[str, Any]) -> str:
    representative_ids = [
        "q1_tem_specimen_preparation",
        "q2_tem_instrument_settings",
        "q3_tem_dataset_analysis",
        "q4_tem_result_value",
        "q5_all_measurement_contexts",
        "q6_all_result_records",
        "q9_conservative_quantity_findings",
        "q46_normalized_result_quantities",
        "q47_qualified_source_fields",
        "q50_preprocessing_transformations",
    ]
    semantic_paths = {
        "q1_tem_specimen_preparation": "Result to measurement subject, then upstream manufacturing and material handoffs",
        "q2_tem_instrument_settings": "Measurement to instrument and parameter record to property and quantity value",
        "q3_tem_dataset_analysis": "Result to generating analysis, input dataset, and software",
        "q4_tem_result_value": "DataPoint to property, specimen bearer, source field, value, and unit",
        "q5_all_measurement_contexts": "Shared Measurement to subject, instrument, and output-data pattern",
        "q6_all_result_records": "Shared DataPoint to property, bearer, source evidence, value, and unit pattern",
        "q9_conservative_quantity_findings": "Validation findings linked to source fields and affected properties",
        "q46_normalized_result_quantities": "Property to complete QUDT quantity value with numeric value and unit",
        "q47_qualified_source_fields": "Source records grouped by explicit missing or qualified status",
        "q50_preprocessing_transformations": "Data-processing activity from input dataset to output dataset",
    }
    query_by_id = {item["id"]: item for item in report["queries"]}
    if any(query_id not in query_by_id for query_id in representative_ids):
        raise AssertionError("Representative manuscript query is missing from the validation report")

    def cell(value: Any) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")

    rows = [
        "### Representative ontology-backed competency queries",
        "",
        "| Query | Plain-language question | H₂KG-enabled path or check | Expected rows | Observed rows | Outcome |",
        "|---|---|---|---:|---:|---|",
    ]
    for query_id in representative_ids:
        item = query_by_id[query_id]
        validation = item["validation"]
        query_number = re.match(r"q(\d+)_", query_id).group(1)
        rows.append(
            "| "
            + " | ".join(
                [
                    f"Q{query_number}",
                    cell(item["question"]),
                    cell(semantic_paths[query_id]),
                    str(validation["expected_row_count"]),
                    str(validation["observed_row_count"]),
                    cell(validation["status"]),
                ]
            )
            + " |"
        )
    return "\n".join(rows) + "\n"


def _query_table(report: dict[str, Any]) -> str:
    rows = [
        "| Query | Category | Plain-language question | Expected rows | Observed rows | Result | Ground-truth basis |",
        "|---|---|---|---:|---:|---|---|",
    ]

    def cell(value: Any) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")

    for item in report["queries"]:
        validation = item["validation"]
        rows.append(
            "| "
            + " | ".join(
                [
                    cell(item["title"]),
                    cell(item["category"]),
                    cell(item["question"]),
                    str(validation["expected_row_count"]),
                    str(validation["observed_row_count"]),
                    cell(validation["status"]),
                    cell(item["ground_truth_basis"]),
                ]
            )
            + " |"
        )
    return "\n".join(rows) + "\n"


def _figure_specification() -> str:
    return """# Figure: workbook field to searchable knowledge graph

Show four aligned layers: (A) corrected workbook cells with cell-level provenance; (B) H₂KG occurrence graph from specimen preparation through TEM measurement and image analysis; (C) parameter/property and DataPoint/quantity-value patterns; and (D) SPARQL result and SHACL finding panels. Use solid lines for semantic assertions, dotted lines for `prov:wasDerivedFrom`, and a visibly hatched style for unconfirmed or unresolved values. The 5 nm TEM value must be labelled as workbook-reported, not illustrative or independently remeasured.
"""


def _figure_svg() -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="720" viewBox="0 0 1600 720">
<style>text{{font-family:Aptos,Arial,sans-serif;fill:#18323a}}.h{{font-size:28px;font-weight:700}}.t{{font-size:19px}}.s{{font-size:16px;fill:#546b73}}.box{{rx:18;stroke-width:3}}.edge{{stroke:#536f78;stroke-width:3;fill:none;marker-end:url(#a)}}.prov{{stroke:#8b6cad;stroke-dasharray:9 8}}</style>
<defs><marker id="a" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#536f78"/></marker></defs>
<text x="45" y="50" class="h">Corrected workbook</text><rect x="45" y="80" width="285" height="185" class="box" fill="#f1f4f5" stroke="#7a8990"/><text x="70" y="120" class="t">TEM!C78 · Average size</text><text x="70" y="158" class="t">TEM!I78 · 5 nm</text><text x="70" y="201" class="s">raw lexical value retained</text><text x="70" y="232" class="s">cell provenance retained</text>
<text x="405" y="50" class="h">H₂KG occurrences</text><rect x="405" y="92" width="235" height="92" class="box" fill="#e4f3ef" stroke="#278978"/><text x="455" y="145" class="t">TEM specimen</text><rect x="715" y="92" width="245" height="92" class="box" fill="#e7f0fa" stroke="#3c78ae"/><text x="750" y="132" class="t">TEM measurement</text><text x="755" y="161" class="s">uses instrument</text><path d="M715 138 L645 138" class="edge"/><rect x="1035" y="92" width="245" height="92" class="box" fill="#f0e8f8" stroke="#8553b5"/><text x="1072" y="145" class="t">Raw image data</text><path d="M960 138 L1030 138" class="edge"/>
<rect x="715" y="265" width="245" height="92" class="box" fill="#e7f0fa" stroke="#3c78ae"/><text x="752" y="318" class="t">Image analysis</text><path d="M1155 188 L1155 245 L965 310" class="edge"/><rect x="1035" y="265" width="245" height="92" class="box" fill="#f0e8f8" stroke="#8553b5"/><text x="1080" y="318" class="t">DataPoint</text><path d="M960 311 L1030 311" class="edge"/>
<rect x="1340" y="265" width="215" height="92" class="box" fill="#e2f3f5" stroke="#3c8792"/><text x="1370" y="305" class="t">Mean particle size</text><text x="1410" y="338" class="s">5 nm</text><path d="M1280 311 L1335 311" class="edge"/>
<path d="M330 170 C390 170 405 240 715 300" class="edge prov"/><text x="420" y="245" class="s">prov:wasDerivedFrom</text>
<text x="45" y="440" class="h">Queryable and validated</text><rect x="45" y="475" width="720" height="185" class="box" fill="#fff8e9" stroke="#b47719"/><text x="75" y="520" class="t">SPARQL: Which specimen, settings, dataset and analysis</text><text x="75" y="552" class="t">support the reported TEM result?</text><text x="75" y="603" class="s">Deterministic RDFLib result table</text><text x="75" y="633" class="s">Raw values and normalized quantities remain linked</text><rect x="835" y="475" width="720" height="185" class="box" fill="#f3eef8" stroke="#8553b5"/><text x="865" y="520" class="t">SHACL: required links, value structure and provenance</text><text x="865" y="568" class="s">Valid graph conforms</text><text x="865" y="603" class="s">Negative examples fail as expected</text><text x="865" y="633" class="s">Source conflicts remain explicit findings</text>
</svg>'''

