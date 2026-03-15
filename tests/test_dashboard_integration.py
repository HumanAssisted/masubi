"""Integration tests for dashboard.py -- Gradio Blocks app."""

import json
from unittest.mock import patch

import pytest


@pytest.fixture
def sample_metrics():
    """List of experiment dicts for testing."""
    base = {
        "run_id": "test_run",
        "change_description": "Agent edit",
        "per_axis_scores": {"phish": 0.8, "manipulation": 0.7, "urgency": 0.6},
        "fp_rate": 0.05,
        "judge_agreement": 0.9,
        "gold_agreement": 0.85,
        "explanation_quality": 0.75,
        "downweighted_axes": [],
        "cost": 0.03,
        "wall_time": 120.0,
    }
    return [
        {**base, "composite": 0.681, "gate_results": {"composite": True, "gold": True, "explanation": True}},
        {**base, "composite": 0.693, "gate_results": {"composite": True, "gold": True, "explanation": True}},
        {**base, "composite": 0.724, "gate_results": {"composite": True, "gold": True, "explanation": True}},
    ]


def test_dashboard_launches_without_error():
    """Import dashboard module and verify Gradio Blocks app can be instantiated."""
    from dashboard import create_app

    app = create_app()
    assert app is not None


def test_dashboard_has_required_components():
    """Verify the dashboard contains required UI components."""
    from dashboard import create_app

    app = create_app()
    assert len(app.blocks) > 0

    block_types = [type(b).__name__ for b in app.blocks.values()]
    assert "Plot" in block_types
    assert "Markdown" in block_types


def test_poll_live_returns_correct_tuple(sample_metrics):
    """With fixture metrics, verify poll_live returns updated values."""
    from dashboard import poll_live, _run_manager, _poll_cache

    old_run_id = _run_manager._current_run_id
    old_status = _run_manager._status
    old_cache = dict(_poll_cache)
    try:
        _run_manager._current_run_id = "test_run"
        _run_manager._status = "running"

        with patch("dashboard.data_loader.load_latest_metrics", return_value=(sample_metrics, 3)):
            result = poll_live()
            assert result is not None
            assert isinstance(result, tuple)
            assert len(result) == 6  # status, banner, composite, gates, radar, log
    finally:
        _run_manager._current_run_id = old_run_id
        _run_manager._status = old_status
        _poll_cache.update(old_cache)


def test_best_scores_table_with_fixture_data(sample_metrics):
    """With fixture metrics, verify best scores table computes correctly."""
    from dashboard import _best_scores_table

    table = _best_scores_table(sample_metrics)
    assert len(table) > 0
    for row in table:
        assert len(row) == 4


def test_load_results_with_no_data():
    """load_results returns gracefully when no data exists."""
    from dashboard import load_results

    with patch("dashboard.data_loader.list_runs", return_value=[]):
        result = load_results()
        assert result is not None
        assert isinstance(result, tuple)
        assert len(result) == 6


def test_poll_live_shows_status_message_before_first_metric():
    """Live tab should show recent status-history lines before metrics exist."""
    from dashboard import poll_live, _run_manager, _poll_cache

    old_run_id = _run_manager._current_run_id
    old_status = _run_manager._status
    old_cache = dict(_poll_cache)
    try:
        _run_manager._current_run_id = None
        _run_manager._status = "idle"
        with patch.object(type(_run_manager), "_detect_active_run", return_value="test_run"), \
             patch.object(type(_run_manager), "_detect_active_run_with_state", return_value=("test_run", "starting")), \
             patch("dashboard.data_loader.load_latest_metrics", return_value=([], 0)), \
             patch("dashboard.data_loader.load_run_status", return_value={"message": "Calling agent for experiment 1."}), \
             patch(
                 "dashboard.data_loader.load_run_status_history",
                 return_value=[
                     {
                         "updated_at": "2026-03-15T01:04:03+00:00",
                         "phase": "boot",
                         "message": "Run created. Waiting to load data.",
                     },
                     {
                         "updated_at": "2026-03-15T01:04:57+00:00",
                         "phase": "calling-agent",
                         "stage": "prompt",
                         "experiment_num": 1,
                         "message": "Calling agent for experiment 1.",
                     },
                 ],
             ):
            result = poll_live()
            assert result[0] == "starting (external)"
            assert "Calling agent for experiment 1." in result[1]
            assert "boot" in result[5]
            assert "Calling agent for experiment 1." in result[5]
    finally:
        _run_manager._current_run_id = old_run_id
        _run_manager._status = old_status
        _poll_cache.update(old_cache)


def test_load_results_with_fixture_data(sample_metrics):
    """load_results returns charts and summary when data exists."""
    from dashboard import load_results

    with patch("dashboard.data_loader.list_runs", return_value=[{"run_id": "test_run", "status": "completed"}]), \
         patch("dashboard.data_loader.load_run_metrics", return_value=sample_metrics):
        result = load_results("test_run")
        assert result is not None
        assert isinstance(result, tuple)
        assert len(result) == 6
        # Last element is the summary markdown
        assert "test_run" in result[-1]
        assert "Viewing" in result[-1]
        assert "Status" in result[-1]


def test_results_summary_content(sample_metrics):
    """Results summary contains key stats."""
    from dashboard import _results_summary

    summary = _results_summary(
        sample_metrics,
        "test_run",
        view_label="selected historical run",
        run_info={"status": "completed"},
    )
    assert "test_run" in summary
    assert "3" in summary  # 3 experiments
    assert "0.724" in summary  # best composite
    assert "selected historical run" in summary


def test_load_results_keeps_selected_historical_run(sample_metrics):
    """Selecting a past run should not be relabeled as the current live run."""
    from dashboard import load_results, _run_manager

    old_run_id = _run_manager._current_run_id
    try:
        _run_manager._current_run_id = "run_live"
        with patch(
            "dashboard.data_loader.list_runs",
            return_value=[
                {"run_id": "run_live", "status": "running"},
                {"run_id": "run_old", "status": "completed"},
            ],
        ), patch("dashboard.data_loader.load_run_metrics", return_value=sample_metrics):
            result = load_results("run_old")
            assert "run_old" in result[-1]
            assert "selected historical run" in result[-1]
    finally:
        _run_manager._current_run_id = old_run_id
