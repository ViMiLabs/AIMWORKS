# TEM Mapping Matrix

This matrix accounts for each populated TEM sheet field and classifies it as `reuse existing term`, `new ontology term`, `instance metadata`, or `not modeled`.

| Section | Field | Example value | Classification | H2KG anchor | Note |
| --- | --- | --- | --- | --- | --- |
| org | ExperimentTitle | Synthetic TEM workflow demonstration | instance metadata | h2kg:hasMetadata + dcterms:title | Identifies an illustrative record; it is not an experimental observation. |
| org | ExperimentID | SYNTHETIC-TEM-001 | instance metadata | h2kg:hasMetadata + h2kg:hasIdentifier | Stable identifier for the synthetic demonstration. |
| org | EvidenceStatus | illustrative synthetic | instance metadata | h2kg:hasMetadata | Prevents the representative values from being interpreted as measured evidence. |
| org | Topic | Catalyst nanoparticle characterization | instance metadata | h2kg:hasMetadata | Retained as thematic metadata. |
| org | Device | PEMFC | instance metadata | h2kg:hasMetadata | Retained as application-context metadata. |
| org | Component | Catalyst layer | instance metadata | h2kg:hasMetadata | Retained as component-context metadata. |
| org | Format | TIFF | instance metadata | h2kg:hasMetadata + dcterms:format | Stored on the raw dataset metadata node. |
| org | DimensionX | 1024 | instance metadata | h2kg:hasMetadata | Representative image dimension for profile validation. |
| org | DimensionY | 1024 | instance metadata | h2kg:hasMetadata | Representative image dimension for profile validation. |
| org | MaskExist | yes | instance metadata | h2kg:hasMetadata | Synthetic processed-dataset metadata. |
| syn | Step 1 Precursor | Pd/C | instance metadata | h2kg:Matter | Represented as a material instance with supplier, lot-number, and CAS metadata. |
| syn | Step 1 AmountPrecursor | 30 wt% | instance metadata | h2kg:hasMetadata | Retained as procurement metadata on the Pd/C material instance. |
| syn | Step 1 Technique | Buy | reuse existing term | h2kg:Process | Modeled as a labeled process instance rather than a new ontology term. |
| syn | Step 1 Condition | Manufacturer = Tanaka Kikinzoku Kogyo K.K., Japan; Lot number = TEC10E30E; CAS = 7440-05-3 | instance metadata | h2kg:hasMetadata | Stored on the Pd/C procurement metadata node. |
| syn | Step 1 Target | Pd/C | instance metadata | h2kg:Matter | The procurement step outputs the Pd/C material instance. |
| syn | Step 2 Precursor | Carbon coated copper TEM grid | instance metadata | h2kg:Matter | Represented as a material instance with procurement metadata. |
| syn | Step 2 AmountPrecursor | 3 mm | instance metadata | h2kg:hasMetadata | Stored as dimensional metadata on the TEM-grid material instance. |
| syn | Step 2 Technique | Buy | reuse existing term | h2kg:Process | Modeled as a labeled process instance rather than a new ontology term. |
| syn | Step 2 Condition | Manufacturer = SigmaAldrich; Lot number = 205680; CAS = 7440-05-4 | instance metadata | h2kg:hasMetadata | Stored on the TEM-grid procurement metadata node. |
| syn | Step 2 Target | Carbon coated copper TEM grid | instance metadata | h2kg:Matter | The procurement step outputs the TEM-grid material instance. |
| sp | Step 1 Technique | Mix | reuse existing term | h2kg:Manufacturing | Modeled as a labeled manufacturing instance under the existing process schema. |
| sp | Step 1 Inputs | Pd/C + Liquid mixture | instance metadata | h2kg:hasInputMaterial | Connected as material-input instances to the mix step. |
| sp | Step 1 AmountTarget | 5 mL | instance metadata | h2kg:hasMetadata | Retained as intermediate-output metadata for SPInt1. |
| sp | Step 2 Technique | Sonification | reuse existing term | h2kg:Sonication | Mapped to the existing Sonication term with explicit time and frequency settings. |
| sp | Step 2 Condition | Time = 10 min; Frequency = 80 Hz | reuse existing term | h2kg:SonicationTime + h2kg:AcousticFrequency | Modeled through parameter-setting instances linked to the sonication step. |
| sp | Step 3 Technique | Dispersion | reuse existing term | h2kg:Manufacturing | Modeled as a labeled manufacturing instance rather than a new ontology term. |
| sp | Step 3 Inputs | SPInt2 + Carbon coated copper TEM grid | instance metadata | h2kg:hasInputMaterial | Connected as material inputs to the dispersion step. |
| sp | Step 4 Technique | Dry | reuse existing term | h2kg:Manufacturing | Modeled as a labeled manufacturing instance rather than a new ontology term. |
| sp | Step 4 Condition | Time = 24 h | reuse existing term | h2kg:DryingTime | Modeled through a drying-time parameter-setting instance. |
| sp | Step 4 Target | Sample | instance metadata | h2kg:Matter | Represented as the final TEM sample material instance. |
| char | MeasurementMethod | TEM | reuse existing term | h2kg:TransmissionElectronMicroscopyImaging | Defines the pilot measurement instance type. |
| char | MeasurementType | ex-situ | instance metadata | h2kg:hasMetadata | Retained as measurement-context metadata in round 1. |
| char | Specimen | homogeneous powder | instance metadata | h2kg:hasMetadata | Retained as specimen-context metadata in round 1. |
| char | Characterization environment |  | not modeled | - | No value was present in the TEM pilot sheet. |
| char | Temperature | 25 C | reuse existing term | h2kg:Temperature | Modeled as a parameter-setting instance linked to the TEM measurement. |
| char | Humidity | 0 % | reuse existing term | h2kg:RelativeHumidity | Modeled as a parameter-setting instance linked to the TEM measurement. |
| char | Atmosphere | Vacuum | instance metadata | h2kg:hasMetadata | Retained as measurement metadata in round 1. |
| char | Pressure | 10^-5 atm | reuse existing term | h2kg:VacuumChamberPressure | Modeled as a parameter-setting instance linked to the TEM measurement. |
| char | Calibration | adjusting lenses and apertures; adjusting the voltage | instance metadata | h2kg:hasMetadata | Retained as calibration metadata in round 1. |
| inst | Instrument | Electron Microscope | reuse existing term | h2kg:TEMInstrument | Represented as a TEM instrument instance. |
| inst | MicroscopeBrand | Zeiss Gemini Ultra plus | instance metadata | h2kg:hasMetadata | Stored as instrument metadata. |
| inst | AccelerationVoltage | 100 kV | reuse existing term | h2kg:AcceleratingVoltage | Modeled as a parameter-setting instance linked to the TEM measurement. |
| inst | Magnification | 140000 | new ontology term | h2kg:Magnification | Introduced as a reusable acquisition parameter in the TEM round. |
| inst | Cathode | LaB6 | instance metadata | h2kg:hasMetadata | Stored as instrument metadata in round 1. |
| inst | WorkingDistance | 8.5 mm | new ontology term | h2kg:WorkingDistance | Introduced as a reusable acquisition parameter in the TEM round. |
| inst | Probe | Electron beam | instance metadata | h2kg:hasMetadata | Stored as instrument metadata in round 1. |
| inst | Detector | CCD Camera | instance metadata | h2kg:hasMetadata | Stored as instrument metadata in round 1. |
| inst | ImagingTechnique | Brightfield | instance metadata | h2kg:hasMetadata | Stored as instrument metadata in round 1. |
| inst | Signal | Transmitted electrons | instance metadata | h2kg:hasMetadata | Stored as instrument metadata in round 1. |
| inst | TimeLapse | 30 s | instance metadata | h2kg:hasMetadata | Retained as acquisition metadata in round 1. |
| inst | RawData | electron images | instance metadata | h2kg:MicrostructureImageDataset | Retained as descriptive metadata on the raw image dataset. |
| inst | DataAdquisitionRate | - | not modeled | - | No usable value was present in the TEM pilot sheet. |
| pre | Step 1 Precursor | RawData | instance metadata | h2kg:MicrostructureImageDataset | Mapped to the raw TEM image dataset instance. |
| pre | Step 1 Technique | Format conversion | reuse existing term | h2kg:Process | Modeled as a labeled process instance rather than a new ontology term. |
| pre | Step 1 Condition | Format = Tiff | instance metadata | h2kg:hasMetadata + dcterms:format | Stored as preprocessing metadata. |
| pre | Step 1 Target | Post-processed image | instance metadata | h2kg:MicrostructureImageDataset | Mapped to the processed TEM image dataset instance. |
| anal | Step 1 Precursor | Post-processed image | instance metadata | h2kg:MicrostructureImageDataset | The analysis process consumes the processed TEM image dataset. |
| anal | Step 1 Technique | Manual particle measurement | reuse existing term | h2kg:Process | Modeled as a labeled analysis-process instance rather than a new ontology term. |
| anal | Step 1 Software | ImageJ | reuse existing term | h2kg:FijiImageJSoftware | The analysis process reuses the existing image-analysis software term through h2kg:usesSoftware. |
| anal | Step 1 Target | Average size | reuse existing term | h2kg:PdNanoparticleDiameter | Mapped conservatively to the existing PdNanoparticleDiameter property. |
| anal | Step 1 AmountTarget | 5 nm | instance metadata | h2kg:DataPoint + h2kg:hasQuantityValue | Represented as the primary TEM result data point with an explicit quantity value. |
