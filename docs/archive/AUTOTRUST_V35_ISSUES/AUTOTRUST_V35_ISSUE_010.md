# Issue 010: BudgetGuard does not auto-stop GPU instances on normal exit

## Severity
Medium

## Category
Bug

## Description
The `BudgetGuard` context manager in `hyperbolic.py` only stops GPU instances when the budget is exceeded (in `track_spend()`). On normal exit (`__exit__` without exception), it logs total spending but does not call `stop_gpu()` on any tracked instances. This means if a training run completes successfully within budget, the GPU instances continue running and accumulating charges.

The PRD explicitly requires: "BudgetGuard context manager auto-terminates GPU instances at $8 spend limit per experiment" and "If you rent GPUs, you MUST terminate them before finishing the experiment."

## Evidence
- File: `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/providers/hyperbolic.py:83-85` -- `__exit__` only logs, does not stop instances
- File: `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/providers/hyperbolic.py:66-77` -- instances only stopped in `track_spend()` when budget exceeded
- PRD Requirement: INITIAL_REQUIREMENTS.md line 59 -- "must call `hyperbolic gpu stop` at end"
- PRD Requirement: INITIAL_DESIGN_CHOICES.md "Hyperbolic for Scoring and Training" -- "BudgetGuard context manager auto-terminates GPU instances"

## Suggested Fix
In `BudgetGuard.__exit__`, stop all active instances regardless of whether the budget was exceeded:
```python
def __exit__(self, exc_type, exc_val, exc_tb) -> None:
    for instance_id in self.active_instances:
        try:
            self.trainer.stop_gpu(instance_id)
            logger.info("Stopped instance %s on exit", instance_id)
        except Exception as exc:
            logger.error("Failed to stop instance %s on exit: %s", instance_id, exc)
    logger.info("BudgetGuard: total spent $%.2f / $%.2f", self.total_spent, self.max_usd)
    return None
```

## Affected Files
- `autotrust/providers/hyperbolic.py`
- `tests/test_providers.py` (add test for auto-stop on normal exit)

## Status: Fixed
Added auto-stop loop in `BudgetGuard.__exit__()` that stops all active instances regardless of how the context exits. All tests pass.
