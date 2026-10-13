# XPS Manuscript Figure Guidance

Use a combined ontology-workflow figure with **TBox-only standalone nodes** and ontology-property edge labels only.

Recommended backbone:

`Matter -> Manufacturing -> X Ray Photoelectron Spectroscopy Measurement -> XPS Dataset -> Process (analysis) -> DataPoint -> {Binding Energy, C 1 s Atomic Percent, O 1 s Atomic Percent, F 1 s Atomic Percent, N 1 s Atomic Percent, Carbon To Oxygen Atom Ratio, Metal Atomic Percent}`

Supporting ontology families:

- sample-side matter anchors:
  - `h2kg:CatalystPowder`
  - `h2kg:PtOnCarbonCatalyst`
  - `h2kg:CatalystInk`
  - `h2kg:PFSAIonomer`
- above acquisition:
  - `h2kg:XPSPassEnergy`
  - `h2kg:XPSTakeOffAngle`
  - `h2kg:XPSAnalysisArea`
- below acquisition:
  - `h2kg:XPSInstrument`
- metadata callouts:
  - source / anode details
  - charge-neutralization and calibration notes
  - file / acquisition-record metadata
  - fit-specific deconvolution notes

Important figure rule:

- do not draw deconvolution fractions or state-specific ratios as standalone nodes in this generic XPS figure
- use labels such as `survey + high-resolution spectra` or `peak fitting and quantification` only as annotations or subtitles
- do not make numeric example values public ontology nodes
