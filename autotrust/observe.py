"""Structured logging and run artifact management for Masubi.

Uses structlog for JSON output. Manages per-run directories under runs/<run_id>/.
"""

from __future__ import annotations

import json
import logging
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from autotrust.config import Spec
    from autotrust.schemas import ExperimentResult, RunArtifacts


def configure_structlog() -> None:
    """Configure structlog with human-readable console output when interactive.

    Uses ConsoleRenderer when stdout is a terminal (colored, readable).
    Falls back to JSONRenderer when piped or redirected (machine-parseable).
    """
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)

    interactive = hasattr(sys.stderr, "isatty") and sys.stderr.isatty()

    if interactive:
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,
    )


# Configure on import
configure_structlog()

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# RunContext
# ---------------------------------------------------------------------------

@dataclass
class RunContext:
    """Context for a single experiment run."""

    run_id: str
    run_dir: Path
    spec_snapshot: dict[str, Any]
    start_time: datetime
    experiments: list[dict[str, Any]] = field(default_factory=list)


def _status_path(ctx: RunContext) -> Path:
    """Return the status.json path for a run."""
    return ctx.run_dir / "status.json"


def _status_history_path(ctx: RunContext) -> Path:
    """Return the status_history.jsonl path for a run."""
    return ctx.run_dir / "status_history.jsonl"


def update_run_status(
    ctx: RunContext,
    *,
    state: str | None = None,
    phase: str | None = None,
    message: str | None = None,
    experiment_num: int | None = None,
    stage: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Write or update the per-run status.json heartbeat."""
    status_path = _status_path(ctx)

    if status_path.exists():
        try:
            payload = json.loads(status_path.read_text())
        except json.JSONDecodeError:
            payload = {}
    else:
        payload = {}

    payload["run_id"] = ctx.run_id
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()

    if state is not None:
        payload["state"] = state
    if phase is not None:
        payload["phase"] = phase
    if message is not None:
        payload["message"] = message
    if experiment_num is not None:
        payload["experiment_num"] = experiment_num
    if stage is not None:
        payload["stage"] = stage
    if error is not None:
        payload["error"] = error
    elif any(value is not None for value in (state, phase, message, experiment_num, stage)):
        payload.pop("error", None)

    status_path.write_text(json.dumps(payload, indent=2))

    history_path = _status_history_path(ctx)
    with open(history_path, "a") as f:
        f.write(json.dumps(dict(payload), default=str) + "\n")

    return payload


# ---------------------------------------------------------------------------
# Run lifecycle
# ---------------------------------------------------------------------------

def start_run(spec: Spec, base_dir: Path | None = None) -> RunContext:
    """Start a new run. Creates run directory and snapshots config.

    Args:
        spec: The current spec configuration.
        base_dir: Override base directory (default: runs/).
    """
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]

    if base_dir is None:
        base_dir = Path("runs")

    run_dir = base_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Snapshot config
    spec_dict = spec.model_dump()
    config_path = run_dir / "config.json"
    config_path.write_text(json.dumps(spec_dict, indent=2, default=str))

    ctx = RunContext(
        run_id=run_id,
        run_dir=run_dir,
        spec_snapshot=spec_dict,
        start_time=datetime.now(timezone.utc),
    )

    update_run_status(
        ctx,
        state="starting",
        phase="boot",
        message="Run created. Waiting to load data.",
    )

    logger.info("Started run", run_id=run_id, start_time=ctx.start_time.isoformat())
    return ctx


def log_experiment(ctx: RunContext, result: ExperimentResult) -> None:
    """Log an experiment result to metrics.jsonl (append) and store in context."""
    result_dict = result.model_dump(exclude_none=True)
    ctx.experiments.append(result_dict)

    metrics_path = ctx.run_dir / "metrics.jsonl"
    with open(metrics_path, "a") as f:
        f.write(json.dumps(result_dict, default=str) + "\n")

    update_run_status(
        ctx,
        state="running",
        phase="logged-experiment",
        message=f"Logged experiment {len(ctx.experiments)}.",
        experiment_num=len(ctx.experiments),
    )

    logger.info(
        "Experiment %s: composite=%.4f, gates=%s",
        result.run_id,
        result.composite,
        result.gate_results,
    )


def log_predictions(ctx: RunContext, predictions: list[dict[str, Any]]) -> None:
    """Write predictions to predictions.jsonl."""
    pred_path = ctx.run_dir / "predictions.jsonl"
    with open(pred_path, "w") as f:
        for pred in predictions:
            f.write(json.dumps(pred, default=str) + "\n")

    logger.info("Logged predictions", count=len(predictions), path=str(pred_path))


def finalize_run(ctx: RunContext) -> RunArtifacts:
    """Finalize the run. Write summary.txt and return artifact paths."""
    from autotrust.schemas import RunArtifacts

    elapsed = (datetime.now(timezone.utc) - ctx.start_time).total_seconds()

    summary_path = ctx.run_dir / "summary.txt"
    summary_lines = [
        f"Run ID: {ctx.run_id}",
        f"Start time: {ctx.start_time.isoformat()}",
        f"Wall time: {elapsed:.1f}s",
        f"Experiments: {len(ctx.experiments)}",
    ]

    if ctx.experiments:
        best = max(ctx.experiments, key=lambda e: e.get("composite", 0))
        summary_lines.append(f"Best composite: {best.get('composite', 'N/A')}")
        total_cost = sum(e.get("cost", 0) for e in ctx.experiments)
        summary_lines.append(f"Total cost: ${total_cost:.2f}")

    summary_path.write_text("\n".join(summary_lines))

    update_run_status(
        ctx,
        state="completed",
        phase="done",
        message=f"Run complete with {len(ctx.experiments)} experiments.",
        experiment_num=len(ctx.experiments),
    )

    artifacts = RunArtifacts(
        metrics_json=ctx.run_dir / "metrics.jsonl",
        predictions_jsonl=ctx.run_dir / "predictions.jsonl",
        config_json=ctx.run_dir / "config.json",
        summary_txt=summary_path,
    )

    logger.info("Run finalized", run_id=ctx.run_id, summary=str(summary_path))
    return artifacts


# ---------------------------------------------------------------------------
# Calibration warnings
# ---------------------------------------------------------------------------

def log_downweight_warning(
    ctx: RunContext,
    axis_name: str,
    original_weight: float,
    effective_weight: float,
    kappa: float,
) -> None:
    """Log when an axis is downweighted due to low Kappa."""
    logger.warning(
        "Axis '%s' downweighted: %.4f -> %.4f (Kappa=%.3f)",
        axis_name,
        original_weight,
        effective_weight,
        kappa,
    )


def log_weight_redistribution(ctx: RunContext, redistributed: dict[str, float]) -> None:
    """Log how weight was redistributed after downweighting."""
    logger.info(
        "Weight redistributed: %s",
        {k: f"{v:.4f}" for k, v in redistributed.items()},
    )
