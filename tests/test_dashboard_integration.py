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
    assert "Button" in block_types
    assert "Plot" in block_types
    assert "Markdown" in block_types
    assert "Number" in block_types


def test_start_button_calls_run_manager():
    """Mock RunManager, click start, verify start() is called."""
    from dashboard import _run_manager, handle_start

    with patch.object(_run_manager, "start", return_value="starting") as mock_start:
        result = handle_start(50)
        mock_start.assert_called_once_with(50)
        assert "Running" in result


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


def test_load_results_with_fixture_data(sample_metrics):
    """load_results returns charts and summary when data exists."""
    from dashboard import load_results

    with patch("dashboard.data_loader.list_runs", return_value=[{"run_id": "test_run"}]), \
         patch("dashboard.data_loader.load_run_metrics", return_value=sample_metrics):
        result = load_results("test_run")
        assert result is not None
        assert isinstance(result, tuple)
        assert len(result) == 6
        # Last element is the summary markdown
        assert "test_run" in result[-1]


def test_results_summary_content(sample_metrics):
    """Results summary contains key stats."""
    from dashboard import _results_summary

    summary = _results_summary(sample_metrics, "test_run")
    assert "test_run" in summary
    assert "3" in summary  # 3 experiments
    assert "0.724" in summary  # best composite
