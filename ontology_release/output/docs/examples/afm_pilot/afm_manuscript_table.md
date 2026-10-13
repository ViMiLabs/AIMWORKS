# AFM Manuscript Companion Table

| AFM case element | H2KG ontology anchor | Example case value | Figure treatment |
| --- | --- | --- | --- |
| Sample context | `h2kg:Matter` / `h2kg:MEAAssembly` | PEMFC MEA / catalyst-layer context | standalone ontology node |
| Drying route | `h2kg:Manufacturing` + `h2kg:DryingTemperature` + `h2kg:DryingTime` | 100 deg C; 10 h | ontology node + parameter callout |
| Mounting/sectioning route | `h2kg:Manufacturing` | cut, embed, cure, microtome, fix | standalone ontology node with annotation |
| AFM acquisition | `h2kg:AtomicForceMicroscopyMeasurement` | AFM | standalone ontology node |
| AFM instrument | `h2kg:AFMInstrument` | Bruker multimode 8 AFM | standalone ontology node with metadata callout |
| AFM acquisition area | `h2kg:MicroscopyMeasuredArea` | 1 um2 | parameter callout |
| AFM scan speed | `h2kg:AFMScanSpeed` | 0.488 Hz | parameter callout |
| AFM tip radius | `h2kg:AFMTipNominalRadius` | 1 nm | parameter callout |
| AFM environment | `h2kg:Temperature`, `h2kg:RelativeHumidity` | 23 deg C; 80 % | parameter callout |
| Raw image data | `h2kg:MicrostructureImageDataset` | afm_rawdata.tif | standalone ontology node |
| Preprocessing | `h2kg:Process` | contrast adjustment; brightness adjustment | standalone ontology node with annotation |
| Processed topography/image data | `h2kg:SurfaceTopographyDataset`, `h2kg:MicrostructureImageDataset` | post-processed image | standalone ontology node |
| Analysis | `h2kg:Process` | manual particle measurement | standalone ontology node with annotation |
| Analysis software | `h2kg:FijiImageJSoftware` | ImageJ | supporting ontology node |
| Final result | `h2kg:MeanParticleSize` | 110 um | final property node via datapoint |
| Provenance | `h2kg:Metadata` + `h2kg:hasMetadata` | DOI, authors, file details | metadata callout |
