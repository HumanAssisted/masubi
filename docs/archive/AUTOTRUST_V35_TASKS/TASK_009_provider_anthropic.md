# Task 009: Build providers/anthropic.py -- AnthropicJudge

## Context
The Anthropic provider implements `JudgeProvider` for LLM-based judging of email chain trust scores. It uses Claude Opus as the primary judge and Claude Sonnet as secondary. Key features: bias-mitigated prompting (position randomization, verbosity normalization) and dual-judge disagreement filtering. The judge evaluates per-axis trust scores and detects when fast-track scoring needs escalation. See CURSOR_PLAN.md "Implementation Details > 5. providers/ > providers/anthropic.py".

## Goal
Implement an Anthropic-based judge that provides per-axis trust scoring with bias mitigation and dual-judge agreement checking.

## Research First
- [ ] Read CURSOR_PLAN.md section on `providers/anthropic.py`
- [ ] Read `autotrust/providers/__init__.py` (TASK_006) for JudgeProvider interface
- [ ] Check `anthropic` Python SDK API: `client.messages.create()`
- [ ] Read spec.yaml `providers.judge_primary`, `providers.judge_secondary` for model names
- [ ] Read spec.yaml `judge` section for escalate_threshold and disagreement_max

## TDD: Tests First (Red)
Write tests FIRST. They should FAIL before implementation.

### Unit Tests (all in `tests/test_providers.py`, using mocks)
- [ ] Test: `test_anthropic_judge_returns_per_axis_scores` -- mock anthropic client, verify judge() returns dict with all spec axis names as keys -- in `tests/test_providers.py`
- [ ] Test: `test_anthropic_judge_scores_are_floats` -- verify all returned values are floats in [0, 1] -- in `tests/test_providers.py`
- [ ] Test: `test_anthropic_dual_judge_agreement` -- mock both models returning similar scores, verify agreement > 0.8 -- in `tests/test_providers.py`
- [ ] Test: `test_anthropic_dual_judge_disagreement` -- mock models returning divergent scores, verify disagreement detected -- in `tests/test_providers.py`
- [ ] Test: `test_anthropic_judge_uses_spec_models` -- verify primary and secondary models come from spec config -- in `tests/test_providers.py`

## Implementation
- [ ] Step 1: Create `autotrust/providers/anthropic.py` with class `AnthropicJudge(JudgeProvider)`:
  - `__init__(self, primary_model: str, secondary_model: str, api_key: str)`: create `anthropic.Anthropic(api_key=api_key)` client
  - `_build_judge_prompt(self, chain: EmailChain, axes: list[str]) -> str`: create bias-mitigated prompt:
    - Randomize axis presentation order
    - Normalize verbosity (fixed-length response format)
    - Request structured JSON output with per-axis scores
  - `judge(self, chain, axes: list[str]) -> dict`: call primary model, parse response into dict[str, float]
  - `dual_judge(self, chain) -> tuple[dict, dict, float]`: call primary then secondary, compute agreement as mean absolute difference across axes, return (primary_scores, secondary_scores, agreement)
- [ ] Step 2: Register AnthropicJudge in `get_provider()` factory for backend="anthropic"
- [ ] DRY check: retry and logging from BaseProvider, not re-implemented

## TDD: Tests Pass (Green)
- [ ] All 5 new tests pass
- [ ] All existing tests still pass

## Acceptance Criteria
- [ ] `autotrust/providers/anthropic.py` exists with AnthropicJudge class
- [ ] Implements all JudgeProvider abstract methods
- [ ] Bias mitigation: axis order randomized, response format normalized
- [ ] `dual_judge()` computes agreement metric
- [ ] Registered in `get_provider()` factory for "anthropic" backend
- [ ] API key loaded from environment variable
- [ ] All tests pass

## Execution
- **Agent Type**: python
- **Wave**: 3 (depends on TASK_006 providers registry; parallel with TASK_007, TASK_008)
- **Complexity**: Medium
