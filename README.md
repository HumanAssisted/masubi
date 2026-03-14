# Masubi

Masubi is an autonomous research system designed to iteratively improve an artificial intelligence model that identifies sophisticated email threats. Inspired by the autoresearch framework, the project utilizes a three-layer architecture where an AI agent is permitted to modify only a single file, ensuring a controlled and safe experimental environment. The system evaluates email chains across ten distinct trust dimensions, such as manipulation and authority impersonation, rather than relying on simple binary labels. Every proposed improvement must pass a rigorous three-gate policy, which requires a higher composite score, a veto check against human-verified data, and high-quality structured explanations. By combining local models for synthetic data generation with advanced cloud-based judges, Masubi maintains a balance between cost-effective testing and expert-level oversight. This design prevents the agent from gaming the metrics while ensuring that findings remain grounded in human consensus.

## How It Works

```
                    +-------------------+
                    |   Agent (Sonnet)  |
                    |  proposes edit to |
                    |     train.py      |
                    +---------+---------+
                              |
                              v
                    +-------------------+
                    |   Score 1,000     |
                    |   email chains    |
                    |   (10 trust axes) |
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

The agent can only edit one file (`train.py`). Everything else -- the evaluation policy, data pipeline, and scoring spec -- is frozen. This makes the loop safe to run unattended: the agent can be creative, but it can't game the metrics or weaken the gates.

## Architecture

Masubi runs a 4-stage pipeline:

| Stage | Name | What Happens |
|-------|------|-------------|
| 0 | Spec/Rubric | Frozen config (`spec.yaml`) and human annotation rubric |
| 1 | Prompt Optimization | Agent iterates on `train.py` prompts to maximize composite score |
| 2 | Student Model Training | Dense baseline then MoE architecture search (50-200M params) |
| 3 | Local Inference | Deploy student checkpoint locally with cloud judge fallback |

**Layer 1 -- Spec/Config:** `spec.yaml` is the single source of truth. `config.py` loads and validates it. `schemas.py` defines all data models (including `StudentConfig`, `MoEConfig`, `CheckpointMeta`).

**Layer 2 -- Fixed Platform:** `providers/` (Ollama, Hyperbolic, Anthropic), `data.py` (data pipeline), `eval.py` (three-gate evaluation), `observe.py` (structured logging), `freeze.py` (teacher artifact extraction), `export.py` (checkpoint export), `inference.py` (local scoring).

**Layer 3 -- Mutable Model:** `train.py` is the ONLY file the research agent edits during the loop. In Stage 1 it contains prompts; in Stage 2 it contains PyTorch model code.

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

Prerequisites: Python 3.12+, [uv](https://docs.astral.sh/uv/), PyTorch 2.0+

```bash
# One-shot setup (deps, .env, Ollama model, data generation)
./setup.sh

# Or manually:
uv sync
cp .env.example .env   # then add your API keys
uv run python -m autotrust.data build-eval
uv run python -m autotrust.data build-gold
uv run python -m autotrust.data build-train --count 5000
```

### Stage 1: Prompt Optimization

```bash
uv run python run_loop.py
```

The agent iterates on `train.py` prompts. After 3 consecutive no-improvement experiments, the system auto-transitions to Stage 2.

### Stage 2: Model Training (after Stage 1 completes)

```bash
# Auto-transition happens automatically, or start directly:
uv run python run_loop.py --stage train
```

Stage 2 freezes teacher artifacts from the best Stage 1 result, then trains a compact student model (50-200M params). Architecture search follows: dense baseline first, then MoE if gains stall. See `spec.yaml` for caps (max_experts, max_params_m, max_top_k).

### Export Model

```bash
# Export best checkpoint as PyTorch
uv run python -m autotrust.export --checkpoint runs/<run_id>/best.pt --format pytorch

# Export as GGUF (requires: uv sync --extra export)
uv run python -m autotrust.export --checkpoint runs/<run_id>/best.pt --format gguf
```

### Monitor

```bash
# Dashboard (separate terminal)
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
- `limits` -- Budget ($8) and per-stage time constraints (Stage 1: 15 min, Stage 2: 10 min)
- `judge` -- Escalation threshold, disagreement max, min gold Kappa
- `calibration` -- Kappa-proportional downweighting (composite only, never veto)
- `explanation` -- Gate mode, flag threshold, quality threshold
- `safety` -- Placeholder-only synth data, operational instruction blocking
- `stage2` -- Dense baseline first, MoE caps (max_experts, max_params_m, max_top_k), export formats
- `production` -- Judge fallback enabled, escalate on flag

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
  schemas.py           # Pydantic data models (including StudentConfig, MoEConfig, CheckpointMeta)
  data.py              # Data pipeline CLI (build-eval, build-gold, build-train, calibrate-judge)
  eval.py              # Three-gate evaluation policy
  observe.py           # Structured logging + run artifacts
  student.py           # Dense and MoE student models (PyTorch nn.Module)
  freeze.py            # Teacher artifact extraction from best Stage 1 commit
  export.py            # Checkpoint export/load (PyTorch, GGUF)
  inference.py         # Local inference with cloud judge escalation fallback
  providers/
    ollama.py          # Local LLM generation (dolphin3)
    hyperbolic.py      # Scoring + GPU training (Llama-3.1-8B)
    anthropic.py       # Judge (Claude Opus/Sonnet)
  dashboard/
    charts.py          # Plotly charts (composite trend, per-axis radar, gate timeline, training loss)
    data_loader.py     # Loads run artifacts for dashboard display
    git_history.py     # Git diff viewer for code evolution
    log_formatter.py   # Structured log display
    run_manager.py     # Run lifecycle management
train.py               # Mutable file (Stage 1: prompts, Stage 2: PyTorch model code)
run_loop.py            # Orchestration loop (--stage prompt|train, auto-transition)
dashboard.py           # Gradio dashboard entry point
program.md             # Agent instruction set (Stage 1 + Stage 2)
spec.yaml              # Single source of truth
annotation_rubric.md   # Human scoring guidelines (10-axis rubric)
setup.sh               # One-shot setup script
teacher/               # Frozen Stage 1 outputs (inputs to Stage 2, auto-created)
eval_set/              # Evaluation data (1,000 chains)
gold_set/              # Gold set for human annotation (200 chains)
synth_data/            # Synthetic training data (5,000+ chains)
runs/                  # Experiment output (auto-created per run)
tests/                 # Unit + integration + smoke tests
```
