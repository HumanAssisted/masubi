"""Parse train.py git log, generate diffs for the Code Evolution tab."""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# Only allow safe characters in commit hashes: hex, ^, ~, HEAD
_SAFE_REF_PATTERN = re.compile(r"^[0-9a-fA-F^~]+$|^HEAD[~^0-9]*$")


def _sanitize_ref(ref: str) -> str:
    """Validate a git ref to prevent command injection."""
    ref = ref.strip()
    if not _SAFE_REF_PATTERN.match(ref):
        raise ValueError(f"Invalid git ref: {ref!r}")
    return ref


def get_train_py_log(file: str = "train.py") -> list[dict]:
    """Get git log for train.py.

    Returns list of dicts:
        {"hash": str, "message": str, "date": str, "composite": None}
    """
    try:
        result = subprocess.run(
            ["git", "log", "--follow", "--pretty=format:%H|||%s|||%ai", "--", file],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        logger.warning("git log timed out for %s", file)
        return []
    except OSError as exc:
        logger.warning("git log failed: %s", exc)
        return []

    if not result.stdout.strip():
        return []

    # Pattern to extract composite score from commit message, e.g. "composite=0.724"
    composite_re = re.compile(r"composite[=:]?\s*([\d.]+)")

    commits = []
    for line in result.stdout.strip().split("\n"):
        parts = line.split("|||")
        if len(parts) != 3:
            continue
        commit_hash, message, date = parts
        msg = message.strip()

        # Try to extract composite from commit message
        composite_match = composite_re.search(msg)
        composite = float(composite_match.group(1)) if composite_match else None

        commits.append(
            {
                "hash": commit_hash.strip(),
                "message": msg,
                "date": date.strip(),
                "composite": composite,
            }
        )
    return commits


def get_diff(hash_a: str, hash_b: str, file: str = "train.py") -> str:
    """Get unified diff between two commits for a file.

    Returns empty string on error or timeout.
    """
    try:
        hash_a = _sanitize_ref(hash_a)
        hash_b = _sanitize_ref(hash_b)
    except ValueError as exc:
        logger.warning("Invalid ref: %s", exc)
        return ""

    try:
        result = subprocess.run(
            ["git", "diff", hash_a, hash_b, "--", file],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout
    except subprocess.TimeoutExpired:
        logger.warning("git diff timed out")
        return ""
    except OSError as exc:
        logger.warning("git diff failed: %s", exc)
        return ""


def get_file_at_commit(commit_hash: str, file: str = "train.py") -> str:
    """Get file contents at a specific commit.

    Returns empty string on error or timeout.
    """
    try:
        commit_hash = _sanitize_ref(commit_hash)
    except ValueError as exc:
        logger.warning("Invalid ref: %s", exc)
        return ""

    try:
        result = subprocess.run(
            ["git", "show", f"{commit_hash}:{file}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout
    except subprocess.TimeoutExpired:
        logger.warning("git show timed out")
        return ""
    except OSError as exc:
        logger.warning("git show failed: %s", exc)
        return ""


def get_discarded_diffs(run_id: str, base_dir: Path = Path("runs")) -> list[dict]:
    """Get metadata about discarded experiments from metrics.jsonl.

    Discarded experiments are those where at least one gate failed.
    Returns list of dicts with experiment metadata (not actual diffs,
    since discarded code is reverted and not in git history).
    """
    from autotrust.dashboard.data_loader import load_run_metrics

    metrics = load_run_metrics(run_id, base_dir=base_dir)
    discarded = []
    for i, m in enumerate(metrics):
        gate_results = m.get("gate_results", {})
        if not all(gate_results.values()):
            discarded.append(
                {
                    "experiment": i + 1,
                    "change_description": m.get("change_description", ""),
                    "composite": m.get("composite", 0.0),
                    "gate_results": gate_results,
                }
            )
    return discarded
