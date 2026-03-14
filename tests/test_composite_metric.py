"""Tests for eval.py composite metric and keep/discard logic."""

import pytest
from pathlib import Path
from autotrust.config import load_spec
from autotrust.schemas import CalibrationReport


@pytest.fixture
def spec():
    return load_spec(Path(__file__).parent.parent / "spec.yaml")


@pytest.fixture
def perfect_calibration(spec):
    """CalibrationReport with perfect Kappa (no downweighting)."""
    return CalibrationReport(
        per_axis_kappa={a.name: 1.0 for a in spec.trust_axes},
        effective_weights={a.name: a.weight for a in spec.trust_axes},
        flagged_axes=[],
        downweight_amounts={},
    )


@pytest.fixture
def per_axis_scores(spec):
    """Perfect scores for all axes."""
    return {a.name: 0.9 for a in spec.trust_axes}


def test_composite_binary_uses_f1(spec):
    """Binary axis dispatches to F1 computation."""
    from autotrust.eval import score_predictions

    # Create predictions and ground truth for phish (binary)
    preds = [{"phish": 1.0}, {"phish": 0.0}, {"phish": 1.0}]
    truth = [{"phish": 1.0}, {"phish": 0.0}, {"phish": 1.0}]
    result = score_predictions(preds, truth, spec)
    assert "phish" in result
    assert result["phish"] == 1.0  # perfect F1


def test_composite_continuous_uses_agreement(spec):
    """Continuous axis with metric=agreement dispatches correctly."""
    from autotrust.eval import score_predictions

    preds = [{"truthfulness": 0.8}, {"truthfulness": 0.7}]
    truth = [{"truthfulness": 0.8}, {"truthfulness": 0.7}]
    result = score_predictions(preds, truth, spec)
    assert "truthfulness" in result
    assert result["truthfulness"] == 1.0  # perfect agreement


def test_composite_continuous_uses_recall(spec):
    """Continuous axis with metric=recall dispatches correctly (deceit)."""
    from autotrust.eval import score_predictions

    # For recall: all positives correctly identified
    preds = [{"deceit": 0.9}, {"deceit": 0.0}]
    truth = [{"deceit": 1.0}, {"deceit": 0.0}]
    result = score_predictions(preds, truth, spec)
    assert "deceit" in result


def test_composite_formula_matches_weights(spec, perfect_calibration, per_axis_scores):
    """composite = sum(weight_i * metric_i) + penalty_weight * fp_rate."""
    from autotrust.eval import compute_composite

    fp_rate = 0.3
    composite = compute_composite(per_axis_scores, spec, perfect_calibration, fp_rate=fp_rate)
    expected = sum(a.weight * per_axis_scores[a.name] for a in spec.trust_axes)
    # Apply composite penalties proportionally
    fp_penalty_weight = spec.composite_penalties.get("false_positive_rate", 0.0)
    expected += fp_penalty_weight * fp_rate
    assert abs(composite - expected) < 1e-6


def test_composite_penalties_applied(spec, perfect_calibration, per_axis_scores):
    """false_positive_rate penalty reduces composite when FP rate > 0."""
    from autotrust.eval import compute_composite

    # With fp_rate=0.0 (default), no penalty applied
    composite_no_fp = compute_composite(per_axis_scores, spec, perfect_calibration, fp_rate=0.0)
    # With fp_rate=1.0, full penalty: -0.15 * 1.0 = -0.15
    composite_full_fp = compute_composite(per_axis_scores, spec, perfect_calibration, fp_rate=1.0)
    assert composite_full_fp < composite_no_fp
    # The difference should be the penalty weight * fp_rate
    fp_penalty = spec.composite_penalties.get("false_positive_rate", 0.0)
    assert abs((composite_full_fp - composite_no_fp) - fp_penalty) < 1e-6


def test_composite_zero_weighted_axis(spec, perfect_calibration):
    """Axis with weight 0.0 does not affect composite."""
    from autotrust.eval import compute_composite

    scores_a = {a.name: 0.9 for a in spec.trust_axes}
    scores_b = {a.name: 0.9 for a in spec.trust_axes}
    scores_b["verify_by_search"] = 0.1  # change zero-weighted axis

    c_a = compute_composite(scores_a, spec, perfect_calibration)
    c_b = compute_composite(scores_b, spec, perfect_calibration)
    assert abs(c_a - c_b) < 1e-6


# ---------------------------------------------------------------------------
# Keep/Discard tests
# ---------------------------------------------------------------------------

def test_keep_all_gates_pass():
    """composite improved + gold ok + explanation ok -> keep."""
    from autotrust.eval import keep_or_discard
    assert keep_or_discard(True, True, True) is True


def test_discard_composite_fails():
    """composite not improved -> discard."""
    from autotrust.eval import keep_or_discard
    assert keep_or_discard(False, True, True) is False


def test_discard_gold_fails():
    """gold veto -> discard even if composite improved."""
    from autotrust.eval import keep_or_discard
    assert keep_or_discard(True, False, True) is False


def test_discard_explanation_fails():
    """explanation gate fails -> discard."""
    from autotrust.eval import keep_or_discard
    assert keep_or_discard(True, True, False) is False
