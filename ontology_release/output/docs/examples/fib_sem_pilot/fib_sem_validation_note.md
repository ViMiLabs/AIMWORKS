# FIB-SEM Validation Note

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
