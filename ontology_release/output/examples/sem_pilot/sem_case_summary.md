# SEM Case Summary

The SEM pilot demonstrates how H2KG can represent an imaging workflow from sample preparation through acquisition, image preprocessing, and derived analysis without introducing unnecessary ontology growth. The acquisition itself is represented as a `ScanningElectronMicroscopyImaging` measurement linked to a `SEMInstrument`, explicit acquisition-parameter settings such as accelerating voltage, magnification, working distance, temperature, and relative humidity, and a raw `SEMImageDataset`.

Two preprocessing steps, contrast adjustment and brightness adjustment, transform the raw dataset into a processed SEM micrograph dataset. An analysis step uses `FijiImageJSoftware` to derive the intended scientific output as a `DataPoint` for `CatalystParticleDiameter`, linked back to the measurement through `fromMeasurement` and to the analysis process through `prov:wasGeneratedBy`.

The source sheet does not provide a numeric average-size value. H2KG therefore captures the semantic result node and its provenance cleanly while preserving the absence of a reported quantity value rather than inventing one. This is important for later cross-method integration, because it keeps the ontology faithful to what was actually reported while still making the intended analytical target queryable.
