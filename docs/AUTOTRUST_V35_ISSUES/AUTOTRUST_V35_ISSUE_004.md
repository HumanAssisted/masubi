# Issue 004: structlog not used anywhere despite being a dependency

## Severity
High

## Category
Omission

## Description
The PRD specifies "structlog with JSON output -- machine-parseable, greppable, no custom dashboards needed." `structlog` is listed as a dependency in `pyproject.toml` and installed, but it is never imported or configured in any source file. All modules use Python's standard `logging` module (`import logging; logger = logging.getLogger(__name__)`).

This means all log output is unstructured text, not machine-parseable JSON. The observability goals described in the PRD (structured JSON logs, greppable events, machine-parseable output) are not met.

## Evidence
- File: `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/config.py:6` -- `import logging`
- File: `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/observe.py:9` -- `import logging`
- File: `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/providers/__init__.py:14` -- `import logging`
- File: `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/data.py:15` -- `import logging`
- File: `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/eval.py:11` -- `import logging`
- PRD Requirement: INITIAL_DESIGN_CHOICES.md "Observability: Structured Logs + Run Artifacts" -- "structlog with JSON output"
- Task 012 Acceptance Criteria: "structlog configured with JSON output"

## Suggested Fix
1. In `autotrust/observe.py`, add structlog configuration:
   ```python
   import structlog
   structlog.configure(
       processors=[
           structlog.stdlib.add_log_level,
           structlog.processors.TimeStamper(fmt="iso"),
           structlog.processors.JSONRenderer(),
       ],
       wrapper_class=structlog.stdlib.BoundLogger,
       context_class=dict,
       logger_factory=structlog.stdlib.LoggerFactory(),
   )
   ```
2. Replace `import logging; logger = logging.getLogger(__name__)` with `import structlog; logger = structlog.get_logger()` in all modules.
3. Update `_log_call` and `_log_result` in `BaseProvider` to use structlog's bound logger pattern.

## Affected Files
- `autotrust/observe.py`
- `autotrust/config.py`
- `autotrust/eval.py`
- `autotrust/data.py`
- `autotrust/providers/__init__.py`
- `autotrust/providers/ollama.py` (indirect via BaseProvider)
- `autotrust/providers/hyperbolic.py`
- `autotrust/providers/anthropic.py`
- `train.py`
- `run_loop.py`

## Status: Fixed
Added `configure_structlog()` in `observe.py` with JSON output, ISO timestamps, and log level. Replaced `import logging; logger = logging.getLogger(__name__)` with `import structlog; logger = structlog.get_logger()` in all 8 modules. Ollama provider uses BaseProvider logging (unchanged). All 103 tests pass.
