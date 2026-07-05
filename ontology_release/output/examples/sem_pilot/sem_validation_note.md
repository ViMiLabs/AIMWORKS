# SEM Validation Note

## Ontology changes introduced in the SEM round

- No new SEM-specific TBox classes or parameters were introduced in this round.
- Existing SEM-related vocabulary entries were strengthened so the Explore/Search page can expose a coherent SEM neighborhood directly from the ontology.
- `ScanningElectronMicroscopyImaging`, `SEM Imaging`, and `SEM Imaging Measurement` were updated to point explicitly to shared SEM acquisition parameters and SEM output datasets.
- `Magnification`, `WorkingDistance`, `SEM Image Dataset`, and `SEM Micrograph Dataset` were generalized textually so they now describe SEM usage explicitly instead of remaining TEM-biased or too narrow.

## What remained instance metadata in round 1

- Organizational, bibliographic, file, and access details from the `org` section.
- `MeasurementType`, `Specimen`, `Atmosphere`, `Pressure`, and `Calibration` from the `char` section.
- `MicroscopeBrand`, `Cathode`, `Probe`, `Detector`, `ImagingTechnique`, `Signal`, `TimeLapse`, and raw-data descriptors from the `inst` section.
- Supplier, lot-number, CAS, and mounting details from the preparation sections.

## What was intentionally deferred

- No new TBox terms were introduced for `Buy`, `Sieve`, `Fix`, `Contrast adjustment`, `Brightness adjustment`, or `Manual particle measurement`; these remain labeled process instances.
- No dedicated metadata sub-vocabulary was introduced for detector, imaging mode, signal, or calibration fields in this first SEM round.
- The SEM pilot creates a `CatalystParticleDiameter` result data point, but the source sheet does not report a numeric result value, so no quantity value is attached.
