"""Teacher artifact extraction and freezing for Stage 1 -> Stage 2 handoff.

Extracts the best-performing scoring prompt, labeling rules, and explanation
schema from train.py git history and writes them to the teacher/ directory.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
import yaml

from autotrust.schemas import TeacherArtifacts

if TYPE_CHECKING:
    from autotrust.config import Spec

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Git history helpers (thin wrappers around dashboard.git_history)
# ---------------------------------------------------------------------------


def _get_train_py_log() -> list[dict]:
    """Get train.py git log with composite scores."""
    from autotrust.dashboard.git_history import get_train_py_log
    return get_train_py_log()


def _get_file_at_commit(commit_hash: str, file: str = "train.py") -> str:
    """Get file contents at a specific commit."""
    from autotrust.dashboard.git_history import get_file_at_commit
    return get_file_at_commit(commit_hash, file)


# ---------------------------------------------------------------------------
# Extraction functions
# ---------------------------------------------------------------------------


def extract_prompt_pack(train_py_source: str) -> dict:
    """Extract the scoring prompt template from train.py source code.

    Parses the _build_prompt method to find the prompt template string
    and axis guidance construction.

    Args:
        train_py_source: full source code of train.py

    Returns:
        Dict with prompt_template and axis_guidance suitable for YAML serialization.
    """
    pack: dict = {}

    # Extract the main prompt template from f-string in _build_prompt
    prompt_match = re.search(
        r'prompt\s*=\s*f?"""(.*?)"""',
        train_py_source,
        re.DOTALL,
    )
    if prompt_match:
        pack["prompt_template"] = prompt_match.group(1).strip()
    else:
        # Fallback: extract any large string with "trust" in it
        string_match = re.search(
            r'"""(.*?trust.*?)"""',
            train_py_source,
            re.DOTALL,
        )
        pack["prompt_template"] = string_match.group(1).strip() if string_match else ""

    # Extract axis-specific guidance mappings
    axis_guidance: dict[str, str] = {}
    guidance_pattern = re.compile(
        r'elif\s+axis\.name\s*==\s*"(\w+)".*?\n\s+guidance\s*=\s*"([^"]+)"',
        re.DOTALL,
    )
    for match in guidance_pattern.finditer(train_py_source):
        axis_guidance[match.group(1)] = match.group(2)

    # Also catch the first if case
    first_match = re.search(
        r'if\s+axis\.name\s*==\s*"(\w+)".*?\n\s+guidance\s*=\s*"([^"]+)"',
        train_py_source,
    )
    if first_match:
        axis_guidance[first_match.group(1)] = first_match.group(2)

    pack["axis_guidance"] = axis_guidance

    # Extract analysis framework sections
    framework_match = re.search(
        r"ANALYSIS FRAMEWORK:\n(.*?)(?=\nFor each axis|\nRespond with)",
        train_py_source,
        re.DOTALL,
    )
    if framework_match:
        pack["analysis_framework"] = framework_match.group(1).strip()

    return pack


def extract_label_rules(train_py_source: str) -> dict:
    """Extract labeling rules and thresholds from train.py source code.

    Args:
        train_py_source: full source code of train.py

    Returns:
        Dict with flag_threshold, scoring rules, and heuristics.
    """
    rules: dict = {}

    # Extract flag threshold (score > threshold -> flagged)
    threshold_match = re.search(r"score\s*>\s*([\d.]+)", train_py_source)
    rules["flag_threshold"] = float(threshold_match.group(1)) if threshold_match else 0.5

    # Extract authority patterns
    authority_patterns: list[str] = []
    auth_match = re.findall(r"r'\\b\(([^)]+)\)\\b'.*?'([^']+)'", train_py_source)
    for pattern_content, desc in auth_match:
        authority_patterns.append(f"{desc}: {pattern_content}")
    rules["authority_patterns"] = authority_patterns

    # Extract urgency patterns
    urgency_match = re.findall(
        r"urgency_patterns\s*=.*?\[.*?\]",
        train_py_source,
        re.DOTALL,
    )
    rules["urgency_detection"] = bool(urgency_match)

    # Extract content thresholds
    brief_match = re.search(r"len\(all_text\)\s*<\s*(\d+)", train_py_source)
    lengthy_match = re.search(r"len\(all_text\)\s*>\s*(\d+)", train_py_source)
    rules["content_thresholds"] = {
        "brief_chars": int(brief_match.group(1)) if brief_match else 100,
        "lengthy_chars": int(lengthy_match.group(1)) if lengthy_match else 2000,
    }

    # Extract timing thresholds
    rapid_match = re.search(r"delta\s*<\s*(\d+).*?rapid", train_py_source, re.IGNORECASE)
    quick_match = re.search(r"delta\s*<\s*(\d+).*?quick", train_py_source, re.IGNORECASE)
    rules["timing_thresholds"] = {
        "rapid_reply_seconds": int(rapid_match.group(1)) if rapid_match else 300,
        "quick_reply_seconds": int(quick_match.group(1)) if quick_match else 3600,
    }

    return rules


def extract_explanation_schema(train_py_source: str, spec: Spec) -> dict:
    """Extract explanation format and reason tag vocabulary.

    Args:
        train_py_source: full source code of train.py
        spec: loaded Spec with axis definitions

    Returns:
        Dict with axis_names, explanation_format, and output_schema.
    """
    schema: dict = {}

    # Axis names from spec (authoritative source)
    schema["axis_names"] = [a.name for a in spec.trust_axes]

    # Explanation format from the prompt
    schema["explanation_format"] = {
        "reasons": "array of axis names scoring > flag_threshold",
        "summary": "concise one-sentence summary of primary concerns",
    }

    # Output schema shape
    schema["output_schema"] = {
        "trust_vector": {name: "float [0.0, 1.0]" for name in schema["axis_names"]},
        "explanation": {
            "reasons": ["axis_name_1", "axis_name_2"],
            "summary": "string",
        },
    }

    return schema


# ---------------------------------------------------------------------------
# Write artifacts
# ---------------------------------------------------------------------------


def write_teacher_artifacts(
    train_py_source: str,
    spec: Spec,
    teacher_dir: Path,
) -> TeacherArtifacts:
    """Write frozen teacher artifacts to the teacher/ directory.

    Args:
        train_py_source: source code of the best train.py
        spec: loaded Spec
        teacher_dir: path to the teacher/ directory

    Returns:
        TeacherArtifacts with paths to the written files.
    """
    teacher_dir.mkdir(parents=True, exist_ok=True)

    # Extract artifacts
    prompt_pack = extract_prompt_pack(train_py_source)
    label_rules = extract_label_rules(train_py_source)
    explanation_schema = extract_explanation_schema(train_py_source, spec)

    # Write prompt_pack.yaml
    prompt_pack_path = teacher_dir / "prompt_pack.yaml"
    with open(prompt_pack_path, "w") as f:
        yaml.dump(prompt_pack, f, default_flow_style=False, allow_unicode=True)

    # Write label_rules.yaml
    label_rules_path = teacher_dir / "label_rules.yaml"
    with open(label_rules_path, "w") as f:
        yaml.dump(label_rules, f, default_flow_style=False, allow_unicode=True)

    # Write explanation_schema.json
    explanation_schema_path = teacher_dir / "explanation_schema.json"
    with open(explanation_schema_path, "w") as f:
        json.dump(explanation_schema, f, indent=2)

    synth_data_dir = teacher_dir.parent / "synth_data"

    return TeacherArtifacts(
        prompt_pack_path=prompt_pack_path,
        label_rules_path=label_rules_path,
        explanation_schema_path=explanation_schema_path,
        synth_data_dir=synth_data_dir,
    )


# ---------------------------------------------------------------------------
# Main freeze function
# ---------------------------------------------------------------------------


def freeze_teacher(
    spec: Spec,
    teacher_dir: Path | None = None,
    run_id: str | None = None,
) -> TeacherArtifacts:
    """Freeze teacher artifacts from the best Stage 1 train.py commit.

    1. Finds the best train.py commit (highest composite)
    2. Reads train.py at that commit
    3. Extracts prompt pack, label rules, explanation schema
    4. Writes to teacher/ directory

    Args:
        spec: loaded Spec
        teacher_dir: override teacher directory path
        run_id: optional run ID for context

    Returns:
        TeacherArtifacts with paths to frozen files.
    """
    if teacher_dir is None:
        teacher_dir = Path("teacher")

    # Find best commit
    log = _get_train_py_log()
    if not log:
        logger.warning("No git history found for train.py, using current file")
        source = Path("train.py").read_text()
    else:
        # Find commit with highest composite
        scored = [c for c in log if c.get("composite") is not None]
        if scored:
            best = max(scored, key=lambda c: c["composite"])
            logger.info(
                "Freezing from best commit",
                hash=best["hash"][:8],
                composite=best["composite"],
            )
            source = _get_file_at_commit(best["hash"])
            if not source:
                logger.warning("Could not read train.py at commit %s, using current", best["hash"][:8])
                source = Path("train.py").read_text()
        else:
            logger.warning("No scored commits found, using current train.py")
            source = Path("train.py").read_text()

    artifacts = write_teacher_artifacts(source, spec, teacher_dir)
    logger.info("Teacher artifacts frozen", teacher_dir=str(teacher_dir))
    return artifacts
