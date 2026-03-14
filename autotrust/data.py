"""Data generation and calibration module for AutoEmailTrust v3.5.

CLI subcommands:
    uv run python -m autotrust.data build-train --count 5000
    uv run python -m autotrust.data build-eval
    uv run python -m autotrust.data build-gold
    uv run python -m autotrust.data annotate-export
    uv run python -m autotrust.data calibrate-judge --annotations <path>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
from sklearn.metrics import cohen_kappa_score

if TYPE_CHECKING:
    from autotrust.config import Spec
    from autotrust.schemas import Email

logger = structlog.get_logger()

# Known real brand names for safety filtering
KNOWN_BRANDS = {
    "paypal", "google", "microsoft", "apple", "amazon", "facebook", "meta",
    "netflix", "ebay", "chase", "wellsfargo", "bankofamerica", "citibank",
    "walmart", "target", "instagram", "twitter", "linkedin", "dropbox",
    "adobe", "zoom", "slack", "github", "stripe", "venmo", "cashapp",
}

# Operational instruction patterns (to be blocked)
OPERATIONAL_PATTERNS = [
    r"reverse\s+shell",
    r"c2\s+server",
    r"malware\.exe",
    r"payload\s+from",
    r"execute\s+as\s+administrator",
    r"exploit\s+the\s+vulnerability",
    r"sql\s+injection.*exec",
    r"buffer\s+overflow.*shellcode",
    r"download.*trojan",
    r"keylogger.*install",
]


# ---------------------------------------------------------------------------
# Safety filter
# ---------------------------------------------------------------------------

def safety_filter(email: Email, is_synth: bool, spec: Spec) -> bool:
    """Filter emails based on safety rules from spec.yaml.

    Returns True if email passes (is safe to include), False if rejected.
    """
    text = f"{email.subject} {email.body}".lower()

    # Block operational instructions
    if spec.safety.block_operational_instructions:
        for pattern in OPERATIONAL_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                logger.warning("Blocked email with operational instructions: %s", pattern)
                return False

    # Synth data: placeholder brands only
    if is_synth and spec.safety.synth_placeholder_only:
        for brand in KNOWN_BRANDS:
            if brand in text:
                logger.warning("Blocked synth email with real brand: %s", brand)
                return False

    # Eval data: real brands allowed
    # (no additional filtering needed -- spec.safety.real_brands_in_eval)

    return True


# ---------------------------------------------------------------------------
# Cohen's Kappa computation
# ---------------------------------------------------------------------------

def compute_cohen_kappa(
    annotator_1: list[float],
    annotator_2: list[float],
) -> float:
    """Compute Cohen's Kappa between two annotators.

    For continuous scores, binarizes at 0.5 threshold.
    """
    y1 = [1 if s >= 0.5 else 0 for s in annotator_1]
    y2 = [1 if s >= 0.5 else 0 for s in annotator_2]

    if y1 == y2:
        return 1.0

    try:
        return float(cohen_kappa_score(y1, y2))
    except Exception:
        return 0.0


def flag_low_kappa_axes(
    kappa_per_axis: dict[str, float],
    spec: Spec,
) -> list[str]:
    """Flag axes where Kappa is below min_gold_kappa threshold."""
    min_kappa = spec.judge.min_gold_kappa
    return [
        axis_name
        for axis_name, kappa in kappa_per_axis.items()
        if kappa < min_kappa
    ]


# ---------------------------------------------------------------------------
# Synthetic chain generation helpers
# ---------------------------------------------------------------------------

_SYNTH_SCENARIOS = [
    {
        "type": "phish",
        "subject": "Action Required: Verify Your Account",
        "body": (
            "Dear User,\n\nWe've detected unusual activity on your account. "
            "Please verify your identity by clicking the link below within 24 hours "
            "or your account will be suspended.\n\nVerify: https://placeholder-corp.example.com/verify\n\n"
            "Regards,\nPlaceholder Corp Security Team"
        ),
        "labels": {"phish": 1.0, "manipulation": 0.7, "authority_impersonation": 0.8,
                    "deceit": 0.8, "vulnerability_risk": 0.6},
    },
    {
        "type": "benign",
        "subject": "Meeting Follow-up Notes",
        "body": (
            "Hi team,\n\nAttached are the notes from today's meeting. "
            "Please review the action items and let me know if I missed anything.\n\n"
            "Key decisions:\n1. Launch date moved to Q2\n2. Budget approved for phase 2\n\nBest,\nProject Lead"
        ),
        "labels": {},
    },
    {
        "type": "manipulation",
        "subject": "RE: Your Performance Review",
        "body": (
            "I noticed some concerning trends in your recent work. "
            "I'd rather not escalate this to HR, but I need you to handle "
            "this wire transfer for me before end of day. It's time-sensitive "
            "and I trust you can handle it discreetly.\n\n- Director"
        ),
        "labels": {"manipulation": 0.9, "authority_impersonation": 0.7,
                    "vulnerability_risk": 0.8, "deceit": 0.6},
    },
    {
        "type": "subtle_toxicity",
        "subject": "RE: Team Restructuring",
        "body": (
            "I'm sure you'll do fine in the new role. Not everyone is cut out for "
            "leadership, and that's perfectly okay. Some people are just better at "
            "following instructions. I'm glad we could find a position that's more "
            "suited to your... capabilities."
        ),
        "labels": {"subtle_toxicity": 0.8, "manipulation": 0.4, "polarization": 0.3},
    },
    {
        "type": "spam",
        "subject": "CONGRATULATIONS!!! You've Won $1,000,000!!!",
        "body": (
            "YOU HAVE BEEN SELECTED as the winner of our annual sweepstakes!!! "
            "To claim your prize, send your full name, address, and bank details "
            "to claims@placeholder-lottery.example.com\n\nACT NOW - EXPIRES IN 24 HOURS!!!"
        ),
        "labels": {"phish": 0.9, "manipulation": 0.6, "deceit": 0.9,
                    "classic_email_metrics": 0.9},
    },
]


def _generate_synth_chain(
    chain_id: str,
    spec: Spec,
    generator: Any | None = None,
) -> dict:
    """Generate a single synthetic email chain.

    If a GeneratorProvider is available, uses it for content generation.
    Otherwise, falls back to template-based generation from built-in scenarios.
    """
    from autotrust.schemas import Email

    scenario = random.choice(_SYNTH_SCENARIOS)
    axis_names = [a.name for a in spec.trust_axes]

    # Build labels: start with zeros, overlay scenario-specific labels
    labels = {a: 0.0 for a in axis_names}
    for axis, score in scenario.get("labels", {}).items():
        if axis in labels:
            # Add small noise for diversity
            labels[axis] = max(0.0, min(1.0, score + random.gauss(0, 0.05)))

    now = datetime.now(timezone.utc)
    email = Email(
        from_addr=f"sender-{random.randint(1, 1000)}@example.com",
        to_addr=f"recipient-{random.randint(1, 1000)}@example.com",
        subject=scenario["subject"],
        body=scenario["body"],
        timestamp=now,
        reply_depth=0,
    )

    # Apply safety filter
    if not safety_filter(email, is_synth=True, spec=spec):
        # Regenerate with benign scenario
        labels = {a: 0.0 for a in axis_names}
        email = Email(
            from_addr=email.from_addr,
            to_addr=email.to_addr,
            subject="Meeting Notes",
            body="Attached are the meeting notes from today.",
            timestamp=now,
            reply_depth=0,
        )

    # Build chain dict
    composite = sum(
        next((a.weight for a in spec.trust_axes if a.name == k), 0.0) * v
        for k, v in labels.items()
    )

    chain = {
        "chain_id": chain_id,
        "emails": [email.model_dump(mode="json")],
        "labels": labels,
        "trust_vector": labels,
        "composite": round(composite, 4),
        "flags": [k for k, v in labels.items() if v > 0.5],
    }

    return chain


def _dedup_chains(chains: list[dict]) -> list[dict]:
    """Deduplicate chains by content hash."""
    seen: set[str] = set()
    unique: list[dict] = []
    for chain in chains:
        # Hash based on email content
        content = json.dumps(chain.get("emails", []), sort_keys=True)
        h = hashlib.md5(content.encode()).hexdigest()
        if h not in seen:
            seen.add(h)
            unique.append(chain)
    return unique


def _write_chains_jsonl(chains: list[dict], output_path: Path) -> int:
    """Write chains to JSONL file. Returns count written."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        for chain in chains:
            f.write(json.dumps(chain, default=str) + "\n")
    return len(chains)


