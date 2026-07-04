# TEM Case Summary

The TEM pilot demonstrates that H2KG can capture one imaging workflow end to end without uncontrolled ontology growth. Procurement and sample-preparation steps are represented as process instances that consume and produce material instances, while the TEM acquisition itself is represented as a `TransmissionElectronMicroscopyImaging` measurement linked to a `TEMInstrument`, explicit acquisition-parameter settings, and a raw `MicrostructureImageDataset`.

A preprocessing step converts the raw image data into a processed image dataset, and an analysis step uses `FijiImageJSoftware` to derive the final scientific result. The reported average particle size is represented as a `DataPoint` for `PdNanoparticleDiameter`, linked back to the TEM measurement through `fromMeasurement`, to the analysis process through `prov:wasGeneratedBy`, and to a local QUDT quantity-value node carrying the numeric value `5 nm`.

This pilot keeps publication, file, author, and organizational information as attached metadata rather than promoting dozens of one-off ontology terms. It therefore shows a conservative H2KG extension pattern that is rich enough for provenance and querying, but disciplined enough to remain compatible with the existing release model.
