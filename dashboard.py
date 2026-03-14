"""Gradio Blocks app entry point for the AutoResearch dashboard."""

from __future__ import annotations

from pathlib import Path

import gradio as gr

from autotrust.dashboard import charts, data_loader, git_history, log_formatter
from autotrust.dashboard.run_manager import RunManager

# ---------------------------------------------------------------------------
# Singleton RunManager
# ---------------------------------------------------------------------------

_run_manager = RunManager()

# Read budget limit from spec.yaml at startup (Issue 007)
try:
    import yaml

    _spec_data = yaml.safe_load(Path("spec.yaml").read_text())
    _budget_limit = float(_spec_data.get("limits", {}).get("max_spend_usd", 5.0))
except Exception:
    _budget_limit = 5.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_best_scores_table(metrics: list[dict]) -> list[list]:
    """Compute best per-axis scores vs baseline for the dataframe."""
    if not metrics:
        return []
    baseline = metrics[0].get("per_axis_scores", {})
    best = dict(baseline)
    for m in metrics[1:]:
        for axis, score in m.get("per_axis_scores", {}).items():
            if score > best.get(axis, 0):
                best[axis] = score
    return [
        [
            axis,
            round(baseline.get(axis, 0), 4),
            round(best.get(axis, 0), 4),
            round(best.get(axis, 0) - baseline.get(axis, 0), 4),
        ]
        for axis in sorted(best.keys())
    ]


# ---------------------------------------------------------------------------
# Button handlers (exposed for testing)
# ---------------------------------------------------------------------------


def handle_start(max_exp):
    """Start button handler."""
    try:
        _run_manager.start(int(max_exp))
        return "Starting..."
    except RuntimeError as exc:
        return f"Error: {exc}"


def handle_stop():
    """Stop button handler."""
    _run_manager.stop()
    return "Stopped"


def handle_pause_resume():
    """Pause/resume toggle handler."""
    if _run_manager.status == "paused":
        _run_manager.resume()
        return "Running"
    else:
        _run_manager.pause()
        return "Paused"


def poll_update(state):
    """Timer callback for polling live run data."""
    run_id = _run_manager.current_run_id
    status_text = _run_manager.status
    if _run_manager.status == "error" and _run_manager.last_error:
        status_text = f"error: {_run_manager.last_error}"
    if not run_id:
        return (
            state,
            status_text,
            "$0.00",
            charts.composite_trend([]),
            charts.cost_burn([], budget_limit=_budget_limit),
            charts.radar_chart({}),
            charts.gate_timeline([]),
            charts.stall_indicator([]),
            "No experiments yet.",
        )

    new_records, new_count = data_loader.load_latest_metrics(run_id, state["line_count"])
    if new_records:
        state["metrics"].extend(new_records)
        state["line_count"] = new_count

    metrics = state["metrics"]
    total_cost = sum(m.get("cost", 0) for m in metrics)

    return (
        state,
        status_text,
        f"${total_cost:.2f}",
        charts.composite_trend(metrics),
        charts.cost_burn(metrics, budget_limit=_budget_limit),
        charts.radar_chart(metrics[-1]) if metrics else charts.radar_chart({}),
        charts.gate_timeline(metrics),
        charts.stall_indicator(metrics),
        log_formatter.format_log_stream(metrics),
    )


# ---------------------------------------------------------------------------
# Code Evolution handlers (exposed for testing)
# ---------------------------------------------------------------------------


def refresh_git_log():
    """Load git log for train.py."""
    commits = git_history.get_train_py_log()
    log_data = [[c["hash"][:7], c["message"], c["date"], c.get("composite", "")] for c in commits]
    choices = [f"{c['hash'][:7]} - {c['message']}" for c in commits]
    return log_data, gr.update(choices=choices), gr.update(choices=choices)


def show_diff(commit_a_str, commit_b_str, show_discarded):
    """Show diff between two commits."""
    if not commit_a_str or not commit_b_str:
        return "Select two commits to compare.", ""
    hash_a = commit_a_str.split(" - ")[0]
    hash_b = commit_b_str.split(" - ")[0]
    diff = git_history.get_diff(hash_a, hash_b)
    annotation = f"Comparing {hash_a} -> {hash_b}"
    return diff, annotation


# ---------------------------------------------------------------------------
# Run History handlers (exposed for testing)
# ---------------------------------------------------------------------------