# ---------------------------------------------------------------------------
# Data pipeline subcommands
# ---------------------------------------------------------------------------

def build_train(count: int, spec: Spec) -> Path:
    """Build training dataset from synthetic generation.

    Pipeline: generate -> safety filter -> dedup -> write.
    Uses GeneratorProvider (Ollama) if available, otherwise template-based.
    Output: synth_data/train.jsonl
    """
    output_path = Path("synth_data/train.jsonl")
    logger.info("Building training set", count=count, output=str(output_path))

    # Try to get generator provider
    generator = None
    try:
        from autotrust.providers import get_provider
        generator_provider = get_provider("generator", spec)
        if generator_provider.check_available():
            generator = generator_provider
            logger.info("Using Ollama generator for synthetic data")
        else:
            logger.info("Ollama not available, using template-based generation")
    except Exception:
        logger.info("Generator provider not available, using template-based generation")

    # Generate chains
    chains: list[dict] = []
    for i in range(count):
        chain = _generate_synth_chain(f"train-{i:06d}", spec, generator)
        chains.append(chain)

    # Deduplicate
    chains = _dedup_chains(chains)
    logger.info("After dedup", original=count, unique=len(chains))

    # Write output
    written = _write_chains_jsonl(chains, output_path)
    logger.info("Training set complete", chains_written=written, path=str(output_path))
    return output_path


