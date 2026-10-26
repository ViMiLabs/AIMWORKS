# Benchmark population audit

- Source records: 8
- Method families: 7
- Unique characterization profiles: 7
- Distinct measurement-setting identities: 131
- Settings with a parseable number and recognized unit: 107
- Reported result records: 24
- Results with a parseable number and recognized unit: 13
- Result property/unit conflicts: 2

Numeric parsing and unit recognition do not establish scientific compatibility. The separate compatibility audit flags both duplicated `electrolyte saturation = 47 mol/L` records because saturation is ordinarily dimensionless whereas mol/L denotes concentration. The raw values remain queryable and are not treated as validated saturation quantities.

The two synchrotron sheets contain identical acquisition/instrument fields and workflow-table values. The sheet titled radiography reports `Synchrotron X-ray tomography` as its measurement method; both records are therefore one unique tomography profile for profile-level reporting.
