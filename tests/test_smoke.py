"""Smoke tests -- end-to-end verification with minimal data.

Tests the complete pipeline with 10 chains: scoring, three-gate evaluation,
explanation gate modes, and structured output validation.
"""

import pytest
from datetime import datetime, timezone
from pathlib import Path

from autotrust.config import load_spec
from autotrust.schemas import (
    Email, EmailChain, Explanation, ScorerOutput,
    CalibrationReport, validate_trust_vector,
)
from autotrust.eval import (
    score_predictions,
    compute_composite,
    gold_regression_gate,
    explanation_quality,
    explanation_gate,
    keep_or_discard,
)


@pytest.fixture
def spec():
    return load_spec(Path(__file__).parent.parent / "spec.yaml")


@pytest.fixture
def axis_names(spec):
    return [a.name for a in spec.trust_axes]


@pytest.fixture
def perfect_calibration(spec):
    return CalibrationReport(
        per_axis_kappa={a.name: 1.0 for a in spec.trust_axes},
        effective_weights={a.name: a.weight for a in spec.trust_axes},
        flagged_axes=[],
        downweight_amounts={},
    )


def make_dummy_chain(chain_id: str, axis_names: list[str], **axis_scores) -> EmailChain:
    """Create an EmailChain with given scores."""
    email = Email(
        from_addr="sender@example.com",
        to_addr="recipient@example.com",
        subject=f"Test email {chain_id}",
        body="This is a test email body for smoke testing.",
        timestamp=datetime.now(timezone.utc),
        reply_depth=0,
    )
    scores = {a: axis_scores.get(a, 0.3) for a in axis_names}
    return EmailChain(
        chain_id=chain_id,
        emails=[email],
        labels=scores,
        trust_vector=scores,
        composite=0.5,
        flags=[],
    )


def make_eval_set(n: int, axis_names: list[str]) -> list[EmailChain]:
    """Generate n diverse chains for evaluation."""
    chains = []
    for i in range(n):
        score_base = (i % 5) * 0.2  # 0.0, 0.2, 0.4, 0.6, 0.8
        chains.append(make_dummy_chain(
            f"eval-{i}", axis_names,
            **{a: min(1.0, score_base + 0.1 * (hash(a) % 3)) for a in axis_names}
        ))
    return chains


def make_gold_set(n: int, axis_names: list[str]) -> list[dict[str, float]]:
    """Generate n gold chain consensus labels."""
    return [
        {a: min(1.0, 0.5 + 0.05 * (i % 5)) for a in axis_names}
        for i in range(n)
    ]


class DummyScorer:
    """Dummy scorer that returns fixed ScorerOutput for testing."""

    def __init__(self, spec, trust_vector: dict[str, float] | None = None,
                 reasons: list[str] | None = None):
        self.spec = spec
        axis_names = [a.name for a in spec.trust_axes]
        self.trust_vector = trust_vector or {a: 0.5 for a in axis_names}
        self.reasons = reasons or ["phish", "manipulation"]

    def score_chain(self, chain):
        return ScorerOutput(
            trust_vector=self.trust_vector,
            explanation=Explanation(
                reasons=self.reasons,
                summary="Dummy scorer output.",
            ),
        )

    def score_batch(self, chains):
        return [self.score_chain(c) for c in chains]


# ---------------------------------------------------------------------------
# Smoke tests
# ---------------------------------------------------------------------------

def test_smoke_eval_10_chains(spec, axis_names):
    """10 synthetic chains -> score_predictions -> per-axis metrics for all axes."""
    eval_set = make_eval_set(10, axis_names)

    # Create predictions (same as labels for perfect scores)
    predictions = [c.trust_vector for c in eval_set]
    ground_truth = [c.labels for c in eval_set]

    metrics = score_predictions(predictions, ground_truth, spec)

    # All 10 axes should have metrics
    assert len(metrics) == 10
    for axis in spec.trust_axes:
        assert axis.name in metrics


def test_smoke_gold_10_chains(spec, axis_names):
    """10 gold chains with known labels -> gold_regression_gate pass/fail."""
    gold_set = make_gold_set(10, axis_names)

    # Predictions matching gold
    predictions = gold_set.copy()
    previous_best = {a: 0.5 for a in axis_names}

    passed, deltas = gold_regression_gate(predictions, gold_set, previous_best, spec)
    assert passed is True
    assert len(deltas) == 10


def test_smoke_full_loop_cycle(spec, axis_names, perfect_calibration):
    """Mock 1 iteration: score -> three gates -> keep/discard -> log."""
    scorer = DummyScorer(spec)
    eval_chains = make_eval_set(10, axis_names)
    gold_set = make_gold_set(10, axis_names)

    # Score
    outputs = scorer.score_batch(eval_chains)
    assert len(outputs) == 10

    # Predictions as dicts
    predictions = [o.trust_vector for o in outputs]
    ground_truth = [c.labels for c in eval_chains]

    # Per-axis metrics
    metrics = score_predictions(predictions, ground_truth, spec)

    # Composite
    composite = compute_composite(metrics, spec, perfect_calibration)
    assert isinstance(composite, float)

    # Gold gate
    previous_best = {a: 0.0 for a in axis_names}  # no previous -> no regression
    gold_ok, _ = gold_regression_gate(predictions, gold_set, previous_best, spec)

    # Explanation quality
    explanations = [o.explanation for o in outputs]
    expl_quality = explanation_quality(explanations, predictions, spec)
    assert 0.0 <= expl_quality <= 1.0

    # Explanation gate
    expl_ok, mode = explanation_gate(expl_quality, spec, has_baseline=False)
    assert mode == "warn"

    # Keep/discard
    keep = keep_or_discard(composite > 0.0, gold_ok, expl_ok)
    assert isinstance(keep, bool)


