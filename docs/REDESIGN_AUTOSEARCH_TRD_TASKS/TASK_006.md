# Task 006: autotrust/student.py -- MoE Layer Extension

## Context
The REDESIGN_AUTOSEARCH_TRD specifies that after a dense baseline is established in Stage 2, the agent unlocks MoE (Mixture of Experts) search. The agent controls which layers are sparse, number of experts, routing strategy, capacity factor, and top-k -- all within caps defined in `spec.yaml`.

The dense baseline from TASK_003 must be extensible: the agent should be able to replace selected transformer layers with MoE variants by specifying a `MoEConfig` in `train.py`. The MoE implementation lives in `autotrust/student.py` (fixed platform), enforcing the caps. Expert-to-axis mapping is emergent (the agent discovers which axes cluster), not hard-coded.

## Goal
Add MoE transformer blocks and `MoEStudent` model to `autotrust/student.py`, enforcing architecture caps from `spec.yaml`.

## Research First
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/docs/REDESIGN_AUTOSEARCH.md` lines 70-82 (MoE architecture search, what agent controls)
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/student.py` -- `DenseStudent` from TASK_003
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/schemas.py` -- `MoEConfig` from TASK_002
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/spec.yaml` -- `stage2` section from TASK_001 (max_experts=16, max_top_k=4, max_params_m=200)
- [ ] Research current MoE routing strategies: top-k, noisy top-k, expert choice (DeepSeek-V3 style)

## TDD: Tests First (Red)

### Unit Tests
- [ ] Test: `test_moe_block_forward` in `tests/test_moe_model.py` -- MoE block accepts hidden states, returns same shape output
- [ ] Test: `test_moe_block_routes_to_top_k` -- with `top_k=2` and `num_experts=4`, only 2 experts are activated per token
- [ ] Test: `test_moe_block_capacity_factor` -- excess tokens beyond capacity are dropped/redistributed
- [ ] Test: `test_moe_student_forward` -- `MoEStudent` accepts input_ids, returns same output dict as `DenseStudent`
- [ ] Test: `test_moe_student_from_config` -- `MoEStudent.from_config(student_config, moe_config)` creates model
- [ ] Test: `test_moe_expert_cap_enforced` -- `MoEConfig(num_experts=20)` raises ValueError when `spec.stage2.max_experts=16`
- [ ] Test: `test_moe_top_k_cap_enforced` -- `MoEConfig(top_k=5)` raises ValueError when `spec.stage2.max_top_k=4`
- [ ] Test: `test_moe_param_budget_enforced` -- model with too many experts exceeding `max_params_m` raises ValueError
- [ ] Test: `test_moe_routing_strategies` -- `routing_strategy="noisy_top_k"` and `"expert_choice"` both work
- [ ] Test: `test_moe_load_balance_loss` -- MoE block computes auxiliary load-balancing loss
- [ ] Test: `test_dense_to_moe_upgrade` -- can create MoE model and load dense model weights for non-MoE layers

## Implementation
- [ ] Step 1: Implement `MoEBlock(nn.Module)` in `autotrust/student.py`:
  ```python
  class MoEBlock(nn.Module):
      """Mixture-of-Experts feed-forward block replacing standard FFN."""
      def __init__(self, hidden_size: int, intermediate_size: int,
                   num_experts: int, top_k: int, capacity_factor: float,
                   routing_strategy: str):
          # Router: Linear(hidden_size, num_experts)
          # Experts: nn.ModuleList of FFN blocks
          # Routing strategy: top_k / noisy_top_k / expert_choice

      def forward(self, x: Tensor) -> tuple[Tensor, Tensor]:
          # Returns (output, load_balance_loss)
  ```
- [ ] Step 2: Implement routing strategies:
  - `top_k`: standard softmax + top-k selection
  - `noisy_top_k`: add Gaussian noise before top-k (Shazeer et al.)
  - `expert_choice`: experts choose tokens (Zhou et al.)
- [ ] Step 3: Implement `MoEStudent(nn.Module)`:
  ```python
  class MoEStudent(nn.Module):
      """Student model with selected layers replaced by MoE blocks."""
      def __init__(self, config: StudentConfig, moe_config: MoEConfig):
          # Same as DenseStudent but layers in moe_config.moe_layers
          # use MoEBlock instead of standard FFN

      @classmethod
      def from_config(cls, config: StudentConfig, moe_config: MoEConfig) -> MoEStudent:
          ...

      @classmethod
      def from_dense(cls, dense_model: DenseStudent, moe_config: MoEConfig) -> MoEStudent:
          """Initialize from a trained dense model, copying shared weights."""
  ```
- [ ] Step 4: Implement cap enforcement in `validate_moe_config()`:
  ```python
  def validate_moe_config(moe_config: MoEConfig, spec: Spec) -> None:
      """Raise ValueError if MoE config exceeds spec.yaml caps."""
      if moe_config.num_experts > spec.stage2.max_experts:
          raise ValueError(...)
      if moe_config.top_k > spec.stage2.max_top_k:
          raise ValueError(...)
  ```
- [ ] Step 5: Implement param budget check:
  ```python
  def check_param_budget(model: nn.Module, spec: Spec) -> None:
      """Raise ValueError if model exceeds max_params_m budget."""
      total = sum(p.numel() for p in model.parameters())
      if total > spec.stage2.max_params_m * 1e6:
          raise ValueError(...)
  ```
- [ ] DRY check: `MoEStudent` should share as much code as possible with `DenseStudent` (common base class or composition)

## TDD: Tests Pass (Green)
- [ ] All new tests in `test_moe_model.py` pass
- [ ] All existing tests (including `test_student_model.py`) still pass

## Acceptance Criteria
- [ ] `MoEBlock` forward pass produces correct output shape
- [ ] `MoEStudent.from_config()` creates a model with MoE layers at specified positions
- [ ] `MoEStudent.from_dense()` loads weights from a trained dense model
- [ ] Cap enforcement raises `ValueError` for configs exceeding spec limits
- [ ] All three routing strategies produce valid outputs
- [ ] Load-balancing auxiliary loss is computed
- [ ] No existing test is broken

## Execution
- **Agent Type**: coding subagent
- **Wave**: 3 (sequential -- depends on TASK_003)
- **Complexity**: High
