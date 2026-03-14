# Task 004: Build config.py -- Typed Settings Loader

## Context
`config.py` is the typed loader for `spec.yaml`. It parses the YAML into pydantic models, validates axis/weight consistency, and provides a cached singleton `get_spec()`. It also contains `get_effective_weights()` which applies Kappa-proportional downweighting for composite scoring only. Every other module depends on this for configuration. See CURSOR_PLAN.md "Implementation Details > 3. config.py".

## Goal
Build a typed, validated spec.yaml loader that catches configuration errors at startup and provides effective weight computation.

## Research First
- [ ] Read CURSOR_PLAN.md section "Implementation Details > 3. config.py"
- [ ] Read `spec.yaml` (created in TASK_002) to understand the full schema
- [ ] Read CURSOR_PLAN.md "Kappa Downweighting: Composite Only" for downweight policy details

## TDD: Tests First (Red)
Write tests FIRST in `tests/test_config.py`. They should FAIL before implementation.

### Unit Tests
- [ ] Test: `test_load_spec_valid` -- loads spec.yaml, returns a Spec object with correct axis count (10) -- in `tests/test_config.py`
- [ ] Test: `test_axis_weights_sum_to_one` -- validates that positive axis weights sum to ~1.0 (within tolerance 0.01) -- in `tests/test_config.py`
- [ ] Test: `test_axis_type_validation` -- rejects axes with invalid types (not binary/continuous) -- in `tests/test_config.py`
- [ ] Test: `test_axis_groups_reference_valid_axes` -- rejects spec where axis_groups reference non-existent axes -- in `tests/test_config.py`
- [ ] Test: `test_composite_penalties_not_axis_names` -- rejects spec where composite_penalty keys match axis names -- in `tests/test_config.py`
- [ ] Test: `test_get_spec_singleton` -- calling get_spec() twice returns same object -- in `tests/test_config.py`
- [ ] Test: `test_get_effective_weights_no_downweight` -- with perfect Kappa (1.0 for all axes), effective weights equal original weights -- in `tests/test_config.py`
- [ ] Test: `test_get_effective_weights_with_downweight` -- with low Kappa on one axis, that axis's weight decreases and remainder is redistributed -- in `tests/test_config.py`
- [ ] Test: `test_get_effective_weights_zero_weighted_axis` -- zero-weighted axes (verify_by_search) are handled correctly (stay at 0.0) -- in `tests/test_config.py`

## Implementation
- [ ] Step 1: Create `autotrust/config.py` with pydantic models:
  - `AxisDef(BaseModel)`: name (str), type (Literal["binary", "continuous"]), metric (str), weight (float >= 0)
  - `AxisGroups(BaseModel)`: binary (list[str]), continuous (list[str]), subtle (list[str]), fast (list[str])
  - `ProviderDef(BaseModel)`: backend (str), model (str), gpu_type (str | None)
  - `Providers(BaseModel)`: generator, scorer, judge_primary, judge_secondary, trainer
  - `Limits(BaseModel)`: experiment_minutes (int), max_spend_usd (float)
  - `JudgeConfig(BaseModel)`: escalate_threshold (float), disagreement_max (float), min_gold_kappa (float)
  - `CalibrationConfig(BaseModel)`: downweight_policy (str), redistribute_remainder (bool), log_downweighted_axes (bool), scope (str)
  - `ExplanationConfig(BaseModel)`: mode (str), flag_threshold (float), min_quality_threshold (float), gate_after_baseline (bool)
  - `SafetyConfig(BaseModel)`: synth_placeholder_only (bool), block_operational_instructions (bool), real_brands_in_eval (bool)
  - `DataConfig(BaseModel)`: eval_set_size (int), gold_set_size (int), synth_real_ratio (float), train_val_test_split (list[float])
  - `Spec(BaseModel)`: trust_axes, composite_penalties, axis_groups, providers, limits, judge, calibration, explanation, safety, data
- [ ] Step 2: Implement `load_spec(path="spec.yaml") -> Spec`:
  - Load YAML with `yaml.safe_load()`
  - Parse into `Spec` pydantic model
  - Run validation: weights sum ~1.0, axis_groups reference valid axes, composite_penalties not axis names, provider backends known
- [ ] Step 3: Implement `get_spec() -> Spec` as a cached singleton (module-level `_spec` variable)
- [ ] Step 4: Implement `get_effective_weights(spec: Spec, kappa_per_axis: dict[str, float]) -> dict[str, float]`:
  - For each axis, multiply weight by its Kappa score (proportional downweight)
  - If `redistribute_remainder` is True, redistribute the "lost" weight proportionally among non-downweighted axes
  - Zero-weighted axes stay at 0.0 regardless
  - Log downweighted axes if `log_downweighted_axes` is True
- [ ] DRY check: no duplication with schemas.py (config owns loading/validation, schemas owns data models)

## TDD: Tests Pass (Green)
- [ ] All 9 unit tests pass
- [ ] No existing tests broken

## Acceptance Criteria
- [ ] `autotrust/config.py` exists with all pydantic models
- [ ] `load_spec()` loads and validates spec.yaml
- [ ] `get_spec()` returns cached singleton
- [ ] `get_effective_weights()` correctly computes Kappa-proportional downweighting
- [ ] Validation errors raise clear exceptions with specific messages
- [ ] All tests in `tests/test_config.py` pass

## Execution
- **Agent Type**: python
- **Wave**: 2 (depends on TASK_001 scaffold, TASK_002 spec.yaml)
- **Complexity**: Medium
