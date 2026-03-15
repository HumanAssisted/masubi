"""Teacher artifact extraction and freezing for Stage 1 -> Stage 2 handoff.

Extracts the best-performing scoring prompt, labeling rules, and explanation
schema from starting_train.py git history and writes them to the teacher/ directory.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
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
    """Get train.py git log with composite scores.

    Tracks train.py (the working copy that gets committed during runs)
    since that is where the agent's edits are recorded in git history.
    """
    from autotrust.dashboard.git_history import get_train_py_log
    return get_train_py_log()


def _get_file_at_commit(commit_hash: str, file: str = "train.py") -> str:
    """Get file contents at a specific commit."""
    from autotrust.dashboard.git_history import get_file_at_commit
    return get_file_at_commit(commit_hash, file)


def _load_stage1_scorer_class(path: Path | None = None):
    """Load EmailTrustScorer from the live Stage 1 working copy when available."""
    scorer_path = path or Path("train.py")
    if not scorer_path.exists():
        scorer_path = Path("starting_train.py")

    module_name = f"masubi_freeze_{scorer_path.stem}_{scorer_path.stat().st_mtime_ns}"
    spec = importlib.util.spec_from_file_location(module_name, scorer_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load EmailTrustScorer from {scorer_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)

    scorer_cls = getattr(module, "EmailTrustScorer", None)
    if scorer_cls is None:
        raise ImportError(f"{scorer_path} does not define EmailTrustScorer")
    return scorer_cls


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

    Falls back to starting_train.py (the canonical template) when no git
    history is available.

    Args:
        spec: loaded Spec
        teacher_dir: override teacher directory path
        run_id: optional run ID for context

    Returns:
        TeacherArtifacts with paths to frozen files.
    """
    if teacher_dir is None:
        teacher_dir = Path("teacher")

    def _read_fallback_source() -> str:
        """Read from starting_train.py (canonical) or train.py (working copy)."""
        starting = Path("starting_train.py")
        if starting.exists():
            return starting.read_text()
        return Path("train.py").read_text()

    # Find best commit
    log = _get_train_py_log()
    if not log:
        logger.warning("No git history found for train.py, using starting_train.py")
        source = _read_fallback_source()
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
                logger.warning("Could not read train.py at commit %s, using starting_train.py", best["hash"][:8])
                source = _read_fallback_source()
        else:
            logger.warning("No scored commits found, using starting_train.py")
            source = _read_fallback_source()

    artifacts = write_teacher_artifacts(source, spec, teacher_dir)
    logger.info("Teacher artifacts frozen", teacher_dir=str(teacher_dir))
    return artifacts


# ---------------------------------------------------------------------------
# Re-label training data
# ---------------------------------------------------------------------------


def relabel_training_data(artifacts: TeacherArtifacts, spec: Spec) -> Path:
    """Re-label training data using frozen teacher prompts.

    Loads existing synth_data/train.jsonl, scores each chain using the
    frozen teacher prompts via ScoringProvider, and writes updated JSONL
    with soft trust vectors as training targets.

    Args:
        artifacts: frozen teacher artifacts with paths
        spec: loaded Spec

    Returns:
        Path to the output labeled JSONL file.
    """
    # Load prompt pack for context
    prompt_pack_path = artifacts.prompt_pack_path
    if prompt_pack_path.exists():
        prompt_pack = yaml.safe_load(prompt_pack_path.read_text())
        logger.info("Loaded prompt pack for relabeling", keys=list(prompt_pack.keys()))

    # Determine input/output paths
    synth_dir = artifacts.synth_data_dir
    input_path = synth_dir / "train.jsonl"
    output_path = synth_dir / "train_labeled.jsonl"

    if not input_path.exists():
        logger.warning("No training data found at %s", input_path)
        return output_path

    # Read input records
    records = []
    for line in input_path.read_text().strip().split("\n"):
        if line.strip():
            records.append(json.loads(line))

    if not records:
        logger.warning("Empty training data at %s", input_path)
        return output_path

    # Score each record using the scoring provider
    try:
        from autotrust.providers import get_provider
        scorer_provider = get_provider("scorer", spec)
    except Exception as exc:
        logger.warning(
            "Could not initialize scoring provider for relabeling: %s. "
            "Using existing labels as soft targets.",
            exc,
        )
        # Fallback: use existing labels as soft targets
        labeled_records = []
        for record in records:
            labeled = dict(record)
            # Use existing labels/trust_vector as soft targets
            if "trust_vector" not in labeled and "labels" in labeled:
                labeled["soft_targets"] = labeled["labels"]
            elif "trust_vector" in labeled:
                labeled["soft_targets"] = labeled["trust_vector"]
            labeled_records.append(labeled)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            for rec in labeled_records:
                f.write(json.dumps(rec) + "\n")

        logger.info(
            "Wrote labeled training data (from existing labels)",
            count=len(labeled_records),
            path=str(output_path),
        )
        return output_path

    # Full relabeling with the current/best Stage 1 scorer
    from autotrust.schemas import EmailChain

    EmailTrustScorer = _load_stage1_scorer_class()
    scorer = EmailTrustScorer(provider=scorer_provider, spec=spec)

    labeled_records = []
    for record in records:
        try:
            # Parse record as EmailChain if possible
            chain = EmailChain.model_validate(record)
            # Score using the frozen teacher scorer (builds prompt, calls provider, parses response)
            scorer_output = scorer.score_chain(chain)
            labeled = dict(record)
            labeled["soft_targets"] = scorer_output.trust_vector
            labeled_records.append(labeled)
        except Exception as exc:
            logger.warning("Failed to relabel record: %s", exc)
            # Keep original record with existing labels as fallback
            labeled = dict(record)
            if "labels" in labeled:
                labeled["soft_targets"] = labeled["labels"]
            labeled_records.append(labeled)

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        for rec in labeled_records:
            f.write(json.dumps(rec, default=str) + "\n")

    logger.info(
        "Wrote labeled training data",
        count=len(labeled_records),
        path=str(output_path),
    )
    return output_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    """CLI entry point for freezing teacher artifacts."""
    import argparse
    from autotrust.config import load_spec

    parser = argparse.ArgumentParser(description="Freeze teacher artifacts")
    parser.add_argument("--run-id", default=None, help="Run ID for context")
    parser.add_argument("--teacher-dir", default=None, help="Output directory for teacher artifacts")
    args = parser.parse_args(argv)

    spec = load_spec()
    teacher_dir = Path(args.teacher_dir) if args.teacher_dir else None
    artifacts = freeze_teacher(spec, teacher_dir=teacher_dir, run_id=args.run_id)
    print(f"Teacher artifacts frozen to: {artifacts.prompt_pack_path.parent}")


if __name__ == "__main__":
    main()
