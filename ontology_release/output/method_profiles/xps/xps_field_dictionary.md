# Field Dictionary

| Semantic role | H2KG term | Cardinality / condition | QUDT guidance |
| --- | --- | --- | --- |
| measurement | `X Ray Photoelectron Spectroscopy Measurement` | one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| input material/sample context | `Matter` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| instrument | `XPS Instrument` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| raw dataset | `XPS Dataset` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| conditional parameter | `XPS Pass Energy` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/EV; quantity kind http://qudt.org/vocab/quantitykind/Energy. |
| conditional parameter | `XPS Take Off Angle` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/DEG; quantity kind http://qudt.org/vocab/quantitykind/PlaneAngle. |
| conditional parameter | `XPS Analysis Area` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/MicroM2; quantity kind http://qudt.org/vocab/quantitykind/Area. |
| derived result | `Binding Energy` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| derived result | `C 1 s Atomic Percent` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| derived result | `O 1 s Atomic Percent` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| derived result | `F 1 s Atomic Percent` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| derived result | `N 1 s Atomic Percent` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| derived result | `Carbon To Oxygen Atom Ratio` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| derived result | `Metal Atomic Percent` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| contextual metadata | `Metadata` | optional | QUDT unit and quantity kind required when a numeric value is asserted. |
