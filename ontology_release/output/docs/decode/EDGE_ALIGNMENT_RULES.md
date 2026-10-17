# DECODE-to-H2KG Edge Alignment Rules

## Scope and invariants

These deterministic rules create the derived semantic-projection layer for
4463 preserved source dependencies.
The source layer is authoritative: labels, source IDs, native categories,
directions, and topology are never rewritten. Every projection cites its
originating `source_dependency_id` in the edge registry.

## Role assignment

Configured anchor mappings assign one intrinsic role to each occurrence:
`Matter`, `Manufacturing`, `Process`, `Measurement`, `Instrument`, `Parameter`,
`Data`, `Property`, or `Metadata`. Source categories remain provenance rather
than assertions of scientific identity. Explicit mapping overrides take
precedence over category defaults, and incompatible roles on one anchor fail
the semantic-role audit.

## Direct projections

| Source role pattern | Semantic projection |
| --- | --- |
| `Matter -> Activity` | reverse to `Activity hasInputMaterial Matter` |
| `Activity -> Matter` | `Activity hasOutputMaterial Matter` |
| `Parameter -> Activity` | reverse to `Activity hasParameter Parameter` |
| `Activity -> Parameter` | `Activity hasParameter Parameter` |
| `Instrument -> Activity` | reverse to `Activity usesInstrument Instrument` |
| `Activity -> Instrument` | `Activity usesInstrument Instrument` |
| `Data -> Activity` | reverse to `Activity hasInputData Data` |
| `Activity -> Data` | `Activity hasOutputData Data` |
| `Metadata -> Activity` | reverse to `Activity hasMetadata Metadata` |
| `Activity -> Metadata` | `Activity hasMetadata Metadata` |
| `Measurement -> Property` | `Measurement measures Property` |
| `Property -> Measurement` | reverse to `Measurement measures Property` |

`Activity` denotes a `Manufacturing`, `Measurement`, or `Process` occurrence.
Semantic direction may differ from source direction, but the source edge is
always retained independently.

## Property-value reification

Property-valued workflow nodes are not treated as datasets or parameter
records. Input properties receive contextual `Parameter` proxies and output
properties receive `DataPoint` proxies. Each proxy links to the preserved
property occurrence through `ofProperty`; activity input/output relations
target the proxy. Data-to-property and property-to-property derivations use
`prov:wasDerivedFrom` only when an H2KG activity predicate is not justified.

## Projection outcomes

- `h2kg_direct`: represented directly with a compatible H2KG predicate.
- `h2kg_reified`: represented through a Parameter or DataPoint proxy.
- `prov_derivation`: represented with compatible PROV-O derivation semantics.
- `decode_structural_only`: preserved without an unsupported semantic claim.

Cross-workflow joins require an explicit `approved_h2kg` or `decode_local`
anchor. Label similarity alone never creates a projection or workflow link.
