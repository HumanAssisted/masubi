# Issue 013: README references non-existent test file tests/test_eval.py

## Severity
Low

## Category
Quality

## Description
The README.md suggests running `uv run pytest tests/test_eval.py -v` as an example of running a specific test file. However, `tests/test_eval.py` does not exist. The eval-related tests are distributed across five separate files: `test_composite_metric.py`, `test_gold_gate.py`, `test_explanation_gate.py`, `test_escalation_rules.py`, and `test_kappa_downweight.py`.

## Evidence
- File: `/Users/jonathan.hendler/personal/autoresearch-helpful/README.md:59` -- `uv run pytest tests/test_eval.py -v`
- Actual test files: `tests/test_composite_metric.py`, `tests/test_gold_gate.py`, `tests/test_explanation_gate.py`, `tests/test_escalation_rules.py`, `tests/test_kappa_downweight.py`

## Suggested Fix
Update the README example to reference an actual test file:
```bash
# Run specific test file
uv run pytest tests/test_composite_metric.py -v
```

## Affected Files
- `README.md`

## Status: Fixed
Changed `tests/test_eval.py` reference to `tests/test_composite_metric.py` which is an actual test file.
