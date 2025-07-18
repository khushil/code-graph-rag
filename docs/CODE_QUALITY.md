# Code Quality Guide

This document describes the code quality tools and practices used in the Graph-Code RAG project.

## Overview

We use a comprehensive set of tools to ensure code quality:
- **Ruff**: Fast Python linter and formatter (replaces Black, isort, flake8, and more)
- **MyPy**: Static type checker for Python
- **Pre-commit**: Git hooks for automatic code quality checks
- **pytest + coverage**: Testing framework with coverage reporting

## Quick Start

### Initial Setup
```bash
# Install development dependencies
make dev

# Run all quality checks
make quality

# Fix issues automatically
make fix
```

### Before Committing
```bash
# Run pre-commit on all files
make pre-commit-all

# Or just run on staged files (automatic with git commit)
git commit -m "feat: your feature"
```

## Available Commands

### Makefile Targets
- `make lint` - Run Ruff linting
- `make format` - Format code with Ruff
- `make type-check` - Run MyPy type checking
- `make quality` - Run all quality checks
- `make fix` - Auto-fix linting issues and format
- `make test` - Run tests
- `make coverage` - Run tests with coverage report
- `make pre-commit-all` - Run pre-commit on all files
- `make pre-commit-update` - Update pre-commit hooks

### Manual Commands
```bash
# Run specific quality check script
./scripts/check-code-quality.sh

# Run pre-commit manually
uv run pre-commit run --all-files

# Run specific hooks
uv run pre-commit run ruff --all-files
uv run pre-commit run mypy --all-files
```

## Configuration Files

### `.editorconfig`
Ensures consistent coding styles across different editors:
- UTF-8 encoding
- LF line endings
- Trailing whitespace removal
- Final newline insertion
- Language-specific indentation

### `pyproject.toml`
Contains configuration for:
- **Ruff**: Linting and formatting rules
- **MyPy**: Type checking settings
- **pytest**: Test discovery and coverage
- **Coverage**: Coverage reporting settings

### `.pre-commit-config.yaml`
Defines git hooks that run automatically:
- Whitespace and file fixes
- Code formatting and linting
- Type checking
- Security scanning (Bandit)
- Commit message validation
- Large file prevention

### `.ruff.toml`
Additional Ruff configuration:
- Per-file rule ignores
- Import sorting settings
- Type checking strictness

## Type Hints

We use Python type hints throughout the codebase:

```python
from typing import Optional, List, Dict, Union

def process_data(
    input_data: List[Dict[str, Any]], 
    config: Optional[Config] = None
) -> ProcessResult:
    """Process input data with optional configuration."""
    ...
```

### Type Checking Rules
- All functions must have type hints
- Use `Optional[T]` instead of `T | None` for clarity
- Prefer specific types over `Any`
- Use `typing.Protocol` for structural subtyping
- Enable strict mode in MyPy

## Code Style

### Python Style Guide
- Line length: 88 characters (Black-compatible)
- Double quotes for strings
- 4 spaces for indentation
- Descriptive variable names
- Docstrings for all public functions

### Import Organization
Imports are automatically sorted by Ruff:
1. Standard library imports
2. Third-party imports
3. Local application imports

### Error Handling
```python
# Good
try:
    result = risky_operation()
except SpecificError as e:
    logger.error(f"Operation failed: {e}")
    raise

# Avoid bare except
except:  # This will be flagged by linting
    pass
```

## Pre-commit Hooks

### Standard Hooks
- `trailing-whitespace`: Remove trailing whitespace
- `end-of-file-fixer`: Ensure files end with newline
- `check-yaml/toml/json`: Validate configuration files
- `check-added-large-files`: Prevent large files (>1MB)
- `detect-private-key`: Prevent committing secrets

### Code Quality Hooks
- `ruff`: Linting with auto-fix
- `ruff-format`: Code formatting
- `mypy`: Type checking
- `bandit`: Security scanning

### Custom Hooks
- `no-print-statements`: Prevent print() in production code

## Testing Standards

### Test Organization
```
codebase_rag/tests/
├── conftest.py          # Shared fixtures
├── fixtures/            # Test data
├── test_*.py           # Test modules
└── integration/        # Integration tests
```

### Test Coverage
- Minimum coverage: 80%
- Exclude test files and `__init__.py` from coverage
- Use `# pragma: no cover` sparingly

### Running Tests
```bash
# Run all tests
make test

# Run with coverage
make coverage

# Run specific test
uv run pytest codebase_rag/tests/test_specific.py -v

# Run tests matching pattern
uv run pytest -k "test_data_flow" -v
```

## IDE Integration

### VS Code
The `.vscode/settings.json` file configures:
- Ruff as the default formatter
- Format on save
- Type checking mode: strict
- pytest integration
- File associations

### Other IDEs
- **PyCharm**: Import `.editorconfig` and configure Ruff
- **Vim/Neovim**: Use `ale` or `coc.nvim` with Ruff
- **Emacs**: Use `lsp-mode` with `pylsp-ruff`

## CI/CD Integration

GitHub Actions workflows enforce quality:
- **pre-commit.yml**: Runs all pre-commit hooks
- **tests.yml**: Runs tests on multiple OS/Python versions
- **Coverage**: Uploads to Codecov

## Common Issues and Solutions

### Issue: Import sorting conflicts
**Solution**: Let Ruff handle all import sorting
```bash
make fix
```

### Issue: Type checking fails on third-party imports
**Solution**: Install type stubs
```bash
uv pip install types-package-name
```

### Issue: Pre-commit hooks fail
**Solution**: Update and reinstall hooks
```bash
make pre-commit-update
uv run pre-commit install --install-hooks
```

### Issue: Coverage below threshold
**Solution**: Add tests or mark untestable code
```python
if TYPE_CHECKING:  # pragma: no cover
    from typing import SomeType
```

## Best Practices

1. **Run quality checks before pushing**
   ```bash
   make quality
   ```

2. **Fix issues immediately**
   - Don't commit code with linting errors
   - Address type checking issues
   - Maintain test coverage

3. **Use type hints consistently**
   - Add types to all new functions
   - Update types when modifying code

4. **Write tests for new features**
   - Unit tests for individual functions
   - Integration tests for workflows

5. **Keep dependencies updated**
   ```bash
   make pre-commit-update
   ```

## Additional Resources

- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [MyPy Documentation](https://mypy.readthedocs.io/)
- [Pre-commit Documentation](https://pre-commit.com/)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)