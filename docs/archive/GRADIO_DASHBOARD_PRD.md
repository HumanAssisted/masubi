# Gradio Dashboard PRD/TRD (v2)

## 1. Problem Statement

The autoresearch loop (`run_loop.py`) runs autonomously for hours or overnight, producing experiment results as JSONL files in `runs/<run_id>/metrics.jsonl` and text summaries. Currently there is **no way to**:

- **Monitor a live run** -- the only feedback is structlog JSON printed to stdout.
- **See progress at a glance** -- no log-style view showing experiments as they arrive.
- **See if the agent is actually optimizing** -- no composite trend, no improvement signal.
- **Inspect what the agent changed** -- train.py is agent-edited, but there's no diff viewer showing what changed per experiment.
- **Browse historical runs** without manual `jq` on raw JSONL files.
- **Compare code versions** -- no way to see the evolution of train.py across experiments.

## 2. Goal

A researcher can **launch the autoresearch loop from a browser tab**, immediately see a composite trend chart showing whether the agent is improving, watch per-axis radar charts and gate timelines update in real time, scroll down to expandable log entries for detail, drill into git diffs of train.py to see what the agent changed, browse past runs, and stop/pause the loop -- all without touching a terminal.

## 3. Key Design Principles

1. **Charts-first UX**: Graphs are the hero. The primary view leads with a large composite trend chart, per-axis radar, cost burn gauge, and gate timeline -- the researcher's eye should immediately land on "is this going up?" The log stream lives below the charts as a scrollable detail panel.

2. **Logs for depth**: Below the prominent charts, a structured log stream shows per-experiment progress as expandable entries. Charts give the signal; logs give the detail.

3. **train.py is agent-edited**: The agent (not a person) modifies train.py. The dashboard provides a git log/diff viewer so researchers can see *what* the agent changed and *whether* those changes improved scores.

4. **Text file storage**: All run history is stored in plain text files (JSONL, summary.txt, config.json). No database. The dashboard reads from the filesystem.

5. **Minimal invasion**: Only `run_loop.py` gets modified (optional stop/pause callbacks). All other modules remain untouched.

## 4. Dashboard Tabs

### 4.1 Live Run (Primary View) -- Charts First

The main tab. **Charts dominate the top 2/3 of the viewport.** The log stream is a scrollable panel below.

**Layout (top to bottom):**

**Row 0 -- Controls**: Start, Stop, Pause/Resume buttons + max_experiments input + status indicator + cost so far.

**Row 1 -- Hero Charts** (large, ~60% of viewport):
- **Left (wide)**: Composite trend line -- the main signal. Each point is an experiment. Kept experiments are green dots, discarded are red. Clear upward slope = working, flat = stalled. This is the single most important visual.
- **Right (narrow)**: Cost burn gauge -- cumulative spend vs budget limit line.

**Row 2 -- Secondary Charts** (medium):
- **Left**: Per-axis radar/spider chart for the latest experiment (or selected experiment).
- **Center**: Gate timeline -- scatter plot showing pass/fail for each gate across experiments.
- **Right**: Stall indicator -- consecutive no-improvement count, LoRA nudge threshold marker.

**Row 3 -- Log Stream** (scrollable, bottom ~35%):
Experiments as expandable log entries, newest first:
```
[14:23:07] Exp #3  composite=0.724 (+0.031)  KEPT  gates: ✓composite ✓gold ✓explanation  $0.03
[14:21:42] Exp #2  composite=0.693 (+0.012)  KEPT  gates: ✓composite ✓gold ⚠explanation(warn)  $0.02
[14:20:15] Exp #1  composite=0.681  KEPT (baseline)  gates: ✓composite ✓gold ⚠explanation(warn)  $0.02
```

**Expanded entry** (click to reveal):
- Per-axis scores table (axis name, score, delta from previous)
- Gate results with reasons (why gold veto passed/failed, explanation quality score)
- Explanation text (reasons + summary)
- Cost breakdown
- Link to code diff ("View what changed")

**Real-time**: `gr.Timer(every=2)` polls metrics.jsonl, updates all charts and appends new log entries.

### 4.2 Optimization Dashboard

