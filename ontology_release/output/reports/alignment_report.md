# Alignment Report

## Summary

- Accepted review-ready mappings: 21
- Exploratory mappings: 1145
- Manual overrides: 11
- Accepted exact matches: 8
- Accepted subclass or subproperty anchors: 6
- Accepted equivalence anchors: 3
- Accepted close matches: 4

## Rejected Candidate Counts

- `hdo_scope`: 744
- `kind_mismatch`: 164
- `deprecated_target`: 67
- `generic_electrochemical_measurement`: 48
- `chemical_non_exact`: 68
- `qudt_scaffold`: 3
- `metadata_scope`: 2

## Representative Accepted Mappings

- `Agent` -> `rdfs:subClassOf` -> `http://www.w3.org/ns/prov#Agent` (0.99)
- `Carbon Dioxide` -> `skos:exactMatch` -> `http://purl.obolibrary.org/obo/CHEBI_16526` (0.99)
- `Ethanol` -> `skos:exactMatch` -> `http://purl.obolibrary.org/obo/CHEBI_16236` (0.99)
- `FTIR Dataset` -> `rdfs:subClassOf` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00002013` (0.842)
- `Formic Acid` -> `skos:exactMatch` -> `http://purl.obolibrary.org/obo/CHEBI_30751` (0.99)
- `Hydrazine` -> `skos:exactMatch` -> `http://purl.obolibrary.org/obo/CHEBI_18280` (0.99)
- `Hydrochloric Acid` -> `skos:exactMatch` -> `http://purl.obolibrary.org/obo/CHEBI_17883` (0.99)
- `Hydrofluoric Acid` -> `skos:exactMatch` -> `http://purl.obolibrary.org/obo/CHEBI_29241` (0.99)
- `Measurement` -> `rdfs:subClassOf` -> `https://w3id.org/emmo/domain/electrochemistry#electrochemistry_7729c34e_1ae9_403d_b933_1765885e7f29` (0.99)
- `Metadata` -> `rdfs:subClassOf` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00000029` (0.904)
- `Metadata` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00001036` (0.776)
- `Microstructure Image Dataset` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00000005` (0.731)
- `PEMFCCFD Simulation` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00001069` (0.786)
- `Potassium Hydroxide` -> `skos:exactMatch` -> `http://purl.obolibrary.org/obo/CHEBI_32035` (0.99)
- `Process` -> `owl:equivalentClass` -> `https://w3id.org/emmo#EMMO_process` (1.0)
- `Property` -> `owl:equivalentClass` -> `https://w3id.org/emmo#EMMO_property` (1.0)
- `Water` -> `skos:exactMatch` -> `http://purl.obolibrary.org/obo/CHEBI_15377` (0.99)
- `hasIdentifier` -> `rdfs:subPropertyOf` -> `http://purl.org/dc/terms/identifier` (0.87)
- `hasMetadata` -> `owl:equivalentProperty` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00006069` (0.995)
- `hasMetadata` -> `skos:closeMatch` -> `https://purls.helmholtz-metadaten.de/hob/HDO_00006070` (0.772)
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
### hdo

- `FTIR Dataset` -> `rdfs:subClassOf` -> `FAIR data` (0.842)
- `Metadata` -> `rdfs:subClassOf` -> `Metadaten` (0.904)
- `Metadata` -> `skos:closeMatch` -> `Metadatenschema` (0.776)
- `Microstructure Image Dataset` -> `skos:closeMatch` -> `structured data` (0.731)
- `PEMFCCFD Simulation` -> `skos:closeMatch` -> `simulation data` (0.786)
### prov-o

- `Agent` -> `rdfs:subClassOf` -> `Agent` (0.99)
### qudt-schema

- `hasQuantityValue` -> `rdfs:subPropertyOf` -> `quantity value` (0.99)

## Exploratory Output

Exploratory mappings are preserved in `output/review/mapping_exploratory.csv` for internal research only. They are excluded from the published alignment TTL and should not be treated as accepted ontology alignments.

- `ATRFTIR Measurement` -> `Electrochemical measurement` [rejected_generic_electrochemical_measurement]
- `ATRFTIR Measurement` -> `semantic artefact` [rejected_hdo_scope]
- `Acetic Acid Solution` -> `simulation data` [rejected_hdo_scope]
- `Acetone` -> `acts upon` [rejected_kind_mismatch]
- `Acetone` -> `agent role` [rejected_hdo_scope]
- `Acetonitrile` -> `agent role` [rejected_hdo_scope]
- `Acetonitrile` -> `Einheitsrolle` [rejected_hdo_scope]
- `Acid Doping` -> `Formic acid` [rejected_chemical_non_exact]
- `Acid Doping` -> `Hydrochloric acid` [rejected_chemical_non_exact]
- `Acid Doping` -> `Hydrofluoric acid` [rejected_chemical_non_exact]
- `Acid Etching Repetitions` -> `action specification` [rejected_hdo_scope]
- `Acid Uptake Dataset` -> `Data Lake` [rejected_hdo_scope]
- `Acid Uptake Dataset` -> `obsolete abstract data type` [rejected_deprecated_target]
- `Acid Uptake Dataset` -> `assigns data type to` [rejected_kind_mismatch]
- `Acid Uptake Measurement` -> `Electrochemical measurement` [rejected_generic_electrochemical_measurement]
- `Acid Value` -> `Quantity value` [rejected_qudt_scaffold]
- `Acid Value` -> `quantity value` [rejected_kind_mismatch]
- `Acid Value` -> `programmatic value` [rejected_hdo_scope]
- `Activated Sludge` -> `directed edge` [rejected_hdo_scope]
- `Additive A` -> `qualitative Daten` [rejected_hdo_scope]
- `Additive A` -> `quantitative Daten` [rejected_hdo_scope]
- `Aemion Ionomer` -> `Taxonomische Daten` [rejected_hdo_scope]
- `Ag NW Surface Density` -> `software agent` [rejected_hdo_scope]
- `Aggregate Aspect Ratio` -> `creates specification` [rejected_kind_mismatch]
- `Aggregate Aspect Ratio` -> `semantic artefact` [rejected_hdo_scope]

## Policy Notes

- HDO is restricted to true data, metadata, identifier, digital-object, schema, validation, and information-profile concepts.
- QUDT scaffold targets such as `QuantityValue` are excluded for domain concepts unless explicitly curated.
- ChEBI remains limited to exact or manually curated chemical matches.
- Generic electrochemical measurement anchors are blocked for automatic proposals unless explicitly curated.
