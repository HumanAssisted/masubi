WE need to rearchtected the code

1. read the following requirements carefully, break into task list in single file, using agents to resesarch
2. reasearch where this changes in the code, add to task list
3. research where our documentation is out of date and add that to the task list
4. research where our dashboard will need to change. 
5. create the TRD we can later break into tasks.


# AutoEmailTrust v3.5 — PRD/TRD

> We use prompt optimization to discover the best teacher signal, then use autoresearch as a true training-and-architecture-search stage to distill that signal into a small fast MoE student model that ships locally.

---

## System Goal

Build a compact local email-trust model (50–200M params) that scores email chains on 9 trust axes, explains its reasoning, and knows when to escalate to a cloud judge. The model trains via Karpathy's autoresearch loop on Hyperbolic H100s, supervised by soft labels from a prompt-optimized LLM teacher.

## Pipeline Stages

### Stage 0 — Fixed Spec and Rubric

Define the contract that never changes.

**Inputs:** domain knowledge, academic frameworks (Gottman, Shapiro, Cialdini).

**Outputs (frozen before any other stage runs):**

- `spec.yaml` — axes, weights, thresholds, provider bindings, MoE caps, budget limits
- `annotation_rubric.md` — per-axis definitions with examples at 0.0 / 0.5 / 1.0, edge cases, annotator instructions
- `gold_set/gold_chains.jsonl` — 200 chains annotated by 2–3 humans
- `gold_set/calibration.json` — per-axis Cohen's Kappa, effective weights after downweighting
- `eval_set/eval_chains.jsonl` — 1,000 held-out chains (70% synthetic, 30% real)

### Stage 1 — Teacher Discovery (Prompt Optimization)

Find the best scoring strategy using large models. No weight training.

**What the agent optimizes (in `train.py`):**

- Scoring prompt (how to extract trust vectors from Llama-3.1-8B)
- Explanation format and content
- Subtle-axis escalation logic
- Judge prompt construction

**Compute:** local Ollama (Dolphin 3.0 for synthetic data), Hyperbolic serverless (Llama-3.1-8B for scoring), Anthropic API (Opus for judging).

**Experiment cycle:** ≤15 min wall time. Git keep/discard after each run.

**Keep/discard gates (all three must pass):**

1. Composite score improved (Kappa-weighted, includes FP penalty)
2. Gold-set veto: no axis degrades vs human consensus
3. Explanation quality ≥ 0.5 (flagged-axis coverage)

**Handoff trigger:** 3 consecutive no-improvement, or manual `--stage train`.

**Outputs (frozen before Stage 2):**

- `teacher/prompt_pack.yaml` — optimized scoring + judge + explanation prompts
- `teacher/label_rules.yaml` — labeling heuristics and escalation thresholds
- `synth_data/*.jsonl` — labeled email chains with soft trust vectors + explanation tags
- `teacher/explanation_schema.json` — tag vocabulary and format spec

### Stage 2 — Autoresearch Training (Student Model)

Train a small model using autoresearch. This is real `autoresearch`: fixed prep/eval, one mutable `train.py`, fixed-budget keep/discard loop.

**What the agent optimizes (in `train.py`, rewritten from Stage 1):**

- Student model architecture (dense baseline first, then MoE search)
- Number of experts, routing strategy (top-k, noisy top-k, expert choice), capacity factor
- Which layers are sparse vs dense
- Loss weighting across trust axes
- Explanation-tag head / multi-task structure
- Escalate-to-judge head
- Optimizer, learning rate schedule, batch size
- Hidden size / depth within param budget

**What the agent cannot change:**

- The dataset (frozen Stage 1 outputs)
- The teacher labels
- The evaluation harness (`eval.py`)
- The gold set
- MoE caps in `spec.yaml`

**Training data consumed:**

- All Stage 1 synthetic + real labeled chains
- Soft teacher scores (not hard labels) as training targets
- Explanation tags as auxiliary supervision signal

**Student model output shape:**

