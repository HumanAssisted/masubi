# Task 015: Final Cleanup -- Full Test Suite, DRY Review, Dead Code Removal

## Context
After all dashboard modules and tabs are implemented (TASK_001 through TASK_014), this final task runs the full test suite, checks for code duplication across dashboard modules, removes any dead code or unused imports, ensures consistent error handling, and verifies the complete end-to-end workflow. See GRADIO_DASHBOARD_PRD.md section 6 (Test Strategy).

## Goal
Ensure all tests pass, eliminate duplication, remove dead code, and verify the dashboard works end-to-end.

## Research First
- [ ] Read all files in `autotrust/dashboard/` for duplication patterns
- [ ] Read `dashboard.py` for unused imports or dead code
- [ ] Read all `tests/test_*.py` files related to the dashboard
- [ ] Run `ruff check autotrust/dashboard/ dashboard.py` for lint issues
- [ ] Run the full test suite: `uv run pytest tests/ -v`

## TDD: Tests First (Red)
No new tests for this task. This is a review/cleanup task.

## Implementation
- [ ] Step 1: Run full test suite and fix any failures:
  ```bash
  uv run pytest tests/ -v --tb=short
  ```
- [ ] Step 2: Run ruff on all dashboard code:
  ```bash
  uv run ruff check autotrust/dashboard/ dashboard.py --fix
  uv run ruff format autotrust/dashboard/ dashboard.py
  ```
- [ ] Step 3: DRY review across dashboard modules:
  - Check for duplicated helper functions across charts.py, log_formatter.py, data_loader.py
  - Extract shared utilities (e.g., `_is_kept()` for checking gate_results) into a shared helper if duplicated
  - Ensure chart builders share common patterns (empty figure handling, color constants)
- [ ] Step 4: Remove dead code:
  - Unused imports in all dashboard files
  - Placeholder functions that were never filled in
  - Debug/print statements
- [ ] Step 5: Verify error handling consistency:
  - All data_loader functions handle missing files gracefully
  - All chart builders handle empty data without crashing
  - All git_history functions handle subprocess failures
  - RunManager handles thread lifecycle edge cases
- [ ] Step 6: End-to-end verification:
  - Start dashboard: `uv run python dashboard.py`
  - Verify all 6 tabs render
  - Verify timer updates work with no active run (no crash)
  - If possible, start a mock run and verify charts update
- [ ] Step 7: Verify all 103+ existing tests still pass:
  ```bash
  uv run pytest tests/ -v
  ```
- [ ] Step 8: Update `__init__.py` exports if needed:
  - `autotrust/dashboard/__init__.py` should export key classes/functions for convenience

## TDD: Tests Pass (Green)
- [ ] All existing tests pass
- [ ] All new dashboard tests pass
- [ ] Zero ruff warnings/errors
- [ ] No dead code remaining

## Acceptance Criteria
- [ ] Full test suite passes (existing + new dashboard tests)
- [ ] ruff check passes with zero warnings
- [ ] No duplicated logic across dashboard modules
- [ ] No unused imports or dead code
- [ ] All error paths handle gracefully (no uncaught exceptions)
- [ ] Dashboard launches and all 6 tabs render
- [ ] Timer updates work when no run is active (empty state)
- [ ] `autotrust/dashboard/__init__.py` has clean exports

## Execution
- **Agent Type**: python-expert
- **Wave**: 6 (final -- depends on all previous tasks)
- **Complexity**: Medium
