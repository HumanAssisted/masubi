# Task 009: Build dashboard.py -- Live Run Tab (Primary View)

## Context
`dashboard.py` is the Gradio Blocks application entry point. This task builds the primary "Live Run" tab -- the charts-first view that researchers see when they open the dashboard. It wires together RunManager (start/stop/pause), data_loader (polling metrics.jsonl), charts (composite trend, cost burn, radar, gate timeline, stall indicator), and log_formatter (experiment log stream). A `gr.Timer(every=2)` drives real-time polling. See GRADIO_DASHBOARD_PRD.md sections 4.1 (Live Run) and 5.1 (Architecture).

This is the largest dashboard task. It assembles all library-layer modules into a working UI.

## Goal
Build the Live Run tab with controls, hero charts, secondary charts, and log stream -- all updating in real time via polling.

## Research First
- [ ] Read GRADIO_DASHBOARD_PRD.md section 4.1 (Live Run) for full layout specification
- [ ] Read GRADIO_DASHBOARD_PRD.md section 5.1 (Architecture) for the overall structure
- [ ] Read Gradio docs: `gr.Blocks`, `gr.Tab`, `gr.Row`, `gr.Column`, `gr.Plot`, `gr.Button`, `gr.Number`, `gr.Timer`, `gr.Markdown`, `gr.Textbox`
- [ ] Read `autotrust/dashboard/run_manager.py` (TASK_007) for RunManager interface
- [ ] Read `autotrust/dashboard/data_loader.py` (TASK_002) for polling functions
- [ ] Read `autotrust/dashboard/charts.py` (TASK_005) for chart builder signatures
- [ ] Read `autotrust/dashboard/log_formatter.py` (TASK_004) for format_log_stream signature

## TDD: Tests First (Red)
Write tests FIRST in `tests/test_dashboard_integration.py`. They should FAIL before implementation.

### Integration Tests
- [ ] Test: `test_dashboard_launches_without_error` -- import dashboard module and verify Gradio Blocks app can be instantiated without crashing -- in `tests/test_dashboard_integration.py`
- [ ] Test: `test_live_run_tab_has_required_components` -- verify the Live Run tab contains: start button, stop button, pause button, max_experiments input, status indicator, composite trend plot, cost burn plot, radar plot, gate timeline plot, stall indicator, log stream -- in `tests/test_dashboard_integration.py`
- [ ] Test: `test_start_button_calls_run_manager` -- mock RunManager, click start, verify start() is called -- in `tests/test_dashboard_integration.py`
- [ ] Test: `test_timer_updates_charts` -- with fixture metrics.jsonl, verify timer callback returns updated chart figures -- in `tests/test_dashboard_integration.py`

## Implementation
- [ ] Step 1: Create `dashboard.py` at project root with Gradio Blocks structure:
  ```python
  import gradio as gr
  from autotrust.dashboard.run_manager import RunManager
  from autotrust.dashboard import data_loader, charts, log_formatter

  run_manager = RunManager()

  def create_app() -> gr.Blocks:
      with gr.Blocks(title="AutoResearch Dashboard") as app:
          with gr.Tab("Live Run"):
              _build_live_run_tab()
          # Other tabs added by later tasks
      return app
  ```
- [ ] Step 2: Build Row 0 -- Controls:
  ```python
  with gr.Row():
      start_btn = gr.Button("Start", variant="primary")
      stop_btn = gr.Button("Stop", variant="stop")
      pause_btn = gr.Button("Pause/Resume")
      max_exp_input = gr.Number(value=50, label="Max Experiments", precision=0)
      status_indicator = gr.Textbox(value="idle", label="Status", interactive=False)
      cost_display = gr.Textbox(value="$0.00", label="Cost So Far", interactive=False)
  ```
- [ ] Step 3: Build Row 1 -- Hero Charts:
  ```python
  with gr.Row():
      with gr.Column(scale=3):
          composite_plot = gr.Plot(label="Composite Score Trend")
      with gr.Column(scale=1):
          cost_burn_plot = gr.Plot(label="Cost Burn")
  ```
