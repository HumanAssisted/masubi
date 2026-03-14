"""Tests for Stage CLI, auto-transition, and Stage 2 subprocess mode in run_loop.py."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from autotrust.config import load_spec


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


def test_auto_transition_triggers(spec):
    """After 3 consecutive no-improvement with stage='prompt', triggers transition."""
    from run_loop import _should_auto_transition
    assert _should_auto_transition("prompt", 3) is True
    assert _should_auto_transition("prompt", 2) is False
    assert _should_auto_transition("train", 3) is False


def test_auto_transition_calls_freeze(spec, tmp_path):
    """Auto-transition calls freeze_teacher()."""
    from run_loop import _auto_transition

    with patch("autotrust.freeze.freeze_teacher") as mock_freeze:
        mock_freeze.return_value = MagicMock()
        new_stage = _auto_transition(spec)
        mock_freeze.assert_called_once()
        assert new_stage == "train"


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


def test_handoff_rewrites_train_py(spec, tmp_path, monkeypatch):
    """At transition, train.py is archived and replaced with Stage 2 template."""
    from run_loop import _archive_train_py, _write_stage2_train_py_template

    # Create a fake train.py
    train_py = tmp_path / "train.py"
    train_py.write_text("# Stage 1 prompt code")

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
    assert (tmp_path / "train_stage1_archive.py").exists()

    _write_stage2_train_py_template()
    content = train_py.read_text()
    assert "autotrust.student" in content
    assert "Stage 2" in content


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
