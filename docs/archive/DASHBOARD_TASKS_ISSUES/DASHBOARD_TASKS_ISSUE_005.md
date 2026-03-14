# Issue 005: Code Evolution tab change annotations missing composite/gate data

## Severity
Medium

## Category
Omission

## Description
The PRD section 4.3 specifies: "Change annotations -- for each diff, show the corresponding composite score, gate results, and whether it was kept." The implementation only shows `"Comparing {hash_a} -> {hash_b}"` as the annotation text. No composite score, no gate results, and no kept/discarded status is shown.

Additionally, `get_train_py_log()` always returns `"composite": None` for every commit. The PRD expects composite scores to appear in the commit log table, but they are never populated from metrics data.

## Evidence
- File: `dashboard.py:132` -- annotation is just `f"Comparing {hash_a} -> {hash_b}"`
- File: `autotrust/dashboard/git_history.py:53-60` -- `"composite": None` always
- PRD Requirement: Section 4.3 -- "Change annotations -- for each diff, show the corresponding composite score, gate results, and whether it was kept"

## Suggested Fix
1. In `get_train_py_log()`, parse composite scores from commit messages (e.g., regex on "experiment N: keep") or cross-reference with metrics.jsonl to populate the composite field.
2. In `show_diff()`, look up the experiment results for the selected commits and include composite score, gate results, and kept/discarded status in the annotation markdown.

## Affected Files
- `autotrust/dashboard/git_history.py`
- `dashboard.py`

## Status: Fixed
`get_train_py_log()` now parses composite scores from commit messages using regex (`composite[=:]\s*[\d.]+`). `show_diff()` now looks up commit metadata from the git log and includes composite score, kept/discarded status for both selected commits in the annotation.
