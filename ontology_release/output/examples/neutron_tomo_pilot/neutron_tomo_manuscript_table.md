# NeutronTomo Manuscript Companion Table

| NeutronTomo case element | H2KG ontology anchor | Example case value | Figure treatment |
| --- | --- | --- | --- |
| Sample context | `h2kg:Matter` / `h2kg:MEAAssembly` | operando MEA assembly | standalone ontology node |
| Assembly route | `h2kg:Manufacturing` | buy, laser cut, hot press, mount, integrate | standalone ontology node with annotation |
| Neutron acquisition | `h2kg:NeutronTomographyMeasurement` | HR neutron CT | standalone ontology node |
| Neutron instrument | `h2kg:NeutronTomographyInstrument` | ILL NeXT beamline setup | standalone ontology node with metadata callout |
| Pixel size | `h2kg:PixelSize` | 63.6 um | parameter callout |
| Exposure time | `h2kg:ExposureTime` | 9 s | parameter callout |
| Projection number | `h2kg:ProjectionNumber` | 1440 | parameter callout |
| Neutron flux | `h2kg:NeutronFlux` | 2.7 x 10^6 n/cm2s | parameter callout |
| Spatial resolution | `h2kg:SpatialResolution` | 300 um | parameter callout |
| Sample-detector distance | `h2kg:SampleDetectorDistance` | 50 mm | parameter callout |
| Acquisition environment | `h2kg:Temperature`, `h2kg:RelativeHumidity` | 23 °C; 50 % | parameter callout |
| Raw tomography data | `h2kg:TomographicProjectionDataset` | TestNeutronTomography.tif | standalone ontology node |
| Preprocessing | `h2kg:Process` | reconstruct, dark-field correction, 3D reconstruction, threshold | standalone ontology node with annotation |
| Reconstructed tomograph | `h2kg:TomographicReconstructionDataset` | post-processed tomograph | standalone ontology node |
| Analysis | `h2kg:Process` | tortuosity analysis; droplet analysis | standalone ontology node with annotation |
| Derived tortuosity result | `h2kg:TortuosityFactor` | 1.5 | final property node via datapoint |
| Derived droplet-area result | `h2kg:AverageWaterDropletArea` | 45 cm2 | final property node via datapoint |
| Derived droplet-count result | `h2kg:AverageWaterDropletCount` | 45 | final property node via datapoint |
| Deferred ambiguous result | `h2kg:Metadata` | AverageBaryCenter = 5 | metadata callout |
| Provenance | `h2kg:Metadata` + `h2kg:hasMetadata` | DOI, authors, facility, file details | metadata callout |
