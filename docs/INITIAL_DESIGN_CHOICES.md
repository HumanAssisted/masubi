# AutoEmailTrust v3.5 -- Design Choices & Rationale

## Why Autoresearch as the Foundation

- Karpathy's autoresearch is a 630-line agent harness that runs autonomous ML experiments -- ~12/hour, ~100 overnight -- keeping only improvements via git ratcheting
- We're repurposing the loop: same ratcheting architecture, but the dataset is email chains, the metric is a multi-dimensional trust score, and the base model is Llama-3.1-8B instead of a 50M GPT
- The key insight autoresearch proved: AI agents independently rediscover architecture improvements that human researchers miss -- and findings on small models transfer to larger ones
- Karpathy's next vision is SETI@home-style distributed agent swarms; our single-agent loop is designed to be parallelizable later

## Three-Layer Architecture (Spec -> Platform -> Mutable)

- **Layer 1 -- spec.yaml as single source of truth:** every axis definition (name, type, metric, weight), composite penalties, axis groups, provider bindings, thresholds, limits, calibration policy, and safety flags live in one YAML file. No scattered config, no magic numbers in code
- **Layer 2 -- fixed platform:** providers, data pipeline, evaluation engine, observability. Heavily tested, never touched by the agent
- **Layer 3 -- train.py as the only mutable file:** the autoresearch agent edits nothing else. This constraint is what makes the ratcheting loop safe -- the evaluation contract can never be gamed
- Why three layers: autoresearch's power comes from a tight sandbox. The agent is creative within constraints; the constraints themselves are immovable

## Trust Score: 9 Dimensions, Not Binary

- Traditional spam/phishing detection is binary (spam or not spam) -- and it's essentially solved at >98% accuracy
- The hard problem is everything else: is a legitimate-looking email subtly manipulative? Does it exploit authority? Is the recipient being put at risk even if the sender is trustworthy?
- Nine axes: phish (binary), truthfulness, verify-by-search (binary), manipulation, deceit, vulnerability risk, subtle toxicity, polarization, authority impersonation
- Each axis carries its own metric type (F1 for binary, agreement/recall for continuous) and composite weight -- defined in spec.yaml, not code
- The output is a trust *vector* (dict of per-axis scores) plus a weighted composite *scalar* -- the vector gives per-dimension insight, the scalar drives the autoresearch keep/discard loop

## Structured Axis Definitions

- Each axis in spec.yaml is a structured object with `name`, `type` (binary/continuous), `metric` (f1/agreement/recall), and `weight`
- `eval.py` auto-dispatches metric computation by type: binary axes get F1, continuous axes get agreement or recall as specified
- `composite_penalties` is a separate section for cross-cutting penalties like `false_positive_rate: -0.15` that aren't axis scores
- `axis_groups` encode binary/continuous/subtle/fast groupings once, removing hidden policy from evaluation code
- `verify_by_search` is tracked at weight 0.00 -- participates in gold-set veto but contributes zero to composite until promoted

## Hybrid Architecture: Fast Scorer + LLM-as-Judge

- Not all dimensions are equally hard. Phishing classification, manipulation detection, and authority impersonation are solvable with fine-tuned small models (>80-98% accuracy in literature)
- Subtle toxicity, deceit, polarization, and vulnerability assessment are open research problems -- small models can't reliably score them
- Solution: Llama-3.1-8B handles the solved dimensions fast and cheap; Claude Opus handles the subtle ones via structured LLM-as-judge with rubric scoring
- The judge only fires when fast scores on subtle axes (defined by `axis_groups.subtle` in spec.yaml) cross an escalation threshold (0.6) -- so most eval chains avoid the expensive Opus call entirely
- This is a cost/quality tradeoff: Opus is ~100x more expensive per token than Llama-3.1-8B, so we only use it where it matters

## Three-Gate Keep/Discard Policy

- **Gate 1 -- Composite improved:** weighted score must go up (includes false-positive penalty and Kappa-adjusted weights)
- **Gate 2 -- Gold-set veto:** no single axis may degrade versus human consensus labels. Absolute authority -- an experiment that improves composite by +10% is still rejected if it degrades any axis, including zero-weighted ones like `verify_by_search`
- **Gate 3 -- Explanation quality:** the model's explanation must reference the correct flagged axes. If an email scores high on manipulation and authority impersonation, the explanation must mention both. Operates in `warn_then_gate` mode: logs only until baseline is established, then becomes a hard gate
- Why three gates: composite alone is gameable (sacrifice one axis to boost others). Gold-set veto prevents silent regression. Explanation gate ensures the model is right for the right reasons, not just pattern-matching
- All three gates are documented in program.md so the agent understands why its experiments get rejected

## Gold Set and Human Annotation

- 200 email chains annotated by 2-3 human scorers using a rubric written before any data generation
- The rubric (`annotation_rubric.md`) defines what 0.0, 0.5, and 1.0 mean for every continuous axis with concrete examples -- this is the semantic foundation of the entire system
- Cohen's Kappa computed per axis to measure inter-annotator and Opus-human agreement
- Purpose: prevents the evaluation loop from being circular (without human ground truth, the LLM judge is grading its own homework)
- The gold set is committed to git and never modified by the agent -- it's the fixed reference frame

