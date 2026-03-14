# Task 012: Build observe.py -- Structured Logging and Run Artifacts

## Context
`observe.py` handles structured logging via structlog (JSON output) and per-run artifact management under `runs/<run_id>/`. It logs experiment results including gate outcomes, Kappa downweight warnings, and explanation quality metrics. It provides a RunContext that manages the lifecycle of a single experiment run. See CURSOR_PLAN.md "Implementation Details > 8. observe.py".

## Goal
Build structured logging and run artifact management that captures all experiment data for debugging and analysis.

## Research First
- [ ] Read CURSOR_PLAN.md section "Implementation Details > 8. observe.py"
- [ ] Read `autotrust/schemas.py` for ExperimentResult, RunArtifacts models
- [ ] Read `autotrust/config.py` for Spec model
- [ ] Check structlog API: `structlog.configure()`, `structlog.get_logger()`, JSON renderer
- [ ] Verify `runs/` directory exists (from TASK_001 scaffold)

## TDD: Tests First (Red)
Write tests FIRST. They should FAIL before implementation.

### Unit Tests
- [ ] Test: `test_start_run_creates_directory` -- start_run() creates `runs/<run_id>/` directory -- in `tests/test_observe.py`
- [ ] Test: `test_start_run_snapshots_config` -- start_run() writes config.json with spec snapshot -- in `tests/test_observe.py`
- [ ] Test: `test_log_experiment_writes_metrics` -- log_experiment() writes metrics.json with gate results -- in `tests/test_observe.py`
- [ ] Test: `test_log_predictions_writes_jsonl` -- log_predictions() writes predictions.jsonl -- in `tests/test_observe.py`
- [ ] Test: `test_finalize_run_writes_summary` -- finalize_run() writes summary.txt -- in `tests/test_observe.py`
- [ ] Test: `test_log_downweight_warning` -- when axes are downweighted, a warning is logged with structlog -- in `tests/test_observe.py`

## Implementation
- [ ] Step 1: Create `autotrust/observe.py` with structlog configuration:
  - Configure structlog with JSON output, ISO timestamps, log level filtering
  - Module-level logger: `log = structlog.get_logger()`
- [ ] Step 2: Implement `RunContext` dataclass:
  - `run_id: str` (UUID or timestamp-based)
  - `run_dir: Path` (runs/<run_id>/)
  - `spec: Spec` (snapshot)
  - `start_time: datetime`
  - `logger: structlog.BoundLogger`
- [ ] Step 3: Implement `start_run(spec: Spec) -> RunContext`:
  - Generate run_id
  - Create `runs/<run_id>/` directory
  - Snapshot spec + effective weights to `config.json`
  - Return RunContext
- [ ] Step 4: Implement `log_experiment(ctx: RunContext, result: ExperimentResult) -> None`:
  - Write `metrics.json` with full ExperimentResult
  - Include gate_results (composite/gold/explanation), downweighted_axes, explanation mode (warn/gate)
  - Log structured event via structlog
- [ ] Step 5: Implement `log_predictions(ctx: RunContext, predictions: list) -> None`:
  - Write `predictions.jsonl` with per-chain trust vectors and explanations
- [ ] Step 6: Implement `finalize_run(ctx: RunContext) -> RunArtifacts`:
  - Write `summary.txt` with run overview (experiments, best composite, total cost, wall time)
  - Return RunArtifacts with all file paths
- [ ] Step 7: Implement calibration warning logging:
  - `log_downweight_warning(ctx, axis_name, original_weight, effective_weight, kappa)`: log when axis is downweighted
  - `log_weight_redistribution(ctx, redistributed: dict)`: log how weight was redistributed
- [ ] DRY check: uses schemas.ExperimentResult and RunArtifacts, doesn't redefine

## TDD: Tests Pass (Green)
- [ ] All 6 unit tests pass
- [ ] All existing tests still pass

## Acceptance Criteria
- [ ] `autotrust/observe.py` exists with all listed functions
- [ ] structlog configured with JSON output
- [ ] `start_run()` creates run directory and config snapshot
- [ ] `log_experiment()` writes complete metrics including gate results
- [ ] `finalize_run()` produces summary.txt
- [ ] Calibration warnings logged with structured data
- [ ] All tests pass

## Execution
- **Agent Type**: python
- **Wave**: 4 (depends on TASK_004 config, TASK_005 schemas; parallel with TASK_010, TASK_011)
- **Complexity**: Medium