def refresh_run_list():
    """Refresh the list of past runs."""
    runs = data_loader.list_runs()
    rows = [
        [
            r["run_id"],
            r.get("date", ""),
            r.get("experiment_count", 0),
            f"{r.get('best_composite', 0):.4f}",
            f"${r.get('total_cost', 0):.2f}",
            r.get("status", "unknown"),
        ]
        for r in runs
    ]
    choices = [r["run_id"] for r in runs]
    return rows, gr.update(choices=choices), gr.update(choices=choices), gr.update(choices=choices)


def show_run_detail(run_id):
    """Show detail for a selected run."""
    if not run_id:
        return "Select a run.", None
    summary = data_loader.load_run_summary(run_id)
    metrics = data_loader.load_run_metrics(run_id)
    fig = charts.composite_trend(metrics)
    return summary, fig


def compare_runs(run_id_1, run_id_2):
    """Compare two runs."""
    if not run_id_1 or not run_id_2:
        return None
    m1 = data_loader.load_run_metrics(run_id_1)
    m2 = data_loader.load_run_metrics(run_id_2)
    return charts.run_comparison(m1, m2)


def export_metrics(run_id):
    """Export metrics.jsonl for a run."""
    if not run_id:
        return None
    path = Path("runs") / run_id / "metrics.jsonl"
    return str(path) if path.exists() else None


# ---------------------------------------------------------------------------
# Tab builders
# ---------------------------------------------------------------------------


def _build_live_run_tab():
    """Build the Live Run tab (primary view)."""
    # Row 0 -- Controls
    with gr.Row():
        start_btn = gr.Button("Start", variant="primary")
        stop_btn = gr.Button("Stop", variant="stop")
        pause_btn = gr.Button("Pause/Resume")
        max_exp_input = gr.Number(value=50, label="Max Experiments", precision=0)
        status_indicator = gr.Textbox(value="idle", label="Status", interactive=False)
        cost_display = gr.Textbox(value="$0.00", label="Cost So Far", interactive=False)

    # Row 1 -- Hero Charts
    with gr.Row():
        with gr.Column(scale=3):
            composite_plot = gr.Plot(label="Composite Score Trend")
        with gr.Column(scale=1):
            cost_burn_plot = gr.Plot(label="Cost Burn")

    # Row 2 -- Secondary Charts
    with gr.Row():
        with gr.Column():
            radar_plot = gr.Plot(label="Per-Axis Radar")
        with gr.Column():
            gate_plot = gr.Plot(label="Gate Timeline")
        with gr.Column():
            stall_plot = gr.Plot(label="Stall Indicator")

    # Row 3 -- Log Stream
    with gr.Row():
        log_stream = gr.Markdown(value="No experiments yet.")

    # Wire buttons
    start_btn.click(handle_start, inputs=[max_exp_input], outputs=[status_indicator])
    stop_btn.click(handle_stop, outputs=[status_indicator])
    pause_btn.click(handle_pause_resume, outputs=[status_indicator])

    # Wire timer for polling
    timer = gr.Timer(value=2)
    poll_state = gr.State({"line_count": 0, "metrics": []})

    timer.tick(
        poll_update,
        inputs=[poll_state],
        outputs=[
            poll_state,
            status_indicator,
            cost_display,
            composite_plot,
            cost_burn_plot,
            radar_plot,
            gate_plot,
            stall_plot,
            log_stream,
        ],
    )


def _build_optimization_tab():
    """Build the Optimization Dashboard tab."""
    with gr.Row():
        opt_composite_plot = gr.Plot(label="Composite Trend (Enhanced)")
    with gr.Row():
        with gr.Column():
            heatmap_plot = gr.Plot(label="Per-Axis Improvement Heatmap")
        with gr.Column():
            gate_rate_plot = gr.Plot(label="Gate Pass Rate")
    with gr.Row():
        with gr.Column():
            cost_eff_plot = gr.Plot(label="Cost Efficiency")
        with gr.Column():
            best_scores_table = gr.Dataframe(
                label="Best Scores vs Baseline",
                headers=["Axis", "Baseline", "Best", "Delta"],
            )

    # Timer for optimization tab updates
    opt_timer = gr.Timer(value=3)
    opt_state = gr.State({"line_count": 0, "metrics": []})

    def opt_poll(state):
        run_id = _run_manager.current_run_id
        if not run_id:
            return (
                state,
                charts.composite_trend([]),
                charts.axis_improvement_heatmap([]),
                charts.gate_pass_rate([]),
                charts.cost_efficiency([]),
                [],
            )

        new_records, new_count = data_loader.load_latest_metrics(run_id, state["line_count"])
        if new_records:
            state["metrics"].extend(new_records)
            state["line_count"] = new_count

        metrics = state["metrics"]
        return (
            state,
            charts.composite_trend(metrics),
            charts.axis_improvement_heatmap(metrics),
            charts.gate_pass_rate(metrics),
            charts.cost_efficiency(metrics),
            _compute_best_scores_table(metrics),
        )

    opt_timer.tick(
        opt_poll,
        inputs=[opt_state],
        outputs=[
            opt_state,
            opt_composite_plot,
            heatmap_plot,
            gate_rate_plot,
            cost_eff_plot,
            best_scores_table,
        ],
    )


