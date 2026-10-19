# Resolution matrix for comments in the 13 July draft

This internal matrix records the disposition of all 31 comments extracted from `SF_MEs_MK_Paper draft_13July_KM (1).docx`. Comment identifiers are the identifiers stored in the source DOCX.

| Comment ID | Comment issue | Resolution in the new article | Location |
| ---: | --- | --- | --- |
| 0 | Title should describe a domain-specific or domain-standard ontology | Replaced the announcement-style title with a technically descriptive, journal-compliant title using “domain-specific ontology.” | Title |
| 3 | “Semantic resources” was imprecise | Replaced generic wording with explicit categories: ontologies, vocabularies, provenance models, quantity/unit systems, and terminology collections. | Introduction; Table 1 |
| 4 | H₂KG name suggests a knowledge graph although the artifact is an ontology | States explicitly that H₂KG is the maintained name of the ontology and that occurrence graphs are separate instance data. | Introduction; Methods, Scope and requirements |
| 5 | Abbreviation should be spelled out | Abbreviations are minimized and expanded at first textual use. | Throughout |
| 7 | Too many abbreviations in the abstract | Abstract defines H₂KG and FAIR and avoids all other abbreviations. | Abstract |
| 9 | Validation criteria were unspecified | Adds structural, logical, SHACL, serialization-parity, competency-query, and negative profile-test criteria. | Methods, Validation; Results; Table 2 |
| 24 | Data interoperability problem was presented as unique to electrochemistry | Frames heterogeneity as a general research-data problem and then explains why hydrogen workflows intensify it. | Introduction, paragraph 1 |
| 25 | Misleading transition | Rewrote the argument from FAIR goals to domain semantics without the criticized contrast. | Introduction, paragraphs 2–3 |
| 26 | Abbreviations were inaccessible | Defines EMMO, QUDT, PROV-O, DCTERMS, TIB, and NFDI context in prose; removes an abbreviation glossary. | Introduction |
| 27 | Figure concepts should be introduced before abbreviations | Introduces the semantic-resource landscape in text and Table 1 before Figure 1. | Introduction; Table 1; Figure 1 |
| 34 | Outcomes appeared in the background instead of comparable-resource review | Introduction reviews existing resources and states research questions only; all H₂KG counts and validation outcomes move to Results. | Introduction; Results |
| 35 | Background should be part of Introduction | Integrated the former background material into one coherent Introduction. | Introduction |
| 38 | Ontology development methodology was unclear | Adds scope derivation, acquisition and reuse, taxonomy correction, role migration, benchmarking, validation, and synthetic-case construction. | Methods |
| 39 | Add an accessible URL | Adds persistent W3ID, GitHub, and GitHub Pages locations in Data availability and Code availability. | Data availability; Code availability |
| 42 | Avoid laundry-list prose | Uses conceptual grouping, four compact main tables, and the supplement for inventories. | Throughout; Supplement |
| 43 | “Schema layer” was unclear | Replaces the phrase with explicit distinctions among ontology classes/properties, SHACL profile constraints, and occurrence records. | Methods, Scope and requirements; Intrinsic identity and contextual workflow use |
| 44 | Numerical metrics lacked interpretation | Explains what class and branch counts measure and states that larger class count is not inherently better. | Results, Ontology content; Discussion |
| 45 | Two items were redundant | Consolidates overlapping ontology-scope and workflow-representation statements. | Introduction and Methods |
| 46 | Structure resembled a white paper rather than a scientific article | Rebuilt the manuscript as an IMRaD Scientific Data Article with explicit research questions, methods, results, discussion, and limitations. | Entire manuscript |
| 47 | Repetition | Generic architecture is explained once; detailed inventories move to tables and supplement. | Entire manuscript |
| 48 | Requested a real-world use case | A real-world claim was not supportable from the available evidence; the replacement is explicitly synthetic and used only to test representation and validation. | Methods and Results, Synthetic TEM profile |
| 49 | Figure was unreadable | Replaced source screenshots and dense graphs with five purpose-built vector figures and publication-resolution rasters. | Figures 1–5 |
| 50 | Long term lists obscured the argument | Replaced long in-text lists with semantic categories and supplementary tables. | Tables 1–4; Supplement |
| 51 | Validation language implied missing automated checks | Reports the implemented external reasoner, SHACL, serialization, structural, and competency checks; limitations are framed separately. | Methods, Validation; Results, Technical quality |
| 52 | Explain possible interaction with computational systems | Describes machine-readable profiles as inputs for forms, structured exports, and targeted extraction without making unsupported automation claims. | Discussion |
| 53 | Computational scalability was ignored | States explicitly that no large-instance performance benchmark has yet been conducted and identifies query/reasoner scaling as future evaluation. | Discussion, Limitations |
| 54 | Conclusion should explain field-level change | Conclusion states the practical contribution: a shared way to state what a value describes, how it was produced, and what context is required. | Conclusions |
| 57 | Repetitive class inventory | Removes prose inventories and reports only interpretable aggregates in the main article. | Results; Supplementary Tables S1–S2 |
| 58 | Methods appeared too late | Methods now precede all Results and quantitative evaluation. | Article structure |
| 59 | Broken data link | Replaces obsolete links with the established W3ID, repository, GitHub Pages site, exact commit, and named artifact paths. | Data availability; Code availability |
| 60 | Persistent IRI should support human and machine resolution | Uses the established H₂KG W3ID as the canonical ontology identifier and documents machine-readable Turtle/JSON-LD plus human-facing release pages. | Methods, Scope; Data availability |
