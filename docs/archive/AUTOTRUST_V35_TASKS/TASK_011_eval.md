# Task 011: Build eval.py -- Fixed Evaluation Policy

## Context
`eval.py` is the fixed evaluation module implementing the three-gate keep/discard policy: composite score improvement (Kappa-adjusted), gold-set veto (raw labels, no downweighting), and explanation gate (warn_then_gate mode). It auto-dispatches metric computation based on axis type from spec.yaml (binary -> F1, continuous -> agreement/recall). This is the core policy engine -- it must be correct and thoroughly tested. See CURSOR_PLAN.md "Implementation Details > 7. eval.py".

## Goal
Implement the complete evaluation policy with auto-dispatch, three-gate decision making, and explanation quality scoring.

## Research First
- [ ] Read CURSOR_PLAN.md section "Implementation Details > 7. eval.py"
- [ ] Read CURSOR_PLAN.md "Key Policy Decisions" for three-gate, Kappa downweighting, explanation quality
- [ ] Read `autotrust/config.py` for Spec, get_effective_weights()
- [ ] Read `autotrust/schemas.py` for ScorerOutput, Explanation, CalibrationReport, GoldChain
- [ ] Read spec.yaml `explanation` section for gate modes and thresholds
- [ ] Read spec.yaml `judge` section for escalation threshold

## TDD: Tests First (Red)
Write tests FIRST across multiple test files. They should FAIL before implementation.

### Unit Tests -- Composite Metric
- [ ] Test: `test_composite_binary_uses_f1` -- binary axis dispatches to F1 computation -- in `tests/test_composite_metric.py`
- [ ] Test: `test_composite_continuous_uses_agreement` -- continuous axis with metric=agreement dispatches correctly -- in `tests/test_composite_metric.py`
- [ ] Test: `test_composite_continuous_uses_recall` -- continuous axis with metric=recall dispatches correctly (deceit) -- in `tests/test_composite_metric.py`
- [ ] Test: `test_composite_formula_matches_weights` -- composite = sum(weight_i * metric_i) + penalties -- in `tests/test_composite_metric.py`
- [ ] Test: `test_composite_penalties_applied` -- false_positive_rate penalty reduces composite -- in `tests/test_composite_metric.py`
- [ ] Test: `test_composite_zero_weighted_axis` -- axis with weight 0.0 does not affect composite -- in `tests/test_composite_metric.py`

### Unit Tests -- Kappa Downweighting
- [ ] Test: `test_kappa_downweight_proportional` -- low Kappa axis gets proportionally lower weight -- in `tests/test_kappa_downweight.py`
- [ ] Test: `test_kappa_downweight_redistribution` -- lost weight redistributed to other axes -- in `tests/test_kappa_downweight.py`
- [ ] Test: `test_kappa_downweight_composite_only` -- downweighting applies to compute_composite() but NOT gold_regression_gate() -- in `tests/test_kappa_downweight.py`
- [ ] Test: `test_kappa_perfect_no_change` -- Kappa=1.0 for all axes means no weight change -- in `tests/test_kappa_downweight.py`

### Unit Tests -- Gold Gate
- [ ] Test: `test_gold_gate_passes_when_no_regression` -- no axis degrades -> passes -- in `tests/test_gold_gate.py`
- [ ] Test: `test_gold_gate_rejects_any_axis_regression` -- single axis degrades -> veto -- in `tests/test_gold_gate.py`
- [ ] Test: `test_gold_gate_uses_raw_labels` -- gold gate ignores Kappa downweighting -- in `tests/test_gold_gate.py`
- [ ] Test: `test_gold_gate_zero_weighted_axis_still_vetoes` -- verify_by_search (weight=0.0) regression still triggers veto -- in `tests/test_gold_gate.py`
- [ ] Test: `test_gold_gate_overrides_composite_improvement` -- composite improves but gold gate vetoes -> discard -- in `tests/test_gold_gate.py`

### Unit Tests -- Explanation Gate
- [ ] Test: `test_explanation_quality_all_flagged_referenced` -- all flagged axes in reasons -> quality=1.0 -- in `tests/test_explanation_gate.py`
- [ ] Test: `test_explanation_quality_partial_reference` -- 1 of 3 flagged axes referenced -> quality=0.33 -- in `tests/test_explanation_gate.py`
- [ ] Test: `test_explanation_quality_no_flags` -- no axes above threshold -> quality=1.0 -- in `tests/test_explanation_gate.py`
- [ ] Test: `test_explanation_gate_warn_mode` -- before baseline, logs but always passes -- in `tests/test_explanation_gate.py`
- [ ] Test: `test_explanation_gate_gate_mode_passes` -- after baseline, quality >= threshold -> passes -- in `tests/test_explanation_gate.py`
- [ ] Test: `test_explanation_gate_gate_mode_blocks` -- after baseline, quality < threshold -> blocks -- in `tests/test_explanation_gate.py`

