# Makefile for poc-import development

.PHONY: help install test test-verbose lint format type-check clean run-example

help:  ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install package in editable mode with dev dependencies
	pip install -e ".[dev]"

test:  ## Run tests with coverage
	pytest

test-verbose:  ## Run tests with verbose output
	pytest -vv

lint:  ## Check code with ruff
	ruff check .

format:  ## Format code with ruff
	ruff format .

type-check:  ## Run type checking with mypy
	mypy poc_import

clean:  ## Clean build artifacts and cache files
	rm -rf build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage

run-example:  ## Run example import with test fixture (dry-run)
	poc-import msproject tests/fixtures/sample_project.xml \
		--mode=initial --token=dummy-token --dry-run --verbose
