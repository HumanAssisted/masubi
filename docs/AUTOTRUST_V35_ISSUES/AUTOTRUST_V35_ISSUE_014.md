# Issue 014: _handle_keep_discard uses check=False, silently ignoring git failures

## Severity
Medium

## Category
Quality

## Description
In `run_loop.py`, the `_handle_keep_discard` function calls `subprocess.run(["git", "add", ...], check=False)` and `subprocess.run(["git", "commit", ...], check=False)`. Using `check=False` means that if `git add` or `git commit` fails (e.g., nothing to commit, git not initialized, dirty index), the failure is silently ignored. The experiment result could be lost without any error or warning.

Similarly, `git checkout -- train.py` with `check=False` means a discard failure (file not in git, merge conflict) would also be silently swallowed.

## Evidence
- File: `/Users/jonathan.hendler/personal/autoresearch-helpful/run_loop.py:128` -- `subprocess.run(["git", "add", "train.py"], check=False)`
- File: `/Users/jonathan.hendler/personal/autoresearch-helpful/run_loop.py:129-132` -- `subprocess.run(["git", "commit"...], check=False)`
- File: `/Users/jonathan.hendler/personal/autoresearch-helpful/run_loop.py:135` -- `subprocess.run(["git", "checkout"...], check=False)`
- PRD Requirement: INITIAL_DESIGN_CHOICES.md "Three-Gate Keep/Discard Policy" -- git ratcheting is core to the autoresearch loop

## Suggested Fix
Use `check=True` with proper exception handling, or at minimum log the return code:
```python
def _handle_keep_discard(keep: bool, experiment_num: int) -> None:
    if keep:
        result = subprocess.run(["git", "add", "train.py"], capture_output=True, text=True)
        if result.returncode != 0:
            logger.error("git add failed: %s", result.stderr)
            return
        result = subprocess.run(
            ["git", "commit", "-m", f"experiment {experiment_num}: keep"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            logger.error("git commit failed: %s", result.stderr)
    else:
        result = subprocess.run(
            ["git", "checkout", "--", "train.py"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            logger.error("git checkout failed: %s", result.stderr)
```

## Affected Files
- `run_loop.py`
