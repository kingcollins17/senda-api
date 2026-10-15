VENV = .venv
PYTHON = $(VENV)/bin/python
UVICORN = $(VENV)/bin/uvicorn

.PHONY: help test test-verbose test-quote run dev install migrate clean

help:
	@echo "Available commands:"
	@echo "  make test          - Run all unit tests"
	@echo "  make test-verbose  - Run all unit tests with verbose output"
	@echo "  make test-quote    - Run quote service unit tests"
	@echo "  make dev           - Start FastAPI development server with auto-reload"
	@echo "  make migrate       - Apply database migrations"
	@echo "  make install       - Install dependencies from requirements.txt"
	@echo "  make clean         - Remove Python bytecode and cache files"

test:
	$(PYTHON) -m unittest discover tests

test-verbose:
	$(PYTHON) -m unittest discover tests -v

test-quote:
	$(PYTHON) -m unittest tests/test_quote_service.py -v

dev:
	$(UVICORN) app.main:app --reload --host 0.0.0.0 --port 8000

run: dev

migrate:
	$(VENV)/bin/alembic upgrade head

install:
	$(PYTHON) -m pip install -r requirements.txt

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
