# AutoEmailTrust v3.5 Redesign -- TRD

> Redesign the codebase to support the full 4-stage pipeline: frozen spec/rubric, prompt-optimized teacher discovery, autoresearch MoE student training, and local production inference.

---

## 1. Problem Statement

The current codebase implements **Stage 1 only**: a prompt-based email trust scorer that calls remote LLM APIs (Hyperbolic) and evaluates results through a three-gate keep/discard loop. The system works end-to-end for prompt optimization but has no path to:

- **Freeze teacher outputs** and transition to a training stage
- **Train a small student model** (50-200M params, dense then MoE) using soft teacher labels
- **Run local inference** without API dependencies
- **Export models** to GGUF for deployment

Evidence from the codebase:
- `train.py` is a prompt builder (`EmailTrustScorer`), not a PyTorch training script
- `spec.yaml` is missing `stage2` and `production` sections
- No `teacher/` directory with frozen artifacts
- `run_loop.py` has no stage transition logic or handoff triggers
- No PyTorch model definitions, training loops, or export code anywhere

## 2. Goal

A user can run the full pipeline: discover optimal scoring prompts via Stage 1, freeze teacher artifacts, then launch Stage 2 autoresearch to train a compact MoE student model that runs locally, falling back to cloud judge only for high-uncertainty cases.

## 3. UX/DevEx Requirements

- `uv run python run_loop.py` runs Stage 1 (prompt optimization) by default
- `uv run python run_loop.py --stage train` switches to Stage 2 (model training)
- Stage 1 auto-transitions to Stage 2 after 3 consecutive no-improvement experiments (or manual `--stage train`)
- Stage 2 produces a PyTorch checkpoint in `runs/<run_id>/checkpoints/`
- `uv run python -m autotrust.export --checkpoint <path>` converts to GGUF
- Dashboard shows stage-aware metrics (prompt optimization vs. training loss curves)
- Existing three-gate keep/discard policy works identically across both stages

## 4. Technical Design

### 4.1 spec.yaml Extensions

Current spec.yaml is missing these sections (present in PRD):

```yaml
stage2:
  dense_baseline_first: true
  max_experts: 16
  max_params_m: 200
  max_top_k: 4
  export_formats: [pytorch, gguf]

production:
  judge_fallback_enabled: true
  escalate_on_flag: true
```

Also, the `limits` section uses `experiment_minutes` (singular) but the PRD defines both `stage1_experiment_minutes: 15` and `stage2_experiment_minutes: 10`. The current `explanation` section uses `mode` and `gate_after_baseline` but the PRD uses `gate_enabled: true`. These need reconciliation.

### 4.2 Teacher Artifact Freezing (Stage 0 -> Stage 1 Handoff)

Stage 1 currently produces no frozen artifacts. After Stage 1 completes, the system needs to:

1. Extract the best-performing scoring prompt from `train.py` into `teacher/prompt_pack.yaml`
2. Extract labeling heuristics into `teacher/label_rules.yaml`
3. Define explanation tag vocabulary in `teacher/explanation_schema.json`
4. Label all training data using the frozen teacher prompts -> `synth_data/*.jsonl` with soft trust vectors

New module: `autotrust/freeze.py` -- extracts artifacts from the best `train.py` commit.

### 4.3 Student Model Architecture (Stage 2)

