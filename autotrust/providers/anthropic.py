"""AnthropicJudge -- JudgeProvider for LLM-based trust scoring with bias mitigation."""

from __future__ import annotations

import json
import random
from typing import Any

import structlog

from autotrust.providers import JudgeProvider, retry_on_error

logger = structlog.get_logger()


class AnthropicJudge(JudgeProvider):
    """Judge email chains using Claude (primary + secondary) with bias mitigation."""

    def __init__(self, primary_model: str, secondary_model: str, api_key: str) -> None:
        self.primary_model = primary_model
        self.secondary_model = secondary_model
        self.api_key = api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def _build_judge_prompt(self, chain: Any, axes: list[str]) -> str:
        """Build a bias-mitigated judge prompt.

        - Randomize axis presentation order
        - Normalize response format (fixed-length JSON)
        - Request per-axis float scores in [0, 1]
        """
        shuffled_axes = list(axes)
        random.shuffle(shuffled_axes)

        # Build chain text
        if hasattr(chain, "emails"):
            chain_text = "\n---\n".join(
                f"From: {e.from_addr}\nTo: {e.to_addr}\nSubject: {e.subject}\n\n{e.body}"
                for e in chain.emails
            )
        else:
            chain_text = str(chain)

        axes_list = ", ".join(f'"{a}"' for a in shuffled_axes)

        prompt = f"""Evaluate the following email chain on these trust axes: [{axes_list}]

For each axis, provide a score from 0.0 to 1.0 where:
- 0.0 = no concern (fully trustworthy on this axis)
- 1.0 = maximum concern (highly untrustworthy on this axis)

Respond ONLY with a JSON object mapping axis name to float score. Example:
{{"phish": 0.1, "manipulation": 0.7}}

EMAIL CHAIN:
{chain_text}

JSON scores:"""
        return prompt

    @retry_on_error(max_retries=3, base_delay=1.0)
    def _judge_with_model(self, chain: Any, axes: list[str], model: str) -> dict[str, float]:
        """Judge a chain on specified axes using a given model.

        Shared implementation for both primary and secondary judge calls.
        """
        self._log_call("_judge_with_model", axes=axes, model=model)
        prompt = self._build_judge_prompt(chain, axes)
        client = self._get_client()

        response = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text
        scores = json.loads(text)

        # Normalize: ensure all requested axes are present with float values
        result = {}
        for axis in axes:
            val = scores.get(axis, 0.0)
            result[axis] = max(0.0, min(1.0, float(val)))
        return result

    def judge(self, chain: Any, axes: list[str]) -> dict[str, float]:
        """Judge a chain on specified axes using the primary model."""
        return self._judge_with_model(chain, axes, self.primary_model)

    def dual_judge(self, chain: Any, axes: list[str] | None = None) -> tuple[dict[str, float], dict[str, float], float]:
        """Judge with both primary and secondary models, compute agreement.

        Args:
            chain: The email chain to judge.
            axes: Axis names to judge on. If None, uses all axes from spec.

        Returns: (primary_scores, secondary_scores, agreement)
        Agreement = 1.0 - mean(|primary - secondary|) across axes.
        """
        if axes is None:
            from autotrust.config import get_spec
            axes = [a.name for a in get_spec().trust_axes]

        primary_scores = self._judge_with_model(chain, axes, self.primary_model)
        secondary_scores = self._judge_with_model(chain, axes, self.secondary_model)

        # Agreement: 1.0 - mean absolute difference
        diffs = [abs(primary_scores[a] - secondary_scores[a]) for a in axes]
        agreement = 1.0 - (sum(diffs) / len(diffs)) if diffs else 1.0

        return primary_scores, secondary_scores, agreement
