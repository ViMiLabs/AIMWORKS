# Supplementary information

## A domain-specific ontology for interoperable hydrogen electrochemical research workflows

Marjan Kohandani, Mohammad J. Eslamibidgoli, Said Fathallah, Michael H. Eikerling, and Kourosh Malek

This supplement documents the exact H₂KG 2.2.0 release state used in the article. It contains taxonomy and relation metrics, correction outcomes, competency checks, the complete ontology-level TIB benchmark, asserted-alignment counts, and the synthetic transmission electron microscopy profile. It contains no experimental data and no additional characterization-method case studies.

## Supplementary Table S1. Taxonomy content and top-branch distribution

| Metric | Count |
| --- | ---: |
| Active local classes | 2,221 |
| Deprecated compatibility classes | 165 |
| New structural classes | 157 |
| Subclass axioms | 2,221 |
| Object properties | 23 |
| Datatype properties | 1 |
| Annotation properties | 9 |
| Named taxonomy individuals | 0 |
| Agent branch | 4 |
| Characteristic branch | 1,052 |
| Information Entity branch | 109 |
| Matter branch | 692 |
| Process branch | 364 |

The five branch counts sum to 2,221. A branch count reports the number of active classes whose unique intrinsic top branch is the named branch; it is not a ranking of scientific importance.

## Supplementary Table S2. H₂KG object properties and declared domains and ranges

| Property | Label | Domain | Range |
| --- | --- | --- | --- |
| h2kg:atCurrentDensity | atCurrentDensity | h2kg:DataPoint | qudt:QuantityValue |
| h2kg:fromMeasurement | fromMeasurement | h2kg:DataPoint | h2kg:Measurement |
| h2kg:hasInputData | hasInputData | h2kg:Process | h2kg:Data |
| h2kg:hasInputMaterial | hasInputMaterial | h2kg:Process | h2kg:Matter |
| h2kg:hasMeasurementSubject | has measurement subject | h2kg:Measurement | h2kg:Matter |
| h2kg:hasMetadata | hasMetadata |  | h2kg:Metadata |
| h2kg:hasOutputData | hasOutputData | h2kg:Process | h2kg:Data |
| h2kg:hasOutputMaterial | hasOutputMaterial | h2kg:Process | h2kg:Matter |
| h2kg:hasParameter | hasParameter | h2kg:Process | h2kg:Parameter |
| h2kg:hasPart | hasPart |  |  |
| h2kg:hasProperty | hasProperty | h2kg:Measurement | h2kg:Property |
| h2kg:hasQuantityValue | hasQuantityValue | h2kg:Property | qudt:QuantityValue |
| h2kg:hasReferenceScale | has reference scale | h2kg:InformationEntity | h2kg:ReferenceScale |
| h2kg:hasSubProcess | hasSubProcess |  |  |
| h2kg:isPartOf | isPartOf |  |  |
| h2kg:isSubProcessOf | isSubProcessOf |  |  |
| h2kg:measures | measures | h2kg:Measurement | h2kg:Property |
| h2kg:normalizedTo | normalizedTo |  | h2kg:NormalizationBasis |
| h2kg:ofProperty | ofProperty | h2kg:InformationEntity | h2kg:Property |
| h2kg:referenceElectrode | referenceElectrode |  |  |
| h2kg:usesInstrument | usesInstrument | h2kg:Process | h2kg:Instrument |
| h2kg:usesReferenceElectrode | uses reference electrode | h2kg:Measurement | h2kg:ReferenceElectrode |
| h2kg:usesSoftware | uses software | h2kg:Process | h2kg:SoftwareArtifact |

Blank domains or ranges indicate intentionally generic relations. Domain and range declarations summarize the canonical H₂KG 2.2 taxonomy. Profile-specific endpoint constraints are expressed separately with SHACL.

## Supplementary Table S3. Version 2.2 correction and role-migration summary

| Correction or migration measure | Result |
| --- | ---: |
| Parent decisions represented | 156 |
| Definition decisions represented | 470 |
| Unique classes covered by correction decisions | 544 |
| Decisions applied | 455 |
| Decisions retained | 6 |
| Replacements | 7 |
| Splits | 1 |
| Source-dependent deprecations | 157 |
| Legacy workflow assertions classified | 4,418 |
| Legacy workflow assertions migrated or explicitly documented | 4,418 (100%) |
| Migrated profile relations | 4,416 |
| Unsupported documented legacy relations | 2 |
| Legacy `hasParameter` assertions classified | 1,163 |
| Parameter-record/property paths | 1,143 |
| Active characteristic classes typed as `Parameter` | 0 |
| Canonical class-to-class workflow assertions | 0 |

The difference between the 1,163 legacy `hasParameter` assertions and 1,143 parameter-record/property paths consists of targets whose intrinsic identities required other treatments, including material input, subprocess, reference-scale, normalization, or explicitly documented unsupported outcomes.

## Supplementary Table S4. Executable competency questions

| ID | Question/check | Expected behavior | Result | Evidence |
| --- | --- | --- | --- | --- |
| CQ1 | Electron microscopy method retrieval | Representative TEM, SEM, and IC-SEM methods are retrievable below ElectronMicroscopyMeasurement. | Pass | ICSEMImagingMeasurement; SEMImagingMeasurement; ScanningElectronMicroscopyImaging; TransmissionElectronMicroscopyImaging |
| CQ2 | Tomography method retrieval | FIB-SEM, neutron, and X-ray tomography methods are retrievable below TomographyMeasurement. | Pass | FIBSEMTomographyMeasurement; NeutronTomographyMeasurement; XRayComputedTomographyMeasurement |
| CQ3 | Characterization dataset retrieval | Representative microscopy, diffraction, and tomography datasets resolve through their dataset branches. | Pass | SEMImageDataset -> ElectronMicroscopyImageDataset; TomographicReconstructionDataset -> TomographyDataset; XRDPatternDataset -> DiffractionDataset |
| CQ4 | Canonical characteristic identity | Quantities used as parameters or results have one canonical identity below Characteristic. | Pass | CatalystLayerThickness; CurrentDensity; GasDiffusionLayerPorosity; IonomerToCarbonRatio |
| CQ5 | Tem workflow compatibility | The preserved TEM vocabulary view retains instrument, parameter, and output-data anchors; sample context is expressed on occurrences through hasMeasurementSubject. | Pass | hasOutputData=1; hasParameter=6; usesInstrument=1 |
| CQ6 | Itc profile retrieval | The grouped ITC profile exposes its 16 parameters, input dataset, scalar-result dataset, and three distribution datasets. | Pass | input_datasets=1; output_datasets=4; parameters=16 |
| CQ7 | Mea measurement subject retrieval | Measurements using an MEA input are retrievable through the corrected measurement-subject projection. | Pass | AcceleratedStressTestVoltageCycling; AtomicForceMicroscopyMeasurement; CurrentInterruptHFRMeasurement; CyclicVoltammetry; ElectrochemicalImpedanceSpectroscopyGalvanostatic; FuelCellPolarizationMeasurement; ICSEMImagingMeasurement; LimitingCurrentMeasurement; NeutronTomographyMeasurement; O2N2SwitchingMeasurement; OxygenGainLossMeasurement |
| CQ8 | Software use projection | Fiji/ImageJ is represented below SoftwareArtifact and the dedicated usesSoftware relation is available to profiles and occurrences. | Pass | FijiImageJSoftware -> SoftwareArtifact; usesSoftware -> owl:ObjectProperty |
| CQ9 | Technology module retrieval | Core, PEMFC, and PEMWE placements are all represented without duplicating shared concepts. | Pass | core=2191; electrochemistry-extension=9; pemfc=19; pemwe=2 |

All nine checks passed in the H₂KG 2.2.0 build cited by the article. A passing check confirms the named retrieval or structural expectation; it does not validate experimental results.

## Supplementary Table S5. Automated TIB matching rules

