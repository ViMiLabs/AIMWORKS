from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "input" / "current_ontology.jsonld"
EXPLORER = ROOT / "output" / "docs" / "data" / "explorer.json"
H2KG = "https://w3id.org/h2kg/hydrogen-ontology#"


def _load_index() -> dict[str, dict]:
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    items = payload["@graph"] if "@graph" in payload else payload
    return {
        item["@id"]: item
        for item in items
        if isinstance(item, dict) and isinstance(item.get("@id"), str)
    }


def _refs(item: dict, predicate: str) -> set[str]:
    values = item.get(predicate, [])
    if not isinstance(values, list):
        values = [values]
    result: set[str] = set()
    for entry in values:
        if isinstance(entry, dict) and isinstance(entry.get("@id"), str):
            result.add(entry["@id"])
    return result


def _literal_values(item: dict, predicate: str) -> list[str]:
    values = item.get(predicate, [])
    if not isinstance(values, list):
        values = [values]
    result: list[str] = []
    for entry in values:
        if isinstance(entry, dict) and "@value" in entry:
            result.append(str(entry["@value"]))
        elif isinstance(entry, str):
            result.append(entry)
    return result


def _item(index: dict[str, dict], local_name: str) -> dict:
    return index[f"{H2KG}{local_name}"]


def test_sampledb_review_manufacturing_chain_is_normalized() -> None:
    index = _load_index()

    screen = _item(index, "ScreenPrinting")
    screen_outputs = _refs(screen, f"{H2KG}hasOutputMaterial")
    screen_parameters = _refs(screen, f"{H2KG}hasParameter")
    assert f"{H2KG}CatalystCoatedMembrane" not in screen_outputs
    assert f"{H2KG}CathodeCatalystLayer" in screen_outputs
    assert f"{H2KG}AnodeCatalystLayer" in screen_outputs
    for local in [
        "ScreenMeshCount",
        "ScreenMeshThickness",
        "ScreenTension",
        "ScreenWireDiameter",
        "SnapOffDistance",
        "SqueegeePressure",
    ]:
        assert f"{H2KG}{local}" in screen_parameters

    decal = _item(index, "DecalTransfer")
    assert _refs(decal, f"{H2KG}hasOutputMaterial") == {f"{H2KG}CatalystCoatedMembrane"}

    hot_pressing = _item(index, "HotPressing")
    hot_press_outputs = _refs(hot_pressing, f"{H2KG}hasOutputMaterial")
    assert f"{H2KG}CatalystCoatedMembrane" in hot_press_outputs
    assert f"{H2KG}MEAAssembly" not in hot_press_outputs

    mea_assembly_process = _item(index, "MEAAssemblyProcess")
    assert _refs(mea_assembly_process, f"{H2KG}hasOutputMaterial") == {f"{H2KG}MEAAssembly"}
    mea_inputs = _refs(mea_assembly_process, f"{H2KG}hasInputMaterial")
    for local in ["CatalystCoatedMembrane", "ProtonExchangeMembrane", "GasDiffusionLayer", "Gasket"]:
        assert f"{H2KG}{local}" in mea_inputs
    assert f"{H2KG}CatalystInk" not in mea_inputs
    assert _refs(mea_assembly_process, f"{H2KG}usesInstrument") == {f"{H2KG}TorqueWrench"}


