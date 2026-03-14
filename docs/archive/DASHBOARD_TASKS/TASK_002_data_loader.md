# Task 002: Build data_loader.py -- Run Data Reader

## Context
`data_loader.py` reads plain text files from the `runs/` directory. All run data is stored as JSONL (metrics.jsonl), JSON (config.json), and plain text (summary.txt). The dashboard polls these files to update charts and log views. The data loader must be resilient to malformed lines (the run loop may be mid-write), support incremental loading for live polling, and handle empty/missing runs gracefully. See GRADIO_DASHBOARD_PRD.md section 5.4 (Data Loader).

## Goal
Build a pure data-access layer that reads filesystem-based run data into Python dicts, with incremental loading support for the polling timer.

## Research First
- [ ] Read GRADIO_DASHBOARD_PRD.md section 5.4 (Data Loader) for function signatures
- [ ] Read GRADIO_DASHBOARD_PRD.md section 5.2 (Data Flow) for file layout
- [ ] Read `autotrust/observe.py` to understand how `metrics.jsonl`, `config.json`, `summary.txt` are written
- [ ] Read `autotrust/schemas.py` for `ExperimentResult` fields (these are the JSONL records)
- [ ] Read `autotrust/config.py` for `CalibrationReport` structure (for `load_calibration`)
- [ ] Check `spec.yaml` for format reference (for `load_spec_text`)

## TDD: Tests First (Red)
Write tests FIRST in `tests/test_data_loader.py`. They should FAIL before implementation.

### Unit Tests
- [ ] Test: `test_list_runs_returns_metadata` -- create two run dirs with summary.txt and metrics.jsonl, verify list_runs returns both with correct metadata (run_id, experiment_count, best_composite, total_cost) -- in `tests/test_data_loader.py`
- [ ] Test: `test_list_runs_empty_dir` -- with no run directories, returns empty list -- in `tests/test_data_loader.py`
- [ ] Test: `test_load_run_metrics_parses_jsonl` -- write 3 valid JSONL lines, verify load_run_metrics returns list of 3 dicts with correct fields -- in `tests/test_data_loader.py`
- [ ] Test: `test_load_run_metrics_skips_malformed_lines` -- write 3 lines with one invalid JSON, verify returns 2 valid records (no crash) -- in `tests/test_data_loader.py`
- [ ] Test: `test_load_run_metrics_missing_file` -- non-existent run_id returns empty list -- in `tests/test_data_loader.py`
- [ ] Test: `test_load_latest_metrics_incremental` -- write 5 lines, load_latest_metrics(after_line=3) returns only lines 4-5 -- in `tests/test_data_loader.py`
- [ ] Test: `test_load_run_summary_returns_text` -- write summary.txt, verify load_run_summary returns its content -- in `tests/test_data_loader.py`
- [ ] Test: `test_load_calibration_parses_json` -- write calibration.json, verify load_calibration returns dict with per_axis_kappa -- in `tests/test_data_loader.py`

All tests use `tmp_path` fixtures to create temporary run directories.

## Implementation
- [ ] Step 1: Implement `list_runs(base_dir: Path = Path("runs")) -> list[dict]` in `autotrust/dashboard/data_loader.py`:
  - Scan `base_dir` for subdirectories
  - For each, read `summary.txt` (parse key: value lines) and count lines in `metrics.jsonl`
  - Return list of dicts: `{"run_id": str, "date": str, "experiment_count": int, "best_composite": float, "total_cost": float, "status": str}`
  - Sort by date descending (newest first)
  ```python
  def list_runs(base_dir: Path = Path("runs")) -> list[dict]:
      """List all runs with metadata from summary.txt and metrics.jsonl."""
  ```
- [ ] Step 2: Implement `load_run_metrics(run_id: str, base_dir: Path = Path("runs")) -> list[dict]`:
  - Read `runs/<run_id>/metrics.jsonl`
  - Parse each line as JSON, skip malformed lines with a warning log
  - Return list of dicts
  ```python
  def load_run_metrics(run_id: str, base_dir: Path = Path("runs")) -> list[dict]:
      """Load metrics.jsonl for a run as a list of dicts."""
  ```
- [ ] Step 3: Implement `load_latest_metrics(run_id: str, after_line: int = 0, base_dir: Path = Path("runs")) -> tuple[list[dict], int]`:
  - Read only lines after `after_line` from `metrics.jsonl`
  - Return `(new_records, new_line_count)` so the caller can pass `new_line_count` as `after_line` next time
  ```python
  def load_latest_metrics(run_id: str, after_line: int = 0, base_dir: Path = Path("runs")) -> tuple[list[dict], int]:
      """Load only new lines from metrics.jsonl (for polling). Returns (records, total_line_count)."""
  ```
- [ ] Step 4: Implement `load_run_summary(run_id: str, base_dir: Path = Path("runs")) -> str`:
  - Read `runs/<run_id>/summary.txt` as plain text
  - Return empty string if file doesn't exist
  ```python
  def load_run_summary(run_id: str, base_dir: Path = Path("runs")) -> str:
      """Load summary.txt as plain text."""
  ```
- [ ] Step 5: Implement `load_calibration(path: Path = Path("gold_set/calibration.json")) -> dict`:
  - Read and parse `gold_set/calibration.json`
  - Return empty dict with defaults if file doesn't exist
  ```python
  def load_calibration(path: Path = Path("gold_set/calibration.json")) -> dict:
      """Load gold_set/calibration.json."""
  ```
- [ ] Step 6: Implement `load_spec_text(path: Path = Path("spec.yaml")) -> str`:
  - Read `spec.yaml` as raw text for display in the Config tab
  ```python
  def load_spec_text(path: Path = Path("spec.yaml")) -> str:
      """Load spec.yaml as raw text for display."""
  ```
- [ ] DRY check: reuses existing file paths/conventions from observe.py. Does NOT re-implement ExperimentResult parsing -- reads raw dicts from JSONL.

## TDD: Tests Pass (Green)
- [ ] All 8 unit tests pass
- [ ] All existing tests still pass

## Acceptance Criteria
- [ ] `autotrust/dashboard/data_loader.py` exists with all 6 functions
- [ ] `list_runs` returns correct metadata from real directory structure
- [ ] `load_run_metrics` handles malformed JSONL gracefully (skip bad lines, log warning)
- [ ] `load_latest_metrics` supports incremental polling (returns only new records)
- [ ] `load_calibration` returns defaults when file is missing
- [ ] All tests pass

## Execution
- **Agent Type**: python-expert
- **Wave**: 2 (depends on TASK_001 scaffold)
- **Complexity**: Medium
