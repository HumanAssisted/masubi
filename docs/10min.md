# Masubi 10-Minute End-to-End Plan

Date: 2026-03-14

This is now an execution document, not just a diagnosis list. Deferred architecture and ML review still lives in `docs/GPT_REVIEW.md`.

## Goal

Get one real end-to-end workflow working:

1. Stage 1 edits `train.py`
2. The edited scorer is actually evaluated
3. The gold gate runs on the gold set without crashing
4. Stage 1 -> Stage 2 handoff creates labeled training data
5. Stage 2 trains a real dense baseline checkpoint
6. Stage 2 emits dashboard-friendly metrics
7. The checkpoint can be exported and scored locally

## TDD Build Order

Build in this order and keep the loop green after each step:

1. Add a test that proves Stage 1 loads `EmailTrustScorer` from `train.py`, not `starting_train.py`.
2. Add a test that gold truth extraction prefers `consensus_labels`.
3. Add a test that Stage 2 uses raw axis names for reason tags so Gate 3 can pass.
4. Add a test that auto-transition relabels training data before Stage 2 starts.
5. Add a test that the generated Stage 2 template really trains and writes `training_metrics.json`.
6. Add a test that `_run_stage2_iteration(...)` surfaces `training_loss` and `param_count`.
7. Add a test that `load_eval_chains(limit=N)` honors the demo cap.
8. Add a test that MoE expert utilization can be collected for dashboard logging.
9. Run the targeted suite after each change, not only at the end.

## Built In This Pass

### 1. Stage 1 now evaluates the mutable working copy

What changed:
- `run_loop.py` now dynamically loads `EmailTrustScorer` from `train.py`.
- `starting_train.py` remains the seed template, but it is no longer the file being silently evaluated during Stage 1.

Where:
- `run_loop.py:106-131`
- `run_loop.py:742-755`

Why it was useful:
- this was the highest-value fix
- without it, the optimization loop was fake

### 2. Gold scoring is now separate from eval scoring

What changed:
- gold records are loaded as raw records
- the loop extracts truth from `consensus_labels`
- gold chains are scored separately
- the loop keeps a separate `prev_best_gold_per_axis` baseline

Where:
- `run_loop.py:92-152`
- `run_loop.py:774-820`
- `run_loop.py:847-851`

Why it was useful:
- this removed the real 1000-vs-200 sample-count crash
- it also fixed the hidden bookkeeping bug where eval metrics and gold metrics were mixed

### 3. Stage 2 reason tags now match the explanation gate contract

What changed:
- Stage 2 now uses raw axis names as reason tags instead of `*_flagged`

Where:
- `run_loop.py:317-325`
- `autotrust/inference.py:100-111`

Why it was useful:
- this makes Gate 3 meaningful for Stage 2 instead of structurally unfair

### 4. Auto-transition now relabels training data

What changed:
- `_auto_transition(...)` now calls `relabel_training_data(...)`
- relabeling now loads the live Stage 1 scorer instead of hardcoding `starting_train.py`

Where:
- `run_loop.py:191-214`
- `autotrust/freeze.py`

Why it was useful:
- this made the Stage 1 -> Stage 2 handoff real instead of partial

### 5. Stage 2 has a real dense-baseline trainer now

What changed:
- added `starting_train_stage2.py`
- the generated Stage 2 `train.py` now trains a compact dense baseline
- it writes `best.pt` and `training_metrics.json`

Where:
- `starting_train_stage2.py:1-203`
- `run_loop.py:345-363`

Why it was useful:
- this was the best observability/performance tradeoff after the core correctness fixes
- the dashboard can now show real Stage 2 loss curves and parameter counts

### 6. Stage 2 metrics now flow into run artifacts

What changed:
- `_run_stage2_iteration(...)` reads `training_metrics.json`
- `ExperimentResult` now has optional Stage 2 fields
- `observe.log_experiment(...)` omits `None` fields so Stage 1 runs are not mislabeled as Stage 2

Where:
- `run_loop.py:354-364`
- `run_loop.py:464-475`
- `run_loop.py:868-890`
- `autotrust/schemas.py`
- `autotrust/observe.py:93-100`

Why it was useful:
- it lights up dashboard charts that already existed
- it gives us immediate feedback on whether Stage 2 is actually learning

### 7. Demo runs can now cap the eval set

What changed:
- added `--eval-limit`
- `load_eval_chains(limit=...)` now truncates at load time
- both Stage 1 and Stage 2 use the capped eval set when provided

Where:
- `run_loop.py`

Why it was useful:
- this is the cheapest real throughput improvement for short demo runs
- it reduces scoring time without changing the full-data default path

### 8. Tests no longer need the live repo `train.py`

What changed:
- run-loop tests now execute inside temp workspaces with copied templates
- the test contract is tied to `starting_train.py`, `starting_train_stage2.py`, or temp files, not the mutable repo root `train.py`

Why it was useful:
- we can run tests without rewriting the repo's working `train.py`
- it keeps the research file free to change during real runs

### 9. Expert-utilization logging is now real for MoE models

What changed:
- MoE blocks now record last expert-utilization estimates
- `starting_train_stage2.py` can collect and emit `expert_utilization` when the trained model is MoE
- `_run_stage2_iteration(...)` already passes that metric through to run artifacts

Where:
- `autotrust/student.py`
- `starting_train_stage2.py`
- `run_loop.py`

Why it was useful:
- the dashboard already knows how to render this
- we do not need full MoE search yet to make the metric path real

## What Proved Most Useful

Highest leverage:

1. Make Stage 1 evaluate `train.py`
2. Score the gold set separately
3. Emit Stage 2 `training_loss` and `param_count`

Best dashboard payoff:

1. `training_loss`
2. `param_count`
3. `expert_utilization` whenever the Stage 2 model switches to MoE

Best "still worth doing next":

1. Start using `log_predictions(...)`
2. Add gold per-axis deltas to logged metrics
3. Add phase timings (`agent_duration_sec`, `scoring_duration_sec`, `train_duration_sec`)
4. Consider a separate `--gold-limit` only if we explicitly want a relaxed demo mode

## Usefulness And Efficacy Check

What to keep:

- the TDD order above
- the dense-baseline-first approach
- Stage 2 metric logging

What not to over-invest in yet:

- parallel scoring before correctness and eval limiting
- MoE visualization before dense baseline is stable
- timeout handling as a substitute for throughput

## Verification

Targeted suites used during the build:

```bash
uv run pytest tests/test_run_loop.py -q
uv run pytest tests/test_stage_transition.py -q
uv run pytest tests/test_gold_gate.py tests/test_explanation_gate.py tests/test_inference.py tests/test_export.py tests/test_train.py tests/test_freeze.py tests/test_stage_transition.py tests/test_run_loop.py tests/test_observe.py tests/test_charts.py tests/test_dashboard_integration.py -q
```

Current result from the broad targeted pass:

- 117 passed

## Next Smallest Steps

If we keep going, do these next:

1. Call `log_predictions(...)` from the main loop.
2. Add `gold_deltas` and `failed_axes` to `ExperimentResult`.
3. Add timing fields so the dashboard can explain where the time went.
4. Decide whether demo mode also needs a separate gold-set cap.
