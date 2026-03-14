# Task 006: Build providers/ Registry and Base Classes

## Context
The providers module implements a registry pattern with abstract base classes for each provider role (Generator, Scorer, Judge, Trainer) and a `get_provider()` factory function. Shared concerns (retry logic, structured logging, error normalization) live in a base class. The registry maps role strings to provider implementations based on spec.yaml config. See CURSOR_PLAN.md "Implementation Details > 5. providers/".

## Goal
Create the provider abstraction layer with base classes, shared retry/logging logic, and the registry factory function.

## Research First
- [ ] Read CURSOR_PLAN.md section "Implementation Details > 5. providers/"
- [ ] Read `autotrust/config.py` to understand Spec.providers structure
- [ ] Verify the four provider roles: generator, scorer, judge (primary/secondary), trainer

## TDD: Tests First (Red)
Write tests FIRST in `tests/test_providers.py`. They should FAIL before implementation.

### Unit Tests
- [ ] Test: `test_get_provider_generator` -- `get_provider("generator", spec)` returns a GeneratorProvider subclass -- in `tests/test_providers.py`
- [ ] Test: `test_get_provider_scorer` -- `get_provider("scorer", spec)` returns a ScoringProvider subclass -- in `tests/test_providers.py`
- [ ] Test: `test_get_provider_judge` -- `get_provider("judge_primary", spec)` returns a JudgeProvider subclass -- in `tests/test_providers.py`
- [ ] Test: `test_get_provider_trainer` -- `get_provider("trainer", spec)` returns a TrainingProvider subclass -- in `tests/test_providers.py`
- [ ] Test: `test_get_provider_unknown_role` -- `get_provider("unknown", spec)` raises ValueError -- in `tests/test_providers.py`
- [ ] Test: `test_base_provider_retry` -- retry decorator retries on transient errors up to max_retries -- in `tests/test_providers.py`

## Implementation
- [ ] Step 1: Create `autotrust/providers/__init__.py` with:
  - `BaseProvider(ABC)`: shared retry logic (configurable max_retries, backoff), structured logging via structlog, error normalization (wrap backend-specific errors in ProviderError)
  - `GeneratorProvider(BaseProvider)`: abstract methods `generate(prompt, **kwargs) -> str`, `generate_batch(prompts, concurrency=4) -> list[str]`, `check_available() -> bool`
  - `ScoringProvider(BaseProvider)`: abstract methods `score(prompt, **kwargs) -> str`, `score_batch(prompts, **kwargs) -> list[str]`
  - `JudgeProvider(BaseProvider)`: abstract methods `judge(chain, axes) -> dict`, `dual_judge(chain) -> tuple[dict, dict, float]`
  - `TrainingProvider(BaseProvider)`: abstract methods `list_gpus() -> list`, `rent_gpu(hours, name) -> str`, `stop_gpu(instance_id) -> None`, `get_status(instance_id) -> dict`, `run_remote(instance_id, command) -> str`, `budget_guard(max_usd) -> ContextManager`, `yarn_extend_context(base_model, target_ctx, steps) -> str`
  - `ProviderError(Exception)`: base exception for all provider errors
  - `get_provider(role: str, spec: Spec) -> BaseProvider`: factory that maps role + spec.providers config to concrete provider classes
- [ ] Step 2: Implement retry decorator with exponential backoff (base=1s, max=30s, max_retries=3)
- [ ] Step 3: Implement structured logging mixin using structlog (log method name, latency, success/failure)
- [ ] DRY check: no duplication with concrete provider implementations (ollama.py, hyperbolic.py, anthropic.py)

## TDD: Tests Pass (Green)
- [ ] All 6 unit tests pass
- [ ] All existing tests still pass

## Acceptance Criteria
- [ ] `autotrust/providers/__init__.py` contains all 4 abstract base classes + BaseProvider + get_provider()
- [ ] All abstract methods have correct signatures matching CURSOR_PLAN.md
- [ ] Retry logic is configurable and tested
- [ ] `get_provider()` maps role strings to correct concrete classes
- [ ] ProviderError exception class exists
- [ ] All tests in `tests/test_providers.py` pass

## Execution
- **Agent Type**: python
- **Wave**: 2 (depends on TASK_001 scaffold; parallel with TASK_004, TASK_005)
- **Complexity**: Medium
