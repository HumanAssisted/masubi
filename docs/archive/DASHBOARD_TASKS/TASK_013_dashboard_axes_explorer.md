# Task 013: Build Dashboard -- Axes Explorer Tab

## Context
The Axes Explorer tab provides per-axis deep dives: multi-line time series with selectable axes, Kappa downweight visualization, and axis correlation analysis. It uses `charts.axis_trends()`, `charts.kappa_bars()` from TASK_006, and `data_loader.load_calibration()` from TASK_002. See GRADIO_DASHBOARD_PRD.md section 4.5 (Axes Explorer).

## Goal
Add the Axes Explorer tab with axis trend selector, Kappa bar chart, and axis correlation view.

## Research First
- [ ] Read GRADIO_DASHBOARD_PRD.md section 4.5 (Axes Explorer) for full layout
- [ ] Read `autotrust/dashboard/charts.py` (TASK_006) for axis_trends(), kappa_bars()
- [ ] Read `autotrust/dashboard/data_loader.py` (TASK_002) for load_calibration()
- [ ] Read `autotrust/config.py` `Spec` model to get list of axis names from spec.yaml
- [ ] Read `spec.yaml` for actual axis definitions

## TDD: Tests First (Red)
Write tests in `tests/test_dashboard_integration.py` (append to existing). They should FAIL before implementation.

### Integration Tests
- [ ] Test: `test_axes_explorer_tab_has_required_components` -- verify tab contains: axis checkboxes, trend chart, kappa bar chart -- in `tests/test_dashboard_integration.py`
- [ ] Test: `test_axis_trends_updates_on_selection` -- mock data, select 2 axes, verify chart has 2 traces -- in `tests/test_dashboard_integration.py`

## Implementation
- [ ] Step 1: Add Axes Explorer tab to `dashboard.py` `create_app()`:
  ```python
  with gr.Tab("Axes Explorer"):
      _build_axes_explorer_tab()
  ```
- [ ] Step 2: Implement `_build_axes_explorer_tab()`:
  ```python
  def _build_axes_explorer_tab():
      with gr.Row():
          # Get axis names from spec for checkboxes
          try:
              from autotrust.config import get_spec
              axis_names = [a.name for a in get_spec().trust_axes]
          except Exception:
              axis_names = []

          axis_selector = gr.CheckboxGroup(
              choices=axis_names,
              value=axis_names[:3] if len(axis_names) >= 3 else axis_names,
              label="Select Axes to Plot",
          )
          update_trends_btn = gr.Button("Update Trends")
      with gr.Row():
          axis_trends_plot = gr.Plot(label="Axis Trends Over Experiments")
      with gr.Row():
          with gr.Column():
              kappa_plot = gr.Plot(label="Per-Axis Kappa (Downweight Visualization)")
          with gr.Column():
              correlation_info = gr.Markdown(
                  label="Axis Correlation",
                  value="Select axes and run to see correlation data.",
              )
  ```
- [ ] Step 3: Wire axis trends update:
  ```python
  def update_axis_trends(selected_axes):
      run_id = run_manager.current_run_id
      if not run_id:
          # Try loading from most recent historical run
          runs = data_loader.list_runs()
          if not runs:
              return charts.axis_trends([], selected_axes)
          run_id = runs[0]["run_id"]
      metrics = data_loader.load_run_metrics(run_id)
      return charts.axis_trends(metrics, selected_axes)

  update_trends_btn.click(update_axis_trends, inputs=[axis_selector], outputs=[axis_trends_plot])
  ```
- [ ] Step 4: Wire Kappa bar chart (loaded once, from calibration):
  ```python
  def load_kappa_chart():
      calibration = data_loader.load_calibration()
      return charts.kappa_bars(calibration)

  # Load on tab open or on app start
  app.load(load_kappa_chart, outputs=[kappa_plot])
  ```
- [ ] Step 5: Implement simple axis correlation display:
  ```python
  def compute_axis_correlation(selected_axes):
      run_id = run_manager.current_run_id
      if not run_id:
          runs = data_loader.list_runs()
          if not runs:
              return "No run data available."
          run_id = runs[0]["run_id"]
      metrics = data_loader.load_run_metrics(run_id)
      if len(metrics) < 3:
          return "Need at least 3 experiments for correlation."
      # Simple correlation: compute which axes improve/degrade together
      lines = ["### Axis Correlation Summary\n"]
      for ax1 in selected_axes:
          for ax2 in selected_axes:
              if ax1 >= ax2:
                  continue
              scores1 = [m.get("per_axis_scores", {}).get(ax1, 0) for m in metrics]
              scores2 = [m.get("per_axis_scores", {}).get(ax2, 0) for m in metrics]
              if len(scores1) >= 2:
                  deltas1 = [b - a for a, b in zip(scores1[:-1], scores1[1:])]
                  deltas2 = [b - a for a, b in zip(scores2[:-1], scores2[1:])]
                  same_dir = sum(1 for d1, d2 in zip(deltas1, deltas2) if d1 * d2 > 0)
                  pct = same_dir / len(deltas1) * 100 if deltas1 else 0
                  lines.append(f"- **{ax1}** / **{ax2}**: move together {pct:.0f}% of the time")
      return "\n".join(lines)

  update_trends_btn.click(compute_axis_correlation, inputs=[axis_selector], outputs=[correlation_info])
  ```
- [ ] DRY check: chart building via charts.py. Calibration loading via data_loader.

## TDD: Tests Pass (Green)
- [ ] All 2 new integration tests pass
- [ ] All existing tests still pass

## Acceptance Criteria
- [ ] Axes Explorer tab exists in the Gradio app
- [ ] Axis selector checkboxes list all axes from spec.yaml
- [ ] Trend chart shows multi-line traces for selected axes
- [ ] Kappa bar chart shows per-axis Kappa with threshold line
- [ ] Axis correlation shows which axes move together
- [ ] All tests pass

## Execution
- **Agent Type**: python-expert
- **Wave**: 5 (depends on TASK_002 data_loader, TASK_006 charts_advanced, TASK_009 dashboard_live_run)
- **Complexity**: Medium
