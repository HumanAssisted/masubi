# Task 015: Build run_loop.py -- Thin Orchestration

## Context
`run_loop.py` is the thin orchestrator that drives the autoresearch loop. It loads spec and calibration, starts a run context, and iterates: call Sonnet with program.md + train.py + last N results, apply proposed edits, score eval chains via train.py, run three-gate evaluation (composite, gold veto, explanation gate), keep/discard via git, and log everything. It enforces budget/time limits and nudges toward LoRA after 3 consecutive no-improvement runs. See CURSOR_PLAN.md "Implementation Details > 10. run_loop.py".

## Goal
Build the complete autoresearch loop orchestrator that ties all modules together.

## Research First
- [ ] Read CURSOR_PLAN.md section "Implementation Details > 10. run_loop.py" (the full pseudocode)
- [ ] Read `autotrust/config.py` for get_spec(), load calibration
- [ ] Read `autotrust/eval.py` for score_predictions(), compute_composite(), gold_regression_gate(), explanation_quality(), explanation_gate(), keep_or_discard()
- [ ] Read `autotrust/observe.py` for start_run(), log_experiment(), finalize_run()
- [ ] Read `train.py` for EmailTrustScorer interface
- [ ] Read `autotrust/schemas.py` for ExperimentResult, ScorerOutput
- [ ] Read spec.yaml `limits` for experiment_minutes and max_spend_usd

## TDD: Tests First (Red)
Write tests FIRST. They should FAIL before implementation.

### Unit Tests
- [ ] Test: `test_loop_enforces_time_limit` -- loop exits when wall time exceeds experiment_minutes -- in `tests/test_run_loop.py`
- [ ] Test: `test_loop_enforces_budget_limit` -- loop exits when cost exceeds max_spend_usd -- in `tests/test_run_loop.py`
- [ ] Test: `test_loop_keep_commits_train_py` -- when all three gates pass, train.py is committed via git -- in `tests/test_run_loop.py`
- [ ] Test: `test_loop_discard_restores_train_py` -- when any gate fails, train.py is restored via git checkout -- in `tests/test_run_loop.py`
- [ ] Test: `test_loop_nudges_lora_after_stalls` -- after 3 consecutive no-improvement, the agent prompt includes LoRA nudge -- in `tests/test_run_loop.py`
- [ ] Test: `test_loop_logs_each_experiment` -- each iteration calls observe.log_experiment() -- in `tests/test_run_loop.py`

## Implementation
- [ ] Step 1: Create `run_loop.py` at project root with main orchestration function:
  ```python
  def run_autoresearch(max_experiments: int = 50):
      spec = get_spec()
      calibration = load_calibration()
      run_ctx = start_run(spec)
      has_baseline = False
      prev_best_composite = 0.0
      prev_best_per_axis = {}
      consecutive_no_improvement = 0
      ...
  ```
- [ ] Step 2: Implement the main loop:
  - Read `program.md` and current `train.py`
  - Build agent prompt with program.md + train.py + last N ExperimentResults
  - If consecutive_no_improvement >= 3: add LoRA nudge to prompt
  - Call Anthropic Sonnet (via providers) with tool-use for editing train.py
  - Apply proposed edit to train.py
- [ ] Step 3: Implement scoring and evaluation:
  - Load eval chains from eval_set/
  - Load gold chains from gold_set/
  - Create EmailTrustScorer from modified train.py
  - Score all eval chains: `outputs = scorer.score_batch(eval_chains)`
  - Compute per-axis metrics: `metrics = eval.score_predictions(outputs, ground_truth, spec)`
  - Compute composite: `composite = eval.compute_composite(metrics, spec, calibration)`
  - Run gold gate: `gold_ok, gold_deltas = eval.gold_regression_gate(outputs, gold_set, prev_best_per_axis, spec)`
  - Compute explanation quality: `expl_quality = eval.explanation_quality([o.explanation for o in outputs], outputs, spec)`
  - Run explanation gate: `expl_ok, expl_mode = eval.explanation_gate(expl_quality, spec, has_baseline)`
  - Decide: `keep = eval.keep_or_discard(composite > prev_best_composite, gold_ok, expl_ok)`
- [ ] Step 4: Implement keep/discard:
  - If keep: `git add train.py && git commit -m "experiment N: composite +X%"`, update prev_best, has_baseline = True, reset consecutive_no_improvement
  - If discard: `git checkout -- train.py`, increment consecutive_no_improvement
- [ ] Step 5: Implement logging:
  - Build ExperimentResult with all data
  - Call `observe.log_experiment(run_ctx, result)`
- [ ] Step 6: Implement limit enforcement:
  - Check wall time against spec.limits.experiment_minutes
  - Track accumulated cost against spec.limits.max_spend_usd
  - Exit loop when either exceeded
- [ ] Step 7: Implement finalization:
  - Call `observe.finalize_run(run_ctx)` after loop exits
- [ ] Step 8: Add CLI entry point: `if __name__ == "__main__": run_autoresearch()`
- [ ] DRY check: all evaluation logic delegated to eval.py, all logging to observe.py, no reimplementation

## TDD: Tests Pass (Green)
- [ ] All 6 unit tests pass (using mocked providers and eval functions)
- [ ] All existing tests still pass

## Acceptance Criteria
- [ ] `run_loop.py` exists at project root
- [ ] Main loop calls all three gates in order
- [ ] Git keep/discard works correctly
- [ ] Budget and time limits enforced
- [ ] LoRA nudge triggers after 3 stalls
- [ ] Each experiment is logged via observe.py
- [ ] Run is finalized with summary
- [ ] All tests pass

## Execution
- **Agent Type**: python
- **Wave**: 6 (depends on TASK_010-013 -- all core modules)
- **Complexity**: High
