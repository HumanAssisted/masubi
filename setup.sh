#!/usr/bin/env bash
# setup.sh — One-shot setup for Masubi
# Usage: ./setup.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

red()   { printf '\033[0;31m%s\033[0m\n' "$*"; }
green() { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow(){ printf '\033[0;33m%s\033[0m\n' "$*"; }

echo "=== Masubi Setup ==="
echo

# -------------------------------------------------------------------
# 1. Python dependencies
# -------------------------------------------------------------------
echo "--- [1/5] Python dependencies ---"
if command -v uv &>/dev/null; then
    uv sync
    green "Dependencies installed via uv."
else
    red "uv not found. Install it: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi
echo

# -------------------------------------------------------------------
# 2. Environment file
# -------------------------------------------------------------------
echo "--- [2/5] Environment file ---"
if [ -f .env ]; then
    # Check if keys are populated
    if grep -qE '^ANTHROPIC_API_KEY=.+' .env && grep -qE '^HYPERBOLIC_API_KEY=.+' .env; then
        green ".env exists and API keys are set."
    else
        yellow ".env exists but API keys are empty. Edit .env and add:"
        grep -E '^(ANTHROPIC_API_KEY|HYPERBOLIC_API_KEY)=' .env | while read -r line; do
            key="${line%%=*}"
            val="${line#*=}"
            [ -z "$val" ] && yellow "  $key=<your-key-here>"
        done
    fi
else
    cp .env.example .env
    yellow ".env created from .env.example. Edit it to add your API keys:"
    yellow "  ANTHROPIC_API_KEY=sk-..."
    yellow "  HYPERBOLIC_API_KEY=..."
fi
echo

# -------------------------------------------------------------------
# 3. Ollama + dolphin3 model
# -------------------------------------------------------------------
echo "--- [3/5] Ollama model (dolphin3:latest) ---"
if command -v ollama &>/dev/null; then
    if ollama list 2>/dev/null | grep -q 'dolphin3'; then
        green "dolphin3:latest already available."
    else
        yellow "Pulling dolphin3:latest (this may take a few minutes)..."
        ollama pull dolphin3:latest
        green "dolphin3:latest pulled."
    fi
else
    yellow "Ollama not installed. Synthetic data generation will use templates instead."
    yellow "Install Ollama (optional): https://ollama.com/download"
fi
echo

# -------------------------------------------------------------------
# 4. Generate datasets
# -------------------------------------------------------------------
echo "--- [4/5] Generating datasets ---"

if [ -s eval_set/eval_chains.jsonl ]; then
    green "eval_set/eval_chains.jsonl exists ($(wc -l < eval_set/eval_chains.jsonl) chains)."
else
    echo "Generating eval set (1000 chains)..."
    uv run python -m autotrust.data build-eval
    green "eval_set/eval_chains.jsonl generated."
fi

if [ -s gold_set/gold_candidates.jsonl ]; then
    green "gold_set/gold_candidates.jsonl exists ($(wc -l < gold_set/gold_candidates.jsonl) chains)."
else
    echo "Generating gold set candidates (200 chains)..."
    uv run python -m autotrust.data build-gold
    green "gold_set/gold_candidates.jsonl generated."
fi

if [ -s synth_data/train.jsonl ]; then
    green "synth_data/train.jsonl exists ($(wc -l < synth_data/train.jsonl) chains)."
else
    echo "Generating training data (5000 chains)..."
    uv run python -m autotrust.data build-train --count 5000
    green "synth_data/train.jsonl generated."
fi
echo

# -------------------------------------------------------------------
# 5. Verify
# -------------------------------------------------------------------
echo "--- [5/5] Verification ---"
ok=true

for f in eval_set/eval_chains.jsonl gold_set/gold_candidates.jsonl synth_data/train.jsonl; do
    if [ -s "$f" ]; then
        green "  $f  ($(wc -l < "$f") lines)"
    else
        red "  $f  MISSING"
        ok=false
    fi
done

if grep -qE '^ANTHROPIC_API_KEY=$' .env 2>/dev/null || grep -qE '^HYPERBOLIC_API_KEY=$' .env 2>/dev/null; then
    yellow "  .env has empty API keys — fill them in before running the loop."
    ok=false
fi

echo
if [ "$ok" = true ]; then
    green "Setup complete! Run the research loop with:"
    echo "  uv run python run_loop.py"
    echo
    echo "Optional: launch the dashboard in another terminal:"
    echo "  uv run python dashboard.py"
else
    yellow "Setup mostly done — see warnings above."
fi
