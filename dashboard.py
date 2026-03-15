"""Masubi dashboard -- two tabs, focused on what matters.

Tab 1: Live Run  -- monitor the autoresearch loop as it runs
Tab 2: Results   -- see how performance improved over time
"""

from __future__ import annotations

from pathlib import Path

import gradio as gr

from autotrust.dashboard import charts, data_loader, log_formatter
from autotrust.dashboard.run_manager import RunManager

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

_run_manager = RunManager()

try:
    import yaml
    _spec_data = yaml.safe_load(Path("spec.yaml").read_text())
    _budget_limit = float(_spec_data.get("limits", {}).get("max_spend_usd", 8.0))
except Exception:
    _budget_limit = 8.0

_poll_cache: dict = {"line_count": 0, "metrics": [], "run_id": None}


def _refresh_poll_cache() -> list[dict]:
    """Fetch new metrics from disk once per poll cycle."""
    run_id = _run_manager.current_run_id
    if not run_id:
        return _poll_cache["metrics"]
    if run_id != _poll_cache["run_id"]:
        _poll_cache["run_id"] = run_id
        _poll_cache["line_count"] = 0
        _poll_cache["metrics"] = []
    new_records, new_count = data_loader.load_latest_metrics(run_id, _poll_cache["line_count"])
    if new_records:
        _poll_cache["metrics"].extend(new_records)
        _poll_cache["line_count"] = new_count
    return _poll_cache["metrics"]


# ---------------------------------------------------------------------------
# Button handlers
# ---------------------------------------------------------------------------

def handle_start(max_exp):
    try:
        _run_manager.start(int(max_exp))
        return "Running..."
    except RuntimeError as exc:
        return f"Error: {exc}"


def handle_stop():
    _run_manager.stop()
    return "Stopped"


def handle_pause_resume():
    if _run_manager.status == "paused":
        _run_manager.resume()
        return "Running"
    else:
        _run_manager.pause()
        return "Paused"


# ---------------------------------------------------------------------------
# Status banner
# ---------------------------------------------------------------------------

def _status_banner(metrics: list[dict]) -> str:
    """One-line status summary shown at top of Live tab."""
    if not metrics:
        return "Waiting for first experiment..."

    n = len(metrics)
    kept = sum(1 for m in metrics if _is_kept(m))
    best = max(m.get("composite", 0) for m in metrics)
    cost = sum(m.get("cost", 0) for m in metrics)
    latest = metrics[-1]
    latest_status = "KEPT" if _is_kept(latest) else "DISCARDED"

    return (
        f"**{n}** experiments | **{kept}** kept | "
        f"Best composite: **{best:.4f}** | "
        f"Latest: {latest.get('composite', 0):.4f} ({latest_status}) | "
        f"Cost: **${cost:.2f}** / ${_budget_limit:.2f}"
    )


def _is_kept(m: dict) -> bool:
    gates = m.get("gate_results", {})
    return bool(gates) and all(gates.values())


# ---------------------------------------------------------------------------
# Live tab polling
# ---------------------------------------------------------------------------

def poll_live():
    """Timer callback -- returns all Live tab outputs."""
    status = _run_manager.status
    if status == "error" and _run_manager.last_error:
        status = f"error: {_run_manager.last_error}"

    metrics = _refresh_poll_cache()
    banner = _status_banner(metrics)

    return (
        status,
        banner,
        charts.composite_trend(metrics),
        charts.gate_timeline(metrics),
        charts.radar_chart(metrics[-1] if metrics else {}),
        log_formatter.format_log_stream(metrics),
    )


# ---------------------------------------------------------------------------
# Results tab
# ---------------------------------------------------------------------------

def load_results(run_id: str | None = None):
    """Load results for the results tab. Uses current/latest run if none specified."""
    if not run_id:
        run_id = _run_manager.current_run_id
    if not run_id:
        runs = data_loader.list_runs()
        if runs:
            run_id = runs[0]["run_id"]
    if not run_id:
        empty = charts._empty_figure("No run data yet")
        return empty, empty, empty, empty, [], "No runs found."

    metrics = data_loader.load_run_metrics(run_id)
    if not metrics:
        # Try poll cache (run might still be in progress)
        metrics = _refresh_poll_cache()

    if not metrics:
        empty = charts._empty_figure("No experiment data")
        return empty, empty, empty, empty, [], f"Run {run_id} has no experiment data yet."

    return (
        charts.enhanced_composite_trend(metrics),
        charts.axis_improvement_heatmap(metrics),
        charts.gate_pass_rate(metrics),
        charts.cost_efficiency(metrics),
        _best_scores_table(metrics),
        _results_summary(metrics, run_id),
    )


def _best_scores_table(metrics: list[dict]) -> list[list]:
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
            f"{baseline.get(axis, 0):.4f}",
            f"{best.get(axis, 0):.4f}",
            f"{best.get(axis, 0) - baseline.get(axis, 0):+.4f}",
        ]
        for axis in sorted(best.keys())
    ]


