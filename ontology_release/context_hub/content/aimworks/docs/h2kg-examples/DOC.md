# H2KG Examples

This entry describes valid modelling patterns for representative H2KG cases.

## Example 1: Measurement Activity

Pattern:

- a measurement resource
- linked to a measured property via `measures`
- linked to parameters via `hasParameter`
- linked to an instrument via `usesInstrument`

Why it is valid:

- the activity remains distinct from the property being characterized
- supporting conditions are modelled as parameters rather than lost in free text

## Example 2: Property To Quantity Value

Pattern:

- a property resource
- linked to a quantity-value node via `hasQuantityValue`
- the quantity-value node uses QUDT unit and quantity kind semantics

Why it is valid:

- the measured property stays conceptually distinct from its numeric realization
- unit and quantity-kind reuse stays interoperable

## Example 3: Material Inputs And Outputs

Pattern:

- a process resource
- input material via `hasInputMaterial`
- output material via `hasOutputMaterial`

Why it is valid:

- material flow is explicit
- the process can still have data inputs or outputs separately

## Example 4: Normalized Results

Pattern:

- a property or result
- normalized against a named basis via `normalizedTo`

Why it is valid:

- the ontology preserves the basis of comparison
- downstream users can distinguish raw and normalized reporting

## Example 5: Provenance Around Generated Data

Pattern:

- a process or measurement produces data
- data output is distinguished from material output
- provenance is represented through PROV-O compatible semantics where appropriate

Why it is valid:

- release metadata and domain data remain interoperable
- generated artifacts can be tracked without collapsing them into schema
