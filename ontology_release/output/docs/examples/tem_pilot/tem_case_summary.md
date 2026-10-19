# Synthetic TEM Demonstration Summary

The synthetic TEM record demonstrates how H2KG represents one imaging workflow end to end. Procurement and sample-preparation steps are represented as process instances that consume and produce material instances, while the acquisition is represented as a `TransmissionElectronMicroscopyImaging` measurement linked to a `TEMInstrument`, explicit parameter records, and a raw `MicrostructureImageDataset`.

A preprocessing step converts the raw image data into a processed image dataset, and an analysis step uses `FijiImageJSoftware` to derive a synthetic result record. The illustrative particle diameter is represented as a `DataPoint` for `PdNanoparticleDiameter`, linked back to the TEM measurement through `fromMeasurement`, to the analysis process through `prov:wasGeneratedBy`, and to a local QUDT quantity-value node carrying the representative value `5 nm`.

The demonstration keeps source-specific file and contextual information as attached metadata rather than promoting one-off ontology terms. It therefore tests a conservative H2KG profile pattern while making the synthetic status of the record explicit.