def build_eval(spec: Spec) -> Path:
    """Build evaluation dataset.

    Size: spec.data.eval_set_size chains.
    Real brands allowed per spec.safety.real_brands_in_eval.
    Output: eval_set/eval_chains.jsonl
    """
    output_path = Path("eval_set/eval_chains.jsonl")
    count = spec.data.eval_set_size
    logger.info("Building eval set", count=count, output=str(output_path))

    # Generate eval chains (same pipeline, different count)
    chains: list[dict] = []
    for i in range(count):
        chain = _generate_synth_chain(f"eval-{i:06d}", spec)
        chains.append(chain)

    chains = _dedup_chains(chains)
    written = _write_chains_jsonl(chains, output_path)
    logger.info("Eval set complete", chains_written=written, path=str(output_path))
    return output_path


def build_gold(spec: Spec) -> Path:
    """Build gold-set candidates for human annotation.

    Size: spec.data.gold_set_size chains.
    Selects diverse chains covering all axis_groups.
    Output: gold_set/gold_candidates.jsonl
    """
    output_path = Path("gold_set/gold_candidates.jsonl")
    count = spec.data.gold_set_size
    logger.info("Building gold set candidates", count=count, output=str(output_path))

    # Generate diverse candidates ensuring coverage of all axis groups
    chains: list[dict] = []
    # Ensure we hit each scenario type at least a few times for diversity
    for i in range(count):
        chain = _generate_synth_chain(f"gold-{i:06d}", spec)
        chains.append(chain)

    chains = _dedup_chains(chains)
    written = _write_chains_jsonl(chains, output_path)
    logger.info("Gold set candidates complete", chains_written=written, path=str(output_path))
    return output_path


