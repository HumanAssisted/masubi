"""Tests for autotrust/dashboard/log_formatter.py -- experiment log formatting."""

import pytest


@pytest.fixture
def kept_experiment():
    """Experiment result dict for a KEPT experiment."""
    return {
        "run_id": "test_run",
        "change_description": "Agent edit (experiment 3)",
        "per_axis_scores": {"phish": 0.85, "manipulation": 0.72, "urgency": 0.68},
        "composite": 0.724,
        "fp_rate": 0.05,
        "judge_agreement": 0.9,
        "gold_agreement": 0.85,
        "explanation_quality": 0.75,
        "downweighted_axes": [],
        "gate_results": {"composite": True, "gold": True, "explanation": True},
        "cost": 0.03,
        "wall_time": 180.5,
    }


@pytest.fixture
def discarded_experiment():
    """Experiment result dict for a DISCARDED experiment."""
    return {
        "run_id": "test_run",
        "change_description": "Agent edit (experiment 4)",
        "per_axis_scores": {"phish": 0.80, "manipulation": 0.65, "urgency": 0.60},
        "composite": 0.690,
        "fp_rate": 0.08,
        "judge_agreement": 0.85,
        "gold_agreement": 0.70,
        "explanation_quality": 0.60,
        "downweighted_axes": [],
        "gate_results": {"composite": False, "gold": True, "explanation": False},
        "cost": 0.04,
        "wall_time": 220.0,
    }


def test_format_log_entry_kept(kept_experiment):
    """Format a KEPT experiment with positive delta and experiment number."""
    from autotrust.dashboard.log_formatter import format_experiment_log_entry

    entry = format_experiment_log_entry(kept_experiment, prev_composite=0.693, experiment_num=3)
    assert "KEPT" in entry
    assert "0.724" in entry
    assert "+" in entry  # positive delta
    assert "Exp #3" in entry


def test_format_log_entry_discarded(discarded_experiment):
    """Format a DISCARDED experiment, verify shows which gates failed."""
    from autotrust.dashboard.log_formatter import format_experiment_log_entry

    entry = format_experiment_log_entry(discarded_experiment, prev_composite=0.724)
    assert "DISCARDED" in entry
    assert "0.690" in entry


def test_format_log_entry_baseline(kept_experiment):
    """First experiment (no previous composite), verify shows '(baseline)'."""
    from autotrust.dashboard.log_formatter import format_experiment_log_entry

    entry = format_experiment_log_entry(kept_experiment, prev_composite=None)
    assert "baseline" in entry.lower()


def test_format_experiment_detail_per_axis(kept_experiment):
    """Expanded detail includes per-axis scores table with deltas."""
    from autotrust.dashboard.log_formatter import format_experiment_detail

    prev_best = {
        "per_axis_scores": {"phish": 0.80, "manipulation": 0.70, "urgency": 0.65},
        "composite": 0.693,
    }
    detail = format_experiment_detail(kept_experiment, prev_best)
    assert "phish" in detail
    assert "manipulation" in detail
    assert "urgency" in detail


def test_format_experiment_detail_gate_reasons(kept_experiment):
    """Expanded detail includes gate pass/fail with reasons."""
    from autotrust.dashboard.log_formatter import format_experiment_detail

    detail = format_experiment_detail(kept_experiment, None)
    assert "composite" in detail.lower()
    assert "gold" in detail.lower()
    assert "explanation" in detail.lower()


def test_format_log_stream_newest_first(kept_experiment, discarded_experiment):
    """format_log_stream with 3 experiments returns entries in reverse order."""
    from autotrust.dashboard.log_formatter import format_log_stream

    metrics = [
        {**kept_experiment, "composite": 0.681},
        {**kept_experiment, "composite": 0.693},
        {**discarded_experiment, "composite": 0.690},
    ]
    stream = format_log_stream(metrics)
    lines = [ln for ln in stream.strip().split("\n") if ln.strip()]
    # Newest first: 0.690 should appear before 0.681
    first_690 = next(i for i, ln in enumerate(lines) if "0.690" in ln)
    first_681 = next(i for i, ln in enumerate(lines) if "0.681" in ln)
    assert first_690 < first_681


def test_format_log_entry_includes_stage2_metrics(kept_experiment):
    """Stage 2 log lines include compact loss and param-count telemetry."""
    from autotrust.dashboard.log_formatter import format_experiment_log_entry

    result = {
        **kept_experiment,
        "training_loss": {"total_loss": 0.612},
        "param_count": 123_000_000,
    }

    entry = format_experiment_log_entry(result, prev_composite=0.700, experiment_num=4)
    assert "loss=0.612" in entry
    assert "params=123.0M" in entry
