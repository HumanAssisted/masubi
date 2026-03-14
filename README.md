# Masubi

Autonomous research loop for email trust scoring. An AI agent iteratively improves a multi-dimensional trust scorer through constrained experimentation, with a three-gate keep/discard policy that prevents metric gaming.

## Architecture

**Layer 1 -- Spec/Config:** `spec.yaml` is the single source of truth. `config.py` loads and validates it. `schemas.py` defines all data models.

**Layer 2 -- Fixed Platform:** `providers/` (Ollama, Hyperbolic, Anthropic), `data.py` (data pipeline), `eval.py` (three-gate evaluation), `observe.py` (structured logging).

**Layer 3 -- Mutable Model:** `train.py` is the ONLY file the research agent edits during the loop.

### Three-Gate Keep/Discard Policy

1. **Composite improved** -- Kappa-adjusted axis weights + FP penalty
2. **Gold-set veto** -- Raw human labels, no downweighting, ALL axes (including zero-weighted). ANY regression = reject.
3. **Explanation gate** -- `warn_then_gate` mode; blocks after first baseline if quality < 0.5

### Trust Axes

10 dimensions scored per email chain: phish, truthfulness, verify_by_search, manipulation, deceit, vulnerability_risk, subtle_toxicity, polarization, classic_email_metrics, authority_impersonation. Each has its own type (binary/continuous), metric (F1/agreement/recall), and composite weight defined in `spec.yaml`.

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
# Run tests
uv run pytest -v

# Run specific test file
uv run pytest tests/test_composite_metric.py -v

# Lint
uv run ruff check .

# Format
uv run ruff format .
```

## File Structure

```
autotrust/
  __init__.py          # Package init
  config.py            # Typed spec.yaml loader + Kappa downweighting
  schemas.py           # Pydantic data models
  data.py              # Data pipeline CLI (build-eval, build-gold, build-train, calibrate-judge)
  eval.py              # Three-gate evaluation policy
  observe.py           # Structured logging + run artifacts
  providers/
    __init__.py        # Registry + abstract base classes
    ollama.py          # Local LLM generation (dolphin3)
    hyperbolic.py      # Scoring + GPU training (Llama-3.1-8B)
    anthropic.py       # Judge with bias mitigation (Claude Opus/Sonnet)
  dashboard/
    __init__.py        # Dashboard package
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
docs/                  # Design docs and task tracking
```
