# Makefile - run tests with PYTHONPATH set so Python finds top-level packages
.PHONY: install test test-integration lint clean show-py

PY := $(shell pwd)
PYTHON := python

# Directories to add to PYTHONPATH: repo root and the typical module dirs
# Add more directories here if you have other top-level folders with python modules.
PYPATH := $(PY):$(PY)/backend:$(PY)/middle:$(PY)/frontend:$(PY)/runtime:$(PY)/util:$(PY)/tests

export PYTHONPATH := $(PYPATH)

install:
	$(PYTHON) -m pip install --upgrade pip
	pip install -r requirements-dev.txt

test:
	@echo "PYTHONPATH=$(PYTHONPATH)"
	# Run unit tests only (non-integration)
	$(PYTHON) -m pytest -q -m "not integration"

test-integration:
	@echo "PYTHONPATH=$(PYTHONPATH)"
	# Run integration tests only
	$(PYTHON) -m pytest -q -m integration

all-tests:
	@echo "PYTHONPATH=$(PYTHONPATH)"
	$(PYTHON) -m pytest -q

lint:
	# add your linter command here (ruff/flake8/black)
	@echo "No linter configured."

clean:
	find . -type d -name "__pycache__" -print0 | xargs -0 rm -rf || true
	rm -rf .pytest_cache || true

show-py:
	@echo "PYTHONPATH = $(PYTHONPATH)"
