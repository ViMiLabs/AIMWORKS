PYTHON ?= python
PACKAGE = aimworks_ontology_release
INPUT ?= input/current_ontology.jsonld

.PHONY: install inspect split map enrich annotate docs validate fair release run test

install:
	$(PYTHON) -m pip install -r requirements.txt

inspect:
	$(PYTHON) -m $(PACKAGE).cli inspect --input $(INPUT)

split:
	$(PYTHON) -m $(PACKAGE).cli split --input $(INPUT)

map:
	$(PYTHON) -m $(PACKAGE).cli map --input $(INPUT)

enrich:
	$(PYTHON) -m $(PACKAGE).cli enrich --input $(INPUT)

annotate:
	$(PYTHON) -m $(PACKAGE).cli annotate --input $(INPUT) --draft-llm

docs:
	$(PYTHON) -m $(PACKAGE).cli docs --input $(INPUT)

validate:
	$(PYTHON) -m $(PACKAGE).cli validate --input $(INPUT)

fair:
	$(PYTHON) -m $(PACKAGE).cli fair --input $(INPUT)

release:
	$(PYTHON) -m $(PACKAGE).cli release --input $(INPUT)

run:
	$(PYTHON) -m $(PACKAGE).cli run --input $(INPUT) --rewrite --split --build-docs --build-release --fair-check

test:
	$(PYTHON) -m pytest
