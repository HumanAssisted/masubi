"""Student model for Stage 2 training.

Dense baseline transformer model that scores email text across trust axes,
produces explanation reason tags, and outputs an escalation flag.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor

from autotrust.schemas import MoEConfig, StudentConfig, StudentOutput, validate_moe_config



class DenseStudent(nn.Module):
    """Dense transformer student model for email trust scoring.

    Takes tokenized email text and produces:
    - trust_logits: per-axis trust scores (num_axes)
    - reason_logits: multi-label reason tag predictions (num_reason_tags)
    - escalate_logit: binary escalation flag (1)
    """

    def __init__(self, config: StudentConfig):
        super().__init__()
        self.config = config

        # Embedding
        self.embedding = nn.Embedding(config.vocab_size, config.hidden_size)
        self.pos_encoding = nn.Embedding(config.max_seq_len, config.hidden_size)

        # Transformer encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=config.hidden_size,
            nhead=max(1, config.hidden_size // 64),
            dim_feedforward=config.hidden_size * 4,
            batch_first=True,
            norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=config.num_layers)

        # Output heads
        self.trust_head = nn.Linear(config.hidden_size, config.num_axes)
        self.reason_head = nn.Linear(config.hidden_size, config.num_reason_tags)
        self.escalate_head = nn.Linear(config.hidden_size, 1)

        self._init_weights()

    def _init_weights(self):
        """Initialize weights with small values for stable training."""
        for p in self.parameters():
            if p.dim() > 1:
                nn.init.xavier_uniform_(p)

    def forward(
        self, input_ids: Tensor, attention_mask: Tensor | None = None
    ) -> dict[str, Tensor]:
        """Forward pass.

        Args:
            input_ids: (batch, seq_len) token IDs
            attention_mask: (batch, seq_len) optional mask (1 = attend, 0 = ignore)

        Returns:
            Dict with trust_logits, reason_logits, escalate_logit tensors.
        """
        batch_size, seq_len = input_ids.shape

        # Clamp positions to max_seq_len
        positions = torch.arange(seq_len, device=input_ids.device).unsqueeze(0)
        positions = positions.clamp(max=self.config.max_seq_len - 1)

        # Embed tokens + positions
        x = self.embedding(input_ids) + self.pos_encoding(positions)

        # Build src_key_padding_mask if attention_mask provided
        src_key_padding_mask = None
        if attention_mask is not None:
            src_key_padding_mask = attention_mask == 0  # True = ignore

        # Transformer encoder
        x = self.encoder(x, src_key_padding_mask=src_key_padding_mask)

        # Pool: mean over sequence dimension
        if attention_mask is not None:
            mask_expanded = attention_mask.unsqueeze(-1).float()
            x = (x * mask_expanded).sum(dim=1) / mask_expanded.sum(dim=1).clamp(min=1)
        else:
            x = x.mean(dim=1)

        # Output heads
        trust_logits = self.trust_head(x)
        reason_logits = self.reason_head(x)
        escalate_logit = self.escalate_head(x)

        return {
            "trust_logits": trust_logits,
            "reason_logits": reason_logits,
            "escalate_logit": escalate_logit,
        }

    @classmethod
    def from_config(cls, config: StudentConfig) -> DenseStudent:
        """Create a DenseStudent model from a StudentConfig."""
        return cls(config)

    def param_count(self) -> int:
        """Total number of trainable parameters."""
        return sum(p.numel() for p in self.parameters())


# ---------------------------------------------------------------------------
# Loss functions
# ---------------------------------------------------------------------------


def compute_trust_loss(logits: Tensor, soft_targets: Tensor) -> Tensor:
    """MSE loss between predicted trust scores and teacher soft labels.

    Uses MSE rather than KL divergence (as originally specified in the TRD)
    because trust axes are independent scores in [0, 1], not a probability
    distribution that sums to 1. MSE is the standard regression loss for
    independent per-axis soft label matching, while KL divergence assumes
    a categorical distribution which does not apply here.

    Args:
        logits: (batch, num_axes) raw model output
        soft_targets: (batch, num_axes) teacher soft labels in [0, 1]

    Returns:
        Scalar loss tensor.
    """
    predictions = torch.sigmoid(logits)
    return F.mse_loss(predictions, soft_targets)


def compute_reason_loss(logits: Tensor, tag_targets: Tensor) -> Tensor:
    """Binary cross-entropy for multi-label reason tag prediction.

    Args:
        logits: (batch, num_reason_tags) raw model output
        tag_targets: (batch, num_reason_tags) binary targets

    Returns:
        Scalar loss tensor.
    """
    return F.binary_cross_entropy_with_logits(logits, tag_targets)


def compute_escalate_loss(logit: Tensor, target: Tensor) -> Tensor:
    """Binary cross-entropy for escalation prediction.

    Args:
        logit: (batch, 1) raw model output
        target: (batch, 1) binary target

    Returns:
        Scalar loss tensor.
    """
    return F.binary_cross_entropy_with_logits(logit, target)


def compute_total_loss(
    trust_loss: Tensor,
    reason_loss: Tensor,
    escalate_loss: Tensor,
    trust_weight: float = 1.0,
    reason_weight: float = 0.3,
    escalate_weight: float = 0.2,
) -> Tensor:
    """Weighted combination of all three losses.

    Args:
        trust_loss: scalar trust axis loss
        reason_loss: scalar reason tag loss
        escalate_loss: scalar escalation loss
        trust_weight: weight for trust loss
        reason_weight: weight for reason loss
        escalate_weight: weight for escalation loss

    Returns:
        Scalar combined loss tensor.
    """
    return (
        trust_weight * trust_loss
        + reason_weight * reason_loss
        + escalate_weight * escalate_loss
    )


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------


def predict(
    model: DenseStudent,
    input_ids: Tensor,
    axis_names: list[str],
    reason_tag_names: list[str],
    threshold: float = 0.5,
) -> StudentOutput:
    """Run inference and convert logits to StudentOutput schema.

    Args:
        model: trained DenseStudent (or MoEStudent) model
        input_ids: (1, seq_len) tokenized input
        axis_names: list of trust axis names matching model output order
        reason_tag_names: list of reason tag names matching model output order
        threshold: classification threshold for binary outputs

    Returns:
        StudentOutput with trust_vector, reason_tags, escalate.
    """
    model.eval()
    with torch.no_grad():
        output = model(input_ids)

    trust_probs = torch.sigmoid(output["trust_logits"]).squeeze(0)
    reason_probs = torch.sigmoid(output["reason_logits"]).squeeze(0)
    escalate_prob = torch.sigmoid(output["escalate_logit"]).squeeze()

    trust_vector = {
        name: round(trust_probs[i].item(), 4)
        for i, name in enumerate(axis_names)
    }

    reason_tags = [
        reason_tag_names[i]
        for i in range(len(reason_tag_names))
        if reason_probs[i].item() >= threshold
    ]

    return StudentOutput(
        trust_vector=trust_vector,
        reason_tags=reason_tags,
        escalate=escalate_prob.item() >= threshold,
    )


# ---------------------------------------------------------------------------
# MoE (Mixture of Experts) extension
# ---------------------------------------------------------------------------


class MoEBlock(nn.Module):
    """Mixture-of-Experts feed-forward block replacing standard FFN.

    Supports three routing strategies:
    - top_k: standard softmax + top-k selection
    - noisy_top_k: Gaussian noise before top-k (Shazeer et al.)
    - expert_choice: experts choose tokens (Zhou et al.)
    """

    def __init__(
        self,
        hidden_size: int,
        intermediate_size: int,
        num_experts: int,
        top_k: int,
        capacity_factor: float = 1.0,
        routing_strategy: str = "top_k",
    ):
        super().__init__()
        self.hidden_size = hidden_size
        self.num_experts = num_experts
        self.top_k = top_k
        self.capacity_factor = capacity_factor
        self.routing_strategy = routing_strategy
        self.last_expert_utilization: Tensor | None = None

        # Router
        self.router = nn.Linear(hidden_size, num_experts, bias=False)

        # Experts: each is a simple FFN (up-proj -> GELU -> down-proj)
        self.experts = nn.ModuleList([
            nn.Sequential(
                nn.Linear(hidden_size, intermediate_size),
                nn.GELU(),
                nn.Linear(intermediate_size, hidden_size),
            )
            for _ in range(num_experts)
        ])

        # Noise for noisy_top_k
        if routing_strategy == "noisy_top_k":
            self.noise_weight = nn.Linear(hidden_size, num_experts, bias=False)

    def forward(self, x: Tensor) -> tuple[Tensor, Tensor]:
        """Forward pass through MoE block.

        Args:
            x: (batch, seq_len, hidden_size)

        Returns:
            Tuple of (output, auxiliary_load_balance_loss).
        """
        batch_size, seq_len, hidden_size = x.shape
        # Flatten to (batch * seq_len, hidden_size)
        flat_x = x.view(-1, hidden_size)

        # Compute router logits
        router_logits = self.router(flat_x)  # (num_tokens, num_experts)

        if self.routing_strategy == "noisy_top_k":
            noise = torch.randn_like(router_logits) * F.softplus(self.noise_weight(flat_x))
            router_logits = router_logits + noise

        # Compute routing weights
        router_probs = F.softmax(router_logits, dim=-1)  # (num_tokens, num_experts)
        self.last_expert_utilization = self._compute_expert_utilization(router_probs)

        if self.routing_strategy == "expert_choice":
            output, aux_loss = self._expert_choice_forward(flat_x, router_probs)
        else:
            output, aux_loss = self._top_k_forward(flat_x, router_probs)

        return output.view(batch_size, seq_len, hidden_size), aux_loss

    def _top_k_forward(
        self, flat_x: Tensor, router_probs: Tensor
    ) -> tuple[Tensor, Tensor]:
        """Standard top-k routing."""
        # Select top-k experts per token
        top_k_probs, top_k_indices = torch.topk(router_probs, self.top_k, dim=-1)
        top_k_probs = top_k_probs / top_k_probs.sum(dim=-1, keepdim=True)  # renormalize

        # Compute expert outputs and combine
        output = torch.zeros_like(flat_x)
        for k in range(self.top_k):
            expert_indices = top_k_indices[:, k]  # (num_tokens,)
            expert_weights = top_k_probs[:, k]    # (num_tokens,)

            for expert_idx in range(self.num_experts):
                mask = expert_indices == expert_idx
                if mask.any():
                    expert_input = flat_x[mask]
                    expert_output = self.experts[expert_idx](expert_input)
                    output[mask] += expert_weights[mask].unsqueeze(-1) * expert_output

        # Load balancing auxiliary loss
        aux_loss = self._compute_load_balance_loss(router_probs)
        return output, aux_loss

    def _expert_choice_forward(
        self, flat_x: Tensor, router_probs: Tensor
    ) -> tuple[Tensor, Tensor]:
        """Expert-choice routing: experts pick tokens."""
        num_tokens = flat_x.shape[0]
        capacity = max(1, int(num_tokens * self.top_k * self.capacity_factor / self.num_experts))

        # Transpose: experts select tokens
        expert_probs = router_probs.t()  # (num_experts, num_tokens)

        output = torch.zeros_like(flat_x)
        for expert_idx in range(self.num_experts):
            # Each expert selects top-capacity tokens
            probs = expert_probs[expert_idx]
            k = min(capacity, num_tokens)
            top_probs, top_indices = torch.topk(probs, k)
            top_probs = top_probs / top_probs.sum().clamp(min=1e-8)  # normalize

            expert_input = flat_x[top_indices]
            expert_output = self.experts[expert_idx](expert_input)
            output[top_indices] += top_probs.unsqueeze(-1) * expert_output

        aux_loss = self._compute_load_balance_loss(router_probs)
        return output, aux_loss

    def _compute_load_balance_loss(self, router_probs: Tensor) -> Tensor:
        """Compute auxiliary load-balancing loss (Switch Transformer style).

        Uses hard top-k assignments for f_i (fraction of tokens dispatched
        to each expert) and soft probabilities for P_i (mean routing
        probability per expert). Loss = N * sum(f_i * P_i).

        This encourages balanced routing by penalizing experts that both
        receive many tokens (high f_i) and have high routing probability (high P_i).
        """
        num_tokens = router_probs.shape[0]

        # f_i: fraction of tokens dispatched to each expert (hard assignment)
        top_k_indices = torch.topk(router_probs, self.top_k, dim=-1).indices
        dispatch_count = torch.zeros(self.num_experts, device=router_probs.device)
        for k in range(self.top_k):
            for expert_idx in range(self.num_experts):
                dispatch_count[expert_idx] += (top_k_indices[:, k] == expert_idx).float().sum()
        f = dispatch_count / (num_tokens * self.top_k)

        # P_i: mean routing probability per expert (soft)
        P = router_probs.mean(dim=0)

        return self.num_experts * (f * P).sum()

    def _compute_expert_utilization(self, router_probs: Tensor) -> Tensor:
        """Estimate per-expert dispatch share from the current router outputs."""
        top_k_indices = torch.topk(router_probs, self.top_k, dim=-1).indices
        dispatch_count = torch.zeros(self.num_experts, device=router_probs.device)
        for k in range(self.top_k):
            for expert_idx in range(self.num_experts):
                dispatch_count[expert_idx] += (top_k_indices[:, k] == expert_idx).float().sum()
        total = dispatch_count.sum().clamp(min=1.0)
        return dispatch_count / total


class TransformerMoELayer(nn.Module):
    """Custom transformer layer that uses self-attention + MoE FFN.

    Replaces the standard FFN in a transformer layer with a Mixture-of-Experts
    block. This implements the TRD requirement that MoE "replaces" the FFN
    rather than being added on top.
    """

    def __init__(
        self,
        d_model: int,
        nhead: int,
        moe_block: MoEBlock,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.self_attn = nn.MultiheadAttention(
            d_model, nhead, dropout=dropout, batch_first=True,
        )
        self.moe_block = moe_block
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.dropout1 = nn.Dropout(dropout)
        self.dropout2 = nn.Dropout(dropout)

    def forward(
        self, x: Tensor, src_key_padding_mask: Tensor | None = None,
    ) -> tuple[Tensor, Tensor]:
        """Forward pass with pre-norm: norm -> attn -> residual, norm -> MoE -> residual.

        Returns:
            Tuple of (output, auxiliary_loss).
        """
        # Self-attention sublayer (pre-norm)
        residual = x
        x = self.norm1(x)
        x, _ = self.self_attn(x, x, x, key_padding_mask=src_key_padding_mask)
        x = self.dropout1(x) + residual

        # MoE FFN sublayer (pre-norm) -- replaces standard FFN
        residual = x
        x = self.norm2(x)
        moe_out, aux_loss = self.moe_block(x)
        x = self.dropout2(moe_out) + residual

        return x, aux_loss


class MoEStudent(nn.Module):
    """Student model with selected layers replaced by MoE blocks.

    Shares embedding, positional encoding, and output heads with DenseStudent.
    Selected transformer layers use MoE FFN blocks INSTEAD of standard FFN
    (true replacement, not additive).
    """

    def __init__(self, config: StudentConfig, moe_config: MoEConfig):
        super().__init__()
        self.config = config
        self.moe_config = moe_config

        # Shared: embedding + positional encoding
        self.embedding = nn.Embedding(config.vocab_size, config.hidden_size)
        self.pos_encoding = nn.Embedding(config.max_seq_len, config.hidden_size)

        # Build layers: standard TransformerEncoderLayer OR TransformerMoELayer
        nhead = max(1, config.hidden_size // 64)
        intermediate_size = config.hidden_size * 4

        self.layers = nn.ModuleList()
        self.moe_layer_indices: set[int] = set()

        for i in range(config.num_layers):
            if i in moe_config.moe_layers:
                # MoE layer: attention + MoE FFN (replaces standard FFN)
                moe_block = MoEBlock(
                    hidden_size=config.hidden_size,
                    intermediate_size=intermediate_size,
                    num_experts=moe_config.num_experts,
                    top_k=moe_config.top_k,
                    capacity_factor=moe_config.capacity_factor,
                    routing_strategy=moe_config.routing_strategy,
                )
                layer = TransformerMoELayer(
                    d_model=config.hidden_size,
                    nhead=nhead,
                    moe_block=moe_block,
                )
                self.layers.append(layer)
                self.moe_layer_indices.add(i)
            else:
                # Standard transformer layer
                layer = nn.TransformerEncoderLayer(
                    d_model=config.hidden_size,
                    nhead=nhead,
                    dim_feedforward=intermediate_size,
                    batch_first=True,
                    norm_first=True,
                )
                self.layers.append(layer)

        self.final_norm = nn.LayerNorm(config.hidden_size)

        # Output heads (same as DenseStudent)
        self.trust_head = nn.Linear(config.hidden_size, config.num_axes)
        self.reason_head = nn.Linear(config.hidden_size, config.num_reason_tags)
        self.escalate_head = nn.Linear(config.hidden_size, 1)

        self._init_weights()

    def _init_weights(self):
        for p in self.parameters():
            if p.dim() > 1:
                nn.init.xavier_uniform_(p)

    def forward(
        self, input_ids: Tensor, attention_mask: Tensor | None = None
    ) -> dict[str, Tensor]:
        batch_size, seq_len = input_ids.shape

        positions = torch.arange(seq_len, device=input_ids.device).unsqueeze(0)
        positions = positions.clamp(max=self.config.max_seq_len - 1)

        x = self.embedding(input_ids) + self.pos_encoding(positions)

        src_key_padding_mask = None
        if attention_mask is not None:
            src_key_padding_mask = attention_mask == 0

        total_aux_loss = torch.tensor(0.0, device=input_ids.device)

        for i, layer in enumerate(self.layers):
            if i in self.moe_layer_indices:
                # TransformerMoELayer returns (output, aux_loss)
                x, aux_loss = layer(x, src_key_padding_mask=src_key_padding_mask)
                total_aux_loss = total_aux_loss + aux_loss
            else:
                x = layer(x, src_key_padding_mask=src_key_padding_mask)

        x = self.final_norm(x)

        # Pool
        if attention_mask is not None:
            mask_expanded = attention_mask.unsqueeze(-1).float()
            x = (x * mask_expanded).sum(dim=1) / mask_expanded.sum(dim=1).clamp(min=1)
        else:
            x = x.mean(dim=1)

        trust_logits = self.trust_head(x)
        reason_logits = self.reason_head(x)
        escalate_logit = self.escalate_head(x)

        return {
            "trust_logits": trust_logits,
            "reason_logits": reason_logits,
            "escalate_logit": escalate_logit,
            "aux_loss": total_aux_loss,
        }

    @classmethod
    def from_config(cls, config: StudentConfig, moe_config: MoEConfig) -> MoEStudent:
        """Create MoEStudent from configs."""
        return cls(config, moe_config)

    @classmethod
    def from_dense(cls, dense_model: DenseStudent, moe_config: MoEConfig) -> MoEStudent:
        """Initialize from a trained dense model, copying shared weights.

        Non-MoE layers, embeddings, and output heads are copied from the dense model.
        MoE-specific parameters (expert FFNs, router) are freshly initialized.
        For MoE layers, only the self-attention weights are copied from the dense model.
        """
        config = dense_model.config
        moe_model = cls(config, moe_config)

        # Copy embeddings
        moe_model.embedding.load_state_dict(dense_model.embedding.state_dict())
        moe_model.pos_encoding.load_state_dict(dense_model.pos_encoding.state_dict())

        # Copy output heads
        moe_model.trust_head.load_state_dict(dense_model.trust_head.state_dict())
        moe_model.reason_head.load_state_dict(dense_model.reason_head.state_dict())
        moe_model.escalate_head.load_state_dict(dense_model.escalate_head.state_dict())

        # Copy transformer layers
        dense_layers = list(dense_model.encoder.layers)
        for i, moe_layer in enumerate(moe_model.layers):
            if i >= len(dense_layers):
                break
            dense_layer = dense_layers[i]

            if i in moe_model.moe_layer_indices:
                # MoE layer: copy self-attention weights from dense layer
                # The MoE FFN is freshly initialized (experts start from scratch)
                moe_attn_state = moe_layer.self_attn.state_dict()
                dense_attn_state = dense_layer.self_attn.state_dict()
                # Copy matching keys
                for key in moe_attn_state:
                    if key in dense_attn_state:
                        moe_attn_state[key] = dense_attn_state[key]
                moe_layer.self_attn.load_state_dict(moe_attn_state)
                # Copy norm1 from dense (attention norm)
                moe_layer.norm1.load_state_dict(dense_layer.norm1.state_dict())
            else:
                # Standard layer: full copy
                moe_layer.load_state_dict(dense_layer.state_dict())

        return moe_model

    def param_count(self) -> int:
        return sum(p.numel() for p in self.parameters())


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

# validate_moe_config is imported from autotrust.schemas (single source of truth)


def check_param_budget(model: nn.Module, spec) -> None:
    """Raise ValueError if model exceeds max_params_m budget."""
    if spec.stage2 is None:
        raise ValueError("spec.yaml has no stage2 section")
    total = sum(p.numel() for p in model.parameters())
    max_params = spec.stage2.max_params_m * 1_000_000
    if total > max_params:
        raise ValueError(
            f"Model has {total:,} params, exceeds budget of {max_params:,} "
            f"(max_params_m={spec.stage2.max_params_m})"
        )
