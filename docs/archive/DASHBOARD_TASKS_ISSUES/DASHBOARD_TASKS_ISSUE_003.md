# Issue 003: RunManager module-level import of run_loop creates tight coupling

## Severity
High

## Category
Quality

## Description
`run_manager.py` has `from run_loop import run_autoresearch` at module level (line 9). This means importing `autotrust.dashboard.run_manager` (or `autotrust.dashboard` via `__init__.py`) transitively imports the entire autoresearch stack: `autotrust.config`, `autotrust.eval`, `autotrust.observe`, `autotrust.schemas`, `structlog`, `anthropic`, `openai`, etc.

This violates the PRD's "Minimal invasion" principle (section 3.5) and "Dashboard is optional" principle (section 5.9). It means:
1. The dashboard cannot be imported or tested without the full autoresearch stack being importable.
2. If any required env var or file is missing, importing the dashboard fails.
3. The `dashboard` optional dependency group should not require the core dependencies.

## Evidence
- File: `autotrust/dashboard/run_manager.py:9` -- `from run_loop import run_autoresearch`
- File: `run_loop.py:20-38` -- imports autotrust.config, autotrust.eval, autotrust.observe, autotrust.schemas, structlog
- PRD Requirement: Section 3.5 -- "Minimal invasion"
- PRD Requirement: Section 5.9 -- "Dashboard is optional -- the core autoresearch loop does not require Gradio"

## Suggested Fix
Move the import inside `_run_wrapper()`:
```python
def _run_wrapper(self, max_experiments: int) -> None:
    try:
        from run_loop import run_autoresearch
        run_autoresearch(
            max_experiments=max_experiments,
            stop_check=self._stop_check,
            pause_check=self._pause_check,
        )
    except Exception:
        logger.exception("run_autoresearch failed")
    finally:
        if self._status != "idle":
            self._status = "idle"
```

## Affected Files
- `autotrust/dashboard/run_manager.py`

## Status: Fixed
Moved `from run_loop import run_autoresearch` from module-level to inside `_run_wrapper()`. The dashboard package can now be imported without the full autoresearch stack. Tests updated to patch `run_loop.run_autoresearch` instead of `autotrust.dashboard.run_manager.run_autoresearch`.
