# Publishing Notes

1. Keep the ontology IRI stable at `https://w3id.org/h2kg/hydrogen-ontology`.
2. Deploy `output/publication/` as the public static root. The publication layout now includes `source/`, `inferred/`, `latest/`, `context/`, and `2026.3.0/`.
3. Register the generated `.htaccess` rules with the w3id maintainers or mirror them into the existing namespace configuration.
4. Ensure that:
   - `https://w3id.org/h2kg/hydrogen-ontology/hydrogen-ontology.html` resolves to the single-page ontology reference.
   - `https://w3id.org/h2kg/hydrogen-ontology/source/ontology.ttl` resolves to the asserted source ontology.
   - `https://w3id.org/h2kg/hydrogen-ontology/inferred/ontology.ttl` resolves to the inferred ontology.
   - `https://w3id.org/h2kg/hydrogen-ontology/latest/ontology.ttl` resolves to the latest asserted release.
   - `https://w3id.org/h2kg/hydrogen-ontology/2026.3.0/ontology.ttl` resolves to the version-pinned asserted release.
5. If namespace migration is enabled later, also publish the generated migration map and add redirects for legacy hash IRIs.

The current default remains hash-based because the existing ontology already uses stable hash IRIs and preserving them is the safest backward-compatible first release.