| Outcome | Deterministic release rule | Public bridge treatment |
| --- | --- | --- |
| `exact_iri_reuse` | H₂KG and external concept use the same stable IRI | Reuse the external IRI; no duplicate mapping triple |
| `machine_exact_equivalent` | Active native external class; compatible role, definition, hierarchy, scientific scope, material state, and entity/value granularity; unique canonical target | `skos:exactMatch` only after the stricter assertion gate |
| `h2kg_narrower` | H₂KG definition adds defensible scientific restrictions to the external concept | `skos:broadMatch` only at high confidence |
| `h2kg_broader` | External definition adds defensible restrictions to the H₂KG concept | `skos:narrowMatch` only at high confidence |
| `related_non_equivalent` | Candidate is scientifically related but equivalence or hierarchy direction is unsupported, tied, or role-incompatible | Benchmark evidence only; no assertion |
| `ambiguous_abstained` | Reserved transparency category | Required to be zero in a publishable complete build |
| `unmatched` | Complete native-term search produced no candidate | Benchmark evidence only |

Candidate generation used preferred labels, alternate labels, normalized lexical forms, definitions, original ontology identifiers, obsolete/replacement state, direct parents, ancestor paths, and coarse semantic roles. Exact labels alone did not establish equivalence. Retrieval failures blocked publication and were not converted into unmatched outcomes. Percentages use all 2,221 active H₂KG classes as denominator.

## Supplementary Table S6. Ontology-level benchmark for all collection memberships

The frozen TIB snapshot contains 165 collection memberships representing 143 unique ontologies. Ontologies occurring in multiple collections appear once in each applicable collection block. Every outcome cell reports `count (percentage of 2,221 active H₂KG classes)`.

