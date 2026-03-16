# Unit Enrichment Report

- Enabled: `True`
- Applied: `True`
- Source: `curated_unit_registry`
- Evidence directory: ``
- Curated units path: `C:\MARJAN\H2KG\AIMWORKS\ontology_release\output\profiles\pemfc\workspace\config\curated_units\pemfc_curated_units.csv`
- Terms examined: **901**
- Terms enriched: **1052**
- QUDT units linked: **653**
- Local reviewed units created: **399**
- Alias-propagated QUDT units: **89**
- Alias-propagated local reviewed units: **62**
- Review rows: **2147**

## Policy

- QUDT-backed units are asserted directly when cleaned PEMFC evidence is stable enough.
- Curated local PEMFC units are retained when no reviewed QUDT mapping is available yet.
- Exact ontology labels and alternative labels are checked conservatively to propagate units to duplicate or sibling terms.
- Ambiguous multi-unit terms remain in the review CSV instead of being forced into the ontology.

