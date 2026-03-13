#!/usr/bin/env bash
set -eu

curl -I -H 'Accept: text/html' 'https://w3id.org/h2kg/hydrogen-ontology'
curl -I -H 'Accept: text/turtle' 'https://w3id.org/h2kg/hydrogen-ontology'
curl -I -H 'Accept: application/ld+json' 'https://w3id.org/h2kg/hydrogen-ontology'
curl -I 'https://w3id.org/h2kg/hydrogen-ontology/source'
curl -I 'https://w3id.org/h2kg/hydrogen-ontology/inferred'
curl -I 'https://w3id.org/h2kg/hydrogen-ontology/latest'
curl -I 'https://w3id.org/h2kg/hydrogen-ontology/context'
curl -I 'https://w3id.org/h2kg/hydrogen-ontology/2026.3.0'
curl -I 'https://w3id.org/h2kg/hydrogen-ontology/2026.3.0/inferred'
