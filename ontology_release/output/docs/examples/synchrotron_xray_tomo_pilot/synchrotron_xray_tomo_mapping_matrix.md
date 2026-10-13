# Synchrotron X-Ray Tomography Mapping Matrix

This matrix uses `SynchrotronTomo` as the canonical sheet and records `SynchrotronRadio` as a duplicate-structure validation sheet with explicitly listed deviations.

| Source sheet | Section | Field | Example value | Classification | H2KG anchor | Note |
| --- | --- | --- | --- | --- | --- | --- |
| SynchrotronTomo | org | ExperimentTitle | Synchrotron x-ray tomography of dry electrode | instance metadata | h2kg:hasMetadata + dcterms:title | Canonical workbook title retained as source metadata. |
| SynchrotronTomo | org | ExperimentID | 2 | instance metadata | h2kg:hasMetadata + h2kg:hasIdentifier | Stored as source-record identifier metadata. |
| SynchrotronTomo | org | Measurement-ID | Run derived DOI | instance metadata | h2kg:hasMetadata + h2kg:hasIdentifier | Stored as source-measurement identifier metadata. |
| SynchrotronTomo | org | UploadDate | 44845 | instance metadata | h2kg:hasMetadata | Excel serial date retained as source metadata in round 1. |
| SynchrotronTomo | org | Institution | HIU | instance metadata | prov:Agent | Represented as institutional provenance metadata. |
| SynchrotronTomo | org | FoundingBody | BASF | instance metadata | prov:Agent | Represented as funding provenance metadata. |
| SynchrotronTomo | org | Country | Germany | instance metadata | h2kg:hasMetadata | Retained as source metadata. |
| SynchrotronTomo | org | Author | Kerstin Koble; Andre Colliard Granero | instance metadata | prov:Agent | Retained as author provenance metadata. |
| SynchrotronTomo | org | ORCID | 123-465-4789; 321-321-3211 | instance metadata | h2kg:hasMetadata | Stored as author metadata. |
| SynchrotronTomo | org | Email | andyhuebsch@gmail.mx; mustermann@yahoo.ru | instance metadata | h2kg:hasMetadata | Stored as author metadata. |
| SynchrotronTomo | org | Published | 1 | instance metadata | h2kg:hasMetadata | Retained as source metadata. |
| SynchrotronTomo | org | Publication | Synchrotron x-ray tomography of dry electrode | instance metadata | h2kg:hasMetadata + dcterms:title | Retained as publication metadata. |
| SynchrotronTomo | org | DOI | https://doi.org/10.3390/35654654654 | instance metadata | h2kg:hasMetadata + dcterms:identifier | Retained as publication metadata. |
| SynchrotronTomo | org | Journal | Nature | instance metadata | h2kg:hasMetadata | Retained as publication metadata. |
| SynchrotronTomo | org | Volume | 41 | instance metadata | h2kg:hasMetadata | Retained as publication metadata. |
| SynchrotronTomo | org | Issue | 5 | instance metadata | h2kg:hasMetadata | Retained as publication metadata. |
| SynchrotronTomo | org | Pages | 6456-6541 | instance metadata | h2kg:hasMetadata | Retained as publication metadata. |
| SynchrotronTomo | org | PublicationDate | 41215 | instance metadata | h2kg:hasMetadata | Excel serial date retained as publication metadata in round 1. |
| SynchrotronTomo | org | Topic | VRFB | instance metadata | h2kg:hasMetadata | Out-of-scope study label retained only as source metadata. |
| SynchrotronTomo | org | Device | VRFB | instance metadata | h2kg:hasMetadata | Out-of-scope study label retained only as source metadata. |
| SynchrotronTomo | org | Component | Electrode | instance metadata | h2kg:hasMetadata | Retained as source metadata rather than a public H2KG scope anchor. |
| SynchrotronTomo | org | Subcomponent | Bubble | instance metadata | h2kg:hasMetadata | Retained as source metadata. |
| SynchrotronTomo | org | Granularity Level | Microstructure | instance metadata | h2kg:hasMetadata | Retained as source metadata. |
| SynchrotronTomo | org | Format | tiff | instance metadata | h2kg:hasMetadata + dcterms:format | Stored on raw-dataset metadata. |
| SynchrotronTomo | org | FileSize | 541 MB | instance metadata | h2kg:hasMetadata + dcterms:extent | Stored on raw-dataset metadata. |
| SynchrotronTomo | org | FileName | TestTomography.tif | instance metadata | h2kg:hasMetadata | Stored on raw-dataset metadata. |
| SynchrotronTomo | org | DimensionX | 1024 | instance metadata | h2kg:hasMetadata | Stored on raw-dataset metadata. |
| SynchrotronTomo | org | DimensionY | 1024 | instance metadata | h2kg:hasMetadata | Stored on raw-dataset metadata. |
| SynchrotronTomo | org | DimensionZ | 600 | instance metadata | h2kg:hasMetadata | Stored on raw-dataset metadata. |
| SynchrotronTomo | org | PixelPerMetric | 8.1 | instance metadata | h2kg:hasMetadata | Stored on raw-dataset metadata. |
| SynchrotronTomo | org | Link | link | instance metadata | h2kg:hasMetadata + dcterms:source | Stored as dataset/source metadata. |
| SynchrotronTomo | org | MaskExist | no | instance metadata | h2kg:hasMetadata | Stored on reconstructed-dataset metadata. |
| SynchrotronTomo | org | MaskLink | link | instance metadata | h2kg:hasMetadata + dcterms:source | Stored on reconstructed-dataset metadata. |
| SynchrotronTomo | syn | Step 1 | Carbon felt electrode -> Buy -> SInt1 | instance metadata | h2kg:Matter + h2kg:Process | Modeled as procurement metadata on a material instance. |
| SynchrotronTomo | syn | Step 2 | Unresolved workbook precursor label; 0.1 M -> Buy -> SInt2 | instance metadata | h2kg:Matter + h2kg:Process | Source label noise retained as metadata only. |
| SynchrotronTomo | syn | Step 3 | Unresolved workbook precursor label; 2 M -> Buy -> SInt3 | instance metadata | h2kg:Matter + h2kg:Process | Source label noise retained as metadata only. |
| SynchrotronTomo | syn | Step 4 | SInt2 -> Dissolve -> SInt4 | reuse existing term | h2kg:Process | Modeled as a labeled process instance. |
| SynchrotronTomo | syn | Step 5 | SInt3 -> Dissolve -> SInt5 | reuse existing term | h2kg:Process | Modeled as a labeled process instance. |
| SynchrotronTomo | syn | Step 6 | SInt4 -> Bubble (Gas = Nitrogen) -> Cell | reuse existing term | h2kg:Process | Modeled as a labeled process instance. |
| SynchrotronTomo | sp | Step 1 | Cell -> Heat -> SPInt1 | reuse existing term | h2kg:Manufacturing | Modeled as a labeled sample-conditioning step. |
| SynchrotronTomo | sp | Step 2 | SPInt1 -> Cool -> SPInt2 | reuse existing term | h2kg:Manufacturing | Modeled as a labeled sample-conditioning step. |
| SynchrotronTomo | sp | Step 3 | SPInt2 -> Cut -> Sample | reuse existing term | h2kg:Manufacturing | Modeled as a labeled sample-cutting step. |
| SynchrotronTomo | char | MeasurementMethod | Synchrotron X-ray tomography | reuse existing term | h2kg:XRayComputedTomographyMeasurement | Canonical public anchor for the combined round. |
| SynchrotronTomo | char | MeasurementType | ex-situ | instance metadata | h2kg:hasMetadata | Retained as measurement metadata in round 1. |
| SynchrotronTomo | char | Specimen | bulk material | instance metadata | h2kg:hasMetadata | Retained as measurement metadata in round 1. |
| SynchrotronTomo | char | Temperature | 23 deg C | reuse existing term | h2kg:Temperature | Modeled as a parameter-setting instance. |
| SynchrotronTomo | char | Humidity | 50 % | reuse existing term | h2kg:RelativeHumidity | Modeled as a parameter-setting instance. |
| SynchrotronTomo | char | Atmosphere | air | instance metadata | h2kg:hasMetadata | Retained as measurement metadata in round 1. |
| SynchrotronTomo | char | Pressure | 1 atm | instance metadata | h2kg:hasMetadata | Retained as measurement metadata in round 1. |
| SynchrotronTomo | char | Calibration | adjusting lenses and apertures; adjusting the voltage | instance metadata | h2kg:hasMetadata | Retained as calibration metadata. |
| SynchrotronTomo | inst | Facility | Canadian Light Source Inc. | instance metadata | h2kg:hasMetadata | Retained as facility metadata. |
| SynchrotronTomo | inst | Beamline | BMIT-ID 05ID-2 | instance metadata | h2kg:hasMetadata | Retained as beamline metadata. |
| SynchrotronTomo | inst | SourceMagneticField | 8.5 T | instance metadata | h2kg:hasMetadata | Retained as source metadata. |
| SynchrotronTomo | inst | MonochromatorType | Double layer monochromator | instance metadata | h2kg:hasMetadata | Retained as instrument metadata. |
| SynchrotronTomo | inst | EnergyResolution | 10^-2 | instance metadata | h2kg:hasMetadata | Retained as instrument metadata. |
| SynchrotronTomo | inst | XrayEnergy | 30 keV | reuse existing term | h2kg:XRayBeamEnergy | Modeled as a parameter-setting instance. |
| SynchrotronTomo | inst | PixelSize | 13 um | reuse existing term | h2kg:PixelSize | Modeled as a parameter-setting instance. |
| SynchrotronTomo | inst | FieldOfView | 26.68 x 8 mm | instance metadata | h2kg:hasMetadata | Retained as detector metadata. |
| SynchrotronTomo | inst | Magnification | 10 | reuse existing term | h2kg:Magnification | Modeled as a parameter-setting instance. |
| SynchrotronTomo | inst | Binning | None | instance metadata | h2kg:hasMetadata | Retained as detector metadata. |
| SynchrotronTomo | inst | ImagingTechnique | Absorption contrast tomography | instance metadata | h2kg:hasMetadata | Retained as acquisition metadata. |
| SynchrotronTomo | inst | MeasuringMode | Tomography fly scan | instance metadata | h2kg:hasMetadata | Retained as acquisition metadata. |
| SynchrotronTomo | inst | NumberOfRadiograms | 2000 | reuse existing term | h2kg:ProjectionNumber | Mapped to the reusable tomography projection-count parameter. |
| SynchrotronTomo | inst | ExposureTime | 50 ms | reuse existing term | h2kg:ExposureTime | Modeled as a parameter-setting instance. |
| SynchrotronTomo | inst | RotationDegree | 180 | instance metadata | h2kg:hasMetadata | Retained as acquisition metadata in round 1. |
| SynchrotronTomo | inst | NumberOfFlatFields | 210 | instance metadata | h2kg:hasMetadata | Retained as acquisition metadata in round 1. |
| SynchrotronTomo | inst | NumberOfDarkFields | 10 | instance metadata | h2kg:hasMetadata | Retained as acquisition metadata in round 1. |
| SynchrotronTomo | inst | SampleHolder | HIU bone cell | instance metadata | h2kg:hasMetadata | Retained as holder metadata. |
| SynchrotronTomo | inst | PositionReferences | 6 | instance metadata | h2kg:hasMetadata | Retained as positioning metadata. |
| SynchrotronTomo | inst | Scintillator | YAG | instance metadata | h2kg:hasMetadata | Retained as detector metadata. |
| SynchrotronTomo | inst | ScintillatorThickness | 500 um | instance metadata | h2kg:hasMetadata | Retained as detector metadata. |
| SynchrotronTomo | inst | Detector | Orca Flash V2 sCMOS | instance metadata | h2kg:hasMetadata | Retained as detector metadata. |
| SynchrotronTomo | inst | DetectorRawPx | 2560 x 2160 px | instance metadata | h2kg:hasMetadata | Retained as detector metadata. |
| SynchrotronTomo | inst | SampleElevation | 81 mm | instance metadata | h2kg:hasMetadata | Retained as positioning metadata. |
| SynchrotronTomo | inst | DistanceSampleSource | 58 m | instance metadata | h2kg:hasMetadata | Retained as source/beamline metadata. |
| SynchrotronTomo | inst | DistanceSampleDetector | 40 cm | reuse existing term | h2kg:SampleDetectorDistance | Mapped to the reusable tomography geometry parameter. |
| SynchrotronTomo | inst | SpatialResolution | 1 um | reuse existing term | h2kg:SpatialResolution | Mapped to the reusable tomography resolution parameter. |
| SynchrotronTomo | inst | Probe | High-intensity monochromatic synchrotron radiation | instance metadata | h2kg:hasMetadata | Retained as source metadata. |
| SynchrotronTomo | inst | Signal | Luminescent image; attenuated x-ray signal | instance metadata | h2kg:hasMetadata | Retained as signal metadata. |
| SynchrotronTomo | inst | TimeLapse | 1200 s | instance metadata | h2kg:hasMetadata | Retained as acquisition metadata in round 1. |
| SynchrotronTomo | inst | DataAdquisitionRate | 1 s | instance metadata | h2kg:hasMetadata | Retained as acquisition metadata in round 1. |
| SynchrotronTomo | pre | Step 1 | RawData -> Convert (8-bit) -> PPInt1 | reuse existing term | h2kg:Process | Modeled as a labeled preprocessing step. |
| SynchrotronTomo | pre | Step 2 | PPInt1 -> DarkFieldCorrect -> PPInt2 | reuse existing term | h2kg:Process | Modeled as a labeled preprocessing step. |
| SynchrotronTomo | pre | Step 3 | PPInt2 -> FlatFieldCorrect -> PPInt3 | reuse existing term | h2kg:Process | Modeled as a labeled preprocessing step. |
| SynchrotronTomo | pre | Step 4 | PPInt3 -> BackgroundCorrect -> PPInt4 | reuse existing term | h2kg:Process | Modeled as a labeled preprocessing step. |
| SynchrotronTomo | pre | Step 5 | PPInt4 -> 3DReconstruct -> PPInt5 | reuse existing term | h2kg:Process | Modeled as a labeled preprocessing step. |
| SynchrotronTomo | pre | Step 6 | PPInt5 -> ManualSegment -> Post-processed tomograph | reuse existing term | h2kg:Process | Modeled as a labeled preprocessing step. |
| SynchrotronTomo | anal | Step 1 | DecayFactorCalculation -> Decay factor = 51 ms | instance metadata | h2kg:DataPoint + h2kg:Metadata | Deferred analysis output represented as a datapoint with metadata only. |
| SynchrotronTomo | anal | Step 2 | BeamPathDistanceMeasurement -> Real distance in beam path = 99 cm | instance metadata | h2kg:DataPoint + h2kg:Metadata | Deferred analysis output represented as a datapoint with metadata only. |
| SynchrotronTomo | anal | Step 3 | ElectrolyteSaturationMeasurement -> Electrolyte saturation = 47 mol/l | instance metadata | h2kg:DataPoint + h2kg:Metadata | Deferred analysis output represented as a datapoint with metadata only. |
| SynchrotronTomo | anal | Step 4 | ElectrodeSegmentRatioCalculation -> carbonfelt/electrolyte/air ratio = 0.12640046296296295 | instance metadata | h2kg:DataPoint + h2kg:Metadata | Deferred analysis output represented as a datapoint with metadata only. |
| SynchrotronRadio | org | ExperimentTitle | Synchrotron x-ray radiography of a dry electrode | instance metadata | h2kg:hasMetadata + dcterms:title | Duplicate-structure validation sheet; only title differs from the canonical sheet. |
| SynchrotronRadio | org | ExperimentID | 6 | instance metadata | h2kg:hasMetadata + h2kg:hasIdentifier | Duplicate-structure validation sheet; identifier differs from the canonical sheet. |
| SynchrotronRadio | org | DOI | https://doi.org/10.3390/35e45447 | instance metadata | h2kg:hasMetadata + dcterms:identifier | Duplicate-structure validation sheet; publication metadata differs. |
| SynchrotronRadio | org | Journal | JACS | instance metadata | h2kg:hasMetadata | Duplicate-structure validation sheet; publication metadata differs. |
| SynchrotronRadio | org | Volume | 11 | instance metadata | h2kg:hasMetadata | Duplicate-structure validation sheet; publication metadata differs. |
| SynchrotronRadio | org | Issue | 12 | instance metadata | h2kg:hasMetadata | Duplicate-structure validation sheet; publication metadata differs. |
| SynchrotronRadio | org | Pages | 21-22 | instance metadata | h2kg:hasMetadata | Duplicate-structure validation sheet; publication metadata differs. |
| SynchrotronRadio | org | Topic | Battery | instance metadata | h2kg:hasMetadata | Duplicate-structure validation sheet; contradictory source label remains metadata only. |
| SynchrotronRadio | org | Device | VRFB | instance metadata | h2kg:hasMetadata | Duplicate-structure validation sheet; out-of-scope source label remains metadata only. |
| SynchrotronRadio | org | Granularity Level | Macrostructure | instance metadata | h2kg:hasMetadata | Duplicate-structure validation sheet; contextual metadata differs. |
| SynchrotronRadio | org | FileSize | 600 MB | instance metadata | h2kg:hasMetadata + dcterms:extent | Duplicate-structure validation sheet; dataset metadata differs. |
| SynchrotronRadio | org | DimensionZ | 780 | instance metadata | h2kg:hasMetadata | Duplicate-structure validation sheet; dataset metadata differs. |
| SynchrotronRadio | char | MeasurementMethod | Synchrotron X-ray tomography | reuse existing term | h2kg:XRayComputedTomographyMeasurement | Duplicate-structure validation confirms the same public method anchor. |
| SynchrotronRadio | inst | NumberOfRadiograms | 2000 | reuse existing term | h2kg:ProjectionNumber | Duplicate-structure validation confirms the same projection-count parameter mapping. |
| SynchrotronRadio | pre | All preprocessing rows | Same workflow as SynchrotronTomo | reuse existing term | h2kg:Process | Duplicate-structure validation confirms the same preprocessing pattern. |
| SynchrotronRadio | anal | All analysis rows | Same workflow as SynchrotronTomo | instance metadata | h2kg:DataPoint + h2kg:Metadata | Duplicate-structure validation confirms the same deferred-output policy. |
