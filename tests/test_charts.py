"""Tests for autotrust/dashboard/charts.py -- Plotly figure builders."""

import pytest
import plotly.graph_objects as go


@pytest.fixture
def sample_metrics():
    """5 experiment dicts with varied composites and gate results."""
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
        {**base, "composite": 0.690, "gate_results": {"composite": False, "gold": True, "explanation": True}},
        {**base, "composite": 0.724, "gate_results": {"composite": True, "gold": True, "explanation": True}},
        {**base, "composite": 0.710, "gate_results": {"composite": False, "gold": False, "explanation": True}},
    ]


# ---------------------------------------------------------------------------
# Core charts (TASK_005)
# ---------------------------------------------------------------------------


def test_composite_trend_returns_figure(sample_metrics):
    """With 5 experiments, returns go.Figure with at least one trace."""
    from autotrust.dashboard.charts import composite_trend

    fig = composite_trend(sample_metrics)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1


def test_composite_trend_colors_kept_vs_discarded(sample_metrics):
    """Verify kept experiments plotted as green dots, discarded as red."""
    from autotrust.dashboard.charts import composite_trend

    fig = composite_trend(sample_metrics)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1
    # Find the trace with per-experiment markers (has color list)
    marker_trace = None
    for trace in fig.data:
        if trace.marker and trace.marker.color and isinstance(trace.marker.color, (list, tuple)):
            marker_trace = trace
            break
    assert marker_trace is not None, "Expected a trace with per-experiment marker colors"
    marker_colors = list(marker_trace.marker.color)
    assert "#10b981" in marker_colors or "#ef4444" in marker_colors, "Expected green/red markers"


def test_composite_trend_single_experiment(sample_metrics):
    """With 1 experiment, still returns valid figure."""
    from autotrust.dashboard.charts import composite_trend

    fig = composite_trend([sample_metrics[0]])
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1


def test_composite_trend_empty_data():
    """With empty list, returns empty figure (no crash)."""
    from autotrust.dashboard.charts import composite_trend

    fig = composite_trend([])
    assert isinstance(fig, go.Figure)


def test_cost_burn_returns_gauge(sample_metrics):
    """With 3 experiments and budget_limit, returns figure with trace."""
    from autotrust.dashboard.charts import cost_burn

    fig = cost_burn(sample_metrics[:3], budget_limit=5.0)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1


def test_radar_chart_returns_scatterpolar(sample_metrics):
    """With experiment dict containing per_axis_scores, returns figure."""
    from autotrust.dashboard.charts import radar_chart

    fig = radar_chart(sample_metrics[0])
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1
    # Should be a scatterpolar trace
    assert any(isinstance(trace, go.Scatterpolar) for trace in fig.data)


def test_gate_timeline_returns_scatter(sample_metrics):
    """With 5 experiments, returns figure showing gate pass/fail."""
    from autotrust.dashboard.charts import gate_timeline

    fig = gate_timeline(sample_metrics)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1


def test_stall_indicator_shows_count(sample_metrics):
    """Verify stall indicator displays a figure."""
    from autotrust.dashboard.charts import stall_indicator

    fig = stall_indicator(sample_metrics)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1


# ---------------------------------------------------------------------------
# Enhanced composite trend (Issue 006)
# ---------------------------------------------------------------------------


def test_enhanced_composite_trend_has_baseline_and_best_so_far(sample_metrics):
    """Enhanced trend includes kept/discarded markers and running best line."""
    from autotrust.dashboard.charts import enhanced_composite_trend

    fig = enhanced_composite_trend(sample_metrics)
    assert isinstance(fig, go.Figure)
    # Should have at least 2 traces: kept markers + running best line (+ optional discarded)
    assert len(fig.data) >= 2
    trace_names = [t.name for t in fig.data]
    assert "Kept" in trace_names
    assert "Running Best" in trace_names


def test_enhanced_composite_trend_empty():
    """Empty metrics returns empty figure."""
    from autotrust.dashboard.charts import enhanced_composite_trend

    fig = enhanced_composite_trend([])
    assert isinstance(fig, go.Figure)


# ---------------------------------------------------------------------------
# Advanced charts (TASK_006)
# ---------------------------------------------------------------------------


def test_axis_improvement_heatmap_returns_figure(sample_metrics):
    """With 5 experiments, returns go.Figure with heatmap trace."""
    from autotrust.dashboard.charts import axis_improvement_heatmap

    fig = axis_improvement_heatmap(sample_metrics)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1


