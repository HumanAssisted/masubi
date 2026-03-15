"""Tests for autotrust/dashboard/data_loader.py -- filesystem-based run data reader."""

import json
from pathlib import Path

import pytest


@pytest.fixture
def sample_experiment():
    """A minimal experiment result dict matching ExperimentResult fields."""
    return {
        "run_id": "test_run",
        "change_description": "Agent edit",
        "per_axis_scores": {"phish": 0.8, "manipulation": 0.7, "urgency": 0.6},
        "composite": 0.72,
        "fp_rate": 0.05,
        "judge_agreement": 0.9,
        "gold_agreement": 0.85,
        "explanation_quality": 0.75,
        "downweighted_axes": [],
        "gate_results": {"composite": True, "gold": True, "explanation": True},
        "cost": 0.03,
        "wall_time": 120.5,
    }


def _create_run_dir(base_dir: Path, run_id: str, experiments: list[dict], summary_lines: list[str] | None = None):
    """Helper: create a run directory with metrics.jsonl and optional summary.txt."""
    run_dir = base_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = run_dir / "metrics.jsonl"
    with open(metrics_path, "w") as f:
        for exp in experiments:
            f.write(json.dumps(exp) + "\n")
    if summary_lines is not None:
        summary_path = run_dir / "summary.txt"
        summary_path.write_text("\n".join(summary_lines))
    return run_dir


def test_list_runs_returns_metadata(tmp_path, sample_experiment):
    """list_runs returns both runs with correct metadata."""
    from autotrust.dashboard.data_loader import list_runs

    exp1 = {**sample_experiment, "composite": 0.70, "cost": 0.02}
    exp2 = {**sample_experiment, "composite": 0.75, "cost": 0.03}
    _create_run_dir(tmp_path, "run_001", [exp1, exp2], [
        "Run ID: run_001",
        "Best composite: 0.75",
        "Total cost: $0.05",
    ])
    _create_run_dir(tmp_path, "run_002", [sample_experiment], [
        "Run ID: run_002",
        "Best composite: 0.72",
        "Total cost: $0.03",
    ])

    runs = list_runs(base_dir=tmp_path)
    assert len(runs) == 2
    run_ids = {r["run_id"] for r in runs}
    assert "run_001" in run_ids
    assert "run_002" in run_ids

    run1 = next(r for r in runs if r["run_id"] == "run_001")
    assert run1["experiment_count"] == 2


def test_list_runs_empty_dir(tmp_path):
    """With no run directories, returns empty list."""
    from autotrust.dashboard.data_loader import list_runs

    runs = list_runs(base_dir=tmp_path)
    assert runs == []


def test_list_runs_detects_running_status(tmp_path, sample_experiment):
    """Run with metrics.jsonl but no summary.txt should show status 'running'."""
    from autotrust.dashboard.data_loader import list_runs

    # Create run with only metrics.jsonl (no summary.txt)
    _create_run_dir(tmp_path, "run_active", [sample_experiment])

    runs = list_runs(base_dir=tmp_path)
    assert len(runs) == 1
    assert runs[0]["status"] == "running"


def test_load_run_metrics_parses_jsonl(tmp_path, sample_experiment):
    """load_run_metrics returns list of 3 dicts with correct fields."""
    from autotrust.dashboard.data_loader import load_run_metrics

    exps = [
        {**sample_experiment, "composite": 0.70},
        {**sample_experiment, "composite": 0.72},
        {**sample_experiment, "composite": 0.75},
    ]
    _create_run_dir(tmp_path, "run_001", exps)

    metrics = load_run_metrics("run_001", base_dir=tmp_path)
    assert len(metrics) == 3
    assert metrics[0]["composite"] == 0.70
    assert metrics[2]["composite"] == 0.75
    assert "gate_results" in metrics[1]


def test_load_run_metrics_skips_malformed_lines(tmp_path, sample_experiment):
    """Write 3 lines with one invalid JSON, verify returns 2 valid records."""
    from autotrust.dashboard.data_loader import load_run_metrics

    run_dir = tmp_path / "run_bad"
    run_dir.mkdir()
    metrics_path = run_dir / "metrics.jsonl"
    with open(metrics_path, "w") as f:
        f.write(json.dumps(sample_experiment) + "\n")
        f.write("THIS IS NOT VALID JSON\n")
        f.write(json.dumps({**sample_experiment, "composite": 0.99}) + "\n")

    metrics = load_run_metrics("run_bad", base_dir=tmp_path)
    assert len(metrics) == 2


def test_load_run_metrics_missing_file(tmp_path):
    """Non-existent run_id returns empty list."""
    from autotrust.dashboard.data_loader import load_run_metrics

    metrics = load_run_metrics("nonexistent", base_dir=tmp_path)
    assert metrics == []


def test_load_latest_metrics_incremental(tmp_path, sample_experiment):
    """load_latest_metrics(after_line=3) returns only lines 4-5."""
    from autotrust.dashboard.data_loader import load_latest_metrics

    exps = [{**sample_experiment, "composite": 0.70 + i * 0.01} for i in range(5)]
    _create_run_dir(tmp_path, "run_inc", exps)

    records, total = load_latest_metrics("run_inc", after_line=3, base_dir=tmp_path)
    assert len(records) == 2
    assert total == 5
    assert records[0]["composite"] == pytest.approx(0.73, abs=0.001)


def test_load_run_summary_returns_text(tmp_path):
    """load_run_summary returns summary.txt content."""
    from autotrust.dashboard.data_loader import load_run_summary

    run_dir = tmp_path / "run_sum"
    run_dir.mkdir()
    summary_text = "Run ID: run_sum\nExperiments: 5\nBest composite: 0.80"
    (run_dir / "summary.txt").write_text(summary_text)

    result = load_run_summary("run_sum", base_dir=tmp_path)
    assert "Run ID: run_sum" in result
    assert "Best composite: 0.80" in result


def test_load_calibration_parses_json(tmp_path):
    """load_calibration returns dict with per_axis_kappa."""
    from autotrust.dashboard.data_loader import load_calibration

    cal_data = {
        "per_axis_kappa": {"phish": 0.9, "manipulation": 0.7},
        "effective_weights": {"phish": 0.3, "manipulation": 0.2},
        "flagged_axes": ["manipulation"],
        "downweight_amounts": {"manipulation": 0.05},
    }
    cal_path = tmp_path / "calibration.json"
    cal_path.write_text(json.dumps(cal_data))

    result = load_calibration(path=cal_path)
    assert "per_axis_kappa" in result
    assert result["per_axis_kappa"]["phish"] == 0.9


def test_format_run_choice_includes_status_and_summary():
    """format_run_choice returns a readable label plus the original run_id value."""
    from autotrust.dashboard.data_loader import format_run_choice

    label, value = format_run_choice(
        {
            "run_id": "run_001",
            "status": "running",
            "experiment_count": 7,
            "best_composite": 0.7243,
            "total_cost": 0.21,
        }
    )

    assert value == "run_001"
    assert "running" in label
    assert "7 exp" in label
    assert "0.7243" in label
    assert "$0.21" in label