def test_smoke_keep_all_gates_pass(spec, axis_names, perfect_calibration):
    """Dummy scorer improves composite, passes gold, good explanations -> keep."""
    # All scores are 0.5, all flagged axes have reasons
    scorer = DummyScorer(spec, reasons=[a for a in axis_names])
    eval_chains = make_eval_set(10, axis_names)

    outputs = scorer.score_batch(eval_chains)
    predictions = [o.trust_vector for o in outputs]
    ground_truth = [c.labels for c in eval_chains]

    metrics = score_predictions(predictions, ground_truth, spec)
    composite = compute_composite(metrics, spec, perfect_calibration)

    # Gold: previous best is 0.0 for all axes
    gold_set = [p for p in predictions]
    previous_best = {a: 0.0 for a in axis_names}
    gold_ok, _ = gold_regression_gate(predictions, gold_set, previous_best, spec)

    explanations = [o.explanation for o in outputs]
    expl_quality_val = explanation_quality(explanations, predictions, spec)
    expl_ok, _ = explanation_gate(expl_quality_val, spec, has_baseline=False)

    keep = keep_or_discard(composite > 0.0, gold_ok, expl_ok)
    assert keep is True


def test_smoke_discard_gold_veto(spec, axis_names, perfect_calibration):
    """Scorer improves composite but degrades one gold axis -> discard."""
    scorer = DummyScorer(spec)
    eval_chains = make_eval_set(10, axis_names)

    outputs = scorer.score_batch(eval_chains)
    predictions = [o.trust_vector for o in outputs]

    # Gold set: predictions match gold
    gold_set = predictions.copy()
    # Previous best: phish was perfect -> current will be regression if we set previous high
    # The scorer outputs 0.5 for all axes
    # Agreement between pred (0.5) and gold (0.5) = 1.0
    # But if previous best was 1.0 for a continuous axis,
    # current agreement < 1.0 = regression
    previous_best = {a: 0.5 for a in axis_names}
    # Make truthfulness previous best very high
    previous_best["truthfulness"] = 1.1  # impossible to beat

    gold_ok, _ = gold_regression_gate(predictions, gold_set, previous_best, spec)
    assert gold_ok is False  # regression on truthfulness

    keep = keep_or_discard(True, gold_ok, True)
    assert keep is False


def test_smoke_explanation_warn_mode(spec, axis_names, perfect_calibration):
    """Before baseline, explanation gate warns but passes."""
    scorer = DummyScorer(spec, reasons=[])  # bad reasons
    eval_chains = make_eval_set(10, axis_names)
    outputs = scorer.score_batch(eval_chains)

    predictions = [o.trust_vector for o in outputs]
    explanations = [o.explanation for o in outputs]

    expl_quality_val = explanation_quality(explanations, predictions, spec)
    expl_ok, mode = explanation_gate(expl_quality_val, spec, has_baseline=False)

    assert mode == "warn"
    assert expl_ok is True  # warn mode always passes


def test_smoke_explanation_gate_mode_blocks(spec, axis_names, perfect_calibration):
    """After baseline, bad explanation quality -> discard."""
    # Use scores above flag_threshold (0.5) so axes get flagged,
    # but provide no reasons -- quality should be 0.0
    high_scores = {a: 0.8 for a in axis_names}
    scorer = DummyScorer(spec, trust_vector=high_scores, reasons=[])
    eval_chains = make_eval_set(10, axis_names)
    outputs = scorer.score_batch(eval_chains)

    predictions = [o.trust_vector for o in outputs]
    explanations = [o.explanation for o in outputs]

    expl_quality_val = explanation_quality(explanations, predictions, spec)
    expl_ok, mode = explanation_gate(expl_quality_val, spec, has_baseline=True)

    assert mode == "gate"
    # All axes score > 0.5 but no reasons -> quality should be 0.0
    assert expl_quality_val < spec.explanation.min_quality_threshold, (
        f"Expected quality < {spec.explanation.min_quality_threshold}, got {expl_quality_val}"
    )
    assert expl_ok is False


def test_smoke_structured_output_validation(spec, axis_names):
    """ScorerOutput with valid trust_vector and explanation.reasons passes validation."""
    tv = {a: 0.5 for a in axis_names}
    validated = validate_trust_vector(tv, spec)
    assert validated == tv

    output = ScorerOutput(
        trust_vector=tv,
        explanation=Explanation(reasons=["phish"], summary="Test"),
    )
    assert isinstance(output.trust_vector, dict)
    assert isinstance(output.explanation.reasons, list)


def test_smoke_structured_output_invalid(spec, axis_names):
    """ScorerOutput with missing axis in trust_vector fails validation."""
    tv = {a: 0.5 for a in axis_names}
    del tv["phish"]  # remove one axis

    with pytest.raises(ValueError, match="phish"):
        validate_trust_vector(tv, spec)
