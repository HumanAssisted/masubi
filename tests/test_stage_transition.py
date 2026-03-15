"""Tests for Stage CLI, auto-transition, and Stage 2 subprocess mode in run_loop.py."""

import pytest
import time
import json
import importlib.util
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from autotrust.config import load_spec
from autotrust.schemas import (
    Email, EmailChain, ScorerOutput, Explanation,
    StudentConfig, CheckpointMeta, MoEConfig,
)


@pytest.fixture
def spec():
    return load_spec(Path(__file__).parent.parent / "spec.yaml")


def test_cli_stage_argument():
    """Parsing --stage train sets stage to 'train'."""
    from run_loop import _parse_args
    args = _parse_args(["--stage", "train"])
    assert args.stage == "train"


def test_cli_default_stage():
    """No --stage defaults to 'prompt'."""
    from run_loop import _parse_args
    args = _parse_args([])
    assert args.stage == "prompt"


def test_cli_eval_limit_argument():
    """Parsing --eval-limit sets the optional demo cap."""
    from run_loop import _parse_args
    args = _parse_args(["--eval-limit", "100"])
    assert args.eval_limit == 100


def test_cli_mock_agent_argument():
    """Parsing --mock-agent enables deterministic smoke runs."""
    from run_loop import _parse_args
    args = _parse_args(["--mock-agent"])
    assert args.mock_agent is True


def test_auto_transition_triggers(spec):
    """After 3 consecutive no-improvement with stage='prompt', triggers transition."""
    from run_loop import _should_auto_transition
    assert _should_auto_transition("prompt", 3) is True
    assert _should_auto_transition("prompt", 2) is False
    assert _should_auto_transition("train", 3) is False


def test_auto_transition_calls_freeze(spec, tmp_path):
    """Auto-transition calls freeze_teacher()."""
    from run_loop import _auto_transition

    with patch("autotrust.freeze.freeze_teacher") as mock_freeze, \
         patch("autotrust.freeze.relabel_training_data"), \
         patch("run_loop._archive_train_py"), \
         patch("run_loop._write_stage2_train_py_template"):
        mock_freeze.return_value = MagicMock()
        new_stage = _auto_transition(spec)
        mock_freeze.assert_called_once()
        assert new_stage == "train"


def test_auto_transition_relabels_training_data(spec):
    """Auto-transition should relabel synth training data before Stage 2 starts."""
    from run_loop import _auto_transition

    artifacts = MagicMock()

    with patch("autotrust.freeze.freeze_teacher", return_value=artifacts) as mock_freeze, \
         patch("autotrust.freeze.relabel_training_data") as mock_relabel, \
         patch("run_loop._archive_train_py"), \
         patch("run_loop._write_stage2_train_py_template"):
        new_stage = _auto_transition(spec)
        assert new_stage == "train"
        mock_freeze.assert_called_once_with(spec)
        mock_relabel.assert_called_once_with(artifacts, spec)


def test_stage2_time_limit(spec):
    """Stage 2 uses stage2_experiment_minutes from spec."""
    from run_loop import _get_time_limit
    limit = _get_time_limit(spec, "train")
    assert limit == spec.limits.stage2_experiment_minutes


def test_stage1_time_limit(spec):
    """Stage 1 uses stage1_experiment_minutes (or experiment_minutes fallback)."""
    from run_loop import _get_time_limit
    limit = _get_time_limit(spec, "prompt")
    expected = spec.limits.stage1_experiment_minutes or spec.limits.experiment_minutes
    assert limit == expected


def test_manual_stage_train_skips_stage1():
    """--stage train goes directly to Stage 2."""
    from run_loop import _parse_args
    args = _parse_args(["--stage", "train"])
    assert args.stage == "train"


def test_get_time_limit_fallback():
    """_get_time_limit falls back to experiment_minutes if per-stage not set."""
    from run_loop import _get_time_limit

    mock_spec = MagicMock()
    mock_spec.limits.experiment_minutes = 15
    mock_spec.limits.stage1_experiment_minutes = None
    mock_spec.limits.stage2_experiment_minutes = None

    assert _get_time_limit(mock_spec, "prompt") == 15
    assert _get_time_limit(mock_spec, "train") == 15


