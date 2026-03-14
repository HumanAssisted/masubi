# Task 001: Project Scaffold

## Context
AutoEmailTrust v3.5 is a greenfield Python project. Before any code can be written, we need the foundational project files: `pyproject.toml` for dependency management (uv, Python 3.12), `.env.example` for credentials, `.gitignore` for exclusions, and the directory skeleton. This task creates the scaffold that all subsequent tasks depend on. See CURSOR_PLAN.md "Implementation Details > 1. Scaffold" and "File Layout".

## Goal
Create a buildable Python project scaffold with all required directories and configuration files so that `uv sync` succeeds.

## Research First
- [ ] Read CURSOR_PLAN.md sections: "File Layout", "Implementation Details > 1. Scaffold"
- [ ] Verify uv is available on PATH (`uv --version`)
- [ ] Confirm Python 3.12 is available

## TDD: Tests First (Red)
No tests for this task (it's pure configuration/scaffold). Verification is that `uv sync` succeeds.

## Implementation
- [ ] Step 1: Create `pyproject.toml` at project root with:
  - `[project]` section: name="autotrust", python=">=3.12"
  - Dependencies: `anthropic`, `openai`, `ollama`, `python-dotenv`, `pydantic`, `pyyaml`, `gitpython`, `httpx`, `rich`, `structlog`, `datasets`, `scikit-learn`
  - Dev dependencies: `pytest`, `ruff`
  - Package source: `autotrust/`
- [ ] Step 2: Create `.env.example` with:
  ```
  ANTHROPIC_API_KEY=
  HYPERBOLIC_API_KEY=
  OLLAMA_MODEL=dolphin3:latest
  ```
- [ ] Step 3: Create `.gitignore` with: `.env`, `synth_data/*.jsonl`, `runs/`, `__pycache__/`, `.venv/`, `*.pyc`, `.ruff_cache/`
- [ ] Step 4: Create directory skeleton:
  - `autotrust/__init__.py` (empty)
  - `autotrust/providers/__init__.py` (empty placeholder)
  - `gold_set/.gitkeep`
  - `eval_set/.gitkeep`
  - `synth_data/.gitkeep`
  - `runs/.gitkeep`
  - `tests/__init__.py` (empty)
- [ ] Step 5: Run `uv sync` to verify installation succeeds

## TDD: Tests Pass (Green)
- [ ] `uv sync` completes without error
- [ ] `uv run python -c "import autotrust"` succeeds

## Acceptance Criteria
- [ ] `pyproject.toml` exists with all listed dependencies
- [ ] `.env.example` exists with all three keys
- [ ] `.gitignore` excludes `.env`, `runs/`, `synth_data/*.jsonl`, `__pycache__/`, `.venv/`
- [ ] All directories in the file layout exist with `.gitkeep` or `__init__.py`
- [ ] `uv sync` succeeds
- [ ] `uv run python -c "import autotrust"` succeeds

## Execution
- **Agent Type**: python
- **Wave**: 1
- **Complexity**: Low
