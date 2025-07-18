#!/bin/bash
# Script to run all code quality checks before committing

set -e  # Exit on error

echo "🚀 Running code quality checks..."
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to run a check
run_check() {
    local name=$1
    local command=$2
    
    echo -n "Running $name... "
    if eval "$command" > /tmp/check_output.txt 2>&1; then
        echo -e "${GREEN}✓ Passed${NC}"
        return 0
    else
        echo -e "${RED}✗ Failed${NC}"
        echo -e "${YELLOW}Output:${NC}"
        cat /tmp/check_output.txt
        return 1
    fi
}

# Track overall status
overall_status=0

# Run checks
run_check "Ruff linting" "uv run ruff check codebase_rag/" || overall_status=1
run_check "Ruff formatting" "uv run ruff format --check codebase_rag/" || overall_status=1
run_check "MyPy type checking" "uv run mypy codebase_rag/" || overall_status=1

# Summary
echo ""
if [ $overall_status -eq 0 ]; then
    echo -e "${GREEN}✅ All checks passed!${NC}"
    echo ""
    echo "You can now commit your changes with confidence! 🎉"
else
    echo -e "${RED}❌ Some checks failed!${NC}"
    echo ""
    echo "To fix formatting issues automatically, run:"
    echo "  make fix"
    echo ""
    echo "For other issues, please fix them manually."
    exit 1
fi