# Figure content and source notes

All five figures were generated as editable SVG and 400 dpi PNG files by `build_article.py`. No third-party figure or unpublished source document is reproduced.

1. **Scope architecture:** generated from the H₂KG 2.2 release profile, taxonomy validation report, and external-alignment policy.
2. **Engineering workflow:** generated from the release pipeline stages and validation gates implemented under `ontology_release/src/aimworks_ontology_release/`.
3. **Taxonomy and role pattern:** branch counts come from `taxonomy_validation.json`; the occurrence pattern follows the canonical `hasParameter / ofProperty / hasQuantityValue` model.
4. **TIB benchmark:** percentages are read directly from the frozen `benchmark_summary.json` generated from the 14 October 2026 snapshot.
5. **Synthetic TEM workflow:** generated from `output/method_profiles/tem/synthetic_example.ttl` and the TEM SHACL profile. Every occurrence value is synthetic.

The SVG files retain text and shapes as editable vector objects. Arrows in Figure 5 follow RDF subject-to-object direction. The edge audit is stored in `tables/figure_5_edge_audit.csv`.
