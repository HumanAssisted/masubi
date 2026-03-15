"""Local inference with escalation for Stage 3 production.

Loads a student model checkpoint and runs trust scoring locally,
selectively escalating to cloud judge when the model's escalate flag triggers.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import structlog
import torch

from autotrust.export import load_pytorch
from autotrust.schemas import (
    Explanation,
    ScorerOutput,
    StudentOutput,
)
from autotrust.student import predict

if TYPE_CHECKING:
    from autotrust.config import Spec
    from autotrust.providers import JudgeProvider

logger = structlog.get_logger()


def student_output_to_scorer_output(student_output: StudentOutput) -> ScorerOutput:
    """Convert StudentOutput to ScorerOutput for compatibility with eval pipeline.

    Args:
        student_output: output from student model prediction

    Returns:
        ScorerOutput with trust_vector and explanation.
    """
    # Build summary from reason tags
    if student_output.reason_tags:
        summary = f"Flagged for: {', '.join(student_output.reason_tags)}"
    else:
        summary = "No significant trust concerns detected."

    if student_output.escalate:
        summary += " [ESCALATE: requires judge review]"

    return ScorerOutput(
        trust_vector=student_output.trust_vector,
        explanation=Explanation(
            reasons=student_output.reason_tags,
            summary=summary,
        ),
    )


def should_escalate(student_output: StudentOutput, spec: Spec) -> bool:
    """Check if the scoring result should be escalated to cloud judge.

    Args:
        student_output: output from student model
        spec: loaded Spec with production config

    Returns:
        True if escalation should occur.
    """
    if spec.production is None or not spec.production.escalate_on_flag:
        return False
    return student_output.escalate


class LocalInference:
    """Load a student model checkpoint and run local trust scoring.

    Supports both DenseStudent and MoEStudent models. No API keys required
    for local-only inference.
    """

    def __init__(self, checkpoint_path: Path):
        """Load model from checkpoint.

        Args:
            checkpoint_path: path to .pt checkpoint file
        """
        self.model, self.config, self.meta = load_pytorch(checkpoint_path)
        self.model.eval()
        self._last_student_output: StudentOutput | None = None

    def score(self, chain) -> ScorerOutput:
        """Score an email chain using the local student model.

        Matches TRD section 4.8 API: score(email_chain) -> ScorerOutput.

        Args:
            chain: EmailChain object with emails to score

        Returns:
            ScorerOutput with trust_vector and explanation.
        """
        from autotrust.config import get_spec
        spec = get_spec()
        axis_names = [a.name for a in spec.trust_axes]
        reason_tag_names = list(axis_names)

        # Concatenate emails from chain into text
        text = "\n".join(
            f"From: {e.from_addr}\nTo: {e.to_addr}\n"
            f"Subject: {e.subject}\n{e.body}"
            for e in chain.emails
        )
        return self.score_text(text, axis_names, reason_tag_names)

    def should_escalate(self, output: ScorerOutput, spec: Spec) -> bool:
        """Check if the scoring result should be escalated to cloud judge.

        Uses the student model's trained escalation head output rather than
        a heuristic threshold. Delegates to the module-level should_escalate()
        using the last StudentOutput from score_text().

        Args:
            output: ScorerOutput from scoring
            spec: loaded Spec with production config

        Returns:
            True if escalation should occur.
        """
        if self._last_student_output is not None:
            return should_escalate(self._last_student_output, spec)
        return False

    def _tokenize_simple(self, text: str) -> torch.Tensor:
        """Simple character-level tokenization for inference.

        Uses a basic encoding scheme. In production, this would use
        the same tokenizer used during training.

        Args:
            text: input text to tokenize

        Returns:
            (1, seq_len) tensor of token IDs
        """
        # Simple byte-level tokenization clamped to vocab_size
        tokens = [
            min(b, self.config.vocab_size - 1)
            for b in text.encode("utf-8")[: self.config.max_seq_len]
        ]
        if not tokens:
            tokens = [0]  # at least one token
        return torch.tensor([tokens], dtype=torch.long)

    def score_text(
        self,
        text: str,
        axis_names: list[str],
        reason_tag_names: list[str],
        threshold: float = 0.5,
    ) -> ScorerOutput:
        """Score text using the local student model.

        Args:
            text: email chain text to score
            axis_names: list of trust axis names matching model output order
            reason_tag_names: list of reason tag names
            threshold: classification threshold

        Returns:
            ScorerOutput with trust_vector and explanation.
        """
        input_ids = self._tokenize_simple(text)
        student_output = predict(
            self.model,
            input_ids,
            axis_names,
            reason_tag_names,
            threshold,
        )
        self._last_student_output = student_output
        return student_output_to_scorer_output(student_output)

    def score_with_fallback(
        self,
        text: str,
        axis_names: list[str],
        reason_tag_names: list[str],
        judge: JudgeProvider | None,
        spec: Spec,
        force_escalate: bool = False,
        threshold: float = 0.5,
    ) -> ScorerOutput:
        """Score locally, escalate to judge if needed.

        Args:
            text: email chain text
            axis_names: trust axis names
            reason_tag_names: reason tag names
            judge: optional judge provider for fallback
            spec: loaded Spec
            force_escalate: if True, always escalate (for testing)
            threshold: classification threshold

        Returns:
            ScorerOutput, potentially enhanced by judge scores.
        """
        input_ids = self._tokenize_simple(text)
        student_output = predict(
            self.model,
            input_ids,
            axis_names,
            reason_tag_names,
            threshold,
        )

        escalate = force_escalate or should_escalate(student_output, spec)

        if escalate and judge is not None:
            logger.info("Escalating to judge")
            subtle_axes = spec.axis_groups.subtle
            judge_scores = judge.judge(text, subtle_axes)

            # Merge judge scores into student output
            merged_vector = dict(student_output.trust_vector)
            merged_vector.update(judge_scores)
            student_output = StudentOutput(
                trust_vector=merged_vector,
                reason_tags=student_output.reason_tags,
                escalate=student_output.escalate,
            )

        return student_output_to_scorer_output(student_output)
