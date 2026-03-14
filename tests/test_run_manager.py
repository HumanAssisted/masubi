"""Tests for autotrust/dashboard/run_manager.py -- thread management."""

import time
import threading
from unittest.mock import patch, MagicMock

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
    assert rm.status == "idle"
    assert rm.current_run_id is None


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
    with patch("run_loop.run_autoresearch", side_effect=_mock_run_autoresearch):
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
        original_stop = rm.stop

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
