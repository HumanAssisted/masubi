# Task 005: Build charts.py -- Core Chart Builders (Live Run + Cost)

## Context
`charts.py` contains Plotly figure builders for the dashboard. This task covers the core charts used in the Live Run tab (Row 1 + Row 2): composite trend line (the "hero chart"), cost burn gauge, per-axis radar/spider chart, gate timeline scatter plot, and stall indicator. Each function takes a list of experiment dicts (from metrics.jsonl) and returns a `plotly.graph_objects.Figure`. See GRADIO_DASHBOARD_PRD.md sections 4.1 (Live Run) and 5.7 (Charts).

## Goal
Build the primary Plotly chart builders for the Live Run tab: composite trend, cost burn, radar, gate timeline, and stall indicator.

## Research First
- [ ] Read GRADIO_DASHBOARD_PRD.md section 4.1 (Live Run) for chart descriptions and layout
- [ ] Read GRADIO_DASHBOARD_PRD.md section 5.7 (Charts) for function signatures
- [ ] Read `autotrust/schemas.py` `ExperimentResult` for available data fields
- [ ] Read Plotly docs: `go.Scatter`, `go.Scatterpolar` (radar), `go.Indicator` (gauge), `go.Figure`
- [ ] Understand kept vs discarded experiments: `gate_results` dict -- all True = kept

## TDD: Tests First (Red)
Write tests FIRST in `tests/test_charts.py`. They should FAIL before implementation.

### Unit Tests
- [ ] Test: `test_composite_trend_returns_figure` -- with 5 experiment dicts, verify returns go.Figure with at least one trace -- in `tests/test_charts.py`
- [ ] Test: `test_composite_trend_colors_kept_vs_discarded` -- verify kept experiments plotted as green dots, discarded as red -- in `tests/test_charts.py`
- [ ] Test: `test_composite_trend_single_experiment` -- with 1 experiment, still returns valid figure (no crash) -- in `tests/test_charts.py`
- [ ] Test: `test_composite_trend_empty_data` -- with empty list, returns empty figure (no crash) -- in `tests/test_charts.py`
- [ ] Test: `test_cost_burn_returns_gauge` -- with 3 experiments and budget_limit, returns figure with indicator trace -- in `tests/test_charts.py`
- [ ] Test: `test_radar_chart_returns_scatterpolar` -- with experiment dict containing per_axis_scores, returns figure with scatterpolar trace -- in `tests/test_charts.py`
- [ ] Test: `test_gate_timeline_returns_scatter` -- with 5 experiments, returns figure showing gate pass/fail as scatter points -- in `tests/test_charts.py`
- [ ] Test: `test_stall_indicator_shows_count` -- verify stall indicator displays consecutive_no_improvement count -- in `tests/test_charts.py`

## Implementation
- [ ] Step 1: Implement `composite_trend(metrics: list[dict]) -> go.Figure` in `autotrust/dashboard/charts.py`:
  - X axis: experiment number (1..N)
  - Y axis: composite score
  - Line trace connecting all points
  - Scatter markers: green for kept (all gate_results True), red for discarded
  - Title: "Composite Score Trend"
  - Layout: clean, dark theme compatible
  ```python
  def composite_trend(metrics: list[dict]) -> go.Figure:
      """Line chart of composite score over experiments with kept/discarded markers."""
  ```
- [ ] Step 2: Implement `cost_burn(metrics: list[dict], budget_limit: float) -> go.Figure`:
  - Cumulative cost line (sum of `cost` field across experiments)
  - Horizontal reference line at `budget_limit`
  - Gauge indicator showing current spend vs limit
  ```python
  def cost_burn(metrics: list[dict], budget_limit: float) -> go.Figure:
      """Cumulative cost line with budget threshold."""
  ```
- [ ] Step 3: Implement `radar_chart(experiment: dict) -> go.Figure`:
  - Scatterpolar trace from `per_axis_scores` dict
  - Axes are the trust axis names, values are scores (0-1)
  - Fill area for visual clarity
  ```python
  def radar_chart(experiment: dict) -> go.Figure:
      """Per-axis radar/spider chart for a single experiment."""
  ```
- [ ] Step 4: Implement `gate_timeline(metrics: list[dict]) -> go.Figure`:
  - X axis: experiment number
  - Y axis: categorical (composite, gold, explanation)
  - Markers: green checkmark for pass, red X for fail
  - Shows gate pass/fail pattern across experiments
  ```python
  def gate_timeline(metrics: list[dict]) -> go.Figure:
      """Scatter plot showing pass/fail for each gate across experiments."""
  ```
- [ ] Step 5: Implement `stall_indicator(metrics: list[dict]) -> go.Figure`:
  - Count consecutive experiments from the end where composite didn't improve
  - Show as a gauge or number indicator
  - Mark LoRA nudge threshold (3) as a reference line
  ```python
  def stall_indicator(metrics: list[dict]) -> go.Figure:
      """Stall indicator showing consecutive no-improvement count."""
  ```
- [ ] DRY check: all chart builders follow the same pattern (take metrics list, return go.Figure). Shared helpers for color mapping, empty data handling.

## TDD: Tests Pass (Green)
- [ ] All 8 unit tests pass
- [ ] All existing tests still pass

## Acceptance Criteria
- [ ] `autotrust/dashboard/charts.py` exists with 5 chart builder functions
- [ ] All functions return valid `plotly.graph_objects.Figure` objects
- [ ] Composite trend distinguishes kept vs discarded with color
- [ ] Cost burn shows cumulative spend with budget reference
- [ ] Radar chart shows per-axis scores for a single experiment
- [ ] Gate timeline shows pass/fail pattern
- [ ] All functions handle empty data gracefully (no crash)
- [ ] All tests pass

## Execution
- **Agent Type**: python-expert
- **Wave**: 3 (depends on TASK_001 scaffold, TASK_002 data_loader for types)
- **Complexity**: Medium
