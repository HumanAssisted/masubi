# AutoEmailTrust v3.5

Automated email trust scoring research loop with a 3-layer architecture and three-gate keep/discard policy.

## Architecture

**Layer 1 -- Spec/Config:** `spec.yaml` is the single source of truth. `config.py` loads and validates it. `schemas.py` defines all data models.

**Layer 2 -- Fixed Platform:** `providers/` (Ollama, Hyperbolic, Anthropic), `data.py` (data pipeline), `eval.py` (three-gate evaluation), `observe.py` (structured logging).

**Layer 3 -- Mutable Model:** `train.py` is the ONLY file the research agent edits during the loop.

### Three-Gate Keep/Discard Policy

1. **Composite improved** -- Kappa-adjusted axis weights + FP penalty
2. **Gold-set veto** -- Raw human labels, no downweighting, ALL axes (including zero-weighted)
3. **Explanation gate** -- `warn_then_gate` mode; blocks after first baseline if quality < 0.5

## Quick Start

Prerequisites: Python 3.12+, [uv](https://docs.astral.sh/uv/)

```bash
# Install dependencies
uv sync

# Copy env and fill in API keys
cp .env.example .env

# Generate data (placeholder pipelines)
uv run python -m autotrust.data build-eval
uv run python -m autotrust.data build-gold

# Run research loop
uv run python run_loop.py

# Run tests
uv run pytest -v
```

## Configuration

All configuration lives in `spec.yaml`:

- `trust_axes` -- 10 axes with name, type (binary/continuous), metric, weight
- `providers` -- Generator (Ollama), Scorer (Hyperbolic), Judge (Anthropic), Trainer (Hyperbolic GPU)
- `limits` -- Budget ($8) and time (15 min) constraints
- `judge` -- Escalation threshold, disagreement max, min gold Kappa
- `calibration` -- Kappa-proportional downweighting (composite only)
- `explanation` -- Gate mode, flag threshold, quality threshold

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
  config.py            # Typed spec.yaml loader + validation
  schemas.py           # Pydantic data models
  data.py              # Data pipeline (CLI subcommands)
  eval.py              # Three-gate evaluation policy
  observe.py           # Structured logging + run artifacts
  providers/
    __init__.py        # Registry + abstract base classes
    ollama.py          # Local LLM generation
    hyperbolic.py      # Scoring + GPU training
    anthropic.py       # Judge with bias mitigation
train.py               # Mutable scorer (agent edits this)
run_loop.py            # Thin orchestration
program.md             # Agent instruction set
spec.yaml              # Single source of truth
annotation_rubric.md   # Human scoring guidelines
tests/                 # Unit + integration + smoke tests
```

## Future

- TUI/graphing dashboard for experiment tracking
- Full data pipeline implementation (SpamAssassin, Enron, Evol-Instruct)
- LoRA fine-tuning integration
