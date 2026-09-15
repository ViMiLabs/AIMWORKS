# Field Dictionary

| Semantic role | H2KG term | Cardinality / condition | QUDT guidance |
| --- | --- | --- | --- |
| measurement | `Scanning Electron Microscopy Imaging` | one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| input material/sample context | `Matter` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| instrument | `SEM Instrument` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| raw dataset | `SEM Image Dataset` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| conditional parameter | `Accelerating Voltage` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/KiloV; quantity kind http://qudt.org/vocab/quantitykind/ElectricPotential. |
| conditional parameter | `Magnification` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/UNITLESS; quantity kind http://qudt.org/vocab/quantitykind/Dimensionless. |
| conditional parameter | `Working Distance` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/MilliM; quantity kind http://qudt.org/vocab/quantitykind/Length. |
| conditional parameter | `Temperature` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/DEG_C; quantity kind http://qudt.org/vocab/quantitykind/ThermodynamicTemperature. |
| conditional parameter | `Relative Humidity` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/PERCENT; quantity kind http://qudt.org/vocab/quantitykind/RelativeHumidity. |
| derived result | `Catalyst Particle Diameter` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| contextual metadata | `Metadata` | optional | QUDT unit and quantity kind required when a numeric value is asserted. |
