"""Thin orchestration for the autoresearch loop.

Drives the research loop: loads spec/calibration, starts run, iterates
(agent prompt -> edit train.py -> score -> three-gate eval -> keep/discard),
enforces budget/time limits, and logs everything.

train.py is the ephemeral working copy that the agent edits each iteration.
starting_train.py is the canonical template -- it is copied to train.py at
the start of a run and is never modified by the loop itself.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
from typing import Any

import structlog

from autotrust.config import get_spec
from autotrust.eval import (
    compute_composite,
    explanation_gate,
    explanation_quality,
    gold_regression_gate,
    keep_or_discard,
    score_predictions,
)
from autotrust.observe import (
    finalize_run,
    log_experiment,
    start_run,
    update_run_status,
)
from autotrust.schemas import (
    CalibrationReport,
    Email,
    EmailChain,
    ExperimentResult,
)

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_calibration() -> CalibrationReport:
    """Load calibration report from gold_set/calibration.json.

    Returns default (perfect Kappa) if file doesn't exist yet.
    """
    cal_path = Path("gold_set/calibration.json")
    if cal_path.exists():
        data = json.loads(cal_path.read_text())
        return CalibrationReport(**data)

    # Default: no downweighting
    spec = get_spec()
    return CalibrationReport(
        per_axis_kappa={a.name: 1.0 for a in spec.trust_axes},
        effective_weights={a.name: a.weight for a in spec.trust_axes},
        flagged_axes=[],
        downweight_amounts={},
    )


def load_eval_chains(limit: int | None = None) -> list[EmailChain]:
    """Load evaluation chains from eval_set/eval_chains.jsonl."""
    path = Path("eval_set/eval_chains.jsonl")
    if not path.exists():
        logger.warning("No eval chains found", path=str(path))
        return []

    chains = []
    for line in path.read_text().strip().split("\n"):
        if line:
            chains.append(EmailChain.model_validate_json(line))
            if limit is not None and len(chains) >= limit:
                break
    return chains


def load_gold_chains() -> list[dict[str, float]]:
    """Load raw gold records from gold_set/gold_chains.jsonl."""
    path = Path("gold_set/gold_chains.jsonl")
    if not path.exists():
        logger.warning("No gold chains found", path=str(path))
        return []

    chains = []
    for line in path.read_text().strip().split("\n"):
        if line:
            chains.append(json.loads(line))
    return chains


def _load_stage1_scorer_class(train_path: Path | None = None):
    """Load EmailTrustScorer from the mutable train.py working copy."""
    path = train_path or Path("train.py")
    if not path.exists():
        fallback = Path("starting_train.py")
        if fallback.exists():
            path = fallback
        else:
            raise ImportError("Could not find train.py or starting_train.py")

    module_name = f"masubi_stage1_{path.stem}_{time.time_ns()}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module spec from {path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)

    scorer_cls = getattr(module, "EmailTrustScorer", None)
    if scorer_cls is None:
        raise ImportError(f"{path} does not define EmailTrustScorer")
    return scorer_cls


def _gold_truth_labels(gold_records: list[dict[str, Any]]) -> list[dict[str, float]]:
    """Extract gold truth labels, preferring consensus labels when present."""
    return [
        record.get("consensus_labels", record.get("labels", record))
        for record in gold_records
    ]


def _gold_chain_models(gold_records: list[dict[str, Any]]) -> list[EmailChain]:
    """Parse raw gold records into EmailChain objects for scoring."""
    return [EmailChain.model_validate(record) for record in gold_records]


def _chain_text(chain: EmailChain) -> str:
    """Convert an EmailChain into plain text for student-model scoring."""
    return "\n".join(
        f"From: {e.from_addr}\nTo: {e.to_addr}\nSubject: {e.subject}\n{e.body}"
        for e in chain.emails
    )


def _artifact_dir(run_ctx: Any, experiment_num: int) -> Path:
    """Return the artifact directory for a specific experiment."""
    artifact_dir = run_ctx.run_dir / "artifacts" / f"exp_{experiment_num:03d}"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return artifact_dir


def _write_run_artifact(
    run_ctx: Any,
    experiment_num: int,
    filename: str,
    content: str,
) -> Path:
    """Persist an experiment artifact under runs/<run_id>/artifacts/."""
    path = _artifact_dir(run_ctx, experiment_num) / filename
    path.write_text(content)
    return path


def _summarize_error(error_text: str, fallback: str = "unknown error") -> str:
    """Return a compact single-line summary from a traceback or error string."""
    lines = [line.strip() for line in error_text.splitlines() if line.strip()]
    if not lines:
        return fallback
    return lines[-1][:300]


def _format_subprocess_output(
    stdout: str | bytes | None,
    stderr: str | bytes | None,
    fallback: str = "train.py exited non-zero",
) -> str:
    """Combine subprocess stdout/stderr into a readable artifact payload."""
    if isinstance(stdout, bytes):
        stdout = stdout.decode(errors="replace")
    if isinstance(stderr, bytes):
        stderr = stderr.decode(errors="replace")

    parts = []
    if stdout and stdout.strip():
        parts.append(f"STDOUT\n{stdout.rstrip()}")
    if stderr and stderr.strip():
        parts.append(f"STDERR\n{stderr.rstrip()}")
    if not parts:
        return fallback
    return "\n\n".join(parts)


class _Stage1ValidationProvider:
    """Deterministic provider used to smoke-test agent-edited Stage 1 scorers."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self._index = 0

    def score(self, prompt: str, **kwargs: Any) -> str:
        if not self._responses:
            raise RuntimeError("No validation responses configured")
        idx = min(self._index, len(self._responses) - 1)
        self._index += 1
        return self._responses[idx]

    def score_batch(self, prompts: list[str], **kwargs: Any) -> list[str]:
        return [self.score(prompt, **kwargs) for prompt in prompts]


def _build_stage1_validation_chain(spec: Any) -> EmailChain:
    """Build a minimal but realistic chain for scorer smoke tests."""
    axis_scores = {axis.name: 0.0 for axis in spec.trust_axes}
    email = Email(
        from_addr="ceo@example.com",
        to_addr="finance@example.com",
        subject="Urgent wire transfer",
        body="Please wire funds immediately and keep this confidential.",
        timestamp=datetime.now(timezone.utc),
        reply_depth=0,
    )
    return EmailChain(
        chain_id="validation-001",
        emails=[email],
        labels=axis_scores,
        trust_vector=axis_scores,
        composite=0.0,
        flags=[],
    )


def _build_stage1_validation_responses(spec: Any) -> list[str]:
    """Representative raw model responses used to test parser robustness."""
    payload = json.dumps(
        {
            "trust_vector": {axis.name: 0.5 for axis in spec.trust_axes},
            "explanation": {
                "reasons": ["phish", "manipulation"],
                "summary": "Validation response.",
            },
        }
    )
    return [
        payload,
        f"Here is the JSON:\n```json\n{payload}\n```",
        f"```json\n{payload}\n```",
    ]