- [ ] Step 4: Build Row 2 -- Secondary Charts:
  ```python
  with gr.Row():
      with gr.Column():
          radar_plot = gr.Plot(label="Per-Axis Radar")
      with gr.Column():
          gate_plot = gr.Plot(label="Gate Timeline")
      with gr.Column():
          stall_plot = gr.Plot(label="Stall Indicator")
  ```
- [ ] Step 5: Build Row 3 -- Log Stream:
  ```python
  with gr.Row():
      log_stream = gr.Markdown(label="Experiment Log", value="No experiments yet.")
  ```
- [ ] Step 6: Wire button click handlers:
  ```python
  def handle_start(max_exp):
      run_id = run_manager.start(int(max_exp))
      return f"Running: {run_id}"

  def handle_stop():
      run_manager.stop()
      return "Stopped"

  def handle_pause_resume():
      if run_manager.status == "paused":
          run_manager.resume()
          return "Running"
      else:
          run_manager.pause()
          return "Paused"

  start_btn.click(handle_start, inputs=[max_exp_input], outputs=[status_indicator])
  stop_btn.click(handle_stop, outputs=[status_indicator])
  pause_btn.click(handle_pause_resume, outputs=[status_indicator])
  ```
- [ ] Step 7: Wire gr.Timer for polling:
  ```python
  timer = gr.Timer(every=2)

  # State to track polling position
  poll_state = gr.State({"line_count": 0, "metrics": []})

  def poll_update(state):
      run_id = run_manager.current_run_id
      if not run_id:
          return state, *_empty_outputs()

      new_records, new_count = data_loader.load_latest_metrics(run_id, state["line_count"])
      if new_records:
          state["metrics"].extend(new_records)
          state["line_count"] = new_count

      metrics = state["metrics"]
      return (
          state,
          run_manager.status,
          f"${sum(m.get('cost', 0) for m in metrics):.2f}",
          charts.composite_trend(metrics),
          charts.cost_burn(metrics, budget_limit=5.0),
          charts.radar_chart(metrics[-1]) if metrics else charts.radar_chart({}),
          charts.gate_timeline(metrics),
          charts.stall_indicator(metrics),
          log_formatter.format_log_stream(metrics),
      )

  timer.tick(
      poll_update,
      inputs=[poll_state],
      outputs=[poll_state, status_indicator, cost_display, composite_plot, cost_burn_plot, radar_plot, gate_plot, stall_plot, log_stream],
  )
  ```
- [ ] Step 8: Add `if __name__ == "__main__"` entry point:
  ```python
  if __name__ == "__main__":
      app = create_app()
      app.launch()
  ```
- [ ] DRY check: all data loading delegated to data_loader, all charting to charts, all formatting to log_formatter. dashboard.py is pure wiring.

## TDD: Tests Pass (Green)
- [ ] All 4 integration tests pass
- [ ] All existing tests still pass

## Acceptance Criteria
- [ ] `dashboard.py` exists at project root
- [ ] Running `python dashboard.py` launches a Gradio app in the browser
- [ ] Live Run tab has controls (Start, Stop, Pause, Max Experiments, Status, Cost)
- [ ] Composite trend chart updates every 2 seconds during a run
- [ ] Cost burn gauge updates with cumulative spend
- [ ] Radar chart shows per-axis scores for the latest experiment
- [ ] Gate timeline shows pass/fail pattern
- [ ] Stall indicator shows consecutive no-improvement count
- [ ] Log stream shows experiment entries newest-first
- [ ] Start/Stop/Pause buttons control the run loop
- [ ] All tests pass

## Execution
- **Agent Type**: python-expert
- **Wave**: 4 (depends on TASK_002 data_loader, TASK_004 log_formatter, TASK_005 charts_core, TASK_007 run_manager)
- **Complexity**: High
