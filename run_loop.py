"""Thin orchestration for the autoresearch loop.

Drives the research loop: loads spec/calibration, starts run, iterates
(agent prompt -> edit train.py -> score -> three-gate eval -> keep/discard),
enforces budget/time limits, and logs everything.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from collections.abc import Callable
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
)
from autotrust.schemas import (
    CalibrationReport,
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


def load_eval_chains() -> list[EmailChain]:
    """Load evaluation chains from eval_set/eval_chains.jsonl."""
    path = Path("eval_set/eval_chains.jsonl")
    if not path.exists():
        logger.warning("No eval chains found at %s", path)
        return []

    chains = []
    for line in path.read_text().strip().split("\n"):
        if line:
            chains.append(EmailChain.model_validate_json(line))
    return chains


def load_gold_chains() -> list[dict[str, float]]:
    """Load gold set consensus labels from gold_set/gold_chains.jsonl."""
    path = Path("gold_set/gold_chains.jsonl")
    if not path.exists():
        logger.warning("No gold chains found at %s", path)
        return []

    chains = []
    for line in path.read_text().strip().split("\n"):
        if line:
            data = json.loads(line)
            chains.append(data.get("consensus_labels", data))
    return chains


def _check_budget(total_cost: float, spec: Any) -> bool:
    """Return True if budget is exceeded."""
    return total_cost >= spec.limits.max_spend_usd


def _check_time_limit(start_time: float, spec: Any) -> bool:
    """Return True if time limit is exceeded."""
    elapsed_minutes = (time.time() - start_time) / 60
    return elapsed_minutes >= spec.limits.experiment_minutes


def _build_agent_prompt(
    program_md: str,
    train_py: str,
    last_results: list[dict],
    consecutive_no_improvement: int,
) -> str:
    """Build the prompt for the research agent."""
    prompt = f"""## Instructions
{program_md}

## Current train.py
```python
{train_py}
```

## Last Experiment Results
{json.dumps(last_results[-3:], indent=2, default=str) if last_results else 'No previous results.'}
"""
    if consecutive_no_improvement >= 3:
        prompt += """
