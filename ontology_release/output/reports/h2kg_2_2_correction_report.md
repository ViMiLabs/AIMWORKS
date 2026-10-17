# H₂KG 2.2 Taxonomy and Definition Correction Report

- Source fingerprint: `998E1F7765175456B955CD8EB777D550ECF1B47E0D77AF03C6BB3F0585C6CB04`
- Decisions: 626 (156 parent; 470 definition)
- Unique classes covered: 544
- Source-dependent classes assessed: 153
- Source-ambiguous classes deprecated: 152
- Source-dependent classes resolved: 1
- Active classes: 2360 -> 2221
- Deprecated compatibility classes: 6 -> 165
- Validation conforms: True
- Competency checks: 9 / 9

## Final Actions

- apply: 455
- deprecate_source_ambiguous: 157
- replace: 7
- retain: 6
- split: 1

## Interpretation

The canonical release applies only registry-backed parent and definition decisions. Scientifically underdetermined terms are retained as deprecated compatibility resources rather than assigned a guessed identity. Stable H₂KG IRIs remain resolvable, and profile-specific identity changes are recorded in the migration registry.

The complete 626-row decision ledger is available in `h2kg_2_2_correction_decisions.csv` and in the JSON report.
