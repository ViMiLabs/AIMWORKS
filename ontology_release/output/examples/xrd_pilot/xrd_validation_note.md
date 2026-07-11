# XRD Validation Note

This controlled XRD round reuses the existing H2KG XRD public vocabulary rather than adding a second XRD method node.

Implemented normalization:

- `h2kg:XRayDiffractionMeasurement` remains the canonical public XRD method node.
- The direct public XRD neighborhood was cleaned to the PEMFC Pt/C catalyst powder pattern only:
  - `usesInstrument -> h2kg:XRayDiffractometer`
  - `hasInputMaterial -> h2kg:CatalystPowder`, `h2kg:PtOnCarbonCatalyst`
  - `hasOutputData -> h2kg:XRDPatternDataset`, `h2kg:ExperimentDataset`
  - `hasParameter -> h2kg:XRayWavelength`, `h2kg:XRDStepSize`, `h2kg:XRDTwoThetaStart`, `h2kg:XRDTwoThetaEnd`
  - `measures -> h2kg:DiffractionPeakPosition2Theta`, `h2kg:XRDPeakFWHM`, `h2kg:PtCrystalliteSize`, `h2kg:TheoreticalMetalSurfaceArea`
- `h2kg:XRayDiffractometer` and `h2kg:XRDPatternDataset` definitions were broadened to reusable catalyst/electrode characterization wording.

Intentionally deferred:

- public promotion of XRD-specific analysis classes such as Scherrer analysis, phase identification, or Rietveld refinement
- broader non-PEMFC XRD cleanup outside the direct public measurement neighborhood
- any public ABox example nodes in Explore
