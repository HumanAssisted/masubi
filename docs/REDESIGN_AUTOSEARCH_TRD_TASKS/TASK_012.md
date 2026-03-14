# Task 012: Full Test Suite, DRY Review, Dead Code Removal

## Context
This is the final cleanup task after all other REDESIGN_AUTOSEARCH_TRD tasks are complete. It ensures the codebase is clean, all tests pass, there is no duplicated logic, and no dead code remains from the refactoring.

## Goal
Run the full test suite, review for DRY violations, remove dead code, and verify the entire redesign is coherent.

## Research First
- [ ] Run `uv run pytest tests/ -v` -- collect all failures
- [ ] Read all new files created in Waves 1-5
- [ ] Search for duplicate patterns across modules
- [ ] Search for unused imports, unreachable code, orphaned functions

## TDD: Tests First (Red)
Not applicable (this task fixes existing tests, does not add new ones).

## Implementation

### Full Test Suite Verification
- [ ] Step 1: Run `uv run pytest tests/ -v` and fix any failures
- [ ] Step 2: Run `uv run pytest tests/ -v --tb=short` for all 20+ test files
- [ ] Step 3: Verify no test was weakened (all original assertions still present)

### DRY Review
- [ ] Step 4: Check for duplicate spec loading patterns across modules
  - `load_spec()` should be the single entry point; no module should parse spec.yaml directly
  - Grep for `yaml.safe_load.*spec` across all files
- [ ] Step 5: Check for duplicate trust vector validation
  - `validate_trust_vector()` in `schemas.py` should be the only validator
  - No other file should manually check axis names against spec
- [ ] Step 6: Check for duplicate metric computation
  - `score_predictions()` in `eval.py` should be the only place metrics are computed
  - No other file should call `f1_score()` or `cohen_kappa_score()` directly
- [ ] Step 7: Check for duplicate git operations
  - Git operations should use `_handle_keep_discard()` in `run_loop.py` or `git_history.py` utilities
  - No ad-hoc `subprocess.run(["git", ...])` calls in new modules
- [ ] Step 8: Check for duplicate model construction
  - `DenseStudent.from_config()` and `MoEStudent.from_config()` should be the only model constructors
  - `load_pytorch()` in `export.py` should be the only checkpoint loader

### Dead Code Removal
- [ ] Step 9: Search for unused imports in all `.py` files:
  ```
  ruff check --select F401 autotrust/ train.py run_loop.py dashboard.py
  ```
- [ ] Step 10: Search for unreachable code / unused functions:
  - Functions defined but never called
  - Classes defined but never instantiated
  - Variables assigned but never read
- [ ] Step 11: Check for orphaned test fixtures (fixtures defined but never used in tests)
- [ ] Step 12: Remove any `# TODO` or `# FIXME` markers that are now resolved

### Coherence Verification
- [ ] Step 13: Verify `spec.yaml` is self-consistent:
  - All `stage2` caps match values referenced in `program.md`
  - All axis names in `axis_groups` match `trust_axes`
  - Weights still sum to 1.0
- [ ] Step 14: Verify all new modules are importable:
  ```python
  from autotrust.student import DenseStudent, MoEStudent
  from autotrust.freeze import freeze_teacher
  from autotrust.export import export_pytorch, load_pytorch
  from autotrust.inference import LocalInference
  ```
- [ ] Step 15: Run `ruff check` on all files and fix any style issues

## TDD: Tests Pass (Green)
- [ ] `uv run pytest tests/ -v` -- all tests pass (0 failures)
- [ ] `ruff check autotrust/ train.py run_loop.py dashboard.py` -- no errors

## Acceptance Criteria
- [ ] All tests pass (original + new)
- [ ] No DRY violations found (or all fixed)
- [ ] No dead code remains
- [ ] No unused imports
- [ ] `ruff check` passes cleanly
- [ ] All new modules importable without errors
- [ ] spec.yaml is self-consistent

## Execution
- **Agent Type**: coding subagent
- **Wave**: 6 (final -- depends on all previous waves)
- **Complexity**: Medium
