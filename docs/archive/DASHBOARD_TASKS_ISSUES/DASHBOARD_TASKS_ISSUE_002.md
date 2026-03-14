# Issue 002: RunManager silently swallows all exceptions from run_autoresearch

## Severity
High

## Category
Bug

## Description
In `RunManager._run_wrapper()`, the entire `run_autoresearch()` call is wrapped in `except Exception: pass`. This means if the research loop crashes due to an OOM error, a missing API key, a broken spec.yaml, a missing module, or any other exception, the error is silently discarded. The dashboard will simply show status "idle" with no indication that anything went wrong.

This makes debugging impossible -- the researcher has no way to know why the loop stopped, whether it completed successfully, or whether it crashed.

## Evidence
- File: `autotrust/dashboard/run_manager.py:96-97` -- `except Exception: pass`
- PRD Requirement: Section 4.1 Row 0 -- "status indicator" should communicate run state

## Suggested Fix
1. Log the exception with `logger.exception("run_autoresearch crashed")` instead of `pass`.
2. Store the exception on the RunManager instance (e.g., `self._last_error = exc`) so the dashboard can display it.
3. Set status to "error" or "crashed" instead of "idle" so the UI can show the failure.

```python
def _run_wrapper(self, max_experiments: int) -> None:
    try:
        run_autoresearch(...)
    except Exception:
        logger.exception("run_autoresearch crashed")
        self._status = "error"
    finally:
        if self._status not in ("idle", "error"):
            self._status = "idle"
```

## Affected Files
- `autotrust/dashboard/run_manager.py`

## Status: Fixed
`_run_wrapper()` now logs exceptions via `logger.exception()`, stores the exception in `self._last_error`, and sets `self._status = "error"`. The dashboard's `poll_update()` displays the error message in the status indicator. Added `test_exception_sets_error_status` test.