Deeper "is the agent actually improving?" analysis. All charts, no logs.

- **Composite trend line** (large) -- same as Live Run but with more context (baseline markers, best-so-far line, improvement rate annotation).
- **Per-axis improvement heatmap** -- which axes are improving, which are degrading.
- **Stall indicator** -- consecutive no-improvement count, LoRA nudge threshold.
- **Gate pass rate** -- what % of experiments pass all three gates.
- **Cost efficiency** -- composite improvement per dollar spent.
- **Best scores table** -- current best per-axis scores vs initial baseline.

### 4.3 Code Evolution (Git Diff Viewer)

train.py is the only mutable file. This tab shows its evolution:

- **Git log for train.py** -- chronological list of experiment commits:
  ```
  abc1234  experiment 5: keep   composite=0.752  2024-03-14 14:35
  def5678  experiment 3: keep   composite=0.724  2024-03-14 14:23
  890abcd  experiment 1: keep   composite=0.681  2024-03-14 14:20
  ```
- **Side-by-side diff** -- select any two versions to compare. Shows what the agent added/removed/changed.
- **Discarded changes** -- toggle to see diffs of experiments that were discarded (reverted). Helps understand what the agent tried but didn't work.
- **Change annotations** -- for each diff, show the corresponding composite score, gate results, and whether it was kept.

### 4.4 Run History

Browse all past runs. Each run is a directory of text files.

- **Run list** -- table showing: run_id, date, experiment count, best composite, total cost, status (completed/stopped/running).
- **Sort/filter** by date, composite, cost.
- **Run detail** -- click to see full metrics.jsonl rendered as a log + charts.
- **Side-by-side comparison** -- select two runs, see grouped bar chart of best metrics.
- **Export** -- download metrics.jsonl or summary.txt directly.

### 4.5 Axes Explorer

Per-axis deep dive:

- **Multi-line time series** -- checkboxes to select axes, see trends across experiments.
- **Kappa downweight visualization** -- bar chart showing per-axis Kappa with threshold line.
- **Axis correlation** -- which axes improve/degrade together.

### 4.6 Config

Read-only reference:

- `spec.yaml` rendered in a code block.
- Calibration report (if exists) as formatted JSON.
- Current effective weights (after Kappa downweighting).

## 5. Technical Design

### 5.1 Architecture

```
dashboard.py                      # Gradio Blocks app entry point
autotrust/dashboard/              # Dashboard support package
    __init__.py
    run_manager.py                # Thread mgmt for run_loop (start/stop/pause)
    data_loader.py                # Read runs/ text files, parse JSONL
    git_history.py                # Parse train.py git log, generate diffs
    charts.py                     # Plotly figure builders
    log_formatter.py              # Format experiment results as log entries
```

### 5.2 Data Flow

```
run_loop.py (background thread)
    |
    | writes to filesystem (text files)
    v
runs/<run_id>/metrics.jsonl     <--- data_loader.py reads
runs/<run_id>/config.json            (polled by gr.Timer every 2s)
runs/<run_id>/summary.txt            |
gold_set/calibration.json           v
spec.yaml                      log_formatter.py formats
                                charts.py builds figures
    |                                |
    v                                v
git log --follow train.py       dashboard.py renders in Gradio
    |
    v
git_history.py parses
```

### 5.3 Run Manager (`run_manager.py`)

```python
class RunManager:
    """Manages the autoresearch loop in a background thread."""

    def __init__(self):
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._current_run_id: str | None = None
        self._status: str = "idle"  # idle | running | paused | stopping

    def start(self, max_experiments: int = 50) -> str:
        """Launch run_autoresearch in a daemon thread. Returns run_id."""

    def stop(self) -> None:
        """Signal graceful stop after current experiment."""

    def pause(self) -> None:
        """Pause between experiments."""

    def resume(self) -> None:
        """Resume from pause."""

    @property
    def status(self) -> str: ...

    @property
    def current_run_id(self) -> str | None: ...
```

**Hook into `run_loop.py`**: Add optional `stop_check` and `pause_check` callback parameters to `run_autoresearch()`. Minimal change -- backward-compatible.