def _results_summary(metrics: list[dict], run_id: str) -> str:
    n = len(metrics)
    kept = sum(1 for m in metrics if _is_kept(m))
    composites = [m.get("composite", 0) for m in metrics]
    baseline = composites[0]
    best = max(composites)
    cost = sum(m.get("cost", 0) for m in metrics)

    gate_fails: dict[str, int] = {}
    for m in metrics:
        for gate, passed in m.get("gate_results", {}).items():
            if not passed:
                gate_fails[gate] = gate_fails.get(gate, 0) + 1

    lines = [
        f"### Run: {run_id}",
        f"- **{n}** experiments, **{kept}** kept ({kept/n*100:.0f}% acceptance rate)" if n else "",
        f"- Baseline composite: **{baseline:.4f}**",
        f"- Best composite: **{best:.4f}** ({best - baseline:+.4f} improvement)",
        f"- Total cost: **${cost:.2f}**",
    ]
    if gate_fails:
        lines.append("- Gate failures: " + ", ".join(f"{g}: {c}" for g, c in sorted(gate_fails.items())))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tab builders
# ---------------------------------------------------------------------------

def _build_live_tab():
    """Tab 1: Monitor the running loop."""
    # Controls
    with gr.Row():
        start_btn = gr.Button("Start Run", variant="primary", scale=2)
        stop_btn = gr.Button("Stop", variant="stop", scale=1)
        pause_btn = gr.Button("Pause / Resume", scale=1)
        max_exp_input = gr.Number(value=10, label="Max Experiments", precision=0, scale=1)
        status_box = gr.Textbox(value="idle", label="Status", interactive=False, scale=1)

    # Status banner
    banner = gr.Markdown(value="Waiting for first experiment...")

    # Hero chart: composite trend
    composite_plot = gr.Plot(label="Composite Score Over Time")

    # Two side-by-side: gates + radar
    with gr.Row():
        with gr.Column():
            gate_plot = gr.Plot(label="Gate Results")
        with gr.Column():
            radar_plot = gr.Plot(label="Latest Per-Axis Scores")

    # Log stream
    log_stream = gr.Markdown(value="No experiments yet.")

    # Wire buttons
    start_btn.click(handle_start, inputs=[max_exp_input], outputs=[status_box])
    stop_btn.click(handle_stop, outputs=[status_box])
    pause_btn.click(handle_pause_resume, outputs=[status_box])

    # Poll every 2 seconds
    timer = gr.Timer(value=2)
    timer.tick(
        poll_live,
        outputs=[status_box, banner, composite_plot, gate_plot, radar_plot, log_stream],
    )


def _build_results_tab():
    """Tab 2: See how performance improved."""
    with gr.Row():
        run_selector = gr.Dropdown(
            label="Select Run",
            choices=[r["run_id"] for r in data_loader.list_runs()],
            value=None,
        )
        refresh_btn = gr.Button("Load Results", variant="primary")

    # Summary
    summary_md = gr.Markdown(value="Select a run and click Load Results.")

    # Hero chart: enhanced composite trend with annotations
    composite_plot = gr.Plot(label="Autoresearch Progress")

    # Analysis row
    with gr.Row():
        with gr.Column():
            heatmap_plot = gr.Plot(label="Per-Axis Improvement Over Time")
        with gr.Column():
            gate_rate_plot = gr.Plot(label="Gate Pass/Fail Breakdown")

    # Cost + scores
    with gr.Row():
        with gr.Column():
            cost_plot = gr.Plot(label="Composite Improvement vs Cost")
        with gr.Column():
            scores_table = gr.Dataframe(
                label="Best Scores vs Baseline",
                headers=["Axis", "Baseline", "Best", "Delta"],
            )

    def on_load(run_id):
        return load_results(run_id)

    refresh_btn.click(
        on_load,
        inputs=[run_selector],
        outputs=[composite_plot, heatmap_plot, gate_rate_plot, cost_plot, scores_table, summary_md],
    )

    # Also auto-load on dropdown change
    run_selector.change(
        on_load,
        inputs=[run_selector],
        outputs=[composite_plot, heatmap_plot, gate_rate_plot, cost_plot, scores_table, summary_md],
    )

    # Auto-refresh results from live run too
    results_timer = gr.Timer(value=5)

    def auto_refresh():
        return load_results(None)

    results_timer.tick(
        auto_refresh,
        outputs=[composite_plot, heatmap_plot, gate_rate_plot, cost_plot, scores_table, summary_md],
    )


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

_THEME = gr.themes.Soft(
    primary_hue="emerald",
    secondary_hue="blue",
    neutral_hue="slate",
)


def create_app() -> gr.Blocks:
    with gr.Blocks(title="Masubi") as app:
        gr.Markdown(
            "# Masubi\n"
            "Autonomous email trust research -- 10 axes, three gates, git ratcheting"
        )

        with gr.Tab("Live Run"):
            _build_live_tab()

        with gr.Tab("Results"):
            _build_results_tab()

    return app


if __name__ == "__main__":
    app = create_app()
    app.launch(theme=_THEME)