### Unit Tests -- Escalation
- [ ] Test: `test_judge_escalation_subtle_axis_above_threshold` -- subtle axis score > escalate_threshold triggers judge fallback -- in `tests/test_escalation_rules.py`
- [ ] Test: `test_judge_escalation_fast_axis_no_escalation` -- fast axis high score does not trigger escalation -- in `tests/test_escalation_rules.py`
- [ ] Test: `test_judge_escalation_below_threshold` -- subtle axis below threshold does not trigger -- in `tests/test_escalation_rules.py`

### Unit Tests -- Keep/Discard
- [ ] Test: `test_keep_all_gates_pass` -- composite improved + gold ok + explanation ok -> keep -- in `tests/test_composite_metric.py`
- [ ] Test: `test_discard_composite_fails` -- composite not improved -> discard -- in `tests/test_composite_metric.py`
- [ ] Test: `test_discard_gold_fails` -- gold veto -> discard even if composite improved -- in `tests/test_composite_metric.py`
- [ ] Test: `test_discard_explanation_fails` -- explanation gate fails -> discard -- in `tests/test_composite_metric.py`

## Implementation
- [ ] Step 1: Create `autotrust/eval.py` with function `score_predictions(predictions, ground_truth, spec) -> dict`:
  - Iterate over spec.trust_axes
  - Dispatch: binary -> compute_f1(), continuous + recall -> compute_recall(), continuous + agreement -> compute_agreement()
  - Return dict[axis_name, score]
- [ ] Step 2: Implement `compute_f1(preds, truth, axis_name) -> float` using sklearn.metrics
- [ ] Step 3: Implement `compute_agreement(preds, truth, axis_name) -> float` (mean absolute agreement: 1 - mean|pred - truth|)
- [ ] Step 4: Implement `compute_recall(preds, truth, axis_name) -> float` using sklearn.metrics
- [ ] Step 5: Implement `compute_composite(per_axis: dict, spec: Spec, calibration: CalibrationReport) -> float`:
  - Get effective weights via config.get_effective_weights()
  - composite = sum(effective_weight[axis] * per_axis[axis] for axis in trust_axes)
  - Apply composite_penalties
  - Return final composite
- [ ] Step 6: Implement `gold_regression_gate(predictions, gold_set, previous_best, spec) -> tuple[bool, dict]`:
  - Compare per-axis scores against raw human consensus labels
  - NO Kappa downweighting
  - Check ALL axes including zero-weighted ones
  - Return (passed=True only if no axis degrades, per_axis_delta)
- [ ] Step 7: Implement `explanation_quality(explanations: list[Explanation], predictions: list, spec: Spec) -> float`:
  - For each chain: count axes scoring > flag_threshold
  - Check if explanation.reasons references each flagged axis
  - quality = correctly_referenced / flagged_count (1.0 if no flags)
  - Return mean across chains
- [ ] Step 8: Implement `explanation_gate(quality: float, spec: Spec, has_baseline: bool) -> tuple[bool, str]`:
  - If not has_baseline or not gate_after_baseline: return (True, "warn")
  - Else: return (quality >= min_quality_threshold, "gate")
- [ ] Step 9: Implement `keep_or_discard(composite_improved: bool, gold_ok: bool, explanation_ok: bool) -> bool`:
  - Return composite_improved and gold_ok and explanation_ok
- [ ] Step 10: Implement `run_judge_fallback(chain, fast_scores, judge: JudgeProvider, spec: Spec) -> dict`:
  - Check if any axis in axis_groups.subtle scores > escalate_threshold
  - If so, call judge.judge(chain, subtle_axes)
  - Merge judge scores with fast_scores
- [ ] DRY check: weight computation delegated to config.get_effective_weights(), not reimplemented

## TDD: Tests Pass (Green)
- [ ] All 29 unit tests pass across 5 test files
- [ ] All existing tests still pass

## Acceptance Criteria
- [ ] `autotrust/eval.py` exists with all listed functions
- [ ] Auto-dispatch correctly maps axis type -> metric function
- [ ] Three-gate logic correctly enforces all three gates
- [ ] Gold gate uses raw labels, never Kappa-adjusted
- [ ] Explanation quality computed correctly per specification
- [ ] Explanation gate respects warn_then_gate mode
- [ ] Judge escalation triggers for subtle axes above threshold
- [ ] All tests pass across all test files

## Execution
- **Agent Type**: python
- **Wave**: 4 (depends on TASK_004 config, TASK_005 schemas; parallel with TASK_010)
- **Complexity**: High
