.PHONY: help install install-dev test test-unit test-integration test-cov lint format type-check clean

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install the package
	pip install -e .

install-dev: ## Install the package with development dependencies
	pip install -e ".[dev,test]"

test: ## Run all tests
	pytest

test-unit: ## Run unit tests only (exclude integration tests)
	pytest -m "not integration and not slow"

test-integration: ## Run integration tests (requires network)
	pytest -m "integration or slow"

test-cov: ## Run tests with coverage report
	pytest --cov=src/compoid_mcp --cov-report=term-missing --cov-report=html

test-watch: ## Run tests in watch mode
	pytest -f

lint: ## Run linting checks
	ruff check src/ tests/
	black --check src/ tests/

format: ## Format code
	black src/ tests/
	ruff check --fix src/ tests/

type-check: ## Run type checking
	mypy src/

clean: ## Clean up generated files
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/
	rm -rf src/*.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

ci: lint type-check test-unit ## Run CI checks (linting, type checking, unit tests)

all: clean install-dev lint type-check test ## Run all checks and tests

# Development helpers
run-server: ## Run the MCP server
	python -m src.compoid_mcp.server

example: ## Run the example usage script
	python example_usage.py

# Docker commands (if needed)
docker-build: ## Build Docker image
	docker build -t compoid-mcp .

docker-run: ## Run Docker container
	docker run -it --rm compoid-mcp
