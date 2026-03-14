# Issue 007: dual_judge secondary call lacks retry logic and has DRY violation

## Severity
Medium

## Category
DRY Violation

## Description
In `anthropic.py`, the `dual_judge()` method calls `self.judge()` for the primary model (which uses the `@retry_on_error` decorator), but manually constructs a separate API call for the secondary model (lines 101-113) without going through any retry-decorated method. The secondary call duplicates the API call logic from `judge()` but without retry protection, error handling, or logging.

Additionally, `dual_judge()` calls `get_spec()` from the global singleton to get axis names, which couples it to global state rather than accepting axes as a parameter.

## Evidence
- File: `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/providers/anthropic.py:98` -- primary call: `self.judge(chain, axes)` (has retry)
- File: `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/providers/anthropic.py:101-113` -- secondary call: raw `client.messages.create()` (no retry, duplicate logic)
- File: `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/providers/anthropic.py:94` -- `from autotrust.config import get_spec` (global state coupling)
- PRD Requirement: INITIAL_DESIGN_CHOICES.md "Provider Registry Pattern" -- "Shared base class handles retry logic, structured logging, error normalization -- written once, tested once"

## Suggested Fix
1. Extract a `_judge_with_model(self, chain, axes, model)` private method that handles the API call, parsing, and normalization. Apply the retry decorator to this method.
2. Have both `judge()` and `dual_judge()` call `_judge_with_model()` with the appropriate model name.
3. Accept `axes` as a parameter to `dual_judge()` instead of fetching from global state:
   ```python
   def dual_judge(self, chain: Any, axes: list[str] | None = None) -> tuple[...]:
       if axes is None:
           from autotrust.config import get_spec
           axes = [a.name for a in get_spec().trust_axes]
   ```

## Affected Files
- `autotrust/providers/anthropic.py`

## Status: Fixed
Extracted `_judge_with_model()` private method with retry decorator. Both `judge()` and `dual_judge()` now delegate to it. `dual_judge()` accepts optional `axes` parameter, falling back to spec only when not provided. All tests pass.
