# Field Dictionary

| Semantic role | H2KG term | Cardinality / condition | QUDT guidance |
| --- | --- | --- | --- |
| measurement | `X Ray Diffraction Measurement` | one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| input material/sample context | `Matter` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| instrument | `X Ray Diffractometer` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| raw dataset | `XRD Pattern Dataset` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| conditional parameter | `X Ray Wavelength` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/NanoM; quantity kind http://qudt.org/vocab/quantitykind/Wavelength. |
| conditional parameter | `XRD Step Size` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/DEG; quantity kind http://qudt.org/vocab/quantitykind/PlaneAngle. |
| conditional parameter | `XRD Two Theta Start` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/DEG; quantity kind http://qudt.org/vocab/quantitykind/PlaneAngle. |
| conditional parameter | `XRD Two Theta End` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/DEG; quantity kind http://qudt.org/vocab/quantitykind/PlaneAngle. |
| derived result | `Diffraction Peak Position 2 Theta` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| derived result | `XRD Peak FWHM` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| derived result | `Pt Crystallite Size` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| derived result | `Theoretical Metal Surface Area` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| contextual metadata | `Metadata` | optional | QUDT unit and quantity kind required when a numeric value is asserted. |
