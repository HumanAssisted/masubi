# Issue 007: Budget limit hardcoded to $5.00 in dashboard polling

## Severity
Medium

## Category
Bug

## Description
The `cost_burn` chart is called with `budget_limit=5.0` in both `poll_update()` (Live Run tab) and `opt_poll()` (Optimization tab). This value is hardcoded and does not reflect the actual budget configuration in `spec.yaml` (`limits.max_spend_usd`).

If the researcher configures a budget of $20 or $100, the cost burn chart will still show a budget line at $5.00, which is misleading and defeats the purpose of the gauge.

## Evidence
- File: `dashboard.py:85` -- `charts.cost_burn(metrics, budget_limit=5.0)`
- File: `dashboard.py:275` -- `charts.cost_burn([], budget_limit=5.0)` (in opt_poll empty case -- but this is the fallback)
- File: `spec.yaml` -- contains actual `limits.max_spend_usd` configuration
- PRD Requirement: Section 4.1 Row 1 -- "Cost burn gauge -- cumulative spend vs budget limit line"

## Suggested Fix
Read the budget limit from `spec.yaml` at app startup or from the RunManager:
```python
try:
    from autotrust.config import get_spec
    _budget_limit = get_spec().limits.max_spend_usd
except Exception:
    _budget_limit = 5.0  # fallback default
```
Then use `_budget_limit` in both `poll_update()` and `opt_poll()`.

## Affected Files
- `dashboard.py`

## Status: Fixed
Added `_budget_limit` module-level variable that reads `limits.max_spend_usd` from `spec.yaml` at startup using PyYAML, with a fallback default of $5.00. Both `poll_update()` and `opt_poll()` now use `_budget_limit` instead of hardcoded 5.0.
