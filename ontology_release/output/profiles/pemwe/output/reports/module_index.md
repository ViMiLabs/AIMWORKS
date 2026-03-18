# Module Index

Generated BattINFO-inspired engineering modules for the asserted H2KG release.

## Top / metadata

- File: `modules/top.ttl`
- Purpose: Ontology header, release metadata, import declarations, and publication-level annotations.
- Local terms: `0`
- Triples: `37`
- Dependencies: None

## Core local terms

- File: `modules/core.ttl`
- Purpose: Local H2KG backbone terms that anchor the application ontology and do not fit a narrower domain module.
- Local terms: `11`
- Triples: `83`
- Dependencies: None

## Materials

- File: `modules/materials.ttl`
- Purpose: Local material, chemical, catalyst, ionomer, and matter-oriented terms retained in the H2KG namespace.
- Local terms: `133`
- Triples: `1339`
- Dependencies: core, processes_manufacturing

## Components and devices

- File: `modules/components_devices.ttl`
- Purpose: Local components, devices, assemblies, and hardware-oriented terms for PEMFC and hydrogen electrochemical systems.
- Local terms: `89`
- Triples: `917`
- Dependencies: core, materials, measurements_data, processes_manufacturing

## Processes and manufacturing

- File: `modules/processes_manufacturing.ttl`
- Purpose: Local process, fabrication, coating, printing, and manufacturing terms.
- Local terms: `49`
- Triples: `403`
- Dependencies: core, materials

## Measurements, properties, and data

- File: `modules/measurements_data.ttl`
- Purpose: Local measurement, property, parameter, data, metadata, unit, and instrument terms.
- Local terms: `319`
- Triples: `3951`
- Dependencies: core, components_devices, materials

## Mappings and alignments

- File: `modules/mappings.ttl`
- Purpose: Conservative reviewed alignment assertions connecting H2KG local terms to external ontologies.
- Local terms: `0`
- Triples: `163`
- Dependencies: None

## Examples and individuals

- File: `modules/examples.ttl`
- Purpose: Separated individuals, example resources, and data-like content kept outside the asserted local TBox release.
- Local terms: `0`
- Triples: `3920`
- Dependencies: None

