# DECODE-to-H2KG Edge Alignment Rules

## Scope and invariants

This document specifies the deterministic rules used to create the derived
DECODE semantic-projection layer. It applies to 3,986 immutable GraphML source
dependencies and 290 PDF-derived multiscale-interface dependencies.

The source layer is authoritative. The release never changes a source GraphML
node label, GraphML identifier, native category, edge identifier, source edge
direction, or source topology. A semantic projection is an additional,
traceable statement. Every projection records the original
`source_dependency_id` in `decode_edge_registry.csv` and JSON.

## 1. Role assignment

Each source occurrence receives one reviewed semantic role before edge mapping.
The default mapping from native DECODE categories is:

| Native DECODE category | Default H2KG semantic role |
| --- | --- |
| `material`, `component` | `Matter` |
| `data` | `Data` |
| `device` | `Instrument` |
| `process` | `Manufacturing` |
| `method` | `Measurement` |
| `model` | `Process` |
| `other` | `Metadata` |

The source category is provenance, not scientific truth. Explicit reviewed
overrides in `config/decode_workflow_mappings.yaml` take precedence. Examples
include `CLSM temperature -> Parameter`, `LRE pH distribution -> Data`, and
`Inert substrate -> Matter`. Conflicting roles on one shared anchor fail the
role-quality audit; the renderer does not silently select a role.

`Manufacturing`, `Measurement`, and `Process` are activity roles. The other
roles are entity/value-context roles.

## 2. Mapping prerequisites

1. Only anchors approved in the versioned DECODE mapping configuration can
   support H2KG semantic projections or cross-workflow joins.
2. Lexical similarity alone never creates an edge mapping or a cross-workflow
   connection.
3. Explicit, reviewed edge overrides take precedence over the generic rules.
4. An H2KG predicate is emitted only if its endpoint roles are compatible.
5. The semantic direction may differ from the source direction. This corrects
   the representation to H2KG relation direction while preserving the original
   dependency unchanged.

## 3. Direct H2KG projections

The following role-aware patterns are applied after any explicit override.
`Activity` means `Manufacturing`, `Measurement`, or `Process`.

| Preserved source direction | Derived semantic statement | Predicate |
| --- | --- | --- |
| `Matter -> Activity` | `Activity -> Matter` | `h2kg:hasInputMaterial` |
| `Activity -> Matter` | `Activity -> Matter` | `h2kg:hasOutputMaterial` |
| `Parameter -> Activity` | `Activity -> Parameter` | `h2kg:hasParameter` |
| `Activity -> Parameter` | `Activity -> Parameter` | `h2kg:hasParameter` |
| `Instrument -> Activity` | `Activity -> Instrument` | `h2kg:usesInstrument` |
| `Activity -> Instrument` | `Activity -> Instrument` | `h2kg:usesInstrument` |
| `Data -> Activity` | `Activity -> Data` | `h2kg:hasInputData` |
| `Activity -> Data` | `Activity -> Data` | `h2kg:hasOutputData` |
| `Metadata -> Activity` | `Activity -> Metadata` | `h2kg:hasMetadata` |
| `Activity -> Metadata` | `Activity -> Metadata` | `h2kg:hasMetadata` |
| `Measurement -> Property` | `Measurement -> Property anchor` | `h2kg:measures` |
| `Property -> Measurement` | `Measurement -> Property anchor` | `h2kg:measures` |

For an explicit override, the release applies the same direction normalization
to `hasInputMaterial`, `hasInputData`, `hasParameter`, and `usesInstrument`.
The original GraphML direction remains visible as a solid source-dependency
arrow; the H2KG direction is visible as a separate semantic arrow.

## 4. Reified property-value projections

A property class is not itself a dataset or numeric result. If a source edge
uses a `Property` as an input, output, or dependency, the release creates a
derived `h2kg:DataPoint` proxy for that *occurrence* rather than connecting the
activity directly to the property class.

| Preserved role pattern | Derived representation |
| --- | --- |
| `Property -> Activity` | `Activity h2kg:hasInputData DataPoint`; `DataPoint h2kg:ofProperty Property` |
| `Activity -> Property` | `Activity h2kg:hasOutputData DataPoint`; `DataPoint h2kg:ofProperty Property` |
| `Property -> Property` | source and target DataPoint proxies linked by `prov:wasDerivedFrom`, each typed by `h2kg:ofProperty` |
| `Data -> Property` | target DataPoint derived from source data by `prov:wasDerivedFrom`, typed by `h2kg:ofProperty` |
| `Property -> Data` | target data derived from source DataPoint proxy by `prov:wasDerivedFrom` |

Each proxy preserves the source occurrence identifier, label, canonical property
anchor, and the edge that caused the reification. A proxy does not enter the
H2KG TBox or the TBox-only H2KG Explore page.

## 5. PROV-O projections

The release uses PROV-O only for compatible provenance statements:

| Preserved role pattern | Derived statement |
| --- | --- |
| `Activity -> Activity` | target `prov:wasInformedBy` source |
| `Data -> Data` | target `prov:wasDerivedFrom` source |
| Property-value/data transformations | `prov:wasDerivedFrom` between the compatible data or DataPoint proxy nodes |

`h2kg:fromMeasurement` is not inferred from an ordinary workflow edge. It is
used only when explicit source evidence identifies a producing measurement.
Similarly, `prov:wasDerivedFrom` is not used for arbitrary structural
dependencies without a data/value derivation interpretation.

## 6. Structural-only outcome

An edge receives `decode_structural_only` when the source topology lacks enough
scientific context to assert a role-compatible H2KG or PROV-O predicate. This
is a valid, reviewed classification, not an unprocessed error. No artificial
`dependsOn` predicate is created merely to force coverage.

## 7. Four required outcomes

Every source dependency has exactly one registry outcome:

| Outcome | Meaning |
| --- | --- |
| `h2kg_direct` | one or more direct, role-compatible H2KG predicate statements |
| `h2kg_reified` | H2KG representation through an occurrence-level `DataPoint` proxy |
| `prov_derivation` | compatible PROV-O activity or data provenance statement |
| `decode_structural_only` | preserved DECODE dependency with no defensible semantic assertion from current evidence |

## 8. Validation and release evidence

The release validates that every source edge has exactly one registry record,
every semantic edge is registered and traces to its source dependency, every
outcome is valid, and source GraphML node/edge parity is preserved. The
validation report also audits shared-anchor role conflicts and source/semantic
edge consistency.

For this release, the registry contains 4,276 classified source dependencies:
2,232 `h2kg_direct`, 1,606 `h2kg_reified`, 22 `prov_derivation`, and 416
`decode_structural_only`. The 3,986 original GraphML dependencies remain
unchanged; 290 additional dependencies belong to the explicitly separate
PDF-derived multiscale interface schema.

## Reproducibility artifacts

- `config/decode_workflow_mappings.yaml`: reviewed occurrence-role and anchor
  decisions, plus explicit edge overrides.
- `decode_edge_registry.csv` and `.json`: one complete decision record per
  source edge.
- `decode_validation_report.json`: machine-readable integrity and outcome
  checks.
- `decode_federated_graph.json`: source layer, semantic projections, and
  occurrence-level provenance.
- Per-workflow `.json`, `.jsonld`, and `.ttl` exports: reproducible workflow
  projections.
