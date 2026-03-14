"""Tests for autotrust.observe -- structured logging and run artifacts."""

import json
import pytest
from pathlib import Path

from autotrust.config import load_spec
from autotrust.schemas import ExperimentResult


@pytest.fixture
def spec():
    return load_spec(Path(__file__).parent.parent / "spec.yaml")


@pytest.fixture
def sample_result():
    return ExperimentResult(
        run_id="test-run-001",
        change_description="test experiment",
        per_axis_scores={"phish": 0.9, "truthfulness": 0.8},
        composite=0.85,
        fp_rate=0.05,
        judge_agreement=0.92,
        gold_agreement=0.88,
        explanation_quality=0.75,
        downweighted_axes=["deceit"],
        gate_results={"composite": True, "gold": True, "explanation": True},
        cost=1.50,
        wall_time=120.0,
    )


def test_start_run_creates_directory(tmp_path, spec):
    """start_run() creates runs/<run_id>/ directory."""
    from autotrust.observe import start_run

    ctx = start_run(spec, base_dir=tmp_path)
    assert ctx.run_dir.exists()
    assert ctx.run_dir.is_dir()


def test_start_run_snapshots_config(tmp_path, spec):
    """start_run() writes config.json with spec snapshot."""
    from autotrust.observe import start_run

    ctx = start_run(spec, base_dir=tmp_path)
    config_path = ctx.run_dir / "config.json"
    assert config_path.exists()
    data = json.loads(config_path.read_text())
    assert "trust_axes" in data


def test_log_experiment_writes_metrics(tmp_path, spec, sample_result):
    """log_experiment() appends to metrics.jsonl with gate results."""
    from autotrust.observe import start_run, log_experiment

    ctx = start_run(spec, base_dir=tmp_path)
    log_experiment(ctx, sample_result)
    log_experiment(ctx, sample_result)  # log twice to verify append
    metrics_path = ctx.run_dir / "metrics.jsonl"
    assert metrics_path.exists()
    lines = metrics_path.read_text().strip().split("\n")
    assert len(lines) == 2  # both experiments persisted
    data = json.loads(lines[0])
    assert data["composite"] == 0.85
    assert data["gate_results"]["gold"] is True


def test_log_predictions_writes_jsonl(tmp_path, spec):
    """log_predictions() writes predictions.jsonl."""
    from autotrust.observe import start_run, log_predictions

    ctx = start_run(spec, base_dir=tmp_path)
    predictions = [
        {"chain_id": "c1", "trust_vector": {"phish": 0.9}},
        {"chain_id": "c2", "trust_vector": {"phish": 0.1}},
    ]
    log_predictions(ctx, predictions)
    pred_path = ctx.run_dir / "predictions.jsonl"
    assert pred_path.exists()
    lines = pred_path.read_text().strip().split("\n")
    assert len(lines) == 2


def test_finalize_run_writes_summary(tmp_path, spec):
    """finalize_run() writes summary.txt."""
    from autotrust.observe import start_run, finalize_run

    ctx = start_run(spec, base_dir=tmp_path)
    artifacts = finalize_run(ctx)
    assert artifacts.summary_txt.exists()
    content = artifacts.summary_txt.read_text()
    assert "Run ID" in content


def test_log_downweight_warning(tmp_path, spec, caplog):
    """When axes are downweighted, a warning is logged."""
    from autotrust.observe import start_run, log_downweight_warning
    import logging

    ctx = start_run(spec, base_dir=tmp_path)
    with caplog.at_level(logging.WARNING):
        log_downweight_warning(ctx, "deceit", 0.10, 0.05, 0.5)
    assert any("deceit" in record.message for record in caplog.records)
