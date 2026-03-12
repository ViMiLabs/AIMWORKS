PYTHON ?= python
CLI = $(PYTHON) -m aimworks_ontology_release.cli
INPUT = input/current_ontology.jsonld

.PHONY: install inspect split map enrich annotate docs validate fair release run test clean

install:
	$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) -m pip install -e .

inspect:
	$(CLI) inspect --input $(INPUT)

split:
	$(CLI) split --input $(INPUT)

map:
	$(CLI) map --input $(INPUT)

enrich:
	$(CLI) enrich --input $(INPUT)

annotate:
	$(CLI) annotate --input $(INPUT)

docs:
	$(CLI) docs --input $(INPUT)

validate:
	$(CLI) validate --input $(INPUT)

fair:
	$(CLI) fair --input $(INPUT)

release:
	$(CLI) release --input $(INPUT)

run:
	$(CLI) run --input $(INPUT) --build-docs --build-release --fair-check

test:
	$(PYTHON) -m pytest

clean:
	$(PYTHON) -c "from pathlib import Path; import shutil; [shutil.rmtree(p, ignore_errors=True) for p in [Path('output/release_bundle'), Path('.pytest_cache')]]"
