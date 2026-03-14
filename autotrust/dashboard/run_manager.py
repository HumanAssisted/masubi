"""Thread management for start/stop/pause of the autoresearch loop."""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


class RunManager:
    """Manages the autoresearch loop in a background thread."""

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # set = NOT paused (normal running)
        self._current_run_id: str | None = None
        self._status: str = "idle"
        self._last_error: BaseException | None = None

    def start(self, max_experiments: int = 50) -> str:
        """Launch run_autoresearch in a daemon thread. Returns placeholder run_id.

        The actual run_id is detected from the runs/ directory after
        run_autoresearch calls start_run() internally.
        """
        if self._status == "running":
            raise RuntimeError("Already running. Stop the current run first.")

        # Record existing run directories so we can detect the new one
        self._existing_run_dirs = self._list_run_dirs()

        self._current_run_id = None
        self._last_error = None

        # Reset events
        self._stop_event.clear()
        self._pause_event.set()  # not paused

        self._status = "running"

        self._thread = threading.Thread(
            target=self._run_wrapper,
            args=(max_experiments,),
            daemon=True,
        )
        self._thread.start()
        return "starting"

    def stop(self) -> None:
        """Signal graceful stop after current experiment."""
        if self._status not in ("running", "paused"):
            return
        self._status = "stopping"
        self._stop_event.set()
        # Also unpause so the loop can exit
        self._pause_event.set()

        if self._thread is not None:
            self._thread.join(timeout=30.0)
            if self._thread.is_alive():
                logger.warning("Background thread did not exit within timeout")
                return
        self._status = "idle"
        self._thread = None

    def pause(self) -> None:
        """Pause between experiments."""
        if self._status == "running":
            self._pause_event.clear()  # clear = paused
            self._status = "paused"

    def resume(self) -> None:
        """Resume from pause."""
        if self._status == "paused":
            self._pause_event.set()  # set = not paused
            self._status = "running"

    @property
    def status(self) -> str:
        return self._status

    @property
    def current_run_id(self) -> str | None:
        return self._current_run_id

    @property
    def last_error(self) -> BaseException | None:
        return self._last_error

    def _stop_check(self) -> bool:
        """Check if stop has been requested."""
        return self._stop_event.is_set()

    def _pause_check(self) -> bool:
        """Check if pause is active. Returns True when paused."""
        return not self._pause_event.is_set()

    @staticmethod
    def _list_run_dirs(base_dir: Path = Path("runs")) -> set[str]:
        """List existing run directory names."""
        if not base_dir.exists():
            return set()
        return {e.name for e in base_dir.iterdir() if e.is_dir()}

    def _detect_run_id(self) -> None:
        """Detect the actual run_id by finding new directories in runs/."""
        current_dirs = self._list_run_dirs()
        new_dirs = current_dirs - getattr(self, "_existing_run_dirs", set())
        if new_dirs:
            # Pick the most recent (lexicographic sort works since run IDs start with timestamps)
            self._current_run_id = sorted(new_dirs)[-1]
            logger.info("Detected run_id: %s", self._current_run_id)

    def _run_wrapper(self, max_experiments: int) -> None:
        """Wrapper that runs run_autoresearch and cleans up status on exit."""
        try:
            from run_loop import run_autoresearch

            run_autoresearch(
                max_experiments=max_experiments,
                stop_check=self._stop_check,
                pause_check=self._pause_check,
            )
        except Exception as exc:
            logger.exception("run_autoresearch crashed")
            self._last_error = exc
            self._status = "error"
        finally:
            # Detect the actual run_id from the runs/ directory
            self._detect_run_id()
            if self._status not in ("idle", "error"):
                self._status = "idle"
