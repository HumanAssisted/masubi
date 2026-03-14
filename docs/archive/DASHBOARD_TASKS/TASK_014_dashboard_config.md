# Task 014: Build Dashboard -- Config Tab (Read-Only Reference)

## Context
The Config tab is a simple read-only reference panel showing `spec.yaml` as a code block, the calibration report as formatted JSON, and current effective weights after Kappa downweighting. This is the simplest dashboard tab. It uses `data_loader.load_spec_text()` and `data_loader.load_calibration()` from TASK_002. See GRADIO_DASHBOARD_PRD.md section 4.6 (Config).

## Goal
Add the Config tab displaying spec.yaml, calibration report, and effective weights as read-only reference.

## Research First
- [ ] Read GRADIO_DASHBOARD_PRD.md section 4.6 (Config) for layout
- [ ] Read `autotrust/dashboard/data_loader.py` (TASK_002) for load_spec_text(), load_calibration()
- [ ] Read `autotrust/config.py` for get_effective_weights() to compute displayed weights
- [ ] Read `dashboard.py` (TASK_009) for tab structure

## TDD: Tests First (Red)
Write tests in `tests/test_dashboard_integration.py` (append to existing). They should FAIL before implementation.

### Integration Tests
- [ ] Test: `test_config_tab_has_required_components` -- verify tab contains: spec code block, calibration JSON display, effective weights table -- in `tests/test_dashboard_integration.py`

## Implementation
- [ ] Step 1: Add Config tab to `dashboard.py` `create_app()`:
  ```python
  with gr.Tab("Config"):
      _build_config_tab()
  ```
- [ ] Step 2: Implement `_build_config_tab()`:
  ```python
  def _build_config_tab():
      with gr.Row():
          refresh_config_btn = gr.Button("Refresh Config")
      with gr.Row():
          with gr.Column():
              spec_display = gr.Code(
                  label="spec.yaml",
                  language="yaml",
                  value=data_loader.load_spec_text(),
              )
          with gr.Column():
              calibration_display = gr.JSON(
                  label="Calibration Report",
                  value=data_loader.load_calibration(),
              )
      with gr.Row():
          weights_table = gr.Dataframe(
              headers=["Axis", "Original Weight", "Effective Weight", "Kappa"],
              label="Current Effective Weights",
          )
  ```
- [ ] Step 3: Wire refresh button:
  ```python
  def refresh_config():
      spec_text = data_loader.load_spec_text()
      calibration = data_loader.load_calibration()
      # Compute effective weights
      try:
          from autotrust.config import get_spec, get_effective_weights
          spec = get_spec()
          kappa = calibration.get("per_axis_kappa", {})
          eff_weights = get_effective_weights(spec, kappa)
          weights_data = [
              [a.name, f"{a.weight:.4f}", f"{eff_weights.get(a.name, a.weight):.4f}",
               f"{kappa.get(a.name, 1.0):.3f}"]
              for a in spec.trust_axes
          ]
      except Exception:
          weights_data = []
      return spec_text, calibration, weights_data

  refresh_config_btn.click(refresh_config, outputs=[spec_display, calibration_display, weights_table])
  ```
- [ ] Step 4: Load initial values on app start:
  ```python
  app.load(refresh_config, outputs=[spec_display, calibration_display, weights_table])
  ```
- [ ] DRY check: uses data_loader for file reading, config.get_effective_weights for weight computation. No reimplementation.

## TDD: Tests Pass (Green)
- [ ] All 1 new integration test passes
- [ ] All existing tests still pass

## Acceptance Criteria
- [ ] Config tab exists in the Gradio app
- [ ] spec.yaml is displayed as a YAML code block
- [ ] Calibration report is displayed as formatted JSON
- [ ] Effective weights table shows axis name, original weight, effective weight, and Kappa
- [ ] Refresh button reloads all three displays
- [ ] All tests pass

## Execution
- **Agent Type**: python-expert
- **Wave**: 5 (depends on TASK_002 data_loader, TASK_009 dashboard_live_run)
- **Complexity**: Low
