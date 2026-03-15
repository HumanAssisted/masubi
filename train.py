"""EmailTrustScorer -- improved prompt, thread signals, JSON parsing, and Stage 2 student training.

Produces structured ScorerOutput with trust_vector (dict) and Explanation
(reasons array + summary). Includes dense baseline student model training.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import TYPE_CHECKING

from autotrust.schemas import Explanation, ScorerOutput

if TYPE_CHECKING:
    from autotrust.config import Spec
    from autotrust.providers import ScoringProvider, TrainingProvider
    from autotrust.schemas import EmailChain

logger = logging.getLogger(__name__)

# ── Trust axis definitions for the scoring prompt ────────────────────────────
AXIS_DEFINITIONS = {
    "phish": (
        "Phishing risk: Does the email attempt to steal credentials, personal info, "
        "or financial data? Look for spoofed sender domains, deceptive links, login "
        "pages, fake alerts ('your account will be suspended'), or requests to click "
        "suspicious URLs. Score 0.0 = clearly safe, 1.0 = textbook phishing."
    ),
    "truthfulness": (
        "Truthfulness: Are the factual claims in the email accurate and verifiable? "
        "Look for fabricated statistics, false deadlines, invented policies, or "
        "misattributed quotes. Score 0.0 = all claims appear truthful, 1.0 = "
        "pervasive falsehoods."
    ),
    "verify_by_search": (
        "Verify-by-search: Could the claims be fact-checked with a simple web search? "
        "Score 0.0 = claims are easily verifiable and likely true, 1.0 = claims are "
        "unverifiable or contradicted by public information."
    ),
    "manipulation": (
        "Manipulation: Does the email use psychological pressure tactics? Look for "
        "artificial urgency ('act now or lose access'), fear appeals, guilt-tripping, "
        "love-bombing, reciprocity exploitation, or social proof fabrication. "
        "Score 0.0 = no manipulation, 1.0 = heavy manipulation."
    ),
    "deceit": (
        "Deceit: Is the sender being deliberately deceptive about their identity, "
        "intentions, or the nature of the communication? Look for impersonation, "
        "hidden agendas, misleading subject lines, or bait-and-switch tactics. "
        "Score 0.0 = transparent, 1.0 = deeply deceptive."
    ),
    "vulnerability_risk": (
        "Vulnerability risk: Does the email target vulnerable populations (elderly, "
        "children, non-native speakers, financially distressed)? Look for simplified "
        "language designed to confuse, exploitation of trust, or targeting of specific "
        "vulnerable demographics. Score 0.0 = no targeting, 1.0 = clearly exploitative."
    ),
    "subtle_toxicity": (
        "Subtle toxicity: Does the email contain veiled hostility, passive aggression, "
        "microaggressions, backhanded compliments, or coded discriminatory language? "
        "Not overt hate speech, but insidious negativity. Score 0.0 = no toxicity, "
        "1.0 = pervasively toxic."
    ),
    "polarization": (
        "Polarization: Does the email push extreme viewpoints, use us-vs-them framing, "
        "demonize outgroups, or attempt to radicalize the reader? Look for divisive "
        "rhetoric, conspiracy theories, or inflammatory generalizations. "
        "Score 0.0 = balanced/neutral, 1.0 = highly polarizing."
    ),
    "classic_email_metrics": (
        "Classic email red flags: Check for spam indicators -- ALL CAPS, excessive "
        "punctuation (!!!), too-good-to-be-true offers, unsolicited attachments, "
        "mismatched reply-to addresses, generic greetings ('Dear Customer'), or "
        "broken formatting. Score 0.0 = professional email, 1.0 = obvious spam."
    ),
    "authority_impersonation": (
        "Authority impersonation: Does the sender falsely claim to be from a position "
        "of authority (CEO, IT admin, government official, bank representative)? "
        "Look for domain mismatches, unusual requests from 'leadership', or claims "
        "of official capacity without verification. Score 0.0 = no impersonation, "
        "1.0 = clear authority impersonation."
    ),
}


class EmailTrustScorer:
    """Thread-aware email trust scorer with structured explanation output."""

    def __init__(self, provider: ScoringProvider, spec: Spec) -> None:
        self.provider = provider
        self.spec = spec

    def score_chain(self, chain: EmailChain) -> ScorerOutput:
        """Score a single email chain. Returns trust vector + structured explanation."""
        prompt = self._build_prompt(chain)
        raw_response = self.provider.score(prompt)
        return self._parse_response(raw_response)

    def score_batch(self, chains: list[EmailChain]) -> list[ScorerOutput]:
        """Score multiple chains (sequential)."""
        return [self.score_chain(c) for c in chains]

    # ── Prompt construction ──────────────────────────────────────────────────

    def _build_prompt(self, chain: EmailChain) -> str:
        """Build a thread-aware scoring prompt with detailed axis definitions,
        thread signals, and explicit output format instructions."""

        # Build chain text with thread context
        thread_parts = []
        for i, email in enumerate(chain.emails):
            thread_parts.append(
                f"--- Email {i + 1} (depth={email.reply_depth}) ---\n"
                f"From: {email.from_addr}\n"
                f"To: {email.to_addr}\n"
                f"Subject: {email.subject}\n"
                f"Time: {email.timestamp}\n\n"
                f"{email.body}"
            )
        thread_text = "\n\n".join(thread_parts)

        # Thread encoder signals
        signals = self._extract_thread_signals(chain)
        signals_text = "\n".join(f"  - {s}" for s in signals) if signals else "  None detected"

        # Build detailed axis descriptions
        axis_descriptions = []
        for a in self.spec.trust_axes:
            desc = AXIS_DEFINITIONS.get(a.name, f"{a.name}: Score 0.0 (safe) to 1.0 (maximum concern).")
            axis_descriptions.append(f"  {a.name} (weight={a.weight}): {desc}")
        axes_block = "\n".join(axis_descriptions)

        # Get axis names for the JSON template
        axis_names = [a.name for a in self.spec.trust_axes]
        example_vector = ", ".join(f'"{name}": 0.0' for name in axis_names)

        prompt = f"""You are an expert email security analyst. Your job is to analyze email threads for trust and safety risks.

