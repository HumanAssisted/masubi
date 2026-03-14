# Task 016: Smoke Tests -- End-to-End Verification

## Context
Smoke tests verify the entire system works end-to-end with minimal data: 10-chain eval set, 10-chain gold set, 1 full loop cycle with a dummy train.py. They verify the three-gate keep/discard logic, explanation gate modes (warn vs gate), and structured explanation output validation. These are the final integration tests before the system is ready for real use. See CURSOR_PLAN.md "Test Strategy > Smoke tests".

## Goal
Create end-to-end smoke tests that validate the complete autoresearch pipeline with synthetic minimal data.

## Research First
- [ ] Read CURSOR_PLAN.md section "Test Strategy > Smoke tests"
- [ ] Read all source files: config.py, schemas.py, eval.py, observe.py, train.py, run_loop.py
- [ ] Read existing unit test files to understand test patterns and fixtures
- [ ] Understand the three-gate logic flow end-to-end

## TDD: Tests First (Red)
Write tests FIRST. They should FAIL before implementation (some will pass after prior tasks).

### Integration Tests
- [ ] Test: `test_smoke_eval_10_chains` -- create 10 synthetic chains, score them with a dummy scorer, run score_predictions, verify per-axis metrics are computed for all axes -- in `tests/test_smoke.py`
- [ ] Test: `test_smoke_gold_10_chains` -- create 10 gold chains with known labels, run gold_regression_gate, verify pass/fail logic -- in `tests/test_smoke.py`
- [ ] Test: `test_smoke_full_loop_cycle` -- mock providers, run 1 iteration of run_loop, verify:
  - train.py is read
  - Scoring produces ScorerOutput
  - Three gates are evaluated
  - Git keep/discard is called
  - Experiment is logged
  -- in `tests/test_smoke.py`
- [ ] Test: `test_smoke_keep_all_gates_pass` -- with a dummy scorer that improves composite, passes gold, and has good explanations -> verify keep -- in `tests/test_smoke.py`
- [ ] Test: `test_smoke_discard_gold_veto` -- with a dummy scorer that improves composite but degrades one gold axis -> verify discard -- in `tests/test_smoke.py`
- [ ] Test: `test_smoke_explanation_warn_mode` -- before baseline, explanation gate warns but passes -> verify keep (if other gates pass) -- in `tests/test_smoke.py`
- [ ] Test: `test_smoke_explanation_gate_mode_blocks` -- after baseline, bad explanation quality -> verify discard -- in `tests/test_smoke.py`
- [ ] Test: `test_smoke_structured_output_validation` -- verify ScorerOutput with valid trust_vector and explanation.reasons passes validation -- in `tests/test_smoke.py`
- [ ] Test: `test_smoke_structured_output_invalid` -- verify ScorerOutput with missing axis in trust_vector fails validation -- in `tests/test_smoke.py`

## Implementation
- [ ] Step 1: Create test fixtures in `tests/test_smoke.py`:
  - `make_dummy_chain(chain_id, **axis_scores)` -- creates EmailChain with given scores
  - `make_dummy_gold_chain(chain_id, **consensus_labels)` -- creates GoldChain
  - `DummyScorer` -- returns fixed ScorerOutput for testing
  - `make_eval_set(n=10)` -- generates n diverse chains
  - `make_gold_set(n=10)` -- generates n gold chains with known labels
- [ ] Step 2: Implement each test using fixtures and mocked providers
- [ ] Step 3: Ensure tests use `tmp_path` for run artifacts (don't pollute real runs/)
- [ ] DRY check: reuse fixtures across tests, don't duplicate chain creation logic

## TDD: Tests Pass (Green)
- [ ] All 9 smoke tests pass
- [ ] All existing tests still pass

## Acceptance Criteria
- [ ] `tests/test_smoke.py` exists with all 9 tests
- [ ] Tests use minimal data (10 chains each)
- [ ] Full loop cycle test validates all three gates
- [ ] Explanation gate modes (warn/gate) tested
- [ ] Structured output validation tested
- [ ] Tests run in < 5 seconds (no real API calls)
- [ ] All tests pass

## Execution
- **Agent Type**: python
- **Wave**: 7 (depends on ALL prior tasks)
- **Complexity**: Medium
