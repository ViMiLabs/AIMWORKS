#!/usr/bin/env sh
set -eu

curl -I -H "Accept: text/html" https://w3id.org/h2kg/hydrogen-ontology
curl -I -H "Accept: text/turtle" https://w3id.org/h2kg/hydrogen-ontology
curl -I -H "Accept: application/ld+json" https://w3id.org/h2kg/hydrogen-ontology

curl -I -H "Accept: text/html" https://w3id.org/h2kg/pemfc/hydrogen-ontology
curl -I -H "Accept: text/turtle" https://w3id.org/h2kg/pemfc/hydrogen-ontology

curl -I -H "Accept: text/html" https://w3id.org/h2kg/pemwe/hydrogen-ontology
curl -I -H "Accept: text/turtle" https://w3id.org/h2kg/pemwe/hydrogen-ontology
