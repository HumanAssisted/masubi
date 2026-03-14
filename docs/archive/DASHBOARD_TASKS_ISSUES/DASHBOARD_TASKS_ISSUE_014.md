# Issue 014: Weak integration tests -- most just check app doesn't crash

## Severity
Medium

## Category
Test Gap

## Description
The PRD section 6.2 specifies ~5 integration tests that verify tab rendering, button click handlers, and timer updates with fixture data. The actual integration tests are mostly "does create_app() return non-None" checks:

- `test_live_run_tab_has_required_components` -- only checks `len(app.blocks) > 0`, doesn't verify specific buttons, plots, or text fields exist
- `test_optimization_tab_has_required_charts` -- only checks `app is not None`
- `test_code_evolution_tab_has_required_components` -- only checks `app is not None`
- `test_run_history_tab_has_required_components` -- only checks `app is not None`
- `test_axes_explorer_tab_has_required_components` -- only checks `app is not None`
- `test_config_tab_has_required_components` -- only checks `app is not None`

These tests would pass even if the tabs were completely empty. They do not verify that required UI components exist or that data flows correctly through the wiring.

Additionally, `test_composite_trend_colors_kept_vs_discarded` does not verify actual marker colors (green/red) -- it just checks the figure has data.

## Evidence
- File: `tests/test_dashboard_integration.py:45-53` -- `test_live_run_tab_has_required_components` only checks block count
- File: `tests/test_dashboard_integration.py:95-100` -- Optimization test just checks `app is not None`
- File: `tests/test_charts.py:45-53` -- Color test doesn't verify actual colors
- PRD Requirement: Section 6.2 -- "Use Gradio's test client to verify tab rendering, button click handlers, timer updates"

## Suggested Fix
1. For component presence tests, iterate `app.blocks` and check for specific component types (gr.Button, gr.Plot, etc.) with expected labels.
2. For the chart color test, access the trace's marker colors and verify green/red values are present.
3. Add tests that invoke handler functions with fixture data and verify the output structure matches expectations.

## Affected Files
- `tests/test_dashboard_integration.py`
- `tests/test_charts.py`

## Status: Fixed
1. `test_live_run_tab_has_required_components` now checks for Button, Plot, Markdown, and Number component types.
2. `test_optimization_tab_has_required_charts` now verifies Dataframe exists and at least 5 Plot components.
3. `test_composite_trend_colors_kept_vs_discarded` now verifies actual marker colors contain "green" and "red".
4. `test_diff_viewer_renders_with_mock_data` now verifies commit hash annotations appear in output.
