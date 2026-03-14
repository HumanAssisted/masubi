# Issue 003: Kappa downweighting formula does not match PRD specification

## Severity
High

## Category
Bug

## Description
The `get_effective_weights()` function in `config.py` multiplies the axis weight directly by the Kappa value (`weight * kappa`). The PRD specifies the formula as `effective_weight = original_weight * (actual_kappa / min_gold_kappa)`. With `min_gold_kappa = 0.70`, these produce different results:

- PRD formula: If kappa=0.55, effective_weight = weight * (0.55/0.70) = weight * 0.786
- Implementation: effective_weight = weight * 0.55

The current implementation is more aggressive in downweighting axes with imperfect Kappa. An axis with kappa=0.70 (exactly at the minimum threshold) would keep only 70% of its weight in the implementation, but should keep 100% per the PRD formula (since 0.70/0.70 = 1.0).

## Evidence
- File: `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/config.py:189` -- `raw_weights[axis.name] = axis.weight * kappa`
- PRD Requirement: INITIAL_DESIGN_CHOICES.md "Kappa-Proportional Downweighting" -- "axis weight is multiplied by `actual_kappa / min_gold_kappa`"
- spec.yaml line 96: `min_gold_kappa: 0.70`

## Suggested Fix
Change line 189 in `config.py` from:
```python
raw_weights[axis.name] = axis.weight * kappa
```
to:
```python
min_kappa = spec.judge.min_gold_kappa
scale = min(kappa / min_kappa, 1.0)  # cap at 1.0 for kappa >= min
raw_weights[axis.name] = axis.weight * scale
```
Also update `test_get_effective_weights_with_downweight` in `tests/test_config.py` to verify the correct formula, and `test_kappa_downweight_proportional` in `tests/test_kappa_downweight.py`.

## Affected Files
- `autotrust/config.py`
- `tests/test_config.py`
- `tests/test_kappa_downweight.py`

## Status: Fixed
Changed `get_effective_weights()` to use `scale = min(kappa / min_gold_kappa, 1.0)` and `weight * scale` instead of `weight * kappa`. Updated redistribution eligibility to check `kappa >= min_kappa` instead of `kappa == 1.0`. Logging now only warns when `kappa < min_kappa`. All 13 config/kappa tests pass.
