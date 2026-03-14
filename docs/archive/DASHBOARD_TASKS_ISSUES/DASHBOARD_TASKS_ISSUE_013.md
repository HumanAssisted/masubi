# Issue 013: Run History tab missing sort/filter capability

## Severity
Low

## Category
Omission

## Description
PRD section 4.4 specifies: "Sort/filter by date, composite, cost." The Run History tab renders the run list as a static `gr.Dataframe` with `interactive=False`. There is no sort or filter UI. Gradio Dataframes do support column sorting when interactive, but the current implementation explicitly disables this.

## Evidence
- File: `dashboard.py:348` -- `interactive=False` on run_list Dataframe
- PRD Requirement: Section 4.4 -- "Sort/filter by date, composite, cost"

## Suggested Fix
Set `interactive=True` on the run list Dataframe to enable built-in Gradio column sorting. For filtering, add a text input or dropdown filters above the table.

## Affected Files
- `dashboard.py`

## Status: Fixed
Changed `interactive=False` to `interactive=True` on the Run History `gr.Dataframe`, enabling built-in Gradio column sorting.
