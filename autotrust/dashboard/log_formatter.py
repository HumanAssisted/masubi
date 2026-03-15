"""Format experiment results as human-readable log entries."""

from __future__ import annotations

from autotrust.dashboard.utils import is_kept as _is_kept


def _gate_symbols(gate_results: dict) -> str:
    """Format gate results as symbols."""
    symbols = []
    for gate_name, passed in gate_results.items():
        if passed:
            symbols.append(f"pass:{gate_name}")
        else:
            symbols.append(f"FAIL:{gate_name}")
    return "  ".join(symbols)


def _format_time(wall_time: float) -> str:
    """Format wall_time seconds as HH:MM:SS."""
    hours = int(wall_time // 3600)
    minutes = int((wall_time % 3600) // 60)
    seconds = int(wall_time % 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _format_stage2_suffix(result: dict) -> str:
    """Format optional Stage 2 telemetry fields for compact log lines."""
    parts = []

    total_loss = result.get("training_loss", {}).get("total_loss")
    if total_loss is not None:
        parts.append(f"loss={float(total_loss):.3f}")

    param_count = result.get("param_count")
    if param_count is not None:
        parts.append(f"params={float(param_count) / 1e6:.1f}M")

    return "  ".join(parts)


def format_experiment_log_entry(
    result: dict,
    prev_composite: float | None,
    experiment_num: int | None = None,
) -> str:
    """Format a single experiment as a collapsed log line.

    Example:
        [00:03:00] Exp #3  composite=0.724 (+0.031)  KEPT  gates: pass:composite  pass:gold  pass:explanation  $0.03
    """
    composite = result.get("composite", 0.0)
    cost = result.get("cost", 0.0)
    wall_time = result.get("wall_time", 0.0)
    gate_results = result.get("gate_results", {})
    kept = _is_kept(result)

    time_str = _format_time(wall_time)
    exp_label = f"Exp #{experiment_num}  " if experiment_num is not None else ""
    status = "KEPT" if kept else "DISCARDED"

    if prev_composite is None:
        delta_str = "(baseline)"
    else:
        delta = composite - prev_composite
        sign = "+" if delta >= 0 else ""
        delta_str = f"({sign}{delta:.3f})"

    gates_str = _gate_symbols(gate_results)

    stage2_suffix = _format_stage2_suffix(result)
    suffix = f"  {stage2_suffix}" if stage2_suffix else ""

    return (
        f"[{time_str}] {exp_label}composite={composite:.3f} {delta_str}  "
        f"{status}  gates: {gates_str}  ${cost:.2f}{suffix}"
    )


def format_experiment_detail(result: dict, prev_best: dict | None) -> str:
    """Format expanded detail view with per-axis deltas, gate reasons, explanation.

    Returns a multi-line string suitable for Markdown rendering.
    """
    lines = []

    # Per-axis scores table
    lines.append("### Per-Axis Scores")
    lines.append("| Axis | Score | Delta |")
    lines.append("|------|-------|-------|")

    per_axis = result.get("per_axis_scores", {})
    prev_per_axis = (prev_best or {}).get("per_axis_scores", {})

    for axis_name in sorted(per_axis.keys()):
        score = per_axis[axis_name]
        prev_score = prev_per_axis.get(axis_name)
        if prev_score is not None:
            delta = score - prev_score
            sign = "+" if delta >= 0 else ""
            delta_str = f"{sign}{delta:.3f}"
        else:
            delta_str = "---"
        lines.append(f"| {axis_name} | {score:.3f} | {delta_str} |")

    # Gate results
    lines.append("")
    lines.append("### Gate Results")
    gate_results = result.get("gate_results", {})
    for gate_name, passed in gate_results.items():
        status = "PASS" if passed else "FAIL"
        lines.append(f"- **{gate_name}**: {status}")

    # Explanation / change description
    change_desc = result.get("change_description", "")
    if change_desc:
        lines.append("")
        lines.append("### Change Description")
        lines.append(change_desc)

    # Cost breakdown
    lines.append("")
    lines.append(f"### Cost: ${result.get('cost', 0.0):.2f}")

    return "\n".join(lines)


def format_log_stream(metrics: list[dict]) -> str:
    """Format full metrics list as a log stream (newest first).

    Each line is a collapsed log entry. Returns entries joined by newlines.
    """
    if not metrics:
        return "No experiments yet."

    entries = []
    for i, m in enumerate(metrics):
        prev_composite = metrics[i - 1].get("composite") if i > 0 else None
        entry = format_experiment_log_entry(m, prev_composite, experiment_num=i + 1)
        entries.append(entry)

    # Reverse so newest is first
    entries.reverse()
    return "\n".join(entries)
