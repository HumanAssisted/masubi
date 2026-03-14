# Issue 008: DRY violation -- _is_kept() duplicated in charts.py and log_formatter.py

## Severity
Medium

## Category
DRY Violation

## Description
The `_is_kept()` helper function is implemented identically in two files:
- `autotrust/dashboard/charts.py:21-24`
- `autotrust/dashboard/log_formatter.py:6-9`

Both have the same logic: `bool(gate_results) and all(gate_results.values())`. This is a clear DRY violation that creates a maintenance burden -- if the kept/discarded logic changes, both files must be updated.

## Evidence
- File: `autotrust/dashboard/charts.py:21-24` -- `_is_kept()` implementation
- File: `autotrust/dashboard/log_formatter.py:6-9` -- identical `_is_kept()` implementation
- PRD Requirement: TASK_015 Step 3 -- "DRY review: Extract shared utilities (e.g., _is_kept() for checking gate_results) into a shared helper if duplicated"

## Suggested Fix
Extract `_is_kept()` into a shared utility module (e.g., `autotrust/dashboard/utils.py`) or into `__init__.py`:

```python
# autotrust/dashboard/utils.py
def is_kept(result: dict) -> bool:
    """Check if all gates passed (experiment was kept)."""
    gate_results = result.get("gate_results", {})
    return bool(gate_results) and all(gate_results.values())
```

Then import from both `charts.py` and `log_formatter.py`.

## Affected Files
- `autotrust/dashboard/charts.py`
- `autotrust/dashboard/log_formatter.py`
- `autotrust/dashboard/utils.py` (new)

## Status: Fixed
Extracted `is_kept()` into `autotrust/dashboard/utils.py`. Both `charts.py` and `log_formatter.py` now import `from autotrust.dashboard.utils import is_kept as _is_kept`. Added `utils` to `__init__.py` `__all__`.
