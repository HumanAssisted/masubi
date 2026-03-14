# Task 012: Build Dashboard -- Run History Tab

## Context
The Run History tab lets researchers browse all past runs stored in `runs/` as text files. It shows a sortable/filterable run list, click-to-view run detail (metrics + charts), side-by-side run comparison, and file export. Uses `data_loader.list_runs()` and `data_loader.load_run_metrics()` for data, plus `charts.run_comparison()` for the comparison view. See GRADIO_DASHBOARD_PRD.md section 4.4 (Run History).

## Goal
Add the Run History tab with run list, detail view, comparison, and export.

## Research First
- [ ] Read GRADIO_DASHBOARD_PRD.md section 4.4 (Run History) for full layout
- [ ] Read `autotrust/dashboard/data_loader.py` (TASK_002) for list_runs(), load_run_metrics(), load_run_summary()
- [ ] Read `autotrust/dashboard/charts.py` (TASK_006) for run_comparison()
- [ ] Read `dashboard.py` (TASK_009) for tab structure

## TDD: Tests First (Red)
Write tests in `tests/test_dashboard_integration.py` (append to existing). They should FAIL before implementation.

### Integration Tests
- [ ] Test: `test_run_history_tab_has_required_components` -- verify tab contains: run list table, detail panel, comparison selector, export button -- in `tests/test_dashboard_integration.py`
- [ ] Test: `test_run_list_populates_from_fixture` -- create fixture run directories with metrics.jsonl and summary.txt, verify run list displays correct metadata -- in `tests/test_dashboard_integration.py`

## Implementation
- [ ] Step 1: Add Run History tab to `dashboard.py` `create_app()`:
  ```python
  with gr.Tab("Run History"):
      _build_run_history_tab()
  ```
- [ ] Step 2: Implement `_build_run_history_tab()`:
  ```python
  def _build_run_history_tab():
      with gr.Row():
          refresh_runs_btn = gr.Button("Refresh Run List")
      with gr.Row():
          run_list = gr.Dataframe(
              headers=["Run ID", "Date", "Experiments", "Best Composite", "Total Cost", "Status"],
              label="Past Runs",
              interactive=False,
          )
      with gr.Row():
          with gr.Column():
              selected_run = gr.Dropdown(label="View Run Detail", choices=[])
              compare_run_1 = gr.Dropdown(label="Compare Run 1", choices=[])
              compare_run_2 = gr.Dropdown(label="Compare Run 2", choices=[])
              compare_btn = gr.Button("Compare Runs")
          with gr.Column(scale=2):
              run_detail = gr.Markdown(label="Run Detail")
              run_detail_plot = gr.Plot(label="Run Composite Trend")
      with gr.Row():
          comparison_plot = gr.Plot(label="Run Comparison")
      with gr.Row():
          export_btn = gr.Button("Export metrics.jsonl")
          export_file = gr.File(label="Download")
  ```
- [ ] Step 3: Wire refresh button:
  ```python
  def refresh_run_list():
      runs = data_loader.list_runs()
      rows = [[r["run_id"], r.get("date", ""), r.get("experiment_count", 0),
               f"{r.get('best_composite', 0):.4f}", f"${r.get('total_cost', 0):.2f}",
               r.get("status", "unknown")] for r in runs]
      choices = [r["run_id"] for r in runs]
      return rows, gr.update(choices=choices), gr.update(choices=choices), gr.update(choices=choices)

  refresh_runs_btn.click(refresh_run_list, outputs=[run_list, selected_run, compare_run_1, compare_run_2])
  ```
- [ ] Step 4: Wire run detail view:
  ```python
  def show_run_detail(run_id):
      if not run_id:
          return "Select a run.", None
      summary = data_loader.load_run_summary(run_id)
      metrics = data_loader.load_run_metrics(run_id)
      fig = charts.composite_trend(metrics)
      return summary, fig

  selected_run.change(show_run_detail, inputs=[selected_run], outputs=[run_detail, run_detail_plot])
  ```
- [ ] Step 5: Wire run comparison:
  ```python
  def compare_runs(run_id_1, run_id_2):
      if not run_id_1 or not run_id_2:
          return None
      m1 = data_loader.load_run_metrics(run_id_1)
      m2 = data_loader.load_run_metrics(run_id_2)
      return charts.run_comparison(m1, m2)

  compare_btn.click(compare_runs, inputs=[compare_run_1, compare_run_2], outputs=[comparison_plot])
  ```
- [ ] Step 6: Wire export button:
  ```python
  def export_metrics(run_id):
      if not run_id:
          return None
      path = Path("runs") / run_id / "metrics.jsonl"
      return str(path) if path.exists() else None

  export_btn.click(export_metrics, inputs=[selected_run], outputs=[export_file])
  ```
- [ ] DRY check: data loading via data_loader, charting via charts.py. Dashboard only handles UI wiring.

## TDD: Tests Pass (Green)
- [ ] All 2 new integration tests pass
- [ ] All existing tests still pass

## Acceptance Criteria
- [ ] Run History tab exists in the Gradio app
- [ ] Run list shows run_id, date, experiment count, best composite, total cost, status
- [ ] Clicking a run shows its summary and composite trend chart
- [ ] Run comparison produces a grouped bar chart of two runs
- [ ] Export downloads the metrics.jsonl file
- [ ] All tests pass

## Execution
- **Agent Type**: python-expert
- **Wave**: 5 (depends on TASK_002 data_loader, TASK_006 charts_advanced, TASK_009 dashboard_live_run)
- **Complexity**: Medium