```json
{
  "trust_vector": {"phish": 0.92, "truthfulness": 0.15, ...},
  "reason_tags": ["authority_impersonation", "urgent_request", "unverifiable_claim"],
  "escalate": true
}
```

**Compute:** Hyperbolic H100 on-demand rental. BudgetGuard at $8/experiment.

**Experiment cycle:** 5–10 min wall time (MoE needs more steps). Git keep/discard after each run.

**Keep/discard gates:** same three gates as Stage 1.

**Architecture search path:** dense baseline → agent proves baseline works → agent unlocks MoE search. Controlled by experiment history: `program.md` instructs agent to establish dense baseline before introducing sparse layers.

**Output:** PyTorch checkpoint. Separate export function converts to GGUF for local testing when ready.

### Stage 3 — Production Inference

Ship the trained student model locally.

**Primary path:** student model runs locally (PyTorch → GGUF via llama.cpp/Ollama). Handles most emails with no API calls.

**Fallback path:** when student's `escalate` flag is true, route to cloud judge (Opus) for final verdict. This is rare — the escalation threshold is tuned during Stage 2 to minimize fallback rate.

**No runtime dependency on Stage 1 teacher prompts or Hyperbolic inference.**

---

## Trust Axes

9 axes. Each carries a type, metric, and composite weight.

| Axis | Type | Metric | Weight | Notes |
|------|------|--------|--------|-------|
| phish | binary | F1 | 0.22 | Spam/phishing classification |
| truthfulness | continuous | agreement | 0.18 | Factual accuracy, verifiability |
| manipulation | continuous | agreement | 0.13 | Persuasion tactics (Cialdini) |
| authority_impersonation | continuous | agreement | 0.10 | CEO fraud, vendor impersonation |
| deceit | continuous | recall | 0.10 | Hidden info, intent mismatch |
| vulnerability_risk | continuous | agreement | 0.10 | Recipient exposure given the ask |
| subtle_toxicity | continuous | agreement | 0.08 | Implicit harmful content |
| polarization | continuous | agreement | 0.05 | Zero-sum framing |
| classic_email_metrics | continuous | agreement | 0.04 | Standard email signals |

**Cross-cutting penalty:** `false_positive_rate: -0.15`

**Tracked but zero-weighted:** `verify_by_search` (binary, F1). Participates in gold-set veto but not composite.

**Kappa-proportional downweighting:** if an axis has Cohen's Kappa below 0.70, its weight is multiplied by `actual_kappa / 0.70`. Remainder redistributed proportionally to passing axes. Axis still participates in gold-set veto (human labels are reference).

**Explanation quality:** `(axes correctly referenced in explanation) / (axes scoring above 0.5)`. Emails with no flagged axes pass automatically. Gated at ≥ 0.5.

---

## File Layout

```
autoresearch-helpful/
├── pyproject.toml                # uv, Python 3.12
├── .env.example                  # ANTHROPIC_API_KEY, HYPERBOLIC_API_KEY, OLLAMA_MODEL
├── .gitignore
├── spec.yaml                     # single source of truth (see below)
├── annotation_rubric.md          # human scoring guidelines (written first)
├── autotrust/
│   ├── __init__.py
│   ├── config.py                 # typed spec.yaml loader, Kappa-adjusted weight calc
│   ├── schemas.py                # pydantic: Email, EmailChain, TrustVector, ExperimentResult, GoldChain, CalibrationReport
│   ├── providers/
│   │   ├── __init__.py           # registry, base classes, get_provider()
│   │   ├── ollama.py             # GeneratorProvider (Dolphin 3.0, local)
│   │   ├── hyperbolic.py         # ScoringProvider (serverless) + TrainingProvider (GPU rental)
│   │   └── anthropic.py          # JudgeProvider (Opus primary, Sonnet secondary)
│   ├── data.py                   # subcommands: build-train, build-eval, build-gold, annotate-export, calibrate-judge
│   ├── eval.py                   # composite metric, judge fallback, gold-set veto, explanation gate, keep_or_discard()
│   └── observe.py                # structlog, runs/<run_id>/ artifacts
├── train.py                      # THE ONLY MUTABLE FILE (Stage 1: prompts → Stage 2: PyTorch MoE)
├── run_loop.py                   # thin Anthropic tool-use orchestration, git keep/discard
├── program.md                    # agent instructions (references spec.yaml)
├── teacher/                      # frozen Stage 1 outputs (inputs to Stage 2)
│   ├── prompt_pack.yaml
│   ├── label_rules.yaml
│   └── explanation_schema.json
├── gold_set/
│   ├── gold_chains.jsonl
│   └── calibration.json
├── eval_set/
│   └── eval_chains.jsonl
├── synth_data/
│   └── .gitkeep
├── runs/
│   └── .gitkeep
└── tests/
    ├── test_composite_metric.py
    ├── test_kappa_downweight.py
    ├── test_escalation_rules.py
    ├── test_safety_filter.py
    ├── test_schema_validation.py
    ├── test_gold_gate.py
    ├── test_explanation_gate.py
    ├── test_providers.py
    └── test_smoke.py
```

