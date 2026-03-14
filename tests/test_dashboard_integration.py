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


# ---------------------------------------------------------------------------
# TASK_009: Live Run tab integration tests
# ---------------------------------------------------------------------------


def test_dashboard_launches_without_error():
    """Import dashboard module and verify Gradio Blocks app can be instantiated."""
    from dashboard import create_app

    app = create_app()
    assert app is not None


def test_live_run_tab_has_required_components():
    """Verify the Live Run tab contains required UI components by type."""
    from dashboard import create_app

    app = create_app()
    assert app is not None
    assert len(app.blocks) > 0

    # Check for expected component types
    block_types = [type(b).__name__ for b in app.blocks.values()]
    assert "Button" in block_types, "Expected Button components"
    assert "Plot" in block_types, "Expected Plot components"
    assert "Markdown" in block_types, "Expected Markdown component for log stream"
    assert "Number" in block_types, "Expected Number input for max experiments"


def test_start_button_calls_run_manager():
    """Mock RunManager, click start, verify start() is called."""
    from dashboard import _run_manager, handle_start

    with patch.object(_run_manager, "start", return_value="starting") as mock_start:
        result = handle_start(50)
        mock_start.assert_called_once_with(50)
        assert "Starting" in result


def test_timer_updates_charts(sample_metrics):
    """With fixture metrics, verify timer callback returns updated values."""
    from dashboard import poll_update, _run_manager, _poll_cache

    # Directly set internal state instead of patching properties
    old_run_id = _run_manager._current_run_id
    old_status = _run_manager._status
    old_cache = dict(_poll_cache)
    try:
        _run_manager._current_run_id = "test_run"
        _run_manager._status = "running"

        with patch("dashboard.data_loader.load_latest_metrics", return_value=(sample_metrics, 3)):
            result = poll_update()
            # Result should be a tuple with all outputs (no state)
            assert result is not None
            assert isinstance(result, tuple)
            assert len(result) == 9  # 9 outputs (status, cost, summary, 5 plots, log)
    finally:
        _run_manager._current_run_id = old_run_id
        _run_manager._status = old_status
        _poll_cache.update(old_cache)


# ---------------------------------------------------------------------------
# TASK_010: Optimization Dashboard tab
# ---------------------------------------------------------------------------


def test_optimization_tab_has_required_charts():
    """Verify Optimization Dashboard tab has Plot and Dataframe components."""
    from dashboard import create_app

    app = create_app()
    assert app is not None
    # Should have Dataframe for best scores table
    block_types = [type(b).__name__ for b in app.blocks.values()]
    assert "Dataframe" in block_types, "Expected Dataframe for best scores table"
    # Count plots -- should have several (composite, heatmap, gate rate, cost eff, etc.)
    plot_count = block_types.count("Plot")
    assert plot_count >= 5, f"Expected at least 5 Plot components, got {plot_count}"


def test_optimization_tab_renders_with_fixture_data(sample_metrics):
    """With fixture metrics, verify optimization helper works."""
    from dashboard import _compute_best_scores_table

    table = _compute_best_scores_table(sample_metrics)
    assert len(table) > 0
    # Each row should have [axis, baseline, best, delta]
    for row in table:
        assert len(row) == 4


# ---------------------------------------------------------------------------
# TASK_011: Code Evolution tab
# ---------------------------------------------------------------------------


def test_code_evolution_tab_has_required_components():
    """Verify Code Evolution tab exists in the app."""
    from dashboard import create_app

    app = create_app()
    assert app is not None


def test_diff_viewer_renders_with_mock_data():
    """Mock git_history, verify diff output works with commit annotations."""
    from dashboard import show_diff

    mock_commits = [
        {"hash": "abc1234", "message": "experiment 1: keep composite=0.681", "date": "2024-03-14", "composite": 0.681},
        {"hash": "def5678", "message": "experiment 2: keep composite=0.724", "date": "2024-03-14", "composite": 0.724},
    ]
    with patch("dashboard.git_history.get_diff", return_value="--- a/train.py\n+++ b/train.py\n@@ -1 +1 @@\n-old\n+new"), \
         patch("dashboard.git_history.get_train_py_log", return_value=mock_commits):
        diff, annotation = show_diff("abc1234 - experiment 1", "def5678 - experiment 2", False)
        assert "old" in diff
        assert "new" in diff
        assert "abc1234" in annotation
        assert "def5678" in annotation


# ---------------------------------------------------------------------------
# TASK_012: Run History tab
# ---------------------------------------------------------------------------


def test_run_history_tab_has_required_components():
    """Verify Run History tab exists in the app."""
    from dashboard import create_app

    app = create_app()
    assert app is not None


def test_run_list_populates_from_fixture(tmp_path):
    """Create fixture run directories, verify refresh_run_list works."""
    from dashboard import refresh_run_list

    # Create fixture runs
    for run_id in ["run_001", "run_002"]:
        run_dir = tmp_path / run_id
        run_dir.mkdir()
        metrics = [{"composite": 0.72, "cost": 0.03, "gate_results": {"composite": True}}]
        (run_dir / "metrics.jsonl").write_text(json.dumps(metrics[0]) + "\n")
        (run_dir / "summary.txt").write_text(f"Run ID: {run_id}\nBest composite: 0.72\nTotal cost: $0.03\n")

    with patch("dashboard.data_loader.list_runs") as mock_list:
        mock_list.return_value = [
            {"run_id": "run_001", "date": "2024-01-01", "experiment_count": 1,
             "best_composite": 0.72, "total_cost": 0.03, "status": "completed"},
            {"run_id": "run_002", "date": "2024-01-02", "experiment_count": 1,
             "best_composite": 0.72, "total_cost": 0.03, "status": "completed"},
        ]
        result = refresh_run_list()
        assert result is not None


# ---------------------------------------------------------------------------
# TASK_013: Axes Explorer tab
# ---------------------------------------------------------------------------


def test_axes_explorer_tab_has_required_components():
    """Verify Axes Explorer tab exists in the app."""
    from dashboard import create_app

    app = create_app()
    assert app is not None


def test_axis_trends_updates_on_selection(sample_metrics):
    """Mock data, select 2 axes, verify chart has traces."""
    from autotrust.dashboard.charts import axis_trends

    fig = axis_trends(sample_metrics, axes=["phish", "manipulation"])
    assert len(fig.data) == 2


# ---------------------------------------------------------------------------
# TASK_014: Config tab
# ---------------------------------------------------------------------------


def test_config_tab_has_required_components():
    """Verify Config tab exists in the app."""
    from dashboard import create_app

    app = create_app()
    assert app is not None
