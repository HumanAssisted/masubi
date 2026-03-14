# Issue 012: Conditional assertion in test_smoke_explanation_gate_mode_blocks

## Severity
Low

## Category
Test Gap

## Description
In `tests/test_smoke.py`, the test `test_smoke_explanation_gate_mode_blocks` has a conditional assertion on line 265:
```python
if expl_quality_val < spec.explanation.min_quality_threshold:
    assert expl_ok is False
```
If the condition is false (quality happens to be above threshold), the test does not assert anything about the blocking behavior. A test should always assert its expected outcome unconditionally. The DummyScorer with empty reasons should always produce quality < 0.5 when predictions have scores above the flag threshold, but the test does not verify this.

## Evidence
- File: `/Users/jonathan.hendler/personal/autoresearch-helpful/tests/test_smoke.py:264-265` -- conditional assertion
- Task 016 spec: "test_smoke_explanation_gate_mode_blocks -- after baseline, bad explanation quality -> verify discard"

## Suggested Fix
Remove the conditional and assert both the quality and the gate result:
```python
# DummyScorer with empty reasons + predictions with scores > 0.5 -> quality should be < 0.5
assert expl_quality_val < spec.explanation.min_quality_threshold, (
    f"Expected quality < {spec.explanation.min_quality_threshold}, got {expl_quality_val}"
)
assert expl_ok is False
```
If the DummyScorer's fixed scores don't guarantee some axes above threshold, adjust the DummyScorer `trust_vector` to ensure at least some axes are above 0.5.

## Affected Files
- `tests/test_smoke.py`
