# H2KG--TIB Collection Benchmark

This package benchmarks `2360` active local H2KG classes against the ontologies assigned to NFDI4Cat, NFDI4Energy, and NFDI4Ing in the TIB catalogue snapshot retrieved at `2026-10-14T07:32:20+00:00`.

Primary percentages use native classes only. Imported availability is documented separately. Each collection and ontology row assigns every H2KG class to exactly one of seven outcomes, so the outcome percentages total 100% subject only to decimal rounding.

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

Frozen inputs: `input\tib_collection_snapshot.json` and `input\tib_collection_candidate_cache.json`.
