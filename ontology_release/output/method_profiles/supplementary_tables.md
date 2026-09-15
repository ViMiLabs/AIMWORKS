# Supplementary Tables S1-S9: H2KG Method Data Profiles

Each profile consists of a SHACL constraint file, value-free JSON-LD capture template, field dictionary, copied pilot record, and validation report. `source_grounded` means the example originates from the integrated pilot material. The XPS profile is structurally validated but its existing pilot is illustrative.

## Table S1. Transmission electron microscopy

| Element | H2KG anchor(s) | Rule |
| --- | --- | --- |
| Measurement | `h2kg:TransmissionElectronMicroscopyImaging` | One typed measurement occurrence. |
| Instrument | `h2kg:TEMInstrument` | At least one linked instrument. |
| Dataset chain | `h2kg:MicrostructureImageDataset` | At least one raw output dataset. |
| Conditional parameters | `h2kg:AcceleratingVoltage, h2kg:Magnification, h2kg:WorkingDistance, h2kg:Temperature, h2kg:RelativeHumidity, h2kg:VacuumChamberPressure` | Capture only when reported or method-defining; numeric values require QUDT quantity values. |
| Results | `h2kg:PdNanoparticleDiameter` | At least one DataPoint or explicit missing-value metadata. |
| Evidence boundary | Metadata | Detector, grid, specimen descriptors, file details, and publication details remain metadata. |

## Table S2. Scanning electron microscopy

| Element | H2KG anchor(s) | Rule |
| --- | --- | --- |
| Measurement | `h2kg:ScanningElectronMicroscopyImaging` | One typed measurement occurrence. |
| Instrument | `h2kg:SEMInstrument` | At least one linked instrument. |
| Dataset chain | `h2kg:SEMImageDataset` | At least one raw output dataset. |
| Conditional parameters | `h2kg:AcceleratingVoltage, h2kg:Magnification, h2kg:WorkingDistance, h2kg:Temperature, h2kg:RelativeHumidity` | Capture only when reported or method-defining; numeric values require QUDT quantity values. |
| Results | `h2kg:CatalystParticleDiameter` | At least one DataPoint or explicit missing-value metadata. |
| Evidence boundary | Metadata | Detector mode, supplier information, image-file details, and publication details remain metadata. |

## Table S3. FIB-SEM tomography

| Element | H2KG anchor(s) | Rule |
| --- | --- | --- |
| Measurement | `h2kg:FIBSEMTomographyMeasurement` | One typed measurement occurrence. |
| Instrument | `h2kg:FIBSEMInstrument` | At least one linked instrument. |
| Dataset chain | `h2kg:SEMImageDataset, h2kg:TomographicReconstructionDataset` | At least one raw output dataset. |
| Conditional parameters | `h2kg:IonBeamEnergy, h2kg:IonBeamCurrent, h2kg:ElectronBeamEnergy, h2kg:ElectronCurrent, h2kg:VoxelSize, h2kg:SliceNumber, h2kg:CutThickness, h2kg:StageTilt, h2kg:DwellTime, h2kg:ExposureTime, h2kg:Magnification, h2kg:MicroscopyMeasuredArea, h2kg:Temperature, h2kg:RelativeHumidity, h2kg:VacuumChamberPressure, h2kg:TotalAcquisitionTime` | Capture only when reported or method-defining; numeric values require QUDT quantity values. |
| Results | `h2kg:TotalPorosity, h2kg:GeodesicTortuosity, h2kg:Constrictivity` | At least one DataPoint or explicit missing-value metadata. |
| Evidence boundary | Metadata | Instrument settings not represented by reusable parameters, segmentation choices, and file details remain metadata. |

## Table S4. Ion-cut scanning electron microscopy

| Element | H2KG anchor(s) | Rule |
| --- | --- | --- |
| Measurement | `h2kg:ICSEMImagingMeasurement` | One typed measurement occurrence. |
| Instrument | `h2kg:ICSEMInstrument` | At least one linked instrument. |
| Dataset chain | `h2kg:SEMImageDataset, h2kg:SEMMicrographDataset` | At least one raw output dataset. |
| Conditional parameters | `h2kg:IonBeamEnergy, h2kg:IonBeamCurrent, h2kg:ElectronBeamEnergy, h2kg:ElectronCurrent, h2kg:PixelSize, h2kg:CutThickness, h2kg:DwellTime, h2kg:ExposureTime, h2kg:Magnification, h2kg:MicroscopyMeasuredArea, h2kg:Temperature, h2kg:RelativeHumidity, h2kg:VacuumChamberPressure, h2kg:TotalAcquisitionTime` | Capture only when reported or method-defining; numeric values require QUDT quantity values. |
| Results | `h2kg:MembraneElectrodeAssemblyThickness, h2kg:GasDiffusionLayerThickness, h2kg:TotalPorosity` | At least one DataPoint or explicit missing-value metadata. |
| Evidence boundary | Metadata | Cutting details, detector settings, and study-specific context remain metadata. |

## Table S5. Atomic force microscopy