---

## `spec.yaml`

```yaml
trust_axes:
  - name: phish
    type: binary
    metric: f1
    weight: 0.22
  - name: truthfulness
    type: continuous
    metric: agreement
    weight: 0.18
  - name: manipulation
    type: continuous
    metric: agreement
    weight: 0.13
  - name: authority_impersonation
    type: continuous
    metric: agreement
    weight: 0.10
  - name: deceit
    type: continuous
    metric: recall
    weight: 0.10
  - name: vulnerability_risk
    type: continuous
    metric: agreement
    weight: 0.10
  - name: subtle_toxicity
    type: continuous
    metric: agreement
    weight: 0.08
  - name: polarization
    type: continuous
    metric: agreement
    weight: 0.05
  - name: classic_email_metrics
    type: continuous
    metric: agreement
    weight: 0.04
  - name: verify_by_search
    type: binary
    metric: f1
    weight: 0.00

composite_penalties:
  false_positive_rate: -0.15

providers:
  generator:
    backend: local_ollama
    model: dolphin3:latest
  scorer:
    backend: hyperbolic
    model: meta-llama/Llama-3.1-8B-Instruct
  judge_primary:
    backend: anthropic
    model: claude-opus-4-20250514
  judge_secondary:
    backend: anthropic
    model: claude-sonnet-4-20250514
  trainer:
    backend: hyperbolic_gpu
    gpu_type: H100

limits:
  stage1_experiment_minutes: 15
  stage2_experiment_minutes: 10
  max_spend_usd: 8

judge:
  escalate_threshold: 0.60
  disagreement_max: 0.20
  min_gold_kappa: 0.70

calibration:
  downweight_policy: kappa_proportional
  redistribute_remainder: true
  log_downweighted_axes: true

explanation:
  flag_threshold: 0.5
  min_quality_threshold: 0.5
  gate_enabled: true

safety:
  synth_placeholder_only: true
  block_operational_instructions: true
  real_brands_in_eval: true

data:
  eval_set_size: 1000
  gold_set_size: 200
  synth_real_ratio: 0.7
  train_val_test_split: [0.70, 0.15, 0.15]

stage2:
  dense_baseline_first: true
  max_experts: 16
  max_params_m: 200
  max_top_k: 4
  export_formats: [pytorch, gguf]

production:
  judge_fallback_enabled: true
  escalate_on_flag: true
```

---

## File Responsibilities (One Sentence Each)

