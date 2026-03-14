# Issue 008: log_experiment overwrites metrics.json on each call

## Severity
Medium

## Category
Bug

## Description
In `observe.py`, `log_experiment()` writes the experiment result to `metrics.json` using `write_text()` (line 79), which overwrites the file each time. In a multi-experiment run, only the last experiment's metrics persist on disk. While the `RunContext.experiments` list accumulates all results in memory, if the process crashes, all previous experiment data is lost.

The PRD specifies "every experiment gets a `runs/<run_id>/` directory with metrics.json" -- but with the current implementation, only the final experiment's metrics survive.

## Evidence
- File: `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/observe.py:78-79` -- `metrics_path = ctx.run_dir / "metrics.json"; metrics_path.write_text(json.dumps(result_dict, ...))`
- PRD Requirement: INITIAL_DESIGN_CHOICES.md "Observability: Structured Logs + Run Artifacts" -- "Every experiment gets a runs/<run_id>/ directory with metrics.json"

## Suggested Fix
Either:
1. **Append to a JSONL file** (recommended): Change `metrics.json` to `metrics.jsonl` and append each experiment:
   ```python
   metrics_path = ctx.run_dir / "metrics.jsonl"
   with open(metrics_path, "a") as f:
       f.write(json.dumps(result_dict, default=str) + "\n")
   ```
2. **Write all experiments**: Write the entire `ctx.experiments` list each time:
   ```python
   metrics_path.write_text(json.dumps(ctx.experiments, indent=2, default=str))
   ```
Update `RunArtifacts.metrics_json` field name/type accordingly, and update `test_log_experiment_writes_metrics` to verify accumulation.

## Affected Files
- `autotrust/observe.py`
- `autotrust/schemas.py` (RunArtifacts field name if changed)
- `tests/test_observe.py`
