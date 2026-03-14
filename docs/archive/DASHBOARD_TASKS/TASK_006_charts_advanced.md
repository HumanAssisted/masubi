# Task 006: Build charts.py -- Optimization, Axes Explorer & Run Comparison Charts

## Context
This task adds the remaining chart builders to `charts.py`: the Optimization Dashboard charts (heatmap, gate pass rate, cost efficiency, enhanced composite trend), the Axes Explorer charts (multi-line axis trends, Kappa bars, axis correlation), and the Run History comparison chart. See GRADIO_DASHBOARD_PRD.md sections 4.2 (Optimization Dashboard), 4.5 (Axes Explorer), 4.4 (Run History), and 5.7 (Charts).

## Goal
Complete the chart builder module with all remaining Plotly figure builders for the Optimization Dashboard, Axes Explorer, and Run Comparison tabs.

## Research First
- [ ] Read GRADIO_DASHBOARD_PRD.md section 4.2 (Optimization Dashboard) for chart descriptions
- [ ] Read GRADIO_DASHBOARD_PRD.md section 4.5 (Axes Explorer) for axis analysis charts
- [ ] Read GRADIO_DASHBOARD_PRD.md section 4.4 (Run History) for comparison chart
- [ ] Read GRADIO_DASHBOARD_PRD.md section 5.7 (Charts) for remaining function signatures
- [ ] Read `autotrust/dashboard/charts.py` (TASK_005) for existing patterns
- [ ] Read `autotrust/schemas.py` `CalibrationReport` for Kappa data structure

## TDD: Tests First (Red)
Write tests FIRST in `tests/test_charts.py` (append to existing). They should FAIL before implementation.

### Unit Tests
- [ ] Test: `test_axis_improvement_heatmap_returns_figure` -- with 5 experiments, returns go.Figure with heatmap trace -- in `tests/test_charts.py`
- [ ] Test: `test_axis_improvement_heatmap_empty` -- empty metrics returns empty figure -- in `tests/test_charts.py`
- [ ] Test: `test_gate_pass_rate_returns_bar` -- with 5 experiments, returns figure showing pass/fail rate per gate -- in `tests/test_charts.py`
- [ ] Test: `test_cost_efficiency_returns_figure` -- with 5 experiments, returns figure showing composite improvement per dollar -- in `tests/test_charts.py`
- [ ] Test: `test_axis_trends_returns_multiline` -- with 5 experiments and 3 selected axes, returns figure with 3 line traces -- in `tests/test_charts.py`
- [ ] Test: `test_axis_trends_no_axes_selected` -- empty axes list returns empty figure -- in `tests/test_charts.py`
- [ ] Test: `test_kappa_bars_returns_bar_chart` -- with calibration dict, returns bar chart with threshold line -- in `tests/test_charts.py`
- [ ] Test: `test_run_comparison_returns_grouped_bar` -- with two metrics lists, returns grouped bar comparing best scores -- in `tests/test_charts.py`

## Implementation
- [ ] Step 1: Implement `axis_improvement_heatmap(metrics: list[dict]) -> go.Figure` in `autotrust/dashboard/charts.py`:
  - X axis: experiment number
  - Y axis: axis names
  - Color: score delta from previous experiment (green = improved, red = degraded)
  - Use `go.Heatmap` trace
  ```python
  def axis_improvement_heatmap(metrics: list[dict]) -> go.Figure:
      """Heatmap showing per-axis score changes across experiments."""
  ```
- [ ] Step 2: Implement `gate_pass_rate(metrics: list[dict]) -> go.Figure`:
  - Stacked bar chart: X = gate name (composite, gold, explanation), Y = count
  - Segments: pass (green) vs fail (red)
  ```python
  def gate_pass_rate(metrics: list[dict]) -> go.Figure:
      """Stacked bar showing gate pass/fail counts."""
  ```
- [ ] Step 3: Implement `cost_efficiency(metrics: list[dict]) -> go.Figure`:
  - X axis: cumulative cost
  - Y axis: composite improvement from baseline
  - Shows "bang for buck" -- steep curve = cost-effective optimization
  ```python
  def cost_efficiency(metrics: list[dict]) -> go.Figure:
      """Composite improvement per dollar spent."""
  ```
- [ ] Step 4: Implement `axis_trends(metrics: list[dict], axes: list[str]) -> go.Figure`:
  - Multi-line chart: one line per selected axis
  - X axis: experiment number
  - Y axis: score (0-1)
  - Checkboxes for axis selection are handled in dashboard.py, this just renders
  ```python
  def axis_trends(metrics: list[dict], axes: list[str]) -> go.Figure:
      """Multi-line chart of selected axes over experiments."""
  ```
- [ ] Step 5: Implement `kappa_bars(calibration: dict) -> go.Figure`:
  - Bar chart: one bar per axis showing Kappa value
  - Horizontal reference line at `min_gold_kappa` threshold
  - Red bars for axes below threshold
  ```python
  def kappa_bars(calibration: dict) -> go.Figure:
      """Bar chart of per-axis Kappa with threshold line."""
  ```
- [ ] Step 6: Implement `run_comparison(metrics1: list[dict], metrics2: list[dict]) -> go.Figure`:
  - Grouped bar chart comparing best per-axis scores between two runs
  - Two groups per axis (run1 blue, run2 orange)
  ```python
  def run_comparison(metrics1: list[dict], metrics2: list[dict]) -> go.Figure:
      """Grouped bar comparing best metrics of two runs."""
  ```
- [ ] DRY check: share helper functions with TASK_005 charts (e.g., `_empty_figure()`, `_extract_axis_names()`)

## TDD: Tests Pass (Green)
- [ ] All 8 new unit tests pass
- [ ] All TASK_005 chart tests still pass
- [ ] All existing tests still pass

## Acceptance Criteria
- [ ] `autotrust/dashboard/charts.py` has all 11 chart builder functions total (5 from TASK_005 + 6 new)
- [ ] Heatmap shows per-axis score deltas
- [ ] Gate pass rate shows per-gate pass/fail counts
- [ ] Axis trends supports multi-line with axis selection
- [ ] Kappa bars shows threshold reference line
- [ ] Run comparison produces grouped bars
- [ ] All functions handle empty data gracefully
- [ ] All tests pass

## Execution
- **Agent Type**: python-expert
- **Wave**: 3 (depends on TASK_001 scaffold; parallel with TASK_005)
- **Complexity**: Medium