| Element | H2KG anchor(s) | Rule |
| --- | --- | --- |
| Measurement | `h2kg:AtomicForceMicroscopyMeasurement` | One typed measurement occurrence. |
| Instrument | `h2kg:AFMInstrument` | At least one linked instrument. |
| Dataset chain | `h2kg:MicrostructureImageDataset, h2kg:SurfaceTopographyDataset` | At least one raw output dataset. |
| Conditional parameters | `h2kg:AFMScanSpeed, h2kg:AFMTipNominalRadius, h2kg:MicroscopyMeasuredArea, h2kg:Temperature, h2kg:RelativeHumidity, h2kg:CantileverSpringConstant, h2kg:CantileverResonanceFrequency` | Capture only when reported or method-defining; numeric values require QUDT quantity values. |
| Results | `h2kg:MeanParticleSize` | At least one DataPoint or explicit missing-value metadata. |
| Evidence boundary | Metadata | AFM mode, tip model, sensitivity, resolution, and local file details remain metadata unless reusable across cases. |

## Table S6. Neutron tomography

| Element | H2KG anchor(s) | Rule |
| --- | --- | --- |
| Measurement | `h2kg:NeutronTomographyMeasurement` | One typed measurement occurrence. |
| Instrument | `h2kg:NeutronTomographyInstrument` | At least one linked instrument. |
| Dataset chain | `h2kg:TomographicProjectionDataset, h2kg:TomographicReconstructionDataset, h2kg:ExperimentDataset` | At least one raw output dataset. |
| Conditional parameters | `h2kg:PixelSize, h2kg:ExposureTime, h2kg:ProjectionNumber, h2kg:NeutronFlux, h2kg:SpatialResolution, h2kg:SampleDetectorDistance, h2kg:Temperature, h2kg:RelativeHumidity` | Capture only when reported or method-defining; numeric values require QUDT quantity values. |
| Results | `h2kg:TortuosityFactor, h2kg:AverageWaterDropletArea, h2kg:AverageWaterDropletCount` | At least one DataPoint or explicit missing-value metadata. |
| Evidence boundary | Metadata | Facility, beamline, detector, holder, and ambiguous source descriptors remain metadata. |

## Table S7. Synchrotron X-ray tomography

| Element | H2KG anchor(s) | Rule |
| --- | --- | --- |
| Measurement | `h2kg:XRayComputedTomographyMeasurement` | One typed measurement occurrence. |
| Instrument | `h2kg:XRayCTInstrument` | At least one linked instrument. |
| Dataset chain | `h2kg:TomographicProjectionDataset, h2kg:TomographicReconstructionDataset, h2kg:ExperimentDataset` | At least one raw output dataset. |
| Conditional parameters | `h2kg:XRayBeamEnergy, h2kg:ExposureTime, h2kg:PixelSize, h2kg:ProjectionNumber, h2kg:SpatialResolution, h2kg:SampleDetectorDistance, h2kg:Temperature, h2kg:RelativeHumidity, h2kg:Magnification` | Capture only when reported or method-defining; numeric values require QUDT quantity values. |
| Results | `Deferred` | Output property semantics deferred in this profile. |
| Evidence boundary | Metadata | Facility, beamline, detector, sample-holder, and deferred output semantics remain metadata. |

## Table S8. X-ray diffraction

| Element | H2KG anchor(s) | Rule |
| --- | --- | --- |
| Measurement | `h2kg:XRayDiffractionMeasurement` | One typed measurement occurrence. |
| Instrument | `h2kg:XRayDiffractometer` | At least one linked instrument. |
| Dataset chain | `h2kg:XRDPatternDataset, h2kg:ExperimentDataset` | At least one raw output dataset. |
| Conditional parameters | `h2kg:XRayWavelength, h2kg:XRDStepSize, h2kg:XRDTwoThetaStart, h2kg:XRDTwoThetaEnd` | Capture only when reported or method-defining; numeric values require QUDT quantity values. |
| Results | `h2kg:DiffractionPeakPosition2Theta, h2kg:XRDPeakFWHM, h2kg:PtCrystalliteSize, h2kg:TheoreticalMetalSurfaceArea` | At least one DataPoint or explicit missing-value metadata. |
| Evidence boundary | Metadata | Sample-holder, scan implementation details, fitting choices, and bibliographic details remain metadata. |

## Table S9. X-ray photoelectron spectroscopy

| Element | H2KG anchor(s) | Rule |
| --- | --- | --- |
| Measurement | `h2kg:XRayPhotoelectronSpectroscopyMeasurement` | One typed measurement occurrence. |
| Instrument | `h2kg:XPSInstrument` | At least one linked instrument. |
| Dataset chain | `h2kg:XPSDataset, h2kg:ExperimentDataset` | At least one raw output dataset. |
| Conditional parameters | `h2kg:XPSPassEnergy, h2kg:XPSTakeOffAngle, h2kg:XPSAnalysisArea` | Capture only when reported or method-defining; numeric values require QUDT quantity values. |
| Results | `h2kg:BindingEnergy, h2kg:C1sAtomicPercent, h2kg:O1sAtomicPercent, h2kg:F1sAtomicPercent, h2kg:N1sAtomicPercent, h2kg:CarbonToOxygenAtomRatio, h2kg:MetalAtomicPercent` | At least one DataPoint or explicit missing-value metadata. |
| Evidence boundary | Metadata | Spectral fitting conventions, instrument brand/model, and source-specific preparation details remain metadata. |