### 5.4 Data Loader (`data_loader.py`)

All functions read plain text files. No database.

```python
def list_runs(base_dir: Path = Path("runs")) -> list[dict]:
    """List all runs with metadata from summary.txt and metrics.jsonl."""

def load_run_metrics(run_id: str, base_dir: Path = Path("runs")) -> list[dict]:
    """Load metrics.jsonl for a run as a list of dicts."""

def load_latest_metrics(run_id: str, after_line: int = 0) -> list[dict]:
    """Load only new lines from metrics.jsonl (for polling)."""

def load_run_summary(run_id: str) -> str:
    """Load summary.txt as plain text."""

def load_calibration() -> dict:
    """Load gold_set/calibration.json."""

def load_spec_text() -> str:
    """Load spec.yaml as raw text for display."""
```

### 5.5 Git History Parser (`git_history.py`)

```python
def get_train_py_log() -> list[dict]:
    """Get git log for train.py. Returns list of:
    {"hash": "abc1234", "message": "experiment 5: keep", "date": "...", "composite": 0.752}
    """

def get_diff(hash_a: str, hash_b: str, file: str = "train.py") -> str:
    """Get unified diff between two commits for a file."""

def get_file_at_commit(commit_hash: str, file: str = "train.py") -> str:
    """Get file contents at a specific commit."""

def get_discarded_diffs(run_id: str) -> list[dict]:
    """Reconstruct diffs of discarded experiments from metrics.jsonl change_descriptions."""
```

### 5.6 Log Formatter (`log_formatter.py`)

```python
def format_experiment_log_entry(result: dict, prev_composite: float | None) -> str:
    """Format a single experiment as a collapsed log line.
    [14:23:07] Exp #3  composite=0.724 (+0.031)  KEPT  gates: ✓✓✓  $0.03
    """

def format_experiment_detail(result: dict, prev_best: dict | None) -> str:
    """Format expanded detail view with per-axis deltas, gate reasons, explanation."""

def format_log_stream(metrics: list[dict]) -> str:
    """Format full metrics list as a log stream (newest first)."""
```

### 5.7 Charts (`charts.py`)

Each function returns a `plotly.graph_objects.Figure`:

```python
# Optimization Dashboard
def composite_trend(metrics: list[dict]) -> go.Figure:
    """Line chart of composite score over experiments with improvement markers."""

def axis_improvement_heatmap(metrics: list[dict]) -> go.Figure:
    """Heatmap showing per-axis score changes across experiments."""

def gate_pass_rate(metrics: list[dict]) -> go.Figure:
    """Stacked bar showing gate pass/fail per experiment."""

def cost_efficiency(metrics: list[dict]) -> go.Figure:
    """Composite improvement per dollar spent."""

# Axes Explorer
def axis_trends(metrics: list[dict], axes: list[str]) -> go.Figure:
    """Multi-line chart of selected axes over experiments."""

def kappa_bars(calibration: dict) -> go.Figure:
    """Bar chart of per-axis Kappa with threshold line."""

# Run Comparison
def run_comparison(metrics1: list[dict], metrics2: list[dict]) -> go.Figure:
    """Grouped bar comparing best metrics of two runs."""

# Cost
def cost_burn(metrics: list[dict], budget_limit: float) -> go.Figure:
    """Cumulative cost line with budget threshold."""
```

### 5.8 Modifications to Existing Code

**`run_loop.py`** -- add optional callback parameters:

```python
def run_autoresearch(
    max_experiments: int = 50,
    stop_check: Callable[[], bool] | None = None,
    pause_check: Callable[[], bool] | None = None,
) -> None:
    # In the main loop, after each experiment:
    if stop_check and stop_check():
        logger.info("Stop requested. Ending loop.")
        break
    while pause_check and pause_check():
        time.sleep(1)
```

**No changes** to: `eval.py`, `schemas.py`, `config.py`, `data.py`, `observe.py`, `train.py`, `program.md`, `spec.yaml`, providers/, or any existing tests.

### 5.9 Dependencies

Add to `pyproject.toml`:

```toml
[project.optional-dependencies]
dashboard = [
    "gradio>=5.0",
    "plotly>=5.0",
    "pandas>=2.0",
]
```

