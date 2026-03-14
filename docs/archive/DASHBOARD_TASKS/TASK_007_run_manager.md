# Task 007: Build run_manager.py -- Thread Management for Start/Stop/Pause

## Context
`run_manager.py` manages the autoresearch loop (`run_autoresearch()`) in a background thread so the Gradio dashboard can launch, stop, and pause the loop from the browser. It uses `threading.Event` for stop/pause signaling and exposes status as a simple string property. The RunManager passes `stop_check` and `pause_check` callbacks into `run_autoresearch()`, which requires TASK_008 (run_loop.py modification) to accept those parameters. See GRADIO_DASHBOARD_PRD.md section 5.3 (Run Manager).

## Goal
Build a thread-safe RunManager class that can start/stop/pause the autoresearch loop from the dashboard UI.

## Research First
- [ ] Read GRADIO_DASHBOARD_PRD.md section 5.3 (Run Manager) for class interface
- [ ] Read GRADIO_DASHBOARD_PRD.md section 5.8 (Modifications to Existing Code) for stop_check/pause_check callbacks
- [ ] Read `run_loop.py` `run_autoresearch()` signature and main loop structure
- [ ] Read `autotrust/observe.py` `start_run()` to understand how run_id is generated
- [ ] Verify threading.Event semantics: `set()` = signaled, `is_set()` = check, `clear()` = reset

## TDD: Tests First (Red)
Write tests FIRST in `tests/test_run_manager.py`. They should FAIL before implementation.

### Unit Tests
- [ ] Test: `test_initial_status_is_idle` -- newly created RunManager has status "idle" and current_run_id is None -- in `tests/test_run_manager.py`
- [ ] Test: `test_start_sets_running` -- after start(), status is "running" and current_run_id is not None -- in `tests/test_run_manager.py`
- [ ] Test: `test_stop_sets_stopping_then_idle` -- after stop(), status transitions to "stopping", then "idle" after thread exits -- in `tests/test_run_manager.py`
- [ ] Test: `test_pause_resume_lifecycle` -- pause() sets status "paused", resume() sets status back to "running" -- in `tests/test_run_manager.py`
- [ ] Test: `test_stop_check_callback_returns_true_when_stopped` -- the stop_check callback returns True after stop() is called -- in `tests/test_run_manager.py`
- [ ] Test: `test_start_when_already_running_raises` -- calling start() while already running raises RuntimeError -- in `tests/test_run_manager.py`

All tests use a mock `run_autoresearch` function (a simple sleep loop that checks stop_check) to avoid requiring the full autoresearch stack.

## Implementation
- [ ] Step 1: Implement `RunManager.__init__()` in `autotrust/dashboard/run_manager.py`:
  - `self._thread: threading.Thread | None = None`
  - `self._stop_event = threading.Event()`
  - `self._pause_event = threading.Event()` (set = NOT paused, clear = paused; set initially)
  - `self._current_run_id: str | None = None`
  - `self._status: str = "idle"`
  ```python
  class RunManager:
      """Manages the autoresearch loop in a background thread."""
      def __init__(self):
          ...
  ```
- [ ] Step 2: Implement `start(self, max_experiments: int = 50) -> str`:
  - Raise RuntimeError if already running
  - Generate run_id (or delegate to run_autoresearch)
  - Clear stop event, set pause event (not paused)
  - Launch `run_autoresearch(max_experiments, stop_check=..., pause_check=...)` in a daemon thread
  - Set status to "running"
  - Return run_id
  ```python
  def start(self, max_experiments: int = 50) -> str:
      """Launch run_autoresearch in a daemon thread. Returns run_id."""
  ```
- [ ] Step 3: Implement `stop(self) -> None`:
  - Set stop event
  - Set status to "stopping"
  - Optionally join thread with timeout
  - Set status to "idle" after thread exits
  ```python
  def stop(self) -> None:
      """Signal graceful stop after current experiment."""
  ```
- [ ] Step 4: Implement `pause(self) -> None` and `resume(self) -> None`:
  - pause: clear pause event, set status "paused"
  - resume: set pause event, set status "running"
  ```python
  def pause(self) -> None:
      """Pause between experiments."""
  def resume(self) -> None:
      """Resume from pause."""
  ```
- [ ] Step 5: Implement properties:
  ```python
  @property
  def status(self) -> str: ...
  @property
  def current_run_id(self) -> str | None: ...
  ```
- [ ] Step 6: Implement private `_stop_check` and `_pause_check` methods that read from the events:
  ```python
  def _stop_check(self) -> bool:
      return self._stop_event.is_set()
  def _pause_check(self) -> bool:
      return not self._pause_event.is_set()
  ```
- [ ] DRY check: does NOT reimplement run_autoresearch logic, only wraps it in a thread with event-based callbacks.

## TDD: Tests Pass (Green)
- [ ] All 6 unit tests pass
- [ ] All existing tests still pass

## Acceptance Criteria
- [ ] `autotrust/dashboard/run_manager.py` exists with RunManager class
- [ ] RunManager has start(), stop(), pause(), resume() methods
- [ ] RunManager has status and current_run_id properties
- [ ] Thread is a daemon thread (won't prevent process exit)
- [ ] Status transitions: idle -> running -> paused -> running -> stopping -> idle
- [ ] start() while running raises RuntimeError
- [ ] All tests pass

## Execution
- **Agent Type**: python-expert
- **Wave**: 3 (depends on TASK_001 scaffold, TASK_008 run_loop modification)
- **Complexity**: Medium
