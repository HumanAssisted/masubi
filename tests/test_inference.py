"""Tests for autotrust.inference -- Local inference with escalation."""

import pytest
import torch
from pathlib import Path
from unittest.mock import MagicMock

from autotrust.config import load_spec
from autotrust.schemas import (
    StudentConfig,
    StudentOutput,
    CheckpointMeta,
    ScorerOutput,
    Explanation,
)


@pytest.fixture
def spec():
    return load_spec(Path(__file__).parent.parent / "spec.yaml")


@pytest.fixture
def student_config():
    return StudentConfig(
        hidden_size=128,
        num_layers=2,
        vocab_size=1000,
        max_seq_len=64,
        num_axes=10,
        num_reason_tags=20,
    )


@pytest.fixture
def checkpoint_path(tmp_path, student_config):
    """Create a real checkpoint for testing."""
    from autotrust.student import DenseStudent
    from autotrust.export import export_pytorch

    model = DenseStudent.from_config(student_config)
    meta = CheckpointMeta(
        stage="dense_baseline",
        experiment_num=1,
        composite=0.80,
        path=tmp_path / "test_model.pt",
        param_count=model.param_count(),
    )
    export_pytorch(model, student_config, meta, tmp_path / "test_model.pt")
    return tmp_path / "test_model.pt"


def test_local_inference_loads_checkpoint(checkpoint_path):
    """LocalInference(path) loads model from checkpoint."""
    from autotrust.inference import LocalInference
    inference = LocalInference(checkpoint_path)
    assert inference.model is not None
    assert inference.config is not None
    assert inference.meta is not None


def test_local_inference_scores_text(checkpoint_path, spec):
    """score_text(text) returns ScorerOutput with valid trust vector."""
    from autotrust.inference import LocalInference
    inference = LocalInference(checkpoint_path)
    axis_names = [a.name for a in spec.trust_axes]
    reason_tags = ["phish_detected", "manipulation_detected"]

    output = inference.score_text(
        "This is a test email about a suspicious offer",
        axis_names=axis_names,
        reason_tag_names=reason_tags,
    )
    assert isinstance(output, ScorerOutput)
    assert isinstance(output.trust_vector, dict)
    assert len(output.trust_vector) == len(axis_names)


def test_local_inference_no_api_dependency(checkpoint_path, spec, monkeypatch):
    """Scoring works without any API keys set."""
    from autotrust.inference import LocalInference
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("HYPERBOLIC_API_KEY", raising=False)

    inference = LocalInference(checkpoint_path)
    axis_names = [a.name for a in spec.trust_axes]
    output = inference.score_text(
        "test email",
        axis_names=axis_names,
        reason_tag_names=["tag1"],
    )
    assert isinstance(output, ScorerOutput)


def test_escalation_decision_true(spec):
    """should_escalate returns True when escalate flag is set and spec allows it."""
    from autotrust.inference import should_escalate

    student_output = StudentOutput(
        trust_vector={"phish": 0.9},
        reason_tags=["phish"],
        escalate=True,
    )
    assert should_escalate(student_output, spec) is True


def test_escalation_decision_false(spec):
    """should_escalate returns False when escalate flag is False."""
    from autotrust.inference import should_escalate

    student_output = StudentOutput(
        trust_vector={"phish": 0.1},
        reason_tags=[],
        escalate=False,
    )
    assert should_escalate(student_output, spec) is False


def test_escalation_disabled_in_spec(spec, monkeypatch):
    """Returns False when spec.production.escalate_on_flag is False."""
    from autotrust.inference import should_escalate

    # Monkey-patch the production config
    spec.production.escalate_on_flag = False

    student_output = StudentOutput(
        trust_vector={"phish": 0.9},
        reason_tags=["phish"],
        escalate=True,
    )
    assert should_escalate(student_output, spec) is False

    # Restore
    spec.production.escalate_on_flag = True


def test_score_with_fallback_escalates(checkpoint_path, spec):
    """score_with_fallback calls judge when escalation triggered."""
    from autotrust.inference import LocalInference

    inference = LocalInference(checkpoint_path)
    axis_names = [a.name for a in spec.trust_axes]

    mock_judge = MagicMock()
    mock_judge.judge.return_value = {"deceit": 0.95}

    # Force escalation by using a student output that escalates
    output = inference.score_with_fallback(
        "suspicious email",
        axis_names=axis_names,
        reason_tag_names=["tag1"],
        judge=mock_judge,
        spec=spec,
        force_escalate=True,
    )
    assert isinstance(output, ScorerOutput)
    mock_judge.judge.assert_called_once()


def test_score_with_fallback_skips_judge(checkpoint_path, spec):
    """Does not call judge when escalation is disabled in spec."""
    from autotrust.inference import LocalInference

    inference = LocalInference(checkpoint_path)
    axis_names = [a.name for a in spec.trust_axes]

    mock_judge = MagicMock()

    # Disable escalation in spec so the model's escalate flag is ignored
    original_flag = spec.production.escalate_on_flag
    spec.production.escalate_on_flag = False
    try:
        output = inference.score_with_fallback(
            "safe email",
            axis_names=axis_names,
            reason_tag_names=["tag1"],
            judge=mock_judge,
            spec=spec,
            force_escalate=False,
        )
        assert isinstance(output, ScorerOutput)
        mock_judge.judge.assert_not_called()
    finally:
        spec.production.escalate_on_flag = original_flag


def test_student_output_to_scorer_output():
    """Conversion from StudentOutput to ScorerOutput preserves trust vector."""
    from autotrust.inference import student_output_to_scorer_output

    # Must include all 10 axes to pass ScorerOutput validation when spec is loaded
    trust_vector = {
        "phish": 0.9,
        "truthfulness": 0.5,
        "verify_by_search": 0.1,
        "manipulation": 0.3,
        "deceit": 0.2,
        "vulnerability_risk": 0.1,
        "subtle_toxicity": 0.1,
        "polarization": 0.05,
        "classic_email_metrics": 0.1,
        "authority_impersonation": 0.15,
    }
    student_out = StudentOutput(
        trust_vector=trust_vector,
        reason_tags=["phish_detected"],
        escalate=False,
    )
    scorer_out = student_output_to_scorer_output(student_out)
    assert isinstance(scorer_out, ScorerOutput)
    assert scorer_out.trust_vector == student_out.trust_vector
    assert "phish_detected" in scorer_out.explanation.reasons


def test_inference_pipeline_end_to_end(checkpoint_path, spec):
    """Create model, export checkpoint, load via LocalInference, score text."""
    from autotrust.inference import LocalInference

    inference = LocalInference(checkpoint_path)
    axis_names = [a.name for a in spec.trust_axes]

    output = inference.score_text(
        "Hello, I am the CEO and need you to wire $50,000 immediately.",
        axis_names=axis_names,
        reason_tag_names=["urgency", "authority"],
    )
    assert isinstance(output, ScorerOutput)
    assert len(output.trust_vector) == len(axis_names)
    assert isinstance(output.explanation.summary, str)
