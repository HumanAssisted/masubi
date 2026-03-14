# Issue 015: Config tab weights_table not populated on app start

## Severity
Low

## Category
Omission

## Description
PRD section 4.6 and TASK_014 specify that the Config tab should load initial values on app start via `app.load(refresh_config, outputs=[spec_display, calibration_display, weights_table])`. The implementation loads `spec_display` and `calibration_display` initial values at tab build time (lines 461, 466), but `weights_table` is only populated when the user clicks "Refresh Config".

On first visit to the Config tab, the spec.yaml and calibration report are visible, but the "Current Effective Weights" table is empty.

## Evidence
- File: `dashboard.py:469-472` -- `weights_table` has no initial value
- File: `dashboard.py:496-498` -- `refresh_config_btn.click(...)` populates table only on click
- TASK_014 Step 4 -- "Load initial values on app start: app.load(refresh_config, ...)"

## Suggested Fix
Add `app.load(refresh_config, outputs=[spec_display, calibration_display, weights_table])` inside `create_app()` after all tabs are built, or compute the weights data at build time and pass it as the `value` parameter to `gr.Dataframe`.

## Affected Files
- `dashboard.py`

## Status: Fixed
Added initial weights computation at Config tab build time using `get_spec()` and `get_effective_weights()` (with try/except fallback). The `weights_table` `gr.Dataframe` now receives `value=_init_weights` so it is populated on first render.
