# XRD Manuscript Figure Guidance

Use a combined ontology-workflow figure with **TBox-only standalone nodes** and ontology-property edge labels only.

Recommended backbone:

`Matter -> Manufacturing -> X Ray Diffraction Measurement -> XRD Pattern Dataset -> Process (analysis) -> DataPoint -> {Pt Crystallite Size, Theoretical Metal Surface Area}`

Supporting ontology families:

- sample node:
  - `h2kg:CatalystPowder`
  - `h2kg:PtOnCarbonCatalyst`
- above acquisition:
  - `h2kg:XRayWavelength`
  - `h2kg:XRDStepSize`
  - `h2kg:XRDTwoThetaStart`
  - `h2kg:XRDTwoThetaEnd`
- below acquisition:
  - `h2kg:XRayDiffractometer`
- analysis-side measured outputs:
  - `h2kg:DiffractionPeakPosition2Theta`
  - `h2kg:XRDPeakFWHM`
  - `h2kg:PtCrystalliteSize`
  - `h2kg:TheoreticalMetalSurfaceArea`
- metadata callouts:
  - supplier / lot / Pt wt.% context
  - holder / run-record context
  - Scherrer-assumption note

Important figure rule:

- do not draw worksheet-style procedural labels as standalone nodes
- use annotations such as `powder loading`, `Pt(111) peak`, or `Scherrer-style analysis` only inside callouts or subtitles
- do not make example datapoint values public ontology nodes
