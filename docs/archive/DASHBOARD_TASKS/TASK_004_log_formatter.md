# Task 004: Build log_formatter.py -- Experiment Log Formatting

## Context
`log_formatter.py` formats raw experiment result dicts (from metrics.jsonl) into human-readable log entries for the dashboard's log stream panel. It produces both collapsed one-line summaries and expanded detail views. The collapsed line includes timestamp, experiment number, composite score with delta, KEPT/DISCARDED status, gate indicators, and cost. The expanded view adds per-axis scores with deltas, gate reasons, explanation text, and cost breakdown. See GRADIO_DASHBOARD_PRD.md section 5.6 (Log Formatter).

## Goal
Build log formatting functions that turn raw metrics dicts into human-readable log stream entries for the Live Run tab.

## Research First
- [ ] Read GRADIO_DASHBOARD_PRD.md section 5.6 (Log Formatter) for function signatures
- [ ] Read GRADIO_DASHBOARD_PRD.md section 4.1 (Live Run > Row 3 -- Log Stream) for display format
- [ ] Read `autotrust/schemas.py` `ExperimentResult` for available fields
- [ ] Read `autotrust/observe.py` `log_experiment()` to see what fields are written to metrics.jsonl

## TDD: Tests First (Red)
Write tests FIRST in `tests/test_log_formatter.py`. They should FAIL before implementation.

### Unit Tests
- [ ] Test: `test_format_log_entry_kept` -- format a KEPT experiment with positive delta, verify contains "KEPT", composite value, positive delta, green gate symbols -- in `tests/test_log_formatter.py`
- [ ] Test: `test_format_log_entry_discarded` -- format a DISCARDED experiment, verify contains "DISCARDED" and shows which gate(s) failed -- in `tests/test_log_formatter.py`
- [ ] Test: `test_format_log_entry_baseline` -- first experiment (no previous composite), verify shows "(baseline)" instead of delta -- in `tests/test_log_formatter.py`
- [ ] Test: `test_format_experiment_detail_per_axis` -- expanded detail includes per-axis scores table with deltas from previous best -- in `tests/test_log_formatter.py`
- [ ] Test: `test_format_experiment_detail_gate_reasons` -- expanded detail includes gate pass/fail with reasons -- in `tests/test_log_formatter.py`
- [ ] Test: `test_format_log_stream_newest_first` -- format_log_stream with 3 experiments returns entries in reverse order (newest first) -- in `tests/test_log_formatter.py`

## Implementation
- [ ] Step 1: Implement `format_experiment_log_entry(result: dict, prev_composite: float | None) -> str` in `autotrust/dashboard/log_formatter.py`:
  - Extract timestamp from `wall_time` or use experiment index
  - Format: `[HH:MM:SS] Exp #N  composite=X.XXX (+X.XXX)  KEPT  gates: <symbols>  $X.XX`
  - Use checkmark for passed gates, X for failed
  - Show "(baseline)" for first experiment when prev_composite is None
  - Show KEPT if all gate_results values are True, else DISCARDED
  ```python
  def format_experiment_log_entry(result: dict, prev_composite: float | None) -> str:
      """Format a single experiment as a collapsed log line."""
  ```
- [ ] Step 2: Implement `format_experiment_detail(result: dict, prev_best: dict | None) -> str`:
  - Per-axis scores table: axis name, score, delta from previous
  - Gate results with descriptive labels: composite (improved/not), gold (pass/veto), explanation (pass/warn/fail)
  - Explanation text (change_description)
  - Cost breakdown
  ```python
  def format_experiment_detail(result: dict, prev_best: dict | None) -> str:
      """Format expanded detail view with per-axis deltas, gate reasons, explanation."""
  ```
- [ ] Step 3: Implement `format_log_stream(metrics: list[dict]) -> str`:
  - Iterate metrics list, calling `format_experiment_log_entry` for each
  - Compute delta from previous experiment's composite
  - Return entries in reverse order (newest first), joined by newlines
  ```python
  def format_log_stream(metrics: list[dict]) -> str:
      """Format full metrics list as a log stream (newest first)."""
  ```
- [ ] DRY check: reads raw dicts from metrics.jsonl, does NOT re-parse or re-validate via pydantic. Uses field names matching ExperimentResult.

## TDD: Tests Pass (Green)
- [ ] All 6 unit tests pass
- [ ] All existing tests still pass

## Acceptance Criteria
- [ ] `autotrust/dashboard/log_formatter.py` exists with all 3 functions
- [ ] Collapsed log entries match the format from PRD section 4.1
- [ ] Expanded details include per-axis deltas and gate reasons
- [ ] Log stream is newest-first
- [ ] Baseline experiment handled (no delta shown)
- [ ] All tests pass

## Execution
- **Agent Type**: python-expert
- **Wave**: 2 (depends on TASK_001 scaffold; parallel with TASK_002, TASK_003)
- **Complexity**: Low
