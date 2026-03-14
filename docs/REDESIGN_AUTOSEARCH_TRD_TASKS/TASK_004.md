# Task 004: autotrust/freeze.py -- Teacher Artifact Extraction

## Context
The REDESIGN_AUTOSEARCH_TRD requires that Stage 1 outputs (optimized prompts, labeling rules, explanation schema) are frozen before Stage 2 begins. Currently, when Stage 1 completes, there is no mechanism to extract and freeze these artifacts. The `teacher/` directory referenced in the PRD file layout does not exist.

The freeze step:
1. Extracts the best-performing `train.py` (the kept commit with highest composite)
2. Parses out the scoring prompt, explanation format, and escalation logic
3. Writes frozen artifacts to `teacher/`
4. Re-labels all synthetic training data using the frozen teacher prompts
5. Commits the frozen artifacts to git

## Goal
Implement `autotrust/freeze.py` that extracts Stage 1 outputs into frozen teacher artifacts and re-labels training data.

## Research First
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/docs/REDESIGN_AUTOSEARCH.md` lines 57-64 (Stage 1 outputs)
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/train.py` (current scorer -- understand what to extract)
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/dashboard/git_history.py` (existing git utilities)
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/run_loop.py` lines 206-231 (existing git keep/discard)
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/schemas.py` -- `TeacherArtifacts` from TASK_002

## TDD: Tests First (Red)

### Unit Tests
- [ ] Test: `test_extract_prompt_pack` in `tests/test_freeze.py` -- given a `train.py` string, extracts prompt template into YAML structure
- [ ] Test: `test_extract_label_rules` -- extracts threshold/escalation rules from `train.py` code
- [ ] Test: `test_extract_explanation_schema` -- extracts reason tag vocabulary
- [ ] Test: `test_write_teacher_artifacts` -- writes `prompt_pack.yaml`, `label_rules.yaml`, `explanation_schema.json` to `teacher/`
- [ ] Test: `test_freeze_creates_teacher_dir` -- `teacher/` directory is created if it does not exist
- [ ] Test: `test_freeze_returns_teacher_artifacts` -- returns a `TeacherArtifacts` model with correct paths

### Integration Tests
- [ ] Test: `test_freeze_from_git_history` -- given a mocked git log with composite scores, selects the best commit and extracts artifacts
- [ ] Test: `test_relabel_training_data` -- takes existing synth_data JSONL, re-labels each chain using frozen teacher, writes updated JSONL with soft trust vectors

## Implementation
- [ ] Step 1: Create `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/freeze.py`
- [ ] Step 2: Implement `extract_prompt_pack(train_py_source: str) -> dict`:
  - Parse the `_build_prompt` method to extract the scoring prompt template
  - Parse `_build_axis_guidance` to extract per-axis guidance
  - Return structured YAML-serializable dict
- [ ] Step 3: Implement `extract_label_rules(train_py_source: str) -> dict`:
  - Extract flag threshold, escalation logic, scoring heuristics
  - Return structured dict for `label_rules.yaml`
- [ ] Step 4: Implement `extract_explanation_schema(train_py_source: str) -> dict`:
  - Extract reason tag vocabulary (axis names used in reasons)
  - Extract explanation format spec
  - Return structured dict for `explanation_schema.json`
- [ ] Step 5: Implement `freeze_teacher(spec: Spec, run_id: str | None = None) -> TeacherArtifacts`:
  - Find best `train.py` commit from git history (highest composite)
  - Read `train.py` at that commit via `git show`
  - Call extract functions
  - Write to `teacher/` directory
  - Return `TeacherArtifacts` with paths
- [ ] Step 6: Implement `relabel_training_data(artifacts: TeacherArtifacts, spec: Spec) -> Path`:
  - Load existing `synth_data/train.jsonl`
  - For each chain, score using frozen teacher prompts via ScoringProvider
  - Write updated JSONL with soft trust vectors as training targets
  - Return output path
- [ ] Step 7: Add CLI: `uv run python -m autotrust.freeze [--run-id <id>]`
- [ ] DRY check: Reuse `git_history.get_file_at_commit()` and `git_history.get_train_py_log()` from dashboard module

## TDD: Tests Pass (Green)
- [ ] All new tests in `test_freeze.py` pass
- [ ] All existing tests still pass

## Acceptance Criteria
- [ ] `freeze_teacher()` creates `teacher/prompt_pack.yaml`, `teacher/label_rules.yaml`, `teacher/explanation_schema.json`
- [ ] Frozen artifacts are valid YAML/JSON and round-trip correctly
- [ ] `relabel_training_data()` produces updated JSONL with soft trust vectors
- [ ] CLI works: `uv run python -m autotrust.freeze`
- [ ] No existing test is broken

## Execution
- **Agent Type**: coding subagent
- **Wave**: 2 (parallel with TASK_003, TASK_005; depends on Wave 1)
- **Complexity**: Medium
