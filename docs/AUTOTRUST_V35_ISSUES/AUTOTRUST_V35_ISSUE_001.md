# Issue 001: run_loop.py is a placeholder -- main orchestration loop is unimplemented

## Severity
Critical

## Category
Omission

## Description
The `run_loop.py` main loop (the core autoresearch orchestration) is fundamentally unimplemented. After building the agent prompt, the loop immediately `break`s on line 210 with a comment "Experiment loop requires LLM agent. Exiting placeholder loop." The system cannot run any experiments. Variables `_calibration`, `_gold_chains`, `_has_baseline`, `_prev_best_composite`, and `_prev_best_per_axis` are assigned but annotated `noqa: F841` (unused). The three-gate evaluation, git keep/discard, scoring, and cost tracking are never executed.

This is the single most critical missing piece -- without it, the entire system is non-functional as an autoresearch loop.

## Evidence
- File: `/Users/jonathan.hendler/personal/autoresearch-helpful/run_loop.py:206-210` -- loop breaks immediately with placeholder comment
- File: `/Users/jonathan.hendler/personal/autoresearch-helpful/run_loop.py:163-174` -- variables assigned with `noqa: F841` never used
- PRD Requirement: INITIAL_DESIGN_CHOICES.md "Plain Anthropic Tool-Use, Not Agent SDK" -- orchestration loop using direct `anthropic` library calls with tool-use
- Task 015 Acceptance Criteria: "Main loop calls all three gates in order", "Git keep/discard works correctly", "Budget and time limits enforced"

## Suggested Fix
1. In `run_loop.py`, implement the experiment loop body after the agent prompt is built:
   - Call Anthropic Sonnet via `get_provider("judge_primary", spec)` or a separate orchestration provider with tool-use to propose train.py edits
   - Apply the proposed edit to `train.py` by writing the file
   - Create an `EmailTrustScorer` from the modified train.py and score eval chains
   - Run `score_predictions()`, `compute_composite()`, `gold_regression_gate()`, `explanation_quality()`, `explanation_gate()`, and `keep_or_discard()`
   - Call `_handle_keep_discard()` based on the result
   - Track `total_cost`, `consecutive_no_improvement`, `prev_best_composite`, `prev_best_per_axis`
   - Call `log_experiment()` for each iteration
2. Remove the `break` statement and `noqa: F841` annotations.

## Affected Files
- `run_loop.py`
