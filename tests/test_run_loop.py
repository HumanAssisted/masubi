"""Tests for run_loop.py -- thin orchestration."""

import time

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from autotrust.config import load_spec
from autotrust.schemas import (
    Email, EmailChain, ScorerOutput, Explanation, ExperimentResult,
)


@pytest.fixture
def spec():
    return load_spec(Path(__file__).parent.parent / "spec.yaml")


@pytest.fixture
def axis_names(spec):
    return [a.name for a in spec.trust_axes]


@pytest.fixture
def mock_scorer_output(axis_names):
    return ScorerOutput(
        trust_vector={a: 0.8 for a in axis_names},
        explanation=Explanation(
            reasons=["phish", "manipulation"],
            summary="Suspicious email.",
        ),
    )


@pytest.fixture
def sample_chains(axis_names):
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
def isolated_workspace(tmp_path, monkeypatch):
    """Run loop tests should never touch the repo's live train.py."""
    monkeypatch.chdir(tmp_path)
    root = Path(__file__).parent.parent
    (tmp_path / "starting_train.py").write_text((root / "starting_train.py").read_text())
    (tmp_path / "program.md").write_text((root / "program.md").read_text())
    (tmp_path / "train.py").write_text("# test working copy\n")
    return tmp_path


def test_loop_enforces_time_limit(spec, tmp_path, isolated_workspace):
    """Loop exits when wall time exceeds experiment_minutes."""
    from run_loop import run_autoresearch

    with patch("run_loop.get_spec", return_value=spec), \
         patch("run_loop.load_calibration") as mock_cal, \
         patch("run_loop.start_run") as mock_run, \
         patch("run_loop.load_eval_chains", return_value=[]), \
         patch("run_loop.load_gold_chains", return_value=[]), \
         patch("run_loop.finalize_run"), \
         patch("run_loop.update_run_status"), \
         patch("run_loop.time") as mock_time:

        mock_cal.return_value = MagicMock()
        mock_run.return_value = MagicMock(run_dir=tmp_path)

        # Simulate time exceeding limit (enough values for all time.time() calls)
        mock_time.time.side_effect = [0, 0, 0, 1000, 1000, 1000]

        run_autoresearch(max_experiments=10)
        # Should exit without running experiments due to time limit


def test_loop_enforces_budget_limit(spec, tmp_path):
    """Loop exits when cost exceeds max_spend_usd."""

    with patch("run_loop.get_spec", return_value=spec), \
         patch("run_loop.load_calibration") as mock_cal, \
         patch("run_loop.start_run") as mock_run, \
         patch("run_loop.load_eval_chains", return_value=[]), \
         patch("run_loop.load_gold_chains", return_value=[]), \
         patch("run_loop.finalize_run"):

        mock_cal.return_value = MagicMock()
        mock_run.return_value = MagicMock(run_dir=tmp_path)

        # Directly test the budget check function
        from run_loop import _check_budget
        assert _check_budget(10.0, spec) is True  # over budget
        assert _check_budget(1.0, spec) is False  # under budget


def test_loop_keep_commits_train_py():
    """When all three gates pass, train.py is committed via git."""
    from run_loop import _handle_keep_discard

    with patch("run_loop.subprocess") as mock_subprocess:
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        _handle_keep_discard(keep=True, experiment_num=1)
        # Should call git add + git commit
        assert mock_subprocess.run.call_count >= 2


def test_loop_discard_restores_train_py():
    """When any gate fails, train.py is restored via git checkout."""
    from run_loop import _handle_keep_discard

    with patch("run_loop.subprocess") as mock_subprocess:
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        _handle_keep_discard(keep=False, experiment_num=1)
        # Should call git checkout
        calls = [str(c) for c in mock_subprocess.run.call_args_list]
        assert any("checkout" in c for c in calls)


def test_loop_nudges_lora_after_stalls():
    """After 3 consecutive no-improvement, agent prompt includes LoRA nudge."""
    from run_loop import _build_agent_prompt

    prompt = _build_agent_prompt(
        program_md="test program",
        train_py="test train",
        last_results=[],
        consecutive_no_improvement=3,
    )
    assert "LoRA" in prompt


