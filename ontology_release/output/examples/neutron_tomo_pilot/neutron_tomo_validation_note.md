# NeutronTomo Validation Note

This controlled `NeutronTomo` round adds a small public neutron-tomography neighborhood to H2KG while keeping worksheet-specific facility and preprocessing detail out of the public TBox.

Introduced public ontology terms:

- `h2kg:NeutronTomographyMeasurement`
- `h2kg:NeutronTomographyInstrument`
- `h2kg:TomographicProjectionDataset`
- `h2kg:TomographicReconstructionDataset`
- `h2kg:ProjectionNumber`
- `h2kg:NeutronFlux`
- `h2kg:SpatialResolution`
- `h2kg:SampleDetectorDistance`
- `h2kg:TortuosityFactor`
- `h2kg:AverageWaterDropletArea`
- `h2kg:AverageWaterDropletCount`

Reused public ontology terms:

- `h2kg:MEAAssembly`
- `h2kg:Temperature`
- `h2kg:RelativeHumidity`
- `h2kg:PixelSize`
- `h2kg:ExposureTime`
- `h2kg:ExperimentDataset`
- `h2kg:DataPoint`
- `h2kg:Process`
- `h2kg:Manufacturing`
- `h2kg:Metadata`
- `h2kg:hasMetadata`

What remained instance metadata:

- publication and organizational fields
- facility, beamline, detector, lens, scintillator, and beam descriptors
- operando/specimen/atmosphere/pressure context
- contradictory sheet labels such as `Topic = Battery` and `Device = Lithium Battery`
- preprocessing software and workflow labels
- deferred `AverageBaryCenter` result semantics

What was intentionally deferred:

- a public TBox term for `AverageBaryCenter`
- public TBox terms for worksheet preprocessing labels such as `Reconstruct`, `DarkFieldCorrect`, `3DReconstruct`, and `Threshold`
- public TBox terms for facility-specific hardware details
- exact QUDT specialization of neutron flux beyond the reusable public parameter anchor
