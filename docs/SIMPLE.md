# Masubi -- Simple Explanation

An AI agent improves an email trust scorer through autonomous experimentation. It edits one file, we score email chains across 10 trust dimensions, and a three-gate policy accepts or reverts each change.

## The Core Bet

Traditional phishing detection is binary and solved (~98% accuracy). The unsolved problem is nuanced trust: is a legitimate-looking email subtly manipulative? Does it exploit authority? Is the recipient being put at risk?

Masubi scores 10 axes (phishing, manipulation, authority impersonation, subtle toxicity, etc.) with a gold-set veto that blocks any single-axis regression, even if the overall score improves. The agent can be creative but can't game the metrics because it can't touch the evaluation contract.

## How It Works

1. An AI agent (Claude Opus) proposes changes to `train.py`
2. The modified scorer evaluates email chains across 10 trust axes
3. Three gates decide whether to keep or revert:
   - Did the composite score improve?
   - Did any axis regress on the gold set? (if yes, reject)
   - Did the model explain why it flagged each axis?
4. Repeat

## What's Running

- **One command**: `uv run python run_loop.py --max-experiments 5 --eval-limit 100`
- Dashboard opens automatically, shows live progress
- Stage 1 optimizes LLM prompts, Stage 2 trains a compact model
- Auto-transitions between stages after 3 consecutive stalls

## What Makes It Different From autoresearch

Same loop shape (edit one file, keep/discard via git). Everything inside is different:

- **10 axes instead of 1 metric** -- can't hide regressions in a weighted average
- **Gold-set veto** -- human-labeled reference set with absolute authority
- **Explanation gate** -- model must say *why* it flagged axes, not just output scores
- **Remote APIs** -- scores via Qwen3-80B on Hyperbolic, not local GPU training
- **Safety by construction** -- agent can't modify the evaluation contract
