# Task 008: Modify run_loop.py -- Add Stop/Pause Callbacks

## Context
The dashboard needs to stop and pause the autoresearch loop gracefully between experiments. This requires adding two optional callback parameters to `run_autoresearch()`: `stop_check` (returns True to stop) and `pause_check` (returns True to pause/block). These are backward-compatible -- both default to None, so calling `run_autoresearch()` without them works exactly as before. See GRADIO_DASHBOARD_PRD.md section 5.8 (Modifications to Existing Code).

This is the ONLY modification to existing code required by the dashboard. All other modules remain untouched.

## Goal
Add optional stop_check and pause_check callback parameters to `run_autoresearch()` so the dashboard can control the loop without modifying its core logic.

## Research First
- [ ] Read GRADIO_DASHBOARD_PRD.md section 5.8 (Modifications to Existing Code)
- [ ] Read `run_loop.py` `run_autoresearch()` -- understand the main loop structure
- [ ] Read `tests/test_run_loop.py` -- understand all 6 existing tests to ensure they still pass
- [ ] Verify the change is backward-compatible: `run_autoresearch()` with no args must behave identically

## TDD: Tests First (Red)
Write NEW tests in `tests/test_run_loop.py`. They should FAIL before implementation. Do NOT modify existing tests.

### Unit Tests
- [ ] Test: `test_stop_check_callback_exits_loop` -- pass a stop_check that returns True after 1 call; verify loop exits early -- in `tests/test_run_loop.py`
- [ ] Test: `test_pause_check_callback_blocks` -- pass a pause_check that returns True for 2 calls then False; verify loop pauses then continues -- in `tests/test_run_loop.py`
- [ ] Test: `test_callbacks_default_none_backward_compatible` -- call run_autoresearch() without callbacks; verify it works identically to before -- in `tests/test_run_loop.py`

## Implementation
- [ ] Step 1: Modify `run_autoresearch()` signature in `run_loop.py`:
  ```python
  from collections.abc import Callable

  def run_autoresearch(
      max_experiments: int = 50,
      stop_check: Callable[[], bool] | None = None,
      pause_check: Callable[[], bool] | None = None,
  ) -> None:
  ```
- [ ] Step 2: Add stop check at the top of the main loop (before each experiment), right after the existing limit checks:
  ```python
  # In the for loop, after budget/time checks:
  if stop_check and stop_check():
      logger.info("Stop requested via callback. Ending loop.")
      break
  ```
- [ ] Step 3: Add pause check after the stop check:
  ```python
  while pause_check and pause_check():
      time.sleep(1)
      # Re-check stop during pause
      if stop_check and stop_check():
          logger.info("Stop requested during pause. Ending loop.")
          break
  ```
- [ ] Step 4: Add `from collections.abc import Callable` to imports (if not present)
- [ ] DRY check: no logic duplication. The callbacks are simple event checks passed in by RunManager. The loop logic itself is unchanged.

## TDD: Tests Pass (Green)
- [ ] All 3 new tests pass
- [ ] All 6 existing tests in test_run_loop.py still pass unchanged
- [ ] All other existing tests still pass

## Acceptance Criteria
- [ ] `run_autoresearch()` accepts optional `stop_check` and `pause_check` parameters
- [ ] Both default to None (backward-compatible)
- [ ] Stop check is evaluated at the top of each experiment iteration
- [ ] Pause check blocks with sleep(1) between experiments
- [ ] Stop during pause is handled (break out of pause loop)
- [ ] All existing tests pass without modification
- [ ] All new tests pass

## Execution
- **Agent Type**: python-expert
- **Wave**: 2 (depends on TASK_001; parallel with TASK_002, TASK_003, TASK_004)
- **Complexity**: Low
