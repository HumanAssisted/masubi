# Issue 004: Discarded experiments toggle does nothing in Code Evolution tab

## Severity
High

## Category
Omission

## Description
The Code Evolution tab has a "Show discarded experiments" checkbox (`show_discarded`), and it is passed to the `show_diff()` handler function. However, `show_diff()` completely ignores the `show_discarded` parameter -- it only computes the diff between two selected commits and never calls `git_history.get_discarded_diffs()`.

The PRD section 4.3 specifies: "Discarded changes -- toggle to see diffs of experiments that were discarded (reverted). Helps understand what the agent tried but didn't work." This entire feature is unimplemented.

## Evidence
- File: `dashboard.py:125-133` -- `show_diff()` receives `show_discarded` but never uses it
- File: `autotrust/dashboard/git_history.py:119-141` -- `get_discarded_diffs()` exists but is never called from dashboard.py
- PRD Requirement: Section 4.3 -- "Discarded changes -- toggle to see diffs of experiments that were discarded"

## Suggested Fix
When `show_discarded` is True, call `git_history.get_discarded_diffs()` and display the discarded experiment metadata below the diff viewer. Format each discarded experiment with its change_description, composite score, and gate results.

```python
def show_diff(commit_a_str, commit_b_str, show_discarded):
    # ... existing diff logic ...

    if show_discarded:
        run_id = _run_manager.current_run_id
        if run_id:
            discarded = git_history.get_discarded_diffs(run_id)
            annotation += "\n\n### Discarded Experiments\n"
            for d in discarded:
                annotation += f"- Exp #{d['experiment']}: composite={d['composite']:.3f}, gates={d['gate_results']}\n"
                if d.get("change_description"):
                    annotation += f"  Description: {d['change_description']}\n"

    return diff, annotation
```

## Affected Files
- `dashboard.py`

## Status: Fixed
`show_diff()` now calls `git_history.get_discarded_diffs()` when `show_discarded` is True. Displays each discarded experiment with its number, composite score, gate results, and change description in the annotation markdown below the diff.
