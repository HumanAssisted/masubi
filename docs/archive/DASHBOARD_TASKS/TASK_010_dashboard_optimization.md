# Task 010: Build Dashboard -- Optimization Dashboard Tab

## Context
The Optimization Dashboard tab provides deeper "is the agent actually improving?" analysis. It is all charts, no logs. It uses the advanced chart builders from TASK_006 (axis_improvement_heatmap, gate_pass_rate, cost_efficiency) plus an enhanced composite trend with baseline markers and best-so-far line. It also includes a best-scores table showing current best per-axis scores vs initial baseline. See GRADIO_DASHBOARD_PRD.md section 4.2 (Optimization Dashboard).

## Goal
Add the Optimization Dashboard tab to dashboard.py with all analytical charts and a best-scores summary table.

## Research First
- [ ] Read GRADIO_DASHBOARD_PRD.md section 4.2 (Optimization Dashboard) for full layout
- [ ] Read `autotrust/dashboard/charts.py` (TASK_005 + TASK_006) for available chart builders
- [ ] Read `dashboard.py` (TASK_009) for tab structure and timer pattern
- [ ] Read `autotrust/dashboard/data_loader.py` (TASK_002) for data loading functions

## TDD: Tests First (Red)
Write tests in `tests/test_dashboard_integration.py` (append to existing). They should FAIL before implementation.

### Integration Tests
- [ ] Test: `test_optimization_tab_has_required_charts` -- verify the Optimization Dashboard tab contains: enhanced composite trend, heatmap, gate pass rate bar, cost efficiency chart, best scores table -- in `tests/test_dashboard_integration.py`
- [ ] Test: `test_optimization_tab_renders_with_fixture_data` -- with fixture metrics, verify all charts render without error -- in `tests/test_dashboard_integration.py`

## Implementation
- [ ] Step 1: Add Optimization Dashboard tab to `dashboard.py` `create_app()`:
  ```python
  with gr.Tab("Optimization"):
      _build_optimization_tab()
  ```
- [ ] Step 2: Implement `_build_optimization_tab()`:
  ```python
  def _build_optimization_tab():
      with gr.Row():
          opt_composite_plot = gr.Plot(label="Composite Trend (Enhanced)")
      with gr.Row():
          with gr.Column():
              heatmap_plot = gr.Plot(label="Per-Axis Improvement Heatmap")
          with gr.Column():
              gate_rate_plot = gr.Plot(label="Gate Pass Rate")
      with gr.Row():
          with gr.Column():
              cost_eff_plot = gr.Plot(label="Cost Efficiency")
          with gr.Column():
              best_scores_table = gr.Dataframe(label="Best Scores vs Baseline")
  ```
- [ ] Step 3: Wire timer updates for optimization charts. Reuse the same poll_state from Live Run tab or create a shared state:
  - Enhanced composite trend: same as composite_trend but with annotations for baseline and best-so-far
  - Heatmap: `charts.axis_improvement_heatmap(metrics)`
  - Gate pass rate: `charts.gate_pass_rate(metrics)`
  - Cost efficiency: `charts.cost_efficiency(metrics)`
  - Best scores: compute from metrics list (first experiment baseline vs best per-axis)
- [ ] Step 4: Implement best_scores helper:
  ```python
  def _compute_best_scores_table(metrics: list[dict]) -> list[list]:
      """Compute best per-axis scores vs baseline for the dataframe."""
      if not metrics:
          return []
      baseline = metrics[0].get("per_axis_scores", {})
      best = dict(baseline)
      for m in metrics[1:]:
          for axis, score in m.get("per_axis_scores", {}).items():
              if score > best.get(axis, 0):
                  best[axis] = score
      return [[axis, baseline.get(axis, 0), best.get(axis, 0), best.get(axis, 0) - baseline.get(axis, 0)]
              for axis in sorted(best.keys())]
  ```
- [ ] DRY check: chart building delegated to charts.py. No reimplementation of chart logic in dashboard.py.

## TDD: Tests Pass (Green)
- [ ] All 2 new integration tests pass
- [ ] All existing tests still pass

## Acceptance Criteria
- [ ] Optimization Dashboard tab exists in the Gradio app
- [ ] Enhanced composite trend shows baseline markers and best-so-far line
- [ ] Heatmap shows per-axis score changes (green = improved, red = degraded)
- [ ] Gate pass rate shows per-gate pass/fail counts
- [ ] Cost efficiency shows composite improvement per dollar
- [ ] Best scores table shows axis, baseline, best, delta columns
- [ ] All charts update via timer during a live run
- [ ] All tests pass

## Execution
- **Agent Type**: python-expert
- **Wave**: 5 (depends on TASK_006 charts_advanced, TASK_009 dashboard_live_run)
- **Complexity**: Medium