| Collection | Ontology ID | Ontology title | Version | TIB link | TIB-reported terms | H2KG classes assessed | Exact IRI reuse | Machine exact equivalent | H2KG narrower | H2KG broader | Related non-equivalent | Ambiguous abstained | Unmatched |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NFDI4Cat | afo | Allotrope Foundation Ontology Merged Without QUDT And Inferred (REC/2025/03) | REC/2026/03 | https://terminology.tib.eu/ts/ontologies/afo | 3516 | 2221 | 0 (0.00%) | 18 (0.81%) | 18 (0.81%) | 26 (1.17%) | 189 (8.51%) | 0 (0.00%) | 1970 (88.70%) |
| NFDI4Cat | bfo | Basic Formal Ontology |  | https://terminology.tib.eu/ts/ontologies/bfo | 35 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 8 (0.36%) | 0 (0.00%) | 2213 (99.64%) |
| NFDI4Cat | bao | BioAssay Ontology | 2.1 | https://terminology.tib.eu/ts/ontologies/bao | 7921 | 2221 | 0 (0.00%) | 5 (0.23%) | 19 (0.86%) | 10 (0.45%) | 196 (8.82%) | 0 (0.00%) | 1991 (89.64%) |
| NFDI4Cat | cao | Chemical Analysis Metadata Platform (ChAMP) Ontology version 0.2 | 0.2 | https://terminology.tib.eu/ts/ontologies/cao | 445 | 2221 | 0 (0.00%) | 3 (0.14%) | 4 (0.18%) | 3 (0.13%) | 54 (2.43%) | 0 (0.00%) | 2157 (97.12%) |
| NFDI4Cat | chebi | Chemical Entities of Biological Interest | 255 | https://terminology.tib.eu/ts/ontologies/chebi | 237960 | 2221 | 0 (0.00%) | 25 (1.13%) | 7 (0.31%) | 27 (1.22%) | 198 (8.91%) | 0 (0.00%) | 1964 (88.43%) |
| NFDI4Cat | cheminf | chemical information ontology (cheminf) - information entities about chemical entities | 2.1.0 | https://terminology.tib.eu/ts/ontologies/cheminf | 859 | 2221 | 0 (0.00%) | 1 (0.05%) | 0 (0.00%) | 1 (0.04%) | 16 (0.72%) | 0 (0.00%) | 2203 (99.19%) |
| NFDI4Cat | chmo | Chemical Methods Ontology | 2026-05-28 | https://terminology.tib.eu/ts/ontologies/chmo | 3263 | 2221 | 0 (0.00%) | 30 (1.35%) | 17 (0.77%) | 30 (1.35%) | 255 (11.48%) | 0 (0.00%) | 1889 (85.05%) |
| NFDI4Cat | ontocompchem | Computational Chemistry Ontology | 1 | https://terminology.tib.eu/ts/ontologies/ontocompchem | 77 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Cat | cif | Crystallography domain ontology |  | https://terminology.tib.eu/ts/ontologies/cif | 1804 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 1 (0.05%) | 0 (0.00%) | 2220 (99.95%) |
| NFDI4Cat | edam | EDAM - The ontology of data analysis and management | 1.25-20260626T1230Z | https://terminology.tib.eu/ts/ontologies/edam | 3539 | 2221 | 0 (0.00%) | 0 (0.00%) | 8 (0.36%) | 7 (0.31%) | 95 (4.28%) | 0 (0.00%) | 2111 (95.05%) |
| NFDI4Cat | ms | Mass Spectrometry |  | https://terminology.tib.eu/ts/ontologies/ms | 6084 | 2221 | 0 (0.00%) | 1 (0.04%) | 9 (0.41%) | 11 (0.50%) | 189 (8.51%) | 0 (0.00%) | 2011 (90.54%) |
| NFDI4Cat | m4i | Metadata4Ing: An ontology for describing the generation of research data within a scientific activity | v1.4.0 | https://terminology.tib.eu/ts/ontologies/m4i | 52 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 3 (0.14%) | 0 (0.00%) | 2218 (99.86%) |
| NFDI4Cat | mop | MOP |  | https://terminology.tib.eu/ts/ontologies/mop | 3686 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 1 (0.04%) | 47 (2.12%) | 0 (0.00%) | 2173 (97.84%) |
| NFDI4Cat | obi | Ontology for Biomedical Investigations | 2026-07-27 | https://terminology.tib.eu/ts/ontologies/obi | 5240 | 2221 | 0 (0.00%) | 6 (0.27%) | 8 (0.36%) | 19 (0.86%) | 183 (8.24%) | 0 (0.00%) | 2005 (90.27%) |
| NFDI4Cat | ontokin | Ontology for Chemical Kinetic Reaction Mechanisms | 1 | https://terminology.tib.eu/ts/ontologies/ontokin | 58 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 1 (0.05%) | 0 (0.00%) | 2220 (99.95%) |
| NFDI4Cat | osmo | Ontology for simulation, modelling, and optimization | 1.8 | https://terminology.tib.eu/ts/ontologies/osmo | 148 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 3 (0.14%) | 0 (0.00%) | 2218 (99.86%) |
| NFDI4Cat | om | Ontology of units of Measure (OM) | 2.0.59 | https://terminology.tib.eu/ts/ontologies/om | 813 | 2221 | 0 (0.00%) | 4 (0.18%) | 12 (0.54%) | 4 (0.18%) | 93 (4.19%) | 0 (0.00%) | 2108 (94.91%) |
| NFDI4Cat | rex | Physico-chemical process |  | https://terminology.tib.eu/ts/ontologies/rex | 552 | 2221 | 0 (0.00%) | 0 (0.00%) | 4 (0.18%) | 1 (0.04%) | 49 (2.21%) | 0 (0.00%) | 2167 (97.57%) |
| NFDI4Cat | rxno | RXNO |  | https://terminology.tib.eu/ts/ontologies/rxno | 1019 | 2221 | 0 (0.00%) | 1 (0.05%) | 0 (0.00%) | 0 (0.00%) | 22 (0.99%) | 0 (0.00%) | 2198 (98.96%) |
| NFDI4Cat | sbo | Systems Biology Ontology | 28:08:2021 03:13 | https://terminology.tib.eu/ts/ontologies/sbo | 695 | 2221 | 0 (0.00%) | 2 (0.09%) | 2 (0.09%) | 0 (0.00%) | 6 (0.27%) | 0 (0.00%) | 2211 (99.55%) |
| NFDI4Cat | envo | The Environment Ontology | 2026-06-26 | https://terminology.tib.eu/ts/ontologies/envo | 6936 | 2221 | 0 (0.00%) | 2 (0.09%) | 16 (0.72%) | 13 (0.58%) | 117 (5.27%) | 0 (0.00%) | 2073 (93.34%) |
| NFDI4Cat | envo2023 | The Environment Ontology | 2023-02-13 | https://terminology.tib.eu/ts/ontologies/envo2023 | 6996 | 2221 | 0 (0.00%) | 2 (0.09%) | 6 (0.27%) | 6 (0.27%) | 61 (2.75%) | 0 (0.00%) | 2146 (96.62%) |
| NFDI4Cat | emmo | The European Materials Modelling Ontology | 1.0.0-beta4 | https://terminology.tib.eu/ts/ontologies/emmo | 1191 | 2221 | 0 (0.00%) | 3 (0.14%) | 18 (0.81%) | 0 (0.00%) | 72 (3.24%) | 0 (0.00%) | 2128 (95.81%) |
| NFDI4Cat | voc4cat | Voc4Cat - A SKOS vocabulary for Catalysis |  | https://terminology.tib.eu/ts/ontologies/voc4cat | 560 | 2221 | 0 (0.00%) | 17 (0.77%) | 26 (1.17%) | 20 (0.90%) | 178 (8.01%) | 0 (0.00%) | 1980 (89.15%) |
| NFDI4Energy | brick | Brick Ontology | 1.3.0 | https://terminology.tib.eu/ts/ontologies/brick | 1438 | 2221 | 0 (0.00%) | 0 (0.00%) | 2 (0.09%) | 0 (0.00%) | 63 (2.84%) | 0 (0.00%) | 2156 (97.07%) |
| NFDI4Energy | cepo | Climate and Energy Policy Ontology |  | https://terminology.tib.eu/ts/ontologies/cepo | 431 | 2221 | 0 (0.00%) | 0 (0.00%) | 2 (0.09%) | 2 (0.09%) | 10 (0.45%) | 0 (0.00%) | 2207 (99.37%) |
| NFDI4Energy | dices | Digital Construction Energy (dices) |  | https://terminology.tib.eu/ts/ontologies/dices | 322 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2 (0.09%) | 0 (0.00%) | 2219 (99.91%) |
| NFDI4Energy | docbias | Doc-Bias Ontology | 0.3 | https://terminology.tib.eu/ts/ontologies/docbias | 388 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2 (0.09%) | 0 (0.00%) | 2219 (99.91%) |
| NFDI4Energy | dogont | DogOnt Ontology Modeling for Intelligent Domotic Environments | 4.0.2 | https://terminology.tib.eu/ts/ontologies/dogont | 1065 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 3 (0.14%) | 0 (0.00%) | 2218 (99.86%) |
| NFDI4Energy | energymarketroles | Energy Market Roles ontology | 2.0 | https://terminology.tib.eu/ts/ontologies/energymarketroles | 5 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Energy | fmi | FMI-Ontology | 0.1.0-beta.1 | https://terminology.tib.eu/ts/ontologies/fmi | 7 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Energy | openadr | OpenADR ontology | 0.2.2 | https://terminology.tib.eu/ts/ontologies/openadr | 77 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 3 (0.14%) | 0 (0.00%) | 2218 (99.86%) |
| NFDI4Energy | quantitykind | QUDT Quantity Kind Vocabulary Version 3.2.1 |  | https://terminology.tib.eu/ts/ontologies/quantitykind | 75 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Energy | qudtdatatypeschema | QUDT SCHEMA - Datatypes |  | https://terminology.tib.eu/ts/ontologies/qudtdatatypeschema | 241 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 8 (0.36%) | 0 (0.00%) | 2213 (99.64%) |
| NFDI4Energy | qudt | QUDT Schema - Version 3.2.1 |  | https://terminology.tib.eu/ts/ontologies/qudt | 288 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 15 (0.68%) | 0 (0.00%) | 2206 (99.32%) |
| NFDI4Energy | prefix | QUDT VOCAB Decimal Prefixes Release 3.2.1 | Created with TopBraid Composer | https://terminology.tib.eu/ts/ontologies/prefix | 75 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Energy | qkdv | QUDT VOCAB Dimension Vectors Release 3.2.1 |  | https://terminology.tib.eu/ts/ontologies/qkdv | 76 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Energy | constant | QUDT VOCAB Physical Constants Release 3.2.1 |  | https://terminology.tib.eu/ts/ontologies/constant | 75 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Energy | soqk | QUDT VOCAB Systems of Quantity Kinds Release 3.2.1 | Created with TopBraid Composer | https://terminology.tib.eu/ts/ontologies/soqk | 75 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Energy | sou | QUDT VOCAB Systems of Units Release 3.2.1 | Created with TopBraid Composer | https://terminology.tib.eu/ts/ontologies/sou | 75 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Energy | unit | QUDT Vocab Units of Measure Release 3.2.1 |  | https://terminology.tib.eu/ts/ontologies/unit | 75 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Energy | datatype | QUDT Vocabulary of Datatypes v3.2.1 |  | https://terminology.tib.eu/ts/ontologies/datatype | 247 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 1 (0.05%) | 0 (0.00%) | 2220 (99.95%) |
| NFDI4Energy | oeo | Repository for the Open Energy Ontology (OEO) | 2.13.0 | https://terminology.tib.eu/ts/ontologies/oeo | 1611 | 2221 | 0 (0.00%) | 5 (0.22%) | 15 (0.68%) | 10 (0.45%) | 102 (4.59%) | 0 (0.00%) | 2089 (94.06%) |
| NFDI4Energy | re | Retail Energy Market of Great Britain |  | https://terminology.tib.eu/ts/ontologies/re | 211 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Energy | s4ener | SAREF for Energy Flexibility | v2.1.1 | https://terminology.tib.eu/ts/ontologies/s4ener | 112 | 2221 | 0 (0.00%) | 1 (0.05%) | 0 (0.00%) | 0 (0.00%) | 4 (0.18%) | 0 (0.00%) | 2216 (99.77%) |
| NFDI4Energy | s4grid | SAREF4GRID: an extension of SAREF for the Smart Grid domain | v2.1.1 | https://terminology.tib.eu/ts/ontologies/s4grid | 78 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 1 (0.05%) | 0 (0.00%) | 2220 (99.95%) |
| NFDI4Energy | sargon | SARGON (SmArt eneRGy dOmain oNtology) | 2.1.2 | https://terminology.tib.eu/ts/ontologies/sargon | 170 | 2221 | 0 (0.00%) | 0 (0.00%) | 3 (0.13%) | 0 (0.00%) | 13 (0.59%) | 0 (0.00%) | 2205 (99.28%) |
| NFDI4Energy | sargon2 | SARGON2 Ontology |  | https://terminology.tib.eu/ts/ontologies/sargon2 | 2079 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 1 (0.05%) | 14 (0.63%) | 0 (0.00%) | 2206 (99.32%) |
| NFDI4Energy | sms | SMS-Ontology | 0.2.0-beta.1 | https://terminology.tib.eu/ts/ontologies/sms | 38 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Energy | stw | STW Thesaurus for Economics |  | https://terminology.tib.eu/ts/ontologies/stw | 7645 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 113 (5.09%) | 0 (0.00%) | 2108 (94.91%) |
| NFDI4Energy | bont | The BONSAI ontology | Version 0.2 - 2022-03-15 | https://terminology.tib.eu/ts/ontologies/bont | 8 | 2221 | 0 (0.00%) | 0 (0.00%) | 1 (0.05%) | 0 (0.00%) | 4 (0.18%) | 0 (0.00%) | 2216 (99.77%) |
| NFDI4Ing | s4bldg |  SAREF4BLDG: an extension of SAREF for the building domain | v2.1.1 | https://terminology.tib.eu/ts/ontologies/s4bldg | 98 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 1 (0.04%) | 13 (0.59%) | 0 (0.00%) | 2207 (99.37%) |
| NFDI4Ing | cco | All Core Ontology | Version 2.2 | https://terminology.tib.eu/ts/ontologies/cco | 1437 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Ing | afo | Allotrope Foundation Ontology Merged Without QUDT And Inferred (REC/2025/03) | REC/2026/03 | https://terminology.tib.eu/ts/ontologies/afo | 3516 | 2221 | 0 (0.00%) | 18 (0.81%) | 18 (0.81%) | 26 (1.17%) | 189 (8.51%) | 0 (0.00%) | 1970 (88.70%) |
| NFDI4Ing | atomistic | Atomistic | 0.0.1 | https://terminology.tib.eu/ts/ontologies/atomistic | 1789 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 3 (0.14%) | 0 (0.00%) | 2218 (99.86%) |
| NFDI4Ing | bo | Base Ontology |  | https://terminology.tib.eu/ts/ontologies/bo | 23 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 1 (0.05%) | 0 (0.00%) | 2220 (99.95%) |
| NFDI4Ing | bfo | Basic Formal Ontology |  | https://terminology.tib.eu/ts/ontologies/bfo | 35 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 8 (0.36%) | 0 (0.00%) | 2213 (99.64%) |
| NFDI4Ing | bk | Basisklassifikation |  | https://terminology.tib.eu/ts/ontologies/bk | 2141 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 26 (1.17%) | 0 (0.00%) | 2195 (98.83%) |
| NFDI4Ing | battinfo | Battery Interface Ontology (BattINFO) | 0.8.0 | https://terminology.tib.eu/ts/ontologies/battinfo | 4220 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2 (0.09%) | 0 (0.00%) | 2219 (99.91%) |
| NFDI4Ing | brick | Brick Ontology | 1.3.0 | https://terminology.tib.eu/ts/ontologies/brick | 1438 | 2221 | 0 (0.00%) | 0 (0.00%) | 2 (0.09%) | 0 (0.00%) | 63 (2.84%) | 0 (0.00%) | 2156 (97.07%) |
| NFDI4Ing | building | Building Ontology | 0.1.5 | https://terminology.tib.eu/ts/ontologies/building | 45 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 10 (0.45%) | 0 (0.00%) | 2211 (99.55%) |
| NFDI4Ing | bot | Building Topology Ontology | 0.3.2 | https://terminology.tib.eu/ts/ontologies/bot | 8 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Ing | chameo | CHAracterisation MEthodology Ontology | 1.0.0 | https://terminology.tib.eu/ts/ontologies/chameo | 1604 | 2221 | 0 (0.00%) | 7 (0.32%) | 4 (0.18%) | 7 (0.31%) | 55 (2.48%) | 0 (0.00%) | 2148 (96.71%) |
| NFDI4Ing | co | CodeOntology |  | https://terminology.tib.eu/ts/ontologies/co | 65 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 5 (0.23%) | 0 (0.00%) | 2216 (99.77%) |
| NFDI4Ing | credit | Contributor Roles Taxonomy | 2022 | https://terminology.tib.eu/ts/ontologies/credit | 16 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 1 (0.05%) | 2 (0.09%) | 0 (0.00%) | 2218 (99.86%) |
| NFDI4Ing | dot | Damage Topology Ontology | 0.8 | https://terminology.tib.eu/ts/ontologies/dot | 14 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Ing | dpv | Data Privacy Vocabulary (DPV) | 2.3 | https://terminology.tib.eu/ts/ontologies/dpv | 973 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2 (0.09%) | 39 (1.76%) | 0 (0.00%) | 2180 (98.15%) |
| NFDI4Ing | dcterms | DCMI Metadata Terms |  | https://terminology.tib.eu/ts/ontologies/dcterms | 22 | 2221 | 0 (0.00%) | 0 (0.00%) | 1 (0.05%) | 0 (0.00%) | 4 (0.18%) | 0 (0.00%) | 2216 (99.77%) |
| NFDI4Ing | ccrel | Describing Copyright in RDF - Creative Commons Rights Expression Language |  | https://terminology.tib.eu/ts/ontologies/ccrel | 19 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Ing | dfgfo | DFG Classification of Subject Areas Ontology - 2020-2024 | 2020-2024 | https://terminology.tib.eu/ts/ontologies/dfgfo | 556 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 7 (0.32%) | 0 (0.00%) | 2214 (99.68%) |
| NFDI4Ing | dfgfo2024 | DFG Classification of Subject Areas Ontology - 2024-2028 | 2024-2028 | https://terminology.tib.eu/ts/ontologies/dfgfo2024 | 281 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 7 (0.32%) | 0 (0.00%) | 2214 (99.68%) |
| NFDI4Ing | dices | Digital Construction Energy (dices) |  | https://terminology.tib.eu/ts/ontologies/dices | 322 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2 (0.09%) | 0 (0.00%) | 2219 (99.91%) |
| NFDI4Ing | dicl | Digital Construction Lifecycle (dicl) | 0.5 | https://terminology.tib.eu/ts/ontologies/dicl | 165 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Ing | dicob | Digital Construction Occupancy |  | https://terminology.tib.eu/ts/ontologies/dicob | 300 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2 (0.09%) | 0 (0.00%) | 2219 (99.91%) |
| NFDI4Ing | dr | Digital Reference | 1.2.12 | https://terminology.tib.eu/ts/ontologies/dr | 1238 | 2221 | 0 (0.00%) | 1 (0.04%) | 1 (0.04%) | 3 (0.14%) | 73 (3.29%) | 0 (0.00%) | 2143 (96.49%) |
| NFDI4Ing | dogont | DogOnt Ontology Modeling for Intelligent Domotic Environments | 4.0.2 | https://terminology.tib.eu/ts/ontologies/dogont | 1065 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 3 (0.14%) | 0 (0.00%) | 2218 (99.86%) |
| NFDI4Ing | edam | EDAM - The ontology of data analysis and management | 1.25-20260626T1230Z | https://terminology.tib.eu/ts/ontologies/edam | 3539 | 2221 | 0 (0.00%) | 0 (0.00%) | 8 (0.36%) | 7 (0.31%) | 95 (4.28%) | 0 (0.00%) | 2111 (95.05%) |
| NFDI4Ing | fair | FAIR Vocabulary |  | https://terminology.tib.eu/ts/ontologies/fair | 5 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Ing | bdsubj | FID BAUdigital Subject Headings |  | https://terminology.tib.eu/ts/ontologies/bdsubj | 5 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Ing | fiestaiot | FIESTA-IoT Ontology | 3.1 | https://terminology.tib.eu/ts/ontologies/fiestaiot | 483 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 3 (0.13%) | 29 (1.31%) | 0 (0.00%) | 2189 (98.56%) |
| NFDI4Ing | bau | FINDEX Bau as a SKOS Thesaurus - Facetted Indexing System for Civil Engineering |  | https://terminology.tib.eu/ts/ontologies/bau | 49 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 225 (10.13%) | 0 (0.00%) | 1996 (89.87%) |
| NFDI4Ing | raum | FINDEX Raum |  | https://terminology.tib.eu/ts/ontologies/raum | 1 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 40 (1.80%) | 0 (0.00%) | 2181 (98.20%) |
| NFDI4Ing | foaf | Friend of a Friend (FOAF) vocabulary |  | https://terminology.tib.eu/ts/ontologies/foaf | 13 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 8 (0.36%) | 0 (0.00%) | 2213 (99.64%) |
| NFDI4Ing | ftonto | FTOnto |  | https://terminology.tib.eu/ts/ontologies/ftonto | 219 | 2221 | 0 (0.00%) | 0 (0.00%) | 1 (0.05%) | 0 (0.00%) | 18 (0.81%) | 0 (0.00%) | 2202 (99.14%) |
| NFDI4Ing | gpo | General Process Ontology (GPO) |  | https://terminology.tib.eu/ts/ontologies/gpo | 2383 | 2221 | 0 (0.00%) | 0 (0.00%) | 1 (0.05%) | 0 (0.00%) | 10 (0.45%) | 0 (0.00%) | 2210 (99.50%) |
| NFDI4Ing | geo | GeoSPARQL Ontology | 1.1.1 - 2026-02 - minor metadata changes to ensure Rainbow display  1.1 - version as originally published with GeoSPARQL 1.1  | https://terminology.tib.eu/ts/ontologies/geo | 6 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Ing | gist | gist |  | https://terminology.tib.eu/ts/ontologies/gist | 96 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 15 (0.68%) | 0 (0.00%) | 2206 (99.32%) |
| NFDI4Ing | ifc | IFC4_ADD2_TC1 |  | https://terminology.tib.eu/ts/ontologies/ifc | 1325 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Ing | iirds | IIRDS CORE Ontology |  | https://terminology.tib.eu/ts/ontologies/iirds | 67 | 2221 | 0 (0.00%) | 0 (0.00%) | 3 (0.14%) | 0 (0.00%) | 8 (0.36%) | 0 (0.00%) | 2210 (99.50%) |
| NFDI4Ing | iirdsmch | IIRDS Machinery Ontology |  | https://terminology.tib.eu/ts/ontologies/iirdsmch | 8 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Ing | iirdssft | IIRDS Software Ontology |  | https://terminology.tib.eu/ts/ontologies/iirdssft | 1 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Ing | lis | Industrial Data Ontology | 4.0 Proposed DIS November 2024 | https://terminology.tib.eu/ts/ontologies/lis | 49 | 2221 | 0 (0.00%) | 0 (0.00%) | 1 (0.04%) | 0 (0.00%) | 5 (0.23%) | 0 (0.00%) | 2215 (99.73%) |
| NFDI4Ing | iofcore | Industrial Ontology Foundry (IOF) Core Ontology |  | https://terminology.tib.eu/ts/ontologies/iofcore | 122 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 16 (0.72%) | 0 (0.00%) | 2205 (99.28%) |
| NFDI4Ing | iao | Information Artifact Ontology (IAO) | 2026-03-30 | https://terminology.tib.eu/ts/ontologies/iao | 266 | 2221 | 0 (0.00%) | 1 (0.04%) | 0 (0.00%) | 2 (0.09%) | 15 (0.68%) | 0 (0.00%) | 2203 (99.19%) |
| NFDI4Ing | io | Information Objects Ontology | 0.0.3 | https://terminology.tib.eu/ts/ontologies/io | 1 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Ing | infosecsos | InfoSecSoS Ontology |  | https://terminology.tib.eu/ts/ontologies/infosecsos | 133 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Ing | kdsfffk | Interdisziplinäre Forschungsfeldklassifikation |  | https://terminology.tib.eu/ts/ontologies/kdsfffk | 88 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2 (0.09%) | 0 (0.00%) | 2219 (99.91%) |
| NFDI4Ing | idsa | International Data Spaces Information Model | 4.2.0 | https://terminology.tib.eu/ts/ontologies/idsa | 249 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 11 (0.50%) | 0 (0.00%) | 2210 (99.50%) |
| NFDI4Ing | ioc | IOC: Internet of Construction Ontology | 0.5.1 | https://terminology.tib.eu/ts/ontologies/ioc | 23 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 3 (0.14%) | 0 (0.00%) | 2218 (99.86%) |
| NFDI4Ing | kpi | Key Performance Indicator ontology | 0.1.6 | https://terminology.tib.eu/ts/ontologies/kpi | 17 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 5 (0.23%) | 0 (0.00%) | 2216 (99.77%) |
| NFDI4Ing | listdb | ListDB Ontology 0.0.1 (Draft) |  | https://terminology.tib.eu/ts/ontologies/listdb | 87 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 1 (0.05%) | 14 (0.63%) | 0 (0.00%) | 2206 (99.32%) |
| NFDI4Ing | mat | Material properties ontology | 0.0.8 | https://terminology.tib.eu/ts/ontologies/mat | 140 | 2221 | 0 (0.00%) | 0 (0.00%) | 2 (0.09%) | 0 (0.00%) | 28 (1.26%) | 0 (0.00%) | 2191 (98.65%) |
| NFDI4Ing | mdo | Materials Design Ontology - Full | 1.0 | https://terminology.tib.eu/ts/ontologies/mdo | 37 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Ing | mathmoddb | MathModDB Knowledge Graph of Mathematical Models | 2.0.0 | https://terminology.tib.eu/ts/ontologies/mathmoddb | 7 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Ing | m4i | Metadata4Ing: An ontology for describing the generation of research data within a scientific activity | v1.4.0 | https://terminology.tib.eu/ts/ontologies/m4i | 52 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 3 (0.14%) | 0 (0.00%) | 2218 (99.86%) |
| NFDI4Ing | mt | Mobility Theme | 1.1.1 | https://terminology.tib.eu/ts/ontologies/mt | 2 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 7 (0.32%) | 0 (0.00%) | 2214 (99.68%) |
| NFDI4Ing | mv | MobiVoc Open Mobility Vocabulary 1.1.4 | v1.1.4 | https://terminology.tib.eu/ts/ontologies/mv | 49 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2 (0.09%) | 0 (0.00%) | 2219 (99.91%) |
| NFDI4Ing | modsci | Modern Science Ontology | 1.1 | https://terminology.tib.eu/ts/ontologies/modsci | 380 | 2221 | 0 (0.00%) | 1 (0.05%) | 2 (0.09%) | 1 (0.04%) | 11 (0.50%) | 0 (0.00%) | 2206 (99.32%) |
| NFDI4Ing | mwo | NFDI Matwerk Ontology | 3.0.2 | https://terminology.tib.eu/ts/ontologies/mwo | 457 | 2221 | 0 (0.00%) | 3 (0.14%) | 2 (0.09%) | 0 (0.00%) | 14 (0.63%) | 0 (0.00%) | 2202 (99.14%) |
| NFDI4Ing | ofm | Ontology for manufacturing and logistics |  | https://terminology.tib.eu/ts/ontologies/ofm | 108 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Ing | sepio | Ontology for Scientific Evidence and Provenance Information | 2023-06-13 | https://terminology.tib.eu/ts/ontologies/sepio | 125 | 2221 | 0 (0.00%) | 1 (0.05%) | 0 (0.00%) | 0 (0.00%) | 6 (0.27%) | 0 (0.00%) | 2214 (99.68%) |
| NFDI4Ing | om | Ontology of units of Measure (OM) | 2.0.59 | https://terminology.tib.eu/ts/ontologies/om | 813 | 2221 | 0 (0.00%) | 4 (0.18%) | 12 (0.54%) | 4 (0.18%) | 93 (4.19%) | 0 (0.00%) | 2108 (94.91%) |
| NFDI4Ing | physh | PhySH - Physics Subject Headings |  | https://terminology.tib.eu/ts/ontologies/physh | 3891 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 219 (9.86%) | 0 (0.00%) | 2002 (90.14%) |
| NFDI4Ing | pmd | PMD Core Ontology | 3.1.1 | https://terminology.tib.eu/ts/ontologies/pmd | 1375 | 2221 | 0 (0.00%) | 7 (0.31%) | 23 (1.04%) | 2 (0.09%) | 210 (9.46%) | 0 (0.00%) | 1979 (89.10%) |
| NFDI4Ing | pror | PRO Research: An ontology for describing RDM-Policies in a structured way | v1.0.0 | https://terminology.tib.eu/ts/ontologies/pror | 195 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 1 (0.05%) | 6 (0.27%) | 0 (0.00%) | 2214 (99.68%) |
| NFDI4Ing | quantitykind | QUDT Quantity Kind Vocabulary Version 3.2.1 |  | https://terminology.tib.eu/ts/ontologies/quantitykind | 75 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Ing | qudtdatatypeschema | QUDT SCHEMA - Datatypes |  | https://terminology.tib.eu/ts/ontologies/qudtdatatypeschema | 241 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 8 (0.36%) | 0 (0.00%) | 2213 (99.64%) |
| NFDI4Ing | qudt | QUDT Schema - Version 3.2.1 |  | https://terminology.tib.eu/ts/ontologies/qudt | 288 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 15 (0.68%) | 0 (0.00%) | 2206 (99.32%) |
| NFDI4Ing | prefix | QUDT VOCAB Decimal Prefixes Release 3.2.1 | Created with TopBraid Composer | https://terminology.tib.eu/ts/ontologies/prefix | 75 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Ing | qkdv | QUDT VOCAB Dimension Vectors Release 3.2.1 |  | https://terminology.tib.eu/ts/ontologies/qkdv | 76 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Ing | constant | QUDT VOCAB Physical Constants Release 3.2.1 |  | https://terminology.tib.eu/ts/ontologies/constant | 75 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Ing | soqk | QUDT VOCAB Systems of Quantity Kinds Release 3.2.1 | Created with TopBraid Composer | https://terminology.tib.eu/ts/ontologies/soqk | 75 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Ing | sou | QUDT VOCAB Systems of Units Release 3.2.1 | Created with TopBraid Composer | https://terminology.tib.eu/ts/ontologies/sou | 75 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Ing | unit | QUDT Vocab Units of Measure Release 3.2.1 |  | https://terminology.tib.eu/ts/ontologies/unit | 75 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Ing | datatype | QUDT Vocabulary of Datatypes v3.2.1 |  | https://terminology.tib.eu/ts/ontologies/datatype | 247 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 1 (0.05%) | 0 (0.00%) | 2220 (99.95%) |
| NFDI4Ing | oeo | Repository for the Open Energy Ontology (OEO) | 2.13.0 | https://terminology.tib.eu/ts/ontologies/oeo | 1611 | 2221 | 0 (0.00%) | 5 (0.22%) | 15 (0.68%) | 10 (0.45%) | 102 (4.59%) | 0 (0.00%) | 2089 (94.06%) |
| NFDI4Ing | s4ener | SAREF for Energy Flexibility | v2.1.1 | https://terminology.tib.eu/ts/ontologies/s4ener | 112 | 2221 | 0 (0.00%) | 1 (0.05%) | 0 (0.00%) | 0 (0.00%) | 4 (0.18%) | 0 (0.00%) | 2216 (99.77%) |
| NFDI4Ing | s4auto | SAREF4AUTO: an extension of SAREF for the automotive domain | v2.1.1 | https://terminology.tib.eu/ts/ontologies/s4auto | 73 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 4 (0.18%) | 0 (0.00%) | 2217 (99.82%) |
| NFDI4Ing | s4ehaw | SAREF4EHAW: an extension of SAREF for eHealth Ageing Well domain | v2.1.1 | https://terminology.tib.eu/ts/ontologies/s4ehaw | 112 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 1 (0.05%) | 0 (0.00%) | 2220 (99.95%) |
| NFDI4Ing | s4envi | SAREF4ENVI: an extension of SAREF for the Environment domain | v2.1.1 | https://terminology.tib.eu/ts/ontologies/s4envi | 107 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 4 (0.18%) | 0 (0.00%) | 2217 (99.82%) |
| NFDI4Ing | s4inma | SAREF4INMA: an extension of SAREF for the industry and manufacturing domain | v2.1.1 | https://terminology.tib.eu/ts/ontologies/s4inma | 122 | 2221 | 0 (0.00%) | 0 (0.00%) | 9 (0.41%) | 0 (0.00%) | 2 (0.09%) | 0 (0.00%) | 2210 (99.50%) |
| NFDI4Ing | s4lift | SAREF4LIFT: an extension of SAREF for the Smart Lifts domain | v2.1.1 | https://terminology.tib.eu/ts/ontologies/s4lift | 128 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 1 (0.05%) | 0 (0.00%) | 2220 (99.95%) |
| NFDI4Ing | s4syst | SAREF4SYST: an extension of SAREF for typology of systems and their inter-connections | v1.1.2 | https://terminology.tib.eu/ts/ontologies/s4syst | 3 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Ing | s4watr | SAREF4WATR: an extension of SAREF for the water domain | v2.1.1 | https://terminology.tib.eu/ts/ontologies/s4watr | 114 | 2221 | 0 (0.00%) | 0 (0.00%) | 2 (0.09%) | 0 (0.00%) | 6 (0.27%) | 0 (0.00%) | 2213 (99.64%) |
| NFDI4Ing | s4wear | SAREF4WEAR: an extension of SAREF for the Wearables domain | v2.1.1 | https://terminology.tib.eu/ts/ontologies/s4wear | 91 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2 (0.09%) | 0 (0.00%) | 2219 (99.91%) |
| NFDI4Ing | saref | SAREF: the Smart Applications REFerence ontology | v4.1.1 | https://terminology.tib.eu/ts/ontologies/saref | 32 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 5 (0.23%) | 0 (0.00%) | 2216 (99.77%) |
| NFDI4Ing | ssn | Semantic Sensor Network Ontology | New modular version of the SSN ontology.  This ontology was originally developed in 2009-2011 by the W3C Semantic Sensor Networks Incubator Group (SSN-XG). For more information on the group's activities see: http://www.w3.org/2005/Incubator/ssn/. The ontology was revised and modularized in 2015-2017 by the W3C/OGC Spatial Data on the Web Working Group, see: https://www.w3.org/2015/spatial/wiki/Semantic_Sensor_Network_Ontology.  In particular, (a) the scope is extended to include actuation and sampling; (b) the core concepts and properties are factored out into the SOSA ontology. The SSN ontology imports SOSA and adds formal axiomatization consistent with the text definitions in SOSA, and adds classes and properties to accommodate the scope of the original SSN ontology. | https://terminology.tib.eu/ts/ontologies/ssn | 22 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2 (0.09%) | 0 (0.00%) | 2219 (99.91%) |
| NFDI4Ing | sweet | Semantic Web for Earth and Environmental Terminology (SWEET) Ontologies. | 3.6.0 | https://terminology.tib.eu/ts/ontologies/sweet | 10236 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 3 (0.14%) | 0 (0.00%) | 2218 (99.86%) |
| NFDI4Ing | sio | Semanticscience Integrated Ontology (SIO) | 1.61 | https://terminology.tib.eu/ts/ontologies/sio | 1585 | 2221 | 0 (0.00%) | 2 (0.09%) | 29 (1.31%) | 2 (0.09%) | 94 (4.23%) | 0 (0.00%) | 2094 (94.28%) |
| NFDI4Ing | sosa | Sensor, Observation, Sample, and Actuator (SOSA) Ontology |  | https://terminology.tib.eu/ts/ontologies/sosa | 16 | 2221 | 0 (0.00%) | 0 (0.00%) | 1 (0.05%) | 0 (0.00%) | 1 (0.04%) | 0 (0.00%) | 2219 (99.91%) |
| NFDI4Ing | mdv | Simple Knowledge Organization System (SKOS) version of Materials Data Vocabulary |  | https://terminology.tib.eu/ts/ontologies/mdv | 2 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 144 (6.48%) | 0 (0.00%) | 2077 (93.52%) |
| NFDI4Ing | sto | Standards Ontology | 0.2 | https://terminology.tib.eu/ts/ontologies/sto | 80 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 10 (0.45%) | 0 (0.00%) | 2211 (99.55%) |
| NFDI4Ing | ssnsystem | System capabilities, operating ranges, and survival ranges ontology |  | https://terminology.tib.eu/ts/ontologies/ssnsystem | 45 | 2221 | 0 (0.00%) | 0 (0.00%) | 1 (0.04%) | 0 (0.00%) | 11 (0.50%) | 0 (0.00%) | 2209 (99.46%) |
| NFDI4Ing | t4fs | terms4FAIRskills (T4FS) | 2025-02-09 | https://terminology.tib.eu/ts/ontologies/t4fs | 563 | 2221 | 0 (0.00%) | 1 (0.05%) | 4 (0.18%) | 2 (0.09%) | 14 (0.63%) | 0 (0.00%) | 2200 (99.05%) |
| NFDI4Ing | ac | The Audio Commons Ontology | Revision: 1.3.0 | https://terminology.tib.eu/ts/ontologies/ac | 20 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Ing | bont | The BONSAI ontology | Version 0.2 - 2022-03-15 | https://terminology.tib.eu/ts/ontologies/bont | 8 | 2221 | 0 (0.00%) | 0 (0.00%) | 1 (0.05%) | 0 (0.00%) | 4 (0.18%) | 0 (0.00%) | 2216 (99.77%) |
| NFDI4Ing | condo | The COnCEPT upper-level Design Ontology | v0.1 | https://terminology.tib.eu/ts/ontologies/condo | 77 | 2221 | 0 (0.00%) | 0 (0.00%) | 2 (0.09%) | 0 (0.00%) | 5 (0.23%) | 0 (0.00%) | 2214 (99.68%) |
| NFDI4Ing | duo | The Data Use Ontology |  | https://terminology.tib.eu/ts/ontologies/duo | 308 | 2221 | 0 (0.00%) | 1 (0.05%) | 0 (0.00%) | 0 (0.00%) | 2 (0.09%) | 0 (0.00%) | 2218 (99.86%) |
| NFDI4Ing | emmo | The European Materials Modelling Ontology | 1.0.0-beta4 | https://terminology.tib.eu/ts/ontologies/emmo | 1191 | 2221 | 0 (0.00%) | 3 (0.14%) | 18 (0.81%) | 0 (0.00%) | 72 (3.24%) | 0 (0.00%) | 2128 (95.81%) |
| NFDI4Ing | fabio | The FRBR-aligned Bibliographic Ontology (FaBiO) | 2.3.1 | https://terminology.tib.eu/ts/ontologies/fabio | 274 | 2221 | 0 (0.00%) | 0 (0.00%) | 4 (0.18%) | 2 (0.09%) | 18 (0.81%) | 0 (0.00%) | 2197 (98.92%) |
| NFDI4Ing | hpont | The Heat Pump Ontology (HPOnt). | 0.2 | https://terminology.tib.eu/ts/ontologies/hpont | 4 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Ing | panet | The Photon and Neutron Experimental Techniques Ontology | 1.3.0 | https://terminology.tib.eu/ts/ontologies/panet | 507 | 2221 | 0 (0.00%) | 0 (0.00%) | 5 (0.23%) | 0 (0.00%) | 52 (2.34%) | 0 (0.00%) | 2164 (97.43%) |
| NFDI4Ing | pmat | The PolyMat ontology | 1.1.0 | https://terminology.tib.eu/ts/ontologies/pmat | 231 | 2221 | 0 (0.00%) | 6 (0.27%) | 7 (0.32%) | 6 (0.27%) | 80 (3.60%) | 0 (0.00%) | 2122 (95.54%) |
| NFDI4Ing | prov | The PROV Ontology | Recommendation version 2013-04-30 | https://terminology.tib.eu/ts/ontologies/prov | 31 | 2221 | 0 (0.00%) | 2 (0.09%) | 0 (0.00%) | 0 (0.00%) | 4 (0.18%) | 0 (0.00%) | 2215 (99.73%) |
| NFDI4Ing | rosetta | The ROSETTA ontology of industrial robotics devices and robotic skills. | 0.9 | https://terminology.tib.eu/ts/ontologies/rosetta | 594 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 1 (0.05%) | 0 (0.00%) | 2220 (99.95%) |
| NFDI4Ing | sd | The Software Description Ontology | 1.9.0 | https://terminology.tib.eu/ts/ontologies/sd | 33 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2 (0.09%) | 10 (0.45%) | 0 (0.00%) | 2209 (99.46%) |
| NFDI4Ing | swo | The Software Ontology (SWO) | 2023-03-05 | https://terminology.tib.eu/ts/ontologies/swo | 1971 | 2221 | 0 (0.00%) | 1 (0.05%) | 0 (0.00%) | 0 (0.00%) | 22 (0.99%) | 0 (0.00%) | 2198 (98.96%) |
| NFDI4Ing | td | Thing Description Ontology | 0.9.0 | https://terminology.tib.eu/ts/ontologies/td | 6 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Ing | tai | tribAIn - Derived from the ancient Greek word “tribein” (= rubbing) and the acronym “AI” (= Artificial Intelligence) |  | https://terminology.tib.eu/ts/ontologies/tai | 237 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 1 (0.05%) | 0 (0.00%) | 0 (0.00%) | 2220 (99.95%) |
| NFDI4Ing | tso | TUBES system ontology | 0.3.0 | https://terminology.tib.eu/ts/ontologies/tso | 40 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 6 (0.27%) | 0 (0.00%) | 2215 (99.73%) |
| NFDI4Ing | uat | Unified Astronomy Thesaurus (UAT) |  | https://terminology.tib.eu/ts/ontologies/uat | 2411 | 2221 | 0 (0.00%) | 0 (0.00%) | 2 (0.09%) | 2 (0.09%) | 111 (5.00%) | 0 (0.00%) | 2106 (94.82%) |
| NFDI4Ing | uo | Units of measurement ontology | 2026-07-31 | https://terminology.tib.eu/ts/ontologies/uo | 574 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 51 (2.30%) | 0 (0.00%) | 2170 (97.70%) |
| NFDI4Ing | kitmtxx | Vocabulary of Materials Tribology Lab at KIT |  | https://terminology.tib.eu/ts/ontologies/kitmtxx | 1354 | 2221 | 0 (0.00%) | 8 (0.36%) | 16 (0.72%) | 13 (0.58%) | 151 (6.80%) | 0 (0.00%) | 2033 (91.54%) |
| NFDI4Ing | vssocore | VSSo Core: Vehicle Signal Specification Core Ontology. W3C First Public Working Draft 03 March 2022 | v2.0-develop | https://terminology.tib.eu/ts/ontologies/vssocore | 8 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 2221 (100.00%) |
| NFDI4Ing | sh | W3C Shapes Constraint Language (SHACL) Vocabulary |  | https://terminology.tib.eu/ts/ontologies/sh | 40 | 2221 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 7 (0.32%) | 0 (0.00%) | 2214 (99.68%) |

