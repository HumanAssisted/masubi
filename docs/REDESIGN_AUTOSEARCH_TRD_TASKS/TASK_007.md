# Task 007: autotrust/inference.py -- Local Inference with Escalation

## Context
The REDESIGN_AUTOSEARCH_TRD specifies Stage 3 (production inference) where the trained student model runs locally without API dependencies, falling back to the cloud judge (Anthropic Opus) only when the student's `escalate` flag is set. This module bridges the student model output to the existing `ScorerOutput` schema and integrates with the existing `JudgeProvider` for fallback.

## Goal
Implement `autotrust/inference.py` with local inference that loads a checkpoint, scores email chains, and selectively escalates to the cloud judge.

## Research First
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/docs/REDESIGN_AUTOSEARCH.md` lines 115-123 (Stage 3 spec)
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/student.py` -- `DenseStudent`, `MoEStudent`, `predict()` from TASK_003/006
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/export.py` -- `load_pytorch()` from TASK_005
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/eval.py` lines 225-254 -- existing `run_judge_fallback()` pattern
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/providers/anthropic.py` -- `AnthropicJudge` interface
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/schemas.py` -- `ScorerOutput`, `StudentOutput`

## TDD: Tests First (Red)

### Unit Tests
- [ ] Test: `test_local_inference_loads_checkpoint` in `tests/test_inference.py` -- `LocalInference(path)` loads model from checkpoint
- [ ] Test: `test_local_inference_scores_chain` -- `score(chain)` returns `ScorerOutput` with valid trust vector
- [ ] Test: `test_local_inference_no_api_dependency` -- scoring works without any API keys set
- [ ] Test: `test_escalation_decision_true` -- `should_escalate(output, spec)` returns True when escalate flag is set and `spec.production.escalate_on_flag` is True
- [ ] Test: `test_escalation_decision_false` -- returns False when escalate flag is False
- [ ] Test: `test_escalation_disabled_in_spec` -- returns False when `spec.production.escalate_on_flag` is False, regardless of flag
- [ ] Test: `test_score_with_fallback_escalates` -- `score_with_fallback(chain, judge, spec)` calls judge when escalation triggered
- [ ] Test: `test_score_with_fallback_skips_judge` -- does not call judge when no escalation
- [ ] Test: `test_student_output_to_scorer_output` -- conversion from `StudentOutput` to `ScorerOutput` preserves trust vector and maps reason tags to Explanation

### Integration Tests
- [ ] Test: `test_inference_pipeline_end_to_end` -- create model, export checkpoint, load via LocalInference, score a chain, verify output shape

## Implementation
- [ ] Step 1: Create `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/inference.py`
- [ ] Step 2: Implement `LocalInference`:
  ```python
  class LocalInference:
      """Load a student model checkpoint and run local trust scoring."""

      def __init__(self, checkpoint_path: Path):
          self.model, self.config, self.meta = load_pytorch(checkpoint_path)
          self.model.eval()
          self._tokenizer = None  # lazy-loaded

      def score(self, chain: EmailChain) -> ScorerOutput:
          """Score an email chain using the local student model."""
          input_ids = self._tokenize(chain)
          student_output = predict(self.model, input_ids, get_spec(), self._reason_tag_names())
          return self._to_scorer_output(student_output)

      def should_escalate(self, output: ScorerOutput, spec: Spec) -> bool:
          """Check if the scoring result should be escalated to cloud judge."""
          if not spec.production or not spec.production.escalate_on_flag:
              return False
          # Check if any subtle axis exceeds escalation threshold
          ...

      def score_with_fallback(
          self, chain: EmailChain, judge: JudgeProvider | None, spec: Spec
      ) -> ScorerOutput:
          """Score locally, escalate to judge if needed."""
          output = self.score(chain)
          if judge and self.should_escalate(output, spec):
              judge_scores = judge.judge(chain, spec.axis_groups.subtle)
              # Merge judge scores into output
              ...
          return output
  ```
- [ ] Step 3: Implement `_to_scorer_output()` conversion:
  ```python
  def _to_scorer_output(self, student_output: StudentOutput) -> ScorerOutput:
      """Convert StudentOutput to ScorerOutput for compatibility."""
      return ScorerOutput(
          trust_vector=student_output.trust_vector,
          explanation=Explanation(
              reasons=student_output.reason_tags,
              summary=self._generate_summary(student_output),
          ),
      )
  ```
- [ ] Step 4: Implement tokenization (simple tokenizer for email text):
  ```python
  def _tokenize(self, chain: EmailChain) -> Tensor:
      """Tokenize email chain text for model input."""
      # Concatenate emails with separators
      # Use simple tokenizer (byte-pair or character-level)
  ```
- [ ] DRY check: Reuse `run_judge_fallback()` pattern from `eval.py`; reuse `ScorerOutput` from `schemas.py`

## TDD: Tests Pass (Green)
- [ ] All new tests in `test_inference.py` pass
- [ ] All existing tests still pass

## Acceptance Criteria
- [ ] `LocalInference(path)` loads a checkpoint and scores email chains
- [ ] No API keys required for local-only scoring
- [ ] `should_escalate()` respects `spec.production` configuration
- [ ] `score_with_fallback()` calls judge only when escalation is triggered
- [ ] Output is a valid `ScorerOutput` compatible with existing eval pipeline
- [ ] No existing test is broken

## Execution
- **Agent Type**: coding subagent
- **Wave**: 3 (sequential -- depends on TASK_003, TASK_005, TASK_006)
- **Complexity**: Medium
