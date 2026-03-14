# Issue 010: Log entry format missing experiment number (Exp #N)

## Severity
Medium

## Category
Omission

## Description
The PRD section 4.1 specifies the log entry format as:
```
[14:23:07] Exp #3  composite=0.724 (+0.031)  KEPT  gates: ...  $0.03
```

The implementation in `format_experiment_log_entry()` produces:
```
[00:03:00]  composite=0.724 (+0.031)  KEPT  gates: ...  $0.03
```

The `Exp #N` label is missing. This makes it harder for the researcher to identify which experiment they're looking at, especially in a long log stream.

The root cause is that `ExperimentResult` does not have an `experiment_num` field, and `format_experiment_log_entry()` does not receive the experiment index.

## Evidence
- File: `autotrust/dashboard/log_formatter.py:55` -- output format lacks "Exp #N"
- File: `autotrust/dashboard/log_formatter.py:31` -- function signature has no experiment number parameter
- PRD Requirement: Section 4.1 Row 3 -- "[14:23:07] Exp #3  composite=0.724 (+0.031)  KEPT"

## Suggested Fix
Add an `experiment_num` parameter to `format_experiment_log_entry()`:
```python
def format_experiment_log_entry(result: dict, prev_composite: float | None, experiment_num: int | None = None) -> str:
```
And update `format_log_stream()` to pass `i + 1` as the experiment number.

## Affected Files
- `autotrust/dashboard/log_formatter.py`

## Status: Fixed
Added `experiment_num: int | None = None` parameter to `format_experiment_log_entry()`. When provided, prepends "Exp #N" label. `format_log_stream()` now passes `i + 1` as the experiment number. Updated `test_format_log_entry_kept` to verify "Exp #3" appears.
