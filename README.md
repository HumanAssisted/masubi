# Masubi

An autonomous research system that iteratively improves an email trust scorer. An AI agent proposes code changes, the system evaluates them against three independent gates, and keeps or discards via git ratcheting. Emails are scored across 10 trust dimensions -- not binary spam/not-spam.

## How It Works

```
                    +-------------------+
                    |   Agent (Opus)    |
                    |  proposes edit to |
                    |     train.py      |
                    +---------+---------+
                              |
                              v
                    +-------------------+
                    |   Score email     |
                    |   chains on 10   |
                    |   trust axes     |
                    +---------+---------+
                              |
                              v
              +---------------+---------------+
              |           Three Gates         |
              |                               |
              |  1. Composite score improved? |
              |  2. No axis regressed on      |
              |     human-verified gold set?  |
              |  3. Explanations cover all    |
              |     flagged axes?             |
              +-------+-----------+-----------+
                      |           |
                 ALL PASS      ANY FAIL
                      |           |
                      v           v
               git commit    git revert
               (keep edit)   (discard)
                      |           |
                      +-----+-----+
                            |
                            v
                   Repeat until budget
                   or time limit hit
```

The agent can only edit one file (`train.py`). Everything else -- the evaluation policy, data pipeline, and scoring spec -- is frozen. The agent can be creative, but it can't game the metrics or weaken the gates.

## Quick Start

Prerequisites: Python 3.12+, [uv](https://docs.astral.sh/uv/)

```bash
# One-shot setup
./setup.sh

# Or manually:
uv sync
cp .env.example .env   # add ANTHROPIC_API_KEY and HYPERBOLIC_API_KEY
uv run python -m autotrust.data build-eval
uv run python -m autotrust.data build-gold
```

### Run It

```bash
# Stage 1: prompt optimization (dashboard opens automatically)
uv run python run_loop.py --max-experiments 5 --eval-limit 100

# Full eval set (slower)
uv run python run_loop.py

# Stage 2: student model training
uv run python run_loop.py --stage train --max-experiments 5

# Skip auto-launching dashboard
uv run python run_loop.py --max-experiments 5 --no-dashboard
```

The dashboard opens in your browser automatically. Stage 1 auto-transitions to Stage 2 after 3 consecutive no-improvement experiments.

### Dashboard Only

```bash
uv run python dashboard.py
```

The dashboard detects CLI-started runs automatically.

### API Keys

Add to `.env`:
- `ANTHROPIC_API_KEY` -- Claude Opus (agent + judge)
- `HYPERBOLIC_API_KEY` -- Qwen3-80B scorer + GPU training

## Architecture

Two stages, same three-gate evaluation:

| Stage | What Happens |
|-------|-------------|
| 1 - Prompt Optimization | Agent (Claude Opus) improves scoring prompts in `train.py`. Scorer calls Qwen3-80B on Hyperbolic. |
| 2 - Student Training | Agent trains a compact model (50-200M params) on Hyperbolic H100s. Dense baseline first, then MoE. |

Five provider roles, all configured in `spec.yaml`:

| Role | Backend | Model |
|------|---------|-------|
| Agent | Anthropic | claude-opus-4-6 |
| Scorer | Hyperbolic | Qwen3-Next-80B-A3B-Instruct |
| Judge | Anthropic | claude-opus-4-6 (primary), claude-sonnet-4-6 (fallback) |
| Generator | Local Ollama | dolphin3 (uncensored, for synth data) |
| Trainer | Hyperbolic GPU | H100 (on-demand, for Stage 2) |

Three layers with strict boundaries:

| Layer | Contents | Who Touches It |
|-------|----------|---------------|
| Spec | `spec.yaml` -- axes, weights, providers, caps | Humans only |
| Platform | eval, data, providers, observability | Humans only, TDD'd |
| Mutable | `train.py` -- the ONE file the agent edits | Agent only |

### Trust Axes

| Axis | Type | Weight |
|------|------|--------|
| phish | binary | 0.22 |
| truthfulness | continuous | 0.18 |
| manipulation | continuous | 0.13 |
| deceit | continuous | 0.10 |
| vulnerability_risk | continuous | 0.10 |
| authority_impersonation | continuous | 0.10 |
| subtle_toxicity | continuous | 0.08 |
| polarization | continuous | 0.05 |
| classic_email_metrics | continuous | 0.04 |
| verify_by_search | binary | 0.00 |

### Three Gates

1. **Composite improved** -- weighted score must go up
2. **Gold-set veto** -- no single axis may regress vs human labels. ANY regression = reject.
3. **Explanation gate** -- model must explain which axes it flagged and why

## Configuration

All configuration lives in `spec.yaml`: trust axes, providers (agent, scorer, judge), budget limits, calibration policy, safety rules, and Stage 2 caps.

## Development

```bash
uv run pytest -v              # Run tests
uv run ruff check .           # Lint
uv run ruff format .          # Format
```
