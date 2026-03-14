"""Pydantic data models for AutoEmailTrust v3.5.

TrustVector is dict[str, float] validated against spec.yaml axis names,
NOT a dynamically generated pydantic model.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, model_validator

if TYPE_CHECKING:
    from autotrust.config import Spec


# ---------------------------------------------------------------------------
# TrustVector validation
# ---------------------------------------------------------------------------

def validate_trust_vector(v: dict[str, float], spec: Spec) -> dict[str, float]:
    """Validate that trust vector keys match spec axis names and values are floats in [0, 1].

    Raises ValueError if keys don't match or values are invalid.
    """
    expected_names = {a.name for a in spec.trust_axes}
    actual_names = set(v.keys())

    missing = expected_names - actual_names
    if missing:
        raise ValueError(f"Trust vector missing axes: {missing}")

    extra = actual_names - expected_names
    if extra:
        raise ValueError(f"Trust vector has unknown axes: {extra}")

    for name, score in v.items():
        if not isinstance(score, (int, float)):
            raise TypeError(f"Trust vector value for '{name}' must be float, got {type(score).__name__}")
        score_f = float(score)
        if not (0.0 <= score_f <= 1.0):
            raise ValueError(f"Trust vector value for '{name}' must be in [0, 1], got {score_f}")

    return v


# ---------------------------------------------------------------------------
# Core data models
# ---------------------------------------------------------------------------

class Email(BaseModel):
    from_addr: str
    to_addr: str
    subject: str
    body: str
    timestamp: datetime
    reply_depth: int


class EmailChain(BaseModel):
    chain_id: str
    emails: list[Email]
    labels: dict[str, float]
    trust_vector: dict[str, float]
    composite: float
    flags: list[str]


class Explanation(BaseModel):
    reasons: list[str]
    summary: str


class ScorerOutput(BaseModel):
    trust_vector: dict[str, float]
    explanation: Explanation

    @model_validator(mode="after")
    def _validate_trust_vector(self) -> ScorerOutput:
        """Validate trust_vector keys against spec.yaml axis names at construction time.

        Only validates when the spec singleton is already loaded (avoids
        circular imports and allows test fixtures to construct without a spec).
        """
        from autotrust.config import _spec
        if _spec is not None:
            validate_trust_vector(self.trust_vector, _spec)
        return self


# ---------------------------------------------------------------------------
# Experiment and run models
# ---------------------------------------------------------------------------

class ExperimentResult(BaseModel):
    run_id: str
    change_description: str
    per_axis_scores: dict[str, float]
    composite: float
    fp_rate: float
    judge_agreement: float
    gold_agreement: float
    explanation_quality: float
    downweighted_axes: list[str]
    gate_results: dict[str, bool]
    cost: float
    wall_time: float


class RunArtifacts(BaseModel):
    metrics_json: Path
    predictions_jsonl: Path
    config_json: Path
    summary_txt: Path


# ---------------------------------------------------------------------------
# Gold set models
# ---------------------------------------------------------------------------

class GoldChain(EmailChain):
    annotator_scores: dict[str, list[float]]
    consensus_labels: dict[str, float]
    kappa: dict[str, float]
    opus_agreement: dict[str, float]


class CalibrationReport(BaseModel):
    per_axis_kappa: dict[str, float]
    effective_weights: dict[str, float]
    flagged_axes: list[str]
    downweight_amounts: dict[str, float]
