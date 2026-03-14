# Masubi

Masubi is an autonomous research system designed to iteratively improve an artificial intelligence model that identifies sophisticated email threats. Inspired by the autoresearch framework, the project utilizes a three-layer architecture where an AI agent is permitted to modify only a single file, ensuring a controlled and safe experimental environment. The system evaluates email chains across ten distinct trust dimensions, such as manipulation and authority impersonation, rather than relying on simple binary labels. Every proposed improvement must pass a rigorous three-gate policy, which requires a higher composite score, a veto check against human-verified data, and high-quality structured explanations. By combining local models for synthetic data generation with advanced cloud-based judges, Masubi maintains a balance between cost-effective testing and expert-level oversight. This design prevents the agent from gaming the metrics while ensuring that findings remain grounded in human consensus.

## Architecture

**Layer 1 -- Spec/Config:** `spec.yaml` is the single source of truth. `config.py` loads and validates it. `schemas.py` defines all data models.

**Layer 2 -- Fixed Platform:** `providers/` (Ollama, Hyperbolic, Anthropic), `data.py` (data pipeline), `eval.py` (three-gate evaluation), `observe.py` (structured logging).

**Layer 3 -- Mutable Model:** `train.py` is the ONLY file the research agent edits during the loop.

### Three-Gate Keep/Discard Policy

1. **Composite improved** -- Kappa-adjusted axis weights + false-positive penalty
2. **Gold-set veto** -- Raw human labels, no downweighting, ALL axes including zero-weighted. ANY regression = reject.
3. **Explanation gate** -- Structured reasons must cover flagged axes; blocks after first baseline if quality < 0.5

### Trust Axes

| Axis | Type | Metric | Weight |
|------|------|--------|--------|
| phish | binary | F1 | 0.22 |
| truthfulness | continuous | agreement | 0.18 |
| manipulation | continuous | agreement | 0.13 |
| deceit | continuous | recall | 0.10 |
| vulnerability_risk | continuous | agreement | 0.10 |
| authority_impersonation | continuous | agreement | 0.10 |
| subtle_toxicity | continuous | agreement | 0.08 |
| polarization | continuous | agreement | 0.05 |
| classic_email_metrics | continuous | agreement | 0.04 |
| verify_by_search | binary | F1 | 0.00 |

## Quick Start

Prerequisites: Python 3.12+, [uv](https://docs.astral.sh/uv/)

```bash
# One-shot setup (deps, .env, Ollama model, data generation)
./setup.sh

# Or manually:
uv sync
cp .env.example .env   # then add your API keys
uv run python -m autotrust.data build-eval
uv run python -m autotrust.data build-gold
uv run python -m autotrust.data build-train --count 5000

# Run research loop
uv run python run_loop.py

# Monitor via dashboard (separate terminal)
uv run python dashboard.py
```

### API Keys Required

Add to `.env`:
- `ANTHROPIC_API_KEY` -- for the Claude judge and research agent
- `HYPERBOLIC_API_KEY` -- for the Llama scorer
- `OLLAMA_MODEL=dolphin3:latest` -- for synthetic data generation (optional; falls back to templates)

## Configuration

All configuration lives in `spec.yaml`:

- `trust_axes` -- 10 axes with name, type (binary/continuous), metric, weight
- `providers` -- Generator (Ollama), Scorer (Hyperbolic), Judge (Anthropic), Trainer (Hyperbolic GPU)
- `limits` -- Budget ($8) and time (15 min) constraints per experiment
- `judge` -- Escalation threshold, disagreement max, min gold Kappa
- `calibration` -- Kappa-proportional downweighting (composite only, never veto)
- `explanation` -- Gate mode, flag threshold, quality threshold
- `safety` -- Placeholder-only synth data, operational instruction blocking

## Development

```bash
uv run pytest -v              # Run tests
uv run ruff check .           # Lint
uv run ruff format .          # Format
```

## File Structure

```
autotrust/
  config.py            # Typed spec.yaml loader + Kappa downweighting
  schemas.py           # Pydantic data models
  data.py              # Data pipeline CLI (build-eval, build-gold, build-train, calibrate-judge)
  eval.py              # Three-gate evaluation policy
  observe.py           # Structured logging + run artifacts
  providers/
    ollama.py          # Local LLM generation (dolphin3)
    hyperbolic.py      # Scoring + GPU training (Llama-3.1-8B)
    anthropic.py       # Judge (Claude Opus/Sonnet)
  dashboard/
    charts.py          # Plotly charts (composite trend, per-axis radar, gate timeline)
    data_loader.py     # Loads run artifacts for dashboard display
    git_history.py     # Git diff viewer for code evolution
    log_formatter.py   # Structured log display
    run_manager.py     # Run lifecycle management
train.py               # Mutable scorer (agent edits this)
run_loop.py            # Orchestration loop
dashboard.py           # Gradio dashboard entry point
program.md             # Agent instruction set
spec.yaml              # Single source of truth
annotation_rubric.md   # Human scoring guidelines (10-axis rubric)
setup.sh               # One-shot setup script
eval_set/              # Evaluation data (1,000 chains)
gold_set/              # Gold set for human annotation (200 chains)
synth_data/            # Synthetic training data (5,000+ chains)
runs/                  # Experiment output (auto-created per run)
tests/                 # Unit + integration + smoke tests
```