## Kappa-Proportional Downweighting

- Problem: some axes (polarization, subtle toxicity) will inevitably have lower Opus-human agreement than others
- Binary exclude/include is too coarse -- excluding an axis loses all signal; including it at full weight overweights unreliable judgments
- Solution: axis weight is multiplied by `actual_kappa / min_gold_kappa`. If subtle_toxicity has Kappa 0.55 vs minimum 0.70, its weight drops from 0.08 to 0.063
- Unallocated weight (the difference) is redistributed proportionally across passing axes
- Scoped to composite only: Kappa downweighting affects composite ranking but never affects the gold-set veto. The veto always compares against raw human consensus labels
- Fully automated, fully logged -- every experiment run shows which axes are downweighted and by how much

## Explanation Quality as a First-Class Metric

- Most phishing detectors are black boxes -- they flag an email but don't say why
- We require structured explanations: a `reasons` array listing which axes were flagged, plus a human-readable summary
- Explanation quality = (axes correctly referenced in explanation) / (axes scoring above flag threshold of 0.5). Chains with no flagged axes auto-pass at 1.0
- The scorer emits explicit structured output (`{"trust_vector": {...}, "explanation": {"reasons": [...], "summary": "..."}}`), not extracted from hidden chain-of-thought reasoning. This is testable and deterministic
- `warn_then_gate` mode: early experiments log explanation quality without blocking; after the first successful baseline, the gate becomes hard
- This is a separate gate, not a composite weight -- the agent can't compensate for bad explanations with better scores
- Why it matters: a trust scorer that says "this email is 85% likely to be manipulative because it impersonates your CFO and creates artificial urgency around a wire transfer" is categorically more useful than one that just outputs 0.85

## Local Uncensored Models for Synthetic Data

- Generating realistic spearphishing training data requires models that won't refuse security research prompts
- Dolphin 3.0 (Llama 3.1 8B) via Ollama -- runs locally, is uncensored by design, costs nothing per generation, works offline
- All synthetic data uses placeholder-only tokens: no real brands, domains, phone numbers, or operational phishing steps
- Real brands are preserved in eval data from real corpora (SpamAssassin, Enron) -- the model must learn to recognize actual brand impersonation patterns
- The data teaches the model to recognize attack *patterns* (urgency + authority + financial request), not to produce copy-pasteable phishing templates
- Safety filter is a hard constraint in the data pipeline -- regex + blocklist rejects anything with operational phishing instructions before it enters training data

## Hyperbolic for Scoring and Training

- Hyperbolic provides OpenAI-compatible inference for the scoring model (Llama-3.1-8B) and GPU Marketplace for on-demand H100 rental for LoRA fine-tuning
- Inference for scoring: same `openai.OpenAI` client pattern, just swap `base_url` and `api_key`
- Training compute only when needed: the agent can rent GPUs after 3 consecutive no-improvement experiments
- BudgetGuard context manager auto-terminates GPU instances at $8 spend limit per experiment
- Synthetic data generation and judge evaluation are handled elsewhere (local Ollama and Anthropic API respectively) -- clear infrastructure boundaries

## Llama-3.1-8B with 128K Native Context

- Autoresearch's original model has a 2048-token context window -- most email threads exceed that
- Rather than patch context with YaRN (which degrades quality on small models), we swap the base model entirely to Llama-3.1-8B which has 128K native context
- YaRN is available as an escape hatch if the agent wants to push further, but 128K handles any realistic email chain
- The agent's first experiment can be a base model swap without any architectural rework -- this is by design

## Thread-Aware Scoring

- Email chains are not flat text. Important signals emerge across messages: escalation patterns, authority shifts, persuasion buildup, and request progression
- Example spearphishing pattern: email 1 (casual contact) -> email 2 (small request) -> email 3 (financial action)
- The thread encoder architecture: per-email embeddings -> attention over thread sequence -> chain-level classifier with per-axis heads
- Flat encoding will miss these temporal patterns -- thread-aware scoring is the single biggest accuracy lever for multi-message spearphishing detection

## Provider Registry Pattern

- Four provider roles: Generator (local Ollama), Scorer (Hyperbolic Llama-3.1-8B), Judge (Anthropic Opus), Trainer (Hyperbolic GPU)
- Each role is an abstract interface with per-backend implementations: `ollama.py`, `hyperbolic.py`, `anthropic.py`
- Swapping backends is a spec.yaml change, not a code change -- future-proofs against provider lock-in
- Shared base class handles retry logic, structured logging, error normalization -- written once, tested once
- `train.py` uses providers through the registry -- it never constructs API clients directly

## Plain Anthropic Tool-Use, Not Agent SDK

- The orchestration loop uses direct `anthropic` library calls with tool-use, not the Claude Agent SDK
- Why: full control over budget enforcement, git integration, and the three-gate keep/discard policy
- The tradeoff: no subagent parallelism, no built-in evaluator-optimizer loop
- For a single-agent autoresearch ratchet, this is the right call -- the loop is sequential by design and the evaluation contract is too important to delegate

