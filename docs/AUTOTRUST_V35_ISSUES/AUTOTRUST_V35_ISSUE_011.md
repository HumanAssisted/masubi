# Issue 011: gold_regression_gate duplicates metric dispatch logic from score_predictions

## Severity
Medium

## Category
DRY Violation

## Description
In `eval.py`, `gold_regression_gate()` (lines 120-127) reimplements the same metric dispatch logic (binary -> F1, continuous+recall -> recall, else -> agreement) that `score_predictions()` already implements (lines 74-82). The dispatch logic is duplicated rather than delegated.

If the dispatch logic needs to change (e.g., adding a new metric type), it would need to be updated in two places, risking inconsistency.

## Evidence
- File: `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/eval.py:120-127` -- inline dispatch in gold_regression_gate
- File: `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/eval.py:74-82` -- same dispatch in score_predictions
- PRD Requirement: INITIAL_DESIGN_CHOICES.md "Simplicity as a Design Goal" -- no duplicated logic

## Suggested Fix
Refactor `gold_regression_gate()` to call `score_predictions()` for its per-axis metric computation:
```python
def gold_regression_gate(predictions, gold_set, previous_best, spec):
    current_performance = score_predictions(predictions, gold_set, spec)
    deltas = {}
    passed = True
    for axis in spec.trust_axes:
        prev = previous_best.get(axis.name, 0.0)
        curr = current_performance.get(axis.name, 0.0)
        delta = curr - prev
        deltas[axis.name] = delta
        if delta < -1e-9:
            passed = False
    return passed, deltas
```

## Affected Files
- `autotrust/eval.py`
