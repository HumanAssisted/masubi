"""Masubi dashboard -- two tabs, focused on what matters.

Tab 1: Live Run  -- monitor the autoresearch loop as it runs
Tab 2: Results   -- see how performance improved over time
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import gradio as gr

from autotrust.dashboard import charts, data_loader, log_formatter
from autotrust.dashboard.run_manager import RunManager
from autotrust.dashboard.utils import is_kept as _is_kept

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


def _load_current_run_status() -> dict:
    """Load status metadata for the current external or local run."""
    run_id = _run_manager.current_run_id
    if not run_id:
        return {}
    return data_loader.load_run_status(run_id)


def _format_currency(value: object) -> str:
    """Format dashboard currency fields defensively."""
    try:
        return f"${float(value):.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def _format_started_at(value: str) -> str:
    """Format ISO timestamps into a friendlier local-looking string."""
    if not value:
        return "unknown"
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return value


# ---------------------------------------------------------------------------
# Status banner
# ---------------------------------------------------------------------------

def _status_banner(metrics: list[dict]) -> str:
    """One-line status summary shown at top of Live tab."""
    if not metrics:
        status = _run_manager.status
        run_status = _load_current_run_status()
        if run_status.get("message"):
            return f"**{status}** | {run_status['message']}"
        if "starting" in status:
            return "Run detected -- waiting for first experiment to complete..."
        if "running" in status:
            return "Run in progress -- waiting for first result..."
        return "Waiting for first experiment... (start a run with `uv run python run_loop.py`)"

    n = len(metrics)
    kept = sum(1 for m in metrics if _is_kept(m))
    best = max(m.get("composite", 0) for m in metrics)
    cost = sum(m.get("cost", 0) for m in metrics)
    latest = metrics[-1]
    latest_status = "KEPT" if _is_kept(latest) else "DISCARDED"
    stage2_snapshot = _stage2_snapshot(latest)
    stage2_suffix = f" | {stage2_snapshot}" if stage2_snapshot else ""

    return (
        f"**{n}** experiments | **{kept}** kept | "
        f"Best composite: **{best:.4f}** | "
        f"Latest: {latest.get('composite', 0):.4f} ({latest_status}) | "
        f"Cost: **${cost:.2f}** / ${_budget_limit:.2f}"
        f"{stage2_suffix}"
    )


def _run_snapshot(status: dict, metrics: list[dict]) -> str:
    """Compact run card shown even before charts have data."""
    if not status and not metrics and not _run_manager.current_run_id:
        return "### Run Snapshot\nWaiting for a run."

    lines = ["### Run Snapshot"]
    run_id = _run_manager.current_run_id
    if run_id:
        lines.append(f"**Run ID:** `{run_id}`")

    stage = status.get("stage")
    phase = status.get("phase")
    if stage or phase:
        lines.append(f"**Stage / Phase:** `{stage or 'unknown'}` / `{phase or 'unknown'}`")

    current_exp = status.get("current_experiment", status.get("experiment_num"))
    max_exp = status.get("max_experiments")
    if current_exp is not None or max_exp is not None:
        if max_exp is not None:
            lines.append(f"**Experiment:** {current_exp or 0} / {max_exp}")
        else:
            lines.append(f"**Experiment:** {current_exp}")

    eval_count = status.get("eval_count")
    gold_count = status.get("gold_count")
    if eval_count is not None or gold_count is not None:
        lines.append(f"**Eval / Gold:** {eval_count or 0} / {gold_count or 0}")

    if status.get("spent_usd") is not None:
        lines.append(f"**Spend:** {_format_currency(status.get('spent_usd'))}")

    if status.get("agent_model"):
        lines.append(f"**Agent:** `{status['agent_model']}`")

    if status.get("started_at"):
        lines.append(f"**Started:** {_format_started_at(status['started_at'])}")

    latest = metrics[-1] if metrics else {}
    latest_decision = status.get("latest_decision")
    latest_composite = status.get("latest_composite")
    if latest:
        latest_decision = latest_decision or ("KEPT" if _is_kept(latest) else "DISCARDED")
        latest_composite = latest_composite if latest_composite is not None else latest.get("composite")

    if latest_decision:
        lines.append(f"**Latest decision:** {latest_decision}")
    if latest_composite is not None:
        lines.append(f"**Latest composite:** {float(latest_composite):.4f}")

    if status.get("message"):
        lines.extend(["", f"**Message:** {status['message']}"])

    if not metrics:
        if status.get("state") == "completed":
            lines.extend(
                [
                    "",
                    "_Run completed without scored experiments. The live snapshot and timeline stay visible until a newer run starts._",
                ]
            )
        else:
            lines.extend(["", "_No scored experiments yet. Charts populate after `metrics.jsonl` entries are written._"])

    return "\n".join(lines)


def _stage2_snapshot(result: dict) -> str:
    """Compact summary of Stage 2 telemetry for banners and summaries."""
    parts = []

    total_loss = result.get("training_loss", {}).get("total_loss")
    if total_loss is not None:
        parts.append(f"Stage 2 loss: **{float(total_loss):.3f}**")

    param_count = result.get("param_count")
    if param_count is not None:
        parts.append(f"Params: **{float(param_count) / 1e6:.1f}M**")

    expert_utilization = result.get("expert_utilization", [])
    if expert_utilization:
        hottest = max(enumerate(expert_utilization), key=lambda item: item[1])
        parts.append(f"Top expert: **E{hottest[0]} {hottest[1]:.2f}**")

    return " | ".join(parts)


def _run_selector_choices() -> list[tuple[str, str]]:
    """Build dropdown labels that make live vs historical runs easier to scan."""
    return [data_loader.format_run_choice(run) for run in data_loader.list_runs()]


def _resolve_results_run(run_id: str | None = None) -> tuple[str | None, str, dict | None]:
    """Resolve which run the Results tab should display and how to label it."""
    runs = data_loader.list_runs()
    current_run_id = _run_manager.current_run_id
    runs_by_id = {run["run_id"]: run for run in runs}
    live_statuses = {"starting", "running", "paused", "stopping", "finalizing"}

    if run_id:
        run_info = runs_by_id.get(run_id, {"run_id": run_id, "status": "unknown"})
        if run_id == current_run_id and run_info.get("status") in live_statuses:
            return run_id, "selected live run", run_info
        if run_id == current_run_id:
            return run_id, "selected current run", run_info
        return run_id, "selected historical run", run_info

    if current_run_id:
        run_info = runs_by_id.get(current_run_id, {"run_id": current_run_id, "status": "running"})
        if run_info.get("status") in live_statuses:
            return current_run_id, "live run", run_info
        return current_run_id, "latest run", run_info

    if runs:
        return runs[0]["run_id"], "latest completed run", runs[0]

    return None, "no run", None


# ---------------------------------------------------------------------------
# Live tab polling
# ---------------------------------------------------------------------------

_last_metrics_len = 0


def poll_live():
    """Timer callback -- returns all Live tab outputs.

    Uses gr.update() for charts when data hasn't changed to prevent
    the browser from re-rendering (which causes page jumping).
    """
    global _last_metrics_len

    status = _run_manager.status
    if status == "error" and _run_manager.last_error:
        status = f"error: {_run_manager.last_error}"

    metrics = _refresh_poll_cache()
    run_status = _load_current_run_status()
    banner = _status_banner(metrics)
    snapshot = _run_snapshot(run_status, metrics)

    if metrics:
        log_stream = log_formatter.format_log_stream(metrics)
    else:
        run_id = _run_manager.current_run_id
        if run_id:
            history = data_loader.load_run_status_history(run_id, limit=8)
            if history:
                log_stream = log_formatter.format_status_history(history)
            else:
                log_stream = run_status.get("message", "No experiments yet.")
        else:
            log_stream = run_status.get("message", "No experiments yet.")

    # Only re-render charts when metrics count changes (prevents page jumping)
    if len(metrics) != _last_metrics_len:
        _last_metrics_len = len(metrics)
        composite = charts.composite_trend(metrics)
        gates = charts.gate_timeline(metrics)
        radar = charts.radar_chart(metrics[-1] if metrics else {})
    else:
        composite = gr.update()
        gates = gr.update()
        radar = gr.update()

    return (
        status,
        banner,
        snapshot,
        composite,
        gates,
        radar,
        log_stream,
    )


# ---------------------------------------------------------------------------
# Results tab
# ---------------------------------------------------------------------------

def load_results(run_id: str | None = None):
    """Load results for the results tab. Uses current/latest run if none specified."""
    run_id, view_label, run_info = _resolve_results_run(run_id)
    if not run_id:
        empty = charts._empty_figure("No run data yet")
        return empty, empty, empty, empty, [], "No runs found."

    metrics = data_loader.load_run_metrics(run_id)
    if not metrics and run_id == _run_manager.current_run_id:
        # Try poll cache (run might still be in progress)
        metrics = _refresh_poll_cache()

    if not metrics:
        empty = charts._empty_figure("No experiment data")
        status_message = run_info.get("status_message", "") if run_info else ""
        run_status = data_loader.load_run_status(run_id)
        history = data_loader.load_run_status_history(run_id, limit=10)
        summary_text = data_loader.load_run_summary(run_id).strip()

        details = [f"### Run: {run_id}", f"**Viewing:** {view_label}"]
        if run_info is not None:
            details.append(f"**Status:** {run_info.get('status', 'unknown')}")
        if run_status.get("stage") or run_status.get("phase"):
            details.append(
                f"**Stage / Phase:** `{run_status.get('stage', 'unknown')}` / `{run_status.get('phase', 'unknown')}`"
            )
        if status_message:
            details.append(f"**Message:** {status_message}")
        if run_status.get("current_experiment") or run_status.get("experiment_num"):
            current_exp = run_status.get("current_experiment", run_status.get("experiment_num"))
            max_exp = run_status.get("max_experiments")
            if max_exp is not None:
                details.append(f"**Experiment:** {current_exp} / {max_exp}")
            else:
                details.append(f"**Experiment:** {current_exp}")
        if run_status.get("eval_count") is not None or run_status.get("gold_count") is not None:
            details.append(
                f"**Eval / Gold:** {run_status.get('eval_count', 0)} / {run_status.get('gold_count', 0)}"
            )
        if run_status.get("spent_usd") is not None:
            details.append(f"**Spend:** {_format_currency(run_status.get('spent_usd'))}")
        details.extend(["", "No experiment metrics were written for this run."])

        if history:
            details.extend(
                [
                    "",
                    "#### Recent Timeline",
                    "```text",
                    log_formatter.format_status_history(history),
                    "```",
                ]
            )
        if summary_text:
            details.extend(
                [
                    "",
                    "#### Summary File",
                    "```text",
                    summary_text,
                    "```",
                ]
            )
        return (
            empty,
            empty,
            empty,
            empty,
            [],
            "\n".join(details),
        )

    return (
        charts.enhanced_composite_trend(metrics),
        charts.axis_improvement_heatmap(metrics),
        charts.gate_pass_rate(metrics),
        charts.cost_efficiency(metrics),
        _best_scores_table(metrics),
        _results_summary(metrics, run_id, view_label=view_label, run_info=run_info),
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


def _results_summary(
    metrics: list[dict],
    run_id: str,
    *,
    view_label: str,
    run_info: dict | None,
) -> str:
    lines = [f"### Run: {run_id}", f"**Viewing:** {view_label}"]

    if run_info is not None:
        lines.append(f"**Status:** {run_info.get('status', 'unknown')}")

    summary = charts.summary_stats(metrics)
    if summary:
        lines.extend(["", summary])

    stage2_snapshot = _stage2_snapshot(metrics[-1])
    if stage2_snapshot:
        lines.extend(["", f"**Latest Stage 2:** {stage2_snapshot}"])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tab builders
# ---------------------------------------------------------------------------

def _build_live_tab():
    """Tab 1: Monitor the running loop (view-only -- runs are started from CLI)."""
    # Status
    status_box = gr.Textbox(value="idle", label="Status", interactive=False)

    # Status banner
    banner = gr.Markdown(value="Waiting for first experiment... (start a run with `uv run python run_loop.py`)")
    snapshot = gr.Markdown(value="### Run Snapshot\nWaiting for a run.")

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

    # Poll every 2 seconds
    timer = gr.Timer(value=5)
    timer.tick(
        poll_live,
        outputs=[status_box, banner, snapshot, composite_plot, gate_plot, radar_plot, log_stream],
    )


def _build_results_tab():
    """Tab 2: See how performance improved."""
    initial_run_id, _view_label, _run_info = _resolve_results_run()
    initial_results = load_results(initial_run_id)

    with gr.Row():
        run_selector = gr.Dropdown(
            label="Select Run",
            choices=_run_selector_choices(),
            value=initial_run_id,
            info="Leave blank to follow the live or latest run.",
        )
        refresh_btn = gr.Button("Load Results", variant="primary")

    # Summary
    summary_md = gr.Markdown(value=initial_results[5])

    # Hero chart: enhanced composite trend with annotations
    composite_plot = gr.Plot(label="Autoresearch Progress", value=initial_results[0])

    # Analysis row
    with gr.Row():
        with gr.Column():
            heatmap_plot = gr.Plot(label="Per-Axis Improvement Over Time", value=initial_results[1])
        with gr.Column():
            gate_rate_plot = gr.Plot(label="Gate Pass/Fail Breakdown", value=initial_results[2])

    # Cost + scores
    with gr.Row():
        with gr.Column():
            cost_plot = gr.Plot(label="Composite Improvement vs Cost", value=initial_results[3])
        with gr.Column():
            scores_table = gr.Dataframe(
                label="Best Scores vs Baseline",
                headers=["Axis", "Baseline", "Best", "Delta"],
                value=initial_results[4],
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

    # No auto-refresh timer -- prevents page jumping. Users click "Load Results"
    # or the Live tab polls independently.


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
    import argparse

    parser = argparse.ArgumentParser(description="Masubi dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()

    app = create_app()
    app.launch(
        theme=_THEME,
        server_name=args.host,
        server_port=args.port,
        show_error=True,
    )
