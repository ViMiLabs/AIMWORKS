# IC-SEM Manuscript Companion Table

| IC-SEM case element | H2KG ontology anchor | Example case value | Figure treatment |
| --- | --- | --- | --- |
| Sample context | `h2kg:Matter` | doctor-bladed MEA sample | standalone ontology node |
| Coating route | `h2kg:DoctorBladeCoating` | doctor blade | standalone ontology node |
| Drying controls | `h2kg:DryingTemperature`, `h2kg:DryingTime` | 80 °C; 16 h | parameter callout |
| Measurement route | `h2kg:ICSEMImagingMeasurement` | IC-SEM | standalone ontology node |
| Instrument | `h2kg:ICSEMInstrument` | Jeol cross-section polisher + SEM stack | standalone ontology node with metadata callout |
| Acquisition geometry | `h2kg:CutThickness`, `h2kg:MicroscopyMeasuredArea`, `h2kg:PixelSize` | 150 nm; 20 um2; 20 nm | parameter callout |
| Beam settings | `h2kg:IonBeamCurrent`, `h2kg:IonBeamEnergy`, `h2kg:ElectronCurrent`, `h2kg:ElectronBeamEnergy` | 700 pA; 6 keV; 250 pA; 1.5 keV | parameter callout |
| Acquisition timing | `h2kg:DwellTime`, `h2kg:ExposureTime`, `h2kg:TotalAcquisitionTime` | 12 h; 60 s; 12 h | parameter callout |
| Environment | `h2kg:Temperature`, `h2kg:RelativeHumidity`, `h2kg:VacuumChamberPressure` | 25 °C; 0 %; 10^-6 atm | parameter callout |
| Raw data | `h2kg:SEMImageDataset` | ICSEM.zip | standalone ontology node |
| Preprocessing | `h2kg:Process` | thresholding; scale set | standalone ontology node with annotation |
| Processed data | `h2kg:SEMMicrographDataset`, `h2kg:MicrostructureImageDataset` | post-processed image | standalone ontology node |
| Analysis | `h2kg:Process` | layer-thickness analysis; porosity analysis | standalone ontology node with annotation |
| Thickness result | `h2kg:MembraneElectrodeAssemblyThickness` | 80 nm | final property node via datapoint |
| GDL result | `h2kg:GasDiffusionLayerThickness` | 160 nm | final property node via datapoint |
| Porosity result | `h2kg:TotalPorosity` | 6 pu | final property node via datapoint |
| Software | `h2kg:FijiImageJSoftware` | ImageJ | supporting ontology node |
| Provenance | `h2kg:Metadata` + `h2kg:hasMetadata` | DOI, authors, file details | metadata callout |