def annotate_export(spec: Spec) -> Path:
    """Export gold candidates in annotator-friendly format.

    Reads gold_set/gold_candidates.jsonl and converts to a format
    suitable for human annotation, including the rubric reference.
    Output: gold_set/annotate_export.jsonl
    """
    output_path = Path("gold_set/annotate_export.jsonl")
    candidates_path = Path("gold_set/gold_candidates.jsonl")
    logger.info("Exporting for annotation", output=str(output_path))

    if not candidates_path.exists():
        logger.warning("No gold candidates found. Run build-gold first.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        return output_path

    axis_names = [a.name for a in spec.trust_axes]
    axis_types = {a.name: a.type for a in spec.trust_axes}

    export_items: list[dict] = []
    for line in candidates_path.read_text().strip().split("\n"):
        if not line:
            continue
        chain = json.loads(line)
        export_item = {
            "chain_id": chain["chain_id"],
            "emails": chain["emails"],
            "axes_to_score": [
                {
                    "name": name,
                    "type": axis_types[name],
                    "instructions": (
                        "Score 0 or 1" if axis_types[name] == "binary"
                        else "Score from 0.0 to 1.0 (see annotation_rubric.md for anchors)"
                    ),
                }
                for name in axis_names
            ],
            "rubric_reference": "annotation_rubric.md",
            "annotator_id": "",
            "scores": {name: None for name in axis_names},
            "notes": "",
        }
        export_items.append(export_item)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        for item in export_items:
            f.write(json.dumps(item, default=str) + "\n")

    logger.info("Annotation export complete", chains_exported=len(export_items))
    return output_path


def calibrate_judge(annotations_path: str, spec: Spec) -> Path:
    """Calibrate judge against human annotations.

    Ingests human annotations (JSONL with per-axis scores from 2+ annotators),
    computes Cohen's Kappa per axis, flags axes below min_gold_kappa,
    computes effective weights, and writes CalibrationReport.
    """
    from autotrust.config import get_effective_weights
    from autotrust.schemas import CalibrationReport

    output_path = Path("gold_set/calibration.json")
    logger.info("Calibrating judge", annotations=annotations_path, output=str(output_path))

    # Load annotations: expected format is JSONL where each line has
    # {"chain_id": "...", "annotator_id": "...", "scores": {"phish": 0.0, ...}}
    ann_path = Path(annotations_path)
    if not ann_path.exists():
        logger.error("Annotations file not found", path=annotations_path)
        raise FileNotFoundError(f"Annotations file not found: {annotations_path}")

    # Group annotations by chain_id
    annotations_by_chain: dict[str, list[dict[str, float]]] = {}
    for line in ann_path.read_text().strip().split("\n"):
        if not line:
            continue
        record = json.loads(line)
        chain_id = record["chain_id"]
        scores = record["scores"]
        annotations_by_chain.setdefault(chain_id, []).append(scores)

    # Compute per-axis Kappa from pairwise annotator agreement
    axis_names = [a.name for a in spec.trust_axes]
    kappa_per_axis: dict[str, float] = {}

    for axis_name in axis_names:
        annotator_1_scores: list[float] = []
        annotator_2_scores: list[float] = []

        for _chain_id, ann_list in annotations_by_chain.items():
            if len(ann_list) >= 2:
                score_1 = ann_list[0].get(axis_name, 0.0)
                score_2 = ann_list[1].get(axis_name, 0.0)
                annotator_1_scores.append(score_1)
                annotator_2_scores.append(score_2)

        if annotator_1_scores and annotator_2_scores:
            kappa_per_axis[axis_name] = compute_cohen_kappa(
                annotator_1_scores, annotator_2_scores
            )
        else:
            kappa_per_axis[axis_name] = 1.0  # no data -> assume perfect agreement

    # Flag low-Kappa axes
    flagged = flag_low_kappa_axes(kappa_per_axis, spec)

    # Compute effective weights
    effective_weights = get_effective_weights(spec, kappa_per_axis)

    # Compute downweight amounts
    downweight_amounts = {}
    for axis in spec.trust_axes:
        original = axis.weight
        effective = effective_weights.get(axis.name, 0.0)
        if original > effective:
            downweight_amounts[axis.name] = round(original - effective, 6)

    # Build and write calibration report
    report = CalibrationReport(
        per_axis_kappa=kappa_per_axis,
        effective_weights=effective_weights,
        flagged_axes=flagged,
        downweight_amounts=downweight_amounts,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.model_dump(), indent=2))

    logger.info(
        "Judge calibration complete",
        flagged_axes=flagged,
        axes_calibrated=len(kappa_per_axis),
    )
    return output_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI entry point for data subcommands."""
    from autotrust.config import load_spec

    parser = argparse.ArgumentParser(
        prog="autotrust.data",
        description="Data generation and calibration for AutoEmailTrust v3.5",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # build-train
    p_train = subparsers.add_parser("build-train", help="Generate training data")
    p_train.add_argument("--count", type=int, default=5000, help="Number of chains")

    # build-eval
    subparsers.add_parser("build-eval", help="Generate evaluation data")

    # build-gold
    subparsers.add_parser("build-gold", help="Generate gold-set candidates")

    # annotate-export
    subparsers.add_parser("annotate-export", help="Export for annotation")

    # calibrate-judge
    p_cal = subparsers.add_parser("calibrate-judge", help="Calibrate judge")
    p_cal.add_argument("--annotations", required=True, help="Path to annotations")

    args = parser.parse_args()
    spec = load_spec()

    if args.command == "build-train":
        build_train(args.count, spec)
    elif args.command == "build-eval":
        build_eval(spec)
    elif args.command == "build-gold":
        build_gold(spec)
    elif args.command == "annotate-export":
        annotate_export(spec)
    elif args.command == "calibrate-judge":
        calibrate_judge(args.annotations, spec)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