def test_stage2_runs_subprocess(spec, tmp_path, monkeypatch):
    """Stage 2 mode calls subprocess.run to execute train.py."""
    from run_loop import _run_stage2_iteration

    # Mock subprocess.run to succeed
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_result.stderr = ""

    with patch("run_loop.subprocess.run", return_value=mock_result) as mock_sub:
        with patch("run_loop._call_agent", return_value="# stage 2 train.py"):
            with patch("run_loop._score_with_student_model", return_value=None):
                result = _run_stage2_iteration(
                    experiment_num=1,
                    spec=spec,
                    program_md="Stage 2 instructions",
                    all_results=[],
                    consecutive_no_improvement=0,
                    experiment_start=__import__("time").time(),
                )
                # Verify subprocess.run was called with uv run python train.py
                subprocess_calls = [
                    call for call in mock_sub.call_args_list
                    if "train.py" in str(call)
                ]
                assert len(subprocess_calls) > 0


def test_stage2_scoring_uses_checkpoint(spec, tmp_path, monkeypatch):
    """Stage 2 evaluation loads student model checkpoint, not LLM API."""
    from run_loop import _score_with_student_model
    from autotrust.student import DenseStudent
    from autotrust.export import export_pytorch
    from autotrust.schemas import StudentConfig, CheckpointMeta

    # Create a test checkpoint
    config = StudentConfig(
        hidden_size=64, num_layers=1, vocab_size=500,
        max_seq_len=32, num_axes=10, num_reason_tags=10,
    )
    model = DenseStudent.from_config(config)
    ckpt_path = tmp_path / "checkpoints" / "best.pt"
    meta = CheckpointMeta(
        stage="dense_baseline", experiment_num=1,
        composite=0.0, path=ckpt_path, param_count=model.param_count(),
    )
    export_pytorch(model, config, meta, ckpt_path)

    # Score with student model
    axis_names = [a.name for a in spec.trust_axes]
    outputs = _score_with_student_model(
        ckpt_path, ["test email text"], axis_names
    )
    assert outputs is not None
    assert len(outputs) == 1
    from autotrust.schemas import ScorerOutput
    assert isinstance(outputs[0], ScorerOutput)


def test_stage2_scoring_uses_axis_names_for_reason_tags(spec, tmp_path, monkeypatch):
    """Stage 2 should map reason tags to raw axis names for Gate 3 compatibility."""
    from run_loop import _score_with_student_model
    import autotrust.inference as inference_mod
    from autotrust.schemas import ScorerOutput, Explanation

    axis_names = [a.name for a in spec.trust_axes]
    captured: dict[str, list[str]] = {}

    class DummyInference:
        def __init__(self, checkpoint_path):
            self.checkpoint_path = checkpoint_path

        def score_text(self, text, axis_names_arg, reason_tag_names, threshold=0.5):
            captured["reason_tag_names"] = list(reason_tag_names)
            return ScorerOutput(
                trust_vector={a: 0.0 for a in axis_names_arg},
                explanation=Explanation(reasons=[], summary="dummy"),
            )

    monkeypatch.setattr(inference_mod, "LocalInference", DummyInference)

    outputs = _score_with_student_model(tmp_path / "best.pt", ["hello"], axis_names)
    assert outputs is not None
    assert captured["reason_tag_names"] == axis_names


def test_handoff_rewrites_train_py(spec, tmp_path, monkeypatch):
    """At transition, train.py is tagged and replaced with Stage 2 template."""
    from run_loop import _archive_train_py, _write_stage2_train_py_template

    # Create a fake train.py (the working copy)
    train_py = tmp_path / "train.py"
    train_py.write_text("# Stage 1 prompt code")

    # Create starting_train.py (the canonical template -- always preserved)
    starting_train = tmp_path / "starting_train.py"
    starting_train.write_text("# Stage 1 prompt code")

    monkeypatch.chdir(tmp_path)

    # Initialize git repo for archival
    import subprocess
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=str(tmp_path), capture_output=True,
        env={**__import__("os").environ, "GIT_AUTHOR_NAME": "test",
             "GIT_AUTHOR_EMAIL": "test@test.com",
             "GIT_COMMITTER_NAME": "test",
             "GIT_COMMITTER_EMAIL": "test@test.com"},
    )

    _archive_train_py()
    # starting_train.py is the canonical template (always exists)
    assert starting_train.exists()

    _write_stage2_train_py_template()
    content = train_py.read_text()
    assert "autotrust.student" in content
    assert "Stage 2" in content
    # starting_train.py is preserved (not overwritten)
    assert starting_train.read_text() == "# Stage 1 prompt code"


