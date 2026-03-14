# Task 001: Dashboard Scaffold & Dependencies

## Context
The Gradio Dashboard is an optional add-on for monitoring the autoresearch loop. It requires its own package directory (`autotrust/dashboard/`) and optional dependencies (gradio, plotly, pandas). The dashboard must not affect the core autoresearch loop -- `gradio` is an optional dependency, and the existing code must continue to work without it. See GRADIO_DASHBOARD_PRD.md sections 5.1 (Architecture) and 5.9 (Dependencies).

## Goal
Create the dashboard package skeleton and add optional dependencies so that `uv sync --extra dashboard` installs Gradio/Plotly/Pandas and `uv run python -c "from autotrust.dashboard import *"` succeeds.

## Research First
- [x] Read GRADIO_DASHBOARD_PRD.md section 5.1 (Architecture) for the file layout
- [x] Read GRADIO_DASHBOARD_PRD.md section 5.9 (Dependencies) for required packages
- [x] Read `pyproject.toml` to understand current dependency structure
- [x] Verify `autotrust/__init__.py` exists

## TDD: Tests First (Red)
No unit tests for this task (it is pure configuration/scaffold). Verification is that imports succeed.

## Implementation
- [x] Step 1: Add `[project.optional-dependencies]` entry for dashboard in `pyproject.toml`
- [x] Step 2: Create the dashboard package skeleton
- [x] Step 3: Create `dashboard.py` at project root
- [x] Step 4: Run `uv sync --extra dashboard` to verify installation succeeds
- [x] Step 5: Run imports to verify

## Review Notes
- Installed gradio 6.9.0, plotly 6.6.0, pandas via uv sync --extra dashboard
- All 103 existing tests pass
- All dashboard module imports succeed

## TDD: Tests Pass (Green)
- [ ] `uv sync --extra dashboard` completes without error
- [ ] `uv run python -c "from autotrust.dashboard import data_loader"` succeeds
- [ ] All 103 existing tests still pass

## Acceptance Criteria
- [ ] `pyproject.toml` has `dashboard` optional dependency group with gradio, plotly, pandas
- [ ] `autotrust/dashboard/__init__.py` exists
- [ ] All 5 submodule placeholder files exist under `autotrust/dashboard/`
- [ ] `dashboard.py` exists at project root
- [ ] `uv sync --extra dashboard` succeeds
- [ ] All existing tests pass unchanged

## Execution
- **Agent Type**: infra-sre-architect
- **Wave**: 1
- **Complexity**: Low
