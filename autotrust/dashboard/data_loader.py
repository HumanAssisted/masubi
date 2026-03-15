"""Read runs/ text files, parse JSONL for dashboard display."""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_run_status(run_id: str, base_dir: Path = Path("runs")) -> dict:
    """Load status.json for a run. Returns empty dict if missing or invalid."""
    status_path = base_dir / run_id / "status.json"
    if not status_path.exists():
        return {}
    try:
        return json.loads(status_path.read_text())
    except (json.JSONDecodeError, OSError):
        logger.warning("Failed to parse status at %s", status_path)
        return {}


def load_run_status_history(
    run_id: str,
    limit: int = 20,
    base_dir: Path = Path("runs"),
) -> list[dict]:
    """Load recent status-history events for a run."""
    history_path = base_dir / run_id / "status_history.jsonl"
    if not history_path.exists():
        return []

    records = []
    for line in history_path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning("Skipping malformed status-history line in %s", history_path)

    if limit <= 0:
        return records
    return records[-limit:]


def list_runs(base_dir: Path = Path("runs")) -> list[dict]:
    """List all runs with metadata from summary.txt and metrics.jsonl.

    Returns list of dicts sorted by run_id descending (newest first):
        {"run_id": str, "date": str, "experiment_count": int,
         "best_composite": float, "total_cost": float, "status": str}
    """
    if not base_dir.exists():
        return []

    runs = []
    for entry in base_dir.iterdir():
        if not entry.is_dir():
            continue

        run_id = entry.name
        info: dict = {
            "run_id": run_id,
            "date": "",
            "experiment_count": 0,
            "best_composite": 0.0,
            "total_cost": 0.0,
            "status": "unknown",
            "status_message": "",
        }

        # Count experiments from metrics.jsonl
        metrics_path = entry / "metrics.jsonl"
        status = load_run_status(run_id, base_dir=base_dir)
        if metrics_path.exists():
            lines = [ln for ln in metrics_path.read_text().strip().split("\n") if ln.strip()]
            info["experiment_count"] = len(lines)

            # Parse to find best composite and total cost
            best_composite = 0.0
            total_cost = 0.0
            for line in lines:
                try:
                    record = json.loads(line)
                    composite = record.get("composite", 0.0)
                    if composite > best_composite:
                        best_composite = composite
                    total_cost += record.get("cost", 0.0)
                except json.JSONDecodeError:
                    continue
            info["best_composite"] = best_composite
            info["total_cost"] = total_cost

        # Parse summary.txt for date and status
        summary_path = entry / "summary.txt"
        if summary_path.exists():
            for line in summary_path.read_text().strip().split("\n"):
                if line.startswith("Start time:"):
                    info["date"] = line.split(":", 1)[1].strip()
                elif line.startswith("Run ID:"):
                    pass  # already have it
            info["status"] = "completed"
        elif status.get("state"):
            info["status"] = status["state"]
        elif metrics_path.exists():
            info["status"] = "interrupted"

        if status.get("message"):
            info["status_message"] = status["message"]

        runs.append(info)

    # Sort by run_id descending (run IDs start with timestamps)
    runs.sort(key=lambda r: r["run_id"], reverse=True)
    return runs


def format_run_choice(run: dict) -> tuple[str, str]:
    """Format a run metadata dict as a human-readable dropdown label."""
    run_id = run.get("run_id", "unknown")
    status = run.get("status", "unknown")
    experiment_count = int(run.get("experiment_count", 0) or 0)
    best_composite = float(run.get("best_composite", 0.0) or 0.0)
    total_cost = float(run.get("total_cost", 0.0) or 0.0)

    exp_label = "1 exp" if experiment_count == 1 else f"{experiment_count} exp"
    parts = [status, run_id, exp_label]

    if experiment_count:
        parts.append(f"best {best_composite:.4f}")
    if total_cost:
        parts.append(f"${total_cost:.2f}")

    return (" | ".join(parts), run_id)


def load_run_metrics(run_id: str, base_dir: Path = Path("runs")) -> list[dict]:
    """Load metrics.jsonl for a run as a list of dicts.

    Skips malformed lines with a warning log. Returns empty list if file missing.
    """
    metrics_path = base_dir / run_id / "metrics.jsonl"
    if not metrics_path.exists():
        return []

    records = []
    for line_num, line in enumerate(metrics_path.read_text().strip().split("\n"), 1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning("Skipping malformed line %d in %s", line_num, metrics_path)
    return records


def load_latest_metrics(
    run_id: str,
    after_line: int = 0,
    base_dir: Path = Path("runs"),
) -> tuple[list[dict], int]:
    """Load only new lines from metrics.jsonl (for polling).

    Returns (new_records, total_line_count) so the caller can pass
    total_line_count as after_line next time.
    """
    metrics_path = base_dir / run_id / "metrics.jsonl"
    if not metrics_path.exists():
        return [], 0

    lines = [ln for ln in metrics_path.read_text().strip().split("\n") if ln.strip()]
    total = len(lines)
    new_lines = lines[after_line:]

    records = []
    for line in new_lines:
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning("Skipping malformed line in %s", metrics_path)
    return records, total


def load_run_summary(run_id: str, base_dir: Path = Path("runs")) -> str:
    """Load summary.txt as plain text. Returns empty string if missing."""
    summary_path = base_dir / run_id / "summary.txt"
    if not summary_path.exists():
        return ""
    return summary_path.read_text()


def load_calibration(path: Path = Path("gold_set/calibration.json")) -> dict:
    """Load gold_set/calibration.json. Returns empty dict if missing."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        logger.warning("Failed to parse calibration at %s", path)
        return {}


def load_spec_text(path: Path = Path("spec.yaml")) -> str:
    """Load spec.yaml as raw text for display in the Config tab."""
    if not path.exists():
        return ""
    return path.read_text()
