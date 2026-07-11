# XRD Case Summary

The XRD round demonstrates how H2KG captures a PEMFC-relevant Pt/C catalyst powder characterization case without introducing a second XRD method node. A catalyst-powder sample enters a conservative sample-conditioning step, is analyzed by `h2kg:XRayDiffractionMeasurement` using an `h2kg:XRayDiffractometer`, and yields an `h2kg:XRDPatternDataset` plus a generic `h2kg:ExperimentDataset` acquisition record. A downstream generic `h2kg:Process` instance represents peak analysis, from which `h2kg:DataPoint` instances are linked to `h2kg:DiffractionPeakPosition2Theta`, `h2kg:XRDPeakFWHM`, `h2kg:PtCrystalliteSize`, and `h2kg:TheoreticalMetalSurfaceArea`.

This keeps the public ontology Explore surface disciplined: users find reusable TBox anchors for XRD acquisition, datasets, parameters, and core Pt/C-derived outputs, while supplier details, holder details, and Scherrer-analysis assumptions remain metadata on example instances.
