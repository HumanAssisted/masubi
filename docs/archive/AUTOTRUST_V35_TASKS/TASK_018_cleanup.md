# Task 018: Final Cleanup -- Full Test Suite, DRY Review, Dead Code Removal

## Context
This is the final cleanup task. After all features are implemented, we need to: run the full test suite and fix any failures, review for DRY violations across all modules, remove any dead code or unused imports, verify ruff linting passes, and ensure all modules are consistent with spec.yaml. This is the quality gate before the system is considered complete.

## Goal
Ensure the entire codebase is clean, tested, lint-free, and internally consistent.

## Research First
- [ ] Read ALL source files in `autotrust/` and project root
- [ ] Read ALL test files in `tests/`
- [ ] Run `uv run pytest -v` to see current test status
- [ ] Run `uv run ruff check .` to see current lint status

## TDD: Tests First (Red)
No new tests in this task. Fix any existing test failures.

## Implementation
- [ ] Step 1: Run full test suite: `uv run pytest -v --tb=short`
  - Fix any failing tests
  - Ensure no test depends on external services (all mocked)
- [ ] Step 2: Run ruff linter: `uv run ruff check .`
  - Fix all lint violations
  - Run `uv run ruff format .` for consistent formatting
- [ ] Step 3: DRY review across all modules:
  - Check config.py vs schemas.py: no overlapping model definitions
  - Check eval.py vs config.py: weight computation delegated correctly
  - Check providers/*.py: no duplicated retry/logging logic (should be in BaseProvider)
  - Check run_loop.py: no reimplemented eval logic (should delegate to eval.py)
  - Check train.py: no direct API client construction (should use providers)
- [ ] Step 4: Dead code removal:
  - Remove unused imports in all files
  - Remove any commented-out code
  - Remove any placeholder functions that were superseded
- [ ] Step 5: Consistency check:
  - All axis names in code match spec.yaml exactly
  - All threshold values reference spec (not hardcoded)
  - All provider roles use get_provider() factory
- [ ] Step 6: Final verification:
  - `uv run pytest -v` -- all tests pass
  - `uv run ruff check .` -- no violations
  - `uv run python -c "from autotrust.config import load_spec; s = load_spec(); print(f'{len(s.trust_axes)} axes loaded')"` -- prints "10 axes loaded"

## TDD: Tests Pass (Green)
- [ ] ALL tests pass (unit + integration + smoke)
- [ ] Zero ruff violations

## Acceptance Criteria
- [ ] Full test suite passes with 0 failures
- [ ] ruff check reports 0 violations
- [ ] No DRY violations found (or all fixed)
- [ ] No dead code remaining
- [ ] All modules consistent with spec.yaml
- [ ] Project is ready for first autoresearch run

## Execution
- **Agent Type**: python
- **Wave**: 8 (final wave, parallel with TASK_017)
- **Complexity**: Medium
