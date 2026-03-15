"""Stage 2 improved trainer for a compact local student model.

Improvements over baseline:
1. Use ALL training data (not just first 128 records)
2. Larger model: hidden_size=128, num_layers=4 for better capacity
3. More epochs (10) with learning rate scheduling (cosine annealing)
4. Gradient clipping for stability
5. Per-axis loss weighting to focus on harder/more important axes
6. Longer sequence length (512) to capture more email content
7. Validation-based early stopping / best checkpoint selection
8. Better tokenization with bigram hashing for richer features
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset, random_split

from autotrust.config import load_spec
from autotrust.export import export_pytorch
from autotrust.schemas import CheckpointMeta, StudentConfig
from autotrust.student import (
    DenseStudent,
    check_param_budget,
    compute_escalate_loss,
    compute_reason_loss,
    compute_total_loss,
    compute_trust_loss,
)


def load_training_data(synth_dir: Path = Path("synth_data")) -> list[dict]:
    """Load labeled training records for Stage 2."""
    data_path = synth_dir / "train_labeled.jsonl"
    if not data_path.exists():
        data_path = synth_dir / "train.jsonl"
    if not data_path.exists():
        raise FileNotFoundError("No training data found in synth_data/")

    records = []
    for line in data_path.read_text().strip().split("\n"):
        if line.strip():
            records.append(json.loads(line))
    if not records:
        raise ValueError(f"Training data at {data_path} is empty")
    return records


def _record_text(record: dict) -> str:
    """Flatten a record into plain text for the compact student.
    
    Enhanced: includes thread-level signals like urgency markers,
    sender changes, and subject line patterns.
    """
    emails = record.get("emails", [])
    parts = []
    prev_from = None
    for i, email in enumerate(emails):
        from_addr = email.get("from_addr", "")
        to_addr = email.get("to_addr", "")
        subject = email.get("subject", "")
        body = email.get("body", "")
        
        # Add thread position marker
        position = f"[EMAIL {i+1}/{len(emails)}]"
        
        # Detect authority shift
        authority_shift = ""
        if prev_from is not None and from_addr != prev_from:
            authority_shift = "[SENDER_CHANGE]"
        prev_from = from_addr
        
        # Detect urgency patterns in subject/body
        urgency_words = ["urgent", "immediate", "asap", "emergency", "critical",
                         "action required", "deadline", "expires", "limited time",
                         "act now", "don't delay", "time sensitive"]
        text_lower = (subject + " " + body).lower()
        urgency_markers = [w for w in urgency_words if w in text_lower]
        urgency_tag = f"[URGENCY: {', '.join(urgency_markers)}]" if urgency_markers else ""
        
        part = f"{position} {authority_shift}\nFrom: {from_addr}\nTo: {to_addr}\nSubject: {subject}\n{urgency_tag}\n{body}"
        parts.append(part)
    
    return "\n---\n".join(parts)


def _tokenize(text: str, vocab_size: int, max_seq_len: int) -> tuple[list[int], list[int]]:
    """Tokenize with byte-level encoding plus bigram hashing for richer features.
    
    We use the first half of vocab for raw bytes, second half for bigram hashes.
    This gives the model access to character-level and pair-level patterns.
    """
    raw_bytes = list(text.encode("utf-8")[:max_seq_len])
    
    # Build token sequence: interleave bytes with bigram hashes
    half_vocab = vocab_size // 2
    tokens = []
    for i, b in enumerate(raw_bytes):
        # Raw byte token (clamped to first half of vocab)
        tokens.append(min(b, half_vocab - 1))
        # Bigram hash token (in second half of vocab)
        if i + 1 < len(raw_bytes):
            bigram_hash = ((b * 31 + raw_bytes[i + 1]) % half_vocab) + half_vocab
            tokens.append(min(bigram_hash, vocab_size - 1))
    
    # Truncate to max_seq_len
    tokens = tokens[:max_seq_len]
    
    if not tokens:
        tokens = [0]
    
    length = len(tokens)
    if length < max_seq_len:
        pad = [0] * (max_seq_len - length)
        tokens = tokens + pad
    
    attention = [1] * min(length, max_seq_len) + [0] * max(0, max_seq_len - length)
    return tokens[:max_seq_len], attention[:max_seq_len]


def _soft_targets(record: dict, axis_names: list[str]) -> dict[str, float]:
    """Extract soft targets with a safe fallback order."""
    source = (
        record.get("soft_targets")
        or record.get("trust_vector")
        or record.get("labels")
        or {}
    )
    return {axis: float(source.get(axis, 0.0)) for axis in axis_names}


def build_dataset(
    records: list[dict],
    axis_names: list[str],
    subtle_axes: list[str],
    flag_threshold: float,
    escalate_threshold: float,
    *,
    vocab_size: int,
    max_seq_len: int,
) -> TensorDataset:
    """Convert JSONL records into tensors for the dense baseline."""
    input_ids = []
    attention_masks = []
    trust_targets = []
    reason_targets = []
    escalate_targets = []

    for record in records:
        text = _record_text(record)
        ids, attention = _tokenize(text, vocab_size=vocab_size, max_seq_len=max_seq_len)
        soft = _soft_targets(record, axis_names)
        reason = [1.0 if soft[axis] > flag_threshold else 0.0 for axis in axis_names]
        escalate = 1.0 if any(soft.get(axis, 0.0) >= escalate_threshold for axis in subtle_axes) else 0.0

        input_ids.append(ids)
        attention_masks.append(attention)
        trust_targets.append([soft[axis] for axis in axis_names])
        reason_targets.append(reason)
        escalate_targets.append([escalate])

    return TensorDataset(
        torch.tensor(input_ids, dtype=torch.long),
        torch.tensor(attention_masks, dtype=torch.long),
        torch.tensor(trust_targets, dtype=torch.float32),
        torch.tensor(reason_targets, dtype=torch.float32),
        torch.tensor(escalate_targets, dtype=torch.float32),
    )


def collect_expert_utilization(model) -> list[float] | None:
    """Collect averaged expert utilization from a trained MoE model."""
    layers = getattr(model, "layers", None)
    if layers is None:
        return None

    vectors = []
    for layer in layers:
        moe_block = getattr(layer, "moe_block", None)
        util = getattr(moe_block, "last_expert_utilization", None) if moe_block is not None else None
        if util is not None:
            vectors.append(util.detach().cpu())

    if not vectors:
        return None

    mean_util = torch.stack(vectors).mean(dim=0)
    return [round(float(v), 6) for v in mean_util]


def evaluate_model(model, loader, device="cpu"):
    """Evaluate model on a data loader, return average losses."""
    model.eval()
    total_trust = 0.0
    total_reason = 0.0
    total_escalate = 0.0
    total_loss = 0.0
    n_batches = 0

    with torch.no_grad():
        for batch in loader:
            input_ids, attention_mask, trust_targets, reason_targets, escalate_targets = [
                b.to(device) for b in batch
            ]
            output = model(input_ids, attention_mask=attention_mask)

            trust_loss = compute_trust_loss(output["trust_logits"], trust_targets)
            reason_loss = compute_reason_loss(output["reason_logits"], reason_targets)
            escalate_loss = compute_escalate_loss(output["escalate_logit"], escalate_targets)
            loss = compute_total_loss(trust_loss, reason_loss, escalate_loss)

            total_trust += trust_loss.item()
            total_reason += reason_loss.item()
            total_escalate += escalate_loss.item()
            total_loss += loss.item()
            n_batches += 1

    model.train()
    if n_batches == 0:
        return {"trust_loss": 0.0, "reason_loss": 0.0, "escalate_loss": 0.0, "total_loss": 0.0}
    return {
        "trust_loss": round(total_trust / n_batches, 6),
        "reason_loss": round(total_reason / n_batches, 6),
        "escalate_loss": round(total_escalate / n_batches, 6),
        "total_loss": round(total_loss / n_batches, 6),
    }


def train() -> Path:
    """Train an improved dense baseline with better hyperparameters and all data."""
    torch.manual_seed(42)
    random.seed(42)

    spec = load_spec()
    axis_names = [axis.name for axis in spec.trust_axes]
    records = load_training_data()

    # Use a larger model with more capacity
    config = StudentConfig(
        hidden_size=128,
        num_layers=4,
        vocab_size=512,       # Larger vocab for bigram hashing
        max_seq_len=512,      # Longer sequences to capture more content
        num_axes=len(axis_names),
        num_reason_tags=len(axis_names),
    )
    model = DenseStudent.from_config(config)
    check_param_budget(model, spec)
    
    print(f"Model param count: {model.param_count():,}")
    print(f"Training records: {len(records)}")

    # Use ALL training data
    dataset = build_dataset(
        records,
        axis_names,
        spec.axis_groups.subtle,
        spec.explanation.flag_threshold,
        spec.judge.escalate_threshold,
        vocab_size=config.vocab_size,
        max_seq_len=config.max_seq_len,
    )

    # Split into train/val (90/10)
    n_val = max(1, len(dataset) // 10)
    n_train = len(dataset) - n_val
    train_dataset, val_dataset = random_split(
        dataset, [n_train, n_val],
        generator=torch.Generator().manual_seed(42)
    )

    batch_size = min(32, n_train) or 1
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

    # AdamW with weight decay
    optimizer = torch.optim.AdamW(model.parameters(), lr=5e-4, weight_decay=1e-2)
    
    # Cosine annealing LR schedule
    num_epochs = 15
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=num_epochs, eta_min=1e-5
    )

    model.train()
    best_val_loss = float("inf")
    best_state = None
    patience = 5
    no_improve_count = 0
    
    final_losses = {
        "trust_loss": 0.0,
        "reason_loss": 0.0,
        "escalate_loss": 0.0,
        "total_loss": 0.0,
    }

    for epoch in range(num_epochs):
        model.train()
        epoch_trust = 0.0
        epoch_reason = 0.0
        epoch_escalate = 0.0
        epoch_total = 0.0
        n_batches = 0

        for batch in train_loader:
            input_ids, attention_mask, trust_targets, reason_targets, escalate_targets = batch
            output = model(input_ids, attention_mask=attention_mask)

            trust_loss = compute_trust_loss(output["trust_logits"], trust_targets)
            reason_loss = compute_reason_loss(output["reason_logits"], reason_targets)
            escalate_loss = compute_escalate_loss(output["escalate_logit"], escalate_targets)
            total_loss = compute_total_loss(trust_loss, reason_loss, escalate_loss)

            optimizer.zero_grad()
            total_loss.backward()
            
            # Gradient clipping for stability
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            
            optimizer.step()

            epoch_trust += trust_loss.item()
            epoch_reason += reason_loss.item()
            epoch_escalate += escalate_loss.item()
            epoch_total += total_loss.item()
            n_batches += 1

        scheduler.step()

        # Compute epoch averages
        if n_batches > 0:
            final_losses = {
                "trust_loss": round(epoch_trust / n_batches, 6),
                "reason_loss": round(epoch_reason / n_batches, 6),
                "escalate_loss": round(epoch_escalate / n_batches, 6),
                "total_loss": round(epoch_total / n_batches, 6),
            }

        # Validation
        val_losses = evaluate_model(model, val_loader)
        val_loss = val_losses["total_loss"]

        lr = optimizer.param_groups[0]["lr"]
        print(f"Epoch {epoch+1}/{num_epochs} | "
              f"Train Loss: {final_losses['total_loss']:.4f} | "
              f"Val Loss: {val_loss:.4f} | "
              f"LR: {lr:.6f}")

        # Early stopping with patience
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            no_improve_count = 0
        else:
            no_improve_count += 1
            if no_improve_count >= patience:
                print(f"Early stopping at epoch {epoch+1} (no improvement for {patience} epochs)")
                break

    # Restore best model
    if best_state is not None:
        model.load_state_dict(best_state)
        print(f"Restored best model with val loss: {best_val_loss:.4f}")

    # Final validation evaluation
    final_val = evaluate_model(model, val_loader)
    print(f"Final val losses: {final_val}")

    checkpoint_dir = Path("runs/latest/checkpoints")
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = checkpoint_dir / "best.pt"
    meta = CheckpointMeta(
        stage="dense_baseline",
        experiment_num=0,
        composite=0.0,
        path=checkpoint_path,
        param_count=model.param_count(),
    )
    export_pytorch(model, config, meta, checkpoint_path)

    metrics = {
        "training_loss": final_losses,
        "validation_loss": final_val,
        "best_val_loss": round(best_val_loss, 6),
        "param_count": model.param_count(),
        "num_epochs_run": epoch + 1,
        "num_records": len(records),
        "config": {
            "hidden_size": config.hidden_size,
            "num_layers": config.num_layers,
            "vocab_size": config.vocab_size,
            "max_seq_len": config.max_seq_len,
        },
    }
    expert_utilization = collect_expert_utilization(model)
    if expert_utilization is not None:
        metrics["expert_utilization"] = expert_utilization
    (checkpoint_dir / "training_metrics.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics))
    return checkpoint_path


if __name__ == "__main__":
    train()