def test_build_agent_prompt_stage2(spec):
    """_build_agent_prompt with stage='train' includes Stage 2 context."""
    from run_loop import _build_agent_prompt

    prompt = _build_agent_prompt(
        program_md="test instructions",
        train_py="# test code",
        last_results=[],
        consecutive_no_improvement=0,
        stage="train",
        spec=spec,
    )
    assert "Stage 2" in prompt
    assert "max_experts" in prompt or "student model" in prompt.lower()


# ---------------------------------------------------------------------------
# Stage 2 integration tests (ISSUE 022)
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_chains(spec):
    """Create sample eval chains for integration tests."""
    axis_names = [a.name for a in spec.trust_axes]
    email = Email(
        from_addr="test@example.com",
        to_addr="user@example.com",
        subject="Test",
        body="Test email body",
        timestamp=datetime.now(timezone.utc),
        reply_depth=0,
    )
    return [
        EmailChain(
            chain_id=f"eval-{i}",
            emails=[email],
            labels={a: 0.5 for a in axis_names},
            trust_vector={a: 0.5 for a in axis_names},
            composite=0.5,
            flags=[],
        )
        for i in range(3)
    ]


@pytest.fixture
def stage2_checkpoint(tmp_path, spec):
    """Create a real student model checkpoint for Stage 2 testing."""
    from autotrust.student import DenseStudent
    from autotrust.export import export_pytorch

    config = StudentConfig(
        hidden_size=64, num_layers=1, vocab_size=500,
        max_seq_len=32, num_axes=len(spec.trust_axes), num_reason_tags=10,
    )
    model = DenseStudent.from_config(config)
    ckpt_dir = tmp_path / "runs" / "latest" / "checkpoints"
    ckpt_dir.mkdir(parents=True)
    ckpt_path = ckpt_dir / "best.pt"
    meta = CheckpointMeta(
        stage="dense_baseline", experiment_num=1,
        composite=0.75, path=ckpt_path, param_count=model.param_count(),
    )
    export_pytorch(model, config, meta, ckpt_path)
    return ckpt_path


def test_stage2_iteration_full_pipeline(spec, tmp_path, monkeypatch, sample_chains, stage2_checkpoint):
    """Stage 2 iteration: agent edit -> subprocess -> checkpoint -> scoring produces results."""
    from run_loop import _run_stage2_iteration

    # Create a train.py in the working directory
    monkeypatch.chdir(tmp_path)
    (tmp_path / "train.py").write_text("# placeholder train.py")

    mock_subprocess = MagicMock()
    mock_subprocess.returncode = 0
    mock_subprocess.stdout = ""
    mock_subprocess.stderr = ""

    axis_names = [a.name for a in spec.trust_axes]
    mock_outputs = [
        ScorerOutput(
            trust_vector={a: 0.6 for a in axis_names},
            explanation=Explanation(reasons=["phish"], summary="Test"),
        )
        for _ in sample_chains
    ]

    with patch("run_loop.subprocess.run", return_value=mock_subprocess), \
         patch("run_loop._call_agent", return_value="# stage 2 modified train.py\nprint('hello')"), \
         patch("run_loop._find_latest_checkpoint", return_value=stage2_checkpoint), \
         patch("run_loop.load_eval_chains", return_value=sample_chains), \
         patch("run_loop._score_with_student_model", return_value=mock_outputs):

        result = _run_stage2_iteration(
            experiment_num=1,
            spec=spec,
            program_md="Stage 2 instructions",
            all_results=[],
            consecutive_no_improvement=0,
            experiment_start=time.time(),
        )

        # Should return a valid result dict with outputs
        assert result is not None
        assert "outputs" in result
        assert len(result["outputs"]) == len(sample_chains)
        assert "cost" in result
        assert "change_desc" in result


