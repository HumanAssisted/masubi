"""Fixed evaluation policy -- three-gate keep/discard with auto-dispatch metrics.

Three gates (all must pass):
1. Composite score improved (Kappa-adjusted weights + penalties)
2. Gold-set veto passed (raw labels, NO downweighting, ALL axes including zero-weighted)
3. Explanation gate (warn_then_gate mode)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from sklearn.metrics import f1_score, recall_score

from autotrust.config import get_effective_weights

if TYPE_CHECKING:
    from autotrust.config import Spec
    from autotrust.providers import JudgeProvider
    from autotrust.schemas import CalibrationReport, Explanation

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Metric computation helpers
# ---------------------------------------------------------------------------

def compute_f1(preds: list[dict], truth: list[dict], axis_name: str) -> float:
    """Compute F1 score for a binary axis.

    Binarizes at 0.5 threshold for continuous predictions.
    """
    y_pred = [1 if p.get(axis_name, 0) >= 0.5 else 0 for p in preds]
    y_true = [1 if t.get(axis_name, 0) >= 0.5 else 0 for t in truth]
    if len(set(y_true)) < 2 and len(set(y_pred)) < 2:
        # Both all-same -> perfect if they match
        return 1.0 if y_pred == y_true else 0.0
    return float(f1_score(y_true, y_pred, zero_division=1.0))


def compute_agreement(preds: list[dict], truth: list[dict], axis_name: str) -> float:
    """Compute agreement as 1 - mean(|pred - truth|) for a continuous axis."""
    diffs = [abs(p.get(axis_name, 0) - t.get(axis_name, 0)) for p, t in zip(preds, truth)]
    return 1.0 - (sum(diffs) / len(diffs)) if diffs else 1.0


def compute_recall(preds: list[dict], truth: list[dict], axis_name: str) -> float:
    """Compute recall for an axis.

    For continuous predictions, binarizes at 0.5 threshold.
    """
    y_pred = [1 if p.get(axis_name, 0) >= 0.5 else 0 for p in preds]
    y_true = [1 if t.get(axis_name, 0) >= 0.5 else 0 for t in truth]
    if sum(y_true) == 0:
        return 1.0  # no positives -> perfect recall trivially
    return float(recall_score(y_true, y_pred, zero_division=1.0))


# ---------------------------------------------------------------------------
# Core evaluation functions
# ---------------------------------------------------------------------------

def score_predictions(
    predictions: list[dict[str, float]],
    ground_truth: list[dict[str, float]],
    spec: Spec,
) -> dict[str, float]:
    """Compute per-axis metrics by auto-dispatching based on axis type.

    Binary axes -> F1. Continuous axes -> agreement or recall (per axis.metric).
    """
    results: dict[str, float] = {}
    for axis in spec.trust_axes:
        if axis.type == "binary":
            results[axis.name] = compute_f1(predictions, ground_truth, axis.name)
        elif axis.metric == "recall":
            results[axis.name] = compute_recall(predictions, ground_truth, axis.name)
        else:  # agreement
            results[axis.name] = compute_agreement(predictions, ground_truth, axis.name)
    return results


def compute_composite(
    per_axis: dict[str, float],
    spec: Spec,
    calibration: CalibrationReport,
    fp_rate: float = 0.0,
) -> float:
    """Compute composite score using Kappa-adjusted weights + penalties.

    Uses get_effective_weights() from config.py for downweighting.
    Composite penalties scale with actual metrics (e.g., false_positive_rate
    penalty weight is multiplied by the actual FP rate).
    """
    effective_weights = get_effective_weights(spec, calibration.per_axis_kappa)

    composite = sum(
        effective_weights.get(axis.name, 0.0) * per_axis.get(axis.name, 0.0)
        for axis in spec.trust_axes
    )

    # Apply composite penalties proportionally
    # Each penalty value acts as a weight on the corresponding metric
    fp_penalty_weight = spec.composite_penalties.get("false_positive_rate", 0.0)
    composite += fp_penalty_weight * fp_rate

    return composite


def gold_regression_gate(
    predictions: list[dict[str, float]],
    gold_set: list[dict[str, float]],
    previous_best: dict[str, float],
    spec: Spec,
) -> tuple[bool, dict[str, float]]:
    """Compare per-axis performance against raw human consensus labels.

    NO Kappa downweighting. Checks ALL axes including zero-weighted ones.
    Returns (passed, per_axis_delta). Veto if ANY axis degrades.
    """
    # Reuse score_predictions for metric dispatch (DRY)
    current_performance = score_predictions(predictions, gold_set, spec)

    # Compute deltas against previous best
    deltas: dict[str, float] = {}
    passed = True
    for axis in spec.trust_axes:
        prev = previous_best.get(axis.name, 0.0)
        curr = current_performance.get(axis.name, 0.0)
        delta = curr - prev
        deltas[axis.name] = delta
        if delta < -1e-9:  # any regression -> veto
            logger.warning(
                "Gold gate veto: %s degraded by %.4f (%.4f -> %.4f)",
                axis.name, delta, prev, curr,
            )
            passed = False

    return passed, deltas


# ---------------------------------------------------------------------------
# Explanation quality and gate
# ---------------------------------------------------------------------------

def explanation_quality(
    explanations: list[Explanation],
    predictions: list[dict[str, float]],
    spec: Spec,
) -> float:
    """Compute explanation quality as mean(flagged_referenced / flagged_count).

    For each chain:
    - Count axes with score > flag_threshold
    - Check if explanation.reasons references each flagged axis
    - quality = correctly_referenced / flagged_count (1.0 if no flags)
    Returns mean across chains.
    """
    flag_threshold = spec.explanation.flag_threshold
    qualities: list[float] = []

    for explanation, pred_scores in zip(explanations, predictions):
        # Find flagged axes
        flagged = [
            a.name for a in spec.trust_axes
            if pred_scores.get(a.name, 0.0) > flag_threshold
        ]

        if not flagged:
            qualities.append(1.0)
            continue

        # Check which flagged axes are referenced in reasons
        reasons_set = set(explanation.reasons)
        referenced = sum(1 for axis in flagged if axis in reasons_set)
        quality = referenced / len(flagged)
        qualities.append(quality)

    return sum(qualities) / len(qualities) if qualities else 1.0


def explanation_gate(
    quality: float,
    spec: Spec,
    has_baseline: bool,
) -> tuple[bool, str]:
    """Apply explanation gate based on mode.

    Returns (passed, mode).
    - 'warn': logs but always passes (before baseline)
    - 'gate': blocks if quality < min_quality_threshold (after baseline)
    """
    if not has_baseline or not spec.explanation.gate_after_baseline:
        logger.info("Explanation gate: warn mode (quality=%.3f)", quality)
        return True, "warn"

    passed = quality >= spec.explanation.min_quality_threshold
    logger.info(
        "Explanation gate: gate mode (quality=%.3f, threshold=%.3f, %s)",
        quality, spec.explanation.min_quality_threshold,
        "passed" if passed else "blocked",
    )
    return passed, "gate"


# ---------------------------------------------------------------------------
# Keep/discard decision
# ---------------------------------------------------------------------------

def keep_or_discard(
    composite_improved: bool,
    gold_ok: bool,
    explanation_ok: bool,
) -> bool:
    """All three gates must pass to keep an experiment."""
    return composite_improved and gold_ok and explanation_ok


# ---------------------------------------------------------------------------
# Judge fallback / escalation
# ---------------------------------------------------------------------------

def run_judge_fallback(
    chain: Any,
    fast_scores: dict[str, float],
    judge: JudgeProvider,
    spec: Spec,
) -> dict[str, float]:
    """Escalate to judge if any subtle axis scores > escalate_threshold.

    Checks axis_groups.subtle. If triggered, calls judge on subtle axes
    and merges results with fast_scores.
    """
    subtle_axes = spec.axis_groups.subtle
    threshold = spec.judge.escalate_threshold

    # Check if any subtle axis exceeds threshold
    escalated_axes = [
        axis for axis in subtle_axes
        if fast_scores.get(axis, 0.0) > threshold
    ]

    if not escalated_axes:
        return fast_scores

    logger.info("Escalating to judge for axes: %s", escalated_axes)
    judge_scores = judge.judge(chain, escalated_axes)

    # Merge: judge scores override fast scores for escalated axes
    merged = dict(fast_scores)
    merged.update(judge_scores)
    return merged
