# Task 013: Build train.py -- Baseline Scorer (Mutable File)

## Context
`train.py` is the ONLY file the research agent is allowed to edit during the autoresearch loop. The baseline implementation provides a `EmailTrustScorer` class with structured explanation output (reasons array + summary, NOT CoT extraction). It uses thread-aware analysis and scores via ScoringProvider. LoRA scaffolding methods are placeholders. This task creates the initial baseline; the autoresearch agent will evolve it from there. See CURSOR_PLAN.md "Implementation Details > 9. train.py".

## Goal
Create a working baseline email trust scorer that produces structured ScorerOutput with both trust_vector and explanation fields.

## Research First
- [ ] Read CURSOR_PLAN.md section "Implementation Details > 9. train.py"
- [ ] Read `autotrust/schemas.py` for ScorerOutput, Explanation, EmailChain models
- [ ] Read `autotrust/providers/__init__.py` for ScoringProvider, TrainingProvider interfaces
- [ ] Read spec.yaml `providers.scorer` for the baseline model (Llama-3.1-8B on Hyperbolic)
- [ ] Read the structured explanation contract in CURSOR_PLAN.md

## TDD: Tests First (Red)
Write tests FIRST. They should FAIL before implementation. Note: train.py is lightly tested (the autoresearch agent modifies it).

### Unit Tests
- [ ] Test: `test_scorer_returns_scorer_output` -- score_chain() returns ScorerOutput instance -- in `tests/test_train.py`
- [ ] Test: `test_scorer_output_has_trust_vector` -- returned ScorerOutput.trust_vector has all spec axis keys -- in `tests/test_train.py`
- [ ] Test: `test_scorer_output_has_explanation` -- returned ScorerOutput.explanation has reasons (list) and summary (str) -- in `tests/test_train.py`
- [ ] Test: `test_scorer_batch` -- score_batch returns list of ScorerOutput with correct length -- in `tests/test_train.py`
- [ ] Test: `test_scorer_reasons_are_strings` -- explanation.reasons contains strings (axis names or semantic references) -- in `tests/test_train.py`

## Implementation
- [ ] Step 1: Create `train.py` at project root (NOT inside autotrust/) with:
  ```python
  class EmailTrustScorer:
      def __init__(self, provider: ScoringProvider, spec: Spec):
          self.provider = provider
          self.spec = spec

      def score_chain(self, chain: EmailChain) -> ScorerOutput:
          """Score a single email chain. Returns trust vector + structured explanation."""

      def score_batch(self, chains: list[EmailChain]) -> list[ScorerOutput]:
          """Score multiple chains."""
  ```
- [ ] Step 2: Implement `score_chain()`:
  - Build thread-aware prompt from chain (reply timing, escalation, authority shifts, persuasion progression)
  - Call `self.provider.score(prompt)` requesting structured JSON output
  - Parse response into ScorerOutput with trust_vector (dict[str, float]) and Explanation (reasons list + summary)
  - Validate trust_vector against spec axis names
- [ ] Step 3: Implement thread encoder signals in the prompt:
  - Reply timing analysis (rushed responses, unusual timing)
  - Escalation detection (increasing urgency across thread)
  - Authority shifts (who claims authority and when)
  - Persuasion progression (how manipulation builds across messages)
- [ ] Step 4: Implement `score_batch()` as sequential calls to score_chain()
- [ ] Step 5: Add LoRA scaffolding (placeholder methods):
  ```python
  def fine_tune(self, data_path: str, trainer: TrainingProvider) -> str:
      """Placeholder: LoRA fine-tune via TrainingProvider. Returns checkpoint path."""
      raise NotImplementedError("LoRA fine-tuning not yet implemented")

  def load_fine_tuned(self, checkpoint: str) -> None:
      """Placeholder: Load LoRA checkpoint."""
      raise NotImplementedError("LoRA loading not yet implemented")
  ```
- [ ] DRY check: uses providers, doesn't construct API clients directly

## TDD: Tests Pass (Green)
- [ ] All 5 unit tests pass (using mocked ScoringProvider)
- [ ] All existing tests still pass

## Acceptance Criteria
- [ ] `train.py` exists at project root
- [ ] `EmailTrustScorer.score_chain()` returns valid ScorerOutput
- [ ] Trust vector has all spec axis names as keys with float values
- [ ] Explanation has reasons (list[str]) and summary (str)
- [ ] Thread-aware prompt includes reply timing, escalation, authority, persuasion signals
- [ ] LoRA placeholder methods exist but raise NotImplementedError
- [ ] All tests pass

## Execution
- **Agent Type**: python
- **Wave**: 5 (depends on TASK_004 config, TASK_005 schemas, TASK_006 providers registry, TASK_008 hyperbolic scorer)
- **Complexity**: Medium
