# Field Dictionary

| Semantic role | H2KG term | Cardinality / condition | QUDT guidance |
| --- | --- | --- | --- |
| measurement | `Atomic Force Microscopy Measurement` | one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| input material/sample context | `Matter` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| instrument | `AFM Instrument` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| raw dataset | `Microstructure Image Dataset` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| conditional parameter | `AFM Scan Speed` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/HZ; quantity kind http://qudt.org/vocab/quantitykind/Frequency. |
| conditional parameter | `AFM Tip Nominal Radius` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/NanoM; quantity kind http://qudt.org/vocab/quantitykind/Length. |
| conditional parameter | `Microscopy Measured Area` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/MicroM2; quantity kind http://qudt.org/vocab/quantitykind/Area. |
| conditional parameter | `Temperature` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/DEG_C; quantity kind http://qudt.org/vocab/quantitykind/ThermodynamicTemperature. |
| conditional parameter | `Relative Humidity` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/PERCENT; quantity kind http://qudt.org/vocab/quantitykind/RelativeHumidity. |
| conditional parameter | `Cantilever Spring Constant` | conditional when reported or method-defining | QUDT unit and quantity kind required when a numeric value is asserted. |
| conditional parameter | `Cantilever Resonance Frequency` | conditional when reported or method-defining | QUDT unit and quantity kind required when a numeric value is asserted. |
| derived result | `Mean Particle Size` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| contextual metadata | `Metadata` | optional | QUDT unit and quantity kind required when a numeric value is asserted. |