## Supplementary Table S7. Asserted TIB-derived bridge mappings by defining ontology

The external bridge contains 245 TIB-derived mapping assertions involving 159 H₂KG classes and 29 defining ontologies. Original ontology IRIs are mapping targets; TIB catalogue URLs are provenance links only. `skos:broadMatch` means that the H₂KG subject is narrower than its target, whereas `skos:narrowMatch` means that the H₂KG subject is broader.

| Ontology ID | Ontology title | Version | Exact | H₂KG narrower (`broadMatch`) | H₂KG broader (`narrowMatch`) | Assertions | H₂KG classes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| afo | Allotrope Foundation Ontology Merged Without QUDT And Inferred (REC/2025/03) | REC/2026/03 | 18 | 6 | 12 | 36 | 36 |
| bao | BioAssay Ontology | 2.1 | 5 | 1 | 5 | 11 | 11 |
| chameo | CHAracterisation MEthodology Ontology | 1.0.0 | 7 | 0 | 1 | 8 | 8 |
| cao | Chemical Analysis Metadata Platform (ChAMP) Ontology version 0.2 | 0.2 | 3 | 0 | 0 | 3 | 3 |
| chebi | Chemical Entities of Biological Interest | 255 | 16 | 0 | 0 | 16 | 16 |
| chmo | Chemical Methods Ontology | 2026-05-28 | 29 | 1 | 2 | 32 | 32 |
| dr | Digital Reference | 1.2.12 | 1 | 1 | 0 | 2 | 2 |
| edam | EDAM - The ontology of data analysis and management | 1.25-20260626T1230Z | 0 | 3 | 0 | 3 | 3 |
| ms | Mass Spectrometry | version-not-reported-in-TIB-snapshot | 1 | 3 | 0 | 4 | 4 |
| modsci | Modern Science Ontology | 1.1 | 1 | 1 | 0 | 2 | 2 |
| mwo | NFDI Matwerk Ontology | 3.0.2 | 1 | 2 | 0 | 3 | 3 |
| obi | Ontology for Biomedical Investigations | 2026-07-27 | 5 | 1 | 0 | 6 | 6 |
| om | Ontology of units of Measure (OM) | 2.0.59 | 4 | 0 | 0 | 4 | 4 |
| pmd | PMD Core Ontology | 3.1.1 | 4 | 0 | 0 | 4 | 4 |
| oeo | Repository for the Open Energy Ontology (OEO) | 2.13.0 | 4 | 4 | 1 | 9 | 9 |
| s4ener | SAREF for Energy Flexibility | v2.1.1 | 1 | 0 | 0 | 1 | 1 |
| s4inma | SAREF4INMA: an extension of SAREF for the industry and manufacturing domain | v2.1.1 | 0 | 8 | 0 | 8 | 8 |
| sio | Semanticscience Integrated Ontology (SIO) | 1.61 | 2 | 14 | 0 | 16 | 16 |
| ssnsystem | System capabilities, operating ranges, and survival ranges ontology | version-not-reported-in-TIB-snapshot | 0 | 1 | 0 | 1 | 1 |
| sbo | Systems Biology Ontology | 28:08:2021 03:13 | 2 | 0 | 0 | 2 | 2 |
| t4fs | terms4FAIRskills (T4FS) | 2025-02-09 | 1 | 4 | 0 | 5 | 5 |
| envo | The Environment Ontology | 2026-06-26 | 0 | 3 | 1 | 4 | 4 |
| emmo | The European Materials Modelling Ontology | 1.0.0-beta4 | 3 | 8 | 0 | 11 | 11 |
| fabio | The FRBR-aligned Bibliographic Ontology (FaBiO) | 2.3.1 | 0 | 4 | 0 | 4 | 4 |
| pmat | The PolyMat ontology | 1.1.0 | 6 | 2 | 0 | 8 | 8 |
| prov | The PROV Ontology | Recommendation version 2013-04-30 | 1 | 0 | 0 | 1 | 1 |
| uat | Unified Astronomy Thesaurus (UAT) | version-not-reported-in-TIB-snapshot | 0 | 1 | 0 | 1 | 1 |
| voc4cat | Voc4Cat - A SKOS vocabulary for Catalysis | version-not-reported-in-TIB-snapshot | 17 | 9 | 0 | 26 | 26 |
| kitmtxx | Vocabulary of Materials Tribology Lab at KIT | version-not-reported-in-TIB-snapshot | 8 | 6 | 0 | 14 | 14 |

