# Task 017: Update README.md and Final Documentation

## Context
The README.md currently only contains placeholder text. It needs to be updated with project overview, setup instructions, architecture summary, and usage guide. This is the final task after all code is written and tested. See CURSOR_PLAN.md "Execution Order > 15. Update README.md".

## Goal
Create clear, concise project documentation in README.md that enables a new developer to understand, set up, and run the system.

## Research First
- [ ] Read all implemented source files to understand final architecture
- [ ] Read `spec.yaml` for configuration reference
- [ ] Read `program.md` for agent instruction reference
- [ ] Verify all commands work: `uv sync`, `uv run python -m autotrust.data --help`, `uv run pytest`

## TDD: Tests First (Red)
No code tests (documentation only).

## Implementation
- [ ] Step 1: Update `README.md` at project root with:

  **Section 1: Project Title + One-line Description**
  - "AutoEmailTrust v3.5: Automated email trust scoring research loop"

  **Section 2: Architecture Overview**
  - 3-layer architecture: Spec/Config, Fixed Platform, Mutable Model
  - Diagram reference (link to CURSOR_PLAN.md mermaid diagram)
  - Three-gate keep/discard policy summary

  **Section 3: Quick Start**
  - Prerequisites: Python 3.12, uv, Ollama (optional for local gen)
  - `uv sync`
  - Copy `.env.example` to `.env`, fill in API keys
  - Generate data: `uv run python -m autotrust.data build-eval`
  - Run research loop: `uv run python run_loop.py`

  **Section 4: Configuration**
  - `spec.yaml` is the single source of truth
  - Key sections: trust_axes, providers, limits, judge, calibration, explanation

  **Section 5: Development**
  - Run tests: `uv run pytest`
  - Lint: `uv run ruff check .`
  - Format: `uv run ruff format .`

  **Section 6: File Structure**
  - Brief description of each file/module

## TDD: Tests Pass (Green)
- [ ] README content is accurate and complete

## Acceptance Criteria
- [ ] `README.md` updated with comprehensive content
- [ ] Quick start instructions are accurate and testable
- [ ] Architecture overview matches implementation
- [ ] All commands in README actually work

## Execution
- **Agent Type**: python (documentation)
- **Wave**: 8 (final wave, depends on everything)
- **Complexity**: Low