Dashboard is optional -- the core autoresearch loop does not require Gradio.

## 6. Test Strategy

### 6.1 Unit Tests (TDD -- write first)

- **`tests/test_data_loader.py`** (~8 tests): `list_runs`, `load_run_metrics`, `load_latest_metrics` against fixture JSONL files in a temp directory. Empty run handling, malformed JSONL resilience, incremental load.
- **`tests/test_log_formatter.py`** (~6 tests): Format collapsed/expanded entries. Verify delta computation, gate symbols, cost formatting.
- **`tests/test_git_history.py`** (~5 tests): Parse git log output, generate diffs. Mock subprocess calls to git.
- **`tests/test_charts.py`** (~8 tests): Each chart builder returns a valid `plotly.graph_objects.Figure` with expected traces. Edge cases: single experiment, empty data, missing axes.
- **`tests/test_run_manager.py`** (~6 tests): Start/stop/pause lifecycle using a mock `run_autoresearch`. Verify status transitions, thread cleanup, stop flag propagation.

### 6.2 Integration Tests

- **`tests/test_dashboard_integration.py`** (~5 tests): Use Gradio's test client to verify tab rendering, button click handlers, timer updates with fixture data.

### 6.3 Existing Tests

All 103 existing tests must continue to pass. The `run_loop.py` signature change is backward-compatible (optional params with defaults).

## 7. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Thread safety: run_loop writes while dashboard reads | JSONL is append-only; dashboard reads from start each poll. File-level atomicity sufficient. |
| Large runs (1000+ experiments) | Downsample for live charts; full data in Axes Explorer with scroll. |
| Git subprocess in dashboard process | Use `subprocess.run` with timeout; cache results; only refresh on tab focus. |
| Discarded diffs not in git history | Discarded experiments revert train.py. We can't show their diffs from git. Store proposed changes in metrics.jsonl (add `proposed_code` field) or use `git stash`. |

## 8. Out of Scope

- **Authentication/multi-user** -- local researcher tool.
- **Database backend** -- filesystem (text files) is the source of truth.
- **Editing train.py from the dashboard** -- the agent loop handles that.
- **OpenTelemetry/Prometheus** -- may add later.
- **Cloud/HF Spaces deployment** -- local only.
- **Editing spec.yaml from the dashboard** -- read-only.
- **Multiple concurrent runs** -- single run at a time for v1.

## 9. Execution Plan (Wave Summary)

Tasks are in `docs/DASHBOARD_TASKS/`. Grouped by dependency order:

```
Wave 1 (no dependencies):
  TASK_001  Scaffold & Dependencies              infra-sre-architect  Low

Wave 2 (depends on Wave 1 -- all parallel):
  TASK_002  data_loader.py                        python-expert        Medium
  TASK_003  git_history.py                        python-expert        Medium
  TASK_004  log_formatter.py                      python-expert        Low
  TASK_008  run_loop.py callbacks (stop/pause)    python-expert        Low

Wave 3 (depends on Wave 1 + Wave 2 partial):
  TASK_005  charts.py core (Live Run)             python-expert        Medium
  TASK_006  charts.py advanced (Optimization+)    python-expert        Medium
  TASK_007  run_manager.py (thread mgmt)          python-expert        Medium

Wave 4 (depends on Waves 2-3 -- assembles the primary tab):
  TASK_009  dashboard.py -- Live Run tab          python-expert        High

Wave 5 (depends on Wave 4 -- all parallel secondary tabs):
  TASK_010  Optimization Dashboard tab            python-expert        Medium
  TASK_011  Code Evolution tab (git diffs)        python-expert        Medium
  TASK_012  Run History tab                       python-expert        Medium
  TASK_013  Axes Explorer tab                     python-expert        Medium
  TASK_014  Config tab (read-only)                python-expert        Low

Wave 6 (final -- depends on all):
  TASK_015  Cleanup, DRY review, full test suite  python-expert        Medium
```

**Total: 15 tasks, 6 waves, ~38 unit tests + ~12 integration tests.**

## Execution Results

**Status**: All 15 tasks completed across 6 waves.

