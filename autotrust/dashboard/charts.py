"""Plotly figure builders for dashboard charts."""

from __future__ import annotations

import plotly.graph_objects as go

from autotrust.dashboard.utils import is_kept as _is_kept


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _empty_figure(title: str = "") -> go.Figure:
    """Return an empty figure with optional title."""
    fig = go.Figure()
    if title:
        fig.update_layout(title=title)
    return fig


def _extract_axis_names(metrics: list[dict]) -> list[str]:
    """Extract axis names from the first experiment that has per_axis_scores."""
    for m in metrics:
        axes = m.get("per_axis_scores", {})
        if axes:
            return sorted(axes.keys())
    return []


# ---------------------------------------------------------------------------
# Core charts (Live Run tab) -- TASK_005
# ---------------------------------------------------------------------------


def composite_trend(metrics: list[dict]) -> go.Figure:
    """Line chart of composite score over experiments with kept/discarded markers."""
    if not metrics:
        return _empty_figure("Composite Score Trend")

    x = list(range(1, len(metrics) + 1))
    y = [m.get("composite", 0.0) for m in metrics]
    colors = ["green" if _is_kept(m) else "red" for m in metrics]
    descs = [m.get("change_description", "") for m in metrics]

    fig = go.Figure()
    # Line trace
    fig.add_trace(
        go.Scatter(
            x=x,
            y=y,
            mode="lines+markers",
            line={"color": "steelblue"},
            marker={"color": colors, "size": 10},
            name="Composite",
            text=descs,
            hovertemplate="Exp %{x}: %{y:.4f}<br>%{text}<extra></extra>",
        )
    )

    n_total = len(metrics)
    n_kept = sum(1 for m in metrics if _is_kept(m))
    fig.update_layout(
        title=f"Composite Score: {n_total} Experiments, {n_kept} Kept",
        xaxis_title="Experiment",
        yaxis_title="Composite Score",
    )
    return fig


def enhanced_composite_trend(metrics: list[dict]) -> go.Figure:
    """Enhanced composite trend with baseline markers, best-so-far line, improvement rate,
    and annotations on kept experiments showing what changed.

    Used in the Optimization Dashboard tab for deeper analysis.
    """
    if not metrics:
        return _empty_figure("Composite Score Trend (Enhanced)")

    x = list(range(1, len(metrics) + 1))
    y = [m.get("composite", 0.0) for m in metrics]
    colors = ["green" if _is_kept(m) else "red" for m in metrics]

    # Compute best-so-far line
    best_so_far = []
    running_best = 0.0
    for score in y:
        if score > running_best:
            running_best = score
        best_so_far.append(running_best)

    fig = go.Figure()

    # Discarded experiments as faint background dots
    disc_x = [xi for xi, m in zip(x, metrics) if not _is_kept(m)]
    disc_y = [yi for yi, m in zip(y, metrics) if not _is_kept(m)]
    if disc_x:
        fig.add_trace(
            go.Scatter(
                x=disc_x,
                y=disc_y,
                mode="markers",
                marker={"color": "#cccccc", "size": 8, "opacity": 0.5},
                name="Discarded",
            )
        )

    # Kept experiments as prominent green dots
    kept_x = [xi for xi, m in zip(x, metrics) if _is_kept(m)]
    kept_y = [yi for yi, m in zip(y, metrics) if _is_kept(m)]
    kept_descs = [
        m.get("change_description", "") for m in metrics if _is_kept(m)
    ]
    if kept_x:
        fig.add_trace(
            go.Scatter(
                x=kept_x,
                y=kept_y,
                mode="markers",
                marker={
                    "color": "#2ecc71",
                    "size": 12,
                    "line": {"color": "black", "width": 1},
                },
                name="Kept",
                text=kept_descs,
                hovertemplate="%{text}<br>Composite: %{y:.4f}<extra></extra>",
            )
        )

    # Best-so-far step line
    fig.add_trace(
        go.Scatter(
            x=x,
            y=best_so_far,
            mode="lines",
            line={"color": "#27ae60", "width": 2},
            name="Running Best",
        )
    )

    # Annotate kept experiments with their change description
    for xi, yi, desc in zip(kept_x, kept_y, kept_descs):
        if desc:
            label = desc[:45] + "..." if len(desc) > 45 else desc
            fig.add_annotation(
                x=xi,
                y=yi,
                text=label,
                showarrow=False,
                textangle=-30,
                xshift=8,
                yshift=8,
                font={"size": 9, "color": "#1a7a3a"},
            )

    # Baseline horizontal line (first experiment)
    baseline = y[0]
    fig.add_hline(
        y=baseline,
        line_dash="dash",
        line_color="gray",
        annotation_text=f"Baseline: {baseline:.3f}",
    )

    # Improvement rate annotation
    if len(y) >= 2:
        total_improvement = best_so_far[-1] - baseline
        rate = total_improvement / (len(y) - 1)
        fig.add_annotation(
            x=x[-1],
            y=best_so_far[-1],
            text=f"Rate: {rate:+.4f}/exp",
            showarrow=True,
            arrowhead=2,
            yshift=20,
        )

    n_total = len(metrics)
    n_kept = len(kept_x)
    fig.update_layout(
        title=f"Autoresearch Progress: {n_total} Experiments, {n_kept} Kept Improvements",
        xaxis_title="Experiment",
        yaxis_title="Composite Score",
    )
    return fig