def test_loop_logs_each_experiment(spec, tmp_path):
    """Each iteration calls observe.log_experiment()."""
    from run_loop import _log_iteration

    with patch("run_loop.log_experiment") as mock_log:
        ctx = MagicMock(run_dir=tmp_path)
        result = ExperimentResult(
            run_id="test",
            change_description="test",
            per_axis_scores={},
            composite=0.5,
            fp_rate=0.05,
            judge_agreement=0.9,
            gold_agreement=0.8,
            explanation_quality=0.7,
            downweighted_axes=[],
            gate_results={"composite": True, "gold": True, "explanation": True},
            cost=1.0,
            wall_time=60.0,
        )
        _log_iteration(ctx, result)
        mock_log.assert_called_once_with(ctx, result)


# ---------------------------------------------------------------------------
# New tests for stop_check / pause_check callbacks
# ---------------------------------------------------------------------------


def test_stop_check_callback_exits_loop(spec, tmp_path, isolated_workspace):
    """Pass a stop_check that returns True after 1 call; verify loop exits early."""
    from run_loop import run_autoresearch

    call_count = 0

    def stop_after_first():
        nonlocal call_count
        call_count += 1
        return call_count >= 1  # stop immediately

    with patch("run_loop.get_spec", return_value=spec), \
         patch("run_loop.load_calibration") as mock_cal, \
         patch("run_loop.start_run") as mock_run, \
         patch("run_loop.load_eval_chains", return_value=[MagicMock()]), \
         patch("run_loop.load_gold_chains", return_value=[]), \
         patch("run_loop.finalize_run"), \
         patch("run_loop.update_run_status"):

        mock_cal.return_value = MagicMock()
        mock_run.return_value = MagicMock(run_dir=tmp_path)

        run_autoresearch(max_experiments=100, stop_check=stop_after_first)
        # If stop_check works, we should have exited after 1 call,
        # not run any experiments
        assert call_count == 1


def test_pause_check_callback_blocks(spec, tmp_path, isolated_workspace):
    """Pass a pause_check that returns True for 2 calls then False; verify loop pauses then continues."""
    from run_loop import run_autoresearch

    pause_calls = 0

    def pause_briefly():
        nonlocal pause_calls
        pause_calls += 1
        return pause_calls <= 2  # pause for 2 checks, then resume

    stop_calls = 0

    def stop_after_pause():
        nonlocal stop_calls
        stop_calls += 1
        return stop_calls >= 2  # stop on 2nd stop check (after pause resumes)

    with patch("run_loop.get_spec", return_value=spec), \
         patch("run_loop.load_calibration") as mock_cal, \
         patch("run_loop.start_run") as mock_run, \
         patch("run_loop.load_eval_chains", return_value=[MagicMock()]), \
         patch("run_loop.load_gold_chains", return_value=[]), \
         patch("run_loop.finalize_run"), \
         patch("run_loop.update_run_status"), \
         patch("run_loop.time") as mock_time:

        mock_cal.return_value = MagicMock()
        mock_run.return_value = MagicMock(run_dir=tmp_path)
        mock_time.time.return_value = 0  # no time limit
        mock_time.sleep = MagicMock()  # don't actually sleep

        run_autoresearch(
            max_experiments=100,
            stop_check=stop_after_pause,
            pause_check=pause_briefly,
        )
        # pause_check should have been called (at least once during pause)
        assert pause_calls >= 1


# ---------------------------------------------------------------------------
# Per-experiment timeout tests
# ---------------------------------------------------------------------------


def test_check_experiment_timeout_raises():
    """_check_experiment_timeout raises ExperimentTimeout when cap exceeded."""
    from run_loop import _check_experiment_timeout, ExperimentTimeout

    mock_spec = MagicMock()
    mock_spec.limits.per_experiment_timeout_minutes = 10.0

    # 11 minutes ago -> should raise
    experiment_start = time.time() - 11 * 60
    with pytest.raises(ExperimentTimeout):
        _check_experiment_timeout(experiment_start, mock_spec)


