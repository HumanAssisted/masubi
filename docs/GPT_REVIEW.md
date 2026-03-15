# GPT Review: Masubi Sanity, DRYness, Architecture, and ML/PyTorch Assessment

Review date: 2026-03-14

Repository reviewed: `~/personal/musubi`

This file is the deferred review. The immediate execution list is in `docs/10min.md`.

## Bottom Line

Masubi has the right fixed-platform shape, and the 2026-03-14 TDD pass moved the repo materially closer to a real runnable baseline. The project still does not need a rewrite. It needs continued integration cleanup and a few final throughput/observability improvements.

## Status Update After The 10-Minute Build Pass

Fixed in this pass:

- Stage 1 now evaluates the mutable `train.py` working copy.
- Gold scoring is separate from eval scoring and tracks its own baseline.
- Stage 2 reason tags now use raw axis names for Gate 3 compatibility.
- Auto-transition now relabels synth training data before Stage 2.
- Stage 2 now has a real dense-baseline trainer plus `training_loss` / `param_count` logging.

## Remaining High-Value Work

1. Add a demo-friendly eval limiter and better timing visibility.

The loop is more correct now than it was, but 1,000-row eval scoring is still a lot for a short demo budget. `--eval-limit` plus timing fields would make the dashboard and live runs much easier to reason about.

2. Start logging richer per-experiment artifacts.

`training_loss` and `param_count` now flow through, but predictions, phase timings, and gold per-axis deltas would make the dashboard much more diagnostic.

3. Keep dense-baseline work ahead of MoE work.

The dense baseline now exists and trains, so the next ML question is whether it is good enough before any MoE search complexity is added.

4. Continue reducing duplicated sources of truth.

The biggest remaining DRY issue is still state-model duplication across docs, templates, and stage-specific behaviors.

## High-Value Work That Can Wait Until After The Loop Runs

1. Strengthen the new dense-baseline trainer.

The repo now has a real dense-baseline trainer, but it is intentionally minimal. The next step is improving training quality, not just plumbing.

2. Enforce Stage 2 limits in the live path.

`check_param_budget(...)` is now exercised by the dense baseline. `validate_moe_config(...)` still needs to be enforced once MoE search is live.

3. Remove the most important duplication.

The Stage 2 template is duplicated between `run_loop.py` and the generated `train.py` shape. Axis count and reason-tag count are also hardcoded rather than derived from `spec.yaml`.

4. Unify escalation semantics.

One path uses the explicit escalate head. Another reconstructs escalation heuristically from axis scores. Pick one contract.

5. Decide whether synthetic data is template-only or provider-backed.

`build_train(...)` detects the generator provider, but `_generate_synth_chain(...)` ignores it and always uses built-in templates.

## Architecture Assessment

### Strong

- `spec.yaml` is the right source of truth for trust axes and platform constraints.
- `autotrust/eval.py` is correctly positioned as a frozen evaluator.
- `schemas.py` centralizes the important typed contracts.
- The provider split and observability split are reasonable for this problem.

### Weak

The repo currently has multiple competing definitions of "what stage the system is in":

- Stage 1 mutable file: `train.py`
- Stage 1 executed scorer: `starting_train.py`
- Stage 2 auto-generated template: emitted from `run_loop.py`
- teacher freeze/relabel path: partly tied to git history, partly tied to `starting_train.py`

That state-model duplication is the real architecture problem.

## DRYness Assessment

The repo is mostly DRY in the evaluator and config layers. The biggest duplication problems are not random copy-paste; they are duplicated sources of truth.

Highest-impact DRY issues:

1. Stage 1 has two scorer sources: `starting_train.py` and `train.py`.
2. Stage 2 template logic lives inside `run_loop.py` instead of in a shared module or seed file.
3. Axis and reason-tag counts are hardcoded in multiple places.
4. Explanation/reason-tag naming is split between inference and evaluation.

## ML / PyTorch Assessment

### Dense Student

The dense student is a credible scaffold:

- transformer encoder backbone
- separate trust, reason, and escalation heads
- export/load path
- local inference path

What is still missing:

- a stronger training loop
- real teacher distillation during handoff
- tokenizer parity between training and local inference
- calibration and objective shaping beyond the current stub

### MoE

The MoE direction is fine as a later optimization, but it should stay later.

Reasons to postpone:

- the dense baseline is not established yet
- capacity and routing validation are still light
- nested Python dispatch loops are not iteration-speed friendly
- hard caps are not enforced in the main loop

### PyTorch Note

The recurring `TransformerEncoder` nested-tensor warning is a performance smell, not a correctness bug. It is worth cleaning up once the baseline loop is real.

## Documentation Assessment

The docs still describe a cleaner and more coherent status than the current code actually provides. The most helpful posture is:

- `docs/10min.md`: live blocker checklist
- `README.md`: only claim workflows that run today
- historical redesign docs: keep as intent, not status

## Recommendation

Priority order:

1. Add `--eval-limit` and timing visibility for live demos.
2. Log predictions and gold per-axis deltas for the dashboard.
3. Improve the dense baseline before adding MoE search complexity.
4. Clean up duplicated state descriptions across docs and templates.
5. Then invest in MoE, GGUF, tokenizer parity, and provider-backed synthetic generation.

## Local Verification Notes

Verified locally from the current repo state:

- `eval_set/eval_chains.jsonl` has 1000 rows.
- `gold_set/gold_chains.jsonl` has 200 rows.
- The two datasets have zero `chain_id` overlap.
- The loop now scores the gold set separately instead of feeding eval predictions into the gold gate.
- A targeted pass covering run-loop, stage-transition, gold-gate, inference, export, observe, charts, dashboard integration, train, and freeze paths finished with 117 passing tests.
