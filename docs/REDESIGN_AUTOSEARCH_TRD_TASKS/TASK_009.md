# Task 009: program.md -- Stage 2 Agent Instructions

## Context
The REDESIGN_AUTOSEARCH_TRD specifies that `program.md` needs Stage 2 instructions alongside the existing Stage 1 instructions. The agent reads `program.md` every iteration to understand what to optimize and what the gates are. Stage 2 has different optimization targets (model architecture, hyperparameters, loss functions) and different constraints (param budget, MoE caps, dense-first baseline requirement).

Currently `program.md` is 31 lines covering Stage 1 only (prompt optimization). It needs a Stage 2 section that:
1. Instructs the agent to establish a dense baseline first
2. Unlocks MoE architecture search after baseline
3. References spec.yaml caps (max_experts, max_params_m, max_top_k)
4. Explains the training loop structure (train.py as subprocess)
5. Explains how to use TrainingProvider for Hyperbolic GPU rental

## Goal
Add Stage 2 agent instructions to `program.md` without breaking Stage 1 instructions.

## Research First
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/program.md` (current Stage 1 instructions)
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/docs/REDESIGN_AUTOSEARCH.md` lines 66-113 (Stage 2 spec)
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/docs/REDESIGN_AUTOSEARCH.md` lines 389-411 (execution order steps 17-18)
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/spec.yaml` -- `stage2` section from TASK_001

## TDD: Tests First (Red)
No code tests for this task (it's a Markdown file), but verify:

### Validation Checks
- [ ] Test: `test_program_md_references_spec_yaml` in `tests/test_smoke.py` -- program.md mentions "spec.yaml" (existing behavior preserved)
- [ ] Test: `test_program_md_has_stage2_section` -- program.md contains "Stage 2" heading
- [ ] Test: `test_program_md_mentions_dense_baseline` -- program.md mentions "dense baseline"
- [ ] Test: `test_program_md_mentions_moe` -- program.md mentions "MoE" or "Mixture of Experts"
- [ ] Test: `test_program_md_mentions_param_budget` -- program.md mentions "max_params" or "200M"

## Implementation
- [ ] Step 1: Restructure `program.md` with stage headers:
  ```markdown
  # Stage 1: Prompt Optimization
  [existing content]

  # Stage 2: Student Model Training
  [new content]
  ```
- [ ] Step 2: Write Stage 2 instructions:
  ```markdown
  ## Stage 2: Student Model Training

  You are training a compact student model (50-200M params) to replace the LLM scorer.

  ### What you optimize (in train.py):
  - Model architecture: hidden size, depth, number of layers
  - Loss weighting across trust axes
  - Optimizer, learning rate schedule, batch size
  - After dense baseline: MoE expert count, routing strategy, capacity factor, which layers are sparse

  ### What you cannot change:
  - The dataset (frozen Stage 1 outputs in teacher/)
  - The teacher labels (soft trust vectors)
  - The evaluation harness (eval.py)
  - The gold set
  - MoE caps in spec.yaml (max_experts=16, max_params=200M, max_top_k=4)

  ### Architecture search path:
  1. Establish dense baseline FIRST (prove it converges)
  2. Only then introduce MoE layers
  3. Start with few experts (4-8), increase only if gains stall

  ### Training data:
  - All Stage 1 synthetic + real labeled chains (synth_data/)
  - Soft teacher scores (not hard labels) as training targets
  - Explanation tags as auxiliary supervision signal

  ### Output shape:
  train.py must produce a PyTorch checkpoint that, when loaded, outputs:
  {"trust_vector": {...}, "reason_tags": [...], "escalate": true/false}

  ### Budget:
  See spec.yaml limits (currently 10 min / $8 per experiment)
  Use TrainingProvider to rent Hyperbolic H100s. Auto-terminate GPUs when done.
  ```
- [ ] Step 3: Ensure Stage 1 section is clearly labeled and unchanged
- [ ] DRY check: program.md references spec.yaml values by name, never duplicates them

## TDD: Tests Pass (Green)
- [ ] All validation checks pass
- [ ] All existing tests still pass

## Acceptance Criteria
- [ ] program.md has both Stage 1 and Stage 2 sections
- [ ] Stage 2 section references spec.yaml caps by name
- [ ] Dense-first baseline requirement is clearly stated
- [ ] MoE constraints are documented
- [ ] TrainingProvider usage is explained
- [ ] Stage 1 content is preserved exactly
- [ ] No existing test is broken

## Execution
- **Agent Type**: coding subagent
- **Wave**: 4 (parallel with TASK_008; depends on Wave 1 for spec.yaml values)
- **Complexity**: Low
