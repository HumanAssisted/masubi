"""Stage 2: Student model training script.

This train.py is automatically generated at the Stage 1 -> Stage 2 transition.
The agent (Sonnet) will modify this file to optimize the student model.

Usage: uv run python train.py
Output: saves checkpoint to runs/<run_id>/checkpoints/best.pt
"""

import json
import sys
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from autotrust.student import DenseStudent, compute_trust_loss, compute_reason_loss, compute_escalate_loss, compute_total_loss
from autotrust.export import export_pytorch
from autotrust.schemas import StudentConfig, CheckpointMeta


def load_training_data(synth_dir: Path = Path("synth_data")):
    """Load soft-labeled training data from synth_data/."""
    data_path = synth_dir / "train_labeled.jsonl"
    if not data_path.exists():
        data_path = synth_dir / "train.jsonl"
    if not data_path.exists():
        print("No training data found in synth_data/")
        sys.exit(1)
    records = []
    for line in data_path.read_text().strip().split("\n"):
        if line:
            records.append(json.loads(line))
    return records


def train():
    """Train the student model."""
    config = StudentConfig(
        hidden_size=256,
        num_layers=6,
        vocab_size=50000,
        max_seq_len=512,
        num_axes=10,
        num_reason_tags=20,
    )
    model = DenseStudent.from_config(config)

    # TODO: Agent will customize this training loop
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)

    # Save initial checkpoint
    checkpoint_dir = Path("runs/latest/checkpoints")
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    meta = CheckpointMeta(
        stage="dense_baseline",
        experiment_num=0,
        composite=0.0,
        path=checkpoint_dir / "best.pt",
        param_count=model.param_count(),
    )
    export_pytorch(model, config, meta, checkpoint_dir / "best.pt")
    print(f"Checkpoint saved to {checkpoint_dir / 'best.pt'}")


if __name__ == "__main__":
    train()
