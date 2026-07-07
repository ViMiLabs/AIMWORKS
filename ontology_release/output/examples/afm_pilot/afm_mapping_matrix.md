# AFM Mapping Matrix

This matrix accounts for each populated AFM sheet field and classifies it as `reuse existing term`, `new ontology term`, `instance metadata`, or `not modeled` for the controlled AFM round.

| Section | Field | Example value | Classification | H2KG anchor | Note |
| --- | --- | --- | --- | --- | --- |
| org | ExperimentTitle | Quantitative in Situ Analysis of Ionomer Structure in Fuel Cell catalytic layer | instance metadata | h2kg:hasMetadata + dcterms:title | Stored on the AFM source-record metadata node. |
| org | ExperimentID | 5 | instance metadata | h2kg:hasMetadata + h2kg:hasIdentifier | Stored as a literal identifier on the source record. |
| org | Measurement-ID | Run derived DOI | instance metadata | h2kg:hasMetadata + h2kg:hasIdentifier | Stored on AFM measurement metadata. |
| org | UploadDate | 2023-10-11 | instance metadata | h2kg:hasMetadata + dcterms:date | Excel serial normalized to ISO date. |
| org | Institution | DLR | instance metadata | prov:Agent | Represented as an institutional agent. |
| org | FoundingBody | HIP | instance metadata | prov:Agent | Represented as a funding-body agent. |
| org | Country | Germany | instance metadata | h2kg:hasMetadata | Retained as contextual metadata. |
| org | Author | Tobias Morawitz; Andre Colliard Granero | instance metadata | prov:Agent | Represented as author agent instances. |
| org | ORCID | 123-465-7777; 321-321-3211 | instance metadata | h2kg:hasMetadata | Stored on author metadata nodes. |
| org | Email | tobi.mora@dlr.de; andyhuebsch@gmail.mx | instance metadata | h2kg:hasMetadata | Stored on author metadata nodes. |
| org | Published | 1 | instance metadata | h2kg:hasMetadata | Retained as publication-status metadata. |
| org | Publication | Quantitative in Situ Analysis of Ionomer Structure in Fuel Cell catalytic layer | instance metadata | h2kg:hasMetadata + dcterms:title | Stored on a publication metadata node. |
| org | DOI | https://doi.org/10.3390/afm38383 | instance metadata | h2kg:hasMetadata + dcterms:identifier | Stored on a publication metadata node. |
| org | Journal | PCCP | instance metadata | h2kg:hasMetadata | Retained as bibliographic metadata. |
| org | Volume | 8 | instance metadata | h2kg:hasMetadata | Retained as bibliographic metadata. |
| org | Issue | 78 | instance metadata | h2kg:hasMetadata | Retained as bibliographic metadata. |
| org | Pages | 789-987 | instance metadata | h2kg:hasMetadata | Retained as bibliographic metadata. |
| org | PublicationDate | 2012-11-28 | instance metadata | h2kg:hasMetadata + dcterms:issued | Excel serial normalized to ISO date. |
| org | Topic | Fuel cell | instance metadata | h2kg:hasMetadata | Retained as topical metadata. |
| org | Device | PEMFC | instance metadata | h2kg:hasMetadata | Retained as application-context metadata. |
| org | Component | MEA | instance metadata | h2kg:MEAAssembly | Used as MEA application context metadata. |
| org | Subcomponent | Catalyst layer | instance metadata | h2kg:hasMetadata | Retained as subcomponent metadata. |
| org | Granularity Level | Microstructure | instance metadata | h2kg:hasMetadata | Retained as scale metadata. |
| org | Format | tiff | instance metadata | h2kg:hasMetadata + dcterms:format | Stored on raw-dataset metadata. |
| org | FileSize | 258 | instance metadata | h2kg:hasMetadata + dcterms:extent | Stored with file-size unit in raw-dataset metadata. |
| org | FileSizeUnit | MB | instance metadata | h2kg:hasMetadata + dcterms:extent | Stored with file size in raw-dataset metadata. |
| org | FileName | afm_rawdata.tif | instance metadata | h2kg:hasMetadata | Stored on raw-dataset metadata. |
| org | DimensionX | 256 | instance metadata | h2kg:hasMetadata | Stored on raw-dataset metadata. |
| org | DimensionY | 256 | instance metadata | h2kg:hasMetadata | Stored on raw-dataset metadata. |
| org | DimensionZ | 0 | instance metadata | h2kg:hasMetadata | Stored on raw-dataset metadata. |
| org | PixelPerMetric | 8.1 | instance metadata | h2kg:hasMetadata | Stored on raw-dataset metadata. |
| org | Link | link | instance metadata | h2kg:hasMetadata + dcterms:source | Stored as source/link metadata. |
| org | MaskExist | yes | instance metadata | h2kg:hasMetadata | Stored on processed-dataset metadata. |
| org | MaskLink | link | instance metadata | h2kg:hasMetadata + dcterms:source | Stored on processed-dataset metadata. |
| syn | Step 1 Precursor | Pd/C | instance metadata | h2kg:Matter | Represented as a material instance with supplier, lot-number, and CAS metadata. |
| syn | Step 1 AmountPrecursor | 5 wt% | instance metadata | h2kg:hasMetadata | Stored as precursor material metadata. |
| syn | Step 1 Technique | Buy | reuse existing term | h2kg:Process | Modeled as a labeled procurement process instance rather than a new TBox term. |
| syn | Step 1 Condition | Manufacturer = SigmaAldrich; Loot number = 205680; CAS-number = 7440-05-3 | instance metadata | h2kg:hasMetadata | Stored as procurement metadata on the Pd/C precursor. |
| syn | Step 1 Target | SInt1 | instance metadata | h2kg:Matter | Represents the procured catalyst material instance. |
| syn | Step 2 Precursor | SInt1 | instance metadata | h2kg:Matter | Uses the procured catalyst material as input. |
| syn | Step 2 Technique | Sieve | reuse existing term | h2kg:Manufacturing | Modeled as a labeled manufacturing instance. |
| syn | Step 2 Condition | sieve size = 75 um | instance metadata | h2kg:hasMetadata | Retained as sieving metadata in round 1. |
| syn | Step 2 Target | SInt2 | instance metadata | h2kg:Matter | Represents the sieved catalyst material. |
| syn | Step 3 Precursor | SInt2 | instance metadata | h2kg:Matter | Uses the sieved catalyst material as input. |
| syn | Step 3 Technique | Dry | reuse existing term | h2kg:Manufacturing | Modeled as a labeled manufacturing instance with drying parameters. |
| syn | Step 3 Condition | Temperature = 100 deg C; Time = 10 h | reuse existing term | h2kg:DryingTemperature + h2kg:DryingTime | Modeled through parameter-setting instances linked to the drying step. |
| syn | Step 3 Target | MEA | instance metadata | h2kg:MEAAssembly | Represents the MEA-oriented material context used for AFM sample preparation. |
| sp | Step 1 Precursor | MEA | instance metadata | h2kg:MEAAssembly | Represents the MEA sample entering AFM preparation. |
| sp | Step 1 Technique | Cut | reuse existing term | h2kg:Manufacturing | Modeled as a labeled manufacturing instance rather than a new TBox term. |
| sp | Step 1 Condition | Size = 25 cm2 | instance metadata | h2kg:hasMetadata | Retained as cut-step metadata. |
| sp | Step 1 Target | SPInt1 | instance metadata | h2kg:Matter | Represents the cut MEA sample. |
| sp | Step 2 Precursor | SPInt1; Terosion Teromix PU6700 | instance metadata | h2kg:Matter | Cut sample and embedding resin are retained as material metadata. |
| sp | Step 2 Technique | Embedded | reuse existing term | h2kg:Manufacturing | Modeled as a labeled manufacturing instance. |
| sp | Step 2 Condition | - | instance metadata | h2kg:hasMetadata | No explicit embedding condition was reported. |
| sp | Step 2 Target | SPInt2 | instance metadata | h2kg:Matter | Represents the embedded sample. |
| sp | Step 3 Precursor | SPInt2 | instance metadata | h2kg:Matter | Uses the embedded sample as input. |
| sp | Step 3 Technique | Curated | reuse existing term | h2kg:Manufacturing | Modeled conservatively as a labeled curing process instance. |
| sp | Step 3 Condition | Temperature = 25 deg C; Time = 24 h | instance metadata | h2kg:hasMetadata | Retained as curing metadata in round 1. |
| sp | Step 3 Target | SPInt3 | instance metadata | h2kg:Matter | Represents the cured embedded sample. |
| sp | Step 4 Precursor | SPInt3 | instance metadata | h2kg:Matter | Uses the cured sample as input. |
| sp | Step 4 Technique | Microtome cut | reuse existing term | h2kg:Manufacturing | Modeled as a labeled sectioning process instance. |
| sp | Step 4 Condition | Microtome = Leitz; Thickness = 2 mm | instance metadata | h2kg:hasMetadata | Retained as sectioning metadata in round 1. |
| sp | Step 4 Target | SPInt4 | instance metadata | h2kg:Matter | Represents the sectioned AFM sample intermediate. |
| sp | Step 5 Precursor | SPInt4; Double sided adhesive tape; AFM sample disc | instance metadata | h2kg:Matter | Sample, adhesive tape, and sample disc remain material instances with metadata. |
| sp | Step 5 Technique | Fix | reuse existing term | h2kg:Manufacturing | Modeled as a labeled mounting process instance. |
| sp | Step 5 Condition | Disc size = 12 mm; Disc brand = Plano | instance metadata | h2kg:hasMetadata | Retained as mounting metadata in round 1. |
| sp | Step 5 Target | Sample | instance metadata | h2kg:Matter | Represents the final AFM sample material instance. |
| char | MeasurementMethod | AFM | reuse existing term | h2kg:AtomicForceMicroscopyMeasurement | Reuses the public AFM measurement anchor. |
| char | MeasurementType | ex-situ | instance metadata | h2kg:hasMetadata | Retained as measurement metadata in round 1. |
| char | Specimen | homogeneous powder | instance metadata | h2kg:hasMetadata | Retained as specimen metadata in round 1. |
| char | Temperature | 23 | reuse existing term | h2kg:Temperature | Modeled as a parameter-setting instance linked to the AFM measurement. |
| char | TemperatureUnit | C | reuse existing term | h2kg:Temperature | Unit captured through the quantity-value pattern on the temperature setting. |
| char | Humidity | 80 | reuse existing term | h2kg:RelativeHumidity | Modeled as a parameter-setting instance linked to the AFM measurement. |
| char | HumidityUnit | % | reuse existing term | h2kg:RelativeHumidity | Unit captured through the quantity-value pattern on the humidity setting. |
| char | Atmosphere | air | instance metadata | h2kg:hasMetadata | Retained as measurement metadata in round 1. |
| char | AtmosphereUnit | - | instance metadata | h2kg:hasMetadata | Retained as atmosphere metadata in round 1. |
| char | Pressure | 1 | instance metadata | h2kg:hasMetadata | Retained as measurement metadata in round 1. |
| char | PressureUnit | atm | instance metadata | h2kg:hasMetadata | Retained as measurement metadata in round 1. |
| char | Calibration | adjusting lenses and apertures; adjusting the voltage | instance metadata | h2kg:hasMetadata | Retained as acquisition metadata. |
| inst | Instrument | Bruker multimode 8 AFM | reuse existing term | h2kg:AFMInstrument | Represented as an AFM instrument instance. |
| inst | Mode | Conductive tapping | instance metadata | h2kg:hasMetadata | Retained as instrument metadata in round 1. |
| inst | Tip | DLC SHR150, Nanosensors | instance metadata | h2kg:hasMetadata | Retained as tip metadata in round 1. |
| inst | NominalRadius | 1 | new ontology term | h2kg:AFMTipNominalRadius | Promoted as a reusable AFM acquisition parameter. |
| inst | NominalRadiusUnit | nm | new ontology term | h2kg:AFMTipNominalRadius | Unit captured through the quantity-value pattern on the tip-radius setting. |
| inst | Look-inAmplifier | PF-TUNA module, Bruker | instance metadata | h2kg:hasMetadata | Retained as supporting electronics metadata in round 1. |
| inst | Sensitivity | 1 | instance metadata | h2kg:hasMetadata | Retained as metadata in round 1. |
| inst | SensitivityUnit | fA | instance metadata | h2kg:hasMetadata | Retained as metadata in round 1. |
| inst | MeasuringSize | 1 | reuse existing term | h2kg:MicroscopyMeasuredArea | Reused as the public AFM measured-area parameter. |
| inst | MeasuringSizeUnit | um2 | reuse existing term | h2kg:MicroscopyMeasuredArea | Unit captured through the quantity-value pattern on the measured-area setting. |
| inst | ScanSpeed | 0.488 | new ontology term | h2kg:AFMScanSpeed | Promoted as a reusable AFM acquisition parameter. |
| inst | ScanSpeedUnit | Hz | new ontology term | h2kg:AFMScanSpeed | Unit captured through the quantity-value pattern on the AFM scan-speed setting. |
| inst | Resolution | 0.5 | instance metadata | h2kg:hasMetadata | Retained as metadata in round 1. |
| inst | ResolutionUnit | mm | instance metadata | h2kg:hasMetadata | Retained as metadata in round 1. |
| inst | Raw data | electron images | instance metadata | h2kg:MicrostructureImageDataset | Retained as descriptive dataset metadata exactly as reported in the worksheet. |
| inst | DataAdquisitionRate | 1024 | instance metadata | h2kg:hasMetadata | Retained as metadata in round 1. |
| inst | DataAdquisitionRateUnit | px | instance metadata | h2kg:hasMetadata | Retained as metadata in round 1. |
| pre | Step 1 Precursor | RawData | instance metadata | h2kg:MicrostructureImageDataset | Mapped to the raw AFM image dataset instance. |
| pre | Step 1 AmountPrecursor | - | instance metadata | h2kg:hasMetadata | No precursor amount value was reported. |
| pre | Step 1 Technique | Contrast adjustment | reuse existing term | h2kg:Process | Modeled as a labeled preprocessing process instance. |
| pre | Step 1 Condition | Contrast factor = 1 | instance metadata | h2kg:hasMetadata | Stored as preprocessing metadata. |
| pre | Step 1 Software | - | instance metadata | h2kg:hasMetadata | No preprocessing software was explicitly reported for this step. |
| pre | Step 1 Target | PPInt1 | instance metadata | h2kg:MicrostructureImageDataset | Represents the contrast-adjusted intermediate dataset. |
| pre | Step 2 Precursor | PPInt1 | instance metadata | h2kg:MicrostructureImageDataset | Uses the contrast-adjusted intermediate dataset as input. |
| pre | Step 2 AmountPrecursor | - | instance metadata | h2kg:hasMetadata | No precursor amount value was reported. |
| pre | Step 2 Technique | Brightness adjustment | reuse existing term | h2kg:Process | Modeled as a labeled preprocessing process instance. |
| pre | Step 2 Condition | Brightness factor = 1 | instance metadata | h2kg:hasMetadata | Stored as preprocessing metadata. |
| pre | Step 2 Software | - | instance metadata | h2kg:hasMetadata | No preprocessing software was explicitly reported for this step. |
| pre | Step 2 Target | Post-processed image | instance metadata | h2kg:SurfaceTopographyDataset | Mapped to the final processed AFM topography/image dataset. |
| anal | Step 1 Precursor | Post-processed image | instance metadata | h2kg:SurfaceTopographyDataset | The analysis process consumes the processed AFM dataset. |
| anal | Step 1 Technique | Manual particle measurement | reuse existing term | h2kg:Process | Modeled as a labeled analysis-process instance rather than a new TBox term. |
| anal | Step 1 Condition | - | instance metadata | h2kg:hasMetadata | No extra analysis condition was reported. |
| anal | Step 1 Software | ImageJ | reuse existing term | h2kg:FijiImageJSoftware | Reuses the existing software instrument term. |
| anal | Step 1 Target | Average size | reuse existing term | h2kg:MeanParticleSize | Mapped to the broadened reusable MeanParticleSize property. |
| anal | Step 1 AmountTarget | 110 um | reuse existing term | h2kg:DataPoint + h2kg:MeanParticleSize | Represented as a datapoint with a quantity value for MeanParticleSize. |
