# Import Catalog

Configured source ontologies and release-time reuse targets.

## EMMO Core

- Source ID: `emmo_core`
- Category: `primary`
- Enabled: `True`
- Optional: `False`
- Version label: `rolling/master`
- Base IRI: `https://w3id.org/emmo#`
- Fetch kind: `remote_rdf`
- Fetch location: `https://raw.githubusercontent.com/emmo-repo/EMMO/master/emmo.ttl`

## EMMO Electrochemistry

- Source ID: `echo`
- Category: `primary`
- Enabled: `True`
- Optional: `False`
- Version label: `rolling/master`
- Base IRI: `https://purls.helmholtz-metadaten.de/echo/`
- Fetch kind: `remote_rdf`
- Fetch location: `https://raw.githubusercontent.com/emmo-repo/domain-electrochemistry/master/electrochemistry.ttl`

## QUDT Schema

- Source ID: `qudt_schema`
- Category: `primary`
- Enabled: `True`
- Optional: `False`
- Version label: `3.1.1`
- Base IRI: `http://qudt.org/schema/qudt/`
- Fetch kind: `remote_rdf`
- Fetch location: `https://qudt.org/3.1.1/schema/qudt`

## QUDT Units

- Source ID: `qudt_units`
- Category: `primary`
- Enabled: `True`
- Optional: `False`
- Version label: `3.1.1`
- Base IRI: `http://qudt.org/vocab/unit/`
- Fetch kind: `remote_rdf`
- Fetch location: `https://qudt.org/3.1.1/vocab/unit`

## QUDT Quantity Kinds

- Source ID: `qudt_quantitykinds`
- Category: `primary`
- Enabled: `True`
- Optional: `False`
- Version label: `3.1.1`
- Base IRI: `http://qudt.org/vocab/quantitykind/`
- Fetch kind: `remote_rdf`
- Fetch location: `https://qudt.org/3.1.1/vocab/quantitykind`

## ChEBI

- Source ID: `chebi`
- Category: `primary`
- Enabled: `True`
- Optional: `False`
- Version label: `unversioned`
- Base IRI: `http://purl.obolibrary.org/obo/CHEBI_`
- Fetch kind: `ols4`
- Fetch location: `https://www.ebi.ac.uk/ols4/api/search`

## PROV-O

- Source ID: `provo`
- Category: `primary`
- Enabled: `True`
- Optional: `False`
- Version label: `unversioned`
- Base IRI: `http://www.w3.org/ns/prov#`
- Fetch kind: `remote_rdf`
- Fetch location: `https://www.w3.org/ns/prov-o.ttl`

## Dublin Core Terms

- Source ID: `dcterms`
- Category: `primary`
- Enabled: `True`
- Optional: `False`
- Version label: `unversioned`
- Base IRI: `http://purl.org/dc/terms/`
- Fetch kind: `remote_rdf`
- Fetch location: `https://www.dublincore.org/specifications/dublin-core/dcmi-terms/dublin_core_terms.ttl`

## VANN

- Source ID: `vann`
- Category: `primary`
- Enabled: `True`
- Optional: `False`
- Version label: `unversioned`
- Base IRI: `http://purl.org/vocab/vann/`
- Fetch kind: `remote_rdf`
- Fetch location: `http://purl.org/vocab/vann/vann-vocab-20100607.rdf`

## Open Energy Ontology

- Source ID: `oeo`
- Category: `fallback`
- Enabled: `True`
- Optional: `True`
- Version label: `rolling/master`
- Base IRI: `http://openenergy-platform.org/ontology/oeo/`
- Fetch kind: `remote_rdf`
- Fetch location: `https://raw.githubusercontent.com/OpenEnergyPlatform/ontology/master/oeo.ttl`

## Optional PEMFC-specific source ontology

- Source ID: `pemfc_specific`
- Category: `configurable`
- Enabled: `False`
- Optional: `True`
- Version label: `configurable`
- Base IRI: `None`
- Fetch kind: `configurable`
- Fetch location: ``

