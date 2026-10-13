# XPS Validation Note

This controlled XPS round reuses the existing H2KG XPS public vocabulary rather than adding a second XPS method node.

Implemented normalization:

- `h2kg:XRayPhotoelectronSpectroscopyMeasurement` remains the canonical public XPS method node.
- The direct public XPS neighborhood was cleaned to a PEMFC-focused generic pattern:
  - `usesInstrument -> h2kg:XPSInstrument`
  - `hasInputMaterial -> h2kg:CatalystPowder`, `h2kg:PtOnCarbonCatalyst`, `h2kg:CatalystInk`, `h2kg:PFSAIonomer`
  - `hasOutputData -> h2kg:XPSDataset`, `h2kg:ExperimentDataset`
  - `hasParameter -> h2kg:XPSPassEnergy`, `h2kg:XPSTakeOffAngle`, `h2kg:XPSAnalysisArea`
  - `measures -> h2kg:BindingEnergy`, `h2kg:C1sAtomicPercent`, `h2kg:O1sAtomicPercent`, `h2kg:F1sAtomicPercent`, `h2kg:N1sAtomicPercent`, `h2kg:CarbonToOxygenAtomRatio`, `h2kg:MetalAtomicPercent`
- `h2kg:BindingEnergy`, `h2kg:XPSInstrument`, and `h2kg:XPSDataset` definitions were broadened to reusable PEMFC-oriented XPS wording.
- `h2kg:XRayPhotoelectronSpectrometer` remains in the ontology as a legacy synonym anchor but is no longer used as a direct public instrument link from the measurement node.

Intentionally deferred:

- direct public exposure of many fit-specific, state-specific, or study-specific XPS outputs on the generic XPS method node
- public promotion of survey/high-resolution mode vocabulary, charge-neutralization settings, or calibration-reference terms
- any public ABox example nodes in Explore
