# Task 002: schemas.py Student Model Types

## Context
The REDESIGN_AUTOSEARCH_TRD introduces a student model (dense + MoE) trained in Stage 2. `schemas.py` currently defines data models for email chains, trust vectors, and experiment results, but has no types for student model configuration, MoE architecture parameters, or checkpoint metadata. These types will be consumed by `student.py`, `export.py`, and `run_loop.py`.

## Goal
Add Pydantic models for student model configuration, MoE architecture, checkpoint metadata, and teacher artifacts to `schemas.py`.

## Research First
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/schemas.py` (current models)
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/docs/REDESIGN_AUTOSEARCH.md` lines 96-103 (student model output shape)
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/docs/REDESIGN_AUTOSEARCH.md` lines 66-113 (Stage 2 spec)
- [ ] Verify existing tests in `test_schema_validation.py` pass

## TDD: Tests First (Red)

### Unit Tests
- [ ] Test: `test_student_config_roundtrip` in `tests/test_schema_validation.py` -- StudentConfig serializes and deserializes correctly
- [ ] Test: `test_moe_config_validates_expert_cap` -- MoEConfig rejects `num_experts > spec.stage2.max_experts`
- [ ] Test: `test_moe_config_validates_param_budget` -- MoEConfig rejects total params exceeding `max_params_m`
- [ ] Test: `test_checkpoint_meta_has_required_fields` -- CheckpointMeta has `stage`, `experiment_num`, `composite`, `path`
- [ ] Test: `test_student_output_matches_scorer_output` -- StudentOutput has `trust_vector`, `reason_tags`, `escalate`
- [ ] Test: `test_teacher_artifacts_model` -- TeacherArtifacts has `prompt_pack_path`, `label_rules_path`, `explanation_schema_path`

## Implementation
- [ ] Step 1: Add `StudentConfig` to `schemas.py`:
  ```python
  class StudentConfig(BaseModel):
      hidden_size: int
      num_layers: int
      vocab_size: int
      max_seq_len: int
      num_axes: int
      num_reason_tags: int
  ```
- [ ] Step 2: Add `MoEConfig` to `schemas.py`:
  ```python
  class MoEConfig(BaseModel):
      num_experts: int
      top_k: int
      capacity_factor: float = 1.0
      moe_layers: list[int]  # which layers are sparse
      routing_strategy: str = "top_k"  # top_k, noisy_top_k, expert_choice
  ```
- [ ] Step 3: Add `StudentOutput` to `schemas.py`:
  ```python
  class StudentOutput(BaseModel):
      trust_vector: dict[str, float]
      reason_tags: list[str]
      escalate: bool
  ```
- [ ] Step 4: Add `CheckpointMeta` to `schemas.py`:
  ```python
  class CheckpointMeta(BaseModel):
      stage: str  # "dense_baseline" or "moe_search"
      experiment_num: int
      composite: float
      path: Path
      param_count: int
      moe_config: MoEConfig | None = None
  ```
- [ ] Step 5: Add `TeacherArtifacts` to `schemas.py`:
  ```python
  class TeacherArtifacts(BaseModel):
      prompt_pack_path: Path
      label_rules_path: Path
      explanation_schema_path: Path
      synth_data_dir: Path
  ```
- [ ] DRY check: `StudentOutput.trust_vector` reuses the same validation as `ScorerOutput.trust_vector`; share `validate_trust_vector()`

## TDD: Tests Pass (Green)
- [ ] All new tests pass
- [ ] All existing tests in `test_schema_validation.py` still pass

## Acceptance Criteria
- [ ] `StudentConfig`, `MoEConfig`, `StudentOutput`, `CheckpointMeta`, `TeacherArtifacts` all importable from `autotrust.schemas`
- [ ] `StudentOutput` trust vector validation uses shared `validate_trust_vector()` function
- [ ] All models serialize to JSON and deserialize back correctly
- [ ] No existing test is broken

## Execution
- **Agent Type**: coding subagent
- **Wave**: 1 (parallel with TASK_001)
- **Complexity**: Low