def _validate_stage1_candidate(train_path: Path, spec: Any) -> str | None:
    """Smoke-test an agent-edited Stage 1 scorer before live provider calls."""
    try:
        scorer_cls = _load_stage1_scorer_class(train_path)
        responses = _build_stage1_validation_responses(spec)
        scorer = scorer_cls(provider=_Stage1ValidationProvider(responses), spec=spec)
        chains = [_build_stage1_validation_chain(spec) for _ in responses]
        outputs = scorer.score_batch(chains)
        expected_axes = {axis.name for axis in spec.trust_axes}

        if len(outputs) != len(chains):
            raise ValueError(
                f"score_batch returned {len(outputs)} outputs for {len(chains)} chains"
            )

        for index, output in enumerate(outputs, 1):
            actual_axes = set(output.trust_vector.keys())
            if actual_axes != expected_axes:
                raise ValueError(
                    f"validation output {index} axes mismatch: expected {sorted(expected_axes)}, got {sorted(actual_axes)}"
                )
            if not isinstance(output.explanation.summary, str):
                raise TypeError(f"validation output {index} explanation summary must be a string")
            if not isinstance(output.explanation.reasons, list):
                raise TypeError(f"validation output {index} explanation reasons must be a list")

        return None
    except Exception:
        return traceback.format_exc()


def _capture_candidate_failure(
    run_ctx: Any,
    experiment_num: int,
    candidate_source: str,
    phase: str,
    error_text: str,
) -> tuple[Path, Path]:
    """Persist the candidate train.py plus its failure traceback."""
    candidate_path = _write_run_artifact(run_ctx, experiment_num, "candidate_train.py", candidate_source)
    error_path = _write_run_artifact(run_ctx, experiment_num, f"{phase}_error.txt", error_text)
    return candidate_path, error_path


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for run_loop.py."""
    parser = argparse.ArgumentParser(description="Autoresearch loop")
    parser.add_argument(
        "--stage",
        choices=["prompt", "train"],
        default="prompt",
        help="Stage to run: 'prompt' (Stage 1) or 'train' (Stage 2)",
    )
    parser.add_argument(
        "--max-experiments",
        type=int,
        default=50,
        help="Maximum number of experiments to run",
    )
    parser.add_argument(
        "--eval-limit",
        type=int,
        default=None,
        help="Optional cap on eval chains to score per experiment (useful for demo runs)",
    )
    parser.add_argument(
        "--mock-agent",
        action="store_true",
        help="Skip live agent calls and simulate no-op proposals (useful for transition smoke tests)",
    )
    parser.add_argument(
        "--no-dashboard",
        action="store_true",
        help="Skip launching the Gradio dashboard",
    )
    return parser.parse_args(argv)


def _get_time_limit(spec: Any, stage: str) -> int:
    """Get per-stage time limit in minutes.

    Falls back to experiment_minutes if per-stage limit not set.
    """
    if stage == "train":
        limit = getattr(spec.limits, "stage2_experiment_minutes", None)
        return limit if limit is not None else spec.limits.experiment_minutes
    else:
        limit = getattr(spec.limits, "stage1_experiment_minutes", None)
        return limit if limit is not None else spec.limits.experiment_minutes


def _should_auto_transition(stage: str, consecutive_no_improvement: int) -> bool:
    """Check if auto-transition from Stage 1 to Stage 2 should occur."""
    return stage == "prompt" and consecutive_no_improvement >= 3


def _maybe_auto_transition(
    stage: str,
    consecutive_no_improvement: int,
    spec: Any,
    run_ctx: Any | None = None,
    experiment_num: int | None = None,
) -> tuple[str, int]:
    """Auto-transition Stage 1 -> Stage 2 when the no-improvement streak hits the threshold."""
    if not _should_auto_transition(stage, consecutive_no_improvement):
        return stage, consecutive_no_improvement

    logger.info(
        "Auto-transition trigger reached",
        from_stage=stage,
        to_stage="train",
        no_improvement_streak=consecutive_no_improvement,
        experiment=experiment_num,
    )
    if run_ctx is not None:
        update_run_status(
            run_ctx,
            state="running",
            phase="auto-transition",
            stage=stage,
            experiment_num=experiment_num,
            message="Auto-transitioning to Stage 2 after repeated prompt-stage stalls.",
            details={
                "current_experiment": experiment_num,
                "no_improvement_streak": consecutive_no_improvement,
                "next_stage": "train",
            },
        )

    new_stage = _auto_transition(spec)

    if run_ctx is not None:
        update_run_status(
            run_ctx,
            state="running",
            phase="transition-complete",
            stage=new_stage,
            experiment_num=experiment_num,
            message="Stage 2 is ready. The next experiment will run student-model training.",
            details={
                "current_experiment": experiment_num,
                "next_stage": new_stage,
            },
        )

    return new_stage, 0


def _auto_transition(spec: Any) -> str:
    """Execute auto-transition from Stage 1 to Stage 2.

    1. Freeze teacher artifacts
    2. Archive Stage 1 train.py
    3. Write Stage 2 train.py template
    """
    from autotrust.freeze import freeze_teacher, relabel_training_data
    logger.info("Auto-transitioning to Stage 2: freezing teacher artifacts...")
    artifacts = freeze_teacher(spec)
    logger.info("Teacher artifacts frozen.")

    logger.info("Relabeling training data from frozen teacher...")
    relabel_training_data(artifacts, spec)
    logger.info("Training data relabeled.")

    logger.info("Archiving Stage 1 train.py...")
    _archive_train_py()

    logger.info("Writing Stage 2 train.py template...")
    _write_stage2_train_py_template()

    logger.info("Stage 2 transition complete.")
    return "train"


def _check_budget(total_cost: float, spec: Any) -> bool:
    """Return True if budget is exceeded."""
    return total_cost >= spec.limits.max_spend_usd


def _check_time_limit(start_time: float, spec: Any, time_limit: int | None = None) -> bool:
    """Return True if time limit is exceeded."""
    elapsed_minutes = (time.time() - start_time) / 60
    limit = time_limit if time_limit is not None else spec.limits.experiment_minutes
    return elapsed_minutes >= limit


class ExperimentTimeout(Exception):
    """Raised when a single experiment exceeds its time cap."""


def _check_experiment_timeout(experiment_start: float, spec: Any) -> None:
    """Raise ExperimentTimeout if per-experiment time cap is exceeded."""
    timeout_minutes = spec.limits.per_experiment_timeout_minutes
    elapsed_minutes = (time.time() - experiment_start) / 60
    if elapsed_minutes >= timeout_minutes:
        raise ExperimentTimeout(
            f"Experiment exceeded {timeout_minutes:.0f}m cap ({elapsed_minutes:.1f}m elapsed)"
        )


def _build_agent_prompt(
    program_md: str,
    train_py: str,
    last_results: list[dict],
    consecutive_no_improvement: int,
    stage: str = "prompt",
    spec: Any = None,
) -> str:
    """Build the prompt for the research agent.

    Args:
        program_md: contents of program.md
        train_py: current train.py source
        last_results: recent experiment results
        consecutive_no_improvement: count of consecutive no-improvement experiments
        stage: "prompt" (Stage 1) or "train" (Stage 2)
        spec: loaded Spec (used for Stage 2 constraints)
    """
    prompt = f"""## Instructions
{program_md}

## Current train.py
```python
{train_py}
```

## Last Experiment Results
{json.dumps(last_results[-3:], indent=2, default=str) if last_results else 'No previous results.'}
"""
    prompt += """
