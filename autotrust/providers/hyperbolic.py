"""Hyperbolic providers -- ScoringProvider for inference, TrainingProvider for GPU rental."""

from __future__ import annotations

from typing import Any

import structlog

from autotrust.providers import (
    ScoringProvider,
    TrainingProvider,
    BudgetExceededError,
    retry_on_error,
)

logger = structlog.get_logger()


class HyperbolicScorer(ScoringProvider):
    """Score emails via Hyperbolic's OpenAI-compatible API."""

    def __init__(self, model: str, api_key: str) -> None:
        self.model = model
        self.api_key = api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                base_url="https://api.hyperbolic.xyz/v1",
                api_key=self.api_key,
            )
        return self._client

    @retry_on_error(max_retries=3, base_delay=1.0)
    def score(self, prompt: str, **kwargs: Any) -> str:
        """Score a single prompt and return raw response text."""
        self._log_call("score", prompt_len=len(prompt))
        client = self._get_client()
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            **kwargs,
        )
        return response.choices[0].message.content or ""

    def score_batch(self, prompts: list[str], **kwargs: Any) -> list[str]:
        """Score multiple prompts (sequential for now)."""
        return [self.score(p, **kwargs) for p in prompts]


class BudgetGuard:
    """Context manager that tracks spend and auto-terminates GPUs at budget limit."""

    def __init__(self, max_usd: float, trainer: HyperbolicTrainer) -> None:
        self.max_usd = max_usd
        self.trainer = trainer
        self.total_spent = 0.0
        self.active_instances: list[str] = []

    def __enter__(self) -> BudgetGuard:
        self.total_spent = 0.0
        return self

    def track_spend(self, amount: float) -> None:
        """Record spending and check budget."""
        self.total_spent += amount
        if self.total_spent >= self.max_usd:
            logger.warning("Budget exceeded: $%.2f >= $%.2f", self.total_spent, self.max_usd)
            for instance_id in self.active_instances:
                try:
                    self.trainer.stop_gpu(instance_id)
                except Exception as exc:
                    logger.error("Failed to stop instance %s: %s", instance_id, exc)
            raise BudgetExceededError(
                f"Budget exceeded: ${self.total_spent:.2f} >= ${self.max_usd:.2f}"
            )

    def register_instance(self, instance_id: str) -> None:
        """Track an active GPU instance."""
        self.active_instances.append(instance_id)

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # Auto-stop all active instances on exit (normal or exceptional)
        for instance_id in self.active_instances:
            try:
                self.trainer.stop_gpu(instance_id)
                logger.info("Stopped instance %s on exit", instance_id)
            except Exception as exc:
                logger.error("Failed to stop instance %s on exit: %s", instance_id, exc)
        logger.info("BudgetGuard: total spent $%.2f / $%.2f", self.total_spent, self.max_usd)
        return None


class HyperbolicTrainer(TrainingProvider):
    """Manage GPU training via Hyperbolic Marketplace API."""

    BASE_URL = "https://api.hyperbolic.xyz/v1/marketplace"

    def __init__(self, api_key: str, gpu_type: str) -> None:
        self.api_key = api_key
        self.gpu_type = gpu_type
        self._client = None

    def _get_client(self):
        if self._client is None:
            import httpx
            self._client = httpx.Client(
                base_url=self.BASE_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=30.0,
            )
        return self._client

    @retry_on_error(max_retries=3, base_delay=1.0)
    def list_gpus(self) -> list[dict[str, Any]]:
        """List available GPU instances."""
        self._log_call("list_gpus")
        client = self._get_client()
        resp = client.get("/gpus")
        resp.raise_for_status()
        return resp.json()

    @retry_on_error(max_retries=3, base_delay=1.0)
    def rent_gpu(self, hours: int, name: str) -> str:
        """Rent a GPU instance, return instance_id."""
        self._log_call("rent_gpu", hours=hours, name=name)
        client = self._get_client()
        resp = client.post("/instances", json={
            "gpu_type": self.gpu_type,
            "hours": hours,
            "name": name,
        })
        resp.raise_for_status()
        return resp.json()["instance_id"]

    @retry_on_error(max_retries=3, base_delay=1.0)
    def stop_gpu(self, instance_id: str) -> None:
        """Stop a GPU instance."""
        self._log_call("stop_gpu", instance_id=instance_id)
        client = self._get_client()
        resp = client.post(f"/instances/{instance_id}/stop")
        resp.raise_for_status()

    @retry_on_error(max_retries=3, base_delay=1.0)
    def get_status(self, instance_id: str) -> dict[str, Any]:
        """Get status of a GPU instance."""
        self._log_call("get_status", instance_id=instance_id)
        client = self._get_client()
        resp = client.get(f"/instances/{instance_id}")
        resp.raise_for_status()
        return resp.json()

    @retry_on_error(max_retries=3, base_delay=1.0)
    def run_remote(self, instance_id: str, command: str) -> str:
        """Run a command on a remote GPU instance."""
        self._log_call("run_remote", instance_id=instance_id, command=command)
        client = self._get_client()
        resp = client.post(f"/instances/{instance_id}/exec", json={"command": command})
        resp.raise_for_status()
        return resp.json().get("output", "")

    def budget_guard(self, max_usd: float) -> BudgetGuard:
        """Return a context manager that tracks spend and auto-terminates at limit."""
        return BudgetGuard(max_usd=max_usd, trainer=self)

    def yarn_extend_context(self, base_model: str, target_ctx: int, steps: int) -> str:
        """Generate YaRN training config for context extension."""
        config = {
            "base_model": base_model,
            "target_context_length": target_ctx,
            "training_steps": steps,
            "method": "yarn",
            "gpu_type": self.gpu_type,
        }
        import json
        return json.dumps(config, indent=2)
