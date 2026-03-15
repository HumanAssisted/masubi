"""Pydantic data models for Masubi.

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
    training_loss: dict[str, float] | None = None
    param_count: int | None = None
    expert_utilization: list[float] | None = None


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


# ---------------------------------------------------------------------------
# Student model types (Stage 2)
# ---------------------------------------------------------------------------

class StudentConfig(BaseModel):
    hidden_size: int
    num_layers: int
    vocab_size: int
    max_seq_len: int
    num_axes: int
    num_reason_tags: int


class MoEConfig(BaseModel):
    num_experts: int
    top_k: int
    capacity_factor: float = 1.0
    moe_layers: list[int]  # which layers are sparse
    routing_strategy: str = "top_k"  # top_k, noisy_top_k, expert_choice


class StudentOutput(BaseModel):
    trust_vector: dict[str, float]
    reason_tags: list[str]
    escalate: bool

    @model_validator(mode="after")
    def _validate_trust_vector(self) -> StudentOutput:
        """Validate trust_vector keys against spec.yaml axis names at construction time.

        Only validates when the spec singleton is already loaded (avoids
        circular imports and allows test fixtures to construct without a spec).
        """
        from autotrust.config import _spec
        if _spec is not None:
            validate_trust_vector(self.trust_vector, _spec)
        return self


class CheckpointMeta(BaseModel):
    stage: str  # "dense_baseline" or "moe_search"
    experiment_num: int
    composite: float
    path: Path
    param_count: int
    moe_config: MoEConfig | None = None


class TeacherArtifacts(BaseModel):
    prompt_pack_path: Path
    label_rules_path: Path
    explanation_schema_path: Path
    synth_data_dir: Path


def validate_moe_config(moe_config: MoEConfig, spec: Spec) -> None:
    """Validate MoE config against spec.yaml stage2 caps.

    Raises ValueError if config exceeds limits.
    """
    if spec.stage2 is None:
        raise ValueError("spec.yaml has no stage2 section")
    if moe_config.num_experts > spec.stage2.max_experts:
        raise ValueError(
            f"num_experts ({moe_config.num_experts}) exceeds max_experts ({spec.stage2.max_experts})"
        )
    if moe_config.top_k > spec.stage2.max_top_k:
        raise ValueError(
            f"top_k ({moe_config.top_k}) exceeds max_top_k ({spec.stage2.max_top_k})"
        )
