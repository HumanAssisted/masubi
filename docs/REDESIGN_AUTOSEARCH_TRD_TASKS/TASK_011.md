# Task 011: README.md + setup.sh Updates

## Context
The REDESIGN_AUTOSEARCH_TRD adds Stage 2 (model training), Stage 3 (local inference), and new modules (`student.py`, `freeze.py`, `export.py`, `inference.py`). The existing `README.md` and `setup.sh` document only Stage 1. They need updates for:

- New dependencies (`torch`, optional `llama-cpp-python`)
- New CLI commands (`--stage train`, `autotrust.freeze`, `autotrust.export`)
- Updated architecture description (4-stage pipeline)
- Stage 2 quickstart
- Updated file layout showing new modules

## Goal
Update `README.md` and `setup.sh` to document the full 4-stage pipeline.

## Research First
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/README.md` (current content)
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/setup.sh` (current steps)
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/pyproject.toml` (current deps)
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/docs/REDESIGN_AUTOSEARCH.md` lines 155-200 (target file layout)
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/docs/REDESIGN_AUTOSEARCH.md` lines 389-411 (execution order)

## TDD: Tests First (Red)
No code tests for documentation changes, but verify:

### Validation Checks
- [ ] Verify: README.md mentions "Stage 2" or "model training"
- [ ] Verify: README.md mentions `freeze.py` or `autotrust.freeze`
- [ ] Verify: README.md mentions `export.py` or GGUF export
- [ ] Verify: setup.sh installs `torch` dependency
- [ ] Verify: pyproject.toml has `torch` in dependencies

## Implementation
- [ ] Step 1: Add `torch` to `pyproject.toml` main dependencies:
  ```toml
  dependencies = [
      ...
      "torch>=2.0",
  ]
  ```
- [ ] Step 2: Add `export` optional dependency group:
  ```toml
  [project.optional-dependencies]
  export = ["llama-cpp-python>=0.2"]
  ```
- [ ] Step 3: Update `setup.sh`:
  - Add PyTorch verification step
  - Add `teacher/` directory creation
  - Update verification section to check for new files
  - Add note about `--stage train` CLI option
- [ ] Step 4: Update `README.md` architecture section:
  - Add 4-stage pipeline description
  - Updated file layout with new modules
  - Stage 2 quickstart section
  - Export/deployment section
- [ ] Step 5: Update `README.md` quickstart:
  ```markdown
  ## Quick Start

  ### Stage 1: Prompt Optimization
  uv run python run_loop.py

  ### Stage 2: Model Training (after Stage 1 completes)
  uv run python run_loop.py --stage train

  ### Export Model
  uv run python -m autotrust.export --checkpoint runs/<id>/best.pt --format gguf
  ```
- [ ] DRY check: README.md references spec.yaml values by name, not duplicated literals

## TDD: Tests Pass (Green)
- [ ] All validation checks pass
- [ ] All existing tests still pass
- [ ] `setup.sh` runs without errors

## Acceptance Criteria
- [ ] README.md documents the full 4-stage pipeline
- [ ] README.md includes Stage 2 quickstart
- [ ] setup.sh installs new dependencies
- [ ] pyproject.toml has `torch` dependency
- [ ] File layout in README.md matches actual codebase
- [ ] No existing test is broken

## Execution
- **Agent Type**: coding subagent
- **Wave**: 5 (parallel with TASK_010; depends on Wave 4)
- **Complexity**: Low