def cost_burn(metrics: list[dict], budget_limit: float) -> go.Figure:
    """Cumulative cost line with budget threshold."""
    if not metrics:
        return _empty_figure("Cost Burn")

    cumulative = []
    running = 0.0
    for m in metrics:
        running += m.get("cost", 0.0)
        cumulative.append(running)

    x = list(range(1, len(metrics) + 1))

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x,
            y=cumulative,
            mode="lines+markers",
            name="Cumulative Cost",
            line={"color": "orange"},
        )
    )
    fig.add_hline(
        y=budget_limit,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Budget: ${budget_limit:.2f}",
    )
    fig.update_layout(
        title="Cost Burn",
        xaxis_title="Experiment",
        yaxis_title="Cost ($)",
    )
    return fig


def radar_chart(experiment: dict) -> go.Figure:
    """Per-axis radar/spider chart for a single experiment."""
    per_axis = experiment.get("per_axis_scores", {})
    if not per_axis:
        return _empty_figure("Per-Axis Radar")

    axis_names = sorted(per_axis.keys())
    values = [per_axis[a] for a in axis_names]
    # Close the polygon
    axis_names_closed = axis_names + [axis_names[0]]
    values_closed = values + [values[0]]

    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(
            r=values_closed,
            theta=axis_names_closed,
            fill="toself",
            name="Scores",
        )
    )
    fig.update_layout(
        title="Per-Axis Radar",
        polar={"radialaxis": {"range": [0, 1]}},
    )
    return fig


def gate_timeline(metrics: list[dict]) -> go.Figure:
    """Scatter plot showing pass/fail for each gate across experiments."""
    if not metrics:
        return _empty_figure("Gate Timeline")

    fig = go.Figure()
    gate_names = []
    if metrics:
        gate_names = sorted(metrics[0].get("gate_results", {}).keys())

    for gate_name in gate_names:
        x_pass, y_pass = [], []
        x_fail, y_fail = [], []
        for i, m in enumerate(metrics, 1):
            passed = m.get("gate_results", {}).get(gate_name, False)
            if passed:
                x_pass.append(i)
                y_pass.append(gate_name)
            else:
                x_fail.append(i)
                y_fail.append(gate_name)

        if x_pass:
            fig.add_trace(
                go.Scatter(
                    x=x_pass,
                    y=y_pass,
                    mode="markers",
                    marker={"color": "green", "symbol": "circle", "size": 12},
                    name=f"{gate_name} pass",
                    showlegend=False,
                )
            )
        if x_fail:
            fig.add_trace(
                go.Scatter(
                    x=x_fail,
                    y=y_fail,
                    mode="markers",
                    marker={"color": "red", "symbol": "x", "size": 12},
                    name=f"{gate_name} fail",
                    showlegend=False,
                )
            )

    fig.update_layout(
        title="Gate Timeline",
        xaxis_title="Experiment",
        yaxis_title="Gate",
    )
    return fig