## Observability: Structured Logs + Run Artifacts

- Every experiment gets a `runs/<run_id>/` directory with metrics.json, predictions.jsonl, config.json, summary.txt
- structlog with JSON output -- machine-parseable, greppable, no custom dashboards needed
- Calibration warnings surface in logs: which axes are downweighted, how much weight was redistributed, which gates passed or failed and in which mode (warn vs gate)
- No OpenTelemetry at this stage -- the complexity isn't justified for a single-agent loop. OTLP can be layered in later
- Flat experiment history derivable from run artifacts for quick human review

## Test Boundaries

- Platform code (layers 1-2) is heavily tested via TDD: composite math with auto-dispatch by axis type, Kappa downweighting math, all three gates (including explanation gate modes), safety filters, provider contracts, schema validation
- `train.py` (layer 3) is lightly smoke-tested -- it's meant to evolve freely within the constraints the tests enforce
- Smoke test: 10-chain eval set, 10-chain gold set, 1 full loop cycle with a dummy scorer that returns fixed `ScorerOutput` -- verifies the git commit/discard cycle and all three gates end-to-end
- Regression test: frozen gold-set agreement on raw labels, false-positive test slice, explanation format validation (reasons array present, maps to valid axis names)
- The insight: you test the cage, not the animal inside it

## TrustVector as `dict[str, float]`

- Trust vectors are plain `dict[str, float]` validated against spec.yaml axis names at construction time
- Not a dynamically-generated pydantic model -- that would make typing, serialization, and tests awkward
- Validation catches missing or extra axis keys; the schema itself stays simple and portable

## Safety Policy Separated from Model Experimentation

- Placeholder rules, operational-instruction blocking, and dataset constraints live in the fixed data pipeline (`data.py`), not in `train.py`
- The agent cannot weaken safety constraints while optimizing -- they're outside its edit boundary
- Hybrid safety policy: placeholder-only in synthetic generation, real brands preserved in eval data from real corpora

## Simplicity as a Design Goal

- Small, rigid systems are easier to trust, test, and iterate on
- Complexity is only added when it clearly improves model quality or reliability
- The entire fixed platform is ~6 modules; the mutable layer is 1 file; the spec is 1 YAML file

---

These choices satisfy three simultaneous constraints:

1. **Stay faithful to autoresearch** (one mutable file, ratcheting git loop)
2. **Address every reliability/safety warning** from external research reports
3. **Maximize cheap, scalable experimentation** on Hyperbolic while keeping human oversight as the final gate

Result: a system that can run unsupervised for days yet still produces trustworthy, explainable, world-class spearphishing detection.

---

## Review Summary

**Review Date:** 2026-03-14
**Reviewer:** Claude Code (deep-review)
**Tests:** 103/103 passing (5.63s)
**Lint:** ruff check clean (0 violations)

### Issue Counts by Severity
| Severity | Count |
|----------|-------|
| Critical | 2 |
| High     | 4 |
| Medium   | 5 |
| Low      | 4 |
| **Total**| **15** |

### Issues by Category
| Category | Count |
|----------|-------|
| Omission | 4 |
| Bug | 4 |
| DRY Violation | 2 |
| Quality | 2 |
| Test Gap | 1 |

### Requirements Met
- Scaffold (pyproject.toml, .env.example, .gitignore, directories) -- MET
- spec.yaml (10 axes, weights sum to 1.0, all sections) -- MET
- annotation_rubric.md (all 10 axes, edge cases, annotator instructions) -- MET
- config.py (pydantic models, load_spec, get_spec singleton) -- MET (formula issue in get_effective_weights)
- schemas.py (all models, validate_trust_vector) -- MET (validation not at construction time)
- providers/ (registry, 4 roles, retry, concrete implementations) -- MET (retry scope limited)
- data.py (CLI, safety filter, Kappa computation) -- PARTIALLY MET (pipeline is placeholder)
- eval.py (three-gate policy, auto-dispatch, explanation gate) -- MET (FP penalty issue)
- observe.py (run lifecycle, artifacts) -- PARTIALLY MET (no structlog, metrics overwritten)
- train.py (EmailTrustScorer, structured output, thread signals) -- MET
- program.md (agent instructions, three-gate policy) -- MET
- run_loop.py (orchestration) -- NOT MET (placeholder loop)
- Smoke tests (9 tests, three-gate coverage) -- MET (one conditional assertion)
- README.md -- MET (one bad file reference)

### Critical Items
1. **ISSUE 001**: run_loop.py main loop is unimplemented -- the autoresearch loop cannot execute
2. **ISSUE 002**: All data pipeline subcommands are placeholders -- no data can be generated

### Recommendation
**Needs rework.** The two critical issues (unimplemented orchestration loop and placeholder data pipeline) mean the system cannot run any experiments. The fixed platform layer (eval.py, config.py, schemas.py, providers/) is solid and well-tested, but the glue that ties it all together (run_loop.py, data.py) is incomplete. The Kappa formula bug (Issue 003) and missing structlog (Issue 004) are significant deviations from the PRD that should be fixed before shipping.