def _build_code_evolution_tab():
    """Build the Code Evolution tab (git diff viewer)."""
    with gr.Row():
        refresh_btn = gr.Button("Refresh Git Log")
    with gr.Row():
        commit_log = gr.Dataframe(
            headers=["Hash", "Message", "Date", "Composite"],
            label="train.py Commit History",
        )
    with gr.Row():
        with gr.Column():
            commit_a = gr.Dropdown(label="Compare From (older)", choices=[])
            commit_b = gr.Dropdown(label="Compare To (newer)", choices=[])
            show_discarded = gr.Checkbox(label="Show discarded experiments", value=False)
            diff_btn = gr.Button("Show Diff")
        with gr.Column(scale=2):
            diff_display = gr.Code(label="Diff")
    with gr.Row():
        change_annotation = gr.Markdown(value="")

    refresh_btn.click(refresh_git_log, outputs=[commit_log, commit_a, commit_b])
    diff_btn.click(
        show_diff,
        inputs=[commit_a, commit_b, show_discarded],
        outputs=[diff_display, change_annotation],
    )


def _build_run_history_tab():
    """Build the Run History tab."""
    with gr.Row():
        refresh_runs_btn = gr.Button("Refresh Run List")
    with gr.Row():
        run_list = gr.Dataframe(
            headers=["Run ID", "Date", "Experiments", "Best Composite", "Total Cost", "Status"],
            label="Past Runs",
            interactive=False,
        )
    with gr.Row():
        with gr.Column():
            selected_run = gr.Dropdown(label="View Run Detail", choices=[])
            compare_run_1 = gr.Dropdown(label="Compare Run 1", choices=[])
            compare_run_2 = gr.Dropdown(label="Compare Run 2", choices=[])
            compare_btn = gr.Button("Compare Runs")
        with gr.Column(scale=2):
            run_detail = gr.Markdown(value="Select a run to view details.")
            run_detail_plot = gr.Plot(label="Run Composite Trend")
    with gr.Row():
        comparison_plot = gr.Plot(label="Run Comparison")
    with gr.Row():
        export_btn = gr.Button("Export metrics.jsonl")
        export_file = gr.File(label="Download")

    refresh_runs_btn.click(
        refresh_run_list,
        outputs=[run_list, selected_run, compare_run_1, compare_run_2],
    )
    selected_run.change(
        show_run_detail, inputs=[selected_run], outputs=[run_detail, run_detail_plot]
    )
    compare_btn.click(
        compare_runs, inputs=[compare_run_1, compare_run_2], outputs=[comparison_plot]
    )
    export_btn.click(export_metrics, inputs=[selected_run], outputs=[export_file])


