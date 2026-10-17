from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


W_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
H2KG = "https://w3id.org/h2kg/hydrogen-ontology#"
EXPECTED_SHA256 = "998E1F7765175456B955CD8EB777D550ECF1B47E0D77AF03C6BB3F0585C6CB04"

STATUS_ACTIONS = {
    "Apply recommended correction": "apply",
    "Keep current wording or placement": "retain",
    "Confirm scope before applying": "deprecate_source_ambiguous",
    "Source information required": "deprecate_source_ambiguous",
}

STRUCTURAL_ADDITIONS: dict[str, dict[str, str]] = {
    "Solution": {
        "label": "Solution",
        "parent": "Mixture",
        "definition": "A mixture in which one or more substances are dissolved at molecular or ionic scale in a continuous phase.",
    },
    "OxideMaterial": {
        "label": "Oxide material",
        "parent": "MaterialEntity",
        "definition": "A material entity containing an oxide as a principal functional constituent or phase.",
    },
    "SilicaBasedMaterial": {
        "label": "Silica-based material",
        "parent": "OxideMaterial",
        "definition": "An oxide material in which silica or a silicate is a principal functional constituent or structural phase.",
    },
    "MillingProcess": {
        "label": "Milling process",
        "parent": "MaterialProcessing",
        "definition": "A material-processing operation that uses mechanical action to reduce particle size, mix constituents, or modify particle morphology.",
    },
    "ChemicalReactionProcess": {
        "label": "Chemical reaction process",
        "parent": "MaterialProcessing",
        "definition": "A material-processing operation in which chemical bonds are formed, broken, or rearranged to transform one or more material inputs.",
    },
    "PhotochemicalCuringProcess": {
        "label": "Photochemical curing process",
        "parent": "ChemicalReactionProcess",
        "definition": "A chemical-reaction process in which incident radiation initiates or drives reactions that harden or cross-link a material.",
    },
    "OperatingCharacteristic": {
        "label": "Operating characteristic",
        "parent": "QuantitativeCharacteristic",
        "definition": "A quantitative characteristic that specifies or describes the operating state of a process, device, or experimental system.",
    },
    "ElectrochemicalOperatingCharacteristic": {
        "label": "Electrochemical operating characteristic",
        "parent": "OperatingCharacteristic",
        "definition": "An operating characteristic that specifies or describes the operating state of an electrochemical process, cell, or system.",
    },
    "ElectricalCharacteristic": {
        "label": "Electrical characteristic",
        "parent": "QuantitativeCharacteristic",
        "definition": "A quantitative characteristic describing an electrical state, excitation, response, or transport behavior.",
    },
    "RheologicalCharacteristic": {
        "label": "Rheological characteristic",
        "parent": "MechanicalCharacteristic",
        "definition": "A mechanical characteristic describing the deformation or flow response of a material under an applied stress or strain.",
    },
    "MolecularMassCharacteristic": {
        "label": "Molecular-mass characteristic",
        "parent": "QuantitativeCharacteristic",
        "definition": "A quantitative characteristic describing molecular mass or a distribution of molecular masses in a substance or material.",
    },
    "MassToChargeCharacteristic": {
        "label": "Mass-to-charge characteristic",
        "parent": "QuantitativeCharacteristic",
        "definition": "A quantitative characteristic expressing the ratio of an ion's mass to its electric charge number.",
    },
    "MagneticFieldCharacteristic": {
        "label": "Magnetic-field characteristic",
        "parent": "QuantitativeCharacteristic",
        "definition": "A quantitative characteristic describing the magnitude, direction, gradient, or spatial distribution of a magnetic field.",
    },
}

