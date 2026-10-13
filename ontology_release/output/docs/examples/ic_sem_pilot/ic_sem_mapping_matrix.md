# IC-SEM Mapping Matrix

This matrix accounts for each populated IC-SEM sheet field and classifies it as `reuse existing term`, `new ontology term`, `instance metadata`, or `not modeled` for the controlled pilot round.

| Section | Field | Example value | Classification | H2KG anchor | Note |
| --- | --- | --- | --- | --- | --- |
| org | ExperimentTitle | Ion-cut SEM of a doctor bladed MEA | instance metadata | h2kg:hasMetadata + dcterms:title | Stored on the source-record metadata node. |
| org | ExperimentID | 4 | instance metadata | h2kg:hasMetadata + h2kg:hasIdentifier | Stored as a literal identifier on the source record. |
| org | Measurement-ID | Run derived DOI | instance metadata | h2kg:hasMetadata + h2kg:hasIdentifier | Stored on measurement metadata. |
| org | UploadDate | 2021-10-15 | instance metadata | h2kg:hasMetadata + dcterms:date | Excel serial normalized to ISO date. |
| org | Institution | DLR | instance metadata | prov:Agent | Represented as an institutional agent. |
| org | FoundingBody | Helmholtz Imaging (HI) | instance metadata | prov:Agent | Represented as a funding-body agent. |
| org | Country | Germany | instance metadata | h2kg:hasMetadata | Retained as contextual metadata. |
| org | Author | Tobias Morawietz; Andre Colliard | instance metadata | prov:Agent | Represented as author agent instances. |
| org | ORCID | 123-465-7777; 321-321-3211 | instance metadata | h2kg:hasMetadata | Stored on author metadata nodes. |
| org | Email | tobi.mora@dlr.de; andyhuebsch@gmail.mx | instance metadata | h2kg:hasMetadata | Stored on author metadata nodes. |
| org | Published | 1 | instance metadata | h2kg:hasMetadata | Retained as publication-status metadata. |
| org | Publication | Automatic Characterization of Ion-cut SEM of a doctor bladed MEA | instance metadata | h2kg:hasMetadata + dcterms:title | Stored on a publication metadata node. |
| org | DOI | https://doi.org/10.3390/catal11077778 | instance metadata | h2kg:hasMetadata + dcterms:identifier | Stored on a publication metadata node. |
| org | Journal | Nature | instance metadata | h2kg:hasMetadata | Retained as bibliographic metadata. |
| org | Volume | 89 | instance metadata | h2kg:hasMetadata | Retained as bibliographic metadata. |
| org | Issue | 5 | instance metadata | h2kg:hasMetadata | Retained as bibliographic metadata. |
| org | Pages | 7778-9998 | instance metadata | h2kg:hasMetadata | Retained as bibliographic metadata. |
| org | PublicationDate | 2021-10-18 | instance metadata | h2kg:hasMetadata + dcterms:issued | Excel serial normalized to ISO date. |
| org | Topic | Fuel Cell | instance metadata | h2kg:hasMetadata | Retained as thematic metadata. |
| org | Device | PEMFC | instance metadata | h2kg:hasMetadata | Retained as application-context metadata. |
| org | Component | MEA | instance metadata | h2kg:hasMetadata | Retained as component metadata. |
| org | Subcomponent | Gas diffusion layer | instance metadata | h2kg:hasMetadata | Retained as subcomponent metadata in round 1 instead of promoting a new local node. |
| org | Granularity Level | Nanostructure | instance metadata | h2kg:hasMetadata | Retained as scale metadata. |
| org | Format | tiff | instance metadata | h2kg:hasMetadata + dcterms:format | Stored on raw-dataset metadata. |
| org | FileSize | 50 MB | instance metadata | h2kg:hasMetadata + dcterms:extent | Stored on raw-dataset metadata. |
| org | FileName | ICSEM.zip | instance metadata | h2kg:hasMetadata | Stored on raw-dataset metadata. |
| org | DimensionX | 512 | instance metadata | h2kg:hasMetadata | Stored on raw-dataset metadata. |
| org | DimensionY | 512 | instance metadata | h2kg:hasMetadata | Stored on raw-dataset metadata. |
| org | DimensionZ | 0 | instance metadata | h2kg:hasMetadata | Stored on raw-dataset metadata. |
| org | PixelPerMetric | 20 | instance metadata | h2kg:hasMetadata | Stored on raw-dataset metadata. |
| org | Link | link | instance metadata | h2kg:hasMetadata + dcterms:source | Stored as source/link metadata. |
| org | MaskExist | yes | instance metadata | h2kg:hasMetadata | Stored on processed-dataset metadata. |
| org | MaskLink | github-com/ICSEM | instance metadata | h2kg:hasMetadata + dcterms:source | Stored on processed-dataset metadata. |
| syn | Step 1 Precursor | HiSPEC 4000 | instance metadata | h2kg:Matter | Represented as a material instance with procurement metadata. |
| syn | Step 1 AmountPrecursor | 40 wt% | instance metadata | h2kg:hasMetadata | Stored on the catalyst precursor metadata node. |
| syn | Step 1 Technique | Buy | reuse existing term | h2kg:Process | Modeled as a labeled procurement process instance rather than a new TBox term. |
| syn | Step 2 Precursor | Nafion XL membrane | instance metadata | h2kg:Matter | Represented as a material instance with procurement metadata. |
| syn | Step 2 AmountPrecursor | 28 um | instance metadata | h2kg:hasMetadata | Stored as membrane-procurement metadata. |
| syn | Step 2 Technique | Buy | reuse existing term | h2kg:Process | Modeled as a labeled procurement process instance. |
| syn | Step 3 Precursor | Nafion ionomer | instance metadata | h2kg:Matter | Represented as a material instance with procurement metadata. |
| syn | Step 3 AmountPrecursor | 5 wt.% | instance metadata | h2kg:hasMetadata | Stored as material metadata. |
| syn | Step 4 Precursor | Gas diffusion layer | instance metadata | h2kg:Matter | Represented as a material instance with procurement metadata. |
| syn | Step 4 Technique | Buy | reuse existing term | h2kg:Process | Modeled as a labeled procurement process instance. |
| syn | Step 5 Technique | Dissolved | reuse existing term | h2kg:Manufacturing | Modeled as a labeled manufacturing instance; ratio and viscosity remain metadata. |
| syn | Step 5 Condition | Ratio = 70:30; Viscosity = 80 Pas | instance metadata | h2kg:hasMetadata | Retained as process metadata in round 1. |
| syn | Step 6 Technique | Doctor blade | reuse existing term | h2kg:DoctorBladeCoating | Mapped to the existing DoctorBladeCoating term. |
| syn | Step 6 Condition | Velocity = 1 cm/s; Instrument = MICOS Blading; Thickness = 1 mm | instance metadata | h2kg:hasMetadata | Retained as process metadata in round 1. |
| syn | Step 7 Technique | Dry | reuse existing term | h2kg:Manufacturing | Modeled as a labeled manufacturing instance with drying parameters. |
| syn | Step 7 Condition | Time = 16 h; Temperature = 80 °C | reuse existing term | h2kg:DryingTime + h2kg:DryingTemperature | Modeled through parameter-setting instances linked to the drying step. |
| sp | Step 1 Technique | Cut | reuse existing term | h2kg:Manufacturing | Modeled as a labeled manufacturing instance; sample size stays metadata. |
| sp | Step 1 Condition | Size = 5 mm2 | instance metadata | h2kg:hasMetadata | Retained as cut-step metadata. |
| sp | Step 2 Technique | Fix | reuse existing term | h2kg:Manufacturing | Modeled as a labeled manufacturing instance. |
| sp | Step 2 Condition | SampleHolder = Standard CSP | instance metadata | h2kg:hasMetadata | Retained as fixture metadata. |
| sp | Step 3 Technique | Dispersion | reuse existing term | h2kg:Process | Modeled as a labeled process instance. |
| sp | Step 3 Precursor | Carbon coated copper TEM grid | instance metadata | h2kg:Matter | Retained as supporting sample-context material metadata. |
| sp | Step 4 Technique | Dry | reuse existing term | h2kg:Manufacturing | Modeled as a labeled manufacturing instance. |
| sp | Step 4 Condition | Time = 24 h | reuse existing term | h2kg:DryingTime | Modeled through a drying-time setting instance. |
| char | MeasurementMethod | IC-SEM | reuse existing term | h2kg:ICSEMImagingMeasurement | Mapped to the new public IC-SEM measurement term. |
| char | MeasurementType | ex-situ | instance metadata | h2kg:hasMetadata | Retained as measurement metadata in round 1. |
| char | Specimen | highly porous bulk material | instance metadata | h2kg:hasMetadata | Retained as specimen metadata in round 1. |
| char | Temperature | 25 C | reuse existing term | h2kg:Temperature | Modeled as a parameter-setting instance linked to the IC-SEM measurement. |
| char | Humidity | 0 % | reuse existing term | h2kg:RelativeHumidity | Modeled as a parameter-setting instance linked to the IC-SEM measurement. |
| char | Atmosphere | Vacuum | instance metadata | h2kg:hasMetadata | Retained as measurement metadata in round 1. |
| char | Pressure | 10^-6 atm | reuse existing term | h2kg:VacuumChamberPressure | Modeled as a parameter-setting instance linked to the IC-SEM measurement. |
| char | Calibration | adjusting lenses and apertures; adjusting the voltage | instance metadata | h2kg:hasMetadata | Retained as acquisition metadata. |
| inst | Instrument | FIB-SEM | new ontology term | h2kg:ICSEMInstrument | A distinct public instrument term is introduced so ion-cut SEM is retrievable independently in H2KG Explore. |
| inst | FIBEquipment | Jeol IB-19530CP Cross Section Polisher | instance metadata | h2kg:hasMetadata | Retained on instrument metadata. |
| inst | SEMEquipment | Jeol JSM-7200F SEM | instance metadata | h2kg:hasMetadata | Retained on instrument metadata. |
| inst | Optics | GEMINI | instance metadata | h2kg:hasMetadata | Retained on instrument metadata. |
| inst | InjectionSystem | multi channel gas injection system GIS | instance metadata | h2kg:hasMetadata | Retained on instrument metadata. |
| inst | IonBeamType | Ar | instance metadata | h2kg:hasMetadata | Retained on instrument metadata. |
| inst | IonBeamCurrent | 700 pA | reuse existing term | h2kg:IonBeamCurrent | Modeled as a parameter-setting instance linked to the IC-SEM measurement. |
| inst | IonBeamEnergy | 6 keV | reuse existing term | h2kg:IonBeamEnergy | Modeled as a parameter-setting instance linked to the IC-SEM measurement. |
| inst | PlaneSpacing | 10 | instance metadata | h2kg:hasMetadata | Retained as acquisition metadata in round 1. |
| inst | MeasuredArea | 20 um2 | reuse existing term | h2kg:MicroscopyMeasuredArea | Modeled as a parameter-setting instance linked to the IC-SEM measurement. |
| inst | CutThickness | 150 nm | reuse existing term | h2kg:CutThickness | Modeled as a parameter-setting instance linked to the IC-SEM measurement. |
| inst | DwellTime | 12 h | reuse existing term | h2kg:DwellTime | Modeled as a parameter-setting instance linked to the IC-SEM measurement. |
| inst | Detector | InLens, SE2 | instance metadata | h2kg:hasMetadata | Retained on instrument metadata. |
| inst | ElectronCurrent | 250 pA | reuse existing term | h2kg:ElectronCurrent | Modeled as a parameter-setting instance linked to the IC-SEM measurement. |
| inst | ElectronBeamEnergy | 1.5 keV | reuse existing term | h2kg:ElectronBeamEnergy | Modeled as a parameter-setting instance linked to the IC-SEM measurement. |
| inst | PixelSize | 20 nm | new ontology term | h2kg:PixelSize | A dedicated 2D microscopy pixel-size parameter is introduced instead of reusing voxel size. |
| inst | Magnification | 10 | reuse existing term | h2kg:Magnification | Modeled as a parameter-setting instance linked to the IC-SEM measurement. |
| inst | Brightness | 1 | instance metadata | h2kg:hasMetadata | Retained as acquisition metadata in round 1. |
| inst | Contrast | 1 | instance metadata | h2kg:hasMetadata | Retained as acquisition metadata in round 1. |
| inst | ImageAcquisitionTime | 60 s | reuse existing term | h2kg:ExposureTime | Mapped conservatively to the existing exposure-time parameter. |
| inst | TotalAcquisitionTime | 12 h | reuse existing term | h2kg:TotalAcquisitionTime | Modeled as a parameter-setting instance linked to the IC-SEM measurement. |
| pre | Step 1 Technique | Thresholding | reuse existing term | h2kg:Process | Modeled as a labeled preprocessing process instance. |
| pre | Step 1 Software | ImageJ; algorithm = Watershed | reuse existing term | h2kg:FijiImageJSoftware | Software is represented through the existing ImageJ software term; algorithm stays metadata. |
| pre | Step 2 Technique | Scale set | reuse existing term | h2kg:Process | Modeled as a labeled preprocessing process instance. |
| pre | Step 2 Software | ImageJ | reuse existing term | h2kg:FijiImageJSoftware | Software is represented through the existing ImageJ software term. |
| anal | Step 1 Technique | Layer thickness measurement | reuse existing term | h2kg:Process | Modeled as a labeled analysis process instance. |
| anal | Step 1 Software | ImageJ | reuse existing term | h2kg:FijiImageJSoftware | Software is represented through the existing ImageJ software term. |
| anal | Step 1 Target | MEA thickness | new ontology term | h2kg:MembraneElectrodeAssemblyThickness | Promoted as a new public H2KG property term. |
| anal | Step 1 AmountTarget | 80 nm | instance metadata | h2kg:DataPoint + h2kg:hasQuantityValue | Represented as a measurement-derived datapoint with a quantity value. |
| anal | Step 1 Target | GDL thickness | reuse existing term | h2kg:GasDiffusionLayerThickness | Reused as the existing H2KG thickness anchor requested for this round. |
| anal | Step 1 AmountTarget | 160 nm | instance metadata | h2kg:DataPoint + h2kg:hasQuantityValue | Represented as a measurement-derived datapoint with a quantity value. |
| anal | Step 2 Technique | Porosity measurement | reuse existing term | h2kg:Process | Modeled as a labeled analysis process instance. |
| anal | Step 2 Software | ImageJ | reuse existing term | h2kg:FijiImageJSoftware | Software is represented through the existing ImageJ software term. |
| anal | Step 2 Target | Porosity | reuse existing term | h2kg:TotalPorosity | Mapped conservatively to the existing total-porosity property. |
| anal | Step 2 AmountTarget | 6 pu | instance metadata | h2kg:DataPoint + h2kg:hasQuantityValue | Represented as a porosity datapoint with metadata noting the raw sheet unit token. |