## Guardrails
- Keep Stage 1 JSON parsing simple and robust.
- Do not use brittle regex cleanup or regex backreferences in replacement strings.
- Candidate Stage 1 code must handle both plain JSON and code-fenced JSON responses.
"""
    if stage == "train" and spec is not None:
        # Stage 2: include model architecture constraints
        prompt += "\n## Stage 2: Student Model Training Context\n"
        prompt += "You are editing train.py for Stage 2 model training.\n"
        prompt += "train.py is run as a subprocess and must produce a PyTorch checkpoint.\n\n"
        if spec.stage2:
            prompt += f"### Architecture Constraints (from spec.yaml)\n"
            prompt += f"- max_experts: {spec.stage2.max_experts}\n"
            prompt += f"- max_params_m: {spec.stage2.max_params_m}\n"
            prompt += f"- max_top_k: {spec.stage2.max_top_k}\n"
            prompt += f"- dense_baseline_first: {spec.stage2.dense_baseline_first}\n"
            prompt += f"- export_formats: {spec.stage2.export_formats}\n\n"
        prompt += "### Available APIs\n"
        prompt += "- `from autotrust.student import DenseStudent, MoEStudent`\n"
        prompt += "- `from autotrust.export import export_pytorch`\n"
        prompt += "- `from autotrust.schemas import StudentConfig, MoEConfig, CheckpointMeta`\n\n"
        prompt += "### StudentConfig Contract\n"
        prompt += "- `StudentConfig(hidden_size, num_layers, vocab_size, max_seq_len, num_axes, num_reason_tags)`\n"
        prompt += "- Do not invent unsupported kwargs such as `axis_names`.\n"
        prompt += "- Derive `num_axes` and `num_reason_tags` from `spec.trust_axes`.\n\n"
        prompt += "### Output Requirements\n"
        prompt += "train.py must save a checkpoint to `runs/<run_id>/checkpoints/best.pt`\n"
        prompt += "The checkpoint must produce: {trust_vector, reason_tags, escalate}\n"
    elif consecutive_no_improvement >= 3:
        prompt += """