NEW_DOMAIN_TERMS: dict[str, dict[str, Any]] = {
    "PrintingWithdrawalSpeed": {
        "label": "Printing withdrawal speed",
        "parent": "QuantitativeCharacteristic",
        "definition": "A speed characteristic specifying the withdrawal or vertical translation rate of a dispensing nozzle during direct-ink-writing deposition.",
        "scope_note": "Use for the direct-ink-writing withdrawal motion; retain FeedRate for the generic rate at which material is supplied.",
    },
    "VolumetricInkDepositionRate": {
        "label": "Volumetric ink deposition rate",
        "parent": "QuantitativeCharacteristic",
        "definition": "A volumetric-rate characteristic specifying the volume of ink deposited per unit time by a printing or dispensing process.",
    },
    "LEDLuminousEfficacy": {
        "label": "LED luminous efficacy",
        "parent": "PerformanceCharacteristic",
        "definition": "A performance characteristic expressing the luminous flux produced by a light-emitting diode per unit electrical power consumed.",
    },
    "DLSPolydispersityIndex": {
        "label": "DLS polydispersity index",
        "parent": "MorphologicalCharacteristic",
        "definition": "A dimensionless characteristic derived from dynamic-light-scattering cumulant analysis that describes the relative breadth of a particle-size distribution.",
        "alt_labels": ["dynamic light scattering polydispersity index", "DLS PDI"],
    },
    "MolarMassDispersity": {
        "label": "Molar-mass dispersity",
        "parent": "MolecularMassCharacteristic",
        "definition": "A dimensionless molecular-mass characteristic equal to the ratio of mass-average molar mass to number-average molar mass for a polymer sample.",
        "alt_labels": ["molecular-weight dispersity", "Đ"],
    },
    "SuspensionIntrinsicViscosityCoefficient": {
        "label": "Suspension intrinsic-viscosity coefficient",
        "parent": "RheologicalCharacteristic",
        "definition": "A dimensionless coefficient in a suspension-viscosity model that quantifies the first-order contribution of dispersed-particle volume fraction to relative viscosity.",
        "scope_note": "Use for the intrinsic-viscosity coefficient in Krieger-Dougherty-type suspension models, not for polymer-solution intrinsic viscosity.",
    },
    "WaterToNitrogenAdsorptionCapacityRatio": {
        "label": "Water-to-nitrogen adsorption-capacity ratio",
        "parent": "SurfaceCharacteristic",
        "definition": "A dimensionless sorption characteristic equal to the ratio of a material's maximum water-vapor adsorption capacity to its maximum nitrogen adsorption capacity under the stated conditions.",
    },
}

PARENT_OVERRIDES = {
    "AceticAcidSolution": "Solution",
    "CesiumFormateSolution": "Solution",
    "IonomerSolution": "Solution",
    "NafionSolution": "Solution",
    "PrecursorSolution": "Solution",
    "MetalOxideMaterial": "OxideMaterial",
    "ColloidalSilica": "SilicaBasedMaterial",
    "ExfoliatedSilicaNanosheet": "SilicaBasedMaterial",
    "FumedSilica": "SilicaBasedMaterial",
    "PotassiumSilicate": "SilicaBasedMaterial",
    "QuaternaryAmmoniumSilicaPrecursor": "SilicaBasedMaterial",
    "QuaternizedSilicaFiller": "SilicaBasedMaterial",
    "SilicaNanosheet": "SilicaBasedMaterial",
    "SodiumSilicate": "SilicaBasedMaterial",
    "SulfonatedSilicaNanosheet": "SilicaBasedMaterial",
    "PAAPVAHydrogel": "PolymerMaterial",
    "AcidDopedPAAPVAHydrogel": "PAAPVAHydrogel",
    "InkPreparationBurningReaction": "ChemicalReactionProcess",
    "UVCuringProcess": "PhotochemicalCuringProcess",
    "BallMilling": "MillingProcess",
    "AnodeStoichiometricRatio": "ElectrochemicalOperatingCharacteristic",
    "CathodeStoichiometricRatio": "ElectrochemicalOperatingCharacteristic",
    "StorageModulusIncreaseOnsetTime": "MechanicalCharacteristic",
    "EISPerturbationAmplitude": "ACAmplitude",
    "ACAmplitude": "ElectricalCharacteristic",
    "IonBeamCurrent": "ElectricalCharacteristic",
    "IntrinsicViscosity": "RheologicalCharacteristic",
    "Viscosity": "RheologicalCharacteristic",
    "ZeroShearViscosity": "RheologicalCharacteristic",
    "ViscosityRecoveryShearRateHigh": "RheologicalCharacteristic",
    "ViscosityRecoveryShearRateLow": "RheologicalCharacteristic",
    "MolecularWeight": "MolecularMassCharacteristic",
    "NumberAverageMolecularWeight": "MolecularMassCharacteristic",
    "WeightAverageMolecularWeight": "MolecularMassCharacteristic",
    "MassToChargeRatio": "MassToChargeCharacteristic",
    "MagneticFieldStrength": "MagneticFieldCharacteristic",
}

