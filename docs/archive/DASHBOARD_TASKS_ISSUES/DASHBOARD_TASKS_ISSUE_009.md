# Issue 009: Duplicate polling states cause doubled I/O and potential data inconsistency

## Severity
Medium

## Category
Quality

## Description
The Live Run tab and Optimization tab each have their own independent `gr.Timer` and `gr.State` for polling:
- Live Run: `timer = gr.Timer(value=2)` + `poll_state = gr.State({"line_count": 0, "metrics": []})`
- Optimization: `opt_timer = gr.Timer(value=3)` + `opt_state = gr.State({"line_count": 0, "metrics": []})`

Both timers independently read the same `metrics.jsonl` file and maintain separate copies of the metrics data in memory. This means:
1. Double the filesystem I/O during a live run
2. Two copies of all metrics in memory
3. The two states can be temporarily out of sync (different polling intervals: 2s vs 3s)

## Evidence
- File: `dashboard.py:228-229` -- Live Run timer and state
- File: `dashboard.py:267-268` -- Optimization tab timer and state
- PRD Requirement: Section 7 Risks -- "Large runs (1000+ experiments)" -- doubling I/O makes this worse

## Suggested Fix
Share a single polling timer and state across tabs. Use a single `gr.Timer` that updates a shared `gr.State`, then have both tabs' outputs wired to the same timer callback. Alternatively, use a server-side cache that both callbacks read from.

## Affected Files
- `dashboard.py`

## Status: Fixed
Added a shared `_poll_cache` dict and `_refresh_poll_cache()` function at module level. Both the Live Run and Optimization tabs now use this shared cache instead of maintaining independent `gr.State` objects. Eliminated the per-tab `gr.State` and `inputs` for polling. Single filesystem read shared across tabs.
