# Task 008: run_loop.py -- Stage CLI, Auto-Transition, Stage 2 Subprocess Mode

## Context
The REDESIGN_AUTOSEARCH_TRD requires `run_loop.py` to support two stages of operation: Stage 1 (prompt optimization, current behavior) and Stage 2 (student model training). The loop needs:

1. A `--stage` CLI argument to select the stage
2. Auto-transition from Stage 1 to Stage 2 after 3 consecutive no-improvement (or manual trigger)
3. Stage 2 mode that executes `train.py` as a subprocess (like original autoresearch) instead of importing it
4. Per-stage time limits from spec.yaml
5. Integration with `freeze.py` for the stage handoff

Currently, `run_loop.py` only supports Stage 1. It imports `EmailTrustScorer` from `train.py` and calls `score_batch()`. The handoff trigger (3 consecutive no-improvement) already exists as `consecutive_no_improvement` but only nudges toward LoRA.

## Goal
Add stage-aware orchestration to `run_loop.py` with CLI control, auto-transition, and Stage 2 subprocess execution.

## Research First
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/run_loop.py` (full current implementation)
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/docs/REDESIGN_AUTOSEARCH.md` lines 47-49 (handoff trigger)
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/docs/REDESIGN_AUTOSEARCH.md` lines 66-113 (Stage 2 spec)
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/freeze.py` -- `freeze_teacher()` from TASK_004
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/export.py` -- checkpoint handling from TASK_005
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/tests/test_run_loop.py` (existing test patterns)

## TDD: Tests First (Red)

### Unit Tests
- [ ] Test: `test_cli_stage_argument` in `tests/test_stage_transition.py` -- parsing `--stage train` sets stage to "train"
- [ ] Test: `test_cli_default_stage` -- no `--stage` defaults to "prompt"
- [ ] Test: `test_auto_transition_triggers` -- after 3 consecutive no-improvement with `--stage prompt`, triggers freeze + transition
- [ ] Test: `test_auto_transition_calls_freeze` -- auto-transition calls `freeze_teacher()`
- [ ] Test: `test_stage2_runs_subprocess` -- Stage 2 mode calls `subprocess.run(["uv", "run", "python", "train.py"])` instead of importing
- [ ] Test: `test_stage2_time_limit` -- Stage 2 uses `stage2_experiment_minutes` from spec
- [ ] Test: `test_stage1_time_limit` -- Stage 1 uses `stage1_experiment_minutes` (or `experiment_minutes` fallback)
- [ ] Test: `test_stage2_scoring_uses_checkpoint` -- Stage 2 evaluation loads student model checkpoint, not LLM API
- [ ] Test: `test_handoff_rewrites_train_py` -- at transition, `train.py` is archived and replaced with Stage 2 template
- [ ] Test: `test_manual_stage_train_skips_stage1` -- `--stage train` goes directly to Stage 2

### Integration Tests (in `tests/test_stage_transition.py`)
- [ ] Test: `test_stage_transition_end_to_end` -- mock Stage 1 completion, verify freeze artifacts exist, verify Stage 2 starts

## Implementation
- [ ] Step 1: Add `argparse` CLI to `run_loop.py`:
  ```python
  parser = argparse.ArgumentParser()
  parser.add_argument("--stage", choices=["prompt", "train"], default="prompt")
  parser.add_argument("--max-experiments", type=int, default=50)
  ```
- [ ] Step 2: Refactor `run_autoresearch()` to accept `stage` parameter:
  ```python
  def run_autoresearch(
      max_experiments: int = 50,
      stage: str = "prompt",
      stop_check=None,
      pause_check=None,
  ) -> None:
  ```
- [ ] Step 3: Extract Stage 1 logic into `_run_stage1_iteration()`:
  - Current experiment loop body (agent call, score via import, three-gate eval)
  - No functional changes, just extraction for clarity
- [ ] Step 4: Implement `_run_stage2_iteration()`:
  ```python
  def _run_stage2_iteration(experiment_num, spec, run_ctx, ...):
      """Stage 2: run train.py as subprocess, evaluate checkpoint."""
      # 1. Call agent to propose train.py edits (same as Stage 1)
      # 2. Run train.py as subprocess: subprocess.run(["uv", "run", "python", "train.py"])
      # 3. Load resulting checkpoint
      # 4. Score eval chains using student model
      # 5. Three-gate evaluation (same policy)
      # 6. Git keep/discard
  ```
- [ ] Step 5: Implement auto-transition logic:
  ```python
  if stage == "prompt" and consecutive_no_improvement >= 3:
      logger.info("Auto-transitioning to Stage 2...")
      from autotrust.freeze import freeze_teacher
      freeze_teacher(spec)
      _archive_train_py()  # git-safe archive of Stage 1 train.py
      _write_stage2_train_py_template()
      stage = "train"
  ```
- [ ] Step 6: Implement per-stage time limits:
  ```python
  def _get_time_limit(spec, stage):
      if stage == "train" and spec.stage2:
          return getattr(spec.limits, "stage2_experiment_minutes",
                        spec.limits.experiment_minutes)
      return getattr(spec.limits, "stage1_experiment_minutes",
                    spec.limits.experiment_minutes)
  ```
- [ ] Step 7: Update `_build_agent_prompt()` to include stage-specific instructions:
  - Stage 1: current prompt (prompt optimization)
  - Stage 2: include `program.md` Stage 2 instructions, model architecture constraints from spec.yaml
- [ ] DRY check: Three-gate evaluation (`keep_or_discard()`) is stage-agnostic -- do not duplicate; reuse `_handle_keep_discard()`

## TDD: Tests Pass (Green)
- [ ] All new tests in `test_stage_transition.py` pass
- [ ] All existing tests in `test_run_loop.py` still pass
- [ ] `run_autoresearch()` without `--stage` argument works identically to current behavior

## Acceptance Criteria
- [ ] `uv run python run_loop.py` runs Stage 1 (backward compatible)
- [ ] `uv run python run_loop.py --stage train` runs Stage 2
- [ ] Auto-transition fires after 3 consecutive no-improvement in Stage 1
- [ ] `freeze_teacher()` is called at transition
- [ ] Stage 2 runs `train.py` as subprocess
- [ ] Three-gate policy works for both stages
- [ ] Per-stage time limits are respected
- [ ] No existing test is broken

## Execution
- **Agent Type**: coding subagent
- **Wave**: 4 (parallel with TASK_009; depends on Wave 3)
- **Complexity**: High