DEFINITION_OVERRIDES = {
    "FeedRate": "A rate characteristic specifying the quantity of material supplied to a process per unit time, with the transported quantity and basis stated explicitly.",
    "ACAmplitude": "An electrical characteristic specifying the amplitude of an alternating electrical excitation, with the controlled electrical quantity and amplitude convention stated explicitly.",
    "EISPerturbationAmplitude": "An AC-amplitude characteristic specifying the small alternating voltage or current perturbation applied during electrochemical impedance spectroscopy.",
    "IntrinsicViscosity": "A rheological characteristic equal to the limiting value of reduced viscosity or inherent viscosity of a polymer solution as solute concentration approaches zero.",
    "Argon5PercentHydrogen": "A gaseous mixture containing argon and hydrogen, with hydrogen reported as 5 percent and the percentage basis retained from the source record when available.",
}

SCOPE_NOTE_OVERRIDES = {
    "AcidBaseTitrationMeasurement": (
        "The phosphoric-acid doping level workflow is a source-specific application and does not "
        "restrict the reusable acid-base titration measurement class."
    ),
    "AtomicLayerDeposition": (
        "The Pt/NbB2 catalyst workflow is a source-specific application and does not restrict "
        "the reusable atomic-layer-deposition process class."
    ),
}

REPLACEMENTS = {
    "DepositionRate": "VolumetricInkDepositionRate",
    "PowerEfficiency": "LEDLuminousEfficacy",
    "WaterUptakeRatio": "WaterToNitrogenAdsorptionCapacityRatio",
    "MercurySulfateReferenceElectrode": "ReferenceElectrodeMercurousSulfate",
    "XRayPhotoelectronSpectrometer": "XPSInstrument",
    "MercuryIntrusionPorosimetryMeasurement3": "MercuryPorosimeter",
}

SPLITS = {
    "PolydispersityIndex": ["DLSPolydispersityIndex", "MolarMassDispersity"],
}