def stall_indicator(metrics: list[dict]) -> go.Figure:
    """Stall indicator showing consecutive no-improvement count."""
    if not metrics:
        return _empty_figure("Stall Indicator")

    # Count consecutive experiments from the end where composite didn't improve
    best_so_far = 0.0
    consecutive_stall = 0
    for m in metrics:
        composite = m.get("composite", 0.0)
        if composite > best_so_far:
            best_so_far = composite
            consecutive_stall = 0
        else:
            consecutive_stall += 1

    fig = go.Figure()
    fig.add_trace(
        go.Indicator(
            mode="gauge+number",
            value=consecutive_stall,
            title={"text": "Consecutive No-Improvement"},
            gauge={
                "axis": {"range": [0, 10]},
                "bar": {"color": "darkred" if consecutive_stall >= 3 else "steelblue"},
                "threshold": {
                    "line": {"color": "red", "width": 4},
                    "thickness": 0.75,
                    "value": 3,  # LoRA nudge threshold
                },
            },
        )
    )
    fig.update_layout(title="Stall Indicator")
    return fig


# ---------------------------------------------------------------------------
# Advanced charts (Optimization, Axes Explorer, Run Comparison) -- TASK_006
# ---------------------------------------------------------------------------


def axis_improvement_heatmap(metrics: list[dict]) -> go.Figure:
    """Heatmap showing per-axis score changes across experiments."""
    if not metrics or len(metrics) < 2:
        return _empty_figure("Per-Axis Improvement Heatmap")

    axis_names = _extract_axis_names(metrics)
    if not axis_names:
        return _empty_figure("Per-Axis Improvement Heatmap")

    # Compute deltas: score[i] - score[i-1] for each axis
    z = []
    for axis in axis_names:
        row = []
        for i in range(1, len(metrics)):
            prev_score = metrics[i - 1].get("per_axis_scores", {}).get(axis, 0.0)
            curr_score = metrics[i].get("per_axis_scores", {}).get(axis, 0.0)
            row.append(curr_score - prev_score)
        z.append(row)

    x_labels = [str(i + 1) for i in range(1, len(metrics))]

    fig = go.Figure()
    fig.add_trace(
        go.Heatmap(
            z=z,
            x=x_labels,
            y=axis_names,
            colorscale="RdYlGn",
            zmid=0,
        )
    )
    fig.update_layout(
        title="Per-Axis Improvement Heatmap",
        xaxis_title="Experiment",
        yaxis_title="Axis",
    )
    return fig


def gate_pass_rate(metrics: list[dict]) -> go.Figure:
    """Stacked bar showing gate pass/fail counts."""
    if not metrics:
        return _empty_figure("Gate Pass Rate")

    gate_names = sorted(metrics[0].get("gate_results", {}).keys())
    pass_counts = {g: 0 for g in gate_names}
    fail_counts = {g: 0 for g in gate_names}

    for m in metrics:
        for gate, passed in m.get("gate_results", {}).items():
            if gate in pass_counts:
                if passed:
                    pass_counts[gate] += 1
                else:
                    fail_counts[gate] += 1

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=gate_names,
            y=[pass_counts[g] for g in gate_names],
            name="Pass",
            marker_color="green",
        )
    )
    fig.add_trace(
        go.Bar(
            x=gate_names,
            y=[fail_counts[g] for g in gate_names],
            name="Fail",
            marker_color="red",
        )
    )
    fig.update_layout(
        title="Gate Pass Rate",
        barmode="stack",
        xaxis_title="Gate",
        yaxis_title="Count",
    )
    return fig


def cost_efficiency(metrics: list[dict]) -> go.Figure:
    """Composite improvement per dollar spent."""
    if not metrics:
        return _empty_figure("Cost Efficiency")

    baseline = metrics[0].get("composite", 0.0)
    cumulative_cost = []
    improvements = []
    running_cost = 0.0

    for m in metrics:
        running_cost += m.get("cost", 0.0)
        cumulative_cost.append(running_cost)
        improvements.append(m.get("composite", 0.0) - baseline)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=cumulative_cost,
            y=improvements,
            mode="lines+markers",
            name="Improvement vs Cost",
            line={"color": "teal"},
        )
    )
    fig.update_layout(
        title="Cost Efficiency",
        xaxis_title="Cumulative Cost ($)",
        yaxis_title="Composite Improvement",
    )
    return fig