New file: `autotrust/student.py` -- PyTorch model definitions (outside agent's edit boundary).

```
StudentModel (dense baseline):
  - Tokenizer: use Llama tokenizer for email text
  - Encoder: small transformer (6-12 layers, 256-512 hidden)
  - Trust head: Linear -> 10 axes (soft label MSE loss)
  - Explanation head: Multi-label classifier for reason tags
  - Escalate head: Binary classifier for judge fallback

MoEStudentModel (after dense baseline established):
  - Same as above but selected layers replaced with MoE blocks
  - Expert count, routing strategy, capacity factor are agent-controlled via train.py
  - Caps enforced from spec.yaml stage2 section
```

The student model definitions live in `autotrust/student.py` (fixed platform, Layer 2). The agent controls architecture hyperparameters through `train.py` which constructs and trains the model.

### 4.4 train.py Lifecycle

`train.py` serves two purposes across stages:

- **Stage 1**: Prompt-based scorer (current implementation). Agent optimizes prompts, parsing, thread encoding.
- **Stage 2**: PyTorch training script. Agent optimizes architecture, hyperparameters, loss functions.

At stage handoff, `train.py` is **rewritten** from scratch. The old prompt-based code is archived. The new `train.py` imports from `autotrust/student.py` and implements the training loop.

### 4.5 run_loop.py Changes

- Add `--stage` CLI argument (`prompt` or `train`)
- Add auto-transition after 3 consecutive no-improvement (existing `consecutive_no_improvement` counter)
- Stage 2 mode: `train.py` is executed as a subprocess (like original autoresearch) instead of imported as a module
- Per-stage time limits from spec.yaml (`stage1_experiment_minutes`, `stage2_experiment_minutes`)
- Stage 2 scoring uses the trained student model checkpoint, not the LLM API

### 4.6 eval.py Changes

Minimal. The three-gate policy is intentionally stage-agnostic. However:

- Stage 2 needs to compute metrics against the **same eval set** using student model predictions instead of LLM API predictions
- `score_predictions()` already works with any `list[dict[str, float]]` -- no change needed
- Student model output shape (`trust_vector`, `reason_tags`, `escalate`) maps directly to existing `ScorerOutput`

### 4.7 Export Pipeline

New module: `autotrust/export.py`

- `export_pytorch(checkpoint_path, output_path)` -- save clean state dict
- `export_gguf(checkpoint_path, output_path)` -- convert via llama.cpp (requires llama-cpp-python)
- CLI: `uv run python -m autotrust.export --checkpoint runs/<id>/best.pt --format gguf`

### 4.8 Production Inference (Stage 3)

New module: `autotrust/inference.py`

- `LocalInference(model_path)` -- loads PyTorch or GGUF checkpoint
- `score(email_chain) -> ScorerOutput` -- local trust vector + explanation tags
- `should_escalate(scorer_output, spec) -> bool` -- checks escalate head output
- Integrates with existing `JudgeProvider` for fallback

### 4.9 Dashboard Changes

- Stage indicator in Live Run tab (Stage 1: Prompt Optimization / Stage 2: Model Training)
- Stage 2 metrics: training loss curve, parameter count, expert utilization
- Checkpoint list with export buttons
- Model size / latency stats for production readiness

### 4.10 Documentation Updates

- `program.md` needs Stage 2 instructions (dense baseline first, then MoE search, caps from spec.yaml)
- `README.md` needs architecture diagram update, Stage 2 quickstart
- `annotation_rubric.md` -- no changes (frozen before any stage)

## 5. Test Strategy

### Existing tests (must not break)
All 20 test files in `tests/` must continue to pass. The redesign is additive.

### New tests

| Test File | What it verifies |
|-----------|-----------------|
| `test_spec_stage2.py` | stage2/production sections load, validate caps |
| `test_freeze.py` | Teacher artifact extraction from git, YAML round-trip |
| `test_student_model.py` | Dense model forward pass, output shapes, param budget |
| `test_moe_model.py` | MoE layer construction, expert routing, cap enforcement |
| `test_stage2_train.py` | Training loop with soft labels, loss computation |
| `test_export.py` | PyTorch checkpoint save/load, GGUF conversion |
| `test_inference.py` | Local inference produces valid ScorerOutput |
| `test_stage_transition.py` | Handoff trigger, artifact freezing, train.py rewrite |

## 6. Risks & Open Questions

1. **GGUF export dependency**: Requires `llama-cpp-python` which has native build requirements. May need to be optional.
2. **GPU availability**: Stage 2 requires Hyperbolic H100 rental. If unavailable, need graceful fallback.
3. **train.py rewrite safety**: Rewriting train.py at stage handoff is destructive. Need git branch protection.
4. **MoE training convergence**: Small MoE models (50-200M) with 5-10 min experiment cycles may not converge. May need longer cycles.
5. **Tokenizer choice**: The PRD specifies Llama tokenizer but the student model may benefit from a simpler/smaller tokenizer for email text.
6. **Soft label noise**: Teacher LLM predictions have variance. Need to handle noisy soft labels in the training loss.

## 7. Out of Scope

- Multi-agent parallel branches (future work)
- SETI@home-style distributed training
- Real-time email processing (Stage 3 is batch-mode)
- Fine-tuning the teacher model itself
- Custom tokenizer training
- Mobile/edge deployment beyond GGUF

---

## Execution Order

```
Wave 1 (parallel -- spec + schemas):
  TASK_001: spec.yaml stage2/production sections + config.py models
  TASK_002: schemas.py student model types (StudentConfig, MoEConfig, CheckpointMeta)

Wave 2 (parallel -- new modules):
  TASK_003: autotrust/student.py -- dense baseline model
  TASK_004: autotrust/freeze.py -- teacher artifact extraction
  TASK_005: autotrust/export.py -- PyTorch/GGUF export

Wave 3 (sequential -- depends on Wave 2):
  TASK_006: autotrust/student.py -- MoE layer extension
  TASK_007: autotrust/inference.py -- local inference with escalation

Wave 4 (parallel -- integration):
  TASK_008: run_loop.py -- stage CLI, auto-transition, Stage 2 subprocess mode
  TASK_009: program.md -- Stage 2 agent instructions

Wave 5 (parallel -- dashboard + docs):
  TASK_010: dashboard.py -- stage-aware metrics, checkpoint UI
  TASK_011: README.md + setup.sh updates

Wave 6 (final -- cleanup):
  TASK_012: Full test suite run, DRY review, dead code removal
```

---

## Review Summary

**Review Date**: 2026-03-14 (updated)
**Reviewer**: Claude Opus 4.6 (1M context)
**Test Suite**: 249 passed, 5 failed (see ISSUE_015)

### Issue Counts by Severity (current state)

| Severity | Count | Notes |
|----------|-------|-------|
| Critical | 1 | ISSUE_015 (train.py overwritten, 5 test failures) |
| High     | 2 | ISSUE_016 (relabel API mismatch), ISSUE_022 (Stage 2 test gap) |
| Medium   | 4 | ISSUE_017 (StudentOutput validation), ISSUE_018 (MSE vs KL), ISSUE_020 (escalate heuristic), ISSUE_021 (CLI -m flag) |
| Low      | 1 | ISSUE_019 (6 stale issues to close) |
| **Open** | **8 new** | Issues 015-022 |
| **Resolved** | **6** | Issues 001, 002, 004, 005, 006, 008 (code has been updated) |
| **Still open (prior)** | **5** | Issues 003 (partially), 007, 009, 010, 011, 012, 013, 014 |

### Requirements Coverage

| TRD Section | Status | Notes |
|-------------|--------|-------|
| 4.1 spec.yaml extensions | Met | Stage2Config, ProductionConfig, per-stage limits all implemented |
| 4.2 Teacher artifact freezing | Partially met | Freeze works; `relabel_training_data()` exists but full path has wrong API (ISSUE_016) |
| 4.3 Student model architecture | Met | Dense and MoE models implemented with cap enforcement |
| 4.4 train.py lifecycle | Met (with regression) | Archive + template rewrite implemented, but currently applied to working dir (ISSUE_015) |
| 4.5 run_loop.py changes | Met | CLI, auto-transition, Stage 2 subprocess execution all implemented |
| 4.6 eval.py changes | Met | Eval is stage-agnostic as designed |
| 4.7 Export pipeline | Partially met | PyTorch export works; GGUF is placeholder; CLI -m flag broken (ISSUE_021) |
| 4.8 Production inference | Partially met | LocalInference works but escalation uses heuristic not model flag (ISSUE_020) |
| 4.9 Dashboard changes | Partially met | Charts implemented and integrated; checkpoint management UI deferred (ISSUE_009) |
| 4.10 Documentation | Met | README, program.md, setup.sh all updated |

### Critical Items

1. **ISSUE_015**: `train.py` has been overwritten with the Stage 2 template in the working directory. This breaks 5 tests in `test_train.py` that import `EmailTrustScorer`. The original code is preserved in `train_stage1_archive.py`. Restoring `train.py` fixes the regression.

### Previously Critical, Now Resolved

- **ISSUE_001** (Stage 2 execution path): `_run_stage2_iteration()` is now fully implemented with subprocess execution, checkpoint discovery, and student model scoring.
- **ISSUE_002** (train.py archive/rewrite): Both `_archive_train_py()` and `_write_stage2_train_py_template()` are implemented.

### Tests Passing

249 of 254 tests pass. The 5 failures are all in `test_train.py` due to `train.py` being overwritten (ISSUE_015). Stage 2 helper tests pass but integration-level tests for the full Stage 2 loop are absent (ISSUE_022).

### Recommendation

**Fix then ship.** The core implementation is substantially complete -- all major modules (student models, loss functions, MoE, export, inference, freeze, run_loop Stage 2 path, dashboard charts) are working. The critical blocker is ISSUE_015 (restore `train.py` to Stage 1 content). After that fix, the remaining issues are medium/low severity: API mismatches in freeze/inference, missing CLI routing, and test coverage gaps. None block the system from functioning in Stage 1 or from transitioning to Stage 2 when triggered.