def test_sampledb_review_operations_and_analysis_are_explicit() -> None:
    index = _load_index()

    break_in = _item(index, "BreakInProcedure")
    break_in_types = set(break_in.get("@type", []))
    assert f"{H2KG}Process" in break_in_types
    assert f"{H2KG}Manufacturing" not in break_in_types
    assert _refs(break_in, f"{H2KG}hasOutputData") == {f"{H2KG}BreakInDataset"}
    break_in_parameters = _refs(break_in, f"{H2KG}hasParameter")
    for local in [
        "SetCurrentDensity",
        "OperatingVoltage",
        "AnodeGasComposition",
        "CathodeGasComposition",
        "AnodeGasVolumetricFlowRate",
        "CathodeGasVolumetricFlowRate",
    ]:
        assert f"{H2KG}{local}" in break_in_parameters

    ast = _item(index, "AcceleratedStressTestVoltageCycling")
    ast_types = set(ast.get("@type", []))
    assert f"{H2KG}Process" in ast_types
    assert f"{H2KG}Manufacturing" not in ast_types
    assert f"{H2KG}Measurement" in ast_types
    assert _refs(ast, f"{H2KG}hasOutputData") == {f"{H2KG}ASTDataset"}

    fuel_pol = _item(index, "FuelCellPolarizationMeasurement")
    assert _refs(fuel_pol, f"{H2KG}hasOutputData") == {f"{H2KG}PolarizationCurveDataset"}
    assert f"{H2KG}PolarizationCurveAnalysis" in _refs(fuel_pol, f"{H2KG}hasSubProcess")
    fuel_pol_parameters = _refs(fuel_pol, f"{H2KG}hasParameter")
    assert fuel_pol_parameters == {
        f"{H2KG}AnodeGasComposition",
        f"{H2KG}CathodeGasComposition",
        f"{H2KG}AnodeGasVolumetricFlowRate",
        f"{H2KG}CathodeGasVolumetricFlowRate",
        f"{H2KG}AnodeStoichiometricRatio",
        f"{H2KG}CathodeStoichiometricRatio",
        f"{H2KG}CellActiveArea",
        f"{H2KG}CellPressure",
        f"{H2KG}HumidifierTemperature",
        f"{H2KG}OperatingTemperature",
        f"{H2KG}PolarizationPointDuration",
        f"{H2KG}RelativeHumidityOperation",
    }
    fuel_pol_measures = _refs(fuel_pol, f"{H2KG}measures")
    assert f"{H2KG}CurrentDensity" in fuel_pol_measures
    assert f"{H2KG}CellVoltage" in fuel_pol_measures
    assert f"{H2KG}CurrentDensity" not in fuel_pol_parameters
    assert f"{H2KG}CellVoltage" not in fuel_pol_parameters
    for local in [
        "IonomerToCarbonRatio",
        "IsopropanolVolumeFractionInSolventMixture",
        "CatalystLoadingPattern",
        "IonomerMassFraction",
        "GasComposition",
        "GasVolumetricFlowRate",
        "GasFlowRate",
    ]:
        assert f"{H2KG}{local}" not in fuel_pol_parameters

    mea_pol = _item(index, "MEAPolarization")
    assert "true" in {value.lower() for value in _literal_values(mea_pol, "http://www.w3.org/2002/07/owl#deprecated")}
    assert _refs(mea_pol, "http://www.w3.org/2000/01/rdf-schema#seeAlso") == {
        f"{H2KG}FuelCellPolarizationMeasurement"
    }
    for predicate in [
        f"{H2KG}hasInputMaterial",
        f"{H2KG}hasOutputData",
        f"{H2KG}hasParameter",
        f"{H2KG}hasSubProcess",
        f"{H2KG}measures",
        f"{H2KG}usesInstrument",
        f"{H2KG}referenceElectrode",
    ]:
        assert predicate not in mea_pol

    cv = _item(index, "CyclicVoltammetry")
    cv_outputs = _refs(cv, f"{H2KG}hasOutputData")
    assert f"{H2KG}CyclicVoltammogramDataset" in cv_outputs
    assert f"{H2KG}ECSADataset" not in cv_outputs
    assert f"{H2KG}PolarizationCurveDataset" not in cv_outputs
    cv_parameters = _refs(cv, f"{H2KG}hasParameter")
    for local in ["GasComposition", "GasVolumetricFlowRate", "GasFlowRate", "CatalystLoading", "PtLoading"]:
        assert f"{H2KG}{local}" not in cv_parameters

    coating_weight = _item(index, "CoatingWeightMeasurement")
    assert _refs(coating_weight, f"{H2KG}usesInstrument") == {f"{H2KG}AnalyticalBalance"}
    assert _refs(coating_weight, f"{H2KG}measures") == {
        f"{H2KG}PtLoading",
        f"{H2KG}SpecificLayerWeight",
    }

    thickness = _item(index, "CatalystLayerThicknessMeasurement")
    assert _refs(thickness, f"{H2KG}measures") == {
        f"{H2KG}AnodeCatalystLayerThickness",
        f"{H2KG}CathodeCatalystLayerThickness",
        f"{H2KG}MembraneThickness",
    }

    eis_galv = _item(index, "ElectrochemicalImpedanceSpectroscopyGalvanostatic")
    eis_galv_parameters = _refs(eis_galv, f"{H2KG}hasParameter")
    for local in [
        "GasComposition",
        "GasVolumetricFlowRate",
        "GasFlowRate",
        "CatalystLoading",
        "CatalystLayerThickness",
        "IonomerFilmThickness",
        "ReactionAreaPositionInCatalystLayer",
    ]:
        assert f"{H2KG}{local}" not in eis_galv_parameters

    eis_pot = _item(index, "ElectrochemicalImpedanceSpectroscopyPotentiostatic")
    eis_pot_parameters = _refs(eis_pot, f"{H2KG}hasParameter")
    for local in [
        "GasComposition",
        "GasVolumetricFlowRate",
        "GasFlowRate",
        "CatalystLoading",
        "IonomerMassFraction",
        "IonomerToCarbonRatio",
        "SolventType",
    ]:
        assert f"{H2KG}{local}" not in eis_pot_parameters


