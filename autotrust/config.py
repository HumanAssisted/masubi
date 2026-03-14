"""Typed settings loader for spec.yaml with validation and Kappa-proportional downweighting."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import structlog
import yaml
from pydantic import BaseModel, field_validator

logger = structlog.get_logger()

_DEFAULT_SPEC_PATH = Path(__file__).parent.parent / "spec.yaml"


# ---------------------------------------------------------------------------
# Pydantic models for spec.yaml
# ---------------------------------------------------------------------------

class AxisDef(BaseModel):
    name: str
    type: Literal["binary", "continuous"]
    metric: str
    weight: float

    @field_validator("weight")
    @classmethod
    def weight_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError(f"Axis weight must be >= 0, got {v}")
        return v


class AxisGroups(BaseModel):
    binary: list[str]
    continuous: list[str]
    subtle: list[str]
    fast: list[str]


class ProviderDef(BaseModel):
    backend: str
    model: str
    gpu_type: str | None = None


class Providers(BaseModel):
    generator: ProviderDef
    scorer: ProviderDef
    judge_primary: ProviderDef
    judge_secondary: ProviderDef
    trainer: ProviderDef


class Limits(BaseModel):
    experiment_minutes: int
    max_spend_usd: float


class JudgeConfig(BaseModel):
    escalate_threshold: float
    disagreement_max: float
    min_gold_kappa: float


class CalibrationConfig(BaseModel):
    downweight_policy: str
    redistribute_remainder: bool
    log_downweighted_axes: bool
    scope: str


class ExplanationConfig(BaseModel):
    mode: str
    flag_threshold: float
    min_quality_threshold: float
    gate_after_baseline: bool


class SafetyConfig(BaseModel):
    synth_placeholder_only: bool
    block_operational_instructions: bool
    real_brands_in_eval: bool


class DataConfig(BaseModel):
    eval_set_size: int
    gold_set_size: int
    synth_real_ratio: float
    train_val_test_split: list[float]


class Spec(BaseModel):
    trust_axes: list[AxisDef]
    composite_penalties: dict[str, float]
    axis_groups: AxisGroups
    providers: Providers
    limits: Limits
    judge: JudgeConfig
    calibration: CalibrationConfig
    explanation: ExplanationConfig
    safety: SafetyConfig
    data: DataConfig


# ---------------------------------------------------------------------------
# Loader + validation
# ---------------------------------------------------------------------------

def load_spec(path: str | Path = _DEFAULT_SPEC_PATH) -> Spec:
    """Load and validate spec.yaml into a Spec model."""
    path = Path(path)
    with open(path) as f:
        raw = yaml.safe_load(f)

    spec = Spec(**raw)
    _validate_spec(spec)
    return spec


def _validate_spec(spec: Spec) -> None:
    """Run cross-field validations that pydantic can't express as field validators."""
    axis_names = {a.name for a in spec.trust_axes}

    # 1. Positive axis weights sum to ~1.0
    total_weight = sum(a.weight for a in spec.trust_axes)
    if abs(total_weight - 1.0) > 0.01:
        raise ValueError(
            f"Axis weights sum to {total_weight}, expected ~1.0 (tolerance 0.01)"
        )

    # 2. All axis_groups reference valid axes
    for group_name in ("binary", "continuous", "subtle", "fast"):
        members = getattr(spec.axis_groups, group_name)
        for name in members:
            if name not in axis_names:
                raise ValueError(
                    f"axis_groups.{group_name} references '{name}' which is not in trust_axes"
                )

    # 3. composite_penalties keys are not axis names
    for penalty_name in spec.composite_penalties:
        if penalty_name in axis_names:
            raise ValueError(
                f"composite_penalties key '{penalty_name}' conflicts with axis name"
            )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_spec: Spec | None = None


def get_spec() -> Spec:
    """Return cached Spec singleton, loading from default path on first call."""
    global _spec
    if _spec is None:
        _spec = load_spec(_DEFAULT_SPEC_PATH)
    return _spec


# ---------------------------------------------------------------------------
# Kappa-proportional downweighting (composite only)
# ---------------------------------------------------------------------------

def get_effective_weights(
    spec: Spec,
    kappa_per_axis: dict[str, float],
) -> dict[str, float]:
    """Apply Kappa-proportional downweighting to axis weights.

    Only used by compute_composite(), never by gold_regression_gate().

    For each axis:
      scale = min(actual_kappa / min_gold_kappa, 1.0)
      effective_weight = original_weight * scale
    Zero-weighted axes stay at 0.0.
    If redistribute_remainder is True, lost weight is redistributed proportionally
    among non-downweighted (scale=1.0) positive-weighted axes.
    """
    min_kappa = spec.judge.min_gold_kappa
    raw_weights: dict[str, float] = {}
    for axis in spec.trust_axes:
        kappa = kappa_per_axis.get(axis.name, 1.0)
        if axis.weight == 0.0:
            raw_weights[axis.name] = 0.0
        else:
            scale = min(kappa / min_kappa, 1.0)  # cap at 1.0 for kappa >= min
            raw_weights[axis.name] = axis.weight * scale

    if spec.calibration.redistribute_remainder:
        original_total = sum(a.weight for a in spec.trust_axes if a.weight > 0)
        current_total = sum(w for w in raw_weights.values() if w > 0)
        lost = original_total - current_total

        if lost > 1e-9:
            # Redistribute among axes that were NOT downweighted (kappa >= min_kappa) and have positive weight
            eligible = [
                a.name for a in spec.trust_axes
                if a.weight > 0 and kappa_per_axis.get(a.name, 1.0) >= min_kappa
            ]
            eligible_total = sum(raw_weights[n] for n in eligible)
            if eligible_total > 0:
                for name in eligible:
                    share = raw_weights[name] / eligible_total
                    raw_weights[name] += lost * share

    if spec.calibration.log_downweighted_axes:
        for axis in spec.trust_axes:
            kappa = kappa_per_axis.get(axis.name, 1.0)
            if kappa < min_kappa and axis.weight > 0:
                logger.info(
                    "Axis downweighted",
                    extra={
                        "axis": axis.name,
                        "original_weight": axis.weight,
                        "effective_weight": raw_weights[axis.name],
                        "kappa": kappa,
                    },
                )

    return raw_weights