def test_axis_improvement_heatmap_empty():
    """Empty metrics returns empty figure."""
    from autotrust.dashboard.charts import axis_improvement_heatmap

    fig = axis_improvement_heatmap([])
    assert isinstance(fig, go.Figure)


def test_gate_pass_rate_returns_bar(sample_metrics):
    """With 5 experiments, returns figure showing pass/fail rate per gate."""
    from autotrust.dashboard.charts import gate_pass_rate

    fig = gate_pass_rate(sample_metrics)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1


def test_cost_efficiency_returns_figure(sample_metrics):
    """With 5 experiments, returns figure showing composite improvement per dollar."""
    from autotrust.dashboard.charts import cost_efficiency

    fig = cost_efficiency(sample_metrics)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1


def test_axis_trends_returns_multiline(sample_metrics):
    """With 5 experiments and 3 selected axes, returns figure with 3 line traces."""
    from autotrust.dashboard.charts import axis_trends

    fig = axis_trends(sample_metrics, axes=["phish", "manipulation", "urgency"])
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 3


def test_axis_trends_no_axes_selected(sample_metrics):
    """Empty axes list returns empty figure."""
    from autotrust.dashboard.charts import axis_trends

    fig = axis_trends(sample_metrics, axes=[])
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 0


def test_kappa_bars_returns_bar_chart():
    """With calibration dict, returns bar chart with threshold line."""
    from autotrust.dashboard.charts import kappa_bars

    calibration = {
        "per_axis_kappa": {"phish": 0.9, "manipulation": 0.5, "urgency": 0.8},
        "min_gold_kappa": 0.6,
    }
    fig = kappa_bars(calibration)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1


def test_run_comparison_returns_grouped_bar(sample_metrics):
    """With two metrics lists, returns grouped bar comparing best scores."""
    from autotrust.dashboard.charts import run_comparison

    metrics2 = [{**m, "composite": m["composite"] + 0.05} for m in sample_metrics]
    fig = run_comparison(sample_metrics, metrics2)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 2  # two groups


# ---------------------------------------------------------------------------
# Stage 2 charts (TASK_010)
# ---------------------------------------------------------------------------


@pytest.fixture
def stage2_metrics():
    """Stage 2 metrics with training loss and param count."""
    return [
        {
            "composite": 0.65,
            "training_loss": {"trust_loss": 0.5, "reason_loss": 0.3, "escalate_loss": 0.2, "total_loss": 1.0},
            "param_count": 50_000_000,
            "gate_results": {"composite": True, "gold": True, "explanation": True},
        },
        {
            "composite": 0.72,
            "training_loss": {"trust_loss": 0.4, "reason_loss": 0.25, "escalate_loss": 0.15, "total_loss": 0.8},
            "param_count": 75_000_000,
            "gate_results": {"composite": True, "gold": True, "explanation": True},
        },
        {
            "composite": 0.78,
            "training_loss": {"trust_loss": 0.3, "reason_loss": 0.2, "escalate_loss": 0.1, "total_loss": 0.6},
            "param_count": 100_000_000,
            "expert_utilization": [0.25, 0.30, 0.20, 0.25],
            "gate_results": {"composite": True, "gold": True, "explanation": True},
        },
    ]


def test_training_loss_chart(stage2_metrics):
    """charts.training_loss(metrics) returns valid Plotly figure with loss curves."""
    from autotrust.dashboard.charts import training_loss

    fig = training_loss(stage2_metrics)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1


def test_training_loss_empty_for_stage1(sample_metrics):
    """training_loss returns empty figure when no Stage 2 metrics."""
    from autotrust.dashboard.charts import training_loss

    fig = training_loss(sample_metrics)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 0


def test_param_count_display(stage2_metrics):
    """charts.param_count_timeline(metrics) shows parameter count over experiments."""
    from autotrust.dashboard.charts import param_count_timeline

    fig = param_count_timeline(stage2_metrics)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1


def test_expert_utilization_chart(stage2_metrics):
    """charts.expert_utilization(metrics) returns valid figure."""
    from autotrust.dashboard.charts import expert_utilization

    fig = expert_utilization(stage2_metrics)
    assert isinstance(fig, go.Figure)
    # Only the last metric has expert_utilization, so should have data
    assert len(fig.data) >= 1


def test_expert_utilization_empty(sample_metrics):
    """expert_utilization returns empty figure with no MoE data."""
    from autotrust.dashboard.charts import expert_utilization

    fig = expert_utilization(sample_metrics)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 0
