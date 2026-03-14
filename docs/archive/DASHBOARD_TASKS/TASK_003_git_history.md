# Task 003: Build git_history.py -- Git Diff & Log Parser

## Context
`git_history.py` parses the git history of `train.py` to power the Code Evolution tab. The agent edits `train.py` each experiment -- kept edits are committed, discarded edits are reverted. This module extracts the commit log, generates diffs between any two commits, and retrieves file contents at specific commits. All git operations use `subprocess.run` with timeouts to avoid blocking the dashboard. See GRADIO_DASHBOARD_PRD.md section 5.5 (Git History Parser).

## Goal
Build git history parsing for train.py that provides commit log, diffs, and file-at-commit retrieval for the Code Evolution tab.

## Research First
- [ ] Read GRADIO_DASHBOARD_PRD.md section 5.5 (Git History Parser) for function signatures
- [ ] Read GRADIO_DASHBOARD_PRD.md section 4.3 (Code Evolution tab) for UI requirements
- [ ] Read `run_loop.py` `_handle_keep_discard()` to understand git commit/revert pattern
- [ ] Check git log format: `git log --follow --pretty=format:"%H %s %ai" -- train.py`
- [ ] Understand that discarded experiments have no git commit -- their diffs must come from metrics.jsonl `change_description` or `proposed_code` field

## TDD: Tests First (Red)
Write tests FIRST in `tests/test_git_history.py`. They should FAIL before implementation.

### Unit Tests
- [ ] Test: `test_get_train_py_log_parses_output` -- mock subprocess to return known git log output, verify returns list of dicts with hash, message, date, composite fields -- in `tests/test_git_history.py`
- [ ] Test: `test_get_train_py_log_empty_repo` -- mock subprocess returning empty output, returns empty list -- in `tests/test_git_history.py`
- [ ] Test: `test_get_diff_returns_unified_diff` -- mock subprocess to return known diff output, verify returns diff string -- in `tests/test_git_history.py`
- [ ] Test: `test_get_file_at_commit_returns_content` -- mock subprocess to return file content, verify returns string -- in `tests/test_git_history.py`
- [ ] Test: `test_subprocess_timeout_handled` -- mock subprocess to raise TimeoutExpired, verify returns empty/default gracefully -- in `tests/test_git_history.py`

All tests mock `subprocess.run` to avoid requiring actual git history.

## Implementation
- [ ] Step 1: Implement `get_train_py_log(file: str = "train.py") -> list[dict]` in `autotrust/dashboard/git_history.py`:
  - Run `git log --follow --pretty=format:"%H|||%s|||%ai" -- {file}`
  - Parse each line into `{"hash": str, "message": str, "date": str}`
  - Extract composite score from commit message if present (e.g., "experiment 5: keep" -> parse metrics.jsonl for that experiment's composite)
  - Add `"composite"` field where parseable, `None` otherwise
  - Use `subprocess.run(..., timeout=10, capture_output=True, text=True)`
  ```python
  def get_train_py_log(file: str = "train.py") -> list[dict]:
      """Get git log for train.py. Returns list of commit info dicts."""
  ```
- [ ] Step 2: Implement `get_diff(hash_a: str, hash_b: str, file: str = "train.py") -> str`:
  - Run `git diff {hash_a} {hash_b} -- {file}`
  - Return unified diff as string
  - Return empty string on error or timeout
  ```python
  def get_diff(hash_a: str, hash_b: str, file: str = "train.py") -> str:
      """Get unified diff between two commits for a file."""
  ```
- [ ] Step 3: Implement `get_file_at_commit(commit_hash: str, file: str = "train.py") -> str`:
  - Run `git show {commit_hash}:{file}`
  - Return file contents as string
  - Return empty string on error or timeout
  ```python
  def get_file_at_commit(commit_hash: str, file: str = "train.py") -> str:
      """Get file contents at a specific commit."""
  ```
- [ ] Step 4: Implement `get_discarded_diffs(run_id: str, base_dir: Path = Path("runs")) -> list[dict]`:
  - Read metrics.jsonl for the run
  - Filter for experiments where gate_results show at least one False (i.e., discarded)
  - Return list of `{"experiment": int, "change_description": str, "composite": float, "gate_results": dict}`
  - NOTE: actual diffs of discarded code are not in git. This returns metadata only. Full proposed_code support is deferred (see PRD section 7 Risks).
  ```python
  def get_discarded_diffs(run_id: str, base_dir: Path = Path("runs")) -> list[dict]:
      """Get metadata about discarded experiments from metrics.jsonl."""
  ```
- [ ] Step 5: Add input validation -- sanitize `hash_a`, `hash_b`, `commit_hash` to prevent command injection (only allow hex characters and `^`, `~`, `HEAD`)
- [ ] DRY check: uses `data_loader.load_run_metrics()` for reading metrics.jsonl in `get_discarded_diffs()`

## TDD: Tests Pass (Green)
- [ ] All 5 unit tests pass
- [ ] All existing tests still pass

## Acceptance Criteria
- [ ] `autotrust/dashboard/git_history.py` exists with all 4 functions
- [ ] All subprocess calls use `timeout=10` to prevent blocking
- [ ] Commit hash inputs are sanitized against injection
- [ ] Graceful fallback on subprocess errors (return empty, log warning)
- [ ] All tests pass

## Execution
- **Agent Type**: python-expert
- **Wave**: 2 (depends on TASK_001 scaffold; parallel with TASK_002, TASK_004)
- **Complexity**: Medium
