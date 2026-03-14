# Masubi -- Requirements

## Core Concept

An autonomous research loop (inspired by Karpathy's autoresearch) that iteratively improves an email trust scorer. An AI agent proposes code changes, the system evaluates them against three independent gates, and keeps or discards via git ratcheting.

## Key Requirements

### 1. Three-Layer Architecture

- **Layer 1 (Config):** `spec.yaml` is the single source of truth for axes, weights, providers, limits, thresholds, calibration, and safety rules. `config.py` loads and validates it.
- **Layer 2 (Fixed Platform):** Providers, data pipeline, evaluation engine, observability. Heavily tested, never touched by the agent.
- **Layer 3 (Mutable):** `train.py` is the ONLY file the research agent edits. This constraint makes the ratcheting loop safe.

### 2. Trust Scoring: 10 Axes, Not Binary

Traditional spam filtering is binary. We score 10 dimensions:

| Axis | Type | Metric | Weight |
|------|------|--------|--------|
| phish | binary | F1 | 0.22 |
| truthfulness | continuous | agreement | 0.18 |
| verify_by_search | binary | F1 | 0.00 |
| manipulation | continuous | agreement | 0.13 |
| deceit | continuous | recall | 0.10 |
| vulnerability_risk | continuous | agreement | 0.10 |
| subtle_toxicity | continuous | agreement | 0.08 |
| polarization | continuous | agreement | 0.05 |
| classic_email_metrics | continuous | agreement | 0.04 |
| authority_impersonation | continuous | agreement | 0.10 |

Output: a trust *vector* (per-axis scores) + weighted composite *scalar*.

### 3. Three-Gate Keep/Discard Policy

All three must pass for an experiment to be kept:

1. **Composite improved** -- Kappa-adjusted axis weights + FP penalty
2. **Gold-set veto** -- Raw human labels, no downweighting, ALL axes (including zero-weighted). ANY regression = reject.
3. **Explanation gate** -- `warn_then_gate` mode; blocks after first baseline if explanation quality < 0.5

### 4. Provider Architecture

Four provider roles, each with pluggable backends:

- **Generator:** Ollama local (`dolphin3:latest`) -- uncensored synthetic data generation
- **Scorer:** Hyperbolic (`meta-llama/Llama-3.1-8B-Instruct`) -- fast/cheap inference
- **Judge:** Anthropic (`claude-opus-4-20250514` primary, `claude-sonnet-4-20250514` secondary) -- subtle axis escalation + agent coordination
- **Trainer:** Hyperbolic GPU (H100) -- LoRA fine-tuning when gains plateau

### 5. Data Pipeline

- **Eval set:** 1,000 chains (`eval_set/eval_chains.jsonl`)
- **Gold set:** 200 chains for human annotation (`gold_set/gold_candidates.jsonl`)
- **Training data:** 5,000+ synthetic chains (`synth_data/train.jsonl`)
- Safety filtering: placeholder-only brands in synth data, operational instruction blocking
- Deduplication by content hash

### 6. Kappa-Proportional Downweighting

- Axes with low inter-annotator agreement get downweighted in composite (not in veto)
- `effective_weight = original_weight * min(kappa / min_gold_kappa, 1.0)`
- Lost weight redistributed proportionally among non-downweighted axes

### 7. Structured Explanations

- Scorer outputs `{"trust_vector": {...}, "explanation": {"reasons": [...], "summary": "..."}}`
- Explanation quality = flagged axes referenced in reasons / total flagged axes
- This is gated, not cosmetic -- the agent can't compensate for bad explanations with better scores

### 8. Budget and Time Constraints

- 15 minutes wall time per experiment
- $8 maximum spend per experiment
- Agent nudged toward LoRA fine-tuning after 3 consecutive no-improvement experiments

### 9. Observability

- Structured logging via structlog
- Per-run artifacts in `runs/<run_id>/` (metrics, predictions, config, summary)
- Gradio dashboard for real-time monitoring (composite trend, per-axis radar, gate timeline, code diff)

### 10. Safety

- Synthetic data: placeholder brands only (no real PayPal, Google, etc.)
- Eval data: real brands allowed
- Operational instruction patterns blocked (reverse shell, malware, etc.)
- Agent sandboxed to train.py -- cannot modify evaluation contract

### 11. Orchestration

- `run_loop.py` drives the loop: agent prompt -> edit train.py -> score -> three-gate eval -> git keep/discard
- Uses direct Anthropic tool-use (not Agent SDK) for full control over budget enforcement and git integration
- Dashboard callbacks for stop/pause control

### 12. Setup

- `setup.sh` handles: Python deps (uv), .env creation, Ollama model pull, data generation
- Idempotent -- skips steps already completed