## IMPORTANT: LoRA Fine-Tuning Nudge
You have had 3+ consecutive experiments with no improvement.
Consider using LoRA fine-tuning via TrainingProvider to break through the plateau.
Call self.fine_tune(data_path, trainer) to start a fine-tuning run.
Remember to auto-terminate GPUs when done.
"""
    return prompt


def _score_with_student_model(
    checkpoint_path: Path,
    texts: list[str],
    axis_names: list[str],
) -> list[Any] | None:
    """Score texts using a student model checkpoint.

    Args:
        checkpoint_path: path to the .pt checkpoint
        texts: list of email chain texts to score
        axis_names: trust axis names from spec

    Returns:
        List of ScorerOutput, or None if loading fails.
    """
    try:
        from autotrust.inference import LocalInference
        inference = LocalInference(checkpoint_path)
        reason_tags = list(axis_names)
        outputs = []
        for text in texts:
            output = inference.score_text(text, axis_names, reason_tags)
            outputs.append(output)
        return outputs
    except Exception as exc:
        logger.error("Student model scoring failed", error=str(exc))
        return None


def _archive_train_py() -> None:
    """Archive Stage 1 train.py with a git tag.

    starting_train.py already holds the canonical Stage 1 template, so we
    only need to tag the current state in git for reference.
    """
    # Try to create git tag
    subprocess.run(
        ["git", "tag", "stage1-complete"],
        capture_output=True, text=True,
    )
    logger.info("Tagged current state as stage1-complete")


def _write_stage2_train_py_template() -> None:
    """Write Stage 2 PyTorch training template for train.py."""
    template_path = Path(__file__).with_name("starting_train_stage2.py")
    if not template_path.exists():
        raise FileNotFoundError(f"Missing Stage 2 template at {template_path}")
    Path("train.py").write_text(template_path.read_text())
    logger.info("Wrote Stage 2 train.py template")


def _load_stage2_training_metrics(checkpoint_path: Path) -> dict[str, Any]:
    """Load optional training metrics emitted by the Stage 2 trainer."""
    metrics_path = checkpoint_path.parent / "training_metrics.json"
    if not metrics_path.exists():
        return {}
    try:
        return json.loads(metrics_path.read_text())
    except json.JSONDecodeError:
        logger.warning("Invalid Stage 2 training metrics", path=str(metrics_path))
        return {}


def _run_stage2_iteration(
    experiment_num: int,
    spec: Any,
    program_md: str,
    all_results: list[dict],
    consecutive_no_improvement: int,
    experiment_start: float,
    eval_limit: int | None = None,
    run_ctx: Any | None = None,
    mock_agent: bool = False,
) -> dict | None:
    """Run a single Stage 2 experiment iteration.

    1. Call agent to propose train.py edits
    2. Run train.py as subprocess
    3. Load resulting checkpoint
    4. Score eval chains using student model
    5. Return scoring results dict or None on failure

    Args:
        experiment_num: current experiment number
        spec: loaded Spec
        program_md: program.md contents
        all_results: previous experiment results
        consecutive_no_improvement: no-improvement counter
        experiment_start: time when experiment started

    Returns:
        Dict with 'outputs', 'predictions', 'cost' keys, or None on failure.
    """
    train_py = Path("train.py").read_text()
    candidate_path: Path | None = None

    # Build stage-aware agent prompt
    prompt = _build_agent_prompt(
        program_md, train_py, all_results, consecutive_no_improvement,
        stage="train", spec=spec,
    )

    # Call agent for train.py edits
    logger.info(
        "Calling agent to propose Stage 2 train.py edits...",
        model=spec.providers.agent.model,
    )
    if run_ctx is not None:
        update_run_status(
            run_ctx,
            state="running",
            phase="stage2-calling-agent",
            stage="train",
            experiment_num=experiment_num,
            message=f"Calling agent for Stage 2 experiment {experiment_num}.",
            details={
                "current_experiment": experiment_num,
                "agent_model": spec.providers.agent.model,
            },
        )
    try:
        if mock_agent:
            logger.info("Mock agent enabled; skipping live Stage 2 agent call.")
            proposed_edit = None
        else:
            proposed_edit = _call_agent(prompt, spec)
        experiment_cost = 0.01
        _check_experiment_timeout(experiment_start, spec)
    except ExperimentTimeout as exc:
        logger.warning("Stage 2 experiment timed out during agent call", experiment=experiment_num, error=str(exc))
        if run_ctx is not None:
            update_run_status(
                run_ctx,
                state="running",
                phase="stage2-calling-agent",
                stage="train",
                experiment_num=experiment_num,
                message=f"Stage 2 experiment {experiment_num} timed out during agent call.",
                error=str(exc),
            )
        return None
    except Exception as exc:
        logger.error("Agent call failed in Stage 2", error=str(exc))
        if run_ctx is not None:
            update_run_status(
                run_ctx,
                state="running",
                phase="stage2-calling-agent",
                stage="train",
                experiment_num=experiment_num,
                message=f"Stage 2 experiment {experiment_num} failed during agent call.",
                error=str(exc),
            )
        return None

    # Apply edit
    if proposed_edit and proposed_edit.strip() != train_py.strip():
        if run_ctx is not None:
            candidate_path = _write_run_artifact(
                run_ctx,
                experiment_num,
                "candidate_train.py",
                proposed_edit,
            )
        Path("train.py").write_text(proposed_edit)
        diff_lines = len(proposed_edit.splitlines()) - len(train_py.splitlines())
        logger.info(
            "Stage 2 edit applied",
            lines_delta=f"{diff_lines:+d}",
            new_lines=len(proposed_edit.splitlines()),
            candidate_path=str(candidate_path) if candidate_path else None,
        )
    else:
        logger.info("Agent proposed no change in Stage 2.")
        if run_ctx is not None:
            update_run_status(
                run_ctx,
                state="running",
                phase="stage2-no-change",
                stage="train",
                experiment_num=experiment_num,
                message=f"Stage 2 experiment {experiment_num} proposed no change.",
            )
        return None

    # Run train.py as subprocess
    logger.info("Running train.py as subprocess (Stage 2)...")
    if run_ctx is not None:
        update_run_status(
            run_ctx,
            state="running",
            phase="stage2-running-train",
            stage="train",
            experiment_num=experiment_num,
            message=f"Running Stage 2 trainer for experiment {experiment_num}.",
        )
    timeout_seconds = int(spec.limits.per_experiment_timeout_minutes * 60)
    try:
        result = subprocess.run(
            ["uv", "run", "python", "train.py"],
            capture_output=True, text=True,
            timeout=timeout_seconds,
        )
        if result.returncode != 0:
            error_text = _format_subprocess_output(result.stdout, result.stderr)
            error_summary = _summarize_error(error_text, fallback="train.py exited non-zero")
            error_path = None
            if run_ctx is not None:
                candidate_path, error_path = _capture_candidate_failure(
                    run_ctx,
                    experiment_num,
                    proposed_edit,
                    "stage2_train",
                    error_text,
                )
            logger.error(
                "Stage 2 train.py failed",
                experiment_num=experiment_num,
                error=error_summary,
                candidate_path=str(candidate_path) if candidate_path else None,
                error_path=str(error_path) if error_path else None,
            )
            if run_ctx is not None:
                update_run_status(
                    run_ctx,
                    state="running",
                    phase="stage2-running-train",
                    stage="train",
                    experiment_num=experiment_num,
                    message=(
                        f"Stage 2 trainer failed for experiment {experiment_num}."
                        + (f" Saved artifacts in {candidate_path.parent.relative_to(run_ctx.run_dir)}." if candidate_path else "")
                    ),
                    error=error_summary,
                )
            Path("train.py").write_text(train_py)  # restore
            return None
    except subprocess.TimeoutExpired as exc:
        error_text = _format_subprocess_output(
            exc.stdout,
            exc.stderr,
            fallback=f"Timed out after {timeout_seconds}s",
        )
        error_summary = _summarize_error(error_text, fallback=f"Timed out after {timeout_seconds}s")
        error_path = None
        if run_ctx is not None:
            candidate_path, error_path = _capture_candidate_failure(
                run_ctx,
                experiment_num,
                proposed_edit,
                "stage2_train_timeout",
                error_text,
            )
        logger.warning(
            "Stage 2 train.py timed out",
            timeout_sec=timeout_seconds,
            experiment_num=experiment_num,
            error=error_summary,
            candidate_path=str(candidate_path) if candidate_path else None,
            error_path=str(error_path) if error_path else None,
        )
        if run_ctx is not None:
            update_run_status(
                run_ctx,
                state="running",
                phase="stage2-running-train",
                stage="train",
                experiment_num=experiment_num,
                message=(
                    f"Stage 2 trainer timed out for experiment {experiment_num}."
                    + (f" Saved artifacts in {candidate_path.parent.relative_to(run_ctx.run_dir)}." if candidate_path else "")
                ),
                error=error_summary,
            )
        Path("train.py").write_text(train_py)
        return None
    except Exception as exc:
        error_text = traceback.format_exc()
        error_summary = _summarize_error(error_text, fallback=str(exc))
        error_path = None
        if run_ctx is not None:
            candidate_path, error_path = _capture_candidate_failure(
                run_ctx,
                experiment_num,
                proposed_edit,
                "stage2_train_crash",
                error_text,
            )
        logger.error(
            "Stage 2 subprocess error",
            experiment_num=experiment_num,
            error=error_summary,
            candidate_path=str(candidate_path) if candidate_path else None,
            error_path=str(error_path) if error_path else None,
        )
        if run_ctx is not None:
            update_run_status(
                run_ctx,
                state="running",
                phase="stage2-running-train",
                stage="train",
                experiment_num=experiment_num,
                message=(
                    f"Stage 2 trainer crashed for experiment {experiment_num}."
                    + (f" Saved artifacts in {candidate_path.parent.relative_to(run_ctx.run_dir)}." if candidate_path else "")
                ),
                error=error_summary,
            )
        Path("train.py").write_text(train_py)
        return None

    # Find checkpoint
    checkpoint_path = _find_latest_checkpoint()
    if checkpoint_path is None:
        logger.warning("No checkpoint found after Stage 2 train.py run")
        if run_ctx is not None:
            update_run_status(
                run_ctx,
                state="running",
                phase="stage2-running-train",
                stage="train",
                experiment_num=experiment_num,
                message=f"Stage 2 experiment {experiment_num} produced no checkpoint.",
            )
        Path("train.py").write_text(train_py)
        return None

    # Score eval chains using student model
    eval_chains = load_eval_chains(limit=eval_limit)
    if not eval_chains:
        return None

    if run_ctx is not None:
        update_run_status(
            run_ctx,
            state="running",
            phase="stage2-scoring-eval",
            stage="train",
            experiment_num=experiment_num,
            message=f"Scoring {len(eval_chains)} eval chains with the Stage 2 checkpoint.",
            details={
                "current_experiment": experiment_num,
                "eval_count": len(eval_chains),
            },
        )

    axis_names = [a.name for a in spec.trust_axes]
    texts = [
        "\n".join(f"{e.subject}\n{e.body}" for e in chain.emails)
        for chain in eval_chains
    ]
    outputs = _score_with_student_model(checkpoint_path, texts, axis_names)
    if outputs is None:
        Path("train.py").write_text(train_py)
        return None

    training_metrics = _load_stage2_training_metrics(checkpoint_path)

    return {
        "outputs": outputs,
        "checkpoint_path": checkpoint_path,
        "cost": experiment_cost + 0.02 * len(eval_chains),
        "change_desc": f"Stage 2 model training (experiment {experiment_num})",
        "original_train_py": train_py,
        "training_loss": training_metrics.get("training_loss"),
        "param_count": training_metrics.get("param_count"),
        "expert_utilization": training_metrics.get("expert_utilization"),
    }


def _find_latest_checkpoint() -> Path | None:
    """Find the most recently modified .pt checkpoint in runs/."""
    runs_dir = Path("runs")
    if not runs_dir.exists():
        return None
    checkpoints = list(runs_dir.glob("**/checkpoints/*.pt"))
    if not checkpoints:
        return None
    return max(checkpoints, key=lambda p: p.stat().st_mtime)


def _root_exception(exc: BaseException) -> BaseException:
    """Follow chained exceptions to the deepest available root cause."""
    root = exc
    seen: set[int] = set()
    while True:
        next_exc = getattr(root, "__cause__", None) or getattr(root, "__context__", None)
        if next_exc is None or id(next_exc) in seen:
            return root
        seen.add(id(next_exc))
        root = next_exc


def _format_agent_exception(exc: BaseException) -> str:
    """Render Anthropic/httpx exceptions into a useful single-line diagnostic."""
    parts = [type(exc).__name__]

    message = str(exc).strip()
    if message:
        parts.append(message)

    status_code = getattr(exc, "status_code", None)
    if status_code is not None:
        parts.append(f"status={status_code}")

    request_id = getattr(exc, "request_id", None)
    if request_id:
        parts.append(f"request_id={request_id}")

    request = getattr(exc, "request", None)
    if request is not None:
        method = getattr(request, "method", None)
        url = getattr(request, "url", None)
        if method or url:
            parts.append(f"request={method or '?'} {url or ''}".strip())

    body = getattr(exc, "body", None)
    if body not in (None, ""):
        try:
            body_text = json.dumps(body, sort_keys=True)
        except TypeError:
            body_text = str(body)
        parts.append(f"body={body_text[:240]}")

    root = _root_exception(exc)
    if root is not exc:
        root_message = str(root).strip()
        if root_message:
            parts.append(f"root_cause={type(root).__name__}: {root_message}")
        else:
            parts.append(f"root_cause={type(root).__name__}")

    if type(exc).__name__ == "APIConnectionError":
        parts.append("No HTTP response received from Anthropic; this is a transport/connectivity failure.")

    return " | ".join(parts)


def _call_agent(prompt: str, spec: Any) -> str | None:
    """Call Anthropic Sonnet with tool-use to propose train.py edits.

    Returns the proposed new content for train.py, or None if no edit proposed.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("No ANTHROPIC_API_KEY set. Cannot call agent.")
        return None

    try:
        import anthropic
    except ImportError:
        logger.error("anthropic package not installed.")
        return None

    # Disable SDK-managed retries so we can log clearer retry reasons ourselves.
    client = anthropic.Anthropic(api_key=api_key, max_retries=0)

    # Use tool-use to get structured edits
    tools = [
        {
            "name": "edit_train_py",
            "description": "Replace the contents of train.py with new code.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "new_content": {
                        "type": "string",
                        "description": "The complete new content for train.py",
                    },
                },
                "required": ["new_content"],
            },
        },
    ]

    max_attempts = 3
    base_delay = 0.5

    for attempt in range(1, max_attempts + 1):
        try:
            response = client.messages.create(
                model=spec.providers.agent.model,
                max_tokens=16384,
                tools=tools,
                tool_choice={"type": "tool", "name": "edit_train_py"},
                messages=[{"role": "user", "content": prompt}],
            )
            break
        except anthropic.APIConnectionError as exc:
            error_text = _format_agent_exception(exc)
            if attempt < max_attempts:
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning(
                    "Agent request transient failure",
                    attempt=attempt,
                    max_attempts=max_attempts,
                    retry_in_sec=f"{delay:.1f}",
                    error=error_text,
                )
                time.sleep(delay)
                continue
            raise RuntimeError(error_text) from exc
        except anthropic.APIStatusError as exc:
            raise RuntimeError(_format_agent_exception(exc)) from exc
        except Exception as exc:
            raise RuntimeError(_format_agent_exception(exc)) from exc

    # Extract tool use from response
    for block in response.content:
        if hasattr(block, "type") and block.type == "tool_use":
            if block.name == "edit_train_py":
                return block.input.get("new_content")

    logger.info("Agent did not propose any edits.")
    return None