Related benchmark candidates are deliberately absent from this table because they are not asserted as mappings.

## Supplementary Table S8. Synthetic TEM profile field dictionary

| H₂KG IRI | Preferred label | Role | Value form | Cardinality/condition | QUDT guidance | Metadata boundary |
| --- | --- | --- | --- | --- | --- | --- |
| h2kg:TransmissionElectronMicroscopyImaging | Transmission Electron Microscopy Imaging | measurement | workflow occurrence | one required | QUDT unit and quantity kind required when a numeric value is asserted. | Method identity; source citation or record identifier. |
| h2kg:Matter | Matter | input material/sample context | IRI or linked material record | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. | Sample, composition, and preparation details may remain metadata. |
| h2kg:TEMInstrument | TEM Instrument | instrument | linked instrument occurrence | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. | Brand/model belongs in metadata. |
| h2kg:MicrostructureImageDataset | Microstructure Image Dataset | raw dataset | linked data occurrence | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. | File, detector, and local storage details belong in metadata. |
| h2kg:AcceleratingVoltage | Accelerating Voltage | conditional parameter | quantity value when numeric | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/KiloV; quantity kind http://qudt.org/vocab/quantitykind/ElectricPotential. | Use a QUDT QuantityValue with numeric value, unit, and quantity kind when a value is asserted. |
| h2kg:Magnification | Magnification | conditional parameter | quantity value when numeric | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/UNITLESS; quantity kind http://qudt.org/vocab/quantitykind/Dimensionless. | Use a QUDT QuantityValue with numeric value, unit, and quantity kind when a value is asserted. |
| h2kg:WorkingDistance | Working Distance | conditional parameter | quantity value when numeric | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/MilliM; quantity kind http://qudt.org/vocab/quantitykind/Length. | Use a QUDT QuantityValue with numeric value, unit, and quantity kind when a value is asserted. |
| h2kg:Temperature | Temperature | conditional parameter | quantity value when numeric | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/DEG_C; quantity kind http://qudt.org/vocab/quantitykind/ThermodynamicTemperature. | Use a QUDT QuantityValue with numeric value, unit, and quantity kind when a value is asserted. |
| h2kg:RelativeHumidity | Relative Humidity | conditional parameter | quantity value when numeric | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/PERCENT; quantity kind http://qudt.org/vocab/quantitykind/RelativeHumidity. | Use a QUDT QuantityValue with numeric value, unit, and quantity kind when a value is asserted. |
| h2kg:VacuumChamberPressure | Vacuum Chamber Pressure | conditional parameter | quantity value when numeric | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/ATM; quantity kind http://qudt.org/vocab/quantitykind/Pressure. | Use a QUDT QuantityValue with numeric value, unit, and quantity kind when a value is asserted. |
| h2kg:PdNanoparticleDiameter | Pd Nanoparticle Diameter | derived result | DataPoint; numeric or explicitly unreported | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. | Link through fromMeasurement, ofProperty, and a producing Process. |
| h2kg:Metadata | Metadata | contextual metadata | metadata node | optional | QUDT unit and quantity kind required when a numeric value is asserted. | Detector, grid, specimen descriptors, file details, and publication details remain metadata. |

