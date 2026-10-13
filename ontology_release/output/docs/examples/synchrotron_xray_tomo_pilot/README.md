# Synchrotron X-Ray Tomography Pilot Package

This package contains the controlled combined `SynchrotronTomo` / `SynchrotronRadio` integration outputs for H2KG.

Generated files:

- `synchrotron_xray_tomo_mapping_matrix.csv`
- `synchrotron_xray_tomo_mapping_matrix.md`
- `synchrotron_xray_tomo_example.jsonld`
- `synchrotron_xray_tomo_example.ttl`
- `synchrotron_xray_tomo_validation_note.md`
- `synchrotron_xray_tomo_case_summary.md`
- `synchrotron_xray_tomo_follow_on_gaps.md`
- `synchrotron_xray_tomo_manuscript_figure.md`
- `synchrotron_xray_tomo_manuscript_table.md`

Highlights:

- Public measurement anchor reused and normalized: `h2kg:XRayComputedTomographyMeasurement`
- Public instrument anchor reused and normalized: `h2kg:XRayCTInstrument`
- Public dataset anchors reused and generalized: `h2kg:TomographicProjectionDataset`, `h2kg:TomographicReconstructionDataset`
- No new public derived-property terms added in this round
- `SynchrotronRadio` handled as duplicate-structure validation rather than a separate public method node
