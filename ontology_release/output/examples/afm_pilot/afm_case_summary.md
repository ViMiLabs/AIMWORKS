# AFM Case Summary

The AFM pilot demonstrates how H2KG can represent an atomic-force-microscopy workflow for PEMFC catalyst-layer and MEA-related characterization without duplicating the public AFM measurement vocabulary. The acquisition is represented as an `AtomicForceMicroscopyMeasurement` linked to an `AFMInstrument`, explicit acquisition-parameter settings such as temperature, relative humidity, measured area, AFM scan speed, and AFM tip nominal radius, and a raw `MicrostructureImageDataset`.

Two preprocessing steps, contrast adjustment and brightness adjustment, transform the raw AFM dataset into a processed dataset typed as both `SurfaceTopographyDataset` and `MicrostructureImageDataset`. An analysis step uses `FijiImageJSoftware` to derive the scientific result as a `DataPoint` for `MeanParticleSize`, linked back to the AFM measurement through `fromMeasurement` and to the analysis process through `prov:wasGeneratedBy`.

The pilot remains conservative about ontology growth: worksheet-specific operational labels stay at instance level, while the public AFM node exposed in Explore is strengthened through reusable TBox links to instrument, parameters, datasets, and the measured-property anchor.