All example values are synthetic. The profile defines a record shape, not an experimental protocol, a certified reference dataset, or evidence for a particle-size result.

## Supplementary Table S9. Synthetic TEM validation cases

| Test case | Deliberate change | Expected result | Observed result |
| --- | --- | --- | --- |
| Positive record | Complete synthetic TEM occurrence graph | Conforms | Conforms |
| Wrong measurement type | Remove `TransmissionElectronMicroscopyImaging` type | Fails | Fails |
| Missing measurement output | Remove measurement-to-raw-dataset `hasOutputData` | Fails | Fails |
| Incompatible result property | Replace `PdNanoparticleDiameter` occurrence type with unsupported property | Fails | Fails |
| Incomplete quantity value | Remove QUDT unit from the synthetic `5 nm` quantity value | Fails | Fails |

The result chain uses `DataPoint → ofProperty → property occurrence → hasQuantityValue → qudt:QuantityValue`. The `DataPoint` also points to the TEM measurement with `fromMeasurement` and to the analysis process with `prov:wasGeneratedBy`. Parameter settings use `Measurement → hasParameter → Parameter record → ofProperty → property occurrence`. Thus, a scientific characteristic is not reclassified as a parameter.

## Reproducibility and artifact locations

The release state is identified by Git commit `55e7d86bdde3d41d85411f745b291d8caa3f8d31`. The principal files are:

- `ontology_release/output/ontology/h2kg-v2-complete.ttl` and `.jsonld`: complete recommended distribution.
- `ontology_release/output/ontology/h2kg-v2-taxonomy.ttl` and `.jsonld`: taxonomy-only distribution.
- `ontology_release/output/ontology/h2kg-v2-workflow-profiles.ttl` and `.jsonld`: canonical workflow-use profiles.
- `ontology_release/output/ontology/h2kg-v2-external-bridge.ttl` and `.jsonld`: asserted external mappings.
- `ontology_release/output/benchmarks/tib_collections/`: frozen benchmark reports and workbooks.
- `ontology_release/output/method_profiles/tem/`: synthetic TEM record, SHACL shape, capture template, field dictionary, and validation report.

The ontology resolves from `https://w3id.org/h2kg/hydrogen-ontology`; human-facing release documentation is available at `https://vimilabs.github.io/AIMWORKS/`.
