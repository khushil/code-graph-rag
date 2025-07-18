# Code Quality Quick Reference

## 🚀 Daily Commands

### Before Starting Work
```bash
make quality      # Run all checks
make test         # Ensure tests pass
```

### Before Committing
```bash
make fix          # Auto-fix issues
git commit        # Pre-commit runs automatically
```

### Quick Fixes
```bash
make format       # Fix formatting only
make lint         # Check linting only
make type-check   # Check types only
```

## 📊 Current Status & Targets

| Metric | Current | Sprint 1 | Sprint 3 | Sprint 6 |
|--------|---------|----------|----------|----------|
| Tests | 117/142 | 142/142 | 100% | 100% |
| Linting | 161 errors | 161 | 40 | 0 |
| Types | 377 errors | 300 | 100 | 0 |
| Coverage | ~82% | 83% | 86% | >90% |

## 🎯 Sprint Integration Summary

### Sprint 1 (Weeks 1-2): Foundation + Critical Fixes
- **Day 1**: Fix 25 failing tests
- **Week 1**: C parser + test fixes
- **Week 2**: Type annotations Phase 1

### Sprint 2 (Weeks 3-4): Advanced C + Linting
- **Day 4, Week 3**: Fix 40 linting issues
- **Day 5, Week 4**: Fix 40 more linting issues
- **Focus**: Pointer analysis + code cleanup

### Sprint 3 (Weeks 5-6): Testing + Type Safety
- **Day 3, Week 5**: Type annotation marathon
- **Day 4, Week 6**: Complete type fixes
- **Goal**: <100 type errors remaining

### Sprint 4 (Weeks 7-8): Performance + Zero Linting
- **Day 4, Week 7**: Refactor complex functions
- **Day 5, Week 8**: Achieve 0 linting errors
- **Focus**: Code optimization

### Sprint 5 (Weeks 9-10): Advanced + Type Perfection
- **Day 4, Week 9**: Fix final type errors
- **Day 3, Week 10**: Update documentation
- **Goal**: 0 type errors

### Sprint 6 (Weeks 11-12): Polish + Production
- **Day 4, Week 11**: CI/CD enhancements
- **Day 2, Week 12**: Quality dashboard
- **Goal**: Production certification

## ⚡ Common Fixes

### Linting Issues
```python
# PLR1714: Merge comparisons
# Bad
if x == "a" or x == "b":
# Good
if x in {"a", "b"}:

# ARG002: Remove unused arguments
# Add _ prefix or remove
def func(self, _unused_arg):
```

### Type Issues
```python
# Add return types
def func() -> None:
    pass

# Fix union types
from typing import Optional
value: Optional[str] = None

# Use Any correctly
from typing import Any
result: Any = complex_operation()
```

### Test Fixes
```bash
# Run specific failing test
uv run pytest codebase_rag/tests/test_file.py::test_name -v

# Debug with print
uv run pytest -s
```

## 📋 Quality Checklist

### Before Each Commit
- [ ] Tests pass (`make test`)
- [ ] No new linting errors (`make lint`)
- [ ] Types are annotated (new code)
- [ ] Pre-commit hooks pass

### End of Each Day
- [ ] Run `make quality`
- [ ] Fix any critical issues
- [ ] Update type hints for new code

### End of Each Sprint
- [ ] Meet sprint quality targets
- [ ] Update documentation
- [ ] Run coverage report
- [ ] Review quality metrics

## 🛠️ Useful Aliases

Add to your `.bashrc` or `.zshrc`:
```bash
alias mq='make quality'
alias mf='make fix'
alias mt='make test'
alias mc='make coverage'
```

## 📈 Progress Tracking

Weekly metrics update:
```bash
# Count current issues
make lint 2>&1 | grep "Found"
make type-check 2>&1 | grep "Found"
make test 2>&1 | grep "failed,"
```

## 🔥 Emergency Fixes

If builds are broken:
```bash
# Quick fix syntax errors
make fix

# Skip hooks temporarily (NOT RECOMMENDED)
git commit --no-verify -m "emergency: fixing build"

# Then immediately fix issues
make quality
```

Remember: **Quality is everyone's responsibility!**