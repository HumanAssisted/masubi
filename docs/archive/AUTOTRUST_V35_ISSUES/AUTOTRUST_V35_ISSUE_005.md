# Issue 005: composite_penalties applied as flat constant, not based on actual FP rate

## Severity
High

## Category
Bug

## Description
In `eval.py`, `compute_composite()` applies composite penalties as flat constants (line 102-104). The penalty `false_positive_rate: -0.15` is added to the composite score unconditionally. This means every experiment gets a -0.15 penalty regardless of its actual false positive rate.

The PRD describes composite penalties as including a "false-positive penalty" and the gate "includes false-positive penalty." The penalty should scale with the actual false positive rate of the predictions, not be a fixed constant. As implemented, the penalty is neither informative (it's the same for all experiments) nor corrective (it doesn't penalize worse FP rates more).

## Evidence
- File: `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/eval.py:101-104` -- `for penalty_value in spec.composite_penalties.values(): composite += penalty_value`
- PRD Requirement: INITIAL_DESIGN_CHOICES.md "Three-Gate Keep/Discard Policy" -- "Gate 1: composite improved (includes false-positive penalty)"
- spec.yaml line 44: `false_positive_rate: -0.15`

## Suggested Fix
Change `compute_composite()` to accept the actual false positive rate and apply the penalty proportionally:
```python
def compute_composite(
    per_axis: dict[str, float],
    spec: Spec,
    calibration: CalibrationReport,
    fp_rate: float = 0.0,
) -> float:
    ...
    # Apply composite penalties proportionally
    fp_penalty_weight = spec.composite_penalties.get("false_positive_rate", 0.0)
    composite += fp_penalty_weight * fp_rate
    return composite
```
This way, the -0.15 acts as a weight on the actual FP rate. An experiment with 0% FP rate gets no penalty, while one with 100% FP rate gets -0.15.

Update callers to pass `fp_rate` computed from predictions vs ground truth.

## Affected Files
- `autotrust/eval.py`
- `run_loop.py` (caller)
- `tests/test_composite_metric.py`

## Status: Fixed
Changed `compute_composite()` to accept `fp_rate: float = 0.0` parameter and apply penalty weight proportionally (`fp_penalty_weight * fp_rate`). Updated tests to verify proportional penalty application. All tests pass.