TASK: Score the following email chain on each of the trust axes below. Each score is a float from 0.0 (completely safe / no concern) to 1.0 (maximum risk / highest concern).

TRUST AXES (score each one):
{axes_block}

THREAD SIGNALS (automatically detected patterns):
{signals_text}

EMAIL CHAIN TO ANALYZE:
{thread_text}

SCORING INSTRUCTIONS:
1. Read the entire email chain carefully, considering the thread context and how the conversation evolves.
2. Pay special attention to the automatically detected thread signals above.
3. For each axis, assign a score between 0.0 and 1.0 based on the definitions above.
4. In the explanation, list EVERY axis that scores above 0.5 and explain WHY it was flagged.
5. The summary should be a single sentence capturing the overall risk assessment.

IMPORTANT: Respond with ONLY a valid JSON object. No markdown, no code fences, no extra text.

Output format:
{{"trust_vector": {{{example_vector}}}, "explanation": {{"reasons": ["<axis_name>: <why it was flagged>", ...], "summary": "<one sentence overall assessment>"}}}}

JSON:"""
        return prompt

    # ── Thread signal extraction ─────────────────────────────────────────────

    def _extract_thread_signals(self, chain: EmailChain) -> list[str]:
        """Extract thread-aware signals from the email chain with enhanced detection."""
        signals = []

        if len(chain.emails) > 1:
            # Reply timing analysis
            for i in range(1, len(chain.emails)):
                prev_time = chain.emails[i - 1].timestamp
                curr_time = chain.emails[i].timestamp
                delta = (curr_time - prev_time).total_seconds()
                if delta < 60:
                    signals.append(
                        f"VERY rapid reply at email {i + 1} ({delta:.0f}s) -- "
                        "possible automated or pre-scripted response"
                    )
                elif delta < 300:
                    signals.append(f"Rapid reply at email {i + 1} ({delta:.0f}s)")

            # Thread depth escalation
            depths = [e.reply_depth for e in chain.emails]
            if len(set(depths)) > 1:
                signals.append(f"Thread depth escalation: {depths}")

            # Authority shifts: detect when a new, more authoritative sender appears
            senders = [e.from_addr for e in chain.emails]
            unique_senders = list(dict.fromkeys(senders))  # preserve order, dedupe
            if len(unique_senders) > 1:
                signals.append(f"Sender changes in thread: {unique_senders}")
                # Check if later senders claim higher authority
                for i in range(1, len(chain.emails)):
                    if chain.emails[i].from_addr != chain.emails[i - 1].from_addr:
                        signals.append(
                            f"Authority shift at email {i + 1}: "
                            f"{chain.emails[i - 1].from_addr} -> {chain.emails[i].from_addr}"
                        )

            # Escalation in tone: check if urgency increases over the thread
            urgency_per_email = []
            urgency_keywords = [
                "urgent", "immediately", "asap", "right now", "deadline",
                "time-sensitive", "act now", "expires", "final notice",
                "last chance", "don't delay", "do not delay"
            ]
            for email in chain.emails:
                text = (email.subject + " " + email.body).lower()
                count = sum(1 for w in urgency_keywords if w in text)
                urgency_per_email.append(count)

            if len(urgency_per_email) > 1 and urgency_per_email[-1] > urgency_per_email[0]:
                signals.append(
                    f"Urgency escalation across thread: {urgency_per_email} "
                    "(later emails more urgent)"
                )

            # Persuasion progression: requests become more specific/demanding
            request_keywords = [
                "please send", "wire transfer", "click here", "download",
                "provide your", "confirm your", "verify your", "update your",
                "send me", "share your", "give me", "transfer"
            ]
            requests_per_email = []
            for email in chain.emails:
                text = (email.subject + " " + email.body).lower()
                count = sum(1 for w in request_keywords if w in text)
                requests_per_email.append(count)
            if len(requests_per_email) > 1 and requests_per_email[-1] > requests_per_email[0]:
                signals.append(
                    f"Request escalation: later emails contain more action demands "
                    f"({requests_per_email})"
                )

        # ── Single-email and cross-thread signals ────────────────────────────

        all_text = " ".join(e.subject + " " + e.body for e in chain.emails).lower()

        # Urgency keywords (expanded)
        urgency_words = [
            "urgent", "immediately", "asap", "right now", "deadline",
            "time-sensitive", "act now", "expires", "final notice",
            "last chance", "don't delay", "do not delay", "hours left",
            "limited time", "respond immediately"
        ]
        found_urgency = [w for w in urgency_words if w in all_text]
        if found_urgency:
            signals.append(f"Urgency signals: {found_urgency}")

        # Authority claims (expanded)
        authority_words = [
            "ceo", "cfo", "cto", "coo", "director", "manager",
            "admin", "it department", "help desk", "helpdesk",
            "president", "vice president", "vp", "chairman",
            "compliance", "legal department", "hr department",
            "security team", "system administrator"
        ]
        found_authority = [w for w in authority_words if w in all_text]
        if found_authority:
            signals.append(f"Authority claims: {found_authority}")

        # Financial / credential requests
        financial_words = [
            "bank account", "routing number", "wire transfer", "bitcoin",
            "cryptocurrency", "gift card", "payment", "invoice",
            "social security", "ssn", "credit card", "password",
            "login credentials", "pin number"
        ]
        found_financial = [w for w in financial_words if w in all_text]
        if found_financial:
            signals.append(f"Financial/credential requests detected: {found_financial}")

        # Link/attachment signals
        link_patterns = ["click here", "click below", "click this link",
                         "open the attachment", "see attached", "download"]
        found_links = [w for w in link_patterns if w in all_text]
        if found_links:
            signals.append(f"Link/attachment action requests: {found_links}")

        # Emotional manipulation
        emotional_words = [
            "disappointed in you", "i trusted you", "you owe me",
            "don't let me down", "i'm counting on you", "this is your fault",
            "you'll regret", "consequences", "disciplinary action"
        ]
        found_emotional = [w for w in emotional_words if w in all_text]
        if found_emotional:
            signals.append(f"Emotional manipulation signals: {found_emotional}")

        # Domain mismatch detection
        if len(chain.emails) > 0:
            from_domains = set()
            for email in chain.emails:
                addr = email.from_addr.lower()
                if "@" in addr:
                    from_domains.add(addr.split("@")[-1])
            if len(from_domains) > 1:
                signals.append(
                    f"Multiple sender domains detected: {sorted(from_domains)} "
                    "(possible spoofing)"
                )

        return signals

    # ── Response parsing ─────────────────────────────────────────────────────

    def _parse_response(self, raw: str) -> ScorerOutput:
        """Parse LLM response into ScorerOutput with robust fallback handling."""
        data = None

        # Strategy 1: Direct JSON parse
        try:
            data = json.loads(raw.strip())
        except (json.JSONDecodeError, TypeError):
            pass

        # Strategy 2: Strip code fences (```json ... ``` or ``` ... ```)
        if data is None:
            cleaned = raw.strip()
            # Remove opening code fence
            if cleaned.startswith("```"):
                # Remove first line (```json or ```)
                first_newline = cleaned.find("\n")
                if first_newline != -1:
                    cleaned = cleaned[first_newline + 1:]
                else:
                    cleaned = cleaned[3:]
            # Remove closing code fence
            if cleaned.rstrip().endswith("```"):
                cleaned = cleaned.rstrip()
                cleaned = cleaned[:-3].rstrip()

            try:
                data = json.loads(cleaned)
            except (json.JSONDecodeError, TypeError):
                pass

        # Strategy 3: Find the outermost JSON object with brace matching
        if data is None:
            data = self._extract_json_object(raw)

        # Strategy 4: Find JSON with simple regex (no backreferences)
        if data is None:
            match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", raw, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(0))
                except (json.JSONDecodeError, TypeError):
                    pass

        # Strategy 5: Try to fix common JSON issues
        if data is None:
            cleaned = raw.strip()
            # Remove trailing commas before closing braces/brackets
            cleaned = re.sub(r",\s*}", "}", cleaned)
            cleaned = re.sub(r",\s*]", "]", cleaned)
            try:
                data = json.loads(cleaned)
            except (json.JSONDecodeError, TypeError):
                pass

        if data is None:
            logger.error("Failed to parse response as JSON: %s", raw[:300])
            return self._default_output()

        # Extract trust vector
        trust_vector = data.get("trust_vector", {})
        explanation_data = data.get("explanation", {})

        # Handle case where explanation is a string instead of dict
        if isinstance(explanation_data, str):
            explanation_data = {"reasons": [], "summary": explanation_data}

        # Ensure all axes are present with defaults
        axis_names = {a.name for a in self.spec.trust_axes}
        for axis in self.spec.trust_axes:
            if axis.name not in trust_vector:
                trust_vector[axis.name] = 0.0

        # Clamp values to [0, 1] and filter to known axes
        clean_vector = {}
        for k, v in trust_vector.items():
            if k in axis_names:
                try:
                    clean_vector[k] = max(0.0, min(1.0, float(v)))
                except (ValueError, TypeError):
                    clean_vector[k] = 0.0

        # Ensure all axes present after filtering
        for axis in self.spec.trust_axes:
            if axis.name not in clean_vector:
                clean_vector[axis.name] = 0.0

        # Build explanation: ensure reasons reference flagged axes (score > 0.5)
        raw_reasons = explanation_data.get("reasons", [])
        if not isinstance(raw_reasons, list):
            raw_reasons = [str(raw_reasons)]

        flagged_axes = [name for name, score in clean_vector.items() if score > 0.5]

        # Ensure all flagged axes are mentioned in reasons
        mentioned_axes = set()
        valid_reasons = []
        for reason in raw_reasons:
            if isinstance(reason, str) and reason.strip():
                valid_reasons.append(reason.strip())
                # Track which axes are mentioned
                for axis_name in flagged_axes:
                    if axis_name in reason.lower():
                        mentioned_axes.add(axis_name)

        # Add missing flagged axes to reasons
        for axis_name in flagged_axes:
            if axis_name not in mentioned_axes:
                score = clean_vector[axis_name]
                valid_reasons.append(
                    f"{axis_name}: flagged with score {score:.2f}"
                )

        summary = explanation_data.get("summary", "")
        if not isinstance(summary, str) or not summary.strip():
            if flagged_axes:
                summary = f"Flagged axes: {', '.join(flagged_axes)}."
            else:
                summary = "No significant trust concerns detected."

        explanation = Explanation(
            reasons=valid_reasons,
            summary=summary,
        )

        return ScorerOutput(trust_vector=clean_vector, explanation=explanation)

    def _extract_json_object(self, text: str) -> dict | None:
        """Extract the outermost JSON object using brace-matching."""
        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        in_string = False
        escape_next = False

        for i in range(start, len(text)):
            c = text[i]

            if escape_next:
                escape_next = False
                continue

            if c == "\\":
                if in_string:
                    escape_next = True
                continue

            if c == '"':
                in_string = not in_string
                continue

            if in_string:
                continue

            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        return None

        return None

    def _default_output(self) -> ScorerOutput:
        """Return default output when parsing fails."""
        return ScorerOutput(
            trust_vector={a.name: 0.0 for a in self.spec.trust_axes},
            explanation=Explanation(reasons=[], summary="Failed to parse response."),
        )

    # ── Stage 2: Student model training ──────────────────────────────────────

    def fine_tune(self, data_path: str, trainer: TrainingProvider) -> str:
        """Train a dense student model on teacher-generated soft labels.

        Returns the path to the best checkpoint.
        """
        import glob
        import torch
        import torch.nn as nn
        import torch.optim as optim
        from torch.utils.data import Dataset, DataLoader

        # Determine run ID and create output directory
        run_id = os.environ.get("RUN_ID", "run_0")
        checkpoint_dir = os.path.join("runs", run_id, "checkpoints")
        os.makedirs(checkpoint_dir, exist_ok=True)
        best_path = os.path.join(checkpoint_dir, "best.pt")

        # ── Load teacher data ────────────────────────────────────────────
        teacher_files = glob.glob(os.path.join(data_path, "*.json"))
        if not teacher_files:
            teacher_files = glob.glob(os.path.join(data_path, "**", "*.json"), recursive=True)

        axis_names = [a.name for a in self.spec.trust_axes]
        num_axes = len(axis_names)

        samples = []
        for fpath in teacher_files:
            try:
                with open(fpath, "r") as f:
                    record = json.load(f)

                # Extract text features from email chain
                chain_text = ""
                if "emails" in record:
                    for email in record["emails"]:
                        chain_text += email.get("subject", "") + " " + email.get("body", "") + " "
                elif "text" in record:
                    chain_text = record["text"]
                elif "chain" in record:
                    chain_text = str(record["chain"])

                # Extract teacher scores (soft labels)
                trust_vector = record.get("trust_vector", record.get("scores", {}))
                scores = [float(trust_vector.get(name, 0.0)) for name in axis_names]

                # Extract reason tags and escalate flag
                explanation = record.get("explanation", {})
                reason_tags = explanation.get("reasons", [])
                escalate = any(s > 0.7 for s in scores)

                samples.append({
                    "text": chain_text.strip(),
                    "scores": scores,
                    "reason_tags": reason_tags,
                    "escalate": escalate,
                })
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.warning("Skipping malformed teacher file %s: %s", fpath, e)
                continue

        if not samples:
            logger.error("No training samples found in %s", data_path)
            raise RuntimeError(f"No training samples found in {data_path}")

        logger.info("Loaded %d training samples", len(samples))

        # ── Simple text tokenizer (character-level + bigram features) ────
        # Build vocabulary from training data
        vocab = {"<PAD>": 0, "<UNK>": 1}
        for sample in samples:
            for word in sample["text"].lower().split():
                if word not in vocab and len(vocab) < 50000:
                    vocab[word] = len(vocab)

        max_seq_len = 512

        def tokenize(text: str) -> list[int]:
            tokens = []
            for word in text.lower().split()[:max_seq_len]:
                tokens.append(vocab.get(word, 1))
            # Pad
            while len(tokens) < max_seq_len:
                tokens.append(0)
            return tokens[:max_seq_len]

        # ── Dataset ──────────────────────────────────────────────────────
        class TrustDataset(Dataset):
            def __init__(self, samples_list):
                self.samples = samples_list

            def __len__(self):
                return len(self.samples)

            def __getitem__(self, idx):
                s = self.samples[idx]
                input_ids = torch.tensor(tokenize(s["text"]), dtype=torch.long)
                scores = torch.tensor(s["scores"], dtype=torch.float32)
                escalate = torch.tensor(1.0 if s["escalate"] else 0.0, dtype=torch.float32)
                return input_ids, scores, escalate

        # ── Dense Student Model ──────────────────────────────────────────
        class DenseStudentModel(nn.Module):
            def __init__(self, vocab_size, embed_dim, hidden_dim, num_axes_out,
                         num_layers=3, dropout=0.1):
                super().__init__()
                self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
                self.positional = nn.Embedding(max_seq_len, embed_dim)

                # Transformer encoder layers
                encoder_layer = nn.TransformerEncoderLayer(
                    d_model=embed_dim,
                    nhead=4,
                    dim_feedforward=hidden_dim,
                    dropout=dropout,
                    batch_first=True,
                )
                self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)

                # Trust vector head
                self.trust_head = nn.Sequential(
                    nn.Linear(embed_dim, hidden_dim),
                    nn.ReLU(),
                    nn.Dropout(dropout),
                    nn.Linear(hidden_dim, num_axes_out),
                    nn.Sigmoid(),
                )

                # Escalation head
                self.escalate_head = nn.Sequential(
                    nn.Linear(embed_dim, hidden_dim // 2),
                    nn.ReLU(),
                    nn.Dropout(dropout),
                    nn.Linear(hidden_dim // 2, 1),
                    nn.Sigmoid(),
                )

                # Reason tag head (multi-label: one per axis)
                self.reason_head = nn.Sequential(
                    nn.Linear(embed_dim, hidden_dim),
                    nn.ReLU(),
                    nn.Dropout(dropout),
                    nn.Linear(hidden_dim, num_axes_out),
                    nn.Sigmoid(),
                )

            def forward(self, input_ids):
                B, L = input_ids.shape
                positions = torch.arange(L, device=input_ids.device).unsqueeze(0).expand(B, L)

                x = self.embedding(input_ids) + self.positional(positions)

                # Create padding mask
                padding_mask = (input_ids == 0)
                x = self.encoder(x, src_key_padding_mask=padding_mask)

                # Pool: mean of non-padded tokens
                mask = (~padding_mask).unsqueeze(-1).float()
                pooled = (x * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1.0)

                trust_vector = self.trust_head(pooled)
                escalate = self.escalate_head(pooled).squeeze(-1)
                reason_tags = self.reason_head(pooled)

                return trust_vector, escalate, reason_tags

        # ── Training configuration ───────────────────────────────────────
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        vocab_size = len(vocab)
        embed_dim = 128
        hidden_dim = 256
        num_layers = 3
        dropout = 0.1
        batch_size = 32
        learning_rate = 3e-4
        num_epochs = 50
        patience = 10

        model = DenseStudentModel(
            vocab_size=vocab_size,
            embed_dim=embed_dim,
            hidden_dim=hidden_dim,
            num_axes_out=num_axes,
            num_layers=num_layers,
            dropout=dropout,
        ).to(device)

        # Count parameters
        total_params = sum(p.numel() for p in model.parameters())
        logger.info("Student model has %.2fM parameters", total_params / 1e6)
        if total_params > 200e6:
            raise ValueError(
                f"Model has {total_params / 1e6:.1f}M params, exceeding 200M limit"
            )

        # Loss weights per axis (from spec)
        axis_weights = torch.tensor(
            [a.weight for a in self.spec.trust_axes], dtype=torch.float32
        ).to(device)
        # Normalize weights
        axis_weights = axis_weights / axis_weights.sum() * num_axes

        # Split into train/val
        val_size = max(1, len(samples) // 10)
        train_samples = samples[val_size:]
        val_samples = samples[:val_size]

        train_loader = DataLoader(
            TrustDataset(train_samples), batch_size=batch_size, shuffle=True,
            num_workers=0, drop_last=False,
        )
        val_loader = DataLoader(
            TrustDataset(val_samples), batch_size=batch_size, shuffle=False,
            num_workers=0, drop_last=False,
        )

        optimizer = optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)
        scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=num_epochs)

        mse_loss = nn.MSELoss(reduction="none")
        bce_loss = nn.BCELoss()

        # ── Training loop ────────────────────────────────────────────────
        best_val_loss = float("inf")
        epochs_no_improve = 0

        for epoch in range(num_epochs):
            model.train()
            train_loss_sum = 0.0
            train_count = 0

            for input_ids, scores, escalate in train_loader:
                input_ids = input_ids.to(device)
                scores = scores.to(device)
                escalate = escalate.to(device)

                pred_trust, pred_escalate, pred_reasons = model(input_ids)

                # Weighted MSE loss for trust vector
                trust_loss = (mse_loss(pred_trust, scores) * axis_weights).mean()

                # Escalation loss
                esc_loss = bce_loss(pred_escalate, escalate)

                # Reason tag auxiliary loss (flag axes > 0.5)
                reason_targets = (scores > 0.5).float()
                reason_loss = bce_loss(pred_reasons, reason_targets)

                loss = trust_loss + 0.3 * esc_loss + 0.2 * reason_loss

                optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()

                train_loss_sum += loss.item() * input_ids.size(0)
                train_count += input_ids.size(0)

            scheduler.step()

            # Validation
            model.eval()
            val_loss_sum = 0.0
            val_count = 0
            with torch.no_grad():
                for input_ids, scores, escalate in val_loader:
                    input_ids = input_ids.to(device)
                    scores = scores.to(device)
                    escalate = escalate.to(device)

                    pred_trust, pred_escalate, pred_reasons = model(input_ids)
                    trust_loss = (mse_loss(pred_trust, scores) * axis_weights).mean()
                    esc_loss = bce_loss(pred_escalate, escalate)
                    reason_targets = (scores > 0.5).float()
                    reason_loss = bce_loss(pred_reasons, reason_targets)
                    loss = trust_loss + 0.3 * esc_loss + 0.2 * reason_loss

                    val_loss_sum += loss.item() * input_ids.size(0)
                    val_count += input_ids.size(0)

            avg_train = train_loss_sum / max(train_count, 1)
            avg_val = val_loss_sum / max(val_count, 1)
            logger.info(
                "Epoch %d/%d  train_loss=%.4f  val_loss=%.4f  lr=%.6f",
                epoch + 1, num_epochs, avg_train, avg_val,
                scheduler.get_last_lr()[0],
            )

            if avg_val < best_val_loss:
                best_val_loss = avg_val
                epochs_no_improve = 0
                # Save best checkpoint
                checkpoint = {
                    "model_state_dict": model.state_dict(),
                    "vocab": vocab,
                    "axis_names": axis_names,
                    "config": {
                        "vocab_size": vocab_size,
                        "embed_dim": embed_dim,
                        "hidden_dim": hidden_dim,
                        "num_axes": num_axes,
                        "num_layers": num_layers,
                        "dropout": dropout,
                        "max_seq_len": max_seq_len,
                    },
                    "epoch": epoch + 1,
                    "val_loss": best_val_loss,
                    "total_params": total_params,
                }
                torch.save(checkpoint, best_path)
                logger.info("Saved best checkpoint at epoch %d (val_loss=%.4f)", epoch + 1, best_val_loss)
            else:
                epochs_no_improve += 1
                if epochs_no_improve >= patience:
                    logger.info("Early stopping at epoch %d", epoch + 1)
                    break

        logger.info("Training complete. Best val_loss=%.4f. Checkpoint: %s", best_val_loss, best_path)
        return best_path

    def load_fine_tuned(self, checkpoint: str) -> None:
        """Load a trained student checkpoint for inference."""
        import torch
        import torch.nn as nn

        ckpt = torch.load(checkpoint, map_location="cpu")
        config = ckpt["config"]

        self._student_vocab = ckpt["vocab"]
        self._student_axis_names = ckpt["axis_names"]
        self._student_config = config

        # Rebuild model
        class DenseStudentModel(nn.Module):
            def __init__(self, vocab_size, embed_dim, hidden_dim, num_axes_out,
                         num_layers=3, dropout=0.1, max_seq_len=512):
                super().__init__()
                self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
                self.positional = nn.Embedding(max_seq_len, embed_dim)

                encoder_layer = nn.TransformerEncoderLayer(
                    d_model=embed_dim,
                    nhead=4,
                    dim_feedforward=hidden_dim,
                    dropout=dropout,
                    batch_first=True,
                )
                self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)

                self.trust_head = nn.Sequential(
                    nn.Linear(embed_dim, hidden_dim),
                    nn.ReLU(),
                    nn.Dropout(dropout),
                    nn.Linear(hidden_dim, num_axes_out),
                    nn.Sigmoid(),
                )
                self.escalate_head = nn.Sequential(
                    nn.Linear(embed_dim, hidden_dim // 2),
                    nn.ReLU(),
                    nn.Dropout(dropout),
                    nn.Linear(hidden_dim // 2, 1),
                    nn.Sigmoid(),
                )
                self.reason_head = nn.Sequential(
                    nn.Linear(embed_dim, hidden_dim),
                    nn.ReLU(),
                    nn.Dropout(dropout),
                    nn.Linear(hidden_dim, num_axes_out),
                    nn.Sigmoid(),
                )
                self.max_seq_len = max_seq_len

            def forward(self, input_ids):
                B, L = input_ids.shape
                positions = torch.arange(L, device=input_ids.device).unsqueeze(0).expand(B, L)
                x = self.embedding(input_ids) + self.positional(positions)
                padding_mask = (input_ids == 0)
                x = self.encoder(x, src_key_padding_mask=padding_mask)
                mask = (~padding_mask).unsqueeze(-1).float()
                pooled = (x * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1.0)
                trust_vector = self.trust_head(pooled)
                escalate = self.escalate_head(pooled).squeeze(-1)
                reason_tags = self.reason_head(pooled)
                return trust_vector, escalate, reason_tags

        model = DenseStudentModel(
            vocab_size=config["vocab_size"],
            embed_dim=config["embed_dim"],
            hidden_dim=config["hidden_dim"],
            num_axes_out=config["num_axes"],
            num_layers=config["num_layers"],
            dropout=config["dropout"],
            max_seq_len=config["max_seq_len"],
        )
        model.load_state_dict(ckpt["model_state_dict"])
        model.eval()
        self._student_model = model
        logger.info("Loaded student model from %s", checkpoint)
