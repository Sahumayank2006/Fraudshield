.PHONY: help setup train-fast train demo test clean

PYTHON ?= python

help:
	@echo "FraudShield Automation Commands:"
	@echo "  make setup        Install all dependencies"
	@echo "  make train-fast   Run quick training pipeline (<3 min)"
	@echo "  make train        Run full production training pipeline"
	@echo "  make demo         Launch FastAPI server and serve Fraud Desk UI"
	@echo "  make test         Execute full pytest test suite"
	@echo "  make clean        Remove cache files"

setup:
	$(PYTHON) run.py setup

train-fast:
	$(PYTHON) run.py train-fast

train:
	$(PYTHON) run.py train

demo:
	$(PYTHON) run.py demo

test:
	$(PYTHON) run.py test

clean:
	$(PYTHON) -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]"
	$(PYTHON) -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('.pytest_cache')]"
