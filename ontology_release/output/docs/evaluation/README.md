# H2KG application evaluation package

This package separates reproducible machine checks from authentic independent application review.

## Completed reproducible checks

- DECODE concepts: 29 public H2KG outcomes and 544 DECODE-local outcomes out of 573 canonical source concepts.
- ITC overlap: 6 of 44 ITC fields have concept-wide source alignments; 5 has an occurrence-specific source alignment, and 33 have no source occurrence in this corpus.
- Competency demonstrations: 4 named queries. RQ1 runs semantic-anchor and normalized exact-label retrieval independently over the same source-output population and the same 24 ITC inputs. No precision, recall, or retrieval-improvement estimate is claimed.
- Automated consistency inventory: 5486 deterministic registry and traceability checks. These are not reviewer judgments.
- Independent application audit: review_pending for 134 prespecified items assessed by two external experts; publication remains blocked until valid workbooks and any required adjudication are imported.
- Comparator assessment: 20 author-curated capability judgments across H2KG, EDO, HDO, and HOLY. Automation verifies RDF parsing and cited-IRI presence only; no aggregate score is calculated.
- BattINFO is retained as a TIB catalogue membership but is not assigned semantic outcomes because native frozen evidence is unavailable.

## Interpretation boundary

The review-pending package does not infer human acceptance from existing ontology registries. Future acceptance of a DECODE-local concept will confirm its project-local identity and role only; it will not create an H2KG class, W3ID identifier, synonym, or external mapping.