def test_sampledb_review_public_anchors_and_explorer_links_exist() -> None:
    index = _load_index()
    for local in [
        "ProtonExchangeMembrane",
        "GasDiffusionLayer",
        "Gasket",
        "FlowField",
        "BreakInDataset",
        "ASTDataset",
        "EquivalentCircuitFitting",
        "PolarizationCurveAnalysis",
        "LayerThicknessAnalysis",
        "CoatingWeightCalculation",
    ]:
        assert f"{H2KG}{local}" in index

    station = _item(index, "FuelCellTestStation")
    assert _refs(station, f"{H2KG}hasPart") == {
        f"{H2KG}FuelCellTestCell",
        f"{H2KG}GasHumidificationUnit",
        f"{H2KG}MassFlowController",
        f"{H2KG}Cryostat",
        f"{H2KG}ElectricLoad",
    }

    cell = _item(index, "FuelCellTestCell")
    assert _refs(cell, f"{H2KG}hasPart") == {
        f"{H2KG}MEAAssembly",
        f"{H2KG}Gasket",
        f"{H2KG}GraphiteBipolarPlate",
        f"{H2KG}FlowField",
    }

    explorer = json.loads(EXPLORER.read_text(encoding="utf-8"))
    node_ids = {node["id"] for node in explorer["nodes"]}
    for local in [
        "ProtonExchangeMembrane",
        "GasDiffusionLayer",
        "BreakInProcedure",
        "AcceleratedStressTestVoltageCycling",
        "PolarizationCurveAnalysis",
    ]:
        assert f"{H2KG}{local}" in node_ids

    links = {
        (link["source"], link["target"], link["predicate"])
        for link in explorer["links"]
    }
    assert (
        f"{H2KG}FuelCellPolarizationMeasurement",
        f"{H2KG}PolarizationCurveAnalysis",
        f"{H2KG}hasSubProcess",
    ) in links
    assert (
        f"{H2KG}PolarizationCurveAnalysis",
        f"{H2KG}MEAPolarization",
        f"{H2KG}isSubProcessOf",
    ) not in links
    assert (
        f"{H2KG}FuelCellTestStation",
        f"{H2KG}FuelCellTestCell",
        f"{H2KG}hasPart",
    ) in links


def test_sampledb_review_tbox_process_relations_are_disciplined() -> None:
    index = _load_index()
    process_like_types = {f"{H2KG}Process", f"{H2KG}Manufacturing", f"{H2KG}Measurement"}
    process_predicates = {
        f"{H2KG}hasInputMaterial",
        f"{H2KG}hasOutputMaterial",
        f"{H2KG}hasParameter",
        f"{H2KG}usesInstrument",
    }

    for item in index.values():
        types = set(item.get("@type", []))
        if types & process_like_types:
            continue
        for predicate in process_predicates:
            assert predicate not in item, f"{item['@id']} still carries {predicate} without a process-like type"
        if f"{H2KG}measures" in item:
            assert f"{H2KG}Measurement" in types, f"{item['@id']} still carries h2kg:measures without h2kg:Measurement"