| File | Does | Does Not |
|------|------|----------|
| `spec.yaml` | Defines every axis, weight, threshold, provider binding, and cap | Contain code |
| `annotation_rubric.md` | Defines what 0.0/0.5/1.0 mean per axis with examples | Change after gold-set annotation |
| `config.py` | Loads spec.yaml into typed pydantic model, computes Kappa-adjusted weights | Make policy decisions |
| `schemas.py` | Defines all data models (Email, EmailChain, TrustVector, etc.) | Contain business logic |
| `providers/` | Wraps Ollama, Hyperbolic, Anthropic behind abstract interfaces | Choose which provider to use (spec.yaml does) |
| `data.py` | Builds train/eval/gold sets, runs calibration | Touch train.py or run experiments |
| `eval.py` | Computes composite, runs three gates, returns keep/discard verdict | Change between stages |
| `observe.py` | Writes structured logs and run artifacts to `runs/` | Make decisions |
| `train.py` | Stage 1: prompt-based scorer. Stage 2: PyTorch MoE training code | Touch any other file |
| `run_loop.py` | Calls Claude, applies edits to train.py, runs eval, git keep/discard | Implement eval logic (delegates to eval.py) |
| `program.md` | Tells the agent what to optimize and what the gates are | Duplicate spec.yaml values (references it) |

---

## Keep/Discard Policy

Applies identically in both stages. An experiment is kept only if ALL three gates pass:

1. **Composite improved** — weighted score (with FP penalty and Kappa-adjusted weights) exceeds previous best
2. **Gold-set veto** — no single axis degrades vs human consensus labels. Absolute authority. An experiment that improves composite by +10% is rejected if any axis regresses
3. **Explanation gate** — explanation quality ≥ 0.5 (ratio of correctly referenced flagged axes)

The gold-set veto is evaluated first. If it fails, composite and explanation are not checked.

---

## Provider Interfaces

```
GeneratorProvider    (local_ollama)     → generate(), generate_batch(), check_available()
ScoringProvider      (hyperbolic)       → score(), score_batch()
JudgeProvider        (anthropic)        → judge(), dual_judge()
TrainingProvider     (hyperbolic_gpu)   → list_gpus(), rent_gpu(), stop_gpu(), run_remote(), budget_guard()
```

Shared base class: retry, structured logging, error normalization. `get_provider(role, spec)` factory.

---

## Synthetic Data Safety

All synthetic generation uses placeholder-only tokens. Hard constraints:

- No real brands, domains, phone numbers, or personal identifiers
- No operational phishing instructions (step-by-step attack playbooks)
- Structural malicious only: teaches the model to recognize attack *patterns* (urgency + authority + financial request)
- Safety filter in `data.py`: regex + blocklist, runs before any example enters training data
- Real brands preserved in eval/gold sets only (from SpamAssassin/Enron corpora)

---

## Test Strategy

Platform code (Layers 0–2) is TDD. `train.py` (Layer 3) is smoke-tested only.

| Test | What it verifies |
|------|-----------------|
| `test_composite_metric` | Formula matches spec weights, FP penalty, metric dispatch (F1 vs agreement) |
| `test_kappa_downweight` | Proportional downweighting math, redistribution, edge cases (all axes fail, one axis at exactly threshold) |
| `test_escalation_rules` | Judge fallback triggers at threshold, not below |
| `test_safety_filter` | Rejects operational instructions, allows structural malicious, passes clean emails |
| `test_schema_validation` | All pydantic models round-trip correctly |
| `test_gold_gate` | Veto rejects axis regressions, accepts genuine improvements, veto overrides composite |
| `test_explanation_gate` | Blocks below threshold, passes above, respects gate_enabled flag, handles zero-flagged emails |
| `test_providers` | Contract tests per backend (mock-based): returns expected shapes, retries on failure, budget guard triggers |
| `test_smoke` | 10-chain eval, 10-chain gold, 1 full loop cycle with dummy train.py, three-gate keep/discard end-to-end |

---

## Execution Order