## IMPORTANT: LoRA Fine-Tuning Nudge
You have had 3+ consecutive experiments with no improvement.
Consider using LoRA fine-tuning via TrainingProvider to break through the plateau.
Call self.fine_tune(data_path, trainer) to start a fine-tuning run.
Remember to auto-terminate GPUs when done.
"""
    return prompt


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

    client = anthropic.Anthropic(api_key=api_key)

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

    response = client.messages.create(
        model=spec.providers.judge_secondary.model,  # Use Sonnet for agent
        max_tokens=4096,
        tools=tools,
        messages=[{"role": "user", "content": prompt}],
    )

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
            logger.error("git add failed: %s", result.stderr)
            return
        result = subprocess.run(
            ["git", "commit", "-m", f"experiment {experiment_num}: keep"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            logger.error("git commit failed: %s", result.stderr)
            return
        logger.info("Experiment %d: KEPT (committed train.py)", experiment_num)
    else:
        result = subprocess.run(
            ["git", "checkout", "--", "train.py"], capture_output=True, text=True,
        )
        if result.returncode != 0:
            logger.error("git checkout failed: %s", result.stderr)
        logger.info("Experiment %d: DISCARDED (restored train.py)", experiment_num)


def _log_iteration(ctx: Any, result: ExperimentResult) -> None:
    """Log a single experiment iteration."""
    log_experiment(ctx, result)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run_autoresearch(
    max_experiments: int = 50,
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

    eval_chains = load_eval_chains()
    gold_chains = load_gold_chains()

    has_baseline = False
    prev_best_composite = 0.0
    prev_best_per_axis: dict[str, float] = {}
    consecutive_no_improvement = 0
    total_cost = 0.0
    all_results: list[dict] = []

    start_time = time.time()

    for experiment_num in range(1, max_experiments + 1):
        # Check limits
        if _check_time_limit(start_time, spec):
            logger.info("Time limit reached. Stopping.")
            break
        if _check_budget(total_cost, spec):
            logger.info("Budget limit reached. Stopping.")
            break

        # Dashboard callbacks: stop and pause
        if stop_check and stop_check():
            logger.info("Stop requested via callback. Ending loop.")
            break
        while pause_check and pause_check():
            time.sleep(1)
            # Re-check stop during pause
            if stop_check and stop_check():
                logger.info("Stop requested during pause. Ending loop.")
                break

        if not eval_chains:
            logger.warning("No eval chains available. Stopping.")
            break

        logger.info("--- Experiment %d ---", experiment_num)

        # Read current files
        program_md = Path("program.md").read_text()
        train_py = Path("train.py").read_text()

        # Build agent prompt
        prompt = _build_agent_prompt(
            program_md, train_py, all_results, consecutive_no_improvement
        )

        # --- Call Anthropic Sonnet to propose train.py edits ---
        experiment_cost = 0.0
        try:
            proposed_edit = _call_agent(prompt, spec)
            experiment_cost += 0.01  # estimated per-call cost
        except Exception as exc:
            logger.error("Agent call failed: %s", exc)
            consecutive_no_improvement += 1
            continue

        # Apply proposed edit to train.py
        if proposed_edit and proposed_edit.strip() != train_py.strip():
            Path("train.py").write_text(proposed_edit)
            change_desc = f"Agent edit (experiment {experiment_num})"
        else:
            change_desc = f"No change proposed (experiment {experiment_num})"
            logger.info("Agent proposed no change. Skipping scoring.")
            consecutive_no_improvement += 1
            continue

        # --- Score eval chains using modified train.py ---
        try:
            from train import EmailTrustScorer
            from autotrust.providers import get_provider

            scorer_provider = get_provider("scorer", spec)
            scorer = EmailTrustScorer(provider=scorer_provider, spec=spec)
            outputs = scorer.score_batch(eval_chains)
            experiment_cost += 0.02 * len(eval_chains)  # estimated scoring cost
        except Exception as exc:
            logger.error("Scoring failed: %s", exc)
            # Restore train.py on failure
            Path("train.py").write_text(train_py)
            consecutive_no_improvement += 1
            continue

        # --- Three-gate evaluation ---
        predictions = [o.trust_vector for o in outputs]
        ground_truth = [c.labels for c in eval_chains]
        explanations = [o.explanation for o in outputs]

        # Gate 1: Composite score
        per_axis_metrics = score_predictions(predictions, ground_truth, spec)

        # Compute FP rate for binary axes (phish)
        phish_preds = [1 if p.get("phish", 0) >= 0.5 else 0 for p in predictions]
        phish_truth = [1 if t.get("phish", 0) >= 0.5 else 0 for t in ground_truth]
        fp_count = sum(1 for p, t in zip(phish_preds, phish_truth) if p == 1 and t == 0)
        neg_count = sum(1 for t in phish_truth if t == 0)
        fp_rate = fp_count / neg_count if neg_count > 0 else 0.0

        composite = compute_composite(per_axis_metrics, spec, calibration, fp_rate=fp_rate)
        composite_improved = composite > prev_best_composite

        # Gate 2: Gold-set veto
        if gold_chains:
            gold_ok, gold_deltas = gold_regression_gate(
                predictions, gold_chains, prev_best_per_axis, spec
            )
        else:
            gold_ok = True
            gold_deltas = {}

        # Gate 3: Explanation gate
        expl_quality = explanation_quality(explanations, predictions, spec)
        expl_ok, expl_mode = explanation_gate(expl_quality, spec, has_baseline)

        # Keep/discard decision
        keep = keep_or_discard(composite_improved, gold_ok, expl_ok)

        # --- Git keep/discard ---
        _handle_keep_discard(keep, experiment_num)

        if keep:
            prev_best_composite = composite
            prev_best_per_axis = per_axis_metrics
            has_baseline = True
            consecutive_no_improvement = 0
        else:
            consecutive_no_improvement += 1

        # --- Log experiment ---
        total_cost += experiment_cost
        elapsed = time.time() - start_time

        result = ExperimentResult(
            run_id=run_ctx.run_id,
            change_description=change_desc,
            per_axis_scores=per_axis_metrics,
            composite=composite,
            fp_rate=fp_rate,
            judge_agreement=0.0,
            gold_agreement=sum(gold_deltas.values()) / len(gold_deltas) if gold_deltas else 0.0,
            explanation_quality=expl_quality,
            downweighted_axes=calibration.flagged_axes,
            gate_results={
                "composite": composite_improved,
                "gold": gold_ok,
                "explanation": expl_ok,
            },
            cost=experiment_cost,
            wall_time=elapsed,
        )

        _log_iteration(run_ctx, result)
        all_results.append(result.model_dump())

        logger.info(
            "Experiment %d: composite=%.4f, keep=%s, gates=%s",
            experiment_num, composite, keep, result.gate_results,
        )

    finalize_run(run_ctx)
    logger.info("Autoresearch loop complete. %d experiments run.", len(all_results))


if __name__ == "__main__":
    run_autoresearch()
