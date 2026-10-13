# NeutronTomo Manuscript Figure Guidance

Use a combined ontology-workflow figure with **TBox-only standalone nodes** and worksheet-derived values shown only as annotations or metadata callouts.

Recommended backbone:

`Matter -> Manufacturing -> Neutron Tomography Measurement -> Tomographic Projection Dataset -> Process (reconstruction / preprocessing) -> Tomographic Reconstruction Dataset -> Process (analysis) -> DataPoint -> {Tortuosity Factor, Average Water Droplet Area, Average Water Droplet Count}`

Supporting families:

- Above acquisition:
  - `Pixel Size`
  - `Exposure Time`
  - `Projection Number`
  - `Neutron Flux`
  - `Spatial Resolution`
  - `Sample Detector Distance`
  - `Temperature`
  - `Relative Humidity`
- Below acquisition:
  - `Neutron Tomography Instrument`
- Metadata callouts:
  - MEA assembly and holder context
  - beamline, detector, and scintillator details
  - raw and reconstructed dataset details
  - publication/provenance details
  - deferred `AverageBaryCenter` note

Important rule:

- Every standalone node in the figure must be retrievable from the public H2KG TBox and therefore visible in Explore after regeneration.
- Worksheet values such as `NeXT Beamline`, `GADOX`, `Astra Toolbox`, `Avizo`, DOI, file dimensions, and contradictory battery/device labels remain annotations or metadata-callout text, not standalone ontology nodes.
