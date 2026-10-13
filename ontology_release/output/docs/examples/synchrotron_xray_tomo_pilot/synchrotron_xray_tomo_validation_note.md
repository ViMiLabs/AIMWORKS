# Synchrotron X-Ray Tomography Validation Note

This controlled round does not introduce a new public synchrotron-branded measurement node. Instead, it normalizes the existing public CT neighborhood around `h2kg:XRayComputedTomographyMeasurement`.

Public ontology changes in this round:

- no new public TBox terms added
- normalized `h2kg:XRayComputedTomographyMeasurement`
- normalized `h2kg:XRayCTInstrument`
- broadened `h2kg:TomographicProjectionDataset`
- broadened `h2kg:TomographicReconstructionDataset`
- broadened `h2kg:PixelSize` so it can support tomography-detector usage as well as microscopy usage

What remained metadata or example-instance content:

- VRFB and dry-electrode study context
- beamline, detector, scintillator, and holder details
- acquisition descriptors such as fly-scan mode, flat fields, dark fields, and time-lapse settings
- worksheet preprocessing labels such as `Convert`, `DarkFieldCorrect`, `FlatFieldCorrect`, `BackgroundCorrect`, `3DReconstruct`, and `ManualSegment`
- worksheet analysis labels such as `DecayFactorCalculation`, `BeamPathDistanceMeasurement`, `ElectrolyteSaturationMeasurement`, and `ElectrodeSegmentRatioCalculation`

What was intentionally deferred:

- no new public property term for decay factor
- no new public property term for beam-path distance
- no new public property term for electrolyte saturation
- no new public property term for the carbonfelt/electrolyte/air ratio
- no separate public `SynchrotronXRayTomographyMeasurement` node
- no separate public `SynchrotronRadiographyMeasurement` node