def test_check_experiment_timeout_no_raise():
    """_check_experiment_timeout does not raise when within cap."""
    from run_loop import _check_experiment_timeout

    mock_spec = MagicMock()
    mock_spec.limits.per_experiment_timeout_minutes = 10.0

    # 1 minute ago -> should not raise
    experiment_start = time.time() - 1 * 60
    _check_experiment_timeout(experiment_start, mock_spec)  # no exception


def test_load_eval_chains_respects_limit(tmp_path, monkeypatch, sample_chains):
    """load_eval_chains(limit=N) should only load the requested prefix."""
    from run_loop import load_eval_chains

    monkeypatch.chdir(tmp_path)
    eval_dir = tmp_path / "eval_set"
    eval_dir.mkdir()
    (eval_dir / "eval_chains.jsonl").write_text(
        "\n".join(chain.model_dump_json() for chain in sample_chains) + "\n"
    )

    loaded = load_eval_chains(limit=2)
    assert len(loaded) == 2


def test_load_stage1_scorer_class_uses_train_py_working_copy(tmp_path, monkeypatch):
    """Stage 1 should load EmailTrustScorer from train.py, not starting_train.py."""
    from run_loop import _load_stage1_scorer_class

    monkeypatch.chdir(tmp_path)
    (tmp_path / "starting_train.py").write_text(
        "class EmailTrustScorer:\n"
        "    SOURCE = 'starting_train'\n"
    )
    (tmp_path / "train.py").write_text(
        "class EmailTrustScorer:\n"
        "    SOURCE = 'train'\n"
    )

    scorer_cls = _load_stage1_scorer_class()
    assert scorer_cls.SOURCE == "train"


def test_validate_stage1_candidate_accepts_baseline(spec, isolated_workspace):
    """The baseline Stage 1 template should pass the pre-score smoke validation."""
    from run_loop import _validate_stage1_candidate

    assert _validate_stage1_candidate(Path("train.py"), spec) is None


def test_validate_stage1_candidate_rejects_broken_regex(spec, isolated_workspace):
    """Validation should catch fragile regex edits before live scoring starts."""
    from run_loop import _validate_stage1_candidate

    Path("train.py").write_text(
        """from starting_train import EmailTrustScorer as BaseScorer
import re

class EmailTrustScorer(BaseScorer):
    def _parse_response(self, raw):
        raw = re.sub(r"```json|```", "\\1", raw)
        return super()._parse_response(raw)
"""
    )

    error = _validate_stage1_candidate(Path("train.py"), spec)
    assert error is not None
    assert "invalid group reference" in error


def test_extract_gold_truth_prefers_consensus_labels():
    """Gold truth should come from consensus_labels when present."""
    from run_loop import _gold_truth_labels

    gold_records = [
        {
            "chain_id": "gold-1",
            "labels": {"phish": 0.1},
            "consensus_labels": {"phish": 0.9},
        },
        {
            "chain_id": "gold-2",
            "labels": {"phish": 0.2},
        },
    ]

    truth = _gold_truth_labels(gold_records)
    assert truth == [{"phish": 0.9}, {"phish": 0.2}]


def test_per_experiment_timeout_in_spec(spec):
    """spec.yaml has per_experiment_timeout_minutes field."""
    assert hasattr(spec.limits, "per_experiment_timeout_minutes")
    assert spec.limits.per_experiment_timeout_minutes == 10.0


def test_callbacks_default_none_backward_compatible(spec, tmp_path):
    """Call run_autoresearch() without callbacks; verify it works identically."""
    from run_loop import run_autoresearch

    with patch("run_loop.get_spec", return_value=spec), \
         patch("run_loop.load_calibration") as mock_cal, \
         patch("run_loop.start_run") as mock_run, \
         patch("run_loop.load_eval_chains", return_value=[]), \
         patch("run_loop.load_gold_chains", return_value=[]), \
         patch("run_loop.finalize_run"), \
         patch("run_loop.update_run_status"):

        mock_cal.return_value = MagicMock()
        mock_run.return_value = MagicMock(run_dir=tmp_path)

        # Should work without passing any callbacks
        run_autoresearch(max_experiments=10)
        # No crash = backward compatible
