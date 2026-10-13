# AFM Validation Note

## Ontology changes introduced in the AFM round

- Reused and broadened the existing public AFM vocabulary rather than introducing a parallel AFM measurement node.
- `h2kg:AtomicForceMicroscopyMeasurement` now supports a wider AFM neighborhood for ex-situ catalyst-layer and MEA microstructure/topography characterization while preserving the prior in-situ AFM use.
- `h2kg:AFMInstrument` was kept as the public AFM instrument anchor and generalized textually for broader AFM usage.
- New public AFM parameters introduced in this round:
  - `h2kg:AFMScanSpeed`
  - `h2kg:AFMTipNominalRadius`
- `h2kg:MeanParticleSize` was broadened so it can support both legacy particle-sizing contexts and AFM-derived size results.

## What remained instance metadata in round 1

- Organizational, bibliographic, file, and access details from the `org` section.
- `MeasurementType`, `Specimen`, `Atmosphere`, `Pressure`, and `Calibration` from the `char` section.
- AFM mode, tip model, lock-in amplifier, sensitivity, resolution, and data-acquisition-rate fields from the `inst` section.
- Supplier, lot-number, CAS, mounting-disc, resin, and sectioning details from the preparation sections.

## What was intentionally deferred

- No public TBox terms were introduced for `Buy`, `Sieve`, `Dry`, `Cut`, `Embedded`, `Curated`, `Microtome cut`, `Fix`, `Contrast adjustment`, `Brightness adjustment`, or `Manual particle measurement`; these remain labeled process instances.
- No dedicated AFM metadata sub-vocabulary was introduced for mode, tip, amplifier, sensitivity, or calibration fields in this first AFM round.
- The worksheet value `Raw data = electron images` is preserved only as metadata because it is a sheet descriptor rather than a reusable ontology node.