def axis_trends(metrics: list[dict], axes: list[str]) -> go.Figure:
    """Multi-line chart of selected axes over experiments."""
    fig = go.Figure()

    if not metrics or not axes:
        fig.update_layout(title="Axis Trends")
        return fig

    x = list(range(1, len(metrics) + 1))
    for axis_name in axes:
        y = [m.get("per_axis_scores", {}).get(axis_name, 0.0) for m in metrics]
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                mode="lines+markers",
                name=axis_name,
            )
        )

    fig.update_layout(
        title="Axis Trends Over Experiments",
        xaxis_title="Experiment",
        yaxis_title="Score",
    )
    return fig


def kappa_bars(calibration: dict) -> go.Figure:
    """Bar chart of per-axis Kappa with threshold line."""
    per_axis_kappa = calibration.get("per_axis_kappa", {})
    if not per_axis_kappa:
        return _empty_figure("Per-Axis Kappa")

    threshold = calibration.get("min_gold_kappa", 0.6)
    axis_names = sorted(per_axis_kappa.keys())
    values = [per_axis_kappa[a] for a in axis_names]
    colors = ["red" if v < threshold else "steelblue" for v in values]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=axis_names,
            y=values,
            marker_color=colors,
            name="Kappa",
        )
    )
    fig.add_hline(
        y=threshold, line_dash="dash", line_color="red", annotation_text=f"Threshold: {threshold}"
    )
    fig.update_layout(
        title="Per-Axis Kappa (Downweight Visualization)",
        xaxis_title="Axis",
        yaxis_title="Kappa",
    )
    return fig


def run_comparison(metrics1: list[dict], metrics2: list[dict]) -> go.Figure:
    """Grouped bar comparing best metrics of two runs."""

    def _best_per_axis(metrics: list[dict]) -> dict[str, float]:
        best: dict[str, float] = {}
        for m in metrics:
            for axis, score in m.get("per_axis_scores", {}).items():
                if score > best.get(axis, 0.0):
                    best[axis] = score
        return best

    best1 = _best_per_axis(metrics1)
    best2 = _best_per_axis(metrics2)

    all_axes = sorted(set(best1.keys()) | set(best2.keys()))
    if not all_axes:
        return _empty_figure("Run Comparison")

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=all_axes,
            y=[best1.get(a, 0.0) for a in all_axes],
            name="Run 1",
            marker_color="steelblue",
        )
    )
    fig.add_trace(
        go.Bar(
            x=all_axes,
            y=[best2.get(a, 0.0) for a in all_axes],
            name="Run 2",
            marker_color="orange",
        )
    )
    fig.update_layout(
        title="Run Comparison -- Best Per-Axis Scores",
        barmode="group",
        xaxis_title="Axis",
        yaxis_title="Best Score",
    )
    return fig


def summary_stats(metrics: list[dict]) -> str:
    """Generate a markdown summary header for the run."""
    if not metrics:
        return ""

    n_total = len(metrics)
    n_kept = sum(1 for m in metrics if _is_kept(m))
    n_discarded = n_total - n_kept
    keep_rate = (n_kept / n_total * 100) if n_total else 0

    composites = [m.get("composite", 0.0) for m in metrics]
    baseline = composites[0]
    best = max(composites)
    latest = composites[-1]
    improvement = best - baseline

    total_cost = sum(m.get("cost", 0) for m in metrics)

    # Gate failure breakdown
    gate_fails: dict[str, int] = {}
    for m in metrics:
        for gate, passed in m.get("gate_results", {}).items():
            if not passed:
                gate_fails[gate] = gate_fails.get(gate, 0) + 1

    fail_parts = [f"{g}: {c}" for g, c in sorted(gate_fails.items())]
    fail_str = ", ".join(fail_parts) if fail_parts else "none"

    return (
        f"**{n_total}** experiments | "
        f"**{n_kept}** kept ({keep_rate:.0f}%) | "
        f"**{n_discarded}** discarded | "
        f"Baseline: **{baseline:.4f}** | "
        f"Best: **{best:.4f}** ({improvement:+.4f}) | "
        f"Latest: **{latest:.4f}** | "
        f"Cost: **${total_cost:.2f}** | "
        f"Gate failures: {fail_str}"
    )
