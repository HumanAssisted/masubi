# Task 011: Build Dashboard -- Code Evolution Tab (Git Diff Viewer)

## Context
The Code Evolution tab shows the git history of `train.py` -- the only file the agent edits. It displays a chronological commit log, side-by-side diff viewer for comparing any two commits, discarded experiment metadata, and change annotations (composite score, gate results, kept/discarded). This tab uses `git_history.py` (TASK_003) for all git operations. See GRADIO_DASHBOARD_PRD.md section 4.3 (Code Evolution).

## Goal
Add the Code Evolution tab with git log, diff viewer, and change annotations for train.py.

## Research First
- [ ] Read GRADIO_DASHBOARD_PRD.md section 4.3 (Code Evolution) for full layout
- [ ] Read `autotrust/dashboard/git_history.py` (TASK_003) for available functions
- [ ] Read `dashboard.py` (TASK_009) for tab structure
- [ ] Check `run_loop.py` `_handle_keep_discard()` for commit message format ("experiment N: keep")

## TDD: Tests First (Red)
Write tests in `tests/test_dashboard_integration.py` (append to existing). They should FAIL before implementation.

### Integration Tests
- [ ] Test: `test_code_evolution_tab_has_required_components` -- verify tab contains: commit log display, commit selector dropdowns (A and B), diff display, discarded toggle, change annotations -- in `tests/test_dashboard_integration.py`
- [ ] Test: `test_diff_viewer_renders_with_mock_data` -- mock git_history functions, select two commits, verify diff output is non-empty -- in `tests/test_dashboard_integration.py`

## Implementation
- [ ] Step 1: Add Code Evolution tab to `dashboard.py` `create_app()`:
  ```python
  with gr.Tab("Code Evolution"):
      _build_code_evolution_tab()
  ```
- [ ] Step 2: Implement `_build_code_evolution_tab()`:
  ```python
  def _build_code_evolution_tab():
      with gr.Row():
          refresh_btn = gr.Button("Refresh Git Log")
      with gr.Row():
          commit_log = gr.Dataframe(
              headers=["Hash", "Message", "Date", "Composite"],
              label="train.py Commit History",
          )
      with gr.Row():
          with gr.Column():
              commit_a = gr.Dropdown(label="Compare From (older)", choices=[])
              commit_b = gr.Dropdown(label="Compare To (newer)", choices=[])
              show_discarded = gr.Checkbox(label="Show discarded experiments", value=False)
              diff_btn = gr.Button("Show Diff")
          with gr.Column(scale=2):
              diff_display = gr.Code(label="Diff", language="diff")
      with gr.Row():
          change_annotation = gr.Markdown(label="Change Annotations")
  ```
- [ ] Step 3: Wire refresh button to load git log:
  ```python
  def refresh_git_log():
      commits = git_history.get_train_py_log()
      log_data = [[c["hash"][:7], c["message"], c["date"], c.get("composite", "")] for c in commits]
      choices = [f"{c['hash'][:7]} - {c['message']}" for c in commits]
      return log_data, gr.update(choices=choices), gr.update(choices=choices)

  refresh_btn.click(refresh_git_log, outputs=[commit_log, commit_a, commit_b])
  ```
- [ ] Step 4: Wire diff button:
  ```python
  def show_diff(commit_a_str, commit_b_str, show_discarded):
      if not commit_a_str or not commit_b_str:
          return "Select two commits to compare.", ""
      hash_a = commit_a_str.split(" - ")[0]
      hash_b = commit_b_str.split(" - ")[0]
      diff = git_history.get_diff(hash_a, hash_b)
      # Build annotation from metrics if available
      annotation = f"Comparing {hash_a} -> {hash_b}"
      return diff, annotation

  diff_btn.click(show_diff, inputs=[commit_a, commit_b, show_discarded], outputs=[diff_display, change_annotation])
  ```
- [ ] Step 5: Handle discarded experiments toggle:
  - When checked, also show metadata from `git_history.get_discarded_diffs()` below the commit log
  - These are experiments that were tried but reverted (not in git history)
- [ ] DRY check: all git operations delegated to git_history.py. No subprocess calls in dashboard.py.

## TDD: Tests Pass (Green)
- [ ] All 2 new integration tests pass
- [ ] All existing tests still pass

## Acceptance Criteria
- [ ] Code Evolution tab exists in the Gradio app
- [ ] Commit log shows hash, message, date, composite for each train.py commit
- [ ] Diff viewer shows unified diff between two selected commits
- [ ] Discarded experiments toggle shows metadata of reverted changes
- [ ] Change annotations display composite score and gate results for each commit
- [ ] All tests pass

## Execution
- **Agent Type**: python-expert
- **Wave**: 5 (depends on TASK_003 git_history, TASK_009 dashboard_live_run)
- **Complexity**: Medium
