# Synthetic TEM Demonstration Validation Note

## Ontology changes introduced in the TEM round

- Added `h2kg:hasMetadata` as a generic metadata-attachment relation with range `h2kg:Metadata`.
- Generalized the domain of `h2kg:hasOutputData` from `h2kg:Measurement` to `h2kg:Process` so preprocessing and analysis steps can emit data cleanly.
- Added `h2kg:Magnification` as a reusable acquisition parameter.
- Added `h2kg:WorkingDistance` as a reusable acquisition parameter.
- Normalized the definition of `h2kg:MicrostructureImageDataset` so it remains generic and reusable beyond one source paper.

## What remained instance metadata in round 1

- Synthetic record, file, and access descriptors from the `org` section.
- `MeasurementType`, `Specimen`, `Atmosphere`, and `Calibration` from the `char` section.
- `MicroscopeBrand`, `Cathode`, `Probe`, `Detector`, `ImagingTechnique`, `Signal`, `TimeLapse`, `RawData`, and `DataAdquisitionRate` from the `inst` section.
- Procurement metadata such as supplier, lot number, and CAS number.

## What was intentionally deferred

- No new TBox terms were introduced for `Buy`, `Mix`, `Dispersion`, `Dry`, or `Manual particle measurement`; these remain labeled process instances.
- No dedicated metadata sub-vocabulary was introduced for every catalog field in this first round.
- `MeasurementType`, imaging mode, detector, and signal remain metadata until they are reviewed across additional imaging methods.
- The demonstration uses `PdNanoparticleDiameter` as the primary result type and does not broaden it to a generic particle-size term.

## Modeling note

The synthetic TEM demonstration follows the current H2KG release style by combining the reusable base schema (`Process`, `Measurement`, `Data`, `Metadata`, `DataPoint`) with local controlled-vocabulary anchors such as `TransmissionElectronMicroscopyImaging`, `TEMInstrument`, `MicrostructureImageDataset`, and `PdNanoparticleDiameter`.

All values are illustrative profile-test values. They are not measurements, are not attributed to a publication, and must not be used as scientific evidence.
