# SEM Mapping Matrix

This matrix accounts for the SEM pilot fields and classifies them as `reuse existing term`, `instance metadata`, or `not modeled` for the current round.

| Section | Field | Example value | Classification | H2KG anchor | Note |
| --- | --- | --- | --- | --- | --- |
| org | ExperimentTitle | Elucidating the Influence of the d-Band Center on the Synthesis of Isobutanol | instance metadata | h2kg:hasMetadata + dcterms:title | Stored on the SEM source-record metadata node. |
| org | ExperimentID | 1 | instance metadata | h2kg:hasMetadata + h2kg:hasIdentifier | Stored as a literal identifier on the source record. |
| org | Measurement-ID | Run derived DOI | instance metadata | h2kg:hasMetadata + h2kg:hasIdentifier | Stored on measurement metadata. |
| org | UploadDate | 2022-10-11 | instance metadata | h2kg:hasMetadata + dcterms:date | Excel serial normalized to ISO date. |
| org | MeasurementDate |  | not modeled | - | No value was present. |
| org | Institution | FZJ IEK-14 | instance metadata | prov:Agent | Represented as an institutional agent. |
| org | FoundingBody | HIP | instance metadata | prov:Agent | Represented as a funding-body agent. |
| org | Country | Germany | instance metadata | h2kg:hasMetadata | Retained as contextual metadata. |
| org | Author | Joachim Pasel | instance metadata | prov:Agent | Represented as an author agent instance. |
| org | ORCID | 123-465-4789 | instance metadata | h2kg:hasMetadata | Stored on author metadata. |
| org | Email | andyhuebsch@gmail.mx | instance metadata | h2kg:hasMetadata | Stored on author metadata. |
| org | Published | 1 | instance metadata | h2kg:hasMetadata | Retained as publication-status metadata. |
| org | Publication | Interseting study about myself | instance metadata | h2kg:hasMetadata + dcterms:title | Stored on a publication metadata node. |
| org | DOI | https://doi.org/10.3390/catal11030406 | instance metadata | h2kg:hasMetadata + dcterms:identifier | Stored as publication metadata. |
| org | Journal | RSC Nanoscale | instance metadata | h2kg:hasMetadata | Retained as bibliographic metadata. |
| org | Volume | 1 | instance metadata | h2kg:hasMetadata | Retained as bibliographic metadata. |
| org | Issue | 25 | instance metadata | h2kg:hasMetadata | Retained as bibliographic metadata. |
| org | Pages | 456-654 | instance metadata | h2kg:hasMetadata | Retained as bibliographic metadata. |
| org | PublicationDate | 2012-11-12 | instance metadata | h2kg:hasMetadata + dcterms:issued | Excel serial normalized to ISO date. |
| org | Topic | Catalysis | instance metadata | h2kg:hasMetadata | Retained as topical metadata. |
| org | Device | - | not modeled | - | No device value was supplied. |
| org | Component | - | not modeled | - | No component value was supplied. |
| org | Subcomponent | Catalyst | instance metadata | h2kg:hasMetadata | Retained as subcomponent metadata. |
| org | Granularity Level | Nanostructure | instance metadata | h2kg:hasMetadata | Retained as scale metadata. |
| org | Format | tiff | instance metadata | h2kg:hasMetadata + dcterms:format | Stored on dataset metadata. |
| org | FileSize | 1 | instance metadata | h2kg:hasMetadata + dcterms:extent | Stored with file-size unit in dataset metadata. |
| org | FileSizeUnit | MB | instance metadata | h2kg:hasMetadata + dcterms:extent | Stored with file size in dataset metadata. |
| org | FileName | Test.tif | instance metadata | h2kg:hasMetadata | Stored on raw dataset metadata. |
| org | DimensionX | 1024 | instance metadata | h2kg:hasMetadata | Stored on raw dataset metadata. |
| org | DimensionY | 1024 | instance metadata | h2kg:hasMetadata | Stored on raw dataset metadata. |
| org | DimensionZ | 600 | instance metadata | h2kg:hasMetadata | Stored on raw dataset metadata. |
| org | PixelPerMetric | 8.1 | instance metadata | h2kg:hasMetadata | Stored on raw dataset metadata. |
| org | Link | link | instance metadata | h2kg:hasMetadata + dcterms:source | Stored as source/link metadata. |
| org | MaskExist | yes | instance metadata | h2kg:hasMetadata | Stored on processed-dataset metadata. |
| org | MaskLink | link | instance metadata | h2kg:hasMetadata + dcterms:source | Stored on processed-dataset metadata. |
| syn | Step 1 Precursor | Pd/C | instance metadata | h2kg:Matter | Represented as a material instance with supplier, lot-number, and CAS metadata. |
| syn | Step 1 AmountPrecursor | 5 wt% | instance metadata | h2kg:hasMetadata | Stored as material metadata on the Pd/C precursor. |
| syn | Step 1 Technique | Buy | reuse existing term | h2kg:Process | Modeled as a labeled process instance rather than a new TBox term. |
| syn | Step 1 Condition | Manufacturer = SigmaAldrich; Loot number = 205680; CAS-number = 7440-05-3 | instance metadata | h2kg:hasMetadata | Stored as procurement metadata on the Pd/C precursor. |
| syn | Step 1 Target | SInt1 | instance metadata | h2kg:Matter | Represented as the procured Pd/C material instance. |
| syn | Step 2 Precursor | SInt1 | instance metadata | h2kg:Matter | Uses the procured Pd/C material instance as input. |
| syn | Step 2 Technique | Sieve | reuse existing term | h2kg:Manufacturing | Modeled as a labeled manufacturing instance rather than a new TBox term. |
| syn | Step 2 Condition | sieve size = 75 um | instance metadata | h2kg:hasMetadata | Retained as sieving metadata in round 1. |
| syn | Step 2 Target | SInt2 | instance metadata | h2kg:Matter | Represents the sieved catalyst material. |
| syn | Step 3 Precursor | SInt2 | instance metadata | h2kg:Matter | Uses the sieved catalyst material as input. |
| syn | Step 3 Technique | Dry | reuse existing term | h2kg:Manufacturing | Modeled as a labeled manufacturing instance with drying parameters. |
| syn | Step 3 Condition | Temperature = 100 °C / Time = 10 h | reuse existing term | h2kg:DryingTemperature + h2kg:DryingTime | Modeled through parameter-setting instances linked to the drying step. |
| syn | Step 3 Target | MEA | instance metadata | h2kg:Matter | Represents the dried catalyst material used for SEM sample preparation. |
| sp | Step 1 Inputs | MEA + Sampleholder (Plano GmbH) + Tape (Plano GmbH) | instance metadata | h2kg:hasInputMaterial | Connected as material-input instances to the mounting step. |
| sp | Step 1 Technique | Fix | reuse existing term | h2kg:Manufacturing | Modeled as a labeled manufacturing instance rather than a new TBox term. |
| sp | Step 1 Target | SPInt1 | instance metadata | h2kg:Matter | Represents the mounted SEM intermediate sample. |
| sp | Step 2 Inputs | SPInt1 + Au | instance metadata | h2kg:hasInputMaterial | Connected as material-input instances to the conductive-coating step. |
| sp | Step 2 Technique | Deposition | reuse existing term | h2kg:SputterCoating | Mapped conservatively to the existing SputterCoating term. |
| sp | Step 2 Target | Sample | instance metadata | h2kg:Matter | Represents the final SEM sample material instance. |
| char | MeasurementMethod | SEM | reuse existing term | h2kg:ScanningElectronMicroscopyImaging | Defines the pilot measurement instance type. |
| char | MeasurementType | ex-situ | instance metadata | h2kg:hasMetadata | Retained as measurement-context metadata in round 1. |
| char | Specimen | homogeneous powder | instance metadata | h2kg:hasMetadata | Retained as specimen-context metadata in round 1. |
| char | Characterization environment |  | not modeled | - | No value was present. |
| char | Temperature | 23 C | reuse existing term | h2kg:Temperature | Modeled as a parameter-setting instance linked to the SEM measurement. |
| char | Humidity | 50 % | reuse existing term | h2kg:RelativeHumidity | Modeled as a parameter-setting instance linked to the SEM measurement. |
| char | Atmosphere | air | instance metadata | h2kg:hasMetadata | Retained as measurement metadata. |
| char | Pressure | 1 atm | instance metadata | h2kg:hasMetadata | Stored as measurement metadata because a generic pressure term is not promoted in this round. |
| char | Calibration | adjusting lenses and apertures / adjusting the voltage | instance metadata | h2kg:hasMetadata | Retained as calibration metadata. |
| inst | Instrument | Electron Microscope | reuse existing term | h2kg:SEMInstrument | Represented as a SEM instrument instance. |
| inst | MicroscopeBrand | Zeiss Gemini Ultra plus | instance metadata | h2kg:hasMetadata | Stored as instrument metadata. |
| inst | AccelerationVoltage | 20 kV | reuse existing term | h2kg:AcceleratingVoltage | Modeled as a parameter-setting instance linked to the SEM measurement. |
| inst | Magnification | 250 | reuse existing term | h2kg:Magnification | Modeled as a parameter-setting instance linked to the SEM measurement. |
| inst | Cathode | LaB6 | instance metadata | h2kg:hasMetadata | Stored as instrument metadata. |
| inst | WorkingDistance | 8.5 mm | reuse existing term | h2kg:WorkingDistance | Modeled as a parameter-setting instance linked to the SEM measurement. |
| inst | Probe | Electron beam | instance metadata | h2kg:hasMetadata | Stored as instrument metadata. |
| inst | Detector | InLens | instance metadata | h2kg:hasMetadata | Stored as instrument metadata. |
| inst | ImagingTechnique | Brightfield | instance metadata | h2kg:hasMetadata | Stored as instrument metadata in round 1. |
| inst | Signal | Secondary electrons | instance metadata | h2kg:hasMetadata | Stored as instrument metadata in round 1. |
| inst | TimeLapse | 30 s | instance metadata | h2kg:hasMetadata | Retained as acquisition metadata in round 1. |
| inst | RawData | electron images | instance metadata | h2kg:SEMImageDataset | Retained as descriptive metadata on the raw SEM dataset. |
| inst | DataAdquisitionRate | - | not modeled | - | No usable value was present. |
| pre | Step 1 Precursor | RawData | instance metadata | h2kg:SEMImageDataset | Mapped to the raw SEM image dataset instance. |
| pre | Step 1 Technique | Contrast adjustment | reuse existing term | h2kg:Process | Modeled as a labeled process instance rather than a new TBox term. |
| pre | Step 1 Condition | Contrast factor = 1 | instance metadata | h2kg:hasMetadata | Stored as preprocessing metadata. |
| pre | Step 1 Target | PPInt1 | instance metadata | h2kg:SEMImageDataset | Mapped to the contrast-adjusted SEM image dataset instance. |
| pre | Step 2 Precursor | PPInt1 | instance metadata | h2kg:SEMImageDataset | Uses the contrast-adjusted SEM image dataset as input. |
| pre | Step 2 Technique | Brightness adjustment | reuse existing term | h2kg:Process | Modeled as a labeled process instance rather than a new TBox term. |
| pre | Step 2 Condition | Brightness factor = 1 | instance metadata | h2kg:hasMetadata | Stored as preprocessing metadata. |
| pre | Step 2 Target | Post-processed image | instance metadata | h2kg:SEMMicrographDataset | Mapped to the final processed SEM image dataset. |
| anal | Step 1 Precursor | Post-processed image | instance metadata | h2kg:SEMMicrographDataset | The analysis process consumes the processed SEM image dataset. |
| anal | Step 1 Technique | Manual particle measurement | reuse existing term | h2kg:Process | Modeled as a labeled analysis-process instance rather than a new TBox term. |
| anal | Step 1 Software | ImageJ | reuse existing term | h2kg:FijiImageJSoftware | The analysis process reuses the existing software instrument term. |
| anal | Step 1 Target | Average size | reuse existing term | h2kg:CatalystParticleDiameter | Mapped conservatively to the existing CatalystParticleDiameter property. |
| anal | Step 1 AmountTarget |  | not modeled | h2kg:DataPoint | A semantic result data point is created, but the worksheet does not provide a numeric value. |
