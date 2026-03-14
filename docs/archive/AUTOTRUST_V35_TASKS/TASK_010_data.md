# Task 010: Build data.py -- Data Generation and Calibration Module

## Context
`data.py` is the fixed data module with CLI subcommands: `build-train`, `build-eval`, `build-gold`, `annotate-export`, and `calibrate-judge`. It handles real corpora ingestion (SpamAssassin, Enron), synthetic generation via Dolphin 3.0, the safety filter, Evol-Instruct augmentation, SpearBot critic, dual-judge labeling, deduplication, and judge calibration against human annotations. It uses `axis_groups` from spec to determine which axes need judge escalation. See CURSOR_PLAN.md "Implementation Details > 6. data.py".

## Goal
Build the complete data pipeline module that can generate training, evaluation, and gold-set datasets from real and synthetic sources with quality controls.

## Research First
- [ ] Read CURSOR_PLAN.md section "Implementation Details > 6. data.py"
- [ ] Read `autotrust/config.py` for Spec model and get_spec()
- [ ] Read `autotrust/schemas.py` for EmailChain, GoldChain, CalibrationReport models
- [ ] Read `autotrust/providers/__init__.py` for GeneratorProvider, JudgeProvider interfaces
- [ ] Read spec.yaml `data` section for set sizes and ratios
- [ ] Read spec.yaml `safety` section for safety filter rules
- [ ] Read spec.yaml `axis_groups.subtle` for judge escalation axes

## TDD: Tests First (Red)
No separate test file for data.py since its logic is heavily integration-dependent. Unit tests for the safety filter go here; composite/eval tests are in TASK_011.

### Unit Tests
- [ ] Test: `test_safety_filter_blocks_operational_instructions` -- verify emails with operational attack instructions are rejected -- in `tests/test_safety_filter.py`
- [ ] Test: `test_safety_filter_allows_structural_malicious` -- verify structurally malicious emails (phishing patterns without real ops) pass filter -- in `tests/test_safety_filter.py`
- [ ] Test: `test_safety_filter_placeholder_only` -- verify synth emails use placeholder brand names, not real brands -- in `tests/test_safety_filter.py`
- [ ] Test: `test_safety_filter_real_brands_in_eval` -- verify eval set allows real brand names -- in `tests/test_safety_filter.py`
- [ ] Test: `test_calibrate_judge_computes_kappa` -- with known annotator scores, verify Cohen's Kappa computation is correct -- in `tests/test_safety_filter.py`
- [ ] Test: `test_calibrate_judge_flags_low_kappa` -- axes below min_gold_kappa are flagged -- in `tests/test_safety_filter.py`

## Implementation
- [ ] Step 1: Create `autotrust/data.py` with CLI entry point `__main__` support:
  ```python
  # Invoked as: uv run python -m autotrust.data <subcommand>
  ```
- [ ] Step 2: Implement `build_train(count: int)`:
  - Load real corpora (SpamAssassin public corpus, Enron email dataset)
  - Generate synthetic emails via GeneratorProvider (Dolphin 3.0)
  - Apply safety filter: block operational instructions, enforce placeholder brands for synth
  - Apply Evol-Instruct augmentation for diversity
  - Run SpearBot critic for quality
  - Dual-judge labeling via JudgeProvider
  - Deduplication
  - Output to `synth_data/train.jsonl`
- [ ] Step 3: Implement `build_eval()`:
  - Similar pipeline but with `data.eval_set_size` chains
  - Real brands allowed (per safety.real_brands_in_eval)
  - Output to `eval_set/eval_chains.jsonl`
- [ ] Step 4: Implement `build_gold()`:
  - Generate gold-set candidates (data.gold_set_size chains)
  - Select diverse chains covering all axis_groups
  - Output to `gold_set/gold_candidates.jsonl` (for human annotation)
- [ ] Step 5: Implement `annotate_export()`:
  - Export gold candidates in annotator-friendly format
  - Include annotation_rubric.md reference
- [ ] Step 6: Implement `calibrate_judge(annotations_path: str)`:
  - Ingest human annotations (2-3 annotators per chain)
  - Compute Cohen's Kappa per axis
  - Flag axes below `judge.min_gold_kappa`
  - Write `gold_set/calibration.json` (CalibrationReport)
  - Log which axes need recalibration
- [ ] Step 7: Implement `safety_filter(email: Email, is_synth: bool, spec: Spec) -> bool`:
  - If `safety.block_operational_instructions`: reject emails with real operational attack instructions
  - If `safety.synth_placeholder_only` and `is_synth`: reject emails with real brand names
  - If `safety.real_brands_in_eval` and not `is_synth`: allow real brands
- [ ] Step 8: Wire CLI argument parser for subcommands
- [ ] DRY check: uses providers via get_provider(), does not construct API clients directly

## TDD: Tests Pass (Green)
- [ ] All 6 unit tests pass
- [ ] All existing tests still pass

## Acceptance Criteria
- [ ] `autotrust/data.py` exists with all 5 subcommands
- [ ] Safety filter correctly blocks/allows per spec.yaml safety config
- [ ] `calibrate_judge` computes per-axis Kappa and flags low axes
- [ ] CLI invocation works: `uv run python -m autotrust.data --help`
- [ ] Uses axis_groups from spec for judge escalation
- [ ] All tests pass

## Execution
- **Agent Type**: python
- **Wave**: 4 (depends on TASK_004 config, TASK_005 schemas, TASK_006-009 providers)
- **Complexity**: High
