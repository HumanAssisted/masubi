# Masubi -- Simple Explanation

An AI agent improves an email trust scorer through autonomous experimentation. It edits one file, we score email chains across 10 trust dimensions, and a three-gate policy accepts or reverts each change.

## The Core Bet

Traditional phishing detection is binary and solved (~98% accuracy). The unsolved problem is nuanced trust: is a legitimate-looking email subtly manipulative? Does it exploit authority? Is the recipient being put at risk?

Masubi scores 10 axes (phishing, manipulation, authority impersonation, subtle toxicity, etc.) with a gold-set veto that blocks any single-axis regression, even if the overall score improves. The agent can be creative but can't game the metrics because it can't touch the evaluation contract.

## The Pipeline

Two stages, same loop, same three gates. The agent edits `train.py` in both -- but `train.py` serves a different purpose in each stage.

**Stage 1 -- Prompt Optimization.** The agent improves the *prompts* sent to a large LLM scorer (Qwen3-80B on Hyperbolic). `train.py` contains the prompt construction, thread signal extraction, and JSON parsing logic. No model weights are trained -- the agent is discovering the best way to extract trust signals from a powerful model. This is the "teacher discovery" phase.

**Stage 2 -- Student Model Training.** Once prompt optimization stalls (3 consecutive no-improvement experiments), the system freezes the best Stage 1 prompts as "teacher" artifacts and rewrites `train.py` as a PyTorch training script. Now the agent optimizes a compact student model (50-200M params) that learns to replicate the teacher's scoring without needing API calls. Dense baseline first, then MoE architecture search.

The same three gates apply to both stages:
1. Did the composite score improve?
2. Did any axis regress on the gold set? (if yes, reject regardless)
3. Did the model explain why it flagged each axis?

Every experiment that passes all three gates is git-committed. Every failure is git-reverted. The agent can be creative, but the ratchet only goes forward.

## What's Running

- **One command**: `uv run python run_loop.py --max-experiments 5 --eval-limit 100`
- Dashboard opens automatically, shows live progress
- Auto-transitions from Stage 1 to Stage 2 after 3 consecutive stalls

## What Makes It Different From autoresearch

Same loop shape (edit one file, keep/discard via git). Everything inside is different:

- **10 axes instead of 1 metric** -- can't hide regressions in a weighted average
- **Gold-set veto** -- human-labeled reference set with absolute authority
- **Explanation gate** -- model must say *why* it flagged axes, not just output scores
- **Remote APIs** -- scores via Qwen3-80B on Hyperbolic, not local GPU training
- **Safety by construction** -- agent can't modify the evaluation contract
