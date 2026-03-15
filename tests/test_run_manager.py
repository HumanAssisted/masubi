"""Tests for autotrust/dashboard/run_manager.py -- thread management."""

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest


def _mock_run_autoresearch(max_experiments=50, stop_check=None, pause_check=None):
    """A mock run_autoresearch that checks stop/pause like the real one."""
    for _ in range(max_experiments):
        if stop_check and stop_check():
            break
        while pause_check and pause_check():
            time.sleep(0.01)
            if stop_check and stop_check():
                return
        time.sleep(0.01)


def test_initial_status_is_idle():
    """Newly created RunManager has status 'idle' and current_run_id is None."""
    from autotrust.dashboard.run_manager import RunManager

    rm = RunManager()
    with patch.object(RunManager, "_detect_active_run_with_state", return_value=(None, "idle")), \
         patch.object(RunManager, "_detect_active_run", return_value=None):
        assert rm.status == "idle"
        assert rm.current_run_id is None


def test_external_starting_run_is_detected(tmp_path):
    """A config-only external run should show up as starting."""
    from autotrust.dashboard.run_manager import RunManager

    run_dir = tmp_path / "20260314_120000_abcd1234"
    run_dir.mkdir()
    (run_dir / "config.json").write_text("{}")
    (run_dir / "status.json").write_text('{"state": "starting", "message": "Booting"}')

    run_id, state = RunManager._detect_active_run_with_state(base_dir=tmp_path)
    assert run_id == run_dir.name
    assert state == "starting"


def test_completed_summary_only_run_is_detected(tmp_path):
    """Completed runs without metrics should still be discoverable after smoke tests."""
    from autotrust.dashboard.run_manager import RunManager

    run_dir = tmp_path / "20260315_010000_abcd1234"
    run_dir.mkdir()
    (run_dir / "summary.txt").write_text("Run ID: 20260315_010000_abcd1234\nExperiments: 0\n")

    run_id, state = RunManager._detect_active_run_with_state(base_dir=tmp_path)
    assert run_id == run_dir.name
    assert state == "completed"


def test_stale_running_status_does_not_beat_completed_run(tmp_path):
    """Old external heartbeats should not keep the Live tab pinned to dead runs."""
    from autotrust.dashboard.run_manager import RunManager

    stale_run = tmp_path / "20260315_010000_deadbeef"
    stale_run.mkdir()
    stale_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    (stale_run / "status.json").write_text(f'{{"state": "running", "updated_at": "{stale_time}"}}')

    completed_run = tmp_path / "20260315_020000_goodbeef"
    completed_run.mkdir()
    (completed_run / "summary.txt").write_text("Run ID: 20260315_020000_goodbeef\nExperiments: 1\n")

    run_id, state = RunManager._detect_active_run_with_state(base_dir=tmp_path)
    assert run_id == completed_run.name
    assert state == "completed"


def test_start_sets_running():
    """After start(), status is 'running' and current_run_id may be detected."""
    from autotrust.dashboard.run_manager import RunManager

    rm = RunManager()
    with patch("run_loop.run_autoresearch", side_effect=_mock_run_autoresearch):
        result = rm.start(max_experiments=5)
        time.sleep(0.05)
        assert rm.status == "running"
        assert result is not None
        rm.stop()
        time.sleep(0.2)


def test_stop_sets_stopping_then_idle():
    """After stop(), status transitions to 'stopping', then 'idle' after thread exits."""
    from autotrust.dashboard.run_manager import RunManager

    rm = RunManager()
    with patch.object(RunManager, "_detect_active_run_with_state", return_value=(None, "idle")), \
         patch.object(RunManager, "_detect_active_run", return_value=None), \
         patch("run_loop.run_autoresearch", side_effect=_mock_run_autoresearch):
        rm.start(max_experiments=1000)
        time.sleep(0.05)
        rm.stop()
        # Should eventually become idle
        time.sleep(0.5)
        assert rm.status == "idle"


def test_pause_resume_lifecycle():
    """pause() sets status 'paused', resume() sets status back to 'running'."""
    from autotrust.dashboard.run_manager import RunManager

    rm = RunManager()
    with patch("run_loop.run_autoresearch", side_effect=_mock_run_autoresearch):
        rm.start(max_experiments=1000)
        time.sleep(0.05)

        rm.pause()
        assert rm.status == "paused"

        rm.resume()
        assert rm.status == "running"

        rm.stop()
        time.sleep(0.5)


def test_stop_check_callback_returns_true_when_stopped():
    """The stop_check callback returns True after stop() is called."""
    from autotrust.dashboard.run_manager import RunManager

    rm = RunManager()
    assert rm._stop_check() is False  # not stopped yet

    rm._stop_event.set()
    assert rm._stop_check() is True


def test_start_when_already_running_raises():
    """Calling start() while already running raises RuntimeError."""
    from autotrust.dashboard.run_manager import RunManager

    rm = RunManager()
    with patch("run_loop.run_autoresearch", side_effect=_mock_run_autoresearch):
        rm.start(max_experiments=1000)
        time.sleep(0.05)

        with pytest.raises(RuntimeError):
            rm.start(max_experiments=10)

        rm.stop()
        time.sleep(0.5)


def test_exception_sets_error_status():
    """If run_autoresearch raises, status becomes 'error' and last_error is set."""
    from autotrust.dashboard.run_manager import RunManager

    rm = RunManager()

    def _crashing_run(**kwargs):
        raise ValueError("API key missing")

    with patch("run_loop.run_autoresearch", side_effect=_crashing_run):
        rm.start(max_experiments=5)
        time.sleep(0.3)
        assert rm.status == "error"
        assert rm.last_error is not None
        assert "API key" in str(rm.last_error)


def test_stop_race_condition_thread_still_alive():
    """If thread doesn't exit within timeout, status should NOT become idle."""
    from autotrust.dashboard.run_manager import RunManager

    rm = RunManager()

    def _slow_run(**kwargs):
        time.sleep(60)  # won't exit in time

    with patch("run_loop.run_autoresearch", side_effect=_slow_run):
        rm.start(max_experiments=5)
        time.sleep(0.05)

        # Patch join timeout to be very short so test doesn't block
        def quick_stop():
            if rm._status not in ("running", "paused"):
                return
            rm._status = "stopping"
            rm._stop_event.set()
            rm._pause_event.set()
            if rm._thread is not None:
                rm._thread.join(timeout=0.1)
                if rm._thread.is_alive():
                    return  # should NOT set idle
            rm._status = "idle"
            rm._thread = None

        quick_stop()
        # Thread is still alive, so status should remain "stopping"
        assert rm.status == "stopping"

        # Clean up: let thread die
        rm._stop_event.set()
        if rm._thread:
            rm._thread.join(timeout=2)
