# Issue 001: RunManager run_id does not match actual run's run_id -- polling never finds data

## Severity
Critical

## Category
Bug

## Description
`RunManager.start()` generates its own `run_id` using `datetime.now().strftime(...) + uuid.hex[:8]`, but never passes this run_id to `run_autoresearch()`. The actual `run_autoresearch()` function calls `start_run(spec)` internally, which generates a completely different `run_id` via `observe.start_run()`.

As a result, `RunManager.current_run_id` returns the dashboard-generated run_id, but the actual metrics are written to `runs/<real_run_id>/metrics.jsonl` by the observe module. When `poll_update()` in dashboard.py calls `data_loader.load_latest_metrics(run_id, ...)` using the dashboard's run_id, the file path `runs/<dashboard_run_id>/metrics.jsonl` does not exist. **The Live Run tab will never show any data from a running loop.**

## Evidence
- File: `autotrust/dashboard/run_manager.py:29` -- generates `run_id` locally
- File: `autotrust/dashboard/run_manager.py:91-95` -- calls `run_autoresearch()` without passing run_id
- File: `run_loop.py:244` -- `start_run(spec)` generates its own run_id
- File: `dashboard.py:91` -- `data_loader.load_latest_metrics(run_id, ...)` uses RunManager's run_id
- PRD Requirement: Section 4.1 -- "Real-time: gr.Timer(every=2) polls metrics.jsonl, updates all charts"

## Suggested Fix
Option A: Modify `run_autoresearch()` to accept an optional `run_id` parameter and pass it to `start_run()`. Then have `RunManager.start()` pass its generated `run_id`.

Option B: Have `RunManager._run_wrapper()` detect the actual run_id from the observe module (e.g., by checking `runs/` directory for newly created subdirectories after launch) and update `self._current_run_id`.

Option C: After `run_autoresearch()` starts, scan `runs/` for the most recently created directory and set `self._current_run_id` to that.

## Affected Files
- `autotrust/dashboard/run_manager.py`
- `run_loop.py`
- `dashboard.py`

## Status: Fixed
Removed the dashboard-generated run_id. RunManager now detects the actual run_id by scanning the `runs/` directory for newly created subdirectories after `run_autoresearch()` starts. The `_detect_run_id()` method compares pre-launch directory listing against current state and picks the newest new directory. Added `test_exception_sets_error_status` and `test_stop_race_condition_thread_still_alive` tests.
