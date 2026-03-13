PYTHON ?= python
CLI = $(PYTHON) -m aimworks_ontology_release.cli
PROFILE ?= pemfc

.PHONY: install profiles inspect split map enrich annotate docs docs-all validate fair release release-all run test clean

install:
	$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) -m pip install -e .

profiles:
	$(CLI) profiles

inspect:
	$(CLI) inspect --profile $(PROFILE)

split:
	$(CLI) split --profile $(PROFILE)

map:
	$(CLI) map --profile $(PROFILE)

enrich:
	$(CLI) enrich --profile $(PROFILE)

annotate:
	$(CLI) annotate --profile $(PROFILE)

docs:
	$(CLI) docs --profile $(PROFILE)

docs-all:
	$(CLI) docs-all

validate:
	$(CLI) validate --profile $(PROFILE)

fair:
	$(CLI) fair --profile $(PROFILE)

release:
	$(CLI) release --profile $(PROFILE)

release-all:
	$(CLI) release-all

run:
	$(CLI) run --all-profiles --build-docs --build-release --fair-check

test:
	$(PYTHON) -m pytest

clean:
	$(PYTHON) -c "from pathlib import Path; import shutil; [shutil.rmtree(p, ignore_errors=True) for p in [Path('output/release_bundle'), Path('.pytest_cache')]]"
