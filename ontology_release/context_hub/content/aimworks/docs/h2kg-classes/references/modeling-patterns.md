# Class Modeling Patterns

Use these patterns for class decisions:

- local domain distinction plus external semantic anchor
- local application class as subclass of an external generic class
- controlled vocabulary class kept separate from example instances

Good pattern:

- `Measurement` remains local
- `Measurement rdfs:subClassOf <external electrochemical measurement class>`

Avoid this pattern:

- deleting a local application class immediately after finding a vaguely similar external term
