"""Structured logging and run artifact management for Masubi.

Uses structlog for JSON output. Manages per-run directories under runs/<run_id>/.
"""

from __future__ import annotations

import json
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
    """Configure structlog with JSON output, ISO timestamps, and log level."""
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
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

    logger.info("Started run %s at %s", run_id, ctx.start_time.isoformat())
    return ctx


def log_experiment(ctx: RunContext, result: ExperimentResult) -> None:
    """Log an experiment result to metrics.jsonl (append) and store in context."""
    result_dict = result.model_dump()
    ctx.experiments.append(result_dict)

    metrics_path = ctx.run_dir / "metrics.jsonl"
    with open(metrics_path, "a") as f:
        f.write(json.dumps(result_dict, default=str) + "\n")

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

    logger.info("Logged %d predictions to %s", len(predictions), pred_path)


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

    artifacts = RunArtifacts(
        metrics_json=ctx.run_dir / "metrics.jsonl",
        predictions_jsonl=ctx.run_dir / "predictions.jsonl",
        config_json=ctx.run_dir / "config.json",
        summary_txt=summary_path,
    )

    logger.info("Run %s finalized. Summary at %s", ctx.run_id, summary_path)
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
