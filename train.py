"""Baseline EmailTrustScorer -- the ONLY file the research agent may edit.

Produces structured ScorerOutput with trust_vector (dict) and Explanation
(reasons array + summary). NOT CoT extraction -- explicit structured output.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from autotrust.schemas import Explanation, ScorerOutput

if TYPE_CHECKING:
    from autotrust.config import Spec
    from autotrust.providers import ScoringProvider, TrainingProvider
    from autotrust.schemas import EmailChain

logger = logging.getLogger(__name__)


class EmailTrustScorer:
    """Thread-aware email trust scorer with structured explanation output."""

    def __init__(self, provider: ScoringProvider, spec: Spec) -> None:
        self.provider = provider
        self.spec = spec

    def score_chain(self, chain: EmailChain) -> ScorerOutput:
        """Score a single email chain. Returns trust vector + structured explanation."""
        prompt = self._build_prompt(chain)
        raw_response = self.provider.score(prompt)
        return self._parse_response(raw_response)

    def score_batch(self, chains: list[EmailChain]) -> list[ScorerOutput]:
        """Score multiple chains (sequential)."""
        return [self.score_chain(c) for c in chains]

    def _build_prompt(self, chain: EmailChain) -> str:
        """Build a thread-aware scoring prompt.

        Includes thread encoder signals:
        - Reply timing analysis
        - Escalation detection
        - Authority shifts
        - Persuasion progression
        """
        # Build chain text with thread context
        thread_parts = []
        for i, email in enumerate(chain.emails):
            thread_parts.append(
                f"--- Email {i + 1} (depth={email.reply_depth}) ---\n"
                f"From: {email.from_addr}\n"
                f"To: {email.to_addr}\n"
                f"Subject: {email.subject}\n"
                f"Time: {email.timestamp}\n\n"
                f"{email.body}"
            )

        thread_text = "\n\n".join(thread_parts)

        # Thread encoder signals
        signals = self._extract_thread_signals(chain)
        signals_text = "\n".join(f"- {s}" for s in signals) if signals else "None detected"

        # Build axis list
        axes_desc = ", ".join(
            f'"{a.name}" ({a.type}, weight={a.weight})'
            for a in self.spec.trust_axes
        )

        prompt = f"""Analyze this email chain for trust signals across these axes: [{axes_desc}]

THREAD SIGNALS:
{signals_text}

EMAIL CHAIN:
{thread_text}

Respond with a JSON object containing:
1. "trust_vector": a dict mapping each axis name to a float score from 0.0 (safe) to 1.0 (maximum concern)
2. "explanation": an object with:
   - "reasons": a list of axis names or semantic references for axes scoring above 0.5
   - "summary": a one-sentence human-readable summary

Respond ONLY with valid JSON. Example format:
{{"trust_vector": {{"phish": 0.9, ...}}, "explanation": {{"reasons": ["phish", "manipulation"], "summary": "..."}}}}

JSON:"""
        return prompt

    def _extract_thread_signals(self, chain: EmailChain) -> list[str]:
        """Extract thread-aware signals from the email chain."""
        signals = []

        if len(chain.emails) > 1:
            # Reply timing
            for i in range(1, len(chain.emails)):
                prev_time = chain.emails[i - 1].timestamp
                curr_time = chain.emails[i].timestamp
                delta = (curr_time - prev_time).total_seconds()
                if delta < 300:  # < 5 minutes
                    signals.append(f"Rapid reply at email {i + 1} ({delta:.0f}s)")

            # Escalation detection
            depths = [e.reply_depth for e in chain.emails]
            if len(set(depths)) > 1:
                signals.append(f"Thread depth escalation: {depths}")

            # Authority shifts
            senders = [e.from_addr for e in chain.emails]
            if len(set(senders)) > 1:
                signals.append(f"Sender changes in thread: {senders}")

        # Urgency keywords
        all_text = " ".join(e.subject + " " + e.body for e in chain.emails).lower()
        urgency_words = ["urgent", "immediately", "asap", "right now", "deadline"]
        found_urgency = [w for w in urgency_words if w in all_text]
        if found_urgency:
            signals.append(f"Urgency signals: {found_urgency}")

        # Authority claims
        authority_words = ["ceo", "cfo", "director", "manager", "admin", "it department"]
        found_authority = [w for w in authority_words if w in all_text]
        if found_authority:
            signals.append(f"Authority claims: {found_authority}")

        return signals

    def _parse_response(self, raw: str) -> ScorerOutput:
        """Parse LLM response into ScorerOutput."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            import re
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                data = json.loads(match.group())
            else:
                logger.error("Failed to parse response as JSON: %s", raw[:200])
                # Return default scores
                return self._default_output()

        trust_vector = data.get("trust_vector", {})
        explanation_data = data.get("explanation", {})

        # Ensure all axes are present
        for axis in self.spec.trust_axes:
            if axis.name not in trust_vector:
                trust_vector[axis.name] = 0.0

        # Clamp values to [0, 1]
        trust_vector = {
            k: max(0.0, min(1.0, float(v)))
            for k, v in trust_vector.items()
            if k in {a.name for a in self.spec.trust_axes}
        }

        explanation = Explanation(
            reasons=explanation_data.get("reasons", []),
            summary=explanation_data.get("summary", "No summary provided."),
        )

        return ScorerOutput(trust_vector=trust_vector, explanation=explanation)

    def _default_output(self) -> ScorerOutput:
        """Return default output when parsing fails."""
        return ScorerOutput(
            trust_vector={a.name: 0.0 for a in self.spec.trust_axes},
            explanation=Explanation(reasons=[], summary="Failed to parse response."),
        )

    # ---------------------------------------------------------------------------
    # LoRA scaffolding (placeholders)
    # ---------------------------------------------------------------------------

    def fine_tune(self, data_path: str, trainer: TrainingProvider) -> str:
        """Placeholder: LoRA fine-tune via TrainingProvider. Returns checkpoint path."""
        raise NotImplementedError("LoRA fine-tuning not yet implemented")

    def load_fine_tuned(self, checkpoint: str) -> None:
        """Placeholder: Load LoRA checkpoint."""
        raise NotImplementedError("LoRA loading not yet implemented")