**Test Summary**:
- 160 total tests pass (103 original + 57 new dashboard tests)
- 8 data_loader tests, 5 git_history tests, 6 log_formatter tests
- 16 chart tests (8 core + 8 advanced), 6 run_manager tests
- 3 run_loop callback tests, 13 dashboard integration tests
- Zero ruff warnings/errors

**Files Created**:
- `autotrust/dashboard/__init__.py` -- package init with __all__
- `autotrust/dashboard/data_loader.py` -- 6 functions for filesystem-based run data reading
- `autotrust/dashboard/git_history.py` -- 4 functions for git log/diff parsing with input sanitization
- `autotrust/dashboard/log_formatter.py` -- 3 functions for experiment log formatting
- `autotrust/dashboard/charts.py` -- 11 Plotly figure builders (5 core + 6 advanced)
- `autotrust/dashboard/run_manager.py` -- RunManager class with thread-safe start/stop/pause
- `dashboard.py` -- Gradio Blocks app with 6 tabs (Live Run, Optimization, Code Evolution, Run History, Axes Explorer, Config)
- `tests/test_data_loader.py`, `tests/test_git_history.py`, `tests/test_log_formatter.py`, `tests/test_charts.py`, `tests/test_run_manager.py`, `tests/test_dashboard_integration.py`

**Files Modified**:
- `pyproject.toml` -- added dashboard optional dependency group
- `run_loop.py` -- added stop_check/pause_check callback parameters (backward-compatible)

**Deviations from PRD**:
- Gradio 6.x installed (PRD specified >=5.0): Timer uses `value=` param instead of `every=`; Code component does not support `language="diff"` (uses default instead)
- Plotly 6.x installed (PRD specified >=5.0): fully compatible
- All dashboard tabs built in a single dashboard.py file rather than separate tab modules (simpler, less boilerplate)

## Review Summary

**Review Date**: 2026-03-14
**Reviewer**: Deep Review (automated)

### Issue Counts by Severity
| Severity | Count |
|----------|-------|
| Critical | 1     |
| High     | 3     |
| Medium   | 8     |
| Low      | 4     |
| **Total** | **16** |

### Issues by Category
| Category     | Count |
|--------------|-------|
| Bug          | 4     |
| Omission     | 5     |
| Quality      | 2     |
| DRY Violation| 1     |
| Test Gap     | 1     |
| Security     | 0     |
| Performance  | 0     |

### Requirements Met
- **Scaffold & Dependencies**: All met
- **data_loader.py**: 6/6 functions implemented; incremental polling works; malformed JSONL handled
- **git_history.py**: 4/4 functions implemented; input sanitization present; subprocess timeouts enforced
- **log_formatter.py**: 3/3 functions implemented; newest-first ordering works
- **charts.py**: 11/11 chart builders implemented; all handle empty data gracefully
- **run_manager.py**: Start/stop/pause lifecycle works; thread is daemon
- **run_loop.py callbacks**: stop_check/pause_check added; backward-compatible
- **Dashboard tabs**: All 6 tabs render (Live Run, Optimization, Code Evolution, Run History, Axes Explorer, Config)

### Key Gaps
- **CRITICAL**: RunManager generates its own run_id but never passes it to run_autoresearch. The dashboard polling can never find actual run data (Issue 001).
- **HIGH**: RunManager silently swallows all exceptions from the background thread (Issue 002).
- **HIGH**: Module-level import of run_loop creates tight coupling to the full autoresearch stack (Issue 003).
- **HIGH**: "Show discarded experiments" toggle is wired but does nothing (Issue 004).

### Tests
- **160 total tests pass** (103 original + 57 new dashboard tests)
- All original tests unaffected by dashboard changes
- Integration tests are shallow (mostly "app doesn't crash" checks)
- Chart color test does not verify actual colors

### Recommendation
**Needs rework** -- Issue 001 (run_id mismatch) is a critical bug that makes the Live Run tab non-functional for real runs. Issues 002-004 are high-severity problems that significantly degrade the user experience. These 4 issues should be fixed before shipping. The remaining 12 medium/low issues can be addressed in a follow-up iteration.
