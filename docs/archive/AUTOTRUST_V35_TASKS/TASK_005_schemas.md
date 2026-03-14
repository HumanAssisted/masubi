# Task 005: Build schemas.py -- Pydantic Data Models

## Context
`schemas.py` defines all the pydantic data models used across the system: Email, EmailChain, TrustVector (as dict[str, float] validated against spec), Explanation, ScorerOutput, ExperimentResult, RunArtifacts, GoldChain, and CalibrationReport. TrustVector is NOT a dynamic pydantic model -- it's a plain `dict[str, float]` with a validator that checks keys against spec.yaml axis names. See CURSOR_PLAN.md "Implementation Details > 4. schemas.py".

## Goal
Create validated data models that enforce the spec.yaml contract at construction time, ensuring data consistency across all modules.

## Research First
- [ ] Read CURSOR_PLAN.md section "Implementation Details > 4. schemas.py"
- [ ] Read `autotrust/config.py` (TASK_004) to understand the Spec model and `get_spec()`
- [ ] Understand TrustVector design decision: dict[str, float] validated against spec, NOT dynamic pydantic model

## TDD: Tests First (Red)
Write tests FIRST in `tests/test_schema_validation.py`. They should FAIL before implementation.

### Unit Tests
- [ ] Test: `test_trust_vector_valid_keys` -- dict with all spec axis names accepted -- in `tests/test_schema_validation.py`
- [ ] Test: `test_trust_vector_rejects_unknown_key` -- dict with key not in spec raises ValidationError -- in `tests/test_schema_validation.py`
- [ ] Test: `test_trust_vector_rejects_missing_key` -- dict missing a spec axis raises ValidationError -- in `tests/test_schema_validation.py`
- [ ] Test: `test_trust_vector_rejects_non_float` -- dict with non-float value raises ValidationError -- in `tests/test_schema_validation.py`
- [ ] Test: `test_email_chain_round_trip` -- EmailChain serializes to JSON and deserializes back identically -- in `tests/test_schema_validation.py`
- [ ] Test: `test_scorer_output_structure` -- ScorerOutput has trust_vector (dict) and explanation (Explanation with reasons list + summary string) -- in `tests/test_schema_validation.py`
- [ ] Test: `test_explanation_reasons_are_strings` -- Explanation.reasons must be list[str] -- in `tests/test_schema_validation.py`
- [ ] Test: `test_experiment_result_fields` -- ExperimentResult has all required fields (run_id, composite, gold_agreement, explanation_quality, gate_results, etc.) -- in `tests/test_schema_validation.py`
- [ ] Test: `test_gold_chain_extends_email_chain` -- GoldChain has annotator_scores, consensus_labels, kappa, opus_agreement in addition to EmailChain fields -- in `tests/test_schema_validation.py`
- [ ] Test: `test_calibration_report_fields` -- CalibrationReport has per_axis_kappa, effective_weights, flagged_axes, downweight_amounts -- in `tests/test_schema_validation.py`

## Implementation
- [ ] Step 1: Create `autotrust/schemas.py` with models:
  - `Email(BaseModel)`: from_addr (str), to_addr (str), subject (str), body (str), timestamp (datetime), reply_depth (int)
  - `EmailChain(BaseModel)`: chain_id (str), emails (list[Email]), labels (dict[str, float]), trust_vector (dict[str, float]), composite (float), flags (list[str])
  - `validate_trust_vector(v: dict[str, float], spec: Spec) -> dict[str, float]` -- standalone validator function that checks keys match spec.trust_axes names and values are float
  - `Explanation(BaseModel)`: reasons (list[str]), summary (str)
  - `ScorerOutput(BaseModel)`: trust_vector (dict[str, float]), explanation (Explanation)
  - `ExperimentResult(BaseModel)`: run_id (str), change_description (str), per_axis_scores (dict[str, float]), composite (float), fp_rate (float), judge_agreement (float), gold_agreement (float), explanation_quality (float), downweighted_axes (list[str]), gate_results (dict[str, bool]), cost (float), wall_time (float)
  - `RunArtifacts(BaseModel)`: metrics_json (Path), predictions_jsonl (Path), config_json (Path), summary_txt (Path)
  - `GoldChain(EmailChain)`: annotator_scores (dict[str, list[float]]), consensus_labels (dict[str, float]), kappa (dict[str, float]), opus_agreement (dict[str, float])
  - `CalibrationReport(BaseModel)`: per_axis_kappa (dict[str, float]), effective_weights (dict[str, float]), flagged_axes (list[str]), downweight_amounts (dict[str, float])
- [ ] Step 2: Implement `validate_trust_vector()` to check keys match spec axis names and values are floats in [0, 1]
- [ ] DRY check: no duplication with config.py (schemas imports Spec from config, but doesn't re-validate spec)

## TDD: Tests Pass (Green)
- [ ] All 10 unit tests pass
- [ ] All existing tests (test_config.py) still pass

## Acceptance Criteria
- [ ] `autotrust/schemas.py` exists with all listed models
- [ ] TrustVector validates keys against spec.yaml axis names
- [ ] ScorerOutput correctly nests Explanation with reasons array
- [ ] All models serialize to/from JSON cleanly
- [ ] All tests in `tests/test_schema_validation.py` pass

## Execution
- **Agent Type**: python
- **Wave**: 2 (depends on TASK_001 scaffold, TASK_002 spec.yaml; parallel with TASK_004)
- **Complexity**: Medium
