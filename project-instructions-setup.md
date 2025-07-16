# Project Instructions Setup Guide

## For Claude Code Custom Instructions

Copy the following into Claude Code's custom instructions field when starting your session:

---

### Custom Instructions for Graph-Code RAG Enhancement

You are enhancing the Graph-Code RAG system in an already cloned repository. ENSURE you read and understand CLAUDE.md and PLANNING.md and Follow these critical practices:

**Git Discipline:**
- NEVER commit to main branch directly
- Create feature branches: `feature/descriptive-name`
- Commit format: `type(scope): subject` with REQ-IDs
- Run tests before every commit
- Include tests in the same commit as features

**Development Practices:**
- Reference SRS requirements (REQ-XXX-N) in all work
- Write tests FIRST, then implementation
- Handle million-line codebases efficiently (use generators)
- Maintain backward compatibility always
- Document with docstrings and examples
- Handle errors gracefully with logging
- Validate all inputs for security

**Before Every Commit:**
- Run pytest
- Run flake8
- Verify requirement tracing
- Check memory efficiency
- Ensure error handling

Remember: This is production-quality code for massive codebases. Every decision should consider scale, security, and reliability.

---

## What Stays in CLAUDE.md

CLAUDE.md remains your technical reference containing:
- Detailed implementation plans
- Code structure and architecture
- Specific technical requirements
- API documentation
- Complex examples and patterns

## How to Use Both Together

1. **Start Claude Code** with the custom instructions above
2. **Keep CLAUDE.md open** in your editor for reference
3. **Custom instructions** = What to always remember
4. **CLAUDE.md** = What to look up when needed

## Quick Reference Card

| Topic | Custom Instructions | CLAUDE.md |
|-------|-------------------|-----------|
| Git commit format | ✓ "Always use type(scope)" | Full examples & types |
| Test-first approach | ✓ "Write tests first" | Testing strategies |
| Memory efficiency | ✓ "Use generators" | Optimization patterns |
| Requirements | ✓ "Reference REQ-IDs" | Full requirements list |
| Error handling | ✓ "Handle gracefully" | Error handling patterns |
| C parsing details | Basic reminder | Full implementation guide |
| Graph schema | Basic principles | Complete schema docs |