PROFILE_MIGRATIONS = {
    "DirectInkWriting|FeedRate": "PrintingWithdrawalSpeed",
    "DirectInkWriting|DepositionRate": "VolumetricInkDepositionRate",
    "DynamicLightScatteringMeasurement|PolydispersityIndex": "DLSPolydispersityIndex",
    "GelPermeationChromatographyMeasurement|PolydispersityIndex": "MolarMassDispersity",
    "RheologyMeasurement|IntrinsicViscosity": "SuspensionIntrinsicViscosityCoefficient",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _paragraph_text(element: ElementTree.Element) -> str:
    return "".join(node.text or "" for node in element.findall(".//w:t", W_NS)).strip()


def _cell_text(element: ElementTree.Element) -> str:
    return " ".join(
        text for paragraph in element.findall(".//w:p", W_NS) if (text := _paragraph_text(paragraph))
    ).strip()


def _status_action(text: str) -> tuple[str, str]:
    for status, action in STATUS_ACTIONS.items():
        if text.startswith(status):
            return status, action
    raise ValueError(f"Unrecognized correction-guide status: {text[:120]}")


def _parse_parent_decisions(root: ElementTree.Element) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    for table in root.findall(".//w:tbl", W_NS)[1:]:
        rows = table.findall("./w:tr", W_NS)
        index = 1
        while index < len(rows):
            cells = [_cell_text(cell) for cell in rows[index].findall("./w:tc", W_NS)]
            if not cells or not re.match(r"^P\d{3}\s+", cells[0]):
                index += 1
                continue
            match = re.match(r"^(P\d{3})\s+(.+)$", cells[0])
            if match is None or len(cells) < 3:
                raise ValueError(f"Malformed parent decision row: {cells}")
            rationale_cells = (
                [_cell_text(cell) for cell in rows[index + 1].findall("./w:tc", W_NS)]
                if index + 1 < len(rows)
                else []
            )
            rationale = next((value for value in rationale_cells if value), "")
            document_status, final_action = _status_action(rationale)
            decisions.append(
                {
                    "decision_id": match.group(1),
                    "local_name": match.group(2).strip(),
                    "dimension": "parent",
                    "current_value": cells[1].strip(),
                    "recommended_value": cells[2].strip(),
                    "document_status": document_status,
                    "final_action": final_action,
                    "final_value": cells[2].strip() if final_action == "apply" else cells[1].strip(),
                    "rationale": rationale,
                }
            )
            index += 2
    return decisions


def _parse_definition_decisions(root: ElementTree.Element) -> list[dict[str, Any]]:
    paragraphs = [
        text
        for paragraph in root.findall(".//w:p", W_NS)
        if (text := _paragraph_text(paragraph))
    ]
    starts = [index for index, text in enumerate(paragraphs) if re.match(r"^D\d{3}\s+", text)]
    decisions: list[dict[str, Any]] = []
    for offset, start in enumerate(starts):
        end = starts[offset + 1] if offset + 1 < len(starts) else len(paragraphs)
        block = paragraphs[start:end]
        match = re.match(r"^(D\d{3})\s+(.+)$", block[0])
        if match is None or len(block) < 2:
            raise ValueError(f"Malformed definition decision block at paragraph {start}")
        document_status, final_action = _status_action(block[1])
        fields: dict[str, str] = {}
        prefixes = {
            "Current definition": "current_value",
            "Replacement definition": "recommended_value",
            "Reason": "reason",
            "Implementation": "implementation",
        }
        for line in block[2:]:
            for prefix, key in prefixes.items():
                if line.startswith(prefix):
                    fields[key] = line[len(prefix) :].strip()
                    break
        current = fields.get("current_value", "")
        recommended = fields.get("recommended_value", "")
        decisions.append(
            {
                "decision_id": match.group(1),
                "local_name": match.group(2).strip(),
                "dimension": "definition",
                "current_value": current,
                "recommended_value": recommended,
                "document_status": document_status,
                "final_action": final_action,
                "final_value": recommended if final_action == "apply" else current,
                "rationale": fields.get("reason", ""),
                "implementation": fields.get("implementation", ""),
            }
        )
    return decisions


def _local_name(iri: str) -> str:
    return iri.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _new_term(local_name: str, spec: dict[str, Any], *, kind: str) -> dict[str, Any]:
    return {
        "iri": H2KG + local_name,
        "local_name": local_name,
        "label": spec["label"],
        "alt_labels": list(spec.get("alt_labels", [])),
        "notations": [],
        "definition": spec["definition"],
        "definition_status": "structural" if kind == "structural" else "curated",
        "source_roles": [],
        "disposition": "active_local_class",
        "primary_parent": spec["parent"],
        "replacement": "",
        "migration_targets": [],
        "profile_fallback": "",
        "scope_note": spec.get("scope_note", ""),
        "governance_status": "approved",
        "correction_action": "apply",
        "evidence": "H2KG 2.2 correction registry",
    }


def _curated_definition(term: dict[str, Any]) -> str:
    """Replace the former broad fallback sentence with a scoped definition.

    This runs only in the one-time importer. The resulting sentence is frozen
    in the authoritative term registry and is never generated during release.
    """

    label = str(term["label"]).strip()
    lower = label.casefold()
    compact = re.sub(r"[^a-z0-9]", "", lower)
    parent = str(term["primary_parent"])

    suffixes = (
        ("volumefraction", "A composition characteristic expressing the volume occupied by {base} divided by the stated total reference volume."),
        ("massfraction", "A composition characteristic expressing the mass of {base} divided by the stated total reference mass."),
        ("molefraction", "A composition characteristic expressing the amount of substance of {base} divided by the stated total amount of substance."),
        ("weightpercent", "A composition characteristic expressing the mass percentage assigned to {base} on the stated reference basis."),
        ("volumepercent", "A composition characteristic expressing the volume percentage assigned to {base} on the stated reference basis."),
        ("concentration", "A composition characteristic specifying the amount of {base} per stated quantity of mixture or solution."),
        ("thickness", "A geometric characteristic specifying the distance between the opposing bounding surfaces of {base}."),
        ("diameter", "A geometric characteristic specifying the diameter of {base}."),
        ("radius", "A geometric characteristic specifying the radius of {base}."),
        ("length", "A geometric characteristic specifying the length of {base}."),
        ("width", "A geometric characteristic specifying the width of {base}."),
        ("area", "A geometric characteristic specifying the area associated with {base}."),
        ("volume", "A geometric characteristic specifying the three-dimensional volume occupied by {base}."),
        ("temperature", "A thermal characteristic specifying the temperature associated with {base}."),
        ("pressure", "A pressure characteristic specifying the pressure associated with {base}."),
        ("duration", "A temporal characteristic specifying the duration of {base}."),
        ("time", "A temporal characteristic specifying the elapsed time associated with {base}."),
        ("frequency", "A frequency characteristic specifying the repetition rate or oscillation frequency associated with {base}."),
        ("current", "An electrical characteristic specifying the electric current associated with {base}."),
        ("voltage", "An electrical characteristic specifying the electric potential difference associated with {base}."),
        ("potential", "An electrical characteristic specifying the electric or electrochemical potential associated with {base}."),
        ("resistance", "An electrical characteristic specifying resistance to electric or ionic charge transport through {base}."),
        ("conductivity", "A transport characteristic specifying the electrical or ionic conductivity of {base}."),
        ("viscosity", "A rheological characteristic specifying the resistance of {base} to flow under the stated conditions."),
        ("density", "A density characteristic specifying the stated amount of {base} per unit reference volume or area."),
        ("speed", "A rate characteristic specifying the speed associated with {base}."),
        ("velocity", "A rate characteristic specifying the velocity associated with {base}."),
        ("flowrate", "A transport characteristic specifying the quantity of {base} passing a reference boundary per unit time."),
        ("count", "A count characteristic specifying the number of {base}."),
        ("number", "A count characteristic specifying the number assigned to {base}."),
        ("energy", "An energy characteristic specifying the energy associated with {base}."),
        ("power", "A performance characteristic specifying the rate of energy transfer associated with {base}."),
        ("mass", "A quantitative characteristic specifying the mass of {base}."),
        ("torque", "A mechanical characteristic specifying the torque applied to or produced by {base}."),
        ("angle", "A geometric characteristic specifying the angle associated with {base}."),
        ("rate", "A quantitative characteristic specifying the change in {base} per stated unit of time or progression variable."),
    )
    for suffix, template in suffixes:
        if compact.endswith(suffix):
            words = label.split()
            multiword_suffixes = {
                "volumefraction",
                "massfraction",
                "molefraction",
                "weightpercent",
                "volumepercent",
                "flowrate",
            }
            suffix_word_count = 2 if suffix in multiword_suffixes else 1
            base_words = words[: max(1, len(words) - suffix_word_count)]
            base = " ".join(base_words).casefold()
            return template.format(base=base)

    if "ratio" in compact:
        return f"A dimensionless characteristic expressing the stated ratio identified as {label}."
    if "fraction" in compact or "percent" in compact:
        return f"A composition characteristic expressing the stated fractional composition identified as {label}."

    parent_labels = {
        "CompositionCharacteristic": "A composition characteristic specifying",
        "GeometricCharacteristic": "A geometric characteristic specifying",
        "TemporalCharacteristic": "A temporal characteristic specifying",
        "MorphologicalCharacteristic": "A morphological characteristic describing",
        "TransportCharacteristic": "A transport characteristic specifying",
        "ThermalCharacteristic": "A thermal characteristic specifying",
        "CountCharacteristic": "A count characteristic specifying",
        "ElectrochemicalCharacteristic": "An electrochemical characteristic specifying",
        "PressureCharacteristic": "A pressure characteristic specifying",
        "FrequencyCharacteristic": "A frequency characteristic specifying",
        "DensityCharacteristic": "A density characteristic specifying",
        "CategoricalCharacteristic": "A categorical characteristic identifying",
        "SpectroscopicCharacteristic": "A spectroscopic characteristic specifying",
        "EnergyCharacteristic": "An energy characteristic specifying",
        "SurfaceCharacteristic": "A surface characteristic describing",
        "PerformanceCharacteristic": "A performance characteristic quantifying",
        "MechanicalCharacteristic": "A mechanical characteristic specifying",
        "QuantitativeCharacteristic": "A quantitative characteristic specifying",
    }
    genus = parent_labels.get(parent, f"A {re.sub(r'(?<!^)(?=[A-Z])', ' ', parent).casefold()} representing")
    return f"{genus} {lower} under the conditions and reference basis stated with the record."


def _baseline_terms(path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, dict[str, Any]] = {}
    for source in payload["terms"]:
        local_name = source["local_name"]
        status = source.get("definition_status", "")
        if status == "curated-structural":
            definition_status = "structural"
        elif status == "source-curated":
            definition_status = "source"
        elif status.startswith("curated-"):
            definition_status = "curated"
        else:
            definition_status = "legacy"
        result[local_name] = {
            "iri": source["iri"],
            "local_name": local_name,
            "label": source["label"],
            "alt_labels": list(source.get("alt_labels", [])),
            "notations": list(source.get("notations", [])),
            "definition": source["definition"],
            "definition_status": definition_status,
            "source_roles": list(source.get("source_roles", [])),
            "disposition": source["disposition"],
            "primary_parent": _local_name(source.get("parent_iri", "")) if source.get("parent_iri") else "",
            "replacement": _local_name(source.get("replacement_iri", "")) if source.get("replacement_iri") else "",
            "migration_targets": [],
            "profile_fallback": "",
            "scope_note": "",
            "governance_status": "approved" if source["disposition"] == "active_local_class" else "legacy",
            "correction_action": "retain",
            "evidence": "H2KG 2.1 taxonomy registry",
            "module": source.get("module", "core"),
            "technology_applicability": list(source.get("technology_applicability", [])),
        }
    return result


def _apply_final_policy(
    decisions: list[dict[str, Any]],
    terms: dict[str, dict[str, Any]],
) -> None:
    by_name: dict[str, list[dict[str, Any]]] = {}
    for decision in decisions:
        by_name.setdefault(decision["local_name"], []).append(decision)

    for local_name, rows in by_name.items():
        if local_name not in terms:
            raise ValueError(f"Correction guide targets unknown class {local_name}")
        term = terms[local_name]
        for row in rows:
            if row["dimension"] == "parent":
                if term["primary_parent"] != row["current_value"]:
                    raise ValueError(
                        f"{row['decision_id']} current parent mismatch for {local_name}: "
                        f"registry={term['primary_parent']!r}, guide={row['current_value']!r}"
                    )
                if row["final_action"] == "apply":
                    term["primary_parent"] = row["final_value"]
            else:
                if term["definition"] != row["current_value"]:
                    raise ValueError(f"{row['decision_id']} current definition mismatch for {local_name}")
                if row["final_action"] == "apply":
                    term["definition"] = row["final_value"]
                    term["definition_status"] = "curated"
                elif row["final_action"] == "retain":
                    term["definition_status"] = "curated"

        unresolved = any(row["final_action"] == "deprecate_source_ambiguous" for row in rows)
        if unresolved and local_name not in REPLACEMENTS:
            term["disposition"] = "deprecated_source_ambiguous"
            term["definition_status"] = "legacy"
            term["governance_status"] = "legacy"
            term["correction_action"] = "deprecate_source_ambiguous"
            term["profile_fallback"] = term["primary_parent"]
            term["primary_parent"] = ""

    for local_name, parent in PARENT_OVERRIDES.items():
        if local_name not in terms:
            raise ValueError(f"Parent override targets unknown class {local_name}")
        terms[local_name]["primary_parent"] = parent
        if terms[local_name]["disposition"] == "active_local_class":
            terms[local_name]["correction_action"] = "apply"

    for local_name, definition in DEFINITION_OVERRIDES.items():
        if local_name not in terms:
            raise ValueError(f"Definition override targets unknown class {local_name}")
        terms[local_name]["definition"] = definition
        terms[local_name]["definition_status"] = "curated"
        terms[local_name]["correction_action"] = "apply"

    for local_name, scope_note in SCOPE_NOTE_OVERRIDES.items():
        if local_name not in terms:
            raise ValueError(f"Scope-note override targets unknown class {local_name}")
        terms[local_name]["scope_note"] = scope_note

    for local_name, replacement in REPLACEMENTS.items():
        term = terms[local_name]
        term["disposition"] = "deprecated_compatibility_class"
        term["primary_parent"] = ""
        term["replacement"] = replacement
        term["migration_targets"] = [replacement]
        term["profile_fallback"] = replacement
        term["definition_status"] = "legacy"
        term["governance_status"] = "legacy"
        term["correction_action"] = "replace"
        for row in by_name.get(local_name, []):
            row["final_action"] = "replace"
            row["final_value"] = replacement

    for local_name, targets in SPLITS.items():
        term = terms[local_name]
        term["disposition"] = "deprecated_split_class"
        term["primary_parent"] = ""
        term["replacement"] = ""
        term["migration_targets"] = targets
        term["profile_fallback"] = "QuantitativeCharacteristic"
        term["definition_status"] = "legacy"
        term["governance_status"] = "legacy"
        term["correction_action"] = "split"
        for row in by_name.get(local_name, []):
            row["final_action"] = "split"
            row["final_value"] = " | ".join(targets)

    # Terms outside the correction guide remain in scope, but their former
    # broad runtime-fallback sentences are replaced by frozen scoped text.
    corrected_names = {
        row["local_name"]
        for row in decisions
        if row["dimension"] == "definition" and row["final_action"] in {"apply", "retain"}
    } | set(DEFINITION_OVERRIDES)
    protected = set(STRUCTURAL_ADDITIONS) | set(NEW_DOMAIN_TERMS)
    for local_name, term in terms.items():
        if (
            term["disposition"] == "active_local_class"
            and term["definition_status"] == "legacy"
            and local_name not in corrected_names
            and local_name not in protected
        ):
            term["definition"] = _curated_definition(term)
            term["definition_status"] = "curated"
            term["correction_action"] = "retain"
            term["evidence"] = "Published term retained outside the 2.2 correction-guide decision set; definition normalized in the authoritative registry."


def _validate(
    decisions: list[dict[str, Any]],
    terms: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    errors: list[str] = []
    if len(decisions) != 626:
        errors.append(f"Expected 626 guide decisions, found {len(decisions)}")
    ids = [row["decision_id"] for row in decisions]
    if len(set(ids)) != len(ids):
        errors.append("Duplicate correction-guide decision IDs found")
    parent_count = sum(row["dimension"] == "parent" for row in decisions)
    definition_count = sum(row["dimension"] == "definition" for row in decisions)
    if (parent_count, definition_count) != (156, 470):
        errors.append(f"Expected 156/470 decisions, found {parent_count}/{definition_count}")
    valid_actions = {"apply", "retain", "split", "replace", "deprecate_source_ambiguous"}
    invalid_actions = sorted({row["final_action"] for row in decisions} - valid_actions)
    if invalid_actions:
        errors.append(f"Invalid final actions: {invalid_actions}")
    active_names = {
        name for name, term in terms.items() if term["disposition"] == "active_local_class"
    }
    for name in sorted(active_names):
        term = terms[name]
        if not term["definition"].strip():
            errors.append(f"Active term {name} has no definition")
        if name not in {"Matter", "Process", "InformationEntity", "Characteristic", "Agent"}:
            parent = term["primary_parent"]
            if not parent or parent not in active_names:
                errors.append(f"Active term {name} has missing or inactive parent {parent!r}")
        if term["definition_status"] not in {"source", "curated", "structural"}:
            errors.append(f"Active term {name} has invalid definition state {term['definition_status']}")
    labels: dict[str, list[str]] = {}
    for name in active_names:
        labels.setdefault(terms[name]["label"].strip().casefold(), []).append(name)
    duplicates = {label: names for label, names in labels.items() if len(names) > 1}
    if duplicates:
        errors.append(f"Duplicate active preferred labels: {duplicates}")
    return {
        "conforms": not errors,
        "errors": errors,
        "counts": {
            "decisions": len(decisions),
            "parent_decisions": parent_count,
            "definition_decisions": definition_count,
            "active_classes": len(active_names),
            "deprecated_classes": len(terms) - len(active_names),
            "source_ambiguous_deprecations": sum(
                term["disposition"] == "deprecated_source_ambiguous" for term in terms.values()
            ),
        },
    }


def build_registries(docx: Path, baseline: Path, output_dir: Path) -> dict[str, Any]:
    actual_sha = _sha256(docx)
    if actual_sha != EXPECTED_SHA256:
        raise ValueError(f"Unexpected correction-guide SHA-256: {actual_sha}")
    with zipfile.ZipFile(docx) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))
    decisions = [*_parse_parent_decisions(root), *_parse_definition_decisions(root)]
    terms = _baseline_terms(baseline)
    baseline_counts = {
        "active_classes": sum(term["disposition"] == "active_local_class" for term in terms.values()),
        "deprecated_classes": sum(term["disposition"] != "active_local_class" for term in terms.values()),
    }
    source_dependent_classes = {
        str(row["local_name"])
        for row in decisions
        if row["document_status"] in {"Confirm scope before applying", "Source information required"}
    }
    for local_name, spec in STRUCTURAL_ADDITIONS.items():
        if local_name in terms:
            raise ValueError(f"Structural addition already exists: {local_name}")
        terms[local_name] = _new_term(local_name, spec, kind="structural")
    for local_name, spec in NEW_DOMAIN_TERMS.items():
        if local_name in terms:
            raise ValueError(f"Domain addition already exists: {local_name}")
        terms[local_name] = _new_term(local_name, spec, kind="domain")
    _apply_final_policy(decisions, terms)
    validation = _validate(decisions, terms)
    if not validation["conforms"]:
        raise ValueError("Registry validation failed: " + "; ".join(validation["errors"][:12]))

    output_dir.mkdir(parents=True, exist_ok=True)
    correction_payload = {
        "schema_version": "h2kg-taxonomy-corrections/v2.2",
        "release_version": "2.2.0",
        "source_provenance": {
            "sha256": actual_sha,
            "source_type": "curated correction guide",
            "source_file_distributed": False,
        },
        "decision_counts": {
            "parent": 156,
            "definition": 470,
            "total": 626,
            "unique_classes": len({str(row["local_name"]) for row in decisions}),
            "source_dependent_classes": len(source_dependent_classes),
        },
        "baseline_counts": baseline_counts,
        "profile_migrations": PROFILE_MIGRATIONS,
        "decisions": sorted(decisions, key=lambda row: row["decision_id"]),
    }
    term_payload = {
        "schema_version": "h2kg-authoritative-term-registry/v2.2",
        "ontology_iri": "https://w3id.org/h2kg/hydrogen-ontology",
        "version": "2.2.0",
        "source_correction_sha256": actual_sha,
        "terms": [deepcopy(terms[name]) for name in sorted(terms)],
    }
    (output_dir / "h2kg_taxonomy_corrections_2_2.json").write_text(
        json.dumps(correction_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "h2kg_term_registry_2_2.json").write_text(
        json.dumps(term_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "h2kg_taxonomy_corrections_2_2_validation.json").write_text(
        json.dumps(validation, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return validation


def main() -> None:
    parser = argparse.ArgumentParser(description="Import the H2KG 2.2 correction guide into build registries.")
    parser.add_argument("docx", type=Path)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    result = build_registries(args.docx, args.baseline, args.output_dir)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
