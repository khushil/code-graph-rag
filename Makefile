.PHONY: help install dev test clean python lint format type-check quality fix pre-commit-all pre-commit-update coverage

help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install project dependencies with full language support
	uv sync --extra treesitter-full

python: ## Install project dependencies for Python only
	uv sync

dev: ## Setup development environment (install deps + pre-commit hooks)
	uv sync --extra treesitter-full --extra dev --extra test
	uv run pre-commit install
	uv run pre-commit install --hook-type commit-msg
	@echo "✅ Development environment ready!"

test: ## Run tests
	uv run pytest

clean: ## Clean up build artifacts and cache
	rm -rf .pytest_cache/ .mypy_cache/ .ruff_cache/ htmlcov/ .coverage coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -name "*.pyc" -delete

lint: ## Run linting with ruff
	@echo "🔍 Running ruff linter..."
	uv run ruff check codebase_rag/

format: ## Format code with ruff
	@echo "✨ Formatting code with ruff..."
	uv run ruff format codebase_rag/

type-check: ## Run type checking with mypy
	@echo "🔎 Running mypy type checker..."
	uv run mypy codebase_rag/

quality: lint type-check ## Run all quality checks
	@echo "✅ All quality checks passed!"

fix: ## Auto-fix linting issues and format code
	@echo "🔧 Auto-fixing code issues..."
	uv run ruff check --fix codebase_rag/
	uv run ruff format codebase_rag/
	@echo "✅ Code fixed and formatted!"

pre-commit-all: ## Run pre-commit on all files
	@echo "🚀 Running pre-commit on all files..."
	uv run pre-commit run --all-files

pre-commit-update: ## Update pre-commit hooks
	@echo "🔄 Updating pre-commit hooks..."
	uv run pre-commit autoupdate

coverage: ## Run tests with coverage report
	@echo "📊 Running tests with coverage..."
	uv run pytest --cov=codebase_rag --cov-report=term-missing --cov-report=html
	@echo "📈 Coverage report generated at htmlcov/index.html"
