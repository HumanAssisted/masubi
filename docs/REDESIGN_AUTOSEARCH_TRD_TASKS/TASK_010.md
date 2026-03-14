# Task 010: dashboard.py -- Stage-Aware Metrics and Checkpoint UI

## Context
The REDESIGN_AUTOSEARCH_TRD adds Stage 2 (model training) which produces different metrics than Stage 1 (prompt optimization). The dashboard currently shows prompt-optimization metrics (composite score, per-axis scores, gate results). Stage 2 adds training-specific metrics (training loss curves, parameter count, expert utilization for MoE, checkpoint sizes) and needs a checkpoint management UI.

## Goal
Add stage-aware displays and checkpoint management to the Gradio dashboard.

## Research First
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/dashboard.py` (full current implementation)
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/dashboard/charts.py` (existing chart functions)
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/dashboard/data_loader.py` (metrics loading)
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/dashboard/run_manager.py` (run lifecycle)
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/export.py` -- `list_checkpoints()` from TASK_005
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/tests/test_dashboard_integration.py` (existing test patterns)
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/tests/test_charts.py` (existing chart tests)

## TDD: Tests First (Red)

### Unit Tests
- [ ] Test: `test_stage_indicator_shows_stage1` in `tests/test_dashboard_integration.py` -- when run is Stage 1, indicator shows "Stage 1: Prompt Optimization"
- [ ] Test: `test_stage_indicator_shows_stage2` -- when run is Stage 2, indicator shows "Stage 2: Model Training"
- [ ] Test: `test_training_loss_chart` in `tests/test_charts.py` -- `charts.training_loss(metrics)` returns valid Plotly figure with loss curves
- [ ] Test: `test_param_count_display` -- `charts.param_count_timeline(metrics)` shows parameter count over experiments
- [ ] Test: `test_checkpoint_list_loads` -- checkpoint list UI loads `CheckpointMeta` from run directory
- [ ] Test: `test_expert_utilization_chart` -- `charts.expert_utilization(metrics)` returns valid figure (or empty figure if no MoE data)

## Implementation
- [ ] Step 1: Add stage indicator to Live Run tab in `dashboard.py`:
  ```python
  stage_indicator = gr.Textbox(value="Stage 1: Prompt Optimization",
                                label="Current Stage", interactive=False)
  ```
- [ ] Step 2: Add `training_loss()` chart to `charts.py`:
  ```python
  def training_loss(metrics: list[dict]) -> go.Figure:
      """Training loss curve for Stage 2 experiments."""
      # Extract training_loss from metrics (Stage 2 only)
      # Show trust_loss, reason_loss, escalate_loss, total_loss
  ```
- [ ] Step 3: Add `param_count_timeline()` chart to `charts.py`:
  ```python
  def param_count_timeline(metrics: list[dict]) -> go.Figure:
      """Parameter count over experiments (shows architecture changes)."""
  ```
- [ ] Step 4: Add `expert_utilization()` chart to `charts.py`:
  ```python
  def expert_utilization(metrics: list[dict]) -> go.Figure:
      """Expert utilization heatmap for MoE experiments."""
  ```
- [ ] Step 5: Add checkpoint management section to Run History tab:
  ```python
  # Checkpoint list with columns: experiment, composite, param_count, stage, path
  # Export buttons: PyTorch, GGUF
  ```
- [ ] Step 6: Update `poll_update()` to include stage indicator:
  - Read stage from run metadata or current `run_loop.py` state
- [ ] Step 7: Update `data_loader.py` to support Stage 2 metrics:
  - Stage 2 metrics include `training_loss`, `param_count`, `moe_config` in addition to existing fields
- [ ] Step 8: Conditionally show Stage 2 charts only when Stage 2 data exists
- [ ] DRY check: Reuse existing `_empty_figure()` helper for empty states; reuse `data_loader.load_run_metrics()` for both stages

## TDD: Tests Pass (Green)
- [ ] All new tests pass
- [ ] All existing dashboard tests still pass

## Acceptance Criteria
- [ ] Stage indicator shows current stage
- [ ] Training loss chart displays when Stage 2 metrics exist
- [ ] Parameter count timeline updates across experiments
- [ ] Checkpoint list shows available checkpoints with metadata
- [ ] Dashboard remains functional for Stage 1 only (backward compatible)
- [ ] No existing test is broken

## Execution
- **Agent Type**: coding subagent
- **Wave**: 5 (parallel with TASK_011; depends on Wave 4)
- **Complexity**: Medium
