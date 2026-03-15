"""Stage 2 baseline trainer for a compact local student model.

This file is copied into train.py when the loop transitions from Stage 1 to
Stage 2. It provides a minimal but real dense-baseline trainer so the repo can
run end to end before any architecture search begins.
"""

from __future__ import annotations

import json
from pathlib import Path

import torch
from torch.utils.data import DataLoader, TensorDataset

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
    """Flatten a record into plain text for the compact student."""
    emails = record.get("emails", [])
    return "\n".join(
        f"From: {email.get('from_addr', '')}\n"
        f"To: {email.get('to_addr', '')}\n"
        f"Subject: {email.get('subject', '')}\n"
        f"{email.get('body', '')}"
        for email in emails
    )


def _tokenize(text: str, vocab_size: int, max_seq_len: int) -> tuple[list[int], list[int]]:
    """Tokenize with a small byte-level encoding and pad/truncate."""
    tokens = [min(b, vocab_size - 1) for b in text.encode("utf-8")[:max_seq_len]]
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


def train() -> Path:
    """Train a compact dense baseline and emit checkpoint + training metrics."""
    torch.manual_seed(0)

    spec = load_spec()
    axis_names = [axis.name for axis in spec.trust_axes]
    records = load_training_data()

    config = StudentConfig(
        hidden_size=64,
        num_layers=2,
        vocab_size=256,
        max_seq_len=256,
        num_axes=len(axis_names),
        num_reason_tags=len(axis_names),
    )
    model = DenseStudent.from_config(config)
    check_param_budget(model, spec)

    dataset = build_dataset(
        records[:128],
        axis_names,
        spec.axis_groups.subtle,
        spec.explanation.flag_threshold,
        spec.judge.escalate_threshold,
        vocab_size=config.vocab_size,
        max_seq_len=config.max_seq_len,
    )
    batch_size = min(16, len(dataset)) or 1
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4)

    model.train()
    final_losses = {
        "trust_loss": 0.0,
        "reason_loss": 0.0,
        "escalate_loss": 0.0,
        "total_loss": 0.0,
    }
    for _epoch in range(2):
        for batch in loader:
            input_ids, attention_mask, trust_targets, reason_targets, escalate_targets = batch
            output = model(input_ids, attention_mask=attention_mask)

            trust_loss = compute_trust_loss(output["trust_logits"], trust_targets)
            reason_loss = compute_reason_loss(output["reason_logits"], reason_targets)
            escalate_loss = compute_escalate_loss(output["escalate_logit"], escalate_targets)
            total_loss = compute_total_loss(trust_loss, reason_loss, escalate_loss)

            optimizer.zero_grad()
            total_loss.backward()
            optimizer.step()

            final_losses = {
                "trust_loss": round(float(trust_loss.item()), 6),
                "reason_loss": round(float(reason_loss.item()), 6),
                "escalate_loss": round(float(escalate_loss.item()), 6),
                "total_loss": round(float(total_loss.item()), 6),
            }

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
        "param_count": model.param_count(),
    }
    expert_utilization = collect_expert_utilization(model)
    if expert_utilization is not None:
        metrics["expert_utilization"] = expert_utilization
    (checkpoint_dir / "training_metrics.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics))
    return checkpoint_path


if __name__ == "__main__":
    train()
