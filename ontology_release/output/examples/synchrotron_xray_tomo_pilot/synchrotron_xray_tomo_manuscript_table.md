# Synchrotron X-Ray Tomography Manuscript Table Guidance

Recommended columns:

- Scientific case element
- H2KG ontology anchor
- Example workbook value
- Figure treatment

Recommended rows:

| Scientific case element | H2KG ontology anchor | Example workbook value | Figure treatment |
| --- | --- | --- | --- |
| Sample/material context | `h2kg:Matter` | Carbon felt electrode; dry-electrode sample | standalone ontology node with metadata callout |
| Sample conditioning | `h2kg:Manufacturing` | Heat, cool, cut | standalone ontology node with example annotation |
| CT acquisition | `h2kg:XRayComputedTomographyMeasurement` | Synchrotron X-ray tomography | standalone ontology node |
| CT instrument | `h2kg:XRayCTInstrument` | BMIT-ID / detector / scintillator stack | standalone ontology node with metadata callout |
| X-ray beam energy | `h2kg:XRayBeamEnergy` | 30 keV | parameter callout |
| Exposure time | `h2kg:ExposureTime` | 50 ms | parameter callout |
| Pixel size | `h2kg:PixelSize` | 13 um | parameter callout |
| Projection number | `h2kg:ProjectionNumber` | 2000 | parameter callout |
| Spatial resolution | `h2kg:SpatialResolution` | 1 um | parameter callout |
| Sample-detector distance | `h2kg:SampleDetectorDistance` | 40 cm | parameter callout |
| Temperature | `h2kg:Temperature` | 23 deg C | parameter callout |
| Relative humidity | `h2kg:RelativeHumidity` | 50 % | parameter callout |
| Magnification | `h2kg:Magnification` | 10 | parameter callout |
| Raw data | `h2kg:TomographicProjectionDataset` | TestTomography.tif | standalone ontology node |
| Preprocessing | `h2kg:Process` | Convert, dark-field correction, flat-field correction, 3D reconstruction, segmentation | standalone ontology node with annotation |
| Reconstructed data | `h2kg:TomographicReconstructionDataset` | Post-processed tomograph | standalone ontology node |
| Analysis | `h2kg:Process` | Decay-factor, beam-path, saturation, and phase-ratio analysis | standalone ontology node with annotation |
| Deferred outputs | `h2kg:DataPoint` | 51 ms; 99 cm; 47 mol/l; 0.12640046296296295 | standalone ontology node with metadata callout |