```
 1. Scaffold:           pyproject.toml, .env.example, .gitignore, spec.yaml
 2. Annotation rubric:  annotation_rubric.md (BEFORE any data generation)
 3. Core platform:      config.py, schemas.py, providers/ (registry + 3 backends)
 4. Core tests:         TDD — write tests for config, schemas, providers, then implement
 5. Data + eval:        data.py, eval.py (composite, three gates, Kappa downweighting)
 6. Data/eval tests:    TDD — composite, downweighting, escalation, safety, gold gate, explanation gate
 7. Observability:      observe.py
 8. Gold-set gen:       uv run python -m autotrust.data build-gold
 9. HUMAN STEP:         annotate 200 chains, run calibrate-judge, review Kappa per axis
10. Stage 1 train.py:   prompt-based scorer baseline
11. program.md:         agent instructions (references spec.yaml, explains three gates)
12. run_loop.py:        thin orchestration
13. Smoke tests:        10-chain eval, 1 loop cycle, three-gate verification
14. Generate eval_set:  uv run python -m autotrust.data build-eval
15. RUN STAGE 1:        prompt optimization until stall or manual trigger
16. Freeze teacher:     commit teacher/ artifacts, lock synth_data/
17. Rewrite train.py:   PyTorch dense baseline student model
18. Update program.md:  Stage 2 instructions (dense first, then MoE search, caps from spec.yaml)
19. RUN STAGE 2:        autoresearch training loop on Hyperbolic H100s
20. Export:             PyTorch checkpoint → GGUF for local testing
21. README.md:          architecture, quickstart, safety policy
```

---

## Decisions Log

Every design choice made during planning, with rationale.

| # | Decision | Choice | Why |
|---|----------|--------|-----|
| 1 | Orchestration | Plain Anthropic tool-use, not Agent SDK | Full control over budget, git, three-gate policy |
| 2 | Synthetic data gen | Local Ollama (Dolphin 3.0), not cloud | Uncensored, free, offline, fast iteration on prompts |
| 3 | Training compute | Hyperbolic H100 on-demand | GPU rental for training only, not inference or data gen |
| 4 | Base scoring model | Llama-3.1-8B (128K native context) | Eliminates 2048 truncation; handles full email threads |
| 5 | LLM-as-judge | Claude Opus via Anthropic API | Highest quality; not Hyperbolic 405B |
| 6 | Kappa < 0.70 policy | Proportional downweighting + redistribute | Avoids binary include/exclude; poorly-calibrated axes contribute less, not zero |
| 7 | Explanation quality | Separate gate (not composite weight) | Agent can't compensate for bad explanations with better scores |
| 8 | Stage 1 → Stage 2 | Sequential: teacher discovery then student training | Stage 1 outputs freeze before Stage 2 starts; prevents eval contamination |
| 9 | MoE architecture | Agent-controlled (expert count, routing, capacity) | True autoresearch: agent does real architecture search |
| 10 | Expert-to-axis mapping | Emergent, not 1:1 | Agent discovers which axes cluster; more flexible |
| 11 | Stage 2 baseline | Dense first, then MoE | Establishes working baseline before introducing complexity |
| 12 | Student output | Trust vector + explanation tags + escalate flag | Enables explainability and selective cloud fallback |
| 13 | Training supervision | Soft teacher scores + explanation tags | Richer signal than hard labels; explanation as auxiliary loss |
| 14 | Production runtime | PyTorch primary, GGUF export for local | PyTorch for flexibility during training; GGUF for deployment |
| 15 | Production fallback | Student + rare judge for high-uncertainty | Handles edge cases without making judge a runtime dependency |
| 16 | MoE scale caps | Capped in spec.yaml (16 experts, 200M params, top-4) | Prevents agent from exceeding budget or VRAM limits |
| 17 | Stage 2 cycle time | 5–10 min (not Karpathy's 300 sec) | MoE training needs more steps to converge |
| 18 | Composite weights | Per-axis objects in spec.yaml (not separate mapping) | Eliminates name-translation layer; eval.py dispatches automatically |
| 19 | Gold-set veto | Absolute authority, evaluated first | Prevents silent single-axis regression even when composite improves |
| 20 | train.py lifecycle | Same file across both stages; rewritten at handoff | Respects autoresearch single-mutable-file rule |