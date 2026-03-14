"""Provider registry with abstract base classes and shared retry/logging logic.

Four provider roles:
- GeneratorProvider: local LLM text generation (Ollama)
- ScoringProvider: inference scoring (Hyperbolic)
- JudgeProvider: LLM judging with bias mitigation (Anthropic)
- TrainingProvider: GPU rental and remote training (Hyperbolic Marketplace)
"""

from __future__ import annotations

import functools
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from autotrust.config import Spec

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ProviderError(Exception):
    """Base exception for all provider errors."""


class BudgetExceededError(ProviderError):
    """Raised when spending exceeds budget limit."""


# ---------------------------------------------------------------------------
# Retry decorator
# ---------------------------------------------------------------------------

def _build_transient_errors() -> tuple[type[Exception], ...]:
    """Build tuple of transient exception types, including API-specific ones if available."""
    errors: list[type[Exception]] = [ConnectionError, TimeoutError, OSError]
    try:
        import openai
        errors.extend([openai.RateLimitError, openai.APITimeoutError, openai.APIConnectionError])
    except (ImportError, AttributeError):
        pass
    try:
        import anthropic
        errors.extend([anthropic.RateLimitError, anthropic.InternalServerError, anthropic.APITimeoutError])
    except (ImportError, AttributeError):
        pass
    try:
        import httpx
        errors.append(httpx.HTTPStatusError)
    except (ImportError, AttributeError):
        pass
    return tuple(errors)


TRANSIENT_ERRORS = _build_transient_errors()


def retry_on_error(max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 30.0):
    """Decorator that retries on transient errors with exponential backoff."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries):
                try:
                    return fn(*args, **kwargs)
                except TRANSIENT_ERRORS as exc:
                    last_exc = exc
                    if attempt < max_retries - 1:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        logger.warning(
                            "Retry %d/%d for %s: %s",
                            attempt + 1, max_retries, fn.__name__, exc,
                        )
                        time.sleep(delay)
            raise last_exc  # type: ignore[misc]
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Base provider
# ---------------------------------------------------------------------------

class BaseProvider(ABC):
    """Shared base class with retry logic and structured logging."""

    def _log_call(self, method: str, **kwargs: Any) -> None:
        logger.debug("Provider call: %s.%s", self.__class__.__name__, method, extra=kwargs)

    def _log_result(self, method: str, latency: float, success: bool, **kwargs: Any) -> None:
        logger.debug(
            "Provider result: %s.%s (%.2fs, %s)",
            self.__class__.__name__, method, latency, "ok" if success else "fail",
            extra=kwargs,
        )


# ---------------------------------------------------------------------------
# Abstract provider interfaces
# ---------------------------------------------------------------------------

class GeneratorProvider(BaseProvider):
    """Abstract base for text generation providers (e.g., local Ollama)."""

    @abstractmethod
    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate text from a prompt."""

    @abstractmethod
    def generate_batch(self, prompts: list[str], concurrency: int = 4) -> list[str]:
        """Generate text for multiple prompts."""

    @abstractmethod
    def check_available(self) -> bool:
        """Check if the provider is available (daemon running, model loaded)."""


class ScoringProvider(BaseProvider):
    """Abstract base for scoring/inference providers (e.g., Hyperbolic)."""

    @abstractmethod
    def score(self, prompt: str, **kwargs: Any) -> str:
        """Score a single prompt and return raw response text."""

    @abstractmethod
    def score_batch(self, prompts: list[str], **kwargs: Any) -> list[str]:
        """Score multiple prompts."""


class JudgeProvider(BaseProvider):
    """Abstract base for LLM judges (e.g., Anthropic Claude)."""

    @abstractmethod
    def judge(self, chain: Any, axes: list[str]) -> dict[str, float]:
        """Judge a chain on specified axes, return per-axis scores."""

    @abstractmethod
    def dual_judge(self, chain: Any) -> tuple[dict[str, float], dict[str, float], float]:
        """Primary + secondary judge, return (primary_scores, secondary_scores, agreement)."""


class TrainingProvider(BaseProvider):
    """Abstract base for GPU training providers (e.g., Hyperbolic Marketplace)."""

    @abstractmethod
    def list_gpus(self) -> list[dict[str, Any]]:
        """List available GPU instances."""

    @abstractmethod
    def rent_gpu(self, hours: int, name: str) -> str:
        """Rent a GPU instance, return instance_id."""

    @abstractmethod
    def stop_gpu(self, instance_id: str) -> None:
        """Stop a GPU instance."""

    @abstractmethod
    def get_status(self, instance_id: str) -> dict[str, Any]:
        """Get status of a GPU instance."""

    @abstractmethod
    def run_remote(self, instance_id: str, command: str) -> str:
        """Run a command on a remote GPU instance."""

    @abstractmethod
    def budget_guard(self, max_usd: float) -> Any:
        """Return a context manager that tracks spend and auto-terminates at limit."""

    @abstractmethod
    def yarn_extend_context(self, base_model: str, target_ctx: int, steps: int) -> str:
        """Generate YaRN training config for context extension."""


# ---------------------------------------------------------------------------
# Provider registry / factory
# ---------------------------------------------------------------------------

def get_provider(role: str, spec: Spec) -> BaseProvider:
    """Factory that maps role + spec.providers config to concrete provider classes.

    Roles: 'generator', 'scorer', 'judge_primary', 'judge_secondary', 'trainer'
    """
    import os

    providers_config = spec.providers

    if role == "generator":
        from autotrust.providers.ollama import OllamaGenerator
        return OllamaGenerator(model=providers_config.generator.model)

    elif role == "scorer":
        from autotrust.providers.hyperbolic import HyperbolicScorer
        api_key = os.environ.get("HYPERBOLIC_API_KEY", "")
        return HyperbolicScorer(model=providers_config.scorer.model, api_key=api_key)

    elif role in ("judge_primary", "judge_secondary"):
        from autotrust.providers.anthropic import AnthropicJudge
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        primary_cfg = providers_config.judge_primary
        secondary_cfg = providers_config.judge_secondary
        return AnthropicJudge(
            primary_model=primary_cfg.model,
            secondary_model=secondary_cfg.model,
            api_key=api_key,
        )

    elif role == "trainer":
        from autotrust.providers.hyperbolic import HyperbolicTrainer
        api_key = os.environ.get("HYPERBOLIC_API_KEY", "")
        gpu_type = providers_config.trainer.gpu_type or "H100"
        return HyperbolicTrainer(api_key=api_key, gpu_type=gpu_type)

    else:
        raise ValueError(f"Unknown provider role: '{role}'")
