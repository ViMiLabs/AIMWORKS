# Field Dictionary

| Semantic role | H2KG term | Cardinality / condition | QUDT guidance |
| --- | --- | --- | --- |
| measurement | `Neutron Tomography Measurement` | one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| input material/sample context | `Matter` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| instrument | `Neutron Tomography Instrument` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| raw dataset | `Tomographic Projection Dataset` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| conditional parameter | `Pixel Size` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/MicroM; quantity kind http://qudt.org/vocab/quantitykind/Length. |
| conditional parameter | `Exposure Time` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/SEC; quantity kind http://qudt.org/vocab/quantitykind/Time. |
| conditional parameter | `Projection Number` | conditional when reported or method-defining | Observed: unit not supplied; quantity kind http://qudt.org/vocab/quantitykind/Count. |
| conditional parameter | `Neutron Flux` | conditional when reported or method-defining | Observed: unit not supplied; quantity kind not supplied. |
| conditional parameter | `Spatial Resolution` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/MicroM; quantity kind http://qudt.org/vocab/quantitykind/Length. |
| conditional parameter | `Sample Detector Distance` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/MilliM; quantity kind http://qudt.org/vocab/quantitykind/Length. |
| conditional parameter | `Temperature` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/DEG_C; quantity kind http://qudt.org/vocab/quantitykind/ThermodynamicTemperature. |
| conditional parameter | `Relative Humidity` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/PERCENT; quantity kind http://qudt.org/vocab/quantitykind/RelativeHumidity. |
| derived result | `Tortuosity Factor` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| derived result | `Average Water Droplet Area` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| derived result | `Average Water Droplet Count` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| contextual metadata | `Metadata` | optional | QUDT unit and quantity kind required when a numeric value is asserted. |
