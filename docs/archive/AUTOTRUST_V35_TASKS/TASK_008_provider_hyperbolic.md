# Task 008: Build providers/hyperbolic.py -- HyperbolicScorer + HyperbolicTrainer

## Context
The Hyperbolic provider implements two roles: `ScoringProvider` for inference via OpenAI-compatible API, and `TrainingProvider` for GPU rental and remote training via the Hyperbolic Marketplace API. The scorer wraps `openai.OpenAI(base_url="https://api.hyperbolic.xyz/v1")`. The trainer uses `httpx` for GPU lifecycle management and includes a `BudgetGuard` context manager. See CURSOR_PLAN.md "Implementation Details > 5. providers/ > providers/hyperbolic.py".

## Goal
Implement scoring inference and GPU training lifecycle management via Hyperbolic APIs.

## Research First
- [ ] Read CURSOR_PLAN.md section on `providers/hyperbolic.py`
- [ ] Read `autotrust/providers/__init__.py` (TASK_006) for ScoringProvider and TrainingProvider interfaces
- [ ] Check OpenAI Python SDK API for `client.chat.completions.create()`
- [ ] Read spec.yaml `providers.scorer` and `providers.trainer` for model/GPU config
- [ ] Read spec.yaml `limits.max_spend_usd` for budget guard threshold

## TDD: Tests First (Red)
Write tests FIRST. They should FAIL before implementation.

### Unit Tests (all in `tests/test_providers.py`, using mocks)
- [ ] Test: `test_hyperbolic_scorer_returns_string` -- mock openai client, verify score() returns string -- in `tests/test_providers.py`
- [ ] Test: `test_hyperbolic_scorer_batch` -- mock openai client, verify score_batch() returns list[str] -- in `tests/test_providers.py`
- [ ] Test: `test_hyperbolic_scorer_uses_spec_model` -- verify HyperbolicScorer uses model from spec config -- in `tests/test_providers.py`
- [ ] Test: `test_hyperbolic_scorer_retry_on_error` -- mock client to fail then succeed, verify retry works -- in `tests/test_providers.py`
- [ ] Test: `test_hyperbolic_trainer_rent_gpu` -- mock httpx POST, verify rent_gpu returns instance_id -- in `tests/test_providers.py`
- [ ] Test: `test_hyperbolic_trainer_stop_gpu` -- mock httpx POST, verify stop_gpu calls correct endpoint -- in `tests/test_providers.py`
- [ ] Test: `test_hyperbolic_trainer_budget_guard_triggers` -- mock spend tracking, verify BudgetGuard raises at limit -- in `tests/test_providers.py`
- [ ] Test: `test_hyperbolic_trainer_budget_guard_auto_terminates` -- verify BudgetGuard calls stop_gpu on budget exceeded -- in `tests/test_providers.py`

## Implementation
- [ ] Step 1: Create `autotrust/providers/hyperbolic.py` with:

  **HyperbolicScorer(ScoringProvider):**
  - `__init__(self, model: str, api_key: str)`: create `openai.OpenAI(base_url="https://api.hyperbolic.xyz/v1", api_key=api_key)`
  - `score(self, prompt: str, **kwargs) -> str`: call `client.chat.completions.create(model=self.model, messages=[...])`, return content
  - `score_batch(self, prompts: list[str], **kwargs) -> list[str]`: sequential calls (can upgrade to async later)

  **BudgetGuard:**
  - Context manager that tracks accumulated spend
  - On `__enter__`: record start time, initialize spend counter
  - Track each API call's estimated cost
  - On spend exceeding `max_usd`: call stop_gpu on all active instances, raise BudgetExceededError
  - On `__exit__`: log total spend

  **HyperbolicTrainer(TrainingProvider):**
  - `__init__(self, api_key: str, gpu_type: str)`: create httpx client with auth header
  - `list_gpus(self) -> list`: GET /v1/marketplace/gpus
  - `rent_gpu(self, hours: int, name: str) -> str`: POST /v1/marketplace/instances, return instance_id
  - `stop_gpu(self, instance_id: str) -> None`: POST /v1/marketplace/instances/{id}/stop
  - `get_status(self, instance_id: str) -> dict`: GET /v1/marketplace/instances/{id}
  - `run_remote(self, instance_id: str, command: str) -> str`: SSH via API or subprocess
  - `budget_guard(self, max_usd: float) -> BudgetGuard`: return BudgetGuard context manager
  - `yarn_extend_context(self, base_model: str, target_ctx: int, steps: int) -> str`: generate YaRN training config

- [ ] Step 2: Register HyperbolicScorer and HyperbolicTrainer in `get_provider()` factory for backends "hyperbolic" and "hyperbolic_gpu"
- [ ] DRY check: retry and logging from BaseProvider, not re-implemented

## TDD: Tests Pass (Green)
- [ ] All 8 new tests pass
- [ ] All existing tests still pass

## Acceptance Criteria
- [ ] `autotrust/providers/hyperbolic.py` exists with both classes
- [ ] HyperbolicScorer implements all ScoringProvider abstract methods
- [ ] HyperbolicTrainer implements all TrainingProvider abstract methods
- [ ] BudgetGuard context manager auto-terminates GPUs at budget limit
- [ ] Both registered in `get_provider()` factory
- [ ] API key loaded from environment variable
- [ ] All tests pass

## Execution
- **Agent Type**: python
- **Wave**: 3 (depends on TASK_006 providers registry; parallel with TASK_007)
- **Complexity**: High
