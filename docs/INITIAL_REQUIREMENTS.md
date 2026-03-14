**AutoEmailTrust v2: Hyperbolic-Powered Version**  
(fully focused on your exact requirements + Hyperbolic integration)

We are keeping the **exact autoresearch loop** (agent edits one core file → fixed-budget experiment → evaluate → git keep/discard) but now **scaling it aggressively** with Hyperbolic for both cheap inference **and** on-demand training/fine-tuning. This gives you:
- 3–10× cheaper inference than Claude/Anthropic for synthetic data + judge loops
- Instant H100/H200 clusters ($1.49+/hr) for real model training inside the research loop
- No local GPU limits — the agent can spin up 8×H100 clusters overnight when it decides a full fine-tune is worth testing

### 1. Updated Project Structure (still 3 core files + Hyperbolic glue)
```
autoemailtrust/
├── prepare.py          # FIXED: email loader + Hyperbolic synth data generator (never edited)
├── analyzer.py         # ← ONLY FILE THE AGENT EDITS (prompts, sub-agents, or full LoRA fine-tune code)
├── program.md          # Focused instructions (updated below)
├── hyperbolic_utils.py # NEW: helpers for inference + GPU rental
├── requirements.txt    # + hyperbolic-cli + openai + Hyperbolic-AgentKit
└── eval_set/           # 1,000 held-out labeled chains (synthetic + public phishing datasets)
```

### 2. Hyperbolic Integration (this is the big upgrade)

**A. Inference API (OpenAI-compatible – use for everything fast/cheap)**
```python
# hyperbolic_utils.py
import openai
client = openai.OpenAI(
    api_key="your-hyperbolic-key",
    base_url="https://api.hyperbolic.xyz/v1"
)

# Example: mass synthetic spearphish generation
def generate_synthetic_batch(n=1000, model="meta-llama/Llama-3.1-405B"):
    # dolphin-style uncensored prompt for malicious examples
    ...
```

Use this for:
- Synthetic data gen (uncensored Dolphin/Llama-3.1-405B at ~1/5th Claude price)
- Fast judge during evaluation (still fall back to Opus only for final validation)

**B. GPU Rental for Training (the real power in the loop)**
Install:
```bash
pip install hyperbolic-cli
# or use their AgentKit for full programmatic control
git clone https://github.com/HyperbolicLabs/Hyperbolic-AgentKit
```

The Claude Agent SDK agent can now **call shell**:
```bash
hyperbolic gpu rent --type h100-8x --hours 2 --name experiment-47
hyperbolic ssh experiment-47 "python train_lora.py --data /tmp/synth_data"
```

In `analyzer.py` the agent can decide:
- “This prompt tweak is small → just run inference eval”
- “Delta > 5% and subtle-deceit axis weak → rent H100 cluster, run LoRA fine-tune, evaluate, terminate”

Budget control: agent is instructed to never exceed $10 per experiment and must call `hyperbolic gpu stop` at end.

### 3. Synthetic Data Strategy (now massive & uncensored)
`prepare.py` runs a nightly job via Hyperbolic inference:
- 50k+ email chains per night (benign + obvious spam + **subtle** spearphish with hidden deceit, zero-sum polarization, vulnerability traps, etc.)
- Use your 8-axis prompt to generate + self-label
- Opus (via Anthropic) validates only the top 10% for quality
- Store as JSONL with per-axis labels + composite trust score

This dataset grows automatically — the agent can even edit the synth prompt in a separate branch.

### 4. Focused `program.md` (copy-paste this — this is the new instruction set)
```
You are optimizing the world's best email trust scorer.

You may only edit analyzer.py.
Every experiment must finish in ≤15 minutes wall time OR ≤$8 Hyperbolic spend.

Your goal: maximize composite trust score on the held-out eval_set.

Composite metric (do NOT change this formula):
trust_score = 0.25*phish_f1 + 0.20*truthfulness_agreement + 0.15*manipulation_detection + 0.10*deceit_recall + 0.10*vulnerability_risk + 0.10*subtle_toxicity + 0.05*polarization + 0.05*classic_email_metrics

Prioritize experiments in this order:
1. Better chain-of-thought for subtle manipulation & hidden intent
2. Vulnerability detection given the "ask" (even if content is truthful)
3. Zero-sum polarization & emotional blackmail patterns
4. When prompt improvements stall for 3 runs → propose a LoRA fine-tune on Hyperbolic using the latest synthetic data
5. Always use Hyperbolic inference for speed; only use Claude Opus for judge on final candidates

If you rent GPUs, you MUST terminate them before finishing the experiment.
Log every change, metric delta, and cost.

Start now.
```

### 5. Two-Stage Research Loop (much more powerful than v1)
Stage 1 (default): prompt engineering + sub-agent improvements (fast, cheap inference)  
Stage 2 (when gains slow): agent writes LoRA fine-tune code → rents H100 cluster → trains on latest 20k+ synthetic examples → merges weights back → evaluates

This hybrid is exactly what Karpathy envisioned for real research.

### 6. Model Recommendations for the Scorer
- Start: Llama-3.1-8B or Qwen2.5-14B (fits in single H100)
- Scale: distill to 3B–7B after 200 experiments for production speed
- All fine-tuning done with Unsloth or Axolotl on Hyperbolic (pre-installed images available)

### 7. Quick Start Commands (do these today)
```bash
# 1. Fork & setup
git clone https://github.com/yourname/autoemailtrust
uv sync

# 2. Hyperbolic setup
hyperbolic login   # or export HYPERBOLIC_API_KEY=...

# 3. First run
python -m claude_agent_sdk run --program program.md --model claude-3.5-sonnet
```

This setup will produce **dramatically better results** than pure prompting because the agent can now actually **train** real models on cheap Hyperbolic compute when it discovers something worth memorizing.

We now have:
- Unlimited synthetic malicious data
- Real fine-tuning inside the loop
- Cost controls + automatic termination
- All while keeping the original autoresearch simplicity

Ready for the next step? Tell me:
- Draft the full `analyzer.py` skeleton + `hyperbolic_utils.py`?
- Or the first 10 synthetic email examples generated with Hyperbolic?
- Or the exact Claude Agent SDK + Hyperbolic-AgentKit orchestration code?

We’re building the best spearphishing detector on the planet. Let’s ship the first 50 experiments tonight.