def _handle_keep_discard(keep: bool, experiment_num: int) -> None:
    """Handle git keep/discard for train.py."""
    if keep:
        result = subprocess.run(
            ["git", "add", "train.py"], capture_output=True, text=True,
        )
        if result.returncode != 0:
            logger.error("git add failed", stderr=result.stderr)
            return
        result = subprocess.run(
            ["git", "commit", "-m", f"experiment {experiment_num}: keep"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            logger.error("git commit failed", stderr=result.stderr)
            return
        logger.info("KEPT (committed train.py)", experiment=experiment_num)
    else:
        result = subprocess.run(
            ["git", "checkout", "--", "train.py"], capture_output=True, text=True,
        )
        if result.returncode != 0:
            logger.error("git checkout failed", stderr=result.stderr)
        logger.info("DISCARDED (restored train.py)", experiment=experiment_num)


def _log_iteration(ctx: Any, result: ExperimentResult) -> None:
    """Log a single experiment iteration."""
    log_experiment(ctx, result)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run_autoresearch(
    max_experiments: int = 50,
    stage: str = "prompt",
    eval_limit: int | None = None,
    mock_agent: bool = False,
    stop_check: Callable[[], bool] | None = None,
    pause_check: Callable[[], bool] | None = None,
) -> None:
    """Run the autoresearch loop.

    1. Load spec, calibration, and data
    2. For each experiment:
       a. Call agent with program.md + train.py + last results
       b. Apply proposed edit to train.py
       c. Score eval chains
       d. Run three-gate evaluation
       e. Keep/discard via git
       f. Log everything
    3. Enforce budget/time limits
    4. Finalize run
    """
    spec = get_spec()
    calibration = load_calibration()
    run_ctx = start_run(spec)
    update_run_status(
        run_ctx,
        state="running",
        phase="loading-data",
        stage=stage,
        message="Loading eval and gold chains.",
        details={
            "max_experiments": max_experiments,
            "budget_usd": spec.limits.max_spend_usd,
            "agent_model": spec.providers.agent.model,
        },
    )

    try:
        # Ensure train.py exists as working copy from the canonical template
        starting = Path("starting_train.py")
        working = Path("train.py")
        if starting.exists() and (not working.exists() or stage == "prompt"):
            shutil.copy(str(starting), str(working))
            logger.info("Copied starting_train.py -> train.py as working copy")

        logger.info("Loading eval chains...")
        eval_chains = load_eval_chains(limit=eval_limit)
        logger.info("Loaded eval chains", count=len(eval_chains))

        logger.info("Loading gold chains...")
        gold_chains = load_gold_chains()
        logger.info("Loaded gold chains", count=len(gold_chains))

        has_baseline = False
        prev_best_composite = 0.0
        prev_best_per_axis: dict[str, float] = {}
        prev_best_gold_per_axis: dict[str, float] = {}
        consecutive_no_improvement = 0
        total_cost = 0.0
        all_results: list[dict] = []

        time_limit = _get_time_limit(spec, stage)
        start_time = time.time()
        logger.info(
            "Starting research loop",
            max_experiments=max_experiments,
            stage=stage,
            budget_usd=spec.limits.max_spend_usd,
            time_limit_min=time_limit,
            run_id=run_ctx.run_id,
        )
        update_run_status(
            run_ctx,
            state="running",
            phase="ready",
            stage=stage,
            message=f"Loaded {len(eval_chains)} eval chains and {len(gold_chains)} gold chains.",
            details={
                "eval_count": len(eval_chains),
                "gold_count": len(gold_chains),
                "max_experiments": max_experiments,
                "budget_usd": spec.limits.max_spend_usd,
                "agent_model": spec.providers.agent.model,
                "spent_usd": total_cost,
            },
        )

        for experiment_num in range(1, max_experiments + 1):
            elapsed_total_min = (time.time() - start_time) / 60

            # Check limits
            if _check_time_limit(start_time, spec, time_limit):
                logger.info("Time limit reached. Stopping.", elapsed_min=f"{elapsed_total_min:.1f}")
                break
            if _check_budget(total_cost, spec):
                logger.info("Budget limit reached. Stopping.", spent_usd=f"{total_cost:.2f}")
                break

            if stop_check and stop_check():
                logger.info("Stop requested via callback. Ending loop.")
                break

            stop_requested_during_pause = False
            while pause_check and pause_check():
                time.sleep(1)
                if stop_check and stop_check():
                    logger.info("Stop requested during pause. Ending loop.")
                    stop_requested_during_pause = True
                    break
            if stop_requested_during_pause:
                break

            if not eval_chains:
                logger.warning("No eval chains available. Stopping.")
                update_run_status(
                    run_ctx,
                    state="running",
                    phase="waiting-for-data",
                    stage=stage,
                    message="No eval chains available; stopping early.",
                    experiment_num=experiment_num,
                )
                break

            logger.info(
                f"=== Experiment {experiment_num}/{max_experiments} ===",
                elapsed_min=f"{elapsed_total_min:.1f}",
                spent_usd=f"${total_cost:.2f}",
                no_improvement_streak=consecutive_no_improvement,
            )

            update_run_status(
                run_ctx,
                state="running",
                phase="experiment-start",
                stage=stage,
                experiment_num=experiment_num,
                message=f"Starting experiment {experiment_num} ({stage}).",
                details={
                    "current_experiment": experiment_num,
                    "max_experiments": max_experiments,
                    "spent_usd": total_cost,
                    "eval_count": len(eval_chains),
                    "gold_count": len(gold_chains),
                },
            )

            experiment_start = time.time()
            training_loss = None
            param_count = None
            expert_utilization = None
            candidate_path: Path | None = None

            # Read current files
            program_md = Path("program.md").read_text()
            train_py = Path("train.py").read_text()

            if stage == "train":
                logger.info("Running Stage 2 iteration...")
                update_run_status(
                    run_ctx,
                    state="running",
                    phase="stage2-train",
                    stage=stage,
                    experiment_num=experiment_num,
                    message=f"Running Stage 2 training for experiment {experiment_num}.",
                )
                stage2_result = _run_stage2_iteration(
                    experiment_num=experiment_num,
                    spec=spec,
                    program_md=program_md,
                    all_results=all_results,
                    consecutive_no_improvement=consecutive_no_improvement,
                    experiment_start=experiment_start,
                    eval_limit=eval_limit,
                    run_ctx=run_ctx,
                    mock_agent=mock_agent,
                )
                if stage2_result is None:
                    update_run_status(
                        run_ctx,
                        state="running",
                        phase="stage2-train",
                        stage=stage,
                        experiment_num=experiment_num,
                        message=f"Stage 2 experiment {experiment_num} produced no checkpoint or scores.",
                    )
                    consecutive_no_improvement += 1
                    stage, consecutive_no_improvement = _maybe_auto_transition(
                        stage, consecutive_no_improvement, spec, run_ctx, experiment_num
                    )
                    time_limit = _get_time_limit(spec, stage)
                    continue
                outputs = stage2_result["outputs"]
                checkpoint_path = stage2_result["checkpoint_path"]
                experiment_cost = stage2_result["cost"]
                change_desc = stage2_result["change_desc"]
                training_loss = stage2_result.get("training_loss")
                param_count = stage2_result.get("param_count")
                expert_utilization = stage2_result.get("expert_utilization")
            else:
                prompt = _build_agent_prompt(
                    program_md, train_py, all_results, consecutive_no_improvement,
                    stage="prompt", spec=spec,
                )

                experiment_cost = 0.0
                logger.info("Calling agent to propose train.py edits...", model=spec.providers.agent.model)
                update_run_status(
                    run_ctx,
                    state="running",
                    phase="calling-agent",
                    stage=stage,
                    experiment_num=experiment_num,
                    message=f"Calling agent for experiment {experiment_num}.",
                    details={
                        "current_experiment": experiment_num,
                        "agent_model": spec.providers.agent.model,
                        "spent_usd": total_cost,
                    },
                )
                try:
                    if mock_agent:
                        logger.info("Mock agent enabled; skipping live Stage 1 agent call.")
                        proposed_edit = None
                    else:
                        proposed_edit = _call_agent(prompt, spec)
                    agent_duration = time.time() - experiment_start
                    experiment_cost += 0.01
                    logger.info("Agent responded", duration_sec=f"{agent_duration:.1f}s")
                    _check_experiment_timeout(experiment_start, spec)
                except ExperimentTimeout as exc:
                    logger.warning("Experiment timed out during agent call", experiment=experiment_num, error=str(exc))
                    update_run_status(
                        run_ctx,
                        state="running",
                        phase="calling-agent",
                        stage=stage,
                        experiment_num=experiment_num,
                        message=f"Experiment {experiment_num} timed out during agent call.",
                        error=str(exc),
                    )
                    consecutive_no_improvement += 1
                    stage, consecutive_no_improvement = _maybe_auto_transition(
                        stage, consecutive_no_improvement, spec, run_ctx, experiment_num
                    )
                    time_limit = _get_time_limit(spec, stage)
                    continue
                except Exception as exc:
                    logger.error("Agent call failed", error=str(exc))
                    update_run_status(
                        run_ctx,
                        state="running",
                        phase="calling-agent",
                        stage=stage,
                        experiment_num=experiment_num,
                        message=f"Experiment {experiment_num} failed during agent call.",
                        error=str(exc),
                    )
                    consecutive_no_improvement += 1
                    stage, consecutive_no_improvement = _maybe_auto_transition(
                        stage, consecutive_no_improvement, spec, run_ctx, experiment_num
                    )
                    time_limit = _get_time_limit(spec, stage)
                    continue

                if proposed_edit and proposed_edit.strip() != train_py.strip():
                    candidate_path = _write_run_artifact(
                        run_ctx,
                        experiment_num,
                        "candidate_train.py",
                        proposed_edit,
                    )
                    Path("train.py").write_text(proposed_edit)
                    diff_lines = len(proposed_edit.splitlines()) - len(train_py.splitlines())
                    change_desc = f"Agent edit (experiment {experiment_num})"
                    logger.info(
                        "Edit applied",
                        lines_delta=f"{diff_lines:+d}",
                        new_lines=len(proposed_edit.splitlines()),
                        candidate_path=str(candidate_path),
                    )
                    update_run_status(
                        run_ctx,
                        state="running",
                        phase="validating-train-py",
                        stage=stage,
                        experiment_num=experiment_num,
                        message=f"Validating candidate train.py for experiment {experiment_num}.",
                        details={
                            "current_experiment": experiment_num,
                            "candidate_path": str(candidate_path.relative_to(run_ctx.run_dir)),
                        },
                    )
                    validation_error = _validate_stage1_candidate(Path("train.py"), spec)
                    if validation_error is not None:
                        candidate_path, error_path = _capture_candidate_failure(
                            run_ctx,
                            experiment_num,
                            proposed_edit,
                            "validation",
                            validation_error,
                        )
                        logger.error(
                            "Candidate train.py validation failed",
                            experiment_num=experiment_num,
                            candidate_path=str(candidate_path),
                            error_path=str(error_path),
                            error=_summarize_error(validation_error),
                        )
                        update_run_status(
                            run_ctx,
                            state="running",
                            phase="validating-train-py",
                            stage=stage,
                            experiment_num=experiment_num,
                            message=(
                                f"Experiment {experiment_num} failed candidate validation. "
                                f"Saved artifacts in {candidate_path.parent.relative_to(run_ctx.run_dir)}."
                            ),
                            error=_summarize_error(validation_error),
                        )
                        Path("train.py").write_text(train_py)
                        consecutive_no_improvement += 1
                        stage, consecutive_no_improvement = _maybe_auto_transition(
                            stage, consecutive_no_improvement, spec, run_ctx, experiment_num
                        )
                        time_limit = _get_time_limit(spec, stage)
                        continue
                else:
                    change_desc = f"No change proposed (experiment {experiment_num})"
                    logger.info("Agent proposed no change. Skipping scoring.")
                    update_run_status(
                        run_ctx,
                        state="running",
                        phase="no-change",
                        stage=stage,
                        experiment_num=experiment_num,
                        message=f"Experiment {experiment_num} proposed no change.",
                    )
                    consecutive_no_improvement += 1
                    stage, consecutive_no_improvement = _maybe_auto_transition(
                        stage, consecutive_no_improvement, spec, run_ctx, experiment_num
                    )
                    time_limit = _get_time_limit(spec, stage)
                    continue
                logger.info("Scoring eval chains...", count=len(eval_chains))
                update_run_status(
                    run_ctx,
                    state="running",
                    phase="scoring-eval",
                    stage=stage,
                    experiment_num=experiment_num,
                    message=f"Scoring {len(eval_chains)} eval chains for experiment {experiment_num}.",
                    details={
                        "current_experiment": experiment_num,
                        "eval_count": len(eval_chains),
                        "spent_usd": total_cost,
                    },
                )
                score_start = time.time()
                try:
                    from autotrust.providers import get_provider

                    EmailTrustScorer = _load_stage1_scorer_class()
                    scorer_provider = get_provider("scorer", spec)
                    scorer = EmailTrustScorer(provider=scorer_provider, spec=spec)
                    outputs = scorer.score_batch(eval_chains)
                    score_duration = time.time() - score_start
                    experiment_cost += 0.02 * len(eval_chains)
                    logger.info("Scoring complete", chains=len(outputs), duration_sec=f"{score_duration:.1f}s")
                    _check_experiment_timeout(experiment_start, spec)
                except ExperimentTimeout as exc:
                    logger.warning("Experiment timed out during scoring", experiment=experiment_num, error=str(exc))
                    error_path = None
                    if candidate_path is not None:
                        _candidate_path, error_path = _capture_candidate_failure(
                            run_ctx,
                            experiment_num,
                            proposed_edit,
                            "scoring_timeout",
                            traceback.format_exc(),
                        )
                    update_run_status(
                        run_ctx,
                        state="running",
                        phase="scoring-eval",
                        stage=stage,
                        experiment_num=experiment_num,
                        message=(
                            f"Experiment {experiment_num} timed out during scoring."
                            + (f" See {error_path.relative_to(run_ctx.run_dir)}." if error_path else "")
                        ),
                        error=str(exc),
                    )
                    Path("train.py").write_text(train_py)
                    consecutive_no_improvement += 1
                    stage, consecutive_no_improvement = _maybe_auto_transition(
                        stage, consecutive_no_improvement, spec, run_ctx, experiment_num
                    )
                    time_limit = _get_time_limit(spec, stage)
                    continue
                except Exception as exc:
                    scoring_error = traceback.format_exc()
                    error_path = None
                    if candidate_path is not None:
                        candidate_path, error_path = _capture_candidate_failure(
                            run_ctx,
                            experiment_num,
                            proposed_edit,
                            "scoring",
                            scoring_error,
                        )
                    logger.error(
                        "Scoring failed",
                        experiment_num=experiment_num,
                        error_type=type(exc).__name__,
                        error=str(exc),
                        candidate_path=str(candidate_path) if candidate_path else None,
                        error_path=str(error_path) if error_path else None,
                    )
                    update_run_status(
                        run_ctx,
                        state="running",
                        phase="scoring-eval",
                        stage=stage,
                        experiment_num=experiment_num,
                        message=(
                            f"Experiment {experiment_num} failed during scoring."
                            + (f" See {error_path.relative_to(run_ctx.run_dir)}." if error_path else "")
                        ),
                        error=_summarize_error(scoring_error),
                    )
                    Path("train.py").write_text(train_py)
                    consecutive_no_improvement += 1
                    stage, consecutive_no_improvement = _maybe_auto_transition(
                        stage, consecutive_no_improvement, spec, run_ctx, experiment_num
                    )
                    time_limit = _get_time_limit(spec, stage)
                    continue

            logger.info("Running three-gate evaluation...")
            update_run_status(
                run_ctx,
                state="running",
                phase="evaluating",
                stage=stage,
                experiment_num=experiment_num,
                message=f"Running gates for experiment {experiment_num}.",
                details={
                    "current_experiment": experiment_num,
                    "eval_count": len(eval_chains),
                    "gold_count": len(gold_chains),
                },
            )
            predictions = [o.trust_vector for o in outputs]
            ground_truth = [c.labels for c in eval_chains]
            explanations = [o.explanation for o in outputs]

            gold_predictions: list[dict[str, float]] = []
            gold_truth = _gold_truth_labels(gold_chains)
            if gold_chains:
                try:
                    if stage == "train":
                        gold_models = _gold_chain_models(gold_chains)
                        gold_texts = [_chain_text(chain) for chain in gold_models]
                        gold_outputs = _score_with_student_model(
                            checkpoint_path, gold_texts, [a.name for a in spec.trust_axes]
                        )
                        if gold_outputs is None:
                            raise RuntimeError("Student model gold scoring returned no outputs")
                    else:
                        gold_outputs = scorer.score_batch(_gold_chain_models(gold_chains))

                    gold_predictions = [o.trust_vector for o in gold_outputs]
                    experiment_cost += 0.02 * len(gold_predictions)
                except Exception as exc:
                    gold_error = traceback.format_exc()
                    error_path = None
                    if stage != "train" and candidate_path is not None:
                        candidate_path, error_path = _capture_candidate_failure(
                            run_ctx,
                            experiment_num,
                            proposed_edit,
                            "gold_scoring",
                            gold_error,
                        )
                    logger.error(
                        "Gold-set scoring failed",
                        experiment_num=experiment_num,
                        error_type=type(exc).__name__,
                        error=str(exc),
                        candidate_path=str(candidate_path) if candidate_path else None,
                        error_path=str(error_path) if error_path else None,
                    )
                    update_run_status(
                        run_ctx,
                        state="running",
                        phase="gold-scoring",
                        stage=stage,
                        experiment_num=experiment_num,
                        message=(
                            f"Experiment {experiment_num} failed during gold scoring."
                            + (f" See {error_path.relative_to(run_ctx.run_dir)}." if error_path else "")
                        ),
                        error=_summarize_error(gold_error),
                    )
                    if stage != "train":
                        Path("train.py").write_text(train_py)
                    consecutive_no_improvement += 1
                    stage, consecutive_no_improvement = _maybe_auto_transition(
                        stage, consecutive_no_improvement, spec, run_ctx, experiment_num
                    )
                    time_limit = _get_time_limit(spec, stage)
                    continue

            per_axis_metrics = score_predictions(predictions, ground_truth, spec)

            phish_preds = [1 if p.get("phish", 0) >= 0.5 else 0 for p in predictions]
            phish_truth = [1 if t.get("phish", 0) >= 0.5 else 0 for t in ground_truth]
            fp_count = sum(1 for p, t in zip(phish_preds, phish_truth) if p == 1 and t == 0)
            neg_count = sum(1 for t in phish_truth if t == 0)
            fp_rate = fp_count / neg_count if neg_count > 0 else 0.0

            composite = compute_composite(per_axis_metrics, spec, calibration, fp_rate=fp_rate)
            composite_improved = composite > prev_best_composite
            logger.info(
                "Gate 1 (composite): %.4f -> %s (prev best: %.4f, fp_rate: %.3f)",
                composite, "PASS" if composite_improved else "FAIL", prev_best_composite, fp_rate,
            )

            if gold_chains:
                gold_per_axis_metrics = score_predictions(gold_predictions, gold_truth, spec)
                gold_ok, gold_deltas = gold_regression_gate(
                    gold_predictions, gold_truth, prev_best_gold_per_axis, spec
                )
                regressed = {k: f"{v:.4f}" for k, v in gold_deltas.items() if v < -1e-9}
                logger.info(
                    "Gate 2 (gold veto): %s%s",
                    "PASS" if gold_ok else "FAIL",
                    f" regressed={regressed}" if regressed else "",
                )
            else:
                gold_per_axis_metrics = {}
                gold_ok = True
                gold_deltas = {}
                logger.info("Gate 2 (gold veto): SKIP (no gold chains)")

            expl_quality = explanation_quality(explanations, predictions, spec)
            expl_ok, expl_mode = explanation_gate(expl_quality, spec, has_baseline)
            logger.info(
                "Gate 3 (explanation): quality=%.3f mode=%s -> %s",
                expl_quality, expl_mode, "PASS" if expl_ok else "FAIL",
            )

            keep = keep_or_discard(composite_improved, gold_ok, expl_ok)
            logger.info("Decision", result="KEEP" if keep else "DISCARD")

            _handle_keep_discard(keep, experiment_num)

            if keep:
                prev_best_composite = composite
                prev_best_per_axis = per_axis_metrics
                if gold_chains:
                    prev_best_gold_per_axis = gold_per_axis_metrics
                has_baseline = True
                consecutive_no_improvement = 0
            else:
                consecutive_no_improvement += 1

            stage, consecutive_no_improvement = _maybe_auto_transition(
                stage, consecutive_no_improvement, spec, run_ctx, experiment_num
            )
            time_limit = _get_time_limit(spec, stage)

            total_cost += experiment_cost
            experiment_elapsed = time.time() - experiment_start
            elapsed = time.time() - start_time

            result = ExperimentResult(
                run_id=run_ctx.run_id,
                change_description=change_desc,
                per_axis_scores=per_axis_metrics,
                composite=composite,
                fp_rate=fp_rate,
                judge_agreement=0.0,
                gold_agreement=(
                    sum(gold_per_axis_metrics.values()) / len(gold_per_axis_metrics)
                    if gold_chains else 0.0
                ),
                explanation_quality=expl_quality,
                downweighted_axes=calibration.flagged_axes,
                gate_results={
                    "composite": composite_improved,
                    "gold": gold_ok,
                    "explanation": expl_ok,
                },
                cost=experiment_cost,
                wall_time=elapsed,
                training_loss=training_loss,
                param_count=param_count,
                expert_utilization=expert_utilization,
            )

            _log_iteration(run_ctx, result)
            all_results.append(result.model_dump(exclude_none=True))
            update_run_status(
                run_ctx,
                state="running",
                phase="experiment-complete",
                stage=stage,
                experiment_num=experiment_num,
                message=f"Experiment {experiment_num} complete: {'KEPT' if keep else 'DISCARDED'} at {composite:.4f}.",
                details={
                    "current_experiment": experiment_num,
                    "latest_composite": composite,
                    "latest_decision": "KEPT" if keep else "DISCARDED",
                    "spent_usd": total_cost,
                },
            )

            logger.info(
                "Experiment %d complete: composite=%.4f %s [%.1fs, $%.2f total, %.1fm elapsed]",
                experiment_num, composite, "KEPT" if keep else "DISCARDED",
                experiment_elapsed, total_cost, elapsed / 60,
            )

        update_run_status(
            run_ctx,
            state="finalizing",
            phase="finalizing",
            stage=stage,
            message="Writing run summary.",
            experiment_num=len(all_results),
            details={
                "current_experiment": len(all_results),
                "spent_usd": total_cost,
            },
        )
        finalize_run(run_ctx)
        logger.info(
            "Research loop complete",
            experiments=len(all_results),
            best_composite=f"{prev_best_composite:.4f}",
            total_cost=f"${total_cost:.2f}",
            total_time=f"{(time.time() - start_time) / 60:.1f}m",
        )
        if mock_agent and not all_results:
            shutil.rmtree(run_ctx.run_dir, ignore_errors=True)
            logger.info("Cleaned up mock-agent run artifacts", run_id=run_ctx.run_id)
    except Exception as exc:
        update_run_status(
            run_ctx,
            state="failed",
            phase="error",
            stage=stage,
            message="Run crashed before completion.",
            error=str(exc),
        )
        raise


def _launch_dashboard(port: int = 7860) -> None:
    """Launch the Gradio dashboard as a separate process and open the browser."""
    import subprocess
    import time
    import urllib.error
    import urllib.request
    import webbrowser

    url = f"http://127.0.0.1:{port}/"

    def _is_ready() -> bool:
        try:
            with urllib.request.urlopen(url, timeout=0.5) as response:
                return 200 <= getattr(response, "status", 200) < 500
        except (urllib.error.URLError, TimeoutError, OSError):
            return False

    if _is_ready():
        webbrowser.open(url)
        logger.info("Dashboard already running", url=url)
        return

    dashboard_path = Path(__file__).with_name("dashboard.py")
    try:
        proc = subprocess.Popen(
            [sys.executable, str(dashboard_path), "--port", str(port)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
        )
    except Exception as exc:
        logger.warning("Dashboard failed to start", error=str(exc))
        return

    deadline = time.time() + 8.0
    while time.time() < deadline:
        if _is_ready():
            webbrowser.open(url)
            logger.info("Dashboard launched", url=url)
            return
        if proc.poll() is not None:
            logger.warning("Dashboard exited before becoming ready", returncode=proc.returncode)
            return
        time.sleep(0.2)

    logger.warning("Dashboard launch did not confirm within 8 seconds.", pid=proc.pid)


if __name__ == "__main__":
    args = _parse_args()

    if not args.no_dashboard:
        _launch_dashboard()

    run_autoresearch(
        max_experiments=args.max_experiments,
        stage=args.stage,
        eval_limit=args.eval_limit,
        mock_agent=args.mock_agent,
    )
