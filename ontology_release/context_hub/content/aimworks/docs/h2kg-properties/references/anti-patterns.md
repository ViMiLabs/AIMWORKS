# Property Anti-Patterns

Do not do the following:

- map an object property to a datatype property
- use a metadata literal relation where a process-material relation is intended
- connect a measurement directly to a unit and skip the quantity-value node when a quantity-value pattern is required
- use one generic relation for both data outputs and material outputs

Preferred correction pattern:

- process to material via `hasInputMaterial` or `hasOutputMaterial`
- process to data via `hasInputData` or `hasOutputData`
- property to quantity node via `hasQuantityValue`
- quantity node to unit and quantity kind via QUDT terms
