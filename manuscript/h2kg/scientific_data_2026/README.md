# H₂KG 2.2 Scientific Data article package

This directory contains the manuscript and supplementary information for **A domain-specific ontology for interoperable hydrogen electrochemical research workflows**.

## Primary files

- `manuscript.md` and `H2KG_2_2_Scientific_Data_Article.docx`: article text.
- `supplementary_information.md` and `H2KG_2_2_Supplementary_Information.docx`: supplementary information.
- `figures/`: five editable SVG figures and matching 400 dpi PNG files.
- `tables/`: machine-readable supplementary tables, the benchmark workbook, and the Figure 5 edge audit.
- `bibliography_verification.md`: numbered-reference audit.
- `review_comment_resolution.md`: resolution matrix for all 31 comments in the previous draft.
- `manuscript_validation.json`: machine-readable acceptance report.

## Rebuild

From the repository root, install the release package with its manuscript dependencies and run:

```powershell
python -m pip install -e ".\ontology_release[manuscript]"
python .\manuscript\h2kg\scientific_data_2026\build_article.py
```

The builder reads the versioned H₂KG 2.2 reports and benchmark artifacts under `ontology_release/output/`, regenerates the supplement and all figures, writes both DOCX files, and fails if the manuscript acceptance checks do not pass.

## Evidence boundary

The transmission electron microscopy example is entirely synthetic. The package contains no DECODE scientific workflow content, unpublished source document, or experimental measurement claim.
