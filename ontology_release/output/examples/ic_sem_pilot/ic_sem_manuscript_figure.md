# IC-SEM Manuscript Figure Guidance

Use a combined ontology-workflow figure with **TBox-only standalone nodes** and worksheet-derived values shown only as annotations or metadata callouts.

Recommended backbone:

`Matter -> Manufacturing -> IC-SEM Imaging Measurement -> SEM Image Dataset -> Process (thresholding / scale set) -> SEM Micrograph Dataset -> Process (analysis) -> DataPoint -> {Membrane Electrode Assembly Thickness, Gas Diffusion Layer Thickness, Total Porosity}`

Supporting families:

- Above acquisition:
  - `Temperature`
  - `Relative Humidity`
  - `Vacuum Chamber Pressure`
  - `Dwell Time`
  - `Magnification`
  - `Pixel Size`
  - `Microscopy Measured Area`
  - `Exposure Time`
  - `Ion Beam Current`
  - `Ion Beam Energy`
  - `Electron Current`
  - `Electron Beam Energy`
  - `Cut Thickness`
  - `Total Acquisition Time`
- Below acquisition:
  - `IC-SEM Instrument`
- Below preprocessing and analysis:
  - `Fiji ImageJ Software`
- Metadata callouts:
  - sample context
  - acquisition context
  - instrument metadata
  - raw/processed dataset metadata
  - publication/provenance metadata
