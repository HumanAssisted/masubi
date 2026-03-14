# Issue 011: RunManager.stop() race condition -- status set to idle before thread exits

## Severity
Medium

## Category
Bug

## Description
`RunManager.stop()` calls `self._thread.join(timeout=5.0)` and then unconditionally sets `self._status = "idle"` and `self._thread = None`. If the background thread hasn't finished within 5 seconds (e.g., because a scoring API call is in progress), the status becomes "idle" but the thread is still running.

This creates a race condition:
1. User clicks Stop, status shows "idle"
2. User clicks Start (allowed because status is "idle"), launching a new thread
3. Now two threads are running `run_autoresearch` simultaneously, potentially writing to the same files

## Evidence
- File: `autotrust/dashboard/run_manager.py:55-58` -- `join(timeout=5.0)` then unconditional `self._status = "idle"`
- PRD Requirement: Section 5.3 -- "Signal graceful stop after current experiment"
- PRD Requirement: Section 8 Out of Scope -- "Multiple concurrent runs -- single run at a time for v1"

## Suggested Fix
Check if the thread is still alive after join:
```python
def stop(self) -> None:
    if self._status not in ("running", "paused"):
        return
    self._status = "stopping"
    self._stop_event.set()
    self._pause_event.set()

    if self._thread is not None:
        self._thread.join(timeout=30.0)
        if self._thread.is_alive():
            logger.warning("Background thread did not exit within timeout")
            # Don't set idle -- still running
            return
    self._status = "idle"
    self._thread = None
```

## Affected Files
- `autotrust/dashboard/run_manager.py`

## Status: Fixed
`stop()` now uses `join(timeout=30.0)` and checks `self._thread.is_alive()` after join. If the thread is still alive, the method returns early without setting status to "idle", preventing the race condition where a new run could be started while the old one is still running. Added `test_stop_race_condition_thread_still_alive` test.
