# Issue 002: data.py pipeline subcommands are all placeholders

## Severity
Critical

## Category
Omission

## Description
All five data pipeline subcommands (`build_train`, `build_eval`, `build_gold`, `annotate_export`, `calibrate_judge`) are placeholder implementations. They create output directories and log messages but produce no actual output files. The PRD describes a complete pipeline including: real corpora ingestion (SpamAssassin, Enron), synthetic generation via Dolphin 3.0, safety filtering, Evol-Instruct augmentation, SpearBot critic, dual-judge labeling, and deduplication. None of these are implemented.

Without data, the eval set and gold set are empty, and `run_loop.py` cannot execute any experiments (even if its loop were implemented).

## Evidence
- File: `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/data.py:122-145` -- `build_train` is a placeholder
- File: `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/data.py:148-160` -- `build_eval` is a placeholder
- File: `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/data.py:163-175` -- `build_gold` is a placeholder
- File: `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/data.py:191-209` -- `calibrate_judge` is a placeholder
- PRD Requirement: INITIAL_DESIGN_CHOICES.md "Local Uncensored Models for Synthetic Data" and "Gold Set and Human Annotation"
- Task 010 Acceptance Criteria: "Safety filter correctly blocks/allows", "calibrate_judge computes per-axis Kappa"

## Suggested Fix
1. Implement `build_train()`:
   - Load SpamAssassin public corpus and Enron email dataset using `datasets` library
   - Generate synthetic emails via `get_provider("generator", spec)` (OllamaGenerator)
   - Apply `safety_filter()` to all generated emails
   - Implement Evol-Instruct augmentation for diversity
   - Write results to `synth_data/train.jsonl`
2. Implement `build_eval()` similarly with `spec.data.eval_set_size` chains
3. Implement `build_gold()` selecting diverse chains across all axis groups
4. Implement `calibrate_judge()` to compute per-axis Kappa from human annotations and write `CalibrationReport` to `gold_set/calibration.json`

## Affected Files
- `autotrust/data.py`
