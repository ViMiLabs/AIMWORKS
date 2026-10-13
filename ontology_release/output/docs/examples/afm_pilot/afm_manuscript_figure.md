# AFM Manuscript Figure Guidance

Use a combined ontology-workflow figure with **TBox-only standalone nodes** and worksheet-derived values shown only as annotations or metadata callouts.

Recommended backbone:

`Matter -> Manufacturing -> Atomic Force Microscopy Measurement -> Microstructure Image Dataset -> Process (contrast / brightness adjustment) -> Surface Topography Dataset -> Process (analysis) -> DataPoint -> Mean Particle Size`

Supporting families:

- Above acquisition:
  - `Temperature`
  - `Relative Humidity`
  - `Microscopy Measured Area`
  - `AFM Scan Speed`
  - `AFM Tip Nominal Radius`
  - `Cantilever Spring Constant`
  - `Cantilever Resonance Frequency`
- Below acquisition:
  - `AFM Instrument`
- Below analysis:
  - `Fiji ImageJ Software`
- Metadata callouts:
  - sample context
  - AFM mode/tip metadata
  - raw/processed dataset metadata
  - publication/provenance metadata

Important rule:

- Every standalone node in the figure must be retrievable from the public H2KG TBox and therefore visible in Explore after regeneration.
- Worksheet values such as `Bruker multimode 8 AFM`, `Conductive tapping`, `DLC SHR150`, `PF-TUNA module`, DOI, and file dimensions remain annotations or metadata-callout text, not standalone ontology nodes.
