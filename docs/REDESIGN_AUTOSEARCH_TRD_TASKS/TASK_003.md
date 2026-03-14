# Task 003: autotrust/student.py -- Dense Baseline Model

## Context
The REDESIGN_AUTOSEARCH_TRD specifies a student model that trains on soft teacher labels from Stage 1. Stage 2 begins with a dense baseline model before the agent introduces MoE layers. This file lives in Layer 2 (fixed platform) -- the agent controls hyperparameters through `train.py` but cannot modify the model definitions themselves.

The student model scores email text across 10 trust axes, produces explanation reason tags, and outputs an escalation flag. It consumes tokenized email chain text and outputs structured predictions matching the `StudentOutput` schema from TASK_002.

## Goal
Implement a dense transformer student model in `autotrust/student.py` that takes tokenized email text and produces trust vectors, reason tags, and escalation predictions.

## Research First
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/docs/REDESIGN_AUTOSEARCH.md` lines 66-113 (Stage 2 spec, model architecture)
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/schemas.py` -- `StudentConfig`, `StudentOutput` from TASK_002
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/spec.yaml` -- trust axes count (10), `stage2` section from TASK_001
- [ ] Verify PyTorch is available: check `pyproject.toml` dependencies (will need `torch` added)

## TDD: Tests First (Red)

### Unit Tests
- [ ] Test: `test_dense_model_forward_pass` in `tests/test_student_model.py` -- model accepts input_ids tensor, returns dict with `trust_logits`, `reason_logits`, `escalate_logit`
- [ ] Test: `test_dense_model_output_shapes` -- `trust_logits` shape is `(batch, 10)`, `reason_logits` shape is `(batch, num_reason_tags)`, `escalate_logit` shape is `(batch, 1)`
- [ ] Test: `test_dense_model_param_count_within_budget` -- total params <= `spec.stage2.max_params_m * 1e6`
- [ ] Test: `test_dense_model_from_config` -- `DenseStudent.from_config(StudentConfig)` creates model correctly
- [ ] Test: `test_trust_loss_soft_labels` -- `compute_trust_loss(logits, soft_targets)` returns scalar loss using KL divergence
- [ ] Test: `test_reason_tag_loss` -- `compute_reason_loss(logits, tag_targets)` returns scalar BCE loss
- [ ] Test: `test_escalate_loss` -- `compute_escalate_loss(logit, target)` returns scalar BCE loss
- [ ] Test: `test_combined_loss_weighted` -- `compute_total_loss()` combines all three with configurable weights

## Implementation
- [ ] Step 1: Add `torch` to `pyproject.toml` dependencies
- [ ] Step 2: Create `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/student.py`
- [ ] Step 3: Implement `DenseStudent(nn.Module)`:
  ```python
  class DenseStudent(nn.Module):
      def __init__(self, config: StudentConfig):
          # Embedding layer (vocab_size x hidden_size)
          # Positional encoding (max_seq_len)
          # Transformer encoder layers (num_layers)
          # Trust head: Linear(hidden_size, num_axes) -> sigmoid
          # Reason head: Linear(hidden_size, num_reason_tags) -> sigmoid
          # Escalate head: Linear(hidden_size, 1) -> sigmoid

      def forward(self, input_ids: Tensor, attention_mask: Tensor | None = None) -> dict[str, Tensor]:
          # Returns {"trust_logits", "reason_logits", "escalate_logit"}

      @classmethod
      def from_config(cls, config: StudentConfig) -> DenseStudent:
          ...

      def param_count(self) -> int:
          return sum(p.numel() for p in self.parameters())
  ```
- [ ] Step 4: Implement loss functions:
  ```python
  def compute_trust_loss(logits: Tensor, soft_targets: Tensor) -> Tensor:
      """KL divergence between predicted and teacher soft labels."""

  def compute_reason_loss(logits: Tensor, tag_targets: Tensor) -> Tensor:
      """Binary cross-entropy for multi-label reason tag prediction."""

  def compute_escalate_loss(logit: Tensor, target: Tensor) -> Tensor:
      """Binary cross-entropy for escalation prediction."""

  def compute_total_loss(trust_loss, reason_loss, escalate_loss,
                         trust_weight=1.0, reason_weight=0.3, escalate_weight=0.2) -> Tensor:
      """Weighted combination of all three losses."""
  ```
- [ ] Step 5: Implement `predict(model, input_ids, spec) -> StudentOutput`:
  ```python
  def predict(model: DenseStudent, input_ids: Tensor, spec: Spec, reason_tag_names: list[str]) -> StudentOutput:
      """Run inference and convert logits to StudentOutput schema."""
  ```
- [ ] DRY check: Use `StudentConfig` from `schemas.py` (TASK_002), not a separate config

## TDD: Tests Pass (Green)
- [ ] All new tests in `test_student_model.py` pass
- [ ] All existing tests still pass
- [ ] Model param count is within budget for default config

## Acceptance Criteria
- [ ] `DenseStudent.from_config(config)` creates a valid model
- [ ] Forward pass produces correctly-shaped outputs
- [ ] `param_count()` stays within 200M for default config
- [ ] Loss functions compute gradients correctly (`.backward()` works)
- [ ] `predict()` returns a valid `StudentOutput`
- [ ] No existing test is broken

## Execution
- **Agent Type**: coding subagent
- **Wave**: 2 (parallel with TASK_004, TASK_005; depends on Wave 1)
- **Complexity**: Medium
