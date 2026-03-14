# Issue 009: Retry decorator does not cover API-specific transient errors

## Severity
Medium

## Category
Bug

## Description
The `retry_on_error` decorator in `providers/__init__.py` only catches `(ConnectionError, TimeoutError, OSError)`. For API providers (Hyperbolic via OpenAI client, Anthropic), common transient errors include HTTP 429 (rate limit), 500, 502, 503 errors. These would manifest as `openai.RateLimitError`, `openai.APIStatusError`, `anthropic.RateLimitError`, `anthropic.InternalServerError`, or `httpx.HTTPStatusError`. None of these are retried, so a single rate-limit response from Hyperbolic or Anthropic would crash the scoring/judging call.

## Evidence
- File: `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/providers/__init__.py:49` -- `except (ConnectionError, TimeoutError, OSError) as exc:`
- PRD Requirement: INITIAL_DESIGN_CHOICES.md "Provider Registry Pattern" -- "Shared base class handles retry logic"
- PRD Requirement: INITIAL_REQUIREMENTS.md line 59 -- "Budget control: agent is instructed to never exceed $10 per experiment" (implies graceful handling of API issues)

## Suggested Fix
Expand the exception tuple to include API-specific transient errors:
```python
TRANSIENT_ERRORS = (ConnectionError, TimeoutError, OSError)
try:
    import openai
    TRANSIENT_ERRORS += (openai.RateLimitError, openai.APITimeoutError, openai.APIConnectionError)
except ImportError:
    pass
try:
    import anthropic
    TRANSIENT_ERRORS += (anthropic.RateLimitError, anthropic.InternalServerError, anthropic.APITimeoutError)
except ImportError:
    pass
try:
    import httpx
    TRANSIENT_ERRORS += (httpx.HTTPStatusError,)
except ImportError:
    pass
```
Or, accept a configurable `retryable_exceptions` parameter in the decorator.

## Affected Files
- `autotrust/providers/__init__.py`

## Status: Fixed
Added `_build_transient_errors()` that dynamically includes openai, anthropic, and httpx error types when available. The `TRANSIENT_ERRORS` tuple is built at import time. All provider tests pass.