def test_stage2_iteration_reads_training_metrics(spec, tmp_path, monkeypatch, sample_chains, stage2_checkpoint):
    """Stage 2 iteration should surface training metrics for dashboard use."""
    from run_loop import _run_stage2_iteration

    monkeypatch.chdir(tmp_path)
    (tmp_path / "train.py").write_text("# placeholder train.py")

    metrics_path = stage2_checkpoint.parent / "training_metrics.json"
    metrics_path.write_text(json.dumps({
        "training_loss": {
            "trust_loss": 0.4,
            "reason_loss": 0.2,
            "escalate_loss": 0.1,
            "total_loss": 0.7,
        },
        "param_count": 123456,
        "expert_utilization": [0.2, 0.3, 0.5],
    }))

    mock_subprocess = MagicMock(returncode=0, stdout="", stderr="")
    axis_names = [a.name for a in spec.trust_axes]
    mock_outputs = [
        ScorerOutput(
            trust_vector={a: 0.6 for a in axis_names},
            explanation=Explanation(reasons=["phish"], summary="Test"),
        )
        for _ in sample_chains
    ]

    with patch("run_loop.subprocess.run", return_value=mock_subprocess), \
         patch("run_loop._call_agent", return_value="# stage 2 modified train.py\nprint('hello')"), \
         patch("run_loop._find_latest_checkpoint", return_value=stage2_checkpoint), \
         patch("run_loop.load_eval_chains", return_value=sample_chains), \
         patch("run_loop._score_with_student_model", return_value=mock_outputs):

        result = _run_stage2_iteration(
            experiment_num=1,
            spec=spec,
            program_md="Stage 2 instructions",
            all_results=[],
            consecutive_no_improvement=0,
            experiment_start=time.time(),
        )

        assert result is not None
        assert result["training_loss"]["total_loss"] == 0.7
        assert result["param_count"] == 123456
        assert result["expert_utilization"] == [0.2, 0.3, 0.5]


def test_stage2_results_flow_through_three_gate_eval(spec, tmp_path, monkeypatch, sample_chains, stage2_checkpoint):
    """Stage 2 results are evaluated through the three-gate pipeline (composite, gold, explanation)."""
    from run_loop import run_autoresearch

    monkeypatch.chdir(tmp_path)
    (tmp_path / "train.py").write_text("# placeholder")
    (tmp_path / "starting_train.py").write_text("# Stage 1 template")
    (tmp_path / "program.md").write_text("# Stage 2 instructions")

    axis_names = [a.name for a in spec.trust_axes]
    mock_outputs = [
        ScorerOutput(
            trust_vector={a: 0.6 for a in axis_names},
            explanation=Explanation(reasons=["phish"], summary="Test"),
        )
        for _ in sample_chains
    ]

    mock_subprocess_result = MagicMock()
    mock_subprocess_result.returncode = 0
    mock_subprocess_result.stdout = ""
    mock_subprocess_result.stderr = ""

    experiment_logged = []

    with patch("run_loop.get_spec", return_value=spec), \
         patch("run_loop.load_calibration") as mock_cal, \
         patch("run_loop.start_run") as mock_run, \
         patch("run_loop.load_eval_chains", return_value=sample_chains), \
         patch("run_loop.load_gold_chains", return_value=[]), \
         patch("run_loop.finalize_run"), \
         patch("run_loop._call_agent", return_value="# modified train.py\nprint('train')"), \
         patch("run_loop.subprocess.run", return_value=mock_subprocess_result), \
         patch("run_loop._find_latest_checkpoint", return_value=stage2_checkpoint), \
         patch("run_loop._score_with_student_model", return_value=mock_outputs), \
         patch("run_loop._handle_keep_discard") as mock_keep_discard, \
         patch("run_loop.log_experiment") as mock_log:

        mock_cal.return_value = MagicMock(
            per_axis_kappa={a: 1.0 for a in axis_names},
            effective_weights={a.name: a.weight for a in spec.trust_axes},
            flagged_axes=[],
            downweight_amounts={},
        )
        mock_run.return_value = MagicMock(run_id="test-stage2", run_dir=tmp_path)

        run_autoresearch(max_experiments=1, stage="train")

        # Three-gate evaluation should have run and decided keep/discard
        mock_keep_discard.assert_called_once()
        # Experiment should have been logged
        mock_log.assert_called_once()


def test_auto_transition_changes_stage_midloop(spec, tmp_path, monkeypatch):
    """After 3 consecutive no-improvement in Stage 1, auto-transition switches to Stage 2."""
    from run_loop import _should_auto_transition, _auto_transition

    # Verify transition triggers
    assert _should_auto_transition("prompt", 3) is True

    # Verify auto_transition returns "train" and calls freeze
    with patch("autotrust.freeze.freeze_teacher") as mock_freeze, \
         patch("autotrust.freeze.relabel_training_data"), \
         patch("run_loop._archive_train_py"), \
         patch("run_loop._write_stage2_train_py_template"):
        mock_freeze.return_value = MagicMock()
        new_stage = _auto_transition(spec)
        assert new_stage == "train"
        mock_freeze.assert_called_once_with(spec)


