# Field Dictionary

| Semantic role | H2KG term | Cardinality / condition | QUDT guidance |
| --- | --- | --- | --- |
| measurement | `IC-SEM Imaging Measurement` | one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| input material/sample context | `Matter` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| instrument | `IC-SEM Instrument` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| raw dataset | `SEM Image Dataset` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| conditional parameter | `Ion Beam Energy` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/KiloV; quantity kind http://qudt.org/vocab/quantitykind/ElectricPotential. |
| conditional parameter | `Ion Beam Current` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/PicoA; quantity kind http://qudt.org/vocab/quantitykind/ElectricCurrent. |
| conditional parameter | `Electron Beam Energy` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/KiloV; quantity kind http://qudt.org/vocab/quantitykind/ElectricPotential. |
| conditional parameter | `Electron Current` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/PicoA; quantity kind http://qudt.org/vocab/quantitykind/ElectricCurrent. |
| conditional parameter | `Pixel Size` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/NanoM; quantity kind http://qudt.org/vocab/quantitykind/Length. |
| conditional parameter | `Cut Thickness` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/NanoM; quantity kind http://qudt.org/vocab/quantitykind/Length. |
| conditional parameter | `Dwell Time` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/HR; quantity kind http://qudt.org/vocab/quantitykind/Time. |
| conditional parameter | `Exposure Time` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/SEC; quantity kind http://qudt.org/vocab/quantitykind/Time. |
| conditional parameter | `Magnification` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/UNITLESS; quantity kind http://qudt.org/vocab/quantitykind/Dimensionless. |
| conditional parameter | `Microscopy Measured Area` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/MicroM2; quantity kind http://qudt.org/vocab/quantitykind/Area. |
| conditional parameter | `Temperature` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/DEG_C; quantity kind http://qudt.org/vocab/quantitykind/ThermodynamicTemperature. |
| conditional parameter | `Relative Humidity` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/PERCENT; quantity kind http://qudt.org/vocab/quantitykind/RelativeHumidity. |
| conditional parameter | `Vacuum Chamber Pressure` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/ATM; quantity kind http://qudt.org/vocab/quantitykind/Pressure. |
| conditional parameter | `Total Acquisition Time` | conditional when reported or method-defining | Observed: unit http://qudt.org/vocab/unit/HR; quantity kind http://qudt.org/vocab/quantitykind/Time. |
| derived result | `Membrane Electrode Assembly Thickness` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| derived result | `Gas Diffusion Layer Thickness` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| derived result | `Total Porosity` | at least one required | QUDT unit and quantity kind required when a numeric value is asserted. |
| contextual metadata | `Metadata` | optional | QUDT unit and quantity kind required when a numeric value is asserted. |