def _build_axes_explorer_tab():
    """Build the Axes Explorer tab."""
    with gr.Row():
        # Get axis names from spec for checkboxes
        try:
            from autotrust.config import get_spec

            axis_names = [a.name for a in get_spec().trust_axes]
        except Exception:
            axis_names = []

        axis_selector = gr.CheckboxGroup(
            choices=axis_names,
            value=axis_names[:3] if len(axis_names) >= 3 else axis_names,
            label="Select Axes to Plot",
        )
        update_trends_btn = gr.Button("Update Trends")
    with gr.Row():
        axis_trends_plot = gr.Plot(label="Axis Trends Over Experiments")
    with gr.Row():
        with gr.Column():
            kappa_plot = gr.Plot(label="Per-Axis Kappa (Downweight Visualization)")
        with gr.Column():
            correlation_info = gr.Markdown(
                value="Select axes and run to see correlation data.",
            )

    def update_axis_trends(selected_axes):
        run_id = _run_manager.current_run_id
        if not run_id:
            runs = data_loader.list_runs()
            if not runs:
                return charts.axis_trends([], selected_axes)
            run_id = runs[0]["run_id"]
        metrics = data_loader.load_run_metrics(run_id)
        return charts.axis_trends(metrics, selected_axes)

    def compute_axis_correlation(selected_axes):
        run_id = _run_manager.current_run_id
        if not run_id:
            runs = data_loader.list_runs()
            if not runs:
                return "No run data available."
            run_id = runs[0]["run_id"]
        metrics = data_loader.load_run_metrics(run_id)
        if len(metrics) < 3:
            return "Need at least 3 experiments for correlation."
        lines = ["### Axis Correlation Summary\n"]
        for ax1 in selected_axes:
            for ax2 in selected_axes:
                if ax1 >= ax2:
                    continue
                scores1 = [m.get("per_axis_scores", {}).get(ax1, 0) for m in metrics]
                scores2 = [m.get("per_axis_scores", {}).get(ax2, 0) for m in metrics]
                if len(scores1) >= 2:
                    deltas1 = [b - a for a, b in zip(scores1[:-1], scores1[1:])]
                    deltas2 = [b - a for a, b in zip(scores2[:-1], scores2[1:])]
                    same_dir = sum(1 for d1, d2 in zip(deltas1, deltas2) if d1 * d2 > 0)
                    pct = same_dir / len(deltas1) * 100 if deltas1 else 0
                    lines.append(f"- **{ax1}** / **{ax2}**: move together {pct:.0f}% of the time")
        return "\n".join(lines)

    update_trends_btn.click(update_axis_trends, inputs=[axis_selector], outputs=[axis_trends_plot])
    update_trends_btn.click(
        compute_axis_correlation, inputs=[axis_selector], outputs=[correlation_info]
    )

    # Load kappa chart on button click too
    def load_kappa_chart():
        calibration = data_loader.load_calibration()
        return charts.kappa_bars(calibration)

    update_trends_btn.click(load_kappa_chart, outputs=[kappa_plot])


def _build_config_tab():
    """Build the Config tab (read-only reference)."""
    with gr.Row():
        refresh_config_btn = gr.Button("Refresh Config")
    with gr.Row():
        with gr.Column():
            spec_display = gr.Code(
                label="spec.yaml",
                language="yaml",
                value=data_loader.load_spec_text(),
            )
        with gr.Column():
            calibration_display = gr.JSON(
                label="Calibration Report",
                value=data_loader.load_calibration(),
            )
    with gr.Row():
        weights_table = gr.Dataframe(
            headers=["Axis", "Original Weight", "Effective Weight", "Kappa"],
            label="Current Effective Weights",
        )

    def refresh_config():
        spec_text = data_loader.load_spec_text()
        calibration = data_loader.load_calibration()
        try:
            from autotrust.config import get_spec, get_effective_weights

            spec = get_spec()
            kappa = calibration.get("per_axis_kappa", {})
            eff_weights = get_effective_weights(spec, kappa)
            weights_data = [
                [
                    a.name,
                    f"{a.weight:.4f}",
                    f"{eff_weights.get(a.name, a.weight):.4f}",
                    f"{kappa.get(a.name, 1.0):.3f}",
                ]
                for a in spec.trust_axes
            ]
        except Exception:
            weights_data = []
        return spec_text, calibration, weights_data

    refresh_config_btn.click(
        refresh_config, outputs=[spec_display, calibration_display, weights_table]
    )


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app() -> gr.Blocks:
    """Create the Gradio Blocks app with all tabs."""
    with gr.Blocks(title="AutoResearch Dashboard") as app:
        gr.Markdown("# AutoResearch Dashboard")

        with gr.Tab("Live Run"):
            _build_live_run_tab()

        with gr.Tab("Optimization"):
            _build_optimization_tab()

        with gr.Tab("Code Evolution"):
            _build_code_evolution_tab()

        with gr.Tab("Run History"):
            _build_run_history_tab()

        with gr.Tab("Axes Explorer"):
            _build_axes_explorer_tab()

        with gr.Tab("Config"):
            _build_config_tab()

    return app


if __name__ == "__main__":
    app = create_app()
    app.launch()
