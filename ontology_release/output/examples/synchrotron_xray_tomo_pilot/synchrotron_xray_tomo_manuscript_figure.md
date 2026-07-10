# Synchrotron X-Ray Tomography Manuscript Figure Guidance

Use a combined ontology-workflow figure with **TBox-only standalone nodes** and worksheet-derived values shown only as annotations or metadata callouts.

Recommended backbone:

`Matter -> Manufacturing -> X Ray Computed Tomography Measurement -> Tomographic Projection Dataset -> Process (correction / reconstruction / segmentation) -> Tomographic Reconstruction Dataset -> Process (analysis) -> DataPoint`

Supporting families:

- Above acquisition:
  - `X Ray Beam Energy`
  - `Exposure Time`
  - `Pixel Size`
  - `Projection Number`
  - `Spatial Resolution`
  - `Sample Detector Distance`
  - `Temperature`
  - `Relative Humidity`
  - `Magnification`
- Below acquisition:
  - `X Ray CT Instrument`
- Metadata callouts:
  - facility / beamline / detector / scintillator details
  - sample-holder and positioning details
  - raw file and dataset details
  - deferred output semantics for decay factor, beam-path distance, electrolyte saturation, and phase ratio

Important rule:

- Every standalone node in the figure must be retrievable from the public H2KG TBox and therefore visible in Explore after regeneration.
- Workbook values such as `Canadian Light Source`, `Orca Flash V2 sCMOS`, `YAG`, DOI, or VRFB labels remain annotations or metadata-callout text, not standalone ontology nodes.
