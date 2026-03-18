# Module Index

Generated BattINFO-inspired engineering modules for the asserted H2KG release.

## Top / metadata

- File: `modules/top.ttl`
- Purpose: Ontology header, release metadata, import declarations, and publication-level annotations.
- Local terms: `0`
- Triples: `66`
- Dependencies: None

## Core local terms

- File: `modules/core.ttl`
- Purpose: Local H2KG backbone terms that anchor the application ontology and do not fit a narrower domain module.
- Local terms: `16`
- Triples: `164`
- Dependencies: None

## Materials

- File: `modules/materials.ttl`
- Purpose: Local material, chemical, catalyst, ionomer, and matter-oriented terms retained in the H2KG namespace.
- Local terms: `596`
- Triples: `6421`
- Dependencies: core, processes_manufacturing, measurements_data

## Components and devices

- File: `modules/components_devices.ttl`
- Purpose: Local components, devices, assemblies, and hardware-oriented terms for PEMFC and hydrogen electrochemical systems.
- Local terms: `137`
- Triples: `1632`
- Dependencies: core, measurements_data, materials, processes_manufacturing

## Processes and manufacturing

- File: `modules/processes_manufacturing.ttl`
- Purpose: Local process, fabrication, coating, printing, and manufacturing terms.
- Local terms: `93`
- Triples: `1038`
- Dependencies: core, materials, measurements_data

## Measurements, properties, and data

- File: `modules/measurements_data.ttl`
- Purpose: Local measurement, property, parameter, data, metadata, unit, and instrument terms.
- Local terms: `1032`
- Triples: `13210`
- Dependencies: core, materials, components_devices

## Mappings and alignments

- File: `modules/mappings.ttl`
- Purpose: Conservative reviewed alignment assertions connecting H2KG local terms to external ontologies.
- Local terms: `0`
- Triples: `366`
- Dependencies: None

## Examples and individuals

- File: `modules/examples.ttl`
- Purpose: Separated individuals, example resources, and data-like content kept outside the asserted local TBox release.
- Local terms: `0`
- Triples: `13418`
- Dependencies: None