def test_mock_agent_no_change_run_auto_transitions_into_stage2(spec, tmp_path, monkeypatch):
    """Three no-change prompt experiments should still trigger Stage 2 on the next loop iteration."""
    from run_loop import run_autoresearch

    monkeypatch.chdir(tmp_path)
    (tmp_path / "starting_train.py").write_text("# stage 1 template\n")
    (tmp_path / "train.py").write_text("# working copy\n")
    (tmp_path / "program.md").write_text("# test program\n")

    mock_run_ctx = MagicMock(run_id="test-run", run_dir=tmp_path)

    with patch("run_loop.get_spec", return_value=spec), \
         patch("run_loop.load_calibration", return_value=MagicMock()), \
         patch("run_loop.start_run", return_value=mock_run_ctx), \
         patch("run_loop.load_eval_chains", return_value=[MagicMock()]), \
         patch("run_loop.load_gold_chains", return_value=[]), \
         patch("run_loop.finalize_run"), \
         patch("run_loop.update_run_status"), \
         patch("run_loop._auto_transition", return_value="train") as mock_transition, \
         patch("run_loop._run_stage2_iteration", return_value=None) as mock_stage2:

        run_autoresearch(
            max_experiments=4,
            stage="prompt",
            eval_limit=1,
            mock_agent=True,
        )

    mock_transition.assert_called_once_with(spec)
    mock_stage2.assert_called_once()


def test_generated_stage2_template_trains_and_writes_metrics(tmp_path, monkeypatch):
    """Generated Stage 2 train.py should train a small model and emit metrics."""
    from run_loop import _write_stage2_train_py_template

    monkeypatch.chdir(tmp_path)
    synth_dir = tmp_path / "synth_data"
    synth_dir.mkdir(parents=True)

    spec = load_spec(Path(__file__).parent.parent / "spec.yaml")
    axis_names = [a.name for a in spec.trust_axes]

    def make_record(i: int) -> dict:
        soft_targets = {a: 0.0 for a in axis_names}
        soft_targets["phish"] = 0.9 if i % 2 == 0 else 0.1
        soft_targets["manipulation"] = 0.8 if i % 2 == 0 else 0.2
        return {
            "chain_id": f"train-{i}",
            "emails": [
                {
                    "from_addr": "sender@example.com",
                    "to_addr": "recipient@example.com",
                    "subject": f"Sample {i}",
                    "body": "Urgent action required" if i % 2 == 0 else "Weekly status update",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "reply_depth": 0,
                }
            ],
            "soft_targets": soft_targets,
            "labels": soft_targets,
        }

    records = [make_record(i) for i in range(6)]
    (synth_dir / "train_labeled.jsonl").write_text(
        "\n".join(json.dumps(record) for record in records) + "\n"
    )

    _write_stage2_train_py_template()

    spec_obj = importlib.util.spec_from_file_location("stage2_train_module", tmp_path / "train.py")
    assert spec_obj is not None and spec_obj.loader is not None
    module = importlib.util.module_from_spec(spec_obj)
    spec_obj.loader.exec_module(module)
    module.train()

    checkpoint_dir = tmp_path / "runs" / "latest" / "checkpoints"
    assert (checkpoint_dir / "best.pt").exists()
    metrics = json.loads((checkpoint_dir / "training_metrics.json").read_text())
    assert metrics["param_count"] > 0
    assert "training_loss" in metrics
    assert metrics["training_loss"]["total_loss"] >= 0.0


def test_collect_expert_utilization_from_moe_model(spec):
    """MoE models should expose expert utilization for dashboard logging."""
    from starting_train_stage2 import collect_expert_utilization
    from autotrust.student import MoEStudent
    import torch

    config = StudentConfig(
        hidden_size=64,
        num_layers=2,
        vocab_size=256,
        max_seq_len=32,
        num_axes=len(spec.trust_axes),
        num_reason_tags=len(spec.trust_axes),
    )
    moe_config = MoEConfig(
        num_experts=4,
        top_k=2,
        capacity_factor=1.0,
        moe_layers=[0],
        routing_strategy="top_k",
    )
    model = MoEStudent.from_config(config, moe_config)
    input_ids = torch.randint(0, config.vocab_size, (2, 16))
    attention_mask = torch.ones((2, 16), dtype=torch.long)
    model(input_ids, attention_mask=attention_mask)

    utilization = collect_expert_utilization(model)
    assert utilization is not None
    assert len(utilization) == moe_config.num_experts
    assert abs(sum(utilization) - 1.0) < 1e-5
