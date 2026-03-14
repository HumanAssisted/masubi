# Issue 016: list_runs does not detect currently-running runs

## Severity
Low

## Category
Omission

## Description
`data_loader.list_runs()` sets `status = "completed"` when `summary.txt` exists, and `status = "unknown"` otherwise. A currently-running run will have a `metrics.jsonl` being actively written but no `summary.txt` (since `finalize_run()` writes it at the end). Such a run will show as status "unknown" in the Run History tab instead of "running".

## Evidence
- File: `autotrust/dashboard/data_loader.py:66` -- `info["status"] = "completed"` only when summary.txt exists
- File: `autotrust/dashboard/data_loader.py:34` -- default status is "unknown"
- PRD Requirement: Section 4.4 -- "Run list -- table showing: run_id, date, experiment count, best composite, total cost, status (completed/stopped/running)"

## Suggested Fix
Add logic to detect running status: if `metrics.jsonl` exists but `summary.txt` does not, set status to "running". Also consider checking if the RunManager has a current_run_id that matches.

## Affected Files
- `autotrust/dashboard/data_loader.py`

## Status: Fixed
Added `elif metrics_path.exists(): info["status"] = "running"` in `list_runs()`. Runs with `metrics.jsonl` but no `summary.txt` now show as "running" instead of "unknown". Added `test_list_runs_detects_running_status` test.
