# Alignment Report

## Summary

- Accepted review-ready mappings: 14
- Exploratory mappings: 135
- Manual overrides: 11
- Accepted exact matches: 8
- Accepted subclass or subproperty anchors: 4
- Accepted equivalence anchors: 2
- Accepted close matches: 0

## Rejected Candidate Counts

- `generic_electrochemical_measurement`: 49
- `chemical_non_exact`: 68
- `kind_mismatch`: 3
- `qudt_scaffold`: 3
- `metadata_scope`: 2

## Representative Accepted Mappings

- `Agent` -> `rdfs:subClassOf` -> `http://www.w3.org/ns/prov#Agent` (0.99)
- `Carbon Dioxide` -> `skos:exactMatch` -> `http://purl.obolibrary.org/obo/CHEBI_16526` (0.99)
- `Ethanol` -> `skos:exactMatch` -> `http://purl.obolibrary.org/obo/CHEBI_16236` (0.99)
- `Formic Acid` -> `skos:exactMatch` -> `http://purl.obolibrary.org/obo/CHEBI_30751` (0.99)
- `Hydrazine` -> `skos:exactMatch` -> `http://purl.obolibrary.org/obo/CHEBI_18280` (0.99)
- `Hydrochloric Acid` -> `skos:exactMatch` -> `http://purl.obolibrary.org/obo/CHEBI_17883` (0.99)
- `Hydrofluoric Acid` -> `skos:exactMatch` -> `http://purl.obolibrary.org/obo/CHEBI_29241` (0.99)
- `Measurement` -> `rdfs:subClassOf` -> `https://w3id.org/emmo/domain/electrochemistry#electrochemistry_7729c34e_1ae9_403d_b933_1765885e7f29` (0.99)
- `Potassium Hydroxide` -> `skos:exactMatch` -> `http://purl.obolibrary.org/obo/CHEBI_32035` (0.99)
- `Process` -> `owl:equivalentClass` -> `https://w3id.org/emmo#EMMO_process` (1.0)
- `Property` -> `owl:equivalentClass` -> `https://w3id.org/emmo#EMMO_property` (1.0)
- `Water` -> `skos:exactMatch` -> `http://purl.obolibrary.org/obo/CHEBI_15377` (0.99)
- `hasIdentifier` -> `rdfs:subPropertyOf` -> `http://purl.org/dc/terms/identifier` (0.87)
- `hasQuantityValue` -> `rdfs:subPropertyOf` -> `http://qudt.org/schema/qudt/quantityValue` (0.99)

## Accepted Mappings by Source

### chebi

- `Carbon Dioxide` -> `skos:exactMatch` -> `Carbon dioxide` (0.99)
- `Ethanol` -> `skos:exactMatch` -> `Ethanol` (0.99)
- `Formic Acid` -> `skos:exactMatch` -> `Formic acid` (0.99)
- `Hydrazine` -> `skos:exactMatch` -> `Hydrazine` (0.99)
- `Hydrochloric Acid` -> `skos:exactMatch` -> `Hydrochloric acid` (0.99)
### dcterms

- `hasIdentifier` -> `rdfs:subPropertyOf` -> `identifier` (0.87)
### emmo-core

- `Process` -> `owl:equivalentClass` -> `Process` (1.0)
- `Property` -> `owl:equivalentClass` -> `Property` (1.0)
### emmo-electrochemistry

- `Measurement` -> `rdfs:subClassOf` -> `Electrochemical measurement` (0.99)
### prov-o

- `Agent` -> `rdfs:subClassOf` -> `Agent` (0.99)
### qudt-schema

- `hasQuantityValue` -> `rdfs:subPropertyOf` -> `quantity value` (0.99)

## Exploratory Output

Exploratory mappings are preserved in `output/review/mapping_exploratory.csv` for internal research only. They are excluded from the published alignment TTL and should not be treated as accepted ontology alignments.

- `ATRFTIR Measurement` -> `Electrochemical measurement` [rejected_generic_electrochemical_measurement]
- `Acid Doping` -> `Formic acid` [rejected_chemical_non_exact]
- `Acid Doping` -> `Hydrochloric acid` [rejected_chemical_non_exact]
- `Acid Doping` -> `Hydrofluoric acid` [rejected_chemical_non_exact]
- `Acid Uptake Measurement` -> `Electrochemical measurement` [rejected_generic_electrochemical_measurement]
- `Acid Value` -> `Quantity value` [rejected_qudt_scaffold]
- `Acid Value` -> `quantity value` [rejected_kind_mismatch]
- `Archimedes Density Measurement` -> `Electrochemical measurement` [rejected_generic_electrochemical_measurement]
- `Argon` -> `Agent` [rejected_metadata_scope]
- `Carbon Dioxide Percent` -> `Carbon dioxide` [rejected_chemical_non_exact]
- `Carbon Felt Electrode` -> `Carbon dioxide` [rejected_chemical_non_exact]
- `Carbon Fiber` -> `Carbon dioxide` [rejected_chemical_non_exact]
- `Carbon Fiber Diameter` -> `Carbon dioxide` [rejected_chemical_non_exact]
- `Carbon Mass` -> `Carbon dioxide` [rejected_chemical_non_exact]
- `Carbon Nanotube` -> `Carbon dioxide` [rejected_chemical_non_exact]
- `Carbon Oxide Fraction Percent` -> `Carbon dioxide` [rejected_chemical_non_exact]
- `Carbon Support` -> `Carbon dioxide` [rejected_chemical_non_exact]
- `Carbon Yield` -> `Carbon dioxide` [rejected_chemical_non_exact]
- `Castor Oil` -> `Material` [exploratory_candidate]
- `Chronoamperometry Measurement` -> `Electrochemical measurement` [rejected_generic_electrochemical_measurement]
- `Chronopotentiometry Measurement` -> `Electrochemical measurement` [rejected_generic_electrochemical_measurement]
- `Coating Mass Measurement` -> `Electrochemical measurement` [rejected_generic_electrochemical_measurement]
- `Coating Weight Measurement` -> `Electrochemical measurement` [rejected_generic_electrochemical_measurement]
- `Contact Angle` -> `Agent` [rejected_metadata_scope]
- `Contact Angle Measurement` -> `Electrochemical measurement` [rejected_generic_electrochemical_measurement]

## Policy Notes

- HDO is restricted to true data, metadata, identifier, digital-object, schema, validation, and information-profile concepts.
- QUDT scaffold targets such as `QuantityValue` are excluded for domain concepts unless explicitly curated.
- ChEBI remains limited to exact or manually curated chemical matches.
- Generic electrochemical measurement anchors are blocked for automatic proposals unless explicitly curated.
