# Task 002: Create spec.yaml -- Single Source of Truth

## Context
`spec.yaml` is the single source of truth for AutoEmailTrust v3.5. It defines structured trust axes (with name/type/metric/weight), axis_groups for eval dispatch, composite_penalties, provider configs, limits, judge thresholds, calibration policy, explanation gate settings, safety rules, and data parameters. Every other module reads from this file. See CURSOR_PLAN.md section "spec.yaml -- Single Source of Truth".

## Goal
Create a complete, valid `spec.yaml` at the project root that matches the specification in CURSOR_PLAN.md exactly.

## Research First
- [ ] Read CURSOR_PLAN.md section "spec.yaml -- Single Source of Truth" (the full YAML block)
- [ ] Verify all axis weights sum to ~1.0 (0.22 + 0.18 + 0.00 + 0.13 + 0.10 + 0.10 + 0.08 + 0.05 + 0.04 + 0.10 = 1.00)
- [ ] Verify all axis names in `axis_groups` reference valid axes in `trust_axes`

## TDD: Tests First (Red)
No code tests for this task; spec.yaml is validated by TASK_004 (config.py). Manual verification only.

## Implementation
- [ ] Step 1: Create `spec.yaml` at `/Users/jonathan.hendler/personal/autoresearch-helpful/spec.yaml` with the exact YAML content from CURSOR_PLAN.md, including all sections:
  - `trust_axes` (10 axes, each with name/type/metric/weight)
  - `composite_penalties` (false_positive_rate: -0.15)
  - `axis_groups` (binary, continuous, subtle, fast)
  - `providers` (generator, scorer, judge_primary, judge_secondary, trainer)
  - `limits` (experiment_minutes: 15, max_spend_usd: 8)
  - `judge` (escalate_threshold: 0.60, disagreement_max: 0.20, min_gold_kappa: 0.70)
  - `calibration` (downweight_policy, redistribute_remainder, log_downweighted_axes, scope)
  - `explanation` (mode, flag_threshold, min_quality_threshold, gate_after_baseline)
  - `safety` (synth_placeholder_only, block_operational_instructions, real_brands_in_eval)
  - `data` (eval_set_size, gold_set_size, synth_real_ratio, train_val_test_split)
- [ ] Step 2: Validate YAML is parseable: `uv run python -c "import yaml; yaml.safe_load(open('spec.yaml'))"`

## TDD: Tests Pass (Green)
- [ ] YAML parses without error
- [ ] Manual inspection confirms all sections present

## Acceptance Criteria
- [ ] `spec.yaml` exists at project root
- [ ] All 10 trust axes defined with name, type, metric, weight
- [ ] Axis weights sum to 1.00
- [ ] All axis_groups reference valid axis names
- [ ] All 10 sections (trust_axes through data) are present
- [ ] YAML parses cleanly with `yaml.safe_load()`

## Execution
- **Agent Type**: python
- **Wave**: 1 (parallel with TASK_001)
- **Complexity**: Low
