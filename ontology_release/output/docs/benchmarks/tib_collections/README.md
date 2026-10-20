# H2KG--TIB Collection Benchmark

This package benchmarks `2226` active local H2KG classes against the ontologies assigned to NFDI4Cat, NFDI4Energy, and NFDI4Ing in the TIB catalogue snapshot retrieved at `2026-10-14T07:32:20+00:00`.

Primary percentages use native classes only. Imported availability is documented separately. BattINFO remains one of the 165 catalogue-membership rows but is marked not assessed because native frozen evidence is unavailable; it contributes no semantic outcome and is excluded from the NFDI4Ing union. Every assessed row assigns each H2KG class to exactly one outcome. Percentages are rounded independently, so displayed totals may differ from 100% by 0.01 percentage point while exact counts remain authoritative.

TIB catalogue term/property/individual counts are retained as descriptive metadata. They may include imported resources and are never used as the H2KG overlap denominator.

The analysis is fully automated and conservative. Exact machine decisions are not described as human-validated equivalence. A publishable build contains zero semantic abstentions: uncertain candidates are reported as related, and failed API retrieval blocks publication.

## Files

- `collection_summary.csv`: collection-level percentages.
- `ontology_summary.csv`: manuscript-ready percentages for every ontology under each collection.
- `ontology_benchmark.csv` and `.md`: the complete 165-row count-and-percentage supplementary table.
- `h2kg_tib_collection_benchmark.xlsx`: complete documented benchmark.
- `h2kg_tib_manuscript_tables.xlsx`: compact manuscript tables.
- `candidate_decisions.csv`: evidence for every discovered correspondence.
- `retrieval_failures.csv`: blocking API failures; empty in a publishable build.
- `ambiguity_resolution_history.csv`: every former semantic abstention and its deterministic final result.
- `pre_post_harmonization.csv`: collection-level baseline/final comparison.
- `h2kg_corrections.csv`: high-confidence internal corrections applied before the final benchmark.
- `h2kg_collection_coverage.csv`: class-level collection outcomes.
- `imported_availability.csv`: secondary import-inclusive evidence.
- `automatic_harmonization_registry.json`: exact, machine-safe mappings and non-destructive label actions.

Frozen inputs: `ontology_release\input\tib_collection_snapshot.json` and `ontology_release\input\tib_collection_candidate_cache.json`.
