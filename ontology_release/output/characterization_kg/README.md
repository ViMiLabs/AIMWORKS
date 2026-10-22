# H₂KG-backed characterization knowledge graph

This package is generated from the sanitized, fingerprinted corrected workbook manifest. The source workbook is not redistributed.

## Scope

- 8 case graphs across 7 method families
- 1635 of 1635 eligible workbook fields represented (100.00%)
- TEM is the principal bounded competency demonstration
- XRD and XPS are outside this workbook-backed package

## Modeling policy

The package uses H₂KG 2.3.0 classes and properties without changing the ontology taxonomy. Parameter records are distinct from intrinsic scientific properties. Missing, unconfirmed, inapplicable, unresolved-unit, and semantically conflicting source values remain explicit provenance records and are not silently normalized.

## Run

```bash
python run_demo.py --query q1_tem_specimen_preparation
```

The notebook and query files provide the equivalent RDFLib and SPARQL workflow. `validation_report.json` records SHACL conformance, negative tests, RDF serialization parity, and source coverage.
